import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import nord_ovpn_picker as picker
from nord_ovpn_picker import (
    AuthCredentials,
    CandidateScore,
    CancelledError,
    CliError,
    NordServer,
    build_inline_auth_user_pass_block,
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


@pytest.mark.parametrize(
    ("factory_name", "prompt_action"),
    [
        (
            "autocomplete",
            lambda: picker.ask_autocomplete(
                "Country",
                [picker.AutocompleteOption("Australia", "AU", ())],
                lambda value: value,
            ),
        ),
        ("text", picker.interactive_limit_prompt),
        ("confirm", picker.interactive_ping_prompt),
        ("confirm", lambda: picker.maybe_warn_obfuscated("obfuscated", "udp", True)),
        ("text", lambda: picker.pick_interactive_selection([make_candidate("au001.nordvpn.com")])),
    ],
    ids=["autocomplete", "result-limit", "ping-confirmation", "obfuscated-confirmation", "selection"],
)
def test_questionary_prompt_cancellation_propagates(
    monkeypatch: pytest.MonkeyPatch,
    factory_name: str,
    prompt_action,
) -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        prompt_factory = getattr(picker.questionary, factory_name)

        def factory_with_test_io(*args, **kwargs):
            kwargs["input"] = pipe_input
            kwargs["output"] = DummyOutput()
            return prompt_factory(*args, **kwargs)

        monkeypatch.setattr(picker.questionary, factory_name, factory_with_test_io)

        with pytest.raises(KeyboardInterrupt):
            prompt_action()


@pytest.mark.parametrize(
    ("factory_name", "prompt_action", "expected"),
    [
        (
            "autocomplete",
            lambda: picker.interactive_city_prompt(
                picker.Country(id=13, name="Australia", code="AU"),
                [picker.City(id=1001, name="Melbourne", country_id=13), picker.City(id=1002, name="Sydney", country_id=13)],
            ),
            None,
        ),
        ("autocomplete", lambda: picker.interactive_protocol_prompt(["udp", "tcp"]), "udp"),
        ("autocomplete", lambda: picker.interactive_group_prompt(["standard", "p2p"]), "standard"),
        ("text", picker.interactive_limit_prompt, picker.DEFAULT_LIMIT),
        ("confirm", picker.interactive_ping_prompt, True),
    ],
    ids=["blank-city", "default-protocol", "default-group", "default-limit", "default-ping"],
)
def test_questionary_blank_input_and_defaults_still_work(
    monkeypatch: pytest.MonkeyPatch,
    factory_name: str,
    prompt_action,
    expected,
) -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        prompt_factory = getattr(picker.questionary, factory_name)

        def factory_with_test_io(*args, **kwargs):
            kwargs["input"] = pipe_input
            kwargs["output"] = DummyOutput()
            return prompt_factory(*args, **kwargs)

        monkeypatch.setattr(picker.questionary, factory_name, factory_with_test_io)

        assert prompt_action() == expected


def test_overwrite_prompt_cancellation_propagates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    candidate = make_candidate("au001.nordvpn.com")
    destination = tmp_path / picker.format_output_filename(candidate.server, candidate.protocol, candidate.group)
    destination.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        prompt_factory = picker.questionary.confirm

        def confirm_with_test_io(*args, **kwargs):
            kwargs["input"] = pipe_input
            kwargs["output"] = DummyOutput()
            return prompt_factory(*args, **kwargs)

        monkeypatch.setattr(picker.questionary, "confirm", confirm_with_test_io)

        with pytest.raises(KeyboardInterrupt):
            picker.download_candidate(
                client=None,  # type: ignore[arg-type]
                candidate=candidate,
                output_dir=tmp_path,
                force=False,
                dry_run=True,
            )

    assert destination.read_text(encoding="utf-8") == "existing"
    assert list(tmp_path.iterdir()) == [destination]


def test_city_prompt_cancellation_stops_filter_gathering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    args = picker.argparse.Namespace(
        country="Australia",
        city=None,
        protocol=None,
        group=None,
        limit=None,
        no_ping=False,
    )
    countries = [picker.Country(id=13, name="Australia", code="AU")]
    cities = [picker.City(id=1001, name="Melbourne", country_id=13), picker.City(id=1002, name="Sydney", country_id=13)]
    autocomplete_calls = 0

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x03")
        prompt_factory = picker.questionary.autocomplete

        def autocomplete_with_test_io(*prompt_args, **kwargs):
            nonlocal autocomplete_calls
            autocomplete_calls += 1
            if autocomplete_calls > 1:
                raise AssertionError("filter gathering continued after city cancellation")
            kwargs["input"] = pipe_input
            kwargs["output"] = DummyOutput()
            return prompt_factory(*prompt_args, **kwargs)

        monkeypatch.setattr(picker.questionary, "autocomplete", autocomplete_with_test_io)

        with pytest.raises(KeyboardInterrupt):
            picker.gather_filters(
                args,
                countries,
                {13: cities},
                prompt_protocol_keys=["udp", "tcp"],
                prompt_group_keys=["standard", "p2p"],
                allowed_protocol_keys=["udp", "tcp"],
                allowed_group_keys=["standard", "p2p"],
            )

    assert autocomplete_calls == 1


def test_main_keyboard_interrupt_exits_130_once_without_later_prompts(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("PTY-based prompt integration test requires a POSIX host")
    import pty

    home = tmp_path / "home"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["TERM"] = "dumb"
    cache_dir = picker.get_cache_dir(home=home, platform=sys.platform, environ=env)
    cache_dir.mkdir(parents=True)
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "v2_servers.json"
    (cache_dir / "v2_servers.json").write_bytes(fixture_path.read_bytes())

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        [
            sys.executable,
            str(picker.SCRIPT_PATH),
            "--country",
            "Australia",
            "--full-data",
            "--no-ping",
            "--dry-run",
            "--auth-username",
            "fixture-user",
            "--auth-password",
            "fixture-password",
        ],
        cwd=tmp_path,
        env=env,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)
    output = bytearray()
    sent_interrupt = False
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.1)
            if ready:
                try:
                    output.extend(os.read(master_fd, 4096))
                except OSError:
                    break
            if not sent_interrupt and b"City (blank for best country-wide recommendation)" in output:
                os.write(master_fd, b"\x03")
                sent_interrupt = True
            if process.poll() is not None and not ready:
                break
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        os.close(master_fd)

    rendered_output = output.decode("utf-8", errors="replace")
    assert sent_interrupt
    assert process.returncode == 130
    assert rendered_output.count("Cancelled by user") == 1
    assert "Protocol (blank" not in rendered_output
    assert "Server group (blank" not in rendered_output
    assert "Result limit" not in rendered_output
    assert "DRY RUN" not in rendered_output


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

    patched = patch_ovpn_auth_user_pass(original, AuthCredentials("demo-user", "demo-pass", "cli"))

    assert "<auth-user-pass>\ndemo-user\ndemo-pass\n</auth-user-pass>" in patched
    assert "auth-user-pass\n" not in patched


def test_patch_ovpn_auth_user_pass_replaces_existing_inline_block() -> None:
    original = "client\n<auth-user-pass>\nold-user\nold-pass\n</auth-user-pass>\nremote example 1194\n"

    patched = patch_ovpn_auth_user_pass(original, AuthCredentials("demo-user", "demo-pass", "cli"))

    assert "<auth-user-pass>\ndemo-user\ndemo-pass\n</auth-user-pass>" in patched
    assert "old-user" not in patched


def test_build_inline_auth_user_pass_block() -> None:
    assert (
        build_inline_auth_user_pass_block(AuthCredentials("demo-user", "demo-pass", "cli"))
        == "<auth-user-pass>\ndemo-user\ndemo-pass\n</auth-user-pass>"
    )


def test_download_candidate_inlines_auth_credentials_into_config(tmp_path: Path) -> None:
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

    assert destination.exists()
    contents = destination.read_text(encoding="utf-8")
    assert "<auth-user-pass>\ndemo-user\ndemo-pass\n</auth-user-pass>" in contents
    assert ".auth.txt" not in contents


def test_download_candidate_without_auth_leaves_config_unpatched(tmp_path: Path) -> None:
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
        auth_credentials=None,
    )

    contents = destination.read_text(encoding="utf-8")
    assert "auth-user-pass\n" in contents
    assert "<auth-user-pass>" not in contents


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


def test_download_candidate_does_not_leave_final_config_if_write_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    credentials = AuthCredentials("demo-user", "demo-pass", "cli")
    candidate = make_candidate("au001.nordvpn.com")

    class FakeClient:
        def get_text(self, url: str) -> str:
            return "client\nremote au001.nordvpn.com 1194\n<ca>\nCERT\n</ca>\n"

    monkeypatch.setattr(
        picker,
        "write_text_atomic",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("config write failed")),
    )

    with pytest.raises(RuntimeError, match="config write failed"):
        picker.download_candidate(
            client=FakeClient(),
            candidate=candidate,
            output_dir=tmp_path,
            force=False,
            dry_run=False,
            auth_credentials=credentials,
        )

    assert not (tmp_path / "Australia (AU) - Melbourne [UDP] [Standard] - au001.ovpn").exists()
