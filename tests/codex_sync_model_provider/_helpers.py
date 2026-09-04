from __future__ import annotations

import json
import os
import shlex
import shutil
import sqlite3 as sqlite3_module
import subprocess
import time
from pathlib import Path
from typing import Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_SOURCE = REPO_ROOT / "shell/codex-sync-model-provider.zsh"
STANDARD_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REQUIRED_TOOLS = (
    "zsh",
    "sqlite3",
    "jq",
    "awk",
    "grep",
    "date",
    "mkdir",
    "mktemp",
    "mv",
    "tail",
    "rm",
    "sort",
    "uniq",
    "chmod",
    "touch",
    "dd",
    "cat",
    "sleep",
)


def required_tools_missing() -> list[str]:
    """Return tools unavailable from the fixed PATH used by the shell tests."""

    return [tool for tool in REQUIRED_TOOLS if shutil.which(tool, path=STANDARD_PATH) is None]


def _write_fake_command(path: Path, *, default_status: int) -> None:
    command_name = path.name.upper()
    output_name = f"TEST_FAKE_{command_name}_OUTPUT"
    status_name = f"TEST_FAKE_{command_name}_STATUS"
    count_name = f"TEST_FAKE_{command_name}_COUNT_FILE"
    path.write_text(
        f"""#!/bin/sh
count_file=\"${{{count_name}:-}}\"
if [ -n \"$count_file\" ]; then
  count=0
  if [ -f \"$count_file\" ]; then count=$(cat \"$count_file\"); fi
  count=$((count + 1))
  printf '%s\\n' \"$count\" > \"$count_file\"
fi
control_dir=\"${{TEST_FAKE_CONTROL_DIR:-}}\"
output_file=\"$control_dir/{path.name}-output-$count\"
if [ -n \"$control_dir\" ] && [ -f \"$output_file\" ]; then
  cat \"$output_file\"
else
  output=\"${{{output_name}:-}}\"
  if [ -n \"$output\" ]; then printf '%s' \"$output\"; fi
fi
status_file=\"$control_dir/{path.name}-status-$count\"
if [ -n \"$control_dir\" ] && [ -f \"$status_file\" ]; then
  status=$(cat \"$status_file\")
else
  status=\"${{{status_name}:-{default_status}}}\"
fi
case \"$status\" in
  ''|*[!0-9]*) exit 2 ;;
esac
exit \"$status\"
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def create_environment(tmp_path: Path, *, create_root: bool = True) -> dict[str, Path]:
    """Create a disposable Codex root and shell-command test environment."""

    home = tmp_path / "home"
    codex_home = home / ".codex"
    fake_bin = tmp_path / "fake-bin"
    control = tmp_path / "test-control"
    invoke_cwd = tmp_path / "invoke-cwd"
    script = tmp_path / "codex-sync-model-provider.zsh"

    home.mkdir()
    fake_bin.mkdir()
    control.mkdir()
    invoke_cwd.mkdir()
    shutil.copy2(SCRIPT_SOURCE, script)
    script.chmod(script.stat().st_mode | 0o111)
    _write_fake_command(fake_bin / "ps", default_status=0)
    _write_fake_command(fake_bin / "lsof", default_status=1)
    script_text = script.read_text(encoding="utf-8")
    for variable, native_path, fake_path in (
        ("PS_CMD", "/bin/ps", fake_bin / "ps"),
        ("LSOF_CMD", "/usr/sbin/lsof", fake_bin / "lsof"),
    ):
        sentinel = f"{variable}={native_path}"
        assert script_text.count(sentinel) == 1
        script_text = script_text.replace(
            sentinel, f"{variable}={shlex.quote(str(fake_path))}", 1
        )
    script.write_text(script_text, encoding="utf-8")

    if create_root:
        codex_home.mkdir()
        sessions = codex_home / "sessions"
        sessions.mkdir()
        config = codex_home / "config.toml"
        config.write_text('model_provider = "openai"\n', encoding="utf-8")
        db = codex_home / "state_5.sqlite"
        connection = sqlite3_module.connect(db)
        try:
            connection.executescript(
                """
                CREATE TABLE threads (
                    id TEXT,
                    rollout_path TEXT,
                    model_provider TEXT
                );
                CREATE INDEX idx_threads_provider ON threads(model_provider);
                """
            )
            connection.commit()
        finally:
            connection.close()

    return {
        "home": home,
        "codex_home": codex_home,
        "codex_root": codex_home,
        "root": codex_home,
        "config": codex_home / "config.toml",
        "db": codex_home / "state_5.sqlite",
        "sessions": codex_home / "sessions",
        "script": script,
        "fake_bin": fake_bin,
        "control": control,
        "invoke_cwd": invoke_cwd,
        "zsh": Path(shutil.which("zsh", path=STANDARD_PATH) or "zsh"),
        "sqlite3": Path(shutil.which("sqlite3", path=STANDARD_PATH) or "sqlite3"),
        "jq": Path(shutil.which("jq", path=STANDARD_PATH) or "jq"),
    }


def _clear_invocation_counters(control: Path) -> None:
    for name in ("ps.count", "lsof.count", "ps.calls", "lsof.calls"):
        path = control / name
        if path.exists():
            path.unlink()


def configure_fake_call(
    environment: Mapping[str, Path],
    command: str,
    call_number: int,
    *,
    output: str | None = None,
    status: int | None = None,
) -> None:
    """Configure one numbered fake ps/lsof invocation using tmp_path files."""

    if command not in {"ps", "lsof"}:
        raise ValueError(f"unsupported fake command: {command}")
    if call_number < 1:
        raise ValueError("call_number must be positive")
    control = environment["control"]
    if output is not None:
        (control / f"{command}-output-{call_number}").write_text(output, encoding="utf-8")
    if status is not None:
        (control / f"{command}-status-{call_number}").write_text(str(status), encoding="ascii")


def process_environment(
    environment: Mapping[str, Path],
    *,
    extra_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a sanitized process environment for sync-script execution."""

    control = environment["control"]
    _clear_invocation_counters(control)
    process_env = {
        key: value
        for key, value in os.environ.items()
        if key != "CODEX_SQLITE_HOME"
        and not key.startswith("SYNC_MODEL_PROVIDER_TEST_")
        and not key.startswith("TEST_FAKE_PS_")
        and not key.startswith("TEST_FAKE_LSOF_")
    }
    process_env.update(
        {
            "HOME": str(environment["home"]),
            "CODEX_HOME": str(environment["codex_home"]),
            "PATH": f"{environment['fake_bin']}:{STANDARD_PATH}",
            "TEST_FAKE_CONTROL_DIR": str(control),
            "TEST_FAKE_PS_COUNT_FILE": str(control / "ps.count"),
            "TEST_FAKE_LSOF_COUNT_FILE": str(control / "lsof.count"),
        }
    )
    if extra_env:
        process_env.update(extra_env)
    return process_env


def run_script(
    environment: Mapping[str, Path],
    *args: str,
    cwd: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the copied script with isolated state and controlled ps/lsof."""

    process_env = process_environment(environment, extra_env=extra_env)

    return subprocess.run(
        [str(environment["script"]), *args],
        cwd=str(cwd or environment["home"]),
        env=process_env,
        text=True,
        capture_output=True,
        check=False,
        input=input_text,
        timeout=30,
    )


def start_script(
    environment: Mapping[str, Path],
    *args: str,
    cwd: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.Popen[str]:
    """Start the script for a bounded checkpoint-controlled test."""

    return subprocess.Popen(
        [str(environment["script"]), *args],
        cwd=str(cwd or environment["home"]),
        env=process_environment(environment, extra_env=extra_env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def finish_script(
    process: subprocess.Popen[str], *, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    """Collect a started script, enforcing the helper's hard timeout."""

    timeout = min(timeout, 30)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
        raise subprocess.TimeoutExpired(process.args, timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def terminate_script(process: subprocess.Popen[str]) -> None:
    """Best-effort cleanup for a started test process."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_for_path(path: Path, *, timeout: float = 20) -> None:
    """Wait for a checkpoint marker without allowing an unbounded test hang."""

    deadline = time.monotonic() + min(timeout, 30)
    while not path.exists():
        if time.monotonic() >= deadline:
            raise AssertionError(f"timed out waiting for checkpoint: {path}")
        time.sleep(0.05)


def write_config(environment: Mapping[str, Path], content: str) -> None:
    environment["config"].write_text(content, encoding="utf-8")


def create_backfill_state(
    environment: Mapping[str, Path],
    *,
    status: str = "complete",
    rows: Sequence[tuple[object, object]] | None = None,
    id_type: str = "INTEGER",
    status_type: str = "TEXT",
) -> None:
    connection = sqlite3_module.connect(environment["db"])
    try:
        connection.execute("DROP TABLE IF EXISTS backfill_state")
        connection.execute(
            f"CREATE TABLE backfill_state (id {id_type}, status {status_type})"
        )
        if rows is None:
            rows = ((1, status),)
        connection.executemany(
            "INSERT INTO backfill_state (id, status) VALUES (?, ?)", rows
        )
        connection.commit()
    finally:
        connection.close()


def set_backfill_status(environment: Mapping[str, Path], status: object) -> None:
    connection = sqlite3_module.connect(environment["db"])
    try:
        connection.execute("UPDATE backfill_state SET status = ? WHERE id = 1", (status,))
        connection.commit()
    finally:
        connection.close()


def add_valid_session_and_db_row(
    environment: Mapping[str, Path],
    *,
    thread_id: str = "11111111-1111-4111-8111-111111111111",
    old_provider: str = "openai",
    filename: str | None = None,
) -> Path:
    session_file = environment["sessions"] / "2026" / "09" / (filename or f"{thread_id}.jsonl")
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": thread_id,
                    "session_id": thread_id,
                    "model_provider": old_provider,
                    "originator": "codex_cli_rs",
                    "history_mode": "legacy",
                },
            },
            separators=(",", ":"),
        )
        + "\n"
        + '{"type":"event_msg","payload":{}}\n',
        encoding="utf-8",
    )
    connection = sqlite3_module.connect(environment["db"])
    try:
        connection.execute(
            "INSERT INTO threads (id, rollout_path, model_provider) VALUES (?, ?, ?)",
            (thread_id, str(session_file.resolve()), old_provider),
        )
        connection.commit()
    finally:
        connection.close()
    return session_file


def read_provider_values(environment: Mapping[str, Path]) -> dict[str, str | None]:
    connection = sqlite3_module.connect(environment["db"])
    try:
        rows = connection.execute("SELECT id, model_provider FROM threads ORDER BY id").fetchall()
    finally:
        connection.close()
    return {thread_id: provider for thread_id, provider in rows}


def snapshot_fixture(environment: Mapping[str, Path]) -> dict[str, bytes] | None:
    """Return all regular fixture-file bytes, or None when the root is absent."""

    root = environment["codex_home"]
    if not root.exists():
        return None
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }
