#!/usr/local/bin/zsh

# Multi-file target selection mode for choice 8 (Y/N)
MULTI_FILE_SELECTION=""

function get_track_count() {
  local file="$1"
  local count=$(mkvmerge "$file" --identify | grep 'Track ID' | wc -l)
  echo $count
}

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

current_dir=$(pwd)
echo "Current Work Dir: $current_dir"
cd "$current_dir"

if [ ! "$(ls -A "$current_dir"/*.mkv 2>/dev/null)" ]; then
  echo "Please check if there are video files present before running this script again."
  exit 1
fi

print -n "Select an option:
1) Set flag-forced for a track
2) Set flag-default for all tracks
3) Set flag-default for a track
4) Remove flag-forced for all tracks
5) Set language for a track
6) Set name for a track
7) Extract all attachments from MKV files
8) Mass Remove tracks for multi-MKV files
9) Mass Re-order tracks for multi-MKV files
Enter choice: "
read choice

choice=${choice:-1}

if [ "$choice" = "1" ]; then
  print -n "Enter the track number: "
  read track_num
  print -n "Enter flag-forced value (1 or 0, blank for 1): "
  read flag_value
  flag_value=${flag_value:-1}
  track_num=${track_num:-4}

  for file in *.mkv; do
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" --edit track:$track_num --set flag-forced=$flag_value
  done
  # Re-enable Ctrl+C after processing
  trap - INT

elif [ "$choice" = "2" ]; then
#  function get_track_count() {
#    local file="$1"
#    local count=$(mkvmerge "$file" --identify | grep 'Track ID' | wc -l)
#    echo $count
#  }

  print -n "Enter flag-default value (1 or 0, blank for 1): "
  read flag_value
  flag_value=${flag_value:-1}

  for file in *.mkv; do
    track_count=$(get_track_count "$file")
    typeset -a edit_flags
    edit_flags=()
    for (( i=1; i<=track_count; i++ )); do
      edit_flags+=(--edit track:$i --set flag-default=$flag_value)
    done
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" "${edit_flags[@]}"
  done
  
elif [ "$choice" = "3" ]; then
  print -n "Enter the track number: "
  read track_num
  print -n "Enter flag-default value (1 or 0, blank for 1): "
  read flag_value
  flag_value=${flag_value:-1}
  track_num=${track_num:-4}

  for file in *.mkv; do
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" --edit track:$track_num --set flag-default=$flag_value
  done
  
elif [ "$choice" = "4" ]; then
#  function get_track_count() {
#    local file="$1"
#    local count=$(mkvmerge "$file" --identify | grep 'Track ID' | wc -l)
#    echo $count
#  }

  flag_value=${flag_value:-0}

  for file in *.mkv; do
    track_count=$(get_track_count "$file")
    typeset -a edit_flags
    edit_flags=()
    for (( i=1; i<=track_count; i++ )); do
      edit_flags+=(--edit track:$i --set flag-forced=$flag_value)
    done
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" "${edit_flags[@]}"
  done
  
elif [ "$choice" = "5" ]; then
  print -n "Enter the track number: "
  read track_num
  print -n "Enter the lang (eng, jpn, und): "
  read flag_lang
  flag_lang=${flag_lang:-jpn}
  track_num=${track_num:-2}

  for file in *.mkv; do
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" --edit track:$track_num --set language=$flag_lang
  done
  
elif [ "$choice" = "6" ]; then
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

elif [ "$choice" = "7" ]; then
  for file in *.mkv; do
    attachment_count=$(count_attachments "$file")
    echo "Processing $file: Extracting $attachment_count attachments..."

    if [ "$attachment_count" -gt 0 ]; then
      attachment_ids=($(seq 1 $attachment_count))
      mkvextract attachments "$file" "${attachment_ids[@]}"
    fi
  done
  echo "Attachments extraction completed."

elif [ "$choice" = "8" ]; then
  # Single-file Remove-Tracks flow (from mkv_mux choice 3)
  # Ask if user wants multi-file target selection or single-file
  print -n "Enable multi-file target selection? (Y/N) [N]: "
  read MULTI_FILE_SELECTION
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

  echo "Select the source Matroska file (.mkv, .mka, .mks, .mk3d): to pull track ids"
  source_file=$(find . -maxdepth 1 -type f \
    \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf --height 40% --reverse --border --prompt="Select Matroska file > ")
  [ -z "$source_file" ] && { echo "No file selected. Exiting."; exit 1; }

  echo "Identifying all tracks in $source_file..."
  info=$(mkvinfo "$source_file" < /dev/null)
  all_tracks=$(mkvmerge --identify "$source_file" < /dev/null | grep -E 'Track ID [0-9]+:')
  track_count=$(echo "$all_tracks" | wc -l)
  [ "$track_count" -eq 0 ] && { echo "No tracks found."; exit 1; }

  echo "Tracks found:"
  while IFS= read -r line; do
    id=$(echo "$line" | sed -E 's/Track ID ([0-9]+):.*/\1/')
    name=$(echo "$info" | awk -v id="$id" '
      /Track number:/ && $0 ~ "extract: " id { in_block=1; next }
      /^\| \+ Track/ && in_block { exit }
      /Name:/ && in_block { sub(/.*Name:[ \t]*/, ""); print; exit }
    ')
    [ -n "$name" ] && echo "$line [$name]" || echo "$line"
  done <<< "$all_tracks"

  printf "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): "
  read track_ids
  exclude_ids=()
  IFS=',' read -r raw <<< "$track_ids"
  for id in ${(s:,:)raw}; do
    if [[ $id == *-* ]]; then
      start=${id%-*}; end=${id#*-}
      for ((i=start; i<=end; i++)); do exclude_ids+=($i); done
    else
      exclude_ids+=($id)
    fi
  done
  exclude_ids=($(printf "%s\n" "${exclude_ids[@]}" | sort -n | uniq))

  info_json=$(mkvmerge -J "$source_file" < /dev/null)
  video_ids=($(echo "$info_json" | jq -r '.tracks[]|select(.type=="video")|.id'))
  audio_ids=($(echo "$info_json" | jq -r '.tracks[]|select(.type=="audio")|.id'))
  subtitle_ids=($(echo "$info_json" | jq -r '.tracks[]|select(.type=="subtitles")|.id'))

  video_keep=(); for i in "${video_ids[@]}";   do [[ ! " ${exclude_ids[@]} " =~ " $i " ]] && video_keep+=($i); done
  audio_keep=(); for i in "${audio_ids[@]}";   do [[ ! " ${exclude_ids[@]} " =~ " $i " ]] && audio_keep+=($i); done
  subtitle_keep=(); for i in "${subtitle_ids[@]}"; do [[ ! " ${exclude_ids[@]} " =~ " $i " ]] && subtitle_keep+=($i); done

  echo "Removing tracks: $track_ids"
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then

  echo "Select Matroska file(s) to apply removal:"
  typeset -a targets
  targets=()
  # Read fzf multi-selection into targets array (zsh-compatible)
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
    typeset -a targets
    targets=("$source_file")
  fi

  for target in "${targets[@]}"; do
    echo Processing file: $(basename "$target")
    src_base=${target##*/}; base=${src_base%.*}; ext=${src_base##*.}
    [ ${#video_keep[@]} -eq 0 ] && out_ext="mka" || out_ext="$ext"
    tmp="${base}_temp.${out_ext}"

    cmd=(mkvmerge -o "$tmp")
    [[ ${#video_keep[@]} -gt 0 ]] && cmd+=(--video-tracks "$(IFS=,; echo ${video_keep[*]})") || cmd+=(--no-video)
    [[ ${#audio_keep[@]} -gt 0 ]] && cmd+=(--audio-tracks "$(IFS=,; echo ${audio_keep[*]})") || cmd+=(--no-audio)
    [[ ${#subtitle_keep[@]} -gt 0 ]] && cmd+=(--subtitle-tracks "$(IFS=,; echo ${subtitle_keep[*]})") || cmd+=(--no-subtitles)
    cmd+=("$target")

    echo "Executing: ${cmd[*]}"
    "${cmd[@]}" || { echo "Error during mkvmerge on $target. Skipping."; rm -f "$tmp"; continue; }
    mv "$tmp" "${base}.${out_ext}"
    echo "Replaced file: ${base}.${out_ext}"
    # If extension changed (e.g., mkv->mka), remove the original source file
    if [ "$out_ext" != "$ext" ]; then
      echo "Removed source file: $(basename "$target")"
      rm -f "$target"
    fi
  done

elif [ "$choice" = "9" ]; then
  # Option 9: Reorder tracks via mkvmerge
  print -n "Enable multi-file target selection? (Y/N) [N]: "
  read MULTI_FILE_SELECTION
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:-N}
  MULTI_FILE_SELECTION=${MULTI_FILE_SELECTION:u}

  # Select source file for track IDs
  echo "Select the source Matroska file (.mkv, .mka, .mks, .mk3d) to pull track IDs:"
  source_file=$(find . -maxdepth 1 -type f \
    \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf --height 40% --reverse --border --prompt="Select Matroska file > ")
  [ -z "$source_file" ] && { echo "No file selected. Exiting."; exit 1; }

  # Identify tracks and get full JSON metadata
  info_json=$(mkvmerge -J "$source_file")

  echo "Tracks found:"
  echo "$info_json" \
    | jq -c '.tracks[]' \
    | while IFS= read -r track; do
        id=$(   echo "$track" | jq '.id')
        type=$( echo "$track" | jq -r '.type')
        codec=$(echo "$track" | jq -r '.properties.codec_id')
        name=$( echo "$track" | jq -r '.properties.track_name // empty')
        lang=$( echo "$track" | jq -r '.properties.language   // empty')

        line="Track ID ${id}: ${type} (${codec})"
        [[ -n $name ]] && line+=" [${name}]"
        if [[ -n $lang ]]; then
          if [[ -n $name ]]; then
            line+=" - [${lang}]"
          else
            line+=" [${lang}]"
          fi
        fi
        echo "$line"
      done

  # Prompt for new order
  printf "Enter the new track order (e.g., 0:0,0:1,0:2,0:4,0:5,0:6,0:3): "
  read track_order

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply reorder:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    [ ${#targets[@]} -eq 0 ] && { echo "No target files selected. Exiting."; exit 1; }
  else
    targets=("$source_file")
  fi

  # Apply reordering
  for target in "${targets[@]}"; do
    echo "Processing file: $(basename "$target")"
    src_base=${target##*/}
    base=${src_base%.*}
    ext=${src_base##*.}
    tmp="${base}_temp.${ext}"

    cmd=(mkvmerge -o "$tmp" --track-order "$track_order")
    cmd+=("$target")

    echo "Executing: ${cmd[*]}"
    "${cmd[@]}" || { echo "Error during mkvmerge on $target. Skipping."; rm -f "$tmp"; continue; }

    mv "$tmp" "${base}.${ext}"
    echo "Replaced file: ${base}.${ext}"
  done

else
  echo "Invalid choice."
fi