from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "python" / "yt-transcribe.py"

spec = importlib.util.spec_from_file_location("yt_transcribe_script_core", MODULE_PATH)
assert spec and spec.loader
yt_transcribe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = yt_transcribe
spec.loader.exec_module(yt_transcribe)


def test_configure_logging_uses_debug_level_when_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_basic_config(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(yt_transcribe.logging, "basicConfig", fake_basic_config)

    yt_transcribe.configure_logging(True)

    assert captured["level"] == yt_transcribe.logging.DEBUG
    assert captured["format"] == "%(message)s"


def test_expand_language_list_trims_and_drops_empty_values() -> None:
    assert yt_transcribe.expand_language_list(" en, ,en-US,fr ,, ") == ["en", "en-US", "fr"]
    assert yt_transcribe.expand_language_list("") == []


def test_normalize_url_adds_https_for_www_prefix() -> None:
    assert yt_transcribe.normalize_url("www.youtube.com/watch?v=dQw4w9WgXcQ") == (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert yt_transcribe.normalize_url("https://youtu.be/dQw4w9WgXcQ") == "https://youtu.be/dQw4w9WgXcQ"


@pytest.mark.parametrize(
    ("value", "expected_id"),
    [
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_supports_common_input_formats(value: str, expected_id: str) -> None:
    video_id, canonical_url = yt_transcribe.extract_video_id(value)

    assert video_id == expected_id
    assert canonical_url == f"https://www.youtube.com/watch?v={expected_id}"


@pytest.mark.parametrize("value", ["", "not-a-youtube-url", "https://youtu.be/short"])
def test_extract_video_id_rejects_invalid_input(value: str) -> None:
    with pytest.raises(yt_transcribe.CliError):
        yt_transcribe.extract_video_id(value)


def test_probe_ytdlp_respects_skip_flag() -> None:
    assert yt_transcribe.probe_ytdlp(skip_probe=True) is None


def test_probe_ytdlp_uses_path_lookup_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt_transcribe.shutil, "which", lambda name: "/custom/bin/yt-dlp" if name == "yt-dlp" else None)

    assert yt_transcribe.probe_ytdlp() == Path("/custom/bin/yt-dlp")


def test_probe_ytdlp_uses_fallback_locations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt_transcribe.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda self: str(self) == "/usr/local/bin/yt-dlp")
    monkeypatch.setattr(
        yt_transcribe.os,
        "access",
        lambda path, mode: str(path) == "/usr/local/bin/yt-dlp" and mode == yt_transcribe.os.X_OK,
    )

    assert yt_transcribe.probe_ytdlp() == Path("/usr/local/bin/yt-dlp")


def test_probe_ytdlp_returns_none_when_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yt_transcribe.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    monkeypatch.setattr(yt_transcribe.os, "access", lambda path, mode: False)

    assert yt_transcribe.probe_ytdlp() is None


def test_get_video_title_returns_first_nonempty_line(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(stdout="Picked title\nignored line\n", stderr="")
    monkeypatch.setattr(yt_transcribe.subprocess, "run", lambda *args, **kwargs: result)

    title = yt_transcribe.get_video_title(Path("/usr/local/bin/yt-dlp"), "https://example.com")

    assert title == "Picked title"


@pytest.mark.parametrize(
    "raised",
    [
        FileNotFoundError(),
        subprocess.TimeoutExpired(cmd=["yt-dlp"], timeout=30.0),
        subprocess.CalledProcessError(1, ["yt-dlp"], stderr="boom"),
    ],
)
def test_get_video_title_returns_none_for_subprocess_failures(
    monkeypatch: pytest.MonkeyPatch, raised: BaseException
) -> None:
    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        raise raised

    monkeypatch.setattr(yt_transcribe.subprocess, "run", fake_run)

    assert yt_transcribe.get_video_title(Path("/usr/local/bin/yt-dlp"), "https://example.com") is None


def test_get_video_title_returns_none_for_empty_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(stdout=" \n", stderr="")
    monkeypatch.setattr(yt_transcribe.subprocess, "run", lambda *args, **kwargs: result)

    assert yt_transcribe.get_video_title(Path("/usr/local/bin/yt-dlp"), "https://example.com") is None


def test_sanitize_filename_removes_invalid_characters_and_reserved_names() -> None:
    assert yt_transcribe.sanitize_filename("  Hello / world? 😄  ") == "Hello world"
    assert yt_transcribe.sanitize_filename("CON") == "CON_"


def test_sanitize_filename_truncates_to_200_characters() -> None:
    assert len(yt_transcribe.sanitize_filename("a" * 250)) == 200


def test_normalize_entries_accepts_dicts_and_objects() -> None:
    entries = yt_transcribe.normalize_entries(
        [
            {"text": "hello", "start": 1.0, "duration": 2.0},
            SimpleNamespace(text="world", start=3.0, duration=4.0),
        ]
    )

    assert entries == [
        {"text": "hello", "start": 1.0, "duration": 2.0},
        {"text": "world", "start": 3.0, "duration": 4.0},
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("59", 59), ("01:23", 83), ("01:02:03", 3723)],
)
def test_parse_timecode_accepts_valid_values(value: str, expected: int) -> None:
    assert yt_transcribe.parse_timecode(value) == expected


@pytest.mark.parametrize("value", ["", "aa:bb", "00:61", "00:00:61", "1:2:3:4"])
def test_parse_timecode_rejects_invalid_values(value: str) -> None:
    with pytest.raises(yt_transcribe.CliError):
        yt_transcribe.parse_timecode(value)


def test_parse_time_selection_supports_cutoff_and_range() -> None:
    cutoff = yt_transcribe.parse_time_selection("01:23")
    window = yt_transcribe.parse_time_selection("00:04:03 - 00:08:50")

    assert cutoff == yt_transcribe.TimeSelection(start_seconds=None, end_seconds=83)
    assert window == yt_transcribe.TimeSelection(start_seconds=243, end_seconds=530)


@pytest.mark.parametrize("value", ["", ["00:01", "00:02"], "00:09:00 - 00:08:50"])
def test_parse_time_selection_rejects_invalid_values(value: object) -> None:
    with pytest.raises(yt_transcribe.CliError):
        yt_transcribe.parse_time_selection(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("01:23", True), ("01:02:03", True), ("1:2", False), ("abc", False)],
)
def test_looks_like_timecode_matches_expected_shapes(value: str, expected: bool) -> None:
    assert yt_transcribe.looks_like_timecode(value) is expected


def test_normalize_time_argv_collapses_split_ranges_and_keeps_url() -> None:
    argv = ["--time", "00:04:03", "-", "00:08:50", "dQw4w9WgXcQ"]

    assert yt_transcribe.normalize_time_argv(argv) == ["--time", "00:04:03 - 00:08:50", "dQw4w9WgXcQ"]


def test_normalize_time_argv_rejects_missing_value() -> None:
    with pytest.raises(yt_transcribe.CliError):
        yt_transcribe.normalize_time_argv(["--time"])


def test_apply_time_selection_supports_cutoffs_and_ranges() -> None:
    transcript = yt_transcribe.TranscriptSelection(
        kind="manual",
        source_kind="manual",
        language="en",
        translated_to=None,
        entries=[
            {"text": "first", "start": 1.0, "duration": 1.0},
            {"text": "second", "start": 5.0, "duration": 1.0},
            {"text": "third", "start": 10.0, "duration": 1.0},
        ],
    )

    cutoff = yt_transcribe.apply_time_selection(transcript, yt_transcribe.TimeSelection(None, 5.0))
    window = yt_transcribe.apply_time_selection(transcript, yt_transcribe.TimeSelection(5.0, 10.0))

    assert [entry["text"] for entry in cutoff.entries] == ["first", "second"]
    assert [entry["text"] for entry in window.entries] == ["second", "third"]


def test_format_timestamp_handles_negative_and_hour_values() -> None:
    assert yt_transcribe.format_timestamp(-1) == "00:00"
    assert yt_transcribe.format_timestamp(83) == "01:23"
    assert yt_transcribe.format_timestamp(3723) == "01:02:03"


def test_parse_args_accepts_split_time_range_and_flags() -> None:
    parsed = yt_transcribe.parse_args(
        [
            "--docx",
            "--out",
            "tmp/output",
            "--nostamp",
            "--gencaps",
            "--lang",
            "en,ja",
            "--translate",
            "lt",
            "--keep-tags",
            "--no-yt-dlp",
            "-v",
            "--time",
            "00:04:03",
            "-",
            "00:08:50",
            "dQw4w9WgXcQ",
        ]
    )

    assert parsed.docx is True
    assert parsed.out == "tmp/output"
    assert parsed.nostamp is True
    assert parsed.gencaps is True
    assert parsed.lang == "en,ja"
    assert parsed.translate == "lt"
    assert parsed.keep_tags is True
    assert parsed.no_yt_dlp is True
    assert parsed.verbose is True
    assert parsed.time == "00:04:03 - 00:08:50"
    assert parsed.url_or_id == "dQw4w9WgXcQ"
