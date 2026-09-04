from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ._helpers import (
    configure_fake_call,
    create_environment,
    run_script,
    snapshot_fixture,
    write_config,
)


LOCK_DIR_NAME = "thread-writer-locks"
THREAD_IDS = (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
)
HIGH_PID = "999991"
LIVE_UNLOCK_ARGS = ("--yes", "--unlock", "--skip-backup", "--no-prepare-bucket")


def _lock_dir(environment: dict[str, Path]) -> Path:
    path = environment["codex_home"] / LOCK_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_persistent_locks(environment: dict[str, Path]) -> dict[str, bytes]:
    lock_dir = _lock_dir(environment)
    files = {
        f"{THREAD_IDS[0]}.lock": b"persistent lock\n",
        ".coordination.lock": b"coordination lock\n",
    }
    for name, content in files.items():
        (lock_dir / name).write_bytes(content)
    return files


def _lsof_records(
    environment: dict[str, Path], *, pid: str = HIGH_PID, thread_ids: tuple[str, ...] = THREAD_IDS
) -> str:
    lock_dir = _lock_dir(environment)
    records = [f"p{pid}", "ccodex"]
    for fd, thread_id in enumerate(thread_ids, start=3):
        records.extend((f"f{fd}", f"n{lock_dir / f'{thread_id}.lock'}"))
    records.extend((f"f{len(thread_ids) + 3}", f"n{lock_dir / '.coordination.lock'}"))
    return "\n".join(records) + "\n"


def _ps_record(
    environment: dict[str, Path],
    *,
    pid: str = HIGH_PID,
    ppid: str = "1",
    uid: int | None = None,
    lstart: str = "Mon Jan 01 00:00:00 2024",
    comm: str = "codex",
    args: str = "codex resume",
) -> str:
    del environment
    return f"{pid} {ppid} {os.geteuid() if uid is None else uid} {lstart} {comm} {args}\n"


def _configure_lsof_and_ps(
    environment: dict[str, Path], *, lsof: str, ps: str, lsof_status: int = 0, ps_status: int = 0
) -> None:
    configure_fake_call(environment, "lsof", 1, output=lsof, status=lsof_status)
    configure_fake_call(environment, "ps", 1, output=ps, status=ps_status)


def test_unheld_persistent_locks_survive_dry_run_unlock(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    expected = _create_persistent_locks(environment)
    before = snapshot_fixture(environment)

    result = run_script(environment, "--dry-run", "--unlock")

    assert result.returncode == 0
    lock_dir = environment["codex_home"] / LOCK_DIR_NAME
    assert {path.name: path.read_bytes() for path in lock_dir.iterdir()} == expected
    assert snapshot_fixture(environment) == before


def test_dry_run_unlock_reports_candidate_and_all_affected_threads(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    _configure_lsof_and_ps(
        environment,
        lsof=_lsof_records(environment),
        ps=_ps_record(environment),
    )
    before = snapshot_fixture(environment)

    result = run_script(environment, "--dry-run", "--unlock")

    assert result.returncode == 0
    assert f"actionable candidate" in result.stdout
    assert f"would send TERM to candidate PID(s): {HIGH_PID}" in result.stdout
    for thread_id in THREAD_IDS:
        assert thread_id in result.stdout
    assert "Continue with lock recovery?" not in result.stdout
    assert "no prompt, signal, data edit, lock-path edit/deletion, JSONL edit, or SQLite edit performed" in result.stdout
    assert snapshot_fixture(environment) == before


def test_protected_holder_refuses_live_unlock_without_signal(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    protected_uid = os.geteuid() + 1
    _configure_lsof_and_ps(
        environment,
        lsof=_lsof_records(environment, thread_ids=(THREAD_IDS[0],)),
        ps=_ps_record(environment, uid=protected_uid),
    )
    before = snapshot_fixture(environment)

    result = run_script(environment, *LIVE_UNLOCK_ARGS)
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "ERROR: Unlock recovery failed: protected or unconfirmed lock holder(s) found; refusing to signal any PID" in combined
    assert "Sending TERM" not in combined
    assert "Continue with lock recovery?" not in combined
    assert snapshot_fixture(environment) == before
    assert not (environment["codex_home"] / "tmp").exists()
    assert not (environment["codex_home"] / "backups").exists()


def test_mixed_candidate_and_protected_holders_refuse_all_signals(
    tmp_path: Path,
) -> None:
    environment = create_environment(tmp_path)
    lock_dir = _lock_dir(environment)
    _create_persistent_locks(environment)
    second_lock = lock_dir / f"{THREAD_IDS[1]}.lock"
    second_lock.write_bytes(b"second persistent lock\n")
    protected_pid = "999992"
    lsof_output = "\n".join(
        (
            f"p{HIGH_PID}",
            "ccodex",
            "f3",
            f"n{lock_dir / f'{THREAD_IDS[0]}.lock'}",
            f"p{protected_pid}",
            "ccodex",
            "f3",
            f"n{lock_dir / f'{THREAD_IDS[1]}.lock'}",
        )
    ) + "\n"
    ps_output = _ps_record(environment, pid=HIGH_PID) + _ps_record(
        environment, pid=protected_pid, ppid="2"
    )
    _configure_lsof_and_ps(environment, lsof=lsof_output, ps=ps_output)
    before = snapshot_fixture(environment)

    result = run_script(environment, *LIVE_UNLOCK_ARGS, input_text="y\n")
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "protected or unconfirmed lock holder(s) found; refusing to signal any PID" in combined
    assert "Continue with lock recovery?" not in combined
    assert "Sending TERM" not in combined
    assert "Escalating to KILL" not in combined
    assert snapshot_fixture(environment) == before


@pytest.mark.parametrize(
    ("lsof_output", "error_text"),
    (
        (f"p{HIGH_PID}\n", "lsof emitted an incomplete final process record"),
        (f"p{HIGH_PID}\nccodex\nf3\np999992\n", "lsof emitted an incomplete process record"),
    ),
)
def test_malformed_lsof_fails_closed(
    tmp_path: Path, lsof_output: str, error_text: str
) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    configure_fake_call(environment, "lsof", 1, output=lsof_output, status=0)
    before = snapshot_fixture(environment)

    result = run_script(environment, "--dry-run", "--unlock")
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert f"ERROR: Unlock recovery failed: {error_text}" in combined
    assert snapshot_fixture(environment) == before


@pytest.mark.parametrize(
    "ps_output",
    (
        f"{HIGH_PID} 1 {os.geteuid()} codex codex resume\n",
        f"{HIGH_PID} 1 {os.geteuid()} Mon Jan 01 codex codex resume\n",
    ),
)
def test_malformed_or_missing_lstart_ps_fails_closed(
    tmp_path: Path, ps_output: str
) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    _configure_lsof_and_ps(
        environment,
        lsof=_lsof_records(environment, thread_ids=(THREAD_IDS[0],)),
        ps=ps_output,
    )
    before = snapshot_fixture(environment)

    result = run_script(environment, "--dry-run", "--unlock")
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "ERROR: Unlock recovery failed: ps emitted a malformed" in combined
    assert snapshot_fixture(environment) == before


@pytest.mark.parametrize("input_text", ("", "n\n"))
def test_yes_does_not_bypass_unlock_prompt(
    tmp_path: Path, input_text: str
) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    _configure_lsof_and_ps(
        environment,
        lsof=_lsof_records(environment, thread_ids=(THREAD_IDS[0],)),
        ps=_ps_record(environment),
    )
    before = snapshot_fixture(environment)

    result = run_script(environment, *LIVE_UNLOCK_ARGS, input_text=input_text)

    assert result.returncode == 0
    assert "Continue with lock recovery? [y/N]" in result.stdout
    assert "Unlock recovery not confirmed. No recovery or sync was performed." in result.stdout
    assert "Sending TERM" not in result.stdout
    assert snapshot_fixture(environment) == before


def test_identity_change_at_term_revalidation_refuses_before_signal(
    tmp_path: Path,
) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    lsof_output = _lsof_records(environment, thread_ids=(THREAD_IDS[0],))
    matching_ps = _ps_record(environment)
    changed_ps = _ps_record(environment, lstart="Mon Jan 01 00:00:01 2024")
    for call_number in (1, 2, 3):
        configure_fake_call(environment, "lsof", call_number, output=lsof_output, status=0)
    configure_fake_call(environment, "ps", 1, output=matching_ps, status=0)
    configure_fake_call(environment, "ps", 2, output=matching_ps, status=0)
    configure_fake_call(environment, "ps", 3, output=changed_ps, status=0)
    before = snapshot_fixture(environment)

    result = run_script(
        environment,
        "--unlock",
        "--skip-backup",
        "--no-prepare-bucket",
        input_text="y\n",
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert f"ERROR: Unlock recovery failed: lock owner identity or lock set changed before TERM for PID {HIGH_PID}; refusing to signal" in combined
    assert "Sending TERM" not in combined
    assert (environment["control"] / "ps.count").read_text(encoding="utf-8").strip() == "3"
    assert (environment["control"] / "lsof.count").read_text(encoding="utf-8").strip() == "3"
    assert snapshot_fixture(environment) == before
    assert not (environment["codex_home"] / "tmp").exists()
    assert not (environment["codex_home"] / "backups").exists()


def test_release_before_kill_skips_escalation_and_preserves_child(
    tmp_path: Path,
) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    before = snapshot_fixture(environment)
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "HOME": str(environment["home"])},
    )
    try:
        lsof_with_holder = _lsof_records(
            environment, pid=str(child.pid), thread_ids=(THREAD_IDS[0],)
        )
        ps_output = _ps_record(environment, pid=str(child.pid))
        for call_number in range(1, 5):
            configure_fake_call(environment, "lsof", call_number, output=lsof_with_holder, status=0)
            configure_fake_call(environment, "ps", call_number, output=ps_output, status=0)
        configure_fake_call(environment, "lsof", 5, output="", status=1)

        started = time.monotonic()
        result = run_script(
            environment,
            "--unlock",
            "--skip-backup",
            "--no-prepare-bucket",
            input_text="y\n",
        )
        elapsed = time.monotonic() - started
        combined = result.stdout + result.stderr

        assert elapsed >= 4.5
        assert result.returncode == 0
        assert "Released 1 thread writer lock" in combined
        assert f"Sending TERM to PID {child.pid}." in combined
        assert "Escalating to KILL" not in combined
        assert child.poll() is None
        assert snapshot_fixture(environment) == before
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_kill_escalation_revalidates_then_kills_child(
    tmp_path: Path,
) -> None:
    environment = create_environment(tmp_path)
    _create_persistent_locks(environment)
    before = snapshot_fixture(environment)
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "HOME": str(environment["home"])},
    )
    try:
        lsof_with_holder = _lsof_records(
            environment, pid=str(child.pid), thread_ids=(THREAD_IDS[0],)
        )
        ps_output = _ps_record(environment, pid=str(child.pid))
        for call_number in range(1, 7):
            configure_fake_call(environment, "lsof", call_number, output=lsof_with_holder, status=0)
            configure_fake_call(environment, "ps", call_number, output=ps_output, status=0)
        configure_fake_call(environment, "lsof", 7, output="", status=1)

        result = run_script(
            environment,
            "--unlock",
            "--skip-backup",
            "--no-prepare-bucket",
            input_text="y\n",
        )
        combined = result.stdout + result.stderr

        assert result.returncode == 0
        assert f"Sending TERM to PID {child.pid}." in combined
        assert f"Escalating to KILL for PID {child.pid}." in combined
        assert child.poll() is not None
        assert child.wait(timeout=5) < 0
        assert "Released 1 thread writer lock" in combined
        assert snapshot_fixture(environment) == before
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
