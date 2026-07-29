from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from _helpers import (
    APP_NAMES,
    DATA_DIRS,
    _assert_no_download_artifacts,
    _assert_no_update_artifacts,
    _application_path,
    _create_manager_environment,
    _read_settings,
    _run_manager,
    _settings_path,
)


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _write_hdiutil_with_looping_client(fake_bin: Path) -> None:
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
    printf '#!/usr/bin/env sh\\n/bin/sleep "$@"\\n' > "$app_path/Contents/MacOS/$executable"
  fi
  chmod +x "$app_path/Contents/MacOS/$executable"
  : > "$app_path/Contents/Resources/app.asar"
  exit 0
elif [ "$1" = "detach" ]; then
  exit 0
else
  exit 0
fi
""",
    )


def _write_sleep_spawns_client(fake_bin: Path) -> None:
    _write_executable(
        fake_bin / "sleep",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'sleep\\targs=%s\\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
marker="${state_dir}/test-lock-client-spawned"

if [ -z "${TEST_FAKE_LOCK_CLIENT_EXE:-}" ]; then
  /bin/sleep "$@"
  exit $?
fi

if [ ! -f "$marker" ] && [ "${TEST_FAKE_LOCK_CLIENT_EXECUTE:-0}" = "1" ]; then
  touch "$marker"
  "$TEST_FAKE_LOCK_CLIENT_EXE" 1000 >/dev/null 2>&1 &
  if [ -n "${TEST_FAKE_DISCORD_PID_TRACKER:-}" ]; then
    printf '%s\\n' "$!" >> "${TEST_FAKE_DISCORD_PID_TRACKER}"
  fi
fi

/bin/sleep "$@"
""",
    )


def _read_tracker_pids(tracker: Path) -> list[int]:
    if not tracker.exists():
        return []

    return [
        int(raw_pid)
        for raw_pid in tracker.read_text(encoding="utf-8").splitlines()
        if raw_pid.strip().isdigit()
    ]


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _pid_command(pid: int) -> str:
    completed = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "command="],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip()


def _wait_for_process_exit(pid: int, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_running(pid):
            return True
        time.sleep(0.02)
    return not _is_process_running(pid)


@pytest.mark.parametrize(
    "args",
    [
        ["--channel", "stable", "--update", "401", "--openasar-source", "{openasar}", "--lock"],
        ["--openasar-source", "{openasar}", "--lock", "--update", "401", "--channel", "stable"],
        ["--channel", "stable", "--lock", "--openasar-source", "{openasar}", "--update", "401"],
    ],
)
def test_lock_argument_ordering(env: dict[str, Path], args: list[str]):
    run_args = [arg.format(openasar=str(env["openasar_source"])) for arg in args]
    result = _run_manager(env, *run_args)

    assert result.returncode == 0, result.stderr
    settings = _read_settings(_settings_path(env["home"], "stable"))
    assert settings["openasar"]["VersionLock"] == "401"


@pytest.mark.parametrize("version", ["401", "0.0.401"])
def test_lock_accepts_short_and_long_version_formats(env: dict[str, Path], version: str):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        version,
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr
    settings = _read_settings(_settings_path(env["home"], "stable"))
    assert settings["openasar"]["VersionLock"] == "401"


def test_lock_accepts_openasar_flag_without_source(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar",
        "--lock",
    )

    assert result.returncode == 0, result.stderr
    settings = _read_settings(_settings_path(env["home"], "stable"))
    assert settings["openasar"]["VersionLock"] == "401"


def test_lock_accepts_update_equals_version_form(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update=401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr
    settings = _read_settings(_settings_path(env["home"], "stable"))
    assert settings["openasar"]["VersionLock"] == "401"


@pytest.mark.parametrize("channel", ["stable", "ptb", "canary"])
def test_lock_uses_channel_specific_paths(env: dict[str, Path], channel: str):
    result = _run_manager(
        env,
        "--channel",
        channel,
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr

    app_path = _application_path(env["applications_root"], channel)
    assert app_path.exists()

    expected_app_name = APP_NAMES[channel]
    assert str(app_path) in result.stdout
    assert _settings_path(env["home"], channel).exists()
    settings = _read_settings(_settings_path(env["home"], channel))
    assert settings["openasar"]["VersionLock"] == "401"
    assert expected_app_name in str(result.stdout)


def test_lock_preserves_existing_openasar_block(env: dict[str, Path]):
    settings = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    settings.mkdir(parents=True, exist_ok=True)
    settings_path = settings / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "openasar": {"Theme": "dark", "VersionLock": "399"},
                "foo": "bar",
                "other": 12,
            },
            indent=2,
        )
    )
    settings_path.chmod(0o755)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr

    updated = _read_settings(settings_path)
    assert updated["openasar"]["Theme"] == "dark"
    assert updated["openasar"]["VersionLock"] == "401"
    assert updated["foo"] == "bar"
    assert updated["other"] == 12
    assert settings_path.stat().st_mode & 0o777 == 0o755
    assert settings_path.read_bytes().endswith(b"}")
    assert not settings_path.read_bytes().endswith(b"\n")


def test_lock_appends_openasar_block_when_missing(env: dict[str, Path]):
    settings = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    settings.mkdir(parents=True, exist_ok=True)
    settings_path = settings / "settings.json"
    settings_path.write_text(json.dumps({"foo": "keep"}, indent=2))

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr

    updated = _read_settings(settings_path)
    assert updated["foo"] == "keep"
    assert updated["openasar"] == {"VersionLock": "401"}


def test_lock_creates_settings_directory_when_missing(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr

    settings_path = _settings_path(env["home"], "stable")
    assert settings_path.exists()
    settings = _read_settings(settings_path)
    assert settings == {"openasar": {"VersionLock": "401"}}
    assert settings_path.stat().st_mode & 0o777 == 0o600
    assert not settings_path.read_bytes().endswith(b"\n")


def test_lock_creates_settings_in_existing_empty_data_directory(env: dict[str, Path]):
    data_dir = _settings_path(env["home"], "stable").parent
    data_dir.mkdir(parents=True)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr
    assert _read_settings(data_dir / "settings.json") == {
        "openasar": {"VersionLock": "401"}
    }


@pytest.mark.parametrize("version, message", [("0401", "--lock versions cannot contain leading zeroes"), ("abc", "Invalid Discord version: abc")])
def test_lock_rejects_invalid_version_formats(env: dict[str, Path], version: str, message: str):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        version,
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert message in (result.stdout + result.stderr)


def test_lock_rejects_malformed_settings_file(env: dict[str, Path]):
    settings_dir = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text("{bad")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert "settings.json is invalid" in result.stderr
    assert settings_path.read_text() == "{bad"
    _assert_no_update_artifacts(env)


def test_lock_rejects_non_object_root_settings(env: dict[str, Path]):
    settings_dir = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text("[]")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert "settings.json is invalid" in result.stderr
    assert settings_path.read_text() == "[]"
    _assert_no_update_artifacts(env)


def test_lock_rejects_non_object_openasar_value(env: dict[str, Path]):
    settings_dir = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text('{"openasar": 123}')

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert "openasar value is not an object" in result.stderr
    assert settings_path.read_text() == '{"openasar": 123}'
    _assert_no_update_artifacts(env)


def test_lock_rejects_unsafe_json_integer_without_mutation(env: dict[str, Path]):
    settings_dir = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"
    original = '{"openasar": {}, "largeInteger": 9007199254740993}'
    settings_path.write_text(original)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert "cannot be preserved safely" in result.stderr
    assert settings_path.read_text() == original
    _assert_no_update_artifacts(env)


def test_lock_preflights_settings_before_remote_openasar_download(env: dict[str, Path]):
    settings_path = _settings_path(env["home"], "stable")
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{bad")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar",
        "--lock",
    )

    assert result.returncode != 0
    assert "settings.json is invalid" in result.stderr
    assert not (env["script"].parent / "openasar-app.asar").exists()
    _assert_no_update_artifacts(env)


def test_lock_rejects_symlinked_data_dir_and_settings(env: dict[str, Path]):
    target = env["home"] / "Library" / "Application Support" / "stable_target"
    target.mkdir(parents=True)
    (target / "settings.json").write_text('{}')

    data_dir = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    if data_dir.exists():
        data_dir.unlink()
    data_dir.symlink_to(target)

    settings_path = data_dir / "settings.json"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert "data directory is a symlink" in result.stderr
    assert settings_path.read_text() == "{}"
    _assert_no_update_artifacts(env)


def test_lock_rejects_symlinked_settings_file(env: dict[str, Path]):
    data_dir = env["home"] / "Library" / "Application Support" / DATA_DIRS["stable"]
    data_dir.mkdir(parents=True, exist_ok=True)
    settings_link_target = env["home"] / "Library" / "Application Support" / "settings-target.json"
    settings_link_target.write_text('{}')
    settings_path = data_dir / "settings.json"
    settings_path.symlink_to(settings_link_target)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode != 0
    assert "settings.json is a symlink" in result.stderr
    assert settings_link_target.read_text() == "{}"
    _assert_no_update_artifacts(env)


def test_lock_rejects_data_path_that_is_not_a_directory(env: dict[str, Path]):
    data_dir = _settings_path(env["home"], "stable").parent
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    data_dir.write_text("not-a-directory", encoding="utf-8")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 1
    assert "data directory is not a directory" in result.stderr
    assert data_dir.read_text(encoding="utf-8") == "not-a-directory"
    _assert_no_update_artifacts(env)


def test_lock_rejects_settings_path_that_is_not_a_regular_file(
    env: dict[str, Path],
):
    settings_path = _settings_path(env["home"], "stable")
    settings_path.mkdir(parents=True)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 1
    assert "settings.json is not a regular file" in result.stderr
    assert settings_path.is_dir()
    _assert_no_update_artifacts(env)


def test_lock_does_not_replace_without_openasar_source(tmp_path: Path):
    env = _create_manager_environment(tmp_path)
    missing_source = env["home"] / "missing-openasar.app.asar"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(missing_source),
        "--lock",
    )

    assert result.returncode != 0
    assert "was not found" in result.stderr.lower()
    assert "cannot proceed with --lock" in (result.stderr + result.stdout).lower()

    _assert_no_update_artifacts(env)
    assert not _settings_path(env["home"], "stable").exists()


def test_lock_does_not_change_settings_when_openasar_injection_fails(
    env: dict[str, Path],
):
    settings_path = _settings_path(env["home"], "stable")
    settings_path.parent.mkdir(parents=True)
    original = {"openasar": {"VersionLock": "399"}, "keep": True}
    settings_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
        extra_env={"TEST_FAKE_CP_FAIL_OPENASAR": "1"},
    )

    assert result.returncode == 1
    assert "OpenAsar injection failed while staging the payload" in (
        result.stdout + result.stderr
    )
    assert _read_settings(settings_path) == original
    _assert_no_download_artifacts(env)


def test_lock_aborts_if_client_reappears_before_settings_mutation(env: dict[str, Path]):
    settings_path = _settings_path(env["home"], "stable")
    settings_path.parent.mkdir(parents=True)
    original = {"openasar": {"VersionLock": "399"}, "keep": True}
    settings_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    app_executable = (
        env["applications_root"] / "Discord.app" / "Contents" / "MacOS" / APP_NAMES["stable"]
    )
    _write_hdiutil_with_looping_client(env["fake_bin"])
    _write_sleep_spawns_client(env["fake_bin"])

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
        extra_env={
            "TEST_FAKE_LOCK_CLIENT_EXE": str(app_executable),
            "TEST_FAKE_LOCK_CLIENT_EXECUTE": "1",
        },
    )

    tracked_pids = _read_tracker_pids(env["discord_pid_tracker"])
    try:
        assert result.returncode == 1
        assert "Cannot write --lock for Discord because the client reappeared during update:" in (
            result.stdout + result.stderr
        )
        assert _read_settings(settings_path) == original
        assert tracked_pids, "Expected test fake lock-client process to be spawned."
        assert all(_is_process_running(pid) for pid in tracked_pids)
    finally:
        allowed_prefix = f"{env['applications_root']}/"
        for pid in tracked_pids:
            if _is_process_running(pid):
                command = _pid_command(pid)
                assert command.startswith(allowed_prefix), (
                    f"Refusing to signal a process outside the test Applications root: "
                    f"pid={pid} command={command}"
                )
                os.kill(pid, 15)
                if not _wait_for_process_exit(pid):
                    command = _pid_command(pid)
                    assert command.startswith(allowed_prefix), (
                        f"Refusing to force-stop a process outside the test Applications root: "
                        f"pid={pid} command={command}"
                    )
                    os.kill(pid, 9)
                    assert _wait_for_process_exit(pid)
