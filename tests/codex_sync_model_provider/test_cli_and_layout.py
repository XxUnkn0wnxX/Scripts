from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import create_environment, run_script, snapshot_fixture, write_config


@pytest.mark.parametrize("flag", ("-h", "--help"))
def test_help_is_side_effect_free(tmp_path: Path, flag: str) -> None:
    environment = create_environment(tmp_path, create_root=False)

    result = run_script(environment, flag)

    assert result.returncode == 0
    assert "--unlock" in result.stdout
    assert not environment["codex_home"].exists()


def test_unknown_option_exits_two(tmp_path: Path) -> None:
    environment = create_environment(tmp_path, create_root=False)

    result = run_script(environment, "--not-an-option")

    assert result.returncode == 2
    assert "ERROR: Unknown option: --not-an-option" in result.stdout
    assert "Usage:" in result.stdout
    assert not environment["codex_home"].exists()


@pytest.mark.parametrize(
    ("config_value", "source", "cwd_kind"),
    (
        ('"/tmp/codex-sync-config-sqlite"', "config.toml sqlite_home", "home"),
        ('"relative-sqlite"', "config.toml sqlite_home", "invoke"),
    ),
)
def test_split_config_sqlite_layout_fails_without_mutation(
    tmp_path: Path, config_value: str, source: str, cwd_kind: str
) -> None:
    environment = create_environment(tmp_path)
    write_config(
        environment,
        f'model_provider = "openai"\nsqlite_home = {config_value}\n',
    )
    cwd = environment["home"] if cwd_kind == "home" else environment["invoke_cwd"]
    expected_effective_dir = (
        Path("/tmp/codex-sync-config-sqlite")
        if cwd_kind == "home"
        else environment["invoke_cwd"] / "relative-sqlite"
    ).resolve()
    before = snapshot_fixture(environment)

    result = run_script(environment, "--dry-run", "--skip-backup", cwd=cwd)

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "ERROR: Split SQLite layout is not supported" in combined
    assert f"Codex root:                  {environment['codex_home'].resolve()}" in combined
    assert "Effective source:            " + source in combined
    assert f"Resolved effective SQLite dir: {expected_effective_dir}" in combined
    assert f"Effective state_5.sqlite path: {expected_effective_dir / 'state_5.sqlite'}" in combined
    assert f"Script state_5.sqlite target:  {environment['db'].resolve()}" in combined
    assert snapshot_fixture(environment) == before


def test_split_environment_sqlite_layout_fails_without_mutation(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    split_dir = (tmp_path / "env-sqlite").resolve()
    write_config(environment, 'model_provider = "openai"\n')
    before = snapshot_fixture(environment)

    result = run_script(
        environment,
        "--dry-run",
        "--skip-backup",
        extra_env={"CODEX_SQLITE_HOME": str(split_dir)},
    )

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert f"Codex root:                  {environment['codex_home'].resolve()}" in combined
    assert "Effective source:            CODEX_SQLITE_HOME" in combined
    assert f"Raw configured value:        {split_dir}" in combined
    assert f"Resolved effective SQLite dir: {split_dir}" in combined
    assert f"Effective state_5.sqlite path: {split_dir / 'state_5.sqlite'}" in combined
    assert f"Script state_5.sqlite target:  {environment['db'].resolve()}" in combined
    assert snapshot_fixture(environment) == before


@pytest.mark.parametrize("key", ("sqlite_home", '"sqlite_home"', "'sqlite_home'"))
def test_same_dir_sqlite_home_and_quoted_keys_pass_guard(
    tmp_path: Path, key: str
) -> None:
    environment = create_environment(tmp_path)
    write_config(
        environment,
        f'model_provider = "openai"\n{key} = "{environment["codex_home"].resolve()}"\n',
    )

    result = run_script(environment, "--dry-run", "--skip-backup")

    assert result.returncode == 0
    assert "Schema contract: OK" in result.stdout
    assert "Split SQLite layout is not supported" not in result.stderr


def test_root_config_sqlite_home_overrides_differing_environment(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    differing_dir = (tmp_path / "different-env-sqlite").resolve()
    write_config(
        environment,
        f'model_provider = "openai"\nsqlite_home = "{environment["codex_home"].resolve()}"\n',
    )

    result = run_script(
        environment,
        "--dry-run",
        "--skip-backup",
        extra_env={"CODEX_SQLITE_HOME": str(differing_dir)},
    )

    assert result.returncode == 0
    assert "NOTICE: root-level sqlite_home overrides a differing CODEX_SQLITE_HOME value." in result.stderr
    assert "Schema contract: OK" in result.stdout


def test_section_scoped_sqlite_home_is_ignored(tmp_path: Path) -> None:
    environment = create_environment(tmp_path)
    write_config(
        environment,
        'model_provider = "openai"\n\n[sqlite]\nsqlite_home = "/tmp/section-sqlite"\n',
    )

    result = run_script(environment, "--dry-run", "--skip-backup")

    assert result.returncode == 0
    assert "Schema contract: OK" in result.stdout
    assert "Split SQLite layout is not supported" not in result.stderr


@pytest.mark.parametrize(
    "sqlite_line",
    (
        "sqlite_home =",
        'sqlite_home = ""',
        'sqlite_home = "one"\nsqlite_home = "two"',
        "sqlite_home = true",
    ),
)
def test_invalid_root_sqlite_home_fails_closed_before_db_lookup(
    tmp_path: Path, sqlite_line: str
) -> None:
    environment = create_environment(tmp_path)
    write_config(environment, f'model_provider = "openai"\n{sqlite_line}\n')
    environment["db"].unlink()

    result = run_script(environment, "--dry-run", "--skip-backup")

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "ERROR: Invalid root-level sqlite_home in config.toml:" in combined
    assert "state_5.sqlite not found" not in combined
