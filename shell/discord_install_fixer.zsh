#!/usr/bin/env zsh

set -euo pipefail
setopt null_glob

script_name="${0:t}"
script_dir="${0:A:h}"
OPENASAR_RELEASE_URL="https://github.com/XxUnkn0wnxX/OpenAsar/releases/latest/download/app.asar"

typeset -A channel_app_names=(
  stable "Discord"
  ptb "Discord PTB"
  canary "Discord Canary"
)

typeset -A channel_data_dirs=(
  stable "$HOME/Library/Application Support/discord"
  ptb "$HOME/Library/Application Support/discordptb"
  canary "$HOME/Library/Application Support/discordcanary"
)

typeset -A channel_download_urls=(
  stable "https://discord.com/api/download/stable?platform=osx"
  ptb "https://discord.com/api/download/ptb?platform=osx"
  canary "https://discord.com/api/download/canary?platform=osx"
)

print_usage() {
  cat <<EOF
Usage:
  $script_name --channel stable|ptb|canary|all [--update] [--openasar]
  $script_name --help

Options:
  --channel  Select the Discord channel to clean. Use "all" for Stable, PTB, and Canary.
  --update   Download and replace the selected Discord app before cleaning updater files.
  --openasar Download and inject OpenAsar app.asar into the selected Discord app.
  --help     Show this help message.

Examples:
  $script_name --channel stable
  $script_name --channel ptb --update
  $script_name --channel canary --openasar
  $script_name --channel all --update

Notes:
  --channel without --update only cleans the selected channel's updater/core files.
  --update must be paired with --channel so the target app is explicit.
  --openasar must be paired with --channel so the target app is explicit.
EOF
}

fail_usage() {
  print -u2 -- "$1"
  print -u2
  print_usage >&2
  exit 2
}

selected_channel=""
update_requested=false
openasar_requested=false
explicit_channel=false

while (( $# > 0 )); do
  case "$1" in
    --help|-h)
      print_usage
      exit 0
      ;;
    --channel)
      (( $# >= 2 )) || fail_usage "Missing value for --channel."
      selected_channel="$2"
      explicit_channel=true
      shift 2
      ;;
    --update)
      update_requested=true
      shift
      ;;
    --openasar)
      openasar_requested=true
      shift
      ;;
    *)
      fail_usage "Unknown argument: $1"
      ;;
  esac
done

if [[ "$update_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--update requires --channel stable|ptb|canary|all."
fi

if [[ "$openasar_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--openasar requires --channel stable|ptb|canary|all."
fi

if [[ "$explicit_channel" != true ]]; then
  selected_channel="stable"
fi

case "$selected_channel" in
  stable|ptb|canary)
    selected_channels=("$selected_channel")
    ;;
  all)
    selected_channels=(stable ptb canary)
    ;;
  *)
    fail_usage "Invalid channel: $selected_channel"
    ;;
esac

typeset -A channel_was_running=()

app_name_for_channel() {
  print -- "${channel_app_names[$1]}"
}

app_path_for_channel() {
  print -- "/Applications/$(app_name_for_channel "$1").app"
}

executable_path_for_channel() {
  local channel="$1"
  print -- "$(app_path_for_channel "$channel")/Contents/MacOS/$(app_name_for_channel "$channel")"
}

data_dir_for_channel() {
  print -- "${channel_data_dirs[$1]}"
}

download_url_for_channel() {
  print -- "${channel_download_urls[$1]}"
}

dmg_path_for_channel() {
  local channel="$1"
  print -- "$script_dir/Discord-${channel}-installer.dmg"
}

mount_point_for_channel() {
  local channel="$1"
  print -- "$script_dir/mount-${channel}"
}

openasar_payload_path() {
  print -- "$script_dir/openasar-app.asar"
}

available_mount_point_for_channel() {
  local channel="$1"
  local base_mount_point
  local candidate
  local random_number

  base_mount_point="$(mount_point_for_channel "$channel")"

  if [[ ! -e "$base_mount_point" ]]; then
    print -- "$base_mount_point"
    return 0
  fi

  for _ in {1..100}; do
    random_number=$(( RANDOM % 90 + 10 ))
    candidate="${base_mount_point}-${random_number}"
    if [[ ! -e "$candidate" ]]; then
      print -- "$candidate"
      return 0
    fi
  done

  print -u2 "Could not find an unused mountpoint path for:"
  print -u2 "  $base_mount_point"
  return 1
}

discord_is_running() {
  local channel="$1"
  local executable
  executable="$(executable_path_for_channel "$channel")"
  pgrep -f "^${executable}$" >/dev/null 2>&1
}

download_openasar_payload() {
  local payload_path="$1"

  rm -f -- "$payload_path"

  print "Downloading OpenAsar payload to:"
  print "  $payload_path"
  if ! curl -L --fail --show-error --output "$payload_path" "$OPENASAR_RELEASE_URL"; then
    rm -f -- "$payload_path"
    return 1
  fi

  if [[ ! -f "$payload_path" ]]; then
    print -u2 "OpenAsar payload download failed:"
    print -u2 "  $payload_path"
    rm -f -- "$payload_path"
    return 1
  fi
}

inject_openasar() {
  local channel="$1"
  local payload_path="$2"
  local app_name
  local app_path
  local resources_dir
  local target_asar

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  resources_dir="$app_path/Contents/Resources"
  target_asar="$resources_dir/app.asar"

  if [[ ! -d "$app_path" ]]; then
    print -u2 "$app_name app was not found:"
    print -u2 "  $app_path"
    return 1
  fi

  if [[ ! -d "$resources_dir" ]]; then
    print -u2 "$app_name resources directory was not found:"
    print -u2 "  $resources_dir"
    return 1
  fi

  print "Injecting OpenAsar into $app_name..."
  cp "$payload_path" "$target_asar"

  if [[ ! -f "$target_asar" ]]; then
    print -u2 "OpenAsar injection failed; app.asar was not found after copy:"
    print -u2 "  $target_asar"
    return 1
  fi

  if ! cmp -s "$payload_path" "$target_asar"; then
    print -u2 "OpenAsar injection failed; app.asar does not match the downloaded payload:"
    print -u2 "  $target_asar"
    return 1
  fi

  print "OpenAsar injected into $app_name:"
  print "  $target_asar"
  sleep 1
}

quit_discord() {
  local channel="$1"
  local app_name
  local executable
  app_name="$(app_name_for_channel "$channel")"
  executable="$(executable_path_for_channel "$channel")"

  discord_is_running "$channel" || return 1

  print "$app_name is running. Quitting it before continuing..."
  osascript -e "tell application \"$app_name\" to quit" >/dev/null 2>&1 || true

  for _ in {1..10}; do
    discord_is_running "$channel" || break
    sleep 1
  done

  if discord_is_running "$channel"; then
    print "$app_name did not quit cleanly. Force-killing it..."
    pkill -9 -f "^${executable}$" || true
    sleep 1
  fi

  if discord_is_running "$channel"; then
    print -u2 "$app_name is still running. Refusing to continue."
    exit 1
  fi

  return 0
}

download_and_replace_app() {
  local channel="$1"
  local app_name
  local app_path
  local executable_path
  local download_url
  local dmg_path
  local mount_point
  local mounted=false
  local mount_point_created=false
  local source_app=""
  local attempt
  local -a found_apps

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  executable_path="$(executable_path_for_channel "$channel")"
  download_url="$(download_url_for_channel "$channel")"
  dmg_path="$(dmg_path_for_channel "$channel")"
  mount_point="$(available_mount_point_for_channel "$channel")"

  rm -f -- "$dmg_path"

  mkdir -p "$mount_point"
  mount_point_created=true

  cleanup_mount_and_dmg() {
    if [[ "$mounted" == true && -n "$mount_point" ]]; then
      hdiutil detach "$mount_point" -quiet >/dev/null 2>&1 || hdiutil detach "$mount_point" -force -quiet >/dev/null 2>&1 || true
    fi
    if [[ "$mount_point_created" == true ]]; then
      rm -rf -- "$mount_point"
    fi
    rm -f -- "$dmg_path"
  }

  print "Downloading $app_name installer to:"
  print "  $dmg_path"
  for attempt in {1..3}; do
    if curl -L --fail --show-error --output "$dmg_path" "$download_url"; then
      break
    fi

    rm -f -- "$dmg_path"
    if (( attempt == 3 )); then
      print -u2 "$app_name installer download failed after $attempt attempts."
      print -u2 "$app_name was not replaced."
      return 1
    fi

    print "$app_name installer download failed. Retrying in 3 seconds..."
    sleep 3
  done

  {
    hdiutil attach "$dmg_path" -nobrowse -readonly -mountpoint "$mount_point" >/dev/null
    mounted=true

    source_app="$mount_point/$app_name.app"
    if [[ ! -d "$source_app" ]]; then
      found_apps=("$mount_point"/*.app(N))
      source_app="${found_apps[1]:-}"
    fi

    if [[ -z "$source_app" || ! -d "$source_app" ]]; then
      print -u2 "Could not find a Discord app inside the mounted installer:"
      print -u2 "  $mount_point"
      exit 1
    fi

    print "Replacing $app_name in /Applications..."
    rm -rf -- "$app_path"
    ditto "$source_app" "$app_path"

    if [[ ! -d "$app_path" ]]; then
      print -u2 "Copy failed; app was not found after replacement:"
      print -u2 "  $app_path"
      exit 1
    fi

    if [[ ! -x "$executable_path" ]]; then
      print -u2 "Copy failed; app executable was not found after replacement:"
      print -u2 "  $executable_path"
      exit 1
    fi
  } always {
    cleanup_mount_and_dmg
  }

  print "$app_name app replaced successfully."
  sleep 2
}

clean_channel() {
  local channel="$1"
  local allow_missing_data_dir="${2:-false}"
  local app_name
  local data_dir
  local targets
  local existing_targets
  local target

  app_name="$(app_name_for_channel "$channel")"
  data_dir="$(data_dir_for_channel "$channel")"

  if [[ ! -d "$data_dir" ]]; then
    if [[ "$allow_missing_data_dir" == true ]]; then
      print "$app_name data directory not found, so there is no App Support cleanup to run:"
      print "  $data_dir"
      return 0
    fi

    print -u2 "$app_name data directory not found:"
    print -u2 "  $data_dir"
    return 1
  fi

  if [[ ! -f "$data_dir/settings.json" && ! -d "$data_dir/Local Storage" ]]; then
    print -u2 "Refusing to clean because the target does not look like $app_name's data directory:"
    print -u2 "  $data_dir"
    return 1
  fi

  targets=(
    "$data_dir/installer.db"
    "$data_dir"/0.0.*/
    "$data_dir"/app-*/
    "$data_dir/modules"
    "$data_dir/module_data"
    "$data_dir/download"
  )

  existing_targets=()
  for target in "${targets[@]}"; do
    [[ -e "$target" ]] && existing_targets+=("$target")
  done

  if (( ${#existing_targets[@]} == 0 )); then
    print "Warning: no $app_name installation files were detected."
    print "Expected at least one of:"
    print "  installer.db"
    print "  0.0.*/"
    print "  app-*/"
    print "  modules/"
    print "  module_data/"
    print "  download/"
    print
    print "Nothing was changed for $app_name."
    return 0
  fi

  print "The following $app_name installation files will be deleted:"
  for target in "${existing_targets[@]}"; do
    print "  ${target#$data_dir/}"
  done

  print
  print "Login and settings data will be preserved."

  if discord_is_running "$channel"; then
    quit_discord "$channel"
  fi

  if discord_is_running "$channel"; then
    print -u2 "$app_name is still running. Refusing to clean its installation."
    return 1
  fi

  for target in "${existing_targets[@]}"; do
    rm -rf -- "$target"
  done

  print "$app_name installation files cleaned successfully."
}

relaunch_channel_if_needed() {
  local channel="$1"
  local was_running_at_start="${2:-false}"
  local app_name
  local app_path
  local executable_path
  local attempt

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  executable_path="$(executable_path_for_channel "$channel")"

  if [[ "$was_running_at_start" == true ]]; then
    print "Relaunching $app_name because it was running when this script started..."
    for attempt in {1..3}; do
      if open "$app_path"; then
        return 0
      fi

      print "$app_name did not relaunch cleanly with open. Retrying..."
      sleep 1
    done

    if [[ -x "$executable_path" ]]; then
      print "Falling back to launching $app_name executable directly..."
      "$executable_path" >/dev/null 2>&1 &!
      return 0
    fi

    print -u2 "$app_name could not be relaunched because its executable is missing:"
    print -u2 "  $executable_path"
    return 1
  else
    print "$app_name was not running, so it will remain closed."
  fi
}

validate_selected_data_dirs() {
  local channel
  local app_name
  local data_dir

  for channel in "${selected_channels[@]}"; do
    app_name="$(app_name_for_channel "$channel")"
    data_dir="$(data_dir_for_channel "$channel")"

    if [[ -d "$data_dir" && ! -f "$data_dir/settings.json" && ! -d "$data_dir/Local Storage" ]]; then
      print -u2 "Refusing to continue because the target does not look like $app_name's data directory:"
      print -u2 "  $data_dir"
      exit 1
    fi
  done
}

validate_selected_data_dirs

openasar_payload=""
openasar_payload_downloaded=false

if [[ "$openasar_requested" == true ]]; then
  openasar_payload="$(openasar_payload_path)"
  cleanup_openasar_payload() {
    if [[ "$openasar_payload_downloaded" == true && -n "$openasar_payload" ]]; then
      rm -f -- "$openasar_payload"
    fi
  }

  trap cleanup_openasar_payload EXIT
  download_openasar_payload "$openasar_payload"
  openasar_payload_downloaded=true
fi

for channel in "${selected_channels[@]}"; do
  if discord_is_running "$channel"; then
    channel_was_running[$channel]=true
  else
    channel_was_running[$channel]=false
  fi
done

if [[ "$selected_channel" == all ]]; then
  print
  print "Stopping all selected Discord clients before continuing..."
  for channel in "${selected_channels[@]}"; do
    if discord_is_running "$channel"; then
      quit_discord "$channel"
    fi
  done
fi

for channel in "${selected_channels[@]}"; do
  app_name="$(app_name_for_channel "$channel")"
  was_running_at_start="${channel_was_running[$channel]:-false}"
  allow_missing_data_dir=false

  print
  print "== $app_name =="

  if [[ "$selected_channel" != all && ( "$update_requested" == true || "$openasar_requested" == true ) ]]; then
    if discord_is_running "$channel"; then
      quit_discord "$channel"
    fi
  fi

  if [[ "$selected_channel" == all || "$update_requested" == true ]]; then
    allow_missing_data_dir=true
  fi

  clean_channel "$channel" "$allow_missing_data_dir"

  if [[ "$update_requested" == true ]]; then
    download_and_replace_app "$channel"
  fi

  if [[ "$openasar_requested" == true ]]; then
    inject_openasar "$channel" "$openasar_payload"
  fi

  relaunch_channel_if_needed "$channel" "$was_running_at_start"
done

if [[ "$openasar_requested" == true ]]; then
  cleanup_openasar_payload
fi
