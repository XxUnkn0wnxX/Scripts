from __future__ import annotations

import hashlib
import json
import plistlib
import zipfile
import zipfile
import os
from pathlib import Path

import pytest

from ._helpers import SCRIPT, app, run


def test_backup_publication_replaces_symlink_and_preserves_referent(env):
    target = app(env["root"] / "Prowlarr.app", "original-payload")
    referent = env["root"] / "keep-this-file"
    referent.write_text("preserve this data")
    backup = env["root"] / "Prowlarr.backup.zip"
    backup.symlink_to(referent)
    result = run(env, str(target))
    assert result.returncode == 0, result.stderr
    assert not backup.is_symlink()
    assert referent.read_text() == "preserve this data"
    with zipfile.ZipFile(backup) as archive:
        assert archive.read("Prowlarr.app/Contents/MacOS/Prowlarr") == b"original-payload"


def test_valid_metadata_with_failed_producer_is_rejected_before_unload(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    result = run(env, str(target), extra={"FAIL_PATCHED_OTOOL": "1", "PROWLARR_MANAGE_LAUNCH_AGENT": "true", "JOB_STATE_FILE": str(state), "LOADED_EXEC": str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode != 0
    assert state.read_text() == "loaded"
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"
    assert "launchctl bootout" not in env["log"].read_text()


def test_valid_hash_with_failed_producer_preserves_cached_archive(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    downloaded = app(env["root"] / "download-source.app", "new")
    release = _release("2.10.0", prerelease=False)
    metadata = _metadata(env, [release])
    cached = env["home"] / "Downloads" / release["assets"][0]["name"]
    cached.write_bytes(b"existing-archive")
    result = run(env, "--dl", "stable", str(target), extra={"FAIL_DOWNLOAD_HASH": "1", "METADATA_DIR": str(metadata), "ARCHIVE_CONTENT": "abc", "DOWNLOAD_APP": str(downloaded)})
    assert result.returncode != 0
    assert "could not hash downloaded archive" in result.stderr
    assert cached.read_bytes() == b"existing-archive"
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_has_no_external_effects(env, flag):
    result = run(env, flag)
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert not env["log"].exists()
    assert not (env["root"] / "Prowlarr.app").exists()


@pytest.mark.parametrize(
    "args",
    [("--unknown",), ("one.app", "two.app"), ("--dl", "beta"), ("--dl", "stable", "extra")],
)
def test_invalid_arguments_fail_before_side_effects(env, args):
    result = run(env, *args)
    assert result.returncode == 2
    assert "Prowlarr patch:" in result.stderr
    assert not env["log"].exists()


def test_exported_configuration_is_honored_and_disabled_skips_service_calls(env):
    result = run(env, "--dl", "pre", str(env["root"] / "Prowlarr.app"), extra={"PROWLARR_MANAGE_LAUNCH_AGENT": "false", "PROWLARR_LAUNCH_AGENT": "../Prowlarr"})
    assert result.returncode != 0  # the fake downloader is not configured
    calls = env["log"].read_text() if env["log"].exists() else ""
    assert "launchctl" not in calls
    assert "plutil" not in calls
    assert "Prowlarr patch: Unloading launch agent " not in result.stdout
    assert "Prowlarr patch: Reloading launch agent " not in result.stdout


def test_local_patch_signs_registers_and_retains_original(env):
    target = app(env["root"] / "Prowlarr.app", "original-bytes")
    result = run(env, str(target))
    assert result.returncode == 0, result.stderr
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original-bytes"
    info = plistlib.loads((target / "Contents/Info.plist").read_bytes())
    assert info["LSMinimumSystemVersion"] == "11.0"
    assert info["LSMinimumSystemVersionByArchitecture"]["x86_64"] == "11.0"
    assert (env["root"] / "Prowlarr.backup.zip").exists()
    calls = env["log"].read_text()
    assert "vtool " in calls and "codesign --force --deep --sign -" in calls
    assert "lsregister -f " in calls
    assert "launchctl" not in calls


def test_signing_failure_keeps_live_bundle_and_skips_service_cleanup(env):
    target = app(env["root"] / "Prowlarr.app", "keep-me")
    result = run(env, str(target), extra={"FAIL_SIGN": "1"})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "keep-me"
    assert not (env["root"] / "Prowlarr.backup.zip").exists()
    assert "launchctl" not in (env["log"].read_text() if env["log"].exists() else "")


def test_unmanaged_executable_use_blocks_replacement(env):
    target = app(env["root"] / "Prowlarr.app")
    result = run(env, str(target), extra={"BUSY": "1"})
    assert result.returncode != 0
    assert "still in use" in result.stderr
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "old"
    assert not (env["root"] / "Prowlarr.backup.zip").exists()


@pytest.mark.parametrize("loaded", [None, False, True])
def test_correct_local_app_is_noop_without_service_bounce(env, loaded):
    target = app(env["root"] / "Prowlarr.app", "already-good")
    # Match candidate metadata and bytes so the local path takes the verified no-op.
    (target / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier":"com.osx.prowlarr.com","CFBundleExecutable":"Prowlarr","LSMinimumSystemVersion":"11.0","LSMinimumSystemVersionByArchitecture":{"x86_64":"11.0"}}))
    (target / ".signed").touch()
    extra = {}
    if loaded is not None:
        _agent(env, target)
        state = env["root"] / "job-state"
        state.write_text("loaded" if loaded else "unloaded")
        extra = {"PROWLARR_MANAGE_LAUNCH_AGENT": "true", "JOB_STATE_FILE": str(state), "LOADED_EXEC": str(target / "Contents/MacOS/Prowlarr")}
    result = run(env, str(target), extra=extra)
    assert result.returncode == 0, result.stderr
    assert "no changes made" in result.stdout
    assert not (env["root"] / "Prowlarr.backup.zip").exists()
    calls = env["log"].read_text()
    assert "launchctl bootout" not in calls and "launchctl bootstrap" not in calls
    assert "Prowlarr patch: Unloading launch agent " not in result.stdout
    assert "Prowlarr patch: Reloading launch agent " not in result.stdout
    if loaded is None:
        assert "launchctl" not in calls
    else:
        assert "launchctl print" in calls
        assert state.read_text() == ("loaded" if loaded else "unloaded")


def _agent(env, target: Path, *, program_key="Program"):
    plist = env["home"] / "Library/LaunchAgents/Prowlarr.plist"
    plist.parent.mkdir(parents=True)
    record = {"Label": "local.test.prowlarr"}
    if program_key == "Program":
        record["Program"] = str(target / "Contents/MacOS/Prowlarr")
    else:
        record["ProgramArguments"] = [str(target / "Contents/MacOS/Prowlarr"), "--nobrowser"]
    plist.write_bytes(plistlib.dumps(record))
    return plist


@pytest.mark.parametrize("program_key", ["Program", "ProgramArguments"])
def test_unloaded_agent_stays_unloaded_with_exact_plist(env, program_key):
    target = app(env["root"] / "Prowlarr.app")
    plist = _agent(env, target, program_key=program_key)
    before = hashlib.sha256(plist.read_bytes()).hexdigest()
    # launchctl's default fixture reports unloaded; the exact plist remains untouched.
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT": "true"})
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(plist.read_bytes()).hexdigest() == before
    calls = env["log"].read_text()
    assert "launchctl print" in calls
    assert "launchctl bootout" not in calls and "launchctl bootstrap" not in calls
    assert "Prowlarr patch: Unloading launch agent " not in result.stdout
    assert "Prowlarr patch: Reloading launch agent " not in result.stdout


def test_bad_agent_name_is_rejected_without_service_mutation(env):
    target = app(env["root"] / "Prowlarr.app")
    _agent(env, target)
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT": "true", "PROWLARR_LAUNCH_AGENT": "../Prowlarr"})
    assert result.returncode != 0
    assert "simple plist name" in result.stderr
    assert "launchctl" not in (env["log"].read_text() if env["log"].exists() else "")


def test_missing_agent_is_left_missing(env):
    target = app(env["root"] / "Prowlarr.app")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT": "true"})
    assert result.returncode == 0, result.stderr
    calls = env["log"].read_text()
    assert "launchctl" not in calls
    assert "Prowlarr patch: Unloading launch agent " not in result.stdout
    assert "Prowlarr patch: Reloading launch agent " not in result.stdout


def test_local_path_can_be_replaced_when_version_is_older(env):
    target = app(env["root"] / "Prowlarr.app", "old-version")
    (target / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier":"com.osx.prowlarr.com","CFBundleExecutable":"Prowlarr","CFBundleShortVersionString":"1.0"}))
    result = run(env, str(target))
    assert result.returncode == 0, result.stderr
    assert (env["root"] / "Prowlarr.backup.zip").exists()
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "old-version"


def _release(tag: str, *, prerelease: bool, asset=True, version_name=None):
    assets = []
    if asset:
        assets.append({"name": "Prowlarr.master.osx-app-core-x64.zip", "browser_download_url": f"https://github.com/Prowlarr/Prowlarr/releases/download/{tag}/app.zip", "digest": "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"})
    return {"tag_name": tag, "name": version_name or tag, "draft": False, "prerelease": prerelease, "assets": assets}


def _metadata(env, page1, page2=None):
    directory = env["root"] / "metadata"
    directory.mkdir()
    (directory / "page1.json").write_text(json.dumps(page1))
    (directory / "page2.json").write_text(json.dumps(page2 or []))
    return directory


@pytest.mark.parametrize("family,expected,installed", [("stable", "2.10.0", "2.10.0"), ("pre", "3.0.1", "3.0.1"), ("stable", "2.10.0", "0.1.0"), ("pre", "3.0.1", "0.1.0"), ("stable", "2.10.0", "99.0.0"), ("pre", "3.0.1", "99.0.0")])
def test_download_selects_latest_family_and_unconditionally_replaces(env, family, expected, installed):
    target = app(env["root"] / "Prowlarr.app", "same-version-installed")
    (target / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier":"com.osx.prowlarr.com","CFBundleExecutable":"Prowlarr","CFBundleShortVersionString":installed}))
    downloaded = app(env["root"] / "download-source.app", "downloaded-latest")
    stable = [_release("2.9.0", prerelease=False), _release("2.10.0", prerelease=False)]
    prereleases = [_release("3.0.1", prerelease=True)]
    metadata = _metadata(env, stable + prereleases)
    result = run(env, "--dl", family, str(target), extra={"METADATA_DIR": str(metadata), "ARCHIVE_CONTENT": "abc", "DOWNLOAD_APP": str(downloaded)})
    assert result.returncode == 0, result.stderr
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "downloaded-latest"
    assert expected in result.stdout
    assert (env["root"] / "Prowlarr.backup.zip").exists()


def test_release_enumeration_paginates_and_never_uses_core_tarball(env):
    target = env["root"] / "Prowlarr.app"
    downloaded = app(env["root"] / "download-source.app", "from-page-two")
    fillers = [_release(f"1.{i}.0", prerelease=False) for i in range(100)]
    page2 = [_release("9.0.0", prerelease=False)]
    metadata = _metadata(env, fillers, page2)
    result = run(env, "--dl", "stable", str(target), extra={"METADATA_DIR": str(metadata), "ARCHIVE_CONTENT": "abc", "DOWNLOAD_APP": str(downloaded)})
    assert result.returncode == 0, result.stderr
    assert "9.0.0" in result.stdout
    assert "n=100" not in result.stdout
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "from-page-two"
    assert "page=2" in env["log"].read_text()


def test_loaded_idle_agent_is_restored_after_actual_unload(env):
    target = app(env["root"] / "Prowlarr.app")
    plist = _agent(env, target, program_key="ProgramArguments")
    before = hashlib.sha256(plist.read_bytes()).hexdigest()
    state = env["root"] / "job-state"
    state.write_text("loaded")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true","JOB_STATE_FILE":str(state),"LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode == 0, result.stderr
    assert state.read_text() == "loaded", result.stdout + result.stderr
    assert hashlib.sha256(plist.read_bytes()).hexdigest() == before
    calls = env["log"].read_text()
    assert "launchctl bootout" in calls and "launchctl bootstrap" in calls
    assert f"Prowlarr patch: Unloading launch agent gui/{os.getuid()}/local.test.prowlarr" in result.stdout
    assert f"Prowlarr patch: Reloading launch agent gui/{os.getuid()}/local.test.prowlarr" in result.stdout


@pytest.mark.parametrize("failure", ["before", "after"])
def test_unload_error_preserves_agent_and_original(env, failure):
    target = app(env["root"] / "Prowlarr.app", "preserve-on-unload-error")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true","JOB_STATE_FILE":str(state),"LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr"),"FAIL_UNLOAD":failure})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "preserve-on-unload-error"
    assert state.read_text() == "loaded", result.stdout + result.stderr
    assert ("launchctl bootstrap" in env["log"].read_text()) == (failure == "after")
    assert ("Prowlarr patch: Reloading launch agent " in result.stdout) == (failure == "after")


def test_bootstrap_failure_after_install_does_not_roll_back_candidate(env):
    target = app(env["root"] / "Prowlarr.app", "old")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    downloaded = app(env["root"] / "download-source.app", "new")
    metadata = _metadata(env, [_release("2.10.0", prerelease=False)])
    result = run(env, "--dl", "stable", str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true","JOB_STATE_FILE":str(state),"LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr"),"METADATA_DIR":str(metadata),"ARCHIVE_CONTENT":"abc","DOWNLOAD_APP":str(downloaded),"FAIL_BOOTSTRAP":"1"})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "new"
    assert (env["root"] / "Prowlarr.backup.zip").exists()
    assert env["log"].read_text().count("launchctl bootstrap") == 1
    assert f"recoverable backup ZIP: {env['root'] / 'Prowlarr.backup.zip'}" in result.stdout
    assert "recoverable original bundle:" not in result.stdout


def test_wrong_asset_family_is_rejected_without_install(env):
    downloaded = app(env["root"] / "download-source.app", "must-not-install")
    release = _release("2.10.0", prerelease=False)
    release["assets"] = [{"name":"Prowlarr.Core.osx-core-x64.tar.gz","browser_download_url":"https://github.com/Prowlarr/Prowlarr/releases/download/2.10.0/core.tar.gz"}]
    metadata = _metadata(env, [release])
    target = env["root"] / "Prowlarr.app"
    result = run(env, "--dl", "stable", str(target), extra={"METADATA_DIR":str(metadata),"ARCHIVE_CONTENT":"abc","DOWNLOAD_APP":str(downloaded)})
    assert result.returncode != 0
    assert "exactly one full x64 app archive" in result.stderr
    assert not target.exists()


def test_download_digest_mismatch_preserves_existing_bundle(env):
    target = app(env["root"] / "Prowlarr.app", "keep-existing")
    downloaded = app(env["root"] / "download-source.app", "new")
    release = _release("2.10.0", prerelease=False)
    release["assets"][0]["digest"] = "sha256:" + "0" * 64
    metadata = _metadata(env, [release])
    result = run(env, "--dl", "stable", str(target), extra={"METADATA_DIR":str(metadata),"ARCHIVE_CONTENT":"abc","DOWNLOAD_APP":str(downloaded)})
    assert result.returncode != 0
    assert "SHA256 mismatch" in result.stderr
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "keep-existing"
    assert not (env["root"] / "Prowlarr.backup.zip").exists()


def test_loaded_job_with_unrelated_executable_is_refused(env):
    target = app(env["root"] / "Prowlarr.app")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true","JOB_STATE_FILE":str(state),"LOADED_EXEC":str(env["root"] / "unrelated/Prowlarr")})
    assert result.returncode != 0
    assert "binding differs" in result.stderr
    assert state.read_text() == "loaded"
    assert "launchctl bootout" not in env["log"].read_text()


def test_failed_second_bundle_rename_rolls_back_and_restores_loaded_job(env):
    target = app(env["root"] / "Prowlarr.app", "original-stays")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true","JOB_STATE_FILE":str(state),"LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr"),"FAIL_RENAME_AT":"2"})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original-stays"
    assert state.read_text() == "loaded"
    assert "launchctl bootstrap" in env["log"].read_text()


def test_signed_app_with_macos_12_minimum_is_patched(env):
    target = app(env["root"] / "Prowlarr.app")
    info = target / "Contents/Info.plist"
    data = plistlib.loads(info.read_bytes())
    data["LSMinimumSystemVersion"] = "11.0"
    data["LSMinimumSystemVersionByArchitecture"]["x86_64"] = "11.0"
    info.write_bytes(plistlib.dumps(data))
    (target / ".signed").touch()
    result = run(env, str(target), extra={"OTOOL_MIN":"12.0"})
    assert result.returncode == 0, result.stderr
    assert "no changes made" not in result.stdout
    assert (env["root"] / "Prowlarr.backup.zip").exists()


def test_unexpected_destination_preserved_and_backup_retained(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    result = run(env, str(target), extra={"FAIL_RENAME_AT":"2", "CREATE_UNEXPECTED":"1"})
    assert result.returncode != 0
    assert target.is_dir() and not (target / "Contents").exists()
    backups = list(env["root"].glob(".Prowlarr.app.txn.*/original/Prowlarr.app"))
    assert len(backups) == 1
    assert (backups[0] / "Contents/MacOS/Prowlarr").read_text() == "original"


def test_unknown_launchctl_error_blocks_replacement(env):
    target = app(env["root"] / "Prowlarr.app")
    _agent(env, target)
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true", "UNKNOWN_JOB_ERROR":"1"})
    assert result.returncode != 0
    assert "cannot determine LaunchAgent state" in result.stderr
    assert "launchctl bootout" not in env["log"].read_text()


def test_lock_contention_does_not_touch_bundle(env):
    target = app(env["root"] / "Prowlarr.app")
    (env["root"] / ".Prowlarr.app.prowlarr-lock").mkdir()
    result = run(env, str(target))
    assert result.returncode != 0
    assert "lock exists" in result.stderr
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "old"


def test_interrupt_between_renames_restores_original(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    result = run(env, str(target), extra={"INTERRUPT_RENAME_AT":"2"})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"
    assert not (env["root"] / ".Prowlarr.app.prowlarr-lock").exists()


@pytest.mark.parametrize("load_command", [
    "cmd LC_VERSION_MIN_MACOSX\nversion 12.0\nsdk 14.0",
    "cmd LC_BUILD_VERSION\nplatform 1\nminos 12.0\nsdk 14.0\nntools 2\ntool 3\nversion 1.0",
    "cmd LC_BUILD_VERSION\nplatform 2\nminos 12.0\nsdk 14.0\nntools 0",
    "cmd LC_BUILD_VERSION\nplatform 1\nminos 12.0\nsdk 14.0\nntools 0\nLoad command 2\ncmd LC_BUILD_VERSION\nplatform 1\nminos 12.0\nsdk 14.0\nntools 0",
])
def test_invalid_build_commands_are_refused_before_stop(env, load_command):
    target = app(env["root"] / "Prowlarr.app")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    fixture = env["root"] / "otool-output"
    fixture.write_text("Load command 1\n" + load_command + "\n")
    result = run(env, str(target), extra={"OTOOL_FIXTURE":str(fixture), "PROWLARR_MANAGE_LAUNCH_AGENT":"true", "JOB_STATE_FILE":str(state), "LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode != 0
    assert state.read_text() == "loaded"
    assert "launchctl bootout" not in env["log"].read_text()


def test_loaded_program_must_match_even_when_arguments_mention_target(env):
    target = app(env["root"] / "Prowlarr.app")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    exe = str(target / "Contents/MacOS/Prowlarr")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true", "JOB_STATE_FILE":str(state), "LOADED_EXEC":"/tmp/unrelated", "EXTRA_ARGUMENT":exe})
    assert result.returncode != 0
    assert "binding differs" in result.stderr
    assert state.read_text() == "loaded"


def test_mktemp_failure_releases_lock(env):
    mktemp = env["bin"] / "mktemp"
    mktemp.write_text("#!/bin/sh\nexit 1\n")
    mktemp.chmod(0o755)
    target = app(env["root"] / "Prowlarr.app")
    result = run(env, str(target))
    assert result.returncode != 0
    assert not (env["root"] / ".Prowlarr.app.prowlarr-lock").exists()
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "old"


def test_zero_build_tools_are_preserved(env):
    target = app(env["root"] / "Prowlarr.app")
    fixture = env["root"] / "otool-output"
    fixture.write_text("Load command 1\ncmd LC_BUILD_VERSION\nplatform 1\nminos 11.0\nsdk 14.0\nntools 0\n")
    result = run(env, str(target), extra={"OTOOL_FIXTURE": str(fixture)})
    assert result.returncode == 0, result.stderr
    vtool_call = next(line for line in env["log"].read_text().splitlines() if line.startswith("vtool "))
    assert " -tool " not in vtool_call


def test_default_download_family_is_stable(env):
    target = env["root"] / "Prowlarr.app"
    downloaded = app(env["root"] / "download-source.app", "stable-content")
    draft = _release("100.0.0", prerelease=False)
    draft["draft"] = True
    metadata = _metadata(env, [_release("2.10.0", prerelease=False), _release("99.0.0", prerelease=True), draft])
    result = run(env, "--dl", str(target), extra={"METADATA_DIR": str(metadata), "ARCHIVE_CONTENT": "abc", "DOWNLOAD_APP": str(downloaded)})
    assert result.returncode == 0, result.stderr
    assert "2.10.0 (stable)" in result.stdout
    assert "99.0.0" not in result.stdout
    assert "100.0.0" not in result.stdout


@pytest.mark.parametrize("family", ["stable", "pre"])
@pytest.mark.parametrize("loaded", [False, True])
def test_download_preserves_agent_state_and_custom_plist(env, family, loaded):
    target = app(env["root"] / "Prowlarr.app", "old")
    plist = _agent(env, target)
    custom = plist.with_name("MyProwlarr.plist")
    plist.rename(custom)
    before = custom.read_bytes()
    state = env["root"] / "job-state"
    state.write_text("loaded" if loaded else "unloaded")
    downloaded = app(env["root"] / "download-source.app", "new")
    metadata = _metadata(env, [_release("3.0.1", prerelease=(family == "pre"))])
    result = run(env, "--dl", family, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT": "true", "PROWLARR_LAUNCH_AGENT": "MyProwlarr.plist", "JOB_STATE_FILE": str(state), "LOADED_EXEC": str(target / "Contents/MacOS/Prowlarr"), "METADATA_DIR": str(metadata), "ARCHIVE_CONTENT": "abc", "DOWNLOAD_APP": str(downloaded)})
    assert result.returncode == 0, result.stderr
    assert state.read_text() == ("loaded" if loaded else "unloaded")
    assert custom.read_bytes() == before
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "new"
    calls = env["log"].read_text()
    assert ("launchctl bootout" in calls) == loaded
    assert ("launchctl bootstrap" in calls) == loaded
    if loaded:
        assert str(custom) in next(line for line in calls.splitlines() if "launchctl bootstrap" in line)
        assert f"Prowlarr patch: Unloading launch agent gui/{os.getuid()}/local.test.prowlarr" in result.stdout
        assert f"Prowlarr patch: Reloading launch agent gui/{os.getuid()}/local.test.prowlarr" in result.stdout
    else:
        assert "Prowlarr patch: Unloading launch agent " not in result.stdout
        assert "Prowlarr patch: Reloading launch agent " not in result.stdout


@pytest.mark.parametrize("signal_name", ["INT", "TERM"])
@pytest.mark.parametrize("rename_number", ["1", "2"])
def test_signal_after_successful_rename_restores_original_and_agent(env, rename_number, signal_name):
    target = app(env["root"] / "Prowlarr.app", "recover-after-signal")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    result = run(env, str(target), extra={"INTERRUPT_AFTER_RENAME_AT": rename_number, "INTERRUPT_SIGNAL": signal_name, "PROWLARR_MANAGE_LAUNCH_AGENT": "true", "JOB_STATE_FILE": str(state), "LOADED_EXEC": str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "recover-after-signal"
    assert state.read_text() == "loaded"
    assert not (env["root"] / ".Prowlarr.app.prowlarr-lock").exists()


def test_recovery_preserves_source_swapped_during_rename(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    result = run(env, str(target), extra={"FAIL_INSTALLED_VERIFY": "1", "SWAP_SOURCE_AT_RENAME": "3"})
    assert result.returncode != 0
    assert (target / "user-data").read_text() == "preserve this replacement"
    backups = list(env["root"].glob(".Prowlarr.app.txn.*/original/Prowlarr.app"))
    assert len(backups) == 1
    assert (backups[0] / "Contents/MacOS/Prowlarr").read_text() == "original"
    assert list(env["root"].glob(".Prowlarr.app.txn.*"))


@pytest.mark.parametrize("member", ["Contents/Info.plist", "Contents/MacOS/Prowlarr"])
def test_external_bundle_members_are_refused(env, member):
    target = app(env["root"] / "Prowlarr.app")
    original = target / member
    external = env["root"] / original.name
    original.rename(external)
    original.symlink_to(external)
    before = external.read_bytes()
    result = run(env, str(target))
    assert result.returncode != 0
    assert external.read_bytes() == before
    assert "codesign" not in (env["log"].read_text() if env["log"].exists() else "")


@pytest.mark.parametrize("phase", ["metadata", "archive"])
def test_transfer_failure_preserves_existing_app_and_loaded_agent(env, phase):
    target = app(env["root"] / "Prowlarr.app", "keep-existing")
    _agent(env, target)
    state = env["root"] / "job-state"
    state.write_text("loaded")
    downloaded = app(env["root"] / "download-source.app", "must-not-install")
    metadata = _metadata(env, [_release("2.10.0", prerelease=False)])
    result = run(env, "--dl", "stable", str(target), extra={"FAIL_CURL": phase, "METADATA_DIR": str(metadata), "ARCHIVE_CONTENT": "abc", "DOWNLOAD_APP": str(downloaded), "PROWLARR_MANAGE_LAUNCH_AGENT": "true", "JOB_STATE_FILE": str(state), "LOADED_EXEC": str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "keep-existing"
    assert state.read_text() == "loaded"
    assert "launchctl bootout" not in env["log"].read_text()
    assert not (env["root"] / "Prowlarr.backup.zip").exists()


def test_ambiguous_app_assets_are_refused(env):
    target = app(env["root"] / "Prowlarr.app", "keep-existing")
    release = _release("2.10.0", prerelease=False)
    release["assets"].append(release["assets"][0].copy())
    metadata = _metadata(env, [release])
    result = run(env, "--dl", "stable", str(target), extra={"METADATA_DIR": str(metadata)})
    assert result.returncode != 0
    assert "exactly one full x64 app archive" in result.stderr
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "keep-existing"


@pytest.mark.parametrize("args", [("--dl", "a.app", "b.app"), ("--dl", "stable", "a.app", "b.app"), ("--dl", "pre", "a.app", "b.app")])
def test_duplicate_destinations_rejected_before_side_effects(env, args):
    result = run(env, *args)
    assert result.returncode == 2
    assert not env["log"].exists()


def test_successive_runs_publish_one_zip_of_previous_app(env):
    target = app(env["root"] / "Prowlarr.app", "first")
    result = run(env, str(target))
    assert result.returncode == 0, result.stderr
    archive = env["root"] / "Prowlarr.backup.zip"
    with zipfile.ZipFile(archive) as z:
        assert z.read("Prowlarr.app/Contents/MacOS/Prowlarr") == b"first"
    (target / "Contents/MacOS/Prowlarr").write_text("second")
    result = run(env, str(target), extra={"OTOOL_MIN":"12"})
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(archive) as z:
        assert z.read("Prowlarr.app/Contents/MacOS/Prowlarr") == b"second"
    assert list(env["root"].glob("*.backup.zip")) == [archive]
    assert not list(env["root"].glob(".Prowlarr.app.txn.*"))


@pytest.mark.parametrize("failure", ["FAIL_BACKUP_CREATE", "FAIL_BACKUP_CHECK"])
def test_failed_backup_preserves_previous_zip_and_restores_app(env, failure):
    target = app(env["root"] / "Prowlarr.app", "original")
    archive = env["root"] / "Prowlarr.backup.zip"
    archive.write_bytes(b"old-archive")
    result = run(env, str(target), extra={failure:"1"})
    assert result.returncode != 0
    assert archive.read_bytes() == b"old-archive"
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"


@pytest.mark.parametrize("failure", [None, "FAIL_CURL", "FAIL_EXTRACT"])
def test_download_archive_publication_preserves_or_replaces_existing(env, failure):
    target = env["root"] / "Prowlarr.app"
    downloaded = app(env["root"] / "download-source.app", "new")
    metadata = _metadata(env, [_release("2.10.0", prerelease=False)])
    archive = env["home"] / "Downloads/Prowlarr.master.osx-app-core-x64.zip"
    archive.write_bytes(b"previous")
    extra = {"METADATA_DIR":str(metadata), "ARCHIVE_CONTENT":"abc", "DOWNLOAD_APP":str(downloaded)}
    if failure: extra[failure] = "archive" if failure == "FAIL_CURL" else "1"
    result = run(env, "--dl", str(target), extra=extra)
    assert (result.returncode == 0) == (failure is None), result.stderr
    assert archive.read_bytes() == (b"abc" if failure is None else b"previous")
    assert not list(archive.parent.glob(".prowlarr-download.*"))


@pytest.mark.parametrize("mutation", ["missing", "substitute"])
def test_missing_or_substituted_original_preserves_candidate_and_does_not_restart(env, mutation):
    target = app(env["root"] / "Prowlarr.app", "original")
    _agent(env, target)
    state = env["root"] / "job-state"; state.write_text("loaded")
    result = run(env, str(target), extra={"MUTATE_ORIGINAL":mutation, "PROWLARR_MANAGE_LAUNCH_AGENT":"true", "JOB_STATE_FILE":str(state), "LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode != 0
    assert (target / ".signed").exists()
    assert list(env["root"].glob(".Prowlarr.app.txn.*/original/Prowlarr.app.displaced"))
    assert state.read_text() == "unloaded"
    assert "launchctl bootstrap" not in env["log"].read_text()
    assert "recoverable original bundle:" not in result.stdout


def test_user_domain_restores_exact_agent(env):
    target = app(env["root"] / "Prowlarr.app")
    plist = _agent(env, target)
    state = env["root"] / "job-state"; state.write_text("loaded")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true", "JOB_STATE_FILE":str(state), "LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr"), "JOB_DOMAIN":"user"})
    assert result.returncode == 0, result.stderr
    calls = env["log"].read_text()
    assert f"launchctl bootout user/{os.getuid()}/local.test.prowlarr" in calls
    assert f"launchctl bootstrap user/{os.getuid()} {plist}" in calls
    assert f"Prowlarr patch: Unloading launch agent user/{os.getuid()}/local.test.prowlarr" in result.stdout
    assert f"Prowlarr patch: Reloading launch agent user/{os.getuid()}/local.test.prowlarr" in result.stdout


def test_interrupt_during_bootstrap_keeps_new_app_and_zip(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    _agent(env, target)
    state = env["root"] / "job-state"; state.write_text("loaded")
    result = run(env, str(target), extra={"PROWLARR_MANAGE_LAUNCH_AGENT":"true", "JOB_STATE_FILE":str(state), "LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr"), "INTERRUPT_BOOTSTRAP":"1"})
    assert result.returncode != 0
    assert (target / ".signed").exists()
    assert (env["root"] / "Prowlarr.backup.zip").exists()
    assert env["log"].read_text().count("launchctl bootstrap") == 1
    assert not list(env["root"].glob(".Prowlarr.app.txn.*"))
    assert f"recoverable backup ZIP: {env['root'] / 'Prowlarr.backup.zip'}" in result.stdout
    assert "recoverable original bundle:" not in result.stdout


def test_failed_backup_publication_keeps_old_zip_and_restores_original(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    archive = env["root"] / "Prowlarr.backup.zip"; archive.write_bytes(b"old")
    result = run(env, str(target), extra={"FAIL_PUBLISH_KIND":"backup"})
    assert result.returncode != 0
    assert archive.read_bytes() == b"old"
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"


def test_failed_download_publication_keeps_old_archive(env):
    target = env["root"] / "Prowlarr.app"
    downloaded = app(env["root"] / "download-source.app", "new")
    metadata = _metadata(env, [_release("2.10.0", prerelease=False)])
    archive = env["home"] / "Downloads/Prowlarr.master.osx-app-core-x64.zip"; archive.write_bytes(b"old")
    result = run(env, "--dl", str(target), extra={"METADATA_DIR":str(metadata), "ARCHIVE_CONTENT":"abc", "DOWNLOAD_APP":str(downloaded), "FAIL_PUBLISH_KIND":"download"})
    assert result.returncode != 0
    assert archive.read_bytes() == b"old"
    assert not target.exists()


@pytest.mark.parametrize("signal_name,rename_number", [("INT", "1"), ("INT", "2"), ("TERM", "1"), ("TERM", "2")])
def test_signal_before_bundle_renames_preserves_original(env, signal_name, rename_number):
    target = app(env["root"] / "Prowlarr.app", "original")
    result = run(env, str(target), extra={"INTERRUPT_RENAME_AT":rename_number, "INTERRUPT_SIGNAL":signal_name})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"
    assert not (env["root"] / ".Prowlarr.app.prowlarr-lock").exists()


def test_second_interrupt_during_recovery_is_ignored(env):
    target = app(env["root"] / "Prowlarr.app", "original")
    _agent(env, target)
    state = env["root"] / "job-state"; state.write_text("loaded")
    result = run(env, str(target), extra={"INTERRUPT_AFTER_RENAME_AT":"2", "INTERRUPT_SIGNAL":"INT", "SECOND_SIGNAL_AT":"3", "PROWLARR_MANAGE_LAUNCH_AGENT":"true", "JOB_STATE_FILE":str(state), "LOADED_EXEC":str(target / "Contents/MacOS/Prowlarr")})
    assert result.returncode != 0
    assert (target / "Contents/MacOS/Prowlarr").read_text() == "original"
    assert state.read_text() == "loaded"
    assert env["log"].read_text().count("launchctl bootstrap") == 1
