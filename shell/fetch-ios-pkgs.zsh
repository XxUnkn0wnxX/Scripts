#!/usr/bin/env zsh

set -euo pipefail

# Foundation of this script came from a MacRumors post by bogdanw:
# https://forums.macrumors.com/threads/itunes-software-updates.2416893/page-3?post=33894235#post-33894235

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

if (( EUID == 0 )); then
  INSTALLER_CMD=(/usr/sbin/installer)
  LAUNCHCTL_CMD=(/bin/launchctl)
else
  INSTALLER_CMD=(sudo /usr/sbin/installer)
  LAUNCHCTL_CMD=(sudo /bin/launchctl)
fi

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
  curl -fL --show-error --progress-bar -o "$TARGET_DIR/$(basename "$pkg_url")" "$pkg_url"
  echo
done < "$URLS_FILE"

echo "Files saved in: $TARGET_DIR"
echo

install_pkg() {
  local pkg_path="$1"

  if [[ ! -f "$pkg_path" ]]; then
    echo "Missing package: $pkg_path"
    exit 1
  fi

  echo "Installing package:"
  echo "$pkg_path"
  "${INSTALLER_CMD[@]}" -verboseR -pkg "$pkg_path" -target /
  echo
}

restart_mobile_services() {
  local usbmux_label="com.apple.usbmuxd"
  local usbmux_plist="/System/Library/LaunchDaemons/com.apple.usbmuxd.plist"
  local old_pid=""
  local new_pid=""

  echo "Restarting mobile device services..."
  echo

  old_pid="$(/usr/bin/pgrep -x usbmuxd | head -n 1 || true)"

  # Kill usbmuxd first and let launchd respawn it.
  if /usr/bin/pgrep -x usbmuxd >/dev/null 2>&1; then
    echo "Stopping usbmuxd with killall..."
    if (( EUID == 0 )); then
      /usr/bin/killall -TERM usbmuxd >/dev/null 2>&1 || true
    else
      sudo /usr/bin/killall -TERM usbmuxd >/dev/null 2>&1 || true
    fi
    sleep 2
  fi

  new_pid="$(/usr/bin/pgrep -x usbmuxd | head -n 1 || true)"
  if [[ -n "$new_pid" ]]; then
    if [[ -n "$old_pid" && "$new_pid" != "$old_pid" ]]; then
      echo "usbmuxd restarted successfully with new PID: $new_pid"
    else
      echo "usbmuxd is running with PID: $new_pid"
    fi
    return 0
  fi

  echo "Trying launchctl kickstart..."
  if "${LAUNCHCTL_CMD[@]}" kickstart "system/$usbmux_label" >/dev/null 2>&1; then
    sleep 2
    new_pid="$(/usr/bin/pgrep -x usbmuxd | head -n 1 || true)"
    if [[ -n "$new_pid" ]]; then
      if [[ -n "$old_pid" && "$new_pid" != "$old_pid" ]]; then
        echo "usbmuxd restarted via launchctl kickstart with new PID: $new_pid"
      else
        echo "usbmuxd is running after launchctl kickstart with PID: $new_pid"
      fi
      return 0
    fi
  fi

  if [[ -e "$usbmux_plist" ]]; then
    echo "Trying legacy launchctl unload/load..."
    "${LAUNCHCTL_CMD[@]}" unload "$usbmux_plist" >/dev/null 2>&1 || true
    sleep 1
    "${LAUNCHCTL_CMD[@]}" load "$usbmux_plist" >/dev/null 2>&1 || true
    sleep 2

    new_pid="$(/usr/bin/pgrep -x usbmuxd | head -n 1 || true)"
    if [[ -n "$new_pid" ]]; then
      if [[ -n "$old_pid" && "$new_pid" != "$old_pid" ]]; then
        echo "usbmuxd restarted via legacy unload/load with new PID: $new_pid"
      else
        echo "usbmuxd is running after legacy unload/load with PID: $new_pid"
      fi
      return 0
    fi
  fi

  echo "Could not confirm usbmuxd restarted."
  echo "Most reliable fallback: unplug the iPhone, reconnect it, or reboot the Mac."
  return 1
}

CORETYPES_PATH="$TARGET_DIR/$(basename "${LATEST_URL/MobileDeviceOnDemand.pkg/CoreTypes.pkg}")"
MOBILEDEVICE_PATH="$TARGET_DIR/$(basename "$LATEST_URL")"

echo "Installing downloaded packages..."
echo
install_pkg "$CORETYPES_PATH"
install_pkg "$MOBILEDEVICE_PATH"

echo "Install completed successfully."
if ! restart_mobile_services; then
  echo "Mobile device services restart could not be confirmed."
fi
echo "Done."
