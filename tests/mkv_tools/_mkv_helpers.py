from __future__ import annotations

import os
import signal
import shutil
import subprocess
from pathlib import Path

SCRIPT_MKV_MUX_SOURCE = (
    Path(__file__).resolve().parents[2] / "shell" / "mkv_mux.zsh"
)
SCRIPT_MKV_UTILS_SOURCE = (
    Path(__file__).resolve().parents[2] / "shell" / "mkv_utils.zsh"
)
FAKE_TOOLS_BY_SCRIPT = {
    "mux": ("ffmpeg", "ffprobe", "mkvmerge", "mkvextract", "fzf", "jq", "rsync"),
    "utils": ("mkvmerge", "mkvextract", "mkvpropedit", "fzf", "jq", "python3"),
}


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def _prepare_fake_commands(fake_bin: Path) -> None:
    _write_executable(
        fake_bin / "ffmpeg",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/ffmpeg.$$"
state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
call_file="${state_dir}/fake_ffmpeg_calls"

call=1
if [ -f "$call_file" ]; then
  previous="$(cat "$call_file" 2>/dev/null || echo 0)"
  call=$((previous + 1))
fi
printf '%s\n' "$call" > "$call_file"

if [ -n "$log_file" ]; then
  printf 'ffmpeg\\targs=%s\\n' "$*" >> "$log_file"
fi

fail_call="${TEST_FAKE_FFMPEG_FAIL_CALL:-}"
if [ -n "$fail_call" ] && [ "$call" -eq "$fail_call" ]; then
  exit 1
fi

output=""
for arg in "$@"; do
  case "$arg" in
    -*)
      ;;
    *)
      output="$arg"
      ;;
  esac
done

if [ -n "$output" ]; then
  mkdir -p "$(dirname "$output")"
  : > "$output"
fi
""",
    )

    _write_executable(
        fake_bin / "ffprobe",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/ffprobe.$$"
if [ -n "$log_file" ]; then
  printf 'ffprobe\\targs=%s\\n' "$*" >> "$log_file"
fi

source_file=""
for arg in "$@"; do
  case "$arg" in
    -*)
      ;;
    *)
      source_file="$arg"
      ;;
  esac
done
if [ -n "$source_file" ]; then
  printf '%s\\n' "$source_file" > "${TEST_FAKE_STATE_DIR:-/tmp}/fake_ffprobe_last_file"
fi
base="$(basename "$source_file")"

if printf '%s' "$*" | grep -Eq -- '-show_entries stream=codec_type'; then
  case "$base" in
    *nonvideo*|*notvideo*|*not_video*|*.txt)
      printf 'subtitle\\n'
      ;;
    *)
      printf 'video\\n'
      ;;
  esac
  exit 0
fi

if printf '%s' "$*" | grep -Eq -- '-show_entries stream=index'; then
  case "$base" in
    *option1_reencode*|*option1_replace*|*option1_replace_fail*|*option1_replace_limited*)
      printf '0\\n1\\n'
      ;;
    *)
      printf '0\\n'
      ;;
  esac
  exit 0
fi

if printf '%s' "$*" | grep -Eq -- '-of json'; then
  case "$base" in
    option1_reencode*|option1_replace*|option1_replace_fail*|option1_replace_limited*)
      cat <<'JSON'
{"streams":[
  {"index":0,"codec_type":"audio","tags":{"language":"eng","title":"Narration"},"disposition":{}},
  {"index":1,"codec_type":"audio","tags":{"language":"jpn","title":"Commentary"},"disposition":{}}
]}
JSON
      ;;
    *)
      cat <<'JSON'
{"streams":[
  {"index":0,"codec_type":"audio","tags":{"language":"eng","title":"Narration"},"disposition":{"default":1}},
  {"index":1,"codec_type":"audio","tags":{"language":"spa","title":"Music"},"disposition":{}}
]}
JSON
      ;;
  esac
  exit 0
fi

""",
    )

    _write_executable(
        fake_bin / "mkvmerge",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/mkvmerge.$$"
if [ -n "$log_file" ]; then
  printf 'mkvmerge\\targs=%s\\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
call_mode="remux"
source_file=""

if [ "$1" = "--identify" ]; then
  call_mode="identify"
  source_file="$2"
elif [ "$1" = "-J" ]; then
  call_mode="json"
  source_file="$2"
else
  for arg in "$@"; do
    case "$arg" in
      -*)
        ;;
      *)
        source_file="$arg"
        ;;
    esac
  done
fi

if [ -n "$source_file" ]; then
  printf '%s\\n' "$source_file" > "${state_dir}/fake_mkvmerge_last_file"
fi

call_file="${state_dir}/fake_mkvmerge_${call_mode}_calls"
call=1
if [ -f "$call_file" ]; then
  previous="$(cat "$call_file" 2>/dev/null || echo 0)"
  call=$((previous + 1))
fi
printf '%s\\n' "$call" > "$call_file"

if [ "$call_mode" = "json" ] && [ -n "${TEST_FAKE_MKVMERGE_JSON_FAIL_CALL:-}" ] && [ "$call" -eq "${TEST_FAKE_MKVMERGE_JSON_FAIL_CALL}" ]; then
  exit 1
fi
if [ "$call_mode" = "remux" ] && [ -n "${TEST_FAKE_MKVMERGE_FAIL_CALL:-}" ] && [ "$call" -eq "${TEST_FAKE_MKVMERGE_FAIL_CALL}" ]; then
  exit 1
fi

if [ "$call_mode" = "identify" ]; then
  base="$(basename "$source_file")"
  count=0
  case "$base" in
    *attachments2*)
      count=2
      ;;
    *attachments1*)
      count=1
      ;;
  esac
  i=1
  while [ "$i" -le "$count" ]; do
    printf 'Attachment ID %s\\n' "$i"
    i=$((i + 1))
  done
  exit 0
fi

if [ "$call_mode" = "json" ]; then
  base="$(basename "$source_file")"

  case "$base" in
    *option7_alt*)
      cat <<'JSON'
{"tracks":[
  {"id":0,"type":"video","properties":{"id":0,"codec_id":"V_MPEG4/ISO/AVC","track_name":"","language":"eng"}},
  {"id":11,"type":"audio","properties":{"id":11,"codec_id":"A_AAC","track_name":"Narration","language":"eng"}},
  {"id":12,"type":"subtitles","properties":{"id":12,"codec_id":"S_TEXT/ASS","track_name":"Subs","language":"eng"}}
]}
JSON
      ;;
    *novideo*)
      cat <<'JSON'
{"tracks":[
  {"id":0,"type":"audio","properties":{"id":0,"codec_id":"A_AC3","track_name":"Dolby","language":"eng"}},
  {"id":1,"type":"subtitles","properties":{"id":1,"codec_id":"S_TEXT/ASS","track_name":"Subs","language":"eng"}}
]}
JSON
      ;;
    *extract_unknown*)
      cat <<'JSON'
{"tracks":[
  {"id":0,"type":"audio","properties":{"id":0,"codec_id":"A_TRUEHD","track_name":"Atmos","language":"eng"}}
]}
JSON
      ;;
    *extract_codec*)
      cat <<'JSON'
{"tracks":[
  {"id":0,"type":"video","properties":{"id":0,"codec_id":"V_MPEG4/ISO/AVC","track_name":"","language":"eng"}},
  {"id":1,"type":"audio","properties":{"id":1,"codec_id":"A_OPUS","track_name":"Opus","language":"eng"}},
  {"id":2,"type":"subtitles","properties":{"id":2,"codec_id":"S_TEXT/ASS","track_name":"","language":"eng"}}
]}
JSON
      ;;
    *boost_single*|*boost_fail*)
      cat <<'JSON'
{"tracks":[
  {"id":0,"type":"video","properties":{"id":0,"codec_id":"V_MPEG4/ISO/AVC","track_name":"","language":"eng"}},
  {"id":1,"type":"audio","properties":{"id":1,"codec_id":"A_AAC","track_name":"Primary","language":"eng"}}
]}
JSON
      ;;
    *)
      cat <<'JSON'
{"tracks":[
  {"id":0,"type":"video","properties":{"id":0,"codec_id":"V_MPEG4/ISO/AVC","track_name":"","language":"eng"}},
  {"id":1,"type":"audio","properties":{"id":1,"codec_id":"A_AAC","track_name":"Narration","language":"eng"}},
  {"id":2,"type":"audio","properties":{"id":2,"codec_id":"A_OPUS","track_name":"Music","language":"jpn"}},
  {"id":3,"type":"subtitles","properties":{"id":3,"codec_id":"S_TEXT/ASS","track_name":"Subs","language":"eng"}}
]}
JSON
      ;;
  esac
  exit 0
fi

output=""
next_is_output=0
for arg in "$@"; do
  if [ "$next_is_output" -eq 1 ]; then
    output="$arg"
    next_is_output=0
    continue
  fi
  case "$arg" in
    -o)
      next_is_output=1
      ;;
    -o*)
      output="${arg#-o}"
      ;;
  esac
done

if [ -n "$output" ]; then
  mkdir -p "$(dirname "$output")"
  : > "$output"
fi
""",
    )

    _write_executable(
        fake_bin / "mkvextract",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/mkvextract.$$"
if [ -n "$log_file" ]; then
  printf 'mkvextract\\targs=%s\\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
call_file="${state_dir}/fake_mkvextract_calls"
call=1
if [ -f "$call_file" ]; then
  previous="$(cat "$call_file" 2>/dev/null || echo 0)"
  call=$((previous + 1))
fi
printf '%s\\n' "$call" > "$call_file"

if [ -n "${TEST_FAKE_MKVEXTRACT_FAIL_CALL:-}" ] && [ "$call" -eq "${TEST_FAKE_MKVEXTRACT_FAIL_CALL}" ]; then
  exit 1
fi

mode="$1"
if [ "$mode" = "tracks" ]; then
  shift
  shift
  for spec in "$@"; do
    case "$spec" in
      *:*)
        extracted="${spec#*:}"
        mkdir -p "$(dirname "$extracted")"
        : > "$extracted"
        ;;
    esac
  done
  exit 0
fi

if [ "$mode" = "attachments" ]; then
  shift
  shift
  for id in "$@"; do
    : > "attachment_${id}.bin"
  done
  exit 0
fi
""",
    )

    _write_executable(
        fake_bin / "mkvpropedit",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/mkvpropedit.$$"
if [ -n "$log_file" ]; then
  printf 'mkvpropedit\\targs=%s\\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
call_file="${state_dir}/fake_mkvpropedit_calls"
call=1
if [ -f "$call_file" ]; then
  previous="$(cat "$call_file" 2>/dev/null || echo 0)"
  call=$((previous + 1))
fi
printf '%s\\n' "$call" > "$call_file"

if [ -n "${TEST_FAKE_MKVPROPEDIT_FAIL_CALL:-}" ] && [ "$call" -eq "${TEST_FAKE_MKVPROPEDIT_FAIL_CALL}" ]; then
  exit 1
fi
""",
    )

    _write_executable(
        fake_bin / "fzf",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/fzf.$$"
if [ -n "$log_file" ]; then
  printf 'fzf\\targs=%s\\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
call_file="${state_dir}/fake_fzf_calls"
call=1
if [ -f "$call_file" ]; then
  previous="$(cat "$call_file" 2>/dev/null || echo 0)"
  call=$((previous + 1))
fi
printf '%s\\n' "$call" > "$call_file"

selection_file="${TEST_FAKE_FZF_SELECTIONS:-}"
selection=""
if [ -n "$selection_file" ] && [ -f "$selection_file" ]; then
  selection="$(awk "NR==${call} { print; exit }" "$selection_file")"
fi

if [ -z "$selection" ]; then
  exit 0
fi

OLD_IFS=$IFS
IFS='|'
for choice in $selection; do
  printf '%s\\n' "$choice"
done
IFS=$OLD_IFS
""",
    )

    _write_executable(
        fake_bin / "jq",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/jq.$$"
if [ -n "$log_file" ]; then
  printf 'jq\\targs=%s\\n' "$*" >> "$log_file"
fi

if [ "$1" = "-r" ]; then
  shift
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
ffprobe_last_file="${state_dir}/fake_ffprobe_last_file"
mkvmerge_last_file="${state_dir}/fake_mkvmerge_last_file"

query="$*"

call_file="${state_dir}/fake_jq_calls"
call=1
if [ -f "$call_file" ]; then
  previous="$(cat "$call_file" 2>/dev/null || echo 0)"
  call=$((previous + 1))
fi
printf '%s\\n' "$call" > "$call_file"

if [ -n "${TEST_FAKE_JQ_FAIL_CALL:-}" ] && [ "$call" -eq "${TEST_FAKE_JQ_FAIL_CALL}" ]; then
  exit 1
fi

query_file="${state_dir}/fake_jq_query.$$"
input_file="${state_dir}/fake_jq_input.$$"
cat > "$input_file"
if printf '%s' "$query" | grep -q '\\.streams\\[\\]'; then
  [ -f "$ffprobe_last_file" ] && source_file="$(cat "$ffprobe_last_file")"
else
  [ -f "$mkvmerge_last_file" ] && source_file="$(cat "$mkvmerge_last_file")"
fi
base="$(basename "$source_file")"

{ printf '%s' "$query"; } > "$query_file"
/usr/bin/python3 - "$base" "$query_file" "$input_file" <<'PY'
#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

base = sys.argv[1]
query = Path(sys.argv[2]).read_text()
raw_input = Path(sys.argv[3]).read_text()

def tracks_for(base: str):
    if "option7_alt" in base:
        return [
            (0, "video", "V_MPEG4/ISO/AVC", "", "eng"),
            (11, "audio", "A_AAC", "Narration", "eng"),
            (12, "subtitles", "S_TEXT/ASS", "Subs", "eng"),
        ]
    if "novideo" in base:
        return [
            (0, "audio", "A_AC3", "Dolby", "eng"),
            (1, "subtitles", "S_TEXT/ASS", "Subs", "eng"),
        ]
    if "extract_unknown" in base:
        return [(0, "audio", "A_TRUEHD", "Atmos", "eng")]
    if "extract_codec" in base:
        return [
            (0, "video", "V_MPEG4/ISO/AVC", "", "eng"),
            (1, "audio", "A_OPUS", "Opus", "eng"),
            (2, "subtitles", "S_TEXT/ASS", "", "eng"),
        ]
    if "boost_single" in base or "boost_fail" in base:
        return [
            (0, "video", "V_MPEG4/ISO/AVC", "", "eng"),
            (1, "audio", "A_AAC", "Primary", "eng"),
        ]
    return [
        (0, "video", "V_MPEG4/ISO/AVC", "", "eng"),
        (1, "audio", "A_AAC", "Narration", "eng"),
        (2, "audio", "A_OPUS", "Music", "jpn"),
        (3, "subtitles", "S_TEXT/ASS", "Subs", "eng"),
    ]


def streams_for(base: str):
    if (
        "option1_reencode" in base
        or "option1_replace" in base
        or "option1_replace_fail" in base
        or "option1_replace_limited" in base
    ):
        return [
            {"index": 0, "language": "eng", "title": "Narration", "disposition": "0"},
            {"index": 1, "language": "jpn", "title": "Commentary", "disposition": "0"},
        ]
    return [
        {"index": 0, "language": "eng", "title": "Narration", "disposition": "default"},
        {"index": 1, "language": "spa", "title": "Music", "disposition": "0"},
    ]


tracks = tracks_for(base)
streams = streams_for(base)
stdin_lines = [line for line in raw_input.splitlines() if line.strip()]

def emit(line: str):
    print(line)

if ".streams[]" in query:
    if "select(" in query and "select(.index" in query and ".index" in query:
        # used only by production fake; keep generic stream output
        pass
    for row in streams:
        print(json.dumps(row, separators=(",", ":")))
    sys.exit(0)

if ".tracks" in query and "@tsv" in query:
    row_mode = os.environ.get("TEST_FAKE_JQ_TRACK_ROW_MODE", "")
    if row_mode == "empty":
        sys.exit(0)
    if row_mode == "non-numeric":
        print("video\tbad")
        sys.exit(0)
    if row_mode == "duplicate":
        print("video\t0")
        print("audio\t0")
        sys.exit(0)
    if row_mode == "unsupported":
        print("buttons\t0")
        sys.exit(0)
    for idx, typ, codec, _name, _lang in tracks:
        print(f"{typ}\t{idx}")
    sys.exit(0)

if "select(.id==" in query:
    match = re.search(r"select\\(\\.id==([0-9]+)\\)", query)
    wanted = int(match.group(1)) if match else None
    for idx, _typ, codec, _name, _lang in tracks:
        if wanted is not None and idx == wanted:
            emit(codec)
            break
    sys.exit(0)

if 'select(.type=="audio")' in query and 'Track ID' in query:
    for idx, typ, codec, name, lang in tracks:
        if typ == "audio":
            label = f"Track ID {idx}: audio ({codec})"
            if name:
                label += f" [{name}]"
            if lang:
                label += f" [{lang}]"
            emit(label)
    sys.exit(0)

if 'Track ID' in query and '.tracks[]' in query:
    for idx, typ, codec, name, lang in tracks:
        label = f"Track ID {idx}: {typ} ({codec})"
        if name:
            label += f" [{name}]"
        if lang:
            label += f" [{lang}]"
        emit(label)
    sys.exit(0)

if 'select(.type=="audio")' in query and '.id' in query:
    for idx, typ, _codec, _name, _lang in tracks:
        if typ == "audio":
            emit(str(idx))
    sys.exit(0)

if 'select(.type=="video")' in query and '.id' in query:
    for idx, typ, _codec, _name, _lang in tracks:
        if typ == "video":
            emit(str(idx))
    sys.exit(0)

if 'select(.type=="subtitles")' in query and '.id' in query:
    for idx, typ, _codec, _name, _lang in tracks:
        if typ == "subtitles":
            emit(str(idx))
    sys.exit(0)

if '.language //' in query or '.language' == query.strip():
    for line in stdin_lines:
        data = json.loads(line)
        value = data.get("language")
        if value is None or value == "":
            value = "und"
        emit(value)
    sys.exit(0)

if '.title //' in query or '.title' in query:
    for line in stdin_lines:
        data = json.loads(line)
        emit(data.get("title", "") or "")
    sys.exit(0)

if '.disposition' in query:
    for line in stdin_lines:
        data = json.loads(line)
        emit(data.get("disposition", "0") or "0")
    sys.exit(0)

sys.exit(0)
PY
rm -f "$query_file" "$input_file"
""",
    )

    _write_executable(
        fake_bin / "rsync",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/rsync.$$"
if [ -n "$log_file" ]; then
  printf 'rsync\\targs=%s\\n' "$*" >> "$log_file"
fi

source=""
destination=""
for arg in "$@"; do
  case "$arg" in
    -*)
      ;;
    *)
      if [ -z "$source" ]; then
        source="$arg"
      else
        destination="$arg"
      fi
      ;;
  esac
done

if [ -n "$source" ] && [ -n "$destination" ]; then
  mkdir -p "$(dirname "$destination")"
  cp "$source" "$destination"
fi
""",
    )

    _write_executable(
        fake_bin / "python3",
        """#!/usr/bin/env sh
argv_dir="${TEST_ARGV_LOG_DIR:-}"
[ -z "$argv_dir" ] || printf '%s\\0' "$@" > "$argv_dir/python3.$$"
code=\"$(cat)\"

if [ \"${TEST_FAKE_PYTHON_FAIL:-0}\" = \"1\" ]; then
  exit 1
fi

if echo \"$code\" | grep -Fq 'from pymkv.TypeTrack import type_files'; then
  cat <<'PY'
typeset -A codec_ext=( ['A_TRUEHD']='thd' )
PY
  exit 0
fi

if echo \"$code\" | grep -Fq 'import pymkv'; then
  exit 0
fi
""",
    )


def create_mkv_tools_environment(tmp_path: Path) -> dict[str, Path]:
    workdir = tmp_path / "workdir"
    fake_bin = tmp_path / "fake_bin"
    command_log = tmp_path / "commands.log"
    argv_log_dir = tmp_path / "argv"
    fake_state = tmp_path / "fake_state"
    selection_file = tmp_path / "fake_fzf_selections.txt"

    for path in (workdir, fake_bin, fake_state, argv_log_dir):
        path.mkdir(parents=True, exist_ok=True)

    _prepare_fake_commands(fake_bin)

    mux_script = tmp_path / "mkv_mux.zsh"
    utils_script = tmp_path / "mkv_utils.zsh"
    mux_script.write_text(SCRIPT_MKV_MUX_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    utils_script.write_text(
        SCRIPT_MKV_UTILS_SOURCE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    mux_script.chmod(mux_script.stat().st_mode | 0o111)
    utils_script.chmod(utils_script.stat().st_mode | 0o111)

    selection_file.write_text("", encoding="utf-8")
    return {
        "workdir": workdir,
        "fake_bin": fake_bin,
        "command_log": command_log,
        "argv_log_dir": argv_log_dir,
        "fake_state": fake_state,
        "fake_fzf_selections": selection_file,
        "mkv_mux_script": mux_script,
        "mkv_utils_script": utils_script,
    }


def _set_fake_fzf_responses(
    env: dict[str, Path],
    responses: list[list[str]],
) -> None:
    env["fake_fzf_selections"].write_text(
        "\n".join("|".join(response) for response in responses),
        encoding="utf-8",
    )


def _clear_fake_state(env: dict[str, Path]) -> None:
    if env["fake_state"].exists():
        for path in env["fake_state"].iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    env["command_log"].write_text("", encoding="utf-8")
    for path in env["argv_log_dir"].iterdir():
        path.unlink()


def _read_command_log(env: dict[str, Path]) -> list[str]:
    if not env["command_log"].exists():
        return []
    data = env["command_log"].read_text(encoding="utf-8")
    return data.splitlines() if data else []


def _command_invocations(log: list[str], command: str) -> list[str]:
    prefix = f"{command}\targs="
    literal_prefix = f"{command}\\targs="
    return [
        entry.removeprefix(prefix) if entry.startswith(prefix) else entry.removeprefix(literal_prefix)
        for entry in log
        if entry.startswith(prefix) or entry.startswith(literal_prefix)
    ]


def _command_argv(env: dict[str, Path], command: str) -> list[list[str]]:
    calls: list[list[str]] = []
    if not env["argv_log_dir"].exists():
        return calls

    for path in sorted(env["argv_log_dir"].glob(f"{command}.*")):
        encoded_args = path.read_bytes().split(b"\0")
        if encoded_args and encoded_args[-1] == b"":
            encoded_args.pop()
        calls.append([arg.decode("utf-8") for arg in encoded_args])
    return calls


def _run_mkv_script(
    env: dict[str, Path],
    script_key: str,
    *args: str,
    input_data: str = "",
    extra_env: dict[str, str] | None = None,
    working_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    script_path = env[f"mkv_{script_key}_script"]
    cwd = working_dir or env["workdir"]

    _clear_fake_state(env)

    run_env = os.environ.copy()
    run_env["HOME"] = str(cwd)
    run_env["PATH"] = f"{env['fake_bin']}:/usr/bin:/bin:/usr/sbin:/sbin"
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"
    run_env["TEST_COMMAND_LOG"] = str(env["command_log"])
    run_env["TEST_ARGV_LOG_DIR"] = str(env["argv_log_dir"])
    run_env["TEST_FAKE_STATE_DIR"] = str(env["fake_state"])
    run_env["TEST_FAKE_FZF_SELECTIONS"] = str(env["fake_fzf_selections"])
    if extra_env:
        run_env.update(extra_env)

    for tool in FAKE_TOOLS_BY_SCRIPT[script_key]:
        expected = (env["fake_bin"] / tool).resolve()
        resolved = shutil.which(tool, path=run_env["PATH"])
        assert resolved is not None and Path(resolved).resolve() == expected, (
            f"{tool} is not resolved from the isolated test PATH: "
            f"expected={expected}, got={resolved}"
        )

    command = ["/usr/local/bin/zsh", "-f", str(script_path), *args]
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=run_env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input_data, timeout=20)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        raise AssertionError(
            f"{script_path.name} timed out after 20 seconds\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        ) from exc

    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def run_mkv_mux_script(
    env: dict[str, Path],
    *args: str,
    input_data: str = "",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run_mkv_script(
        env,
        "mux",
        *args,
        input_data=input_data,
        extra_env=extra_env,
    )


def run_mkv_utils_script(
    env: dict[str, Path],
    *args: str,
    input_data: str = "",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run_mkv_script(
        env,
        "utils",
        *args,
        input_data=input_data,
        extra_env=extra_env,
    )
