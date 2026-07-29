from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from _helpers import (
    _application_path,
    _assert_no_download_artifacts,
    _run_manager,
    _settings_path,
)


def _prepare_data_directory(env: dict[str, Path], channel: str) -> Path:
    data_dir = _settings_path(env["home"], channel).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "settings.json").write_text("{}", encoding="utf-8")
    return data_dir


def _prepare_stub_app(env: dict[str, Path], channel: str) -> Path:
    app_path = _application_path(env["applications_root"], channel)
    executable = "Discord" if channel == "stable" else "Discord PTB" if channel == "ptb" else "Discord Canary"

    if app_path.exists():
        shutil.rmtree(app_path)

    resources = app_path / "Contents" / "Resources"
    info_plist = app_path / "Contents" / "Info.plist"
    executable_path = app_path / "Contents" / "MacOS" / executable

    info_plist.parent.mkdir(parents=True, exist_ok=True)
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    info_plist.write_text("plist", encoding="utf-8")
    executable_path.write_text("#!/usr/bin/env sh\necho", encoding="utf-8")
    executable_path.chmod(0o755)

    return resources


def _write_betterdiscord_marker(path: Path, channel: str, *, mode: str = "release") -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "1",
                "owner": "betterdiscord",
                "style": "app-wrapper",
                "channel": channel,
                "mode": mode,
                "loader": "index.js",
                "payload": "../betterdiscord.app.asar",
                "bdPath": "/tmp/betterdiscord",
                "installationId": "bd-install-id",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_betterdiscord_wrapper(resources: Path, channel: str, *, mode: str = "release") -> None:
    wrapper_dir = resources / "app"
    wrapper_dir.mkdir(parents=True)
    _write_betterdiscord_marker(wrapper_dir / ".betterdiscord-inject.json", channel=channel, mode=mode)
    (wrapper_dir / "index.js").write_text(
        "// __betterdiscord_inject_meta__\nmodule.exports = require(\"../betterdiscord.app.asar\");\n",
        encoding="utf-8",
    )
    (wrapper_dir / "package.json").write_text(
        json.dumps({"main": "index.js"}, indent=2),
        encoding="utf-8",
    )
    (resources / "betterdiscord.app.asar").write_text("wrapper-nested", encoding="utf-8")


def _snapshot_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_wrapper_unchanged(marker: Path, payload: Path, marker_before: str, payload_before: str) -> None:
    assert marker.read_text(encoding="utf-8") == marker_before
    assert payload.read_text(encoding="utf-8") == payload_before


@pytest.mark.parametrize("mode", ["release", "dev"])
def test_unwraps_release_and_dev_wrappers_to_standalone_app_asar(env: dict[str, Path], mode: str):
    resources = _prepare_stub_app(env, "stable")
    _prepare_data_directory(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable", mode=mode)
    nested_payload = (resources / "betterdiscord.app.asar").read_text(encoding="utf-8")

    result = _run_manager(env, "--channel", "stable")

    assert result.returncode == 0, result.stderr
    assert "Unwrapping BetterDiscord from" in result.stdout
    assert "BetterDiscord successfully unwrapped from" in result.stdout
    assert nested_payload == (resources / "app.asar").read_text(encoding="utf-8")
    assert not (resources / "app").exists()
    assert not (resources / "betterdiscord.app.asar").exists()


def test_betterdiscord_wrapper_invalid_marker_json_refuses_without_mutation(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    marker_path = resources / "app" / ".betterdiscord-inject.json"
    payload_path = resources / "betterdiscord.app.asar"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text("{bad", encoding="utf-8")
    payload_path.write_text("wrapper-nested", encoding="utf-8")
    (marker_path.parent / "index.js").write_text(
        "// __betterdiscord_inject_meta__\nmodule.exports = require(\"../betterdiscord.app.asar\");\n",
        encoding="utf-8",
    )
    (marker_path.parent / "package.json").write_text(json.dumps({"main": "index.js"}), encoding="utf-8")
    payload_path.write_text("wrapper-nested", encoding="utf-8")

    marker_before = _snapshot_text(marker_path)
    payload_before = _snapshot_text(payload_path)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--BD",
        "--openasar-source",
        str(env["openasar_source"]),
    )

    assert result.returncode == 1
    assert "Refusing to modify" in result.stderr
    _assert_wrapper_unchanged(marker_path, payload_path, marker_before, payload_before)
    assert not (resources / "app.asar").exists()
    _assert_no_download_artifacts(env)


def test_betterdiscord_wrapper_wrong_marker_channel_refuses_and_does_not_mutate(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "ptb")

    marker_path = resources / "app" / ".betterdiscord-inject.json"
    payload_path = resources / "betterdiscord.app.asar"
    marker_before = _snapshot_text(marker_path)
    payload_before = _snapshot_text(payload_path)

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "does not match the supported BetterDiscord wrapper contract" in result.stderr
    _assert_wrapper_unchanged(marker_path, payload_path, marker_before, payload_before)


def test_betterdiscord_wrapper_missing_ownership_marker_in_loader_refuses(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")
    (resources / "app" / "index.js").write_text(
        'module.exports = require("../betterdiscord.app.asar");\n',
        encoding="utf-8",
    )

    marker_path = resources / "app" / ".betterdiscord-inject.json"
    payload_path = resources / "betterdiscord.app.asar"
    marker_before = _snapshot_text(marker_path)
    payload_before = _snapshot_text(payload_path)

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "missing the BetterDiscord ownership marker" in result.stderr
    _assert_wrapper_unchanged(marker_path, payload_path, marker_before, payload_before)


def test_betterdiscord_wrapper_wrong_package_main_refuses(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")
    (resources / "app" / "package.json").write_text(json.dumps({"main": "main.js"}), encoding="utf-8")

    marker_path = resources / "app" / ".betterdiscord-inject.json"
    payload_path = resources / "betterdiscord.app.asar"
    marker_before = _snapshot_text(marker_path)
    payload_before = _snapshot_text(payload_path)

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "does not use index.js as its main entry" in result.stderr
    _assert_wrapper_unchanged(marker_path, payload_path, marker_before, payload_before)


def test_betterdiscord_wrapper_empty_nested_payload_refuses(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")
    payload_path = resources / "betterdiscord.app.asar"
    payload_path.write_text("", encoding="utf-8")

    marker_path = resources / "app" / ".betterdiscord-inject.json"
    marker_before = _snapshot_text(marker_path)

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "betterdiscord.app.asar is missing or invalid" in result.stderr
    assert payload_path.read_text(encoding="utf-8") == ""
    assert marker_path.read_text(encoding="utf-8") == marker_before


def test_betterdiscord_wrapper_rejects_extra_entry(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")
    (resources / "app" / "extra.txt").write_text("not part of contract", encoding="utf-8")

    marker_path = resources / "app" / ".betterdiscord-inject.json"
    payload_path = resources / "betterdiscord.app.asar"
    marker_before = _snapshot_text(marker_path)
    payload_before = _snapshot_text(payload_path)

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "not part of the BetterDiscord wrapper contract" in result.stderr
    _assert_wrapper_unchanged(marker_path, payload_path, marker_before, payload_before)


def test_betterdiscord_wrapper_rejects_competing_top_level_asar(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")
    (resources / "app.asar").write_text("standalone", encoding="utf-8")

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "already exists beside the BetterDiscord wrapper" in result.stderr
    assert (resources / "app.asar").read_text(encoding="utf-8") == "standalone"


def test_betterdiscord_wrapper_rejects_stale_unwrap_directory(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")
    (resources / ".betterdiscord-app-unwrapping-abc").mkdir()

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "is a stale BetterDiscord unwrap path" in result.stderr


@pytest.mark.parametrize("symlink_target", ["marker", "payload"])
def test_betterdiscord_wrapper_rejects_symlinked_marker_or_payload(env: dict[str, Path], symlink_target: str):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")

    marker_path = resources / "app" / ".betterdiscord-inject.json"
    payload_path = resources / "betterdiscord.app.asar"
    marker_before = _snapshot_text(marker_path)
    payload_before = _snapshot_text(payload_path)

    if symlink_target == "marker":
        marker_target = resources / "wrapper-marker.json"
        marker_target.write_text(marker_before, encoding="utf-8")
        marker_path.unlink()
        marker_path.symlink_to(marker_target)
    else:
        payload_target = resources / "payload.asar"
        payload_target.write_text(payload_before, encoding="utf-8")
        payload_path.unlink()
        payload_path.symlink_to(payload_target)

    result = _run_manager(env, "--channel", "stable", "--BD", "--openasar-source", str(env["openasar_source"]))

    assert result.returncode != 0
    assert "is missing or invalid" in result.stderr
    if symlink_target == "marker":
        assert marker_path.is_symlink()
    else:
        assert payload_path.is_symlink()
    assert marker_path.read_text(encoding="utf-8") == marker_before
    assert payload_path.read_text(encoding="utf-8") == payload_before


def test_betterdiscord_flag_preserves_valid_wrapper_and_replaces_nested_payload_only(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")

    result = _run_manager(env, "--channel", "stable", "--openasar-source", str(env["openasar_source"]), "--BD")

    assert result.returncode == 0, result.stderr
    assert "Preserving the validated BetterDiscord wrapper for Discord." in result.stdout
    assert "OpenAsar will replace its nested betterdiscord.app.asar payload." in result.stdout
    assert "Injecting OpenAsar into the BetterDiscord nested payload for Discord..." in result.stdout
    assert (resources / "app").exists()
    assert (resources / "betterdiscord.app.asar").read_text(encoding="utf-8") == "openasar"


def test_betterdiscord_without_wrapper_injects_standalone_payload(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    (resources / "app.asar").write_text("standalone-before", encoding="utf-8")
    _prepare_data_directory(env, "stable")

    result = _run_manager(env, "--channel", "stable", "--openasar-source", str(env["openasar_source"]), "--BD")

    assert result.returncode == 0, result.stderr
    assert "No BetterDiscord wrapper was detected for Discord." in result.stdout
    assert "OpenAsar will use the normal standalone app.asar layout." in result.stdout
    assert "Injecting standalone OpenAsar into Discord..." in result.stdout
    assert (resources / "app").exists() is False
    assert not (resources / "betterdiscord.app.asar").exists()
    assert (resources / "app.asar").read_text(encoding="utf-8") == "openasar"


def test_update_replaces_wrapped_app_with_unwrapped_app(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")

    result = _run_manager(env, "--channel", "stable", "--update")

    assert result.returncode == 0, result.stderr
    assert "Discord app replaced successfully." in result.stdout
    assert not (resources / "app").exists()
    assert not (resources / "betterdiscord.app.asar").exists()
    assert (resources / "app.asar").exists()


def test_betterdiscord_update_guard_prevents_combined_update_and_bd(env: dict[str, Path]):
    resources = _prepare_stub_app(env, "stable")
    _write_betterdiscord_wrapper(resources, "stable")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--update",
        "--openasar-source",
        str(env["openasar_source"]),
        "--BD",
    )

    assert result.returncode == 2
    assert "--BD cannot be combined with --update because updating replaces the BetterDiscord wrapper." in (
        result.stdout + result.stderr
    )
    assert (resources / "app").exists()
    assert (resources / "betterdiscord.app.asar").exists()
