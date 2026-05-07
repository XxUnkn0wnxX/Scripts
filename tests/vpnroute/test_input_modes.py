import io

from rich.console import Console

from vpnroute import collect_interactive_lines


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
