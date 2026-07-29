from __future__ import annotations

import pytest

from pathlib import Path

from _helpers import (
    _assert_no_download_artifacts,
    _dmg_path,
    _read_command_log,
    _run_manager,
)


def _aria2_entries(command_log: list[str]) -> list[str]:
    return [entry for entry in command_log if entry.startswith("aria2c\t")]


def _curl_entries(command_log: list[str]) -> list[str]:
    return [entry for entry in command_log if entry.startswith("curl\t")]


def test_downloads_with_short_pinned_version_uses_expected_url_and_aria2(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl", "401")

    assert result.returncode == 0, result.stderr
    assert _dmg_path(env["script"], "stable", "0.0.401").exists()

    command_log = _read_command_log(env)
    aria2_calls = _aria2_entries(command_log)
    assert len(aria2_calls) == 1
    assert "https://stable.dl2.discordapp.net/apps/osx/0.0.401/Discord.dmg" in aria2_calls[0]


def test_downloads_with_canonical_pinned_version_uses_expected_url_and_aria2(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl", "0.0.401")

    assert result.returncode == 0, result.stderr
    assert _dmg_path(env["script"], "stable", "0.0.401").exists()

    command_log = _read_command_log(env)
    aria2_calls = _aria2_entries(command_log)
    assert len(aria2_calls) == 1
    assert "https://stable.dl2.discordapp.net/apps/osx/0.0.401/Discord.dmg" in aria2_calls[0]


def test_downloads_with_no_version_uses_latest_manifest(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl")

    assert result.returncode == 0, result.stderr
    assert "Resolved Discord version:" in result.stdout
    assert "  0.0.401" in result.stdout

    command_log = _read_command_log(env)
    curl_calls = _curl_entries(command_log)
    assert any("/api/updates/stable?platform=osx" in entry for entry in curl_calls)
    aria2_calls = _aria2_entries(command_log)
    assert any("https://discord.com/api/download/stable?platform=osx" in entry for entry in aria2_calls)


def test_downloads_rejects_invalid_version(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl", "abc")

    assert result.returncode == 2
    assert "Invalid Discord version: abc" in (result.stdout + result.stderr)
    assert not _dmg_path(env["script"], "stable", "401").exists()
    assert not _read_command_log(env)


def test_downloads_prefers_aria2_when_available(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl", "401")

    assert result.returncode == 0, result.stderr
    assert "Using aria2c downloader:" in result.stdout
    command_log = _read_command_log(env)
    assert _aria2_entries(command_log)
    assert not _curl_entries(command_log)


def test_downloads_falls_back_to_curl_when_aria2_unavailable(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        path_override=env["fake_bin_without_aria2"],
        required_tools=("curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
    )

    assert result.returncode == 0, result.stderr
    assert "Using curl downloader." in result.stdout
    command_log = _read_command_log(env)
    assert _curl_entries(command_log)
    assert not _aria2_entries(command_log)


def test_downloads_defaults_to_16_download_connections(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl", "401")

    assert result.returncode == 0, result.stderr
    aria2_calls = _aria2_entries(_read_command_log(env))
    assert len(aria2_calls) == 1
    assert "--max-connection-per-server=16" in aria2_calls[0]
    assert "--split=16" in aria2_calls[0]


@pytest.mark.parametrize("connections", ["4", "9"])
def test_downloads_uses_custom_download_connections(env: dict[str, Path], connections: str):
    result = _run_manager(env, "--channel", "stable", "--dl", "401", extra_env={"DISCORD_DOWNLOAD_CONNECTIONS": connections})

    assert result.returncode == 0, result.stderr
    aria2_calls = _aria2_entries(_read_command_log(env))
    assert len(aria2_calls) == 1
    assert f"--max-connection-per-server={connections}" in aria2_calls[0]
    assert f"--split={connections}" in aria2_calls[0]


@pytest.mark.parametrize("connections", ["0", "invalid"])
def test_downloads_falls_back_for_invalid_or_zero_download_connections(env: dict[str, Path], connections: str):
    result = _run_manager(env, "--channel", "stable", "--dl", "401", extra_env={"DISCORD_DOWNLOAD_CONNECTIONS": connections})

    assert result.returncode == 0, result.stderr
    aria2_calls = _aria2_entries(_read_command_log(env))
    assert len(aria2_calls) == 1
    assert "--max-connection-per-server=16" in aria2_calls[0]
    assert "--split=16" in aria2_calls[0]


def test_downloads_caps_download_connections_at_16(env: dict[str, Path]):
    result = _run_manager(env, "--channel", "stable", "--dl", "401", extra_env={"DISCORD_DOWNLOAD_CONNECTIONS": "999"})

    assert result.returncode == 0, result.stderr
    aria2_calls = _aria2_entries(_read_command_log(env))
    assert len(aria2_calls) == 1
    assert "--max-connection-per-server=16" in aria2_calls[0]
    assert "--split=16" in aria2_calls[0]


def test_downloads_aria2_transient_failure_then_succeeds(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        extra_env={"TEST_FAKE_ARIA2_FAIL_ATTEMPTS": "2"},
    )

    assert result.returncode == 0, result.stderr
    command_log = _read_command_log(env)
    aria2_calls = _aria2_entries(command_log)
    assert len(aria2_calls) == 3
    assert result.stdout.count("Retrying in 3 seconds...") == 2
    assert _dmg_path(env["script"], "stable", "0.0.401").exists()


def test_downloads_aria2_empty_then_succeeds(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        extra_env={"TEST_FAKE_ARIA2_EMPTY_ATTEMPTS": "1"},
    )

    assert result.returncode == 0, result.stderr
    command_log = _read_command_log(env)
    aria2_calls = _aria2_entries(command_log)
    assert len(aria2_calls) == 2
    assert result.stdout.count("Retrying in 3 seconds...") == 1
    assert _dmg_path(env["script"], "stable", "0.0.401").exists()


def test_downloads_aria2_permanent_failure_cleans_artifacts(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        extra_env={"TEST_FAKE_ARIA2_ALWAYS_FAIL": "1"},
    )

    assert result.returncode != 0
    assert "installer download failed after 3 attempts." in (result.stdout + result.stderr)
    assert len(_aria2_entries(_read_command_log(env))) == 3
    assert not _dmg_path(env["script"], "stable", "0.0.401").exists()
    assert not (env["script"].parent / "Discord-stable-installer (0.0.401).dmg.aria2").exists()
    _assert_no_download_artifacts(env)


def test_downloads_curl_transient_failure_then_succeeds(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        path_override=env["fake_bin_without_aria2"],
        required_tools=("curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
        extra_env={"TEST_FAKE_CURL_FAIL_ATTEMPTS": "2"},
    )

    assert result.returncode == 0, result.stderr
    command_log = _read_command_log(env)
    curl_calls = _curl_entries(command_log)
    assert len(curl_calls) == 3
    assert not _aria2_entries(command_log)
    assert result.stdout.count("Retrying in 3 seconds...") == 2
    assert _dmg_path(env["script"], "stable", "0.0.401").exists()


def test_downloads_curl_permanent_failure_cleans_artifacts(env: dict[str, Path]):
    result = _run_manager(
        env,
        "--channel",
        "stable",
        "--dl",
        "401",
        path_override=env["fake_bin_without_aria2"],
        required_tools=("curl", "hdiutil", "ditto", "sleep", "open", "osascript", "rm"),
        extra_env={"TEST_FAKE_CURL_ALWAYS_FAIL": "1"},
    )

    assert result.returncode != 0
    assert "installer download failed after 3 attempts." in (result.stdout + result.stderr)
    command_log = _read_command_log(env)
    assert len(_curl_entries(command_log)) == 3
    assert not _dmg_path(env["script"], "stable", "0.0.401").exists()
    _assert_no_download_artifacts(env)
