#!/usr/bin/env zsh

set -euo pipefail
setopt null_glob

script_name="${0:t}"
script_dir="${0:A:h}"
DEFAULT_OPENASAR_SOURCE="https://github.com/XxUnkn0wnxX/OpenAsar"
DEFAULT_DOWNLOAD_CONNECTIONS=16

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

typeset -A channel_update_urls=(
  stable "https://discord.com/api/updates/stable?platform=osx"
  ptb "https://discord.com/api/updates/ptb?platform=osx"
  canary "https://discord.com/api/updates/canary?platform=osx"
)

typeset -A channel_cdn_hosts=(
  stable "stable.dl2.discordapp.net"
  ptb "ptb.dl2.discordapp.net"
  canary "canary.dl2.discordapp.net"
)

typeset -A channel_dmg_filenames=(
  stable "Discord.dmg"
  ptb "DiscordPTB.dmg"
  canary "DiscordCanary.dmg"
)

print_usage() {
  cat <<EOF
Usage:
  $script_name --channel stable|ptb|canary|all [--update [version]] [--openasar] [--openasar-source url-or-path]
  $script_name --channel stable|ptb|canary --dl [version]
  $script_name --channel stable|ptb|canary --update-select [minimum-version|start-end]
  $script_name --help

Options:
  --channel             Select the Discord channel to clean. Use "all" for Stable, PTB, and Canary.
  --update              Download and replace the selected Discord app before cleaning updater files.
                        Optionally pass a version such as 0.0.1177 to download that CDN build.
  --dl                  Download the selected Discord DMG only, then exit.
                        Optionally pass a version such as 0.0.1177 to download that CDN build.
  --update-select       Print available CDN DMG versions for one selected channel, then exit.
                        Optionally pass a minimum version such as 900 or a range such as 600-300.
  --openasar            Download and inject OpenAsar app.asar into the selected Discord app.
  --openasar-source     Use a specific OpenAsar repo URL, app.asar URL, or local path. Implies --openasar.
  --help                Show this help message.

Examples:
  $script_name --channel stable
  $script_name --channel ptb --update
  $script_name --channel canary --dl 0.0.1177
  $script_name --channel canary --update-select
  $script_name --channel canary --update-select 900
  $script_name --channel canary --update-select 600-300
  $script_name --channel canary --update 0.0.1177
  $script_name --channel canary --openasar
  $script_name --channel stable --openasar-source "\$HOME/Apps/Dev/BD/OpenAsar/dist/app.asar"
  $script_name --channel stable --update --openasar
  $script_name --channel all --update

Notes:
  --channel without --update only cleans the selected channel's updater/core files.
  --update must be paired with --channel so the target app is explicit.
  --dl must be paired with one channel and only downloads the DMG.
  --update without a version still supports --channel all.
  --update with a version, --dl, and --update-select require a single channel, not "all".
  --update-select only prints versions; it does not clean, update, inject, or relaunch anything.
  --openasar must be paired with --channel so the target app is explicit.
  aria2c is used for downloads when available; set DISCORD_DOWNLOAD_CONNECTIONS to tune its split count.
  OpenAsar sources can be GitHub repo URLs, app.asar URLs, or local paths including ~, \$HOME, and file:// paths.
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
dl_requested=false
update_select_requested=false
update_select_min_version=""
update_version=""
openasar_requested=false
openasar_source="${OPENASAR_SOURCE:-${OPENASAR_RELEASE_URL:-$DEFAULT_OPENASAR_SOURCE}}"
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
      if (( $# >= 2 )) && [[ "$2" != --* ]]; then
        update_version="$2"
        shift 2
      else
        shift
      fi
      ;;
    --update=*)
      update_requested=true
      update_version="${1#--update=}"
      shift
      ;;
    --dl)
      dl_requested=true
      if (( $# >= 2 )) && [[ "$2" != --* ]]; then
        update_version="$2"
        shift 2
      else
        shift
      fi
      ;;
    --dl=*)
      dl_requested=true
      update_version="${1#--dl=}"
      shift
      ;;
    --update-select)
      update_select_requested=true
      if (( $# >= 2 )) && [[ "$2" != --* ]]; then
        update_select_min_version="$2"
        shift 2
      else
        shift
      fi
      ;;
    --update-select=*)
      update_select_requested=true
      update_select_min_version="${1#--update-select=}"
      shift
      ;;
    --openasar)
      openasar_requested=true
      shift
      ;;
    --openasar-source)
      (( $# >= 2 )) || fail_usage "Missing value for --openasar-source."
      openasar_requested=true
      openasar_source="$2"
      shift 2
      ;;
    *)
      fail_usage "Unknown argument: $1"
      ;;
  esac
done

if [[ "$update_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--update requires --channel stable|ptb|canary|all."
fi

if [[ "$dl_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--dl requires --channel stable|ptb|canary."
fi

if [[ "$update_select_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--update-select requires --channel stable|ptb|canary."
fi

if [[ "$openasar_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--openasar requires --channel stable|ptb|canary|all."
fi

if [[ "$explicit_channel" != true ]]; then
  fail_usage "No channel specified. Use --channel stable|ptb|canary|all."
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

if [[ "$update_select_requested" == true && "$selected_channel" == all ]]; then
  fail_usage "--update-select only supports one channel at a time."
fi

if [[ "$dl_requested" == true && "$selected_channel" == all ]]; then
  fail_usage "--dl only supports one channel at a time."
fi

if [[ "$dl_requested" == true && ( "$update_requested" == true || "$update_select_requested" == true || "$openasar_requested" == true ) ]]; then
  fail_usage "--dl only downloads a DMG and cannot be combined with --update, --update-select, or --openasar."
fi

if [[ "$update_select_requested" == true && ( "$update_requested" == true || "$openasar_requested" == true ) ]]; then
  fail_usage "--update-select only prints versions and cannot be combined with --update or --openasar."
fi

if [[ -n "$update_version" && "$selected_channel" == all ]]; then
  fail_usage "--update or --dl with a version only supports one channel at a time."
fi

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
  local channel="$1"

  if [[ -n "$update_version" ]]; then
    versioned_download_url_for_channel "$channel" "$update_version"
  else
    print -- "${channel_download_urls[$channel]}"
  fi
}

normalize_discord_version() {
  local version="$1"
  local suffix

  case "$version" in
    <->)
      suffix="$version"
      ;;
    0.0.<->)
      suffix="${version##*.}"
      ;;
    *)
      print -u2 "Invalid Discord version: $version"
      print -u2 "Use a numeric version such as 1177 or 0.0.1177."
      return 1
      ;;
  esac

  print -- "0.0.$suffix"
}

discord_version_suffix() {
  local version="$1"

  version="$(normalize_discord_version "$version")" || return 1
  print -- "${version##*.}"
}

versioned_download_url_for_channel() {
  local channel="$1"
  local version="$2"

  version="$(normalize_discord_version "$version")" || return 1
  print -- "https://${channel_cdn_hosts[$channel]}/apps/osx/$version/${channel_dmg_filenames[$channel]}"
}

latest_version_for_channel() {
  local channel="$1"
  local manifest
  local version

  manifest="$(curl -Ls --fail --show-error "${channel_update_urls[$channel]}")" || return 1
  version="$(print -r -- "$manifest" | /usr/bin/perl -0ne 'print $1 if /"name"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"/')"

  if [[ -z "$version" ]]; then
    print -u2 "Could not read the latest Discord version from:"
    print -u2 "  ${channel_update_urls[$channel]}"
    return 1
  fi

  print -- "$version"
}

print_update_select_versions() {
  local channel="$1"
  local selector="${2:-}"
  local app_name
  local latest_version
  local latest_suffix
  local first_suffix
  local last_suffix=1
  local min_suffix=""
  local range_start=""
  local range_end=""
  local clamped_start=false
  local clamped_floor=false
  local scan_limit="${DISCORD_UPDATE_SELECT_SCAN_LIMIT:-0}"
  local suffix
  local url
  local headers
  local code
  local last_modified
  local found_any=false

  app_name="$(app_name_for_channel "$channel")"
  latest_version="$(latest_version_for_channel "$channel")" || return 1
  latest_suffix="$(discord_version_suffix "$latest_version")" || return 1
  first_suffix="$latest_suffix"

  if [[ -n "$selector" ]]; then
    if [[ "$selector" == *-* ]]; then
      range_start="${selector%%-*}"
      range_end="${selector#*-}"
      first_suffix="$(discord_version_suffix "$range_start")" || return 1
      last_suffix="$(discord_version_suffix "$range_end")" || return 1

      if (( first_suffix < last_suffix )); then
        print -u2 "Invalid update-select range: $selector"
        print -u2 "Use descending ranges such as 600-300 or 0.0.600-0.0.300."
        return 1
      fi

      if (( first_suffix > latest_suffix )); then
        first_suffix="$latest_suffix"
        clamped_start=true
      fi

      if (( last_suffix > first_suffix )); then
        last_suffix="$first_suffix"
        clamped_floor=true
      fi
    else
      min_suffix="$(discord_version_suffix "$selector")" || return 1
      if (( min_suffix > latest_suffix )); then
        min_suffix="$latest_suffix"
        clamped_floor=true
      fi
      last_suffix="$min_suffix"
    fi
  fi

  if [[ "$scan_limit" == <-> && "$scan_limit" -gt 0 && "$scan_limit" -lt "$latest_suffix" ]]; then
    if [[ -z "$selector" ]]; then
      last_suffix=$(( latest_suffix - scan_limit + 1 ))
    elif [[ -z "$range_start" ]]; then
      last_suffix=$(( latest_suffix - scan_limit + 1 > min_suffix ? latest_suffix - scan_limit + 1 : min_suffix ))
    else
      last_suffix=$(( first_suffix - scan_limit + 1 > last_suffix ? first_suffix - scan_limit + 1 : last_suffix ))
    fi
  fi

  print "Available $app_name macOS DMG versions:"
  print "  latest: $latest_version"
  print "  source: Discord CDN direct DMG URLs"
  print "  note: CDN directory listing is denied, so this probes versioned DMG URLs."
  if [[ "$clamped_start" == true ]]; then
    print "  requested start was newer than latest; using latest $latest_version"
  fi
  if [[ "$clamped_floor" == true ]]; then
    print "  requested floor was newer than latest; using latest $latest_version"
  fi
  if [[ -n "$range_start" ]]; then
    print "  scan range: 0.0.$first_suffix down to 0.0.$last_suffix"
  fi
  if [[ "$last_suffix" -gt 1 ]]; then
    if [[ -z "$range_start" ]]; then
      print "  scan floor: 0.0.$last_suffix"
    fi
    if [[ "$scan_limit" == <-> && "$scan_limit" -gt 0 ]]; then
      print "  scan limit: newest $scan_limit builds because DISCORD_UPDATE_SELECT_SCAN_LIMIT is set"
    fi
  fi
  print

  for (( suffix = first_suffix; suffix >= last_suffix; suffix-- )); do
    url="https://${channel_cdn_hosts[$channel]}/apps/osx/0.0.$suffix/${channel_dmg_filenames[$channel]}"
    headers="$(curl -ILs "$url")"
    code="$(print -r -- "$headers" | /usr/bin/awk 'toupper($0) ~ /^HTTP\// { code=$2 } END { print code }')"

    if [[ "$code" != 200 ]]; then
      continue
    fi

    last_modified="$(print -r -- "$headers" | /usr/bin/awk 'tolower($0) ~ /^last-modified:/ { sub(/^[Ll]ast-[Mm]odified:[[:space:]]*/, ""); value=$0 } END { gsub(/\r/, "", value); print value }')"
    [[ -n "$last_modified" ]] || last_modified="unknown"

    print "$last_modified  0.0.$suffix"
    found_any=true
  done

  if [[ "$found_any" != true ]]; then
    print -u2 "No CDN DMG versions were found for $app_name."
    return 1
  fi
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

openasar_source_is_remote() {
  case "$openasar_source" in
    http://*|https://*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

download_connection_count() {
  local connections="${DISCORD_DOWNLOAD_CONNECTIONS:-$DEFAULT_DOWNLOAD_CONNECTIONS}"

  if [[ "$connections" != <-> || "$connections" -lt 1 ]]; then
    connections="$DEFAULT_DOWNLOAD_CONNECTIONS"
  elif (( connections > DEFAULT_DOWNLOAD_CONNECTIONS )); then
    connections="$DEFAULT_DOWNLOAD_CONNECTIONS"
  fi

  print -- "$connections"
}

download_file() {
  local url="$1"
  local output_path="$2"
  local output_dir
  local output_name
  local aria2_path
  local connections

  output_dir="${output_path:h}"
  output_name="${output_path:t}"

  if aria2_path="$(command -v aria2c 2>/dev/null)"; then
    connections="$(download_connection_count)"
    print "Using aria2c downloader:"
    print "  $aria2_path"
    print "  connections: $connections"

    "$aria2_path" \
      --allow-overwrite=true \
      --auto-file-renaming=false \
      --continue=false \
      --file-allocation=none \
      --max-connection-per-server="$connections" \
      --min-split-size=1M \
      --split="$connections" \
      --dir="$output_dir" \
      --out="$output_name" \
      "$url"
  else
    print "Using curl downloader."
    curl -L --fail --show-error --output "$output_path" "$url"
  fi
}

remove_download_artifacts() {
  local output_path="$1"

  rm -f -- "$output_path" "$output_path.aria2"
}

openasar_remote_download_url() {
  local source_url="$openasar_source"
  local github_path

  case "$source_url" in
    https://github.com/*/*)
      source_url="${source_url%/}"
      source_url="${source_url%.git}"
      github_path="${source_url#https://github.com/}"

      if [[ "$github_path" != */*/* && "$source_url" != */releases/* ]]; then
        print -- "$source_url/releases/latest/download/app.asar"
        return 0
      fi
      ;;
  esac

  print -- "$source_url"
}

resolve_openasar_local_source() {
  local source_path="$openasar_source"

  if [[ "$source_path" == file://* ]]; then
    source_path="${source_path#file://}"
  fi

  if [[ "$source_path" == "~/"* ]]; then
    source_path="$HOME/${source_path#~/}"
  elif [[ "$source_path" == '$HOME/'* ]]; then
    source_path="$HOME/${source_path[7,-1]}"
  elif [[ "$source_path" == '${HOME}/'* ]]; then
    source_path="$HOME/${source_path[9,-1]}"
  elif [[ "$source_path" != /* ]]; then
    source_path="$PWD/$source_path"
  fi

  source_path="${source_path:A}"

  if [[ ! -f "$source_path" ]]; then
    print -u2 "Local OpenAsar payload was not found:"
    print -u2 "  $source_path"
    return 1
  fi

  if [[ ! -s "$source_path" ]]; then
    print -u2 "Local OpenAsar payload is empty:"
    print -u2 "  $source_path"
    return 1
  fi

  print -- "$source_path"
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
  local download_url
  local attempt

  if ! openasar_source_is_remote; then
    if [[ -s "$payload_path" ]]; then
      print "Using local OpenAsar payload:"
      print "  $payload_path"
      return 0
    fi

    print -u2 "Local OpenAsar payload is missing or empty:"
    print -u2 "  $payload_path"
    return 1
  fi

  download_url="$(openasar_remote_download_url)"

  print "Downloading OpenAsar payload to:"
  print "  $payload_path"
  print "From:"
  print "  $download_url"

  for attempt in {1..3}; do
    remove_download_artifacts "$payload_path"
    if download_file "$download_url" "$payload_path" && [[ -s "$payload_path" ]]; then
      rm -f -- "$payload_path.aria2"
      return 0
    fi

    remove_download_artifacts "$payload_path"
    if (( attempt == 3 )); then
      print -u2 "OpenAsar payload download failed after $attempt attempts:"
      print -u2 "  $payload_path"
      return 1
    fi

    print "OpenAsar payload download failed. Retrying in 3 seconds..."
    sleep 3
  done
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

download_installer_dmg() {
  local channel="$1"
  local app_name
  local download_url
  local dmg_path
  local attempt

  app_name="$(app_name_for_channel "$channel")"
  download_url="$(download_url_for_channel "$channel")"
  dmg_path="$(dmg_path_for_channel "$channel")"

  remove_download_artifacts "$dmg_path"

  print "Downloading $app_name installer to:"
  print "  $dmg_path"
  if [[ -n "$update_version" ]]; then
    print "Requested $app_name version:"
    print "  $update_version"
  fi
  print "From:"
  print "  $download_url"

  for attempt in {1..3}; do
    remove_download_artifacts "$dmg_path"
    if download_file "$download_url" "$dmg_path" && [[ -s "$dmg_path" ]]; then
      rm -f -- "$dmg_path.aria2"
      print "$app_name installer downloaded successfully:"
      print "  $dmg_path"
      return 0
    fi

    remove_download_artifacts "$dmg_path"
    if (( attempt == 3 )); then
      print -u2 "$app_name installer download failed after $attempt attempts."
      return 1
    fi

    print "$app_name installer download failed. Retrying in 3 seconds..."
    sleep 3
  done
}

download_and_replace_app() {
  local channel="$1"
  local app_name
  local app_path
  local executable_path
  local dmg_path
  local mount_point
  local mounted=false
  local mount_point_created=false
  local replacement_succeeded=false
  local source_app=""
  local attempt
  local -a found_apps

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  executable_path="$(executable_path_for_channel "$channel")"
  dmg_path="$(dmg_path_for_channel "$channel")"
  mount_point="$(available_mount_point_for_channel "$channel")"

  mkdir -p "$mount_point"
  mount_point_created=true

  cleanup_mount_and_dmg() {
    if [[ "$mounted" == true && -n "$mount_point" ]]; then
      hdiutil detach "$mount_point" -quiet >/dev/null 2>&1 || hdiutil detach "$mount_point" -force -quiet >/dev/null 2>&1 || true
    fi
    if [[ "$mount_point_created" == true ]]; then
      rm -rf -- "$mount_point"
    fi
    remove_download_artifacts "$dmg_path"
  }

  download_installer_dmg "$channel" || {
    print -u2 "$app_name was not replaced."
    cleanup_mount_and_dmg
    return 1
  }

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
      return 1
    fi

    for attempt in {1..3}; do
      guard_update_replacement "$channel"
      print "Replacing $app_name in /Applications (attempt $attempt of 3)..."

      if ! rm -rf -- "$app_path" || [[ -e "$app_path" ]]; then
        print -u2 "Failed to remove the existing $app_name app."
      else
        guard_update_replacement "$channel"

        if ditto "$source_app" "$app_path" &&
           [[ -d "$app_path" ]] &&
           [[ -x "$executable_path" ]] &&
           ! discord_is_running "$channel"; then
          replacement_succeeded=true
          break
        fi

        print -u2 "Failed to copy or verify the replacement $app_name app."
      fi

      guard_update_replacement "$channel"
      rm -rf -- "$app_path" || true

      if (( attempt < 3 )); then
        print "Retrying $app_name replacement in 2 seconds..."
        sleep 2
      fi
    done

    if [[ "$replacement_succeeded" != true ]]; then
      print -u2 "$app_name replacement failed after 3 attempts."
      print -u2 "$app_name was not successfully replaced."
      return 1
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
  local relative_target
  local -a failed_targets=()

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
    "$data_dir/ShipIt_request.json"
    "$data_dir"/0.0.*/
    "$data_dir"/app-*/
    "$data_dir/modules"
    "$data_dir/module_data"
    "$data_dir/download"
    "$data_dir/Cache"
    "$data_dir/Code Cache"
  )

  existing_targets=()
  for target in "${targets[@]}"; do
    [[ -e "$target" ]] && existing_targets+=("$target")
  done

  if (( ${#existing_targets[@]} == 0 )); then
    print "Warning: no $app_name installation files were detected."
    print "Expected at least one of:"
    print "  installer.db"
    print "  ShipIt_request.json"
    print "  0.0.*/"
    print "  app-*/"
    print "  modules/"
    print "  module_data/"
    print "  download/"
    print "  Cache/"
    print "  Code Cache/"
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
    relative_target="${target#$data_dir/}"
    if ! remove_installation_target "$target" "$relative_target"; then
      failed_targets+=("$relative_target")
    fi
  done

  if (( ${#failed_targets[@]} > 0 )); then
    print -u2 "$app_name installation cleanup did not remove every target:"
    for target in "${failed_targets[@]}"; do
      print -u2 "  $target"
    done
    return 1
  fi

  print "$app_name installation files cleaned successfully."
}

remove_installation_target() {
  local target="$1"
  local relative_target="$2"
  local attempt
  local remove_status=1

  for attempt in {1..3}; do
    if [[ ! -e "$target" ]]; then
      return 0
    fi

    chflags -RH nouchg,noschg "$target" >/dev/null 2>&1 || true
    chmod -RN "$target" >/dev/null 2>&1 || true
    chmod -R u+rwX "$target" >/dev/null 2>&1 || true
    xattr -cr "$target" >/dev/null 2>&1 || true

    if rm -rf -- "$target"; then
      remove_status=0
    else
      remove_status=$?
    fi

    if [[ ! -e "$target" ]]; then
      return 0
    fi

    if [[ -d "$target" ]]; then
      find -x "$target" -depth -mindepth 1 -exec chflags -H nouchg,noschg {} + >/dev/null 2>&1 || true
      find -x "$target" -depth -mindepth 1 -exec chmod -N {} + >/dev/null 2>&1 || true
      find -x "$target" -depth -mindepth 1 -exec chmod u+rwX {} + >/dev/null 2>&1 || true
      find -x "$target" -depth -mindepth 1 -exec rm -rf -- {} + >/dev/null 2>&1 || true

      if rmdir "$target" >/dev/null 2>&1 || [[ ! -e "$target" ]]; then
        return 0
      fi
    fi

    if (( attempt < 3 )); then
      print "Could not fully delete $relative_target yet. Retrying in 1 second..."
      sleep 1
    fi
  done

  print -u2 "Failed to delete $relative_target:"
  print -u2 "  $target"
  return "$remove_status"
}

guard_update_replacement() {
  local channel="$1"
  local app_name

  discord_is_running "$channel" || return 0

  app_name="$(app_name_for_channel "$channel")"
  print "$app_name restarted during update replacement. Stopping it and purging App Support again..."
  quit_discord "$channel"
  clean_channel "$channel" true
}

wait_for_app_bundle_ready() {
  local channel="$1"
  local timeout="${2:-10}"
  local app_name
  local app_path
  local executable_path
  local deadline

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  executable_path="$(executable_path_for_channel "$channel")"
  deadline=$(( SECONDS + timeout ))

  while (( SECONDS <= deadline )); do
    if [[ -d "$app_path" && -f "$app_path/Contents/Info.plist" && -x "$executable_path" ]]; then
      return 0
    fi

    sleep 1
  done

  print -u2 "$app_name app bundle is not ready to launch:"
  print -u2 "  $app_path"
  print -u2 "  $executable_path"
  return 1
}

refresh_target_launch_services_registration() {
  local channel="$1"
  local app_path
  local lsregister

  app_path="$(app_path_for_channel "$channel")"
  lsregister="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

  [[ -x "$lsregister" ]] || return 0
  "$lsregister" -f "$app_path" >/dev/null 2>&1 || true
}

print_indented_output() {
  local output="$1"
  local line

  while IFS= read -r line; do
    [[ -n "$line" ]] && print -u2 "  $line"
  done <<< "$output"
}

relaunch_channel_if_needed() {
  local channel="$1"
  local was_running_at_start="${2:-false}"
  local app_name
  local app_path
  local executable_path
  local attempt
  local open_output

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  executable_path="$(executable_path_for_channel "$channel")"

  if [[ "$was_running_at_start" == true ]]; then
    print "Relaunching $app_name because it was running when this script started..."
    for attempt in {1..3}; do
      wait_for_app_bundle_ready "$channel" 10 || return 1
      refresh_target_launch_services_registration "$channel"

      if open_output="$(open "$app_path" 2>&1)"; then
        return 0
      fi

      print -u2 "$app_name did not relaunch cleanly with open:"
      print_indented_output "$open_output"
      print "$app_name did not relaunch cleanly with open. Retrying..."
      sleep 1
    done

    if [[ -x "$executable_path" ]]; then
      print "Falling back to launching $app_name executable directly..."
      "$executable_path" >/dev/null 2>&1 &!
      for _ in {1..10}; do
        discord_is_running "$channel" && return 0
        sleep 1
      done

      print -u2 "$app_name executable fallback was started, but the running process was not detected."
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

if [[ -n "$update_version" ]]; then
  update_version="$(normalize_discord_version "$update_version")" || exit 2
fi

if [[ "$update_select_requested" == true ]]; then
  print_update_select_versions "$selected_channel" "$update_select_min_version"
  exit $?
fi

if [[ "$dl_requested" == true ]]; then
  download_installer_dmg "$selected_channel"
  exit $?
fi

validate_selected_data_dirs

openasar_payload=""
openasar_initial_download_succeeded=false
openasar_payload_is_temporary=false

if [[ "$openasar_requested" == true ]]; then
  if openasar_source_is_remote; then
    openasar_payload="$(openasar_payload_path)"
    openasar_payload_is_temporary=true
  elif ! openasar_payload="$(resolve_openasar_local_source)"; then
    openasar_payload=""
  fi

  cleanup_openasar_payload() {
    if [[ "$openasar_payload_is_temporary" == true && -n "$openasar_payload" ]]; then
      remove_download_artifacts "$openasar_payload"
    fi
  }

  trap cleanup_openasar_payload EXIT
  if [[ -n "$openasar_payload" ]] && download_openasar_payload "$openasar_payload"; then
    openasar_initial_download_succeeded=true
  else
    print -u2 "OpenAsar injection will be skipped because the payload could not be prepared."
  fi
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
    if [[ "$openasar_initial_download_succeeded" != true ]]; then
      print -u2 "Skipping OpenAsar injection for $app_name because the initial payload could not be prepared."
    elif [[ ! -s "$openasar_payload" ]]; then
      print "The initial OpenAsar payload is missing or was deleted before injection. Preparing it again..."
      if ! download_openasar_payload "$openasar_payload"; then
        print -u2 "Skipping OpenAsar injection for $app_name because the payload is unavailable."
      else
        inject_openasar "$channel" "$openasar_payload"
      fi
    else
      inject_openasar "$channel" "$openasar_payload"
    fi
  fi

  relaunch_channel_if_needed "$channel" "$was_running_at_start"
done

if [[ "$openasar_requested" == true ]]; then
  cleanup_openasar_payload
fi
