from __future__ import annotations

from pathlib import Path

import pytest

from _helpers import _application_path, _assert_no_update_artifacts, _run_manager, _settings_path


def _prepare_valid_data_dir(env: dict[str, Path], channel: str) -> Path:
    data_dir = _settings_path(env["home"], channel).parent
    data_dir.mkdir(parents=True)
    (data_dir / "settings.json").write_text("{}", encoding="utf-8")
    (data_dir / "Local Storage").mkdir()
    return data_dir


def _create_cleanup_target(data_dir: Path, relative_target: str, *, is_directory: bool = False) -> Path:
    target = data_dir / relative_target
    if is_directory:
        target.mkdir()
    else:
        target.write_text("target", encoding="utf-8")
    return target


def test_cleanup_fails_if_data_directory_is_missing(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 1
    assert "data directory not found:" in (result.stdout + result.stderr)
    _assert_no_update_artifacts(env)


def test_cleanup_leaves_non_managed_files_when_no_targets(env: dict[str, Path]):
    data_dir = _prepare_valid_data_dir(env, "stable")
    sentinel = data_dir / "arbitrary-sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert "Warning: no Discord installation files were detected." in result.stdout
    assert "Nothing was changed for Discord." in result.stdout
    assert sentinel.exists()


@pytest.mark.parametrize(
    ("relative_target", "is_directory"),
    [
        ("installer.db", False),
        ("ShipIt_request.json", False),
        ("0.0.401", True),
        ("app-9", True),
        ("modules", True),
        ("module_data", True),
        ("download", True),
        ("Cache", True),
        ("Code Cache", True),
    ],
    ids=[
        "installer.db",
        "shipit-request",
        "legacy-version",
        "app-shell",
        "modules-dir",
        "module-data",
        "download-dir",
        "cache-dir",
        "code-cache",
    ],
)
def test_cleanup_removes_each_managed_target(
    env: dict[str, Path], relative_target: str, is_directory: bool
):
    data_dir = _prepare_valid_data_dir(env, "stable")
    target = _create_cleanup_target(data_dir, relative_target, is_directory=is_directory)

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert f"installation files cleaned successfully." in result.stdout
    assert not target.exists()


def test_cleanup_refuses_invalid_data_directory(env: dict[str, Path]):
    data_dir = env["home"] / "Library" / "Application Support" / "discord"
    data_dir.mkdir(parents=True)
    (data_dir / "installer.db").write_text("x", encoding="utf-8")

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 1
    assert "does not look like Discord's data directory" in (result.stdout + result.stderr)
    assert (data_dir / "installer.db").exists()


def test_cleanup_removes_symlink_managed_target_only(env: dict[str, Path]):
    data_dir = _prepare_valid_data_dir(env, "stable")
    real_target = env["home"] / "external-installer.db"
    real_target.write_text("real-installer", encoding="utf-8")
    link_target = data_dir / "installer.db"
    link_target.symlink_to(real_target)

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert not link_target.exists()
    assert real_target.exists()


def test_cleanup_preserves_settings_json(env: dict[str, Path]):
    data_dir = _prepare_valid_data_dir(env, "stable")
    settings = data_dir / "settings.json"
    target = _create_cleanup_target(data_dir, "installer.db")

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert settings.exists()
    assert settings.read_text(encoding="utf-8") == "{}"


def test_cleanup_preserves_local_storage(env: dict[str, Path]):
    data_dir = _prepare_valid_data_dir(env, "stable")
    local_storage = data_dir / "Local Storage"
    target = _create_cleanup_target(data_dir, "installer.db")

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert local_storage.exists()


def test_cleanup_preserves_arbitrary_sentinel(env: dict[str, Path]):
    data_dir = _prepare_valid_data_dir(env, "stable")
    sentinel = data_dir / "keep-me.txt"
    sentinel.write_text("keep", encoding="utf-8")
    target = _create_cleanup_target(data_dir, "installer.db")

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert sentinel.exists()


@pytest.mark.parametrize("channel", ["stable", "ptb", "canary"])
def test_cleanup_uses_channel_specific_data_directories(env: dict[str, Path], channel: str):
    all_channels = ("stable", "ptb", "canary")
    data_dirs = {c: _prepare_valid_data_dir(env, c) for c in all_channels}
    target = "installer.db"

    _create_cleanup_target(data_dirs[channel], target)
    for c in all_channels:
        if c != channel:
            _create_cleanup_target(data_dirs[c], target)

    result = _run_manager(env, "--channel", channel)

    assert result.returncode == 0, result.stderr
    assert not (data_dirs[channel] / target).exists()
    for other_channel in all_channels:
        if other_channel == channel:
            continue
        assert (data_dirs[other_channel] / target).exists()


def test_cleanup_skips_missing_data_dir_for_update_mode(env: dict[str, Path]):
    app_path = _application_path(env["applications_root"], "stable")
    assert not app_path.exists()

    result = _run_manager(env, "--channel", "stable", "--update")

    assert result.returncode == 0, result.stderr
    assert "data directory not found, so there is no App Support cleanup to run:" in result.stdout
