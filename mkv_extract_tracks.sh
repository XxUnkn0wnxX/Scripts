#!/usr/local/bin/zsh

current_dir=$(pwd)
echo "Current Work Dir: $current_dir"
cd "$current_dir"

# Check if there are any MKV files present
if [ ! "$(ls -A "$current_dir"/*.mkv 2>/dev/null)" ]; then
  echo "Please check if there are video files present before running this script again."
  exit 1
fi

# Function to count the number of attachments
count_attachments() {
  local file="$1"
  mkvmerge --identify "$file" | grep -c "Attachment ID"
}

# Extract attachments from all MKV files in the current working directory
for file in *.mkv; do
  attachment_count=$(count_attachments "$file")
  echo "Processing $file: Extracting $attachment_count attachments..."

  if [ "$attachment_count" -gt 0 ]; then
    attachment_ids=($(seq 1 $attachment_count))
    mkvextract attachments "$file" "${attachment_ids[@]}"
  fi
done

echo "Attachments extraction completed."