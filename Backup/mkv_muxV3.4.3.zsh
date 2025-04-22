#!/usr/local/bin/zsh

# Required third-party tools:
# - mkvmerge: for remuxing and identifying tracks in MKV files
# - mkvextract: for extracting specific tracks from MKV files
# - mkvpropedit: for editing properties of existing Matroska files
# - ffmpeg: for multimedia processing, such as boosting audio volume
# - fzf: for interactive file selection using fuzzy finding
# - jq: for processing JSON output

# Install these tools using Homebrew with the following command:
# brew install mkvtoolnix ffmpeg fzf jq

# Global variable for safe mode
safe_mode_write="${safe_mode_write:-true}"  # Set to true by default if not set in the environment
thread_count=8  # Hard-coded to use 8 threads

# Function to print the help message
print_help() {
  echo "Usage: [options] <file>"
  echo ""
  echo "Options:"
  echo "  --help                   Display this help message."
  echo "  -y <file>                Remux to MKV, overwriting the existing file if it exists."
}

# Function to create a temporary directory
create_temp_dir() {
  local temp_dir="temp"
  mkdir -p "$temp_dir"
  echo "$temp_dir"
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
  mkvmerge -o "$temp_file" "$source_file"
  echo "Remuxing completed: $temp_file"

  # Replace the original file with the remuxed file
  mv "$temp_file" "$output_file"
  echo "Replaced the original file with the remuxed file: $output_file"
}

# Function to boost audio volume
boost_audio_volume() {
  local source_file="$1"
  local track_id="$2"
  local volume_changes="$3"
  local codec_extension="$4"
  local safe_mode_write="${5:-false}" # Default to false if not provided
  local output_file="${source_file%.*}.mkv"
  local boost_success=true # Flag to check if boosting was successful

  # Split volume_changes into an array
  local -a volume_change_array
  IFS=',' read -r -A volume_change_array <<< "$volume_changes"

  # Extract original audio track
  local extracted_file="extracted_audio.${codec_extension}"
  echo "Extracting audio track ID $track_id from $source_file..."
  mkvextract tracks "$source_file" "${track_id}:${extracted_file}"
  echo "Extracted audio track to $extracted_file"

  # Loop over each volume change, create a boosted audio file, and remux it
  for volume_change in "${volume_change_array[@]}"; do
    # Ensure the volume_change doesn't already include "dB"
    local clean_volume_change="${volume_change//dB/}"
    local boosted_file="./${clean_volume_change}dB.aac"
    local track_name="${clean_volume_change}dB"

    echo "Boosting volume by ${clean_volume_change}dB..."
    ffmpeg -y -i "$extracted_file" -filter:a "volume=${clean_volume_change}dB" -c:a aac -q:a 0 -threads "$thread_count" "$boosted_file"
    if [ $? -ne 0 ]; then
      echo "Error: Boosting volume failed for ${clean_volume_change}dB."
      boost_success=false
      continue
    fi
    echo "Boosted audio saved to $boosted_file"

    # Remux the boosted audio back into the original file
    local temp_file="${source_file%.*}_${clean_volume_change}dB_temp.mkv"
    echo "Remuxing the boosted audio back to $temp_file..."
    mkvmerge -o "$temp_file" --track-name "0:$track_name" "$boosted_file" "$source_file"

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
    local count=1
    local boosted_file_name="${source_file%.*}_boosted (${count}).mkv"

    # Increment the number if the boosted file already exists
    while [ -f "$boosted_file_name" ]; do
      count=$((count + 1))
      boosted_file_name="${source_file%.*}_boosted (${count}).mkv"
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
  local backup_file="${source_file%.*}_original.mkv"
  local count=2

  # Check if the backup file already exists and increment the count if it does
  while [ -f "$backup_file" ]; do
    backup_file="${source_file%.*}_original ${count}.mkv"
    count=$((count + 1))
  done

  echo "Creating a backup of the original file as $backup_file"
  cp "$source_file" "$backup_file"
  if [ $? -eq 0 ]; then
    echo "Backup created successfully."
    #echo "Listing directory contents:"
    #ls -l
  else
    echo "Error: Failed to create backup. Exiting."
    return 1
  fi
}

# Function to extract tracks from the MKV file, excluding specified tracks
extract_tracks_excluding() {
  local source_file="$1"
  local temp_dir="$2"
  local exclude_tracks="$3"
  
  echo "Extracting tracks from $source_file excluding: $exclude_tracks"
  
  # Convert exclude_tracks to an array, handling ranges
  exclude_tracks_array=()
  IFS=',' read -r raw_ids_str <<< "$exclude_tracks"
  raw_ids=(${(s:,:)raw_ids_str})
  for id in "${raw_ids[@]}"; do
    if [[ $id == *-* ]]; then
      range_start=$(echo $id | cut -d '-' -f 1)
      range_end=$(echo $id | cut -d '-' -f 2)
      for ((i=range_start; i<=range_end; i++)); do
        exclude_tracks_array+=($i)
      done
    else
      exclude_tracks_array+=($id)
    fi
  done

  # Remove duplicates and sort
  exclude_tracks_array=($(echo "${exclude_tracks_array[@]}" | tr ' ' '\n' | sort -n | uniq))

  # Identify all tracks and extract those not in exclude_tracks_array
  all_tracks=$(mkvmerge -J "$source_file")
  total_tracks=$(echo "$all_tracks" | jq '.tracks | length')
  for (( i = 0; i < $total_tracks; i++ )); do
    track_id=$(echo "$all_tracks" | jq -r ".tracks[$i].id")
    track_type=$(echo "$all_tracks" | jq -r ".tracks[$i].type")
    if ! [[ " ${exclude_tracks_array[@]} " =~ " $track_id " ]]; then
      case $track_type in
        video)
          mkvextract tracks "$source_file" "${track_id}:${temp_dir}/${track_id}_video.webm" ;;
        audio)
          mkvextract tracks "$source_file" "${track_id}:${temp_dir}/${track_id}_audio.aac" ;;
        subtitles)
          mkvextract tracks "$source_file" "${track_id}:${temp_dir}/${track_id}_subtitles.srt" ;;
        *)
          mkvextract tracks "$source_file" "${track_id}:${temp_dir}/${track_id}_other.bin" ;;
      esac
    fi
  done

  echo "Extraction completed. Tracks are in $temp_dir"
}

# Function to remux extracted tracks into a new MKV file
remux_tracks() {
  local source_file="$1"
  local temp_dir="$2"
  local output_file

  if [ "$safe_mode_write" = true ]; then
    local base_name="${source_file%.*}_removed"
    local i=1
    output_file="${base_name} (${i}).mkv"
    while [ -f "$output_file" ]; do
      ((i++))
      output_file="${base_name} (${i}).mkv"
    done
  else
    output_file="$source_file"
  fi

  echo "Remuxing tracks from $temp_dir into $output_file..."

  # Prepare mkvmerge input options for each file in temp_dir
  local input_files=()
  for file in "$temp_dir"/*; do
    input_files+=("$file")
  done

  # Run mkvmerge to remux the file with the extracted tracks
  mkvmerge -o "$output_file" "${input_files[@]}"
  echo "Remuxing completed: $output_file"
}

# Function to check if the file has a .mkv extension
validate_mkv_extension() {
  local filename="$1"
  if [[ "$filename" == *.mkv ]]; then
    return 0
  else
    return 1
  fi
}

# Function to display mkvinfo and mkvmerge details
display_track_info() {
  local source_file="$1"

  echo "------------------------  mkvinfo ------------------------"

  mkvinfo "$source_file" | awk '
  /Track number:/ { in_track_block = 1; print; next }
  in_track_block && /Track type:/ { print; next }
  in_track_block && /Codec ID:/ { print; next }
  in_track_block && /Name:/ { print; next }
  in_track_block && (/Channels:/ || /Pixel width:/) {
    in_track_block = 0;
    print "----------------------------------------------------------"
  }
  ' | sed '/^$/d'  # Remove empty lines

  echo "-----------------------  mkvmerge -----------------------"
  mkvmerge --identify "$source_file" | grep -E 'Track ID [0-9]+:'
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
        read name
        mkvpropedit "$source_file" --edit track:$((i+1)) --set name="$name"
      done
    else
      echo "--------------------  Track ID $id Name ---------------------"
      printf "Name: "
      read name
      mkvpropedit "$source_file" --edit track:$((id+1)) --set name="$name"
    fi
  done
}

# Main script
current_dir=$(pwd)
echo "Current Work Dir: $current_dir"
cd "$current_dir"

# Command-line arguments handling
if [ $# -gt 0 ]; then
  if [ "$1" = "--help" ]; then
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
  echo "1) Remux to MKV"
  echo "2) Volume Boost"
  echo "3) Remove Tracks"
  echo "4) Edit Tracks"
  printf "Enter choice: "
  read choice

  if [ "$choice" -eq 1 ]; then
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
      
      # Encapsulate the source file in quotes to handle spaces correctly
      #echo "Debug: Final source file path: \"$source_file\""
      
      # Verify the file is a video file using ffprobe
      if ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "$source_file" 2>/dev/null | grep -q '^video'; then
        remux_to_mkv "$source_file" "prompt"
      else
        echo "Warning: Skipping non-video file \"$source_file\"."
      fi
    done

  elif [ "$choice" -eq 2 ]; then
    local source_file=""
    while true; do
      printf "Select the source video file (.mkv):\n"
      source_file=$(find . -maxdepth 1 -type f -name "*.mkv" | fzf --height 40% --reverse --border)
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

    # Ensure backup is created if in safe mode
    if [ "$safe_mode_write" = true ]; then
      create_backup "$source_file"
      if [ $? -ne 0 ]; then
        echo "Error: Failed to create backup. Exiting."
        exit 1
      fi
    fi

    # Identify audio tracks
    echo "Identifying audio tracks in $source_file..."
    audio_tracks=$(mkvmerge --identify "$source_file" | grep -E 'Track ID [0-9]+: audio' | sed -E 's/Track ID ([0-9]+): audio \(([^)]+)\)/Track ID \1: audio (\2)/')
    audio_count=$(echo "$audio_tracks" | wc -l)

    if [ "$audio_count" -eq 0 ]; then
      echo "No audio tracks found in the file."
      exit 1
    fi

    # Print the audio tracks found
    echo "Audio tracks found:"
    echo "$audio_tracks"

    if [ "$audio_count" -eq 1 ]; then
      # Automatically use the only audio track found
      track_info=$(echo "$audio_tracks" | head -n 1)
    else
      # Prompt the user to select the track ID if more than one is found
      printf "Enter the Track ID to extract: "
      read track_id
      track_info=$(echo "$audio_tracks" | grep "Track ID $track_id: ")
    fi

    # Extract codec and track ID
    codec=$(echo "$track_info" | awk '{print $5}' | tr -d '()')
    track_id=$(echo "$track_info" | awk '{print $3}' | tr -d ':')

    # Generate file extension from codec information
    codec_extension=$(echo "$codec" | tr '[:upper:]' '[:lower:]' | sed 's/-/_/g')

    printf "Enter the amount of dB to change (e.g., 2dB,3.5dB,-5dB): "
    read volume_changes

    # Call the function to boost audio volume
    boost_audio_volume "$source_file" "$track_id" "$volume_changes" "$codec_extension" "$safe_mode_write"

    # Check if boost_audio_volume completed successfully and safe_mode_write is true
    if [ $? -eq 0 ] && [ "$safe_mode_write" = true ]; then
      boost_audio_volume_safe_sorting "$source_file" "$safe_mode_write"
    fi

  elif [ "$choice" -eq 3 ]; then
    local source_file=""
    while true; do
      printf "Select the source video file (.mkv):\n"
      source_file=$(find . -maxdepth 1 -type f -name "*.mkv" | fzf --height 40% --reverse --border)
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

    # Identify all tracks
    echo "Identifying all tracks in $source_file..."
    all_tracks=$(mkvmerge --identify "$source_file" | grep -E 'Track ID [0-9]+:')
    track_count=$(echo "$all_tracks" | wc -l)

    if [ "$track_count" -eq 0 ]; then
      echo "No tracks found in the file."
      exit 1
    fi

    # Print all tracks found
    echo "Tracks found:"
    echo "$all_tracks"

    printf "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): "
    read track_ids

    # Create temporary directory and extract remaining tracks
    temp_dir=$(create_temp_dir)
    extract_tracks_excluding "$source_file" "$temp_dir" "$track_ids"
    remux_tracks "$source_file" "$temp_dir"
    
    # Clean up temporary directory
    remove_temp_dir "$temp_dir"
    
  elif [ "$choice" -eq 4 ]; then
    printf "Select the source video file (.mkv):\n"
    source_file=$(find . -maxdepth 1 -type f -name "*.mkv" | fzf --height 40% --reverse --border)
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
    read track_ids

    rename_tracks "$source_file" "$track_ids"

  else
    echo "Invalid choice."
    exit 1
  fi
fi
