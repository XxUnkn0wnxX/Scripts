from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from _helpers import APP_NAMES, _application_path, _read_command_log, _run_manager, _settings_path

_APP_SLEEP_SECONDS = "99999"
_SLEEP_BIN = Path("/bin/sleep")
_PID_POLL_INTERVAL = 0.05


def _pid_poll_deadline(seconds: float) -> float:
    return time.monotonic() + seconds


def _wait_for_pid_exit(pid: int, *, timeout: float = 3.0) -> bool:
    deadline = _pid_poll_deadline(timeout)
    while time.monotonic() < deadline:
        if not _is_pid_running(pid):
            return True
        time.sleep(_PID_POLL_INTERVAL)
    return not _is_pid_running(pid)


def _pid_command(pid: int) -> str:
    try:
        completed = subprocess.run(
            ["/bin/ps", "-p", str(pid), "-o", "command="],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _command_is_temp_scoped(command: str, allowed_prefixes: set[str]) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()

    if not parts:
        return False

    candidates = [parts[0]]
    if parts[0] in {"/bin/zsh", "/usr/bin/zsh", "/bin/sh", "/usr/bin/sh"} and len(parts) > 1:
        option_index = 1
        while option_index < len(parts) and parts[option_index].startswith("-"):
            option_index += 1
        if option_index < len(parts):
            candidates.append(parts[option_index])

    return any(
        candidate == prefix or candidate.startswith(f"{prefix}{os.sep}")
        for candidate in candidates
        for prefix in allowed_prefixes
    )


def _read_tracker_pids(tracker: Path) -> list[int]:
    if not tracker.exists():
        return []
    pids: list[int] = []
    for line in tracker.read_text(encoding="utf-8").splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


def _start_reaper_thread(process: subprocess.Popen[bytes]) -> threading.Thread:
    def _reap() -> None:
        try:
            process.wait()
        except OSError:
            pass

    thread = threading.Thread(target=_reap, daemon=True)
    thread.start()
    return thread


def _install_sleep_stub(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    shutil.copyfile(_SLEEP_BIN, path)
    path.chmod(0o755)


def _write_executable(path: Path, content: str, *, mode: int = 0o755) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def _prepare_data_directory(env: dict[str, Path], channel: str) -> Path:
    data_dir = _settings_path(env["home"], channel).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "settings.json").write_text("{}", encoding="utf-8")
    return data_dir


def _prepare_standalone_app(env: dict[str, Path], channel: str = "stable", *, asar_payload: bytes = b"base-asar") -> Path:
    app_path = _application_path(env["applications_root"], channel)
    app_path.mkdir(parents=True, exist_ok=True)
    executable = app_path / "Contents" / "MacOS" / APP_NAMES[channel]
    resources = app_path / "Contents" / "Resources"
    info_plist = app_path / "Contents" / "Info.plist"

    info_plist.parent.mkdir(parents=True, exist_ok=True)
    executable.parent.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    info_plist.write_text("plist", encoding="utf-8")
    _install_sleep_stub(executable)
    (resources / "app.asar").write_bytes(asar_payload)

    return app_path


def _start_wrapped_app(
    env: dict[str, Path],
    channel: str = "stable",
    *,
    nested_payload: bytes = b"wrapped-asar",
    top_level_payload: bytes | None = None,
) -> Path:
    app_path = _prepare_standalone_app(env, channel=channel, asar_payload=b"")
    resources = app_path / "Contents" / "Resources"
    wrapper_dir = resources / "app"
    app_asar = resources / "app.asar"
    nested_asar = resources / "betterdiscord.app.asar"

    app_asar.unlink()
    if top_level_payload is not None:
        app_asar.write_bytes(top_level_payload)

    wrapper_dir.mkdir()
    (wrapper_dir / ".betterdiscord-inject.json").write_text(
        json.dumps(
            {
                "schema": "1",
                "owner": "betterdiscord",
                "style": "app-wrapper",
                "channel": channel,
                "mode": "release",
                "loader": "index.js",
                "payload": "../betterdiscord.app.asar",
                "bdPath": "/tmp/betterdiscord",
                "installationId": "bd-install-id",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (wrapper_dir / "index.js").write_text(
        "// __betterdiscord_inject_meta__\nmodule.exports = require(\"../betterdiscord.app.asar\");\n",
        encoding="utf-8",
    )
    (wrapper_dir / "package.json").write_text(json.dumps({"main": "index.js"}, indent=2), encoding="utf-8")
    nested_asar.write_text(nested_payload.decode("utf-8", errors="replace"), encoding="utf-8")
    return resources


def _write_betterdiscord_recovery_state(
    data_dir: Path,
    *,
    include_helper: bool = True,
    helper_pid: str | None = None,
    create_helper: bool = True,
    recovery_disabled: str | None = None,
) -> Path:
    bootstrap_dir = data_dir / "betterdiscord-bootstrap"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)

    if include_helper:
        helper_path = bootstrap_dir / "betterdiscord-update-helper.zsh"
        if create_helper:
            _write_executable(
                helper_path,
                "#!/usr/bin/env sh\n"
                "if [ -n \"${TEST_FAKE_DISCORD_PID_TRACKER:-}\" ]; then\n"
                "  printf '%s\\n' \"$$\" >> \"${TEST_FAKE_DISCORD_PID_TRACKER}\"\n"
                "fi\n"
                "trap 'exit 0' TERM\n"
                "while :; do\n"
                "  /bin/sleep 99999\n"
                "done\n",
            )

    if helper_pid is not None:
        (bootstrap_dir / "betterdiscord-update-helper.pid").write_text(helper_pid, encoding="utf-8")
    if recovery_disabled is not None:
        recovery_disabled_path = bootstrap_dir / "recovery-disabled"
        if recovery_disabled == "symlink":
            target = bootstrap_dir / "recovery-disabled-target"
            target.write_text("{}", encoding="utf-8")
            recovery_disabled_path.symlink_to(target)
        else:
            recovery_disabled_path.write_text("disabled", encoding="utf-8")

    (bootstrap_dir / "update-pending.json").write_text("{}", encoding="utf-8")
    (bootstrap_dir / "wrapper-ready.json").write_text("{}", encoding="utf-8")
    (bootstrap_dir / "active-run").write_text("{}", encoding="utf-8")
    recovery_runs = bootstrap_dir / "recovery-runs"
    recovery_runs.mkdir(exist_ok=True)
    (recovery_runs / "state.json").write_text("{}", encoding="utf-8")

    return bootstrap_dir


def _write_fake_open(fake_bin: Path) -> None:
    _write_executable(
        fake_bin / "open",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'open\targs=%s\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
attempt_file="${state_dir}/fake_open_attempts"
fail_attempts="${TEST_FAKE_OPEN_FAIL_ATTEMPTS:-0}"
attempt=1
if [ -f "$attempt_file" ]; then
  parsed_attempt="$(cat "$attempt_file" 2>/dev/null || echo 0)"
  attempt=$((parsed_attempt + 1))
fi
printf '%s\n' "$attempt" > "$attempt_file"

if [ "$attempt" -le "$fail_attempts" ]; then
  printf 'open attempt %s intentionally failed\\n' "$attempt" >&2
  exit 1
fi

if [ -n "$TEST_FAKE_DISCORD_EXECUTABLE" ] && [ -n "$TEST_FAKE_DISCORD_ALLOWED_EXECUTABLE" ] &&
   [ "$TEST_FAKE_DISCORD_EXECUTABLE" = "$TEST_FAKE_DISCORD_ALLOWED_EXECUTABLE" ] && [ -x "$TEST_FAKE_DISCORD_EXECUTABLE" ]; then
  "$TEST_FAKE_DISCORD_EXECUTABLE" "${TEST_FAKE_DISCORD_EXECUTABLE_ARGS:-}" >/dev/null 2>&1 &
  fake_open_pid=$!
  if [ -n "${TEST_FAKE_DISCORD_PID_TRACKER:-}" ]; then
    printf '%s\\n' "$fake_open_pid" >> "${TEST_FAKE_DISCORD_PID_TRACKER}"
  fi
fi
""",
        mode=0o755,
    )


def _write_fake_osascript(fake_bin: Path) -> None:
    _write_executable(
        fake_bin / "osascript",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'osascript\targs=%s\n' "$*" >> "$log_file"
fi

kill_test_discord_pid() {
  candidate_pid="$1"
  allowed_executable="${TEST_FAKE_DISCORD_ALLOWED_EXECUTABLE:-}"
  case "$candidate_pid" in
    ''|*[!0-9]*) return 0 ;;
  esac
  [ "$candidate_pid" != "0" ] || return 0
  [ -n "$allowed_executable" ] || return 0

  candidate_command="$(/bin/ps -p "$candidate_pid" -o command= 2>/dev/null || true)"
  case "$candidate_command" in
    "$allowed_executable"|"$allowed_executable "*)
      /bin/kill -KILL "$candidate_pid" >/dev/null 2>&1 || true
      ;;
  esac
}

kill_test_discord_pid "${TEST_FAKE_QUIT_PID:-}"

if [ -n "${TEST_FAKE_DISCORD_PID_TRACKER:-}" ] && [ -r "$TEST_FAKE_DISCORD_PID_TRACKER" ]; then
  while IFS= read -r tracked_pid; do
    kill_test_discord_pid "$tracked_pid"
  done < "$TEST_FAKE_DISCORD_PID_TRACKER"
fi
""",
        mode=0o755,
    )


def _write_fake_moving_helper(fake_bin: Path, fail_path: Path) -> None:
    escaped_fail = shlex.quote(str(fail_path))
    _write_executable(
        fake_bin / "mv",
        f"""#!/usr/bin/env sh

log_file="${{TEST_COMMAND_LOG:-}}"
if [ -n "$log_file" ]; then
  printf 'mv\targs=%s\n' "$*" >> "$log_file"
fi

for arg in "$@"; do
  if [ "$arg" = {escaped_fail} ]; then
    exit 1
  fi
done

exec /bin/mv "$@"
""",
        mode=0o755,
    )


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


@pytest.fixture
def tracked_processes(env: dict[str, Path]):
    handles: list[subprocess.Popen[bytes]] = []
    tracked_paths = {str(env["applications_root"]), str(env["home"])}
    tracker = env["discord_pid_tracker"]

    def _spawn(path: Path, *extra_args: str) -> subprocess.Popen[bytes]:
        process_env = os.environ.copy()
        process_env["TEST_FAKE_DISCORD_PID_TRACKER"] = str(tracker)
        executable_args = list(extra_args)
        if not executable_args and path.name in APP_NAMES.values():
            executable_args.append(_APP_SLEEP_SECONDS)
        if path.name == "betterdiscord-update-helper.zsh":
            args = ["/bin/zsh", "-f", str(path), "--test", *executable_args]
        else:
            args = [str(path), *executable_args]
        process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=process_env,
        )
        handles.append(process)
        return process

    yield _spawn

    for process in handles:
        try:
            os.kill(process.pid, 0)
            cmd = _pid_command(process.pid)
        except ProcessLookupError:
            pass
        except OSError:
            pass
        else:
            if not cmd:
                pytest.fail(f"Process command unavailable during teardown: pid={process.pid}")
            if not _command_is_temp_scoped(cmd, tracked_paths):
                pytest.fail(f"Process escaped temp scope: pid={process.pid} cmd={cmd}")

        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
        except OSError:
            pass

    for pid in _read_tracker_pids(tracker):
        cmd = _pid_command(pid)
        if cmd and not _command_is_temp_scoped(cmd, tracked_paths):
            pytest.fail(f"Tracked pid escaped temp scope: pid={pid} cmd={cmd}")
        if not cmd:
            if _is_pid_running(pid):
                pytest.fail(f"Tracked pid command unavailable during teardown: pid={pid}")
            continue
        if _wait_for_pid_exit(pid):
            continue
        for signal in (15, 9):
            try:
                os.kill(pid, signal)
            except ProcessLookupError:
                break
            except OSError:
                pass
            if _wait_for_pid_exit(pid, timeout=1):
                break
        assert not _is_pid_running(pid), f"Tracked process remained alive after teardown: {pid}"


def test_relaunch_closed_client_makes_zero_open_calls(env: dict[str, Path]):
    _prepare_standalone_app(env, "stable", asar_payload=b"base-asar")
    _prepare_data_directory(env, "stable")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 0, result.stderr
    assert "OpenAsar installation verified for Discord; the client remains closed." in result.stdout
    assert all(not entry.startswith("open\t") for entry in _read_command_log(env))


def test_relaunch_stops_running_client_and_relaunches_via_fake_open(
    env: dict[str, Path], tracked_processes,
):
    _prepare_standalone_app(env, "stable", asar_payload=b"base-asar")
    _prepare_data_directory(env, "stable")
    _write_fake_open(env["fake_bin"])
    _write_fake_osascript(env["fake_bin"])

    app_path = _application_path(env["applications_root"], "stable")
    executable = app_path / "Contents" / "MacOS" / "Discord"
    process = tracked_processes(executable)
    old_pid = process.pid

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={
            "TEST_FAKE_DISCORD_EXECUTABLE": str(executable),
            "TEST_FAKE_DISCORD_ALLOWED_EXECUTABLE": str(executable),
            "TEST_FAKE_DISCORD_EXECUTABLE_ARGS": _APP_SLEEP_SECONDS,
            "TEST_FAKE_QUIT_PID": str(old_pid),
        },
        path_override=env["fake_bin"],
        required_tools=("aria2c", "curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
    )

    assert result.returncode == 0, result.stderr
    assert "Relaunching Discord because it was running when this script started..." in result.stdout
    assert process.wait(timeout=3) is not None
    assert _is_pid_running(old_pid) is False
    assert any(entry.startswith("open\t") for entry in _read_command_log(env))


def test_relaunch_retries_open_if_first_spawn_fails(env: dict[str, Path], tracked_processes):
    _prepare_standalone_app(env, "stable", asar_payload=b"base-asar")
    _prepare_data_directory(env, "stable")
    _write_fake_open(env["fake_bin"])
    _write_fake_osascript(env["fake_bin"])

    app_path = _application_path(env["applications_root"], "stable")
    executable = app_path / "Contents" / "MacOS" / "Discord"
    process = tracked_processes(executable)
    old_pid = process.pid

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={
            "TEST_FAKE_DISCORD_EXECUTABLE": str(executable),
            "TEST_FAKE_DISCORD_ALLOWED_EXECUTABLE": str(executable),
            "TEST_FAKE_DISCORD_EXECUTABLE_ARGS": _APP_SLEEP_SECONDS,
            "TEST_FAKE_QUIT_PID": str(old_pid),
            "TEST_FAKE_OPEN_FAIL_ATTEMPTS": "1",
        },
        path_override=env["fake_bin"],
        required_tools=("aria2c", "curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
    )

    assert result.returncode == 0, result.stderr
    open_calls = [entry for entry in _read_command_log(env) if entry.startswith("open\t")]
    assert len(open_calls) >= 2
    assert "did not relaunch cleanly with open:" in (result.stdout + result.stderr)
    assert process.wait(timeout=3) is not None
    assert _is_pid_running(old_pid) is False


def test_recovery_recovers_wrapper_without_fork_helper_by_unwrapping(env: dict[str, Path]):
    resources = _start_wrapped_app(env, "stable")
    _prepare_data_directory(env, "stable")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 0, result.stderr
    assert "No fork-specific BetterDiscord recovery helper detected for Discord.app; continuing with BetterDiscord unwrap for Discord.app" in result.stdout
    assert "Detected BetterDiscord wrapper in Discord.app" in result.stdout
    assert not (resources / "app").exists()
    assert (resources / "app.asar").read_text(encoding="utf-8") == "openasar"
    assert (resources / "betterdiscord.app.asar").exists() is False


def test_recovery_refuses_recovery_disabled_symlink(env: dict[str, Path]):
    resources = _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
        helper_pid="123",
        recovery_disabled="symlink",
    )

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={"TEST_FAKE_OPEN_FAIL_ATTEMPTS": "0"},
    )

    assert result.returncode != 0
    assert "Refusing to disable BetterDiscord update recovery for Discord.app because recovery-disabled is a symlink." in result.stderr
    assert (resources / "app").exists()


def test_recovery_removes_invalid_pid_file_and_proceeds(env: dict[str, Path]):
    _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    bootstrap = _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
        helper_pid="not-a-number",
    )
    (bootstrap / "betterdiscord-update-helper.pid").write_text("not-a-number", encoding="utf-8")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 0, result.stderr
    assert "Removed an invalid BetterDiscord recovery PID file for Discord.app" in result.stdout + result.stderr
    assert not (bootstrap / "betterdiscord-update-helper.pid").exists()


def test_recovery_removes_stale_pid_file(env: dict[str, Path]):
    _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    bootstrap = _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
        helper_pid="999999",
    )

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 0, result.stderr
    assert "Removed a stale BetterDiscord recovery PID file for Discord.app" in result.stdout + result.stderr
    assert not (bootstrap / "betterdiscord-update-helper.pid").exists()


def test_recovery_refuses_unrelated_recovery_pid_and_keeps_process_alive(
    env: dict[str, Path],
    tracked_processes,
):
    resources = _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    app_path = _application_path(env["applications_root"], "stable")
    executable = app_path / "Contents" / "MacOS" / "Discord"
    process = tracked_processes(executable)
    pid_text = str(process.pid)

    bootstrap = _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
        helper_pid=pid_text,
    )
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode != 0
    assert "Refusing to signal PID" in result.stderr
    assert "because it is not the validated BetterDiscord recovery process-group owner." in result.stderr
    assert _is_pid_running(int(pid_text)) is True
    assert (resources / "app").exists()


def test_recovery_stops_valid_fork_helper_with_reaper_thread(env: dict[str, Path], tracked_processes):
    resources = _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    bootstrap = _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
    )
    helper_path = bootstrap / "betterdiscord-update-helper.zsh"
    helper = tracked_processes(helper_path)
    helper_pid_text = str(helper.pid)
    _start_reaper_thread(helper)
    (bootstrap / "betterdiscord-update-helper.pid").write_text(helper_pid_text, encoding="utf-8")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 0, result.stderr
    assert "Stopping BetterDiscord recovery helper for Discord.app" in result.stdout
    assert "Stopped BetterDiscord recovery helper for Discord.app" in result.stdout
    assert "Detected BetterDiscord wrapper in Discord.app" in result.stdout
    assert "BetterDiscord successfully unwrapped from Discord.app" in result.stdout
    assert _wait_for_pid_exit(helper.pid, timeout=4.0)
    assert not (bootstrap / "betterdiscord-update-helper.pid").exists()
    assert not (resources / "app").exists()


def test_recovery_clears_fork_state_before_unwrap(env: dict[str, Path]):
    _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    bootstrap = _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
        helper_pid="999999",
    )

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 0, result.stderr
    assert not (bootstrap / "update-pending.json").exists()
    assert not (bootstrap / "wrapper-ready.json").exists()
    assert not (bootstrap / "active-run").exists()
    assert not (bootstrap / "recovery-runs").exists()


def test_recovery_reenabled_by_trap_when_unwrap_fails(env: dict[str, Path]):
    resources = _start_wrapped_app(env, "stable")
    data_dir = _prepare_data_directory(env, "stable")
    bootstrap = _write_betterdiscord_recovery_state(
        data_dir,
        include_helper=True,
        create_helper=True,
        helper_pid="999999",
    )
    wrapper_dir = resources / "app"
    _write_fake_moving_helper(env["fake_bin"], fail_path=wrapper_dir)
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode != 0
    assert "Unwrapping BetterDiscord from" in result.stdout
    assert "Failed to remove" in result.stdout + result.stderr
    assert (resources / "app").exists()
    assert (resources / "app").is_dir()
    assert (resources / "betterdiscord.app.asar").exists()
    assert not (bootstrap / "recovery-disabled").exists(), result.stdout + result.stderr
