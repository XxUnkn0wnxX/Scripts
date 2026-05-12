from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "yt-transcribe.py"

spec = importlib.util.spec_from_file_location("yt_transcribe_script", MODULE_PATH)
assert spec and spec.loader
yt_transcribe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = yt_transcribe
spec.loader.exec_module(yt_transcribe)


def test_screaming_stage_direction_is_stripped_without_keep_tags() -> None:
    assert yt_transcribe.is_stage_direction_tag("[screaming]")
    assert yt_transcribe.clean_caption_text("[screaming] hello there") == "hello there"


def test_screaming_stage_direction_is_preserved_with_keep_tags() -> None:
    assert yt_transcribe.clean_caption_text("[screaming] hello there", keep_tags=True) == "[screaming] hello there"


def test_dynamic_stage_direction_is_stripped_without_allowlist_entry() -> None:
    assert yt_transcribe.is_stage_direction_tag("[phone ringing]")
    assert yt_transcribe.clean_caption_text("[phone ringing] hello there") == "hello there"
    assert yt_transcribe.is_stage_direction_only_text("[phone ringing]")


def test_ambiguous_bracketed_text_is_left_in_place() -> None:
    assert not yt_transcribe.is_stage_direction_tag("[Chapter 3]")
    assert not yt_transcribe.is_stage_direction_tag("[I can't do this]")
    assert yt_transcribe.clean_caption_text("[Chapter 3] today we're covering setup") == (
        "[Chapter 3] today we're covering setup"
    )
