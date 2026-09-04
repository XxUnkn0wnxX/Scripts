from __future__ import annotations

import json
import stat
from pathlib import Path

from ._helpers import (
    add_valid_session_and_db_row,
    create_environment,
    read_provider_values,
    run_script,
    snapshot_fixture,
)


LIVE_ARGS = ("--yes", "--skip-backup", "--no-prepare-bucket")
DRY_RUN_ARGS = ("--dry-run", "--skip-backup", "--no-prepare-bucket")


def test_live_sync_updates_db_and_session_provider_only(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    session_file = add_valid_session_and_db_row(environment, old_provider="neutral")
    before_bytes = session_file.read_bytes()
    before_first_line, separator, before_rest = before_bytes.partition(b"\n")
    before_json = json.loads(before_first_line)
    before_mode = stat.S_IMODE(session_file.stat().st_mode)

    result = run_script(environment, *LIVE_ARGS)

    assert result.returncode == 0
    assert "Update complete." in result.stdout
    assert read_provider_values(environment) == {
        "11111111-1111-4111-8111-111111111111": "openai"
    }
    after_bytes = session_file.read_bytes()
    after_first_line, after_separator, after_rest = after_bytes.partition(b"\n")
    after_json = json.loads(after_first_line)
    assert separator == after_separator == b"\n"
    assert before_json["payload"].pop("model_provider") == "neutral"
    assert after_json["payload"].pop("model_provider") == "openai"
    assert after_json == before_json
    assert after_rest == before_rest
    assert stat.S_IMODE(session_file.stat().st_mode) == before_mode
    assert (environment["control"] / "ps.count").read_text(encoding="utf-8").strip() == "2"
    assert not (environment["codex_home"] / "backups").exists()


def test_dry_run_reports_db_and_session_updates_without_mutation(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    add_valid_session_and_db_row(environment, old_provider="neutral")
    before = snapshot_fixture(environment)

    result = run_script(environment, *DRY_RUN_ARGS)

    assert result.returncode == 0
    assert "Rows that would be changed to 'openai': 1" in result.stdout
    assert "Session files that would be updated:  1" in result.stdout
    assert snapshot_fixture(environment) == before
    assert not (environment["codex_home"] / "tmp").exists()
    assert not (environment["codex_home"] / "backups").exists()
    assert not (environment["control"] / "ps.count").exists()


def test_matching_live_sync_exits_without_changes_after_early_guard(
    tmp_path: Path,
) -> None:
    environment = create_environment(tmp_path)
    add_valid_session_and_db_row(environment, old_provider="openai")
    before = snapshot_fixture(environment)

    result = run_script(environment, *LIVE_ARGS)

    assert result.returncode == 0
    assert "No changes needed." in result.stdout
    assert snapshot_fixture(environment) == before
    assert (environment["control"] / "ps.count").read_text(encoding="utf-8").strip() == "1"
    assert not (environment["codex_home"] / "tmp").exists()
    assert not (environment["codex_home"] / "backups").exists()
