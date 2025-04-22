#!/usr/local/bin/zsh

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
  local output_file="${source_file%.*}.mkv"

  if [ -f "$output_file" ]; then
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
  local output_file="${source_file%.*}.mkv"

  # Split volume_changes into an array
  local -a volume_change_array
  IFS=',' read -r -A volume_change_array <<< "$volume_changes"

  # Extract original audio track
  local extracted_file="extracted_audio.${codec_extension}"
  echo "Extracting audio track ID $track_id from $source_file..."
  mkvextract tracks "$source_file" "${track_id}:${extracted_file}"
  echo "Extracted audio track to $extracted_file"

  # Loop over each volume change, create a boosted audio file, and remux it
  local temp_file
  for volume_change in "${volume_change_array[@]}"; do
    # Ensure the volume_change doesn't already include "dB"
    local clean_volume_change="${volume_change//dB/}"
    local boosted_file="./${clean_volume_change}dB.${codec_extension}"
    local track_name="${clean_volume_change}dB"

    echo "Boosting volume by ${clean_volume_change}dB..."
    ffmpeg -y -i "$extracted_file" -filter:a "volume=${clean_volume_change}dB" -c:a aac -q:a 0 "$boosted_file"
    echo "Boosted audio saved to $boosted_file"

    # Remux the boosted audio back into the original file
    temp_file="${source_file%.*}_${clean_volume_change}dB_temp.mkv"
    echo "Remuxing the boosted audio back to $temp_file..."
    mkvmerge -o "$temp_file" --track-name "0:$track_name" "$boosted_file" "$source_file"

    if [ -f "$temp_file" ]; then
      mv "$temp_file" "$output_file"
      echo "New file with boosted audio: $output_file"
    else
      echo "Error: Remuxing failed, temporary file not found."
      rm "$boosted_file"
      continue
    fi

    # Clean up
    rm "$boosted_file"
  done

  rm "$extracted_file"
  echo "Temporary files removed."
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
  local output_file="$source_file"

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

# Main script
current_dir=$(pwd)
echo "Current Work Dir: $current_dir"
cd "$current_dir"

# Command-line arguments handling
if [ $# -gt 0 ]; then
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
  # No arguments provided, ask for input via menu
  echo "Select an option:"
  echo "1) Remux to MKV"
  echo "2) Volume Boost"
  echo "3) Remove Tracks"
  printf "Enter choice: "
  read choice

  if [ "$choice" -eq 1 ]; then
    printf "Enter the full file name of the source video file: "
    read source_file
    remux_to_mkv "$source_file" "prompt"
  elif [ "$choice" -eq 2 ]; then
    printf "Enter the full file name of the source video file: "
    read source_file

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

    boost_audio_volume "$source_file" "$track_id" "$volume_changes" "$codec_extension"
  elif [ "$choice" -eq 3 ]; then
    printf "Enter the full file name of the source video file: "
    read source_file

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
  else
    echo "Invalid choice."
    exit 1
  fi
fi
