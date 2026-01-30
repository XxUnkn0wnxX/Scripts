#!/usr/local/bin/zsh

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

SCRIPT_ROOT=${0:A:h}
VENV_PATH="$SCRIPT_ROOT/.venv"
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
          (trap '' SIGINT; exec mkvpropedit "$file" --edit track:$((i+1)) --set name="$name" < /dev/null)
        done
      done
    else
      echo "--------------------  Track ID $id Name ---------------------"
      printf "Name: "
      read name
      for file in "${targets[@]}"; do
        (trap '' SIGINT; exec mkvpropedit "$file" --edit track:$((id+1)) --set name="$name" < /dev/null)
      done
    fi
  done
}

set_mkv_title() {
  local title="$1"

  for file in "${targets[@]}"; do
    if [[ -z "$title" ]]; then
      mkvpropedit "$file" --delete title < /dev/null
    else
      mkvpropedit "$file" --set title="$title" < /dev/null
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
          mkvpropedit "$file" --edit track:$((i+1)) --set language="$lang"
        done
      done
    else
      echo "--------------------  Track ID $id Language ---------------------"
      printf "Language: "
      read lang
      for file in "${targets[@]}"; do
        mkvpropedit "$file" --edit track:$((id+1)) --set language="$lang"
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
          mkvpropedit "$file" --edit track:$((i+1)) --set flag-forced=$value
        done
      done
    else
      echo "--------------------  Track ID $id Forced Flag ---------------------"
      printf "Flag-forced (1 or 0) [0]: "
      read value
      value=${value:-0}
      for file in "${targets[@]}"; do
        mkvpropedit "$file" --edit track:$((id+1)) --set flag-forced=$value
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
          mkvpropedit "$file" --edit track:$((i+1)) --set flag-default=$value
        done
      done
    else
      echo "--------------------  Track ID $id Default Flag ---------------------"
      printf "Flag-default (1 or 0) [1]: "
      read value
      value=${value:-1}
      for file in "${targets[@]}"; do
        mkvpropedit "$file" --edit track:$((id+1)) --set flag-default=$value
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

if [ $# -gt 1 ]; then
  echo "Usage: ${0:t} [working_directory]" >&2
  exit 1
fi

display_dir="${1:-$(pwd)}"
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

choice=${choice:-1}

if [ "$choice" = "1" ]; then
  # Prompt for multi-file or single-file selection
  print -n "Enable multi-file target selection? (Y/N) [N]: "
  read MULTI_FILE_SELECTION
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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

  printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
  read track_ids
  while [[ -z "$track_ids" ]]; do
    echo "Track ID(s) cannot be empty. Please enter at least one Track ID."
    printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
    read track_ids
  done

  # Apply forced-flag edits (prompting per track)
  set_flag_forced_tracks "$track_ids"

elif [ "$choice" = "2" ]; then
  # Prompt for multi-file or single-file selection
  print -n "Enable multi-file target selection? (Y/N) [N]: "
  read MULTI_FILE_SELECTION
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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

  printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
  read track_ids
  while [[ -z "$track_ids" ]]; do
    echo "Track ID(s) cannot be empty. Please enter at least one Track ID."
    printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
    read track_ids
  done

  # Apply default-flag edits (prompting per track)
  set_flag_default_tracks "$track_ids"
  
elif [ "$choice" = "3" ]; then
  # Prompt for multi-file or single-file selection
  print -n "Enable multi-file target selection? (Y/N) [N]: "
  read MULTI_FILE_SELECTION
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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

  printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
  read track_ids
  while [[ -z "$track_ids" ]]; do
    echo "Track ID(s) cannot be empty. Please enter at least one Track ID."
    printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
    read track_ids
  done

  # Perform language setting on selected files (prompting per track)
  set_language_tracks "$track_ids"
  
elif [ "$choice" = "4" ]; then
  # Prompt for multi-file or single-file selection
  print -n "Enable multi-file target selection? (Y/N) [N]: "
  read MULTI_FILE_SELECTION
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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

  printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
  read track_ids
  while [[ -z "$track_ids" ]]; do
    echo "Track ID(s) cannot be empty. Please enter at least one Track ID."
    printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
    read track_ids
  done

	# Perform renaming on selected files
	rename_tracks "$track_ids"

	elif [ "$choice" = "5" ]; then
	  # Prompt for multi-file or single-file selection
	  print -n "Enable multi-file target selection? (Y/N) [N]: "
	  read MULTI_FILE_SELECTION
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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
	  print -n "Enable multi-file target selection? (Y/N) [N]: "
	  read MULTI_FILE_SELECTION
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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
  printf "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): "
  read track_ids
  while [[ -z "$track_ids" ]]; do
    echo "Track ID(s) cannot be empty. Please enter at least one Track ID."
    printf "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): "
    read track_ids
  done

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

    echo "Executing: ${cmd[*]}"
    if "${cmd[@]}"; then
      mv "$tmp" "${base}.${out_ext}"
      echo "Replaced: ${base}.${out_ext}"
      [[ "$out_ext" != "$ext" ]] && rm -f "$target" && echo "Removed original: $target"
    else
      echo "Error on $target; cleaning up."
      rm -f "$tmp"
	    fi
	  done

	elif [ "$choice" = "8" ]; then
	  # --- Choice 8: Mass Re-order tracks ---
	  print -n "Enable multi-file target selection? (Y/N) [N]: "
	  read MULTI_FILE_SELECTION
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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

  printf "Enter the new track order (e.g., 0:0,0:1,0:2,…): "
  read track_order
  while [[ -z "$track_order" ]]; do
    echo "Track order cannot be empty. Please enter at least one mapping."
    printf "Enter the new track order (e.g., 0:0,0:1,0:2,…): "
    read track_order
  done

  for target in "${targets[@]}"; do
    base=${target##*/}; base=${base%.*}; ext=${target##*.}
    tmp="${base}_temp.${ext}"
    cmd=(mkvmerge -o "$tmp" --track-order "$track_order" "$target")

    echo "Executing: ${cmd[*]}"
    if "${cmd[@]}"; then
      mv "$tmp" "${base}.${ext}"
      echo "Replaced: ${base}.${ext}"
    else
      echo "Error on $target; cleaning up."
      rm -f "$tmp"
    fi
	  done
	  
	# --- Choice 9: Extract Tracks ---
	elif [ "$choice" = "9" ]; then
	  # Prompt for multi-file or single-file selection
	  print -n "Enable multi-file target selection? (Y/N) [N]: "
	  read MULTI_FILE_SELECTION
	  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

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
  printf "Enter the Track ID(s) to extract (e.g., 0,1 or 1-2): "
  read track_ids
  while [[ -z "$track_ids" ]]; do
    echo "Track ID(s) cannot be empty. Please enter at least one Track ID."
    printf "Enter the Track ID(s) to extract (e.g., 0,1 or 1-2): "
    read track_ids
  done

  # Loop over all selected files
  for source_file in "${targets[@]}"; do
    echo "→ Extracting tracks ${track_ids} from $source_file"
    extract_tracks "$track_ids"
  done

else
  echo "Invalid choice."
fi
