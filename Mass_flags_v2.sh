#!/usr/local/bin/zsh

  function get_track_count() {
    local file="$1"
    local count=$(mkvmerge "$file" --identify | grep 'Track ID' | wc -l)
    echo $count
  }

function count_attachments() {
  local file="$1"
  mkvmerge --identify "$file" | grep -c "Attachment ID"
}

current_dir=$(pwd)
echo "Current Work Dir: $current_dir"
cd "$current_dir"

if [ ! "$(ls -A "$current_dir"/*.mkv 2>/dev/null)" ]; then
  echo "Please check if there are video files present before running this script again."
  exit 1
fi

read -p "Select an option:
1) Set flag-forced for a track
2) Set flag-default for all tracks
3) Set flag-default for a track
4) Remove flag-forced for all tracks
5) Set language for a track
6) Set name for a track
7) Extract all attachments from MKV files
Enter choice: " choice

choice=${choice:-1}

if [ "$choice" = "1" ]; then
  read -p "Enter the track number: " track_num
  read -p "Enter flag-forced value (1 or 0, blank for 1): " flag_value
  flag_value=${flag_value:-1}
  track_num=${track_num:-4}

  for file in *.mkv; do
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" --edit track:$track_num --set flag-forced=$flag_value
  done

elif [ "$choice" = "2" ]; then
#  function get_track_count() {
#    local file="$1"
#    local count=$(mkvmerge "$file" --identify | grep 'Track ID' | wc -l)
#    echo $count
#  }

  read -p "Enter flag-default value (1 or 0, blank for 1): " flag_value
  flag_value=${flag_value:-1}

  for file in *.mkv
  do
    track_count=$(get_track_count "$file")
    edit_flags=""
    for (( i=1; i<=track_count; i++ ))
    do
      edit_flags+=" --edit track:$i --set flag-default=$flag_value"
    done
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" $edit_flags
  done
  
elif [ "$choice" = "3" ]; then
  read -p "Enter the track number: " track_num
  read -p "Enter flag-default value (1 or 0, blank for 1): " flag_value
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

  for file in *.mkv
  do
    track_count=$(get_track_count "$file")
    edit_flags=""
    for (( i=1; i<=track_count; i++ ))
    do
      edit_flags+=" --edit track:$i --set flag-forced=$flag_value"
    done
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" $edit_flags
  done
  
elif [ "$choice" = "5" ]; then
  read -p "Enter the track number: " track_num
  read -p "Enter the lang (eng, jpn, und): " flag_lang
  flag_lang=${flag_lang:-jpn}
  track_num=${track_num:-2}

  for file in *.mkv; do
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" --edit track:$track_num --set language=$flag_lang
  done
  
elif [ "$choice" = "6" ]; then
  read -p "Enter the track number: " track_num
  read -p "Enter the track name: " title_name
  title_name=${title_name:-""}
  track_num=${track_num:-3}

  for file in *.mkv; do
    echo "Editing file: $(basename "$file")"
    mkvpropedit "$file" --edit track:$track_num --set name="$title_name"
  done

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

else
  echo "Invalid choice."
fi