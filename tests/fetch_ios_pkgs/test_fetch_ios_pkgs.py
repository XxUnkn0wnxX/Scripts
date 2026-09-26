from __future__ import annotations

import os
import plistlib
import re
import shlex
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "shell/fetch-ios-pkgs.zsh"
ZSH_PATH = os.environ.get("FETCH_IOS_PKGS_ZSH", "/bin/zsh")

if sys.platform != "darwin" or not Path("/usr/bin/osascript").is_file():
    pytest.skip("fetch-ios-pkgs tests require macOS osascript", allow_module_level=True)
if not Path(ZSH_PATH).is_file():
    pytest.skip(f"fetch-ios-pkgs tests require zsh at {ZSH_PATH}", allow_module_level=True)
assert SCRIPT_PATH.is_file(), f"Missing script: {SCRIPT_PATH}"


UTC = timezone.utc


def _shell_quote(value: Path | str) -> str:
    return shlex.quote(str(value))


def _run_zsh(body: str, *, cwd: Path, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    isolated_home = home or cwd / "home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(isolated_home)
    tmpdir = cwd / "tmp"
    tmpdir.mkdir(exist_ok=True)
    env["TMPDIR"] = str(tmpdir)
    command = f"""
# Fail closed if a source guard regresses and attempts a live transfer.
curl() {{ return 97; }}
sudo() {{ return 98; }}
usbmuxd_read_pids() {{ return 96; }}
usbmuxd_signal() {{ return 96; }}
usbmuxd_launchctl() {{ return 96; }}
source {_shell_quote(SCRIPT_PATH)}
set +e
{body}
"""
    args = [ZSH_PATH, "-f", "-c", command]
    with subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired as error:
            # A stuck shell child can retain the capture pipes after its parent
            # exits. Terminate only this test's isolated process group.
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(args, 30, output=stdout, stderr=stderr) from error
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second)


def _iso_seconds(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _product(post_date: datetime | str | None, urls: list[str], *, extra: dict | None = None) -> dict:
    product: dict = {}
    if extra:
        product.update(extra)
    product["Packages"] = [{"URL": url} for url in urls]
    if post_date is not None:
        product["PostDate"] = post_date
    return product


def _write_catalog(
    path: Path,
    products: dict[str, dict] | None = None,
    *,
    minified: bool = False,
    binary: bool = False,
    raw: bytes | None = None,
) -> Path:
    if raw is not None:
        path.write_bytes(raw)
        return path
    root = {"Products": products or {}}
    data = plistlib.dumps(
        root,
        fmt=plistlib.FMT_BINARY if binary else plistlib.FMT_XML,
        sort_keys=False,
    )
    if minified and not binary:
        data = re.sub(rb">\s+<", b"><", data)
    path.write_bytes(data)
    return path


def _select(
    catalog: Path,
    *,
    cwd: Path,
    host_version: str = "11.7.11",
) -> subprocess.CompletedProcess[str]:
    return _run_zsh(
        f"select_catalog_product {_shell_quote(catalog)} {_shell_quote(host_version)}",
        cwd=cwd,
    )


def _assert_selection(
    result: subprocess.CompletedProcess[str],
    *,
    product_id: str,
    post_date: datetime,
    core_url: str,
    mobile_url: str,
    mobile_basename: str,
) -> None:
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.splitlines() == [
        product_id,
        _iso_seconds(post_date),
        core_url,
        mobile_url,
        mobile_basename,
    ]


def _main_fixture(tmp_path: Path) -> dict[str, Path | str]:
    core_url = "https://cdn.example.invalid/actual/core/CoreTypes.pkg?sig=core#fragment"
    mobile_url = (
        "https://cdn.example.invalid/renamed/mobile/MobileDeviceOnDemandPackage.pkg"
        "?sig=mobile#fragment"
    )
    apple_kis_url = "https://cdn.example.invalid/optional/apple/AppleKIS.pkg?sig=kis#fragment"
    catalog_url = "https://catalog.example.invalid/DeveloperSeed.plist?seed=27#catalog"
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    catalog = _write_catalog(
        tmp_path / "catalog.plist",
        {
            "142-23719": _product(
                post_date,
                [
                    "https://cdn.example.invalid/metadata/MobileDeviceOnDemandPackage.smd",
                    core_url,
                    apple_kis_url,
                    mobile_url,
                ],
            )
        },
    )
    core_fixture = tmp_path / "core-source.pkg"
    mobile_fixture = tmp_path / "mobile-source.pkg"
    apple_kis_fixture = tmp_path / "apple-kis-source.pkg"
    core_fixture.write_bytes(b"core package")
    mobile_fixture.write_bytes(b"mobile package")
    apple_kis_fixture.write_bytes(b"AppleKIS package")
    return {
        "catalog": catalog,
        "catalog_url": catalog_url,
        "core_url": core_url,
        "mobile_url": mobile_url,
        "apple_kis_url": apple_kis_url,
        "core_fixture": core_fixture,
        "mobile_fixture": mobile_fixture,
        "apple_kis_fixture": apple_kis_fixture,
        "mobile_basename": "MobileDeviceOnDemandPackage.pkg",
    }


def _main_body(
    fixture: dict[str, Path | str],
    trace: Path,
    args: tuple[str, ...] = (),
    *,
    fail_url: str | None = None,
    fail_install_basename: str | None = None,
    fail_restart: bool = False,
    host_version: str = "11.7.11",
    hardware_architecture: str = "x86_64",
    print_install_action: bool = False,
) -> str:
    catalog = _shell_quote(fixture["catalog"])
    catalog_url = _shell_quote(fixture["catalog_url"])
    core_url = _shell_quote(fixture["core_url"])
    mobile_url = _shell_quote(fixture["mobile_url"])
    apple_kis_url = _shell_quote(fixture["apple_kis_url"])
    core_fixture = _shell_quote(fixture["core_fixture"])
    mobile_fixture = _shell_quote(fixture["mobile_fixture"])
    apple_kis_fixture = _shell_quote(fixture["apple_kis_fixture"])
    trace_path = _shell_quote(trace)
    fail_url_value = _shell_quote(fail_url or "")
    fail_install_value = _shell_quote(fail_install_basename or "")
    fail_restart_status = "77" if fail_restart else "0"
    host_version_value = _shell_quote(host_version)
    hardware_architecture_value = _shell_quote(hardware_architecture)
    print_install_action_value = "1" if print_install_action else "0"
    quoted_args = " ".join(_shell_quote(arg) for arg in args)
    return f"""
TRACE={trace_path}
CATALOG_URL={catalog_url}
CATALOG_FIXTURE={catalog}
CORE_URL={core_url}
CORE_FIXTURE={core_fixture}
MOBILE_URL={mobile_url}
MOBILE_FIXTURE={mobile_fixture}
APPLE_KIS_URL={apple_kis_url}
APPLE_KIS_FIXTURE={apple_kis_fixture}
FAIL_URL={fail_url_value}
FAIL_INSTALL_BASENAME={fail_install_value}
HOST_VERSION={host_version_value}
HARDWARE_ARCHITECTURE={hardware_architecture_value}
PRINT_INSTALL_ACTION={print_install_action_value}

get_catalog_url() {{
  print -r -- "$CATALOG_URL"
}}

get_macos_version() {{
  print -r -- "$HOST_VERSION"
}}

get_hardware_architecture() {{
  print -r -- "$HARDWARE_ARCHITECTURE"
}}

curl() {{
  local output="" url="" arg
  while (( $# > 0 )); do
    arg="$1"
    if [[ "$arg" == "-o" ]]; then
      shift
      (( $# > 0 )) || return 2
      output="$1"
    elif [[ "$arg" == http://* || "$arg" == https://* ]]; then
      url="$arg"
    fi
    shift
  done
  print -r -- "curl|$url|$output" >> "$TRACE"
  if [[ -n "$FAIL_URL" && "$url" == "$FAIL_URL" ]]; then
    return 55
  fi
  if [[ "$url" == "$CATALOG_URL" ]]; then
    cp "$CATALOG_FIXTURE" "$output"
    return $?
  fi
  if [[ "$url" == "$CORE_URL" ]]; then
    cp "$CORE_FIXTURE" "$output"
    return $?
  fi
  if [[ "$url" == "$MOBILE_URL" ]]; then
    cp "$MOBILE_FIXTURE" "$output"
    return $?
  fi
  if [[ "$url" == "$APPLE_KIS_URL" ]]; then
    cp "$APPLE_KIS_FIXTURE" "$output"
    return $?
  fi
  return 44
}}

install_pkg() {{
  local package_path="$1"
  print -r -- "install|$package_path" >> "$TRACE"
  if (( PRINT_INSTALL_ACTION )); then
    print -r -- "install-action|$package_path"
  fi
  if [[ "$(basename "$package_path")" == "$FAIL_INSTALL_BASENAME" ]]; then
    return 66
  fi
  [[ -f "$package_path" ]]
}}

restart_mobile_services() {{
  print -r -- "restart" >> "$TRACE"
  print -r -- "restart-action"
  return {fail_restart_status}
}}

sudo() {{
  print -r -- "sudo|$*" >> "$TRACE"
  return 99
}}

fetch_ios_pkgs_main {quoted_args}
"""


def _trace_lines(trace: Path) -> list[str]:
    return trace.read_text(encoding="utf-8").splitlines() if trace.exists() else []


def _restart_body(
    tmp_path: Path,
    trace: Path,
    *,
    initial_pids: str,
    scenario: str,
) -> str:
    state = tmp_path / f"{scenario}.state"
    sleep_count = tmp_path / f"{scenario}.sleep"
    state.write_text(initial_pids, encoding="utf-8")
    sleep_count.write_text("", encoding="utf-8")
    return f"""
TRACE={_shell_quote(trace)}
STATE={_shell_quote(state)}
SLEEP_COUNT={_shell_quote(sleep_count)}
SCENARIO={_shell_quote(scenario)}

usbmuxd_read_pids() {{
  local value
  value="$(<"$STATE")"
  if [[ "$value" == ERROR:* ]]; then
    return "${{value#ERROR:}}"
  fi
  if [[ -z "$value" || "$value" == NONE ]]; then
    return 1
  fi
  print -r -- "$value"
}}

usbmuxd_sleep() {{
  local count
  print -r -- "sleep|$1" >> "$TRACE"
  count="$(wc -l < "$SLEEP_COUNT")"
  (( count += 1 ))
  print -r -- "$count" >> "$SLEEP_COUNT"
  if [[ "$SCENARIO" == delayed && "$count" -ge 2 ]]; then
    print -r -- 456 > "$STATE"
  elif [[ "$SCENARIO" == observer-mid && "$count" -eq 1 ]]; then
    print -r -- ERROR:2 > "$STATE"
  fi
}}

usbmuxd_signal() {{
  local signal="$1"
  shift
  print -r -- "signal|$signal|$*" >> "$TRACE"
  if [[ "$SCENARIO" == signal-error ]]; then
    return 77
  fi
  if [[ "$SCENARIO" == term-fast && "$signal" == TERM ]]; then
    print -r -- 456 > "$STATE"
  elif [[ "$SCENARIO" == kick-success && "$signal" == TERM ]]; then
    :
  elif [[ "$SCENARIO" == delayed && "$signal" == TERM ]]; then
    print -r -- NONE > "$STATE"
  elif [[ "$SCENARIO" == partial-force && "$signal" == TERM ]]; then
    print -r -- 123 > "$STATE"
    print -r -- 124 >> "$STATE"
  elif [[ "$SCENARIO" == partial-force && "$signal" == KILL ]]; then
    print -r -- 456 > "$STATE"
  elif [[ "$SCENARIO" == partial-fail && "$signal" == TERM ]]; then
    print -r -- 124 > "$STATE"
    print -r -- 456 >> "$STATE"
  elif [[ "$SCENARIO" == partial-fail && "$signal" == KILL ]]; then
    print -r -- 124 > "$STATE"
    print -r -- 456 >> "$STATE"
  elif [[ "$SCENARIO" == kick-force && "$signal" == KILL ]]; then
    print -r -- 456 > "$STATE"
  fi
}}

usbmuxd_launchctl() {{
  print -r -- "launchctl|$*" >> "$TRACE"
  if [[ "$1" == kickstart ]]; then
    case "$SCENARIO" in
      no-pid-start) print -r -- 456 > "$STATE" ;;
      kick-success) print -r -- 456 > "$STATE" ;;
      partial-force)
        print -r -- 124 > "$STATE"
        print -r -- 456 >> "$STATE"
        ;;
      partial-fail) : ;;
      fallback-success|apple-fallback-success) return 1 ;;
      *) : ;;
    esac
  elif [[ "$1" == load && "$SCENARIO" == *fallback-success ]]; then
    print -r -- 456 > "$STATE"
  fi
}}

usbmuxd_plist_exists() {{
  print -r -- "plist|$1" >> "$TRACE"
  case "$SCENARIO:$1" in
    fallback-success:/Library/Apple/System/*) return 1 ;;
    fallback-success:/System/Library/*) return 0 ;;
    apple-fallback-success:*) return 0 ;;
    permanent:/Library/Apple/System/*) return 0 ;;
    missing-plist:*) return 1 ;;
    *) return 1 ;;
  esac
}}

set -euo pipefail
if restart_mobile_services; then
  result_code=0
else
  result_code=$?
fi
print -r -- "status|$result_code"
exit "$result_code"
"""


def test_source_is_side_effect_free_and_exposes_public_functions(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        'print -r -- "${+functions[select_catalog_product]} ${+functions[get_catalog_url]} '
        '${+functions[fetch_ios_pkgs_main]}"',
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "1 1 1\n"
    assert not (home / "Downloads").exists()


def test_seed_parser_strips_gzip_suffix(tmp_path: Path):
    seed = _write_catalog(
        tmp_path / "seed.plist",
        raw=plistlib.dumps(
            {"DeveloperSeed": "https://catalog.example.invalid/SeedCatalog.plist.gz"},
            fmt=plistlib.FMT_XML,
        ),
    )
    original = seed.read_bytes()
    result = _run_zsh(f"read_catalog_data seed {_shell_quote(seed)}", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "https://catalog.example.invalid/SeedCatalog.plist\n"
    assert seed.read_bytes() == original


@pytest.mark.parametrize(
    "seed_value",
    (None, "ftp://catalog.example.invalid/SeedCatalog.plist", "not a URL"),
)
def test_seed_parser_rejects_missing_or_invalid_developer_seed(tmp_path: Path, seed_value: str | None):
    root = {} if seed_value is None else {"DeveloperSeed": seed_value}
    seed = _write_catalog(
        tmp_path / "invalid-seed.plist",
        raw=plistlib.dumps(root, fmt=plistlib.FMT_XML),
    )
    result = _run_zsh(f"read_catalog_data seed {_shell_quote(seed)}", cwd=tmp_path)
    assert result.returncode != 0


def test_install_pkg_calls_installer_with_expected_flags_and_stops_on_failure(tmp_path: Path):
    package_path = tmp_path / "CoreTypes.pkg"
    package_path.write_bytes(b"package")
    trace = tmp_path / "installer.trace"
    body = f"""
TRACE={_shell_quote(trace)}
fake_installer() {{
  print -r -- "installer|$*" >> "$TRACE"
  return ${{FAKE_STATUS:-0}}
}}
INSTALLER_CMD=(fake_installer)
FAKE_STATUS=0
install_pkg {_shell_quote(package_path)}
first_status=$?
FAKE_STATUS=7
install_pkg {_shell_quote(package_path)}
second_status=$?
print -r -- "status|$first_status|$second_status"
"""
    result = _run_zsh(body, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "status|0|1" in result.stdout
    assert _trace_lines(trace) == [
        f"installer|-verboseR -pkg {package_path} -target /",
        f"installer|-verboseR -pkg {package_path} -target /",
    ]


@pytest.mark.parametrize("flag", ("--help", "-h"))
def test_help_is_side_effect_free(tmp_path: Path, flag: str):
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        f"fetch_ios_pkgs_main {_shell_quote(flag)}",
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout + result.stderr
    assert not (home / "Downloads").exists()


@pytest.mark.parametrize("args", (("--unknown",), ("--dry-run", "--download-only")))
def test_invalid_cli_arguments_fail_before_network_or_directories(tmp_path: Path, args: tuple[str, ...]):
    home = tmp_path / "home"
    home.mkdir()
    trace = tmp_path / "trace.log"
    body = f"""
TRACE={_shell_quote(trace)}
get_catalog_url() {{ print -r -- https://catalog.example.invalid/catalog.plist; }}
curl() {{ print -r -- called >> "$TRACE"; return 99; }}
fetch_ios_pkgs_main {' '.join(_shell_quote(arg) for arg in args)}
"""
    result = _run_zsh(body, cwd=tmp_path, home=home)
    assert result.returncode != 0
    assert not trace.exists()
    assert not (home / "Downloads").exists()


def test_selector_accepts_old_mobiledevice_name(tmp_path: Path):
    post_date = _utc(2026, 8, 1, 2, 3, 4)
    core_url = "https://cdn.example.invalid/old/core/CoreTypes.pkg?old=1#core"
    mobile_url = "https://cdn.example.invalid/old/mobile/MobileDeviceOnDemand.pkg?old=1#mobile"
    catalog = _write_catalog(
        tmp_path / "old.plist",
        {"100-old": _product(post_date, [core_url, mobile_url])},
    )
    _assert_selection(
        _select(catalog, cwd=tmp_path),
        product_id="100-old",
        post_date=post_date,
        core_url=core_url,
        mobile_url=mobile_url,
        mobile_basename="MobileDeviceOnDemand.pkg",
    )


@pytest.mark.parametrize("minified", (False, True))
@pytest.mark.parametrize("date_first", (False, True))
def test_selector_keeps_product_urls_and_date_together_across_key_order_and_xml_format(
    tmp_path: Path, minified: bool, date_first: bool
):
    old_date = _utc(2026, 8, 1, 2, 3, 4)
    new_date = _utc(2026, 9, 14, 17, 26, 37)
    old_core = "https://cdn.example.invalid/old/CoreTypes.pkg"
    old_mobile = "https://cdn.example.invalid/old/MobileDeviceOnDemand.pkg"
    new_core = "https://cdn.example.invalid/new/different/CoreTypes.pkg?token=new#core"
    new_mobile = "https://cdn.example.invalid/new/MobileDeviceOnDemandPackage.pkg?token=new#mobile"
    products = {
        "142-23719": _product(new_date, [new_mobile, "https://cdn.example.invalid/new/AppleKIS.pkg", new_core]),
        "100-old": _product(old_date, [old_core, old_mobile]),
    }
    if date_first:
        products = {key: dict(reversed(list(value.items()))) for key, value in products.items()}
    catalog = _write_catalog(tmp_path / "ordered.plist", products, minified=minified)
    _assert_selection(
        _select(catalog, cwd=tmp_path),
        product_id="142-23719",
        post_date=new_date,
        core_url=new_core,
        mobile_url=new_mobile,
        mobile_basename="MobileDeviceOnDemandPackage.pkg",
    )


def test_selector_deduplicates_identical_package_urls(tmp_path: Path):
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    core_url = "https://cdn.example.invalid/pair/CoreTypes.pkg?same=1#core"
    mobile_url = "https://cdn.example.invalid/pair/MobileDeviceOnDemandPackage.pkg?same=1#mobile"
    catalog = _write_catalog(
        tmp_path / "duplicates.plist",
        {"100-pair": _product(post_date, [mobile_url, core_url, mobile_url, core_url])},
    )
    _assert_selection(
        _select(catalog, cwd=tmp_path),
        product_id="100-pair",
        post_date=post_date,
        core_url=core_url,
        mobile_url=mobile_url,
        mobile_basename="MobileDeviceOnDemandPackage.pkg",
    )


def test_selector_accepts_native_binary_plist(tmp_path: Path):
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    core_url = "https://cdn.example.invalid/binary/CoreTypes.pkg"
    mobile_url = "https://cdn.example.invalid/binary/MobileDeviceOnDemandPackage.pkg"
    catalog = _write_catalog(
        tmp_path / "binary.plist",
        {"100-binary": _product(post_date, [core_url, mobile_url])},
        binary=True,
    )
    _assert_selection(
        _select(catalog, cwd=tmp_path),
        product_id="100-binary",
        post_date=post_date,
        core_url=core_url,
        mobile_url=mobile_url,
        mobile_basename="MobileDeviceOnDemandPackage.pkg",
    )


@pytest.mark.parametrize("ambiguous", ("mobile", "core"))
def test_selector_rejects_ambiguous_differing_urls(tmp_path: Path, ambiguous: str):
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    mobile_one = "https://cdn.example.invalid/a/MobileDeviceOnDemandPackage.pkg"
    mobile_two = "https://cdn.example.invalid/b/MobileDeviceOnDemandPackage.pkg"
    core_one = "https://cdn.example.invalid/a/CoreTypes.pkg"
    core_two = "https://cdn.example.invalid/b/CoreTypes.pkg"
    urls = [mobile_one, core_one]
    if ambiguous == "mobile":
        urls = [mobile_one, core_one, mobile_two]
    else:
        urls = [mobile_one, core_one, core_two]
    catalog = _write_catalog(tmp_path / f"ambiguous-{ambiguous}.plist", {"100-pair": _product(post_date, urls)})
    result = _select(catalog, cwd=tmp_path)
    assert result.returncode != 0
    assert "warning:" in result.stderr.lower()
    assert len(result.stdout.splitlines()) != 5


@pytest.mark.parametrize(
    "products",
    (
        {"100-no-core": _product(_utc(2026, 9, 1), ["https://cdn.example.invalid/MobileDeviceOnDemand.pkg"])},
        {"100-invalid-date": _product("not-a-date", [
            "https://cdn.example.invalid/CoreTypes.pkg",
            "https://cdn.example.invalid/MobileDeviceOnDemand.pkg",
        ])},
        {"100-missing-date": _product(None, [
            "https://cdn.example.invalid/CoreTypes.pkg",
            "https://cdn.example.invalid/MobileDeviceOnDemand.pkg",
        ])},
    ),
)
def test_selector_rejects_missing_or_invalid_product_metadata(tmp_path: Path, products: dict[str, dict]):
    result = _select(_write_catalog(tmp_path / "invalid.plist", products), cwd=tmp_path)
    assert result.returncode != 0
    assert "warning:" in result.stderr.lower()


@pytest.mark.parametrize(
    "raw",
    (
        b"",
        b"not a plist",
        b"<?xml version=\"1.0\"?><plist version=\"1.0\"><dict/></plist>",
        plistlib.dumps({"Products": {}}, fmt=plistlib.FMT_XML),
    ),
)
def test_selector_rejects_empty_malformed_or_productless_catalogs(tmp_path: Path, raw: bytes):
    result = _select(_write_catalog(tmp_path / "bad.plist", raw=raw), cwd=tmp_path)
    assert result.returncode != 0


def test_selector_rejects_non_http_package_urls(tmp_path: Path):
    post_date = _utc(2026, 9, 14)
    catalog = _write_catalog(
        tmp_path / "non-http.plist",
        {
            "100-pair": _product(
                post_date,
                [
                    "ftp://cdn.example.invalid/CoreTypes.pkg",
                    "ftp://cdn.example.invalid/MobileDeviceOnDemand.pkg",
                ],
            )
        },
    )
    result = _select(catalog, cwd=tmp_path)
    assert result.returncode != 0


def test_selector_warns_when_newest_product_is_incomplete_and_uses_valid_pair(tmp_path: Path):
    old_date = _utc(2026, 8, 1)
    core_url = "https://cdn.example.invalid/old/CoreTypes.pkg"
    mobile_url = "https://cdn.example.invalid/old/MobileDeviceOnDemand.pkg"
    catalog = _write_catalog(tmp_path / "incomplete-newest.plist", {
        "new-incomplete": _product(_utc(2026, 9, 14), [
            "https://cdn.example.invalid/new/MobileDeviceOnDemandPackage.pkg",
        ]),
        "old-complete": _product(old_date, [core_url, mobile_url]),
    })
    result = _select(catalog, cwd=tmp_path)
    _assert_selection(result, product_id="old-complete", post_date=old_date,
                      core_url=core_url, mobile_url=mobile_url,
                      mobile_basename="MobileDeviceOnDemand.pkg")
    assert "Skipping product" in result.stderr and "new-incomplete" in result.stderr


def test_selector_info_skips_older_unknown_mobile_package_after_newer_valid_selection(tmp_path: Path):
    unknown_name = "MobileDeviceSU2.pkg"
    old_date = _utc(2022, 4, 1)
    new_date = _utc(2026, 9, 14, 17, 26, 37)
    old_core = "https://cdn.example.invalid/old/CoreTypes.pkg"
    new_core = "https://cdn.example.invalid/new/CoreTypes.pkg"
    new_mobile = "https://cdn.example.invalid/new/MobileDeviceOnDemandPackage.pkg"
    catalog = _write_catalog(
        tmp_path / "older-unknown.plist",
        {
            "012-08532": _product(old_date, [old_core, f"https://cdn.example.invalid/old/{unknown_name}"]),
            "142-23719": _product(new_date, [new_core, new_mobile]),
        },
    )
    result = _select(catalog, cwd=tmp_path)
    _assert_selection(
        result,
        product_id="142-23719",
        post_date=new_date,
        core_url=new_core,
        mobile_url=new_mobile,
        mobile_basename="MobileDeviceOnDemandPackage.pkg",
    )
    diagnostic = result.stderr.lower()
    assert "info:" in diagnostic
    assert unknown_name.lower() in diagnostic
    assert "older" in diagnostic and "newer" in diagnostic
    assert re.search(r"no action|not needed", diagnostic)
    assert "warning:" not in diagnostic


@pytest.mark.parametrize("unknown_date", (_utc(2026, 10, 1), _utc(2026, 9, 14, 17, 26, 37)))
def test_selector_warns_when_unknown_mobile_package_is_newer_or_equal(
    tmp_path: Path, unknown_date: datetime
):
    unknown_name = "MobileDeviceSU2.pkg"
    valid_date = _utc(2026, 9, 14, 17, 26, 37)
    valid_core = "https://cdn.example.invalid/valid/CoreTypes.pkg"
    valid_mobile = "https://cdn.example.invalid/valid/MobileDeviceOnDemand.pkg"
    catalog = _write_catalog(
        tmp_path / "unknown-current-or-newer.plist",
        {
            "012-08532": _product(
                unknown_date,
                ["https://cdn.example.invalid/unknown/CoreTypes.pkg", f"https://cdn.example.invalid/unknown/{unknown_name}"],
            ),
            "142-23719": _product(valid_date, [valid_core, valid_mobile]),
        },
    )
    result = _select(catalog, cwd=tmp_path)
    _assert_selection(
        result,
        product_id="142-23719",
        post_date=valid_date,
        core_url=valid_core,
        mobile_url=valid_mobile,
        mobile_basename="MobileDeviceOnDemand.pkg",
    )
    diagnostic = result.stderr.lower()
    assert "warning:" in diagnostic
    assert "info:" not in diagnostic
    assert unknown_name.lower() in diagnostic
    assert any(term in diagnostic for term in ("newer", "latest", "potential"))
    assert any(term in diagnostic for term in ("cannot", "unable", "may not", "not selected", "not usable"))


def test_selector_warns_for_unknown_mobile_package_with_invalid_date(tmp_path: Path):
    unknown_name = "MobileDeviceSU2.pkg"
    valid_date = _utc(2026, 9, 14, 17, 26, 37)
    valid_core = "https://cdn.example.invalid/valid/CoreTypes.pkg"
    valid_mobile = "https://cdn.example.invalid/valid/MobileDeviceOnDemand.pkg"
    catalog = _write_catalog(
        tmp_path / "unknown-invalid-date.plist",
        {
            "012-08532": _product(
                "not-a-date",
                ["https://cdn.example.invalid/unknown/CoreTypes.pkg", f"https://cdn.example.invalid/unknown/{unknown_name}"],
            ),
            "142-23719": _product(valid_date, [valid_core, valid_mobile]),
        },
    )
    result = _select(catalog, cwd=tmp_path)
    _assert_selection(
        result,
        product_id="142-23719",
        post_date=valid_date,
        core_url=valid_core,
        mobile_url=valid_mobile,
        mobile_basename="MobileDeviceOnDemand.pkg",
    )
    diagnostic = result.stderr.lower()
    assert "warning:" in diagnostic
    assert "info:" not in diagnostic
    assert "date" in diagnostic or "postdate" in diagnostic


def test_selector_warns_and_fails_when_only_unknown_mobile_package_exists(tmp_path: Path):
    unknown_name = "MobileDeviceSU2.pkg"
    catalog = _write_catalog(
        tmp_path / "only-unknown.plist",
        {
            "012-08532": _product(
                _utc(2022, 4, 1),
                ["https://cdn.example.invalid/unknown/CoreTypes.pkg", f"https://cdn.example.invalid/unknown/{unknown_name}"],
            ),
        },
    )
    result = _select(catalog, cwd=tmp_path)
    assert result.returncode != 0
    diagnostic = result.stderr.lower()
    assert "warning:" in diagnostic
    assert unknown_name.lower() in diagnostic
    assert "info:" not in diagnostic


def test_selector_excludes_metadata_and_applekis_and_uses_exact_path_basename(tmp_path: Path):
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    core_url = "https://cdn.example.invalid/a/deep/CoreTypes.pkg?download=1#core"
    mobile_url = "https://cdn.example.invalid/b/deep/MobileDeviceOnDemandPackage.pkg?download=1#mobile"
    catalog = _write_catalog(
        tmp_path / "packages.plist",
        {
            "100-pair": _product(
                post_date,
                [
                    "https://cdn.example.invalid/meta/MobileDeviceOnDemandPackage.pkm",
                    "https://cdn.example.invalid/meta/MobileDeviceOnDemandPackage.smd",
                    "https://cdn.example.invalid/other/AppleKIS.pkg",
                    core_url,
                    mobile_url,
                ],
            )
        },
    )
    _assert_selection(
        _select(catalog, cwd=tmp_path),
        product_id="100-pair",
        post_date=post_date,
        core_url=core_url,
        mobile_url=mobile_url,
        mobile_basename="MobileDeviceOnDemandPackage.pkg",
    )


@pytest.mark.parametrize("host_version", ("13.0", "14.6.1", "15.0.0", "26.0", "27.0", "28.0"))
def test_selector_includes_same_product_applekis_on_modern_macos(tmp_path: Path, host_version: str):
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    core_url = "https://cdn.example.invalid/core/CoreTypes.pkg"
    mobile_url = "https://cdn.example.invalid/mobile/MobileDeviceOnDemandPackage.pkg"
    apple_kis_url = "https://cdn.example.invalid/apple/AppleKIS.pkg?token=modern#kis"
    catalog = _write_catalog(
        tmp_path / "modern.plist",
        {"100-modern": _product(post_date, [core_url, mobile_url, apple_kis_url])},
    )
    result = _select(catalog, cwd=tmp_path, host_version=host_version)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "100-modern",
        _iso_seconds(post_date),
        core_url,
        mobile_url,
        "MobileDeviceOnDemandPackage.pkg",
        apple_kis_url,
    ]


def test_selector_allows_missing_applekis_on_modern_macos(tmp_path: Path):
    post_date = _utc(2026, 9, 14)
    core_url = "https://cdn.example.invalid/core/CoreTypes.pkg"
    mobile_url = "https://cdn.example.invalid/mobile/MobileDeviceOnDemandPackage.pkg"
    catalog = _write_catalog(
        tmp_path / "modern-no-kis.plist",
        {"100-modern": _product(post_date, [core_url, mobile_url])},
    )
    result = _select(catalog, cwd=tmp_path, host_version="13.0")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 5


def test_selector_deduplicates_identical_applekis_on_modern_macos(tmp_path: Path):
    post_date = _utc(2026, 9, 14)
    core_url = "https://cdn.example.invalid/core/CoreTypes.pkg"
    mobile_url = "https://cdn.example.invalid/mobile/MobileDeviceOnDemandPackage.pkg"
    apple_kis_url = "https://cdn.example.invalid/apple/AppleKIS.pkg"
    catalog = _write_catalog(
        tmp_path / "modern-duplicate-kis.plist",
        {"100-modern": _product(post_date, [core_url, mobile_url, apple_kis_url, apple_kis_url])},
    )
    result = _select(catalog, cwd=tmp_path, host_version="13.0")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == apple_kis_url
    assert "duplicate package URLs" in result.stderr


@pytest.mark.parametrize(
    "apple_kis_urls",
    (
        [
            "https://cdn.example.invalid/a/AppleKIS.pkg",
            "https://cdn.example.invalid/b/AppleKIS.pkg",
        ],
        ["ftp://cdn.example.invalid/a/AppleKIS.pkg"],
    ),
)
def test_selector_rejects_ambiguous_or_invalid_applekis_on_modern_macos(
    tmp_path: Path, apple_kis_urls: list[str]
):
    post_date = _utc(2026, 9, 14)
    urls = [
        "https://cdn.example.invalid/core/CoreTypes.pkg",
        "https://cdn.example.invalid/mobile/MobileDeviceOnDemandPackage.pkg",
        *apple_kis_urls,
    ]
    result = _select(
        _write_catalog(tmp_path / "modern-invalid-kis.plist", {"100-modern": _product(post_date, urls)}),
        cwd=tmp_path,
        host_version="13.0",
    )
    assert result.returncode != 0


def test_selector_ignores_ambiguous_or_invalid_applekis_on_older_macos(tmp_path: Path):
    post_date = _utc(2026, 9, 14)
    core_url = "https://cdn.example.invalid/core/CoreTypes.pkg"
    mobile_url = "https://cdn.example.invalid/mobile/MobileDeviceOnDemandPackage.pkg"
    catalog = _write_catalog(
        tmp_path / "old-bad-kis.plist",
        {
            "100-old": _product(
                post_date,
                [
                    core_url,
                    mobile_url,
                    "https://cdn.example.invalid/a/AppleKIS.pkg",
                    "https://cdn.example.invalid/b/AppleKIS.pkg",
                    "ftp://cdn.example.invalid/bad/AppleKIS.pkg",
                ],
            )
        },
    )
    result = _select(catalog, cwd=tmp_path, host_version="12.7")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 5


@pytest.mark.parametrize("host_version", ("13", "13.x", "unknown"))
def test_selector_rejects_invalid_host_version(tmp_path: Path, host_version: str):
    post_date = _utc(2026, 9, 14)
    catalog = _write_catalog(
        tmp_path / "invalid-host.plist",
        {
            "100-pair": _product(
                post_date,
                [
                    "https://cdn.example.invalid/core/CoreTypes.pkg",
                    "https://cdn.example.invalid/mobile/MobileDeviceOnDemandPackage.pkg",
                ],
            )
        },
    )
    result = _select(catalog, cwd=tmp_path, host_version=host_version)
    assert result.returncode != 0


def test_selector_ties_choose_ascending_product_id_and_warn(tmp_path: Path):
    post_date = _utc(2026, 9, 14, 17, 26, 37)
    low_core = "https://cdn.example.invalid/low/CoreTypes.pkg"
    low_mobile = "https://cdn.example.invalid/low/MobileDeviceOnDemand.pkg"
    high_core = "https://cdn.example.invalid/high/CoreTypes.pkg"
    high_mobile = "https://cdn.example.invalid/high/MobileDeviceOnDemand.pkg"
    catalog = _write_catalog(
        tmp_path / "tie.plist",
        {
            "200-high": _product(post_date, [high_core, high_mobile]),
            "100-low": _product(post_date, [low_core, low_mobile]),
        },
    )
    result = _select(catalog, cwd=tmp_path)
    _assert_selection(
        result,
        product_id="100-low",
        post_date=post_date,
        core_url=low_core,
        mobile_url=low_mobile,
        mobile_basename="MobileDeviceOnDemand.pkg",
    )
    assert re.search(r"tie|equal|same", result.stderr, re.IGNORECASE)


@pytest.mark.parametrize("mode", ("--dry-run", "--download-only", ""))
def test_main_modes_print_selected_urls_and_only_default_installs(tmp_path: Path, mode: str):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / f"{mode or 'default'}.trace"
    home = tmp_path / f"home-{mode or 'default'}"
    home.mkdir()
    args = (mode,) if mode else ()
    result = _run_zsh(_main_body(fixture, trace, args), cwd=tmp_path, home=home)
    assert result.returncode == 0, result.stderr or result.stdout
    output = result.stdout + result.stderr
    assert fixture["core_url"] in output
    assert fixture["mobile_url"] in output
    lines = _trace_lines(trace)
    assert sum(line.startswith("curl|") for line in lines) == (1 if mode == "--dry-run" else 3)
    assert not any(line.startswith("sudo|") for line in lines)
    downloads = home / "Downloads"
    if mode == "--dry-run":
        assert "administrator password" not in output
        assert "Password is invisible" not in output
        assert not downloads.exists()
        assert not any(line.startswith(("install|", "restart")) for line in lines)
    elif mode == "--download-only":
        assert "administrator password" not in output
        assert "Password is invisible" not in output
        assert (downloads / "CoreTypes.pkg").is_file()
        assert (downloads / "MobileDeviceOnDemandPackage.pkg").is_file()
        assert not any(line.startswith(("install|", "restart")) for line in lines)
        assert not list(downloads.glob(".fetch-ios-pkgs.*"))
    else:
        if os.geteuid() == 0:
            assert "administrator password" not in output
            assert "Password is invisible" not in output
        else:
            assert "administrator password" in output
            assert "Password is invisible as you type." in output
        assert [Path(line.split("|", 1)[1]).name for line in lines if line.startswith("install|")] == [
            "CoreTypes.pkg",
            "MobileDeviceOnDemandPackage.pkg",
        ]
        install_positions = [index for index, line in enumerate(lines) if line.startswith("install|")]
        download_positions = [index for index, line in enumerate(lines) if line.startswith("curl|")][1:]
        assert max(download_positions) < min(install_positions)
        assert lines[-1] == "restart"


def test_normal_install_notice_precedes_first_admin_action_and_lists_selected_packages(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "install-notice.trace"
    home = tmp_path / "install-notice-home"
    home.mkdir()
    result = _run_zsh(
        _main_body(
            fixture,
            trace,
            host_version="14.6.1",
            hardware_architecture="arm64",
            print_install_action=True,
        ),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    output_lines = result.stdout.splitlines()
    first_action = next(index for index, line in enumerate(output_lines) if line.startswith("install-action|"))
    notice_index = output_lines.index("Normal install mode will install these packages into system locations on /:")
    assert notice_index < first_action
    assert output_lines[notice_index + 1 : notice_index + 4] == [
        "  CoreTypes.pkg",
        "  MobileDeviceOnDemandPackage.pkg",
        "  AppleKIS.pkg",
    ]
    service_notice = (
        "Restarting usbmuxd to reload device support; service recovery may ask for an administrator password again."
        if os.geteuid() != 0
        else "Restarting usbmuxd to reload device support."
    )
    service_notice_index = output_lines.index(service_notice)
    restart_action_index = output_lines.index("restart-action")
    assert service_notice_index < restart_action_index
    if os.geteuid() != 0:
        assert "The installer may ask for an administrator password for these changes." in result.stdout
        assert "Password is invisible as you type." in result.stdout
        assert output_lines.count("Password is invisible as you type.") == 2
    else:
        assert "administrator password" not in result.stdout


@pytest.mark.parametrize("mode", ("--dry-run", "--download-only", ""))
def test_modern_main_selects_and_processes_applekis_in_order(tmp_path: Path, mode: str):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / f"modern-{mode or 'default'}.trace"
    home = tmp_path / f"modern-home-{mode or 'default'}"
    home.mkdir()
    args = (mode,) if mode else ()
    result = _run_zsh(
        _main_body(
            fixture,
            trace,
            args,
            host_version="14.6.1",
            hardware_architecture="arm64",
        ),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    output = result.stdout + result.stderr
    assert "macOS version: 14.6.1" in output
    assert "Hardware architecture: arm64" in output
    assert fixture["apple_kis_url"] in output
    lines = _trace_lines(trace)
    assert sum(line.startswith("curl|") for line in lines) == (1 if mode == "--dry-run" else 4)
    if mode != "--dry-run":
        assert [line.split("|", 2)[1] for line in lines if line.startswith("curl|")][1:] == [
            str(fixture["mobile_url"]),
            str(fixture["core_url"]),
            str(fixture["apple_kis_url"]),
        ]
    downloads = home / "Downloads"
    if mode == "--dry-run":
        assert not downloads.exists()
        assert not any(line.startswith(("install|", "restart")) for line in lines)
    elif mode == "--download-only":
        assert {path.name for path in downloads.iterdir()} == {
            "CoreTypes.pkg",
            "MobileDeviceOnDemandPackage.pkg",
            "AppleKIS.pkg",
        }
        assert not any(line.startswith(("install|", "restart")) for line in lines)
    else:
        assert [Path(line.split("|", 1)[1]).name for line in lines if line.startswith("install|")] == [
            "CoreTypes.pkg",
            "MobileDeviceOnDemandPackage.pkg",
            "AppleKIS.pkg",
        ]
        install_positions = [index for index, line in enumerate(lines) if line.startswith("install|")]
        download_positions = [index for index, line in enumerate(lines) if line.startswith("curl|")][1:]
        assert max(download_positions) < min(install_positions)
        assert lines[-1] == "restart"


def test_modern_third_download_failure_prevents_install_and_preserves_completed_files(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "modern-kis-failure.trace"
    home = tmp_path / "home"
    downloads = home / "Downloads"
    downloads.mkdir(parents=True)
    (downloads / "CoreTypes.pkg").write_bytes(b"existing core")
    (downloads / "MobileDeviceOnDemandPackage.pkg").write_bytes(b"existing mobile")
    result = _run_zsh(
        _main_body(
            fixture,
            trace,
            fail_url=str(fixture["apple_kis_url"]),
            host_version="15.0.0",
            hardware_architecture="arm64",
        ),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode != 0
    lines = _trace_lines(trace)
    assert [line.split("|", 2)[1] for line in lines if line.startswith("curl|")] == [
        str(fixture["catalog_url"]),
        str(fixture["mobile_url"]),
        str(fixture["core_url"]),
        str(fixture["apple_kis_url"]),
    ]
    assert not any(line.startswith(("install|", "restart", "sudo|")) for line in lines)
    assert (downloads / "CoreTypes.pkg").read_bytes() == b"existing core"
    assert (downloads / "MobileDeviceOnDemandPackage.pkg").read_bytes() == b"existing mobile"
    assert not (downloads / "AppleKIS.pkg").exists()
    assert not list(downloads.glob(".fetch-ios-pkgs.*"))


def test_modern_applekis_installer_failure_stops_before_restart(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "modern-kis-install-failure.trace"
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        _main_body(
            fixture,
            trace,
            fail_install_basename="AppleKIS.pkg",
            host_version="26.0",
            hardware_architecture="arm64",
        ),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode != 0
    lines = _trace_lines(trace)
    assert sum(line.startswith("curl|") for line in lines) == 4
    assert [Path(line.split("|", 1)[1]).name for line in lines if line.startswith("install|")] == [
        "CoreTypes.pkg",
        "MobileDeviceOnDemandPackage.pkg",
        "AppleKIS.pkg",
    ]
    assert not any(line.startswith(("restart", "sudo|")) for line in lines)


def test_main_host_version_failure_stops_before_catalog_fetch(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "host-version-failure.trace"
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        _main_body(fixture, trace, host_version="not-a-version"),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode != 0
    assert "Failed to determine a valid macOS product version." in result.stderr
    assert not trace.exists()
    assert not (home / "Downloads").exists()


def test_main_unsupported_architecture_stops_before_catalog_fetch(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "architecture-failure.trace"
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        _main_body(fixture, trace, hardware_architecture="riscv64"),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode != 0
    assert "Failed to determine a supported hardware architecture." in result.stderr
    assert not trace.exists()
    assert not (home / "Downloads").exists()


def test_second_download_failure_stops_before_install_and_preserves_final_files(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "failure.trace"
    home = tmp_path / "home"
    downloads = home / "Downloads"
    downloads.mkdir(parents=True)
    (downloads / "CoreTypes.pkg").write_bytes(b"pre-existing core")
    result = _run_zsh(
        _main_body(fixture, trace, fail_url=str(fixture["core_url"])),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode != 0
    lines = _trace_lines(trace)
    assert [line.split("|", 2)[1] for line in lines if line.startswith("curl|")] == [
        str(fixture["catalog_url"]),
        str(fixture["mobile_url"]),
        str(fixture["core_url"]),
    ]
    assert not any(line.startswith(("install|", "restart", "sudo|")) for line in lines)
    assert (downloads / "CoreTypes.pkg").read_bytes() == b"pre-existing core"
    assert not (downloads / "MobileDeviceOnDemandPackage.pkg").exists()
    assert not list(downloads.glob(".fetch-ios-pkgs.*"))


@pytest.mark.parametrize("stage", ("catalog_url", "mobile_url", "invalid_catalog"))
def test_earlier_fetch_or_parse_failure_stops_before_installation(tmp_path: Path, stage: str):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "early-failure.trace"
    if stage == "invalid_catalog":
        Path(fixture["catalog"]).write_bytes(b"not a plist")
        fail_url = None
    else:
        fail_url = str(fixture[stage])
    result = _run_zsh(_main_body(fixture, trace, fail_url=fail_url), cwd=tmp_path)
    assert result.returncode != 0
    lines = _trace_lines(trace)
    assert not any(line.startswith(("install|", "restart", "sudo|")) for line in lines)
    assert len(lines) == (2 if stage == "mobile_url" else 1)
    assert not list((tmp_path / "tmp").iterdir())
    downloads = tmp_path / "home/Downloads"
    assert not downloads.exists() or not list(downloads.iterdir())


def test_installer_failure_stops_before_service_restart(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "installer-failure.trace"
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        _main_body(
            fixture,
            trace,
            fail_install_basename="CoreTypes.pkg",
        ),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode != 0
    lines = _trace_lines(trace)
    assert sum(line.startswith("curl|") for line in lines) == 3
    assert [Path(line.split("|", 1)[1]).name for line in lines if line.startswith("install|")] == [
        "CoreTypes.pkg"
    ]
    assert not any(line.startswith(("restart", "sudo|")) for line in lines)
    assert (home / "Downloads/CoreTypes.pkg").is_file()
    assert (home / "Downloads/MobileDeviceOnDemandPackage.pkg").is_file()


def _run_restart(tmp_path: Path, *, initial_pids: str, scenario: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    trace = tmp_path / f"{scenario}.trace"
    result = _run_zsh(
        _restart_body(tmp_path, trace, initial_pids=initial_pids, scenario=scenario),
        cwd=tmp_path,
    )
    return result, _trace_lines(trace)


@pytest.mark.parametrize(
    "sysctl_result, sysctl_status, translation_result, translation_status, uname_result, expected",
    (
        ("1", 0, "", 99, "x86_64", "arm64"),
        ("0", 0, "1", 0, "x86_64", "arm64"),
        ("", 1, "1", 0, "x86_64", "arm64"),
        ("", 1, "", 1, "arm64e", "arm64"),
        ("", 1, "", 1, "x86_64", "x86_64"),
    ),
)
def test_hardware_architecture_prefers_arm_capability_and_normalizes_fallback(
    tmp_path: Path,
    sysctl_result: str,
    sysctl_status: int,
    translation_result: str,
    translation_status: int,
    uname_result: str,
    expected: str,
):
    body = f"""
read_arm64_capability() {{ print -r -- {_shell_quote(sysctl_result)}; return {sysctl_status}; }}
read_rosetta_translation() {{ print -r -- {_shell_quote(translation_result)}; return {translation_status}; }}
read_uname_architecture() {{ print -r -- {_shell_quote(uname_result)}; return 0; }}
get_hardware_architecture
"""
    result = _run_zsh(body, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{expected}\n"


def test_hardware_architecture_rejects_unsupported_uname(tmp_path: Path):
    body = """
read_arm64_capability() { print -r -- 0; return 0; }
read_rosetta_translation() { print -r -- unknown; return 0; }
read_uname_architecture() { print -r -- riscv64; return 0; }
get_hardware_architecture
"""
    result = _run_zsh(body, cwd=tmp_path)
    assert result.returncode != 0
    assert "Unsupported hardware architecture" in result.stderr


def test_hardware_architecture_observation_failure_is_non_success(tmp_path: Path):
    body = """
read_arm64_capability() { return 1; }
read_rosetta_translation() { return 2; }
read_uname_architecture() { return 2; }
get_hardware_architecture
"""
    result = _run_zsh(body, cwd=tmp_path)
    assert result.returncode != 0
    assert "Failed to determine the hardware architecture" in result.stderr


@pytest.mark.parametrize("readable_case", ("first", "current", "versioned", "missing"))
def test_seed_catalog_locator_uses_readable_paths_in_order(tmp_path: Path, readable_case: str):
    trace = tmp_path / "seed-locator.trace"
    body = f"""
TRACE={_shell_quote(trace)}
seed_catalog_readable() {{
  print -r -- "check|$1" >> "$TRACE"
  case "{readable_case}:$1" in
    first:/System/Library/PrivateFrameworks/Seeding.framework/Resources/*) return 0 ;;
    current:/System/Library/PrivateFrameworks/Seeding.framework/Versions/Current/*) return 0 ;;
    versioned:/System/Library/PrivateFrameworks/Seeding.framework/Versions/A/*) return 0 ;;
    *) return 1 ;;
  esac
}}
read_catalog_data() {{ print -r -- "selected|$2"; }}
get_catalog_url
"""
    result = _run_zsh(body, cwd=tmp_path)
    lines = _trace_lines(trace)
    paths = [line.split("|", 1)[1] for line in lines]
    first_path = "/System/Library/PrivateFrameworks/Seeding.framework/Resources/SeedCatalogs.plist"
    current_path = "/System/Library/PrivateFrameworks/Seeding.framework/Versions/Current/Resources/SeedCatalogs.plist"
    versioned_path = "/System/Library/PrivateFrameworks/Seeding.framework/Versions/A/Resources/SeedCatalogs.plist"
    if readable_case == "missing":
        assert result.returncode != 0
        assert "Could not locate a readable SeedCatalogs.plist." in result.stderr
        assert result.stdout == ""
        assert paths == [first_path, current_path, versioned_path]
    else:
        assert result.returncode == 0, result.stderr
        expected_path = {"first": first_path, "current": current_path, "versioned": versioned_path}[readable_case]
        assert result.stdout == f"selected|{expected_path}\n"
        assert paths[-1] == expected_path
        assert paths == [first_path, current_path, versioned_path][: paths.index(expected_path) + 1]


def test_seed_catalog_readable_requires_regular_file_and_accepts_symlink(tmp_path: Path):
    regular = tmp_path / "SeedCatalogs.plist"
    regular.write_bytes(b"plist")
    directory = tmp_path / "directory"
    directory.mkdir()
    link = tmp_path / "SeedCatalogs-link.plist"
    link.symlink_to(regular)
    body = f"""
for candidate in {_shell_quote(regular)} {_shell_quote(directory)} {_shell_quote(link)}; do
  if seed_catalog_readable "$candidate"; then
    print -r -- "yes|$candidate"
  else
    print -r -- "no|$candidate"
  fi
done
"""
    result = _run_zsh(body, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"yes|{regular}",
        f"no|{directory}",
        f"yes|{link}",
    ]


def test_restart_term_replacement_succeeds_without_fallback(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="term-fast")
    assert result.returncode == 0, result.stderr
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout
    assert "signal|TERM|123" in lines
    assert not any(line.startswith(("launchctl|", "signal|KILL|", "plist|")) for line in lines)


def test_restart_waits_for_delayed_respawn_before_fallback(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="delayed")
    assert result.returncode == 0, result.stderr
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout
    assert sum(line.startswith("sleep|") for line in lines) >= 2
    assert not any(line.startswith("launchctl|") for line in lines)


def test_restart_unchanged_term_uses_kickstart_k_and_verifies_replacement(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="kick-force")
    assert result.returncode == 0, result.stderr
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout
    assert "signal|TERM|123" in lines
    assert "launchctl|kickstart -k system/com.apple.usbmuxd" in lines
    assert "signal|KILL|123" in lines


def test_restart_kickstart_replacement_succeeds_without_force_kill(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="kick-success")
    assert result.returncode == 0, result.stderr
    assert "launchctl|kickstart -k system/com.apple.usbmuxd" in lines
    assert not any(line.startswith("signal|KILL|") for line in lines)
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout


def test_restart_force_fallback_targets_only_original_pids_after_partial_replacement(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123\n124", scenario="partial-force")
    assert result.returncode == 0, result.stderr
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout
    assert "signal|TERM|123 124" in lines
    assert "signal|KILL|124" in lines
    assert not any(line == "signal|KILL|124 456" for line in lines)


def test_restart_rejects_partial_original_pid_survival(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123\n124", scenario="partial-fail")
    assert result.returncode != 0
    assert "Could not confirm usbmuxd restarted." in result.stdout
    assert "signal|KILL|124" in lines
    assert not any("RESTARTED" in line or "STARTED" in line for line in result.stdout.splitlines())


def test_restart_permanently_unchanged_daemon_runs_all_fallbacks_and_fails_closed(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="permanent")
    assert result.returncode != 0
    assert "Could not confirm usbmuxd restarted." in result.stdout
    assert "launchctl|kickstart -k system/com.apple.usbmuxd" in lines
    assert "signal|KILL|123" in lines
    assert any(line.startswith("launchctl|unload /Library/Apple/System/") for line in lines)
    assert any(line.startswith("launchctl|load /Library/Apple/System/") for line in lines)
    assert not any("RESTARTED" in line or "STARTED" in line for line in result.stdout.splitlines())


@pytest.mark.parametrize("scenario, expected_status", (("no-pid-start", 0), ("no-pid-fail", 1)))
def test_restart_handles_no_initial_daemon_without_signalling(tmp_path: Path, scenario: str, expected_status: int):
    result, lines = _run_restart(tmp_path, initial_pids="NONE", scenario=scenario)
    assert (result.returncode == 0) is (expected_status == 0)
    assert not any(line.startswith("signal|") for line in lines)
    if expected_status == 0:
        assert "usbmuxd STARTED with PID(s): 456" in result.stdout
    else:
        assert "Could not confirm usbmuxd restarted." in result.stdout


def test_restart_uses_older_system_plist_when_updated_plist_is_absent(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="fallback-success")
    assert result.returncode == 0, result.stderr
    assert any(line.startswith("plist|/System/Library/") for line in lines)
    assert not any(line.startswith("launchctl|unload /Library/Apple/System/") for line in lines)
    assert any(line.startswith("launchctl|unload /System/Library/") for line in lines)
    assert "launchctl kickstart -k failed" in result.stderr
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout


def test_restart_prefers_updated_apple_plist_when_both_locations_exist(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="apple-fallback-success")
    assert result.returncode == 0, result.stderr
    assert any(line.startswith("launchctl|unload /Library/Apple/System/") for line in lines)
    assert not any(line.startswith("plist|/System/Library/") for line in lines)
    assert not any(line.startswith("launchctl|unload /System/Library/") for line in lines)
    assert "usbmuxd RESTARTED with PID(s): 456" in result.stdout


def test_restart_missing_legacy_plists_reports_failure(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="missing-plist")
    assert result.returncode != 0
    assert "No legacy usbmuxd launchd plist was found." in result.stdout
    assert not any(line.startswith("launchctl|unload") for line in lines)


def test_restart_observation_error_is_not_treated_as_absence(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="ERROR:2", scenario="observation-error")
    assert result.returncode != 0
    assert "Could not inspect the usbmuxd process list" in result.stderr
    assert not any(line.startswith(("signal|", "launchctl|")) for line in lines)


def test_restart_mid_recovery_observation_error_stops_before_fallback(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="observer-mid")
    assert result.returncode != 0
    assert "Could not inspect the usbmuxd process list" in result.stderr
    assert not any(line.startswith("launchctl|") for line in lines)


def test_restart_rejects_pid_zero_as_an_invalid_observation(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="0", scenario="pid-zero")
    assert result.returncode != 0
    assert "invalid PID '0'" in result.stderr
    assert not any(line.startswith(("signal|", "launchctl|")) for line in lines)


def test_restart_signal_permission_failure_does_not_claim_success(tmp_path: Path):
    result, lines = _run_restart(tmp_path, initial_pids="123", scenario="signal-error")
    assert result.returncode != 0
    assert "TERM could not be sent" in result.stderr
    assert "Force-kill could not be sent" in result.stderr
    assert not any("RESTARTED" in line or "STARTED" in line for line in result.stdout.splitlines())


def test_normal_mode_service_warning_is_nonfatal_and_reconnect_advice_is_explicit(tmp_path: Path):
    fixture = _main_fixture(tmp_path)
    trace = tmp_path / "service-warning.trace"
    home = tmp_path / "home"
    home.mkdir()
    result = _run_zsh(
        _main_body(fixture, trace, fail_restart=True),
        cwd=tmp_path,
        home=home,
    )
    assert result.returncode == 0, result.stderr
    assert "Mobile device services restart could not be confirmed." in result.stdout
    assert "If the device does not reappear, unlock it and reconnect its cable." in result.stdout
    assert (home / "Downloads/CoreTypes.pkg").is_file()
    assert (home / "Downloads/MobileDeviceOnDemandPackage.pkg").is_file()
