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
eq "${#MKVUTIL_JOBS}" 5 'prior auto skips reconsidered'
eq "${#MKVUTIL_REMOVAL_SKIPS}" 0 'skip receipts refreshed'
eq "${#MKVUTIL_SOURCES}" 5 'explicit exclusion persisted'
print -r -- 'removal eligibility contracts passed'
''', sources)
    assert result.stdout.rstrip().endswith("removal eligibility contracts passed")
    assert all(Path(filename).read_text() == "payload" for filename in sources)
    assert not list(env["workdir"].glob("*.mka"))


def test_mkv_utils_removal_mismatch_receipts_and_empty_builders(env):
    models = _removal_models()
    sources = {str(_mkv_file(env, f"{name}.mkv")): models[name] for name in ("reference", "codec", "kind", "missing")}
    result = _run_planning_contract(env, r'''
reference="$(mkvutil_capture_source "$PWD/reference.mkv")"
codec="$(mkvutil_capture_source "$PWD/codec.mkv")"
kind="$(mkvutil_capture_source "$PWD/kind.mkv")"
missing="$(mkvutil_capture_source "$PWD/missing.mkv")"
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
''', sources)
    receipts = [json.loads(line.removeprefix("RECEIPT ")) for line in result.stdout.splitlines() if line.startswith("RECEIPT ")]
    assert [receipt["source"] for receipt in receipts] == [str(env["workdir"] / f"{name}.mkv") for name in ("codec", "kind", "missing")]
    assert [reason["reason"] for reason in receipts[0]["reasons"]] == ["codec-mismatch"]
    assert receipts[0]["reasons"][0]["expected"] == {"type": "subtitles", "codec_id": "S_TEXT/ASS"}
    assert receipts[0]["reasons"][0]["actual"] == {"type": "subtitles", "codec_id": "S_TEXT/UTF8"}
    assert receipts[1]["reasons"][0]["reason"] == "type-mismatch"
    assert [reason["original_id"] for reason in receipts[2]["reasons"]] == ["1", "2"]
    assert all(reason["reason"] == "missing-id" and reason["actual"] is None for reason in receipts[2]["reasons"])
    assert all(Path(filename).read_text() == "payload" for filename in sources)
    assert not list(env["workdir"].glob("*.mka"))


def test_mkv_utils_removal_signature_unusable_values_and_config(env):
    _run_planning_contract(env, r'''
reference='{"model":{"tracks":[{"id":0,"type":"audio","properties":{"codec_id":"A_AAC"}},{"id":1,"type":"subtitles","properties":{"codec_id":"S_TEXT/ASS"}}]}}'
config="$(jq -cn --arg reference "$PWD/reference.mkv" '{category:"mux",operations:["1"],removed_ids:["1"],order:"",order_ids:[],metadata:"",settings:{},expected_types:{"1":"subtitles"},extract_ids:[],reference:$reference,removal_signatures:{"1":{type:"subtitles",codec_id:"S_TEXT/ASS"}}}')"
for invalid in 'null' '""' '17'; do
  unusable="$(jq --argjson invalid "$invalid" '.model.tracks[1].properties.codec_id=$invalid' <<< "$reference")"
  reject mkvutil_removal_signatures "$unusable" 1
  broken="$(jq --argjson invalid "$invalid" '.removal_signatures["1"].codec_id=$invalid' <<< "$config")"
  reject mkvutil_validate_config "$broken"
done
''', {})


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



def _executor_document():
    document = _source_json([(0, "video", "V_MPEG4/ISO/AVC", True), (11, "audio", "A_PCM/INT/LIT", False), (12, "audio", "A_PCM/INT/LIT", True)])
    for position, track in enumerate(document["tracks"]):
        track["properties"]["uid"] = 18446744073709551000 + position
        track["properties"]["track_name"] = f"Original {position}"
    document["tracks"][0]["properties"]["stereo_mode"] = 1
    return document


def _run_executor_contract(env, body, manifest, *, fault=""):
    manifest_path = env["fake_state"] / "execution.json"
    manifest_path.write_text(json.dumps(manifest))
    run_env = os.environ.copy()
    run_env.update({
        "PATH": f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin",
        "TEST_REAL_JQ": shutil.which("jq") or "/usr/local/bin/jq",
        "TEST_REAL_PYTHON": sys.executable, "TEST_USE_REAL_JSON": "1",
        "TEST_COMMAND_LOG": str(env["command_log"]), "TEST_ARGV_LOG_DIR": str(env["argv_log_dir"]),
        "TEST_FAKE_STATE_DIR": str(env["fake_state"]), "TEST_FAKE_EXECUTION_JSON": str(manifest_path),
        "PYTHONDONTWRITEBYTECODE": "1",
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
config="$(jq --arg reference "$PWD/source.mk3d" --argjson signatures "$(mkvutil_removal_signatures "$record" 0)" '.+{reference:$reference,removal_signatures:$signatures}' <<< "$config")"
job="$(mkvutil_plan_job "$record" "$config")"
''' + body, "executor-contract", str(env["mkv_utils_script"])],
        cwd=env["workdir"], env=run_env, text=True, capture_output=True, timeout=35,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


_EXECUTOR_FAULTS = r'''
import json, os, signal
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
            os.kill(os.getpid(), signal.SIGINT)
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
        os.kill(os.getpid(), signal.SIGINT)
    return result

def patched_unlink(path, *args, **kwargs):
    if Path(path).name == "source.mk3d" and fault == "unlink_fail":
        raise PermissionError("injected old-source cleanup failure")
    return unlink(path, *args, **kwargs)
os.replace, os.link, os.unlink = patched_replace, patched_link, patched_unlink
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
import json, os, signal
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
    assert f"Retained staging directory: {directory}" in result.stdout
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


def test_mkv_utils_reporting_cancel_eof_and_excluded_unresolved_retry(env):
    first, skipped = _mkv_file(env, "completed.mk3d"), _mkv_file(env, "Unresolved source.mkv")
    sources = {str(skipped): _source_json([(0, "audio", "A_AAC", True), (12, "subtitles", "S_TEXT/UTF8", False)])}
    result = _run_planning_contract(env, r'''
MKVUTIL_SOURCES=()
mkvutil_ledger_reset "$PWD" "$PWD/neutral.mkv"
mkvutil_batch_request edit 1,2
mkvutil_finish 2
print -r -- 'NEUTRAL-END'
# All skipped before Run offers no Run and cancellation stays unresolved.
mkvutil_ledger_reset "$PWD" "$PWD/Unresolved source.mkv"
mkvutil_batch_request mux 1
receipt="$(jq -cn --arg source "$PWD/Unresolved source.mkv" --arg reference "$PWD/completed.mk3d" '{kind:"removal-mismatch",source:$source,reference:$reference,reasons:[{original_id:"12",reason:"codec-mismatch",expected:{type:"subtitles",codec_id:"S_TEXT/ASS"},actual:{type:"subtitles",codec_id:"S_TEXT/UTF8"}}]}')"
mkvutil_ledger_skip "$receipt"
MKVUTIL_JOBS=()
MKVUTIL_REMOVAL_SKIPS=("$receipt")
menu="$(mkvutil_review_menu)"
[[ "$menu" != *'Run batch'* ]] || fail 'all skipped offered Run'
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
mkvutil_configure_category mux 2 <<< $'0:0\n3,4' || code=$?
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
mkvutil_controller mux 1,2 <<< 3 || code=$?
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



def test_mkv_utils_reporting_processing_exit_keeps_actual_outcome_and_pending(env):
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
  MKVUTIL_RESULT_JSON="$(jq -c '{source:.source,destination:.source,status:"success",phase:"complete",actual_state:"replaced_complete",reason:""}' <<< "$1")"
}
# The first post-tool clock read fails. The always block must archive the
# tool's actual outcome, finalize the untouched pending job and remain nonzero.
mkvutil_clock() {
  local count=0
  [[ ! -f "$PWD/clock.count" ]] || count="$(< "$PWD/clock.count")"
  count=$(( count + 1 ))
  print -r -- "$count" > "$PWD/clock.count"
  (( count != 3 )) || return 1
  print -r -- "$count"
}
reject mkvutil_execute_queue "$first" "$second"
eq "${#modifiers}" 1 'only first tool invoked'
eq "${#MKVUTIL_JOBS}" 0 'completed queue cleared on early exit'
reject mkvutil_finish 1
print -r -- "SUMMARY $(mkvutil_final_summary)"
''', {})
    summary = json.loads(next(line[8:] for line in result.stdout.splitlines() if line.startswith("SUMMARY ")))
    assert summary["counts"]["done"] == 1 and summary["counts"]["not_attempted"] == 1
    assert summary["batches"][0]["attempted"] == 1 and summary["batches"][0]["completed"] == 1
    first = next(record for record in summary["files"] if record["source"].endswith("first.mkv"))
    assert first["attempts"][0]["result"]["actual_state"] == "replaced_complete"
    assert "actual state=replaced_complete" in result.stdout

def test_mkv_utils_reporting_progress_and_extract_formatter_contract(env):
    result = _run_planning_contract(env, r'''
eq "$(mkvutil_format_progress edit 1,2 9 1 1 2 9)" '' 'all Edit progress silent'
print -r -- "MUX-BEGIN"
mkvutil_format_progress mux 1,2 2 2 1 3 8
print -r -- "MUX-END"
print -r -- "ZERO-BEGIN"
mkvutil_format_progress mux 2 0 0 0 0 0
print -r -- "ZERO-END"
for action in 1 2; do
  output="$(mkvutil_format_progress extract "$action" 5 1 1 2 5)"
  [[ "$output" == *'Processed In: 0h 0m 5s'* && "$output" == *'Estimated Time Remaining: 0h 0m 5s'* ]] || fail 'single Extract timing'
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
    zero = result.stdout.split("ZERO-BEGIN\n")[1].split("ZERO-END")[0]
    assert "Estimated Time Remaining: 0h 0m 0s" in zero and "Files Remaining: 0" in zero
    combined = result.stdout.split("COMBINED-BEGIN\n")[1].split("COMBINED-END")[0]
    assert "Processed In: 0h 0m 3s" in combined and "Estimated Time Remaining: 0h 0m 4s" in combined
    assert "Category:" not in mux and "Directory:" not in mux
    assert "Directory: Extract directory" in result.stdout and "Category: extract; Actions: 1,2" in result.stdout


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


def test_mkv_utils_reporting_mux_skip_fresh_subset_run_entrypoint(env):
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
        input_data="2\n1,2\n12\n0:11\n3,4\n11\nfr-CA\n11\n@literal $name\n3\n1\n1\n12\n5\n\n2\n3\n",
        extra_env={"TEST_FAKE_EXECUTION_JSON": str(manifest)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Skipped removal mismatch: {skipped}" in result.stdout
    assert f"Fresh skipped-subset reference: {skipped}" in result.stdout
    assert result.stdout.count("Final report") == 1 and "Directory: workdir" in result.stdout
    assert "Done: 2; Failed: 0" in result.stdout and "Skipped: 0; Excluded: 0; Not attempted: 0" in result.stdout
    assert "Skip history: resolved" in result.stdout
    assert "Category: mux; Actions: 1,2" in result.stdout and "Optional Mux metadata: 3,4" in result.stdout
    assert "Category: mux; Actions: 1" in result.stdout and "Optional Mux metadata: 5" in result.stdout
    assert "Files Done: 1" in result.stdout and "Cancelled; no media changes." not in result.stdout
    assert len(_command_argv(env, "fzf")) == 1
    merges = [argv for argv in _command_argv(env, "mkvmerge") if "-o" in argv]
    assert len(merges) == 2 and not _command_argv(env, "mkvpropedit")
    first_call = next(argv for argv in merges if argv[-1] == str(first))
    skipped_call = next(argv for argv in merges if argv[-1] == str(skipped))
    assert first_call[first_call.index("--track-order") + 1] == "0:11,0:0"
    assert "--language" in first_call and "11:fr-CA" in first_call and "11:@literal $name" in first_call
    assert "--language" not in skipped_call and "--track-name" not in skipped_call
    assert skipped_call[skipped_call.index("--title") + 1] == ""
    assert first.read_bytes() == skipped.read_bytes() == b"candidate-data\n"
    assert not list(env["workdir"].glob(".mkvutil-*"))

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


def test_mkv_utils_category_extract_run_grouped_entrypoint(env: dict[str, Path]):
    manifest=_extract_manifest(env)
    manifest_path=env["workdir"].parent/"execution.json"
    manifest_path.write_text(json.dumps(manifest))
    collection=env["workdir"]/"Attachments";collection.mkdir();(collection/"Font.ttf").write_bytes(b"old collection")
    source=env["workdir"]/"First source.mkv"
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n1,2\n0-3\n2\n3\n",
                          extra_env={"TEST_FAKE_EXECUTION_JSON":str(manifest_path)})
    assert result.returncode==0,result.stdout+result.stderr
    assert "Category: extract; Actions: 1,2" in result.stdout and "Directory: workdir" in result.stdout
    assert "Artifact vobsub_index (required)" in result.stdout and "Artifact wavpack_correction (optional)" in result.stdout
    assert result.stdout.count("Attachments: shared collection; overwrite regular same-name files in selected-source and embedded-list order; last successful publication wins.")==1
    assert "Done: 1; Failed: 0" in result.stdout and "Attachments processed: 3; published: 3; final unique published names: 2; superseded: 1" in result.stdout
    assert "Files Attempted: 1" in result.stdout and "Estimated Time Remaining:" in result.stdout
    assert len(_command_argv(env,"fzf"))==1
    assert [argv[:2] for argv in _command_argv(env,"mkvextract")]==[[str(source),"attachments"],[str(source),"tracks"]]
    assert all(argv[:1]==["-J"] for argv in _command_argv(env,"mkvmerge")) and not _command_argv(env,"mkvpropedit")
    assert (collection/"Font.ttf").read_bytes()==b"BBB" and source.read_bytes()==b"payload"
    assert (env["workdir"]/"First source - Track [0].sub").read_bytes()==b"data"
    assert (env["workdir"]/"First source - Track [0].idx").read_bytes()==b"index"
    assert (env["workdir"]/"First source - Track [1].wvc").read_bytes()==b"correction"
    assert not list(env["workdir"].glob(".mkvutil-extract-*")) and not list(collection.glob(".mkvutil-extract-*"))


def test_mkv_utils_category_edit_run_grouped_entrypoint(env: dict[str, Path]):
    source = _mkv_file(env, "Run title.mks")
    original = _executor_document()
    actual = json.loads(json.dumps(original))
    actual["container"]["properties"]["title"] = ""
    manifest = env["workdir"].parent / "execution.json"
    manifest.write_text(json.dumps({"sources": {str(source): original}, "post_edit": {str(source): actual}}))
    result = _run_mkv_utils(
        env, fzf_responses=[[str(source)]], input_data="1\n5\n\n3\n",
        extra_env={"TEST_FAKE_EXECUTION_JSON": str(manifest)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "success:" in result.stdout and "edited_observed" in result.stdout
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
    result = _run_mkv_utils(env)
    assert result.returncode == 1
    assert "Please check if there are Matroska files" in result.stdout


def test_mkv_utils_query_failure_adapter_targets_readonly_query(env):
    result=_run_planning_contract(env,r'''
reject jq -r '.tracks as $tracks | if ($tracks|length)==0 then error("empty tracks array") else $tracks end' <<< '{"tracks":[{"id":0}]}'
eq "$(jq -r '.tracks|length' <<< '{"tracks":[{"id":0}]}')" 1 'unrelated JSON remains delegated'
''',{},extra_env={"TEST_FAKE_JQ_FAIL_QUERY_CONTAINS":"empty tracks array"})
    assert "Injected read-only jq query failure: empty tracks array" in result.stderr


# These names preserve the old single-action regression identities. Navigation
# now uses category -> shared configuration -> review -> explicit Run.
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
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data=f"1\n{choice}\n"+prompts+"3\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    assert len(_command_argv(env,"fzf"))==1 and "--multi" in _command_argv(env,"fzf")[0]
    assert "Done: 1; Failed: 0" in result.stdout and "Processed In:" not in result.stdout
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
    result=_run_mkv_utils(env,fzf_responses=[[str(first),str(second)]],input_data="1\n1\n0\n0\n3\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Done: 1; Failed: 0; Warning: 1" in result.stdout and str(second) in result.stdout
    assert len(_command_argv(env,"mkvpropedit"))==2 and "Processed In:" not in result.stdout
    assert first.read_bytes()==b"edited-data\n" and second.read_bytes()==b"payload"
    assert _observed_fake_identification(env,first)["tracks"][0]["properties"]["forced_track"] is False


def test_mkv_utils_option6_extracts_all_attachments(env):
    source=_mkv_file(env,"with_attachments2.mkv")
    embedded=[{"id":1,"file_name":"original $font.ttf","size":3},{"id":2,"file_name":"note.txt","size":4}]
    model=_integration_model(attachments=embedded)
    extra=_integration_manifest(env,{source:model},extraction={str(source):{"attachments":{"outputs":{"1":{"data":"one"},"2":{"data":"note"}}}}})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n1\n3\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=_command_argv(env,"mkvextract")
    assert len(calls)==1 and calls[0][:2]==[str(source),"attachments"]
    assert [spec.split(":",1)[0] for spec in calls[0][2:]]==["1","2"]
    assert (env["workdir"]/"Attachments"/embedded[0]["file_name"]).read_bytes()==b"one"
    assert (env["workdir"]/"Attachments"/"note.txt").read_bytes()==b"note"
    assert source.read_bytes()==b"payload" and "Attachments processed: 2; published: 2; final unique published names: 2" in result.stdout


def test_mkv_utils_option7_video_removal_converts_to_mka_and_keeps_other_tracks(env):
    source=_mkv_file(env,"remove_video.mkv");original=_integration_model();expected=_integration_output(original,[1,2,3])
    extra=_integration_manifest(env,{source:original},stage={str(source):expected})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n0\n\n3\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=[argv for argv in _command_argv(env,"mkvmerge") if "-o" in argv]
    assert len(calls)==1 and "--no-video" in calls[0]
    assert calls[0][calls[0].index("--audio-tracks")+1]=="1,2" and calls[0][calls[0].index("--subtitle-tracks")+1]=="3"
    output=source.with_suffix(".mka")
    assert not source.exists() and output.read_bytes()==b"candidate-data\n"
    assert _observed_fake_identification(env,output)==expected and not _command_argv(env,"mkvpropedit")


def test_mkv_utils_option7_failure_cleans_temporary_file(env):
    # The approved safety policy retains failed candidates; the old legacy
    # stem_temp output remains absent and the original is still preserved.
    source=_mkv_file(env,"remove_fail.mkv");original=_integration_model()
    extra=_integration_manifest(env,{source:original},stage={str(source):_integration_output(original,[1,2,3])},merge_code=2)
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n0\n\n3\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Failed: 1" in result.stdout and "Candidate:" in result.stdout
    assert source.read_bytes()==b"payload" and not source.with_suffix(".mka").exists()
    assert not (env["workdir"]/"remove_fail_temp.mka").exists()
    assert len([a for a in _command_argv(env,"mkvmerge") if "-o" in a])==1
    assert len(list(env["workdir"].glob(".mkvutil-*/candidate.mka")))==1


@pytest.mark.parametrize("extra_env",[
    {"TEST_FAKE_MKVMERGE_JSON_FAIL_CALL":"1"},
    {"TEST_FAKE_JQ_FAIL_QUERY_CONTAINS":"empty tracks array"},
    {"TEST_FAKE_JQ_FAIL_QUERY_CONTAINS":"codec: .properties.codec_id"},
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
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n99\n")
    assert result.returncode==1,result.stdout+result.stderr
    assert source.read_bytes()==b"payload" and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert "requested, not run" in result.stdout


def test_mkv_utils_option7_refuses_to_remove_every_track(env):
    source=_mkv_file(env,"remove_all.mkv")
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n1\n0-3\n")
    assert result.returncode==1,result.stdout+result.stderr
    assert source.read_bytes()==b"payload" and not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert "requested, not run" in result.stdout


def test_mkv_utils_option7_multi_file_uses_per_file_track_layout(env):
    first,second=_mkv_file(env,"option7_default.mkv"),_mkv_file(env,"option7_alt.mkv")
    a=_integration_model();b=_integration_model([(0,"video","V_MPEG4/ISO/AVC",True),(11,"audio","A_AAC",True),(12,"subtitles","S_TEXT/ASS",True)])
    extra=_integration_manifest(env,{first:a,second:b},stage={str(first):_integration_output(a,[1,2,3]),str(second):_integration_output(b,[11,12])})
    result=_run_mkv_utils(env,fzf_responses=[[str(first),str(second)]],input_data="2\n1\n0\n\n3\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=[argv for argv in _command_argv(env,"mkvmerge") if "-o" in argv]
    assert len(calls)==2 and all("--no-video" in c for c in calls)
    assert [(c[c.index("--audio-tracks")+1],c[c.index("--subtitle-tracks")+1]) for c in calls]==[("1,2","3"),("11","12")]
    assert not _command_argv(env,"mkvpropedit") and "Done: 2; Failed: 0" in result.stdout
    assert _observed_fake_identification(env,first.with_suffix(".mka"))["tracks"]==_integration_output(a,[1,2,3])["tracks"]
    assert _observed_fake_identification(env,second.with_suffix(".mka"))["tracks"]==_integration_output(b,[11,12])["tracks"]
    for internal in ("track_rows=","row=","track_type=","track_id=","track_rows_valid=","excluded_id=","requested_ids_valid="):
        assert internal not in result.stdout+result.stderr


def test_mkv_utils_option8_reorder_tracks_replaces_original(env):
    source=_mkv_file(env,"reorder.mkv");original=_integration_model();expected=_integration_output(original,[1,0,2,3])
    extra=_integration_manifest(env,{source:original},stage={str(source):expected})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n2\n0:1,0:0\n\n2\n3\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    calls=[a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    assert len(calls)==1 and calls[0][calls[0].index("--track-order")+1]=="0:1,0:0,0:2,0:3"
    actual=_observed_fake_identification(env,source)
    assert [t["properties"]["uid"] for t in actual["tracks"]]==[original["tracks"][i]["properties"]["uid"] for i in (1,0,2,3)]
    assert actual==expected and source.read_bytes()==b"candidate-data\n"
    assert "Original ID 1 => final position 1: audio" in result.stdout


def test_mkv_utils_option8_reorder_failure_cleans_temp_file(env):
    source=_mkv_file(env,"reorder_fail.mkv");original=_integration_model()
    extra=_integration_manifest(env,{source:original},stage={str(source):_integration_output(original,[1,0,2,3])},merge_code=1)
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="2\n2\n0:1\n\n3\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Warning: 1" in result.stdout and "Candidate:" in result.stdout
    assert source.read_bytes()==b"payload" and not (env["workdir"]/"reorder_fail_temp.mkv").exists()
    assert len(list(env["workdir"].glob(".mkvutil-*/candidate.mkv")))==1


def test_mkv_utils_option9_extract_track_extension_from_override(env):
    source=_mkv_file(env,"extract_codec.mkv");model=_integration_model([(0,"video","V_MPEG4/ISO/AVC",True),(1,"audio","A_OPUS",True),(2,"subtitles","S_TEXT/ASS",False)])
    extra=_integration_manifest(env,{source:model},extraction={str(source):{"tracks":{"outputs":{"1":{"data":"opus bytes"}}}}})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n2\n1\n3\n",extra_env=extra)
    assert result.returncode==0,result.stdout+result.stderr
    assert _command_argv(env,"mkvextract")[0][:2]==[str(source),"tracks"]
    assert (env["workdir"]/"extract_codec - Track [1].opus").read_bytes()==b"opus bytes" and source.read_bytes()==b"payload"


def test_mkv_utils_option9_extract_track_extension_from_python_map(env):
    source=_mkv_file(env,"extract_unknown.mkv");model=_integration_model([(0,"audio","A_TRUEHD",True)])
    extra=_integration_manifest(env,{source:model},extraction={str(source):{"tracks":{"outputs":{"0":{"data":"truehd bytes"}}}}})
    result=_run_mkv_utils(env,fzf_responses=[[str(source)]],input_data="3\n2\n0\n3\n",extra_env=extra)
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
        inputs="1\n1,2\n1,2\n\n\n1,2\n\n\n3\n"
    else:
        actual["tracks"][1]["properties"].update(track_name=literal,language="fre",language_ietf="fr-CA")
        removed=workflow=="remove-reorder-metadata"
        actual=_integration_output(actual,[2,1,3] if removed else [2,1,0,3])
        extra=_integration_manifest(env,{source:original},stage={str(source):actual})
        inputs=("2\n1,2\n0\n0:2\n" if removed else "2\n2\n0:2,0:1\n")+"4,3\n1\n"+literal+"\n1\nfr-CA\n3\n"
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
        assert calls[0][calls[0].index("--track-order")+1]==("0:2,0:1,0:3" if workflow=="remove-reorder-metadata" else "0:2,0:1,0:0,0:3")
        output=source.with_suffix(".mka") if workflow=="remove-reorder-metadata" else source
    assert _observed_fake_identification(env,output)==actual


@pytest.mark.parametrize("boundary",("removed-metadata","cancel","eof","fzf-injection"))
def test_mkv_utils_integration_reject_or_cancel_before_modification(env,boundary):
    source=_mkv_file(env,"Untouched.mkv")
    selected=source
    if boundary=="removed-metadata":inputs="2\n1\n0\n4\n0\n"
    elif boundary=="cancel":inputs="1\n4\n0\nName\n0\n"
    elif boundary=="eof":inputs="1\n4\n0\n"
    else:
        selected=env["workdir"].parent/"outside scanned domain.mkv";selected.write_bytes(b"outside")
        inputs="1\n5\n"
    result=_run_mkv_utils(env,fzf_responses=[[str(selected)]],input_data=inputs)
    assert result.returncode==(0 if boundary in ("cancel","eof") else 1),result.stdout+result.stderr
    assert source.read_bytes()==b"payload"
    assert not _command_argv(env,"mkvpropedit") and not _command_argv(env,"mkvextract")
    assert not [a for a in _command_argv(env,"mkvmerge") if "-o" in a]
    if boundary in ("cancel","eof"):assert "Cancelled; no media changes." in result.stdout


def test_mkv_utils_integration_native_child_signal_stops_menu_queue(env):
    first,second=_mkv_file(env,"Signal first.mkv"),_mkv_file(env,"Pending second.mkv")
    original=_integration_model();stage=_integration_output(original,[1,0,2,3])
    extra=_integration_manifest(env,{first:original,second:original},stage={str(first):stage,str(second):stage},merge_code=-15)
    result=_run_mkv_utils(env,fzf_responses=[[str(first),str(second)]],input_data="2\n2\n0:1\n\n3\n",extra_env=extra)
    assert result.returncode==1,result.stdout+result.stderr
    assert "Interrupted: 1" in result.stdout and "Not attempted: 1" in result.stdout
    assert first.read_bytes()==second.read_bytes()==b"payload"
    assert len([a for a in _command_argv(env,"mkvmerge") if "-o" in a])==1
    assert not _command_argv(env,"mkvpropedit") and len(_command_argv(env,"fzf"))==1
