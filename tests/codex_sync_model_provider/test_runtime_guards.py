from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ._helpers import (
    add_valid_session_and_db_row,
    configure_fake_call,
    create_backfill_state,
    create_environment,
    finish_script,
    read_provider_values,
    run_script,
    set_backfill_status,
    snapshot_fixture,
    start_script,
    terminate_script,
    wait_for_path,
    write_config,
)


LIVE_ARGS = ("--yes", "--skip-backup", "--no-prepare-bucket")


def _set_provider_to_anthropic(environment: dict[str, Path]) -> None:
    write_config(
        environment,
        'model_provider = "anthropic"\n\n[model_providers.anthropic]\n',
    )


def _create_backfill_schema(environment: dict[str, Path], schema: str) -> None:
    connection = sqlite3.connect(environment["db"])
    try:
        connection.execute("DROP TABLE IF EXISTS backfill_state")
        connection.execute(schema)
        connection.commit()
    finally:
        connection.close()


def _assert_backfill_rejected(
    environment: dict[str, Path], before: dict[str, bytes] | None, *, hidden_status: str | None
) -> None:
    result = run_script(environment, "--dry-run", "--skip-backup")
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "ERROR: Backfill readiness check failed during early." in combined
    assert f"Database: {environment['db'].resolve()}" in combined
    assert "Start Codex normally, let its startup rebuild finish, close Codex, then rerun this script." in combined
    if hidden_status is not None:
        if hidden_status == "status=running":
            assert hidden_status in combined
        else:
            assert hidden_status not in combined
    assert snapshot_fixture(environment) == before


def test_backfill_table_absent_is_accepted_in_dry_run(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)

    result = run_script(environment, "--dry-run", "--skip-backup")

    assert result.returncode == 0
    assert "Schema contract: OK" in result.stdout


def test_exact_singleton_complete_backfill_is_accepted_in_dry_run(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    create_backfill_state(environment)

    result = run_script(environment, "--dry-run", "--skip-backup")

    assert result.returncode == 0
    assert "Schema contract: OK" in result.stdout


@pytest.mark.parametrize(
    ("status", "rows", "status_type", "hidden_status"),
    (
        ("running", None, "TEXT", "status=running"),
        ("operator-secret", None, "TEXT", "operator-secret"),
        ("complete", (), "TEXT", None),
        ("complete", ((1, "complete"), (2, "complete")), "TEXT", None),
        (b"complete", None, "BLOB", None),
    ),
)
def test_backfill_status_and_row_contracts_fail_closed(
    tmp_path: Path,
    status: str | bytes,
    rows: tuple[tuple[object, object], ...] | None,
    status_type: str,
    hidden_status: str | None,
) -> None:
    environment = create_environment(tmp_path)
    if rows == ():
        create_backfill_state(environment, rows=())
    elif isinstance(status, bytes):
        create_backfill_state(
            environment,
            status="complete",
            rows=((1, sqlite3.Binary(status)),),
            status_type=status_type,
        )
    else:
        create_backfill_state(environment, status=status, rows=rows, status_type=status_type)
    before = snapshot_fixture(environment)

    _assert_backfill_rejected(environment, before, hidden_status=hidden_status)


@pytest.mark.parametrize(
    ("schema", "hidden_status"),
    (
        ("CREATE TABLE backfill_state (id INTEGER)", None),
        ("CREATE TABLE backfill_state (id TEXT, status TEXT)", None),
        ("CREATE TABLE backfill_state (id INTEGER, status BLOB)", None),
    ),
)
def test_missing_or_wrong_backfill_schema_fails_closed(
    tmp_path: Path, schema: str, hidden_status: str | None
) -> None:
    environment = create_environment(tmp_path)
    _create_backfill_schema(environment, schema)
    before = snapshot_fixture(environment)

    _assert_backfill_rejected(environment, before, hidden_status=hidden_status)


@pytest.mark.parametrize(
    "ps_output",
    (
        "123 1 codex codex resume\n",
        "124 1 /usr/local/bin/codex /usr/local/bin/codex resume\n",
        "125 1 codex-code-mode-host codex-code-mode-host --stdio\n",
        "126 1 node /usr/local/lib/node_modules/codex.js resume\n",
        "129 1 /usr/local/bin/n /usr/local/bin/node /usr/local/lib/node_modules/@openai/codex/bin/codex.js resume\n",
        "130 1 /usr/local/bin/n /usr/local/bin/node /cache/@openai+codex@0.153.2/node_modules/@openai/codex/bin/codex.js resume\n",
    ),
)
def test_live_active_detector_rejects_codex_process_shapes(
    tmp_path: Path, ps_output: str
) -> None:
    environment = create_environment(tmp_path)
    configure_fake_call(environment, "ps", 1, output=ps_output)
    before = snapshot_fixture(environment)

    result = run_script(environment, *LIVE_ARGS)
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "ERROR: Codex appears to be running during early." in combined
    assert (environment["control"] / "ps.count").read_text(encoding="utf-8").strip() == "1"
    assert snapshot_fixture(environment) == before


@pytest.mark.parametrize(
    "ps_output",
    (
        "127 1 zsh zsh -c 'echo codex resume'\n",
        "128 1 node node codex-chats-mcp\n",
    ),
)
def test_live_active_detector_does_not_false_positive(
    tmp_path: Path, ps_output: str
) -> None:
    environment = create_environment(tmp_path)
    configure_fake_call(environment, "ps", 1, output=ps_output)

    result = run_script(environment, *LIVE_ARGS)

    assert result.returncode == 0
    assert (environment["control"] / "ps.count").read_text(encoding="utf-8").strip() == "1"


def test_ps_failure_refuses_live_sync(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    configure_fake_call(environment, "ps", 1, status=1)

    result = run_script(environment, *LIVE_ARGS)
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "ERROR: Could not inspect running processes during early; refusing live sync." in combined
    assert "Process check: ps failed" in combined


def test_dry_run_does_not_invoke_ps(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)

    result = run_script(
        environment,
        "--dry-run",
        "--skip-backup",
        extra_env={"TEST_FAKE_PS_STATUS": "1"},
    )

    assert result.returncode == 0
    assert not (environment["control"] / "ps.count").exists()


def test_early_live_refusal_does_not_create_scratch_or_backup(
    tmp_path: Path,
) -> None:
    environment = create_environment(tmp_path)
    _set_provider_to_anthropic(environment)
    create_backfill_state(environment)
    session_file = add_valid_session_and_db_row(environment)
    configure_fake_call(environment, "ps", 1, output="129 1 codex codex resume\n")
    before = snapshot_fixture(environment)

    result = run_script(environment, *LIVE_ARGS)

    assert result.returncode == 1
    assert "during early" in result.stderr
    assert not (environment["codex_home"] / "tmp").exists()
    assert not (environment["codex_home"] / "backups").exists()
    assert snapshot_fixture(environment) == before
    assert session_file.read_bytes() == before["sessions/2026/09/11111111-1111-4111-8111-111111111111.jsonl"]


def test_final_active_race_refuses_before_scratch_or_writes(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    _set_provider_to_anthropic(environment)
    create_backfill_state(environment)
    session_file = add_valid_session_and_db_row(environment)
    configure_fake_call(environment, "ps", 1, output="")
    configure_fake_call(environment, "ps", 2, output="130 1 codex codex resume\n")
    before_db = read_provider_values(environment)
    before_session = session_file.read_bytes()

    result = run_script(environment, *LIVE_ARGS)
    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert "ERROR: Codex appears to be running during before_final_write_gate." in combined
    assert (environment["control"] / "ps.count").read_text(encoding="utf-8").strip() == "2"
    assert not (environment["codex_home"] / "tmp").exists()
    assert read_provider_values(environment) == before_db
    assert session_file.read_bytes() == before_session


def test_final_backfill_race_refuses_before_scratch_or_writes(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    _set_provider_to_anthropic(environment)
    create_backfill_state(environment)
    session_file = add_valid_session_and_db_row(environment)
    before_db = read_provider_values(environment)
    before_session = session_file.read_bytes()
    process = start_script(
        environment,
        *LIVE_ARGS,
        extra_env={
            "SYNC_MODEL_PROVIDER_TEST_DIR": str(environment["control"]),
            "SYNC_MODEL_PROVIDER_TEST_PAUSE_PHASE": "before_final_write_gate",
        },
    )
    try:
        wait_for_path(environment["control"] / "before_final_write_gate.ready")
        set_backfill_status(environment, "running")
        (environment["control"] / "before_final_write_gate.continue").touch()
        result = finish_script(process)
    finally:
        terminate_script(process)

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "ERROR: Backfill readiness check failed during before_final_write_gate." in combined
    assert not (environment["codex_home"] / "tmp").exists()
    assert read_provider_values(environment) == before_db
    assert session_file.read_bytes() == before_session
