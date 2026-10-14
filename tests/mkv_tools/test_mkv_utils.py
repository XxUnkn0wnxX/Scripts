from __future__ import annotations

import subprocess
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from _mkv_helpers import (
    _command_argv,
    _command_invocations,
    _read_command_log,
    _set_fake_fzf_responses,
    run_mkv_utils_script,
)


def _run_mkv_utils(
    env: dict[str, Path],
    *args: str,
    fzf_responses: list[list[str]] | None = None,
    input_data: str = "",
    extra_env: dict[str, str] | None = None,
):
    if fzf_responses is not None:
        _set_fake_fzf_responses(env, fzf_responses)
    return run_mkv_utils_script(
        env,
        *args,
        input_data=input_data,
        extra_env=extra_env,
    )


def _mkv_file(env: dict[str, Path], name: str) -> Path:
    path = env["workdir"] / name
    path.write_text("payload", encoding="utf-8")
    return path


def _ascii_box_contains(output: str, *required_rows: str) -> tuple[int, int, list[str]]:
    import unicodedata

    def display_width(value: str) -> int:
        return sum(0 if unicodedata.combining(char) else
                   2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
                   for char in value)

    lines = output.splitlines()
    borders = [
        index for index, line in enumerate(lines)
        if len(line) >= 3 and line.startswith("+") and line.endswith("+") and set(line) <= {"+", "-"}
    ]
    for first_index in borders:
        border = lines[first_index]
        for last_index in borders:
            if last_index <= first_index or lines[last_index] != border:
                continue
            interior = lines[first_index + 1:last_index]
            if any(line != border and (not line.startswith("|") or not line.endswith("|")) for line in interior):
                continue
            rows = [line[1:-1].strip() for line in interior if line != border]
            if all(required in rows for required in required_rows):
                border_width = display_width(border)
                assert all(display_width(line) == border_width for line in lines[first_index:last_index + 1])
                return first_index, last_index, rows
    raise AssertionError(f"no ASCII box contains rows: {required_rows!r}\n{output}")


def _indicator_frames(output: str, label: str) -> list[str]:
    import re

    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
    frames = []
    active = False
    for segment in clean.split("\r"):
        match = re.match(r"^  ([⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏])(?: (Analysing|Working))?(?:\^C)?$", segment)
        if match:
            if match.group(2):
                active = match.group(2) == label
            if active:
                frames.append(match.group(1))
        else:
            active = False
    return frames


def _analysis_spinner_frames(output: str) -> list[str]:
    return _indicator_frames(output, "Analysing")


def _assert_readable_outcomes(output: str, *expected_counts: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip().startswith("Outcomes:")]
    assert lines, output
    for line in lines:
        assert "{" not in line and "}" not in line, line
    matching = next((line for line in lines if all(value in line for value in expected_counts)), None)
    assert matching is not None, f"missing readable outcome counts {expected_counts!r}: {lines!r}"
    return matching


def test_mkv_utils_pure_track_planning_contract(tmp_path: Path):
    script_path = Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
    zsh_script = r'''
source "$1"
setopt errexit

fail() {
  print -u2 -r -- "contract failure: $1"
  return 1
}
expect_eq() {
  [[ "$1" == "$2" ]] || fail "$3 (expected '$2', got '$1')"
}
expect_reject() {
  local result=0 captured=""
  captured="$(mkvutil_expand_ids "$1" "$2")" || result=$?
  (( result != 0 )) || fail "accepted invalid selection '$1'"
  [[ -z "$captured" ]] || fail "printed partial output for '$1': $captured"
}
expect_layout_reject() {
  local result=0
  mkvutil_plan_layout "$1" "$2" "$3" "$4" || result=$?
  (( result != 0 )) || fail "accepted invalid layout"
  (( ${#MKVUTIL_INPUT_IDS} == 0 && ${#MKVUTIL_RETAINED_IDS} == 0 )) || fail "stale IDs remained after failure"
  (( ${#MKVUTIL_TRACK_TYPES} == 0 && ${#MKVUTIL_PROPEDIT_SELECTORS} == 0 )) || fail "stale maps remained after failure"
  [[ -z "$MKVUTIL_TRACK_ORDER" && -z "$MKVUTIL_OUTPUT_EXTENSION" ]] || fail "stale scalar state remained after failure"
}

expect_eq "$(mkvutil_expand_ids ' 12, 011-012, 0, 11 ' '0,11,12')" "12,11,0" "range/dedup/order"
expect_eq "$(mkvutil_expand_ids '9-12' '12,9,11,10')" "9,10,11,12" "numeric range order"
expect_eq "$(mkvutil_expand_ids '00011' '11')" "11" "leading zero normalization"
expect_eq "$(mkvutil_expand_ids ' 1 - 2 , 0 ' '0,1,2')" "1,2,0" "whitespace around delimiters"
expect_reject '' '0,1'
expect_reject '1,,2' '1,2'
expect_reject '1 2' '0,1,2,12'
expect_reject '3-1' '1,2,3'
expect_reject '0-3' '0,2,3'
expect_reject '0-999999999999999999999999999999999999' '0,999999999999999999999999999999999999'
expect_reject '13' '0,11,12'
expect_reject '1-x' '1,2'

rows=$'video\t0\naudio\t11\nsubtitles\t12'
mkvutil_plan_layout "$rows" '' '' '.mkv' || fail 'default layout rejected'
expect_eq "${(j:,:)MKVUTIL_INPUT_IDS}" '0,11,12' 'original IDs'
expect_eq "${(j:,:)MKVUTIL_RETAINED_IDS}" '0,11,12' 'default retained IDs'
expect_eq "${MKVUTIL_TRACK_TYPES[11]}" 'audio' 'track type lookup'
expect_eq "${MKVUTIL_PROPEDIT_SELECTORS[0]}" 'track:1' 'first listing selector'
expect_eq "${MKVUTIL_PROPEDIT_SELECTORS[11]}" 'track:2' 'second listing selector'
expect_eq "${MKVUTIL_PROPEDIT_SELECTORS[12]}" 'track:3' 'third listing selector'
expect_eq "$MKVUTIL_TRACK_ORDER" '0:0,0:11,0:12' 'complete default order'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mkv' 'default extension'

mkvutil_plan_layout "$rows" '' ' 0 : 12 , 0:0 ' 'mka' || fail 'partial explicit order rejected'
expect_eq "$MKVUTIL_TRACK_ORDER" '0:12,0:0,0:11' 'partial order completion'
expect_eq "${(j:,:)MKVUTIL_RETAINED_IDS}" '12,0,11' 'retained IDs in output order'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mka' 'unchanged no-removal extension'
for extension in mkv mka mks mk3d; do
  mkvutil_plan_layout "$rows" '' '' "$extension" || fail "extension $extension rejected"
  expect_eq "$MKVUTIL_OUTPUT_EXTENSION" "$extension" "preserve .$extension"
done

mkvutil_plan_layout "$rows" '0' '' 'mka' || fail 'video removal layout rejected'
expect_eq "${(j:,:)MKVUTIL_RETAINED_IDS}" '11,12' 'removal result'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mka' 'audio and subtitle removal naming'
mkvutil_plan_layout "$rows" '11-12' '' 'mkv' || fail 'audio/subtitle removal layout rejected'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mkv' 'video naming after removal'
mkvutil_plan_layout "$rows" '11-12' '' 'mk3d' || fail '3D removal layout rejected'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mk3d' '3D naming after removal'
mkvutil_plan_layout $'audio\t11\nsubtitles\t12' '12' '' 'mkv' || fail 'audio-only result rejected'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mka' 'audio naming after removal'
mkvutil_plan_layout $'subtitles\t12' '' '' 'mkv' || fail 'subtitle-only layout rejected'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mkv' 'subtitle extension without removal'
mkvutil_plan_layout $'subtitles\t12\nsubtitles\t13' '12' '' 'mkv' || fail 'subtitle-only removal layout rejected'
expect_eq "$MKVUTIL_OUTPUT_EXTENSION" 'mks' 'subtitle naming after removal'

expect_layout_reject '' '' '' 'mkv'
expect_layout_reject $'video\t0\nmetadata\t1' '' '' 'mkv'
expect_layout_reject $'video\t0\naudio\t00' '' '' 'mkv'
expect_layout_reject "$rows" '0,11,12' '' 'mkv'
expect_layout_reject "$rows" '' '0:11,0:11' 'mkv'
expect_layout_reject "$rows" '' '1:11' 'mkv'
expect_layout_reject "$rows" '11' '0:11' 'mkv'
expect_layout_reject "$rows" '' '0:99' 'mkv'
expect_layout_reject "$rows" '' '0:1 2' 'mkv'
expect_layout_reject "$rows" '' '' 'avi'

# Repeated calls must neither leak declarations nor expose prior success state.
mkvutil_plan_layout "$rows" '' '' 'mkv' || fail 'repeat success rejected'
expect_layout_reject "$rows" '0,11,12' '' 'mkv'
expect_eq "$(mkvutil_expand_ids '11,12' '0,11,12')" '11,12' 'repeat helper call'
print -r -- 'pure track-planning contracts passed'
'''
    result = subprocess.run(
        [
            "/usr/local/bin/zsh",
            "-f",
            "-c",
            zsh_script,
            "mkvutil-contract-test",
            str(script_path),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "pure track-planning contracts passed"


def _run_metadata_contract(tmp_path: Path, body: str, input_data: str = "", *, binary_output=False):
    script_path = Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
    result = subprocess.run(
        [
            "/usr/local/bin/zsh", "-f", "-c",
            r'''
source "$1"
setopt errexit
fail() { print -u2 -r -- "metadata contract failure: $1"; return 1; }
eq() { [[ "$1" == "$2" ]] || fail "$3: expected '$2', got '$1'"; }
reject() { if "$@"; then fail "accepted invalid call: $*"; fi; }
''' + body,
            "metadata-contract-test", str(script_path),
        ],
        cwd=tmp_path,
        input=input_data.encode() if binary_output else input_data,
        text=not binary_output,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_mkv_utils_track_listing_removal_colour_is_terminal_only(tmp_path: Path):
    import pty
    import select

    script_path = Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True),
                          (4, "audio", "A_AAC", False),
                          (12, "subtitles", "S_TEXT/ASS", False)])
    render_script = r'''source "$1"
display_track_info fixture.mkv "$2" "$3" "${4-}" "${5:-source}"
'''
    args = [
        "/usr/local/bin/zsh", "-f", "-c", render_script, "track-render-test",
        str(script_path), json.dumps(model), "4",
    ]

    def render_terminal(extra_env: dict[str, str] | None = None, *, final_ids: str | None = None) -> str:
        terminal_env = os.environ.copy()
        terminal_env.update({"TERM": "xterm-256color"})
        terminal_env.pop("NO_COLOR", None)
        terminal_env.update(extra_env or {})
        master, slave = pty.openpty()
        try:
            command = args if final_ids is None else [*args, final_ids, "output"]
            result = subprocess.run(command, cwd=tmp_path, env=terminal_env,
                                    stdin=subprocess.DEVNULL, stdout=slave,
                                    stderr=subprocess.PIPE, timeout=5, check=False)
            assert result.returncode == 0, result.stderr.decode(errors="replace")
            # macOS discards unread PTY output when the last slave closes.
            assert select.select([master], [], [], 1)[0], "renderer produced no terminal output"
            return os.read(master, 8192).decode()
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)

    coloured = render_terminal()
    selected = "Track: audio (A_AAC) [Original 4] [eng]"
    unselected = "Track ID 12: subtitles (S_TEXT/ASS) [Original 12] [eng]"
    assert f"\x1b[38;5;203m{selected}\x1b[0m" in coloured
    assert "\x1b[38;5;203mTrack ID 12:" not in coloured
    assert "Track ID 0: video (V_MPEG4/ISO/AVC) [Original 0] [eng]" in coloured
    assert unselected in coloured
    assert coloured.count("\x1b[") == 2
    final = render_terminal(final_ids="0,12")
    assert f"\x1b[38;5;203m{selected}\x1b[0m" in final
    assert "\x1b[38;5;220mTrack ID 1: subtitles (S_TEXT/ASS) [Original 12] [eng]\x1b[0m" in final
    assert "\x1b[38;5;220mTrack ID 0:" not in final
    fallback = render_terminal({"TERM": "xterm"}, final_ids="0,12")
    assert f"\x1b[91m{selected}\x1b[0m" in fallback
    assert "\x1b[33mTrack ID 1:" in fallback
    assert "Track ID 4:" not in final and "Track ID 12:" not in final
    assert "Removed" not in coloured
    assert "\x1b[" not in render_terminal({"NO_COLOR": "1"})
    assert "\x1b[" not in render_terminal({"TERM": "dumb"})
    redirected_env = os.environ.copy()
    redirected_env.update(TERM="xterm-256color")
    redirected_env.pop("NO_COLOR", None)
    redirected = subprocess.run(args, cwd=tmp_path, env=redirected_env,
                                capture_output=True, text=True, timeout=5, check=False)
    assert redirected.returncode == 0, redirected.stderr
    assert selected in redirected.stdout and unselected in redirected.stdout
    assert "\x1b[" not in redirected.stdout


def test_mkv_utils_combined_removal_refreshes_original_track_listing_before_order(env):
    source = _mkv_file(env, "refresh.mkv")
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True),
                          (3, "subtitles", "S_TEXT/ASS", False),
                          (4, "audio", "A_AAC", True),
                          (11, "audio", "A_OPUS", False),
                          (12, "audio", "A_AAC", True)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/refresh.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_batch_request mux 2,1
functions[original_read]="${functions[_mkvutil_read]}"
_mkvutil_read() {
  case "$1" in
    'Remove IDs: '*) print -r -- '<REMOVE PROMPT>' ;;
    'Track order: '*) print -r -- '<ORDER PROMPT>' ;;
  esac
  original_read "$@"
}
mkvutil_configure_category mux 2,1 <<< $'12\n12,0\n0,4,3\n3\nen\nfr-CA\nde'
eq "$(jq -r '.removed_ids|join(",")' <<< "$MKVUTIL_CONFIG")" 12 'removal collected first'
eq "$(jq -r '.order_ids|join(",")' <<< "$MKVUTIL_CONFIG")" 0,4,3 'removed ID rejected from order'
eq "$(jq -r '.settings["3:0"]' <<< "$MKVUTIL_CONFIG")" en 'first retained metadata target'
eq "$(jq -r '.settings["3:4"]' <<< "$MKVUTIL_CONFIG")" fr-CA 'second retained metadata target'
eq "$(jq -r '.settings["3:3"]' <<< "$MKVUTIL_CONFIG")" de 'third retained metadata target'
print -r -- 'combined refresh contracts passed'
''', {str(source): model})
    first_track = result.stdout.index("Track ID 12:")
    remove_prompt = result.stdout.index("<REMOVE PROMPT>")
    refreshed_track = result.stdout.index("Track: audio (A_AAC) [Original 12]", first_track + 1)
    order_prompt = result.stdout.index("<ORDER PROMPT>")
    assert first_track < remove_prompt < refreshed_track < order_prompt
    assert result.stdout.count("Track ID 12:") == 1  # Dropped IDs cannot be selected after removal.
    assert 'Track ID 1: audio (A_AAC) [Original 4] [eng]' in result.stderr
    assert 'Track ID 2: subtitles (S_TEXT/ASS) [Original 3] [eng]' in result.stderr
    assert "Track ID 4: audio (A_AAC) [Original 4] [eng]" in result.stdout
    assert "Track ID 11: audio (A_OPUS) [Original 11] [eng]" in result.stdout
    assert "Invalid order. Available: 0,3,4,11" in result.stderr
    assert len(_command_argv(env, "mkvmerge")) == 1
    assert _command_argv(env, "mkvmerge")[0][0] == "-J"


def test_mkv_utils_removal_only_metadata_maps_output_ids_to_retained_sources(env):
    source = _mkv_file(env, "removal metadata.mkv")
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True),
                          (3, "subtitles", "S_TEXT/ASS", False),
                          (4, "audio", "A_AAC", True),
                          (11, "audio", "A_OPUS", False),
                          (12, "audio", "A_AAC", True)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/removal metadata.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_configure_category mux 1 <<< $'12\n3,4\n2,1\nfr-CA\nde\n3\nCommentary'
eq "$(jq -r '.removed_ids|join(",")' <<< "$MKVUTIL_CONFIG")" 12 'removal retained'
eq "$(jq -r '.order' <<< "$MKVUTIL_CONFIG")" '' 'removal-only has no requested reorder'
jq -e '.settings=={"3:3":"de","3:4":"fr-CA","4:11":"Commentary"}' <<< "$MKVUTIL_CONFIG" >/dev/null
job="$(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG")"
jq -e '.retained_ids==["0","3","4","11"] and
  (.merge_metadata_args|index("4:fr-CA"))!=null and
  (.merge_metadata_args|index("3:de"))!=null and
  (.merge_metadata_args|index("11:Commentary"))!=null' <<< "$job" >/dev/null
print -r -- 'removal-only metadata contracts passed'
''', {str(source): model})
    assert result.stdout.rstrip().endswith("removal-only metadata contracts passed")
    assert result.stdout.count("mkvmerge JSON track listing") == 1
    assert 'Output track layout' in result.stdout
    assert 'Track ID 2: audio (A_AAC) [Original 4] [eng]' in result.stderr
    assert 'Track ID 1: subtitles (S_TEXT/ASS) [Original 3] [eng]' in result.stderr
    assert 'Track ID 3: audio (A_OPUS) [Original 11] [eng]' in result.stderr
    assert "Track order:" not in result.stdout + result.stderr
    assert result.stderr.count("Track IDs:") == 2
    assert source.read_bytes() == b"payload"


def test_mkv_utils_mux_preview_yellow_requires_reorder(env):
    source = _mkv_file(env, "preview colours.mkv")
    model = _source_json([(0, "video", "V_VP9", True),
                          (1, "audio", "A_AAC", False),
                          (2, "subtitles", "S_TEXT/ASS", False),
                          (3, "audio", "A_OPUS", False)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/preview colours.mkv")"
MKVUTIL_SOURCES=("$record")
red=$'\e[38;5;203m'; yellow=$'\e[38;5;220m'
_mkvutil_track_colours() { MKVUTIL_TRACK_RED="$red"; MKVUTIL_TRACK_YELLOW="$yellow"; }
_mkvutil_menu_read() { preview="$6"; REPLY=''; }
mkvutil_configure_category mux 1 <<< 1
[[ "$preview" != *"$yellow"* ]] || fail 'removal-only tracks must not be yellow'
[[ "$preview" == *"${red}Track: audio (A_AAC) [Original 1] [eng]"* ]] || fail 'dropped track stays red'
[[ "$preview" == *'Track ID 1: subtitles (S_TEXT/ASS) [Original 2] [eng]'* ]] || fail 'removal-only output IDs remain projected'
jq -e '.removed_ids==["1"] and .order==""' <<< "$MKVUTIL_CONFIG" >/dev/null
mkvutil_configure_category mux 2 <<< '2,0'
[[ "$preview" == *"${yellow}Track ID 0: subtitles (S_TEXT/ASS) [Original 2] [eng]"* ]] || fail 'reorder-only changes stay yellow'
[[ "$preview" == *"${yellow}Track ID 1: video (V_VP9) [Original 0] [eng]"* ]] || fail 'explicit video move stays yellow'
[[ "$preview" == *$'\nTrack ID 2: audio (A_AAC) [Original 1] [eng]'* ]] || fail 'automatically appended track stays normal'
mkvutil_configure_category mux 1,2 <<< $'1\n2,0'
[[ "$preview" == *"${yellow}Track ID 0: subtitles (S_TEXT/ASS) [Original 2] [eng]"* ]] || fail 'combined changes stay yellow'
[[ "$preview" == *"${red}Track: audio (A_AAC) [Original 1] [eng]"* ]] || fail 'combined dropped track stays red'
[[ "$preview" == *$'\nTrack ID 2: audio (A_OPUS) [Original 3] [eng]'* ]] || fail 'combined automatic adjustment stays normal'
mkvutil_configure_category mux 2 <<< ' 03 , 2 '
[[ "$preview" == *"${yellow}Track ID 1: audio (A_OPUS) [Original 3] [eng]"* ]] || fail 'canonical explicit ID stays yellow'
[[ "$preview" == *$'\nTrack ID 0: video (V_VP9) [Original 0] [eng]'* ]] || fail 'automatically prepended zero stays normal'
[[ "$preview" == *$'\nTrack ID 2: subtitles (S_TEXT/ASS) [Original 2] [eng]'* ]] || fail 'explicit track that stays in position remains normal'
[[ "$preview" == *$'\nTrack ID 3: audio (A_AAC) [Original 1] [eng]'* ]] || fail 'implicit appended track stays normal'
jq -e '.order=="0:0,0:3,0:2" and .order_ids==["0","3","2"]' <<< "$MKVUTIL_CONFIG" >/dev/null
print -r -- 'preview colour modes passed'
''', {str(source): model})
    assert result.stdout.rstrip().endswith("preview colour modes passed")
    assert source.read_bytes() == b"payload"
    assert not [call for call in _command_argv(env, "mkvmerge") if "-o" in call]


@pytest.mark.parametrize('dry_run', (0, 1), ids=('normal', 'dry-run'))
def test_mkv_utils_mux_metadata_context_retains_preview_colours(env, dry_run):
    source = _mkv_file(env, "styled metadata.mkv")
    model = _source_json([(0, "video", "V_VP9", True),
                          (1, "audio", "A_AAC", False),
                          (2, "subtitles", "S_TEXT/ASS", False),
                          (3, "audio", "A_OPUS", False)])
    result = _run_planning_contract(env, r'''
MKVUTIL_DRY_RUN="$TEST_DRY_RUN"
record="$(mkvutil_capture_source "$PWD/styled metadata.mkv")"
MKVUTIL_SOURCES=("$record")
yellow=$'\e[38;5;220m'; red=$'\e[38;5;203m'; reset=$'\e[0m'
_mkvutil_track_colours() { MKVUTIL_TRACK_RED="$red"; MKVUTIL_TRACK_YELLOW="$yellow"; }
_mkvutil_menu_read() { preview="$6"; REPLY=1; }
context_log="$PWD/metadata-context.txt"
mkvutil_configure_category mux 2 <<< $'2,0\n1\n0' 2>"$context_log"
context="$(<"$context_log")"
for row in 'Track ID 0: subtitles (S_TEXT/ASS) [Original 2] [eng]' 'Track ID 1: video (V_VP9) [Original 0] [eng]'; do
  [[ "$preview" == *"${yellow}${row}${reset}"* ]] || fail 'preview moved row lost gold'
  [[ "$context" == *"${yellow}${row}${reset}"$'\nForced'* ]] || fail 'metadata value row lost gold or reset'
done
jq -e '.settings=={"1:2":"1","1:0":"0"} and .metadata_output_map=={"0":"2","1":"0"}' <<< "$MKVUTIL_CONFIG" >/dev/null
# Automatic zero and an explicitly listed track that did not move stay plain.
mkvutil_configure_category mux 2 <<< $'3,2\n1\n0\n1' 2>"$context_log"
context="$(<"$context_log")"
[[ "$context" == *"${yellow}Track ID 1: audio (A_OPUS) [Original 3] [eng]${reset}"* ]] || fail 'explicit moved metadata row lost gold'
[[ "$context" == *$'Track ID 0: video (V_VP9) [Original 0] [eng]\nForced'* ]] || fail 'automatic zero metadata row should stay plain'
[[ "$context" == *$'Track ID 2: subtitles (S_TEXT/ASS) [Original 2] [eng]\nForced'* ]] || fail 'unmoved explicit metadata row should stay plain'
mkvutil_configure_category mux 1 <<< $'1\n1\n1' 2>"$context_log"
context="$(<"$context_log")"
[[ "$context" != *"$yellow"* && "$context" != *"$red"* ]] || fail 'remove-only metadata context must stay plain'
[[ "$context" == *'Track ID 1: subtitles (S_TEXT/ASS) [Original 2] [eng]'* ]] || fail 'remove-only context lost output IDs'
print -r -- 'metadata row colours passed'
''', {str(source): model}, extra_env={'TEST_DRY_RUN': str(dry_run)})
    assert result.stdout.rstrip().endswith('metadata row colours passed')
    assert source.read_bytes() == b'payload'
    assert not [call for call in _command_argv(env, 'mkvmerge') if '-o' in call]


def test_mkv_utils_projected_track_view_and_shared_value_context(tmp_path: Path):
    model = _source_json([(0, "video", "V_VP9", True), (1, "audio", "A_AAC", False),
                          (2, "subtitles", "S_TEXT/ASS", False), (3, "audio", "A_OPUS", True),
                          (4, "subtitles", "S_TEXT/UTF8", False)])
    result = _run_metadata_contract(tmp_path, r'''
raw=''' + "'" + json.dumps(model) + "'" + r'''
rows="$(collect_tracks_for_remux fixture.mkv "$raw")"
mkvutil_plan_layout "$rows" 1 0:0,0:4,0:2 mkv
view="$(_mkvutil_track_view "$raw" 1 0,4,2,3 output)"
jq -e 'map(.source_id)==["0","1","4","2","3"] and
  map(.display_id)==["0",null,"1","2","3"] and
  map(.moved)==[false,false,true,false,false] and
  .[1].row=="Track: audio (A_AAC) [Original 1] [eng]" and
  .[2].row=="Track ID 1: subtitles (S_TEXT/UTF8) [Original 4] [eng]"' <<< "$view" >/dev/null
print -r -- "VIEW $view"
mkvutil_metadata_configure 3 preset 0,4,2 0,4,2,3 "$view" <<< $'en\nfr-CA\nde'
eq "${MKVUTIL_METADATA_SETTINGS[3:4]}" fr-CA 'output one maps source four'
(( ! ${+MKVUTIL_METADATA_SETTINGS[3:3]} )) || fail 'implicit appended track edited'
reject mkvutil_metadata_configure 4 independent 0,4,2 0,2,4,3 "$view" < /dev/null
(( ${#MKVUTIL_METADATA_SETTINGS}==0 )) || fail 'invalid full projection left settings'
# Removal of source zero makes new output zero selectable; Edit still uses source IDs.
mkvutil_plan_layout "$rows" 0 '' mkv
view="$(_mkvutil_track_view "$raw" 0 1,2,3,4 output)"
mkvutil_metadata_configure 4 independent '' 1,2,3,4 "$view" <<< $'0\nRetained audio'
eq "${MKVUTIL_METADATA_SETTINGS[4:1]}" 'Retained audio' 'removed source zero does not block output zero'
mkvutil_plan_layout "$rows" '' '' mkv
view="$(_mkvutil_track_view "$raw")"
mkvutil_metadata_configure 1,4 shared '' '' "$view" <<< $'4\n1\nSigns & Songs'
eq "${MKVUTIL_METADATA_SETTINGS[1:4]}" 1 'Edit existing ID flag'
eq "${MKVUTIL_METADATA_SETTINGS[4:4]}" 'Signs & Songs' 'Edit existing ID name'
print -r -- 'projected view contracts passed'
''')
    assert result.stdout.rstrip().endswith("projected view contracts passed")
    assert "Track ID 1: subtitles (S_TEXT/UTF8) [Original 4] [eng]\nLanguage:" in result.stderr
    assert "Track ID 0: audio (A_AAC) [Original 1] [eng]\nTrack name:" in result.stderr
    assert "Track ID 4: subtitles (S_TEXT/UTF8) [Original 4] [eng]\nForced" in result.stderr
    assert "Track ID 4: subtitles (S_TEXT/UTF8) [Original 4] [eng]\nTrack name:" in result.stderr
    assert "Original track ID" not in result.stderr


def test_mkv_utils_mux_output_map_validation_is_exact_and_legacy_opt_in(env):
    source = _mkv_file(env, "mapping.mkv")
    model = _source_json([(0, "video", "V_VP9", True), (1, "audio", "A_AAC", False),
                          (2, "subtitles", "S_TEXT/ASS", False), (3, "audio", "A_OPUS", True)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/mapping.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_configure_category mux 2 <<< $'3,1,0\n4\nThree\nOne\nZero'
config="$MKVUTIL_CONFIG"
mkvutil_validate_config "$config"
jq -e '.order=="0:3,0:1,0:0" and .order_ids==["3","1","0"] and
  .metadata_output_map=={"0":"3","1":"1","2":"0"} and
  .settings=={"4:3":"Three","4:1":"One","4:0":"Zero"} and
  .expected_codecs=={"0":"V_VP9","1":"A_AAC","2":"S_TEXT/ASS","3":"A_OPUS"}' <<< "$config" >/dev/null
for mutation in \
  '.metadata_output_map=null' '.metadata_output_map=[]' \
  '.metadata_output_map={"00":"3","1":"1","2":"0"}' \
  '.metadata_output_map={"0":3,"1":"1","2":"0"}' \
  '.metadata_output_map={"0":"3","1":"3","2":"0"}' \
  '.metadata_output_map={"0":"3","1":"1"}' \
  '.metadata_output_map={"0":"3","1":"1","2":"0","3":"2"}' \
  '.order="0:0,0:1,0:3"' '.order_ids=["3","3","0"]' \
  '.order_ids=["03","1","0"]' '.removed_ids=["1"]' \
  '.expected_types={}' '.expected_types["01"]="audio"' \
  '.reference_track_count=3' '.expected_codecs=null' \
  '.expected_codecs["2"]=""' '.expected_codecs["4"]="A_AAC"'; do
  invalid="$(jq "$mutation" <<< "$config")"
  reject mkvutil_validate_config "$invalid"
done
# Sparse output keys are intentional when only selected output tracks are edited.
sparse="$(jq '.settings={"4:1":"One"}|.metadata_output_map={"1":"1"}' <<< "$config")"
mkvutil_validate_config "$sparse"
mkvutil_target_mismatch "$record" "$sparse"
# Validation never coerces huge output keys to a lossy floating-point index.
huge="$(jq '.settings={"4:1":"One"}|.metadata_output_map={"999999999999999999999999999999999999999":"1"}' <<< "$config")"
reject mkvutil_validate_config "$huge"
code=0; mismatch="$(mkvutil_target_mismatch "$record" "$huge")" || code=$?
eq "$code" 1 'out-of-domain huge output position is an invalid config'
eq "$mismatch" '' 'invalid output map cannot create a skip receipt'
for mutation in '.settings={}|.metadata_output_map={}' '.settings={"5:info":"Title"}|.metadata_output_map={}'; do
  mkvutil_validate_config "$(jq "$mutation" <<< "$config")"
done
# Handcrafted legacy configs retain source-ID-only eligibility and their old schema.
legacy="$(jq 'del(.metadata_output_map,.expected_codecs,.reference_track_count)' <<< "$config")"
mkvutil_validate_config "$legacy"
mkvutil_target_mismatch "$record" "$legacy"
print -r -- 'output map validation passed'
''', {str(source): model})
    assert result.stdout.rstrip().endswith("output map validation passed")
    assert "Track ID 0: audio (A_OPUS) [Original 3] [eng]\nTrack name:" in result.stderr
    assert "Track ID 2: video (V_VP9) [Original 0] [eng]\nTrack name:" in result.stderr
    assert not [call for call in _command_argv(env, "mkvmerge") if "-o" in call]


def test_mkv_utils_mux_original_tree_and_output_binding_guards_before_writes(env):
    source = _mkv_file(env, "tree.mkv")
    model = _source_json([(0, "video", "V_VP9", True), (1, "audio", "A_AAC", False),
                          (2, "subtitles", "S_TEXT/ASS", False), (3, "audio", "A_OPUS", True),
                          (4, "subtitles", "S_TEXT/ASS", False)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/tree.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_configure_category mux 1 <<< $'1\n4\n2\nCommentary'
config="$MKVUTIL_CONFIG"
jq -e '.metadata_output_map=={"2":"3"} and .settings=={"4:3":"Commentary"}' <<< "$config" >/dev/null
job="$(mkvutil_plan_job "$record" "$config")"
# Labels and flags are intentionally lax on every original track.
labels="$(jq '.model.tracks[].properties|=. + {track_name:"Other",language:"jpn",forced_track:true,default_track:false}' <<< "$record")"
mkvutil_target_mismatch "$labels" "$config"
none="$(jq '.settings={}|.metadata_output_map={}' <<< "$config")"
title="$(jq '.settings={"5:info":"Title"}|.metadata_output_map={}' <<< "$config")"
for variant in missing type codec extra; do
  case "$variant" in
    missing) candidate="$(jq '.model.tracks|=map(select(.id!=4))' <<< "$record")" ;;
    type) candidate="$(jq '.model.tracks[4].type="audio"' <<< "$record")" ;;
    codec) candidate="$(jq '.model.tracks[4].properties.codec_id="S_TEXT/UTF8"' <<< "$record")" ;;
    extra) candidate="$(jq '.model.tracks += [{id:5,type:"audio",properties:{codec_id:"A_AAC"}}]' <<< "$record")" ;;
  esac
  for guarded in "$config" "$none" "$title"; do
    code=0; receipt="$(mkvutil_target_mismatch "$candidate" "$guarded")" || code=$?
    eq "$code" 3 "original tree mismatch: $variant"
    jq -e '.kind=="track-mismatch" and (.reasons|length)==1' <<< "$receipt" >/dev/null
  done
  bypass="$(jq '.bypass_track_count=true' <<< "$config")"
  if [[ "$variant" == extra ]]; then mkvutil_target_mismatch "$candidate" "$bypass"
  else reject mkvutil_target_mismatch "$candidate" "$bypass"; fi
done
# A source-array order is not itself a signature. It matters only if an edited
# output position now refers to another original ID. Untouched labels stay lax.
candidate="$(jq '.model.tracks=[.model.tracks[0],.model.tracks[1],.model.tracks[3],.model.tracks[2],.model.tracks[4]]' <<< "$record")"
mkvutil_target_mismatch "$candidate" "$none"
mkvutil_target_mismatch "$candidate" "$title"
code=0; receipt="$(mkvutil_target_mismatch "$candidate" "$config")" || code=$?
eq "$code" 3 'edited output binding mismatch'
jq -e '.reasons==[{output_id:"2",original_id:"3",reason:"output-position-mismatch",expected:{original_id:"3"},actual:{original_id:"2"}}]' <<< "$receipt" >/dev/null
# Both planning and the last fresh runtime preflight use this same guard.
code=0; planned="$(mkvutil_plan_job "$candidate" "$config")" || code=$?
eq "$code" 3 'planning skips changed output binding'
engine_calls=0
_mkvutil_execution_engine() { (( ++engine_calls )); fail 'native engine reached'; }
_mkvutil_capture_execution_source() { REPLY="$candidate"; }
reject mkvutil_execute_mux_job "$job"
eq "$engine_calls" 0 'late output binding mismatch never entered engine'
jq -e '.status=="skipped" and .phase=="preflight" and .artifacts==[] and .planned_outputs==[] and
  .skip_receipt.reasons[0].reason=="output-position-mismatch"' <<< "$MKVUTIL_RESULT_JSON" >/dev/null
report="$(mkvutil_report_removal_skips "$receipt")"
[[ "$report" == *'Output ID 2: expected source ID 3; actual source ID 2'* ]] || fail 'mapping skip is not readable'
candidate="$(jq '.model.tracks[4].properties.codec_id="S_TEXT/UTF8"' <<< "$record")"
reject mkvutil_execute_mux_job "$job"
eq "$engine_calls" 0 'late original-format mismatch never entered engine'
jq -e '.status=="skipped" and .artifacts==[] and .planned_outputs==[] and
  .skip_receipt.reasons[0].original_id=="4" and .skip_receipt.reasons[0].reason=="codec-mismatch"' <<< "$MKVUTIL_RESULT_JSON" >/dev/null
# A reorder-only queue cannot use the removal-count bypass to admit extra IDs.
reorder="$(jq '.removed_ids=[]|.order_ids=["0","2"]|.order="0:0,0:2"|.settings={}|.metadata_output_map={}|.bypass_track_count=true' <<< "$config")"
extra="$(jq '.model.tracks += [{id:5,type:"audio",properties:{codec_id:"A_AAC"}}]' <<< "$record")"
reject mkvutil_target_mismatch "$extra" "$reorder"
print -r -- 'original tree and output binding guards passed'
''', {str(source): model})
    assert result.stdout.rstrip().endswith("original tree and output binding guards passed")
    assert source.read_bytes() == b"payload"
    assert not [call for call in _command_argv(env, "mkvmerge") if "-o" in call]
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
    assert not list(env["workdir"].glob(".mkvutil-*"))


def test_mkv_utils_metadata_preview_uses_scrollback_if_view_cannot_fit(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
_mkvutil_ui_owned() { return 0; }
entered=0
_mkvutil_ui_enter() { (( ++entered )); MKVUTIL_UI_ACTIVE=1; }
stty() { [[ "$geometry" != unknown ]] || return 1; print -r -- "$geometry"; }
preview=$'Output track layout\n\e[2;31mTrack: audio (A_AAC)\e[0m\nTrack ID 0: video (V_VP9)'
geometry='40 240'
_mkvutil_menu_read metadata mux 'Metadata [none]: ' 0 '' "$preview" <<< e
eq "$entered" 1 'fitting complete preview uses owned view'
_mkvutil_ui_leave
for geometry in '10 120' '40 20' unknown; do
  entered=0
  _mkvutil_menu_read metadata mux 'Metadata [none]: ' 0 '' "$preview" <<< e
  eq "$entered" 0 "overflow/unknown geometry does not enter alternate screen: $geometry"
  eq "$MKVUTIL_UI_ACTIVE" 0 'preview stays in ordinary scrollback'
done
print -r -- 'preview fit contracts passed'
''')
    assert result.stdout.count("Output track layout") == 3
    assert result.stderr.count("Output track layout") == 1
    assert result.stdout.rstrip().endswith("preview fit contracts passed")


def test_mkv_utils_metadata_registry_and_language_contract(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
mkvutil_metadata_validate_registry || fail 'initial registry incomplete'
eq "${(j:,:)MKVUTIL_METADATA_IDS}" '1,2,3,4,5' 'choice order'
eq "${MKVUTIL_METADATA_REGISTRY[1:default]}" 0 'forced default'
eq "${MKVUTIL_METADATA_REGISTRY[2:default]}" 1 'default default'
for tag in eng fr-CA zh-Hant-TW sr-Latn de-CH-1901 en-u-ca-gregory x-private i-klingon en-GB-oed sgn-BE-FR zh-min-nan; do
  _mkvutil_metadata_language_valid "$tag" || fail "supported syntax $tag"
done
for tag in '' f fr_CA en--US en-x x-foo-tooLongTag en-u i-unknown sl-rozaj-rozaj en-a-foo-a-bar; do
  reject _mkvutil_metadata_language_valid "$tag"
done
# Syntax validation cannot establish registry membership; callers retain that
# preflight/tool-validation boundary instead of restricting valid BCP 47 tags.
_mkvutil_metadata_language_valid zz-ZZ || fail 'syntax/membership distinction'

saved="${MKVUTIL_METADATA_REGISTRY[4:merge]}"
unset 'MKVUTIL_METADATA_REGISTRY[4:merge]'
captured="$(mkvutil_metadata_menu)" && fail 'offered an incomplete registry'
eq "$captured" '' 'no partial menu'
captured="$(mkvutil_category_menu edit)" && fail 'category menu masked incomplete registry'
eq "$captured" '' 'no partial category menu'
reject mkvutil_metadata_configure 4
MKVUTIL_METADATA_REGISTRY[4:merge]="$saved"
unset 'MKVUTIL_METADATA_REGISTRY[3:default]'
reject mkvutil_metadata_validate_registry
MKVUTIL_METADATA_REGISTRY[3:default]=''
MKVUTIL_METADATA_REGISTRY[1:default]=''
reject mkvutil_metadata_validate_registry
MKVUTIL_METADATA_REGISTRY[1:default]=0

# One new definition participates in both generic builders without dispatch.
_mkvutil_metadata_define 6 'Set commentary flag' track 'Commentary [0]: ' 0 boolean flag-commentary --commentary-flag '' flag_commentary ''
mkvutil_metadata_validate_registry || fail 'new complete definition rejected'
mkvutil_plan_layout $'audio\t11' '' '' mka
mkvutil_metadata_set 1 11 0
mkvutil_metadata_set 2 11 1
mkvutil_metadata_set 6 11 0
mkvutil_build_propedit_args
eq "${(j:|:)MKVUTIL_PROPEDIT_ARGS}" '--edit|track:1|--set|flag-forced=0|--set|flag-default=1|--set|flag-commentary=0' 'generic edit mapping'
mkvutil_build_merge_metadata_args
eq "${(j:|:)MKVUTIL_MERGE_METADATA_ARGS}" '--forced-display-flag|11:0|--default-track-flag|11:1|--commentary-flag|11:0' 'generic merge mapping'
print -r -- 'registry contracts passed'
''')
    assert result.stdout.strip() == "registry contracts passed"


def test_mkv_utils_metadata_builder_literals_and_preserved_flags(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
mkvutil_plan_layout $'audio\t11\naudio\t12\nsubtitles\t14' 14 '0:12' mkv
json='{"tracks":[{"id":11,"type":"audio","properties":{"forced_track":false,"default_track":true,"language":"eng","language_ietf":"en-US"}},{"id":12,"type":"audio","properties":{"forced_track":true,"default_track":true}},{"id":14,"type":"subtitles","properties":{}}]}'
mkvutil_metadata_snapshot_flags "$json" || fail 'valid snapshot rejected'
eq "${MKVUTIL_SOURCE_FLAGS[1:11]}" 0 'false forced snapshot'
eq "${MKVUTIL_SOURCE_FLAGS[2:12]}" 1 'second true default snapshot'
literal=$'@Name $cash: "quoted" \\ path'
mkvutil_metadata_set 1 12 0
mkvutil_metadata_set 3 11 fr-CA
mkvutil_metadata_set 4 11 "$literal"
mkvutil_metadata_set 5 info '@literal $title: "quoted"'
mkvutil_build_propedit_args
printf '%s\0' edit "${MKVUTIL_PROPEDIT_ARGS[@]}"
mkvutil_build_merge_metadata_args
printf '%s\0' merge "${MKVUTIL_MERGE_METADATA_ARGS[@]}"
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" '@literal $title: "quoted"' 'canonical raw title'
mkvutil_metadata_set 5 info '@@two initial at signs'
mkvutil_build_merge_metadata_args
eq "${MKVUTIL_MERGE_METADATA_ARGS[-1]}" '@@@two initial at signs' 'exactly one emitted escape'
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" '@@two initial at signs' 'escaping does not change config'
# Explicit empties are present; absent settings never become implicit clears.
mkvutil_metadata_set 4 11 ''
mkvutil_metadata_set 5 info ''
(( ${+MKVUTIL_METADATA_SETTINGS[4:11]} && ! ${+MKVUTIL_METADATA_SETTINGS[4:12]} )) || fail 'absent/empty conflated'
mkvutil_build_propedit_args
printf '%s\0' clear_edit "${MKVUTIL_PROPEDIT_ARGS[@]}"
mkvutil_build_merge_metadata_args
printf '%s\0' clear_merge "${MKVUTIL_MERGE_METADATA_ARGS[@]}"
''')
    values = result.stdout.split("\0")
    literal = '@Name $cash: "quoted" \\ path'
    assert values == [
        "edit", "--edit", "track:1", "--set", "language=fr-CA",
        "--set", f"name={literal}", "--edit", "track:2",
        "--set", "flag-forced=0", "--edit", "info",
        "--set", 'title=@literal $title: "quoted"',
        "merge", "--forced-display-flag", "12:0", "--default-track-flag", "12:1",
        "--forced-display-flag", "11:0", "--default-track-flag", "11:1",
        "--language", "11:fr-CA", "--track-name", f"11:{literal}",
        "--title", '@@literal $title: "quoted"',
        "clear_edit", "--edit", "track:1", "--set", "language=fr-CA",
        "--set", "name=", "--edit", "track:2", "--set", "flag-forced=0",
        "--edit", "info", "--delete", "title",
        "clear_merge", "--forced-display-flag", "12:0", "--default-track-flag", "12:1",
        "--forced-display-flag", "11:0", "--default-track-flag", "11:1",
        "--language", "11:fr-CA", "--track-name", "11:", "--title", "", "",
    ]


def test_mkv_utils_metadata_rejects_bad_targets_and_stale_snapshots(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
rows=$'audio\t11\naudio\t12'
mkvutil_plan_layout "$rows" '' '' mka
json='{"tracks":[{"id":11,"type":"audio","properties":{"forced_track":false,"default_track":false}},{"id":12,"type":"audio","properties":{"forced_track":true,"default_track":false}}]}'
mkvutil_metadata_snapshot_flags "$json"
mkvutil_build_merge_metadata_args
eq "${(j:|:)MKVUTIL_MERGE_METADATA_ARGS}" '--forced-display-flag|11:0|--default-track-flag|11:0|--forced-display-flag|12:1|--default-track-flag|12:0' 'all defaults false'
reject mkvutil_metadata_set 4 99 missing
reject mkvutil_metadata_set 1 11 false
reject mkvutil_metadata_set 9 11 unknown
reject mkvutil_metadata_set 5 11 wrong-scope
MKVUTIL_METADATA_SETTINGS[4:99]=missing
reject mkvutil_build_propedit_args
reject mkvutil_build_merge_metadata_args
(( ${#MKVUTIL_PROPEDIT_ARGS} == 0 && ${#MKVUTIL_MERGE_METADATA_ARGS} == 0 )) || fail 'unknown target left output args'
unset 'MKVUTIL_METADATA_SETTINGS[4:99]'
mkvutil_metadata_set 4 11 before-removal
mkvutil_build_propedit_args
mkvutil_plan_layout "$rows" 11 '' mka
reject mkvutil_build_propedit_args
(( ${#MKVUTIL_PROPEDIT_ARGS} == 0 )) || fail 'stale edit args after removed target'
reject mkvutil_build_merge_metadata_args
(( ${#MKVUTIL_MERGE_METADATA_ARGS} == 0 )) || fail 'stale merge args after removed target'
reject mkvutil_metadata_set 3 11 eng
mkvutil_metadata_reset
mkvutil_plan_layout "$rows" '' '' mka
for bad in 'null' '0' '"false"'; do
  broken="${json/\"forced_track\":false/\"forced_track\":$bad}"
  reject mkvutil_metadata_snapshot_flags "$broken"
  (( ${#MKVUTIL_SOURCE_FLAGS} == 0 )) || fail 'partial flags survived invalid snapshot'
  reject mkvutil_build_merge_metadata_args
  (( ${#MKVUTIL_MERGE_METADATA_ARGS} == 0 )) || fail 'partial args survived invalid snapshot'
done
broken="${json/\"forced_track\":false,/}"
reject mkvutil_metadata_snapshot_flags "$broken"
mkvutil_metadata_snapshot_flags "$json"
# Layout changes invalidate preserved flags even when the TIDs still exist.
mkvutil_plan_layout $'audio\t12\naudio\t11' '' '' mka
reject mkvutil_build_merge_metadata_args
reject mkvutil_metadata_snapshot_flags "$json"
mkvutil_metadata_reset
mkvutil_plan_layout $'subtitles\t22' '' '' mks
mkvutil_metadata_snapshot_flags '{"tracks":[{"id":22,"type":"subtitles","properties":{"forced_track":false,"default_track":true}}]}'
mkvutil_metadata_set 4 22 second-file
mkvutil_build_propedit_args
eq "${(j:|:)MKVUTIL_PROPEDIT_ARGS}" '--edit|track:1|--set|name=second-file' 'second file original selector'
mkvutil_build_merge_metadata_args
eq "${(j:|:)MKVUTIL_MERGE_METADATA_ARGS}" '--forced-display-flag|22:0|--default-track-flag|22:1|--track-name|22:second-file' 'second file fresh flags and settings'
print -r -- 'failure and successive-file contracts passed'
''')
    assert result.stdout.strip() == "failure and successive-file contracts passed"


def test_mkv_utils_metadata_configuration_defaults_literals_and_eof(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
calls=0
mkvmerge() { (( calls++ )); return 90; }
mkvpropedit() { (( calls++ )); return 90; }
mkvutil_plan_layout $'audio\t11\nsubtitles\t12' '' '' mka
mkvutil_metadata_configure '1-5' || fail 'complete configuration rejected'
eq "${MKVUTIL_METADATA_SETTINGS[1:11]}" 0 'collected forced default'
eq "${MKVUTIL_METADATA_SETTINGS[2:11]}" 1 'collected default flag default'
eq "${MKVUTIL_METADATA_SETTINGS[2:12]}" 0 'collected explicit false'
eq "${MKVUTIL_METADATA_SETTINGS[3:11]}" fr-CA 'collected language'
eq "${MKVUTIL_METADATA_SETTINGS[4:11]}" '@name $cash: "quote" \literal' 'read -r name'
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" '' 'blank title is clear'
(( ${+MKVUTIL_METADATA_SETTINGS[5:info]} )) || fail 'clear title missing'
mkvutil_build_propedit_args
eq "$calls" 0 'configuration/builders executed modifying tools'
result=0
mkvutil_metadata_configure 4 || result=$?
eq "$result" 2 'EOF returns'
(( ${#MKVUTIL_METADATA_SETTINGS} == 0 && ${#MKVUTIL_PROPEDIT_ARGS} == 0 )) || fail 'EOF left partial settings/args'
result=0
mkvutil_metadata_configure '4,5' <<< $'11\npartial name' || result=$?
eq "$result" 2 'EOF midway through collection returns'
(( ${#MKVUTIL_METADATA_SETTINGS} == 0 )) || fail 'EOF preserved partially collected name'
result=0
mkvutil_metadata_configure 4 <<< cancel || result=$?
eq "$result" 2 'invalid ID text reaches bounded EOF after retry'
reject mkvutil_metadata_configure 4 <<< '11,,12'
print -r -- 'configuration contracts passed'
''', "11\n\n11,12\n\n0\n11\nfr-CA\n11\n@name $cash: \"quote\" \\literal\n\n")
    assert result.stdout.strip() == "configuration contracts passed"


def test_mkv_utils_invalid_prompt_values_retry_without_losing_valid_text(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
mkvutil_plan_layout $'audio\t11\nsubtitles\t12' '' '' mka
mkvutil_metadata_configure '1,3,4,5' shared <<< $'not-an-id\n99\n11,,12\n12-11\ncancel\n11,12\n2\n0\nyes\n1\nbad_tag\nfr-CA\neng\ncancel\n\\e\n\\E'
eq "${MKVUTIL_METADATA_SETTINGS[1:11]}" 0 'invalid/unknown flag values retry to valid false'
eq "${MKVUTIL_METADATA_SETTINGS[1:12]}" 1 'invalid flag text retries to valid true'
eq "${MKVUTIL_METADATA_SETTINGS[3:11]}" fr-CA 'invalid language retries through syntax validator'
eq "${MKVUTIL_METADATA_SETTINGS[3:12]}" eng 'second language target collected'
eq "${MKVUTIL_METADATA_SETTINGS[4:11]}" cancel 'cancel is valid arbitrary track-name text'
eq "${MKVUTIL_METADATA_SETTINGS[4:12]}" e 'escaped e is literal track-name text'
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" E 'escaped E is literal title text'

_mkvutil_metadata_define 6 'Set commentary flag' track 'Commentary [0]: ' 0 boolean flag-commentary --commentary-flag '' flag_commentary ''
mkvutil_metadata_validate_registry || fail 'extended Edit registry invalid'
eq "$(mkvutil_category_choices edit 3)" 3 'single Edit choice'
eq "$(mkvutil_category_choices edit '1-4,2')" '1,2,3,4' 'mixed range/comma Edit choices deduplicate'
eq "$(mkvutil_category_choices edit '1,3,4-6')" '1,3,4,5,6' 'mixed Edit choices include registered ID 6'
eq "$(mkvutil_category_choices mux '1,2')" '1,2' 'combined Mux choices'
eq "$(mkvutil_category_choices extract '1,2')" '1,2' 'combined Extract choices'
for invalid in 0 w 99 '1,,2' '2-1' '1-7'; do
  code=0; captured="$(mkvutil_category_choices edit "$invalid")" || code=$?
  eq "$code" 3 "invalid Edit choice rejected: $invalid"
  eq "$captured" '' "no partial Edit choice: $invalid"
done
for category in mux extract; do
  for invalid in 0 3 99 '1,,2' '2-1' '1-3'; do
    code=0; captured="$(mkvutil_category_choices "$category" "$invalid")" || code=$?
    eq "$code" 3 "invalid $category choice rejected: $invalid"
    eq "$captured" '' "no partial $category choice: $invalid"
  done
done

# Optional metadata choices use the same bounded domain and accept ordinary
# text such as "cancel" as a title value.
raw='{"tracks":[{"id":11,"type":"audio","properties":{"codec_id":"A_AAC"}},{"id":12,"type":"subtitles","properties":{"codec_id":"S_TEXT/ASS"}}]}'
MKVUTIL_SOURCES[1]="$(jq -cn --arg source "$PWD/reference.mkv" --argjson model "$raw" '{source:$source,source_json:($model|tojson)}')"
mkvutil_configure_category mux 2 <<< $'11,12\n0\n5\ncancel'
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" cancel 'optional metadata rejects zero then accepts title'
print -r -- 'invalid prompt retries passed'
''')
    assert result.stdout.rstrip().endswith("invalid prompt retries passed")
    assert result.stderr.count("Track IDs:") == 6
    assert result.stderr.count("Forced (0/1) [0]: ") >= 4
    assert "Language:" in result.stderr and "Track name:" in result.stderr
    assert "Metadata [none]: " in result.stderr


def test_mkv_utils_exclusion_prompt_retries_only_known_answers(tmp_path: Path):
    result = _run_metadata_contract(tmp_path, r'''
code=0
_mkvutil_exclude <<< $'maybe\nYES' || code=$?
eq "$code" 0 'unknown answer retries to YES'
code=0
_mkvutil_exclude <<< $'cancel\nNO' || code=$?
eq "$code" 1 'cancel is not a special exclusion answer'
code=0
_mkvutil_exclude <<< '' || code=$?
eq "$code" 1 'blank selects the default No'
code=0
_mkvutil_exclude <<< e || code=$?
eq "$code" 4 'exact e returns Back'
code=0
_mkvutil_exclude <<< E || code=$?
eq "$code" 4 'exact E returns Back'
print -r -- 'exclusion prompt contracts passed'
''')
    assert result.stdout.strip() == "exclusion prompt contracts passed"
    assert result.stderr.count("Exclude file?") == 7


def _source_json(tracks: list[tuple[int, str, str, bool]], *, attachments=None):
    return {
        "tracks": [
            {"id": tid, "type": kind, "properties": {
                "codec_id": codec, "track_name": f"Original {tid}",
                "language": "eng", "language_ietf": "en-US",
                "forced_track": False, "default_track": default,
                "uid": 18446744073709551615,
            }}
            for tid, kind, codec, default in tracks
        ],
        "container": {"properties": {"title": "Original title"}},
        "attachments": attachments or [],
    }


def _run_planning_contract(env: dict[str, Path], body: str, sources: dict, input_data="", *, extra_env=None):
    overrides = env["fake_state"] / "source-json.json"
    overrides.write_text(json.dumps(sources), encoding="utf-8")
    run_env = os.environ.copy()
    run_env.update({
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq",
        "TEST_REAL_PYTHON": sys.executable,
        "TEST_USE_REAL_JSON": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]),
        "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]),
        "TEST_FAKE_MKVMERGE_JSON_BY_PATH": str(overrides),
        "TEST_FAKE_FZF_SELECTIONS": str(env["fake_fzf_selections"]),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    if extra_env:
        run_env.update(extra_env)
    for tool in ("mkvmerge", "mkvpropedit", "mkvextract", "python3", "jq"):
        assert Path(shutil.which(tool, path=run_env["PATH"])).resolve() == (env["fake_bin"] / tool).resolve()
    result = subprocess.run(
        ["/usr/local/bin/zsh", "-f", "-c", r'''
source "$1"
setopt errexit
fail() { print -u2 -r -- "planning contract failure: $1"; return 1; }
eq() { [[ "$1" == "$2" ]] || fail "$3: expected '$2', got '$1'"; }
reject() { if "$@"; then fail "accepted invalid call: $*"; fi; }
''' + body, "planning-contract", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, input=input_data,
        text=True, capture_output=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not _command_argv(env, "mkvpropedit")
    assert not _command_argv(env, "mkvextract")
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    return result


def test_mkv_utils_category_job_roundtrip_and_per_file_flags(env: dict[str, Path]):
    first, second = _mkv_file(env, "First file.mkv"), _mkv_file(env, "Second file.mk3d")
    tracks = [(0, "video", "V_MPEG4/ISO/AVC", True), (11, "audio", "A_AAC", False), (12, "subtitles", "S_TEXT/ASS", True)]
    first_json = _source_json(tracks)
    second_json = _source_json([(tid, kind, codec, True) for tid, kind, codec, _ in tracks])
    result = _run_planning_contract(env, r'''
_mkvutil_metadata_define 6 'Set commentary flag' track 'Commentary [0]: ' 0 boolean flag-commentary --commentary-flag '' flag_commentary ''
first="$(mkvutil_capture_source "$PWD/First file.mkv")"
second="$(mkvutil_capture_source "$PWD/Second file.mk3d")"
settings="$(_mkvutil_json_map '4:11' $'@name $cash: "quoted" \\literal\n\n' '3:11' fr-CA '5:info' '' '6:11' 0)"
config="$(jq -cn --argjson settings "$settings" '{category:"mux",operations:["1","2"],removed_ids:["0"],order:"0:12",order_ids:["12"],metadata:"3-6",settings:$settings,expected_types:{"0":"video","11":"audio","12":"subtitles"},extract_ids:[]}')"
config="$(jq --arg reference "$PWD/First file.mkv" --argjson signatures "$(mkvutil_removal_signatures "$first" 0)" --argjson reference_track_count "$(jq '.model.tracks|length' <<< "$first")" '.+{reference:$reference,reference_track_count:$reference_track_count,removal_signatures:$signatures}' <<< "$config")"
a="$(mkvutil_plan_job "$first" "$config")"
b="$(mkvutil_plan_job "$second" "$config")"
mkvutil_check_destinations "$a" "$b"
mkvutil_load_job "$a"
eq "${(j:,:)MKVUTIL_RETAINED_IDS}" '12,11' 'resolved final order'
eq "${MKVUTIL_PROPEDIT_SELECTORS[11]}" track:2 'original listing selector'
eq "${MKVUTIL_SOURCE_FLAGS[2:11]}" 0 'first file explicit false'
eq "${MKVUTIL_METADATA_SETTINGS[4:11]}" $'@name $cash: "quoted" \\literal\n\n' 'literal trailing newlines'
eq "${MKVUTIL_MERGE_METADATA_ARGS[-1]}" '' 'last empty argv'
mkvutil_load_job "$b"
eq "${MKVUTIL_SOURCE_FLAGS[2:11]}" 1 'same-layout second source flags refreshed'
eq "$MKVUTIL_OUTPUT_EXTENSION" mka 'retained content extension'
editconfig="$(jq '.category="edit"|.operations=["3","4","5","6"]|.removed_ids=[]|.order=""|.order_ids=[]' <<< "$config")"
editjob="$(mkvutil_plan_job "$first" "$editconfig")"
for job in "$a" "$editjob"; do
  MKVUTIL_JOBS=("$job")
  preview="$(mkvutil_preview_jobs)"
  [[ "$preview" == *'Metadata: Set commentary flag'* ]] || fail 'generic registry row absent in preview'
done
print -r -- "$a"
print -r -- "$b"
: > "$PWD/First file.mka"
reject mkvutil_check_destinations "$a" "$b"
reject mkvutil_check_destinations "$a" "$a"
print -r -- changed >> "$PWD/Second file.mk3d"
changed_code=0
changed_receipt="$(mkvutil_plan_job "$second" "$config")" || changed_code=$?
eq "$changed_code" 3 'changed source automatically skipped'
eq "$(jq -r '.kind' <<< "$changed_receipt")" source-changed 'changed identity receipt'
''', {str(first): first_json, str(second): second_json})
    jobs = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(jobs) == 2
    for job, original, file in zip(jobs, (first_json, second_json), (first, second)):
        assert json.loads(job["source_json"]) == original
        assert "18446744073709551615" in job["source_json"]
        assert job["retained_ids"] == ["12", "11"]
        assert job["track_order"] == "0:12,0:11"
        assert job["merge_metadata_args"][-2:] == ["--title", ""]
        assert job["config"]["settings"]["4:11"].endswith("\n\n")
        assert [track["original_id"] for track in job["preview"]["tracks"]] == ["12", "11"]
        assert job["preview"]["tracks"][1]["language"] == "fr-CA"
        assert job["destination"] == str(file.with_suffix(".mka"))
        assert any(item["choice"] == "6" for item in job["requested_metadata"])
    assert jobs[0]["source_flags"]["2:11"] == "0"
    assert jobs[1]["source_flags"]["2:11"] == "1"


def test_mkv_utils_category_planning_formats_types_and_scan_domain(env: dict[str, Path]):
    models = {
        "video.mkv": [(0, "video", "V_MPEG4/ISO/AVC", True), (1, "audio", "A_AAC", True)],
        "audio.mka": [(11, "audio", "A_AAC", False)],
        "subtitle.mks": [(12, "subtitles", "S_TEXT/ASS", False)],
        "stereo.mk3d": [(2, "video", "V_MPEG4/ISO/AVC", True)],
    }
    sources = {str(_mkv_file(env, name)): _source_json(tracks) for name, tracks in models.items()}
    (env["workdir"] / "Directory with spaces").mkdir()
    result = _run_planning_contract(env, r'''
eq "$(mkvutil_category_choices edit '1-3,2,5')" '1,2,3,5' 'submenu range/dedup'
reject mkvutil_category_choices mux '3'
reject mkvutil_category_choices extract '1,,2'
eq "$(mkvutil_resolve_directory)" "$PWD" 'default directory'
eq "$(mkvutil_resolve_directory '../workdir')" "$PWD" 'relative parent directory'
eq "$(mkvutil_resolve_directory './Directory with spaces')" "$PWD/Directory with spaces" 'relative spaces'
eq "$(mkvutil_resolve_directory "$PWD/Directory with spaces")" "$PWD/Directory with spaces" 'absolute spaces'
mkvutil_scan_files "$PWD"
eq "${#MKVUTIL_SCAN_FILES}" 4 'four format scan'
mkvutil_accept_files "${MKVUTIL_SCAN_FILES[@]}"
reject mkvutil_accept_files /unscanned/injected.mkv
reject mkvutil_accept_files "$PWD/video.mkv" "$PWD/video.mkv"
config='{"category":"edit","operations":["5"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{"5:info":""},"expected_types":{},"extract_ids":[]}'
for file in "${MKVUTIL_SCAN_FILES[@]}"; do
  record="$(mkvutil_capture_source "$file")"
  job="$(mkvutil_plan_job "$record" "$config")"
  print -r -- "$job"
done
record="$(mkvutil_capture_source "$PWD/audio.mka")"
bad="$(jq '.settings={"4:11":"name"}|.expected_types={"11":"subtitles"}' <<< "$config")"
code=0; receipt="$(mkvutil_plan_job "$record" "$bad")" || code=$?
eq "$code" 3 'wrong track type automatically skipped'
eq "$(jq -r '.reasons[0].reason' <<< "$receipt")" type-mismatch 'wrong type receipt'
bad="$(jq '.settings={"4:99":"name"}|.expected_types={"99":"audio"}' <<< "$config")"
code=0; receipt="$(mkvutil_plan_job "$record" "$bad")" || code=$?
eq "$code" 3 'missing target automatically skipped'
eq "$(jq -r '.reasons[0].reason' <<< "$receipt")" missing-id 'missing ID receipt'
bad="$(jq '.removed_ids=["11"]' <<< "$config")"
reject mkvutil_plan_job "$record" "$bad"
''', sources)
    jobs = [json.loads(line) for line in result.stdout.splitlines()]
    assert {Path(job["source"]).suffix for job in jobs} == {".mkv", ".mka", ".mks", ".mk3d"}
    assert all(job["propedit_args"] == ["--edit", "info", "--delete", "title"] for job in jobs)
    assert all(job["destination"] == job["source"] for job in jobs)


def test_mkv_utils_extract_planning_names_and_collision_contract(env: dict[str, Path]):
    source = _mkv_file(env, "Extract source.mkv")
    model = _source_json(
        [(0, "video", "V_MPEG4/ISO/AVC", True), (11, "audio", "A_TRUEHD", True), (12, "subtitles", "S_TEXT/ASS", False)],
        attachments=[{"id": 1, "file_name": 'note $cash "literal".txt', "content_type": "text/plain", "size": 4}],
    )
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/Extract source.mkv")"
config='{"category":"extract","operations":["1","2"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{},"expected_types":{"0":"video","11":"audio","12":"subtitles"},"extract_ids":["0","11","12"]}'
job="$(mkvutil_plan_job "$record" "$config")"
mkvutil_check_destinations "$job"
print -r -- "$job"
: > "$PWD/Attachments"
reject mkvutil_check_destinations "$job"
unsafe="$(jq '.model.attachments[0].file_name="../escape"' <<< "$record")"
reject mkvutil_plan_job "$unsafe" "$config"
''', {str(source): model})
    job = json.loads(result.stdout)
    assert [Path(item["path"]).suffix for item in job["outputs"]] == [".txt", ".h264", ".thd", ".ass"]
    assert job["outputs"][0]["path"] == str(source.parent / "Attachments" / 'note $cash "literal".txt')
    assert job["merge_metadata_args"] == job["propedit_args"] == []


def test_mkv_utils_destination_aliases_follow_filesystem_case_behavior(env: dict[str, Path]):
    first, second = _mkv_file(env, "Show.mkv"), _mkv_file(env, "show.mk3d")
    insensitive = first.with_name(first.name.swapcase()).exists()
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (1, "audio", "A_AAC", True)])
    result = _run_planning_contract(env, r'''
a="$(mkvutil_capture_source "$PWD/Show.mkv")"
b="$(mkvutil_capture_source "$PWD/show.mk3d")"
config='{"category":"mux","operations":["1"],"removed_ids":["0"],"order":"","order_ids":[],"metadata":"","settings":{},"expected_types":{"0":"video"},"extract_ids":[]}'
config="$(jq --arg reference "$PWD/Show.mkv" --argjson signatures "$(mkvutil_removal_signatures "$a" 0)" '.+{reference:$reference,reference_track_count:2,removal_signatures:$signatures}' <<< "$config")"
a="$(mkvutil_plan_job "$a" "$config")"
b="$(mkvutil_plan_job "$b" "$config")"
result=0
mkvutil_check_destinations "$a" "$b" || result=$?
print -r -- "$result"
''', {str(first): model, str(second): model})
    assert result.stdout.strip() == ("1" if insensitive else "0")


@pytest.mark.parametrize("bypass_position", ["none", "before", "after"])
def test_mkv_utils_mux_entrypoint_track_count_skip_and_bypass(env, bypass_position):
    first = _mkv_file(env, "Reference count.mkv")
    second = _mkv_file(env, "Extra count.mkv")
    reference = _integration_model([(0, "video", "V_MPEG4/ISO/AVC", True),
                                    (11, "audio", "A_AAC", True),
                                    (12, "subtitles", "S_TEXT/ASS", False)])
    extra = json.loads(json.dumps(reference))
    extra["tracks"].append(_integration_model([(99, "audio", "A_OPUS", True)])["tracks"][0])
    first_output = _integration_output(reference, [11, 12])
    second_output = _integration_output(extra, [11, 12, 99])
    for output in (first_output, second_output):
        for track in output["tracks"][:2]:
            track["properties"]["track_name"] = "Batch name"
    manifest = _integration_manifest(env, {first: reference, second: extra}, stage={
        str(first): first_output,
        str(second): second_output,
    })
    if bypass_position == "none":
        args = (str(env["workdir"]),)
    elif bypass_position == "before":
        args = ("--bypass", str(env["workdir"]))
    else:
        args = (str(env["workdir"]), "--bypass")
    result = _run_mkv_utils(
        env, *args, input_data="2\n1,2\n0\n11,12\n4\nBatch name\nBatch name\n",
        fzf_responses=[[str(first), str(second)]], extra_env=manifest,
    )
    assert "Removal reference file: Reference count.mkv" in result.stdout
    assert str(first) not in result.stdout and str(second) not in result.stdout
    _ascii_box_contains(result.stdout, "Final report")
    config_header_start, config_header_end, _ = _ascii_box_contains(
        result.stdout, "Track configuration", f"Current Work Dir: {env['workdir']}",
        "Removal reference file: Reference count.mkv")
    listing_index = result.stdout.index("mkvmerge JSON track listing")
    assert config_header_start < config_header_end < listing_index
    merge_calls = [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    expected_orders = {str(first): "0:11,0:12", str(second): "0:11,0:12,0:99"}
    for call in merge_calls:
        source = call[-1]
        assert source in expected_orders
        assert call[call.index("--track-order") + 1] == expected_orders[source]
        assert call[call.index("--track-name") + 1] == "11:Batch name"
    if bypass_position == "none":
        assert result.returncode == 1, result.stdout + result.stderr
        assert len(merge_calls) == 1 and str(first) in merge_calls[0]
        assert str(second) not in merge_calls[0]
        assert merge_calls[0][merge_calls[0].index("--track-order") + 1] == "0:11,0:12"
        assert merge_calls[0][merge_calls[0].index("--track-name") + 1] == "11:Batch name"
        assert "Skipped removal mismatch: Extra count.mkv" in result.stdout
        assert "Track count mismatch: expected 3; actual 4" in result.stdout
        _assert_readable_outcomes(result.stdout, "Done: 1", "Skipped: 1")
        assert "Bypass enabled:" not in result.stdout
        assert second.read_bytes() == b"payload"
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(merge_calls) == 2
        assert {argv[-1] for argv in merge_calls} == {str(first), str(second)}
        assert "Track count mismatch:" not in result.stdout
        _assert_readable_outcomes(result.stdout, "Done: 2")
        assert "Skipped: 0" in result.stdout
        assert "Bypass enabled: removal track-count guard only." in result.stdout
        assert result.stdout.count("Bypass enabled: removal track-count guard only.") == 1
        assert not first.exists() and not second.exists()
        assert first.with_suffix(".mka").read_bytes() == b"candidate-data\n"
        assert second.with_suffix(".mka").read_bytes() == b"candidate-data\n"
    assert not _command_argv(env, "mkvpropedit")
    extract_calls = _command_argv(env, "mkvextract")
    assert all(argv[1] in {"tags", "chapters"} for argv in extract_calls)
    if bypass_position == "none":
        assert all(argv[0] != str(second) for argv in extract_calls)


def test_mkv_utils_collision_check_streams_large_queue_records(env: dict[str, Path]):
    first, second = _mkv_file(env, "One.mkv"), _mkv_file(env, "Two.mkv")
    records = [{"source": str(source), "config": {"category": "mux"},
                "outputs": [str(source.with_suffix(".mka"))], "padding": "x" * 200_000}
               for source in (first, second)]
    result = _run_planning_contract(env, r'''
IFS= read -r first
IFS= read -r second
mkvutil_check_destinations "$first" "$second"
reject mkvutil_check_destinations "$first" "$second" "$second"
print -r -- 'streamed queue contracts passed'
''', {}, "\n".join(json.dumps(record) for record in records) + "\n")
    assert result.stdout.strip() == "streamed queue contracts passed"


def test_mkv_utils_category_configuration_eof_and_failed_inspection(env: dict[str, Path]):
    source = _mkv_file(env, "configure.mkv")
    incompatible = _mkv_file(env, "incompatible.mks")
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/configure.mkv")"
MKVUTIL_SOURCES=("$record")
result=0
mkvutil_configure_category mux '1,2' < /dev/null || result=$?
eq "$result" 2 'configuration EOF bounded'
eq "$MKVUTIL_CONFIG" '' 'EOF has no configuration'
other="$(mkvutil_capture_source "$PWD/incompatible.mks")"
MKVUTIL_SOURCES=("$record" "$other")
MKVUTIL_CONFIG='{"category":"edit","operations":["4"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{"4:0":"Name"},"expected_types":{"0":"audio"},"extract_ids":[]}'
mkvutil_plan_queue < /dev/null
eq "${#MKVUTIL_JOBS}" 1 'incompatible file automatically skipped'
eq "${#MKVUTIL_SOURCES}" 2 'automatic skips retain original scope'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 1 'one type mismatch receipt'
MKVUTIL_SELECTED_FILES=("$PWD/missing.mkv")
result=0
mkvutil_inspect_sources <<< N || result=$?
eq "$result" 1 'inspection requires explicit exclusion'
(( ${#MKVUTIL_JOBS}==0 )) || fail 'failed inspection left jobs'
result=0
mkvutil_inspect_sources <<< Y || result=$?
eq "$result" 1 'zero valid queue aborts after exclusion'
print -r -- 'configuration failure contracts passed'
''', {str(source): _source_json([(0, "audio", "A_AAC", False)]),
      str(incompatible): _source_json([(0, "subtitles", "S_TEXT/ASS", False)])})
    assert result.stdout.rstrip().endswith("configuration failure contracts passed")


def _removal_models():
    reference = _source_json([(0, "audio", "A_AAC", False), (1, "subtitles", "S_TEXT/ASS", True), (2, "audio", "A_OPUS", True)])
    compatible = json.loads(json.dumps(reference))
    compatible["tracks"][1]["properties"].update(track_name="Different", language="jpn", language_ietf="ja", default_track=False, forced_track=True)
    codec = json.loads(json.dumps(reference))
    codec["tracks"][1]["properties"]["codec_id"] = "S_TEXT/UTF8"
    kind = json.loads(json.dumps(reference))
    kind["tracks"][1]["type"] = "audio"
    missing = _source_json([(0, "audio", "A_AAC", True), (99, "video", "V_MPEG4/ISO/AVC", False)])
    failed = json.loads(json.dumps(reference))
    failed["tracks"][0]["properties"]["default_track"] = None
    return dict(reference=reference, compatible=compatible, codec=codec, kind=kind, missing=missing, failed=failed)


def test_mkv_utils_removal_signatures_skips_and_reconsideration(env: dict[str, Path]):
    models = _removal_models()
    sources = {str(_mkv_file(env, f"{name}.mkv")): model for name, model in models.items()}
    result = _run_planning_contract(env, r'''
reference="$(mkvutil_capture_source "$PWD/reference.mkv")"
compatible="$(mkvutil_capture_source "$PWD/compatible.mkv")"
codec="$(mkvutil_capture_source "$PWD/codec.mkv")"
kind="$(mkvutil_capture_source "$PWD/kind.mkv")"
missing="$(mkvutil_capture_source "$PWD/missing.mkv")"
failed="$(mkvutil_capture_source "$PWD/failed.mkv")"
signatures="$(mkvutil_removal_signatures "$reference" '1,2')"
config="$(jq -cn --arg reference "$PWD/reference.mkv" --argjson signatures "$signatures" '{category:"mux",operations:["1","2"],removed_ids:["1","2"],order:"0:0",order_ids:["0"],metadata:"4,5",settings:{"4:0":"@literal $name","5:info":""},expected_types:{"0":"audio","1":"subtitles","2":"audio"},extract_ids:[],reference:$reference,reference_track_count:3,removal_signatures:$signatures}')"
MKVUTIL_SOURCES=("$reference" "$compatible" "$codec" "$kind" "$missing" "$failed")
MKVUTIL_CONFIG="$config"
mkvutil_plan_queue <<< Y
eq "${#MKVUTIL_JOBS}" 2 'mixed eligible count'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 3 'mixed mismatch count'
eq "${#MKVUTIL_SOURCES}" 5 'auto skips retained; explicit failure excluded'
reject mkvutil_prepare_skipped_subset
# New removal IDs reconsider the entire current scope, including prior skips.
signatures="$(mkvutil_removal_signatures "$reference" 0)"
MKVUTIL_CONFIG="$(jq --argjson signatures "$signatures" '.operations=["1"]|.removed_ids=["0"]|.order=""|.order_ids=[]|.metadata=""|.settings={}|.removal_signatures=$signatures' <<< "$config")"
mkvutil_plan_queue
eq "${#MKVUTIL_JOBS}" 4 'prior auto skips reconsidered except changed track count'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 1 'different track count remains skipped'
eq "$(jq -r '.track_count_mismatch.expected' <<< "${MKVUTIL_REMOVAL_SKIPS[1]}")" 3 'reference count retained'
eq "$(jq -r '.track_count_mismatch.actual' <<< "${MKVUTIL_REMOVAL_SKIPS[1]}")" 2 'missing-file count retained'
eq "${#MKVUTIL_SOURCES}" 5 'explicit exclusion persisted'
print -r -- 'removal eligibility contracts passed'
''', sources)
    assert result.stdout.rstrip().endswith("removal eligibility contracts passed")
    assert all(Path(filename).read_text() == "payload" for filename in sources)
    assert not list(env["workdir"].glob("*.mka"))


def test_mkv_utils_removal_mismatch_receipts_and_empty_builders(env):
    models = _removal_models()
    extra = json.loads(json.dumps(models["reference"]))
    extra["tracks"].append(_source_json([(99, "video", "V_MPEG4/ISO/AVC", True)])["tracks"][0])
    models["extra"] = extra
    sources = {str(_mkv_file(env, f"{name}.mkv")): models[name] for name in ("reference", "codec", "kind", "missing", "extra")}
    result = _run_planning_contract(env, r'''
reference="$(mkvutil_capture_source "$PWD/reference.mkv")"
codec="$(mkvutil_capture_source "$PWD/codec.mkv")"
kind="$(mkvutil_capture_source "$PWD/kind.mkv")"
missing="$(mkvutil_capture_source "$PWD/missing.mkv")"
extra="$(mkvutil_capture_source "$PWD/extra.mkv")"
signatures="$(mkvutil_removal_signatures "$reference" '1,2')"
config="$(jq -cn --arg reference "$PWD/reference.mkv" --argjson signatures "$signatures" '{category:"mux",operations:["1","2"],removed_ids:["1","2"],order:"0:0",order_ids:["0"],metadata:"4,5",settings:{"4:0":"@literal $name","5:info":""},expected_types:{"0":"audio","1":"subtitles","2":"audio"},extract_ids:[],reference:$reference,reference_track_count:3,removal_signatures:$signatures}')"
# Missing IDs and exact type/codec differences are receipts, not ordinary errors.
for record in "$codec" "$kind" "$missing" "$extra"; do
  status_code=0
  MKVUTIL_PROPEDIT_ARGS=(stale)
  MKVUTIL_MERGE_METADATA_ARGS=(stale)
  receipt_file="$PWD/receipt.json"
  mkvutil_plan_job "$record" "$config" > "$receipt_file" || status_code=$?
  eq "$status_code" 3 'automatic mismatch status'
  (( ${#MKVUTIL_PROPEDIT_ARGS}==0 && ${#MKVUTIL_MERGE_METADATA_ARGS}==0 )) || fail 'whole skipped job left argv'
  jq -e '.kind=="removal-mismatch" and .outputs==[] and .propedit_args==[] and .merge_metadata_args==[]' "$receipt_file" >/dev/null
  print -r -- "RECEIPT $(< "$receipt_file")"
done
''', sources)
    receipts = [json.loads(line.removeprefix("RECEIPT ")) for line in result.stdout.splitlines() if line.startswith("RECEIPT ")]
    assert [receipt["source"] for receipt in receipts] == [str(env["workdir"] / f"{name}.mkv") for name in ("codec", "kind", "missing", "extra")]
    assert [reason["reason"] for reason in receipts[0]["reasons"]] == ["codec-mismatch"]
    assert receipts[0]["reasons"][0]["expected"] == {"type": "subtitles", "codec_id": "S_TEXT/ASS"}
    assert receipts[0]["reasons"][0]["actual"] == {"type": "subtitles", "codec_id": "S_TEXT/UTF8"}
    assert receipts[1]["reasons"][0]["reason"] == "type-mismatch"
    assert [reason["original_id"] for reason in receipts[2]["reasons"]] == ["1", "2"]
    assert all(reason["reason"] == "missing-id" and reason["actual"] is None for reason in receipts[2]["reasons"])
    assert receipts[2]["track_count_mismatch"] == {"expected": 3, "actual": 2}
    assert receipts[3]["track_count_mismatch"] == {"expected": 3, "actual": 4}
    assert receipts[3]["reasons"] == []
    assert all(Path(filename).read_text() == "payload" for filename in sources)
    assert not list(env["workdir"].glob("*.mka"))


def test_mkv_utils_removal_signature_unusable_values_and_config(env):
    _run_planning_contract(env, r'''
reference='{"model":{"tracks":[{"id":0,"type":"audio","properties":{"codec_id":"A_AAC"}},{"id":1,"type":"subtitles","properties":{"codec_id":"S_TEXT/ASS"}}]}}'
config="$(jq -cn --arg reference "$PWD/reference.mkv" '{category:"mux",operations:["1"],removed_ids:["1"],order:"",order_ids:[],metadata:"",settings:{},expected_types:{"1":"subtitles"},extract_ids:[],reference:$reference,reference_track_count:2,removal_signatures:{"1":{type:"subtitles",codec_id:"S_TEXT/ASS"}}}')"
for invalid in 'null' '""' '17'; do
  unusable="$(jq --argjson invalid "$invalid" '.model.tracks[1].properties.codec_id=$invalid' <<< "$reference")"
  reject mkvutil_removal_signatures "$unusable" 1
  broken="$(jq --argjson invalid "$invalid" '.removal_signatures["1"].codec_id=$invalid' <<< "$config")"
  reject mkvutil_validate_config "$broken"
done
''', {})


def test_mkv_utils_removal_track_count_guard_and_bypass(env):
    reference = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True),
                              (11, "audio", "A_AAC", False),
                              (12, "subtitles", "S_TEXT/ASS", False)])
    fewer = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True),
                          (11, "audio", "A_AAC", False)])
    extra = json.loads(json.dumps(reference))
    extra["tracks"].append(_source_json([(99, "audio", "A_OPUS", True)])["tracks"][0])
    wrong_codec = json.loads(json.dumps(fewer))
    wrong_codec["tracks"][0]["properties"]["codec_id"] = "V_MPEGH/ISO/HEVC"
    wrong_type = json.loads(json.dumps(fewer))
    wrong_type["tracks"][0]["type"] = "audio"
    missing_target = _source_json([(11, "audio", "A_AAC", False),
                                   (12, "subtitles", "S_TEXT/ASS", False)])
    sources = {
        str(_mkv_file(env, "reference.mkv")): reference,
        str(_mkv_file(env, "fewer.mkv")): fewer,
        str(_mkv_file(env, "extra.mkv")): extra,
        str(_mkv_file(env, "wrong-codec.mkv")): wrong_codec,
        str(_mkv_file(env, "wrong-type.mkv")): wrong_type,
        str(_mkv_file(env, "missing-target.mkv")): missing_target,
    }
    result = _run_planning_contract(env, r'''
reference="$(mkvutil_capture_source "$PWD/reference.mkv")"
fewer="$(mkvutil_capture_source "$PWD/fewer.mkv")"
extra="$(mkvutil_capture_source "$PWD/extra.mkv")"
wrong_codec="$(mkvutil_capture_source "$PWD/wrong-codec.mkv")"
wrong_type="$(mkvutil_capture_source "$PWD/wrong-type.mkv")"
missing_target="$(mkvutil_capture_source "$PWD/missing-target.mkv")"
signatures="$(mkvutil_removal_signatures "$reference" 0)"
config="$(jq -cn --arg reference "$PWD/reference.mkv" --argjson signatures "$signatures" '{category:"mux",operations:["1"],removed_ids:["0"],order:"",order_ids:[],metadata:"",settings:{},expected_types:{"0":"video"},extract_ids:[],reference:$reference,reference_track_count:3,removal_signatures:$signatures}')"
job="$(mkvutil_plan_job "$reference" "$config")"
reference_job="$job"
eq "$(jq -r '.config.bypass_track_count // false' <<< "$job")" false 'count bypass defaults off'
for record in "$fewer" "$extra"; do
  status_code=0
  receipt="$(mkvutil_plan_job "$record" "$config")" || status_code=$?
  eq "$status_code" 3 'count-only difference skips complete job'
  eq "$(jq -r '.reasons|length' <<< "$receipt")" 0 'count-only difference has no fabricated ID reason'
  eq "$(jq -r '.track_count_mismatch.expected' <<< "$receipt")" 3 'reference track count'
  [[ "$record" != "$fewer" ]] || count_receipt="$receipt"
done
bypass="$(jq '.bypass_track_count=true' <<< "$config")"
for record in "$fewer" "$extra"; do
  job="$(mkvutil_plan_job "$record" "$bypass")"
  eq "$(jq -r '.config.bypass_track_count' <<< "$job")" true 'bypass retained in plan'
  [[ "$record" != "$fewer" ]] || fewer_job="$job"
done
unsafe="$(jq --arg protected "$PWD/reference.mkv" '.outputs=[$protected]' <<< "$fewer_job")"
reject mkvutil_check_destinations "$reference_job" "$unsafe"
for record in "$wrong_codec" "$wrong_type" "$missing_target"; do
  status_code=0
  receipt="$(mkvutil_plan_job "$record" "$bypass")" || status_code=$?
  eq "$status_code" 3 'bypass does not suppress signature mismatch'
  (( $(jq '.reasons|length' <<< "$receipt") > 0 )) || fail 'bypass erased per-ID mismatch'
done
reject mkvutil_validate_config "$(jq 'del(.reference_track_count)' <<< "$config")"
reject mkvutil_validate_config "$(jq '.reference_track_count=0' <<< "$config")"
reject mkvutil_validate_config "$(jq '.reference_track_count=0.5' <<< "$config")"
reject mkvutil_validate_config "$(jq '.reference_track_count="3"' <<< "$config")"
reject mkvutil_validate_config "$(jq '.removed_ids=["0","11"]|.expected_types["11"]="audio"|.removal_signatures["11"]={type:"audio",codec_id:"A_AAC"}|.reference_track_count=1' <<< "$config")"
reject mkvutil_validate_config "$(jq '.bypass_track_count="true"' <<< "$config")"
nonremoval="$(jq 'del(.reference_track_count,.bypass_track_count)|.removed_ids=[]|.operations=["2"]|.order=""|.order_ids=[]' <<< "$config")"
mkvutil_validate_config "$nonremoval" || fail 'reorder-only config requires removal count'
# A count-only receipt has no per-ID reasons and remains a valid retry scope.
MKVUTIL_JOBS=(); MKVUTIL_REMOVAL_SKIPS=("$count_receipt")
mkvutil_prepare_skipped_subset
eq "${#MKVUTIL_SOURCES}" 1 'count-only skipped subset refreshed'
print -r -- 'removal track-count guard contracts passed'
''', sources)
    assert result.stdout.rstrip().endswith("removal track-count guard contracts passed")
    assert all(Path(filename).read_text() == "payload" for filename in sources)
    assert all("-J" in argv for argv in _command_argv(env, "mkvmerge"))
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")


def test_mkv_utils_all_removal_skips_and_fresh_subset_preparation(env: dict[str, Path]):
    models = _removal_models()
    names = ("reference", "codec", "kind", "missing")
    sources = {str(_mkv_file(env, f"{name}.mkv")): models[name] for name in names}
    result = _run_planning_contract(env, r'''
reference="$(mkvutil_capture_source "$PWD/reference.mkv")"
codec="$(mkvutil_capture_source "$PWD/codec.mkv")"
kind="$(mkvutil_capture_source "$PWD/kind.mkv")"
missing="$(mkvutil_capture_source "$PWD/missing.mkv")"
MKVUTIL_CONFIG="$(jq -cn --arg reference "$PWD/reference.mkv" --argjson signatures "$(mkvutil_removal_signatures "$reference" '1,2')" '{category:"mux",operations:["1"],removed_ids:["1","2"],order:"",order_ids:[],metadata:"4",settings:{"4:0":"old name"},expected_types:{"0":"audio","1":"subtitles","2":"audio"},extract_ids:[],reference:$reference,reference_track_count:3,removal_signatures:$signatures}')"
MKVUTIL_SOURCES=("$codec" "$kind" "$missing")
status_code=0
mkvutil_plan_queue || status_code=$?
eq "$status_code" 3 'all skipped status'
eq "${#MKVUTIL_JOBS}" 0 'all skipped has no jobs'
eq "${#MKVUTIL_SOURCES}" 3 'all skipped scope retained'
reject mkvutil_cancel_status
# EOF while changing settings must preserve unresolved receipts/status.
status_code=0
mkvutil_configure_category mux 1 < /dev/null || status_code=$?
eq "$status_code" 2 'all skipped reconfiguration EOF'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 3 'EOF retained skip report'
reject mkvutil_cancel_status
# Change readonly identification fixture between preparations. Fresh inspection
# must observe it instead of recycling the old records or metadata configuration.
python3 -c 'import json,sys; p=sys.argv[1]; d=json.load(open(p)); key=sys.argv[2]; d[key]["tracks"][0]["properties"]["track_name"]="Fresh name"; json.dump(d,open(p,"w"))' "$TEST_FAKE_MKVMERGE_JSON_BY_PATH" "$PWD/codec.mkv"
MKVUTIL_PROPEDIT_ARGS=(stale)
MKVUTIL_MERGE_METADATA_ARGS=(stale)
mkvutil_prepare_skipped_subset
eq "${#MKVUTIL_SOURCES}" 3 'fresh skipped scope count'
eq "${#MKVUTIL_REMOVAL_SKIP_HISTORY}" 3 'preparation-origin receipts retained'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 0 'fresh current skip list clear'
eq "$MKVUTIL_CONFIG" '' 'old configuration cleared'
(( ${#MKVUTIL_METADATA_SETTINGS}==0 && ${#MKVUTIL_PROPEDIT_ARGS}==0 && ${#MKVUTIL_MERGE_METADATA_ARGS}==0 )) || fail 'old metadata/argv survived'
eq "$(jq -r '.source' <<< "${MKVUTIL_SOURCES[1]}")" "$PWD/codec.mkv" 'new first valid reference'
eq "$(jq -r '.model.tracks[0].properties.track_name' <<< "${MKVUTIL_SOURCES[1]}")" 'Fresh name' 'reidentified skipped source'
for record in "${MKVUTIL_SOURCES[@]}"; do
  [[ "$(jq -r '.source' <<< "$record")" != "$PWD/reference.mkv" ]] || fail 'unskipped source entered subset'
done
mkvutil_configure_category mux 1 <<< $'1\n'
eq "$(jq -r '.removal_signatures["1"].codec_id' <<< "$MKVUTIL_CONFIG")" S_TEXT/UTF8 'fresh reference codec configured'
eq "$(jq -r '.settings|length' <<< "$MKVUTIL_CONFIG")" 0 'new config has no reused metadata'
print -r -- 'fresh subset contracts passed'
''', sources)
    assert result.stdout.rstrip().endswith("fresh subset contracts passed")
    assert not _command_argv(env, "fzf")
    # Four original inspections plus exactly the three skipped-source refreshes.
    assert len(_command_argv(env, "mkvmerge")) == 7


def test_mkv_utils_always_multi_selector_one_and_many(env: dict[str, Path]):
    first, second = _mkv_file(env, 'One $literal "name".mkv'), _mkv_file(env, "Two.mks")
    _set_fake_fzf_responses(env, [[str(first)], [str(first), str(second)], [str(second)]])
    _run_planning_contract(env, r'''
mkvutil_scan_files "$PWD"
for category in edit mux extract; do
  mkvutil_select_files < /dev/null
  case "$category" in
    mux) eq "${#MKVUTIL_SELECTED_FILES}" 2 'multi selection' ;;
    *) eq "${#MKVUTIL_SELECTED_FILES}" 1 'single selection' ;;
  esac
done
''', {})
    calls = _command_argv(env, "fzf")
    assert len(calls) == 3
    assert all("--multi" in call and "--read0" in call and "--print0" in call for call in calls)



def _executor_document():
    document = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (11, "audio", "A_PCM/INT/LIT", False), (12, "audio", "A_PCM/INT/LIT", True)])
    for position, track in enumerate(document["tracks"]):
        track["properties"]["uid"] = 18446744073709551000 + position
        track["properties"]["track_name"] = f"Original {position}"
    document["tracks"][0]["properties"]["stereo_mode"] = 1
    return document


def _run_executor_contract(env, body, manifest, *, fault="", expected_returncode=0):
    manifest_path = env["fake_state"] / "execution.json"
    manifest_path.write_text(json.dumps(manifest))
    transport_root = env["fake_state"] / "engine-transport"
    transport_root.mkdir(exist_ok=True)
    run_env = os.environ.copy()
    run_env.update({
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq",
        "TEST_REAL_PYTHON": sys.executable, "TEST_USE_REAL_JSON": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]), "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]), "TEST_FAKE_EXECUTION_JSON": str(manifest_path),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(transport_root),
    })
    if fault:
        fault_dir = env["fake_state"] / "faults"
        fault_dir.mkdir()
        (fault_dir / "sitecustomize.py").write_text(_EXECUTOR_FAULTS)
        run_env.update(PYTHONPATH=str(fault_dir), TEST_EXECUTOR_FAULT=fault)
    result = subprocess.run(
        ["/usr/local/bin/zsh", "-f", "-c", r'''
source "$1"
setopt errexit
fail() { print -u2 -r -- "executor contract failure: $1"; return 1; }
eq() { [[ "$1" == "$2" ]] || fail "$3: expected '$2', got '$1'"; }
_mkvutil_metadata_define 6 'Set commentary flag' track 'Commentary [0]: ' 0 boolean flag-commentary --commentary-flag '' flag_commentary ''
record="$(mkvutil_capture_source "$PWD/source.mk3d")"
config='{"category":"mux","operations":["1","2"],"removed_ids":["0"],"order":"0:12","order_ids":["12"],"metadata":"1-6","settings":{"1:11":"0","1:12":"0","2:11":"0","2:12":"0","3:11":"fr-CA","4:11":"@literal $cash: \"quote\"\n\n","5:info":"","6:11":"1"},"expected_types":{"0":"video","11":"audio","12":"audio"},"extract_ids":[]}'
config="$(jq --arg reference "$PWD/source.mk3d" --argjson signatures "$(mkvutil_removal_signatures "$record" 0)" '.+{reference:$reference,reference_track_count:3,removal_signatures:$signatures}' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
''' + body, "executor-contract", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, text=True, capture_output=True, timeout=35,
    )
    assert result.returncode == expected_returncode, result.stdout + result.stderr
    return result


def test_mkv_utils_native_renderer_sanitizes_paths_before_record_framing(tmp_path):
    source = Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
    support = subprocess.run(
        ["/usr/local/bin/zsh", "-f", "-c", 'source "$1"; _mkvutil_execution_support', "support", str(source)],
        capture_output=True, text=True, check=True, timeout=5,
    ).stdout
    control = tmp_path / "control"
    control.mkdir()
    script = tmp_path / "renderer_contract.py"
    script.write_text(support + r'''
source = os.path.abspath("/tmp/input/part\nname.mkv")
destination = os.path.abspath("/tmp/output\rname.mka")
source_bytes, destination_bytes = os.fsencode(source), os.fsencode(destination)
paths = [(source, "part-name.mkv"), (destination, "logical-output.mka")]
renderer = NativeOutputRenderer(paths)
assert renderer.feed(b"reading " + source_bytes[:9]) == b""
shown = renderer.feed(source_bytes[9:] + b"\ntrack-name=literal/with/slash\n")
assert shown == b"  reading part-name.mkv\n  track-name=literal/with/slash\n", shown
renderer = NativeOutputRenderer(paths)
assert renderer.feed(b"candidate: " + destination_bytes[:12]) == b""
assert renderer.finish() == b"  candidate: [path]\n"
renderer = NativeOutputRenderer(paths)
assert renderer.feed(b"selected " + destination_bytes + b"\r") == b"  selected logical-output.mka\r"
assert renderer.finish() == b"\n"
# CR progress records start a fresh display line; CRLF remains a single
# physical line break and must not gain an indentation-only line.
renderer = NativeOutputRenderer([])
progress = renderer.feed(b"first\rprogress\r\ncomplete\n") + renderer.finish()
assert progress == b"  first\r  progress\r\n  complete\n", progress
# Byte-sized chunks exercise UTF-8 boundaries and a shorter pathname which
# is also a prefix of the longer known pathname.
renderer = NativeOutputRenderer([("/tmp/字幕", "字幕"), ("/tmp/字幕-final.mkv", "字幕-final.mkv")])
raw = "open /tmp/字幕-final.mkv\rcomplete\n".encode()
shown = b"".join(renderer.feed(raw[index:index + 1]) for index in range(len(raw))) + renderer.finish()
assert shown == "  open 字幕-final.mkv\r  complete\n".encode(), shown
renderer = NativeOutputRenderer(native_display_paths([("/tmp/owned-stage/request.ass", "Episode - Track [3].ass")]))
assert renderer.feed(b"write /tmp/owned-stage/request.ass\n/tmp/owned-stage/mkvextract-123-temp-tta-0\n") == b"  write Episode - Track [3].ass\n  mkvextract-123-temp-tta-0\n"
stdout_renderer, stderr_renderer = NativeOutputRenderer([]), NativeOutputRenderer([])
first = stdout_renderer.feed(b"a" * 4095 + "字".encode())
middle = stderr_renderer.feed(b"ERR\n")
last = stdout_renderer.feed(b"\n") + stdout_renderer.finish()
assert first == b"  " + b"a" * 4095
assert (first + middle + last).decode() == "  " + "a" * 4095 + "  ERR\n字\n"
# Bounded forced fragments retain the UTF-8 boundary and must not introduce
# another indentation prefix inside the continuation of a logical line.
renderer = NativeOutputRenderer([])
chunked = b"x" * 5000
first = renderer.feed(chunked)
complete = first + renderer.finish()
assert first == b"  " + b"x" * 4096
assert complete == b"  " + chunked + b"\n", (len(first), complete[-16:])
assert complete.count(b"  ") == 1
read_fd, write_fd = os.pipe()
saved_read_fd = os.dup(read_fd)
os.close(read_fd)
os.dup2(write_fd, 3)
os.close(write_fd)
read_fd = saved_read_fd
source = os.path.abspath("/tmp/source/input\npart.mkv")
destination = os.path.abspath("/tmp/candidate/output\rpart.mka")
child = "import os,sys; a=os.fsencode(sys.argv[1]); b=os.fsencode(sys.argv[2]); os.write(1,b'OUT '+a); os.write(1,b'\\n'); os.write(2,b'ERR '+b+b'\\n')"
code, stdout, stderr = run([sys.executable, "-c", child, source, destination],
                           display_paths=[(source, "input.mkv"), (destination, "output.mka")])
assert code == 0
assert stdout == "OUT " + source + "\n", repr(stdout)
assert stderr == "ERR " + destination + "\n", repr(stderr)
finish_native_display()
os.close(3)
display = bytearray()
while True:
    chunk = os.read(read_fd, 65536)
    if not chunk:
        break
    display.extend(chunk)
assert bytes(display) == b"  OUT input.mkv\n  ERR output.mka\n", display
os.close(read_fd)
read_fd, write_fd = os.pipe()
writer = NativeDisplayWriter(fd=write_fd, max_chunks=2, chunk_size=4096)
for unused in range(256):
    writer.submit(b"x" * 4096)
started = time.monotonic()
writer.finish(timeout=0.25)
elapsed = time.monotonic() - started
assert elapsed < 0.6, elapsed
os.close(read_fd)
os.close(write_fd)
print("native renderer contracts passed")
''', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "mux", str(os.getpid()), str(control)],
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().endswith("native renderer contracts passed")


def test_mkv_utils_native_blocked_display_does_not_block_owned_shutdown(tmp_path):
    source = Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
    support = subprocess.run(
        ["/usr/local/bin/zsh", "-f", "-c", 'source "$1"; _mkvutil_execution_support', "support", str(source)],
        capture_output=True, text=True, check=True, timeout=5,
    ).stdout
    control = tmp_path / "control"
    control.mkdir()
    script = tmp_path / "blocked_display.py"
    script.write_text(support + r'''
read_fd, write_fd = os.pipe()
saved_read_fd = os.dup(read_fd)
os.close(read_fd)
os.set_blocking(write_fd, False)
try:
    while True: os.write(write_fd, b"x" * 4096)
except BlockingIOError:
    pass
os.set_blocking(write_fd, True)
os.dup2(write_fd, 3)
os.close(write_fd)
command = "import os,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); os.write(1,b'NATIVE HELD\\n'); time.sleep(20)"
try:
    run([sys.executable, "-c", command, os.path.join(control_dir, "native-pid")], display_paths=[])
except Interrupted:
    finish_native_display()
    print("STOPPED", native_stopped, child.returncode, flush=True)
else:
    raise AssertionError("Held native child was not interrupted")
''', encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(script), "mux", str(os.getpid()), str(control)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    import signal
    import time

    native_pid = None
    try:
        deadline = time.monotonic() + 5
        marker = control / "native-pid"
        while not marker.exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(0.01)
        assert marker.exists()
        native_pid = int(marker.read_text())
        # Let the snapshot reach a display pipe which has no reader, then ask
        # the actual ownership guard to terminate its native process group.
        time.sleep(0.2)
        started = time.monotonic()
        (control / "signal").write_text(str(signal.SIGTERM))
        stdout, stderr = process.communicate(timeout=5)
        assert time.monotonic() - started < 3, stdout + stderr
        assert process.returncode == 0 and "STOPPED True -15" in stdout, stdout + stderr
        with pytest.raises(ProcessLookupError):
            os.kill(native_pid, 0)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)
        if native_pid is not None:
            try:
                os.killpg(native_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


_EXECUTOR_FAULTS = r'''
import json, os, signal, subprocess
from pathlib import Path
fault = os.environ.get("TEST_EXECUTOR_FAULT")
replace, link, unlink = os.replace, os.link, os.unlink

def candidate(path):
    return Path(path).name.startswith("candidate.")

def patched_replace(src, dst, *args, **kwargs):
    if candidate(src):
        if fault == "publish_fail":
            raise PermissionError("injected before replacement")
        result = replace(src, dst, *args, **kwargs)
        if fault == "after_replace_interrupt":
            os.kill(os.getpid(), signal.SIGTERM)
        if fault == "after_replace_dest_change":
            Path(dst).unlink()
            Path(dst).write_bytes(b"other writer")
        return result
    result = replace(src, dst, *args, **kwargs)
    if Path(dst).name == "phase.json":
        record = json.loads(Path(dst).read_text())
        if record["phase"] == "validated" and fault == "candidate_change":
            with Path(record["candidate_path"]).open("ab") as stream:
                stream.write(b"changed after validation")
        if record["phase"] == "published_complete" and fault == "after_unlink_dest_change":
            Path(record["destination"]).unlink()
            Path(record["destination"]).write_bytes(b"other writer")
    return result

def patched_link(src, dst, *args, **kwargs):
    if fault == "unsupported_links":
        raise OSError("injected filesystem without links")
    if candidate(src) and fault == "publish_fail":
        raise PermissionError("injected before link")
    result = link(src, dst, *args, **kwargs)
    if candidate(src) and fault == "after_link_interrupt":
        os.kill(os.getpid(), signal.SIGTERM)
    return result

def patched_unlink(path, *args, **kwargs):
    if Path(path).name == "source.mk3d" and fault == "unlink_fail":
        raise PermissionError("injected old-source cleanup failure")
    return unlink(path, *args, **kwargs)
os.replace, os.link, os.unlink = patched_replace, patched_link, patched_unlink
if fault in ("pre_admission_int", "parent_loss"):
    original_popen = subprocess.Popen
    class AcquisitionSignal(original_popen):
        def __init__(self, argv, *args, **kwargs):
            super().__init__(argv, *args, **kwargs)
            if argv[0] == "mkvextract" and argv[-1] == "tags":
                if fault == "pre_admission_int":os.kill(os.getpid(), signal.SIGINT)
            if fault == "parent_loss" and argv[0] == "mkvmerge" and "-o" in argv:
                Path(os.environ["TEST_FAKE_STATE_DIR"], "lost-owner-pids").write_text(json.dumps([os.getpid(),self.pid]))
                os.kill(os.getppid(), signal.SIGKILL)
    subprocess.Popen = AcquisitionSignal
'''


def _executor_manifest(env, *, converted=True):
    source = _mkv_file(env, "source.mk3d")
    original = _executor_document()
    output = json.loads(json.dumps(original))
    tracks = {track["id"]: track for track in output["tracks"]}
    output["tracks"] = [tracks[12], tracks[11]] if converted else output["tracks"]
    for track in output["tracks"]:
        if track["id"] in (11, 12):
            track["properties"].update(default_track=False, forced_track=False)
    tracks[11]["properties"].update(language="fre", language_ietf="fr-CA", track_name='@literal $cash: "quote"\n\n', flag_commentary=True)
    output["container"]["properties"]["title"] = ""
    return source, {"sources": {str(source): original}, "stage": {str(source): output}, "post_edit": {str(source): output}}


def test_mkv_utils_executor_grouped_edit_and_literal_observation(env):
    source, manifest = _executor_manifest(env, converted=False)
    _run_executor_contract(env, r'''
config="$(jq '.category="edit"|.operations=["1","2","3","4","5","6"]|.removed_ids=[]|.order=""|.order_ids=[]' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
mkvutil_execute_edit_job "$job"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" success 'Edit status'
eq "$(jq -r '.applied_metadata["6:11"]' <<< "$MKVUTIL_RESULT_JSON")" true 'generic sixth validation'
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    calls = _command_argv(env, "mkvpropedit")
    assert len(calls) == 1 and calls[0][0] == str(source)
    assert calls[0].count("--edit") == 3
    assert 'name=@literal $cash: "quote"\n\n' in calls[0]
    assert calls[0][-4:] == ["--edit", "info", "--delete", "title"]
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))


def test_mkv_utils_executor_two_file_edit_keeps_source_selectors_and_properties(env):
    first, manifest = _executor_manifest(env, converted=False)
    second = _mkv_file(env, "Second source.mk3d")
    original = json.loads(json.dumps(manifest["sources"][str(first)]))
    # Original ID 11 is listing position 2 in the first file and 3 in the
    # second. Untargeted flags and names also differ between the two inputs.
    original["tracks"] = [original["tracks"][2], original["tracks"][0], original["tracks"][1]]
    original["tracks"][2]["properties"].update(default_track=True, forced_track=True)
    original["tracks"][0]["properties"]["track_name"] = "Second untouched name"
    manifest["sources"][str(second)] = original
    literal = '@literal $cash: "quote"\n\n'
    for source in (first, second):
        actual = json.loads(json.dumps(manifest["sources"][str(source)]))
        for track in actual["tracks"]:
            if track["id"] == 11:
                track["properties"].update(forced_track=False, track_name=literal)
            if track["id"] == 12:
                track["properties"]["default_track"] = True
        actual["container"]["properties"]["title"] = ""
        manifest["post_edit"][str(source)] = actual
    result = _run_executor_contract(env, r'''
config="$(jq '.category="edit"|.operations=["1","2","4","5"]|.metadata="1,2,4,5"|.removed_ids=[]|.order=""|.order_ids=[]|.settings={"1:11":"0","2:12":"1","4:11":"@literal $cash: \"quote\"\n\n","5:info":""}' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
second="$(mkvutil_capture_source "$PWD/Second source.mk3d")"
secondjob="$(mkvutil_plan_job "$second" "$config")"
mkvutil_execute_queue "$job" "$secondjob"
eq "${#MKVUTIL_RESULTS}" 2 'both Edit sources completed'
for result in "${MKVUTIL_RESULTS[@]}"; do
  eq "$(jq -r '.status' <<< "$result")" success 'per-file Edit result'
  eq "$(jq -r '.applied_metadata|all(.==true)' <<< "$result")" true 'all grouped fields observed'
  print -r -- "$result"
done
''', manifest)
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert [record["source"] for record in records] == [str(first), str(second)]
    assert [record["actual_state"] for record in records] == ["edited_observed", "edited_observed"]
    assert "Processed In:" not in result.stdout
    calls = _command_argv(env, "mkvpropedit")
    assert calls == [
        [str(first), "--normalize-language-ietf", "off", "--edit", "track:2",
         "--set", "flag-forced=0", "--set", f"name={literal}", "--edit", "track:3",
         "--set", "flag-default=1", "--edit", "info", "--delete", "title"],
        [str(second), "--normalize-language-ietf", "off", "--edit", "track:1",
         "--set", "flag-default=1", "--edit", "track:3", "--set", "flag-forced=0",
         "--set", f"name={literal}", "--edit", "info", "--delete", "title"],
    ]
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    # The retained-property oracle may read tags; it must not create sidecars.
    assert all(args[0] in (str(first), str(second)) and args[1:] == ["tags"]
               for args in _command_argv(env, "mkvextract"))
    assert first.read_bytes() == second.read_bytes() == b"edited-data\n"


def test_mkv_utils_executor_one_mux_validated_conversion(env):
    source, manifest = _executor_manifest(env)
    result = _run_executor_contract(env, r'''
mkvutil_execute_mux_job "$job"
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    record = json.loads(result.stdout)
    assert record["status"] == "success" and record["actual_state"] == "published_complete"
    assert record["publication_committed"] and record["source_unlinked"]
    assert record["candidate_path"] is None and not source.exists()
    assert source.with_suffix(".mka").read_bytes() == b"candidate-data\n"
    calls = [args for args in _command_argv(env, "mkvmerge") if "-o" in args]
    assert len(calls) == 1 and not _command_argv(env, "mkvpropedit")
    assert calls[0][-1] == str(source) and calls[0][calls[0].index("--title") + 1] == ""
    assert calls[0][calls[0].index("--track-order") + 1] == "0:12,0:11"
    assert not list(env["workdir"].glob(".mkvutil-*"))


def test_mkv_utils_stop_before_admission_and_retry_suffix(env):
    first, manifest = _executor_manifest(env)
    second = _mkv_file(env, "Retry later.mk3d")
    manifest["sources"][str(second)] = manifest["sources"][str(first)]
    result = _run_executor_contract(env, r'''
secondjob="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Retry later.mk3d")" "$config")"
mkvutil_ledger_reset "$PWD" "$PWD/source.mk3d" "$PWD/Retry later.mk3d"
# A retry candidate remains 'skipped' until it is actually processed.
later="$PWD/Retry later.mk3d"
MKVUTIL_LEDGER[$later]="$(jq '.status="skipped"' <<< "${MKVUTIL_LEDGER[$later]}")"
if mkvutil_execute_queue "$job" "$secondjob"; then fail 'accepted stopped queue'; fi
print -r -- "SUMMARY $(mkvutil_final_summary)"
''', manifest, fault="pre_admission_int")
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    batch = summary["batches"][0]
    assert batch["attempted"] == batch["completed"] == 0
    assert batch["stop"]["not_started_sources"] == [str(first), str(second)]
    assert summary["counts"]["not_attempted"] == 1 and summary["counts"]["skipped"] == 1
    assert first.read_bytes() == second.read_bytes() == b"payload"
    assert not [args for args in _command_argv(env, "mkvmerge") if "-o" in args]


def test_mkv_utils_stop_confirmation_handles_permission_race(tmp_path):
    source = Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
    support = subprocess.run(
        ["/usr/local/bin/zsh", "-f", "-c", 'source "$1"; _mkvutil_execution_support', "support", str(source)],
        capture_output=True, text=True, check=True, timeout=5,
    ).stdout
    control = tmp_path / "control"
    control.mkdir()
    checks = r'''
from types import SimpleNamespace
for persistent in (False, True):
    probes = []
    ticks = iter((0.0, 0.1, 0.6))
    time.monotonic = lambda: next(ticks)
    time.sleep = lambda seconds: None
    def probe(pid, signum):
        probes.append(signum)
        if signum == 0:
            if persistent or probes.count(0) == 1:
                raise PermissionError("transient process-group visibility")
            raise ProcessLookupError("owned group is gone")
    os.killpg = probe
    child = SimpleNamespace(pid=12345, communicate=lambda timeout: (b"", b""))
    native_stopped = False
    shutdown_error = ""
    cleaning_up = False
    stop_child()
    assert probes == [signal.SIGTERM, signal.SIGKILL, 0, 0], probes
    assert native_stopped is not persistent
    assert bool(shutdown_error) is persistent
print("bounded shutdown confirmation passed")
'''
    result = subprocess.run(
        [sys.executable, "-B", "-c", support + checks, "extract", str(os.getpid()), str(control)],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "bounded shutdown confirmation passed"


def test_mkv_utils_owner_loss_stops_engine_before_publication(env):
    import time
    first, manifest = _executor_manifest(env)
    _run_executor_contract(env, 'mkvutil_execute_mux_job "$job"', manifest,
                           fault="parent_loss", expected_returncode=-9)
    deadline = time.monotonic() + 5
    results = []
    while time.monotonic() < deadline:
        results = list((env["fake_state"] / "engine-transport").glob("*/result"))
        if results and results[0].stat().st_size: break
        time.sleep(0.02)
    assert len(results) == 1 and results[0].stat().st_size
    record = json.loads(results[0].read_text())
    assert record["status"] == "interrupted" and record["stop_signal"] == 1
    assert not record["publication_attempted"] and not record["publication_committed"]
    assert first.read_bytes() == b"payload" and not first.with_suffix(".mka").exists()
    pids = json.loads((env["fake_state"] / "lost-owner-pids").read_text())
    for pid in pids:
        while time.monotonic() < deadline:
            try: os.kill(pid, 0)
            except ProcessLookupError: break
            time.sleep(0.02)
        with pytest.raises(ProcessLookupError): os.kill(pid, 0)


@pytest.mark.parametrize("code", [1, 2])
def test_mkv_utils_executor_native_warning_error_candidate_and_edit_actual(env, code):
    source, manifest = _executor_manifest(env, converted=False)
    manifest.update(merge_code=code, edit_code=code)
    # One requested field failed while the other actual fields remain observable.
    manifest["post_edit"][str(source)]["tracks"][1]["properties"]["flag_commentary"] = False
    result = _run_executor_contract(env, r'''
if mkvutil_execute_mux_job "$job"; then fail 'accepted native nonzero'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
config="$(jq '.category="edit"|.operations=["1","2","3","4","5","6"]|.removed_ids=[]|.order=""|.order_ids=[]' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
if mkvutil_execute_edit_job "$job"; then fail 'accepted native nonzero Edit'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    mux, edit = [json.loads(line) for line in result.stdout.splitlines()]
    assert mux["status"] == edit["status"] == ("warning" if code == 1 else "failed")
    assert mux["actual_state"] == "unpublished" and Path(mux["candidate_path"]).is_file()
    assert edit["edit_changed"] and edit["observed_metadata"]["6:11"] == {"flag_commentary": False}
    assert edit["applied_metadata"]["6:11"] is False and edit["applied_metadata"]["5:info"] is True
    assert not source.with_suffix(".mka").exists()


@pytest.mark.parametrize("case", ["invalid_output", "source_changed", "candidate_change", "publish_fail", "unsupported_links", "unlink_fail", "after_link_interrupt", "after_unlink_dest_change", "after_replace_interrupt", "after_replace_dest_change"])
def test_mkv_utils_executor_staging_publication_faults(env, case):
    same_name = case.startswith("after_replace")
    source, manifest = _executor_manifest(env, converted=not same_name)
    body = ""
    if same_name:
        body += 'config="$(jq \' .removed_ids=[] | .operations=["2"] \' <<< "$config")"\njob="$(mkvutil_plan_job "$record" "$config")"\n'
        manifest["stage"][str(source)]["tracks"] = [manifest["stage"][str(source)]["tracks"][2], manifest["stage"][str(source)]["tracks"][0], manifest["stage"][str(source)]["tracks"][1]]
    if case == "invalid_output":
        manifest["stage"][str(source)]["tracks"][0]["properties"]["codec_id"] = "A_WRONG"
    if case == "source_changed":
        manifest["source_change_on_merge"] = True
    result = _run_executor_contract(env, body + r'''
if mkvutil_execute_mux_job "$job"; then fail 'accepted injected failure'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest, fault="" if case in ("invalid_output", "source_changed") else case)
    record = json.loads(result.stdout)
    if case in ("after_link_interrupt", "after_replace_interrupt"):
        assert record["status"] == "interrupted"
        assert record["actual_state"] in ("published_source_retained", "replaced_complete")
    elif case in ("after_replace_dest_change", "after_unlink_dest_change"):
        assert record["status"] == "partial" and record["actual_state"] == "published_destination_changed"
        assert record["publication_committed"]
    elif case == "unlink_fail":
        assert record["status"] == "partial" and record["actual_state"] == "published_source_retained"
        assert source.exists() and source.with_suffix(".mka").exists()
    else:
        assert record["status"] == "failed" and record["actual_state"] == "unpublished"
        assert source.exists() and not source.with_suffix(".mka").exists()
    if case == "unsupported_links":
        assert not any("-o" in args for args in _command_argv(env, "mkvmerge"))
    if case in ("candidate_change", "source_changed", "invalid_output"):
        assert not record["publication_committed"]
    assert not _command_argv(env, "mkvpropedit")


def test_mkv_utils_executor_preflight_skip_wildcard_collision_and_empty_result(env):
    source, manifest = _executor_manifest(env)
    result = _run_executor_contract(env, r'''
# A changed source listing keeps file identity but fails the shared signature guard.
"$TEST_REAL_PYTHON" -c 'import json,os; p=os.environ["TEST_FAKE_EXECUTION_JSON"]; m=json.load(open(p)); m["sources"][os.getcwd()+"/source.mk3d"]["tracks"][0]["properties"]["codec_id"]="V_WRONG"; json.dump(m,open(p,"w"))'
if mkvutil_execute_mux_job "$job"; then fail 'accepted late mismatch'; fi
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" skipped 'late signature skip'
print -r -- "$MKVUTIL_RESULT_JSON"
"$TEST_REAL_PYTHON" -c 'import json,os; p=os.environ["TEST_FAKE_EXECUTION_JSON"]; m=json.load(open(p)); m["sources"][os.getcwd()+"/source.mk3d"]["tracks"][0]["properties"]["codec_id"]="V_MPEG4/ISO/AVC"; m["tags_default"]="<Tags><Tag><Targets><TrackUID>0</TrackUID></Targets><Simple><Name>USER</Name><String>  payload  </String></Simple></Tag></Tags>"; json.dump(m,open(p,"w"))'
if mkvutil_execute_mux_job "$job"; then fail 'accepted wildcard loss'; fi
eq "$(jq -r '.phase' <<< "$MKVUTIL_RESULT_JSON")" preflight 'wildcard early refusal'
print -r -- "$MKVUTIL_RESULT_JSON"
"$TEST_REAL_PYTHON" -c 'import json,os; p=os.environ["TEST_FAKE_EXECUTION_JSON"]; m=json.load(open(p)); m["tags_default"]="<Tags/>"; json.dump(m,open(p,"w"))'
ln -s nonexistent "$PWD/source.mka"
if mkvutil_execute_mux_job "$job"; then fail 'accepted dangling symlink collision'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
_mkvutil_execution_engine() { return 1; }
config="$(jq '.category="edit"|.removed_ids=[]|.order_ids=[]|.order=""|.operations=["5"]|.settings={"5:info":""}|.metadata="5"' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
if mkvutil_execute_edit_job "$job"; then fail 'accepted empty engine response'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    skipped, wildcard, collision, unknown = [json.loads(line) for line in result.stdout.splitlines()]
    assert skipped["skip_receipt"]["source"] == str(source)
    assert "TrackUID=0" in wildcard["reason"] and str(source) in wildcard["reason"]
    assert "Destination exists" in collision["reason"]
    assert unknown["status"] == "interrupted" and unknown["actual_state"] == "unknown_inspect_filesystem"
    assert not list(env["workdir"].glob(".mkvutil-*"))
    assert not any("-o" in args for args in _command_argv(env, "mkvmerge"))
    assert not _command_argv(env, "mkvpropedit") and source.read_text() == "payload"


def test_mkv_utils_executor_preflight_track_count_change_skips_before_writer(env):
    source, manifest = _executor_manifest(env)
    result = _run_executor_contract(env, r'''
"$TEST_REAL_PYTHON" -c 'import copy,json,os; p=os.environ["TEST_FAKE_EXECUTION_JSON"]; m=json.load(open(p)); key=os.getcwd()+"/source.mk3d"; track=copy.deepcopy(m["sources"][key]["tracks"][0]); track["id"]=99; track["properties"]["id"]=99; track["properties"]["uid"]+=1; m["sources"][key]["tracks"].append(track); json.dump(m,open(p,"w"))'
if mkvutil_execute_mux_job "$job"; then fail 'accepted late track-count mismatch'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    record = json.loads(result.stdout)
    assert record["status"] == "skipped"
    assert record["skip_receipt"]["track_count_mismatch"] == {"expected": 3, "actual": 4}
    assert record["skip_receipt"]["reasons"] == []
    assert not [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    assert not _command_argv(env, "mkvpropedit")
    assert source.read_bytes() == b"payload" and not source.with_suffix(".mka").exists()


@pytest.mark.parametrize("category", ["edit", "mux"])
def test_mkv_utils_executor_native_signal_stops_queue(env, category):
    source, manifest = _executor_manifest(env, converted=False)
    manifest[f"{('merge' if category == 'mux' else 'edit')}_code"] = -15
    second = _mkv_file(env, "second.mk3d")
    manifest["sources"][str(second)] = _executor_document()
    result = _run_executor_contract(env, r'''
if [[ "$TEST_CATEGORY" == edit ]]; then
  config="$(jq '.category="edit"|.operations=["1","2","3","4","5","6"]|.removed_ids=[]|.order=""|.order_ids=[]' <<< "$config")"
  job="$(mkvutil_plan_job "$record" "$config")"
fi
second="$(mkvutil_capture_source "$PWD/second.mk3d")"
secondjob="$(mkvutil_plan_job "$second" "$config")"
if mkvutil_execute_queue "$job" "$secondjob"; then fail 'accepted signal termination'; fi
eq "${#MKVUTIL_RESULTS}" 1 'queue stop after signal'
eq "$(jq -r '.status' <<< "${MKVUTIL_RESULTS[1]}")" interrupted 'native signal result'
'''.replace('"$TEST_CATEGORY"', f'"{category}"'), manifest)
    assert "interrupted:" in result.stdout
    modifiers = _command_argv(env, "mkvpropedit") + [args for args in _command_argv(env, "mkvmerge") if "-o" in args]
    assert len(modifiers) == 1 and str(second) not in modifiers[0]
    assert second.read_text() == "payload"



def test_mkv_utils_executor_shared_native_language_pair_and_unknown_rewrite(env):
    source, manifest = _executor_manifest(env, converted=False)
    actual = manifest["post_edit"][str(source)]
    actual["tracks"][1]["properties"].update(language="und", language_ietf="tlh")
    actual["tracks"][2]["properties"].update(language="und", language_ietf="x-custom")
    result = _run_executor_contract(env, r'''
config="$(jq '.category="edit"|.operations=["1","2","3","4","5","6"]|.metadata="1-6"|.removed_ids=[]|.order=""|.order_ids=[]|.settings={"3:11":"i-klingon","3:12":"x-custom","1:11":"0","1:12":"0","2:11":"0","2:12":"0","4:11":"@literal $cash: \"quote\"\n\n","5:info":"","6:11":"1"}' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
mkvutil_execute_edit_job "$job"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" success 'verified language equivalence'
record="$(mkvutil_capture_source "$PWD/source.mk3d")"
config="$(jq '.settings["3:11"]="i-lux"' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
if mkvutil_execute_edit_job "$job"; then fail 'accepted unproven language rewrite'; fi
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    assert json.loads(result.stdout)["validation_ok"] is False


@pytest.mark.parametrize("ambiguous", [False, True])
def test_mkv_utils_executor_regenerated_uid_mapping_evidence(env, ambiguous):
    source, manifest = _executor_manifest(env)
    for track in manifest["stage"][str(source)]["tracks"]:
        track["properties"]["uid"] += 2000
    body = ""
    if ambiguous:
        for track in manifest["sources"][str(source)]["tracks"][1:]:
            track["properties"]["track_name"] = "identical"
        for track in manifest["stage"][str(source)]["tracks"]:
            track["properties"].update(track_name="new", language="fre", language_ietf="fr-CA", flag_commentary=True)
        body += 'config="$(jq \'.settings["4:11"]="new"|.settings["4:12"]="new"|.settings["3:12"]="fr-CA"|.settings["6:12"]="1"\' <<< "$config")"\njob="$(mkvutil_plan_job "$record" "$config")"\n'
    result = _run_executor_contract(env, body + r'''
code=0
mkvutil_execute_mux_job "$job" || code=$?
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    result = json.loads(result.stdout)
    if ambiguous:
        assert result["status"] == "failed" and "mapping ambiguous" in result["reason"]
        assert source.exists() and not result["publication_committed"]
    else:
        assert result["status"] == "success"
        assert "unique unchanged properties" in result["validation_notes"][0]

def test_mkv_utils_executor_large_records_and_independent_queue_outcomes(env):
    source, manifest = _executor_manifest(env)
    # A single identification record crosses typical per-argv limits; planning
    # and execution must stream it. Unique UIDs retain exact 64-bit evidence.
    padding = "p" * 160_000
    manifest["sources"][str(source)]["container"]["properties"]["private_fixture"] = padding
    for name in ("bad-stage.mk3d", "successful.mk3d"):
        path = _mkv_file(env, name)
        manifest["sources"][str(path)] = json.loads(json.dumps(manifest["sources"][str(source)]))
        manifest["stage"][str(path)] = json.loads(json.dumps(manifest["stage"][str(source)]))
    bad = str(env["workdir"] / "bad-stage.mk3d")
    manifest["stage"][bad]["tracks"][0]["properties"]["codec_id"] = "A_WRONG"
    result = _run_executor_contract(env, r'''
second="$(mkvutil_capture_source "$PWD/bad-stage.mk3d")"
secondjob="$(mkvutil_plan_job "$second" "$config")"
third="$(mkvutil_capture_source "$PWD/successful.mk3d")"
thirdjob="$(mkvutil_plan_job "$third" "$config")"
"$TEST_REAL_PYTHON" -c 'import json,os; p=os.environ["TEST_FAKE_EXECUTION_JSON"]; m=json.load(open(p)); m["sources"][os.getcwd()+"/source.mk3d"]["tracks"][0]["properties"]["codec_id"]="V_WRONG"; json.dump(m,open(p,"w"))'
if mkvutil_execute_queue "$job" "$secondjob" "$thirdjob"; then fail 'accepted incomplete queue'; fi
eq "${#MKVUTIL_RESULTS}" 3 'all independent jobs reported'
for record in "${MKVUTIL_RESULTS[@]}"; do print -r -- "$record"; done
''', manifest)
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert [record["status"] for record in records] == ["skipped", "failed", "success"]
    assert all(record["source"].startswith(str(env["workdir"])) for record in records)
    assert records[2]["elapsed_seconds"] >= 0
    assert len([args for args in _command_argv(env, "mkvmerge") if "-o" in args]) == 2
    assert not _command_argv(env, "mkvpropedit")
    assert source.read_text() == "payload"
    assert Path(bad).read_text() == "payload"
    assert not (env["workdir"] / "successful.mk3d").exists()



def test_mkv_utils_extract_planner_native_codec_families_and_shared_collection(env):
    model = _source_json([(0,"audio","A_FLAC",False),(1,"audio","A_PCM/INT/LIT",False),(2,"audio","A_TRUEHD",False),(3,"subtitles","S_VOBSUB",False),(4,"audio","A_WAVPACK4",False)], attachments=[{"id":1,"file_name":"Font.ttf","size":2},{"id":2,"file_name":"Font.ttf","size":3}])
    sources={str(_mkv_file(env,"Format."+ext)):model for ext in ("mkv","mka","mks","mk3d")}
    collection=env["workdir"] / "Attachments";collection.mkdir();existing=collection/"Font.ttf";existing.write_bytes(b"older")
    result=_run_planning_contract(env,r'''
config='{"category":"extract","operations":["1","2"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{},"expected_types":{"0":"audio","1":"audio","2":"audio","3":"subtitles","4":"audio"},"extract_ids":["0","1","2","3","4"]}'
MKVUTIL_CODEC_EXT_JSON='{"PCM":"wav","TRUEHD":"thd","FLAC":"flac","VOBSUB":"sub","WAVPACK4":"wv"}'
typeset -a jobs=()
for ext in mkv mka mks mk3d; do
  record="$(mkvutil_capture_source "$PWD/Format.$ext")"
  job="$(mkvutil_plan_job "$record" "$config")"
  print -r -- "JOB $job"
  jobs+=("$job")
  mkvutil_check_destinations "$job"
done
# Different containers share the collection. Their track base names are equal,
# so remove tracks here to isolate permitted attachment-overwrite collisions.
for ((i=1;i<=${#jobs};i++));do jobs[$i]="$(jq -c '.outputs|=map(select(.kind=="attachment"))' <<< "${jobs[$i]}")";done
mkvutil_check_destinations "${jobs[@]}"
# Protected companions are reserved even when correction output is optional.
record="$(mkvutil_capture_source "$PWD/Format.mkv")"
job="$(mkvutil_plan_job "$record" "$config")"
optional="$(jq -r '.outputs[]|.artifacts[]|select(.role=="wavpack_correction")|.path' <<< "$job")"
print -r -- existing > "$optional"
reject mkvutil_check_destinations "$job"
# Attachment-vs-track aliases cannot use the attachment overwrite exception.
conflict="$(jq --arg path "$PWD/Attachments/Font.ttf" '.outputs=[.outputs[0],.outputs[5]]|.outputs[1].artifacts[1].path=$path' <<< "$job")"
reject mkvutil_check_destinations "$conflict"
# Existing regular collections must also not alias any selected input inode.
python3 -c 'import os,sys;os.link(sys.argv[1],sys.argv[2])' "$PWD/Format.mkv" "$PWD/Attachments/Input.mkv"
aliasjob="$(jq --arg path "$PWD/Attachments/Input.mkv" '.outputs=[.outputs[0]]|.outputs[0].path=$path|.outputs[0].artifacts[0].path=$path' <<< "$job")"
reject mkvutil_check_destinations "$aliasjob"
''',sources)
    jobs=[json.loads(line[4:]) for line in result.stdout.splitlines() if line.startswith("JOB ")]
    assert len(jobs)==4
    for job in jobs:
        assert len(job["outputs"])==7
        assert [Path(out["path"]).suffix for out in job["outputs"][2:]]==[".flac",".wav",".thd",".sub",".wv"]
        assert all(out["path"]==str(existing) for out in job["outputs"][:2])
        assert [out["expected_size"] for out in job["outputs"][:2]]==[2,3]
        assert [a["role"] for a in job["outputs"][5]["artifacts"]]==["vobsub_data","vobsub_index"]
        assert all(a["required"] for a in job["outputs"][5]["artifacts"])
        assert job["outputs"][6]["artifacts"][1]["path"].endswith(".wvc") and not job["outputs"][6]["artifacts"][1]["required"]
    assert existing.read_bytes()==b"older" and all(Path(p).read_text()=="payload" for p in sources)

def _run_extract_contract(env, body, manifest, *, fault=""):
    # Keep manifests outside state reset by actual entrypoint tests.
    manifest_path = env["workdir"].parent / "extraction.json"
    manifest_path.write_text(json.dumps(manifest))
    run_env = os.environ.copy()
    run_env.update({
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq", "TEST_REAL_PYTHON": sys.executable,
        "TEST_USE_REAL_JSON": "1", "TEST_COMMAND_LOG": str(env["command_log"]),
        "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]), "TEST_FAKE_STATE_DIR": str(env["fake_state"]),
        "TEST_FAKE_EXECUTION_JSON": str(manifest_path), "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_EXTRACTION_CWD_LOG": str(env["workdir"].parent / "cwd.jsonl"),
    })
    if fault:
        fault_dir = env["workdir"].parent / "extract-faults"
        fault_dir.mkdir()
        (fault_dir / "sitecustomize.py").write_text(_EXTRACT_FAULTS)
        run_env.update(PYTHONPATH=str(fault_dir), TEST_EXTRACT_FAULT=fault)
    result = subprocess.run(
        ["/usr/local/bin/zsh", "-f", "-c", r'''
source "$1"
setopt errexit
fail() { print -u2 -r -- "Extract contract failure: $1"; return 1; }
eq() { [[ "$1" == "$2" ]] || fail "$3: expected '$2', got '$1'"; }
reject() { if "$@"; then fail "accepted invalid call: $*"; fi; }
MKVUTIL_CODEC_EXT_JSON='{"VOBSUB":"sub","WAVPACK4":"wv","UTF8":"srt","TTA1":"tta"}'
config='{"category":"extract","operations":["1","2"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{},"expected_types":{"0":"subtitles","1":"audio","2":"subtitles","3":"audio"},"extract_ids":["0","1","2","3"]}'
''' + body, "extract-contract", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, text=True, capture_output=True, timeout=35,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not _command_argv(env, "mkvpropedit")
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    return result


_EXTRACT_FAULTS = r'''
import json, os, signal, subprocess, sys
from pathlib import Path
fault=os.environ.get("TEST_EXTRACT_FAULT", "")
replace,link,rmdir=os.replace,os.link,os.rmdir
def patched_replace(src,dst,*args,**kwargs):
    staged=Path(src).name.startswith("attachments-")
    if staged and fault=="second_attachment_fail" and Path(src).name.startswith("attachments-000001"):
        raise PermissionError("injected second attachment publication failure")
    value=replace(src,dst,*args,**kwargs)
    if staged and fault=="after_replace_interrupt":os.kill(os.getpid(),signal.SIGINT)
    if staged and fault=="after_replace_changed":
        Path(dst).write_bytes(b"other writer")
        raise RuntimeError("injected changed destination after replacement")
    return value
def patched_link(src,dst,*args,**kwargs):
    if Path(src).name.startswith("tracks-") and fault=="second_vobsub_fail" and Path(src).suffix==".idx":
        raise PermissionError("injected index publication failure")
    return link(src,dst,*args,**kwargs)
def patched_rmdir(path,*args,**kwargs):
    target=Path(path)
    if fault=="late_cleanup_fail" and target.name.startswith(".mkvutil-extract-") and target.parent.name!="Attachments":
        raise PermissionError(f"injected late cleanup failure: {path}")
    return rmdir(path,*args,**kwargs)
os.replace,os.link,os.rmdir=patched_replace,patched_link,patched_rmdir
if fault in ("shutdown_probe_transient", "shutdown_probe_denied"):
    original_killpg = os.killpg
    denied_probes = 0
    def permission_probe(pid, signum):
        global denied_probes
        if signum == 0 and getattr(sys.modules["__main__"], "cleaning_up", False):
            if fault == "shutdown_probe_denied" or denied_probes == 0:
                denied_probes += 1
                raise PermissionError("injected shutdown confirmation denial")
        return original_killpg(pid, signum)
    os.killpg = permission_probe
if fault == "late_recovery_int":
    original_iterdir = Path.iterdir
    recovery_signalled = False
    def recovery_iterdir(path):
        global recovery_signalled
        if not recovery_signalled and path.name.startswith(".mkvutil-extract-") and getattr(sys.modules["__main__"], "cleaning_up", False):
            recovery_signalled = True
            os.kill(os.getpid(), signal.SIGINT)
        return original_iterdir(path)
    Path.iterdir = recovery_iterdir
if fault == "acquisition_int":
    original_popen = subprocess.Popen
    class AcquisitionSignal(original_popen):
        def __init__(self, argv, *args, **kwargs):
            super().__init__(argv, *args, **kwargs)
            self.is_track = argv[0] == "mkvextract" and argv[2] == "tracks"
            self.communications = 0
            if fault == "acquisition_int" and self.is_track:
                Path(os.environ["TEST_FAKE_STATE_DIR"], "acquired-pid").write_text(str(self.pid))
                os.kill(os.getpid(), signal.SIGINT)
    subprocess.Popen = AcquisitionSignal
'''


def _extract_manifest(env, names=("First source.mkv",)):
    model = _source_json([(0,"subtitles","S_VOBSUB",False),(1,"audio","A_WAVPACK4",False),
                          (2,"subtitles","S_TEXT/UTF8",False),(3,"audio","A_TTA1",False)],
                         attachments=[{"id":1,"file_name":"Font.ttf","size":2},
                                      {"id":2,"file_name":"Font.ttf","size":3},
                                      {"id":3,"file_name":"Empty.txt","size":0}])
    sources = {str(_mkv_file(env,name)): json.loads(json.dumps(model)) for name in names}
    extraction = {source: {
        "attachments":{"outputs":{"1":{"data":"AA"},"2":{"data":"BBB"},"3":{"data":""}}},
        "tracks":{"outputs":{"0":{"family":{".sub":"data",".idx":"index"}},
                              "1":{"family":{".wv":"wave",".wvc":"correction"}},
                              "2":{"data":""},"3":{"data":"tta"}},"scratch":True},
    } for source in sources}
    return {"sources":sources,"extraction":extraction}


def test_mkv_utils_extract_grouped_artifacts_overwrites_and_cwd(env):
    manifest = _extract_manifest(env, ("First source.mkv", "Second source.mka"))
    collection=env["workdir"] / "Attachments";collection.mkdir();(collection/"Font.ttf").write_bytes(b"existing")
    # Optional correction output is allowed to be absent in plain lossless.
    manifest["extraction"][str(env["workdir"]/"Second source.mka")]["tracks"]["outputs"]["1"]={"data":"wave"}
    result = _run_extract_contract(env,r'''
first="$(mkvutil_capture_source "$PWD/First source.mkv")"
second="$(mkvutil_capture_source "$PWD/Second source.mka")"
a="$(mkvutil_plan_job "$first" "$config")";b="$(mkvutil_plan_job "$second" "$config")"
mkvutil_check_destinations "$a" "$b"
mkvutil_execute_queue "$a" "$b"
for record in "${MKVUTIL_RESULTS[@]}";do print -r -- "RESULT $record";done
print -r -- "SUMMARY $(mkvutil_final_summary)"
mkvutil_final_report
''',manifest)
    records=[json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
    assert [r["status"] for r in records]==["success","success"]
    assert all([s["status"] for s in r["stages"]]==["complete","complete"] for r in records)
    assert all(r["track_stage_seconds"]>=0 and r["elapsed_seconds"]>=r["track_stage_seconds"] for r in records)
    assert all(not r["staged_paths"] and not r["phase_receipts"] for r in records)
    assert (collection/"Font.ttf").read_bytes()==b"BBB" and (collection/"Empty.txt").read_bytes()==b""
    summary=json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["counts"]["done"]==2
    assert (summary["attachments"]["processed"],summary["attachments"]["published"],summary["attachments"]["unique_names"],summary["attachments"]["superseded"],summary["attachments"]["uncertain_names"])==(6,6,2,4,0)
    winners=[r for r in summary["attachments"]["publications"] if r["outcome"]=="winner"]
    assert {r["id"] for r in winners}=={"2","3"} and all(r["source"].endswith("Second source.mka") for r in winners)
    calls=_command_argv(env,"mkvextract")
    assert [c[1] for c in calls]==["attachments","tracks","attachments","tracks"]
    assert all(len(c)==(5 if c[1]=="attachments" else 6) for c in calls)
    stages=[json.loads(line) for line in (env["workdir"].parent/"cwd.jsonl").read_text().splitlines()]
    assert all(Path(stage["cwd"]).name.startswith(".mkvutil-extract-") for stage in stages)
    assert len({spec.split(":",1)[1] for stage in stages for spec in stage["specs"]})==14
    assert all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])
    assert len(list(env["workdir"].glob("*.idx")))==2 and len(list(env["workdir"].glob("*.wvc")))==1
    assert len(list(env["workdir"].glob("*.srt")))==2 and all(p.stat().st_size==0 for p in env["workdir"].glob("*.srt"))


def test_mkv_utils_extract_warning_preserves_winner_and_track_timing(env):
    manifest=_extract_manifest(env,("First source.mkv","Later source.mks"))
    second=str(env["workdir"]/"Later source.mks");manifest["extraction"][second]["attachments"]["code"]=1
    result=_run_extract_contract(env,r'''
a="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
b="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Later source.mks")" "$config")"
reject mkvutil_execute_queue "$a" "$b"
for record in "${MKVUTIL_RESULTS[@]}";do print -r -- "RESULT $record";done
print -r -- "SUMMARY $(mkvutil_final_summary)"
''',manifest)
    records=[json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
    assert [r["status"] for r in records]==["success","warning"]
    warning=records[1]
    assert warning["stages"][1]==dict(kind="tracks",status="not_attempted",attempted=False,native_code=None,elapsed_seconds=None,validated_count=0)
    assert warning["track_stage_seconds"] is None and not warning["published_artifacts"] and len(warning["staged_paths"])==3
    summary=json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["batches"][0]["track_stages_attempted"]==1
    assert summary["attachments"]["uncertain_names"]==0 and summary["attachments"]["unique_names"]==2
    assert all(r["source"].endswith("First source.mkv") for r in summary["attachments"]["publications"] if r["outcome"]=="winner")
    assert "Track stage: not attempted" in result.stdout and len(_command_argv(env,"mkvextract"))==3
    assert (env["workdir"]/"Attachments"/"Font.ttf").read_bytes()==b"BBB"
    assert all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])


def test_mkv_utils_extract_duplicate_history_after_track_failure(env):
    manifest=_extract_manifest(env);source=next(iter(manifest["sources"]))
    manifest["extraction"][source]["tracks"]["code"]=2
    result=_run_extract_contract(env,r'''
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
reject mkvutil_execute_extract_job "$job"
print -r -- "RESULT $MKVUTIL_RESULT_JSON"
''',manifest)
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]=="partial" and record["native_code"]==2 and record["actual_state"]=="sidecars_published"
    assert len(record["published_artifacts"])==3 and not record["uncertain_artifacts"]
    assert all(a["publication_confirmed"] for a in record["published_artifacts"])
    assert record["stages"][0]["status"]=="complete" and record["stages"][1]["status"]=="failed"
    assert (env["workdir"]/"Attachments"/"Font.ttf").read_bytes()==b"BBB" and Path(source).read_bytes()==b"payload"
    assert len(record["staged_paths"])==6 and not list(env["workdir"].glob("*.sub"))


@pytest.mark.parametrize("fault,expected",[("second_attachment_fail","partial"),("after_replace_interrupt","interrupted"),("after_replace_changed","partial"),("second_vobsub_fail","partial")])
def test_mkv_utils_extract_publication_recovery(env,fault,expected):
    manifest=_extract_manifest(env);collection=env["workdir"]/"Attachments";collection.mkdir();(collection/"Font.ttf").write_bytes(b"previous")
    result=_run_extract_contract(env,r'''
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
reject mkvutil_execute_extract_job "$job"
print -r -- "RESULT $MKVUTIL_RESULT_JSON"
''',manifest,fault=fault)
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]==expected and record["staged_paths"] and record["phase_receipts"]
    if fault=="after_replace_changed":
        assert record["uncertain_artifacts"] and record["actual_state"]=="publication_uncertain"
        assert (collection/"Font.ttf").read_bytes()==b"other writer"
    else:
        assert not record["uncertain_artifacts"]
        assert (collection/"Font.ttf").read_bytes()==(b"BBB" if fault=="second_vobsub_fail" else b"AA")
        assert len(record["published_artifacts"])==(4 if fault=="second_vobsub_fail" else 1)
    if fault=="second_vobsub_fail":
        assert len(list(env["workdir"].glob("*.sub")))==1 and not list(env["workdir"].glob("*.idx"))
    else:
        assert len(_command_argv(env,"mkvextract"))==1
        assert record["track_stage_seconds"] is None
    for path in manifest["sources"]:assert Path(path).read_bytes()==b"payload"
    receipt=json.loads(Path(record["phase_receipts"][0]).read_text())
    assert any(a["publication_attempted"] and a["stage_identity"] and a["previous_identity"] for a in receipt["artifacts"])


def test_mkv_utils_extract_symlink_parent_zero_outputs_and_interruption(env):
    manifest=_extract_manifest(env,("First source.mk3d","Pending.mkv"))
    target=env["workdir"].parent/"resolved collection";target.mkdir();(env["workdir"]/"Attachments").symlink_to(target,target_is_directory=True)
    source=str(env["workdir"]/"First source.mk3d");manifest["extraction"][source]["attachments"]["code"]=-15
    result=_run_extract_contract(env,r'''
a="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mk3d")" "$config")"
b="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Pending.mkv")" "$config")"
empty="$(jq '.outputs=[]' <<< "$a")"
mkvutil_execute_extract_job "$empty"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" success 'zero output success'
reject mkvutil_execute_queue "$a" "$b"
print -r -- "SUMMARY $(mkvutil_final_summary)"
print -r -- "RESULT ${MKVUTIL_RESULTS[1]}"
''',manifest)
    summary=json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["counts"]["interrupted"]==1 and summary["counts"]["not_attempted"]==1
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]=="interrupted" and not record["published_artifacts"]
    assert all(Path(p).parent==target for p in record["staging_directories"])
    assert "Track stage: not attempted" in result.stdout and "unavailable (no track stages attempted)" in result.stdout
    _ascii_box_contains(result.stdout, "File progress", "Track stage: not attempted", "Estimated Time Remaining: unavailable (no track stages attempted)")
    assert len(_command_argv(env,"mkvextract"))==1
    assert all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])


def test_mkv_utils_extract_engine_signal_inventories_owned_candidates(env):
    manifest=_extract_manifest(env,("First source.mkv","Pending.mka"))
    source=str(env["workdir"]/"First source.mkv")
    manifest["extraction"][source]["tracks"].update(signal_engine=True,unexpected="unexpected.bin")
    result=_run_extract_contract(env,r'''
a="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
b="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Pending.mka")" "$config")"
reject mkvutil_execute_queue "$a" "$b"
print -r -- "RESULT ${MKVUTIL_RESULTS[1]}"
print -r -- "SUMMARY $(mkvutil_final_summary)"
''',manifest)
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]=="interrupted" and record["stages"][1]["native_code"] is None
    assert record["stages"][1]["status"]=="interrupted"
    assert record["stages"][1]["attempted"] and record["track_stage_seconds"]>=0
    assert len(record["scratch_paths"])==1 and len(record["unexpected_paths"])==1
    assert all(Path(p).is_file() for p in record["scratch_paths"]+record["unexpected_paths"])
    assert len(record["staged_paths"])==6 and len(record["published_artifacts"])==3
    assert all(a["stage_identity"] for a in record["artifacts"] if a["present"])
    summary=json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["interrupted"] and summary["counts"]["not_attempted"]==1
    assert len(_command_argv(env,"mkvextract"))==2 and all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])
    assert "Processed In:" in result.stdout  # An actual interrupted track attempt is a timing sample.


@pytest.mark.parametrize("fault", ["acquisition_int", "late_recovery_int"])
def test_mkv_utils_extract_stop_acquisition_and_recovery_provenance(env, fault):
    manifest = _extract_manifest(env)
    if fault == "late_recovery_int":
        manifest["extraction"][str(env["workdir"] / "First source.mkv")]["tracks"]["code"] = 1
    result = _run_extract_contract(env, r'''
a="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
reject mkvutil_execute_extract_job "$a"
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest, fault=fault)
    record = json.loads(result.stdout)
    assert record["stop_signal"] == 2
    if fault == "acquisition_int":
        assert record["status"] == "interrupted"
        with pytest.raises(ProcessLookupError): os.kill(int((env["fake_state"] / "acquired-pid").read_text()), 0)
    else:
        assert record["status"] == "warning" and not record.get("discarded_partial_tracks")
        tracks = [a for a in record["artifacts"] if a["kind"] == "track"]
        assert len(tracks) == 6 and all(Path(a["stage_path"]).is_file() for a in tracks)


def test_mkv_utils_extract_leader_exit_stops_owned_descendant(env):
    manifest = _extract_manifest(env)
    tool = env["fake_bin"] / "mkvextract"
    anchor = 'code = stage.get("code", 0)'
    tool.write_text(tool.read_text().replace(anchor, '''if mode == "tracks":
    import subprocess
    pidfile = Path(os.environ["TEST_FAKE_STATE_DIR"], "descendant-pid")
    code = "import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(os.environ['TEST_FAKE_STATE_DIR'],'descendant-pid').write_text(str(os.getpid()));time.sleep(10)"
    subprocess.Popen([sys.executable,"-c",code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    deadline = time.monotonic()+1
    while not pidfile.exists() and time.monotonic()<deadline:time.sleep(0.01)
''' + anchor))
    result = _run_extract_contract(env, r'''
a="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
reject mkvutil_execute_extract_job "$a"
print -r -- "$MKVUTIL_RESULT_JSON"
''', manifest)
    record = json.loads(result.stdout)
    assert "surviving process group" in record["reason"]
    assert not record.get("discarded_partial_tracks")
    assert all(Path(a["stage_path"]).exists() for a in record["artifacts"] if a["kind"] == "track")
    with pytest.raises(ProcessLookupError): os.kill(int((env["fake_state"] / "descendant-pid").read_text()), 0)


def test_mkv_utils_extract_validation_and_protected_companions(env):
    manifest=_extract_manifest(env)
    source=str(env["workdir"]/"First source.mkv")
    manifest["sources"][source]["attachments"][0]["size"]=99
    result=_run_extract_contract(env,r'''
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
# Protected companion collisions fail before either grouped command.
index="$(jq -r '.outputs[]|.artifacts[]|select(.role=="vobsub_index")|.path' <<< "$job")"
print -r -- existing > "$index"
reject mkvutil_execute_extract_job "$job"
eq "$(jq -r '.phase' <<< "$MKVUTIL_RESULT_JSON")" preflight 'companion collision preflight'
print -r -- "PROTECTED $index"
''',manifest)
    assert not _command_argv(env,"mkvextract")
    index=Path(next(line[10:] for line in result.stdout.splitlines() if line.startswith("PROTECTED ")))
    assert index.read_text()=="existing\n" and Path(source).read_bytes()==b"payload"
    # A new source name avoids protected outputs; successful native staging
    # still cannot publish an attachment that fails the known-size oracle.
    second=_mkv_file(env,"Size mismatch.mka")
    manifest["sources"][str(second)]=manifest["sources"][source]
    manifest["extraction"][str(second)]=manifest["extraction"][source]
    result=_run_extract_contract(env,r'''
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Size mismatch.mka")" "$config")"
reject mkvutil_execute_extract_job "$job"
print -r -- "RESULT $MKVUTIL_RESULT_JSON"
''',manifest)
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]=="failed" and "staged size differs" in record["reason"]
    assert not record["published_artifacts"] and record["track_stage_seconds"] is None
    assert len(_command_argv(env,"mkvextract"))==1 and not list((env["workdir"]/"Attachments").glob("*.ttf"))
    assert second.read_bytes()==b"payload"


def test_mkv_utils_extract_progress_failure_continues_after_attachment_warning(env):
    manifest=_extract_manifest(env,("First source.mkv","Later source.mka"))
    manifest["extraction"][str(env["workdir"]/"First source.mkv")]["attachments"]["code"]=1
    result=_run_extract_contract(env,r'''
a="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
b="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Later source.mka")" "$config")"
mkvutil_format_progress() { return 1; }
reject mkvutil_execute_queue "$a" "$b"
print -r -- "SUMMARY $(mkvutil_final_summary)"
''',manifest)
    summary=json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["counts"]["warning"]==1 and summary["counts"]["done"]==1
    assert summary["batches"][0]["attempted"]==2 and summary["batches"][0]["track_stages_attempted"]==1
    assert len(_command_argv(env,"mkvextract"))==3 and "independent files continue" in result.stderr
    assert all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])


def test_mkv_utils_extract_missing_track_artifact_keeps_stage_failure(env):
    manifest=_extract_manifest(env)
    manifest["extraction"][next(iter(manifest["sources"]))]["tracks"]["outputs"]["0"]={"family":{".sub":"data"}}
    result=_run_extract_contract(env,r'''
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
reject mkvutil_execute_extract_job "$job"
print -r -- "RESULT $MKVUTIL_RESULT_JSON"
''',manifest)
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]=="partial" and record["stages"][0]["status"]=="complete"
    assert record["stages"][1]["status"]=="failed" and record["stages"][1]["native_code"]==0
    assert "Required staged artifact missing" in record["reason"] and len(record["published_artifacts"])==3
    assert not any(a["kind"]=="track" and a["publication_attempted"] for a in record["artifacts"])
    assert not list(env["workdir"].glob("*.sub")) and all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])


def test_mkv_utils_extract_late_cleanup_reports_current_inventory(env):
    manifest=_extract_manifest(env)
    result=_run_extract_contract(env,r'''
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/First source.mkv")" "$config")"
reject mkvutil_execute_queue "$job"
print -r -- "RESULT ${MKVUTIL_RESULTS[1]}"
mkvutil_final_report
''',manifest,fault="late_cleanup_fail")
    record=json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")))
    assert record["status"]=="partial" and record["phase"]=="cleanup_failed"
    assert record["cleanup_error"] and "Cleanup failed:" in record["reason"] and "Cleanup failed:" in result.stdout
    assert record["actual_state"]=="sidecars_published" and len(record["published_artifacts"])==9
    assert not record["staged_paths"] and not record["phase_receipts"] and not record["scratch_paths"]
    assert len(record["remaining_staging_directories"])==1
    directory=Path(record["remaining_staging_directories"][0]);assert directory.is_dir() and not list(directory.iterdir())
    assert f"Retained staging directory: {directory.name}" in result.stdout
    assert f"Retained staging directory: {directory}" not in result.stdout
    assert all(Path(p).read_bytes()==b"payload" for p in manifest["sources"])


def test_mkv_utils_extract_rejects_symlink_and_directory_leaves(env):
    source=_mkv_file(env,"Protected source.mkv")
    model=_source_json([(0,"subtitles","S_VOBSUB",False)],attachments=[{"id":1,"file_name":"Font.ttf","size":1}])
    result=_run_planning_contract(env,r'''
MKVUTIL_CODEC_EXT_JSON='{"VOBSUB":"sub"}'
config='{"category":"extract","operations":["1","2"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{},"expected_types":{"0":"subtitles"},"extract_ids":["0"]}'
job="$(mkvutil_plan_job "$(mkvutil_capture_source "$PWD/Protected source.mkv")" "$config")"
leaf="$(jq -r '.outputs[]|.artifacts[]|select(.role=="vobsub_index")|.path' <<< "$job")"
python3 -c 'import os,sys;os.symlink(sys.argv[2],sys.argv[1])' "$leaf" "$PWD/missing-target"
reject mkvutil_check_destinations "$job"
python3 -c 'import os,sys;os.unlink(sys.argv[1]);os.mkdir(sys.argv[1])' "$leaf"
reject mkvutil_check_destinations "$job"
print -r -- 'protected leaves rejected'
''',{str(source):model})
    assert result.stdout.strip()=="protected leaves rejected" and source.read_bytes()==b"payload"


def test_mkv_utils_extract_summary_repeated_name_uncertainty_and_recovery(env):
    result=_run_planning_contract(env,r'''
mkvutil_ledger_reset "$PWD" "$PWD/selected.mkv"
mkvutil_batch_request extract 1 '{"category":"extract","operations":["1"],"metadata":"","settings":{}}'
record="$(jq -cn --arg source "$PWD/selected.mkv" '{source:$source,status:"partial",phase:"published",actual_state:"sidecars_published",attachments_processed:7,
 artifacts:[range(0;7)|{kind:"attachment",id:(tostring),path:"Attachments/Same.ttf",destination_key:"filesystem-key",publication_state:(if .==3 or .==4 then "uncertain" else "confirmed" end),publication_confirmed:(.!=3 and .!=4)}]}')"
mkvutil_ledger_result "$record" "$PWD/selected.mkv" partial
print -r -- "SUMMARY $(mkvutil_final_summary)"
''',{})
    summary=json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert [r["outcome"] for r in summary["attachments"]["publications"]]==["superseded"]*3+["superseded_uncertain"]*2+["superseded","winner"]
    assert summary["attachments"]["unique_names"]==1 and summary["attachments"]["uncertain_names"]==0
    assert summary["attachments"]["published"]==5 and summary["attachments"]["superseded"]==4
    assert summary["attachments"]["publications"][-1]["id"]=="6"


def test_mkv_utils_reporting_ledger_history_counts_and_configurations(env):
    result = _run_planning_contract(env, r'''
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD/Input directory" "$PWD/first.mkv" "$PWD/Skipped file.mk3d" "$PWD/excluded.mkv" "$PWD/warning.mkv" "$PWD/partial.mkv" "$PWD/failed.mkv"
config='{"category":"mux","operations":["1","2"],"metadata":"3,4,5","settings":{"4:11":"@literal $cash\n\n","5:info":""}}'
mkvutil_batch_request mux 1,2 "$config"
mkvutil_ledger_exclude "$PWD/excluded.mkv" 'Initial inspection declined'
receipt="$(jq -cn --arg source "$PWD/Skipped file.mk3d" --arg reference "$PWD/first.mkv" '{kind:"removal-mismatch",source:$source,reference:$reference,reasons:[{original_id:"12",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}')"
mkvutil_ledger_skip "$receipt"
mkvutil_ledger_skip "$receipt"
record_result() {
  local record="$(jq -cn --arg source "$1" --arg status "$2" --arg destination "${3:-$1}" '{source:$source,destination:$destination,status:$status,phase:"complete",actual_state:"observed",reason:"native receipt",native_code:0}')"
  mkvutil_ledger_result "$record" "$1" "$2"
}
MKVUTIL_HAS_RUN=1
record_result "$PWD/first.mkv" success
record_result "$PWD/warning.mkv" warning
record_result "$PWD/partial.mkv" partial
record_result "$PWD/failed.mkv" failed
MKVUTIL_BATCHES[1]="$(jq --argjson outcomes "$(mkvutil_batch_outcomes)" '.+{state:"executed",eligible:4,attempted:4,completed:1,elapsed_seconds:8,outcomes:$outcomes}' <<< "${MKVUTIL_BATCHES[1]}")"
MKVUTIL_SOURCES=("$(jq -cn --arg source "$PWD/Skipped file.mk3d" '{source:$source}')")
mkvutil_batch_request mux 1 '{"category":"mux","operations":["1"],"metadata":"5","settings":{"5:info":""}}'
# The identical late receipt is deduplicated across cohorts, while attribution
# records both configurations. History itself is not a permanent failure.
mkvutil_ledger_skip "$receipt"
record_result "$PWD/Skipped file.mk3d" success "$PWD/Skipped file.mka"
MKVUTIL_BATCHES[2]="$(jq --argjson outcomes "$(mkvutil_batch_outcomes)" '.+{state:"executed",eligible:1,attempted:1,completed:1,elapsed_seconds:2,outcomes:$outcomes}' <<< "${MKVUTIL_BATCHES[2]}")"
MKVUTIL_TOTAL_ELAPSED=10
mkvutil_ledger_finalize
reject mkvutil_ledger_status
mkvutil_sync_unresolved_skips
eq "${#MKVUTIL_REMOVAL_SKIPS}" 0 'resolved skips not offered again'
print -r -- "SUMMARY $(mkvutil_final_summary)"
mkvutil_final_report
''', {})
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["directory"] == "Input directory" and summary["selected"] == 6 and summary["required"] == 5
    assert summary["counts"] == dict(done=2, warning=1, partial=1, failed=1, excluded=1, skipped=0, not_attempted=0, interrupted=0)
    skipped = next(record for record in summary["files"] if record["source"].endswith("Skipped file.mk3d"))
    assert skipped["destination"].endswith("Skipped file.mka")
    assert len(skipped["skip_history"]) == 1 and skipped["skip_history"][0]["resolved"]
    assert skipped["skip_history"][0]["batch_ids"] == [1, 2]
    assert len(skipped["attempts"]) == 1
    assert summary["batches"][0]["action_ids"] == ["1", "2"] and summary["batches"][0]["metadata_ids"] == "3,4,5"
    assert summary["batches"][1]["action_ids"] == ["1"] and summary["batches"][1]["metadata_ids"] == "5"
    assert summary["batches"][0]["config"]["settings"] == {"4:11": "@literal $cash\n\n", "5:info": ""}
    assert summary["batches"][0]["outcomes"]["skipped"] == 1 and summary["batches"][1]["outcomes"] == {"done": 1}
    assert "Directory: Input directory" in result.stdout and f"Directory: {env['workdir']}" not in result.stdout
    assert "Skip history: resolved; configurations 1,2" in result.stdout
    outcomes = _assert_readable_outcomes(
        result.stdout, "Done: 1", "Failed: 1", "Warning: 1", "Partial: 1", "Skipped: 1"
    )
    assert "{" not in outcomes and "Outcomes: Done: 1" in outcomes


def test_mkv_utils_reporting_cancel_eof_and_excluded_unresolved_retry(env):
    first, skipped = _mkv_file(env, "completed.mk3d"), _mkv_file(env, "Unresolved source.mkv")
    sources = {str(skipped): _source_json([(0, "audio", "A_AAC", True), (12, "subtitles", "S_TEXT/UTF8", False)])}
    result = _run_planning_contract(env, r'''
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD" "$PWD/neutral.mkv"
mkvutil_batch_request edit 1,2
mkvutil_finish 2
print -r -- 'NEUTRAL-END'
# All skipped remains unresolved and can be reconfigured before processing.
mkvutil_ledger_reset "$PWD" "$PWD/Unresolved source.mkv"
mkvutil_batch_request mux 1
receipt="$(jq -cn --arg source "$PWD/Unresolved source.mkv" --arg reference "$PWD/completed.mk3d" '{kind:"removal-mismatch",source:$source,reference:$reference,reasons:[{original_id:"12",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}')"
mkvutil_ledger_skip "$receipt"
MKVUTIL_JOBS=()
MKVUTIL_REMOVAL_SKIPS=("$receipt")
reject mkvutil_finish 2
print -r -- 'ALL-SKIPPED-END'
# Prior success and unresolved skip survive fresh configuration EOF. Original
# source key stays counted once after conversion; no settings blindly survive.
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD" "$PWD/completed.mk3d" "$PWD/Unresolved source.mkv"
mkvutil_batch_request mux 1,2
MKVUTIL_HAS_RUN=1
successful="$(jq -cn --arg source "$PWD/completed.mk3d" --arg destination "$PWD/completed.mka" '{source:$source,destination:$destination,status:"success",phase:"complete",actual_state:"published_complete",reason:""}')"
mkvutil_ledger_result "$successful"
mkvutil_ledger_skip "$receipt"
MKVUTIL_JOBS=()
MKVUTIL_REMOVAL_SKIPS=("$receipt")
MKVUTIL_METADATA_SETTINGS[4:0]='old setting'
mkvutil_prepare_skipped_subset
(( ${#MKVUTIL_METADATA_SETTINGS}==0 )) || fail 'old settings leaked'
eq "${#MKVUTIL_SOURCES}" 1 'only unresolved subset refreshed'
mkvutil_batch_request mux 2
code=0
mkvutil_configure_category mux 2 <<< $'0,1\n3,4' || code=$?
eq "$code" 2 'configuration EOF'
reject mkvutil_finish 2
print -r -- "SUMMARY $(mkvutil_final_summary)"
# Exclusion from retry does not resolve an earlier required mismatch.
mkvutil_ledger_exclude "$PWD/Unresolved source.mkv" 'Fresh inspection explicitly excluded'
mkvutil_sync_unresolved_skips
eq "${#MKVUTIL_REMOVAL_SKIPS}" 0 'excluded retry not offered'
reject mkvutil_ledger_status
print -r -- "EXCLUDED $(mkvutil_final_summary)"
''', sources)
    neutral, remainder = result.stdout.split("NEUTRAL-END", 1)
    assert "Cancelled; no media changes." in neutral and "Actions: 1,2" in neutral
    all_skipped, after_run = remainder.split("ALL-SKIPPED-END", 1)
    assert "Skipped: 1" in all_skipped and "requested, not run" in all_skipped
    assert "Continuation cancelled; recorded outcomes retained." in after_run
    assert "Cancelled; no media changes." not in after_run
    summary = json.loads(next(line[8:] for line in after_run.splitlines() if line.startswith("SUMMARY ")))
    excluded = json.loads(next(line[9:] for line in after_run.splitlines() if line.startswith("EXCLUDED ")))
    assert summary["counts"]["done"] == 1 and summary["counts"]["skipped"] == 1
    assert summary["selected"] == 2 and len(summary["batches"]) == 2
    assert summary["batches"][1]["action_ids"] == ["2"] and summary["batches"][1]["state"] == "requested"
    assert summary["batches"][1]["metadata_ids"] == "3,4"
    unresolved = next(record for record in excluded["files"] if record["source"] == str(skipped))
    assert unresolved["required"] and unresolved["status"] == "skipped" and unresolved["excluded_from_retry"]
    assert excluded["counts"]["excluded"] == 0 and excluded["counts"]["skipped"] == 1
    assert len(_command_argv(env, "mkvmerge")) == 1 and first.read_text() == "payload"


def test_mkv_utils_reporting_between_job_signal_stops_continuation_and_pending_success(env):
    result = _run_planning_contract(env, r'''
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD" "$PWD/first.mkv" "$PWD/pending.mkv" "$PWD/skipped.mkv"
config='{"category":"mux","operations":["1","2"],"metadata":"3,4"}'
mkvutil_batch_request mux 1,2 "$config"
first="$(jq -cn --arg source "$PWD/first.mkv" --argjson config "$config" '{source:$source,config:$config}')"
second="$(jq -cn --arg source "$PWD/pending.mkv" --argjson config "$config" '{source:$source,config:$config}')"
receipt="$(jq -cn --arg source "$PWD/skipped.mkv" --arg reference "$PWD/first.mkv" '{kind:"removal-mismatch",source:$source,reference:$reference,reasons:[{original_id:"12",reason:"missing-id",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:null}]}')"
MKVUTIL_REMOVAL_SKIPS=("$receipt")
mkvutil_ledger_skip "$receipt"
typeset -a modifier_sources=()
mkvutil_configure_category() { MKVUTIL_CONFIG="$config"; }
mkvutil_plan_queue() { MKVUTIL_JOBS=("$first" "$second"); }
mkvutil_execute_mux_job() {
  modifier_sources+=("$(jq -r '.source' <<< "$1")")
  MKVUTIL_RESULT_JSON="$(jq -c '{source:.source,destination:.source,status:"success",phase:"complete",actual_state:"replaced_complete",reason:""}' <<< "$1")"
}
mkvutil_format_progress() { kill -TERM $$; }
code=0
mkvutil_controller mux 1,2 || code=$?
eq "$code" 1 'between-job interruption exit'
eq "$MKVUTIL_INTERRUPTED" 1 'global queue interruption'
eq "${#modifier_sources}" 1 'no later modifier'
eq "${modifier_sources[1]}" "$PWD/first.mkv" 'first modifier source'
reject mkvutil_finish "$code"
print -r -- "SUMMARY $(mkvutil_final_summary)"
# Even without the interruption bit, later skip resolution cannot conceal the
# required pending job that was finalized as not attempted.
MKVUTIL_INTERRUPTED=0
resolved="$(jq -cn --arg source "$PWD/skipped.mkv" '{source:$source,destination:$source,status:"success",phase:"complete",actual_state:"observed",reason:""}')"
mkvutil_ledger_result "$resolved"
reject mkvutil_ledger_status
''', {})
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["interrupted"] and summary["counts"]["done"] == 1
    assert summary["counts"]["not_attempted"] == 1 and summary["counts"]["skipped"] == 1
    assert summary["batches"][0]["state"] == "interrupted" and summary["batches"][0]["attempted"] == 1
    assert "Skipped-subset choice:" not in result.stderr and "New skipped-subset operations:" not in result.stderr
    assert "Batch interrupted; remaining jobs not attempted." in result.stdout


def test_mkv_utils_stop_hard_signal_wins_over_finished_receipt(env):
    result = _run_planning_contract(env, r'''
mkvutil_ledger_reset "$PWD" "$PWD/first.mkv" "$PWD/later.mkv"
config='{"category":"mux","operations":["2"],"metadata":""}'
first="$(jq -cn --arg source "$PWD/first.mkv" --argjson config "$config" '{source:$source,config:$config}')"
second="$(jq -cn --arg source "$PWD/later.mkv" --argjson config "$config" '{source:$source,config:$config}')"
mkvutil_execute_mux_job() {
  MKVUTIL_RESULT_JSON="$(jq -c '{source:.source,destination:.source,status:"success",phase:"complete",actual_state:"replaced_complete",reason:"",stop_requested:true,stop_signal:2}' <<< "$1")"
  kill -TERM $$
}
reject mkvutil_execute_queue "$first" "$second"
print -r -- "SUMMARY $(mkvutil_final_summary)"
''', {})
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    stop = summary["batches"][0]["stop"]
    assert stop["signal"] == 15 and stop["mode"] == "immediate"
    assert stop["not_started_sources"] == [str(env["workdir"] / "later.mkv")]
    assert summary["counts"]["done"] == 1


def test_mkv_utils_stop_rejects_mismatched_transport_result(env):
    result = _run_planning_contract(env, r'''
job='{"source":"/source.mkv","config":{"category":"mux"}}'
program='print("{\"source\":\"/different.mkv\",\"category\":\"mux\",\"status\":\"success\"}")'
reject _mkvutil_launch_engine "$TEST_REAL_PYTHON" "$program" mux "$job"
eq "$MKVUTIL_RESULT_JSON" '' 'invalid result never accepted'
''', {}, extra_env={"TMPDIR": str(env["fake_state"])})
    assert "result unavailable or invalid" in result.stderr
    assert len(list(env["fake_state"].glob("mkvutil-engine.*/result"))) == 1



@pytest.mark.parametrize("stop_on_failure,returned_status", [(False, "success"), (True, "success"), (True, "not_attempted")])
def test_mkv_utils_reporting_processing_exit_keeps_actual_outcome_and_pending(env, stop_on_failure, returned_status):
    result = _run_planning_contract(env, r'''
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD" "$PWD/first.mkv" "$PWD/pending.mkv"
config='{"category":"mux","operations":["2"],"metadata":""}'
mkvutil_batch_request mux 2 "$config"
first="$(jq -cn --arg source "$PWD/first.mkv" --argjson config "$config" '{source:$source,config:$config}')"
second="$(jq -cn --arg source "$PWD/pending.mkv" --argjson config "$config" '{source:$source,config:$config}')"
MKVUTIL_JOBS=("$first" "$second")
typeset -a modifiers=()
mkvutil_execute_mux_job() {
  modifiers+=("$(jq -r '.source' <<< "$1")")
  MKVUTIL_RESULT_JSON="$(jq -c --arg outcome "$TEST_RETURNED_STATUS" '{source:.source,destination:.source,status:$outcome,phase:"complete",actual_state:(if $outcome=="success" then "replaced_complete" else "not_modified_by_job" end),reason:""}' <<< "$1")"
}
# The first post-tool clock read fails. The always block must archive the
# tool's actual outcome, finalize the untouched pending job and remain nonzero.
mkvutil_clock() {
  local count=0
  [[ ! -f "$PWD/clock.count" ]] || count="$(< "$PWD/clock.count")"
  count=$(( count + 1 ))
  print -r -- "$count" > "$PWD/clock.count"
  if (( count == 3 )); then
    [[ "$TEST_STOP_ON_FAILURE" != 1 ]] || kill -INT $$
    return 1
  fi
  print -r -- "$count"
}
reject mkvutil_execute_queue "$first" "$second"
eq "${#modifiers}" 1 'only first tool invoked'
eq "${#MKVUTIL_JOBS}" 0 'completed queue cleared on early exit'
reject mkvutil_finish 1
print -r -- "SUMMARY $(mkvutil_final_summary)"
''', {}, extra_env={"TEST_STOP_ON_FAILURE": "1" if stop_on_failure else "0", "TEST_RETURNED_STATUS": returned_status})
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    done = int(returned_status == "success")
    assert summary["counts"]["done"] == done and summary["counts"]["not_attempted"] == 2 - done
    assert summary["batches"][0]["attempted"] == done and summary["batches"][0]["completed"] == done
    first = next(record for record in summary["files"] if record["source"].endswith("first.mkv"))
    state = "replaced_complete" if done else "not_modified_by_job"
    assert first["attempts"][0]["result"]["actual_state"] == state
    assert "actual state" not in result.stdout and "Phase:" not in result.stdout
    assert state not in result.stdout
    if stop_on_failure:
        assert summary["batches"][0]["stop"]["not_started_sources"] == [str(env["workdir"] / name) for name in (["pending.mkv"] if done else ["first.mkv", "pending.mkv"])]

def test_mkv_utils_reporting_progress_and_extract_formatter_contract(env):
    result = _run_planning_contract(env, r'''
eq "$(mkvutil_format_progress edit 1,2 9 1 1 2 9)" '' 'all Edit progress silent'
special="$(mkvutil_ascii_box 'Literal $cash' '100% \literal' '界é')"
print -r -- "SPECIAL-BEGIN"
print -r -- "$special"
print -r -- "SPECIAL-END"
file_progress="$(mkvutil_format_progress mux 1 1 1 1 2 1 1 1 1 "$PWD/Source 界é.mka")"
print -r -- "FILE-PROGRESS-BEGIN"
print -r -- "$file_progress"
print -r -- "FILE-PROGRESS-END"
print -r -- "MUX-BEGIN"
mkvutil_format_progress mux 1,2 2 2 1 3 8
print -r -- "MUX-END"
print -r -- "ZERO-BEGIN"
mkvutil_format_progress mux 2 0 0 0 0 0
print -r -- "ZERO-END"
for action in 1 2; do
  output="$(mkvutil_format_progress extract "$action" 5 1 1 2 5)"
  [[ "$output" == *'Processed In: 0h 0m 5s'* && "$output" == *'Estimated Time Remaining: 0h 0m 5s'* ]] || fail 'single Extract timing'
  print -r -- "EXTRACT-$action-BEGIN"
  print -r -- "$output"
  print -r -- "EXTRACT-$action-END"
done
print -r -- "COMBINED-BEGIN"
mkvutil_format_progress extract 1,2 30 2 2 3 65 3 8
print -r -- "COMBINED-END"
reject mkvutil_format_progress extract 1,2 30 2 2 3 65
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD/Extract directory" "$PWD/one.mkv"
mkvutil_batch_request extract 1,2
mkvutil_finish 2
''', {})
    mux = result.stdout.split("MUX-BEGIN\n")[1].split("MUX-END")[0]
    assert "Processed In: 0h 0m 2s" in mux and "Estimated Time Remaining: 0h 0m 4s" in mux
    assert "Files Attempted: 2" in mux and "Files Done: 1" in mux and "Files Remaining: 1" in mux
    _ascii_box_contains(mux, "File progress", "Processed In: 0h 0m 2s", "Files Done: 1",
                        "Files Attempted: 2", "Files Remaining: 1", "Estimated Time Remaining: 0h 0m 4s")
    zero = result.stdout.split("ZERO-BEGIN\n")[1].split("ZERO-END")[0]
    assert "Estimated Time Remaining: 0h 0m 0s" in zero and "Files Remaining: 0" in zero
    _ascii_box_contains(zero, "File progress", "Files Remaining: 0", "Estimated Time Remaining: 0h 0m 0s")
    combined = result.stdout.split("COMBINED-BEGIN\n")[1].split("COMBINED-END")[0]
    assert "Processed In: 0h 0m 3s" in combined and "Estimated Time Remaining: 0h 0m 4s" in combined
    _ascii_box_contains(combined, "File progress", "Processed In: 0h 0m 3s", "Files Done: 2",
                        "Files Attempted: 2", "Files Remaining: 1", "Estimated Time Remaining: 0h 0m 4s")
    special = result.stdout.split("SPECIAL-BEGIN\n")[1].split("SPECIAL-END")[0]
    _ascii_box_contains(special, "Literal $cash", "100% \\literal", "界é")
    file_progress = result.stdout.split("FILE-PROGRESS-BEGIN\n")[1].split("FILE-PROGRESS-END")[0]
    _ascii_box_contains(file_progress, "File progress", "File: Source 界é.mka", "Files Attempted: 1")
    assert str(env["workdir"]) not in file_progress
    for action in (1, 2):
        extract = result.stdout.split(f"EXTRACT-{action}-BEGIN\n")[1].split(f"EXTRACT-{action}-END")[0]
        _ascii_box_contains(extract, "File progress", "Processed In: 0h 0m 5s", "Files Done: 1",
                            "Files Attempted: 1", "Files Remaining: 1", "Estimated Time Remaining: 0h 0m 5s")
    assert "Category:" not in mux and "Directory:" not in mux
    assert "Directory: Extract directory" in result.stdout and "Category: extract; Actions: 1,2" in result.stdout
    failed_python = _run_planning_contract(env, r'''
export TEST_FAKE_PYTHON_FAIL=1
progress_code=0
output="$(mkvutil_format_progress mux 1 1 1 1 2 2)" || progress_code=$?
eq "$progress_code" 1 'progress Python failure remains nonzero'
eq "$output" '' 'Python failure does not print a success box'
print -r -- 'progress formatter failure preserved'
''', {})
    assert failed_python.stdout.rstrip().endswith("progress formatter failure preserved")


@pytest.mark.parametrize("workflow", ["edit_flags", "mux_reorder_metadata", "mux_remove_reorder_metadata"])
def test_mkv_utils_reporting_legacy_workflow_equivalents(env, workflow):
    source, manifest = _executor_manifest(env, converted=False)
    original = manifest["sources"][str(source)]
    actual = json.loads(json.dumps(original))
    if workflow == "edit_flags":
        actual["tracks"][1]["properties"].update(forced_track=False, default_track=True)
        config_update = '.category="edit"|.operations=["1","2"]|.removed_ids=[]|.order=""|.order_ids=[]|.metadata=""|.settings={"1:11":"0","2:11":"1"}'
        manifest["post_edit"][str(source)] = actual
    else:
        audio = actual["tracks"][1]
        audio["properties"].update(language="fre", language_ietf="fr-CA", track_name='@Name $cash: "literal"')
        actual["tracks"] = [actual["tracks"][2], audio] if workflow == "mux_remove_reorder_metadata" else [actual["tracks"][2], actual["tracks"][0], audio]
        config_update = r'.operations=["1","2"]|.metadata="3,4"|.settings={"3:11":"fr-CA","4:11":"@Name $cash: \"literal\""}'
        if workflow == "mux_reorder_metadata":
            config_update += '|.operations=["2"]|.removed_ids=[]'
        manifest["stage"][str(source)] = actual
    result = _run_executor_contract(env, 'config="$(jq \'' + config_update + '\' <<< "$config")"\njob="$(mkvutil_plan_job "$record" "$config")"\n' + r'''
mkvutil_execute_queue "$job"
mkvutil_finish 0
print -r -- "SUMMARY $(mkvutil_final_summary)"
''', manifest)
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["counts"]["done"] == 1 and summary["batches"][0]["completed"] == 1
    assert summary["elapsed_seconds"] >= summary["files"][0]["attempts"][0]["result"]["processing_seconds"] >= 0
    edits = _command_argv(env, "mkvpropedit")
    merges = [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    if workflow == "edit_flags":
        assert len(edits) == 1 and not merges
        assert edits[0][-6:] == ["--edit", "track:2", "--set", "flag-forced=0", "--set", "flag-default=1"]
        assert "Actions: 1,2" in result.stdout and "Processed In:" not in result.stdout
    else:
        assert len(merges) == 1 and not edits
        assert "--language" in merges[0] and "11:fr-CA" in merges[0]
        assert '11:@Name $cash: "literal"' in merges[0]
        assert "Optional Mux metadata: 3,4" in result.stdout and "Files Done: 1" in result.stdout
        assert summary["batches"][0]["action_ids"] == (["1", "2"] if workflow == "mux_remove_reorder_metadata" else ["2"])


def test_mkv_utils_reporting_mux_skip_ends_run_and_retry_needs_new_invocation(env):
    first, skipped = _mkv_file(env, "Reference ASS.mkv"), _mkv_file(env, "Skipped SRT.mk3d")
    original = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (11, "audio", "A_PCM/INT/LIT", False), (12, "subtitles", "S_TEXT/ASS", False)])
    for position, track in enumerate(original["tracks"]):
        track["properties"]["uid"] = 18446744073709551000 + position
    other = json.loads(json.dumps(original))
    other["tracks"][2]["properties"]["codec_id"] = "S_TEXT/UTF8"
    first_output, second_output = json.loads(json.dumps(original)), json.loads(json.dumps(other))
    first_output["tracks"] = [first_output["tracks"][1], first_output["tracks"][0]]
    first_output["tracks"][0]["properties"].update(language="fre", language_ietf="fr-CA", track_name="@literal $name")
    second_output["tracks"] = second_output["tracks"][:2]
    second_output["container"]["properties"]["title"] = ""
    for output in (first_output, second_output):
        for position, track in enumerate(output["tracks"]):
            track["id"] = position
    manifest = env["workdir"].parent / "continuation-execution.json"
    manifest.write_text(json.dumps({"sources": {str(first): original, str(skipped): other}, "stage": {str(first): first_output, str(skipped): second_output}}))
    result = _run_mkv_utils(
        env, fzf_responses=[[str(first), str(skipped)]],
        input_data="2\n1,2\n12\n11,0\n3,4\nfr-CA\nen-US\n@literal $name\nOriginal 0\n",
        extra_env={"TEST_FAKE_EXECUTION_JSON": str(manifest)},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"Skipped removal mismatch: {skipped.name}" in result.stdout
    assert "Fresh skipped-subset reference:" not in result.stdout
    assert "Skipped-subset choice:" not in result.stderr
    assert "New skipped-subset operations:" not in result.stderr
    assert result.stdout.count("Final report") == 1 and "Directory: workdir" in result.stdout
    assert result.stdout.count("1) Matroska Edit") == 1
    assert "Done: 1; Failed: 0" in result.stdout and "Skipped: 1; Excluded: 0; Not attempted: 0" in result.stdout
    assert "Skip history: unresolved" in result.stdout
    report = result.stdout[result.stdout.index("Final report"):]
    assert report.count("Final report") == 1 and f"| {skipped.name}" in report
    assert "Original ID 12: codec-mismatch" in report
    assert 'expected={"type":"subtitles","codec_id":"S_TEXT/ASS"}' in report
    assert 'actual={"type":"subtitles","codec_id":"S_TEXT/UTF8"}' in report
    assert "Category: mux; Actions: 1,2" in result.stdout and "Optional Mux metadata: 3,4" in result.stdout
    assert "Mux 1,2: remove + reorder; metadata 3,4" in result.stdout
    assert "Configuration 2" not in result.stdout
    assert len(_command_argv(env, "fzf")) == 1
    merges = [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    assert len(merges) == 1 and not _command_argv(env, "mkvpropedit")
    first_call = merges[0]
    assert first_call[-1] == str(first)
    assert first_call[first_call.index("--track-order") + 1] == "0:11,0:0"
    assert "--language" in first_call and "11:fr-CA" in first_call and "11:@literal $name" in first_call
    assert first.read_bytes() == b"candidate-data\n" and skipped.read_bytes() == b"payload"
    assert not list(env["workdir"].glob(".mkvutil-*"))
    completed_bytes = first.read_bytes()
    # Retrying requires a new invocation and an explicit selection of skipped files.
    retry = _run_mkv_utils(
        env, fzf_responses=[[str(skipped)]], input_data="2\n1\n12\n5\n\n",
        extra_env={"TEST_FAKE_EXECUTION_JSON": str(manifest)},
    )
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert retry.stdout.count("Final report") == 1 and "Done: 1; Failed: 0" in retry.stdout
    assert "Skipped: 0" in retry.stdout and "Optional Mux metadata: 5" in retry.stdout
    assert "Configuration 2" not in retry.stdout
    retries = [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    assert len(retries) == 1 and retries[0][-1] == str(skipped)
    assert "--language" not in retries[0] and "--track-name" not in retries[0]
    assert retries[0][retries[0].index("--title") + 1] == ""
    assert len(_command_argv(env, "fzf")) == 1 and not _command_argv(env, "mkvpropedit")
    assert first.read_bytes() == completed_bytes and skipped.read_bytes() == b"candidate-data\n"
    assert not list(env["workdir"].glob(".mkvutil-*"))

def test_mkv_utils_category_incomplete_final_input_does_not_execute(env: dict[str, Path]):
    first, second = _mkv_file(env, "preview-first.mkv"), _mkv_file(env, "preview-second.mk3d")
    before = [path.read_bytes() for path in (first, second)]
    result = _run_mkv_utils(
        env, fzf_responses=[[str(first), str(second)]],
        input_data="2\n2\n2,0\n5\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Title [clear]: " in result.stderr
    assert "Review/change" not in result.stdout + result.stderr
    assert "Preview resulting" not in result.stdout + result.stderr
    assert result.stdout.count("Final report") == 1
    assert "Cancelled; no media changes." in result.stdout
    assert "Outcomes: none" in result.stdout
    assert len(_command_argv(env, "fzf")) == 1
    assert len(_command_argv(env, "mkvmerge")) == 2
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
    assert [path.read_bytes() for path in (first, second)] == before
    assert sorted(path.name for path in env["workdir"].iterdir()) == sorted([first.name, second.name])


def test_mkv_utils_category_extract_run_grouped_entrypoint(env: dict[str, Path]):
    manifest=_extract_manifest(env)
    manifest_path=env["workdir"].parent/"execution.json"
    manifest_path.write_text(json.dumps(manifest))
    collection=env["workdir"]/"Attachments";collection.mkdir();(collection/"Font.ttf").write_bytes(b"old collection")
    source=env["workdir"]/"First source.mkv"
    extractor=env["fake_bin"]/"mkvextract"
    extractor_body=extractor.read_text()
    extraction_anchor='source, mode, specs = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3:]\n'
    assert extractor_body.count(extraction_anchor)==1
    extractor.write_text(extractor_body.replace(extraction_anchor, extraction_anchor +
        'os.write(1, ("NATIVE "+mode+" "+source+"\\n").encode())\n'
        'os.write(2, ("NATIVE STDERR "+mode+" "+source+"\\n").encode())\n', 1))
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n1,2\n0-3\n",
                          extra_env={"TEST_FAKE_EXECUTION_JSON":str(manifest_path)})
    assert result.returncode==0,result.stdout+result.stderr
    _ascii_box_contains(result.stdout, "Final report")
    assert "Category: extract; Actions: 1,2" in result.stdout and "Directory: workdir" in result.stdout
    assert "Extract 1,2: attachments + tracks" in result.stdout
    assert "Done: 1; Failed: 0" in result.stdout and "Attachments processed: 3; published: 3; final unique published names: 2; superseded: 1" in result.stdout
    _assert_readable_outcomes(result.stdout, "Done: 1")
    assert "Processing: First source.mkv" in result.stdout
    assert result.stdout.index("Extract 1,2: attachments + tracks") < result.stdout.index("Processing: First source.mkv")
    for mode in ("attachments", "tracks"):
        assert result.stdout.count(f"NATIVE {mode} First source.mkv") == 1
        assert result.stdout.count(f"NATIVE STDERR {mode} First source.mkv") == 1
        assert result.stdout.index(f"NATIVE {mode} First source.mkv") < result.stdout.index("File progress")
        assert result.stdout.index(f"NATIVE STDERR {mode} First source.mkv") < result.stdout.index("File progress")
    assert str(source) not in result.stdout
    _ascii_box_contains(result.stdout, "File progress", "File: First source.mkv")
    final = result.stdout.split('Final report', 1)[1]
    assert '=> Attachments' not in final
    _ascii_box_contains(final, "Outputs", "First source.mkv",
                        "Track 0: First source - Track [0].idx",
                        "Track 0: First source - Track [0].sub")
    assert 'Track output ID ' not in final and 'published)' not in final
    assert "Files Attempted: 1" in result.stdout and "Estimated Time Remaining:" in result.stdout
    assert len(_command_argv(env,"fzf"))==1
    assert [argv[:2] for argv in _command_argv(env,"mkvextract")]==[[str(source),"attachments"],[str(source),"tracks"]]
    assert all(argv[:1]==["-J"] for argv in _command_argv(env,"mkvmerge")) and not _command_argv(env,"mkvpropedit")
    assert (collection/"Font.ttf").read_bytes()==b"BBB" and source.read_bytes()==b"payload"
    assert (env["workdir"]/"First source - Track [0].sub").read_bytes()==b"data"
    assert (env["workdir"]/"First source - Track [0].idx").read_bytes()==b"index"
    assert (env["workdir"]/"First source - Track [1].wvc").read_bytes()==b"correction"
    assert not list(env["workdir"].glob(".mkvutil-extract-*")) and not list(collection.glob(".mkvutil-extract-*"))


def test_mkv_utils_automatic_start_checks_later_file_before_any_write(env):
    first, second = _mkv_file(env, "First.mkv"), _mkv_file(env, "Second.mkv")
    collision = env["workdir"] / "Second - Track [1].aac"
    collision.write_bytes(b"existing output")
    result = _run_mkv_utils(
        env, fzf_responses=[[str(first), str(second)]], input_data="3\n2\n1\nN\n",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("Final report") == 1
    assert first.read_bytes() == second.read_bytes() == b"payload"
    assert collision.read_bytes() == b"existing output"
    assert not (env["workdir"] / "First - Track [1].aac").exists()
    assert not _command_argv(env, "mkvextract") and not _command_argv(env, "mkvpropedit")
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))


def test_mkv_utils_category_edit_run_grouped_entrypoint(env: dict[str, Path]):
    source = _mkv_file(env, "Run title.mks")
    original = _executor_document()
    actual = json.loads(json.dumps(original))
    actual["container"]["properties"]["title"] = ""
    manifest = env["workdir"].parent / "execution.json"
    manifest.write_text(json.dumps({"sources": {str(source): original}, "post_edit": {str(source): actual}}))
    result = _run_mkv_utils(
        env, fzf_responses=[[str(source)]], input_data="1\n5\n\n",
        extra_env={"TEST_FAKE_EXECUTION_JSON": str(manifest)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    _ascii_box_contains(result.stdout, "Final report")
    assert "Processed In:" not in result.stdout
    assert "Processing: Run title.mks" in result.stdout
    assert "success:" not in result.stdout
    assert source.name not in result.stdout.split("Final report", 1)[1]
    _assert_readable_outcomes(result.stdout, "Done: 1")
    assert len(_command_argv(env, "fzf")) == 1
    assert _command_argv(env, "mkvpropedit") == [[str(source), "--normalize-language-ietf", "off", "--edit", "info", "--delete", "title"]]
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    assert source.read_bytes() == b"edited-data\n"


def test_mkv_utils_help_shows_menu(env: dict[str, Path]):
    result = _run_mkv_utils(env, "--help")

    assert result.returncode == 0
    assert "Usage: mkv_utils.zsh" in result.stdout
    assert "1) Matroska Edit" in result.stdout
    assert "2) Matroska Mux" in result.stdout
    assert "3) Matroska Extract" in result.stdout


def test_mkv_utils_invalid_argument_rejects(env: dict[str, Path]):
    result = _run_mkv_utils(env, "--bad-choice")

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Usage: mkv_utils.zsh" in combined


def test_mkv_utils_nonexistent_working_dir_guard(env: dict[str, Path]):
    missing = env["workdir"] / "missing-dir"
    result = _run_mkv_utils(env, str(missing))
    assert result.returncode == 1
    assert f"Error: Working directory not found: {missing}" in result.stderr


def test_mkv_utils_no_mkv_files_displays_guard(env: dict[str, Path]):
    (env["workdir"] / "notes.txt").write_text("plain", encoding="utf-8")
    result = _run_mkv_utils(env, input_data="1\n5\n")
    assert result.returncode == 1
    assert "No Matroska files found" in result.stdout


def test_mkv_utils_analyze_uses_first_usable_full_id_signature_reference(env):
    names = ("Unusable first.mkv", "Reference library.mkv", "Reordered metadata.mkv",
             "Codec changed.mkv", "Type changed.mkv", "Missing track.mkv", "Extra track.mkv")
    files = [_mkv_file(env, name) for name in names]
    unusable = _source_json([(12, "video", "", True),
                             (30, "audio", "A_AAC", False),
                             (90, "subtitles", "S_TEXT/ASS", True)])
    reference = _source_json([(12, "video", "V_MPEG4/ISO/AVC", True),
                              (30, "audio", "A_AAC", False),
                              (90, "subtitles", "S_TEXT/ASS", True)])
    reordered = json.loads(json.dumps(reference))
    reordered["tracks"].reverse()
    for track in reordered["tracks"]:
        track["properties"].update(track_name="literal/name/value", language="jpn",
                                   language_ietf="ja", default_track=not track["properties"]["default_track"],
                                   forced_track=True)
    codec_changed = json.loads(json.dumps(reference))
    codec_changed["tracks"][0]["properties"]["codec_id"] = "V_MPEGH/ISO/HEVC"
    type_changed = json.loads(json.dumps(reference))
    type_changed["tracks"][1]["type"] = "video"
    missing_track = json.loads(json.dumps(reference))
    missing_track["tracks"] = [track for track in missing_track["tracks"] if track["id"] != 90]
    extra_track = json.loads(json.dumps(reference))
    extra_track["tracks"].append(_source_json([(777, "audio", "A_OPUS", True)])["tracks"][0])
    overrides = env["fake_bin"].parent / "analysis-source-json.json"
    overrides.write_text(json.dumps({
        str(files[0]): unusable, str(files[1]): reference, str(files[2]): reordered,
        str(files[3]): codec_changed, str(files[4]): type_changed,
        str(files[5]): missing_track, str(files[6]): extra_track,
    }), encoding="utf-8")
    result = _run_mkv_utils(
        env, "--bypass", str(env["workdir"]), input_data="4\n", fzf_responses=[list(map(str, files))],
        extra_env={"TEST_FAKE_MKVMERGE_JSON_BY_PATH": str(overrides)},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Current Work Dir: " + str(env["workdir"]) in result.stdout
    assert "Analysis reference file: Reference library.mkv" in result.stdout
    assert "Reference file: Reference library.mkv" in result.stdout
    assert "Files analyzed: 6; Matching: 2; Mismatched: 4; Failed: 1; Not attempted: 0" in result.stdout
    assert "Analysing" not in result.stdout + result.stderr and "\x1b" not in result.stdout + result.stderr
    before_report, separator, final_report = result.stdout.partition("Final report")
    assert separator and result.stdout.count("Final report") == 1
    _ascii_box_contains(result.stdout, "Final report")
    assert before_report.count("Analysis reference file: Reference library.mkv") == 1
    assert before_report.count("mkvmerge JSON track listing") == 1
    header_start, header_end, _ = _ascii_box_contains(
        before_report, "Analysis", f"Current Work Dir: {env['workdir']}",
        "Analysis reference file: Reference library.mkv",
    )
    track_lines = [line for line in before_report.splitlines() if line.startswith("Track ID ")]
    assert len(track_lines) == 3
    assert [line.split(":", 1)[0] for line in track_lines] == ["Track ID 12", "Track ID 30", "Track ID 90"]
    listing_heading = next(i for i, line in enumerate(before_report.splitlines()) if "mkvmerge JSON track listing" in line)
    before_lines = before_report.splitlines()
    assert header_start < header_end < listing_heading
    assert "" in before_lines[header_end + 1:listing_heading]
    assert all("[Original " in line and "[eng]" in line for line in track_lines)
    assert "Track ID 777" not in before_report
    assert "literal/name/value" not in before_report and "jpn" not in before_report
    mismatch_names = names[0:1] + names[3:]
    for name in mismatch_names:
        assert name not in before_report
        assert name in final_report
    assert "Reordered metadata.mkv" not in result.stdout
    assert all(str(env["workdir"] / name) not in result.stdout for name in names)
    assert all(name not in result.stderr for name in names)
    _ascii_box_contains(final_report, "Errors", "Unusable first.mkv")
    _ascii_box_contains(final_report, "Track ID/type/codec mismatch", *names[3:])
    assert "[literal/name/value]" not in result.stdout and "jpn" not in result.stdout
    assert "S_TEXT/ASS" in track_lines[2]
    assert "Actions: " not in result.stdout + result.stderr
    picker_calls = _command_argv(env, "fzf")
    assert len(picker_calls) == 1
    picker = picker_calls[0]
    assert picker[picker.index("--delimiter") + 1] == "/"
    assert picker[picker.index("--with-nth") + 1] == "-1"
    assert picker.count("--read0") == picker.count("--print0") == 1
    inspections = _command_argv(env, "mkvmerge")
    assert len(inspections) == len(files)
    assert {call[1] for call in inspections} == {str(path) for path in files}
    assert not _command_argv(env, "mkvpropedit")
    assert not [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    assert not _command_argv(env, "mkvextract")
    assert all(path.read_text(encoding="utf-8") == "payload" for path in files)


@pytest.mark.parametrize("case", ["single-match", "all-unusable"])
def test_mkv_utils_analyze_single_match_and_no_usable_reference(env, case):
    if case == "single-match":
        files = [_mkv_file(env, "Only source.mkv")]
        models = {str(files[0]): _source_json([(12, "audio", "A_AAC", True)])}
        expected = "Files analyzed: 1; Matching: 1; Mismatched: 0; Failed: 0; Not attempted: 0"
        return_code = 0
    else:
        files = [_mkv_file(env, "Bad one.mkv"), _mkv_file(env, "Bad two.mkv")]
        models = {str(path): "{" for path in files}
        expected = "Files analyzed: 0; Matching: 0; Mismatched: 0; Failed: 2; Not attempted: 0"
        return_code = 1
    overrides = env["fake_bin"].parent / "analysis-source-json.json"
    overrides.write_text(json.dumps(models), encoding="utf-8")
    result = _run_mkv_utils(
        env, input_data="4\n", fzf_responses=[list(map(str, files))],
        extra_env={"TEST_FAKE_MKVMERGE_JSON_BY_PATH": str(overrides), "TERM": "dumb"},
    )
    assert result.returncode == return_code, result.stdout + result.stderr
    assert expected in result.stdout
    assert "Analysing" not in result.stdout + result.stderr and "\x1b" not in result.stdout + result.stderr
    before_report, separator, final_report = result.stdout.partition("Final report")
    assert separator and result.stdout.count("Final report") == 1
    _ascii_box_contains(result.stdout, "Final report")
    if case == "all-unusable":
        assert "No usable reference file." in final_report
        assert "mkvmerge JSON track listing" not in result.stdout + result.stderr
        assert all(name in final_report and name not in before_report for name in ("Bad one.mkv", "Bad two.mkv"))
        assert all(name not in result.stderr for name in ("Bad one.mkv", "Bad two.mkv"))
    else:
        assert "No usable reference file." not in result.stdout
        assert before_report.count("mkvmerge JSON track listing") == 1
        assert before_report.count("Analysis reference file: Only source.mkv") == 1
        assert before_report.count("Track ID 12: audio (A_AAC)") == 1
        _ascii_box_contains(before_report, "Analysis", f"Current Work Dir: {env['workdir']}",
                             "Analysis reference file: Only source.mkv")
        assert "Only source.mkv" not in final_report.partition("Reference file:")[0]
    inspections = _command_argv(env, "mkvmerge")
    assert len(inspections) == len(files)
    assert {call[1] for call in inspections} == {str(path) for path in files}
    assert not _command_argv(env, "mkvpropedit")
    assert not [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    assert not _command_argv(env, "mkvextract")
    assert all(path.read_text(encoding="utf-8") == "payload" for path in files)


def test_mkv_utils_display_projection_keeps_internal_paths_and_literal_slashes(env):
    source_file = _mkv_file(env, "Source file.mkv")
    reference_file = _mkv_file(env, "Reference file.mkv")
    result = _run_planning_contract(env, r'''
source="$PWD/Source file.mkv"
destination="$PWD/Output file.mka"
reference="$PWD/Reference file.mkv"
staged="$PWD/.mkvutil/staged file.mka"
job="$(jq -cn --arg source "$source" --arg destination "$destination" --arg output "$PWD/Output track.flac" '{source:$source,destination:$destination,config:{category:"extract",operations:["2"],removed_ids:[]},preview:{title:"literal/title",tracks:[{original_id:"12",final_position:1,type:"subtitles",codec:"S_TEXT/ASS",name:"literal/name",language:"x/slash",default:false,forced:false}]},requested_metadata:[],outputs:[{kind:"track",id:"12",path:$output,artifacts:[{role:"primary",required:true,path:$output}]}]}')"
raw_source="$(jq -r '.source' <<< "$job")"
MKVUTIL_JOBS=("$job")
MKVUTIL_LEDGER_ENABLED=0
preview="$(mkvutil_preview_jobs)"
[[ "$preview" == *'Source: Source file.mkv'* && "$preview" == *'Destination: Output file.mka'* ]] || fail 'preview did not shorten media paths'
[[ "$preview" == *'Extract track 12: Output track.flac'* ]] || fail 'preview did not shorten extraction output'
[[ "$preview" == *'name="literal/name"'* && "$preview" == *'language="x/slash"'* && "$preview" == *'S_TEXT/ASS'* ]] || fail 'preview changed slash-containing metadata'
[[ "$preview" != *"$PWD/"* ]] || fail 'preview printed a full path'
eq "$(jq -r '.source' <<< "$job")" "$raw_source" 'raw job path remains full'
result="$(jq -cn --arg source "$source" --arg destination "$destination" --arg staged "$staged" --arg reference "$reference" '{source:$source,destination:$destination,status:"failed",phase:"preflight",actual_state:"unpublished",reason:("Destination exists: "+$destination),candidate_path:$destination,phase_receipt:$staged,staged_paths:[$staged],phase_receipts:[],scratch_paths:[],unexpected_paths:[],cleanup_error:("Cleanup failed: "+$staged),inventory_errors:["Inventory could not inspect "+$staged],remaining_staging_directories:[$staged]}')"
rendered_result="$(mkvutil_report_result "$result")"
[[ "$rendered_result" == *'failed: Source file.mkv'* && "$rendered_result" == *'Destination: Output file.mka'* ]] || fail 'result report did not shorten source/destination'
[[ "$rendered_result" == *'Candidate: Output file.mka'* && "$rendered_result" == *'Staged: staged file.mka'* ]] || fail 'result report did not shorten candidate/staging paths'
[[ "$rendered_result" == *'Destination exists: Output file.mka'* && "$rendered_result" == *'Cleanup failed: staged file.mka'* ]] || fail 'result diagnostic paths were not shortened'
[[ "$rendered_result" != *"$PWD/"* ]] || fail 'result report printed a full path'
eq "$(jq -r '.source' <<< "$result")" "$source" 'raw result path remains full'
quoted_source="$PWD/Source \"quoted\".mkv"
quoted_destination="$PWD/Output \"quoted\".mka"
quoted_reason="$(jq -cn --arg source "$quoted_source" --arg destination "$quoted_destination" '{source:$source,destination:$destination}')"
quoted_result="$(jq -cn --arg source "$quoted_source" --arg destination "$quoted_destination" --arg reason "$quoted_reason" '{source:$source,destination:$destination,status:"failed",phase:"preflight",actual_state:"unpublished",reason:$reason}')"
eq "$(jq -r '.source' <<< "$quoted_result")" "$quoted_source" 'raw quoted source path remains full'
eq "$(jq -r '.destination' <<< "$quoted_result")" "$quoted_destination" 'raw quoted destination path remains full'
eq "$(jq -r '.reason' <<< "$quoted_result")" "$quoted_reason" 'raw JSON reason retains full quoted paths'
quoted_report="$(mkvutil_report_result "$quoted_result")"
quoted_diagnostic="$(jq -Rr 'select(startswith("  {"))|ltrimstr("  ")' <<< "$quoted_report")"
[[ -n "$quoted_diagnostic" ]] || fail 'rendered JSON diagnostic missing'
eq "$(jq -r '.source' <<< "$quoted_diagnostic")" 'Source "quoted".mkv' 'rendered JSON source path is basename'
eq "$(jq -r '.destination' <<< "$quoted_diagnostic")" 'Output "quoted".mka' 'rendered JSON destination path is basename'
receipt="$(jq -cn --arg source "$source" --arg reference "$reference" '{source:$source,reference:$reference,reasons:[{original_id:"12",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}')"
skips="$(mkvutil_report_removal_skips "$receipt")"
[[ "$skips" == *'Skipped removal mismatch: Source file.mkv'* && "$skips" == *'Reference: Reference file.mkv'* ]] || fail 'skip report did not shorten paths'
[[ "$skips" == *'codec_id":"S_TEXT/ASS"'* && "$skips" == *'codec_id":"S_TEXT/UTF8"'* ]] || fail 'skip report changed codec metadata'
collision="$(jq -cn --arg source "$PWD/Source file.mkv" --arg protected "$PWD/Reference file.mkv" '{source:$source,config:{category:"mux"},outputs:[$protected]}')"
diagnostic="$(mkvutil_check_destinations "$collision" 2>&1)" && fail 'accepted existing protected output'
[[ "$diagnostic" == *'Destination already exists or is unsafe: Reference file.mkv'* ]] || fail 'preflight diagnostic did not shorten destination'
[[ "$diagnostic" != *"$PWD/"* ]] || fail 'preflight diagnostic printed a full path'
summary="$(jq -cn --arg source "$source" --arg destination "$destination" --arg staged "$staged" --arg reference "$reference" '{directory:"workdir",elapsed_seconds:0,interrupted:true,batches:[{id:1,state:"interrupted",category:"mux",action_ids:["1"],metadata_ids:"",sources:[$source],eligible:1,attempted:0,completed:0,elapsed_seconds:0,outcomes:{},stop:{mode:"signal",not_started_sources:[$source]}}],selected:1,required:1,counts:{done:0,failed:0,warning:0,partial:0,skipped:1,excluded:0,not_attempted:0,interrupted:0},attachments:{processed:0,published:0,unique_names:0,superseded:0,uncertain_names:0,publications:[]},files:[{status:"skipped",source:$source,destination:$destination,exclusion_reason:null,skip_history:[{resolved:false,batch_ids:[1],receipt:{reference:$reference,reasons:[{original_id:"12",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}}],attempts:[{batch_id:1,result:{phase:"preflight",actual_state:"unpublished",status:"failed",reason:("Source unavailable: "+$source),staged_paths:[$staged],discarded_partial_tracks:[],scratch_paths:[],unexpected_paths:[],cleanup_error:null,inventory_errors:[],remaining_staging_directories:[],uncertain_artifacts:[]}}]}]}')"
eq "$(jq -r '.files[0].source' <<< "$summary")" "$source" 'raw summary path remains full'
report="$(mkvutil_format_final_report "$summary")"
[[ "$report" == *'| Source file.mkv => Output file.mka'* && "$report" == *'reference Reference file.mkv'* ]] || fail 'final report did not shorten source, destination and mismatch reference'
[[ "$report" == *'Files not started due to stop: 1'* && "$report" == *'    Source file.mkv'* && "$report" == *'Staged: staged file.mka'* ]] || fail 'final report did not shorten missed/staging names'
[[ "$report" == *'Source unavailable: Source file.mkv'* && "$report" == *'S_TEXT/ASS'* ]] || fail 'final report changed reason or literal codec'
[[ "$report" != *"$PWD/"* ]] || fail 'final report printed a full path'
print -r -- 'display projection contracts passed'
''', {
        str(source_file): _source_json([(0, "video", "V_MPEG4/ISO/AVC", True)]),
        str(reference_file): _source_json([(0, "video", "V_MPEG4/ISO/AVC", True)]),
    })
    assert result.stdout.rstrip().endswith("display projection contracts passed")


def test_mkv_utils_reports_hide_internal_state_and_routine_success_rows(env):
    result = _run_planning_contract(env, r'''
same="$PWD/Same file.mkv"
same_edit="$PWD/Same edit.mkv"
warning="$PWD/Warning file.mkv"
renamed="$PWD/Renamed file.mkv"
renamed_output="$PWD/Renamed file.mka"
extracted="$PWD/Extracted file.mkv"
track="$PWD/English Commentary - Track [3].srt"
failed="$PWD/Failure.mkv"
staged="$PWD/.mkvutil-stage/track.partial.srt"
recovery="$PWD/.mkvutil-stage"
skipped="$PWD/Skipped file.mkv"
reference="$PWD/Reference file.mkv"
summary="$(jq -cn --arg same "$same" --arg same_edit "$same_edit" --arg warning "$warning" --arg renamed "$renamed" --arg renamed_output "$renamed_output" \
  --arg extracted "$extracted" --arg track "$track" --arg failed "$failed" --arg staged "$staged" \
  --arg recovery "$recovery" --arg skipped "$skipped" --arg reference "$reference" '
  {directory:"workdir",elapsed_seconds:7,interrupted:false,selected:7,required:7,
   counts:{done:4,failed:0,warning:1,partial:1,skipped:1,excluded:0,not_attempted:0,interrupted:0},
   batches:[{id:1,state:"executed",category:"mux",action_ids:["2"],metadata_ids:"",sources:[$same,$same_edit,$warning,$renamed,$extracted,$failed,$skipped],eligible:7,attempted:6,completed:4,elapsed_seconds:6,outcomes:{done:4,warning:1,partial:1,skipped:1},stop:null}],
   attachments:{processed:0,published:0,unique_names:0,superseded:0,uncertain_names:0,publications:[]},
   files:[
    {source:$same,destination:$same,status:"success",skip_history:[],attempts:[{batch_id:1,result:{category:"mux",status:"success",phase:"complete",actual_state:"replaced_complete",reason:"",stages:[{kind:"mux",status:"complete",native_code:0}]}}]},
    {source:$same_edit,destination:$same_edit,status:"success",skip_history:[],attempts:[{batch_id:1,result:{category:"edit",status:"success",phase:"complete",actual_state:"edited_observed",reason:"",stages:[{kind:"edit",status:"complete",native_code:0}]}}]},
    {source:$warning,destination:$warning,status:"warning",skip_history:[],attempts:[{batch_id:1,result:{category:"mux",status:"warning",phase:"complete",actual_state:"replaced_complete",reason:"Metadata warning retained",state_description:"The replacement was saved with a warning.",stages:[{kind:"mux",status:"warning",native_code:0}]}}]},
    {source:$renamed,destination:$renamed_output,status:"success",skip_history:[],attempts:[{batch_id:1,result:{category:"mux",status:"success",phase:"complete",actual_state:"published_complete",reason:"",stages:[{kind:"mux",status:"complete",native_code:0}]}}]},
    {source:$extracted,destination:$extracted,status:"success",skip_history:[],attempts:[{batch_id:1,result:{category:"extract",status:"success",phase:"complete",actual_state:"sidecars_published",reason:"",stages:[{kind:"tracks",status:"complete",native_code:0}],artifacts:[{kind:"track",id:"3",path:$track,publication_state:"confirmed"}]}}]},
    {source:$failed,destination:$failed,status:"partial",skip_history:[],attempts:[{batch_id:1,result:{category:"mux",status:"partial",phase:"publishing",actual_state:"publication_uncertain",reason:"Destination publication uncertain",stages:[{kind:"mux",status:"failed",native_code:2}],staged_paths:[$staged],cleanup_error:"Cleanup could not remove candidate",inventory_errors:["Recovery inventory incomplete"],remaining_staging_directories:[$recovery],uncertain_artifacts:[{path:$staged}]}}]},
    {source:$skipped,destination:$skipped,status:"skipped",skip_history:[{resolved:false,batch_ids:[1],receipt:{reference:$reference,track_count_mismatch:{expected:5,actual:4},reasons:[{original_id:"12",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}}],attempts:[]}
   ]}')"
raw_summary="$summary"
report="$(mkvutil_format_final_report "$summary")"
eq "$summary" "$raw_summary" 'formatter leaves raw summary unchanged'
[[ "$report" == *"Done: 4"* && "$report" == *"Warning: 1"* && "$report" == *"Partial: 1"* && "$report" == *"Skipped: 1"* ]] || fail 'aggregate outcomes changed while filtering routine rows'
[[ "$report" != *"Same file.mkv"* && "$report" != *"Same edit.mkv"* ]] || fail 'unchanged successful Edit/Mux file was listed'
[[ "$report" == *"| Warnings"* && "$report" == *"| Warning file.mkv"* && "$report" == *"Metadata warning retained"* ]] || fail 'warning details are not inside their outcome box'
[[ "$report" == *"Renamed file.mkv => Renamed file.mka"* ]] || fail 'meaningful rename output is missing'
[[ "$report" == *"| Outputs"* && "$report" == *"| Renamed file.mkv => Renamed file.mka"* ]] || fail 'successful output is not inside the Outputs box'
[[ "$report" == *"| Extracted file.mkv"* && "$report" == *"English Commentary - Track [3].srt"* ]] || fail 'published track outputs are missing'
[[ "$report" == *"Failure.mkv"* && "$report" == *"Destination publication uncertain"* ]] || fail 'failure outcome is missing'
[[ "$report" == *"mux: failed (tool exit 2)"* ]] || fail 'failed stage details are missing'
[[ "$report" == *"Staged: track.partial.srt"* && "$report" == *"Retained staging directory: .mkvutil-stage"* ]] || fail 'recovery paths are missing'
[[ "$report" == *"Skip history: unresolved; configurations 1; reference Reference file.mkv"* ]] || fail 'skip history is missing'
[[ "$report" == *"| Skipped"* && "$report" == *"| Skipped file.mkv"* ]] || fail 'skip details are not inside their outcome box'
[[ "$report" == *"Track count mismatch: expected 5; actual 4"* && "$report" == *"codec-mismatch"* ]] || fail 'skip receipt details are missing'
[[ "$report" != *"Phase:"* && "$report" != *"phase="* && "$report" != *"actual state"* ]] || fail 'internal phase/state labels leaked'
[[ "$report" != *"replaced_complete"* && "$report" != *"published_complete"* && "$report" != *"sidecars_published"* && "$report" != *"publication_uncertain"* ]] || fail 'internal state enum leaked'
[[ "$report" != *"Stage mux: complete"* && "$report" != *"code=0"* ]] || fail 'completed stage detail was not suppressed'

status_summary="$(jq -cn '
  {directory:"workdir",elapsed_seconds:0,interrupted:false,selected:9,required:9,
   counts:{done:1,failed:1,warning:1,partial:1,skipped:1,excluded:1,not_attempted:2,interrupted:1},
   batches:[{id:1,state:"executed",category:"mux",action_ids:[],metadata_ids:"",sources:[],eligible:9,attempted:0,completed:0,elapsed_seconds:0,outcomes:{},stop:null}],
   attachments:{processed:0,published:0,unique_names:0,superseded:0,uncertain_names:0,publications:[]},
   files:[
    {source:"Error case.mkv",status:"failed",skip_history:[],attempts:[{batch_id:1,result:{status:"failed",reason:"error reason"}}]},
    {source:"Warning case.mkv",status:"warning",skip_history:[],attempts:[{batch_id:1,result:{status:"warning",reason:"warning reason"}}]},
    {source:"Partial case.mkv",status:"partial",skip_history:[],attempts:[{batch_id:1,result:{status:"partial",reason:"partial reason"}}]},
    {source:"Skipped case.mkv",status:"skipped",skip_history:[],attempts:[]},
    {source:"Excluded case.mkv",status:"excluded",exclusion_reason:"user choice",skip_history:[],attempts:[]},
    {source:"Interrupted case.mkv",status:"interrupted",skip_history:[],attempts:[{batch_id:1,result:{status:"interrupted",reason:"signal"}}]},
    {source:"Not attempted case.mkv",status:"not_attempted",skip_history:[],attempts:[]},
    {source:"Pending case.mkv",status:"pending",skip_history:[],attempts:[]},
    {source:"Simulated case.mkv",status:"success",skip_history:[],attempts:[{batch_id:1,result:{status:"success",simulated:true}}]}
   ]}')"
status_report="$(mkvutil_format_final_report "$status_summary")"
for group_name in Errors Warnings 'Partial results' Skipped Excluded Interrupted 'Not attempted' Simulated; do
  case "$group_name" in
    Errors) file_name='Error case.mkv' ;;
    Warnings) file_name='Warning case.mkv' ;;
    'Partial results') file_name='Partial case.mkv' ;;
    Skipped) file_name='Skipped case.mkv' ;;
    Excluded) file_name='Excluded case.mkv' ;;
    Interrupted) file_name='Interrupted case.mkv' ;;
    'Not attempted') file_name='Not attempted case.mkv' ;;
    Simulated) file_name='Simulated case.mkv' ;;
  esac
  [[ "$status_report" == *"| $group_name"* && "$status_report" == *"| $file_name"* ]] || fail "filename-only row missing from $group_name"
done
[[ "$status_report" == *"| Pending case.mkv"* ]] || fail 'pending file missing from Not attempted'
[[ "$status_report" == *"| Error case.mkv"* && "$status_report" != *"failed: Error case.mkv"* &&
   "$status_report" == *"| Warning case.mkv"* && "$status_report" != *"warning: Warning case.mkv"* &&
   "$status_report" == *"| Partial case.mkv"* && "$status_report" != *"partial: Partial case.mkv"* ]] || fail 'outcome labels leaked into file rows'
dry_summary="$(jq -cn '{directory:"workdir",dry_run:true,elapsed_seconds:0,interrupted:false,selected:0,required:0,
  counts:{done:0,failed:0,warning:0,partial:0,skipped:0,excluded:0,not_attempted:0,interrupted:0},
  batches:[],attachments:{processed:0,published:0,unique_names:0,superseded:0,uncertain_names:0,publications:[]},files:[]}')"
dry_report="$(mkvutil_format_final_report "$dry_summary")"
[[ "$dry_report" == *"| Simulated"* && "$dry_report" == *"| Files were not changed."* ]] || fail 'simulated note-only outcome changed'

per_job="$(jq -cn --arg source "$failed" --arg staged "$staged" \
  '{source:$source,destination:$source,category:"mux",status:"partial",phase:"publishing",actual_state:"publication_uncertain",reason:"Destination publication uncertain",staged_paths:[$staged],stages:[{kind:"mux",status:"failed",native_code:2}],artifacts:[{kind:"track",id:"3",path:$staged,publication_state:"uncertain"}]}')"
rendered="$(mkvutil_report_result "$per_job")"
[[ "$rendered" == *"Failure.mkv"* && "$rendered" == *"Destination publication uncertain"* && "$rendered" == *"track.partial.srt"* ]] || fail 'per-job failure details are missing'
[[ "$rendered" != *"Phase:"* && "$rendered" != *"actual state"* && "$rendered" != *"publication_uncertain"* ]] || fail 'per-job internal state leaked'
print -r -- 'human report contracts passed'
''', {})
    assert result.stdout.rstrip().endswith("human report contracts passed")


def test_mkv_utils_public_order_normalizer_bare_ids_and_retained_zero(env):
    result = _run_planning_contract(env, r'''
eq "$(mkvutil_normalize_order '3,4,1' '0,1,3,4,7')" '0:0,0:3,0:4,0:1' 'automatic zero prefix'
eq "$(mkvutil_normalize_order '3,0,4' '0,1,3,4')" '0:3,0:0,0:4' 'explicit zero position'
eq "$(mkvutil_normalize_order '3,1,0' '0,1,2,3')" '0:3,0:1,0:0' 'explicit video last'
eq "$(mkvutil_normalize_order ' 03 , 4 ' '0,1,3,4')" '0:0,0:3,0:4' 'separator whitespace and canonical IDs'
eq "$(mkvutil_normalize_order '3,4' '1,3,4')" '0:3,0:4' 'missing or removed zero stays absent'
for invalid in '7' '0:7' '0:3,0:4' '3,4,1,1' '1,01' '3,3' '3,,4' '3 4' '3,4 1' '3,99' '3,x' '3-4' ''; do
  captured=''
  if captured="$(mkvutil_normalize_order "$invalid" '0,1,3,4,7')"; then fail "accepted $invalid"; fi
  eq "$captured" '' 'no partial normalization on error'
done
reject mkvutil_normalize_order '0,3' '1,3,4'
print -r -- 'public order contracts passed'
''', {})
    assert result.stdout.rstrip().endswith("public order contracts passed")


@pytest.mark.parametrize("category", ("edit", "mux", "extract"))
def test_mkv_utils_dry_queue_dispatch_never_reaches_native_or_writes(env, category):
    source = _mkv_file(env, "Dry source.mkv")
    before = {p.relative_to(env["workdir"]): p.read_bytes() for p in env["workdir"].rglob("*") if p.is_file()}
    result = _run_planning_contract(env, r'''
source="$PWD/Dry source.mkv"
identity="$(mkvutil_source_identity "$source")"
category="$TEST_DRY_CATEGORY"
job="$(jq -cn --arg source "$source" --arg category "$category" --argjson identity "$identity" '
  {source:$source,identity:$identity,destination:(if $category=="extract" then ($source|sub("/[^/]+$";"/Attachments")) else $source end),
   config:{category:$category,operations:(if $category=="extract" then ["1","2"] elif $category=="mux" then ["2"] else ["5"] end),metadata:"",
     removed_ids:[],order:"",order_ids:[],extract_ids:[],settings:{},expected_types:{}},
   outputs:(if $category!="extract" then [$source] else [
     {kind:"attachment",id:"1",path:($source|sub("/[^/]+$";"/Attachments/font.ttf")),artifacts:[{path:($source|sub("/[^/]+$";"/Attachments/font.ttf")),required:true}]},
     {kind:"track",id:"3",path:($source+".sub"),artifacts:[{path:($source+".sub"),required:true},{path:($source+".idx"),required:true}]},
     {kind:"track",id:"4",path:($source+".wv"),artifacts:[{path:($source+".wv"),required:true},{path:($source+".wvc"),required:false}]}] end)}')"
mkvutil_execute_edit_job() { fail 'edit executor reached'; }
mkvutil_execute_mux_job() { fail 'mux executor reached'; }
mkvutil_execute_extract_job() { fail 'extract executor reached'; }
mkvutil_capture_source() { fail 'native inspection reached'; }
MKVUTIL_DRY_RUN=1
mkvutil_ledger_reset "$PWD" "$source"
mkvutil_execute_queue "$job"
summary="$(mkvutil_final_summary)"
jq -e '.dry_run and .batches[0].dry_run and .counts.done==1 and
  (.files[0].attempts[0].result | .simulated and .phase=="simulated" and .native_code==null and
    .actual_state=="not_modified_by_job" and .artifacts==[] and .publications==[] and .stages==[])' <<< "$summary" >/dev/null
eq "$MKVUTIL_ENGINE_CONTROL" '' 'no engine transport'
mkvutil_final_report
print -r -- "SUMMARY $summary"
''', {}, extra_env={"TEST_DRY_CATEGORY": category})
    after = {p.relative_to(env["workdir"]): p.read_bytes() for p in env["workdir"].rglob("*") if p.is_file()}
    assert after == before
    assert not (env["workdir"] / "Attachments").exists()
    assert "(DRYRUN)" in result.stdout and "Simulated: 1; Failed: 0" in result.stdout
    assert "Done:" not in result.stdout and "Output:" not in result.stdout and "Outputs from:" not in result.stdout
    human_output = "\n".join(line for line in result.stdout.splitlines() if not line.startswith("SUMMARY "))
    assert str(env["workdir"]) not in human_output
    assert "| Simulated" in human_output and "| Files were not changed." in human_output
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    planned = summary["files"][0]["attempts"][0]["result"]["planned_outputs"]
    if category == "extract":
        assert len(planned) == 5 and planned[-1]["path"].endswith(".wvc") and planned[-1]["required"] is False
        assert {Path(p["path"]).suffix for p in planned} == {".ttf", ".sub", ".idx", ".wv", ".wvc"}
        assert "Track stage:" not in result.stdout and "Files Simulated: 1" in result.stdout
        assert "|   Would write: font.ttf" in result.stdout and "|   Would extract: Dry source.mkv.idx" in result.stdout, result.stdout
        assert "published:" not in result.stdout
        assert summary["batches"][0]["track_stages_attempted"] == 0
    else:
        assert planned == [{"path": str(source), "kind": category, "id": None, "required": True}]
        assert f"Would {'update' if category == 'edit' else 'write'}: {source.name}" in result.stdout
    assert not _command_argv(env, "mkvmerge")
    assert not _command_argv(env, "mkvpropedit")
    assert not _command_argv(env, "mkvextract")


@pytest.mark.parametrize("category", ("edit", "mux", "extract"))
def test_mkv_utils_target_guard_planning_whole_job_skip_and_config_validity(env, category):
    source = _mkv_file(env, "Targets.mkv")
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (1, "audio", "A_AAC", True),
                          (2, "subtitles", "S_TEXT/ASS", False)],
                         attachments=[{"id": 1, "file_name": "font.ttf", "size": 4}])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/Targets.mkv")"
MKVUTIL_CODEC_EXT_JSON='{"AAC":"aac"}'
config="$(jq -cn --arg category "$TEST_GUARD_CATEGORY" '
 {category:$category,operations:(if $category=="edit" then ["4"] elif $category=="mux" then ["2"] else ["1","2"] end),
  removed_ids:[],order:(if $category=="mux" then "0:1" else "" end),order_ids:(if $category=="mux" then ["1"] else [] end),
  metadata:"",settings:(if $category=="edit" then {"4:1":"New name"} else {} end),expected_types:{"1":"audio"},
  extract_ids:(if $category=="extract" then ["1"] else [] end)}')"
job="$(mkvutil_plan_job "$record" "$config")"
for variant in missing wrongtype; do
  if [[ "$variant" == missing ]]; then changed="$(jq '.model.tracks|=map(select(.id!=1))' <<< "$record")"
  else changed="$(jq '.model.tracks[1].type="subtitles"' <<< "$record")"; fi
  code=0; receipt="$(mkvutil_plan_job "$changed" "$config")" || code=$?
  eq "$code" 3 'incompatible target skips complete job'
  jq -e '.kind=="track-mismatch" and .requested_ids==["1"] and .outputs==[] and .propedit_args==[] and
    .merge_metadata_args==[] and .reasons[0].expected=={type:"audio"}' <<< "$receipt" >/dev/null
  if [[ "$variant" == missing ]]; then
    jq -e '.reasons[0].reason=="missing-id" and .reasons[0].actual==null' <<< "$receipt" >/dev/null
  else jq -e '.reasons[0].reason=="type-mismatch" and .reasons[0].actual=={type:"subtitles"}' <<< "$receipt" >/dev/null; fi
done
# Codec, names, language and unrelated track counts do not define this guard.
compatible="$(jq '.model.tracks[1].properties={codec_id:"A_OPUS",track_name:"Other",language:"jpn"}|.model.tracks|=map(select(.id!=2))' <<< "$record")"
mkvutil_target_mismatch "$compatible" "$config"
for invalid in 'null' '"metadata"' '17'; do
  bad="$(jq --argjson invalid "$invalid" '.expected_types["1"]=$invalid' <<< "$config")"
  code=0; captured="$(mkvutil_plan_job "$record" "$bad")" || code=$?
  eq "$code" 1 'malformed expected type fails rather than skips'
  eq "$captured" '' 'malformed config has no receipt or partial job'
done
reject mkvutil_validate_config "$(jq '.expected_types={}' <<< "$config")"
if [[ "$TEST_GUARD_CATEGORY" == extract ]]; then
  MKVUTIL_SOURCES=("$record")
  _mkvutil_read_track_ids() { fail 'attachments-only requested IDs'; }
  mkvutil_configure_category extract 1
  eq "$(jq -c '.extract_ids' <<< "$MKVUTIL_CONFIG")" '[]' 'attachments-only has no target IDs'
  attachment_job="$(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG")"
  jq -e '.outputs|length==1 and .[0].kind=="attachment" and .[0].id=="1"' <<< "$attachment_job" >/dev/null
fi
print -r -- 'target planning contracts passed'
''', {str(source): model}, extra_env={"TEST_GUARD_CATEGORY": category})
    assert result.stdout.rstrip().endswith("target planning contracts passed")
    assert source.read_bytes() == b"payload" and not (env["workdir"] / "Attachments").exists()


def test_mkv_utils_target_guard_mixed_and_all_skip_queue_ledger(env):
    good, missing, wrong = (_mkv_file(env, name) for name in ("Good.mkv", "Missing.mkv", "Wrong.mkv"))
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (1, "audio", "A_AAC", True)])
    result = _run_planning_contract(env, r'''
good="$(mkvutil_capture_source "$PWD/Good.mkv")"
missing="$(mkvutil_capture_source "$PWD/Missing.mkv")"
wrong="$(mkvutil_capture_source "$PWD/Wrong.mkv")"
config='{"category":"edit","operations":["4"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{"4:1":"Name"},"expected_types":{"1":"audio"},"extract_ids":[]}'
MKVUTIL_CONFIG="$config"; MKVUTIL_SOURCES=("$good" "$missing" "$wrong")
mkvutil_ledger_reset "$PWD" "$PWD/Good.mkv" "$PWD/Missing.mkv" "$PWD/Wrong.mkv"
mkvutil_batch_request edit 4 "$config"
_mkvutil_exclude() { fail 'mismatch requested exclusion'; }
mkvutil_plan_queue
eq "${#MKVUTIL_JOBS}" 1 'mixed queue retains compatible job'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 2 'mixed queue automatically skips incompatible jobs'
MKVUTIL_DRY_RUN=1
if mkvutil_execute_queue "${MKVUTIL_JOBS[@]}"; then fail 'unresolved skips reported success'; fi
summary="$(mkvutil_final_summary)"
jq -e '.counts.done==1 and .counts.skipped==2 and .counts.excluded==0 and .required==3 and
  ([.files[].skip_history[]|select(.resolved==false)]|length)==2' <<< "$summary" >/dev/null
MKVUTIL_DRY_RUN=0
mkvutil_ledger_reset "$PWD" "$PWD/Missing.mkv" "$PWD/Wrong.mkv"
MKVUTIL_CONFIG="$config"; MKVUTIL_SOURCES=("$missing" "$wrong")
mkvutil_batch_request edit 4 "$config"
code=0; mkvutil_plan_queue || code=$?
eq "$code" 3 'all skipped planning exits without a runnable job'
eq "${#MKVUTIL_JOBS}" 0 'all skipped queue has no writes'
reject mkvutil_ledger_status
report="$(mkvutil_format_final_report "$(mkvutil_final_summary)")"
[[ "$report" == *'Skipped: 2'* && "$report" == *'missing-id'* && "$report" == *'type-mismatch'* ]] || fail 'final mismatch diagnostics missing'
print -r -- 'target queue contracts passed'
''', {str(good): model, str(missing): _source_json([(0, "video", "V_MPEG4/ISO/AVC", True)]),
      str(wrong): _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (1, "subtitles", "S_TEXT/ASS", False)])})
    assert result.stdout.rstrip().endswith("target queue contracts passed")
    assert all(source.read_bytes() == b"payload" for source in (good, missing, wrong))


@pytest.mark.parametrize("category", ("edit", "mux", "extract"))
def test_mkv_utils_runtime_shared_guard_skips_before_engine_and_preserves_failures(env, category):
    source = _mkv_file(env, "Runtime.mkv")
    model = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (1, "audio", "A_AAC", True),
                          (2, "subtitles", "S_TEXT/ASS", False)],
                         attachments=[{"id": 1, "file_name": "font.ttf", "size": 4}])
    result = _run_planning_contract(env, r'''
source="$PWD/Runtime.mkv"
record="$(mkvutil_capture_source "$source")"
MKVUTIL_CODEC_EXT_JSON='{"AAC":"aac"}'
config="$(jq -cn --arg category "$TEST_GUARD_CATEGORY" '
 {category:$category,operations:(if $category=="edit" then ["4"] elif $category=="mux" then ["2"] else ["1","2"] end),
  removed_ids:[],order:(if $category=="mux" then "0:1" else "" end),order_ids:(if $category=="mux" then ["1"] else [] end),
  metadata:"",settings:(if $category=="edit" then {"4:1":"Name"} else {} end),expected_types:{"1":"audio"},
  extract_ids:(if $category=="extract" then ["1"] else [] end)}')"
job="$(mkvutil_plan_job "$record" "$config")"
executor="mkvutil_execute_${TEST_GUARD_CATEGORY}_job"
engine_calls=0
_mkvutil_execution_engine() { (( ++engine_calls )); fail 'native engine reached'; }
_mkvutil_extract_engine() { (( ++engine_calls )); fail 'extract engine reached'; }
_mkvutil_capture_execution_source() { REPLY="$fresh_record"; }
for variant in missing wrongtype; do
  if [[ "$variant" == missing ]]; then fresh_record="$(jq '.model.tracks|=map(select(.id!=1))' <<< "$record")"
  else fresh_record="$(jq '.model.tracks[1].type="subtitles"' <<< "$record")"; fi
  reject "$executor" "$job"
  jq -e '.status=="skipped" and .skip_receipt.kind=="track-mismatch" and .native_code==null and
    .phase=="preflight" and .actual_state=="not_modified_by_job" and .artifacts==[] and .planned_outputs==[] and
    (.reason|startswith("Selected track IDs"))' <<< "$MKVUTIL_RESULT_JSON" >/dev/null || fail "wrong target result: $MKVUTIL_RESULT_JSON"
done
fresh_record="$(jq '.model.tracks[1].properties.codec_id="A_OPUS"' <<< "$record")"
_mkvutil_preflight_job "$job"
# A replacement before the queued job starts has a fresh, valid identity.
python3 -c 'import os,sys;from pathlib import Path;p=Path(sys.argv[1]);r=p.with_suffix(".replacement");r.write_bytes(b"replacement bytes");os.replace(r,p)' "$source"
fresh_record="$(jq --argjson identity "$(mkvutil_source_identity "$source")" '.identity=$identity' <<< "$record")"
reject "$executor" "$job"
jq -e '.status=="skipped" and .skip_receipt.kind=="source-changed" and .skip_receipt.expected_identity==.skip_receipt.identity and
  .skip_receipt.actual_identity!=.skip_receipt.identity and .actual_state=="not_modified_by_job" and
  (.reason|startswith("Source changed"))' <<< "$MKVUTIL_RESULT_JSON" >/dev/null || fail "wrong source result: $MKVUTIL_RESULT_JSON"
fresh_record="$(jq '.identity.size=99' <<< "$record")"
reject "$executor" "$job"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" failed 'malformed identity remains failure'
_mkvutil_capture_execution_source() { return 1; }
reject "$executor" "$job"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" failed 'capture/stat failure remains failure'
eq "$engine_calls" 0 'all guards precede native engines'
eq "$MKVUTIL_ENGINE_CONTROL" '' 'no transport'
print -r -- 'runtime guard contracts passed'
''', {str(source): model}, extra_env={"TEST_GUARD_CATEGORY": category})
    assert result.stdout.rstrip().endswith("runtime guard contracts passed")
    assert source.read_bytes() == b"replacement bytes" and not (env["workdir"] / "Attachments").exists()


def test_mkv_utils_source_replacement_planning_receipts_precision_and_subset(env):
    source = _mkv_file(env, "Replacement.mkv")
    model = _source_json([(0, "audio", "A_AAC", True)])
    result = _run_planning_contract(env, r'''
source="$PWD/Replacement.mkv"
record="$(mkvutil_capture_source "$source")"
config='{"category":"edit","operations":["5"],"removed_ids":[],"order":"","order_ids":[],"metadata":"","settings":{"5:info":"Title"},"expected_types":{},"extract_ids":[]}'
python3 -c 'import os,sys;from pathlib import Path;p=Path(sys.argv[1]);r=p.with_suffix(".replacement");r.write_bytes(b"replacement before final Enter");os.replace(r,p)' "$source"
code=0; receipt="$(mkvutil_plan_job "$record" "$config")" || code=$?
eq "$code" 3 'replacement before final planning automatically skipped'
jq -e '.kind=="source-changed" and .expected_identity==.identity and .actual_identity!=.identity and .outputs==[] and .requested_ids==[]' <<< "$receipt" >/dev/null
mkvutil_ledger_reset "$PWD" "$source"
mkvutil_batch_request edit 5 "$config"
mkvutil_ledger_skip "$receipt"
shown="$(mkvutil_report_removal_skips "$receipt")"
report="$(mkvutil_format_final_report "$(mkvutil_final_summary)")"
preview="$(mkvutil_preview_jobs)"
for display in "$shown" "$report" "$preview"; do
  [[ "$display" == *'Source changed after inspection/planning; file was not processed'* ]] || fail 'human source skip reason missing'
  [[ "$display" != *'Original ID null'* && "$display" != *'expected_identity'* && "$display" != *'mtime_ns'* ]] || fail 'identity debug leaked'
done
MKVUTIL_JOBS=(); MKVUTIL_REMOVAL_SKIPS=("$receipt")
mkvutil_prepare_skipped_subset
eq "${#MKVUTIL_SOURCES}" 1 'source-changed subset refreshed'
# Decimal strings remain exact, including signed timestamps and huge inodes.
old='{"dev":"1","ino":"9007199254740992","size":"7","mtime_ns":"-12"}'
new='{"dev":"1","ino":"9007199254740993","size":"7","mtime_ns":"-12"}'
precise="$(jq --argjson identity "$old" '.identity=$identity' <<< "$record")"
code=0; precise_receipt="$(mkvutil_source_mismatch "$precise" "$new" "$config")" || code=$?
eq "$code" 3 'identity comparison retains more than 53 bits'
mkvutil_source_mismatch "$precise" "$old" "$config"
for invalid in 'null' '{}' '{"dev":"1","ino":"2","size":7,"mtime_ns":"12"}'; do
  code=0; captured="$(mkvutil_source_mismatch "$precise" "$invalid" "$config")" || code=$?
  eq "$code" 1 'malformed comparison is failure'
  eq "$captured" '' 'malformed comparison never emits skip'
done
badrecord="$(jq '.identity=null' <<< "$record")"
code=0; captured="$(mkvutil_plan_job "$badrecord" "$config")" || code=$?
eq "$code" 1 'malformed original identity remains failure'
mkvutil_source_identity() { return 1; }
code=0; captured="$(mkvutil_plan_job "$record" "$config")" || code=$?
eq "$code" 1 'stat failure remains failure'
print -r -- 'replacement planning contracts passed'
''', {str(source): model})
    assert result.stdout.rstrip().endswith("replacement planning contracts passed")
    assert source.read_bytes() == b"replacement before final Enter"


def test_mkv_utils_dry_identity_failure_and_engine_transport_guard(env):
    source = _mkv_file(env, "Changed.mkv")
    result = _run_planning_contract(env, r'''
source="$PWD/Changed.mkv"
identity="$(mkvutil_source_identity "$source")"
job="$(jq -cn --arg source "$source" --argjson identity "$identity" '{source:$source,destination:$source,identity:($identity|.size="999"),config:{category:"edit",operations:["5"],metadata:"",removed_ids:[],order:"",order_ids:[],extract_ids:[],settings:{},expected_types:{}},outputs:[$source]}')"
MKVUTIL_DRY_RUN=1
reject mkvutil_simulate_job "$job"
jq -e '.status=="skipped" and .skip_receipt.kind=="source-changed" and .dry_run and .actual_state=="not_modified_by_job" and .simulated==false and .planned_outputs==[]' <<< "$MKVUTIL_RESULT_JSON" >/dev/null
malformed="$(jq '.identity.size=999' <<< "$job")"
reject mkvutil_simulate_job "$malformed"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" failed 'malformed dry identity remains failure'
bad_config="$(jq '.config.operations=["4"]|.config.settings={"4:1":"Name"}|.config.expected_types={"1":"metadata"}' <<< "$job")"
reject mkvutil_simulate_job "$bad_config"
jq -e '.status=="failed" and .reason=="Invalid planned configuration" and .planned_outputs==[] and .simulated==false' <<< "$MKVUTIL_RESULT_JSON" >/dev/null
bad_config="$(jq '.config=null' <<< "$job")"
reject mkvutil_simulate_job "$bad_config"
eq "$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" failed 'missing dry config remains failure'
job="$(jq '.source="/missing/dry-source.mkv"' <<< "$job")"
reject mkvutil_simulate_job "$job"
jq -e '.status=="failed" and (.reason|contains("unavailable"))' <<< "$MKVUTIL_RESULT_JSON" >/dev/null
mktemp() { fail 'transport creation reached'; }
reject _mkvutil_launch_engine unused unused edit "$job"
jq -e '.status=="failed" and (.reason|contains("blocked in dry run"))' <<< "$MKVUTIL_RESULT_JSON" >/dev/null
eq "$MKVUTIL_ENGINE_CONTROL" '' 'guard leaves transport absent'
print -r -- 'dry failure and transport contracts passed'
''', {})
    assert source.read_bytes() == b"payload"
    assert result.stdout.rstrip().endswith("dry failure and transport contracts passed")


def test_mkv_utils_dry_all_skip_summary_and_unresolved_actual_history(env):
    source = _mkv_file(env, "Skipped.mkv")
    result = _run_planning_contract(env, r'''
source="$PWD/Skipped.mkv"
MKVUTIL_DRY_RUN=1
mkvutil_ledger_reset "$PWD" "$source"
mkvutil_batch_request mux 1
receipt="$(jq -cn --arg source "$source" '{source:$source,reference:$source,reasons:[],track_count_mismatch:{expected:3,actual:2}}')"
mkvutil_ledger_skip "$receipt"
mkvutil_batch_planned 0
summary="$(mkvutil_final_summary)"
jq -e '.dry_run and .batches[0].dry_run and .counts.skipped==1' <<< "$summary" >/dev/null
report="$(mkvutil_format_final_report "$summary")"
[[ "$report" == *'Final report (DRYRUN)'* && "$report" == *'Simulated: 0'* && "$report" == *'Skipped: 1'* ]] || fail 'all skip dry report'
job="$(jq -cn --arg source "$source" --argjson identity "$(mkvutil_source_identity "$source")" '{source:$source,destination:$source,identity:$identity,config:{category:"mux",operations:["2"],metadata:"",removed_ids:[],order:"",order_ids:[],extract_ids:[],settings:{},expected_types:{}},outputs:[$source]}')"
mkvutil_simulate_job "$job"
mkvutil_ledger_result "$MKVUTIL_RESULT_JSON"
jq -e '.status=="success" and .skip_history[0].resolved==false' <<< "${MKVUTIL_LEDGER[$source]}" >/dev/null
# Real success still resolves history under the unchanged ledger contract.
real="$(jq '.simulated=false' <<< "$MKVUTIL_RESULT_JSON")"
mkvutil_ledger_result "$real"
jq -e '.skip_history[0].resolved==true' <<< "${MKVUTIL_LEDGER[$source]}" >/dev/null
print -r -- 'dry skip history contracts passed'
''', {})
    assert result.stdout.rstrip().endswith("dry skip history contracts passed")
    assert source.read_bytes() == b"payload"


def test_mkv_utils_dry_flags_argument_order_reset_and_back_preservation(env):
    result = _run_planning_contract(env, r'''
reads=0
_mkvutil_menu_read() { (( ++reads )); REPLY=e; }
for arguments in 1 2 3; do
  case "$arguments" in
    1) mkvutil_main --dry-run "$PWD" --bypass ;;
    2) mkvutil_main "$PWD" --bypass --dry-run ;;
    3) mkvutil_main --bypass --dry-run "$PWD" ;;
  esac
  eq "$MKVUTIL_DRY_RUN" 1 'dry flag any argument order'
  eq "$MKVUTIL_BYPASS_TRACK_COUNT" 1 'bypass retained'
  mkvutil_ledger_reset "$PWD"
  mkvutil_reset_public_selection
  eq "$MKVUTIL_DRY_RUN" 1 'ledger and Back preserve invocation flag'
done
mkvutil_main "$PWD"
eq "$MKVUTIL_DRY_RUN" 0 'fresh invocation default'
mkvutil_main --dry-run --help
eq "$MKVUTIL_DRY_RUN" 1 'help accepts dry flag'
mkvutil_main --help --dry-run
eq "$MKVUTIL_DRY_RUN" 0 'help remains read-only'
eq "$reads" 4 'help never opens menus'
print -r -- 'dry CLI contracts passed'
''', {})
    assert result.stdout.rstrip().endswith("dry CLI contracts passed")

def test_mkv_utils_query_failure_adapter_targets_readonly_query(env):
    result=_run_planning_contract(env,r'''
reject jq -r '.tracks as $tracks | if ($tracks|length)==0 then error("empty tracks array") else $tracks end' <<< '{"tracks":[{"id":0}]}'
eq "$(jq -r '.tracks|length' <<< '{"tracks":[{"id":0}]}')" 1 'unrelated JSON remains delegated'
''',{},extra_env={"TEST_FAKE_JQ_FAIL_QUERY_CONTAINS":"empty tracks array"})
    assert "Injected read-only jq query failure: empty tracks array" in result.stderr


# These names preserve the single-action regression identities. The final
# required configuration value now starts processing automatically.
def _integration_model(tracks=None, *, attachments=None):
    model=_source_json(tracks or [(0,"video","V_MPEG4/ISO/AVC",True),(1,"audio","A_AAC",True),
                                 (2,"audio","A_OPUS",False),(3,"subtitles","S_TEXT/ASS",True)],attachments=attachments)
    for position,track in enumerate(model["tracks"]):
        track["properties"]["uid"]=18446744073709551000+position
    return model


def _integration_output(original, order):
    # Fixture expectation is supplied independently of command arguments.
    by_id={track["id"]:track for track in original["tracks"]}
    output=json.loads(json.dumps(original))
    output["tracks"]=[json.loads(json.dumps(by_id[tid])) for tid in order]
    for position,track in enumerate(output["tracks"]):track["id"]=position
    return output


def _integration_manifest(env,sources,**states):
    manifest=env["workdir"].parent/"menu-execution.json"
    manifest.write_text(json.dumps({"sources":{str(path):model for path,model in sources.items()},**states}))
    return {"TEST_FAKE_EXECUTION_JSON":str(manifest)}


def _observed_fake_identification(env,file):
    state=json.loads((env["fake_state"]/"execution-inodes.json").read_text())
    entry=file.stat()
    return state[f"{entry.st_dev}:{entry.st_ino}"]


def _single_edit_menu(env,filename,choice,prompts,expected):
    source=_mkv_file(env,filename);original=_integration_model()
    if choice==1:original["tracks"][0]["properties"]["forced_track"]=True
    if choice==2:original["tracks"][0]["properties"]["default_track"]=False
    actual=json.loads(json.dumps(original))
    if choice==5:actual["container"]["properties"]["title"]=""
    else:actual["tracks"][0]["properties"].update(expected)
    extra=_integration_manifest(env,{source:original},post_edit={str(source):actual})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data=f"1\n{choice}\n"+prompts,extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    assert len(_command_argv(env,"fzf"))==1 and "--multi" in _command_argv(env,"fzf")[0]
    assert "Done: 1; Failed: 0" in result.stdout and "Processed In:" not in result.stdout
    action_labels={1:"flag-forced",2:"flag-default",3:"language",4:"name",5:"file title"}
    assert f"Edit {choice}: {action_labels[choice]}" in result.stdout
    assert f"Processing: {source.name}" in result.stdout
    assert _observed_fake_identification(env,source)==actual
    assert all(argv[:1]==["-J"] for argv in _command_argv(env,"mkvmerge"))
    return source,result,_command_argv(env,"mkvpropedit")


def test_mkv_utils_option1_forced_flag_uses_one_based_track_selector(env):
    source,_,calls=_single_edit_menu(env,"forced.mkv",1,"0\n\n",{"forced_track":False})
    assert calls==[[str(source),"--normalize-language-ietf","off","--edit","track:1","--set","flag-forced=0"]]


def test_mkv_utils_option2_default_flag_defaults_to_one(env):
    source,_,calls=_single_edit_menu(env,"default.mkv",2,"0\n\n",{"default_track":True})
    assert calls==[[str(source),"--normalize-language-ietf","off","--edit","track:1","--set","flag-default=1"]]


def test_mkv_utils_option3_language_updates_track_language(env):
    source,_,calls=_single_edit_menu(env,"language.mkv",3,"0\neng\n",{"language":"eng","language_ietf":"en"})
    assert calls==[[str(source),"--normalize-language-ietf","off","--edit","track:1","--set","language=eng"]]


def test_mkv_utils_option4_name_updates_track_name(env):
    source,_,calls=_single_edit_menu(env,"rename.mkv",4,"0\nDialogue\n",{"track_name":"Dialogue"})
    assert calls==[[str(source),"--normalize-language-ietf","off","--edit","track:1","--set","name=Dialogue"]]


def test_mkv_utils_option4_handles_spaces_in_file_and_track_name(env):
    literal='English Stereo $cash: "quoted" @name'
    source,_,calls=_single_edit_menu(env,"Episode One.mkv",4,"0\n"+literal+"\n",{"track_name":literal})
    assert len(calls)==1 and calls[0][0]==str(source)
    assert "name="+literal in calls[0] and "English" not in calls[0] and "Stereo" not in calls[0]


def test_mkv_utils_option5_title_empty_input_deletes_title(env):
    source,_,calls=_single_edit_menu(env,"title.mkv",5,"\n",{})
    assert calls==[[str(source),"--normalize-language-ietf","off","--edit","info","--delete","title"]]


def test_mkv_utils_option1_multi_file_partial_failure_summary(env):
    first,second=_mkv_file(env,"multi_fail_a.mkv"),_mkv_file(env,"multi_fail_b.mkv")
    original=_integration_model();original["tracks"][0]["properties"]["forced_track"]=True
    actual=json.loads(json.dumps(original));actual["tracks"][0]["properties"]["forced_track"]=False
    extra=_integration_manifest(env,{first:original,second:original},post_edit={str(first):actual,str(second):actual})
    extra["TEST_FAKE_MKVPROPEDIT_FAIL_CALL"]="2"
    result=_run_mkv_utils(env,fzf_responses=[[str(first),str(second)]],input_data="1\n1\n0\n0\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Done: 1; Failed: 0; Warning: 1" in result.stdout and second.name in result.stdout
    assert len(_command_argv(env,"mkvpropedit"))==2 and "Processed In:" not in result.stdout
    assert first.read_bytes()==b"edited-data\n" and second.read_bytes()==b"payload"
    assert _observed_fake_identification(env,first)["tracks"][0]["properties"]["forced_track"] is False


def test_mkv_utils_option6_extracts_all_attachments(env):
    source=_mkv_file(env,"with_attachments2.mkv")
    embedded=[{"id":1,"file_name":"original $font.ttf","size":3},{"id":2,"file_name":"note.txt","size":4}]
    model=_integration_model(attachments=embedded)
    extra=_integration_manifest(env,{source:model},extraction={str(source):{"attachments":{"outputs":{"1":{"data":"one"},"2":{"data":"note"}}}}})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n1\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=_command_argv(env,"mkvextract")
    assert len(calls)==1 and calls[0][:2]==[str(source),"attachments"]
    assert "Extract 1: attachments" in result.stdout
    assert result.stdout.index("Extract 1: attachments") < result.stdout.index(f"Processing: {source.name}")
    assert [spec.split(":",1)[0] for spec in calls[0][2:]]==["1","2"]
    assert (env["workdir"]/"Attachments"/embedded[0]["file_name"]).read_bytes()==b"one"
    assert (env["workdir"]/"Attachments"/"note.txt").read_bytes()==b"note"
    assert source.read_bytes()==b"payload" and "Attachments processed: 2; published: 2; final unique published names: 2" in result.stdout


def test_mkv_utils_extract_track_id_retries_malformed_and_out_of_range_values(env):
    source = _mkv_file(env, "Retry track ID.mkv")
    model = _integration_model()
    extra = _integration_manifest(
        env, {source: model},
        extraction={str(source): {"tracks": {"outputs": {"1": {"data": "aac payload"}}}}},
    )
    result = _run_mkv_utils(
        env, fzf_responses=[[str(source)]], input_data="3\n2\nnot-an-id\n44\n1\n", extra_env=extra,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr.count("Extract IDs:") == 3
    calls = _command_argv(env, "mkvextract")
    assert len(calls) == 1 and calls[0][:2] == [str(source), "tracks"]
    assert (env["workdir"] / "Retry track ID - Track [1].aac").read_bytes() == b"aac payload"
    assert source.read_bytes() == b"payload" and result.stdout.count("Final report") == 1


def test_mkv_utils_option7_video_removal_converts_to_mka_and_keeps_other_tracks(env):
    source=_mkv_file(env,"remove_video.mkv");original=_integration_model();expected=_integration_output(original,[1,2,3])
    extra=_integration_manifest(env,{source:original},stage={str(source):expected})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n0\n\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=[argv for argv in _command_argv(env,"mkvmerge") if "-o" in argv]
    assert len(calls)==1 and "--no-video" in calls[0]
    assert calls[0][calls[0].index("--audio-tracks")+1]=="1,2" and calls[0][calls[0].index("--subtitle-tracks")+1]=="3"
    output=source.with_suffix(".mka")
    assert not source.exists() and output.read_bytes()==b"candidate-data\n"
    assert _observed_fake_identification(env,output)==expected and not _command_argv(env,"mkvpropedit")
    assert "Mux 1: remove" in result.stdout
    assert result.stdout.index("Mux 1: remove") < result.stdout.index(f"Processing: {source.name}")


def test_mkv_utils_option7_failure_cleans_temporary_file(env):
    # The approved safety policy retains failed candidates; the old legacy
    # stem_temp output remains absent and the original is still preserved.
    source=_mkv_file(env,"remove_fail.mkv");original=_integration_model()
    extra=_integration_manifest(env,{source:original},stage={str(source):_integration_output(original,[1,2,3])},merge_code=2)
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n0\n\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Failed: 1" in result.stdout and "Candidate:" in result.stdout
    report = result.stdout[result.stdout.index("Final report"):]
    assert report.count("Final report") == 1
    _ascii_box_contains(report, "Errors", f"{source.name} => {source.with_suffix('.mka').name}")
    assert f"failed: {source.name}" not in report
    assert source.read_bytes()==b"payload" and not source.with_suffix(".mka").exists()
    assert not (env["workdir"]/"remove_fail_temp.mka").exists()
    assert len([a for a in _command_argv(env,"mkvmerge") if "-o" in a])==1
    assert len(list(env["workdir"].glob(".mkvutil-*/candidate.mka")))==1


@pytest.mark.parametrize("extra_env",[
    {"TEST_FAKE_MKVMERGE_JSON_FAIL_CALL":"1"},
    {"TEST_FAKE_JQ_FAIL_QUERY_CONTAINS":"empty tracks array"},
    {"TEST_FAKE_JQ_FAIL_QUERY_CONTAINS":"def row($id):"},
],ids=("mkvmerge-json","jq-validation","jq-display"))
def test_mkv_utils_option7_inspection_failure_skips_remux(env,extra_env):
    source=_mkv_file(env,"remove_fail_inspect.mkv")
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\nN\n",extra_env=extra_env)
    assert result.returncode==1,result.stdout+result.stderr
    assert ("Inspection failed:" in result.stdout+result.stderr or "Injected read-only jq query failure:" in result.stderr)
    assert source.read_bytes()==b"payload" and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert not _command_argv(env,"mkvpropedit") and not _command_argv(env,"mkvextract")


@pytest.mark.parametrize("row_mode",("empty","non-numeric","duplicate","unsupported"))
def test_mkv_utils_option7_invalid_discovery_rows_skip_remux(env,row_mode):
    source=_mkv_file(env,"remove_invalid_rows.mkv");model=_integration_model()
    if row_mode=="empty":model["tracks"]=[]
    elif row_mode=="non-numeric":model["tracks"][0]["id"]="bad"
    elif row_mode=="duplicate":model["tracks"][1]["id"]=0
    else:model["tracks"][0]["type"]="buttons"
    extra=_integration_manifest(env,{source:model})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\nN\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Inspection failed:" in result.stdout+result.stderr
    assert source.read_bytes()==b"payload" and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]


def test_mkv_utils_option7_nonexistent_track_id_skips_remux(env):
    source=_mkv_file(env,"remove_missing_id.mkv")
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n44\n")
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stderr.count("Remove IDs:") == 2
    assert "Cancelled; no media changes." in result.stdout
    assert source.read_bytes()==b"payload" and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert "requested, not run" in result.stdout


def test_mkv_utils_option7_refuses_to_remove_every_track(env):
    source=_mkv_file(env,"remove_all.mkv")
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n0-3\n")
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stderr.count("Remove IDs:") == 2
    assert "Cancelled; no media changes." in result.stdout
    assert source.read_bytes()==b"payload" and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert "requested, not run" in result.stdout


def test_mkv_utils_option7_bypass_keeps_original_track_guard(env):
    first,second=_mkv_file(env,"option7_default.mkv"),_mkv_file(env,"option7_alt.mkv")
    a=_integration_model();b=_integration_model([(0,"video","V_MPEG4/ISO/AVC",True),(11,"audio","A_AAC",True),(12,"subtitles","S_TEXT/ASS",True)])
    extra=_integration_manifest(env,{first:a,second:b},stage={str(first):_integration_output(a,[1,2,3]),str(second):_integration_output(b,[11,12])})
    # Bypass permits the count difference, while original IDs/types/codecs
    # still have to match the reference tree before a source can be remuxed.
    result=_run_mkv_utils(env,"--bypass",fzf_responses=[[str(first),str(second)]],input_data="2\n1\n0\n\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    calls=[argv for argv in _command_argv(env,"mkvmerge") if "-o" in argv]
    assert len(calls)==1 and calls[0][-1]==str(first) and "--no-video" in calls[0]
    assert (calls[0][calls[0].index("--audio-tracks")+1],calls[0][calls[0].index("--subtitle-tracks")+1])==("1,2","3")
    assert not _command_argv(env,"mkvpropedit") and "Done: 1; Failed: 0" in result.stdout
    assert f"Processing: {first.name}" in result.stdout and f"Processing: {second.name}" not in result.stdout
    assert f"File: {first.name}" in result.stdout and f"File: {second.name}" not in result.stdout
    assert f"Skipped track mismatch: {second.name}" in result.stdout
    assert "Track count mismatch:" not in result.stdout
    assert "Original ID 1: missing-id" in result.stdout
    assert "Original ID 2: missing-id" in result.stdout
    assert "Original ID 3: missing-id" in result.stdout
    _assert_readable_outcomes(result.stdout, "Done: 1", "Skipped: 1")
    assert _observed_fake_identification(env,first.with_suffix(".mka"))["tracks"]==_integration_output(a,[1,2,3])["tracks"]
    assert first.with_suffix(".mka").read_bytes()==b"candidate-data\n"
    assert second.read_bytes()==b"payload" and not second.with_suffix(".mka").exists()
    for internal in ("track_rows=","row=","track_type=","track_id=","track_rows_valid=","excluded_id=","requested_ids_valid="):
        assert internal not in result.stdout+result.stderr


def test_mkv_utils_option8_reorder_tracks_replaces_original(env):
    source=_mkv_file(env,"reorder.mkv");original=_integration_model();expected=_integration_output(original,[1,0,2,3])
    extra=_integration_manifest(env,{source:original},stage={str(source):expected})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n2\n1,0\n\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=[a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert len(calls)==1 and calls[0][calls[0].index("--track-order")+1]=="0:1,0:0,0:2,0:3"
    actual=_observed_fake_identification(env,source)
    assert [t["properties"]["uid"] for t in actual["tracks"]]==[original["tracks"][i]["properties"]["uid"] for i in (1,0,2,3)]
    assert actual==expected and source.read_bytes()==b"candidate-data\n"
    assert "Mux 2: reorder" in result.stdout
    assert result.stdout.index("Mux 2: reorder") < result.stdout.index(f"Processing: {source.name}")
    assert result.stdout.count("Final report") == 1 and "Done: 1; Failed: 0" in result.stdout


def test_mkv_utils_option8_reorder_failure_cleans_temp_file(env):
    source=_mkv_file(env,"reorder_fail.mkv");original=_integration_model()
    extra=_integration_manifest(env,{source:original},stage={str(source):_integration_output(original,[1,0,2,3])},merge_code=1)
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n2\n1,0\n\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Warning: 1" in result.stdout and "Candidate:" in result.stdout
    assert source.read_bytes()==b"payload" and not (env["workdir"]/"reorder_fail_temp.mkv").exists()
    assert len(list(env["workdir"].glob(".mkvutil-*/candidate.mkv")))==1


def test_mkv_utils_option9_extract_track_extension_from_override(env):
    source=_mkv_file(env,"extract_codec.mkv");model=_integration_model([(0,"video","V_MPEG4/ISO/AVC",True),(1,"audio","A_OPUS",True),(2,"subtitles","S_TEXT/ASS",False)])
    extra=_integration_manifest(env,{source:model},extraction={str(source):{"tracks":{"outputs":{"1":{"data":"opus bytes"}}}}})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n2\n1\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    assert _command_argv(env,"mkvextract")[0][:2]==[str(source),"tracks"]
    assert (env["workdir"]/"extract_codec - Track [1].opus").read_bytes()==b"opus bytes" and source.read_bytes()==b"payload"
    final = result.stdout.split('Final report', 1)[1]
    assert '=> Attachments' not in final
    assert 'Track output ID 1: extract_codec - Track [1].opus (published)' in final


def test_mkv_utils_option9_extract_track_extension_from_python_map(env):
    source=_mkv_file(env,"extract_unknown.mkv");model=_integration_model([(0,"audio","A_TRUEHD",True)])
    extra=_integration_manifest(env,{source:model},extraction={str(source):{"tracks":{"outputs":{"0":{"data":"truehd bytes"}}}}})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n2\n0\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    assert (env["workdir"]/"extract_unknown - Track [0].thd").read_bytes()==b"truehd bytes" and source.read_bytes()==b"payload"


@pytest.mark.parametrize("workflow",("edit-flags","reorder-metadata","remove-reorder-metadata"))
def test_mkv_utils_integration_grouped_workflow_equivalents(env,workflow):
    source=_mkv_file(env,'Combined $cash "name".mkv');original=_integration_model();actual=json.loads(json.dumps(original))
    literal='@literal $cash: "quoted"'
    if workflow=="edit-flags":
        for track in actual["tracks"][1:3]:track["properties"].update(forced_track=False,default_track=True)
        original["tracks"][1]["properties"].update(forced_track=True,default_track=False)
        extra=_integration_manifest(env,{source:original},post_edit={str(source):actual})
        inputs="1\n1,2\n1,2\n\n\n\n\n"
    else:
        for track in actual["tracks"][1:3]:
            track["properties"].update(track_name=literal,language="fre",language_ietf="fr-CA")
        removed=workflow=="remove-reorder-metadata"
        if not removed:
            actual["tracks"][0]["properties"].update(track_name=literal,language="fre",language_ietf="fr-CA")
        actual=_integration_output(actual,[2,1,3] if removed else [0,2,1,3])
        extra=_integration_manifest(env,{source:original},stage={str(source):actual})
        inputs=("2\n1,2\n0\n2,1\n" if removed else "2\n2\n2,1\n")+"4,3\n"+(literal+"\n")*(2 if removed else 3)+("fr-CA\n")*(2 if removed else 3)
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data=inputs,extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    assert len(_command_argv(env,"fzf"))==1 and "Done: 1; Failed: 0" in result.stdout
    if workflow=="edit-flags":
        assert len(_command_argv(env,"mkvpropedit"))==1 and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
        output=source;assert "Processed In:" not in result.stdout
    else:
        calls=[a for a in _command_argv(env,"mkvmerge") if "-o" in a]
        assert len(calls)==1 and not _command_argv(env,"mkvpropedit")
        assert "1:"+literal in calls[0] and "1:fr-CA" in calls[0]
        assert calls[0][calls[0].index("--track-order")+1]==("0:2,0:1,0:3" if workflow=="remove-reorder-metadata" else "0:0,0:2,0:1,0:3")
        output=source.with_suffix(".mka") if workflow=="remove-reorder-metadata" else source
    assert _observed_fake_identification(env,output)==actual


@pytest.mark.parametrize("boundary",("removed-metadata","cancel","eof","fzf-injection"))
def test_mkv_utils_integration_reject_or_cancel_before_modification(env,boundary):
    source=_mkv_file(env,"Untouched.mkv")
    selected=source
    if boundary=="removed-metadata":inputs="2\n1\n0\n4\n99\n"
    elif boundary=="cancel":inputs="1\n4\n0\ne\n"
    elif boundary=="eof":inputs="1\n4\n0\n"
    else:
        selected=env["workdir"].parent/"outside scanned domain.mkv";selected.write_bytes(b"outside")
        inputs="1\n5\n"
    result=_run_mkv_utils(env,fzf_responses=[[str(selected)]],input_data=inputs)
    assert result.returncode==(0 if boundary in ("removed-metadata","cancel","eof") else 1),result.stdout+result.stderr
    assert source.read_bytes()==b"payload"
    assert not _command_argv(env,"mkvpropedit") and not _command_argv(env,"mkvextract")
    assert not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    if boundary == "removed-metadata":
        assert result.stderr.count('Track IDs:') == 2
        assert "Available: 0,1,2" in result.stderr
        assert "Cancelled; no media changes." in (result.stdout + result.stderr)
    elif boundary == "eof":
        assert "Cancelled; no media changes." in result.stdout
    elif boundary == "cancel":
        assert result.stdout.count("1) Set flag-forced for tracks") == 2
        assert "Final report" not in result.stdout


def test_mkv_utils_integration_native_child_signal_stops_menu_queue(env):
    first,second=_mkv_file(env,"Signal first.mkv"),_mkv_file(env,"Pending second.mkv")
    original=_integration_model();stage=_integration_output(original,[1,0,2,3])
    extra=_integration_manifest(env,{first:original,second:original},stage={str(first):stage,str(second):stage},merge_code=-15)
    result=_run_mkv_utils(env,fzf_responses=[[str(first),str(second)]],input_data="2\n2\n1,0\n\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Interrupted: 1" in result.stdout and "Not attempted: 1" in result.stdout
    assert first.read_bytes()==second.read_bytes()==b"payload"
    assert len([a for a in _command_argv(env,"mkvmerge") if "-o" in a])==1
    assert not _command_argv(env,"mkvpropedit") and len(_command_argv(env,"fzf"))==1


def test_mkv_utils_navigation_action_back_resets_and_reopens_picker(env):
    first, second = _mkv_file(env, "Back first.mkv"), _mkv_file(env, "Back second.mkv")
    model = _integration_model()
    expected = _integration_output(model, [1, 2, 3])
    extra = _integration_manifest(env, {first: model, second: model}, stage={str(second): expected})
    result = _run_mkv_utils(env, fzf_responses=[[str(first)], [str(second)]],
                            input_data="2\n1,2\n1\ne\n1\n0\n\n", extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_command_argv(env, "fzf")) == 2
    writers = [args for args in _command_argv(env, "mkvmerge") if "-o" in args]
    assert len(writers) == 1 and writers[0][-1] == str(second)
    assert first.read_bytes() == b"payload" and not first.with_suffix(".mka").exists()
    assert not second.exists() and _observed_fake_identification(env, second.with_suffix(".mka")) == expected
    final = result.stdout.split("Final report", 1)[1]
    assert "Selected: 1" in final and first.name not in final
    assert f"{second.name} => {second.with_suffix('.mka').name}" in final
    assert result.stdout.count("Final report") == 1


def test_mkv_utils_navigation_config_action_back_and_data_literals(env):
    source = _mkv_file(env, "literal values.mkv")
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/literal values.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_ledger_reset "$PWD" "$PWD/literal values.mkv"
mkvutil_batch_request mux 2
code=0
mkvutil_configure_category mux 2 <<< $'0,1\nE' || code=$?
eq "$code" 4 'optional metadata list Back to Mux actions'
eq "$MKVUTIL_CONFIG" '' 'no partial config'
mkvutil_discard_configuration
mkvutil_batch_request edit 4,5
mkvutil_configure_category edit 4,5 <<< $'0\n\\e\n\\e'
eq "${MKVUTIL_METADATA_SETTINGS[4:0]}" e 'literal track name e'
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" e 'literal title e'
for actions in 1 3; do
  code=0
  mkvutil_configure_category edit "$actions" <<< $'0\ne' || code=$?
  eq "$code" 4 'flag/language e returns Back'
done
code=0
mkvutil_configure_category mux 1 <<< e || code=$?
eq "$code" 4 'removal e returns to actions'
code=0
mkvutil_configure_category edit 5 < /dev/null || code=$?
eq "$code" 2 'data EOF remains bounded'
print -r -- 'navigation data contracts passed'
''', {str(source): _source_json([(0, "audio", "A_AAC", True),
                                  (1, "audio", "A_OPUS", False)])})
    assert result.stdout.rstrip().endswith("navigation data contracts passed")


@pytest.mark.parametrize("category_key,outcome,exit_code", [("1", "success", "0"), ("2", "skipped", "1"), ("3", "partial", "1")])
def test_mkv_utils_navigation_processing_is_final(env, category_key, outcome, exit_code):
    result = _run_planning_contract(env, r'''
scan_count=0; picker_count=0; inspect_count=0; modifier_count=0
mkvutil_scan_files() { (( ++scan_count )); MKVUTIL_SCAN_FILES=("$PWD/fresh-${scan_count}.mka"); }
mkvutil_select_files() { (( ++picker_count )); MKVUTIL_SELECTED_FILES=("${MKVUTIL_SCAN_FILES[@]}"); }
mkvutil_inspect_sources() {
  (( ++inspect_count ))
  MKVUTIL_SOURCES=("$(jq -cn --arg source "${MKVUTIL_SELECTED_FILES[1]}" '{source:$source}')")
}
mkvutil_configure_category() { MKVUTIL_CONFIG="$(jq -cn --arg category "$1" --arg actions "$2" '{category:$category,operations:($actions|split(",")),metadata:"",settings:{}}')"; }
mkvutil_plan_queue() { MKVUTIL_JOBS=('{}'); }
mkvutil_execute_queue() {
  (( ++modifier_count ))
  MKVUTIL_HAS_RUN=1
  local receipt=""
  if [[ "$TEST_OUTCOME" == skipped ]]; then
    receipt="$(jq -cn --arg source "${MKVUTIL_SELECTED_FILES[1]}" '{kind:"removal-mismatch",source:$source,reference:$source,reasons:[{original_id:"0",reason:"codec-mismatch",expected:{type:"audio",codec_id:"A_AAC"},actual:{type:"audio",codec_id:"A_OPUS"}}]}')"
    mkvutil_ledger_skip "$receipt"
    MKVUTIL_REMOVAL_SKIPS=("$receipt")
  else
    receipt="$(jq -cn --arg source "${MKVUTIL_SELECTED_FILES[1]}" --arg outcome "$TEST_OUTCOME" '{source:$source,status:$outcome,reason:"fixture result",phase:"complete",actual_state:"observed"}')"
    mkvutil_ledger_result "$receipt"
  fi
  MKVUTIL_JOBS=()
  return "$TEST_EXIT_CODE"
}
code=0
mkvutil_main "$PWD" || code=$?
eq "$code" "$TEST_EXIT_CODE" 'actual outcome preserved'
eq "$scan_count" 1 'processing never reopens main'
eq "$picker_count" 1 'processing never reopens picker'
eq "$inspect_count" 1 'no second selection scope'
eq "$modifier_count" 1 'no queue replay'
eq "${MKVUTIL_SCOPE_KEYS[1]}" "$PWD/fresh-1.mka" 'completed scope remains final'
remaining=""
IFS= read -r remaining
eq "$remaining" e 'post-run typeahead is not consumed'
''', {}, input_data=f"{category_key}\n1\ne\n",
        extra_env={"TEST_OUTCOME": outcome, "TEST_EXIT_CODE": exit_code})
    assert result.stdout.count("Final report") == 1
    assert result.stdout.count("1) Matroska Edit") == 1
    final = result.stdout.split("Final report", 1)[1]
    if outcome == "success":
        assert "fresh-1.mka" not in final
    else:
        assert "fresh-1.mka" in final
    assert "fresh-2.mka" not in result.stdout
    assert "Skipped-subset choice:" not in result.stderr and "Press Enter to continue:" not in result.stderr
    assert "0) Exit" not in result.stdout and "0) Finish" not in result.stdout


def test_mkv_utils_navigation_pre_run_skips_back_sticky_and_eof(env):
    result = _run_planning_contract(env, r'''
mkvutil_scan_files() { MKVUTIL_SCAN_FILES=("$PWD/skipped.mkv"); }
mkvutil_select_files() { MKVUTIL_SELECTED_FILES=("${MKVUTIL_SCAN_FILES[@]}"); }
mkvutil_inspect_sources() { MKVUTIL_SOURCES=("$(jq -cn --arg source "$PWD/skipped.mkv" '{source:$source}')"); }
mkvutil_configure_category() { MKVUTIL_CONFIG='{"category":"mux","operations":["1"],"metadata":"","settings":{}}'; }
mkvutil_plan_queue() {
  local receipt="$(jq -cn --arg source "$PWD/skipped.mkv" '{kind:"removal-mismatch",source:$source,reference:$source,reasons:[{original_id:"1",reason:"missing-id",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:null}]}')"
  mkvutil_ledger_skip "$receipt"
  MKVUTIL_REMOVAL_SKIPS=("$receipt")
  MKVUTIL_JOBS=()
  return 3
}
code=0
mkvutil_main "$PWD" || code=$?
eq "$code" 1 'pre-Run unresolved skip sticky after main EOF'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 1 'skip receipt preserved'
eq "$MKVUTIL_HAS_RUN" 0 'no execution'
''', {}, input_data="2\n1\ne\ne\n")
    assert result.stdout.count("Final report") == 1 and "Skipped: 1" in result.stdout
    assert "No media changes" not in result.stdout


def test_mkv_utils_navigation_back_and_literal_e_entrypoint(env):
    source = _mkv_file(env, "Back literal.mkv")
    original = _integration_model()
    actual = json.loads(json.dumps(original))
    actual["tracks"][0]["properties"]["track_name"] = "e"
    actual["container"]["properties"]["title"] = "e"
    extra = _integration_manifest(env, {source: original}, post_edit={str(source): actual})
    result = _run_mkv_utils(env, fzf_responses=[[str(source)]],
                            input_data="1\n4,5\n0\n\\e\n\\e\ne\n", extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Category: edit; Actions: 4,5" in result.stdout
    assert "Review/change" not in result.stdout + result.stderr and "Preview resulting" not in result.stdout + result.stderr
    assert len(_command_argv(env, "fzf")) == 1
    # Identification, before-edit validation and after-edit observation are reads.
    queries = _command_argv(env, "mkvmerge")
    assert len(queries) == 3 and all(call[:1] == ["-J"] for call in queries)
    edits = _command_argv(env, "mkvpropedit")
    assert len(edits) == 1 and "--set" in edits[0]
    assert "name=e" in edits[0] and "title=e" in edits[0]
    assert _observed_fake_identification(env, source) == actual
    assert all(call[0] == str(source) and call[1] in ("chapters", "tags")
               for call in _command_argv(env, "mkvextract"))
    assert source.read_bytes() == b"edited-data\n"


def test_mkv_utils_navigation_hidden_exit_before_selection_entrypoint(env):
    _mkv_file(env, "untouched.mkv")
    result = _run_mkv_utils(env, input_data="2\nE\ne\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("1) Matroska Edit") == 2
    assert "e) Back" in result.stdout and "Exit" not in result.stdout and "Cancel" not in result.stdout
    assert not _command_argv(env, "fzf") and not _command_argv(env, "mkvmerge")
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")


def test_mkv_utils_navigation_interrupt_preserves_ledger_and_ends(env):
    result = _run_planning_contract(env, r'''
read_count=0; scan_count=0
_mkvutil_read() {
  (( ++read_count ))
  case "$read_count" in
    1) REPLY=1 ;;
    2) REPLY=5 ;;
    *) kill -s INT $$; return 2 ;;
  esac
}
mkvutil_scan_files() { (( ++scan_count )); MKVUTIL_SCAN_FILES=("$PWD/pending.mkv"); }
mkvutil_select_files() { MKVUTIL_SELECTED_FILES=("${MKVUTIL_SCAN_FILES[@]}"); }
mkvutil_inspect_sources() { MKVUTIL_SOURCES=("$(jq -cn --arg source "$PWD/pending.mkv" '{source:$source}')"); }
mkvutil_configure_category() {
  MKVUTIL_CONFIG='{"category":"edit","operations":["5"],"metadata":"","settings":{}}'
}
# Interrupt after final configuration but before admission to the writer.
mkvutil_plan_queue() { MKVUTIL_JOBS=('{}'); kill -s INT $$; return 0; }
mkvutil_execute_queue() { fail 'interrupted preflight must not execute'; }
code=0
mkvutil_main "$PWD" || code=$?
eq "$code" 1 'interruption nonzero'
eq "$MKVUTIL_INTERRUPTED" 1 'interruption never reset'
eq "$scan_count" 1 'no outer restart'
eq "$(jq -r '.status' <<< "${MKVUTIL_LEDGER[$PWD/pending.mkv]}")" not_attempted 'pending finalized'
''', {})
    assert result.stdout.count("Final report") == 1 and "Not attempted: 1" in result.stdout
    assert "Cancelled; no media changes." not in result.stdout


def test_mkv_utils_navigation_ctrl_c_blocked_input_entrypoint(env):
    import select
    import signal
    import time

    source = _mkv_file(env, "interrupt title.mkv")
    _set_fake_fzf_responses(env, [[str(source)]])
    run_env = os.environ.copy()
    run_env.update({
        "HOME": str(env["workdir"]),
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq",
        "TEST_REAL_PYTHON": sys.executable,
        "TEST_USE_REAL_JSON": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]),
        "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]),
        "TEST_FAKE_FZF_SELECTIONS": str(env["fake_fzf_selections"]),
    })
    for tool in ("mkvmerge", "mkvpropedit", "mkvextract", "fzf"):
        assert Path(shutil.which(tool, path=run_env["PATH"])).resolve() == (env["fake_bin"] / tool).resolve()
    process = subprocess.Popen(["/usr/local/bin/zsh", "-f", str(env["mkv_utils_script"])],
                               cwd=env["workdir"], env=run_env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    assert process.stdin and process.stderr
    seen = b""
    try:
        process.stdin.write(b"1\n5\n"); process.stdin.flush()
        deadline = time.monotonic() + 10
        while b"Title [clear]: " not in seen and time.monotonic() < deadline:
            if select.select([process.stderr], [], [], 0.1)[0]:
                data = os.read(process.stderr.fileno(), 8192)
                assert data, seen.decode(errors="replace")
                seen += data
        assert b"Title [clear]: " in seen, seen.decode(errors="replace")
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL); process.communicate()
    output = stdout.decode()
    assert process.returncode == 1, output + (seen + stderr).decode(errors="replace")
    assert output.count("1) Matroska Edit") == 1 and output.count("Final report") == 1
    assert "Not attempted: 1" in output and "Cancelled; no media changes." not in output
    assert len(_command_argv(env, "fzf")) == 1 and len(_command_argv(env, "mkvmerge")) == 1
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
    assert source.read_text() == "payload"


def test_mkv_utils_controller_commits_after_full_preflight_and_reports_all_skipped(env):
    skipped = _mkv_file(env, "all-skipped.mkv")
    result = _run_planning_contract(env, r'''
calls=()
mkvutil_configure_category() { IFS= read -r value; eq "$value" complete 'last required input'; calls+=(configure); MKVUTIL_CONFIG='{}'; }
mkvutil_batch_configured() { calls+=(batch_configured); }
mkvutil_plan_queue() { calls+=(plan_queue); MKVUTIL_JOBS=('{}' '{}'); return 0; }
mkvutil_execute_queue() { calls+=(execute_queue); eq "${#@}" 2 'entire queue passed together'; MKVUTIL_HAS_RUN=1; }
mkvutil_ledger_status() { calls+=(ledger_status); return 0; }
_mkvutil_ui_acknowledge() { fail 'no post-plan acknowledgement'; }
functions[original_menu_read]="${functions[_mkvutil_menu_read]}"
_mkvutil_menu_read() { fail 'no review menu'; }
code=0
{
  mkvutil_controller mux 2 || code=$?
  IFS= read -r remaining
} <<< $'complete\ne'
eq "$code" 0 'eligible queue completes'
eq "${(j:,:)calls}" 'configure,batch_configured,plan_queue,execute_queue,ledger_status' 'direct commit sequence'
eq "$remaining" e 'input after final value remains unread'

# A wholly skipped plan reports and returns without reaching a writer.
calls=()
mkvutil_plan_queue() { calls+=(plan_queue); MKVUTIL_JOBS=(); MKVUTIL_REMOVAL_SKIPS=('{}'); return 3; }
mkvutil_execute_queue() { fail 'all-skipped plan executed'; }
code=0
mkvutil_controller mux 2 <<< complete || code=$?
eq "$code" 1 'all-skipped plan is nonzero'
eq "${(j:,:)calls}" 'configure,batch_configured,plan_queue' 'all-skipped returns before execute'
# Exercise the public caller too: it renders one final report with the exact
# skipped identity/reason and exits without invoking a modifying command.
functions[_mkvutil_menu_read]="${functions[original_menu_read]}"
mkvutil_scan_files() { MKVUTIL_SCAN_FILES=("$PWD/all-skipped.mkv"); }
mkvutil_select_files() { MKVUTIL_SELECTED_FILES=("$PWD/all-skipped.mkv"); }
mkvutil_inspect_sources() { MKVUTIL_SOURCES=("$(jq -cn --arg source "$PWD/all-skipped.mkv" '{source:$source}')"); }
mkvutil_configure_category() { IFS= read -r value; eq "$value" complete 'entrypoint final input'; MKVUTIL_CONFIG='{}'; }
mkvutil_plan_queue() {
  local receipt="$(jq -cn --arg source "$PWD/all-skipped.mkv" --arg reference "$PWD/reference.mkv" '{kind:"removal-mismatch",source:$source,reference:$reference,reasons:[{original_id:"1",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}')"
  mkvutil_ledger_skip "$receipt"
  MKVUTIL_REMOVAL_SKIPS=("$receipt"); MKVUTIL_JOBS=()
  return 3
}
code=0
mkvutil_main "$PWD" <<< $'2\n1\ncomplete' || code=$?
eq "$code" 1 'all-skipped entrypoint is nonzero'
print -r -- 'automatic controller contracts passed'
''', {})
    assert result.stdout.rstrip().endswith("automatic controller contracts passed")
    report = result.stdout[result.stdout.index("Final report"):]
    assert report.count("Final report") == 1
    assert f"| {skipped.name}" in report and "Original ID 1: codec-mismatch" in report
    assert 'expected={"type":"subtitles","codec_id":"S_TEXT/ASS"}' in report
    assert 'actual={"type":"subtitles","codec_id":"S_TEXT/UTF8"}' in report
    assert not [args for args in _command_argv(env, "mkvmerge") if "-o" in args]
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")


class _OwnedMenuScreen:
    """ANSI cursor/cell model for navigation's home and line/tail erases."""

    def __init__(self):
        import codecs
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.pending = ""
        self.active = False
        self.cursor_visible = True
        self.normal = ""
        self.normal_row = ""
        self.cells = [[]]
        self.row = self.col = 0
        self.enters = self.leaves = 0
        self.homes = self.line_erases = self.tail_erases = 0

    @property
    def text(self):
        return "\n".join("".join(row) for row in self.cells) if self.active else self.normal

    def _row(self):
        while len(self.cells) <= self.row:
            self.cells.append([])
        return self.cells[self.row]

    def feed(self, data):
        import re
        self.pending += self.decoder.decode(data)
        while self.pending:
            if self.pending.startswith("\x1b"):
                match = re.match(r"\x1b\[([0-?]*)([ -/]*)([@-~])", self.pending)
                if not match:
                    break
                parameters, _, command = match.groups()
                self.pending = self.pending[match.end():]
                if parameters == "?1049" and command == "h":
                    assert not self.active, "nested alternate buffer"
                    self.active = True; self.cells = [[]]; self.row = self.col = 0; self.enters += 1
                elif parameters == "?1049" and command == "l":
                    assert self.active, "unowned alternate-buffer leave"
                    self.active = False; self.leaves += 1
                elif parameters == "?25" and command in ("h", "l"):
                    self.cursor_visible = command == "h"
                elif command in ("J", "K"):
                    if not self.active and command == "K" and parameters == "2":
                        assert re.search(r"  [⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] Working", self.normal_row), "erase outside owned Working row"
                        self.normal_row = ""
                        continue
                    assert self.active and parameters in ("", "0"), "normal/prepaint screen erase"
                    del self._row()[self.col:]
                    if command == "J":
                        del self.cells[self.row + 1:]; self.tail_erases += 1
                    else:
                        self.line_erases += 1
                elif command == "H":
                    assert self.active, "normal screen cursor moved"
                    position = (parameters or "1;1").split(";")
                    self.row = int(position[0] or "1") - 1
                    self.col = int(position[1] or "1") - 1 if len(position) > 1 else 0
                    self.homes += 1
                elif command == "m":
                    pass  # Row styling changes colour, never cell/cursor position.
                else:
                    raise AssertionError(f"unexpected UI escape {parameters}{command}")
            else:
                character, self.pending = self.pending[0], self.pending[1:]
                if not self.active:
                    self.normal += character
                    if character == "\n":
                        self.normal_row = ""
                    elif character != "\r":
                        self.normal_row += character
                elif character == "\r":
                    self.col = 0
                elif character == "\n":
                    self.row += 1
                elif character == "\b":
                    self.col = max(0, self.col - 1)
                else:
                    row = self._row()
                    while len(row) <= self.col:
                        row.append(" ")
                    row[self.col] = character
                    self.col += 1


@pytest.mark.parametrize("exit_key", [b"e", b"\x03", b"line-ctrl-c", b"z", b"0", b"title-ctrl-c", b"track-id-ctrl-c", b"back-retry-remux"],
                         ids=["owned-views-history", "main-ctrl-c", "line-ctrl-c", "invalid-main-reprompt", "zero-is-not-back", "title-ctrl-c", "track-id-ctrl-c", "back-action-retry-remux"])
def test_mkv_utils_main_menu_line_input_terminal(env, exit_key):
    import fcntl
    import pty
    import re
    import select
    import struct
    import termios
    import time

    source, second = _mkv_file(env, "untouched.mkv"), _mkv_file(env, "mismatch.mkv")
    models = _removal_models()
    if exit_key == b"back-retry-remux":
        _set_fake_fzf_responses(env, [[str(source)], [str(source)]])
        integration = _integration_manifest(
            env, {source: models["reference"]},
            stage={str(source): _integration_output(models["reference"], [1, 0, 2])},
        )
    else:
        _set_fake_fzf_responses(env, [[str(source), str(second)], [str(source), str(second)]])
        integration = _integration_manifest(env, {source: models["reference"], second: models["codec"]})
    selector = env["fake_bin"] / "fzf"
    selector.write_text(selector.read_text().replace(
        "set -e\n", "set -e\nprintf '\\nPICKER-OPEN\\n' >&2\n", 1,
    ))
    run_env = os.environ.copy()
    run_env.update({
        "HOME": str(env["workdir"]), "TERM": "xterm-256color",
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq",
        "TEST_REAL_PYTHON": sys.executable,
        "TEST_USE_REAL_JSON": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]),
        "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]),
        "TEST_FAKE_FZF_SELECTIONS": str(env["fake_fzf_selections"]),
    })
    run_env.update(integration)
    for tool in ("mkvmerge", "mkvpropedit", "mkvextract", "fzf"):
        assert Path(shutil.which(tool, path=run_env["PATH"])).resolve() == (env["fake_bin"] / tool).resolve()
    master, terminal = pty.openpty()
    fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 240, 0, 0))
    before = termios.tcgetattr(terminal)

    def own_terminal():
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.tcsetpgrp(0, os.getpgrp())
        assert os.tcgetpgrp(0) == os.getpgrp()

    process = subprocess.Popen(
        ["/usr/local/bin/zsh", "-f", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, stdin=terminal, stdout=terminal, stderr=terminal,
        start_new_session=True, preexec_fn=own_terminal,
    )
    output = bytearray(); screen = _OwnedMenuScreen(); deadline = time.monotonic() + 10

    def receive():
        if select.select([master], [], [], 0.1)[0]:
            data = os.read(master, 8192)
            if not data: return False
            output.extend(data); screen.feed(data)
        return True

    def wait_for(prompt):
        start = len(output)
        while prompt not in output[start:] and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert prompt in output[start:], output.decode(errors="replace")

    def shortcuts():
        wait_for(b"Category: ")
        assert screen.active and screen.cursor_visible and "Category: " in screen.text
        assert "1) Matroska Edit" in screen.text and "e) Back" not in screen.text
        mask = termios.ICANON | termios.ECHO
        assert before[3] & mask == termios.tcgetattr(terminal)[3] & mask

    def line_menu(prompt, view, category):
        wait_for(prompt)
        while not (screen.active and screen.cursor_visible and f"{category} — {view}" in screen.text and prompt.decode() in screen.text):
            assert time.monotonic() < deadline, output.decode(errors="replace")
            receive()
        assert f"{category} — {view}" in screen.text and "Directory: " in screen.text
        assert "1) Matroska Edit" not in screen.text and "2) Matroska Mux" not in screen.text
        assert "e) Back" in screen.text
        mask = termios.ICANON | termios.ECHO
        assert before[3] & mask == termios.tcgetattr(terminal)[3] & mask

    def normal_input(prompt):
        wait_for(prompt)
        assert not screen.active and screen.cursor_visible

    try:
        shortcuts()
        if exit_key == b"e":
            for key, category in ((b"1", "Matroska Edit"), (b"2\n", "Matroska Mux"), (b"3\n", "Matroska Extract"), (b"1\n", "Matroska Edit")):
                switches = (screen.enters, screen.leaves)
                os.write(master, key)
                if key == b"1":
                    # A category number is not accepted until its line ends.
                    receive()
                    assert process.poll() is None and b"Actions: " not in output
                    assert "Category: " in screen.text
                    os.write(master, b"\n")
                line_menu(b"Actions: ", "actions", category)
                assert (screen.enters, screen.leaves) == switches
                os.write(master, b"e\n"); shortcuts()
                assert (screen.enters, screen.leaves) == switches
            # Keep both optional-metadata Back paths on the owned screen. The
            # first backs directly from the choices; the second backs from a
            # title value, then from choices, before any final value commits.
            os.write(master, b"2\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"2\n")
            normal_input(b"Track order:")
            os.write(master, b"0,1\n")
            line_menu(b"Metadata [none]: ", "metadata", "Matroska Mux")
            assert "Output IDs for each track edit: 0,1" in screen.text
            os.write(master, b"E\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"e\n"); shortcuts()

            os.write(master, b"2\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"2\n")
            normal_input(b"Track order:")
            os.write(master, b"0,1\n")
            line_menu(b"Metadata [none]: ", "metadata", "Matroska Mux")
            os.write(master, b"5\n")
            normal_input(b"Title [clear]: ")
            os.write(master, b"e\n")
            line_menu(b"Metadata [none]: ", "metadata", "Matroska Mux")
            os.write(master, b"E\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"e\n"); shortcuts()
            os.write(master, b"e\n")
        elif exit_key == b"track-id-ctrl-c":
            os.write(master, b"2\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"1\n")
            normal_input(b"Remove IDs: ")
            os.write(master, b"\x03")
        elif exit_key == b"title-ctrl-c":
            os.write(master, b"1\n")
            line_menu(b"Actions: ", "actions", "Matroska Edit")
            os.write(master, b"5\n")
            normal_input(b"Title [clear]: ")
            os.write(master, b"\x03")
        elif exit_key == b"line-ctrl-c":
            os.write(master, b"2\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"\x03")
        elif exit_key == b"z":
            for invalid in (b"z\n", b"1,2\n", b"1-2\n", b"\n"):
                os.write(master, invalid)
                wait_for(b"Category: ")
                assert "Invalid category. Use 1, 2, 3 or 4." in screen.text
            os.write(master, b"e\n")
        elif exit_key == b"0":
            os.write(master, b"0\n")
            wait_for(b"Category: ")
            assert "Invalid category. Use 1, 2, 3 or 4." in screen.text
            os.write(master, b"e\n")
        elif exit_key == b"back-retry-remux":
            os.write(master, b"2\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            os.write(master, b"1,2\n")
            normal_input(b"Remove IDs: ")
            os.write(master, b"1\n")
            normal_input(b"Track order:")
            os.write(master, b"e\n")
            line_menu(b"Actions: ", "actions", "Matroska Mux")
            for invalid in (b"0\n", b"w\n", b"\n"):
                os.write(master, invalid)
                line_menu(b"Actions: ", "actions", "Matroska Mux")
                assert "Invalid operations." in screen.text
            os.write(master, b"2\n")
            wait_for(b"PICKER-OPEN")
            normal_input(b"Track order:")
            os.write(master, b"1,0\n")
            line_menu(b"Metadata [none]: ", "metadata", "Matroska Mux")
            os.write(master, b"\n")
        else:
            os.write(master, exit_key)
        while process.poll() is None and time.monotonic() < deadline:
            receive()
        expected_status = 0 if exit_key in (b"e", b"z", b"0", b"back-retry-remux") else 1
        assert process.poll() == expected_status, output.decode(errors="replace")
        while time.monotonic() < deadline and select.select([master], [], [], 0)[0]:
            try:
                if not receive(): break
            except OSError: break
        assert not screen.active and screen.cursor_visible and screen.enters == screen.leaves
        # The picker must inherit the menu's screen without exposing normal
        # history between the two views. Check the actual entrypoint handoff.
        for marker in re.finditer(b"PICKER-OPEN", output):
            prefix = output[:marker.start()]
            assert prefix.count(b"\x1b[?1049h") == prefix.count(b"\x1b[?1049l") + 1
            assert re.findall(rb"\x1b\[\?25([lh])", prefix)[-1] == b"l"
        assert bytes(output).count(b"PICKER-OPEN") == len(_command_argv(env, "fzf"))
        assert screen.homes == screen.tail_erases + len(_command_argv(env, "fzf"))
        assert screen.line_erases >= screen.tail_erases
        assert b"\x1b[2J" not in output
        assert "1) Matroska Edit" not in screen.normal and "2) Matroska Mux" not in screen.normal
        if exit_key in (b"z", b"0"):
            assert output.count(b"Category: ") >= 2
        if exit_key in (b"title-ctrl-c", b"track-id-ctrl-c"):
            scopes = 1
            assert len(_command_argv(env, "fzf")) == scopes
            assert len(_command_argv(env, "mkvmerge")) == 2 * scopes
            assert all(call[0] == "-J" for call in _command_argv(env, "mkvmerge"))
        elif exit_key == b"e":
            assert len(_command_argv(env, "fzf")) == 2
            assert len(_command_argv(env, "mkvmerge")) == 4
            assert all(call[0] == "-J" for call in _command_argv(env, "mkvmerge"))
        elif exit_key == b"back-retry-remux":
            calls = _command_argv(env, "mkvmerge")
            assert len(_command_argv(env, "fzf")) == 2
            assert len([call for call in calls if "-o" in call]) == 1
            assert all(call[:1] == ["-J"] for call in calls if "-o" not in call)
            assert "Invalid" in output.decode(errors="replace")
        else:
            assert not any(_command_argv(env, tool) for tool in ("fzf", "mkvmerge"))
    finally:
        (env["workdir"].parent / "owned-menu-transcript.bin").write_bytes(output)
        os.close(master); os.close(terminal)
        if process.poll() is None:
            process.kill(); process.wait(timeout=10)
    if exit_key == b"back-retry-remux":
        assert source.read_bytes() == b"candidate-data\n" and second.read_bytes() == b"payload"
    else:
        assert source.read_text() == second.read_text() == "payload"
    assert not _command_argv(env, "mkvpropedit")
    assert all(call[1] == "tags" for call in _command_argv(env, "mkvextract"))


def test_mkv_utils_owned_menu_pipe_gating_and_report_failure_visibility(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
TERM=xterm-256color
_mkvutil_ui_enter
_mkvutil_ui_enter
_mkvutil_ui_redraw
_mkvutil_ui_leave
_mkvutil_ui_leave
_mkvutil_ui_acknowledge < /dev/null
eq "$MKVUTIL_UI_ACTIVE" 0 'pipes never enter owned mode'
# A report error must stop before reopening a main view over the diagnostic.
mkvutil_ledger_finalize() { return 0; }
mkvutil_ledger_status() { return 0; }
mkvutil_final_report() { print -u2 -r -- 'Report unavailable'; return 1; }
MKVUTIL_HAS_RUN=1
code=0
mkvutil_finish 0 || code=$?
eq "$code" 1 'report failure nonzero'
eq "$MKVUTIL_UI_REPORT_SHOWN" -1 'failed report not claimed displayed'
mkvutil_configure_category() { MKVUTIL_CONFIG='{}'; }
mkvutil_batch_configured() { return 0; }
mkvutil_plan_queue() { MKVUTIL_JOBS=(); MKVUTIL_REMOVAL_SKIPS=('{}'); return 3; }
mkvutil_execute_queue() { fail 'all-skipped controller executed'; }
code=0
mkvutil_controller mux 1 <<< 'complete' || code=$?
eq "$code" 1 'all-skipped controller exits nonzero'
mkvutil_scan_files() { return 0; }
mkvutil_close_scope() { mkvutil_finish 0; }
code=0
mkvutil_main "$PWD" <<< $'2\ne' || code=$?
eq "$code" 1 'failed report stops before main reopens'
print -r -- 'pipe presentation contracts passed'
''')
    assert result.stdout.rstrip().endswith("pipe presentation contracts passed")
    assert result.stdout.count("1) Matroska Edit") == 1
    assert "No eligible jobs; change settings" not in result.stderr
    assert "Report unavailable" in result.stderr and "Press Enter" not in result.stderr
    assert "\x1b" not in result.stdout + result.stderr


def test_mkv_utils_redraw_single_literal_body_and_shorter_screen(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
MKVUTIL_UI_ACTIVE=1
calls=0
printf() {
  (( ++calls ))
  eq "$#" 2 'one literal body argument'
  eq "$1" '%s' 'literal format'
  builtin printf '%s' "$2"
}
_mkvutil_ui_redraw $'Long heading with an old suffix KEEP THIS STALE SUFFIX\n1) Old choice\n2) Older extra choice'
eq "$calls" 1 'one printf for first body'
_mkvutil_ui_redraw $'Short $cash 100% @literal "quote"\ne) Back'
eq "$calls" 2 'one printf for second body'
''', binary_output=True)
    screen = _OwnedMenuScreen()
    screen.feed(b"durable history\r\n\x1b[?1049h")
    screen.feed(result.stderr)
    assert screen.text == 'Short $cash 100% @literal "quote"\ne) Back\n'
    assert "old suffix" not in screen.text and "Older extra choice" not in screen.text
    assert screen.homes == screen.tail_erases == 2 and screen.line_erases == 5
    assert not screen.cursor_visible
    assert result.stderr.count(b"\x1b[?25l\x1b[H") == 2
    assert b"\x1b[2J" not in result.stderr
    screen.feed(b"\x1b[?1049l")
    assert screen.normal == "durable history\r\n"


def test_mkv_utils_redraw_parent_replays_navigation_failures(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
# Simulate an already owned navigation screen; rendering occurs in a child,
# but every failure must close ACTIVE in the parent before replaying messages.
MKVUTIL_UI_ACTIVE=1
mkvutil_metadata_validate_registry() { print -u2 -r -- 'registry diagnostic'; return 1; }
code=0
_mkvutil_menu_read actions edit 'Actions: ' < /dev/null || code=$?
eq "$code" 1 'registry failure status'
eq "$MKVUTIL_UI_ACTIVE" 0 'registry parent left'
MKVUTIL_UI_ACTIVE=1
mkvutil_category_choices() { print -r -- 'choice partial output'; print -u2 -r -- 'choice diagnostic'; return 1; }
code=0
_mkvutil_menu_choices mux invalid || code=$?
eq "$code" 1 'choice failure status'
eq "$MKVUTIL_UI_ACTIVE" 0 'choice parent left'
MKVUTIL_UI_ACTIVE=1
_mkvutil_menu_body() { print -r -- 'renderer partial output'; print -u2 -r -- 'renderer diagnostic'; return 1; }
code=0
_mkvutil_menu_read main < /dev/null || code=$?
eq "$code" 1 'renderer failure status'
eq "$MKVUTIL_UI_ACTIVE" 0 'renderer parent left'
print -r -- 'diagnostic boundaries passed'
''')
    assert result.stdout.strip() == "diagnostic boundaries passed"
    chunks = result.stderr.split("\x1b[?1049l")
    assert len(chunks) == 4
    assert "registry diagnostic" in chunks[1]
    assert "choice partial output\nchoice diagnostic" in chunks[2]
    assert "renderer partial output\nrenderer diagnostic" in chunks[3]


def test_mkv_utils_redraw_retains_navigation_and_leaves_on_eof(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
# Parent-owned state persists on a valid adjacent navigation choice; EOF
# exits it. No main-reader/line-reader signal handling is replaced here.
MKVUTIL_UI_ACTIVE=1
_mkvutil_menu_read actions mux 'Actions: ' <<< e
eq "$MKVUTIL_UI_ACTIVE" 1 'valid read retained buffer'
eq "$REPLY" e 'choice literal'
code=0
_mkvutil_menu_read actions mux 'Actions: ' < /dev/null || code=$?
eq "$code" 2 'EOF status'
eq "$MKVUTIL_UI_ACTIVE" 0 'EOF parent left'
''')
    assert result.stderr.count("\x1b[?1049l") == 1
    assert "\x1b[?1049h" not in result.stderr and "\x1b[2J" not in result.stderr


def test_mkv_utils_metadata_shared_targets_title_positions_and_literal_escapes(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
mkvutil_plan_layout $'audio\t11\nsubtitles\t12' '' '' mka
for choices in '5,3,4' '3,5,4'; do
  if [[ "$choices" == 5,* ]]; then data=$'\\e\n12,11\nfr-CA\nde\n\\E\n  e  '
  else data=$'12,11\nfr-CA\nde\n\\e\n\\E\n  e  '; fi
  mkvutil_metadata_configure "$choices" shared <<< "$data"
  eq "${MKVUTIL_METADATA_SETTINGS[3:12]}" fr-CA 'first requested ID language'
  eq "${MKVUTIL_METADATA_SETTINGS[3:11]}" de 'second requested ID language'
  eq "${MKVUTIL_METADATA_SETTINGS[4:12]}" E 'exact name text escape'
  eq "${MKVUTIL_METADATA_SETTINGS[4:11]}" '  e  ' 'whitespace text preserved'
  eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" e 'exact title text escape'
done
mkvutil_metadata_configure 5 shared <<< cancel
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" cancel 'title-only literal without IDs'
mkvutil_metadata_configure 4 shared <<< $'11\ncancel'
eq "${MKVUTIL_METADATA_SETTINGS[4:11]}" cancel 'cancel is literal track-name text'
mkvutil_metadata_configure 4 shared <<< $'11,12\n\\e suffix\n\\\\E'
eq "${MKVUTIL_METADATA_SETTINGS[4:11]}" '\e suffix' 'nonexact escape preserved'
eq "${MKVUTIL_METADATA_SETTINGS[4:12]}" '\\E' 'double backslash preserved'
print -r -- 'shared target contracts passed'
''')
    assert result.stdout.strip() == 'shared target contracts passed'
    # Two multi-action collections and one name collection; title-only asks none.
    assert result.stderr.count('Track IDs:') == 4
    assert result.stderr.count('Original track ID 12 — Language:') == 2
    assert result.stderr.count('Original track ID 11 — Language:') == 2
    assert 'Track name:' in result.stderr and 'e) Back' in result.stderr
    assert 'use \\e/\\E' not in result.stderr


def test_mkv_utils_metadata_field_back_resets_partial_collection(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
mkvutil_plan_layout $'audio\t11\nsubtitles\t12' '' '' mka
for scenario in id forced default language name title; do
  case "$scenario" in
    id) choices=5,4; data=$'partial title\ne' ;;
    forced) choices=4,1; data=$'11\npartial name\nE' ;;
    default) choices=1,2; data=$'11\n0\ne' ;;
    language) choices=4,3; data=$'11\npartial name\nE' ;;
    name) choices=1,4; data=$'11\n0\ne' ;;
    title) choices=4,5; data=$'11\npartial name\nE' ;;
  esac
  code=0
  mkvutil_metadata_configure "$choices" shared <<< "$data" || code=$?
  eq "$code" 4 "field Back: $scenario"
  (( ${#MKVUTIL_METADATA_SETTINGS}==0 && ${#MKVUTIL_PROPEDIT_ARGS}==0 && ${#MKVUTIL_MERGE_METADATA_ARGS}==0 && ${#MKVUTIL_SOURCE_FLAGS}==0 )) || fail "partial metadata remained: $scenario"
done
print -r -- 'field Back contracts passed'
''')
    assert result.stdout.strip() == 'field Back contracts passed'


def test_mkv_utils_metadata_preset_explicit_sequence_and_domain(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
mkvutil_plan_layout $'video\t0\nsubtitles\t3\naudio\t4\naudio\t11\naudio\t12' '12' '0:0,0:4,0:3' mkv
mkvutil_metadata_configure '1-5' preset '0,4,3' <<< $'0\n1\n0\n1\n0\n1\nen\nfr-CA\nde\nzero\nfour\nthree\nTitle'
for choice in 1 2 3 4; do
  (( ! ${+MKVUTIL_METADATA_SETTINGS[${choice}:11]} && ! ${+MKVUTIL_METADATA_SETTINGS[${choice}:12]} )) || fail 'appended/removed target received settings'
done
eq "${MKVUTIL_METADATA_SETTINGS[1:4]}" 1 'middle ID flag'
eq "${MKVUTIL_METADATA_SETTINGS[3:0]}" en 'first ID language'
eq "${MKVUTIL_METADATA_SETTINGS[3:4]}" fr-CA 'middle ID language'
eq "${MKVUTIL_METADATA_SETTINGS[3:3]}" de 'last ID language'
eq "${MKVUTIL_METADATA_SETTINGS[4:4]}" four 'middle ID name'
eq "${MKVUTIL_METADATA_SETTINGS[5:info]}" Title 'container unaffected by preset'
for preset in '12' '99' '0,0' '0,,4' '0:0' '04' ''; do
  reject mkvutil_metadata_configure 4 preset "$preset" < /dev/null
  (( ${#MKVUTIL_METADATA_SETTINGS}==0 )) || fail 'failed preset left settings'
done
# Removal-only metadata retains independent per-choice target entry.
mkvutil_metadata_configure '3,4' independent <<< $'4\nfr-CA\n3\nsubtitle'
eq "${MKVUTIL_METADATA_SETTINGS[3:4]}" fr-CA 'independent language target'
eq "${MKVUTIL_METADATA_SETTINGS[4:3]}" subtitle 'independent name target'
reject mkvutil_metadata_configure 4 independent <<< $'12\nremoved'
print -r -- 'preset contracts passed'
''')
    assert result.stdout.strip() == 'preset contracts passed'
    for action in ('Forced', 'Default', 'Language', 'Track name'):
        prompts = [result.stderr.index(f'Original track ID {tid} — {action}') for tid in (0, 4, 3)]
        assert prompts == sorted(prompts)
    assert 'Set language for tracks\nTrack IDs: ' in result.stderr
    assert 'Set name for tracks\nTrack IDs: ' in result.stderr
    assert result.stderr.count('Track IDs:') == 5  # invalid removed target retries, plus independent choices


def test_mkv_utils_configuration_order_retry_metadata_back_and_batch_attribution(env):
    source = _mkv_file(env, 'config.mkv')
    model = _source_json([(0, 'video', 'V_MPEG4/ISO/AVC', True), (3, 'subtitles', 'S_TEXT/ASS', False),
                          (4, 'audio', 'A_AAC', True), (11, 'audio', 'A_OPUS', False), (12, 'audio', 'A_AAC', True)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/config.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_ledger_reset "$PWD" "$PWD/config.mkv"
mkvutil_batch_request mux 2
mkvutil_batch_metadata_requested 3
prior="${MKVUTIL_BATCHES[1]}"
mkvutil_batch_request mux 1,2
mkvutil_configure_category mux 1,2 <<< $'12\n12,0\n99,0\n4,4\nno-order\n0,4,3\n3,4\nen\nfr-CA\nde\nzero\ne\n5\n\\E'
eq "$(jq -r '.removed_ids|join(",")' <<< "$MKVUTIL_CONFIG")" 12 'removal survived retry/Back'
eq "$(jq -r '.order_ids|join(",")' <<< "$MKVUTIL_CONFIG")" 0,4,3 'explicit order survived retry/Back'
eq "$(jq -c '.settings' <<< "$MKVUTIL_CONFIG")" '{"5:info":"E"}' 'all earlier partial metadata discarded'
eq "$(jq -c '.metadata_output_map' <<< "$MKVUTIL_CONFIG")" '{}' 'title-only has no stale track bindings'
eq "$(jq -r '.metadata_ids' <<< "${MKVUTIL_BATCHES[2]}")" 5 'reselected choice attribution'
eq "${MKVUTIL_BATCHES[1]}" "$prior" 'earlier batch unchanged'
job="$(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG")"
eq "$(jq -r '.retained_ids|join(",")' <<< "$job")" 0,4,3,11 'implicit append retained'
mkvutil_batch_request mux 1,2
mkvutil_configure_category mux 1,2 <<< $'12\n4,0\n4\ne\n   '
eq "$(jq -r '.metadata' <<< "$MKVUTIL_CONFIG")" '' 'blank skip normalized'
eq "$(jq -c '.settings' <<< "$MKVUTIL_CONFIG")" '{}' 'field Back then skip discards metadata'
eq "$(jq -c '.metadata_output_map' <<< "$MKVUTIL_CONFIG")" '{}' 'field Back then skip clears track bindings'
eq "$(jq -r '.metadata_ids' <<< "${MKVUTIL_BATCHES[3]}")" '' 'skip clears active attribution'
eq "$(jq -r '.order' <<< "$MKVUTIL_CONFIG")" 0:4,0:0 'skip preserves structure'
mkvutil_batch_request mux 2
code=0
mkvutil_configure_category mux 2 <<< $'3,0\n4\nE\ne' || code=$?
eq "$code" 4 'list Back returns to Mux actions'
eq "$(jq -r '.metadata_ids' <<< "${MKVUTIL_BATCHES[4]}")" '' 'list Back attribution clear'
eq "$MKVUTIL_CONFIG" '' 'list Back leaves no config'
code=0
mkvutil_configure_category mux 1,2 <<< $'0,3,4,11,12\n12\n0,3\n' || code=$?
eq "$code" 0 'all-track removal retries before order'
eq "$(jq -r '.removed_ids|join(",")' <<< "$MKVUTIL_CONFIG")" 12 'valid removal follows rejected all-track choice'
eq "$(jq -r '.order' <<< "$MKVUTIL_CONFIG")" '0:0,0:3' 'explicit reorder follows valid removal'
print -r -- 'configuration retries passed'
''', {str(source): model})
    assert result.stdout.rstrip().endswith('configuration retries passed')
    assert result.stderr.count('Invalid order.') == 4
    assert result.stderr.count('Remove IDs:') == 4
    assert result.stderr.count('Track order:') == 8
    assert 'Output IDs for each track edit: 0,1,2' in result.stdout
    assert not _command_argv(env, 'fzf') and source.read_text() == 'payload'


def test_mkv_utils_configuration_inherited_metadata_preserves_appended_flags(env):
    source = _mkv_file(env, 'inherited.mkv')
    model = _source_json([(0, 'video', 'V_MPEG4/ISO/AVC', True), (3, 'subtitles', 'S_TEXT/ASS', False),
                          (4, 'audio', 'A_AAC', True), (11, 'audio', 'A_OPUS', False)])
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/inherited.mkv")"
MKVUTIL_SOURCES=("$record")
mkvutil_configure_category mux 2 <<< $'0,4,3\n1-4\n1\n0\n1\n0\n1\n0\nen\nfr-CA\nde\nzero\nfour\nthree'
print -r -- "JOB $(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG")"
''', {str(source): model})
    job = json.loads(next(line[4:] for line in result.stdout.splitlines() if line.startswith('JOB ')))
    assert job['config']['order_ids'] == ['0', '4', '3']
    assert job['retained_ids'] == ['0', '4', '3', '11']
    settings = job['config']['settings']
    assert len(settings) == 12 and all(not key.endswith(':11') for key in settings)
    assert [settings[f'4:{tid}'] for tid in (0, 4, 3)] == ['zero', 'four', 'three']
    args = job['merge_metadata_args']
    assert '11:0' in args  # untouched false forced/default flags still preserved
    assert '11:Original 11' not in args and '11:eng' not in args
    assert job['source_flags']['2:11'] == '0' and job['source_flags']['1:11'] == '0'
    assert 'Track IDs:' not in result.stderr


def test_mkv_utils_metadata_field_back_edit_resets_and_reopens_file_scope_entrypoint(env):
    first, second = _mkv_file(env, 'Edit Back first.mkv'), _mkv_file(env, 'Edit Back second.mkv')
    original = _integration_model()
    actual = json.loads(json.dumps(original))
    actual['container']['properties']['title'] = 'Second title'
    extra = _integration_manifest(env, {first: original, second: original}, post_edit={str(second): actual})
    result = _run_mkv_utils(env, fzf_responses=[[str(first)], [str(second)]],
                            input_data='1\n4,5\n0\npartial name\ne\n5\nSecond title\n', extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_command_argv(env, 'fzf')) == 2
    assert 'partial name' not in result.stdout
    edits = _command_argv(env, 'mkvpropedit')
    assert len(edits) == 1 and edits[0][0] == str(second) and 'title=Second title' in edits[0]
    assert not any('name=' in arg for arg in edits[0])
    assert first.read_bytes() == b'payload' and second.read_bytes() == b'edited-data\n'
    assert _observed_fake_identification(env, second) == actual
    final = result.stdout.split('Final report', 1)[1]
    assert 'Selected: 1' in final and first.name not in final and second.name not in final


def test_mkv_utils_shared_edit_per_id_values_across_source_listing_positions(env):
    first, second = _mkv_file(env, 'First.mkv'), _mkv_file(env, 'Second.mkv')
    original = _integration_model()
    other = json.loads(json.dumps(original))
    other['tracks'] = [other['tracks'][2], other['tracks'][0], other['tracks'][3], other['tracks'][1]]
    sources = {first: original, second: other}
    actuals = {}
    for file, model in sources.items():
        actual = json.loads(json.dumps(model))
        for track in actual['tracks']:
            if track['id'] == 2:
                track['properties'].update(track_name='second ID', language='fre', language_ietf='fr-CA')
            elif track['id'] == 1:
                track['properties'].update(track_name='first ID', language='ger', language_ietf='de')
        actual['container']['properties']['title'] = 'Batch title'
        actuals[str(file)] = actual
    extra = _integration_manifest(env, sources, post_edit=actuals)
    result = _run_mkv_utils(env, fzf_responses=[[str(first), str(second)]],
                            input_data='1\n4,5,3\n2,1\nsecond ID\nfirst ID\nBatch title\nfr-CA\nde\n', extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Edit 4,5,3: name + file title + language" in result.stdout
    assert result.stdout.index("Edit 4,5,3: name + file title + language") < result.stdout.index(f"Processing: {first.name}")
    assert result.stderr.count('Track IDs:') == 1
    calls = _command_argv(env, 'mkvpropedit')
    assert len(calls) == 2 and {call[0] for call in calls} == {str(first), str(second)}
    for file, selector2, selector1 in ((first, 'track:3', 'track:2'), (second, 'track:1', 'track:4')):
        call = next(call for call in calls if call[0] == str(file))
        assert call[call.index(selector2):call.index(selector2) + 5] == [selector2, '--set', 'language=fr-CA', '--set', 'name=second ID']
        assert call[call.index(selector1):call.index(selector1) + 5] == [selector1, '--set', 'language=de', '--set', 'name=first ID']
        assert _observed_fake_identification(env, file) == actuals[str(file)]
    assert len(_command_argv(env, 'fzf')) == 1
    assert all(call[:1] == ['-J'] for call in _command_argv(env, 'mkvmerge'))
    assert 'Done: 2; Failed: 0' in result.stdout


def test_mkv_utils_combined_mux_inherited_per_id_metadata_two_sources(env):
    first, second = _mkv_file(env, 'Combined first.mkv'), _mkv_file(env, 'Combined second.mkv')
    original = _integration_model([(0, 'video', 'V_MPEG4/ISO/AVC', True), (3, 'subtitles', 'S_TEXT/ASS', False),
                                   (4, 'audio', 'A_AAC', True), (11, 'audio', 'A_OPUS', False), (12, 'audio', 'A_AAC', True)])
    other = json.loads(json.dumps(original))
    other['tracks'] = [other['tracks'][3], other['tracks'][2], other['tracks'][0], other['tracks'][4], other['tracks'][1]]
    other['tracks'][0]['properties'].update(forced_track=True, default_track=True, track_name='Untouched second')
    sources = {first: original, second: other}
    stages = {}
    values = {0: ('zero', 'eng', 'eng', True, False), 4: ('four', 'fre', 'fr-CA', False, True),
              3: ('three', 'ger', 'de', True, False)}
    for file, model in sources.items():
        actual = json.loads(json.dumps(model))
        for track in actual['tracks']:
            if track['id'] in values:
                name, language, ietf, forced, default = values[track['id']]
                track['properties'].update(track_name=name, language=language, language_ietf=ietf,
                                           forced_track=forced, default_track=default)
        actual['container']['properties']['title'] = 'Batch title'
        stages[str(file)] = _integration_output(actual, [0, 4, 3, 11])
    extra = _integration_manifest(env, sources, stage=stages)
    result = _run_mkv_utils(env, fzf_responses=[[str(first), str(second)]],
                            input_data='2\n1,2\n12\n0,4,3\n1-5\n1\n0\n1\n0\n1\n0\neng\nfr-CA\nde\nzero\nfour\nthree\nBatch title\n', extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Output IDs for each track edit: 0,1,2' in result.stdout
    assert 'Track IDs:' not in result.stderr
    assert result.stdout.count('Final report') == 1 and 'Done: 2; Failed: 0' in result.stdout
    calls = [call for call in _command_argv(env, 'mkvmerge') if '-o' in call]
    assert len(calls) == 2 and {call[-1] for call in calls} == {str(first), str(second)}
    for file in (first, second):
        call = next(call for call in calls if call[-1] == str(file))
        assert call[call.index('--track-order') + 1] == '0:0,0:4,0:3,0:11'
        for tid, name in ((0, 'zero'), (4, 'four'), (3, 'three')):
            assert f'{tid}:{name}' in call
        assert '4:fr-CA' in call and '3:de' in call
        preserved = '0' if file == first else '1'
        expected_flags = {
            '--forced-display-flag': ['0:1', '4:0', '3:1', f'11:{preserved}'],
            '--default-track-flag': ['0:0', '4:1', '3:0', f'11:{preserved}'],
        }
        for option, expected_values in expected_flags.items():
            assert [call[i + 1] for i, arg in enumerate(call[:-1]) if arg == option] == expected_values
        assert not any(arg.startswith('11:') for i, arg in enumerate(call) if i and call[i - 1] in ('--language', '--track-name'))
        assert _observed_fake_identification(env, file) == stages[str(file)]
    assert len(_command_argv(env, 'fzf')) == 1 and not _command_argv(env, 'mkvpropedit')
    assert not list(env['workdir'].glob('.mkvutil-*'))


def test_mkv_utils_configuration_order_retry_interrupt_stops_before_reprompt(env):
    source = _mkv_file(env, 'interrupt.mkv')
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/interrupt.mkv")"
MKVUTIL_SOURCES=("$record")
functions[original_normalize_order]="${functions[mkvutil_normalize_order]}"
mkvutil_normalize_order() {
  original_normalize_order "$@"
}
functions[original_read]="${functions[_mkvutil_read]}"
_mkvutil_read() { original_read "$@"; MKVUTIL_INTERRUPTED=1; }
code=0
mkvutil_configure_category mux 2 <<< $'99,0\n0,1' || code=$?
eq "$code" 2 'interrupted layout leaves boundedly'
eq "$MKVUTIL_CONFIG" '' 'interrupted retry has no config'
eq "${#MKVUTIL_METADATA_SETTINGS}" 0 'interrupted retry has no settings'
print -r -- 'retry interrupt contract passed'
''', {str(source): _source_json([(0, 'audio', 'A_AAC', True), (1, 'audio', 'A_OPUS', False)])})
    assert result.stdout.rstrip().endswith('retry interrupt contract passed')
    assert result.stderr.count('Track order:') == 1
    assert 'Invalid order.' not in result.stderr


def test_mkv_utils_back_cohort_request_identity_and_current_subset(env):
    result = _run_planning_contract(env, r'''
first="$PWD/first.mkv"; excluded="$PWD/excluded.mkv"; completed="$PWD/completed.mk3d"; last=$PWD/$'last\n.mkv\n'
mkvutil_ledger_reset "$PWD" "$first" "$excluded" "$completed" "$last"
mkvutil_ledger_exclude "$excluded" 'explicit exclusion'
mkvutil_ledger_result "$(jq -cn --arg source "$completed" '{source:$source,status:"success",destination:"converted.mka"}')"
# A converted original need not exist to be recognized as completed.
MKVUTIL_SOURCES=()
MKVUTIL_SELECTED_FILES=("$completed" "$excluded" "$last" "$first")
mkvutil_batch_request mux 2
expected="$(_mkvutil_json_array "$last" "$first")"
eq "$(jq '.sources' <<< "${MKVUTIL_BATCHES[1]}")" "$expected" 'current selection filters verified exclusions/completed identities'
MKVUTIL_SOURCES=("$(jq -cn --arg source "$first" '{source:$source}')")
mkvutil_batch_request edit 5
eq "$(jq '.sources' <<< "${MKVUTIL_BATCHES[2]}")" "$(_mkvutil_json_array "$first")" 'full inspected pool takes precedence'
MKVUTIL_SOURCES=(); MKVUTIL_SELECTED_FILES=()
mkvutil_batch_request edit 5
eq "$(jq '.sources' <<< "${MKVUTIL_BATCHES[3]}")" "$(_mkvutil_json_array "$first" "$last")" 'legacy scope fallback filters completed/excluded'
for invalid in missing malformed multiple-documents invalid-first wrong-identity bad-status; do
  saved="${MKVUTIL_LEDGER[$first]}"
  case "$invalid" in
    missing) unset "MKVUTIL_LEDGER[$first]" ;;
    malformed) MKVUTIL_LEDGER[$first]='{}' ;;
    multiple-documents) MKVUTIL_LEDGER[$first]="$saved"$'\n'"$saved" ;;
    invalid-first) MKVUTIL_LEDGER[$first]='{}'$'\n'"$saved" ;;
    wrong-identity) MKVUTIL_LEDGER[$first]="$(jq --arg source "$last" '.source=$source' <<< "$saved")" ;;
    bad-status) MKVUTIL_LEDGER[$first]="$(jq '.status="unknown"' <<< "$saved")" ;;
  esac
  MKVUTIL_SELECTED_FILES=("$first")
  reject mkvutil_batch_request mux 2
  eq "${#MKVUTIL_BATCHES}" 3 "invalid ledger did not publish request: $invalid"
  MKVUTIL_LEDGER[$first]="$saved"
done
nul_record="$(jq -cn --arg source "$first" '{source:($source+"\u0000suffix")}')"
source_record="$(jq -cn --arg source "$first" '{source:$source}')"
for invalid in '{}' '{"source":null}' '{"source":"relative.mkv"}' "$nul_record" "$source_record"$'\n'"$source_record"; do
  MKVUTIL_SOURCES=("$invalid")
  reject mkvutil_batch_request mux 2
done
print -r -- 'cohort identity contracts passed'
''', {})
    assert result.stdout.strip() == 'cohort identity contracts passed'
    assert not _command_argv(env, 'fzf') and not _command_argv(env, 'mkvmerge')


def test_mkv_utils_back_atomic_initial_inspection_resets_and_reselects_entire_cohort(env):
    files = [_mkv_file(env, name) for name in ('first.mkv', 'excluded.mkv', 'back.mkv', 'last.mkv')]
    _set_fake_fzf_responses(env, [[str(file) for file in files], [str(file) for file in files]])
    sources = {str(file): _source_json([(0, 'audio', 'A_AAC', True)]) for file in files}
    result = _run_planning_contract(env, r'''
functions[original_capture_source]="${functions[mkvutil_capture_source]}"
functions[original_inspect_sources]="${functions[mkvutil_inspect_sources]}"
inspection_pass=0
mkvutil_inspect_sources() {
  (( ++inspection_pass ))
  local result=0
  original_inspect_sources || result=$?
  if (( result==4 )); then
    eq "${#MKVUTIL_SOURCES}" 0 'Back publishes no partial inspection pool'
    eq "${#MKVUTIL_SELECTED_FILES}" 4 'Back preserves even not-yet-inspected selection'
  fi
  return "$result"
}
mkvutil_capture_source() {
  printf '%s\0' "$1" >> "$PWD/captures.bin"
  if (( inspection_pass==1 )) && [[ "$1" == */excluded.mkv || "$1" == */back.mkv ]]; then return 1; fi
  original_capture_source "$1"
}
code=0
mkvutil_main "$PWD" || code=$?
eq "$code" 0 'explicit exclusion and Back leave neutral invocation successful'
eq "$inspection_pass" 2 'Back triggers a fresh selection and inspection'
eq "${#MKVUTIL_SELECTED_FILES}" 0 'subsequent metadata Back clears fresh selection'
eq "${#MKVUTIL_SOURCES}" 0 'no abandoned source cache remains'
eq "${#MKVUTIL_LEDGER}" 0 'old explicit exclusions discarded by public Back'
eq "${#MKVUTIL_BATCHES}" 0 'unexecuted requests discarded by public Back'
eq "$MKVUTIL_CONFIG" '' 'pending config discarded'
eq "${#MKVUTIL_JOBS}" 0 'no pending jobs'
print -r -- 'initial atomic Back passed'
''', sources, input_data='1\n5\nY\ne\n5\ne\ne\ne\n')
    assert result.stdout.rstrip().endswith('initial atomic Back passed')
    calls = (env['workdir'] / 'captures.bin').read_bytes().split(b'\0')[:-1]
    assert calls == [os.fsencode(file) for file in (*files[:3], *files)]
    assert len(_command_argv(env, 'fzf')) == 2
    assert len(_command_argv(env, 'mkvmerge')) == 5
    assert 'Final report' not in result.stdout
    assert all(file.read_text() == 'payload' for file in files)


def test_mkv_utils_back_fresh_subset_inspection_retry_preserves_history_and_completed_source(env):
    files = [_mkv_file(env, name) for name in ('completed.mkv', 'skip-first.mkv', 'excluded.mkv', 'back.mkv', 'last.mkv')]
    sources = {str(file): _source_json([(0, 'audio', 'A_AAC', True)]) for file in files}
    result = _run_planning_contract(env, r'''
functions[original_capture_source]="${functions[mkvutil_capture_source]}"
phase=1
mkvutil_capture_source() {
  printf '%s\0' "$1" >> "$PWD/captures.bin"
  if (( phase==2 )) && [[ "$1" == */excluded.mkv || "$1" == */back.mkv ]]; then return 1; fi
  original_capture_source "$1"
}
# Direct helper test: completed scopes never return here from the public UI.
MKVUTIL_SELECTED_FILES=("$PWD/completed.mkv" "$PWD/skip-first.mkv" "$PWD/excluded.mkv" "$PWD/back.mkv" "$PWD/last.mkv")
mkvutil_ledger_reset "$PWD" "${MKVUTIL_SELECTED_FILES[@]}"
mkvutil_inspect_sources
mkvutil_batch_request mux 1
    MKVUTIL_HAS_RUN=1
    mkvutil_ledger_result "$(jq -cn --arg source "$PWD/completed.mkv" '{source:$source,status:"success",destination:$source,phase:"complete",actual_state:"published_complete"}')"
    for file in "$PWD/skip-first.mkv" "$PWD/excluded.mkv" "$PWD/back.mkv" "$PWD/last.mkv"; do
      receipt="$(jq -cn --arg source "$file" --arg reference "$PWD/completed.mkv" '{kind:"removal-mismatch",source:$source,reference:$reference,reasons:[{original_id:"0",reason:"codec-mismatch",expected:{type:"audio",codec_id:"A_OPUS"},actual:{type:"audio",codec_id:"A_AAC"}}]}')"
      mkvutil_ledger_skip "$receipt"
      MKVUTIL_REMOVAL_SKIPS+=("$receipt")
    done
    phase=2
    code=0
    mkvutil_prepare_skipped_subset || code=$?
    eq "$code" 4 'fresh inspection Back propagated'
    eq "${#MKVUTIL_SOURCES}" 0 'fresh partial pool not published'
    eq "${#MKVUTIL_SELECTED_FILES}" 4 'prepared subset includes not-yet-inspected last file'
    eq "${#MKVUTIL_REMOVAL_SKIP_HISTORY}" 4 'all original mismatch receipts archived'
    phase=3
    mkvutil_inspect_sources
    mkvutil_batch_request mux 2
  eq "$(jq '.sources' <<< "${MKVUTIL_BATCHES[2]}")" "$(_mkvutil_json_array "$PWD/skip-first.mkv" "$PWD/back.mkv" "$PWD/last.mkv")" 'retry batch uses eligible current subset only'
  eq "${#MKVUTIL_SOURCES}" 3 'all eligible subset files inspected'
  eq "${#MKVUTIL_REMOVAL_SKIP_HISTORY}" 4 'reinspection retains archived mismatch history'
code=0
mkvutil_finish 2 || code=$?
eq "$code" 1 'unresolved mismatch status remains sticky after main exit'
eq "$(jq -r '.status' <<< "${MKVUTIL_LEDGER[$PWD/completed.mkv]}")" success 'completed outcome retained'
eq "$(jq -r '.attempts|length' <<< "${MKVUTIL_LEDGER[$PWD/completed.mkv]}")" 1 'completed outcome never replayed'
eq "$(jq -r '.excluded_from_retry' <<< "${MKVUTIL_LEDGER[$PWD/excluded.mkv]}")" true 'explicit unresolved exclusion survives retry'
eq "$(jq -r '.status' <<< "${MKVUTIL_LEDGER[$PWD/excluded.mkv]}")" skipped 'exclusion does not resolve previous required mismatch'
eq "${#MKVUTIL_JOBS}" 0 'no jobs survive Back'
print -r -- 'fresh subset Back passed'
''', sources, input_data='Y\nE\n')
    assert result.stdout.rstrip().endswith('fresh subset Back passed')
    calls = (env['workdir'] / 'captures.bin').read_bytes().split(b'\0')[:-1]
    assert calls == [os.fsencode(file) for file in (*files, *files[1:4], files[1], files[3], files[4])]
    assert not _command_argv(env, 'fzf') and len(_command_argv(env, 'mkvmerge')) == 9
    assert result.stdout.count('Final report') == 1 and 'Done: 1' in result.stdout and 'Skipped: 4' in result.stdout
    assert all(file.read_text() == 'payload' for file in files)


def test_mkv_utils_back_planning_exclusion_preserves_full_unexcluded_pool(env):
    files = [_mkv_file(env, name) for name in ('first.mkv', 'excluded.mkv', 'back.mkv', 'last.mkv')]
    result = _run_planning_contract(env, r'''
for file in "$PWD/first.mkv" "$PWD/excluded.mkv" "$PWD/back.mkv" "$PWD/last.mkv"; do
  MKVUTIL_SOURCES+=("$(mkvutil_capture_source "$file")")
done
mkvutil_ledger_reset "$PWD" "$PWD/first.mkv" "$PWD/excluded.mkv" "$PWD/back.mkv" "$PWD/last.mkv"
mkvutil_batch_request edit 5
mkvutil_plan_job() {
  local file="$(jq -r '.source' <<< "$1")"
  [[ "$file" != */excluded.mkv && "$file" != */back.mkv ]] || return 1
  print -r -- '{"planned":true}'
}
MKVUTIL_CONFIG='{"category":"edit"}'
code=0
mkvutil_plan_queue <<< $'Y\ne' || code=$?
eq "$code" 4 'planning exclusion Back'
eq "${#MKVUTIL_SOURCES}" 3 'full pool survives except confirmed exclusion'
eq "${#MKVUTIL_JOBS}" 0 'partially built queue never published'
mkvutil_discard_configuration
mkvutil_batch_request edit 5
eq "$(jq '.sources' <<< "${MKVUTIL_BATCHES[2]}")" "$(_mkvutil_json_array "$PWD/first.mkv" "$PWD/back.mkv" "$PWD/last.mkv")" 'uninspected planning suffix remains requested'
eq "$MKVUTIL_CONFIG" '' 'pending configuration discarded'
print -r -- 'planning Back passed'
''', {str(file): _source_json([(0, 'audio', 'A_AAC', True)]) for file in files})
    assert result.stdout.rstrip().endswith('planning Back passed')
    assert len(_command_argv(env, 'mkvmerge')) == 4


def test_mkv_utils_back_structural_and_extract_fields_reset_configuration(env):
    source = _mkv_file(env, 'fields.mkv')
    result = _run_planning_contract(env, r'''
record="$(mkvutil_capture_source "$PWD/fields.mkv")"
MKVUTIL_SOURCES=("$record")
for category operations data in mux 1 e mux 2 E extract 2 e; do
  MKVUTIL_CONFIG=old; MKVUTIL_JOBS=(old); MKVUTIL_METADATA_SETTINGS[4:0]=old
  code=0
  mkvutil_configure_category "$category" "$operations" <<< "$data" || code=$?
  eq "$code" 4 "field Back: $category/$operations"
  eq "$MKVUTIL_CONFIG" '' 'no partial config'
  eq "${#MKVUTIL_JOBS}" 0 'no stale jobs'
  eq "${#MKVUTIL_METADATA_SETTINGS}" 0 'no partial metadata'
  eq "${#MKVUTIL_SOURCES}" 1 'file pool retained'
done
print -r -- 'structural Back passed'
''', {str(source): _source_json([(0, 'audio', 'A_AAC', True), (1, 'audio', 'A_OPUS', False)])})
    assert result.stdout.rstrip().endswith('structural Back passed')
    assert 'Invalid order' not in result.stderr


def test_mkv_utils_back_extract_id_returns_to_actions_fresh_picker_entrypoint(env):
    source = _mkv_file(env, 'Extract Back.mkv')
    model = _integration_model()
    extra = _integration_manifest(env, {source: model}, extraction={str(source): {'tracks': {'outputs': {'1': {'data': 'aac payload'}}}}})
    result = _run_mkv_utils(env, fzf_responses=[[str(source)], [str(source)]], input_data='3\n2\ne\n2\n1\n', extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr.count('Extract IDs:') == 2
    assert len(_command_argv(env, 'fzf')) == 2 and len(_command_argv(env, 'mkvmerge')) == 3
    assert all(call[:1] == ['-J'] for call in _command_argv(env, 'mkvmerge'))
    assert (source.parent / 'Extract Back - Track [1].aac').read_bytes() == b'aac payload'
    assert result.stdout.count('Final report') == 1 and 'Done: 1; Failed: 0' in result.stdout
    assert len(_command_argv(env, 'mkvextract')) == 1 and source.read_text() == 'payload'


def test_mkv_utils_back_mux_metadata_field_preserves_structure_and_selection(env):
    source = _mkv_file(env, 'Mux field Back.mkv')
    original = _integration_model()
    expected = _integration_output(original, [2, 1, 3])
    expected['container']['properties']['title'] = 'Mux title'
    extra = _integration_manifest(env, {source: original}, stage={str(source): expected})
    result = _run_mkv_utils(env, fzf_responses=[[str(source)]],
                            input_data='2\n1,2\n0\n2,1\n4\ne\n5\nMux title\n', extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Mux 1,2: remove + reorder; metadata 5" in result.stdout
    assert result.stdout.index("Mux 1,2: remove + reorder; metadata 5") < result.stdout.index(f"Processing: {source.name}")
    assert result.stderr.count('Metadata [none]:') == 2
    assert len(_command_argv(env, 'fzf')) == 1
    writers = [call for call in _command_argv(env, 'mkvmerge') if '-o' in call]
    assert len(writers) == 1 and writers[0][writers[0].index('--track-order') + 1] == '0:2,0:1,0:3'
    assert '--title' in writers[0] and writers[0][writers[0].index('--title') + 1] == 'Mux title'
    assert '--track-name' not in writers[0] and '--language' not in writers[0]
    assert not source.exists() and source.with_suffix('.mka').read_bytes() == b'candidate-data\n'
    assert _observed_fake_identification(env, source.with_suffix('.mka')) == expected
    assert 'Selected: 1' in result.stdout.split('Final report', 1)[1]


@pytest.mark.parametrize('setup', ('1\n1\n', '2\n2,0\n', '1,2\n1\n2,0\n'),
                         ids=('remove', 'reorder', 'remove-reorder'))
def test_mkv_utils_back_mux_metadata_list_resets_and_reopens_picker(env, setup):
    first, second = _mkv_file(env, 'Mux list first.mkv'), _mkv_file(env, 'Mux list second.mkv')
    model = _integration_model()
    expected = _integration_output(model, [1, 2, 3])
    extra = _integration_manifest(env, {first: model, second: model}, stage={str(second): expected})
    result = _run_mkv_utils(env, fzf_responses=[[str(first)], [str(second)]],
                            input_data='2\n' + setup + 'E\n1\n0\n\n', extra_env=extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_command_argv(env, 'fzf')) == 2
    writers = [call for call in _command_argv(env, 'mkvmerge') if '-o' in call]
    assert len(writers) == 1 and writers[0][-1] == str(second)
    assert writers[0][writers[0].index('--track-order') + 1] == '0:1,0:2,0:3'
    assert result.stderr.count('Category:') == 1
    assert result.stderr.count('Actions:') == 2
    assert result.stderr.count('Metadata [none]:') == 2
    assert first.read_bytes() == b'payload' and not first.with_suffix('.mka').exists()
    assert not second.exists() and _observed_fake_identification(env, second.with_suffix('.mka')) == expected
    final = result.stdout.split('Final report', 1)[1]
    assert 'Selected: 1' in final and first.name not in final
    assert f'{second.name} => {second.with_suffix(".mka").name}' in final
    assert result.stdout.count('Final report') == 1


def test_mkv_utils_back_initial_inspection_interrupt_never_rereads_menu(tmp_path):
    result = _run_metadata_contract(tmp_path, r'''
reads=0; finished=0
_mkvutil_menu_read() { (( ++reads )); if (( reads==1 )); then REPLY=1; else REPLY=5; fi; }
mkvutil_scan_files() { MKVUTIL_SCAN_FILES=("$PWD/pending.mkv"); }
mkvutil_select_files() { MKVUTIL_SELECTED_FILES=("${MKVUTIL_SCAN_FILES[@]}"); }
mkvutil_inspect_sources() { MKVUTIL_INTERRUPTED=1; return 4; }
mkvutil_finish() { eq "$1" 1 'interrupted inspection finishes as interrupted'; (( ++finished )); return 1; }
code=0
mkvutil_main "$PWD" || code=$?
eq "$code" 1 'interrupt overrides Back control flow'
eq "$reads" 2 'no additional blocking menu after inspection interrupt'
eq "$finished" 1 'one terminal finish'
eq "${#MKVUTIL_BATCHES}" 1 'request remains attributed'
print -r -- 'inspection interrupt passed'
''')
    assert result.stdout.rstrip().endswith('inspection interrupt passed')


@pytest.mark.parametrize('boundary', ('quiet', 'unresolved', 'unresolved-actions-eof', 'report-failure'))
def test_mkv_utils_back_metadata_actions_control_clears_unexecuted_ledger_without_reports(env, boundary):
    result = _run_planning_contract(env, r'''
mkvutil_scan_files() { MKVUTIL_SCAN_FILES=("$PWD/pending.mkv"); }
mkvutil_select_files() { MKVUTIL_SELECTED_FILES=("${MKVUTIL_SCAN_FILES[@]}"); }
mkvutil_inspect_sources() { MKVUTIL_SOURCES=("$(jq -cn --arg source "$PWD/pending.mkv" '{source:$source}')"); }
mkvutil_controller() {
  if [[ "$TEST_BACK_BOUNDARY" != quiet ]]; then
    local receipt="$(jq -cn --arg source "$PWD/pending.mkv" '{kind:"removal-mismatch",source:$source,reference:$source,reasons:[{original_id:"0",reason:"missing-id",expected:{type:"audio",codec_id:"A_AAC"},actual:null}]}')"
    mkvutil_ledger_skip "$receipt"
  fi
  return 4
}
report_calls=0
mkvutil_final_report() { (( ++report_calls )); print -u2 -r -- 'Unexpected report for abandoned selection'; return 1; }
code=0
mkvutil_main "$PWD" || code=$?
eq "$code" 0 'metadata list Back discards all unexecuted outcomes'
eq "$MKVUTIL_CONFIG" '' 'pending configuration discarded'
eq "${#MKVUTIL_JOBS}" 0 'pending jobs discarded'
eq "${#MKVUTIL_LEDGER}" 0 'unexecuted outcome ledger discarded'
eq "${#MKVUTIL_SELECTED_FILES}" 0 'selection discarded'
eq "$report_calls" 0 'abandoned selection never produces a report'
print -r -- 'main Back control passed'
''', {}, input_data='2\n2\n' + ('' if boundary == 'unresolved-actions-eof' else 'e\n'),
        extra_env={'TEST_BACK_BOUNDARY': boundary})
    assert result.stdout.rstrip().endswith('main Back control passed')
    assert result.stdout.count('1) Matroska Edit') == (1 if boundary == 'unresolved-actions-eof' else 2)
    assert result.stderr.count('Actions:') == 2
    assert 'Final report' not in result.stdout and 'Unexpected report' not in result.stderr
    assert not _command_argv(env, 'mkvmerge') and not _command_argv(env, 'fzf')


def test_mkv_utils_back_prepared_subset_preserves_newline_source_identity(env):
    result = _run_planning_contract(env, r'''
file=$PWD/$'skipped\n.mkv\n'
mkvutil_ledger_reset "$PWD" "$file"
MKVUTIL_SOURCES=(); MKVUTIL_SELECTED_FILES=("$file")
mkvutil_batch_request mux 1
receipt="$(jq -cn --arg source "$file" '{kind:"removal-mismatch",source:$source,reference:$source,reasons:[{original_id:"0",reason:"missing-id"}]}')"
mkvutil_ledger_skip "$receipt"
eq "$(jq -r '.status' <<< "${MKVUTIL_LEDGER[$file]}")" skipped 'original newline path receives skip history'
MKVUTIL_REMOVAL_SKIPS=("$receipt"); MKVUTIL_JOBS=()
mkvutil_capture_source() { jq -cn --arg source "$1" '{source:$source}'; }
mkvutil_prepare_skipped_subset
eq "${MKVUTIL_SELECTED_FILES[1]}" "$file" 'prepared selection retains trailing newlines'
IFS= read -r -d '' observed < <(jq -j '.source,"\u0000"' <<< "${MKVUTIL_SOURCES[1]}")
eq "$observed" "$file" 'prepared source retains trailing newlines'
mkvutil_batch_request mux 2
eq "$(jq '.sources' <<< "${MKVUTIL_BATCHES[2]}")" "$(_mkvutil_json_array "$file")" 'fresh request retains same original newline identity'
eq "${#MKVUTIL_REMOVAL_SKIP_HISTORY}" 1 'original newline receipt retained'
print -r -- 'prepared newline identity passed'
''', {})
    assert result.stdout.rstrip().endswith('prepared newline identity passed')
    assert not _command_argv(env, 'mkvmerge')


def _assert_owned_group_gone(group, timeout=0.5):
    """Require confirmed absence, allowing bounded macOS group retirement."""
    import time

    deadline = time.monotonic() + timeout
    while True:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            # EPERM cannot establish absence. Keep probing until it is actually
            # gone, just as the production native-shutdown guard does.
            pass
        assert time.monotonic() < deadline, f"Owned process group {group} shutdown unconfirmed"
        time.sleep(0.01)


@pytest.mark.parametrize("category,stop", [
    ("edit", "int"), ("mux", "int"), ("extract", "int"),
    ("attachments", "int"), ("mux", "term"), ("edit", "hup"),
    ("analysis", "int"), ("analysis", "complete"), ("analysis", "dumb-complete"),
    ("mux", "late-int"),
    ("mux", "native-output"),
    ("extract", "descendant-int"),
    ("extract", "unconfirmed-int"),
])
def test_mkv_utils_runtime_stop_terminal(env, category, stop):
    """Real keyboard/terminal delivery; fake writers pause after creating data."""
    import fcntl
    import pty
    import select
    import signal
    import termios
    import time

    first, second = _mkv_file(env, "Active episode.mkv"), _mkv_file(env, "Missed episode.mkv")
    original = _integration_model(attachments=[{"id": 1, "file_name": "Font.ttf", "size": 4}])
    edited = json.loads(json.dumps(original)); edited["container"]["properties"]["title"] = "Stop test"
    extra = _integration_manifest(env, {first: original, second: original},
        stage={str(first): _integration_output(original, [1, 0, 2, 3]),
               **({str(second): _integration_output(original, [1, 0, 2, 3])} if stop == "native-output" else {})},
        post_edit={str(first): edited},
        extraction={str(first): {"attachments": {"outputs": {"1": {"data": "font"}}},
                                 "tracks": {"outputs": {"3": {"data": "unfinished track"}}}}})
    marker = env["fake_state"] / "writer-ready"
    analysis_last_marker = env["fake_state"] / "analysis-last-ready"
    analysis_release = env["fake_state"] / "analysis-release"
    tool, anchor = {
        "edit": ("mkvpropedit", 'code = manifest.get("edit_code", 0)'),
        "mux": ("mkvmerge", 'code = manifest.get("merge_code", 0)'),
        "extract": ("mkvextract", 'code = stage.get("code", 0)'),
        "attachments": ("mkvextract", 'code = stage.get("code", 0)'),
        "analysis": ("mkvmerge", 'if [ "$call_mode" = "json" ]; then'),
    }[category]
    condition = 'mode == "tracks"' if category == "extract" else 'mode == "attachments"' if category == "attachments" else "True"
    if stop == "native-output":
        condition = 'str(source) == os.environ["TEST_NATIVE_DISPLAY_SOURCE"]'
    executable = env["fake_bin"] / tool
    body = executable.read_text()
    assert body.count(anchor) == 1
    descendant_setup = ""
    if stop == "descendant-int":
        descendant_setup = '''    import subprocess
    child_code = "import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(os.environ['TEST_STOP_MARKER']+'.descendant').write_text(str(os.getpid()));time.sleep(10)"
    subprocess.Popen([sys.executable,"-c",child_code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    ready_deadline = time.monotonic() + 1
    while not Path(str(marker)+".descendant").exists() and time.monotonic() < ready_deadline:time.sleep(0.01)
'''
    if category == "analysis" and stop in ("complete", "dumb-complete"):
        hold_anchor = '  if [ -n "${TEST_FAKE_EXECUTION_JSON:-}" ]; then'
        assert body.count(hold_anchor) == 1
        body = body.replace(hold_anchor, '''  if [ "$source_file" = "$TEST_ANALYSIS_HOLD_PATH" ]; then
    printf '%s\\n' "$$" > "$TEST_ANALYSIS_LAST_MARKER"
    while [ ! -e "$TEST_ANALYSIS_RELEASE" ]; do /bin/sleep 0.02; done
  fi
  if [ -n "${TEST_FAKE_EXECUTION_JSON:-}" ]; then''', 1)
    elif category == "analysis":
        body = body.replace(anchor, '''if [ "$call_mode" = "json" ]; then
  printf '%s\\n' "$$" > "$TEST_STOP_MARKER"
  sleep 0.8
fi
if [ "$call_mode" = "json" ]; then''', 1)
    else:
        display_setup = ""
        hold_setup = "    time.sleep(0.8)"
        if stop == "native-output":
            display_setup = '''    import os
    raw_path = os.environ["TEST_NATIVE_DISPLAY_SOURCE"].encode()
    split = len(raw_path) // 2
    os.write(1, b"NATIVE OUT: " + raw_path[:split])
    time.sleep(0.15)
    os.write(1, raw_path[split:] + b"\\n")
    os.write(2, b"NATIVE ERR: " + raw_path + b"\\n")
'''
            hold_setup = '''    while not Path(os.environ["TEST_NATIVE_DISPLAY_RELEASE"]).exists():
        time.sleep(0.02)'''
        body = body.replace(anchor, f'''if {condition}:
    import time
    marker = Path(os.environ["TEST_STOP_MARKER"])
{descendant_setup}\
{display_setup}\
    marker.write_text(str(os.getpid()))
{hold_setup}
    marker.with_suffix(".finished").write_text("finished")
{anchor}''')
    executable.write_text(body)
    result_marker = env["fake_state"] / "result-check-ready"
    if stop == "late-int":
        checker = env["fake_bin"] / "jq"
        checker_text = checker.read_text()
        checker.write_text(checker_text.replace("set -e\n", '''set -e
case "$*" in
  *'$result.source==$job.source'*)
    printf ready > "$TEST_RESULT_MARKER"
    sleep 0.6
    ;;
esac
''', 1))
    _set_fake_fzf_responses(env, [[str(first), str(second)]])
    transport_root = env["fake_state"] / "transport"; transport_root.mkdir()
    run_env = os.environ.copy()
    run_env.update({
        "HOME": str(env["workdir"]), "TERM": "xterm-256color", "TMPDIR": str(transport_root),
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq", "TEST_REAL_PYTHON": sys.executable,
        "TEST_USE_REAL_JSON": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]), "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]), "TEST_STOP_MARKER": str(marker),
        "TEST_RESULT_MARKER": str(result_marker),
        "TEST_FAKE_FZF_SELECTIONS": str(env["fake_fzf_selections"]), **extra,
    })
    native_display_release = env["fake_state"] / "native-display-release"
    if stop == "native-output":
        run_env.update(TEST_NATIVE_DISPLAY_SOURCE=str(first),
                       TEST_NATIVE_DISPLAY_RELEASE=str(native_display_release))
    if category == "analysis" and stop in ("complete", "dumb-complete"):
        run_env.update(TERM="dumb" if stop == "dumb-complete" else "xterm-256color",
                       TEST_ANALYSIS_HOLD_PATH=str(second),
                       TEST_ANALYSIS_LAST_MARKER=str(analysis_last_marker),
                       TEST_ANALYSIS_RELEASE=str(analysis_release))
    if stop in ("descendant-int", "unconfirmed-int"):
        fault_dir = env["workdir"].parent / "shutdown-probe-fault"
        fault_dir.mkdir()
        (fault_dir / "sitecustomize.py").write_text(_EXTRACT_FAULTS)
        run_env.update(PYTHONPATH=str(fault_dir), TEST_EXTRACT_FAULT=(
            "shutdown_probe_transient" if stop == "descendant-int" else "shutdown_probe_denied"))
    for name in ("mkvmerge", "mkvpropedit", "mkvextract", "fzf"):
        assert Path(shutil.which(name, path=run_env["PATH"])).resolve() == (env["fake_bin"] / name).resolve()
    master, terminal = pty.openpty()
    before = termios.tcgetattr(terminal)

    def own_terminal():
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.tcsetpgrp(0, os.getpgrp())

    process = subprocess.Popen(["/usr/local/bin/zsh", "-f", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, stdin=terminal, stdout=terminal, stderr=terminal,
        start_new_session=True, preexec_fn=own_terminal)
    output = bytearray(); deadline = time.monotonic() + 20

    def receive():
        if select.select([master], [], [], 0.05)[0]:
            try: data = os.read(master, 65536)
            except OSError: return False
            output.extend(data)
            return bool(data)
        return True

    def answer(prompt, value):
        while prompt not in output and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert prompt in output, output.decode(errors="replace")
        os.write(master, value)

    try:
        if stop == "dumb-complete":
            answer(b"Category: ", b"4\n")
        else:
            answer(b"Category: ", {"edit": b"1\n", "mux": b"2\n", "analysis": b"4\n"}.get(category, b"3\n"))
        if category != "analysis":
            answer(b"Actions: ", {"edit": b"5\n", "mux": b"2\n", "extract": b"1,2\n", "attachments": b"1\n"}[category])
            if category == "edit": answer(b"Title [clear]: ", b"Stop test\n")
            elif category == "mux":
                answer(b"Track order:", b"1,0\n")
                answer(b"Metadata [none]: ", b"\n")
            elif category == "extract": answer(b"Extract IDs:", b"3\n")
        analysis_scan = category == "analysis" and stop in ("complete", "dumb-complete")
        ready_marker = analysis_last_marker if analysis_scan else marker
        while not ready_marker.exists() and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert ready_marker.exists(), output.decode(errors="replace")
        if stop == "native-output":
            expected_native = f"NATIVE OUT: {first.name}".encode()
            expected_error = f"NATIVE ERR: {first.name}".encode()
            while (expected_native not in output or expected_error not in output) and time.monotonic() < deadline:
                receive()
            visible = output.decode(errors="replace")
            assert expected_native.decode() in visible and f"NATIVE ERR: {first.name}" in visible, visible
            assert str(first) not in visible, visible
        if category == "analysis":
            if stop == "dumb-complete":
                assert not _analysis_spinner_frames(output.decode(errors="replace"))
            else:
                while len(set(_analysis_spinner_frames(output.decode(errors="replace")))) < 2 and time.monotonic() < deadline:
                    receive()
                frames = _analysis_spinner_frames(output.decode(errors="replace"))
                assert len(set(frames)) >= 2, output.decode(errors="replace")
            if analysis_scan:
                scanning = output.decode(errors="replace")
                assert "Analysis reference file:" not in scanning
                assert "mkvmerge JSON track listing" not in scanning
        mask = termios.ICANON | termios.ECHO
        assert before[3] & mask == termios.tcgetattr(terminal)[3] & mask
        # e is ordinary terminal typeahead during processing, never a stop key.
        os.write(master, b"e")
        if analysis_scan:
            analysis_release.write_text("release", encoding="utf-8")
        elif stop in ("int", "late-int", "descendant-int", "unconfirmed-int"):
            os.write(master, b"\x03")
            if category in ("edit", "mux"):
                if stop == "late-int":
                    while not result_marker.exists() and time.monotonic() < deadline: receive()
                    assert result_marker.exists(), output.decode(errors="replace")
                    os.write(master, b"\x03")
                else: answer(b"finishing the current file", b"\x03")
        elif stop == "native-output":
            native_display_release.write_text("release", encoding="utf-8")
        else:
            process.send_signal(signal.SIGTERM if stop == "term" else signal.SIGHUP)
        while process.poll() is None and time.monotonic() < deadline: receive()
        assert process.poll() is not None, output.decode(errors="replace")
        while select.select([master], [], [], 0)[0] and time.monotonic() < deadline:
            if not receive(): break
        text = output.decode(errors="replace")
        assert process.returncode == (0 if analysis_scan or stop == "native-output" else 1), text
        assert "Review/change" not in text and "Preview resulting" not in text
        assert "Review choice:" not in text
        if category == "analysis":
            assert "Final report" in text and "Actions: " not in text
            if analysis_scan:
                header_index = text.index("Analysis reference file: Active episode.mkv")
                listing_index = text.index("mkvmerge JSON track listing")
                report_index = text.index("Final report")
                if stop == "complete":
                    clear_index = text.rfind("\r\x1b[2K", 0, header_index)
                    assert 0 <= text.index("Analysing") < clear_index < header_index < listing_index < report_index
                else:
                    assert "Analysing" not in text and "\r\x1b[2K" not in text
                    assert header_index < listing_index < report_index
                assert text.count("mkvmerge JSON track listing") == 1
                header_start, header_end, _ = _ascii_box_contains(
                    text, "Analysis", f"Current Work Dir: {env['workdir']}",
                    "Analysis reference file: Active episode.mkv")
                text_lines = text.splitlines()
                listing_line = next(i for i, line in enumerate(text_lines) if "mkvmerge JSON track listing" in line)
                assert header_start < header_end < listing_line
                assert "" in text_lines[header_end + 1:listing_line]
                _ascii_box_contains(text, "Final report")
                assert not _analysis_spinner_frames(text[report_index:])
                assert int(analysis_last_marker.read_text()) > 0
                with pytest.raises(ProcessLookupError): os.kill(int(analysis_last_marker.read_text()), 0)
                assert first.read_bytes() == second.read_bytes() == b"payload"
            else:
                assert "Analysis interrupted." in text
                _ascii_box_contains(text, "Not attempted", "Missed episode.mkv")
                assert str(second) not in text
                before_report, _, final_report = text.partition("Final report")
                assert second.name not in before_report
                _ascii_box_contains(final_report, "Not attempted", "Missed episode.mkv")
                report_index = text.index("Final report")
                clear_index = text.rfind("\r\x1b[2K", 0, report_index)
                assert 0 <= text.index("Analysing") < clear_index < report_index
                assert len(set(_analysis_spinner_frames(text[:clear_index]))) >= 2
                assert not _analysis_spinner_frames(text[report_index:])
                _assert_owned_group_gone(process.pid)
            assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
            assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
            assert _command_argv(env, "fzf")
        elif stop == "native-output":
            assert "Mux 2: reorder" in text and "Processing: Active episode.mkv" in text
            assert text.count("NATIVE OUT: Active episode.mkv") == 1
            assert text.count("NATIVE ERR: Active episode.mkv") == 1
            assert text.index("NATIVE OUT: Active episode.mkv") < text.index("File progress")
            assert text.index("NATIVE ERR: Active episode.mkv") < text.index("File progress")
            assert text.index("File progress") < text.index("Final report")
            assert str(first) not in text and marker.with_suffix(".finished").exists()
            assert first.read_bytes() == b"candidate-data\n"
            assert "Interrupted: 0" in text
        else:
            assert "Files not started due to stop: 1" in text and f"    {second.name}" in text
        assert second.read_bytes() == (b"candidate-data\n" if stop == "native-output" else b"payload")
        assert not list(transport_root.iterdir()), text
        if analysis_scan:
            _assert_owned_group_gone(process.pid)
        else:
            with pytest.raises(ProcessLookupError): os.kill(int(marker.read_text()), 0)
        if stop == "descendant-int":
            with pytest.raises(ProcessLookupError): os.kill(int(Path(str(marker) + ".descendant").read_text()), 0)
        if stop in ("int", "late-int") and category in ("edit", "mux"):
            assert marker.with_suffix(".finished").exists()
            assert "Done: 1; Failed: 0" in text and "Interrupted: 0" in text
            assert text.count("finishing the current file") == 1
            assert _observed_fake_identification(env, first) == (edited if category == "edit" else _integration_output(original, [1, 0, 2, 3]))
        elif category == "analysis" and stop not in ("complete", "dumb-complete"):
            assert not marker.with_suffix(".finished").exists()
            assert "Files analyzed: 0; Matching: 0; Mismatched: 0; Failed: 1; Not attempted: 1" in text
        elif stop == "native-output":
            assert marker.with_suffix(".finished").exists()
        elif category != "analysis":
            assert not marker.with_suffix(".finished").exists()
            assert "Interrupted: 1" in text
        if category == "extract":
            assert (first.parent / "Attachments" / "Font.ttf").read_bytes() == b"font"
            if stop == "unconfirmed-int":
                assert "Cleanup failed: Owned native process group shutdown could not be confirmed" in text
                retained = list(first.parent.glob(".mkvutil-extract-*/tracks-*"))
                assert len(retained) == 1 and retained[0].read_bytes() == b"unfinished track"
                assert "Discarded unfinished track:" not in text
            else:
                assert "Discarded unfinished track:" in text
                assert not list(first.parent.glob(".mkvutil-extract-*/tracks-*"))
            assert not list(first.parent.glob("*.ass"))
        if category == "attachments":
            assert list(first.parent.glob("Attachments/.mkvutil-extract-*/attachments-*"))
        calls = _command_argv(env, tool)
        modifying = [args for args in calls if "-o" in args] if tool == "mkvmerge" else [args for args in calls if len(args) > 1 and args[1] != "tags"]
        expected_modifying = 2 if stop == "native-output" else {"analysis": 0, "extract": 2}.get(category, 1)
        assert len(modifying) == expected_modifying
    finally:
        (env["workdir"].parent / "runtime-stop-transcript.bin").write_bytes(output)
        if stop == "native-output":
            native_display_release.write_text("release", encoding="utf-8")
        if category == "analysis" and stop in ("complete", "dumb-complete"):
            analysis_release.write_text("release", encoding="utf-8")
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
        os.close(master); os.close(terminal)


def test_mkv_utils_working_indicator_during_delayed_inspection(env):
    import fcntl
    import pty
    import select
    import termios
    import time

    source = _mkv_file(env, "Held inspection.mkv")
    manifest = env["workdir"].parent / "held-inspection.json"
    original = _integration_model()
    edited = json.loads(json.dumps(original))
    edited['container']['properties']['title'] = 'Held inspection title'
    manifest.write_text(json.dumps({"sources": {str(source): original}, "post_edit": {str(source): edited}}))
    marker, release = env["fake_state"] / "inspection-held", env["fake_state"] / "inspection-release"
    executable = env["fake_bin"] / "mkvmerge"
    body = executable.read_text()
    anchor = 'if [ "$call_mode" = "json" ]; then\n'
    assert body.count(anchor) == 1
    replacement = (
        'if [ "$call_mode" = "json" ] && [ "$source_file" = "$TEST_INSPECTION_HOLD_PATH" ]; then\n'
        '  printf \'%s\\n\' "$$" > "$TEST_INSPECTION_MARKER"\n'
        '  while [ ! -e "$TEST_INSPECTION_RELEASE" ]; do /bin/sleep 0.02; done\n'
        'fi\n' + anchor
    )
    executable.write_text(body.replace(anchor, replacement, 1))
    _set_fake_fzf_responses(env, [[str(source)]])
    run_env = os.environ.copy()
    run_env.update({
        "TERM": "xterm-256color", "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq", "TEST_REAL_PYTHON": sys.executable,
        "TEST_USE_REAL_JSON": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]), "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]), "TEST_FAKE_FZF_SELECTIONS": str(env["fake_fzf_selections"]),
        "TEST_INSPECTION_HOLD_PATH": str(source), "TEST_INSPECTION_MARKER": str(marker),
        "TEST_INSPECTION_RELEASE": str(release), "TEST_FAKE_EXECUTION_JSON": str(manifest),
    })
    master, terminal = pty.openpty()

    def own_terminal():
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.tcsetpgrp(0, os.getpgrp())

    process = subprocess.Popen(["/usr/local/bin/zsh", "-f", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, stdin=terminal, stdout=terminal, stderr=terminal,
        start_new_session=True, preexec_fn=own_terminal)
    output = bytearray()
    deadline = time.monotonic() + 12

    def receive(timeout=0.05):
        if select.select([master], [], [], timeout)[0]:
            try:
                data = os.read(master, 65536)
            except OSError:
                return False
            output.extend(data)
            return bool(data)
        return True

    def answer(prompt, value):
        while prompt not in output and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert prompt in output, output.decode(errors="replace")
        os.write(master, value)

    try:
        answer(b"Category: ", b"1\n")
        answer(b"Actions: ", b"5\n")
        while not marker.exists() and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert marker.exists(), output.decode(errors="replace")
        while len(set(_indicator_frames(output.decode(errors="replace"), "Working"))) < 2 and time.monotonic() < deadline:
            receive()
        text = output.decode(errors="replace")
        assert len(set(_indicator_frames(text, "Working"))) >= 2, text
        # Working is a status display: the input cursor stays hidden until
        # inspection finishes and the next interactive prompt becomes ready.
        working_start = text.index("Working")
        assert text.rfind("\x1b[?25l", 0, working_start) > text.rfind("\x1b[?25h", 0, working_start)
        assert "\x1b[?25h" not in text[working_start:]
        assert "Track configuration" not in text and "Title [clear]:" not in text
        release.write_text("release", encoding="utf-8")
        answer(b"Title [clear]: ", b"Held inspection title\n")
        while process.poll() is None and time.monotonic() < deadline:
            receive()
        assert process.poll() == 0, output.decode(errors="replace")
        text = output.decode(errors="replace")
        clear_index = text.rfind("\r\x1b[2K", 0, text.index("Track configuration"))
        assert 0 <= text.index("Working") < clear_index < text.index("Track configuration")
        assert "\x1b[?25h" in text[clear_index:text.index("Track configuration")]
        processing_start = text.index("Processing: Held inspection.mkv")
        assert text.rfind("\x1b[?25h", 0, processing_start) > text.rfind("\x1b[?25l", 0, processing_start)
        assert text.rfind("\x1b[?25h") > text.rfind("\x1b[?25l")
        assert "Processing: Held inspection.mkv" in text
        assert "Final report" in text and "Held inspection.mkv" in text
        assert not _indicator_frames(text[text.index("Track configuration"):text.index("Title [clear]:")], "Working")
        assert source.read_bytes() == b"edited-data\n"
        assert len(_command_argv(env, "mkvpropedit")) == 1
        assert all(call[1] == "tags" for call in _command_argv(env, "mkvextract"))
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)
        with pytest.raises(ProcessLookupError):
            os.killpg(process.pid, 0)
    finally:
        (env["workdir"].parent / "working-transcript.bin").write_bytes(output)
        if process.poll() is None:
            release.write_text("release", encoding="utf-8")
            import signal
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)
        os.close(master)
        os.close(terminal)


def test_mkv_utils_analysis_indicator_reaps_child_after_second_signal(env):
    import fcntl
    import pty
    import select
    import signal
    import termios
    import time

    stopping = env["fake_state"] / "indicator-child-stopping"
    release = env["fake_state"] / "indicator-child-release"
    pid_file = env["fake_state"] / "indicator-child-pid"
    interrupted = env["fake_state"] / "indicator-second-signal"
    script = env["workdir"].parent / "indicator-cleanup.zsh"
    script.write_text(r'''
source "$MKVUTIL_TEST_SOURCE"
MKVUTIL_INTERRUPTED=0
(
  trap '' INT
  trap 'trap "" TERM; printf "%s\n" "$$" > "$TEST_INDICATOR_STOPPING"; while [[ ! -e "$TEST_INDICATOR_RELEASE" ]]; do /bin/sleep 0.02; done; exit 73' TERM
  while true; do /bin/sleep 1; done
) &
MKVUTIL_INDICATOR_PID=$!
printf "%s\n" "$MKVUTIL_INDICATOR_PID" > "$TEST_INDICATOR_PID_FILE"
printf '\r  ⠋ Working'
trap 'MKVUTIL_INTERRUPTED=1; print -r -- "SECOND_SIGNAL_RECEIVED"; : > "$TEST_INDICATOR_INTERRUPTED"' INT
print -r -- "STOPPING_INDICATOR"
_mkvutil_indicator_stop
print -r -- "STOP_RETURNED:$MKVUTIL_INTERRUPTED:$MKVUTIL_INDICATOR_PID"
''', encoding="utf-8")
    run_env = os.environ.copy()
    run_env.update({
        "TERM": "xterm-256color",
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "MKVUTIL_TEST_SOURCE": str(env["mkv_utils_script"]),
        "TEST_INDICATOR_STOPPING": str(stopping),
        "TEST_INDICATOR_RELEASE": str(release),
        "TEST_INDICATOR_PID_FILE": str(pid_file),
        "TEST_INDICATOR_INTERRUPTED": str(interrupted),
    })
    master, terminal = pty.openpty()

    def own_terminal():
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.tcsetpgrp(0, os.getpgrp())

    process = subprocess.Popen(["/usr/local/bin/zsh", "-f", str(script)],
        cwd=env["workdir"], env=run_env, stdin=terminal, stdout=terminal, stderr=terminal,
        start_new_session=True, preexec_fn=own_terminal)
    output = bytearray()
    deadline = time.monotonic() + 10

    def receive():
        if select.select([master], [], [], 0.05)[0]:
            try:
                data = os.read(master, 65536)
            except OSError:
                return False
            output.extend(data)
            return bool(data)
        return True

    try:
        while not stopping.exists() and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert stopping.exists(), output.decode(errors="replace")
        assert pid_file.exists()
        child_pid = int(pid_file.read_text())
        assert not interrupted.exists()
        os.kill(child_pid, 0)
        os.write(master, b"\x03")
        while not interrupted.exists() and time.monotonic() < deadline:
            receive()
            assert process.poll() is None, output.decode(errors="replace")
        assert interrupted.exists(), output.decode(errors="replace")
        assert "STOP_RETURNED" not in output.decode(errors="replace")
        os.kill(child_pid, 0)
        release.write_text("release", encoding="utf-8")
        while process.poll() is None and time.monotonic() < deadline:
            receive()
        assert process.poll() is not None, output.decode(errors="replace")
        while select.select([master], [], [], 0)[0] and time.monotonic() < deadline:
            if not receive():
                break
        text = output.decode(errors="replace")
        assert process.returncode == 0, text
        assert "\r  ⠋ Working" in text
        assert "STOP_RETURNED:1:" in text
        assert text.index("\r\x1b[2K") < text.index("STOP_RETURNED:")
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        with pytest.raises(ProcessLookupError):
            os.killpg(process.pid, 0)
    finally:
        release.write_text("release", encoding="utf-8")
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            process.wait(timeout=3)
        os.close(master)
        os.close(terminal)


def test_mkv_utils_working_indicator_stops_at_queue_and_analysis_remains(env):
    import fcntl
    import pty
    import select
    import termios
    import time

    script = r'''
source "$MKVUTIL_TEST_SOURCE"
MKVUTIL_INTERRUPTED=0
_mkvutil_indicator_start Working
/bin/sleep 0.2
_mkvutil_indicator_stop
print -r -- PRE_QUEUE_DONE
MKVUTIL_HAS_RUN=1
_mkvutil_indicator_start Working
/bin/sleep 0.2
_mkvutil_indicator_stop
print -r -- QUEUE_DONE
_mkvutil_indicator_start Analysing
/bin/sleep 0.2
_mkvutil_indicator_stop
print -r -- ANALYSIS_DONE
'''
    run_env = os.environ.copy()
    run_env.update({"TERM": "xterm-256color", "MKVUTIL_TEST_SOURCE": str(env["mkv_utils_script"])})
    master, terminal = pty.openpty()

    def own_terminal():
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.tcsetpgrp(0, os.getpgrp())

    process = subprocess.Popen(["/usr/local/bin/zsh", "-f", "-c", script],
        cwd=env["workdir"], env=run_env, stdin=terminal, stdout=terminal, stderr=terminal,
        start_new_session=True, preexec_fn=own_terminal)
    output = bytearray()
    deadline = time.monotonic() + 10
    try:
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
        assert process.poll() == 0, output.decode(errors="replace")
        while select.select([master], [], [], 0)[0]:
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            output.extend(data)
        text = output.decode(errors="replace")
        pre = text.index("PRE_QUEUE_DONE")
        queue = text.index("QUEUE_DONE", pre)
        analysis = text.index("ANALYSIS_DONE", queue)
        assert "Working" in text[:pre]
        assert "Working" not in text[pre:queue]
        assert "Analysing" in text[queue:analysis]
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        os.close(master)
        os.close(terminal)
