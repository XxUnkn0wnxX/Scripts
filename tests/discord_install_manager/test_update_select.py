from __future__ import annotations

import os
import plistlib
import re
import subprocess
import sys
import threading
from pathlib import Path
import zipfile

import pytest

from _helpers import (
    _assert_no_download_artifacts,
    _read_command_log,
    _run_manager,
    _write_fake_curl_header_map,
    _write_fake_curl_sleep_map,
    _write_fake_curl_range_map,
    _write_fake_curl_zip_source_map,
)


UPDATE_SELECT_MANIFEST = '{"name":"0.0.5"}'
UPDATE_SELECT_ZIP_PLIST_PATHS = {
    "stable": "Discord.app/Contents/Info.plist",
    "ptb": "Discord PTB.app/Contents/Info.plist",
    "canary": "Discord Canary.app/Contents/Info.plist",
}
UPDATE_SELECT_ZIP_ARCHIVES = {
    "stable": "Discord.zip",
    "ptb": "DiscordPTB.zip",
    "canary": "DiscordCanary.zip",
}
UPDATE_SELECT_DMG_ARCHIVES = {
    "stable": "Discord.dmg",
    "ptb": "DiscordPTB.dmg",
    "canary": "DiscordCanary.dmg",
}
UPDATE_SELECT_ZIP_HOSTS = {
    "stable": "stable.dl2.discordapp.net",
    "ptb": "ptb.dl2.discordapp.net",
    "canary": "canary.dl2.discordapp.net",
}


def _run_update_select(
    env: dict[str, Path],
    *args: str,
    extra_env: dict[str, str] | None = None,
    **kwargs,
):
    base_env = {
        "TEST_FAKE_CURL_UPDATE_MANIFEST": UPDATE_SELECT_MANIFEST,
    }
    if extra_env:
        base_env.update(extra_env)
    return _run_manager(env, *args, extra_env=base_env, **kwargs)


def _start_update_select(
    env: dict[str, Path],
    *args: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    process_env = os.environ.copy()
    process_env.update(
        {
            "HOME": str(env["home"]),
            "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
            "TEST_COMMAND_LOG": str(env["command_log"]),
            "TEST_FAKE_STATE_DIR": str(env["fake_state"]),
            "TEST_FAKE_CURL_UPDATE_MANIFEST": UPDATE_SELECT_MANIFEST,
            "TEST_PYTHON": sys.executable,
        }
    )
    if extra_env:
        process_env.update(extra_env)

    env["command_log"].write_text("")
    return subprocess.Popen(
        [str(env["script"]), *args],
        cwd=str(env["home"]),
        env=process_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )


def _update_select_request_urls(
    env: dict[str, Path],
    *,
    suffix: str | None = None,
) -> list[str]:
    urls: list[str] = []
    for line in _read_command_log(env):
        if not line.startswith("curl\targs="):
            continue
        args = line.split("args=", 1)[1].strip().split()
        for arg in args:
            if "/apps/osx/" in arg and arg.startswith("https://"):
                if suffix is None or arg.endswith(suffix):
                    urls.append(arg)
    return sorted(set(urls))


def _update_select_head_urls(env: dict[str, Path]) -> list[str]:
    return _update_select_request_urls(env, suffix=".dmg")


def _update_select_zip_urls(env: dict[str, Path]) -> list[str]:
    return _update_select_request_urls(env, suffix=".zip")


def _assert_no_update_select_network(env: dict[str, Path]) -> None:
    assert not _read_command_log(env)


def _assert_update_select_probe_urls(
    env: dict[str, Path],
    expected_urls: list[str],
) -> None:
    assert _update_select_request_urls(env) == sorted(set(expected_urls))


def _assert_update_select_head_urls(
    env: dict[str, Path],
    expected_urls: list[str],
) -> None:
    assert _update_select_head_urls(env) == sorted(set(expected_urls))


def _assert_update_select_zip_urls(
    env: dict[str, Path],
    expected_urls: list[str],
) -> None:
    assert _update_select_zip_urls(env) == sorted(set(expected_urls))


def _extract_update_select_rows(output: str) -> list[str]:
    return [
        match.group(1)
        for match in (
            re.search(r"\b(0\.0\.\d+)\s+-\s+\[", line)
            for line in output.splitlines()
        )
        if match is not None
    ]


def _write_update_select_zip(
    env: dict[str, Path],
    channel: str,
    version: str,
    minimum_system_version: str | None,
    compression: int,
    *,
    short_version: str | None = None,
    bundle_version: str | None = None,
    plist_path: str | None = None,
    include_short_version: bool = True,
    include_bundle_version: bool = True,
) -> Path:
    normalized_version = version if version.startswith("0.0.") else f"0.0.{version}"
    zip_path = env["script"].parent / f"Discord-{channel}-{normalized_version}.zip"

    payload: dict[str, str] = {}
    if include_short_version:
        payload["CFBundleShortVersionString"] = short_version or normalized_version
    if include_bundle_version:
        payload["CFBundleVersion"] = bundle_version or normalized_version
    if minimum_system_version is not None:
        payload["LSMinimumSystemVersion"] = minimum_system_version

    plist_payload = plistlib.dumps(payload, fmt=plistlib.FMT_XML)

    with zipfile.ZipFile(zip_path, "w", compression=compression) as zip_file:
        zip_file.writestr(plist_path or UPDATE_SELECT_ZIP_PLIST_PATHS[channel], plist_payload)

    return zip_path


def _versioned_zip_url(channel: str, version: str) -> str:
    host = UPDATE_SELECT_ZIP_HOSTS[channel]
    archive = UPDATE_SELECT_ZIP_ARCHIVES[channel]
    normalized_version = version if version.startswith("0.0.") else f"0.0.{version}"
    return f"https://{host}/apps/osx/{normalized_version}/{archive}"


def _versioned_dmg_url(channel: str, version: str) -> str:
    host = UPDATE_SELECT_ZIP_HOSTS[channel]
    archive = UPDATE_SELECT_DMG_ARCHIVES[channel]
    normalized_version = version if version.startswith("0.0.") else f"0.0.{version}"
    return f"https://{host}/apps/osx/{normalized_version}/{archive}"


def test_update_select_without_selector_prints_highest_discovered_artifact_only(
    env: dict[str, Path],
):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.7*", "200"),
            ("*0.0.6*", "200"),
            ("*0.0.5*", "200"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "DISCORD_UPDATE_SELECT_UPWARD_LIMIT": "2",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "Available Discord macOS DMG versions:" in result.stdout
    assert "manifest: 0.0.5" in result.stdout
    assert "upward discovery: 2 versions above the manifest" in result.stdout
    assert "highest CDN artifact: 0.0.7" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.7 - [unknown]" in result.stdout
    assert "0.0.6 - [" not in result.stdout
    assert "0.0.5 - [" not in result.stdout
    assert "scan floor:" not in result.stdout
    assert "scan limit:" not in result.stdout
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.7"),
            _versioned_dmg_url("stable", "0.0.6"),
        ],
    )
    _assert_update_select_zip_urls(env, [_versioned_zip_url("stable", "0.0.7")])
    _assert_no_download_artifacts(env)


def test_update_select_scan_limit_applies_with_selector(env: dict[str, Path]):
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
        "4",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "DISCORD_UPDATE_SELECT_SCAN_LIMIT": "2",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "scan floor: 0.0.4" in result.stdout
    assert "scan limit: newest 2 builds because DISCORD_UPDATE_SELECT_SCAN_LIMIT is set" in result.stdout
    versions = _extract_update_select_rows(result.stdout)
    assert "0.0.5" in versions
    assert "0.0.4" in versions
    assert "0.0.3" not in versions
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.5"),
            _versioned_dmg_url("stable", "0.0.4"),
        ],
    )
    _assert_update_select_zip_urls(
        env,
        [
            _versioned_zip_url("stable", "0.0.5"),
            _versioned_zip_url("stable", "0.0.4"),
        ],
    )


@pytest.mark.parametrize("selector", ["5", "0.0.5"])
def test_update_select_numeric_and_canonical_minimum_select_stops_at_floor(
    env: dict[str, Path],
    selector: str,
):
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
    versions = _extract_update_select_rows(result.stdout)
    assert versions == ["0.0.5"]
    assert "0.0.4" not in result.stdout
    _assert_update_select_head_urls(
        env,
        [_versioned_dmg_url("stable", "0.0.5")],
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
    assert set(_extract_update_select_rows(result.stdout)) == {"0.0.5", "0.0.4", "0.0.3"}
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.5"),
            _versioned_dmg_url("stable", "0.0.4"),
            _versioned_dmg_url("stable", "0.0.3"),
        ],
    )
    _assert_update_select_zip_urls(
        env,
        [
            _versioned_zip_url("stable", "0.0.5"),
            _versioned_zip_url("stable", "0.0.4"),
            _versioned_zip_url("stable", "0.0.3"),
        ],
    )


def test_update_select_accepts_inclusive_100_step_range_and_reports_every_version(
    env: dict[str, Path],
):
    map_path = _write_fake_curl_header_map(env, [("*", "200")])

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "500-400",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "TEST_FAKE_CURL_UPDATE_MANIFEST": '{"name":"0.0.500"}',
        },
    )

    assert result.returncode == 0, result.stderr
    assert "scan range: 0.0.500 down to 0.0.400" in result.stdout
    rows = _extract_update_select_rows(result.stdout)
    expected_rows = [f"0.0.{i}" for i in range(500, 399, -1)]
    assert len(rows) == len(expected_rows)
    assert set(rows) == set(expected_rows)


def test_update_select_rejects_too_wide_inclusive_range(env: dict[str, Path]):
    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "300-100",
    )

    assert result.returncode == 2
    assert "Usage:" in (result.stdout + result.stderr)
    assert "--update-select ranges may span at most 100 version steps" in (result.stdout + result.stderr)
    _assert_no_update_select_network(env)


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
    assert "Use descending ranges such as 500-400 or 0.0.500-0.0.400." in (result.stdout + result.stderr)
    _assert_update_select_head_urls(env, [])


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
    _assert_update_select_head_urls(env, [])


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
    assert "requested floor was newer than the manifest; using 0.0.5" in result.stdout
    assert "scan floor: 0.0.5" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5 - [unknown]" in result.stdout
    assert "0.0.4" not in result.stdout
    _assert_update_select_head_urls(
        env,
        [_versioned_dmg_url("stable", "0.0.5")],
    )


def test_update_select_range_start_newer_than_manifest_is_honored(env: dict[str, Path]):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.6*", "200"),
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
        "6-3",
        extra_env={"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)},
    )

    assert result.returncode == 0, result.stderr
    assert "requested start was newer than latest" not in result.stdout
    assert "scan range: 0.0.6 down to 0.0.3" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.6 - [unknown]" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5 - [unknown]" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.4 - [unknown]" in result.stdout
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.3 - [unknown]" in result.stdout
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.6"),
            _versioned_dmg_url("stable", "0.0.5"),
            _versioned_dmg_url("stable", "0.0.4"),
            _versioned_dmg_url("stable", "0.0.3"),
        ],
    )
    _assert_update_select_zip_urls(
        env,
        [
            _versioned_zip_url("stable", "0.0.6"),
            _versioned_zip_url("stable", "0.0.5"),
            _versioned_zip_url("stable", "0.0.4"),
            _versioned_zip_url("stable", "0.0.3"),
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
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.5"),
            _versioned_dmg_url("stable", "0.0.4"),
            _versioned_dmg_url("stable", "0.0.3"),
        ],
    )
    _assert_update_select_zip_urls(env, [])


def test_update_select_uses_unknown_last_modified_and_unknown_minimum_when_missing(env: dict[str, Path]):
    header_map_path = _write_fake_curl_header_map(
        env,
        [("*0.0.5*", "200")],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(header_map_path),
            "TEST_FAKE_CURL_LAST_MODIFIED": "",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "Mon, 01 Jan 2024 00:00:00 GMT  0.0.5 - [unknown]" not in result.stdout
    assert re.search(r"^unknown\s+0\.0\.5 - \[unknown\]$", result.stdout, re.MULTILINE)
    _assert_update_select_head_urls(
        env,
        [_versioned_dmg_url("stable", "0.0.5")],
    )


@pytest.mark.parametrize("channel", tuple(UPDATE_SELECT_ZIP_HOSTS))
@pytest.mark.parametrize("minimum_system_version", ["12.0+", "12.0"])
@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_update_select_reports_minimum_macos_for_stored_and_deflated_plist_metadata(
    env: dict[str, Path],
    channel: str,
    minimum_system_version: str,
    compression: int,
):
    zip_path = _write_update_select_zip(
        env,
        channel,
        "0.0.5",
        minimum_system_version,
        compression,
    )
    header_map_path = _write_fake_curl_header_map(
        env,
        [
            (f"*0.0.5*", "200"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        channel,
        "--update-select",
        "5",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(header_map_path),
            "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                _write_fake_curl_zip_source_map(
                    env,
                    [(f"*0.0.5*", zip_path)],
                )
            ),
        },
    )

    assert result.returncode == 0, result.stderr
    expected = minimum_system_version.rstrip("+")
    assert f"0.0.5 - [{expected}]" in result.stdout
    _assert_update_select_head_urls(
        env,
        [_versioned_dmg_url(channel, "0.0.5")],
    )
    _assert_update_select_zip_urls(
        env,
        [_versioned_zip_url(channel, "0.0.5")],
    )


@pytest.mark.parametrize("scan_limit", ["0", "abc", None])
def test_update_select_no_selector_ignores_downward_scan_limit(
    env: dict[str, Path],
    scan_limit: str | None,
):
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
    extra_env = {
        "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
        "DISCORD_UPDATE_SELECT_UPWARD_LIMIT": "1",
    }
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
    assert "Available Discord macOS DMG versions:" in result.stdout
    assert "0.0.4" not in result.stdout
    assert "scan limit: newest" not in result.stdout
    assert "scan floor:" not in result.stdout
    assert "manifest: 0.0.5" in result.stdout
    assert "highest CDN artifact: 0.0.5" in result.stdout
    assert "0.0.5 - [unknown]" in result.stdout
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.6"),
            _versioned_dmg_url("stable", "0.0.5"),
        ],
    )
    _assert_update_select_zip_urls(env, [_versioned_zip_url("stable", "0.0.5")])


@pytest.mark.parametrize(
    "jobs,expected",
    [
        (None, "8"),
        ("0", "8"),
        ("invalid", "8"),
        ("3", "3"),
        ("12", "8"),
    ],
)
def test_update_select_worker_count_bounds(
    env: dict[str, Path],
    jobs: str | None,
    expected: str,
):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
        ],
    )
    extra_env = {"TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path)}
    if jobs is not None:
        extra_env["DISCORD_UPDATE_SELECT_JOBS"] = jobs

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5-4",
        extra_env=extra_env,
    )

    assert result.returncode == 0, result.stderr
    assert f"scan workers: {expected}" in result.stdout
    _assert_update_select_head_urls(env, [_versioned_dmg_url("stable", "0.0.5"), _versioned_dmg_url("stable", "0.0.4")])
    _assert_update_select_zip_urls(env, [_versioned_zip_url("stable", "0.0.5"), _versioned_zip_url("stable", "0.0.4")])


def test_update_select_versioned_zip_url_and_plist_paths_are_channel_specific(
    env: dict[str, Path],
):
    for channel in UPDATE_SELECT_ZIP_HOSTS:
        zip_path = _write_update_select_zip(
            env,
            channel,
            "0.0.5",
            "12.0",
            zipfile.ZIP_STORED,
        )
        map_path = _write_fake_curl_header_map(
            env,
            [
                (f"*0.0.5*", "200"),
            ],
        )

        result = _run_update_select(
            env,
            "--channel",
            channel,
            "--update-select",
            "5",
            extra_env={
                "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
                "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                    _write_fake_curl_zip_source_map(
                        env,
                        [(f"*0.0.5*", zip_path)],
                    )
                ),
            },
        )

        assert result.returncode == 0, result.stderr
        assert f"0.0.5 - [12.0]" in result.stdout
        _assert_update_select_head_urls(env, [_versioned_dmg_url(channel, "0.0.5")])
        _assert_update_select_zip_urls(env, [_versioned_zip_url(channel, "0.0.5")])


def test_update_select_rows_print_in_version_order_with_forced_out_of_order_completion(
    env: dict[str, Path],
):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
            ("*0.0.3*", "200"),
            ("*0.0.2*", "200"),
        ],
    )
    zip_path = _write_update_select_zip(
        env,
        "stable",
        "0.0.5",
        "12.0",
        zipfile.ZIP_STORED,
    )
    sleep_map_path = _write_fake_curl_sleep_map(
        env,
        [
            ("*0.0.5/Discord.dmg", "2"),
            ("*0.0.4*", "0"),
            ("*0.0.3*", "0"),
            ("*0.0.2*", "0"),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5-2",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "DISCORD_UPDATE_SELECT_JOBS": "2",
            "TEST_FAKE_CURL_SLEEP_MAP_FILE": str(sleep_map_path),
            "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                _write_fake_curl_zip_source_map(
                    env,
                    [
                        ("*0.0.5*", zip_path),
                        ("*0.0.4*", zip_path),
                        ("*0.0.3*", zip_path),
                        ("*0.0.2*", zip_path),
                    ]
                ),
            ),
        },
    )

    assert result.returncode == 0, result.stderr
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.5"),
            _versioned_dmg_url("stable", "0.0.4"),
            _versioned_dmg_url("stable", "0.0.3"),
            _versioned_dmg_url("stable", "0.0.2"),
        ],
    )
    _assert_update_select_zip_urls(
        env,
        [
            _versioned_zip_url("stable", "0.0.5"),
            _versioned_zip_url("stable", "0.0.4"),
            _versioned_zip_url("stable", "0.0.3"),
            _versioned_zip_url("stable", "0.0.2"),
        ],
    )
    rows = _extract_update_select_rows(result.stdout)
    assert rows == ["0.0.5", "0.0.4", "0.0.3", "0.0.2"]


def test_update_select_streams_ordered_head_before_slower_lower_worker_finishes(
    env: dict[str, Path],
):
    map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
            ("*0.0.4*", "200"),
        ],
    )
    sleep_map_path = _write_fake_curl_sleep_map(
        env,
        [("*0.0.4/Discord.dmg", "4")],
    )
    process = _start_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5-4",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "TEST_FAKE_CURL_SLEEP_MAP_FILE": str(sleep_map_path),
            "DISCORD_UPDATE_SELECT_JOBS": "2",
        },
    )
    output_lines: list[str] = []
    head_row_seen = threading.Event()

    assert process.stdout is not None
    assert process.stderr is not None

    def read_stdout() -> None:
        for line in process.stdout:
            output_lines.append(line)
            if "0.0.5 - [" in line:
                head_row_seen.set()

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()

    try:
        assert head_row_seen.wait(timeout=2.5), (
            "The next ordered row was not streamed before the slower lower worker finished."
        )
        assert process.poll() is None, (
            "The command finished before proving that the ordered head row streamed early."
        )
        returncode = process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        reader.join(timeout=2)

    stderr = process.stderr.read()
    output = "".join(output_lines)
    assert returncode == 0, stderr
    assert _extract_update_select_rows(output) == ["0.0.5", "0.0.4"]


def test_update_select_reaps_worker_that_exits_before_marking_completion(
    env: dict[str, Path],
):
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
        "5-3",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(map_path),
            "TEST_FAKE_CURL_KILL_PARENT_PATTERN": "*0.0.4/Discord.dmg",
            "DISCORD_UPDATE_SELECT_JOBS": "2",
        },
    )

    assert result.returncode == 0, result.stderr
    assert _extract_update_select_rows(result.stdout) == ["0.0.5", "0.0.3"]
    assert "0.0.4 - [" not in result.stdout
    _assert_update_select_head_urls(
        env,
        [
            _versioned_dmg_url("stable", "0.0.5"),
            _versioned_dmg_url("stable", "0.0.4"),
            _versioned_dmg_url("stable", "0.0.3"),
        ],
    )


def test_update_select_range_200_with_mismatched_content_range_reports_unknown(env: dict[str, Path]):
    header_map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.5*", "200"),
        ],
    )
    body_path = env["script"].parent / "one-byte-range.bin"
    body_path.write_bytes(b"x")
    range_map_path = _write_fake_curl_range_map(
        env,
        [
            ("*", "bytes=0-0", "206", "bytes 2-2/9", "", str(body_path)),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(header_map_path),
            "TEST_FAKE_CURL_RANGE_MAP_FILE": str(range_map_path),
        },
    )

    assert result.returncode == 0, result.stderr
    assert "0.0.5 - [unknown]" in result.stdout
    _assert_update_select_head_urls(env, [_versioned_dmg_url("stable", "0.0.5")])
    zip_url = _versioned_zip_url("stable", "0.0.5")
    _assert_update_select_zip_urls(env, [zip_url])
    assert all(
        "--range" in line
        for line in _read_command_log(env)
        if zip_url in line and line.startswith("curl\targs=")
    )


def test_update_select_range_200_for_zip_data_is_treated_unknown_without_fallback(env: dict[str, Path]):
    header_map_path = _write_fake_curl_header_map(
        env,
        [("*0.0.5*", "200")],
    )
    body_path = env["script"].parent / "one-byte-full-response.bin"
    body_path.write_bytes(b"x")
    range_map_path = _write_fake_curl_range_map(
        env,
        [
            ("*", "bytes=0-0", "200", "bytes 0-0/9", "", str(body_path)),
        ],
    )

    result = _run_update_select(
        env,
        "--channel",
        "stable",
        "--update-select",
        "5",
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(header_map_path),
            "TEST_FAKE_CURL_RANGE_MAP_FILE": str(range_map_path),
        },
    )

    assert result.returncode == 0, result.stderr
    assert "0.0.5 - [unknown]" in result.stdout
    zip_url = _versioned_zip_url("stable", "0.0.5")
    zip_calls = [line for line in _read_command_log(env) if zip_url in line and line.startswith("curl\targs=")]
    assert len(zip_calls) == 1
    assert all("--range" in line for line in zip_calls)


def test_update_select_keeps_dmg_rows_when_zip_metadata_is_invalid(
    env: dict[str, Path],
):
    for expected in [
        {"short_version": "0.0.999", "bundle_version": "0.0.999"},
        {"minimum_system_version": None},
        {"include_short_version": False, "include_bundle_version": False},
        {"plist_path": "Discord.app/Contents/NoInfo.plist"},
    ]:
        zip_kwargs = {"minimum_system_version": "12.0", "compression": zipfile.ZIP_STORED}
        zip_kwargs.update(expected)
        zip_path = _write_update_select_zip(
            env,
            "stable",
            "0.0.5",
            zip_kwargs.pop("minimum_system_version"),
            zip_kwargs.pop("compression"),
            **zip_kwargs,
        )
        header_map_path = _write_fake_curl_header_map(
            env,
            [("*0.0.5*", "200")],
        )

        result = _run_update_select(
            env,
            "--channel",
            "stable",
            "--update-select",
            "5",
            extra_env={
                "TEST_FAKE_CURL_HEADER_MAP_FILE": str(header_map_path),
                "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                    _write_fake_curl_zip_source_map(env, [("*0.0.5*", zip_path)])
                ),
            },
        )

        assert result.returncode == 0, result.stderr
        assert "0.0.5 - [unknown]" in result.stdout
        _assert_update_select_head_urls(env, [_versioned_dmg_url("stable", "0.0.5")])
        _assert_update_select_zip_urls(env, [_versioned_zip_url("stable", "0.0.5")])
