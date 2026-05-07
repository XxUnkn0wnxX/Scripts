import io
from pathlib import Path

from rich.console import Console

import vpnroute
from vpnroute import collect_interactive_lines, main


def test_collect_interactive_lines_stops_after_blank_line() -> None:
    responses = iter(["https://example.com/path", "ifconfig.me", ""])
    capture = io.StringIO()
    lines = collect_interactive_lines(input_func=lambda prompt="": next(responses), active_console=Console(file=capture))
    assert lines == ["https://example.com/path", "ifconfig.me"]


def test_collect_interactive_lines_exits_cleanly_on_first_blank_line() -> None:
    responses = iter([""])
    capture = io.StringIO()
    lines = collect_interactive_lines(input_func=lambda prompt="": next(responses), active_console=Console(file=capture))
    assert lines == []
    assert "No input provided." in capture.getvalue()


def test_collect_interactive_lines_handles_eof() -> None:
    def raise_eof(prompt: str = "") -> str:
        raise EOFError

    capture = io.StringIO()
    lines = collect_interactive_lines(input_func=raise_eof, active_console=Console(file=capture))
    assert lines == []


def test_main_applies_flags_in_interactive_mode(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "interactive-output"

    monkeypatch.setattr(vpnroute, "collect_interactive_lines", lambda: ["example.com"])
    monkeypatch.setattr(vpnroute, "build_resolver", lambda: object())
    monkeypatch.setattr(vpnroute, "resolve_ipv4_records", lambda domain, resolver=None: ["1.2.3.4"])

    exit_code = main(
        [
            "--netmask",
            "24",
            "--gateway",
            "vpn_gateway",
            "--metric",
            "7",
            "--nocom",
            "--verbose",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "route 1.2.3.4 255.255.255.0 vpn_gateway 7\n"
