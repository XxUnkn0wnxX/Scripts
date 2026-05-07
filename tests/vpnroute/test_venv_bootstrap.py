from pathlib import Path

import pytest

import vpnroute
from vpnroute import (
    ensure_requirements_file_exists,
    ensure_repo_venv_or_reexec,
    get_repo_venv_python_candidates,
    normalize_platform_path,
    parse_args,
)


def test_get_repo_venv_python_candidates_for_windows() -> None:
    candidates = get_repo_venv_python_candidates(Path(".venv"), platform="win32")
    assert candidates == [Path(".venv/Scripts/python.exe"), Path(".venv/Scripts/python")]


def test_get_repo_venv_python_candidates_for_unix() -> None:
    candidates = get_repo_venv_python_candidates(Path(".venv"), platform="darwin")
    assert candidates == [Path(".venv/bin/python"), Path(".venv/bin/python3")]


def test_normalize_platform_path_returns_resolved_string(tmp_path: Path) -> None:
    assert normalize_platform_path(tmp_path) == str(tmp_path.resolve())


def test_ensure_requirements_file_exists_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(vpnroute, "REQUIREMENTS_PATH", Path("/missing/requirements.txt"))

    with pytest.raises(SystemExit) as excinfo:
        ensure_requirements_file_exists()

    captured = capsys.readouterr()
    assert excinfo.value.code == 1
    assert "Missing requirements.txt next to vpnroute.py." in captured.out


def test_ensure_repo_venv_or_reexec_raises_without_repo_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text("rich\n", encoding="utf-8")

    monkeypatch.setattr(vpnroute, "REQUIREMENTS_PATH", requirements_path)
    monkeypatch.setattr(vpnroute, "REPO_VENV_DIR", tmp_path / ".venv")
    monkeypatch.setattr(vpnroute, "resolve_repo_venv_python", lambda venv_dir: None)

    with pytest.raises(SystemExit) as excinfo:
        ensure_repo_venv_or_reexec([])

    captured = capsys.readouterr()
    assert excinfo.value.code == 1
    assert "No local .venv was found for vpnroute.py." in captured.out


def test_ensure_repo_venv_or_reexec_calls_execv_when_prefix_differs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text("rich\n", encoding="utf-8")
    venv_dir = tmp_path / ".venv"
    python_path = venv_dir / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(vpnroute, "REQUIREMENTS_PATH", requirements_path)
    monkeypatch.setattr(vpnroute, "REPO_VENV_DIR", venv_dir)
    monkeypatch.setattr(vpnroute, "SCRIPT_PATH", tmp_path / "vpnroute.py")
    monkeypatch.setattr(vpnroute, "resolve_repo_venv_python", lambda current_venv: python_path)
    monkeypatch.setattr(vpnroute.sys, "prefix", str(tmp_path / "outside"))
    monkeypatch.delenv(vpnroute.REEXEC_ENV, raising=False)

    captured: dict[str, list[str]] = {}

    def fake_execv(path: str, argv: list[str]) -> None:
        captured["path"] = [path]
        captured["argv"] = argv
        raise SystemExit(0)

    monkeypatch.setattr(vpnroute.os, "execv", fake_execv)

    with pytest.raises(SystemExit):
        ensure_repo_venv_or_reexec(["sites.txt"])

    assert captured["path"] == [str(python_path)]
    assert captured["argv"] == [str(python_path), str(tmp_path / "vpnroute.py"), "sites.txt"]


@pytest.mark.parametrize("flag", ["--no-comments", "--no-comment", "--nocom"])
def test_parse_args_accepts_no_comments_aliases(flag: str) -> None:
    parsed = parse_args([flag])
    assert parsed.no_comments is True
