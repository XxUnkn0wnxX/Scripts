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
expect_reject '' '0,1'
expect_reject '1,,2' '1,2'
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


def _run_metadata_contract(tmp_path: Path, body: str, input_data: str = ""):
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
        input=input_data,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


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
reject mkvutil_metadata_configure 4
MKVUTIL_METADATA_REGISTRY[4:merge]="$saved"
unset 'MKVUTIL_METADATA_REGISTRY[3:default]'
reject mkvutil_metadata_validate_registry
MKVUTIL_METADATA_REGISTRY[3:default]=''
MKVUTIL_METADATA_REGISTRY[1:default]=''
reject mkvutil_metadata_validate_registry
MKVUTIL_METADATA_REGISTRY[1:default]=0

# One new definition participates in both generic builders without dispatch.
_mkvutil_metadata_define 6 'Set commentary flag' track 'Commentary [0]: ' 0 boolean flag-commentary --commentary-flag ''
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
eq "$result" 2 'explicit cancellation returns'
reject mkvutil_metadata_configure 4 <<< '11,,12'
print -r -- 'configuration contracts passed'
''', "11\n\n11,12\n\n0\n11\nfr-CA\n11\n@name $cash: \"quote\" \\literal\n\n")
    assert result.stdout.strip() == "configuration contracts passed"


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


def _run_planning_contract(env: dict[str, Path], body: str, sources: dict, input_data=""):
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
_mkvutil_metadata_define 6 'Set commentary flag' track 'Commentary [0]: ' 0 boolean flag-commentary --commentary-flag ''
first="$(mkvutil_capture_source "$PWD/First file.mkv")"
second="$(mkvutil_capture_source "$PWD/Second file.mk3d")"
settings="$(_mkvutil_json_map '4:11' $'@name $cash: "quoted" \\literal\n\n' '3:11' fr-CA '5:info' '' '6:11' 0)"
config="$(jq -cn --argjson settings "$settings" '{category:"mux",operations:["1","2"],removed_ids:["0"],order:"0:12",order_ids:["12"],metadata:"3-6",settings:$settings,expected_types:{"0":"video","11":"audio","12":"subtitles"},extract_ids:[]}')"
config="$(jq --arg reference "$PWD/First file.mkv" --argjson signatures "$(mkvutil_removal_signatures "$first" 0)" '.+{reference:$reference,removal_signatures:$signatures}' <<< "$config")"
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
reject mkvutil_plan_job "$second" "$config"
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
reject mkvutil_plan_job "$record" "$bad"
bad="$(jq '.settings={"4:99":"name"}|.expected_types={"99":"audio"}' <<< "$config")"
reject mkvutil_plan_job "$record" "$bad"
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
config="$(jq --arg reference "$PWD/Show.mkv" --argjson signatures "$(mkvutil_removal_signatures "$a" 0)" '.+{reference:$reference,removal_signatures:$signatures}' <<< "$config")"
a="$(mkvutil_plan_job "$a" "$config")"
b="$(mkvutil_plan_job "$b" "$config")"
result=0
mkvutil_check_destinations "$a" "$b" || result=$?
print -r -- "$result"
''', {str(first): model, str(second): model})
    assert result.stdout.strip() == ("1" if insensitive else "0")


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
mkvutil_plan_queue <<< Y
eq "${#MKVUTIL_JOBS}" 1 'incompatible file explicitly excluded'
eq "${#MKVUTIL_SOURCES}" 1 'exclusion persists for reconfiguration'
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
    compatible["tracks"].append(_source_json([(99, "video", "V_MPEG4/ISO/AVC", True)])["tracks"][0])
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
config="$(jq -cn --arg reference "$PWD/reference.mkv" --argjson signatures "$signatures" '{category:"mux",operations:["1","2"],removed_ids:["1","2"],order:"0:0",order_ids:["0"],metadata:"4,5",settings:{"4:0":"@literal $name","5:info":""},expected_types:{"0":"audio","1":"subtitles","2":"audio"},extract_ids:[],reference:$reference,removal_signatures:$signatures}')"
# Missing IDs and exact type/codec differences are receipts, not ordinary errors.
for record in "$codec" "$kind" "$missing"; do
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
for invalid in 'null' '""' '17'; do
  unusable="$(jq --argjson invalid "$invalid" '.model.tracks[1].properties.codec_id=$invalid' <<< "$reference")"
  reject mkvutil_removal_signatures "$unusable" 1
  broken="$(jq --argjson invalid "$invalid" '.removal_signatures["1"].codec_id=$invalid' <<< "$config")"
  reject mkvutil_validate_config "$broken"
done
MKVUTIL_SOURCES=("$reference" "$compatible" "$codec" "$kind" "$missing" "$failed")
MKVUTIL_CONFIG="$config"
mkvutil_plan_queue <<< Y
eq "${#MKVUTIL_JOBS}" 2 'mixed eligible count'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 3 'mixed mismatch count'
eq "${#MKVUTIL_SOURCES}" 5 'auto skips retained; explicit failure excluded'
reject mkvutil_prepare_skipped_subset
# New removal IDs reconsider the entire current scope, including prior skips.
signatures="$(mkvutil_removal_signatures "$reference" 0)"
MKVUTIL_CONFIG="$(jq --argjson signatures "$signatures" '.removed_ids=["0"]|.order=""|.order_ids=[]|.metadata=""|.settings={}|.removal_signatures=$signatures' <<< "$config")"
mkvutil_plan_queue
eq "${#MKVUTIL_JOBS}" 5 'prior auto skips reconsidered'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 0 'skip receipts refreshed'
eq "${#MKVUTIL_SOURCES}" 5 'explicit exclusion persisted'
print -r -- 'removal eligibility contracts passed'
''', sources)
    receipts = [json.loads(line.removeprefix("RECEIPT ")) for line in result.stdout.splitlines() if line.startswith("RECEIPT ")]
    assert [receipt["source"] for receipt in receipts] == [str(env["workdir"] / f"{name}.mkv") for name in ("codec", "kind", "missing")]
    assert [reason["reason"] for reason in receipts[0]["reasons"]] == ["codec-mismatch"]
    assert receipts[0]["reasons"][0]["expected"] == {"type": "subtitles", "codec_id": "S_TEXT/ASS"}
    assert receipts[0]["reasons"][0]["actual"] == {"type": "subtitles", "codec_id": "S_TEXT/UTF8"}
    assert receipts[1]["reasons"][0]["reason"] == "type-mismatch"
    assert [reason["original_id"] for reason in receipts[2]["reasons"]] == ["1", "2"]
    assert all(reason["reason"] == "missing-id" and reason["actual"] is None for reason in receipts[2]["reasons"])
    assert result.stdout.rstrip().endswith("removal eligibility contracts passed")
    assert all(Path(filename).read_text() == "payload" for filename in sources)
    assert not list(env["workdir"].glob("*.mka"))


def test_mkv_utils_all_removal_skips_and_fresh_subset_preparation(env: dict[str, Path]):
    models = _removal_models()
    names = ("reference", "codec", "kind", "missing")
    sources = {str(_mkv_file(env, f"{name}.mkv")): models[name] for name in names}
    result = _run_planning_contract(env, r'''
reference="$(mkvutil_capture_source "$PWD/reference.mkv")"
codec="$(mkvutil_capture_source "$PWD/codec.mkv")"
kind="$(mkvutil_capture_source "$PWD/kind.mkv")"
missing="$(mkvutil_capture_source "$PWD/missing.mkv")"
MKVUTIL_CONFIG="$(jq -cn --arg reference "$PWD/reference.mkv" --argjson signatures "$(mkvutil_removal_signatures "$reference" '1,2')" '{category:"mux",operations:["1"],removed_ids:["1","2"],order:"",order_ids:[],metadata:"4",settings:{"4:0":"old name"},expected_types:{"0":"audio","1":"subtitles","2":"audio"},extract_ids:[],reference:$reference,removal_signatures:$signatures}')"
MKVUTIL_SOURCES=("$codec" "$kind" "$missing")
status_code=0
mkvutil_plan_queue || status_code=$?
eq "$status_code" 3 'all skipped status'
eq "${#MKVUTIL_JOBS}" 0 'all skipped has no jobs'
eq "${#MKVUTIL_SOURCES}" 3 'all skipped scope retained'
menu="$(mkvutil_review_menu)"
[[ "$menu" != *'Run batch'* && "$menu" == *'Prepare a fresh batch'* ]] || fail 'all skipped review actions'
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


def test_mkv_utils_removal_mismatch_report_cancel_entrypoint(env: dict[str, Path]):
    models = _removal_models()
    first, skipped = _mkv_file(env, "Reference source.mkv"), _mkv_file(env, "Skipped SRT.mkv")
    overrides = env["fake_bin"].parent / "menu-source-json.json"
    overrides.write_text(json.dumps({str(first): models["reference"], str(skipped): models["codec"]}))
    before = [file.read_bytes() for file in (first, skipped)]
    result = _run_mkv_utils(
        env, fzf_responses=[[str(first), str(skipped)]],
        input_data="2\n1,2\n1\n0:2\n4,5\n0\n@literal $name\n\n2\n0\n",
        extra_env={"TEST_FAKE_MKVMERGE_JSON_BY_PATH": str(overrides)},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"Removal reference file: {first}" in result.stdout
    assert f"Skipped removal mismatch: {skipped}" in result.stdout
    assert "Original ID 1: codec-mismatch" in result.stdout
    assert '"codec_id":"S_TEXT/ASS"' in result.stdout
    assert '"codec_id":"S_TEXT/UTF8"' in result.stdout
    assert "Enable multi-file" not in result.stdout + result.stderr
    assert "Cancelled; no media changes." in result.stdout
    calls = _command_argv(env, "fzf")
    assert len(calls) == 1 and "--multi" in calls[0]
    assert len(_command_argv(env, "mkvmerge")) == 2
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
    assert [file.read_bytes() for file in (first, skipped)] == before
    assert sorted(file.name for file in env["workdir"].iterdir()) == sorted([first.name, skipped.name])


def test_mkv_utils_category_preview_cancel_entrypoint(env: dict[str, Path]):
    first, second = _mkv_file(env, "preview-first.mkv"), _mkv_file(env, "preview-second.mk3d")
    before = [path.read_bytes() for path in (first, second)]
    result = _run_mkv_utils(
        env, fzf_responses=[[str(first), str(second)]],
        input_data="2\n1,2\n0\n0:2\n4,5\n1\n@Name $cash: \"quoted\"\n\n2\n0\n",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Original ID 2 => final position 1: audio" in result.stdout
    assert "Original ID 1 => final position 2: audio" in result.stdout
    assert "Original ID 0: removed" in result.stdout
    assert "preview-first.mka" in result.stdout and "preview-second.mka" in result.stdout
    assert "Cancelled; no media changes." in result.stdout
    assert len(_command_argv(env, "fzf")) == 1
    assert len(_command_argv(env, "mkvmerge")) == 2
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
    assert [path.read_bytes() for path in (first, second)] == before
    assert sorted(path.name for path in env["workdir"].iterdir()) == sorted([first.name, second.name])


def test_mkv_utils_category_edit_run_is_guarded(env: dict[str, Path]):
    source = _mkv_file(env, "guarded.mks")
    result = _run_mkv_utils(env, fzf_responses=[[str(source)]], input_data="1\n5\n\n3\n")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Execution is not available" in result.stderr
    assert len(_command_argv(env, "fzf")) == 1
    assert not _command_argv(env, "mkvpropedit") and not _command_argv(env, "mkvextract")
    assert all(call[:1] == ["-J"] for call in _command_argv(env, "mkvmerge"))
    assert source.read_text() == "payload"


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
    result = _run_mkv_utils(env)
    assert result.returncode == 1
    assert "Please check if there are Matroska files" in result.stdout


def test_mkv_utils_option1_forced_flag_uses_one_based_track_selector(env: dict[str, Path]):
    mkv = _mkv_file(env, "forced.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="1\n\n0\n\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"track:1" in calls[0]
    assert f"{mkv.name} --edit track:1 --set flag-forced=0" in calls[0]
    assert f"Edited File: {mkv.name}" in result.stdout


def test_mkv_utils_option2_default_flag_defaults_to_one(env: dict[str, Path]):
    mkv = _mkv_file(env, "default.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="2\n\n0\n\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --edit track:1 --set flag-default=1" in calls[0]


def test_mkv_utils_option3_language_updates_track_language(env: dict[str, Path]):
    mkv = _mkv_file(env, "language.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="3\n\n0\neng\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --edit track:1 --set language=eng" in calls[0]


def test_mkv_utils_option4_name_updates_track_name(env: dict[str, Path]):
    mkv = _mkv_file(env, "rename.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="4\n\n0\nDialogue\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --edit track:1 --set name=Dialogue" in calls[0]


def test_mkv_utils_option4_handles_spaces_in_file_and_track_name(env: dict[str, Path]):
    mkv = _mkv_file(env, "Episode One.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="4\n\n0\nEnglish Stereo\n",
    )

    calls = _command_argv(env, "mkvpropedit")
    assert result.returncode == 0
    assert len(calls) == 1
    assert mkv.name in calls[0]
    assert "name=English Stereo" in calls[0]
    assert "English" not in calls[0]
    assert "Stereo" not in calls[0]


def test_mkv_utils_option5_title_empty_input_deletes_title(env: dict[str, Path]):
    mkv = _mkv_file(env, "title.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="5\n\n\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --delete title" in calls[0]


def test_mkv_utils_option1_multi_file_partial_failure_summary(env: dict[str, Path]):
    target_a = _mkv_file(env, "multi_fail_a.mkv")
    target_b = _mkv_file(env, "multi_fail_b.mkv")

    result = _run_mkv_utils(
        env,
        fzf_responses=[[target_a.name, target_b.name]],
        input_data="1\nY\n0\n0\n0\n",
        extra_env={"TEST_FAKE_MKVPROPEDIT_FAIL_CALL": "2"},
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "Total Files To Edit: 2" in output
    assert "Total Files Edited: 1" in output
    assert "Failed Files: 01" in output
    assert "multi_fail_b.mkv" in output


def test_mkv_utils_option6_extracts_all_attachments(env: dict[str, Path]):
    mkv = _mkv_file(env, "with_attachments2.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="6\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvextract")
    assert result.returncode == 0
    assert f"attachments {mkv}" in calls[0]
    assert "1" in calls[0]
    assert "2" in calls[0]
    assert (env["workdir"] / "Attachments").exists()
    assert (env["workdir"] / "Attachments" / "attachment_1.bin").exists()
    assert (env["workdir"] / "Attachments" / "attachment_2.bin").exists()


def test_mkv_utils_option7_video_removal_converts_to_mka_and_keeps_other_tracks(
    env: dict[str, Path],
):
    mkv = _mkv_file(env, "remove_video.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    remux_calls = [call for call in calls if " -o " in f" {call} "]
    assert len(remux_calls) == 1
    assert "--no-video" in remux_calls[0]
    assert "--audio-tracks 1,2" in remux_calls[0]
    assert "--subtitle-tracks 3" in remux_calls[0]
    assert not mkv.exists()
    assert (env["workdir"] / "remove_video.mka").exists()


def test_mkv_utils_option7_failure_cleans_temporary_file(env: dict[str, Path]):
    mkv = _mkv_file(env, "remove_fail.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
        extra_env={"TEST_FAKE_MKVMERGE_FAIL_CALL": "1"},
    )

    assert result.returncode == 0
    assert "Error on" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert not (env["workdir"] / f"{mkv.stem}_temp.mka").exists()
    assert not (env["workdir"] / f"{mkv.stem}.mka").exists()
    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 1


@pytest.mark.parametrize(
    "extra_env",
    [
        {"TEST_FAKE_MKVMERGE_JSON_FAIL_CALL": "1"},
        {"TEST_FAKE_JQ_FAIL_CALL": "1"},
        {"TEST_FAKE_JQ_FAIL_CALL": "2"},
    ],
    ids=("mkvmerge-json", "jq-validation", "jq-display"),
)
def test_mkv_utils_option7_inspection_failure_skips_remux(
    env: dict[str, Path], extra_env: dict[str, str]
):
    mkv = _mkv_file(env, "remove_fail_inspect.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
        extra_env=extra_env,
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 1
    assert "track inspection failed; file unchanged" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


@pytest.mark.parametrize(
    "row_mode",
    ("empty", "non-numeric", "duplicate", "unsupported"),
)
def test_mkv_utils_option7_invalid_discovery_rows_skip_remux(
    env: dict[str, Path], row_mode: str
):
    mkv = _mkv_file(env, "remove_invalid_rows.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
        extra_env={"TEST_FAKE_JQ_TRACK_ROW_MODE": row_mode},
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode in (0, 1)
    assert "file unchanged" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


def test_mkv_utils_option7_nonexistent_track_id_skips_remux(env: dict[str, Path]):
    mkv = _mkv_file(env, "remove_missing_id.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n99\n",
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    assert "requested Track ID not found; file unchanged" in (
        result.stdout + result.stderr
    )
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


def test_mkv_utils_option7_refuses_to_remove_every_track(env: dict[str, Path]):
    mkv = _mkv_file(env, "remove_all.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0-3\n",
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    assert "no tracks to keep after removal; file unchanged" in (
        result.stdout + result.stderr
    )
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


def test_mkv_utils_option7_multi_file_uses_per_file_track_layout(env: dict[str, Path]):
    first = _mkv_file(env, "option7_default.mkv")
    second = _mkv_file(env, "option7_alt.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[first.name, second.name]],
        input_data="7\nY\n0\n",
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    calls = _command_invocations(_read_command_log(env), "mkvmerge")
    remux_calls = [call for call in calls if " -o " in f" {call} "]
    assert len(remux_calls) == 2

    first_call, second_call = remux_calls
    assert "--no-video" in first_call
    assert "--audio-tracks 1,2" in first_call
    assert "--subtitle-tracks 3" in first_call
    assert "--no-video" in second_call
    assert "--audio-tracks 11" in second_call
    assert "--subtitle-tracks 12" in second_call
    assert "--audio-tracks 1,2" not in second_call
    assert "track_rows=" not in output
    assert "row=" not in output
    assert "track_type=" not in output
    assert "track_id=" not in output
    assert "track_rows_valid=" not in output
    assert "excluded_id=" not in output
    assert "requested_ids_valid=" not in output


def test_mkv_utils_option8_reorder_tracks_replaces_original(env: dict[str, Path]):
    mkv = _mkv_file(env, "reorder.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="8\n\n0:1,1:0\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    remux_calls = [call for call in calls if " -o " in f" {call} "]
    assert len(remux_calls) == 1
    assert "--track-order 0:1,1:0" in remux_calls[0]
    assert (env["workdir"] / mkv.name).exists()


def test_mkv_utils_option8_reorder_failure_cleans_temp_file(env: dict[str, Path]):
    mkv = _mkv_file(env, "reorder_fail.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="8\n\n0:1\n",
        extra_env={"TEST_FAKE_MKVMERGE_FAIL_CALL": "1"},
    )

    assert result.returncode == 0
    assert "Error on" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert not (env["workdir"] / "reorder_fail_temp.mkv").exists()


def test_mkv_utils_option9_extract_track_extension_from_override(env: dict[str, Path]):
    mkv = _mkv_file(env, "extract_codec.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="9\n\n1\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvextract")
    assert result.returncode == 0
    assert 'extract_codec - Track [1].opus' in calls[0]


def test_mkv_utils_option9_extract_track_extension_from_python_map(env: dict[str, Path]):
    mkv = _mkv_file(env, "extract_unknown.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="9\n\n0\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvextract")
    assert result.returncode == 0
    assert 'extract_unknown - Track [0].thd' in calls[0]
