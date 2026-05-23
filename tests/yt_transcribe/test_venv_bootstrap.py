from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "python" / "yt-transcribe.py"

spec = importlib.util.spec_from_file_location("yt_transcribe_script_venv", MODULE_PATH)
assert spec and spec.loader
yt_transcribe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = yt_transcribe
spec.loader.exec_module(yt_transcribe)


def test_get_repo_venv_python_candidates_for_windows() -> None:
    candidates = yt_transcribe.get_repo_venv_python_candidates(Path(".venv"), platform="win32")
    assert candidates == [Path(".venv/Scripts/python.exe"), Path(".venv/Scripts/python")]


def test_get_repo_venv_python_candidates_for_unix() -> None:
    candidates = yt_transcribe.get_repo_venv_python_candidates(Path(".venv"), platform="darwin")
    assert candidates == [Path(".venv/bin/python"), Path(".venv/bin/python3")]


def test_normalize_platform_path_returns_resolved_string(tmp_path: Path) -> None:
    assert yt_transcribe.normalize_platform_path(tmp_path) == str(tmp_path.resolve())


def test_resolve_repo_root_uses_current_dir_when_markers_exist(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert yt_transcribe.resolve_repo_root(tmp_path) == tmp_path.resolve()


def test_ensure_requirements_file_exists_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(yt_transcribe, "REQUIREMENTS_PATH", Path("/missing/requirements.txt"))

    with pytest.raises(SystemExit) as excinfo:
        yt_transcribe.ensure_requirements_file_exists()

    captured = capsys.readouterr()
    assert excinfo.value.code == 1
    assert "Missing requirements.txt in the repo root for yt-transcribe.py." in captured.out
    assert "python -m pip install -r requirements.txt" in captured.out


def test_ensure_repo_venv_or_reexec_raises_without_repo_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text("python-docx\n", encoding="utf-8")

    monkeypatch.setattr(yt_transcribe, "REQUIREMENTS_PATH", requirements_path)
    monkeypatch.setattr(yt_transcribe, "REPO_VENV_DIR", tmp_path / ".venv")
    monkeypatch.setattr(yt_transcribe, "resolve_repo_venv_python", lambda venv_dir: None)

    with pytest.raises(SystemExit) as excinfo:
        yt_transcribe.ensure_repo_venv_or_reexec([])

    captured = capsys.readouterr()
    assert excinfo.value.code == 1
    assert "No local .venv was found for yt-transcribe.py." in captured.out


def test_ensure_repo_venv_or_reexec_calls_execv_when_prefix_differs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text("python-docx\n", encoding="utf-8")
    venv_dir = tmp_path / ".venv"
    python_path = venv_dir / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(yt_transcribe, "REQUIREMENTS_PATH", requirements_path)
    monkeypatch.setattr(yt_transcribe, "REPO_VENV_DIR", venv_dir)
    monkeypatch.setattr(yt_transcribe, "SCRIPT_PATH", tmp_path / "yt-transcribe.py")
    monkeypatch.setattr(yt_transcribe, "resolve_repo_venv_python", lambda current_venv: python_path)
    monkeypatch.setattr(yt_transcribe.sys, "prefix", str(tmp_path / "outside"))
    monkeypatch.delenv(yt_transcribe.REEXEC_ENV, raising=False)

    captured: dict[str, list[str]] = {}

    def fake_execv(path: str, argv: list[str]) -> None:
        captured["path"] = [path]
        captured["argv"] = argv
        raise SystemExit(0)

    monkeypatch.setattr(yt_transcribe.os, "execv", fake_execv)

    with pytest.raises(SystemExit):
        yt_transcribe.ensure_repo_venv_or_reexec(["--help"])

    assert captured["path"] == [str(python_path)]
    assert captured["argv"] == [str(python_path), str(tmp_path / "yt-transcribe.py"), "--help"]
