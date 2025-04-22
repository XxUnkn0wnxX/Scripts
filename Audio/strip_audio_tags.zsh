#!/bin/local/zsh

# Store the current directory
current_dir=$(pwd)
echo "Current Work Dir: $current_dir"

# Loop through all .m4a files in the current directory
for file in "$current_dir"/*.m4a; do
  echo "Processing $file"
  # Use ffmpeg to strip metadata and overwrite the original file
  ffmpeg -i "$file" -map_metadata -1 -c:a copy "${file%.m4a}.tmp.m4a" && mv "${file%.m4a}.tmp.m4a" "$file"
done

echo "All files have been processed."
