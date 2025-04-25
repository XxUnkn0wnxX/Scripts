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

# Extension overrides for Plex / VLC compatibility
typeset -A ext_override=(
  # Video elementary streams
  ["V_MPEG4/ISO/AVC"]="h264"     # raw H.264 → .h264
  ["V_MPEGH/ISO/HEVC"]="h265"    # raw HEVC/H.265 → .h265

  # Audio elementary streams
  ["A_AAC"]="aac"                # AAC audio → .aac
  ["A_AC3"]="ac3"                # AC-3 (Dolby Digital) → .ac3
  ["A_DTS"]="dts"                # DTS audio → .dts

  # Subtitle sidecars
  ["S_TEXT/SRT"]="srt"           # SubRip → .srt
  ["S_TEXT/ASS"]="ass"           # SubStation Alpha → .ass
  ["S_HDMV/PGS"]="pgs"           # PGS subtitles → .pgs
)

# Multi-file target selection mode for choice 8 (Y/N)
MULTI_FILE_SELECTION=""

function count_attachments() {
  local file="$1"
  mkvmerge --identify "$file" | grep -c "Attachment ID"
}
 
# Function to display track information using mkvmerge JSON output
display_track_info() {
  local source_file="$1"
  echo "-----------------------  mkvmerge JSON track listing -----------------------"
  local info_json
  info_json=$(mkvmerge -J "$source_file" < /dev/null)
  echo "$info_json" | jq -c '.tracks[]' | while IFS= read -r track; do
    local id=$(echo "$track" | jq '.id')
    local type=$(echo "$track" | jq -r '.type')
    local codec=$(echo "$track" | jq -r '.properties.codec_id')
    local name=$(echo "$track" | jq -r '.properties.track_name // empty')
    local lang=$(echo "$track" | jq -r '.properties.language   // empty')

    local line="Track ID ${id}: ${type} (${codec})"
    [[ -n $name ]] && line+=" [${name}]"
    [[ -n $lang ]] && line+=" [${lang}]"
    echo "$line"
  done
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
        printf "Flag-forced (1 or 0) [1]: "
        read value
        value=${value:-1}
        for file in "${targets[@]}"; do
          mkvpropedit "$file" --edit track:$((i+1)) --set flag-forced=$value
        done
      done
    else
      echo "--------------------  Track ID $id Forced Flag ---------------------"
      printf "Flag-forced (1 or 0) [1]: "
      read value
      value=${value:-1}
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
  local cid=$(jq -r ".tracks[] | select(.id==${tid}) | .properties.codec_id" <<<"$info_json")
  local src_base=${source_file##*/}; local base=${src_base%.*}

  # 1) check override by full id
  local ext=${ext_override[$cid]:-}
  if [[ -z $ext ]]; then
    # 2) check override by short key
    local key=${cid##*/}
    ext=${ext_override[$key]:-}
    if [[ -z $ext ]]; then
      # 3) fallback to pymkv2 map
      ext=${codec_ext[$key]:-}
      [[ -z $ext ]] && ext=${(L)${key//[^[:alnum:]]/}}
    fi
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
  eval "$(
    python3 - <<'PYCODE'
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

current_dir=$(pwd)
echo "Current Work Dir: $current_dir"
cd "$current_dir"

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
5) Extract all attachments from MK files
6) Mass Remove tracks for multi-MK files
7) Mass Re-order tracks for multi-MK files
8) Extract Tracks for a single MK file
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

  # Perform renaming on selected files
  rename_tracks "$track_ids"

elif [ "$choice" = "5" ]; then
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

elif [ "$choice" = "6" ]; then
  # --- Choice 6: Mass Remove tracks ---
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

  # Grab JSON metadata once
  info_json=$(mkvmerge -J "$source_file")

  # Build keep lists
  video_keep=($(jq -r '.tracks[]|select(.type=="video")|.id' <<<"$info_json"))
  audio_keep=($(jq -r '.tracks[]|select(.type=="audio")|.id' <<<"$info_json"))
  subtitle_keep=($(jq -r '.tracks[]|select(.type=="subtitles")|.id' <<<"$info_json"))

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


elif [ "$choice" = "7" ]; then
  # --- Choice 7: Mass Re-order tracks ---
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
  
# --- Choice 8: Extract Tracks ---
elif [ "$choice" = "8" ]; then
  # single-file only
  printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
  source_file=$(find . -maxdepth 1 -type f \
    \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf --height 40% --reverse --border)
  [ -z "$source_file" ] && { echo "No file selected. Exiting."; exit 1; }

  # Display track info
  info_json=$(mkvmerge -J "$source_file" < /dev/null)
  display_track_info "$source_file"

  printf "Enter the Track ID(s) to extract (e.g., 0,1 or 1-2): "
  read track_ids

  extract_tracks "$track_ids"

else
  echo "Invalid choice."
fi