from pathlib import Path

from nord_ovpn_picker import (
    build_ping_command,
    get_cache_dir,
    get_default_output_dir,
    get_repo_venv_python_candidates,
    parse_ping_average,
)


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


def test_get_cache_dir_for_macos() -> None:
    cache_dir = get_cache_dir(home=Path("/Users/tester"), platform="darwin", environ={})

    assert cache_dir == Path("/Users/tester/Library/Caches/nord-ovpn-picker")


def test_get_cache_dir_for_linux_uses_xdg_cache_home() -> None:
    cache_dir = get_cache_dir(
        home=Path("/home/tester"),
        platform="linux",
        environ={"XDG_CACHE_HOME": "/tmp/xdg-cache"},
    )

    assert cache_dir == Path("/tmp/xdg-cache/nord-ovpn-picker")


def test_get_cache_dir_for_linux_falls_back_to_dot_cache() -> None:
    cache_dir = get_cache_dir(home=Path("/home/tester"), platform="linux", environ={})

    assert cache_dir == Path("/home/tester/.cache/nord-ovpn-picker")


def test_get_cache_dir_for_windows_uses_localappdata() -> None:
    cache_dir = get_cache_dir(
        home=Path("C:/Users/tester"),
        platform="win32",
        environ={"LOCALAPPDATA": "C:/Users/tester/AppData/Local"},
    )

    assert cache_dir == Path("C:/Users/tester/AppData/Local/nord-ovpn-picker")


def test_get_cache_dir_for_windows_falls_back_to_home_local_appdata_path() -> None:
    cache_dir = get_cache_dir(home=Path("C:/Users/tester"), platform="win32", environ={})

    assert cache_dir == Path("C:/Users/tester/AppData/Local/nord-ovpn-picker")


def test_get_default_output_dir_uses_nordovpns_in_script_dir() -> None:
    script_dir = Path("/tmp/project")

    assert get_default_output_dir(cwd=script_dir, script_dir=script_dir) == script_dir.resolve() / "NordOVPNs"


def test_get_default_output_dir_uses_caller_directory_outside_script_dir() -> None:
    script_dir = Path("/tmp/project")
    caller_dir = Path("/tmp/elsewhere")

    assert get_default_output_dir(cwd=caller_dir, script_dir=script_dir) == caller_dir.resolve()
