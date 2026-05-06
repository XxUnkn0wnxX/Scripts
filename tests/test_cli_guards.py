import signal
import subprocess
import sys
from pathlib import Path

import pytest

import nord_ovpn_picker as picker
from nord_ovpn_picker import (
    AuthCredentials,
    CandidateScore,
    CancelledError,
    CliError,
    NordServer,
    build_auth_file_contents,
    cleanup_atomic_temp_files,
    download_selected_candidates,
    handle_termination_signal,
    install_signal_handlers,
    load_auth_config,
    patch_ovpn_auth_user_pass,
    parse_args,
    ensure_repo_venv_or_reexec,
    resolve_auth_credentials,
    restore_signal_handlers,
    signal_display_name,
    write_text_atomic,
)


def make_candidate(hostname: str) -> CandidateScore:
    return CandidateScore(
        server=NordServer(
            hostname=hostname,
            name=hostname,
            load=10,
            station="127.0.0.1",
            country_name="Australia",
            country_code="AU",
            country_id=13,
            city_name="Melbourne",
            city_id=1001,
            group_identifiers=["legacy_standard"],
            technology_identifiers=["openvpn_udp"],
            status="online",
        ),
        protocol="udp",
        group="standard",
        average_ping_ms=20.0,
        score=40.0,
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--limit", "0"],
        ["--limit", "-1"],
        ["--download-top", "0"],
        ["--download-top", "-1"],
        ["--ping-count", "0"],
        ["--ping-count", "-1"],
    ],
)
def test_parse_args_rejects_non_positive_numeric_values(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_parse_args_rejects_conflicting_download_flags() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--download-best", "--download-top", "2"])


def test_download_selected_candidates_continues_after_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_download_candidate(**kwargs) -> Path:
        hostname = kwargs["candidate"].server.hostname
        calls.append(hostname)
        if hostname == "au001.nordvpn.com":
            raise CliError("first failed")
        return tmp_path / f"{hostname}.ovpn"

    monkeypatch.setattr(picker, "download_candidate", fake_download_candidate)

    downloaded, errors = download_selected_candidates(
        client=None,  # type: ignore[arg-type]
        candidates=[make_candidate("au001.nordvpn.com"), make_candidate("au002.nordvpn.com")],
        selected_indexes=[0, 1],
        output_dir=tmp_path,
        force=False,
        dry_run=True,
        auth_credentials=None,
    )

    assert calls == ["au001.nordvpn.com", "au002.nordvpn.com"]
    assert downloaded == [tmp_path / "au002.nordvpn.com.ovpn"]
    assert errors == ["first failed"]


def test_signal_display_name_uses_signal_name() -> None:
    assert signal_display_name(signal.SIGINT) == "SIGINT"


def test_handle_termination_signal_raises_cancelled_error() -> None:
    with pytest.raises(CancelledError, match="SIGTERM"):
        handle_termination_signal(signal.SIGTERM, None)


def test_install_and_restore_signal_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    original_targets = picker.signal_handler_targets
    monkeypatch.setattr(picker, "signal_handler_targets", lambda: [signal.SIGINT, signal.SIGTERM])

    current_handlers = {signal.SIGINT: "old-int", signal.SIGTERM: "old-term"}
    installed: list[tuple[int, object]] = []

    def fake_getsignal(signum: int) -> object:
        return current_handlers[signum]

    def fake_signal(signum: int, handler: object) -> None:
        installed.append((signum, handler))
        current_handlers[signum] = handler

    monkeypatch.setattr(signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(signal, "signal", fake_signal)

    previous = install_signal_handlers()

    assert previous == {signal.SIGINT: "old-int", signal.SIGTERM: "old-term"}
    assert current_handlers[signal.SIGINT] is handle_termination_signal
    assert current_handlers[signal.SIGTERM] is handle_termination_signal

    restore_signal_handlers(previous)

    assert current_handlers == {signal.SIGINT: "old-int", signal.SIGTERM: "old-term"}
    monkeypatch.setattr(picker, "signal_handler_targets", original_targets)


def test_write_text_atomic_cleans_temp_file_on_cancel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    destination = tmp_path / "sample.ovpn"

    def fake_replace(src: Path, dst: Path) -> None:
        raise CancelledError("Cancelled by SIGINT.")

    monkeypatch.setattr(picker.os, "replace", fake_replace)

    with pytest.raises(CancelledError):
        write_text_atomic(destination, "client\nremote example 1194\n<ca>\n", encoding="utf-8")

    assert not destination.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_sigkill_does_not_leave_partial_destination_and_stale_temp_can_be_cleaned(tmp_path: Path) -> None:
    destination = tmp_path / "sample.ovpn"
    script = """
import os
import sys
import tempfile
import time
from pathlib import Path

output_dir = Path(sys.argv[1])
destination = output_dir / "sample.ovpn"
fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=str(output_dir))
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write("partial payload")
    handle.flush()
    os.fsync(handle.fileno())
print(temp_name, flush=True)
time.sleep(30)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        temp_name = process.stdout.readline().strip()
        assert temp_name
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    temp_path = Path(temp_name)
    assert not destination.exists()
    assert temp_path.exists()
    assert cleanup_atomic_temp_files(tmp_path, destination.name) == 1
    assert not temp_path.exists()


def test_ensure_repo_venv_or_reexec_raises_for_help_without_repo_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(picker, "resolve_repo_venv_python", lambda venv_dir: None)
    monkeypatch.setattr(picker, "REPO_VENV_DIR", Path("/missing/.venv"))

    with pytest.raises(SystemExit, match="No local .venv"):
        ensure_repo_venv_or_reexec(["--help"])


def test_ensure_repo_venv_or_reexec_raises_without_repo_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(picker, "resolve_repo_venv_python", lambda venv_dir: None)
    monkeypatch.setattr(picker, "REPO_VENV_DIR", Path("/missing/.venv"))

    with pytest.raises(SystemExit, match="No local .venv"):
        ensure_repo_venv_or_reexec([])


def test_download_candidate_dry_run_does_not_create_output_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "NordOVPNs"

    destination = picker.download_candidate(
        client=None,  # type: ignore[arg-type]
        candidate=make_candidate("au001.nordvpn.com"),
        output_dir=output_dir,
        force=False,
        dry_run=True,
        auth_credentials=None,
    )

    assert destination == output_dir / "Australia (AU) - Melbourne [UDP] [Standard] - au001.ovpn"
    assert not output_dir.exists()


def test_resolve_auth_credentials_requires_both_cli_values() -> None:
    args = parse_args(["--auth-username", "user"])

    with pytest.raises(CliError, match="provided together"):
        resolve_auth_credentials(args)


def test_load_auth_config_reads_yaml_file(tmp_path: Path) -> None:
    auth_config = tmp_path / "nord_ovpn_auth.yaml"
    auth_config.write_text("user: demo-user\npass: demo-pass\n", encoding="utf-8")

    credentials = load_auth_config(auth_config)

    assert credentials == AuthCredentials("demo-user", "demo-pass", str(auth_config))


def test_resolve_auth_credentials_prefers_cli_over_auth_file(monkeypatch: pytest.MonkeyPatch) -> None:
    args = parse_args(["--auth-username", "cli-user", "--auth-password", "cli-pass"])
    monkeypatch.setattr(picker, "resolve_default_auth_config_path", lambda: Path("/ignored/nord_ovpn_auth.yaml"))

    credentials = resolve_auth_credentials(args)

    assert credentials == AuthCredentials("cli-user", "cli-pass", "cli")


def test_resolve_auth_credentials_uses_repo_auth_file_when_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth_config = tmp_path / "nord_ovpn_auth.yaml"
    auth_config.write_text("user: file-user\npass: file-pass\n", encoding="utf-8")
    args = parse_args([])
    monkeypatch.setattr(picker, "resolve_default_auth_config_path", lambda: auth_config)

    credentials = resolve_auth_credentials(args)

    assert credentials == AuthCredentials("file-user", "file-pass", str(auth_config))


def test_patch_ovpn_auth_user_pass_replaces_existing_directive() -> None:
    original = "client\nauth-user-pass\nremote example 1194\n"

    patched = patch_ovpn_auth_user_pass(original, "sample.auth.txt")

    assert "auth-user-pass sample.auth.txt" in patched
    assert "auth-user-pass\n" not in patched


def test_build_auth_file_contents() -> None:
    assert build_auth_file_contents(AuthCredentials("demo-user", "demo-pass", "cli")) == "demo-user\ndemo-pass\n"


def test_download_candidate_writes_auth_file_and_patches_config(tmp_path: Path) -> None:
    credentials = AuthCredentials("demo-user", "demo-pass", "cli")
    candidate = make_candidate("au001.nordvpn.com")

    class FakeClient:
        def get_text(self, url: str) -> str:
            return "client\nremote au001.nordvpn.com 1194\n<ca>\nCERT\n</ca>\nauth-user-pass\n"

    destination = picker.download_candidate(
        client=FakeClient(),
        candidate=candidate,
        output_dir=tmp_path,
        force=False,
        dry_run=False,
        auth_credentials=credentials,
    )

    auth_path = tmp_path / "australia_au_melbourne_udp_standard_au001.auth.txt"

    assert destination.exists()
    assert auth_path.exists()
    assert "auth-user-pass australia_au_melbourne_udp_standard_au001.auth.txt" in destination.read_text(
        encoding="utf-8"
    )
    assert auth_path.read_text(encoding="utf-8") == "demo-user\ndemo-pass\n"


def test_download_candidate_dry_run_with_auth_does_not_create_output_dir(tmp_path: Path) -> None:
    credentials = AuthCredentials("demo-user", "demo-pass", "cli")
    output_dir = tmp_path / "NordOVPNs"

    destination = picker.download_candidate(
        client=None,  # type: ignore[arg-type]
        candidate=make_candidate("au001.nordvpn.com"),
        output_dir=output_dir,
        force=False,
        dry_run=True,
        auth_credentials=credentials,
    )

    assert destination == output_dir / "Australia (AU) - Melbourne [UDP] [Standard] - au001.ovpn"
    assert not output_dir.exists()


def test_download_candidate_removes_generated_auth_file_if_config_write_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    credentials = AuthCredentials("demo-user", "demo-pass", "cli")
    candidate = make_candidate("au001.nordvpn.com")

    class FakeClient:
        def get_text(self, url: str) -> str:
            return "client\nremote au001.nordvpn.com 1194\n<ca>\nCERT\n</ca>\n"

    real_write_text_atomic = picker.write_text_atomic
    call_count = {"value": 0}

    def fake_write_text_atomic(destination: Path, text: str, encoding: str = "utf-8") -> None:
        call_count["value"] += 1
        if call_count["value"] == 1:
            real_write_text_atomic(destination, text, encoding=encoding)
            return
        raise RuntimeError("config write failed")

    monkeypatch.setattr(picker, "write_text_atomic", fake_write_text_atomic)

    with pytest.raises(RuntimeError, match="config write failed"):
        picker.download_candidate(
            client=FakeClient(),
            candidate=candidate,
            output_dir=tmp_path,
            force=False,
            dry_run=False,
            auth_credentials=credentials,
        )

    auth_path = tmp_path / "australia_au_melbourne_udp_standard_au001.auth.txt"
    assert not auth_path.exists()
