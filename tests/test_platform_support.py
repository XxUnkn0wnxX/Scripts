from pathlib import Path

from nord_ovpn_picker import build_ping_command, get_repo_venv_python_candidates, parse_ping_average


def test_get_repo_venv_python_candidates_for_posix() -> None:
    candidates = get_repo_venv_python_candidates(Path("/tmp/project/.venv"), platform="linux")

    assert candidates == [
        Path("/tmp/project/.venv/bin/python"),
        Path("/tmp/project/.venv/bin/python3"),
    ]


def test_get_repo_venv_python_candidates_for_windows() -> None:
    candidates = get_repo_venv_python_candidates(Path("C:/project/.venv"), platform="win32")

    assert candidates == [
        Path("C:/project/.venv/Scripts/python.exe"),
        Path("C:/project/.venv/Scripts/python"),
    ]


def test_build_ping_command_for_posix() -> None:
    assert build_ping_command("au666.nordvpn.com", 3, platform="darwin") == [
        "ping",
        "-c",
        "3",
        "-q",
        "au666.nordvpn.com",
    ]


def test_build_ping_command_for_windows() -> None:
    assert build_ping_command("au666.nordvpn.com", 3, platform="win32") == [
        "ping",
        "-n",
        "3",
        "au666.nordvpn.com",
    ]


def test_parse_ping_average_from_unix_summary() -> None:
    output = "--- au666.nordvpn.com ping statistics ---\nround-trip min/avg/max/stddev = 27.314/31.127/34.941/2.263 ms\n"

    assert parse_ping_average(output) == 31.127


def test_parse_ping_average_from_windows_summary() -> None:
    output = (
        "Ping statistics for 103.137.14.211:\n"
        "    Packets: Sent = 3, Received = 3, Lost = 0 (0% loss),\n"
        "Approximate round trip times in milli-seconds:\n"
        "    Minimum = 29ms, Maximum = 33ms, Average = 31ms\n"
    )

    assert parse_ping_average(output) == 31.0


def test_parse_ping_average_from_windows_reply_lines() -> None:
    output = (
        "Reply from 103.137.14.211: bytes=32 time=21ms TTL=54\n"
        "Reply from 103.137.14.211: bytes=32 time=23ms TTL=54\n"
    )

    assert parse_ping_average(output) == 22.0
