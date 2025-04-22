#!/bin/local/zsh

# Store the current directory
current_dir=$(pwd)
echo "Current Work Dir: $current_dir"

# Function to extract metadata to a file
extract_metadata() {
  ffmpeg -i "$1" -f ffmetadata "$2"
}

# Function to apply metadata from a file
apply_metadata() {
  ffmpeg -i "$2" -i "$1" -map_metadata 1 -c:a copy -y "$3"
}

# Loop through all .m4a files in the current directory
for file in "$current_dir"/*.m4a; do
  echo "Processing $file"
  
  # Temporary files for metadata and audio
  metadata_file="${file%.m4a}.metadata"
  temp_audio_file="${file%.m4a}.tmp.m4a"
  
  # Extract metadata
  extract_metadata "$file" "$metadata_file"
  
  # Strip all metadata
  ffmpeg -i "$file" -map_metadata -1 -c:a copy "$temp_audio_file"
  
  # Reapply metadata
  apply_metadata "$metadata_file" "$temp_audio_file" "${temp_audio_file%.tmp.m4a}.final.m4a"
  
  # Replace the original file with the final version
  mv "${temp_audio_file%.tmp.m4a}.final.m4a" "$file"
  
  # Clean up temporary metadata file
  rm "$metadata_file"
  
  # Optionally, remove the intermediate temp audio file if you want to keep your directory clean
  rm "$temp_audio_file"
  
done

echo "All files have been processed."
