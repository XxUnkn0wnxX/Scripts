from __future__ import annotations

from pathlib import Path

import pytest

from _helpers import _read_command_log, _run_manager, _write_fake_curl_header_map


UPDATE_SELECT_MANIFEST = '{"name":"0.0.5"}'


def _run_update_select(env: dict[str, Path], *args: str, extra_env: dict[str, str] | None = None, **kwargs):
    base_env = {
        "TEST_FAKE_CURL_UPDATE_MANIFEST": UPDATE_SELECT_MANIFEST,
    }
    if extra_env:
        base_env.update(extra_env)
    return _run_manager(env, *args, extra_env=base_env, **kwargs)


def _update_select_cdn_urls(env: dict[str, Path]) -> list[str]:
    urls: list[str] = []
    for line in _read_command_log(env):
        if not line.startswith("curl\targs="):
            continue
        args = line.split("args=", 1)[1].strip().split()
        for arg in args:
            if "/apps/osx/" in arg and arg.startswith("https://"):
                urls.append(arg)
    return urls


def _assert_update_select_probe_urls(env: dict[str, Path], expected_urls: list[str]) -> None:
    assert _update_select_cdn_urls(env) == expected_urls


def test_update_select_prints_latest_window_and_requests_exact_head_urls(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "404"),
            ("*0.0.2*", "404"),
            ("*0.0.1*", "404"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode == 0, result.stderr
    assert "Available Discord macOS DMG versions:" in result.stdout
    assert "latest: 0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.4" in result.stdout
    assert "0.0.3" not in result.stdout
    _assert_update_select_probe_urls(
        env,
        [
            "https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.4/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.3/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.2/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.1/Discord.dmg",
        ],
    )


def test_update_select_scan_limit_uses_exact_probe_sequence(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "200"),
            ("*0.0.2*", "200"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "DISCORD_UPDATE_SELECT_SCAN_LIMIT": "2",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "scan limit: newest 2 builds because DISCORD_UPDATE_SELECT_SCAN_LIMIT is set" in result.stdout
    _assert_update_select_probe_urls(
        env,
        [
            "https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.4/Discord.dmg",
        ],
    )


@pytest.mark.parametrize("selector", ["5", "0.0.5"])
def test_update_select_numeric_and_canonical_minimum_select_stops_at_floor(env: dict[str, Path], selector: str):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "404"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        selector,
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode == 0, result.stderr
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5" in result.stdout
    assert "0.0.4" not in result.stdout
    _assert_update_select_probe_urls(
        env,
        ["https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg"],
    )


def test_update_select_descending_range_selects_specified_window(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "200"),
            ("*0.0.2*", "200"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5-3",
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode == 0, result.stderr
    assert "scan range: 0.0.5 down to 0.0.3" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.4" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.3" in result.stdout
    assert "0.0.2" not in result.stdout
    _assert_update_select_probe_urls(
        env,
        [
            "https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.4/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.3/Discord.dmg",
        ],
    )


def test_update_select_ascending_range_is_rejected(env: dict[str, Path]):
    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "3-5",
    )

    assert result.returncode != 0
    assert "Invalid update-select range: 3-5" in (result.stdout + result.stderr)
    assert "Use descending ranges such as 600-300 or 0.0.600-0.0.300." in (result.stdout + result.stderr)
    assert not _update_select_cdn_urls(env)


def test_update_select_malformed_selector_is_rejected(env: dict[str, Path]):
    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "abc",
    )

    assert result.returncode != 0
    assert "Invalid Discord version: abc" in (result.stdout + result.stderr)
    assert not _update_select_cdn_urls(env)


def test_update_select_newer_minimum_clamps_to_latest(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "200"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "600",
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode == 0, result.stderr
    assert "requested floor was newer than latest; using latest 0.0.5" in result.stdout
    assert "scan floor: 0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.4" not in result.stdout
    _assert_update_select_probe_urls(
        env,
        ["https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg"],
    )


def test_update_select_range_start_newer_than_latest_is_clamped(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "200"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "600-3",
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode == 0, result.stderr
    assert "requested start was newer than latest; using latest 0.0.5" in result.stdout
    assert "scan range: 0.0.5 down to 0.0.3" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.4" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.3" in result.stdout
    _assert_update_select_probe_urls(
        env,
        [
            "https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.4/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.3/Discord.dmg",
        ],
    )


def test_update_select_reports_no_matches_when_cdn_is_empty(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "404"),
            ("*0.0.4*", "404"),
            ("*0.0.3*", "404"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5-3",
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode != 0
    assert "No CDN DMG versions were found for Discord." in (result.stderr + result.stdout)
    _assert_update_select_probe_urls(
        env,
        [
            "https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.4/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.3/Discord.dmg",
        ],
    )


def test_update_select_uses_unknown_last_modified_when_missing(env: dict[str, Path]):
    env["fake_bin"].joinpath("curl").write_text(
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'curl\\targs=%s\\n' \"$*\" >> \"$log_file\"
fi

url=""
output=""
while [ "$#" -gt 0 ]; do
  case \"$1\" in
    --output)
      shift
      output=\"$1\"
      ;;
    *)
      url=\"$1\"
      ;;
  esac
  shift || break
done

if printf '%s' \"$url\" | /usr/bin/grep -q '^https://discord.com/api/updates/'; then
  manifest=\"${TEST_FAKE_CURL_UPDATE_MANIFEST:-{\\\"name\\\":\\\"0.0.5\\\"}}\"
  if [ -n \"$output\" ]; then
    mkdir -p \"$(dirname \\\"$output\\\")\"
    printf '%s\\n' \"$manifest\" > \"$output\"
  else
    printf '%s\\n' \"$manifest\"
  fi
  exit 0
fi

if [ -z \"$output\" ]; then
  printf 'HTTP/1.1 200 OK\\r\\n'
  exit 0
fi

mkdir -p \"$(dirname \\\"$output\\\")\"
printf 'dummy-curl' > \"$output\"
""",
        encoding="utf-8",
    )
    env["fake_bin"].joinpath("curl").chmod(0o755)

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5",
        extra_env={"TEST_FAKE_CURL_LAST_MODIFIED": ""},
    )

    assert result.returncode == 0, result.stderr
    assert "unknown  0.0.5" in result.stdout
    _assert_update_select_probe_urls(
        env,
        ["https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg"],
    )


@pytest.mark.parametrize("scan_limit", ["0", "abc", None])
def test_update_select_zero_or_nonnumeric_scan_limit_keeps_full_range_probe_sequence(env: dict[str, Path], scan_limit: str | None):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "200"),
            ("*0.0.2*", "200"),
            ("*0.0.1*", "200"),
        ],
    )
    extra_env = {"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)}
    if scan_limit is not None:
        extra_env["DISCORD_UPDATE_SELECT_SCAN_LIMIT"] = scan_limit

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        extra_env=extra_env,
    )

    assert result.returncode == 0, result.stderr
    assert "scan limit: newest" not in result.stdout
    _assert_update_select_probe_urls(
        env,
        [
            "https://stable.dl2.discordapp.net/apps/osx/0.0.5/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.4/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.3/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.2/Discord.dmg",
            "https://stable.dl2.discordapp.net/apps/osx/0.0.1/Discord.dmg",
        ],
    )
