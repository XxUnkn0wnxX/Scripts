from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Callable

import pytest
from docx import Document


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "python" / "yt-transcribe.py"

spec = importlib.util.spec_from_file_location("yt_transcribe_script_fetch_main", MODULE_PATH)
assert spec and spec.loader
yt_transcribe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = yt_transcribe
spec.loader.exec_module(yt_transcribe)


class FakeTranscript:
    def __init__(
        self,
        language_code: str,
        entries: list[dict],
        *,
        translated: "FakeTranscript | None" = None,
        translate_error: BaseException | None = None,
        fetch_error: BaseException | None = None,
    ) -> None:
        self.language_code = language_code
        self._entries = entries
        self._translated = translated
        self._translate_error = translate_error
        self._fetch_error = fetch_error

    def fetch(self) -> list[dict]:
        if self._fetch_error is not None:
            raise self._fetch_error
        return self._entries

    def translate(self, target: str) -> "FakeTranscript":
        if self._translate_error is not None:
            raise self._translate_error
        if self._translated is None:
            raise RuntimeError(f"missing translated transcript for {target}")
        return self._translated


class FakeTranscriptList:
    def __init__(self, *, manual: FakeTranscript | None = None, generated: FakeTranscript | None = None) -> None:
        self.manual = manual
        self.generated = generated
        self.calls: list[tuple[str, list[str]]] = []

    def find_generated_transcript(self, languages: list[str]) -> FakeTranscript:
        self.calls.append(("generated", list(languages)))
        if self.generated is None:
            raise self._no_transcript_found("no generated transcript")
        return self.generated

    def find_manually_created_transcript(self, languages: list[str]) -> FakeTranscript:
        self.calls.append(("manual", list(languages)))
        if self.manual is None:
            raise self._no_transcript_found("no manual transcript")
        return self.manual

    _no_transcript_found: Callable[[str], BaseException]


def install_fake_youtube_transcript_api(
    monkeypatch: pytest.MonkeyPatch,
    build_queue: Callable[[types.SimpleNamespace], list[object]],
) -> tuple[types.SimpleNamespace, list[str]]:
    class FakeYouTubeTranscriptApiException(Exception):
        pass

    class FakeNoTranscriptFound(FakeYouTubeTranscriptApiException):
        pass

    class FakeNotTranslatable(FakeYouTubeTranscriptApiException):
        pass

    class FakeTranscriptsDisabled(FakeYouTubeTranscriptApiException):
        pass

    class FakeTranslationLanguageNotAvailable(FakeYouTubeTranscriptApiException):
        pass

    class FakeVideoUnavailable(FakeYouTubeTranscriptApiException):
        pass

    namespace = types.SimpleNamespace(
        NoTranscriptFound=FakeNoTranscriptFound,
        NotTranslatable=FakeNotTranslatable,
        TranscriptsDisabled=FakeTranscriptsDisabled,
        TranslationLanguageNotAvailable=FakeTranslationLanguageNotAvailable,
        VideoUnavailable=FakeVideoUnavailable,
        YouTubeTranscriptApiException=FakeYouTubeTranscriptApiException,
    )
    queue = list(build_queue(namespace))
    seen_video_ids: list[str] = []

    class FakeApi:
        def list(self, video_id: str) -> object:
            seen_video_ids.append(video_id)
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    namespace.YouTubeTranscriptApi = FakeApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", namespace)
    return namespace, seen_video_ids


def make_transcript_selection(entries: list[dict]) -> yt_transcribe.TranscriptSelection:
    return yt_transcribe.TranscriptSelection(
        kind="manual",
        source_kind="manual",
        language="en",
        translated_to=None,
        entries=entries,
    )


def test_fetch_transcript_prefers_manual_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    manual = FakeTranscript("en", [{"text": "manual", "start": 0.0, "duration": 1.0}])
    generated = FakeTranscript("en", [{"text": "generated", "start": 0.0, "duration": 1.0}])
    transcript_list = FakeTranscriptList(manual=manual, generated=generated)

    classes, seen_video_ids = install_fake_youtube_transcript_api(monkeypatch, lambda _: [transcript_list])
    transcript_list._no_transcript_found = classes.NoTranscriptFound

    result = yt_transcribe.fetch_transcript("dQw4w9WgXcQ", prefer_generated=False, languages=["en"], retries=0)

    assert seen_video_ids == ["dQw4w9WgXcQ"]
    assert transcript_list.calls[:1] == [("manual", ["en"])]
    assert result.kind == "manual"
    assert result.entries[0]["text"] == "manual"


def test_fetch_transcript_prefers_generated_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    generated = FakeTranscript("en", [{"text": "generated", "start": 0.0, "duration": 1.0}])
    transcript_list = FakeTranscriptList(manual=None, generated=generated)

    classes, _ = install_fake_youtube_transcript_api(monkeypatch, lambda _: [transcript_list])
    transcript_list._no_transcript_found = classes.NoTranscriptFound

    result = yt_transcribe.fetch_transcript("dQw4w9WgXcQ", prefer_generated=True, languages=["en"], retries=0)

    assert transcript_list.calls[:1] == [("generated", ["en"])]
    assert result.kind == "generated"
    assert result.entries[0]["text"] == "generated"


def test_fetch_transcript_retries_then_uses_translated_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    translated = FakeTranscript("lt", [{"text": "labas", "start": 0.0, "duration": 1.0}])
    manual = FakeTranscript(
        "en",
        [{"text": "hello", "start": 0.0, "duration": 1.0}],
        translated=translated,
    )
    transcript_list = FakeTranscriptList(manual=manual)

    classes, seen_video_ids = install_fake_youtube_transcript_api(
        monkeypatch,
        lambda ns: [ns.YouTubeTranscriptApiException("retry once"), transcript_list],
    )
    transcript_list._no_transcript_found = classes.NoTranscriptFound
    sleeps: list[float] = []
    monkeypatch.setattr(yt_transcribe.time, "sleep", lambda delay: sleeps.append(delay))

    result = yt_transcribe.fetch_transcript(
        "dQw4w9WgXcQ",
        prefer_generated=False,
        languages=["en"],
        translate_to="lt",
        retries=1,
    )

    assert seen_video_ids == ["dQw4w9WgXcQ", "dQw4w9WgXcQ"]
    assert sleeps == [1.5]
    assert result.kind == "translated"
    assert result.source_kind == "manual"
    assert result.language == "lt"
    assert result.translated_to == "lt"
    assert result.entries[0]["text"] == "labas"


def test_fetch_transcript_falls_back_when_translation_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    holder: dict[str, object] = {}

    def build_queue(namespace: types.SimpleNamespace) -> list[object]:
        manual = FakeTranscript(
            "en",
            [{"text": "hello", "start": 0.0, "duration": 1.0}],
            translate_error=namespace.NotTranslatable("unsupported"),
        )
        transcript_list = FakeTranscriptList(manual=manual)
        transcript_list._no_transcript_found = namespace.NoTranscriptFound
        holder["transcript_list"] = transcript_list
        return [transcript_list]

    install_fake_youtube_transcript_api(monkeypatch, build_queue)

    result = yt_transcribe.fetch_transcript(
        "dQw4w9WgXcQ",
        prefer_generated=False,
        languages=["en"],
        translate_to="lt",
        retries=0,
    )

    assert result.kind == "manual"
    assert result.translated_to is None
    assert result.entries[0]["text"] == "hello"


def test_fetch_transcript_surfaces_video_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    classes, _ = install_fake_youtube_transcript_api(monkeypatch, lambda ns: [ns.VideoUnavailable("gone")])

    with pytest.raises(yt_transcribe.CliError, match="unavailable"):
        yt_transcribe.fetch_transcript("dQw4w9WgXcQ", prefer_generated=False, languages=["en"], retries=0)

    assert classes.VideoUnavailable is not None


def test_fetch_transcript_rejects_missing_transcripts(monkeypatch: pytest.MonkeyPatch) -> None:
    transcript_list = FakeTranscriptList(manual=None, generated=None)
    classes, _ = install_fake_youtube_transcript_api(monkeypatch, lambda _: [transcript_list])
    transcript_list._no_transcript_found = classes.NoTranscriptFound

    with pytest.raises(yt_transcribe.CliError, match="No manual or auto captions"):
        yt_transcribe.fetch_transcript("dQw4w9WgXcQ", prefer_generated=False, languages=["en"], retries=0)


def test_write_txt_writes_expected_content(tmp_path: Path) -> None:
    transcript = make_transcript_selection(
        [
            {"text": "[music]", "start": 0.0, "duration": 1.0},
            {"text": ">> Hello there", "start": 5.0, "duration": 1.0},
            {"text": "[phone ringing] Stay calm", "start": 8.0, "duration": 1.0},
        ]
    )
    output_path = tmp_path / "transcript.txt"

    yt_transcribe.write_txt(
        output_path,
        transcript,
        "https://example.com/video",
        "Test Title",
        include_timestamps=True,
        keep_tags=False,
    )

    content = output_path.read_text(encoding="utf-8")
    assert "Title: Test Title" in content
    assert "Source: https://example.com/video" in content
    assert "[music]" not in content
    assert "00:05 - Hello there" in content
    assert "00:08 - Stay calm" in content


def test_write_docx_writes_a4_document(tmp_path: Path) -> None:
    transcript = make_transcript_selection(
        [
            {"text": "[music]", "start": 0.0, "duration": 1.0},
            {"text": "Narration line", "start": 5.0, "duration": 1.0},
        ]
    )
    output_path = tmp_path / "transcript.docx"

    yt_transcribe.write_docx(
        output_path,
        transcript,
        "https://example.com/video",
        "Doc Title",
        include_timestamps=False,
        keep_tags=True,
    )

    document = Document(str(output_path))
    section = document.sections[0]
    paragraphs = [paragraph.text for paragraph in document.paragraphs]

    assert round(section.page_width / 36000, 0) == 210
    assert round(section.page_height / 36000, 0) == 297
    assert paragraphs[0] == "Doc Title"
    assert "[music]" in paragraphs
    assert "Narration line" in paragraphs


def test_main_writes_txt_and_normalizes_output_suffix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(yt_transcribe, "probe_ytdlp", lambda skip_probe=False: None)
    monkeypatch.setattr(
        yt_transcribe,
        "fetch_transcript",
        lambda **kwargs: make_transcript_selection([{"text": "Hello there", "start": 1.0, "duration": 1.0}]),
    )

    exit_code = yt_transcribe.main(["--no-yt-dlp", "--out", "custom.output", "dQw4w9WgXcQ"])

    assert exit_code == 0
    assert (tmp_path / "custom.txt").exists()


def test_main_writes_docx_into_existing_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "exports"
    output_dir.mkdir()

    monkeypatch.setattr(yt_transcribe, "probe_ytdlp", lambda skip_probe=False: Path("/usr/local/bin/yt-dlp"))
    monkeypatch.setattr(yt_transcribe, "get_video_title", lambda *args, **kwargs: "Doc Title")
    monkeypatch.setattr(
        yt_transcribe,
        "fetch_transcript",
        lambda **kwargs: make_transcript_selection([{"text": "Hello there", "start": 1.0, "duration": 1.0}]),
    )

    exit_code = yt_transcribe.main(["--docx", "--out", str(output_dir), "dQw4w9WgXcQ"])

    assert exit_code == 0
    assert (output_dir / "Doc Title.docx").exists()


def test_main_applies_time_selection_when_requested(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    transcript = make_transcript_selection([{"text": "Hello there", "start": 1.0, "duration": 1.0}])
    captured: dict[str, object] = {}

    monkeypatch.setattr(yt_transcribe, "probe_ytdlp", lambda skip_probe=False: None)
    monkeypatch.setattr(yt_transcribe, "fetch_transcript", lambda **kwargs: transcript)
    monkeypatch.setattr(
        yt_transcribe,
        "parse_time_selection",
        lambda value: yt_transcribe.TimeSelection(start_seconds=1.0, end_seconds=2.0),
    )

    def fake_apply_time_selection(
        active_transcript: yt_transcribe.TranscriptSelection,
        selection: yt_transcribe.TimeSelection,
    ) -> yt_transcribe.TranscriptSelection:
        captured["selection"] = selection
        return active_transcript

    monkeypatch.setattr(yt_transcribe, "apply_time_selection", fake_apply_time_selection)

    exit_code = yt_transcribe.main(["--no-yt-dlp", "--time", "00:00:01 - 00:00:02", "dQw4w9WgXcQ"])

    assert exit_code == 0
    assert captured["selection"] == yt_transcribe.TimeSelection(start_seconds=1.0, end_seconds=2.0)


@pytest.mark.parametrize(
    ("raised", "expected_code"),
    [
        (yt_transcribe.CliError("boom"), 1),
        (KeyboardInterrupt(), 130),
        (RuntimeError("boom"), 1),
    ],
)
def test_main_returns_expected_codes_for_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raised: BaseException,
    expected_code: int,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(yt_transcribe, "probe_ytdlp", lambda skip_probe=False: None)

    def fake_fetch_transcript(**kwargs: object) -> yt_transcribe.TranscriptSelection:
        raise raised

    monkeypatch.setattr(yt_transcribe, "fetch_transcript", fake_fetch_transcript)

    assert yt_transcribe.main(["--no-yt-dlp", "dQw4w9WgXcQ"]) == expected_code
