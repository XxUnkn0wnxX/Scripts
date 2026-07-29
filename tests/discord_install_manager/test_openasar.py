from __future__ import annotations

from pathlib import Path

import pytest

from _helpers import _application_path, _read_command_log, _run_manager, _settings_path


def _create_standalone_app(env: dict[str, Path], *, channel: str = "stable", payload: bytes = b"base-asar") -> Path:
    app_path = _application_path(env["applications_root"], channel)
    app_path.mkdir(parents=True, exist_ok=True)
    (app_path / "Contents").mkdir(parents=True, exist_ok=True)
    (app_path / "Contents" / "Info.plist").write_text("plist", encoding="utf-8")

    executable = app_path / "Contents" / "MacOS" / app_path.name.removesuffix(".app")
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("bin", encoding="utf-8")
    executable.chmod(0o755)

    resources = app_path / "Contents" / "Resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "app.asar").write_bytes(payload)

    return app_path


def _create_standalone_app_without_resources(env: dict[str, Path], *, channel: str = "stable", payload: bytes = b"base-asar") -> Path:
    app_path = _create_standalone_app(env, channel=channel, payload=payload)
    resources = app_path / "Contents" / "Resources"
    (resources / "app.asar").unlink(missing_ok=True)
    resources.rmdir()
    return app_path


def _write_openasar_source(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _prepare_data_dir(
    env: dict[str, Path],
    *,
    channel: str = "stable",
    include_settings: bool = True,
    include_local_storage: bool = False,
) -> Path:
    data_dir = _settings_path(env["home"], channel).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    if include_settings:
        _settings_path(env["home"], channel).write_text("{}", encoding="utf-8")
    if include_local_storage:
        (data_dir / "Local Storage").mkdir(exist_ok=True)
    return data_dir


def test_openasar_injects_local_absolute_payload(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"from-standalone")
    source = env["home"] / "local-openasar.app.asar"
    payload = b"local-absolute"
    _write_openasar_source(source, payload)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode == 0, result.stderr
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == payload
    assert "Injecting standalone OpenAsar into Discord" in result.stdout


@pytest.mark.parametrize(
    "source_form",
    [
        "absolute",
        "relative",
        "tilde",
        "home_literal",
        "home_braced",
        "file_url",
    ],
    ids=["absolute", "relative", "tilde", "home_literal", "home_braced", "file_url"],
)
def test_openasar_source_path_variants_are_resolved(env: dict[str, Path], source_form: str):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"base-asar")

    source_payload = f"payload-{source_form}".encode()
    expected_source = env["home"] / f"openasar-{source_form}.app.asar"
    _write_openasar_source(expected_source, source_payload)

    match source_form:
        case "absolute":
            source_arg = str(expected_source)
        case "relative":
            source_arg = expected_source.name
        case "tilde":
            source_arg = f"~/{expected_source.name}"
        case "home_literal":
            source_arg = f"$HOME/{expected_source.name}"
        case "home_braced":
            source_arg = f"${{HOME}}/{expected_source.name}"
        case "file_url":
            source_arg = f"file://{expected_source}"
        case _:
            raise AssertionError(f"unexpected source form: {source_form}")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        source_arg,
    )

    assert result.returncode == 0, result.stderr
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == source_payload


def test_local_openasar_source_file_is_not_modified(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"base-asar")
    source = env["home"] / "openasar-stable-source.app.asar"
    source_payload = b"persistent-source"
    _write_openasar_source(source, source_payload)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode == 0, result.stderr
    assert source.read_bytes() == source_payload
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == source_payload


def test_missing_local_openasar_source_skips_injection_without_replacement(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")
    missing_source = env["home"] / "missing-openasar.app.asar"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(missing_source),
    )

    assert result.returncode == 0, result.stderr
    assert "OpenAsar injection will be skipped because the payload could not be prepared." in (
        result.stdout + result.stderr
    )
    assert "Local OpenAsar payload was not found:" in (result.stdout + result.stderr)
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == b"original"


def test_empty_local_openasar_source_skips_injection_without_replacement(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")
    empty_source = env["home"] / "empty-openasar.app.asar"
    _write_openasar_source(empty_source, b"")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(empty_source),
    )

    assert result.returncode == 0, result.stderr
    assert "OpenAsar injection will be skipped because the payload could not be prepared." in (
        result.stdout + result.stderr
    )
    assert "Local OpenAsar payload is empty:" in (result.stdout + result.stderr)
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == b"original"


def test_missing_app_refuses_openasar_injection(env: dict[str, Path]):
    _prepare_data_dir(env)
    payload = b"should-not-inject"
    source = env["home"] / "local-openasar.app.asar"
    _write_openasar_source(source, payload)
    app_path = _application_path(env["applications_root"], "stable")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode != 0
    assert "app was not found:" in (result.stdout + result.stderr)
    assert not app_path.exists()


def test_missing_resources_refuses_openasar_injection(env: dict[str, Path]):
    _prepare_data_dir(env)
    payload = b"local-openasar"
    source = env["home"] / "local-openasar.app.asar"
    _write_openasar_source(source, payload)
    app_path = _create_standalone_app_without_resources(env, payload=b"base-asar")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode != 0
    assert "resources directory was not found:" in (result.stdout + result.stderr)
    assert not (app_path / "Contents" / "Resources").exists()


def test_missing_app_asar_refuses_openasar_injection(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"base-asar")
    target = app_path / "Contents" / "Resources" / "app.asar"
    target.unlink()
    source = env["home"] / "local-openasar.app.asar"
    _write_openasar_source(source, b"replacement")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode == 1
    assert "target app.asar is missing or is not a regular file:" in (
        result.stdout + result.stderr
    )
    assert not list(target.parent.glob(".openasar-app-*"))


def test_symlink_app_asar_refused_and_stage_is_not_left(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"base-asar")
    real_target = env["home"] / "real-asar.app.asar"
    _write_openasar_source(real_target, b"real")

    app_asar = app_path / "Contents" / "Resources" / "app.asar"
    app_asar.unlink()
    app_asar.symlink_to(real_target)

    source = env["home"] / "local-openasar.app.asar"
    source_payload = b"replacement"
    _write_openasar_source(source, source_payload)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode != 0
    assert "is missing or is not a regular file:" in (result.stdout + result.stderr)
    assert not list((app_path / "Contents" / "Resources").glob(".openasar-app-*"))


def test_openasar_stage_copy_failure_preserves_target_and_removes_partial_stage(
    env: dict[str, Path],
):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")
    resources = app_path / "Contents" / "Resources"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={"TEST_FAKE_CP_FAIL_OPENASAR": "1"},
    )

    assert result.returncode == 1
    assert "failed while staging the payload" in (result.stdout + result.stderr)
    assert (resources / "app.asar").read_bytes() == b"original"
    assert not list(resources.glob(".openasar-app-*"))


def test_openasar_staged_compare_failure_preserves_target_and_removes_stage(
    env: dict[str, Path],
):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")
    resources = app_path / "Contents" / "Resources"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={"TEST_FAKE_CMP_FAIL_ATTEMPT": "1"},
    )

    assert result.returncode == 1
    assert "staged ASAR does not match" in (result.stdout + result.stderr)
    assert (resources / "app.asar").read_bytes() == b"original"
    assert not list(resources.glob(".openasar-app-*"))


def test_openasar_stage_rename_failure_preserves_target_and_removes_stage(
    env: dict[str, Path],
):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")
    resources = app_path / "Contents" / "Resources"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={"TEST_FAKE_MV_FAIL_OPENASAR": "1"},
    )

    assert result.returncode == 1
    assert "failed while replacing app.asar" in (result.stdout + result.stderr)
    assert (resources / "app.asar").read_bytes() == b"original"
    assert not list(resources.glob(".openasar-app-*"))


def test_openasar_post_rename_compare_failure_is_reported_without_staging_residue(
    env: dict[str, Path],
):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")
    resources = app_path / "Contents" / "Resources"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(env["openasar_source"]),
        extra_env={"TEST_FAKE_CMP_FAIL_ATTEMPT": "2"},
    )

    assert result.returncode == 1
    assert "installed app.asar does not match" in (result.stdout + result.stderr)
    assert (resources / "app.asar").read_bytes() == env["openasar_source"].read_bytes()
    assert not list(resources.glob(".openasar-app-*"))


@pytest.mark.parametrize(
    "source",
    [
        "https://github.com/XxUnkn0wnxX/OpenAsar",
        "https://github.com/XxUnkn0wnxX/OpenAsar/",
        "https://github.com/XxUnkn0wnxX/OpenAsar.git",
    ],
    ids=["plain", "trailing-slash", "dot-git"],
)
def test_openasar_github_source_url_is_normalized_for_remote_download(
    env: dict[str, Path], source: str
):
    _prepare_data_dir(env)
    _create_standalone_app(env, payload=b"base-asar")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        source,
        path_override=env["fake_bin_without_aria2"],
        required_tools=("curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
    )

    assert result.returncode == 0, result.stderr
    assert "https://github.com/XxUnkn0wnxX/OpenAsar/releases/latest/download/app.asar" in (
        result.stdout + result.stderr
    )


def test_openasar_direct_remote_url_is_preserved(env: dict[str, Path]):
    _prepare_data_dir(env)
    _create_standalone_app(env, payload=b"base-asar")
    direct_url = "https://cdn.example.com/downloads/discord/openasar-app.asar"

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        direct_url,
        path_override=env["fake_bin_without_aria2"],
        required_tools=("curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
    )

    assert result.returncode == 0, result.stderr
    assert direct_url in (result.stdout + result.stderr)


def test_openasar_remote_download_retries_then_succeeds(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"base-asar")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        "https://github.com/XxUnkn0wnxX/OpenAsar",
        extra_env={"TEST_FAKE_ARIA2_FAIL_ATTEMPTS": "2"},
    )

    assert result.returncode == 0, result.stderr
    command_log = _read_command_log(env)
    assert sum(1 for entry in command_log if entry.startswith("aria2c")) == 3
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == b"aria2-dmg"


def test_openasar_remote_download_permanent_failure_skips_injection_and_removes_payload(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"original")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        "https://github.com/XxUnkn0wnxX/OpenAsar",
        extra_env={"TEST_FAKE_ARIA2_MODE": "absent"},
    )

    assert result.returncode == 0, result.stderr
    assert "OpenAsar injection will be skipped because the payload could not be prepared." in (
        result.stdout + result.stderr
    )
    assert not (env["script"].parent / "openasar-app.asar").exists()
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == b"original"


def test_closed_client_verification_does_not_call_open(env: dict[str, Path]):
    _prepare_data_dir(env)
    payload = b"closed-client-asar"
    source = env["home"] / "local-openasar.app.asar"
    _write_openasar_source(source, payload)
    _create_standalone_app(env, payload=b"base-asar")

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode == 0, result.stderr
    assert "OpenAsar installation verified for Discord; the client remains closed." in result.stdout
    assert all(not entry.startswith("open\t") for entry in _read_command_log(env))


def test_openasar_injection_uses_source_bytes_exactly(env: dict[str, Path]):
    _prepare_data_dir(env)
    app_path = _create_standalone_app(env, payload=b"base-asar")
    source = env["home"] / "binary-openasar.app.asar"
    source_payload = b"\x00\x01\x02installed-bytes\xff\x89"
    _write_openasar_source(source, source_payload)

    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--openasar-source",
        str(source),
    )

    assert result.returncode == 0, result.stderr
    assert (app_path / "Contents" / "Resources" / "app.asar").read_bytes() == source_payload
