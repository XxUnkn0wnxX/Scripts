#!/usr/local/bin/zsh

set -euo pipefail

# Download destination.
TARGET_DIR="$HOME/Downloads"
mkdir -p "$TARGET_DIR"

echo "Getting DeveloperSeed catalog URL..."

CATALOG_URL=$(
  plutil -p /System/Library/PrivateFrameworks/Seeding.framework/Resources/SeedCatalogs.plist \
  | awk -F'"' '/DeveloperSeed/ {print $4; exit}' \
  | sed 's/\.gz$//'
)

if [[ -z "${CATALOG_URL:-}" ]]; then
  echo "Failed to find DeveloperSeed catalog URL."
  exit 1
fi

echo "Catalog URL:"
echo "$CATALOG_URL"
echo

CATALOG_FILE="$(mktemp)"
URLS_FILE="$(mktemp)"

cleanup() {
  rm -f "$CATALOG_FILE" "$URLS_FILE"
}

trap cleanup EXIT

echo "Fetching catalog..."
curl -fsSL "$CATALOG_URL" -o "$CATALOG_FILE"

echo "Selecting newest package URLs..."

LATEST_URL=$(
  awk '
    /<string>.*MobileDeviceOnDemand\.pkg<\/string>/ {
      if ($0 !~ /MobileDeviceOnDemand\.(smd|pkm)<\/string>/) {
        line = $0
        sub(/^.*<string>/, "", line)
        sub(/<\/string>.*$/, "", line)
        current_url = line
      }
    }
    /<key>PostDate<\/key>/ {
      expect_date = 1
      next
    }
    expect_date && /<date>/ {
      line = $0
      sub(/^.*<date>/, "", line)
      sub(/<\/date>.*$/, "", line)
      if (current_url != "") {
        print line "\t" current_url
        current_url = ""
      }
      expect_date = 0
    }
  ' "$CATALOG_FILE" \
  | sort -r \
  | awk 'NR == 1 { print $2 }'
)

if [[ -z "${LATEST_URL:-}" ]]; then
  echo "No MobileDeviceOnDemand.pkg URL found."
  exit 1
fi

{
  echo "$LATEST_URL"
  echo "${LATEST_URL/MobileDeviceOnDemand.pkg/CoreTypes.pkg}"
} | awk '!seen[$0]++' > "$URLS_FILE"

if [[ ! -s "$URLS_FILE" ]]; then
  echo "No package URLs found."
  exit 1
fi

echo
echo "URLs to download:"
cat "$URLS_FILE"
echo

echo "Downloading to: $TARGET_DIR"
echo

while IFS= read -r pkg_url; do
  [[ -n "$pkg_url" ]] || continue
  echo "Downloading URL:"
  echo "$pkg_url"
  curl -fL --progress-bar -o "$TARGET_DIR/$(basename "$pkg_url")" "$pkg_url"
  echo
done < "$URLS_FILE"

echo "Done."
echo "Files saved in: $TARGET_DIR"
