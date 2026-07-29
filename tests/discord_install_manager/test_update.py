from __future__ import annotations

import json
import plistlib
import zipfile
from pathlib import Path

import pytest

from _helpers import (
    APP_NAMES,
    _assert_no_download_artifacts,
    _application_path,
    _write_fake_curl_header_map,
    _write_fake_curl_zip_source_map,
    _read_command_log,
    _read_settings,
    _run_manager,
    _settings_path,
)


_CDN_HOSTS = {
    "stable": "stable.dl2.discordapp.net",
    "ptb": "ptb.dl2.discordapp.net",
    "canary": "canary.dl2.discordapp.net",
}

_DMG_FILENAMES = {
    "stable": "Discord.dmg",
    "ptb": "DiscordPTB.dmg",
    "canary": "DiscordCanary.dmg",
}

_ZIP_PLIST_PATHS = {
    "stable": "Discord.app/Contents/Info.plist",
    "ptb": "Discord PTB.app/Contents/Info.plist",
    "canary": "Discord Canary.app/Contents/Info.plist",
}

_ZIP_FILENAMES = {
    "stable": "Discord.zip",
    "ptb": "DiscordPTB.zip",
    "canary": "DiscordCanary.zip",
}

_DOWNLOAD_URLS = {
    "stable": "https://discord.com/api/download/stable?platform=osx",
    "ptb": "https://discord.com/api/download/ptb?platform=osx",
    "canary": "https://discord.com/api/download/canary?platform=osx",
}

_MANIFEST_URLS = {
    "stable": "https://discord.com/api/updates/stable?platform=osx",
    "ptb": "https://discord.com/api/updates/ptb?platform=osx",
    "canary": "https://discord.com/api/updates/canary?platform=osx",
}


def _expected_installer_url(channel: str, version: str = "0.0.401") -> str:
    return f"https://{_CDN_HOSTS[channel]}/apps/osx/{version}/{_DMG_FILENAMES[channel]}"


def _expected_zip_url(channel: str, version: str) -> str:
    return f"https://{_CDN_HOSTS[channel]}/apps/osx/{version}/{_ZIP_FILENAMES[channel]}"


def _write_fake_update_select_zip(
    env: dict[str, Path],
    channel: str,
    version: str,
    minimum_system_version: str,
    compression: int,
) -> Path:
    normalized_version = version if version.startswith("0.0.") else f"0.0.{version}"
    zip_path = (
        env["script"].parent
        / f"Discord-update-filter-{channel}-{normalized_version}.zip"
    )
    payload = {
        "CFBundleShortVersionString": normalized_version,
        "CFBundleVersion": normalized_version,
        "LSMinimumSystemVersion": minimum_system_version,
    }
    plist_payload = plistlib.dumps(payload, fmt=plistlib.FMT_XML)

    with zipfile.ZipFile(zip_path, "w", compression=compression) as zip_file:
        zip_file.writestr(_ZIP_PLIST_PATHS[channel], plist_payload)

    return zip_path


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _write_hdiutil_starts_background_discord(fake_bin: Path) -> None:
    _write_executable(
        fake_bin / "hdiutil",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'hdiutil\\targs=%s\\n' "$*" >> "$log_file"
fi

if [ "$1" = "attach" ]; then
  mountpoint=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -mountpoint)
        shift
        mountpoint="$1"
        ;;
    esac
    shift || break
  done

  app_name="Discord.app"
  executable="Discord"
  case "$mountpoint" in
    *mount-ptb*) app_name="Discord PTB.app"; executable="Discord PTB" ;;
    *mount-canary*) app_name="Discord Canary.app"; executable="Discord Canary" ;;
  esac

  app_path="$mountpoint/$app_name"
  mkdir -p "$app_path/Contents/Resources" "$app_path/Contents/MacOS"
  printf 'plist' > "$app_path/Contents/Info.plist"
  if [ -x /bin/sleep ]; then
    cp /bin/sleep "$app_path/Contents/MacOS/$executable"
  else
    printf '#!/usr/bin/env sh\\n/bin/sleep\\n' > "$app_path/Contents/MacOS/$executable"
  fi
  chmod +x "$app_path/Contents/MacOS/$executable"
  : > "$app_path/Contents/Resources/app.asar"

  if [ -n "${TEST_FAKE_START_CLIENT_DURING_REPLACE:-}" ] && [ -x "$app_path/Contents/MacOS/$executable" ]; then
    installed_root="${TEST_FAKE_APPLICATIONS_ROOT:-}"
    if [ -n "$installed_root" ]; then
      installed_app="$installed_root/$app_name"
      installed_exec="$installed_app/Contents/MacOS/$executable"
      mkdir -p "$installed_app/Contents/MacOS"
      cp "$app_path/Contents/MacOS/$executable" "$installed_exec"
      chmod +x "$installed_exec"
      /usr/bin/nohup "$installed_exec" 1000 >/dev/null 2>&1 &
      spawned_pid=$!
      if [ -n "${TEST_FAKE_DISCORD_PID_TRACKER:-}" ]; then
        printf '%s\\n' "$spawned_pid" >> "${TEST_FAKE_DISCORD_PID_TRACKER}"
      fi
      process_ready=0
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        command="$(/bin/ps -p "$spawned_pid" -o command= 2>/dev/null || true)"
        case "$command" in
          "$installed_root"/*)
            process_ready=1
            break
            ;;
        esac
        /bin/sleep 0.02
      done
      if [ "$process_ready" != "1" ]; then
        exit 1
      fi
      if [ -n "${TEST_FAKE_RECREATE_CLEANUP_TARGET:-}" ]; then
        : > "${TEST_FAKE_RECREATE_CLEANUP_TARGET}"
      fi
    else
      "$app_path/Contents/MacOS/$executable" 1000 >/dev/null 2>&1 &
    fi
  fi
  exit 0
elif [ "$1" = "detach" ]; then
  tracker="${TEST_FAKE_DISCORD_PID_TRACKER:-}"
  installed_root="${TEST_FAKE_APPLICATIONS_ROOT:-}"
  if [ -n "$tracker" ] && [ -r "$tracker" ] && [ -n "$installed_root" ]; then
    while IFS= read -r tracked_pid; do
      case "$tracked_pid" in
        ''|*[!0-9]*) continue ;;
      esac
      command="$(/bin/ps -p "$tracked_pid" -o command= 2>/dev/null || true)"
      case "$command" in
        "$installed_root"/*)
          /bin/kill -TERM "$tracked_pid" >/dev/null 2>&1 || true
          for _ in 1 2 3 4 5 6 7 8 9 10; do
            /bin/kill -0 "$tracked_pid" >/dev/null 2>&1 || break
            /bin/sleep 0.02
          done
          if /bin/kill -0 "$tracked_pid" >/dev/null 2>&1; then
            command="$(/bin/ps -p "$tracked_pid" -o command= 2>/dev/null || true)"
            case "$command" in
              "$installed_root"/*)
                /bin/kill -KILL "$tracked_pid" >/dev/null 2>&1 || true
                ;;
            esac
          fi
          ;;
      esac
    done < "$tracker"
  fi
  exit 0
else
  exit 0
fi
""",
    )


def _write_osascript_stops_background_discord(fake_bin: Path) -> None:
    _write_executable(
        fake_bin / "osascript",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'osascript\\targs=%s\\n' "$*" >> "$log_file"
fi

tracker="${TEST_FAKE_DISCORD_PID_TRACKER:-}"
installed_root="${TEST_FAKE_APPLICATIONS_ROOT:-}"
if [ -n "$tracker" ] && [ -r "$tracker" ] && [ -n "$installed_root" ]; then
  while IFS= read -r tracked_pid; do
    case "$tracked_pid" in
      ''|*[!0-9]*) continue ;;
    esac
    command="$(/bin/ps -p "$tracked_pid" -o command= 2>/dev/null || true)"
    case "$command" in
      "$installed_root"/*)
        /bin/kill -TERM "$tracked_pid" >/dev/null 2>&1 || true
        ;;
    esac
  done < "$tracker"
fi
exit 0
""",
    )


def _disable_forced_quit_in_test_copy(env: dict[str, Path]) -> None:
    source = env["script"].read_text(encoding="utf-8")
    marker = '        kill -KILL "$pid" >/dev/null 2>&1 || true'
    assert source.count(marker) == 1
    env["script"].write_text(
        source.replace(marker, "        : # Test copy: simulate a process that cannot be killed."),
        encoding="utf-8",
    )


def _command_log_contains(command_log: list[str], command: str, snippet: str) -> bool:
    return any(entry.startswith(f"{command}\t") and snippet in entry for entry in command_log)


def _command_log_index(command_log: list[str], command: str, snippet: str) -> int | None:
    for index, entry in enumerate(command_log):
        if entry.startswith(f"{command}\t") and snippet in entry:
            return index
    return None


@pytest.mark.parametrize("channel", ["stable", "ptb", "canary"])
def test_update_replaces_single_channel_with_pinned_version(env: dict[str, Path], channel: str):
    result = _run_manager(env, "--channel", channel, "--update", "401")

    assert result.returncode == 0

    app_path = _application_path(env["applications_root"], channel)
    executable = app_path / "Contents" / "MacOS" / APP_NAMES[channel]
    assert app_path.exists()
    assert executable.exists()
    assert "app replaced successfully." in result.stdout

    command_log = _read_command_log(env)
    assert not _command_log_contains(command_log, "curl", _MANIFEST_URLS[channel])
    assert _command_log_contains(command_log, "aria2c", _expected_installer_url(channel))
    assert _command_log_contains(command_log, "hdiutil", "attach")
    assert _command_log_contains(command_log, "ditto", str(app_path))
    _assert_no_download_artifacts(env)


@pytest.mark.parametrize("channel", ["stable", "ptb", "canary"])
def test_update_replaces_single_channel_with_latest_manifest(env: dict[str, Path], channel: str):
    result = _run_manager(env, "--channel", channel, "--update")

    assert result.returncode == 0
    assert "app replaced successfully." in result.stdout

    command_log = _read_command_log(env)
    assert _command_log_contains(command_log, "curl", _MANIFEST_URLS[channel])
    assert _command_log_contains(command_log, "aria2c", _DOWNLOAD_URLS[channel])
    assert _command_log_contains(command_log, "hdiutil", "attach")
    _assert_no_download_artifacts(env)


@pytest.mark.parametrize("openasar_mode", ["none", "default", "local"])
def test_update_with_os_filter_resolves_version_without_pin(
    env: dict[str, Path],
    openasar_mode: str,
):
    header_map_path = _write_fake_curl_header_map(
        env,
        [
            ("*0.0.402*", "200"),
            ("*0.0.401*", "200"),
        ],
    )
    zip_path = _write_fake_update_select_zip(
        env,
        "stable",
        "0.0.402",
        "12.0",
        zipfile.ZIP_DEFLATED,
    )

    args = ["--channel", "stable", "--update", "--OS", "12"]
    if openasar_mode == "default":
        args.append("--openasar")
    elif openasar_mode == "local":
        args.extend(("--openasar-source", str(env["openasar_source"])))

    result = _run_manager(
        env,
        *args,
        extra_env={
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(header_map_path),
            "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                _write_fake_curl_zip_source_map(env, [("*0.0.402*", zip_path)])
            ),
            "DISCORD_UPDATE_OS_SCAN_LIMIT": "1",
            "DISCORD_UPDATE_SELECT_UPWARD_LIMIT": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "Resolved Discord: 0.0.402 - [12.0]" in result.stdout
    command_log = _read_command_log(env)
    assert _command_log_contains(command_log, "aria2c", _expected_installer_url("stable", "0.0.402"))
    assert not _command_log_contains(command_log, "aria2c", _DOWNLOAD_URLS["stable"])
    assert _command_log_contains(command_log, "hdiutil", "attach")
    if openasar_mode == "local":
        installed_asar = (
            _application_path(env["applications_root"], "stable")
            / "Contents"
            / "Resources"
            / "app.asar"
        )
        assert installed_asar.read_bytes() == env["openasar_source"].read_bytes()
    _assert_no_download_artifacts(env)


def test_update_with_os_filter_resolves_distinct_versions_for_all_channels(
    env: dict[str, Path],
):
    matching_versions = {
        "stable": "0.0.5",
        "ptb": "0.0.4",
        "canary": "0.0.3",
    }
    zip_entries: list[tuple[str, Path]] = []
    header_entries: list[tuple[str, str]] = []

    for channel in APP_NAMES:
        for suffix in range(5, 2, -1):
            version = f"0.0.{suffix}"
            minimum = "11.0" if version == matching_versions[channel] else "12.0"
            zip_path = _write_fake_update_select_zip(
                env,
                channel,
                version,
                minimum,
                zipfile.ZIP_STORED,
            )
            header_entries.append(
                (f"*{_CDN_HOSTS[channel]}/apps/osx/{version}/{_DMG_FILENAMES[channel]}", "200")
            )
            zip_entries.append((_expected_zip_url(channel, version), zip_path))

    result = _run_manager(
        env,
        "--channel",
        "all",
        "--update",
        "--OS=11",
        extra_env={
            "TEST_FAKE_CURL_UPDATE_MANIFEST": '{"name":"0.0.5"}',
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(
                _write_fake_curl_header_map(env, header_entries)
            ),
            "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                _write_fake_curl_zip_source_map(env, zip_entries)
            ),
            "DISCORD_UPDATE_SELECT_UPWARD_LIMIT": "1",
            "DISCORD_UPDATE_OS_SCAN_LIMIT": "3",
        },
    )

    assert result.returncode == 0, result.stderr
    command_log = _read_command_log(env)
    for channel, version in matching_versions.items():
        assert f"Resolved {APP_NAMES[channel]}: {version} - [11.0]" in result.stdout
        assert _command_log_contains(
            command_log,
            "aria2c",
            _expected_installer_url(channel, version),
        )
        assert not _command_log_contains(command_log, "aria2c", _DOWNLOAD_URLS[channel])
        assert _application_path(env["applications_root"], channel).exists()

    _assert_no_download_artifacts(env)


def test_update_with_os_filter_failure_precedes_all_mutation(
    env: dict[str, Path],
):
    zip_entries: list[tuple[str, Path]] = []
    header_entries: list[tuple[str, str]] = []
    matching_versions = {
        "stable": "0.0.5",
        "ptb": "0.0.4",
    }

    for channel in APP_NAMES:
        for suffix in range(5, 2, -1):
            version = f"0.0.{suffix}"
            minimum = (
                "11.0"
                if matching_versions.get(channel) == version
                else "12.0"
            )
            zip_path = _write_fake_update_select_zip(
                env,
                channel,
                version,
                minimum,
                zipfile.ZIP_STORED,
            )
            header_entries.append(
                (f"*{_CDN_HOSTS[channel]}/apps/osx/{version}/{_DMG_FILENAMES[channel]}", "200")
            )
            zip_entries.append((_expected_zip_url(channel, version), zip_path))

    preserved_paths: list[Path] = []
    for channel in APP_NAMES:
        app_path = _application_path(env["applications_root"], channel)
        app_path.mkdir(parents=True)
        app_marker = app_path / "preserve-app.txt"
        app_marker.write_text(channel, encoding="utf-8")
        preserved_paths.append(app_marker)

        data_dir = _settings_path(env["home"], channel).parent
        data_dir.mkdir(parents=True)
        (data_dir / "settings.json").write_text("{}", encoding="utf-8")
        cleanup_marker = data_dir / "installer.db"
        cleanup_marker.write_text(channel, encoding="utf-8")
        preserved_paths.append(cleanup_marker)

    result = _run_manager(
        env,
        "--channel",
        "all",
        "--update",
        "--OS",
        "11",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={
            "TEST_FAKE_CURL_UPDATE_MANIFEST": '{"name":"0.0.5"}',
            "TEST_FAKE_CURL_HEADER_MAP_FILE": str(
                _write_fake_curl_header_map(env, header_entries)
            ),
            "TEST_FAKE_CURL_ZIP_SOURCE_MAP_FILE": str(
                _write_fake_curl_zip_source_map(env, zip_entries)
            ),
            "DISCORD_UPDATE_SELECT_UPWARD_LIMIT": "1",
            "DISCORD_UPDATE_OS_SCAN_LIMIT": "3",
        },
    )

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "No direct-CDN builds for Discord Canary matched exact LSMinimumSystemVersion 11.0" in combined_output
    assert "No changes were made" in combined_output
    assert all(path.read_text(encoding="utf-8") in APP_NAMES for path in preserved_paths)

    command_log = _read_command_log(env)
    assert not any(
        entry.startswith(("aria2c\t", "hdiutil\t", "ditto\t", "osascript\t", "cp\t", "mv\t", "rm\t"))
        for entry in command_log
    )
    assert "Stopping all selected Discord clients before continuing..." not in result.stdout
    _assert_no_download_artifacts(env)


def test_update_replaces_all_channels(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "all", "--update")

    assert result.returncode == 0
    assert "Stopping all selected Discord clients before continuing..." in result.stdout

    command_log = _read_command_log(env)
    for channel in APP_NAMES:
        app_path = _application_path(env["applications_root"], channel)
        assert app_path.exists()
        assert _command_log_contains(command_log, "aria2c", _DOWNLOAD_URLS[channel])
        assert _command_log_contains(command_log, "hdiutil", "attach")

    assert "== Discord ==" in result.stdout
    assert "== Discord PTB ==" in result.stdout
    assert "== Discord Canary ==" in result.stdout
    _assert_no_download_artifacts(env)


def test_update_allows_missing_data_dir(env: dict[str, Path]):
    data_dir = env["home"] / "Library" / "Application Support" / "discord"
    assert not data_dir.exists()

    result = _run_manager(env, "--channel", "stable", "--update", "401")

    assert result.returncode == 0
    assert "data directory not found, so there is no App Support cleanup to run:" in result.stdout
    assert _application_path(env["applications_root"], "stable").exists()
    _assert_no_download_artifacts(env)


def test_update_refuses_invalid_data_directory_before_downloader(env: dict[str, Path]):
    data_dir = env["home"] / "Library" / "Application Support" / "discord"
    data_dir.mkdir(parents=True)
    (data_dir / "installer.db").write_text("x", encoding="utf-8")

    result = _run_manager(env, "--channel", "stable", "--update", "401")

    assert result.returncode == 1
    assert "Refusing to continue because the target does not look like" in (result.stdout + result.stderr)
    assert not _command_log_contains(_read_command_log(env), "aria2c", "0.0.401")
    assert not _command_log_contains(_read_command_log(env), "hdiutil", "attach")
    _assert_no_download_artifacts(env)


def test_update_preserves_settings_json_during_cleanup(env: dict[str, Path]):
    data_dir = _settings_path(env["home"], "stable").parent
    data_dir.mkdir(parents=True)
    settings_path = _settings_path(env["home"], "stable")
    initial_settings = {"keep": "value", "nested": {"level": 1}}
    settings_path.write_text(json.dumps(initial_settings), encoding="utf-8")
    (data_dir / "Local Storage").mkdir()
    (data_dir / "installer.db").write_text("x", encoding="utf-8")
    (data_dir / "modules").mkdir()
    (data_dir / "download").mkdir()
    (data_dir / "Cache").mkdir()

    result = _run_manager(env, "--channel", "stable", "--update", "401")

    assert result.returncode == 0
    assert _read_settings(settings_path) == initial_settings
    assert (data_dir / "Local Storage").exists()
    assert not (data_dir / "installer.db").exists()
    assert not (data_dir / "modules").exists()
    assert not (data_dir / "download").exists()
    assert not (data_dir / "Cache").exists()
    _assert_no_download_artifacts(env)


def test_update_removes_previous_app_bundle_before_copy(env: dict[str, Path]):
    app_path = _application_path(env["applications_root"], "stable")
    executable_path = app_path / "Contents" / "MacOS" / APP_NAMES["stable"]
    legacy_marker = app_path / "legacy.txt"
    app_path.mkdir(parents=True)
    (app_path / "Contents").mkdir(parents=True)
    (app_path / "Contents" / "Info.plist").write_text("legacy", encoding="utf-8")
    (app_path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    legacy_marker.write_text("legacy", encoding="utf-8")
    executable_path.write_text("legacy", encoding="utf-8")
    executable_path.chmod(0o700)

    result = _run_manager(env, "--channel", "stable", "--update", "401")

    assert result.returncode == 0
    command_log = _read_command_log(env)
    assert not legacy_marker.exists()
    remove_index = _command_log_index(command_log, "rm", str(app_path))
    copy_index = _command_log_index(command_log, "ditto", str(app_path))
    assert remove_index is not None
    assert copy_index is not None
    assert remove_index < copy_index
    _assert_no_download_artifacts(env)


def test_update_successful_replacement_cleans_artifacts(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--update", "401")

    assert result.returncode == 0
    assert not (env["script"].parent / "Discord-stable-installer (0.0.401).dmg.aria2").exists()
    _assert_no_download_artifacts(env)


def test_update_fails_if_mount_attachment_fails_and_cleans_artifacts(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        extra_env={"TEST_FAKE_HDIUTIL_ATTACH_FAIL_ATTEMPTS": "1"},
    )

    assert result.returncode == 1
    assert "The application was not replaced." not in result.stdout
    assert _command_log_contains(_read_command_log(env), "hdiutil", "attach")
    _assert_no_download_artifacts(env)


def test_update_fails_when_mounted_image_has_no_app_and_cleans_artifacts(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        extra_env={"TEST_FAKE_HDIUTIL_MODE": "no-app"},
    )

    assert result.returncode == 1
    assert "Could not find a Discord app inside the mounted installer:" in (result.stdout + result.stderr)
    assert _command_log_contains(_read_command_log(env), "hdiutil", "attach")
    _assert_no_download_artifacts(env)


def test_update_guard_update_replacement_failure_cleans_mounted_image(env: dict[str, Path]):
    data_dir = _settings_path(env["home"], "stable").parent
    data_dir.mkdir(parents=True)
    (data_dir / "settings.json").write_text("{}", encoding="utf-8")
    (data_dir / "Local Storage").mkdir()
    recreated_target = data_dir / "installer.db"

    _write_hdiutil_starts_background_discord(env["fake_bin"])
    _write_osascript_stops_background_discord(env["fake_bin"])
    env["fake_state"].mkdir(exist_ok=True)
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        extra_env={
            "TEST_FAKE_START_CLIENT_DURING_REPLACE": "1",
            "TEST_FAKE_APPLICATIONS_ROOT": str(env["applications_root"]),
            "TEST_FAKE_RECREATE_CLEANUP_TARGET": str(recreated_target),
            "TEST_FAKE_RM_FAIL_PATH": str(recreated_target),
        },
    )

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "Discord restarted during update replacement." in combined_output
    assert "Failed to delete installer.db:" in combined_output
    assert _command_log_contains(_read_command_log(env), "hdiutil", "detach")
    assert "app replaced successfully." not in result.stdout
    assert recreated_target.exists()
    _assert_no_download_artifacts(env)


def test_update_guard_quit_failure_cleans_mounted_image(env: dict[str, Path]):
    data_dir = _settings_path(env["home"], "stable").parent
    data_dir.mkdir(parents=True)
    (data_dir / "settings.json").write_text("{}", encoding="utf-8")
    (data_dir / "Local Storage").mkdir()

    _write_hdiutil_starts_background_discord(env["fake_bin"])
    _disable_forced_quit_in_test_copy(env)
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        extra_env={
            "TEST_FAKE_START_CLIENT_DURING_REPLACE": "1",
            "TEST_FAKE_APPLICATIONS_ROOT": str(env["applications_root"]),
        },
    )

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "Discord restarted during update replacement." in combined_output
    assert "Discord is still running. Refusing to continue." in combined_output
    assert _command_log_contains(_read_command_log(env), "hdiutil", "detach")
    assert "app replaced successfully." not in result.stdout
    _assert_no_download_artifacts(env)


def test_update_retries_ditto_three_times_before_failing(env: dict[str, Path]):
    app_path = _application_path(env["applications_root"], "stable")
    (app_path / "Contents").mkdir(parents=True, exist_ok=True)
    (app_path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    (app_path / "Contents" / "Info.plist").write_text("legacy", encoding="utf-8")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        extra_env={"TEST_FAKE_DITTO_FAIL_ATTEMPTS": "3"},
    )

    assert result.returncode == 1
    command_log = _read_command_log(env)
    assert _command_log_contains(command_log, "hdiutil", "attach")
    assert len([entry for entry in command_log if entry.startswith("ditto\t")]) == 3
    assert "replacement failed after 3 attempts." in (result.stdout + result.stderr)
    assert "Retrying" in result.stdout
    assert not app_path.exists()
    _assert_no_download_artifacts(env)


def test_update_preserves_existing_app_when_removal_fails(env: dict[str, Path],):
    data_dir = _settings_path(env["home"], "stable").parent
    data_dir.mkdir(parents=True)
    (data_dir / "settings.json").write_text("{}", encoding="utf-8")
    (data_dir / "Local Storage").mkdir()

    app_path = _application_path(env["applications_root"], "stable")
    app_path.mkdir(parents=True)
    preserved_marker = app_path / "preserve-me.txt"
    preserved_marker.write_text("preserve-me", encoding="utf-8")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        extra_env={"TEST_FAKE_RM_FAIL_PATH": str(app_path)},
    )

    assert result.returncode == 1
    assert "Failed to remove the existing Discord app." in (result.stdout + result.stderr)
    assert preserved_marker.exists()
    _assert_no_download_artifacts(env)
