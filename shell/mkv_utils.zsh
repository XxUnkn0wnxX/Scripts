#!/usr/bin/env zsh

# Required third-party tools:
# - mkvmerge, mkvinfo, mkvextract, mkvpropedit: for remuxing, inspecting, extracting, and editing tracks and metadata in Matroska files
# - jq: for processing JSON output from mkvmerge (-J)
# - fzf: for interactive file and track selection via fuzzy finding
# - python3: for inline Python scripting support
# - pymkv2, pymkv Python library: provides the type_files mapping for codec→extension resolution (install via python3 -m pip install pymkv2 pymkv)
#
# On macOS, install dependencies via Homebrew:
#   brew install mkvtoolnix jq fzf python3
#   python3 -m pip install pymkv pymkv2
#
# Ensure that python3 and pip are in your PATH.

SCRIPT_NAME="${0:t}"
SCRIPT_ROOT=${0:A:h}
looks_like_repo_root() {
  local candidate="$1"
  [[ -d "$candidate/.git" ]] && return 0
  [[ -f "$candidate/requirements.txt" && -d "$candidate/docs" ]] && return 0
  return 1
}

resolve_repo_root() {
  local start_dir="$1"
  local max_depth="${2:-1}"
  local candidate="${start_dir:A}"
  local depth=0
  local fallback="$candidate"

  while (( depth <= max_depth )); do
    if (( depth == 1 )); then
      fallback="$candidate"
    fi
    if looks_like_repo_root "$candidate"; then
      print -r -- "$candidate"
      return 0
    fi
    [[ "$candidate" == / ]] && break
    candidate="${candidate:h}"
    (( depth++ ))
  done

  print -r -- "$fallback"
}

REPO_ROOT="$(resolve_repo_root "$SCRIPT_ROOT" 1)"
VENV_PATH="$REPO_ROOT/.venv"
PYTHON_BIN=""
typeset -gi _PY_READY=0

_verify_python_runtime() {
  local py_bin="$1"
  "$py_bin" - <<'PYCODE'
import sys
import importlib

try:
    import pymkv  # primary module used by the script
except ModuleNotFoundError as exc:
    sys.exit(f"pymkv unavailable: {exc}")

try:
    import importlib.metadata as metadata
except ImportError:  # pragma: no cover
    import importlib_metadata as metadata  # type: ignore

try:
    metadata.version("pymkv2")
except metadata.PackageNotFoundError as exc:
    sys.exit("pymkv2 distribution is not installed in this environment.")
PYCODE
}

ensure_venv_python() {
  if [[ $_PY_READY -eq 1 ]]; then
    return 0
  fi

  if [[ -d "$VENV_PATH" ]]; then
    local activate_file="$VENV_PATH/bin/activate"
    if [[ ! -f "$activate_file" ]]; then
      echo "Virtualenv detected at $VENV_PATH but activate script missing. Recreate the venv." >&2
      exit 1
    fi

    if [[ "$VIRTUAL_ENV" != "$VENV_PATH" ]]; then
      if ! source "$activate_file"; then
        echo "Failed to activate virtualenv at $VENV_PATH." >&2
        exit 1
      fi
    fi

    PYTHON_BIN="$VENV_PATH/bin/python3"
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Virtualenv python missing at $PYTHON_BIN." >&2
      exit 1
    fi

    if ! _verify_python_runtime "$PYTHON_BIN"; then
      echo "Required Python packages (pymkv, pymkv2) are not installed in the virtualenv." >&2
      echo "Activate the venv and run: pip install -r requirements.txt" >&2
      exit 1
    fi

    _PY_READY=1
    return 0
  fi

  local global_python
  if ! global_python=$(command -v python3 2>/dev/null); then
    echo "python3 is not available and no .venv exists. Create .venv (python3 -m venv .venv) and install requirements." >&2
    exit 1
  fi

  if ! _verify_python_runtime "$global_python"; then
    echo "Global python at $global_python lacks pymkv/pymkv2. Create .venv and run pip install -r requirements.txt." >&2
    exit 1
  fi

  PYTHON_BIN="$global_python"
  _PY_READY=1
}

# Extension overrides for Plex / VLC compatibility
typeset -A ext_override=(
  # Video elementary streams
  ["V_MPEG4/ISO/AVC"]="h264"     # raw H.264 → .h264
  ["V_MPEGH/ISO/HEVC"]="h265"    # raw HEVC/H.265 → .h265

  # Audio elementary streams
  ["A_AAC"]="aac"                # AAC audio → .aac
  ["A_AC3"]="ac3"                # AC-3 (Dolby Digital) → .ac3
  ["A_DTS"]="dts"                # DTS audio → .dts
  ["A_OPUS"]="opus"              # Opus → .opus
  ["A_MPEG/L3"]="mp3"            # MPEG-1/2 Layer III → .mp3

  # Subtitle sidecars
  ["S_TEXT/SRT"]="srt"           # SubRip → .srt
  ["S_TEXT/ASS"]="ass"           # SubStation Alpha → .ass
  ["S_HDMV/PGS"]="pgs"           # PGS subtitles → .pgs
)

# Multi-file target selection mode for menu choices (Y/N)
MULTI_FILE_SELECTION=""

function count_attachments() {
  local file="$1"
  mkvmerge --identify "$file" | grep -c "Attachment ID"
}

format_duration() {
  local total_seconds="$1"
  printf "%02d:%02d:%02d" \
    $((total_seconds / 3600)) \
    $(((total_seconds % 3600) / 60)) \
    $((total_seconds % 60))
}

prompt_yes_no() {
  local prompt_text="$1"
  local default_choice="$2"
  local response=""

  while true; do
    printf "%s" "$prompt_text" >&2
    read response
    if [[ -z "$response" && -n "$default_choice" ]]; then
      response="$default_choice"
    fi

    case "${response:u}" in
      Y) print -r -- "Y"; return 0 ;;
      N) print -r -- "N"; return 0 ;;
      *) echo "Invalid choice. Please enter Y or N." >&2 ;;
    esac
  done
}

normalize_track_id_input() {
  local track_input="$1"
  track_input=$(printf '%s' "$track_input" | tr -d '[:space:]')
  printf '%s' "$track_input"
}

validate_track_id_list() {
  local track_input="$1"
  if ! printf '%s' "$track_input" | grep -Eq '^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$'; then
    return 1
  fi

  local -a track_parts
  IFS=',' read -rA track_parts <<< "$track_input"

  local part=""
  for part in "${track_parts[@]}"; do
    if [[ "$part" == *-* ]]; then
      local start=${part%-*}
      local end=${part#*-}
      if (( start > end )); then
        return 1
      fi
    fi
  done

  return 0
}

prompt_for_track_ids() {
  local prompt_text="$1"
  local track_ids=""

  while true; do
    printf "%s" "$prompt_text" >&2
    read track_ids
    track_ids=$(normalize_track_id_input "$track_ids")
    if [[ -z "$track_ids" ]]; then
      echo "Track ID(s) cannot be empty. Please enter at least one Track ID." >&2
      continue
    fi
    if validate_track_id_list "$track_ids"; then
      print -r -- "$track_ids"
      return 0
    fi
    echo "Invalid Track ID syntax. Use values like 0,1 or 1-2." >&2
  done
}

normalize_track_order() {
  local track_order="$1"
  track_order=$(printf '%s' "$track_order" | tr -d '[:space:]')
  printf '%s' "$track_order"
}

validate_track_order() {
  local track_order="$1"
  printf '%s' "$track_order" | grep -Eq '^[0-9]+:[0-9]+(,[0-9]+:[0-9]+)*$'
}

prompt_for_track_order() {
  local prompt_text="$1"
  local track_order=""

  while true; do
    printf "%s" "$prompt_text" >&2
    read track_order
    track_order=$(normalize_track_order "$track_order")
    if [[ -z "$track_order" ]]; then
      echo "Track order cannot be empty. Please enter at least one mapping." >&2
      continue
    fi
    if validate_track_order "$track_order"; then
      print -r -- "$track_order"
      return 0
    fi
    echo "Invalid track order syntax. Use values like 0:0,0:1,0:2." >&2
  done
}
 
# Function to display track information safely, projecting only the fields we need
display_track_info() {
  local source_file="$1"

  echo "-----------------------  mkvmerge JSON track listing -----------------------"
  mkvmerge -J "$source_file" < /dev/null \
    | jq -r '
        .tracks[]
        | {
            id:    .id,
            type:  .type,
            codec: .properties.codec_id,
            name:  (.properties.track_name // ""),
            lang:  (.properties.language      // .properties.language_ietf // "")
          }
        | "Track ID \(.id): \(.type) (\(.codec))"
          + (if .name != "" then " [\(.name)]" else "" end)
          + (if .lang != "" then " [\(.lang)]" else "" end)
      '
}

# Function to rename tracks using mkvpropedit
rename_tracks() {
  local track_ids="$1"
  # Split track_ids by comma and space into array ids
  IFS=', ' read -rA ids <<< "$track_ids"
  # Loop over each track ID
  for id in "${ids[@]}"; do
    # Determine range or single ID
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Name ---------------------"
        printf "Name: "
        read name
        # Apply name change to each target file
        for file in "${targets[@]}"; do
          if (trap '' SIGINT; exec mkvpropedit "$file" --edit track:$((i+1)) --set name="$name" < /dev/null); then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Name ---------------------"
      printf "Name: "
      read name
      for file in "${targets[@]}"; do
        if (trap '' SIGINT; exec mkvpropedit "$file" --edit track:$((id+1)) --set name="$name" < /dev/null); then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
        fi
      done
    fi
  done
}

set_mkv_title() {
  local title="$1"

  for file in "${targets[@]}"; do
    if [[ -z "$title" ]]; then
      if mkvpropedit "$file" --delete title < /dev/null; then
        echo "Edited File: ${file:t}"
      else
        echo "Failed File: ${file:t}"
      fi
    else
      if mkvpropedit "$file" --set title="$title" < /dev/null; then
        echo "Edited File: ${file:t}"
      else
        echo "Failed File: ${file:t}"
      fi
    fi
  done
}


# Function to set language of tracks across multiple files
set_language_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<< "$track_ids"
  for id in "${ids[@]}"; do
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Language ---------------------"
        printf "Language: "
        read lang
        for file in "${targets[@]}"; do
          if mkvpropedit "$file" --edit track:$((i+1)) --set language="$lang"; then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Language ---------------------"
      printf "Language: "
      read lang
      for file in "${targets[@]}"; do
        if mkvpropedit "$file" --edit track:$((id+1)) --set language="$lang"; then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
        fi
      done
    fi
  done
}

# Function to set forced flag for tracks across multiple files
set_flag_forced_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<< "$track_ids"
  for id in "${ids[@]}"; do
    # Determine range or single ID
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Forced Flag ---------------------"
        printf "Flag-forced (1 or 0) [0]: "
        read value
        value=${value:-0}
        for file in "${targets[@]}"; do
          if mkvpropedit "$file" --edit track:$((i+1)) --set flag-forced=$value; then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Forced Flag ---------------------"
      printf "Flag-forced (1 or 0) [0]: "
      read value
      value=${value:-0}
      for file in "${targets[@]}"; do
        if mkvpropedit "$file" --edit track:$((id+1)) --set flag-forced=$value; then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
        fi
      done
    fi
  done
}

# Function to set default flag for tracks across multiple files
set_flag_default_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<< "$track_ids"
  for id in "${ids[@]}"; do
    # Determine range or single ID
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Default Flag ---------------------"
        printf "Flag-default (1 or 0) [1]: "
        read value
        value=${value:-1}
        for file in "${targets[@]}"; do
          if mkvpropedit "$file" --edit track:$((i+1)) --set flag-default=$value; then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Default Flag ---------------------"
      printf "Flag-default (1 or 0) [1]: "
      read value
      value=${value:-1}
      for file in "${targets[@]}"; do
        if mkvpropedit "$file" --edit track:$((id+1)) --set flag-default=$value; then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
        fi
      done
    fi
  done
}

# Helper: extract one track by id, with enhanced output
extract_single() {
  local tid=$1
  local src_base=${source_file##*/}
  local base=${src_base%.*}

  # Pull the JSON for this file directly, then grab codec_id
  local cid
  cid=$(mkvmerge -J "$source_file" < /dev/null \
        | jq -r ".tracks[] | select(.id==${tid}) | .properties.codec_id")

  # 1) Try a full‐ID override
  local ext=${ext_override[$cid]:-}

  # 2) Fallback to the short key
  if [[ -z $ext ]]; then
    local key=${cid##*/}
    ext=${ext_override[$key]:-}
  fi

  # 3) Fallback to pymkv2 map or lowercase key
  if [[ -z $ext ]]; then
    ext=${codec_ext[$key]:-}
    [[ -z $ext ]] && ext=${(L)${key//[^[:alnum:]]/}}
  fi

  echo "Matched codec ID: ${cid} → extension: .${ext}"
  echo "Extracting track ${tid} (${cid}) → ${base} - Track [${tid}].${ext}"
  mkvextract tracks "$source_file" \
    ${tid}:"${base} - Track [${tid}].${ext}"
}

# Function to extract selected tracks from a single MKV
extract_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<<"$track_ids"

  # build the codec→ext map
  typeset -A codec_ext
  ensure_venv_python
  eval "$(
    "$PYTHON_BIN" - <<'PYCODE'
from pymkv.TypeTrack import type_files
flat = {k:v for cat in type_files.values() for k,v in cat.items()}
items = ' '.join(f"['{k}']='{v}'" for k, v in flat.items())
print(f"typeset -A codec_ext=( {items} )")
PYCODE
  )"

  for id in "${ids[@]}"; do
    if [[ $id == *-* ]]; then
      local start=${id%-*} end=${id#*-}
      for ((i=start; i<=end; i++)); do
        extract_single "$i"
      done
    else
      extract_single "$id"
    fi
  done
}

print_help() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [working_directory]
       ${SCRIPT_NAME} --help

Interactive Matroska utility script for metadata edits, extraction, and track operations.

Arguments:
  --help, -h            Show this help page and exit.
  working_directory     Directory to scan instead of the current directory.

Menu options:
  1) Set flag-forced for tracks
     Set the forced flag on selected track IDs across one or more Matroska files.

  2) Set flag-default for tracks
     Set the default flag on selected track IDs across one or more Matroska files.

  3) Set language for tracks
     Change the language field on selected track IDs.

  4) Set name for tracks
     Rename selected track IDs.

  5) Set title for MK file
     Set or clear the container title on one or more files.

  6) Extract all attachments from MK files
     Extract every attachment into an Attachments directory.

  7) Mass Remove tracks for multi-MK files
     Remove selected track IDs and remux the remaining tracks.

  8) Mass Re-order tracks for multi-MK files
     Apply a new mkvmerge track order to selected files.

  9) Extract Tracks for multi-MK files
     Extract selected track IDs from one or more files.

Notes:
  - With no working_directory argument, the script uses the current directory.
  - The script requires Matroska files in the target directory before the menu can run.
EOF
}

display_dir="$(pwd)"
working_dir_set=false

while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    -*)
      echo "Usage: ${SCRIPT_NAME} [working_directory]" >&2
      exit 1
      ;;
    *)
      if [ "$working_dir_set" = true ]; then
        echo "Usage: ${SCRIPT_NAME} [working_directory]" >&2
        exit 1
      fi
      display_dir="$1"
      working_dir_set=true
      ;;
  esac
  shift
done

current_dir="$display_dir"
if [ ! -d "$current_dir" ]; then
  echo "Error: Working directory not found: $current_dir" >&2
  exit 1
fi

cd "$current_dir" || exit 1
current_dir="$(pwd)"
echo "Current Work Dir: $display_dir"

# Collect Matroska files in current dir
matroska_files=()
for ext in mkv mka mks mk3d; do
  # Use (N) glob qualifier to suppress nomatch errors
  for f in "$current_dir"/*.$ext(N); do
    [ -e "$f" ] && matroska_files+=("$f")
  done
done
if [ ${#matroska_files[@]} -eq 0 ]; then
  echo "Please check if there are Matroska files (.mkv, .mka, .mks, .mk3d) present before running this script again."
  exit 1
fi

print -n "Select an option:
1) Set flag-forced for tracks
2) Set flag-default for tracks
3) Set language for tracks
4) Set name for tracks
5) Set title for MK file
6) Extract all attachments from MK files
7) Mass Remove tracks for multi-MK files
8) Mass Re-order tracks for multi-MK files
9) Extract Tracks for multi-MK files
Enter choice: "
read choice

while [[ -z "$choice" || "$choice" != [1-9] ]]; do
  echo "Invalid choice. Please enter a number from 1 to 9."
  printf "Enter choice: "
  read choice
done

if [ "$choice" = "1" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply forced-flag edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

  # Apply forced-flag edits (prompting per track)
  set_flag_forced_tracks "$track_ids"

elif [ "$choice" = "2" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply default-flag edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

  # Apply default-flag edits (prompting per track)
  set_flag_default_tracks "$track_ids"
  
elif [ "$choice" = "3" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply language edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

  # Perform language setting on selected files (prompting per track)
  set_language_tracks "$track_ids"
  
elif [ "$choice" = "4" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply name edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

	# Perform renaming on selected files
	rename_tracks "$track_ids"

		elif [ "$choice" = "5" ]; then
		  # Prompt for multi-file or single-file selection
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

	  # Determine target files
	  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
	    echo "Select Matroska file(s) to apply title edits:"
	    typeset -a targets
	    targets=()
	    while IFS= read -r file; do
	      targets+=("$file")
	    done < <(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
	      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
	    if [ ${#targets[@]} -eq 0 ]; then
	      echo "No target files selected. Exiting."
	      exit 1
	    fi
	  else
	    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
	    source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
	      | fzf --height 40% --reverse --border)
	    if [ -z "$source_file" ]; then
	      echo "No file selected. Exiting."
	      exit 1
	    fi
	    typeset -a targets
	    targets=("$source_file")
	  fi

	  printf "Title (empty to unset): "
	  read title

	  set_mkv_title "$title"

	elif [ "$choice" = "6" ]; then
	  echo "Select Matroska file(s) to extract attachments:"
	  typeset -a targets
	  targets=()
	  while IFS= read -r file; do
	    targets+=( "$file" )
  done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")

  if [ ${#targets[@]} -eq 0 ]; then
    echo "No target files selected. Exiting."
    exit 1
  fi
  # Prepare output directory for attachments
  mkdir -p "Attachments"

  for file in "${targets[@]}"; do
    attachment_count=$(count_attachments "$file")
    echo "Processing $file: Extracting $attachment_count attachments..."

    if [ "$attachment_count" -gt 0 ]; then
      # Compute attachment IDs
      attachment_ids=( $(seq 1 $attachment_count) )
      # Determine absolute path to source file
      # Remove leading './' if present
      relpath=${file#./}
      filepath="$current_dir/$relpath"
      # Extract into Attachments directory
      (cd "Attachments" && mkvextract attachments "$filepath" "${attachment_ids[@]}")
    fi
	  done
	  echo "Attachments extraction completed."

		elif [ "$choice" = "7" ]; then
		  # --- Choice 7: Mass Remove tracks ---
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Build fzf args
  fzf_args=(--height 40% --reverse --border --prompt="Select file(s) >")
  [[ $MULTI_FILE_SELECTION == "Y" ]] && fzf_args+=(--multi)

  # Single fzf to pick targets
  targets=()
  while IFS= read -r f; do
    targets+=("$f")
  done < <(
    find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf "${fzf_args[@]}"
  )
  [ ${#targets[@]} -eq 0 ] && { echo "No files selected. Exiting."; exit 1; }

  # Show JSON-based track list for first file
  source_file=${targets[1]}
  display_track_info "$source_file"

  # Ask which track IDs to remove
  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): ")

  # Build exclude_ids[] by splitting on commas and ranges
  exclude_ids=()
  for tok in ${(s:,:)track_ids}; do
    if [[ $tok == *-* ]]; then
      start=${tok%-*}; end=${tok#*-}
      for ((i=start; i<=end; i++)); do
        exclude_ids+=($i)
      done
    else
      exclude_ids+=($tok)
    fi
  done
  # sort & dedupe
  exclude_ids=($(printf "%s\n" "${exclude_ids[@]}" | sort -n | uniq))

  echo "Removing tracks: ${exclude_ids[*]}"

  # Build keep lists by streaming mkvmerge JSON directly into jq
  video_keep=($(mkvmerge -J "$source_file" < /dev/null \
                 | jq -r '.tracks[] | select(.type=="video")      | .id'))
  audio_keep=($(mkvmerge -J "$source_file" < /dev/null \
                 | jq -r '.tracks[] | select(.type=="audio")      | .id'))
  subtitle_keep=($(mkvmerge -J "$source_file" < /dev/null \
                 | jq -r '.tracks[] | select(.type=="subtitles") | .id'))

  # Helper to filter out excluded IDs
  filter_keep() {
    local arr=("$@") keep=()
    for id in "${arr[@]}"; do
      [[ ! " ${exclude_ids[*]} " == *" $id "* ]] && keep+=($id)
    done
    echo "${keep[@]}"
  }
  video_keep=($(filter_keep "${video_keep[@]}"))
  audio_keep=($(filter_keep "${audio_keep[@]}"))
  subtitle_keep=($(filter_keep "${subtitle_keep[@]}"))

  # Apply removal to each file
  files_count=${#targets[@]}
  file_index=1
  total_processing_seconds=0
  successful_files=0
  failed_files=()
  queue_start=$SECONDS
  for target in "${targets[@]}"; do
    base=${target##*/}; base=${base%.*}; ext=${target##*.}
    [[ ${#video_keep[@]} -eq 0 ]] && out_ext=mka || out_ext=$ext
    tmp="${base}_temp.${out_ext}"

    cmd=(mkvmerge -o "$tmp")
    [[ ${#video_keep[@]} -gt 0 ]] \
      && cmd+=(--video-tracks "$(IFS=,; echo "${video_keep[*]}")") \
      || cmd+=(--no-video)
    [[ ${#audio_keep[@]} -gt 0 ]] \
      && cmd+=(--audio-tracks "$(IFS=,; echo "${audio_keep[*]}")") \
      || cmd+=(--no-audio)
    [[ ${#subtitle_keep[@]} -gt 0 ]] \
      && cmd+=(--subtitle-tracks "$(IFS=,; echo "${subtitle_keep[*]}")") \
      || cmd+=(--no-subtitles)
    cmd+=("$target")

    if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 && $file_index -eq 1 ]]; then
      echo "Total Files Count: $files_count"
    fi
    echo "Executing: ${cmd[*]}"
    remux_start=$SECONDS
    if "${cmd[@]}"; then
      remux_duration=$((SECONDS - remux_start))
      mv "$tmp" "${base}.${out_ext}"
      echo "Replaced: ${base}.${out_ext}"
      [[ "$out_ext" != "$ext" ]] && rm -f "$target" && echo "Removed original: $target"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        total_processing_seconds=$((total_processing_seconds + remux_duration))
        successful_files=$((successful_files + 1))
        files_remaining=$((files_count - file_index))
        estimated_seconds=$(((total_processing_seconds * files_remaining + successful_files / 2) / successful_files))
        echo "${target:t}"
        echo "  Processed In: $(format_duration "$remux_duration")"
        echo "  Files Done: $successful_files"
        echo "  Files Remaining: $files_remaining"
        echo "  Estimated Time Remaining: $(format_duration "$estimated_seconds")"
      fi
    else
      rm -f "$tmp"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on $target; cleaning up."
      fi
	    fi
    file_index=$((file_index + 1))
	  done
  if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
    echo "Total Files Done: $successful_files"
    printf "Failed Files: %02d\n" ${#failed_files[@]}
    for failed_file in "${failed_files[@]}"; do
      echo "  $failed_file"
    done
    echo "Elapsed Time: $(format_duration "$((SECONDS - queue_start))")"
  fi

		elif [ "$choice" = "8" ]; then
		  # --- Choice 8: Mass Re-order tracks ---
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  fzf_args=(--height 40% --reverse --border --prompt="Select file(s) >")
  [[ $MULTI_FILE_SELECTION == "Y" ]] && fzf_args+=(--multi)

  targets=()
  while IFS= read -r f; do
    targets+=("$f")
  done < <(
    find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf "${fzf_args[@]}"
  )
  [ ${#targets[@]} -eq 0 ] && { echo "No files selected. Exiting."; exit 1; }

  source_file=${targets[1]}
  display_track_info "$source_file"

  track_order=$(prompt_for_track_order "Enter the new track order (e.g., 0:0,0:1,0:2,…): ")

  files_count=${#targets[@]}
  file_index=1
  total_processing_seconds=0
  successful_files=0
  failed_files=()
  queue_start=$SECONDS
  for target in "${targets[@]}"; do
    base=${target##*/}; base=${base%.*}; ext=${target##*.}
    tmp="${base}_temp.${ext}"
    cmd=(mkvmerge -o "$tmp" --track-order "$track_order" "$target")

    if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 && $file_index -eq 1 ]]; then
      echo "Total Files Count: $files_count"
    fi
    echo "Executing: ${cmd[*]}"
    remux_start=$SECONDS
    if "${cmd[@]}"; then
      remux_duration=$((SECONDS - remux_start))
      mv "$tmp" "${base}.${ext}"
      echo "Replaced: ${base}.${ext}"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        total_processing_seconds=$((total_processing_seconds + remux_duration))
        successful_files=$((successful_files + 1))
        files_remaining=$((files_count - file_index))
        estimated_seconds=$(((total_processing_seconds * files_remaining + successful_files / 2) / successful_files))
        echo "${target:t}"
        echo "  Processed In: $(format_duration "$remux_duration")"
        echo "  Files Done: $successful_files"
        echo "  Files Remaining: $files_remaining"
        echo "  Estimated Time Remaining: $(format_duration "$estimated_seconds")"
      fi
    else
      rm -f "$tmp"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on $target; cleaning up."
      fi
    fi
    file_index=$((file_index + 1))
	  done
  if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
    echo "Total Files Done: $successful_files"
    printf "Failed Files: %02d\n" ${#failed_files[@]}
    for failed_file in "${failed_files[@]}"; do
      echo "  $failed_file"
    done
    echo "Elapsed Time: $(format_duration "$((SECONDS - queue_start))")"
  fi
	  
	# --- Choice 9: Extract Tracks ---
	elif [ "$choice" = "9" ]; then
		  # Prompt for multi-file or single-file selection
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to extract tracks:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for the first target
  source_file=${targets[1]}
  display_track_info "$source_file"

  # Ask once for which tracks to extract
  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to extract (e.g., 0,1 or 1-2): ")

  # Loop over all selected files
  for source_file in "${targets[@]}"; do
    echo "→ Extracting tracks ${track_ids} from $source_file"
    extract_tracks "$track_ids"
  done

else
  echo "Invalid choice."
fi
