from __future__ import annotations

from pathlib import Path

from _helpers import (
    APP_NAMES,
    SCRIPT_SOURCE,
    _assert_no_download_artifacts,
    _application_path,
    _read_settings,
    _run_manager,
    _settings_path,
)


def test_lock_flag_is_documented(env: dict[str, Path]):
    result = _run_manager(env, "--help")

    assert result.returncode == 0
    assert "--lock" in result.stdout
    assert "[--lock]" in result.stdout


def test_help_short_circuits_trailing_invalid_argument(env: dict[str, Path]):
    result = _run_manager(env, "--help", "--does-not-exist")

    assert result.returncode == 0
    assert "--lock" in result.stdout
    assert "Unknown argument:" not in (result.stdout + result.stderr)


def test_short_help_alias_is_documented(env: dict[str, Path]):
    result = _run_manager(env, "-h")

    assert result.returncode == 0
    assert "--lock" in result.stdout


def test_no_args_prints_usage(env: dict[str, Path]):
    result = _run_manager(env)

    assert result.returncode == 2
    assert "No channel specified. Use --channel stable|ptb|canary|all." in result.stderr
    _assert_no_download_artifacts(env)


def test_unknown_argument_is_rejected(env: dict[str, Path]):
    result = _run_manager(env, "--does-not-exist")

    assert result.returncode == 2
    assert "Unknown argument: --does-not-exist" in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_invalid_channel_is_rejected(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable,ptb")

    assert result.returncode == 2
    assert "Invalid channel: stable,ptb" in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_missing_value_for_channel_guard(env: dict[str, Path]):
    result = _run_manager(env, "--channel")

    assert result.returncode == 2
    assert "Missing value for --channel." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_missing_value_for_openasar_source_guard(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
    )

    assert result.returncode == 2
    assert "Missing value for --openasar-source." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_update_requires_channel(env: dict[str, Path]):
    result = _run_manager(env, "--update", "401")

    assert result.returncode == 2
    assert "--update requires --channel stable|ptb|canary|all." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_dl_requires_channel(env: dict[str, Path]):
    result = _run_manager(env, "--dl", "401")

    assert result.returncode == 2
    assert "--dl requires --channel stable|ptb|canary." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_update_select_requires_channel(env: dict[str, Path]):
    result = _run_manager(env, "--update-select")

    assert result.returncode == 2
    assert "--update-select requires --channel stable|ptb|canary." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_openasar_requires_channel(env: dict[str, Path]):
    result = _run_manager(env, "--openasar")

    assert result.returncode == 2
    assert "--openasar requires --channel stable|ptb|canary|all." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_bd_requires_openasar_or_openasar_source(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--BD")

    assert result.returncode == 2
    assert "--BD requires --openasar or --openasar-source." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_update_equals_short_version_is_accepted(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--update=401")

    assert result.returncode == 0
    assert "Invalid Discord version" not in (result.stdout + result.stderr)


def test_dl_equals_short_version_is_accepted(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl=401")

    assert result.returncode == 0
    assert "Invalid Discord version" not in (result.stdout + result.stderr)


def test_update_with_version_is_rejected_for_multi_channel(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "ptb",
        "--update",
        "401",
    )

    assert result.returncode == 2
    assert "--update or --dl with a version only supports one channel at a time." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_dl_with_version_is_rejected_for_multi_channel(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "ptb",
        "--dl",
        "401",
    )

    assert result.returncode == 2
    assert "--dl only supports one channel at a time." in (result.stdout + result.stderr)
    _assert_no_download_artifacts(env)


def test_update_select_is_rejected_for_multi_channel(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "ptb",
        "--update-select",
    )

    assert result.returncode == 2
    assert "--update-select only supports one channel at a time." in (
        result.stdout + result.stderr
    )
    _assert_no_download_artifacts(env)


def test_all_channel_cannot_be_combined_with_named_channel(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "all", "stable")

    assert result.returncode == 2
    assert "--channel all cannot be combined with named channels." in (
        result.stdout + result.stderr
    )
    _assert_no_download_artifacts(env)


def test_dl_cannot_combine_with_update(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        "--update",
        "401",
    )

    assert result.returncode == 2
    assert (
        "--dl only downloads a DMG and cannot be combined with --update, --update-select, or --openasar."
        in (result.stdout + result.stderr)
    )
    _assert_no_download_artifacts(env)


def test_dl_cannot_combine_with_update_select(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        "--update-select",
    )

    assert result.returncode == 2
    assert (
        "--dl only downloads a DMG and cannot be combined with --update, --update-select, or --openasar."
        in (result.stdout + result.stderr)
    )
    _assert_no_download_artifacts(env)


def test_dl_cannot_combine_with_openasar(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        "--openasar",
    )

    assert result.returncode == 2
    assert (
        "--dl only downloads a DMG and cannot be combined with --update, --update-select, or --openasar."
        in (result.stdout + result.stderr)
    )
    _assert_no_download_artifacts(env)


def test_update_select_cannot_combine_with_update(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update-select",
        "--update",
        "401",
    )

    assert result.returncode == 2
    assert "--update-select only prints versions and cannot be combined with --update or --openasar." in (
        result.stdout + result.stderr
    )
    _assert_no_download_artifacts(env)


def test_update_select_cannot_combine_with_openasar(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update-select",
        "--openasar",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 2
    assert "--update-select only prints versions and cannot be combined with --update or --openasar." in (
        result.stdout + result.stderr
    )
    _assert_no_download_artifacts(env)


def test_repeated_channel_clauses_are_merged_and_deduplicated(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--channel", "stable", "--update")

    assert result.returncode == 0, result.stderr
    app_path = _application_path(env["applications_root"], "stable")
    assert app_path.exists()
    _assert_no_download_artifacts(env)


def test_channel_all_expands_to_three_channels(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "all",
        "--update",
    )

    assert result.returncode == 0, result.stderr
    for channel in APP_NAMES:
        assert _application_path(env["applications_root"], channel).exists()


def test_duplicate_named_channels_are_deduplicated_for_lock(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 0, result.stderr
    settings = _read_settings(_settings_path(env["home"], "stable"))
    assert settings["openasar"]["VersionLock"] == "401"


def test_lock_requires_update(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 2
    assert "--lock requires --update." in (result.stdout + result.stderr)


def test_lock_requires_update_with_explicit_version(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 2
    assert "--lock requires --update with an explicit version" in (result.stdout + result.stderr)


def test_lock_requires_openasar_or_openasar_source(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--update", "401", "--lock")

    assert result.returncode == 2
    assert "--lock requires --openasar or --openasar-source." in (result.stdout + result.stderr)


def test_lock_cannot_combine_with_update_select(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--update-select",
        "--lock",
    )

    assert result.returncode == 2
    assert "--lock cannot be combined with --update-select." in (result.stdout + result.stderr)


def test_lock_cannot_combine_with_bd(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--BD",
        "--lock",
    )

    assert result.returncode == 2
    assert "--lock cannot be combined with --BD." in (result.stdout + result.stderr)


def test_lock_cannot_combine_with_dl(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 2
    assert "--dl only downloads a DMG" in (result.stdout + result.stderr)


def test_lock_single_channel_constraint_stable_and_ptb(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "ptb",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 2
    assert "--lock requires exactly one channel" in (result.stdout + result.stderr)


def test_lock_single_channel_constraint_all_channel(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "all",
        "--update",
        "401",
        "--openasar-source",
        str(env["openasar_source"]),
        "--lock",
    )

    assert result.returncode == 2
    assert "--lock requires exactly one channel" in (result.stdout + result.stderr)


def test_production_applications_root_remains_fixed() -> None:
    source = SCRIPT_SOURCE.read_text(encoding="utf-8")

    assert 'DEFAULT_APPLICATIONS_ROOT="/Applications"' in source
    assert "DISCORD_INSTALL_MANAGER_APPLICATIONS_ROOT" not in source
