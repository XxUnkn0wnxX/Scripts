#!/usr/local/bin/zsh

 # Required third-party tools:
 # - mkvmerge, mkvinfo, mkvextract, mkvpropedit: for remuxing, inspecting, extracting,
 #   and editing tracks and metadata in Matroska files
 # - ffmpeg (and ffprobe): for multimedia processing, such as boosting audio volume and verifying video streams
 # - fzf: for interactive file selection via fuzzy finding
 # - jq: for processing JSON output (mkvmerge -J)
 # - rsync: for creating backups in safe mode

# Install these tools using Homebrew with the following command:
# brew install mkvtoolnix ffmpeg fzf jq rsync

# Global variables for signal handling
CHOICE=""
SOURCE_FILE=""
BACKUP_FILE=""
WORK_DIR=""
MKVMERGE_RUNNING=false
MKVMERGE_PID=""
RSYNC_PID=""
FFMPEG_PID=""
TEMP_FILE=""

# Handler for Ctrl+C
handle_ctrl_c() {
  trap '' INT
  echo
  case "$CHOICE" in
    2|5)
      # Cancel remux or edit operations: kill any mkvmerge, remove temp file, and cleanup backup
      if [ -n "$MKVMERGE_PID" ]; then
        kill -9 $MKVMERGE_PID 2>/dev/null
      fi
      if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
        rm -f "$TEMP_FILE"
      fi
      # If safe mode was used to create a backup, delete the original backup file
      if [ "$safe_mode_write" = true ] && [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        echo "Deleting backup file: $BACKUP_FILE"
        rm -f "$BACKUP_FILE"
      fi
      exit 0
      ;;
    3)
      # If in-progress, wait for mkvmerge or rsync accordingly
      if [ "$safe_mode_write" != true ] && [ "$MKVMERGE_RUNNING" = true ]; then
        echo "Ctrl+C detected: waiting for mkvmerge to finish..."
        return
      fi
      # Kill any ongoing mkvmerge to prevent sanitize warnings
      if [ -n "$MKVMERGE_PID" ]; then
        kill -9 $MKVMERGE_PID 2>/dev/null
      fi
      # Kill any ongoing rsync during backup
      if [ -n "$RSYNC_PID" ]; then
        kill -9 $RSYNC_PID 2>/dev/null
      fi
      # Restore backup in safe mode
      if [ "$safe_mode_write" = true ] && [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        echo "Restoring backup: $BACKUP_FILE -> $SOURCE_FILE"
        mv "$BACKUP_FILE" "$SOURCE_FILE"
      fi
      # Cleanup working directory
      if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        echo "Removing temporary directory: $WORK_DIR"
        rm -rf "$WORK_DIR"
      fi
      exit 0
      ;;
    4)
      # If a mkvmerge removal is in progress (non-safe mode), wait till it finishes
      if [ "$safe_mode_write" != true ] && [ "$MKVMERGE_RUNNING" = true ]; then
        echo "Ctrl+C detected: waiting for mkvmerge to finish..."
        return
      fi
      # Kill any ongoing mkvmerge to prevent sanitize warnings
      if [ -n "$MKVMERGE_PID" ]; then
        kill -9 $MKVMERGE_PID 2>/dev/null
      fi
      # Kill any ongoing rsync
      if [ -n "$RSYNC_PID" ]; then
        kill -9 $RSYNC_PID 2>/dev/null
      fi
      # Remove temporary file created by mkvmerge
      if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
        echo "Removing temporary file: $TEMP_FILE"
        rm -f "$TEMP_FILE"
      fi
      exit 0
      ;;
    *)
      exit 1
      ;;
  esac
}
trap 'handle_ctrl_c' INT

# Global variable for safe mode
safe_mode_write="${safe_mode_write:-true}"  # Set to true by default if not set in the environment
thread_count=8  # Hard-coded to use 8 threads
# ——————————————————————————————
# Extension overrides for Plex/VLC (audio only)
typeset -A ext_override=(
  ["A_AAC"]="aac"                # AAC audio → .aac
  ["A_AC3"]="ac3"                # AC-3 (Dolby Digital) → .ac3
  ["A_DTS"]="dts"                # DTS audio → .dts
  ["A_PCM/INT/LIT"]="pcm"        # PCM → .pcm
  ["A_OPUS"]="opus"              # Opus → .opus
  ["A_MPEG/L3"]="mp3"            # MPEG-1/2 Layer III → .mp3
)
# ——————————————————————————————

# Open file descriptor 3 for the controlling terminal (used to flush input)
# Try to attach FD3 to /dev/tty (suppress errors for this attempt only)
{ exec 3</dev/tty; } 2>/dev/null || true
# Function to flush pending terminal input (ignore keystrokes during external commands)
flush_input() {
  local _c
  # Read and discard any pending characters from FD3 (/dev/tty)
  while read -u 3 -t 0 -k 1 _c; do :; done
}

# Function to print the help message
print_help() {
  echo "Usage: [options] <file>"
  echo ""
  echo "Options:"
  echo "  -h, --help               Display this help message."
  echo "  -y <file>                Remux to MKV, overwriting the existing file if it exists."
}


# Function to remove the temporary directory
remove_temp_dir() {
  local temp_dir="$1"
  rm -rf "$temp_dir"
}

# Function to remux a video file to MKV, replacing the original file
remux_to_mkv() {
  local source_file="$1"
  local overwrite_flag="$2"
  local temp_file="${source_file%.*}_temp.mkv"
  local output_file

  if [ "$safe_mode_write" = true ]; then
    if [ "$overwrite_flag" = "-y" ]; then
      echo "Error: safe mode enabled. Remuxing and overwriting are not allowed."
      exit 1
    fi
    # In safe mode, generate a new output file name to avoid overwriting
    local base_name="${source_file%.*}_remuxed"
    local i=1
    output_file="${base_name} (${i}).mkv"
    while [ -f "$output_file" ]; do
      ((i++))
      output_file="${base_name} (${i}).mkv"
    done
  else
    output_file="${source_file%.*}.mkv"
  fi

  if [ -f "$output_file" ] && [ "$safe_mode_write" != true ]; then
    if [ "$overwrite_flag" = "-y" ]; then
      echo "Overwriting existing file: $output_file"
    elif [ -z "$overwrite_flag" ]; then
      echo "Error: File $output_file already exists. Use -y option to overwrite."
      exit 1
    else
      echo "Warning: File $output_file already exists. Do you wish to replace it? (Y/N): "
      flush_input
      read overwrite_choice

      case "$overwrite_choice" in
        Y|y)
          echo "Overwriting existing file: $output_file"
          ;;
        N|n)
          echo "Operation aborted. File not overwritten."
          exit 1
          ;;
        *)
          echo "Invalid choice. Operation aborted."
          exit 1
          ;;
      esac
    fi
  fi

  echo "Remuxing $source_file to $temp_file..."
  # In non-safe mode, disable Ctrl+C so mkvmerge can't be interrupted (no sanitize warnings)
  TEMP_FILE="$temp_file"
  MKVMERGE_RUNNING=true
  if [ "$safe_mode_write" != true ]; then
    stty intr ''
    mkvmerge -o "$temp_file" "$source_file" < /dev/null
    ret=$?
    stty intr ^C
  else
    mkvmerge -o "$temp_file" "$source_file" < /dev/null
    ret=$?
  fi
  MKVMERGE_RUNNING=false
  if [ $ret -ne 0 ]; then
    [ -f "$TEMP_FILE" ] && rm -f "$TEMP_FILE"
    return 1
  fi
  echo "Remuxing completed: $temp_file"

  # Replace the original file with the remuxed file
  mv "$temp_file" "$output_file"
  echo "Replaced the original file with the remuxed file: $output_file"
}

# Helper for ffmpeg full audio re-encode for all tracks (all tracks, all names/langs preserved, temp work dir auto-cleans)
reencode_all_audio_tracks_aac_ffmpeg() {
  local source_file="$1"
  local output_file="$2"
  local src_basename="${source_file##*/}"
  local base_name="${src_basename%.*}"
  local WORK_DIR="${base_name}_temp"
  rm -rf "$WORK_DIR" && mkdir -p "$WORK_DIR"

  local -a audio_tracks
  local -a audio_metadata
  local -a mkvmerge_audio_opts
  local audio_idx=0
  local ret=0

  while IFS="|" read -r idx codec lang name; do
    audio_tracks+=("$idx")
    audio_metadata+=("$codec|$lang|$name")
  done < <(
    ffprobe -loglevel error \
            -select_streams a \
            -show_entries stream=index,codec_name:stream_tags=language,title \
            -of csv="p=0" "$source_file" \
    | awk -F',' '{OFS="|"; print $1, $2, $3, $4}'
  )

  if [ ${#audio_tracks[@]} -eq 0 ]; then
    echo "No audio tracks found; skipping audio re-encode."
    ffmpeg -nostdin -y -i "$source_file" -map 0 -c copy "$output_file"
    rm -rf "$WORK_DIR"
    return $?
  fi

  for idx in "${audio_tracks[@]}"; do
    local meta="${audio_metadata[$audio_idx]}"
    local _codec="$(echo "$meta" | cut -d'|' -f2)"
    local _lang="$(echo "$meta" | cut -d'|' -f3)"
    local _name="$(echo "$meta" | cut -d'|' -f4)"
    local out_audio="$WORK_DIR/${base_name}_track${idx}.m4a"

    ffmpeg -nostdin -y \
           -i "$source_file" \
           -vn \
           -map 0:a:$audio_idx \
           -c:a aac \
           -q:a 0 \
           -threads "$thread_count" \
           "$out_audio"

    local lang_opt=""
    if [ -n "$_lang" ]; then
      lang_opt="--language 0:$_lang"
    fi

    local name_opt=""
    if [ -n "$_name" ]; then
      name_opt="--track-name 0:$_name"
    fi

    mkvmerge_audio_opts+=("$lang_opt" "$name_opt" "$out_audio")
    ((audio_idx++))
  done

  local mkvmerge_json="$WORK_DIR/mkvinfo.json"
  mkvmerge -J "$source_file" > "$mkvmerge_json"

  local non_audio_tracks
  non_audio_tracks=$(
    jq -r '
      .tracks[] |
      select(.type != "audio") |
      "--language \(.id):\(.properties.language // \"und\") " +
      "--track-name \(.id):\(.properties.track_name // \"\") " +
      "--default-track \(.id):" + (if .properties.default_track_id==1 then "yes" else "no" end) + " " +
      "--forced-track \(.id):" + (if .properties.forced_track_id==1 then "yes" else "no" end) + " " +
      "--no-audio --no-chapters --no-tags --tracks \(.id)\n"
    ' "$mkvmerge_json" | tr '\n' ' '
  )

  local cmd=(mkvmerge -o "$output_file")
  cmd+=( $non_audio_tracks )

  for ((i=0; i<${#mkvmerge_audio_opts[@]}; i+=3)); do
    local ao1="${mkvmerge_audio_opts[$i]}"
    local ao2="${mkvmerge_audio_opts[$i+1]}"
    local afile="${mkvmerge_audio_opts[$i+2]}"
    cmd+=( $ao1 $ao2 "$afile" )
  done

  echo "Muxing output..."
  "${cmd[@]}"
  ret=$?

  rm -rf "$WORK_DIR"
  return $ret
}

# New version of remux_to_mkv_ffmpeg to remux with ffprobe-based stream detection and mapping
remux_to_mkv_ffmpeg() {
  local source_file="$1"
  local overwrite_flag="${2:-}"
  local replace_audio_tracks="${3:-N}"
  local output_file

  if [ "$safe_mode_write" = "true" ]; then
    local base="${source_file%.*}_remuxed"
    local i=1
    output_file="${base} (${i}).mkv"
    while [ -f "$output_file" ]; do
      ((i++))
      output_file="${base} (${i}).mkv"
    done
  else
    output_file="${source_file%.*}.mkv"
  fi

  if [ "$safe_mode_write" != "true" ] && [ -f "$output_file" ] && [ "$overwrite_flag" != "-y" ]; then
    printf "Warning: File %s already exists. Overwrite? (Y/N): " "$output_file"
    read resp
    resp=${resp:-N}
    case "$resp" in
      [Yy]*)
        echo "Overwriting $output_file…"
        ;;
      *)
        echo "Aborted; $output_file not changed."
        return 1
        ;;
    esac
  fi

  local ret=0

  if [ "$replace_audio_tracks" = "Y" ] || [ "$replace_audio_tracks" = "y" ]; then
    if ! reencode_all_audio_tracks_aac_ffmpeg "$source_file" "$output_file"; then
      echo "Error: Audio re-encode failed for $source_file."
      return 1
    fi
    return 0
  fi

  local map_opts=()

  if ffprobe -v error -select_streams v -show_entries stream=index -of csv=p=0 "$source_file" 2>/dev/null | grep -q .; then
    map_opts+=( -map 0:v )
  fi

  if ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$source_file" 2>/dev/null | grep -q .; then
    map_opts+=( -map 0:a )
  fi

  if ffprobe -v error -select_streams s -show_entries stream=index -of csv=p=0 "$source_file" 2>/dev/null | grep -q .; then
    map_opts+=( -map 0:s )
  fi

  map_opts+=( -map '0:t?' )

  echo "Remuxing → $output_file  (maps: ${map_opts[*]})"
  ffmpeg -nostdin -y -i "$source_file" \
         "${map_opts[@]}" \
         -map_metadata 0 \
         -map_chapters 0 \
         -c copy \
         "$output_file"

  if [ $? -ne 0 ]; then
    echo "Error: ffmpeg remux failed."
    rm -f "$output_file" 2>/dev/null
    return 1
  fi

  echo "Done: $output_file"
  return 0
}


# Function to boost audio volume
boost_audio_volume() {
  local source_file="$1"
  local track_id="$2"
  local volume_changes="$3"
  local codec_extension="$4"
  local safe_mode_write="${5:-false}" # Default to false if not provided
  # Determine output extension matching source (e.g., mkv, mka, mks, mk3d)
  local ext="${source_file##*.}"
  local output_file="${source_file%.*}.${ext}"
  local boost_success=true # Flag to check if boosting was successful

  # Create temporary working directory based on source file name
  local src_basename="${source_file##*/}"
  local base_name="${src_basename%.*}"
  local work_dir="${base_name}_temp"
  # Clean up any existing temp directory and create a fresh one
  rm -rf "$work_dir"
  mkdir -p "$work_dir"
  echo "Created temporary working directory: $work_dir"

  # Split volume_changes into an array
  local -a volume_change_array
  IFS=',' read -r -A volume_change_array <<< "$volume_changes"

  # Extract original audio track into a uniquely named file
  local extracted_file="${work_dir}/${base_name}_source-audio.${codec_extension}"
  echo "Extracting audio track ID $track_id from $source_file..."
  mkvextract tracks "$source_file" "${track_id}:${extracted_file}" < /dev/null
  echo "Extracted audio track to $extracted_file"

  # Loop over each volume change, create a boosted audio file, and remux it
  for volume_change in "${volume_change_array[@]}"; do
    # Ensure the volume_change doesn't already include "dB"
    local clean_volume_change="${volume_change//dB/}"
    # Name boosted audio files based on source filename and dB change
    local boosted_file="${work_dir}/${base_name}_${clean_volume_change}dB.aac"
    local track_name="${clean_volume_change}dB"

    echo "Boosting volume by ${clean_volume_change}dB..."
    # Prepare to catch Ctrl+C and kill ffmpeg immediately
    FFMPEG_PID=""
    trap 'kill -9 $FFMPEG_PID 2>/dev/null; handle_ctrl_c' INT
    # Run ffmpeg in background so it won’t be in the foreground process group
    ffmpeg -nostdin -y -i "$extracted_file" -filter:a "volume=${clean_volume_change}dB" -c:a aac -q:a 0 -threads "$thread_count" "$boosted_file" &
    FFMPEG_PID=$!
    wait $FFMPEG_PID
    ret=$?
    # Restore the global Ctrl+C handler
    trap 'handle_ctrl_c' INT
    if [ $ret -ne 0 ]; then
      echo "Error: Boosting volume failed for ${clean_volume_change}dB."
      boost_success=false
      continue
    fi
    echo "Boosted audio saved to $boosted_file"

    # Remux the boosted audio back into the original file
    # Temporary MKV/MKA file with boosted audio in the working directory
    local temp_file="${work_dir}/${base_name}_${clean_volume_change}dB_temp.${ext}"
    echo "Remuxing the boosted audio back to $temp_file..."
    TEMP_FILE="$temp_file"
    MKVMERGE_RUNNING=true
    if [ "$safe_mode_write" != true ]; then
      # Non-safe: disable Ctrl+C so mkvmerge runs uninterrupted, then restore
      stty intr ''
      mkvmerge -o "$temp_file" --track-name "0:$track_name" "$boosted_file" "$source_file" < /dev/null
      ret=$?
      stty intr ^C
    else
      # Safe mode: allow immediate interrupt
      mkvmerge -o "$temp_file" --track-name "0:$track_name" "$boosted_file" "$source_file" < /dev/null
      ret=$?
    fi
    MKVMERGE_RUNNING=false
    if [ $ret -ne 0 ]; then
      # Cleanup partial file and abort
      [ -f "$TEMP_FILE" ] && rm -f "$TEMP_FILE"
      exit 0
    fi

    if [ -f "$temp_file" ]; then
      mv "$temp_file" "$output_file"
      echo "New file with boosted audio: $output_file"
    else
      echo "Error: Remuxing failed, temporary file not found."
      boost_success=false
      rm "$boosted_file"
      continue
    fi

    # Clean up
    rm "$boosted_file"
  done

  rm "$extracted_file"
  echo "Temporary files removed."

  # Clean up temporary working directory
  remove_temp_dir "$work_dir"
  echo "Removed temporary working directory: $work_dir"

  # Return status of the function
  if [ "$boost_success" = true ]; then
    return 0
  else
    return 1
  fi
}

# Function to handle file movements in safe mode
boost_audio_volume_safe_sorting() {
  local source_file="$1"
  local safe_mode_write="$2"

  # Only proceed if safe_mode_write is true
  if [ "$safe_mode_write" = true ]; then
    # Determine extension for boosted file, matching source
    local ext="${source_file##*.}"
    local count=1
    local boosted_file_name="${source_file%.*}_boosted (${count}).${ext}"

    # Increment the number if the boosted file already exists
    while [ -f "$boosted_file_name" ]; do
      count=$((count + 1))
      boosted_file_name="${source_file%.*}_boosted (${count}).${ext}"
    done

    # Rename the source file to the boosted file name
    echo "Renaming original file to $boosted_file_name"
    mv "$source_file" "$boosted_file_name"
    if [ $? -ne 0 ]; then
      echo "Error: Failed to rename original file to $boosted_file_name"
      return 1
    fi

    # Restore the backup as the original source file
    local backup_file="${source_file%.*}_original.mkv"
    if [ -f "$backup_file" ]; then
      echo "Restoring backup file $backup_file to $source_file"
      mv "$backup_file" "$source_file"
      if [ $? -ne 0 ]; then
        echo "Error: Failed to restore backup file $backup_file to $source_file"
        return 1
      fi
      echo "Backup restored successfully."
    else
      echo "Error: Backup file $backup_file not found. Exiting."
      return 1
    fi
  fi
}

# Function to create a backup of the original file
create_backup() {
  local source_file="$1"
  # Determine extension of source file
  local ext="${source_file##*.}"
  # Initial backup filename
  local backup_file="${source_file%.*}_original.${ext}"
  local count=2

  # Check if the backup file already exists and increment the count if it does
  while [ -f "$backup_file" ]; do
    backup_file="${source_file%.*}_original ${count}.${ext}"
    count=$((count + 1))
  done

  # Create the backup using rsync, showing progress
  echo "Creating a backup of the original file as $backup_file"
  echo "Rsync Copy"
  rsync -ah --info=progress2 "$source_file" "$backup_file" < /dev/null
  if [ $? -eq 0 ]; then
    echo "\nBackup created successfully."
    BACKUP_FILE="$backup_file"
  else
    echo "\nError: Failed to create backup. Exiting."
    return 1
  fi
}


# Function to check if the file has a Matroska extension
validate_mkv_extension() {
  local filename="$1"
  case "${filename##*.}" in
    mkv|mka|mks|mk3d) return 0 ;;  # Supported Matroska containers
    *) return 1 ;;
  esac
}
# Function to display track information safely, projecting only needed fields
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
        | "Track ID \(.id): \(.type) (\(.codec))" +
          (if .name != "" then " [\(.name)]" else "" end) +
          (if .lang != "" then " [\(.lang)]" else "" end)
      '
}

# Function to collect audio tracks into $audio_tracks_arr safely
collect_audio_tracks() {
  local source_file="$1"

  echo "Identifying audio tracks in $source_file..."
  # Stream mkvmerge JSON straight into jq, selecting only audio tracks and
  # projecting id, codec_id, track_name, and language—any other properties
  # (including control-character ones) are ignored.
  mkvmerge -J "$source_file" < /dev/null \
    | jq -r '
        .tracks[]
        | select(.type=="audio")
        | {
            id:    .id,
            codec: .properties.codec_id,
            name:  (.properties.track_name // ""),
            lang:  (.properties.language // .properties.language_ietf // "")
          }
        | "Track ID \(.id): audio (\(.codec))"
          + (if .name != "" then " [\(.name)]" else "" end)
          + (if .lang != "" then " [\(.lang)]" else "" end)
      ' \
    | while IFS= read -r line; do
        audio_tracks_arr+=("$line")
      done
}

#Function to rename tracks using mkvpropedit
rename_tracks() {
  local source_file="$1"
  local track_ids="$2"

  # Split track_ids by comma and space
  IFS=', ' read -rA ids <<< "$track_ids"
  
  # Loop over each track ID
  for id in "${ids[@]}"; do
    # Check if it's a range (e.g., 1-3)
    if [[ $id == *-* ]]; then
      local start=$(echo $id | cut -d '-' -f 1)
      local end=$(echo $id | cut -d '-' -f 2)
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Name ---------------------"
        printf "Name: "
        flush_input
        read name
        # Run mkvpropedit uninterruptibly
        (trap '' SIGINT; exec mkvpropedit "$source_file" --edit track:$((i+1)) --set name="$name" < /dev/null)
      done
    else
      echo "--------------------  Track ID $id Name ---------------------"
      printf "Name: "
      flush_input
      read name
      # Run mkvpropedit uninterruptibly
      (trap '' SIGINT; exec mkvpropedit "$source_file" --edit track:$((id+1)) --set name="$name" < /dev/null)
    fi
  done
}

# Main script
# Use the directory from which the script was invoked as the working directory
current_dir="$(pwd)"
echo "Current Work Dir: $current_dir"
cd "$current_dir" || exit 1

# Command-line arguments handling
if [ $# -gt 0 ]; then
  if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    print_help
    exit 0
  fi

  if [ "$safe_mode_write" = true ]; then
    echo "Error: safe mode enabled, please use the menu instead."
    exit 1
  fi

  # If not in safe mode, continue with command-line argument processing
  if [ "$1" = "-y" ]; then
    if [ $# -lt 2 ]; then
      echo "Error: No input file provided after -y option."
      exit 1
    fi
    remux_to_mkv "$2" "-y"
  else
    remux_to_mkv "$1"
  fi
else
  # No arguments provided, ask for input via the menu
  echo "Select an option:"
  echo "1) Remux to MKV (ffmpeg)"
  echo "2) Remux to MKV"
  echo "3) Volume Boost"
  echo "4) Remove Tracks"
  echo "5) Edit Tracks"
  printf "Enter choice: "
  flush_input
  read choice
  CHOICE="$choice"

  if [ "$choice" -eq 1 ]; then
    echo "Select the source video files (use Tab or Shift+Tab to select multiple):"
    
    # Use fzf to select one or multiple files
    IFS=$'\n' video_files=($(find . -maxdepth 1 -type f | fzf --height 40% --reverse --border --multi))
    
    # Check if any files were selected
    if [ ${#video_files[@]} -eq 0 ]; then
      echo "No files selected. Exiting."
      exit 1
    fi

    # Iterate over each selected file and pass it to the remux_to_mkv_ffmpeg function (no ffprobe check)
    for source_file in "${video_files[@]}"; do
      source_file="${source_file#./}"  # Remove leading ./ if present
      
      if ! remux_to_mkv_ffmpeg "$source_file" "prompt"; then
        echo "Error processing \"$source_file\". Skipping."
      fi
    done
  
  elif [ "$choice" -eq 2 ]; then
    echo "Select the source video files (use Tab or Shift+Tab to select multiple):"
    
    # Use fzf to select one or multiple files
    IFS=$'\n' video_files=($(find . -maxdepth 1 -type f | fzf --height 40% --reverse --border --multi))
    
    # Check if any files were selected
    if [ ${#video_files[@]} -eq 0 ]; then
      echo "No files selected. Exiting."
      exit 1
    fi

    # Iterate over each selected file and pass it to the remux_to_mkv function
    for source_file in "${video_files[@]}"; do
      source_file="${source_file#./}"  # Remove leading ./ if present
      
      # Verify the file is a video file using ffprobe
      if ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "$source_file" < /dev/null 2>/dev/null | grep -q '^video'; then
        if ! remux_to_mkv "$source_file" "prompt"; then
          echo "Error processing \"$source_file\". Skipping."
        fi
      else
        echo "Warning: Skipping non-video file \"$source_file\"."
      fi
    done

  elif [ "$choice" -eq 3 ]; then
    local source_file=""
    while true; do
      printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
      source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) | fzf --height 40% --reverse --border)
      if [ -z "$source_file" ]; then
        echo "No file selected. Exiting."
        exit 1
      fi
      validate_mkv_extension "$source_file"
      if [ $? -eq 0 ]; then
        break
      else
        echo "Invalid input. Please select a valid .mkv file."
      fi
    done

    # Set context for signal handler
    SOURCE_FILE="$source_file"
    WORK_DIR="${source_file%.*}_temp"

    # Ensure backup is created if in safe mode
    if [ "$safe_mode_write" = true ]; then
      create_backup "$source_file"
      if [ $? -ne 0 ]; then
        echo "Error: Failed to create backup. Exiting."
        exit 1
      fi
    fi

    # Identify audio tracks via JSON and jq
    local -a audio_tracks_arr
    collect_audio_tracks "$source_file"
    local audio_count=${#audio_tracks_arr[@]}

    if [ "$audio_count" -eq 0 ]; then
      echo "No audio tracks found in the file."
      exit 1
    fi

    # Print the audio tracks found
    echo "Audio tracks found:"
    for entry in "${audio_tracks_arr[@]}"; do
      echo "$entry"
    done

    # Prompt the user to select the Track ID if multiple
    if [ "$audio_count" -eq 1 ]; then
      track_info="${audio_tracks_arr[1]}"
    else
      printf "Enter the Track ID to extract: "
      flush_input
      read track_id
      track_info=""
      for entry in "${audio_tracks_arr[@]}"; do
        if [[ $entry == "Track ID $track_id:"* ]]; then
          track_info="$entry"
          break
        fi
      done
    fi

    # Extract codec and track ID
    codec=$(echo "$track_info" | awk '{print $5}' | tr -d '()')
    track_id=$(echo "$track_info" | awk '{print $3}' | tr -d ':')

    # Determine file extension via ext_override, or fall back to codec suffix
    if [[ -n "${ext_override[$codec]}" ]]; then
      codec_extension="${ext_override[$codec]}"
    else
      key="${codec##*/}"     # strip off everything before the last “/”
      # In Z-shell, `${var:l}` lowercases var
      codec_extension=${ext_override[$key]:-${key:l}}
    fi

    printf "Enter the amount of dB to change (e.g., 2dB,3.5dB,-5dB): "
    flush_input
    read volume_changes

    # Call the function to boost audio volume
    boost_audio_volume "$source_file" "$track_id" "$volume_changes" "$codec_extension" "$safe_mode_write"

    # Check if boost_audio_volume completed successfully and safe_mode_write is true
    if [ $? -eq 0 ] && [ "$safe_mode_write" = true ]; then
      boost_audio_volume_safe_sorting "$source_file" "$safe_mode_write"
    fi


  elif [ "$choice" -eq 4 ]; then
    local source_file=""
    while true; do
      printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
      source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) | fzf --height 40% --reverse --border)
      if [ -z "$source_file" ]; then
        echo "No file selected. Exiting."
        exit 1
      fi
      validate_mkv_extension "$source_file"
      if [ $? -eq 0 ]; then
        break
      else
        echo "Invalid input. Please select a valid .mkv file."
      fi
    done

    # Set context for signal handler
    SOURCE_FILE="$source_file"

    # Show all tracks via the unified helper (projects only the fields we need)
    display_track_info "$source_file"

    printf "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): "
    flush_input
    read track_ids

    # Convert track_ids to an array (handling ranges)
    exclude_ids=()
    IFS=',' read -r raw_ids_str <<< "$track_ids"
    raw_ids=(${(s:,:)raw_ids_str})
    for id in "${raw_ids[@]}"; do
      if [[ $id == *-* ]]; then
        range_start=${id%-*}; range_end=${id#*-}
        for ((i=range_start; i<=range_end; i++)); do
          exclude_ids+=($i)
        done
      else
        exclude_ids+=($id)
      fi
    done
    # Remove duplicates and sort
    exclude_ids=($(printf "%s\n" "${exclude_ids[@]}" | sort -n | uniq))

    # Read track info JSON and group IDs by type, streaming directly into jq
    local -a video_ids audio_ids subtitle_ids
    video_ids=($(mkvmerge -J "$source_file" < /dev/null \
                   | jq -r '.tracks[] | select(.type=="video")      | .id'))
    audio_ids=($(mkvmerge -J "$source_file" < /dev/null \
                   | jq -r '.tracks[] | select(.type=="audio")      | .id'))
    subtitle_ids=($(mkvmerge -J "$source_file" < /dev/null \
                   | jq -r '.tracks[] | select(.type=="subtitles") | .id'))

    # Build lists of tracks to keep
    video_keep=()
    for id in "${video_ids[@]}"; do
      if [[ ! " ${exclude_ids[@]} " =~ " $id " ]]; then video_keep+=($id); fi
    done
    audio_keep=()
    for id in "${audio_ids[@]}"; do
      if [[ ! " ${exclude_ids[@]} " =~ " $id " ]]; then audio_keep+=($id); fi
    done
    subtitle_keep=()
    for id in "${subtitle_ids[@]}"; do
      if [[ ! " ${exclude_ids[@]} " =~ " $id " ]]; then subtitle_keep+=($id); fi
    done

    # Prepare temporary output filename using correct extension
    src_basename=${source_file##*/}
    base_name=${src_basename%.*}
    # Determine output extension: if no video tracks, use .mka, else keep original
    input_ext="${source_file##*.}"
    if [ ${#video_keep[@]} -eq 0 ]; then
      out_ext="mka"
    else
      out_ext="$input_ext"
    fi
    temp_file="${base_name}_temp.${out_ext}"
    # Record temp file for cleanup on interrupt
    TEMP_FILE="$temp_file"

    # Assemble mkvmerge command to preserve metadata and track order
    echo "Removing tracks: $track_ids"
    cmd=(mkvmerge -o "$temp_file")
    # Video tracks: keep listed or exclude all
    if [ ${#video_keep[@]} -gt 0 ]; then
      vl=$(IFS=,; echo "${video_keep[*]}")
      cmd+=(--video-tracks "$vl")
    else
      cmd+=(--no-video)
    fi
    # Audio tracks: keep listed or exclude all
    if [ ${#audio_keep[@]} -gt 0 ]; then
      al=$(IFS=,; echo "${audio_keep[*]}")
      cmd+=(--audio-tracks "$al")
    else
      cmd+=(--no-audio)
    fi
    # Subtitle tracks: keep listed or exclude all
    if [ ${#subtitle_keep[@]} -gt 0 ]; then
      sl=$(IFS=,; echo "${subtitle_keep[*]}")
      cmd+=(--subtitle-tracks "$sl")
    else
      cmd+=(--no-subtitles)
    fi
    # Input file
    cmd+=("$source_file")

    # Run mkvmerge to remove tracks
    TEMP_FILE="$temp_file"
    MKVMERGE_RUNNING=true
    echo "Executing: ${cmd[*]}"
    if [ "$safe_mode_write" != true ]; then
      # Non-safe: disable Ctrl+C so mkvmerge finishes uninterrupted
      stty intr ''
      "${cmd[@]}"
      ret=$?
      stty intr ^C
    else
      # Safe mode: allow immediate interrupt
      "${cmd[@]}"
      ret=$?
    fi
    MKVMERGE_RUNNING=false
    if [ $ret -ne 0 ]; then
      # Cleanup temp file if interrupted or failed
      [ -f "$TEMP_FILE" ] && rm -f "$TEMP_FILE"
      echo "Error: mkvmerge failed to remove tracks."
      exit 1
    fi

    # Finalize output: safe mode vs overwrite
    if [ "$safe_mode_write" = true ]; then
      count=1
      output_file="${base_name}_removed (${count}).${out_ext}"
      while [ -f "$output_file" ]; do
        ((count++))
        output_file="${base_name}_removed (${count}).${out_ext}"
      done
      mv "$temp_file" "$output_file"
      echo "Created removed-version: $output_file"
    else
      # Overwrite original: remove it then rename temp to original base_name.ext
      # Disable Ctrl+C during cleanup
      trap '' INT
      rm -f "$source_file"
      mv "$temp_file" "${base_name}.${out_ext}"
      echo "Replaced original file: ${base_name}.${out_ext}"
      # Restore Ctrl+C handler
      trap 'handle_ctrl_c' INT
    fi
    
  elif [ "$choice" -eq 5 ]; then
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi

    # Check for safe_mode_write and create backup if true
    if [ "$safe_mode_write" = true ]; then
      echo "Safe mode is enabled. Creating a backup..."
      create_backup "$source_file"
      if [ $? -ne 0 ]; then
        echo "Error: Failed to create backup. Exiting."
        exit 1
      fi
    fi

    display_track_info "$source_file"

    printf "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): "
    flush_input
    read track_ids

    # Edit track names (SIGINT enabled during prompts, disabled during mkvpropedit)
    rename_tracks "$source_file" "$track_ids"

  else
    echo "Invalid choice."
    exit 1
  fi
fi

