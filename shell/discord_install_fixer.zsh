#!/usr/local/bin/zsh

set -euo pipefail
setopt null_glob

discord_dir="$HOME/Library/Application Support/discord"
discord_executable="/Applications/Discord.app/Contents/MacOS/Discord"

discord_is_running() {
  pgrep -f "^${discord_executable}$" >/dev/null 2>&1
}

if [[ ! -d "$discord_dir" ]]; then
  print -u2 "Discord data directory not found:"
  print -u2 "  $discord_dir"
  exit 1
fi

if [[ ! -f "$discord_dir/settings.json" && ! -d "$discord_dir/Local Storage" ]]; then
  print -u2 "Refusing to clean because the target does not look like Discord's data directory:"
  print -u2 "  $discord_dir"
  exit 1
fi

targets=(
  "$discord_dir/installer.db"
  "$discord_dir"/0.0.*/
  "$discord_dir"/app-*/
  "$discord_dir/modules"
  "$discord_dir/module_data"
  "$discord_dir/download"
)

existing_targets=()
for target in "${targets[@]}"; do
  [[ -e "$target" ]] && existing_targets+=("$target")
done

if (( ${#existing_targets[@]} == 0 )); then
  print "Warning: no Discord Stable installation files were detected."
  print "Expected at least one of:"
  print "  installer.db"
  print "  0.0.*/"
  print "  app-*/"
  print "  modules/"
  print "  module_data/"
  print "  download/"
  print
  print "Nothing was changed."
  exit 0
fi

print "The following Discord installation files will be deleted:"
for target in "${existing_targets[@]}"; do
  print "  ${target#$discord_dir/}"
done

print
print "Login and settings data will be preserved."

discord_was_running=false
if discord_is_running; then
  discord_was_running=true
  print "Discord Stable is running. Quitting it before cleaning..."
  osascript -e 'tell application "Discord" to quit' >/dev/null 2>&1 || true

  for _ in {1..10}; do
    discord_is_running || break
    sleep 1
  done

  if discord_is_running; then
    print "Discord Stable did not quit cleanly. Force-killing it..."
    pkill -9 -f "^${discord_executable}$"
    sleep 1
  fi
fi

if discord_is_running; then
  print -u2 "Discord Stable is still running. Refusing to clean its installation."
  exit 1
fi

for target in "${existing_targets[@]}"; do
  rm -rf -- "$target"
done

print "Discord installation files cleaned successfully."

if [[ "$discord_was_running" == true ]]; then
  print "Relaunching Discord Stable to download a fresh core installation..."
  open -a "/Applications/Discord.app"
else
  print "Discord Stable was not running, so it will remain closed."
fi
