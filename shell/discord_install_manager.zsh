#!/usr/bin/env zsh

set -euo pipefail
setopt null_glob

script_name="${0:t}"
script_dir="${0:A:h}"
DEFAULT_OPENASAR_SOURCE="https://github.com/XxUnkn0wnxX/OpenAsar"
DEFAULT_DOWNLOAD_CONNECTIONS=16
DEFAULT_APPLICATIONS_ROOT="/Applications"

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

typeset -A channel_update_select_archive_filenames=(
  stable "Discord.zip"
  ptb "DiscordPTB.zip"
  canary "DiscordCanary.zip"
)

typeset -A channel_update_select_plist_paths=(
  stable "Discord.app/Contents/Info.plist"
  ptb "Discord PTB.app/Contents/Info.plist"
  canary "Discord Canary.app/Contents/Info.plist"
)

DISCORD_UPDATE_SELECT_MAX_SCAN_SPAN=100
DISCORD_UPDATE_SELECT_MIN_DEFAULT_JOBS=8
DISCORD_UPDATE_SELECT_MAX_JOBS=8
DISCORD_UPDATE_SELECT_DEFAULT_UPWARD_LIMIT=10
DISCORD_UPDATE_SELECT_MAX_UPWARD_LIMIT=100
ZIP_UPDATE_SELECT_EOCD_TAIL_BYTES_LIMIT=65557
ZIP_UPDATE_SELECT_CENTRAL_DIR_BYTES_LIMIT=4194304
ZIP_UPDATE_SELECT_COMPRESSED_PLIST_BYTES_LIMIT=1048576
ZIP_UPDATE_SELECT_UNCOMPRESSED_PLIST_BYTES_LIMIT=8388608

print_usage() {
  cat <<EOF
Usage:
  $script_name --channel stable|ptb|canary|all [...] [--update [version]] [--openasar] [--openasar-source url-or-path] [--lock] [--BD]
  $script_name --channel stable|ptb|canary --dl [version]
  $script_name --channel stable|ptb|canary --update-select [minimum-version|start-end]
  $script_name --help

Options:
  --channel             Select Discord channel(s) to clean. Valid BetterDiscord app wrappers are normally unwrapped.
                        Use "all" for Stable, PTB, and Canary.
  --update              Clean updater files, then download and replace the selected Discord app.
                        Optionally pass a version such as 0.0.1177 to download that CDN build.
  --lock                Lock the selected channel to a specific version. Requires --update with an explicit version
                        and either --openasar or --openasar-source.
  --dl                  Download the selected Discord DMG only, then exit.
                        Optionally pass a version such as 0.0.1177 to download that CDN build.
  --update-select       Print available DMG versions for one selected channel, then exit.
                        Uses bounded range probes (no full ZIP downloads) and supports 101-build ranges.
                        Optionally pass a minimum version such as 900 or a range such as 500-400.
                        Bare --update-select finds and prints the highest CDN artifact in a bounded window.
  --openasar            Download and inject OpenAsar into the selected Discord app.
  --openasar-source     Use a specific OpenAsar repo URL, app.asar URL, or local path. Implies --openasar.
  --BD                  Preserve a valid BetterDiscord wrapper and replace its nested betterdiscord.app.asar.
                        Falls back to normal app.asar when no wrapper exists. Cannot be used with --update.
  --help                Show this help message.

Examples:
  $script_name --channel stable
  $script_name --channel ptb --update
  $script_name --channel canary --dl 0.0.1177
  $script_name --channel canary --update-select 500-400
  $script_name --channel stable ptb --openasar-source "\$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" --BD
  $script_name --channel all --update --openasar
  $script_name --channel stable --openasar-source "\$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" --update 401 --lock

Notes:
  This Discord install manager supports macOS only.
  --channel without --update cleans updater/core files and unwraps a valid BetterDiscord app wrapper.
  Unwrapping restores betterdiscord.app.asar to app.asar without identifying or replacing its payload.
  --update must be paired with --channel so the target app is explicit.
  --update skips BetterDiscord unwrap because the existing app bundle is replaced.
  --dl must be paired with one channel and only downloads the DMG.
  --update without a version supports multiple channels and --channel all.
  --update with a version, --dl, and --update-select require a single selected channel.
  --update-select only prints versions; it does not clean, update, inject, or relaunch anything.
  --update-select ranges are limited to 100 version steps (101 inclusive builds), for example 500-400.
  update-select uses bounded parallel probing and reads minimal ZIP metadata only for versions it reports.
  DMG HEAD is the availability and Last-Modified source for update-select output.
  --update-select defaults to 8 workers and reads DISCORD_UPDATE_SELECT_JOBS (maximum 8).
  Bare --update-select probes 10 versions above the manifest by default.
  DISCORD_UPDATE_SELECT_UPWARD_LIMIT changes that window (maximum 100).
  --openasar must be paired with --channel so the target app is explicit.
  --lock requires --update with an explicit version and either --openasar or --openasar-source.
  --lock supports exactly one named channel and cannot be combined with --BD or --update-select.
  --BD requires --openasar or --openasar-source and cannot be combined with --update.
  With --BD, a valid BetterDiscord wrapper is preserved; an absent wrapper uses standalone app.asar.
  OpenAsar is installed atomically, verified before relaunch, and checked again after relaunch.
  If startup replaces it, the manager stops that channel and retries injection once.
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

selected_channels=()
update_requested=false
dl_requested=false
update_select_requested=false
update_select_min_version=""
update_version=""
lock_version=""
lock_requested=false
openasar_requested=false
openasar_betterdiscord_requested=false
openasar_source="${OPENASAR_SOURCE:-${OPENASAR_RELEASE_URL:-$DEFAULT_OPENASAR_SOURCE}}"
explicit_channel=false

while (( $# > 0 )); do
  case "$1" in
    --help|-h)
      print_usage
      exit 0
      ;;
    --channel)
      shift
      (( $# > 0 )) || fail_usage "Missing value for --channel."
      while (( $# > 0 )) && [[ "$1" != --* ]]; do
        selected_channels+=("$1")
        explicit_channel=true
        shift
      done
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
    --lock)
      lock_requested=true
      shift
      ;;
    --openasar-source)
      if (( $# < 2 )) || [[ -z "$2" || "$2" == --* ]]; then
        fail_usage "Missing value for --openasar-source."
      fi
      openasar_requested=true
      openasar_source="$2"
      shift 2
      ;;
    --BD)
      openasar_betterdiscord_requested=true
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

if [[ "$dl_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--dl requires --channel stable|ptb|canary."
fi

if [[ "$update_select_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--update-select requires --channel stable|ptb|canary."
fi

if [[ "$openasar_requested" == true && "$explicit_channel" != true ]]; then
  fail_usage "--openasar requires --channel stable|ptb|canary|all."
fi

if [[ "$openasar_betterdiscord_requested" == true && "$openasar_requested" != true ]]; then
  fail_usage "--BD requires --openasar or --openasar-source."
fi

if [[ "$lock_requested" == true && "$update_requested" != true ]]; then
  fail_usage "--lock requires --update."
fi

if [[ "$lock_requested" == true && -z "$update_version" ]]; then
  fail_usage "--lock requires --update with an explicit version such as 401 or 0.0.401."
fi

if [[ "$lock_requested" == true && "$openasar_requested" != true ]]; then
  fail_usage "--lock requires --openasar or --openasar-source."
fi

if [[ "$lock_requested" == true && "$update_select_requested" == true ]]; then
  fail_usage "--lock cannot be combined with --update-select."
fi

if [[ "$lock_requested" == true && "$openasar_betterdiscord_requested" == true ]]; then
  fail_usage "--lock cannot be combined with --BD."
fi

if [[ "$openasar_betterdiscord_requested" == true && "$update_requested" == true ]]; then
  fail_usage "--BD cannot be combined with --update because updating replaces the BetterDiscord wrapper."
fi

if [[ "$explicit_channel" != true ]]; then
  fail_usage "No channel specified. Use --channel stable|ptb|canary|all."
fi

expanded_channels=()
typeset -A selected_channel_seen=()
saw_all_channel=false

for selected_channel in "${selected_channels[@]}"; do
  case "$selected_channel" in
    stable|ptb|canary)
      if [[ -z "${selected_channel_seen[$selected_channel]-}" ]]; then
        expanded_channels+=("$selected_channel")
        selected_channel_seen[$selected_channel]=1
      fi
      ;;
    all)
      saw_all_channel=true
      ;;
    *)
      fail_usage "Invalid channel: $selected_channel"
      ;;
  esac
done

if [[ "$saw_all_channel" == true && "${#selected_channels[@]}" -gt 1 ]]; then
  fail_usage "--channel all cannot be combined with named channels."
fi

if [[ "$saw_all_channel" == true ]]; then
  selected_channels=(stable ptb canary)
else
  selected_channels=("${expanded_channels[@]}")
fi

if [[ "$lock_requested" == true && "${#selected_channels[@]}" -ne 1 ]]; then
  fail_usage "--lock requires exactly one channel: stable, ptb, or canary."
fi

if [[ "$update_select_requested" == true && "${#selected_channels[@]}" -ne 1 ]]; then
  fail_usage "--update-select only supports one channel at a time."
fi

if [[ "$dl_requested" == true && "${#selected_channels[@]}" -ne 1 ]]; then
  fail_usage "--dl only supports one channel at a time."
fi

if [[ "$dl_requested" == true && ( "$update_requested" == true || "$update_select_requested" == true || "$openasar_requested" == true ) ]]; then
  fail_usage "--dl only downloads a DMG and cannot be combined with --update, --update-select, or --openasar."
fi

if [[ "$update_select_requested" == true && ( "$update_requested" == true || "$openasar_requested" == true ) ]]; then
  fail_usage "--update-select only prints versions and cannot be combined with --update or --openasar."
fi

if [[ -n "$update_version" && "${#selected_channels[@]}" -ne 1 ]]; then
  fail_usage "--update or --dl with a version only supports one channel at a time."
fi

typeset -A channel_was_running=()
typeset -A channel_download_versions=()
typeset -A channel_betterdiscord_wrapper=()
typeset -A channel_recovery_disabled=()
multiple_channels=false
(( ${#selected_channels[@]} > 1 )) && multiple_channels=true
single_selected_channel="${selected_channels[1]}"

app_name_for_channel() {
  print -- "${channel_app_names[$1]}"
}

app_path_for_channel() {
  print -- "$DEFAULT_APPLICATIONS_ROOT/$(app_name_for_channel "$1").app"
}

app_relative_path_for_channel() {
  print -- "$(app_name_for_channel "$1").app"
}

executable_path_for_channel() {
  local channel="$1"
  print -- "$(app_path_for_channel "$channel")/Contents/MacOS/$(app_name_for_channel "$channel")"
}

data_dir_for_channel() {
  print -- "${channel_data_dirs[$1]}"
}

settings_path_for_channel() {
  print -- "$(data_dir_for_channel "$1")/settings.json"
}

settings_file_signature() {
  local target="$1"
  local metadata_before
  local metadata_after
  local digest

  [[ -f "$target" && ! -L "$target" ]] || return 1
  metadata_before="$(/usr/bin/stat -f '%d:%i:%z:%m:%c' "$target" 2>/dev/null)" || return 1
  digest="$(/usr/bin/shasum -a 256 < "$target" 2>/dev/null)" || return 1
  metadata_after="$(/usr/bin/stat -f '%d:%i:%z:%m:%c' "$target" 2>/dev/null)" || return 1
  [[ "$metadata_before" == "$metadata_after" ]] || return 1

  print -r -- "$metadata_after:$digest"
}

lock_settings_payload_from_file() {
  local settings_path="$1"
  local lock_suffix="$2"

/usr/bin/osascript -l JavaScript - "$settings_path" "$lock_suffix" <<'JXA'
ObjC.import("Foundation");

function isObject(value) {
  return Object.prototype.toString.call(value) === "[object Object]";
}

function assertSafeNumbers(value) {
  if (typeof value === "number") {
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))) {
      throw new Error("The settings file contains a number that cannot be preserved safely.");
    }
    return;
  }

  if (Array.isArray(value)) {
    value.forEach(assertSafeNumbers);
    return;
  }

  if (isObject(value)) {
    Object.keys(value).forEach(function (key) {
      assertSafeNumbers(value[key]);
    });
  }
}

function run(argv) {
  var settingsPath = String(argv[0]);
  var lockSuffix = String(argv[1]);
  var fileManager = $.NSFileManager.defaultManager;
  var fileData;
  var rawJSON;
  var settingsObject = {};

  if (fileManager.fileExistsAtPath(settingsPath)) {
    fileData = fileManager.contentsAtPath(settingsPath);
    if (fileData === null) {
      throw new Error("The settings file cannot be read.");
    }

    rawJSON = $.NSString.alloc.initWithDataEncoding(fileData, $.NSUTF8StringEncoding).js;
    if (rawJSON === null) {
      throw new Error("The settings file cannot be decoded.");
    }

    try {
      settingsObject = JSON.parse(rawJSON);
    } catch (_error) {
      throw new Error("The settings file contains malformed JSON.");
    }

    if (!isObject(settingsObject)) {
      throw new Error("The settings file root is not an object.");
    }

    assertSafeNumbers(settingsObject);

    if (settingsObject.openasar !== undefined && !isObject(settingsObject.openasar)) {
      throw new Error("The settings.openasar value is not an object.");
    }
  }

  settingsObject.openasar = settingsObject.openasar || {};
  settingsObject.openasar.VersionLock = String(lockSuffix);
  return JSON.stringify(settingsObject, null, 2);
}
JXA
}

verify_lock_settings_payload() {
  local settings_path="$1"
  local expected_lock="$2"

/usr/bin/osascript -l JavaScript - "$settings_path" "$expected_lock" <<'JXA' || return 1
ObjC.import("Foundation");

function isObject(value) {
  return Object.prototype.toString.call(value) === "[object Object]";
}

function run(argv) {
  var settingsPath = String(argv[0]);
  var expectedLock = String(argv[1]);
  var fileManager = $.NSFileManager.defaultManager;
  var fileData = fileManager.contentsAtPath(settingsPath);
  var rawJSON;
  var settingsObject;

  if (fileData === null) {
    throw new Error("The settings file cannot be read.");
  }

  rawJSON = $.NSString.alloc.initWithDataEncoding(fileData, $.NSUTF8StringEncoding).js;
  if (rawJSON === null) {
    throw new Error("The settings file cannot be decoded.");
  }

  try {
    settingsObject = JSON.parse(rawJSON);
  } catch (_error) {
    throw new Error("The settings file contains malformed JSON.");
  }

  if (!isObject(settingsObject)) {
    throw new Error("The settings file root is not an object.");
  }

  if (settingsObject.openasar === undefined || settingsObject.openasar === null) {
    throw new Error("The settings file is missing an openasar object.");
  }

  if (!isObject(settingsObject.openasar)) {
    throw new Error("The settings.openasar value is not an object.");
  }

  if (settingsObject.openasar.VersionLock !== expectedLock) {
    throw new Error("The settings.openasar.VersionLock value did not match.");
  }

  return "";
}
JXA
  return 0
}

preflight_lock_settings_target() {
  local channel="$1"
  local app_name
  local data_dir
  local settings_path

  app_name="$(app_name_for_channel "$channel")"
  data_dir="$(data_dir_for_channel "$channel")"
  settings_path="$(settings_path_for_channel "$channel")"

  if [[ -L "$data_dir" ]]; then
    print -u2 "Refusing to write --lock because $app_name data directory is a symlink:"
    print -u2 "  $data_dir"
    return 1
  fi

  if [[ -e "$data_dir" && ! -d "$data_dir" ]]; then
    print -u2 "Refusing to write --lock because $app_name data directory is not a directory:"
    print -u2 "  $data_dir"
    return 1
  fi

  if [[ -L "$settings_path" ]]; then
    print -u2 "Refusing to write --lock because settings.json is a symlink:"
    print -u2 "  $settings_path"
    return 1
  fi

  if [[ -e "$settings_path" && ! -f "$settings_path" ]]; then
    print -u2 "Refusing to write --lock because settings.json is not a regular file:"
    print -u2 "  $settings_path"
    return 1
  fi

  if [[ -e "$settings_path" ]]; then
    if ! lock_settings_payload_from_file "$settings_path" "0" >/dev/null; then
      print -u2 "Cannot write --lock because settings.json is invalid:"
      print -u2 "  $settings_path"
      return 1
    fi
  fi
}

write_lock_settings() {
  local channel="$1"
  local lock_suffix="$2"
  local app_name
  local data_dir
  local settings_path
  local staging_path=""
  local before_signature=""
  local current_signature
  local payload
  local settings_existed=false

  app_name="$(app_name_for_channel "$channel")"
  data_dir="$(data_dir_for_channel "$channel")"
  settings_path="$(settings_path_for_channel "$channel")"

  preflight_lock_settings_target "$channel" || return 1

  if ! /bin/mkdir -p "$data_dir"; then
    print -u2 "Failed to create settings directory for $app_name:"
    print -u2 "  $data_dir"
    return 1
  fi

  preflight_lock_settings_target "$channel" || return 1

  if [[ -f "$settings_path" ]]; then
    settings_existed=true
    before_signature="$(settings_file_signature "$settings_path")"
    if [[ -z "$before_signature" ]]; then
      print -u2 "Failed to capture a stable settings snapshot for $app_name:"
      print -u2 "  $settings_path"
      return 1
    fi
  fi

  if ! staging_path="$(/usr/bin/mktemp "${settings_path}.discord-install-manager-XXXXXX")" ||
     [[ -z "$staging_path" ]]; then
    print -u2 "Failed to create temporary settings staging path for $app_name:"
    print -u2 "  $settings_path"
    return 1
  fi

  {
    if [[ "$settings_existed" == true ]]; then
      current_signature="$(settings_file_signature "$settings_path")"
      if [[ "$before_signature" != "$current_signature" ]]; then
        print -u2 "Refusing to write --lock because settings.json changed during update:"
        print -u2 "  $settings_path"
        return 1
      fi
      /bin/cp -p -- "$settings_path" "$staging_path" || return 1
    else
      if ! /bin/chmod 600 "$staging_path"; then
        print -u2 "Failed to secure temporary settings for $app_name:"
        print -u2 "  $staging_path"
        return 1
      fi
    fi

    payload="$(lock_settings_payload_from_file "$settings_path" "$lock_suffix")" || return 1
    printf "%s" "$payload" > "$staging_path" || return 1

    if ! verify_lock_settings_payload "$staging_path" "$lock_suffix"; then
      print -u2 "Failed to verify prepared settings for $app_name:"
      print -u2 "  $settings_path"
      return 1
    fi

    if [[ -L "$data_dir" || ! -d "$data_dir" ]]; then
      print -u2 "Refusing to write --lock because the $app_name data directory changed during update:"
      print -u2 "  $data_dir"
      return 1
    fi

    if [[ "$settings_existed" == true ]]; then
      current_signature="$(settings_file_signature "$settings_path")"
      if [[ "$before_signature" != "$current_signature" ]]; then
        print -u2 "Refusing to write --lock because settings.json changed during update:"
        print -u2 "  $settings_path"
        return 1
      fi
    elif [[ -e "$settings_path" || -L "$settings_path" ]]; then
      print -u2 "Refusing to write --lock because settings.json appeared during update:"
      print -u2 "  $settings_path"
      return 1
    fi

    /bin/mv -f -- "$staging_path" "$settings_path" || return 1
    if ! verify_lock_settings_payload "$settings_path" "$lock_suffix"; then
      print -u2 "Failed to verify committed settings for $app_name:"
      print -u2 "  $settings_path"
      return 1
    fi

    print "OpenAsar VersionLock set for $app_name:"
    print "  $lock_suffix"
  } always {
    [[ -f "$staging_path" ]] && /bin/rm -f -- "$staging_path"
  }
}

typeset -a betterdiscord_wrapper_issues=()

inspect_betterdiscord_wrapper() {
  local channel="$1"
  local app_relative
  local app_path
  local resources_dir
  local wrapper_dir
  local marker_path
  local loader_path
  local package_path
  local wrapped_asar
  local wrapped_app_dir
  local top_level_asar
  local entry
  local entry_name
  local -a wrapper_entries
  local -a stale_unwrap_paths

  app_relative="$(app_relative_path_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  resources_dir="$app_path/Contents/Resources"
  wrapper_dir="$resources_dir/app"
  marker_path="$wrapper_dir/.betterdiscord-inject.json"
  loader_path="$wrapper_dir/index.js"
  package_path="$wrapper_dir/package.json"
  wrapped_asar="$resources_dir/betterdiscord.app.asar"
  wrapped_app_dir="$resources_dir/betterdiscord.app"
  top_level_asar="$resources_dir/app.asar"
  betterdiscord_wrapper_issues=()

  if [[ ! -e "$wrapper_dir" && ! -L "$wrapper_dir" && ! -e "$wrapped_asar" && ! -L "$wrapped_asar" && ! -e "$wrapped_app_dir" && ! -L "$wrapped_app_dir" ]]; then
    return 1
  fi

  if [[ ! -d "$wrapper_dir" || -L "$wrapper_dir" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/ is missing or is not a real directory")
  else
    wrapper_entries=("$wrapper_dir"/*(DN))
    for entry in "${wrapper_entries[@]}"; do
      entry_name="${entry:t}"
      case "$entry_name" in
        .betterdiscord-inject.json|index.js|package.json)
          ;;
        *)
          betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/$entry_name is not part of the BetterDiscord wrapper contract")
          ;;
      esac
    done
  fi

  if [[ ! -f "$marker_path" || -L "$marker_path" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/.betterdiscord-inject.json is missing or invalid")
  elif ! BETTERDISCORD_EXPECTED_CHANNEL="$channel" /usr/bin/perl -MJSON::PP -0777 -e '
    my $raw = <>;
    my $data = eval { JSON::PP->new->decode($raw) };
    my $expected_channel = $ENV{BETTERDISCORD_EXPECTED_CHANNEL};
    exit 1 unless ref($data) eq "HASH";
    exit 1 unless defined($data->{schema}) && "$data->{schema}" eq "1";
    exit 1 unless defined($data->{owner}) && $data->{owner} eq "betterdiscord";
    exit 1 unless defined($data->{style}) && $data->{style} eq "app-wrapper";
    exit 1 unless defined($data->{channel}) && $data->{channel} eq $expected_channel;
    exit 1 unless defined($data->{mode}) && ($data->{mode} eq "release" || $data->{mode} eq "dev");
    exit 1 unless defined($data->{loader}) && $data->{loader} eq "index.js";
    exit 1 unless defined($data->{payload}) && $data->{payload} eq "../betterdiscord.app.asar";
    exit 1 unless defined($data->{bdPath}) && !ref($data->{bdPath}) && length($data->{bdPath});
    exit 1 unless defined($data->{installationId}) && !ref($data->{installationId}) && length($data->{installationId});
    exit 1 if exists($data->{helperRuntime}) && (ref($data->{helperRuntime}) || !length($data->{helperRuntime}));
  ' "$marker_path"; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/.betterdiscord-inject.json does not match the supported BetterDiscord wrapper contract")
  fi

  if [[ ! -s "$loader_path" || -L "$loader_path" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/index.js is missing or invalid")
  else
    if ! /usr/bin/grep -Fq -- '// __betterdiscord_inject_meta__' "$loader_path"; then
      betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/index.js is missing the BetterDiscord ownership marker")
    fi
    if ! /usr/bin/grep -Fq -- 'module.exports = require("../betterdiscord.app.asar");' "$loader_path"; then
      betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/index.js does not load ../betterdiscord.app.asar")
    fi
  fi

  if [[ ! -s "$package_path" || -L "$package_path" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/package.json is missing or invalid")
  elif ! /usr/bin/perl -MJSON::PP -0777 -e '
    my $raw = <>;
    my $data = eval { JSON::PP->new->decode($raw) };
    exit 1 unless ref($data) eq "HASH";
    exit 1 unless defined($data->{main}) && ($data->{main} eq "index.js" || $data->{main} eq "./index.js");
  ' "$package_path"; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app/package.json does not use index.js as its main entry")
  fi

  if [[ ! -s "$wrapped_asar" || -L "$wrapped_asar" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/betterdiscord.app.asar is missing or invalid")
  fi

  if [[ -e "$wrapped_app_dir" || -L "$wrapped_app_dir" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/betterdiscord.app is an unsupported wrapped directory")
  fi

  if [[ -e "$top_level_asar" || -L "$top_level_asar" ]]; then
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/app.asar already exists beside the BetterDiscord wrapper")
  fi

  stale_unwrap_paths=("$resources_dir"/.betterdiscord-app-unwrapping-*(DN))
  for entry in "${stale_unwrap_paths[@]}"; do
    betterdiscord_wrapper_issues+=("$app_relative/Contents/Resources/${entry:t} is a stale BetterDiscord unwrap path")
  done

  (( ${#betterdiscord_wrapper_issues[@]} == 0 )) || return 2
  return 0
}

validate_selected_betterdiscord_wrappers() {
  local channel
  local app_relative
  local layout_status
  local issue

  for channel in "${selected_channels[@]}"; do
    if inspect_betterdiscord_wrapper "$channel"; then
      channel_betterdiscord_wrapper[$channel]=true
      continue
    else
      layout_status=$?
    fi

    if (( layout_status == 1 )); then
      channel_betterdiscord_wrapper[$channel]=false
      continue
    fi

    app_relative="$(app_relative_path_for_channel "$channel")"
    print -u2 "Refusing to modify $app_relative because its BetterDiscord wrapper layout is incomplete or ambiguous:"
    for issue in "${betterdiscord_wrapper_issues[@]}"; do
      print -u2 "  $issue"
    done
    return 1
  done
}

stop_betterdiscord_recovery_helper() {
  local bootstrap_dir="$1"
  local app_relative="$2"
  local pid_path="$bootstrap_dir/betterdiscord-update-helper.pid"
  local helper_path="$bootstrap_dir/betterdiscord-update-helper.zsh"
  local helper_pid
  local helper_pgid
  local helper_command
  local attempt

  [[ -e "$pid_path" || -L "$pid_path" ]] || return 0
  if [[ -L "$pid_path" ]]; then
    print -u2 "Refusing to stop BetterDiscord recovery for $app_relative because betterdiscord-update-helper.pid is a symlink."
    return 1
  fi

  helper_pid="$(/bin/cat "$pid_path" 2>/dev/null || true)"
  helper_pid="${helper_pid//[[:space:]]/}"
  if [[ "$helper_pid" != <-> || "$helper_pid" -le 0 ]]; then
    print "Removed an invalid BetterDiscord recovery PID file for $app_relative"
    rm -f -- "$pid_path"
    return 0
  fi

  helper_command="$(/bin/ps -p "$helper_pid" -o command= 2>/dev/null || true)"
  helper_pgid="$(/bin/ps -p "$helper_pid" -o pgid= 2>/dev/null || true)"
  helper_pgid="${helper_pgid//[[:space:]]/}"
  if [[ -z "$helper_command" ]]; then
    print "Removed a stale BetterDiscord recovery PID file for $app_relative (PID $helper_pid is not running)"
    rm -f -- "$pid_path"
    return 0
  fi

  if [[ "$helper_command" != "zsh -f $helper_path "* \
      && "$helper_command" != "/bin/zsh -f $helper_path "* \
      && "$helper_command" != "/usr/bin/zsh -f $helper_path "* \
      && "$helper_command" != "/usr/bin/env zsh -f $helper_path "* \
      || "$helper_command" != *"$bootstrap_dir"* \
      || "$helper_pgid" != "$helper_pid" ]]; then
    print -u2 "Refusing to signal PID $helper_pid for $app_relative because it is not the validated BetterDiscord recovery process-group owner."
    return 1
  fi

  print "Stopping BetterDiscord recovery helper for $app_relative (PID $helper_pid and its helper descendants)"
  /bin/kill -TERM -- "-$helper_pgid" 2>/dev/null || true
  for attempt in {1..20}; do
    /bin/kill -0 "$helper_pid" 2>/dev/null || break
    /bin/sleep 0.1
  done

  if /bin/kill -0 "$helper_pid" 2>/dev/null; then
    helper_command="$(/bin/ps -p "$helper_pid" -o command= 2>/dev/null || true)"
    helper_pgid="$(/bin/ps -p "$helper_pid" -o pgid= 2>/dev/null || true)"
    helper_pgid="${helper_pgid//[[:space:]]/}"
    if [[ "$helper_command" != "zsh -f $helper_path "* \
        && "$helper_command" != "/bin/zsh -f $helper_path "* \
        && "$helper_command" != "/usr/bin/zsh -f $helper_path "* \
        && "$helper_command" != "/usr/bin/env zsh -f $helper_path "* \
        || "$helper_command" != *"$bootstrap_dir"* \
        || "$helper_pgid" != "$helper_pid" ]]; then
      print -u2 "Refusing a forced helper stop for $app_relative because PID $helper_pid no longer matches BetterDiscord recovery."
      return 1
    fi
    print "BetterDiscord recovery helper did not stop cleanly for $app_relative; stopping its validated process group"
    /bin/kill -KILL -- "-$helper_pgid" 2>/dev/null || true
    for attempt in {1..10}; do
      /bin/kill -0 "$helper_pid" 2>/dev/null || break
      /bin/sleep 0.1
    done
    if /bin/kill -0 "$helper_pid" 2>/dev/null; then
      print -u2 "BetterDiscord recovery helper PID $helper_pid is still present for $app_relative after the validated process-group stop."
      return 1
    fi
  fi

  rm -f -- "$pid_path"
  print "Stopped BetterDiscord recovery helper for $app_relative"
}

has_fork_betterdiscord_recovery() {
  local bootstrap_dir="$1"
  local helper_path="$bootstrap_dir/betterdiscord-update-helper.zsh"

  [[ -f "$helper_path" && ! -L "$helper_path" ]]
}

disable_betterdiscord_recovery_for_unwrap() {
  local channel="$1"
  local app_relative
  local data_dir
  local bootstrap_dir
  local action_description

  [[ "${channel_betterdiscord_wrapper[$channel]:-false}" == true ]] || return 0

  app_relative="$(app_relative_path_for_channel "$channel")"
  data_dir="$(data_dir_for_channel "$channel")"
  bootstrap_dir="$data_dir/betterdiscord-bootstrap"
  action_description="BetterDiscord unwrap for $app_relative"
  [[ "$update_requested" == true ]] && action_description="$app_relative replacement"

  if [[ ! -d "$data_dir" ]]; then
    print "No BetterDiscord recovery state exists for $app_relative; continuing with $action_description"
    return 0
  fi

  if ! has_fork_betterdiscord_recovery "$bootstrap_dir"; then
    print "No fork-specific BetterDiscord recovery helper detected for $app_relative; continuing with $action_description"
    return 0
  fi

  if [[ -L "$bootstrap_dir/recovery-disabled" ]]; then
    print -u2 "Refusing to disable BetterDiscord update recovery for $app_relative because recovery-disabled is a symlink."
    return 1
  fi

  if [[ -e "$bootstrap_dir/recovery-disabled" ]]; then
    print "BetterDiscord update recovery was already disabled for $app_relative"
  else
    if ! mkdir -p "$bootstrap_dir"; then
      print -u2 "Cannot disable BetterDiscord update recovery before $action_description."
      return 1
    fi

    if ! print -- "$(date +%s)" > "$bootstrap_dir/recovery-disabled"; then
      print -u2 "Cannot disable BetterDiscord update recovery before $action_description."
      return 1
    fi
  fi

  channel_recovery_disabled[$channel]=true
  stop_betterdiscord_recovery_helper "$bootstrap_dir" "$app_relative" || return 1
  if ! rm -f -- "$bootstrap_dir/update-pending.json" "$bootstrap_dir/wrapper-ready.json" "$bootstrap_dir/active-run"; then
    print -u2 "Cannot clear BetterDiscord recovery state before $action_description."
    return 1
  fi
  if ! remove_installation_target "$bootstrap_dir/recovery-runs" "$app_relative BetterDiscord recovery runs" false; then
    print -u2 "Cannot clear BetterDiscord recovery run assets before $action_description."
    return 1
  fi
  print "Disabled BetterDiscord update recovery before $action_description"
}

restore_recovery_for_wrappers_left_installed() {
  local channel
  local data_dir
  local app_relative

  for channel in "${selected_channels[@]}"; do
    [[ "${channel_recovery_disabled[$channel]:-false}" == true ]] || continue
    if inspect_betterdiscord_wrapper "$channel"; then
      data_dir="$(data_dir_for_channel "$channel")"
      app_relative="$(app_relative_path_for_channel "$channel")"
      if rm -f -- "$data_dir/betterdiscord-bootstrap/recovery-disabled"; then
        print "Re-enabled BetterDiscord update recovery because $app_relative remains wrapped"
      else
        print -u2 "Could not re-enable BetterDiscord update recovery for $app_relative"
      fi
    fi
  done
}

download_url_for_channel() {
  local channel="$1"
  local version

  if [[ -n "$update_version" ]]; then
    version="$(download_version_for_channel "$channel")" || return 1
    versioned_download_url_for_channel "$channel" "$version"
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

versioned_update_select_archive_for_channel() {
  local channel="$1"
  local version="$2"

  version="$(normalize_discord_version "$version")" || return 1
  print -- "https://${channel_cdn_hosts[$channel]}/apps/osx/$version/${channel_update_select_archive_filenames[$channel]}"
}

versioned_update_select_plist_path_for_channel() {
  local channel="$1"
  print -- "${channel_update_select_plist_paths[$channel]}"
}

update_select_worker_count() {
  local requested_jobs

  requested_jobs="${DISCORD_UPDATE_SELECT_JOBS:-$DISCORD_UPDATE_SELECT_MIN_DEFAULT_JOBS}"
  if [[ "$requested_jobs" == <-> ]]; then
    if (( requested_jobs < 1 )); then
      requested_jobs="$DISCORD_UPDATE_SELECT_MIN_DEFAULT_JOBS"
    elif (( requested_jobs > DISCORD_UPDATE_SELECT_MAX_JOBS )); then
      requested_jobs="$DISCORD_UPDATE_SELECT_MAX_JOBS"
    fi
  else
    requested_jobs="$DISCORD_UPDATE_SELECT_MIN_DEFAULT_JOBS"
  fi

  print -- "$requested_jobs"
}

update_select_upward_limit() {
  local requested_limit

  requested_limit="${DISCORD_UPDATE_SELECT_UPWARD_LIMIT:-$DISCORD_UPDATE_SELECT_DEFAULT_UPWARD_LIMIT}"
  if [[ "$requested_limit" == <-> ]]; then
    if (( requested_limit < 1 )); then
      requested_limit="$DISCORD_UPDATE_SELECT_DEFAULT_UPWARD_LIMIT"
    elif (( requested_limit > DISCORD_UPDATE_SELECT_MAX_UPWARD_LIMIT )); then
      requested_limit="$DISCORD_UPDATE_SELECT_MAX_UPWARD_LIMIT"
    fi
  else
    requested_limit="$DISCORD_UPDATE_SELECT_DEFAULT_UPWARD_LIMIT"
  fi

  print -- "$requested_limit"
}

http_code_from_headers() {
  local header_path="$1"
  /usr/bin/perl -ne '
    if (/^HTTP\//) {
      if (/^HTTP\/\S+\s+([0-9]{3})/) {
        $http_code = $1;
      }
    }
    END {
      print $http_code || "";
    }
  ' "$header_path"
}

content_range_from_headers() {
  local header_path="$1"
  /usr/bin/perl -ne '
    if (/^HTTP\//) {
      if (/^HTTP\/\S+\s+([0-9]{3})/) {
        $http_code = $1;
      }
      $content_start = "";
      $content_end = "";
      $content_total = "";
      next;
    }

    if (/^Content-Range:\s*bytes\s+(\d+)-(\d+)\/(\d+)/i) {
      $content_start = $1;
      $content_end = $2;
      $content_total = $3;
    }

    END {
      print(
        ($http_code || "") . " " .
        ($content_start // "") . " " .
        ($content_end // "") . " " .
        ($content_total // "")
      );
    }
  ' "$header_path"
}

last_modified_from_headers() {
  local header_path="$1"
  /usr/bin/perl -ne '
    s/\r?\n\z//;
    if (/^HTTP\//) {
      $last_modified = "";
    }
    if (/^Last-Modified:\s*(.+)$/i) {
      $last_modified = $1;
    }
    END {
      print $last_modified || "";
    }
  ' "$header_path"
}

plist_string_from_info_plist() {
  local plist_path="$1"
  local key="$2"

  /usr/bin/plutil -extract "$key" xml1 -o - "$plist_path" 2>/dev/null | \
    /usr/bin/perl -ne 'if (/\<string\>([^<]+)\<\/string\>/) { print $1; exit } '
}

download_update_select_range() {
  local url="$1"
  local start="$2"
  local end="$3"
  local output="$4"
  local headers="$5"
  local expected_size="$6"
  local expected_total="${7:-}"
  local code
  local range_start
  local range_end
  local range_total
  local bytes_written

  /bin/mkdir -p -- "$(/usr/bin/dirname "$output")" || return 1

  if ! curl --location --fail --silent \
      --dump-header "$headers" \
      --max-filesize "$expected_size" \
      --range "${start}-${end}" \
      --output "$output" \
      "$url"; then
    return 1
  fi

  read -r code range_start range_end range_total <<<"$(content_range_from_headers "$headers")"
  if [[ "$code" != 206 ]]; then
    return 1
  fi

  if [[ -z "$range_start" || -z "$range_end" || -z "$range_total" ]]; then
    return 1
  fi

  if (( range_total <= range_end )); then
    return 1
  fi

  if (( range_start != start || range_end != end )); then
    return 1
  fi

  if [[ -n "$expected_total" ]] && (( range_total != expected_total )); then
    return 1
  fi

  bytes_written="$(/usr/bin/wc -c < "$output" | /usr/bin/awk '{ print $1 }')"
  if (( bytes_written != expected_size )); then
    return 1
  fi

  return 0
}

inflate_update_select_plist() {
  local compressed_path="$1"
  local plist_path="$2"
  local expected_size="$3"
  local expected_crc="$4"
  local output_limit="$5"

  /usr/bin/perl -Mbytes -e '
    use strict;
    use warnings;
    use Compress::Raw::Zlib ();
    use IO::Uncompress::RawInflate ();

    my ($compressed_path, $plist_path, $expected_size, $expected_crc, $output_limit) = @ARGV;
    my $written = 0;
    my $crc = 0;

    $expected_size = int($expected_size);
    $expected_crc = int($expected_crc);
    $output_limit = int($output_limit);

    my $inflater = IO::Uncompress::RawInflate->new(
      $compressed_path,
      Strict => 1,
    );
    exit 1 if !$inflater;

    open my $out_fh, ">:raw", $plist_path or exit 1;

    while (1) {
      my $output = "";
      my $bytes_read = $inflater->read($output, 65536);
      exit 1 if !defined($bytes_read) || $bytes_read < 0;
      last if $bytes_read == 0;

      $written += $bytes_read;
      exit 1 if $written > $output_limit;

      $crc = Compress::Raw::Zlib::crc32($output, $crc);
      print {$out_fh} $output;
    }

    exit 1 if !$inflater->eof();
    exit 1 if !$inflater->close();
    close $out_fh or exit 1;
    exit 1 if $written != $expected_size;
    exit 1 if ($crc & 0xffffffff) != ($expected_crc & 0xffffffff);
  ' "$compressed_path" "$plist_path" "$expected_size" "$expected_crc" "$output_limit"
}

minimum_macos_for_update_select_version() (
  local channel="$1"
  local version="$2"
  local zip_url="$3"

  local zip_size
  local tail_offset
  local tail_end
  local tail_size
  local temp_dir
  local central_info
  local central_offset
  local central_size
  local central_end
  local central_path
  local central_entry
  local method
  local comp_size
  local uncompressed_size
  local central_crc
  local central_fname_len
  local local_offset
  local local_flags
  local local_crc
  local local_comp_size
  local local_uncompressed_size
  local local_fname_len
  local local_extra_len
  local local_data_descriptor
  local data_start
  local data_end
  local compressed_path
  local plist_path
  local bundle_version
  local minimum_version
  local plist_crc
  local plist_size
  local normalized_bundle_version
  local filename_extra_size
  local local_entry
  local local_name_entry
  local range_code
  local range_start
  local range_end
  local range_total
  temp_dir="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/discord-update-select-range.XXXXXX")"
  [[ -n "$temp_dir" ]] || return 1

  minimum_macos_for_update_select_cleanup() {
    [[ -n "$temp_dir" ]] && [[ -d "$temp_dir" ]] && /bin/rm -rf -- "$temp_dir"
    return 0
  }

  minimum_macos_for_update_select_fail() {
    minimum_macos_for_update_select_cleanup
    exit 1
  }

  trap 'minimum_macos_for_update_select_cleanup; exit 130' INT TERM HUP

  download_update_select_range "$zip_url" 0 0 "$temp_dir/bytes-0-0" "$temp_dir/headers-0-0" 1 || minimum_macos_for_update_select_fail
  read -r range_code range_start range_end range_total <<<"$(content_range_from_headers "$temp_dir/headers-0-0")"
  if [[ "$range_code" != 206 ]] || (( range_start != 0 || range_end != 0 )); then
    minimum_macos_for_update_select_fail
  fi

  zip_size="$range_total"
  if (( zip_size <= 0 )); then
    minimum_macos_for_update_select_fail
  fi

  if (( zip_size <= ZIP_UPDATE_SELECT_EOCD_TAIL_BYTES_LIMIT )); then
    tail_offset=0
    tail_size="$zip_size"
  else
    tail_offset=$(( zip_size - ZIP_UPDATE_SELECT_EOCD_TAIL_BYTES_LIMIT ))
    tail_size=$ZIP_UPDATE_SELECT_EOCD_TAIL_BYTES_LIMIT
  fi

  tail_end=$(( zip_size - 1 ))
  download_update_select_range "$zip_url" "$tail_offset" "$tail_end" "$temp_dir/central-tail" "$temp_dir/headers-central-tail" "$tail_size" "$zip_size" || minimum_macos_for_update_select_fail

  central_info="$(/usr/bin/perl -e '
    use strict;
    use warnings;

    my ($tail_path, $zip_size, $tail_offset, $limit) = @ARGV;
    open my $tail_handle, "<:raw", $tail_path or die;
    local $/;
    my $tail_data = <$tail_handle>;
    close $tail_handle;

    my $sig = "PK\x05\x06";
    my $len = length($tail_data);
    for (my $i = $len - 22; $i >= 0; $i--) {
      next unless substr($tail_data, $i, 4) eq $sig;

      my ($disk_no, $cd_start_disk, $entries_this_disk, $entries_total, $cd_size, $cd_offset, $comment_len) = unpack(
        "v v v v V V v",
        substr($tail_data, $i + 4, 18),
      );

      next if $disk_no != 0;
      next if $cd_start_disk != 0;
      next if $entries_this_disk != $entries_total;
      next if $entries_total == 0;
      next if ($entries_total == 0xFFFF || $entries_this_disk == 0xFFFF);
      next if $cd_size == 0xFFFFFFFF;
      next if $cd_offset == 0xFFFFFFFF;
      next if $cd_size > $limit;
      next if $cd_size < 1;
      next if $i + 22 + $comment_len != $len;

      my $eocd_offset = $tail_offset + $i;
      my $central_end = $cd_offset + $cd_size;
      next if $cd_offset >= $zip_size;
      next if $central_end > $zip_size;
      next if $central_end > $eocd_offset;

      print "${cd_offset} ${cd_size}\n";
      exit 0;
    }

    exit 1;
  ' "$temp_dir/central-tail" "$zip_size" "$tail_offset" "$ZIP_UPDATE_SELECT_CENTRAL_DIR_BYTES_LIMIT")"

  if [[ -z "$central_info" ]]; then
    minimum_macos_for_update_select_fail
  fi

  read -r central_offset central_size <<<"$central_info"
  central_path="$temp_dir/central-directory"
  central_end=$(( central_offset + central_size - 1 ))
  if (( central_offset < 0 || central_size < 1 || central_end >= zip_size )); then
    minimum_macos_for_update_select_fail
  fi

  download_update_select_range "$zip_url" "$central_offset" "$central_end" "$central_path" "$temp_dir/headers-central" "$central_size" "$zip_size" || minimum_macos_for_update_select_fail

  central_entry="$(/usr/bin/perl -e '
    use strict;
    use warnings;

    my ($central_path, $target_path, $max_compressed_size, $max_uncompressed_size) = @ARGV;
    open my $central_handle, "<:raw", $central_path or die;
    local $/;
    my $data = <$central_handle>;
    close $central_handle;

    my $offset = 0;
    my $len = length($data);
    while ($offset + 46 <= $len) {
      my $sig = substr($data, $offset, 4);
      if ($sig ne "PK\x01\x02") {
        $offset++;
        next;
      }

      my $comp = unpack("v", substr($data, $offset + 10, 2));
      my $flags = unpack("v", substr($data, $offset + 8, 2));
      my $crc32 = unpack("V", substr($data, $offset + 16, 4));
      my $csize = unpack("V", substr($data, $offset + 20, 4));
      my $ucsize = unpack("V", substr($data, $offset + 24, 4));
      my $fname_len = unpack("v", substr($data, $offset + 28, 2));
      my $extra_len = unpack("v", substr($data, $offset + 30, 2));
      my $comment_len = unpack("v", substr($data, $offset + 32, 2));
      my $disk_start = unpack("v", substr($data, $offset + 34, 2));
      my $local_offset = unpack("V", substr($data, $offset + 42, 4));
      my $required = $offset + 46 + $fname_len + $extra_len + $comment_len;

      if ($required > $len) {
        exit 1;
      }

      my $name = substr($data, $offset + 46, $fname_len);

      if (($flags & 0x1) == 0x1 || ($flags & 0x40) == 0x40) {
        $offset = $required;
        next;
      }

      if ($disk_start != 0 || $comp != 0 && $comp != 8 || $csize > $max_compressed_size || $csize < 1 || $ucsize < 1 || $ucsize > $max_uncompressed_size || $local_offset == 0xFFFFFFFF) {
        $offset = $required;
        next;
      }

      if ($name eq $target_path) {
        print "${comp} ${crc32} ${csize} ${ucsize} ${flags} ${fname_len} ${local_offset}\n";
        exit 0;
      }

      $offset = $required;
    }

    exit 1;
  ' "$central_path" "$(versioned_update_select_plist_path_for_channel "$channel")" "$ZIP_UPDATE_SELECT_COMPRESSED_PLIST_BYTES_LIMIT" "$ZIP_UPDATE_SELECT_UNCOMPRESSED_PLIST_BYTES_LIMIT")"

  if [[ -z "$central_entry" ]]; then
    minimum_macos_for_update_select_fail
  fi

  read -r method central_crc comp_size uncompressed_size local_flags central_fname_len local_offset <<<"$central_entry"

  if (( method != 0 && method != 8 )); then
    minimum_macos_for_update_select_fail
  fi

  if (( uncompressed_size <= 0 || uncompressed_size > ZIP_UPDATE_SELECT_UNCOMPRESSED_PLIST_BYTES_LIMIT )); then
    minimum_macos_for_update_select_fail
  fi

  download_update_select_range "$zip_url" "$local_offset" "$(( local_offset + 29 ))" "$temp_dir/local-header" "$temp_dir/headers-local" 30 "$zip_size" || minimum_macos_for_update_select_fail

  local_entry="$(/usr/bin/perl -e '
    use strict;
    use warnings;

    my ($local_path, $expected_method, $expected_flags, $target_fname_len) = @ARGV;
    open my $local_handle, "<:raw", $local_path or die;
    local $/;
    my $data = <$local_handle>;
    close $local_handle;

    if (length($data) < 30) {
      exit 1;
    }

    if (substr($data, 0, 4) ne "PK\x03\x04") {
      exit 1;
    }

    my $flags = unpack("v", substr($data, 6, 2));
    my $method = unpack("v", substr($data, 8, 2));
    my $crc = unpack("V", substr($data, 14, 4));
    my $csize = unpack("V", substr($data, 18, 4));
    my $usize = unpack("V", substr($data, 22, 4));
    my $fname_len = unpack("v", substr($data, 26, 2));
    my $extra_len = unpack("v", substr($data, 28, 2));
    my $data_descriptor = ($flags & 0x08) == 0x08 ? 1 : 0;

    if (($flags & 0x1) == 0x1 || ($flags & 0x40) == 0x40) {
      exit 1;
    }

    if ($method != $expected_method || $flags != $expected_flags || $fname_len != $target_fname_len) {
      exit 1;
    }

    print "${crc} ${csize} ${usize} ${fname_len} ${extra_len} ${data_descriptor}\n";
  ' "$temp_dir/local-header" "$method" "$local_flags" "$central_fname_len")"

  if [[ -z "$local_entry" ]]; then
    minimum_macos_for_update_select_fail
  fi

  read -r local_crc local_comp_size local_uncompressed_size local_fname_len local_extra_len local_data_descriptor <<<"$local_entry"
  if (( local_comp_size == 0 && local_data_descriptor == 0 )) || (( local_uncompressed_size == 0 && local_data_descriptor == 0 )); then
    minimum_macos_for_update_select_fail
  fi

  if (( local_data_descriptor == 0 )); then
    if (( local_comp_size != comp_size || local_uncompressed_size != uncompressed_size || local_crc != central_crc )); then
      minimum_macos_for_update_select_fail
    fi
  else
    if (( local_comp_size != 0 && local_comp_size != comp_size )) || (( local_uncompressed_size != 0 && local_uncompressed_size != uncompressed_size )) || (( local_crc != 0 && local_crc != central_crc )); then
      minimum_macos_for_update_select_fail
    fi
  fi

  if (( local_fname_len < 0 || local_extra_len < 0 )); then
    minimum_macos_for_update_select_fail
  fi

  filename_extra_size=$(( 30 + local_fname_len + local_extra_len ))
  if (( filename_extra_size < 30 )); then
    minimum_macos_for_update_select_fail
  fi

  download_update_select_range "$zip_url" "$(( local_offset + 30 ))" "$(( local_offset + filename_extra_size - 1 ))" "$temp_dir/local-name-extra" "$temp_dir/headers-name-extra" "$(( filename_extra_size - 30 ))" "$zip_size" || minimum_macos_for_update_select_fail

  local_name_entry="$(/usr/bin/perl -e '
    use strict;
    use warnings;

    my ($name_extra_path, $target_path) = @ARGV;
    my $expected_len = length($target_path);
    open my $name_handle, "<:raw", $name_extra_path or die;
    local $/;
    my $name_data = <$name_handle>;
    close $name_handle;

    if (length($name_data) < $expected_len) {
      exit 1;
    }

    my $name = substr($name_data, 0, $expected_len);
    if ($name ne $target_path) {
      exit 1;
    }

    print "1\n";
  ' "$temp_dir/local-name-extra" "$(versioned_update_select_plist_path_for_channel "$channel")")"

  if [[ -z "$local_name_entry" ]]; then
    minimum_macos_for_update_select_fail
  fi

  data_start=$(( local_offset + filename_extra_size ))
  data_end=$(( data_start + comp_size - 1 ))

  if (( data_start < 0 || data_start >= zip_size || data_end < data_start || data_end >= zip_size || comp_size < 1 )); then
    minimum_macos_for_update_select_fail
  fi

  compressed_path="$temp_dir/compressed-plist"
  download_update_select_range "$zip_url" "$data_start" "$data_end" "$compressed_path" "$temp_dir/headers-plist" "$comp_size" "$zip_size" || minimum_macos_for_update_select_fail

  plist_path="$temp_dir/plist"
  if (( method == 8 )); then
    if (( comp_size > ZIP_UPDATE_SELECT_COMPRESSED_PLIST_BYTES_LIMIT )); then
      minimum_macos_for_update_select_fail
    fi
    if ! inflate_update_select_plist "$compressed_path" "$plist_path" "$uncompressed_size" "$central_crc" "$ZIP_UPDATE_SELECT_UNCOMPRESSED_PLIST_BYTES_LIMIT"; then
      minimum_macos_for_update_select_fail
    fi
  elif (( comp_size > ZIP_UPDATE_SELECT_COMPRESSED_PLIST_BYTES_LIMIT )); then
    minimum_macos_for_update_select_fail
  else
    /bin/cp "$compressed_path" "$plist_path"
  fi

  plist_size="$(/usr/bin/wc -c < "$plist_path" | /usr/bin/awk '{ print $1 }')"
  if (( plist_size > ZIP_UPDATE_SELECT_UNCOMPRESSED_PLIST_BYTES_LIMIT || plist_size != uncompressed_size )); then
    minimum_macos_for_update_select_fail
  fi

  bundle_version="$(plist_string_from_info_plist "$plist_path" CFBundleVersion)"
  if [[ -z "$bundle_version" ]]; then
    minimum_macos_for_update_select_fail
  fi
  if ! normalized_bundle_version="$(normalize_discord_version "$bundle_version" 2>/dev/null)"; then
    minimum_macos_for_update_select_fail
  fi

  if [[ "$normalized_bundle_version" != "$version" ]]; then
    minimum_macos_for_update_select_fail
  fi

  plist_crc="$(/usr/bin/cksum -o 3 "$plist_path" | /usr/bin/awk '{ print $1 }')"
  if (( plist_crc != central_crc )); then
    minimum_macos_for_update_select_fail
  fi

  minimum_version="$(plist_string_from_info_plist "$plist_path" LSMinimumSystemVersion)"
  if [[ -z "$minimum_version" ]]; then
    minimum_macos_for_update_select_fail
  fi

  minimum_version="${minimum_version%\+}"

  case "$minimum_version" in
    <->.<->|<->.<->.<->)
      ;;
    *)
      minimum_macos_for_update_select_fail
      ;;
  esac

  minimum_macos_for_update_select_cleanup
  print -- "$minimum_version"
)

run_update_select_availability_worker() {
  local channel="$1"
  local version_suffix="$2"
  local result_file="$3"
  local version
  local dmg_url
  local code
  local head_headers

  version="0.0.$version_suffix"
  dmg_url="$(versioned_download_url_for_channel "$channel" "$version")"
  head_headers="$result_file.headers"

  curl --location --fail --silent -I -D "$head_headers" "$dmg_url" >/dev/null || return 0
  code="$(http_code_from_headers "$head_headers")"
  if [[ "$code" == 200 ]]; then
    print -- "$version_suffix" > "$result_file"
  fi
}

run_update_select_worker() {
  local channel="$1"
  local version_suffix="$2"
  local result_file="$3"
  local completion_file="${4:-}"
  local dmg_url
  local zip_url
  local code
  local last_modified="unknown"
  local version
  local minimum="unknown"
  local head_headers

  version="0.0.$version_suffix"
  dmg_url="$(versioned_download_url_for_channel "$channel" "$version")"
  zip_url="$(versioned_update_select_archive_for_channel "$channel" "$version")"
  head_headers="$result_file.headers"

  if curl --location --fail --silent -I -D "$head_headers" "$dmg_url" >/dev/null; then
    code="$(http_code_from_headers "$head_headers")"
    if [[ "$code" == 200 ]]; then
      last_modified="$(last_modified_from_headers "$head_headers")"
      [[ -n "$last_modified" ]] || last_modified="unknown"

      if ! minimum="$(minimum_macos_for_update_select_version "$channel" "$version" "$zip_url")"; then
        minimum="unknown"
      elif [[ -z "$minimum" ]]; then
        minimum="unknown"
      fi

      /bin/mkdir -p "$(/usr/bin/dirname "$result_file")"
      /usr/bin/printf '%-29s  %s - [%s]\n' "$last_modified" "$version" "$minimum" > "$result_file"
    fi
  fi

  if [[ -n "$completion_file" ]]; then
    /bin/mkdir -p "$(/usr/bin/dirname "$completion_file")"
    /usr/bin/touch "$completion_file"
  fi
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

download_version_for_channel() {
  local channel="$1"
  local version

  if [[ -n "${channel_download_versions[$channel]-}" ]]; then
    print -- "${channel_download_versions[$channel]}"
    return 0
  fi

  if [[ -n "$update_version" ]]; then
    version="$(normalize_discord_version "$update_version")" || return 1
  else
    version="$(latest_version_for_channel "$channel")" || return 1
  fi

  channel_download_versions[$channel]="$version"
  print -- "$version"
}

print_update_select_versions() {
  local channel="$1"
  local selector="${2:-}"
  local app_name
  local latest_version
  local latest_suffix
  local requested_start_suffix=""
  local requested_floor_suffix=""
  local first_suffix
  local last_suffix=1
  local range_start=""
  local range_end=""
  local clamped_floor=false
  local range_requested=false
  local upward_discovery=false
  local upward_limit=0
  local discovery_ceiling
  local discovered_suffix
  local discovery_file
  local scan_jobs
  local scan_limit="${DISCORD_UPDATE_SELECT_SCAN_LIMIT:-0}"
  local suffix
  local found_any=false
  local result_dir
  local -a pids
  local version_file
  local ordinal
  local old_sig_int
  local old_sig_term
  local old_sig_hup
  local pid
  local completion_file
  local completion_pid
  local output_file
  local -a next_active_pids
  local worker_pid
  typeset -A worker_outputs=()
  typeset -A worker_done_files=()

  app_name="$(app_name_for_channel "$channel")"

  if [[ -n "$selector" ]]; then
    if [[ "$selector" == *-* ]]; then
      range_start="${selector%%-*}"
      range_end="${selector#*-}"
      requested_start_suffix="$(discord_version_suffix "$range_start")" || return 1
      requested_floor_suffix="$(discord_version_suffix "$range_end")" || return 1
      range_requested=true

      if (( requested_start_suffix < requested_floor_suffix )); then
        print -u2 "Invalid update-select range: $selector"
        print -u2 "Use descending ranges such as 500-400 or 0.0.500-0.0.400."
        return 1
      fi

      if (( requested_start_suffix - requested_floor_suffix > DISCORD_UPDATE_SELECT_MAX_SCAN_SPAN )); then
        fail_usage "--update-select ranges may span at most ${DISCORD_UPDATE_SELECT_MAX_SCAN_SPAN} version steps (101 inclusive builds), for example 500-400."
      fi
    else
      requested_floor_suffix="$(discord_version_suffix "$selector")" || return 1
      range_requested=true
    fi
  fi

  latest_version="$(latest_version_for_channel "$channel")" || return 1
  latest_suffix="$(discord_version_suffix "$latest_version")" || return 1
  first_suffix="$latest_suffix"

  if [[ -n "$selector" ]]; then
    if [[ "$requested_start_suffix" != "" ]]; then
      first_suffix="$requested_start_suffix"
      last_suffix="$requested_floor_suffix"
    else
      last_suffix="$requested_floor_suffix"
      if (( requested_floor_suffix > first_suffix )); then
        last_suffix="$first_suffix"
        clamped_floor=true
      fi
    fi
  else
    last_suffix="$latest_suffix"
    upward_discovery=true
    upward_limit="$(update_select_upward_limit)"
  fi

  if [[ "$scan_limit" == <-> && "$scan_limit" -gt 0 ]]; then
    if [[ -n "$selector" ]]; then
      last_suffix=$(( first_suffix - scan_limit + 1 > last_suffix ? first_suffix - scan_limit + 1 : last_suffix ))
      if (( last_suffix < 1 )); then
        last_suffix=1
      fi
    fi
  fi

  if (( last_suffix < 1 )); then
    last_suffix=1
  fi
  if (( last_suffix > first_suffix )); then
    last_suffix="$first_suffix"
  fi

  print "Available $app_name macOS DMG versions:"
  print "  manifest: $latest_version"
  print "  source: Discord DMG URLs (ZIP archive is metadata-only)"
  print "  note: CDN directory listing is denied, so this probes versioned URLs."
  if [[ "$upward_discovery" == true ]]; then
    print "  upward discovery: $upward_limit versions above the manifest"
  fi
  if [[ "$range_requested" == true && -n "$requested_start_suffix" ]]; then
    print "  scan range requested: 0.0.$requested_start_suffix down to 0.0.$requested_floor_suffix"
  fi
  if [[ "$clamped_floor" == true ]]; then
    print "  requested floor was newer than the manifest; using $latest_version"
  fi
  if [[ -n "$range_start" ]]; then
    print "  scan range: 0.0.$first_suffix down to 0.0.$last_suffix"
  fi
  if [[ "$last_suffix" -gt 1 ]] && [[ -n "$selector" ]]; then
    if [[ -z "$range_start" ]]; then
      print "  scan floor: 0.0.$last_suffix"
    fi
    if [[ "$scan_limit" == <-> && "$scan_limit" -gt 0 ]]; then
      print "  scan limit: newest $scan_limit builds because DISCORD_UPDATE_SELECT_SCAN_LIMIT is set"
    fi
  fi

  scan_jobs="$(update_select_worker_count)"
  print "  scan workers: $scan_jobs"
  if (( scan_jobs == 0 )); then
    scan_jobs="$DISCORD_UPDATE_SELECT_MIN_DEFAULT_JOBS"
  fi

  if ! result_dir="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/discord-update-select.XXXXXX")" || [[ -z "$result_dir" ]]; then
    print -u2 "Could not create temporary storage for the update-select scan."
    return 1
  fi
  print_update_select_versions_cleanup() {
    [[ -n "$result_dir" ]] && [[ -d "$result_dir" ]] && /bin/rm -rf -- "$result_dir"
    return 0
  }
  print_update_select_versions_restore_traps() {
    trap - INT TERM HUP
    [[ -n "$old_sig_int" ]] && eval "$old_sig_int"
    [[ -n "$old_sig_term" ]] && eval "$old_sig_term"
    [[ -n "$old_sig_hup" ]] && eval "$old_sig_hup"
    return 0
  }
  print_update_select_versions_abort() {
    local child_pid

    for child_pid in "${pids[@]}"; do
      kill -TERM "$child_pid" 2>/dev/null || true
    done
    for child_pid in "${pids[@]}"; do
      wait "$child_pid" 2>/dev/null || true
    done

    print_update_select_versions_cleanup
    print_update_select_versions_restore_traps
    exit 130
  }
  old_sig_int="$(trap -p INT)"
  old_sig_term="$(trap -p TERM)"
  old_sig_hup="$(trap -p HUP)"
  trap 'print_update_select_versions_abort' INT TERM HUP

  if [[ "$upward_discovery" == true ]]; then
    discovery_ceiling=$(( latest_suffix + upward_limit ))
    discovered_suffix="$latest_suffix"
    pids=()

    for (( suffix = latest_suffix + 1; suffix <= discovery_ceiling; suffix++ )); do
      discovery_file="${result_dir}/discovery-${suffix}.txt"
      run_update_select_availability_worker "$channel" "$suffix" "$discovery_file" &
      pids+=("$!")

      if (( ${#pids} >= scan_jobs )); then
        for pid in "$pids[@]"; do
          wait "$pid" || true
        done
        pids=()
      fi
    done

    for pid in "$pids[@]"; do
      wait "$pid" || true
    done
    pids=()

    for (( suffix = discovery_ceiling; suffix > latest_suffix; suffix-- )); do
      discovery_file="${result_dir}/discovery-${suffix}.txt"
      if [[ -f "$discovery_file" ]]; then
        discovered_suffix="$suffix"
        break
      fi
    done

    first_suffix="$discovered_suffix"
    last_suffix="$discovered_suffix"
    print "  highest CDN artifact: 0.0.$discovered_suffix"
  fi

  print
  print "Last-Modified  Version - [Minimum macOS]"

  pids=()
  suffix="$first_suffix"
  while (( suffix >= last_suffix || ${#pids} > 0 )); do
    while (( suffix >= last_suffix && ${#pids} < scan_jobs )); do
      ordinal=$(( first_suffix - suffix ))
      version_file="${result_dir}/${ordinal}.txt"
      completion_file="${result_dir}/${ordinal}.done"
      run_update_select_worker "$channel" "$suffix" "$version_file" "$completion_file" &
      pid="$!"
      worker_outputs[$pid]="$version_file"
      worker_done_files[$pid]="$completion_file"
      pids+=( "$pid" )
      suffix=$(( suffix - 1 ))
    done

    completion_pid=""
    while [[ "$completion_pid" != <-> ]]; do
      for worker_pid in "$pids[@]"; do
        [[ "$worker_pid" == <-> ]] || continue
        completion_file="${worker_done_files[$worker_pid]-}"
        if [[ -n "$completion_file" ]] && [[ -f "$completion_file" ]]; then
          completion_pid="$worker_pid"
          break
        fi
        if ! /bin/kill -0 "$worker_pid" 2>/dev/null; then
          completion_pid="$worker_pid"
          break
        fi
      done

      if [[ "$completion_pid" != <-> ]]; then
        /bin/sleep 0.05
      fi
    done

    wait "$completion_pid" || true
    if [[ -n "${worker_outputs[$completion_pid]-}" ]]; then
      output_file="${worker_outputs[$completion_pid]}"
      if [[ -f "$output_file" ]]; then
        found_any=true
        /bin/cat "$output_file"
      fi
    fi

    next_active_pids=()
    for worker_pid in "$pids[@]"; do
      [[ "$worker_pid" == "$completion_pid" ]] && continue
      next_active_pids+=( "$worker_pid" )
    done
    pids=( "${next_active_pids[@]}" )
    if [[ -n "${worker_outputs[$completion_pid]+x}" ]]; then
      unset "worker_outputs[$completion_pid]"
    fi
    if [[ -n "${worker_done_files[$completion_pid]+x}" ]]; then
      unset "worker_done_files[$completion_pid]"
    fi
  done

  print_update_select_versions_cleanup
  print_update_select_versions_restore_traps

  if [[ "$found_any" != true ]]; then
    print -u2 "No CDN DMG versions were found for $app_name."
    return 1
  fi

  return 0
}

dmg_path_for_channel() {
  local channel="$1"
  local version

  version="$(download_version_for_channel "$channel")" || return 1
  print -- "$script_dir/Discord-${channel}-installer (${version}).dmg"
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
    source_path="$HOME/${source_path[3,-1]}"
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

discord_process_pids() {
  local channel="$1"
  local app_path

  app_path="$(app_path_for_channel "$channel")"

  /bin/ps ax -o pid= -o command= | /usr/bin/awk -v prefix="$app_path/Contents/" '
    {
      pid = $1
      sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", $0)
      if (pid ~ /^[0-9]+$/ && index($0, prefix) == 1) {
        print pid
      }
    }
  '
}

discord_main_process_pids() {
  local channel="$1"
  local executable

  executable="$(executable_path_for_channel "$channel")"

  /bin/ps ax -o pid= -o command= | /usr/bin/awk -v executable="$executable" '
    {
      pid = $1
      sub(/^[[:space:]]*[0-9]+[[:space:]]+/, "", $0)
      if (pid ~ /^[0-9]+$/ && ($0 == executable || index($0, executable " ") == 1)) {
        print pid
      }
    }
  '
}

discord_pid_belongs_to_bundle() {
  local channel="$1"
  local pid="$2"
  local app_path

  [[ "$pid" == <-> ]] || return 1
  app_path="$(app_path_for_channel "$channel")"

  /bin/ps -p "$pid" -o command= 2>/dev/null | /usr/bin/awk -v prefix="$app_path/Contents/" '
    {
      sub(/^[[:space:]]+/, "", $0)
      if (index($0, prefix) == 1) {
        found = 1
      }
    }
    END { exit(found ? 0 : 1) }
  '
}

discord_is_running() {
  local channel="$1"
  [[ -n "$(discord_process_pids "$channel")" ]]
}

discord_main_is_running() {
  local channel="$1"
  [[ -n "$(discord_main_process_pids "$channel")" ]]
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

openasar_target_path_for_channel() {
  local channel="$1"
  local app_relative
  local resources_dir
  local expected_wrapper
  local layout_status
  local issue

  resources_dir="$(app_path_for_channel "$channel")/Contents/Resources"

  if [[ "$openasar_betterdiscord_requested" != true ]]; then
    print -- "$resources_dir/app.asar"
    return 0
  fi

  app_relative="$(app_relative_path_for_channel "$channel")"
  expected_wrapper="${channel_betterdiscord_wrapper[$channel]:-false}"

  if inspect_betterdiscord_wrapper "$channel"; then
    layout_status=0
  else
    layout_status=$?
  fi

  if [[ "$expected_wrapper" == true ]]; then
    if (( layout_status == 0 )); then
      print -- "$resources_dir/betterdiscord.app.asar"
      return 0
    fi

    print -u2 "Refusing OpenAsar injection because the validated BetterDiscord wrapper changed in $app_relative:"
    if (( layout_status == 2 )); then
      for issue in "${betterdiscord_wrapper_issues[@]}"; do
        print -u2 "  $issue"
      done
    else
      print -u2 "  The BetterDiscord wrapper is no longer present."
    fi
    return 1
  fi

  if (( layout_status == 1 )); then
    print -- "$resources_dir/app.asar"
    return 0
  fi

  print -u2 "Refusing standalone OpenAsar injection because the BetterDiscord wrapper layout changed in $app_relative:"
  if (( layout_status == 0 )); then
    print -u2 "  A BetterDiscord wrapper appeared after preflight validation."
  else
    for issue in "${betterdiscord_wrapper_issues[@]}"; do
      print -u2 "  $issue"
    done
  fi
  return 1
}

inject_openasar() {
  local channel="$1"
  local payload_path="$2"
  local app_name
  local app_path
  local resources_dir
  local target_asar
  local target_name
  local staged_asar
  local injection_failed=false

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  resources_dir="$app_path/Contents/Resources"
  if ! target_asar="$(openasar_target_path_for_channel "$channel")"; then
    return 1
  fi
  target_name="${target_asar:t}"
  staged_asar="$resources_dir/.openasar-app-$$-$RANDOM.asar"

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

  if [[ ! -f "$target_asar" || -L "$target_asar" ]]; then
    print -u2 "OpenAsar injection refused; the target $target_name is missing or is not a regular file:"
    print -u2 "  $target_asar"
    return 1
  fi

  if [[ "$target_name" == "betterdiscord.app.asar" ]]; then
    print "Injecting OpenAsar into the BetterDiscord nested payload for $app_name..."
  else
    print "Injecting standalone OpenAsar into $app_name..."
  fi

  rm -f -- "$staged_asar"

  if ! cp -f "$payload_path" "$staged_asar"; then
    print -u2 "OpenAsar injection failed while staging the payload:"
    print -u2 "  $staged_asar"
    injection_failed=true
  elif ! cmp -s "$payload_path" "$staged_asar"; then
    print -u2 "OpenAsar injection failed; the staged ASAR does not match the source payload:"
    print -u2 "  $staged_asar"
    injection_failed=true
  elif ! mv -f "$staged_asar" "$target_asar"; then
    print -u2 "OpenAsar injection failed while replacing $target_name:"
    print -u2 "  $target_asar"
    injection_failed=true
  elif ! cmp -s "$payload_path" "$target_asar"; then
    print -u2 "OpenAsar injection failed; the installed $target_name does not match the source payload:"
    print -u2 "  $target_asar"
    injection_failed=true
  fi

  rm -f -- "$staged_asar" || true
  [[ "$injection_failed" != true ]] || return 1

  print "OpenAsar injected into $app_name:"
  print "  $target_asar"
  sleep 1
}

openasar_matches_installed_target() {
  local channel="$1"
  local payload_path="$2"
  local target_asar

  if ! target_asar="$(openasar_target_path_for_channel "$channel")"; then
    return 1
  fi
  [[ -f "$target_asar" && ! -L "$target_asar" ]] || return 1
  cmp -s "$payload_path" "$target_asar"
}

verify_openasar_after_relaunch() {
  local channel="$1"
  local payload_path="$2"
  local was_running_at_start="${3:-false}"
  local app_name
  local target_asar
  local target_name
  local replaced=false

  app_name="$(app_name_for_channel "$channel")"
  if ! target_asar="$(openasar_target_path_for_channel "$channel")"; then
    return 1
  fi
  target_name="${target_asar:t}"

  if [[ "$was_running_at_start" != true ]]; then
    if openasar_matches_installed_target "$channel" "$payload_path"; then
      print "OpenAsar installation verified for $app_name; the client remains closed."
      return 0
    fi

    print -u2 "OpenAsar verification failed for the closed $app_name client:"
    print -u2 "  $target_asar"
    return 1
  fi

  if ! openasar_matches_installed_target "$channel" "$payload_path"; then
    replaced=true
  else
    for _ in {1..10}; do
      sleep 1
      if ! openasar_matches_installed_target "$channel" "$payload_path"; then
        replaced=true
        break
      fi
    done
  fi

  if [[ "$replaced" != true ]]; then
    print "OpenAsar remained installed after relaunching $app_name."
    return 0
  fi

  print "$app_name replaced $target_name during its first relaunch. Stopping it and reinjecting OpenAsar once..."
  if discord_is_running "$channel"; then
    quit_discord "$channel" || return 1
  fi

  inject_openasar "$channel" "$payload_path"
  relaunch_channel_if_needed "$channel" true

  for _ in {1..10}; do
    sleep 1
    if ! openasar_matches_installed_target "$channel" "$payload_path"; then
      print -u2 "OpenAsar did not survive the retry relaunch for $app_name:"
      print -u2 "  $target_asar"
      return 1
    fi
  done

  print "OpenAsar reinjection remained installed after relaunching $app_name."
}

quit_discord() {
  local channel="$1"
  local app_name
  local pid
  local main_was_running=false
  local -a remaining_pids
  app_name="$(app_name_for_channel "$channel")"

  discord_is_running "$channel" || return 1

  if discord_main_is_running "$channel"; then
    main_was_running=true
    print "$app_name is running. Quitting it before continuing..."
    osascript -e "tell application \"$app_name\" to quit" >/dev/null 2>&1 || true

    for _ in {1..10}; do
      discord_is_running "$channel" || break
      sleep 1
    done
  else
    print "$app_name has remaining helper processes. Stopping them before continuing..."
  fi

  if discord_is_running "$channel"; then
    if [[ "$main_was_running" == true ]]; then
      print "$app_name did not quit cleanly. Force-killing its remaining app processes..."
    fi

    for _ in {1..3}; do
      remaining_pids=("${(@f)$(discord_process_pids "$channel")}")
      (( ${#remaining_pids[@]} > 0 )) || break

      for pid in "${remaining_pids[@]}"; do
        discord_pid_belongs_to_bundle "$channel" "$pid" || continue
        kill -KILL "$pid" >/dev/null 2>&1 || true
      done

      sleep 1
    done
  fi

  if discord_is_running "$channel"; then
    print -u2 "$app_name is still running. Refusing to continue."
    return 1
  fi

  return 0
}

unwrap_betterdiscord_wrapper() {
  local channel="$1"
  local app_relative
  local app_path
  local resources_dir
  local wrapper_dir
  local wrapped_asar
  local top_level_asar
  local temporary_wrapper_dir
  local layout_status
  local issue
  local wrapper_cleanup_warning=false

  [[ "${channel_betterdiscord_wrapper[$channel]:-false}" == true ]] || return 0

  app_relative="$(app_relative_path_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  resources_dir="$app_path/Contents/Resources"
  wrapper_dir="$resources_dir/app"
  wrapped_asar="$resources_dir/betterdiscord.app.asar"
  top_level_asar="$resources_dir/app.asar"
  temporary_wrapper_dir="$resources_dir/.betterdiscord-app-unwrapping-$$"

  if inspect_betterdiscord_wrapper "$channel"; then
    layout_status=0
  else
    layout_status=$?
  fi

  if (( layout_status != 0 )); then
    print -u2 "Refusing to unwrap BetterDiscord from $app_relative because the validated wrapper layout changed:"
    if (( layout_status == 2 )); then
      for issue in "${betterdiscord_wrapper_issues[@]}"; do
        print -u2 "  $issue"
      done
    else
      print -u2 "  The BetterDiscord wrapper is no longer present."
    fi
    return 1
  fi

  if discord_is_running "$channel"; then
    quit_discord "$channel" || return 1
  fi

  if discord_is_running "$channel"; then
    print -u2 "$(app_name_for_channel "$channel") is still running. Refusing to unwrap BetterDiscord from $app_relative."
    return 1
  fi

  print "Detected BetterDiscord wrapper in $app_relative"
  print "Unwrapping BetterDiscord from $app_relative"
  print "Removing $app_relative/Contents/Resources/app/"

  if ! mv -- "$wrapper_dir" "$temporary_wrapper_dir"; then
    print -u2 "Failed to remove $app_relative/Contents/Resources/app/ from its active location."
    return 1
  fi

  print "Restoring $app_relative/Contents/Resources/betterdiscord.app.asar -> $app_relative/Contents/Resources/app.asar"
  if ! mv -- "$wrapped_asar" "$top_level_asar"; then
    print -u2 "Failed to restore $app_relative/Contents/Resources/app.asar."
    if ! mv -- "$temporary_wrapper_dir" "$wrapper_dir"; then
      print -u2 "Failed to return $app_relative/Contents/Resources/app/ to its original location."
    fi
    return 1
  fi

  if ! remove_installation_target "$temporary_wrapper_dir" "$app_relative/Contents/Resources/app/ staging directory" false; then
    print -u2 "BetterDiscord was unwrapped, but its inactive staging directory could not be fully removed from $app_relative."
    wrapper_cleanup_warning=true
  fi

  if [[ -e "$wrapper_dir" || -L "$wrapper_dir" || -e "$wrapped_asar" || -L "$wrapped_asar" || ! -s "$top_level_asar" || -L "$top_level_asar" ]]; then
    print -u2 "BetterDiscord unwrap verification failed for $app_relative."
    return 1
  fi

  channel_betterdiscord_wrapper[$channel]=false
  print "BetterDiscord successfully unwrapped from $app_relative"
  if [[ "$wrapper_cleanup_warning" == true ]]; then
    print -u2 "Warning: an inactive BetterDiscord staging directory remains in $app_relative/Contents/Resources/."
  fi
}

download_installer_dmg() {
  local channel="$1"
  local app_name
  local resolved_version
  local download_url
  local dmg_path
  local attempt

  app_name="$(app_name_for_channel "$channel")"
  resolved_version="$(download_version_for_channel "$channel")" || return 1
  download_url="$(download_url_for_channel "$channel")" || return 1
  dmg_path="$(dmg_path_for_channel "$channel")" || return 1

  remove_download_artifacts "$dmg_path"

  print "Downloading $app_name installer to:"
  print "  $dmg_path"
  print "Resolved $app_name version:"
  print "  $resolved_version"
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
  local replacement_failed=false
  local source_app=""
  local attempt
  local -a found_apps

  app_name="$(app_name_for_channel "$channel")"
  app_path="$(app_path_for_channel "$channel")"
  executable_path="$(executable_path_for_channel "$channel")"
  dmg_path="$(dmg_path_for_channel "$channel")" || return 1
  mount_point="$(available_mount_point_for_channel "$channel")"

  mkdir -p "$mount_point"
  mount_point_created=true

  cleanup_mount_and_dmg() {
    if [[ "$mounted" == true && -n "$mount_point" ]]; then
      hdiutil detach "$mount_point" -quiet >/dev/null 2>&1 || hdiutil detach "$mount_point" -force -quiet >/dev/null 2>&1 || true
    fi
    if [[ "$mount_point_created" == true ]]; then
      rm -rf -- "$mount_point" || true
    fi
    remove_download_artifacts "$dmg_path" || true
  }

  guard_update_replacement_checked() {
    local guard_status=0

    guard_update_replacement "$1" || guard_status=$?
    if [[ "$guard_status" != 0 ]]; then
      cleanup_mount_and_dmg
      return "$guard_status"
    fi

    return 0
  }

  download_installer_dmg "$channel" || {
    print -u2 "$app_name was not replaced."
    cleanup_mount_and_dmg
    return 1
  }

  if ! hdiutil attach "$dmg_path" -nobrowse -readonly -mountpoint "$mount_point" >/dev/null; then
    print -u2 "Failed to attach the $app_name installer:"
    print -u2 "  $dmg_path"
    replacement_failed=true
  else
    mounted=true

    source_app="$mount_point/$app_name.app"
    if [[ ! -d "$source_app" ]]; then
      found_apps=("$mount_point"/*.app(N))
      source_app="${found_apps[1]:-}"
    fi

    if [[ -z "$source_app" || ! -d "$source_app" ]]; then
      print -u2 "Could not find a Discord app inside the mounted installer:"
      print -u2 "  $mount_point"
      replacement_failed=true
    else
      for attempt in {1..3}; do
        guard_update_replacement_checked "$channel" || return 1
        print "Replacing $app_name in $app_path (attempt $attempt of 3)..."

        if ! rm -rf -- "$app_path" || [[ -e "$app_path" ]]; then
          print -u2 "Failed to remove the existing $app_name app."
        else
          guard_update_replacement_checked "$channel" || return 1

          if ditto "$source_app" "$app_path" &&
             [[ -d "$app_path" ]] &&
             [[ -x "$executable_path" ]] &&
             ! discord_is_running "$channel"; then
            replacement_succeeded=true
            break
          fi

          print -u2 "Failed to copy or verify the replacement $app_name app."
        fi

        guard_update_replacement_checked "$channel" || return 1
        rm -rf -- "$app_path" || true

        if (( attempt < 3 )); then
          print "Retrying $app_name replacement in 2 seconds..."
          sleep 2
        fi
      done

      if [[ "$replacement_succeeded" != true ]]; then
        print -u2 "$app_name replacement failed after 3 attempts."
        print -u2 "$app_name was not successfully replaced."
        replacement_failed=true
      fi
    fi
  fi

  cleanup_mount_and_dmg
  [[ "$replacement_failed" != true ]] || return 1

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

  if [[ "$lock_requested" == true && -L "$data_dir" ]]; then
    print -u2 "Refusing locked cleanup because $app_name data directory is a symlink:"
    print -u2 "  $data_dir"
    return 1
  fi

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
    if [[ "$lock_requested" == true && "$allow_missing_data_dir" == true ]]; then
      print "$app_name has no settings.json or Local Storage directory yet."
      print "Only detected updater-managed targets will be cleaned before the locked update."
    else
      print -u2 "Refusing to clean because the target does not look like $app_name's data directory:"
      print -u2 "  $data_dir"
      return 1
    fi
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
    [[ -e "$target" || -L "$target" ]] && existing_targets+=("$target")
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
    if [[ "${channel_betterdiscord_wrapper[$channel]:-false}" == true ]]; then
      if [[ "$openasar_betterdiscord_requested" == true ]]; then
        print "No App Support files were changed for $app_name; its BetterDiscord wrapper will be preserved for nested OpenAsar injection."
      else
        print "No App Support files were changed for $app_name; BetterDiscord app-wrapper cleanup will continue."
      fi
    else
      print "Nothing was changed for $app_name."
    fi
    return 0
  fi

  print "The following $app_name installation files will be deleted:"
  for target in "${existing_targets[@]}"; do
    print "  ${target#$data_dir/}"
  done

  print
  print "Login and settings data will be preserved."

  if discord_is_running "$channel"; then
    quit_discord "$channel" || return 1
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
  local show_raw_target="${3:-true}"
  local attempt
  local remove_output=""
  local last_remove_output=""

  for attempt in {1..3}; do
    if [[ ! -e "$target" && ! -L "$target" ]]; then
      return 0
    fi

    if [[ -L "$target" ]]; then
      chflags -h nouchg,noschg "$target" >/dev/null 2>&1 || true

      if remove_output="$(rm -f -- "$target" 2>&1)"; then
        last_remove_output=""
      else
        last_remove_output="$remove_output"
      fi

      if [[ ! -e "$target" && ! -L "$target" ]]; then
        return 0
      fi

      if (( attempt < 3 )); then
        print "Could not delete $relative_target yet. Retrying in 1 second..."
        sleep 1
      fi
      continue
    fi

    chflags -RH nouchg,noschg "$target" >/dev/null 2>&1 || true
    chmod -RN "$target" >/dev/null 2>&1 || true
    chmod -R u+rwX "$target" >/dev/null 2>&1 || true
    xattr -cr "$target" >/dev/null 2>&1 || true

    if remove_output="$(rm -rf -- "$target" 2>&1)"; then
      last_remove_output=""
    else
      last_remove_output="$remove_output"
    fi

    if [[ ! -e "$target" && ! -L "$target" ]]; then
      return 0
    fi

    if [[ -d "$target" ]]; then
      find -x "$target" -depth -mindepth 1 -exec chflags -H nouchg,noschg {} + >/dev/null 2>&1 || true
      find -x "$target" -depth -mindepth 1 -exec chmod -N {} + >/dev/null 2>&1 || true
      find -x "$target" -depth -mindepth 1 -exec chmod u+rwX {} + >/dev/null 2>&1 || true
      find -x "$target" -depth -mindepth 1 -exec rm -rf -- {} + >/dev/null 2>&1 || true

      if rmdir "$target" >/dev/null 2>&1 || [[ ! -e "$target" && ! -L "$target" ]]; then
        return 0
      fi
    fi

    if (( attempt < 3 )); then
      print "Could not fully delete $relative_target yet. Retrying in 1 second..."
      sleep 1
    fi
  done

  print -u2 "Failed to delete $relative_target:"
  if [[ "$show_raw_target" == true ]]; then
    print -u2 "  $target"
    if [[ -n "$last_remove_output" ]]; then
      print_indented_output "$last_remove_output"
    fi
  fi
  return 1
}

guard_update_replacement() {
  local channel="$1"
  local app_name

  discord_is_running "$channel" || return 0

  app_name="$(app_name_for_channel "$channel")"
  print "$app_name restarted during update replacement. Stopping it and purging App Support again..."
  quit_discord "$channel" || return 1
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

wait_for_discord_main_process() {
  local channel="$1"
  local timeout="${2:-10}"
  local deadline

  deadline=$(( SECONDS + timeout ))
  while (( SECONDS <= deadline )); do
    discord_main_is_running "$channel" && return 0
    sleep 1
  done

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
        if wait_for_discord_main_process "$channel" 10; then
          return 0
        fi

        print -u2 "$app_name launch request succeeded, but its main process was not detected. Retrying..."
        continue
      fi

      print -u2 "$app_name did not relaunch cleanly with open:"
      print_indented_output "$open_output"
      print "$app_name did not relaunch cleanly with open. Retrying..."
      sleep 1
    done

    if [[ -x "$executable_path" ]]; then
      print "Falling back to launching $app_name executable directly..."
      "$executable_path" >/dev/null 2>&1 &!
      wait_for_discord_main_process "$channel" 10 && return 0

      print -u2 "$app_name executable fallback was started, but the running process was not detected."
      return 1
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

    if [[ -d "$data_dir" && ! -f "$data_dir/settings.json" && ! -d "$data_dir/Local Storage" &&
          "$lock_requested" != true ]]; then
      print -u2 "Refusing to continue because the target does not look like $app_name's data directory:"
      print -u2 "  $data_dir"
      exit 1
    fi
  done
}

if [[ -n "$update_version" ]]; then
  update_version="$(normalize_discord_version "$update_version")" || exit 2
  lock_version="${update_version##*.}"
fi

if [[ "$lock_requested" == true && "$lock_version" != "0" && "$lock_version" == 0* ]]; then
  fail_usage "--lock versions cannot contain leading zeroes. Use a value such as 401 or 0.0.401."
fi

if [[ "$update_select_requested" == true ]]; then
  print_update_select_versions "$single_selected_channel" "$update_select_min_version"
  exit $?
fi

if [[ "$dl_requested" == true ]]; then
  download_installer_dmg "$single_selected_channel"
  exit $?
fi

validate_selected_data_dirs
validate_selected_betterdiscord_wrappers

if [[ "$lock_requested" == true ]]; then
  for channel in "${selected_channels[@]}"; do
    preflight_lock_settings_target "$channel" || exit 1
  done
fi

openasar_payload=""
openasar_initial_download_succeeded=false
openasar_payload_is_temporary=false

cleanup_openasar_payload() {
  return 0
}

if [[ "$openasar_requested" == true ]]; then
  if openasar_source_is_remote; then
    openasar_payload="$(openasar_payload_path)"
    openasar_payload_is_temporary=true
  elif ! openasar_payload="$(resolve_openasar_local_source)"; then
    openasar_payload=""
  fi

  function cleanup_openasar_payload() {
    if [[ "$openasar_payload_is_temporary" == true && -n "$openasar_payload" ]]; then
      remove_download_artifacts "$openasar_payload"
    fi
  }

  if [[ -n "$openasar_payload" ]] && download_openasar_payload "$openasar_payload"; then
    openasar_initial_download_succeeded=true
  else
    print -u2 "OpenAsar injection will be skipped because the payload could not be prepared."
  fi
fi

if [[ "$lock_requested" == true && "$openasar_initial_download_succeeded" != true ]]; then
  cleanup_openasar_payload
  print -u2 "Cannot proceed with --lock because the OpenAsar payload could not be prepared."
  exit 1
fi

cleanup_started=false
cleanup_on_exit() {
  local exit_status=$?

  if [[ "$cleanup_started" == true ]]; then
    return "$exit_status"
  fi

  cleanup_started=true
  set +e
  cleanup_openasar_payload
  restore_recovery_for_wrappers_left_installed
  set -e
  return "$exit_status"
}
trap cleanup_on_exit ZERR EXIT

for channel in "${selected_channels[@]}"; do
  if discord_main_is_running "$channel"; then
    channel_was_running[$channel]=true
  else
    channel_was_running[$channel]=false
  fi
done

if [[ "$openasar_betterdiscord_requested" != true ]]; then
  for channel in "${selected_channels[@]}"; do
    disable_betterdiscord_recovery_for_unwrap "$channel"
  done
fi

if [[ "$multiple_channels" == true ]]; then
  print
  print "Stopping all selected Discord clients before continuing..."
  for channel in "${selected_channels[@]}"; do
    if discord_is_running "$channel"; then
      quit_discord "$channel" || exit 1
    fi
  done
fi

for channel in "${selected_channels[@]}"; do
  app_name="$(app_name_for_channel "$channel")"
  was_running_at_start="${channel_was_running[$channel]:-false}"
  allow_missing_data_dir=false
  openasar_injected=false

  print
  print "== $app_name =="

  if [[ "$openasar_betterdiscord_requested" == true ]]; then
    if [[ "${channel_betterdiscord_wrapper[$channel]:-false}" == true ]]; then
      print "Preserving the validated BetterDiscord wrapper for $app_name."
      print "OpenAsar will replace its nested betterdiscord.app.asar payload."
    else
      print "No BetterDiscord wrapper was detected for $app_name."
      print "OpenAsar will use the normal standalone app.asar layout."
    fi
  fi

  if [[ "$multiple_channels" == false && ( "$update_requested" == true || "$openasar_requested" == true ) ]]; then
    if discord_is_running "$channel"; then
      quit_discord "$channel" || exit 1
    fi
  fi

  if [[ "$lock_requested" == true ]]; then
    preflight_lock_settings_target "$channel" || exit 1
  fi

  if [[ "$multiple_channels" == true || "$update_requested" == true || "${channel_betterdiscord_wrapper[$channel]:-false}" == true ]]; then
    allow_missing_data_dir=true
  fi

  clean_channel "$channel" "$allow_missing_data_dir"

  if [[ "$openasar_betterdiscord_requested" != true && "$update_requested" != true ]]; then
    unwrap_betterdiscord_wrapper "$channel"
  fi

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
        openasar_injected=true
      fi
    else
      inject_openasar "$channel" "$openasar_payload"
      openasar_injected=true
    fi
  fi

  if [[ "$openasar_injected" == true ]]; then
    if ! openasar_matches_installed_target "$channel" "$openasar_payload"; then
      print -u2 "OpenAsar verification failed before relaunching $app_name."
      exit 1
    fi
  fi

  if [[ "$lock_requested" == true ]]; then
    if [[ "$openasar_injected" != true ]]; then
      print -u2 "Cannot write --lock for $app_name because OpenAsar injection was not completed."
      exit 1
    fi
    if discord_is_running "$channel"; then
      print -u2 "Cannot write --lock for $app_name because the client reappeared during update:"
      print -u2 "  $app_name is still running."
      exit 1
    fi

    if ! write_lock_settings "$channel" "$lock_version"; then
      print -u2 "Failed to write VersionLock for $app_name."
      exit 1
    fi
  fi

  relaunch_channel_if_needed "$channel" "$was_running_at_start"

  if [[ "$openasar_injected" == true ]]; then
    verify_openasar_after_relaunch "$channel" "$openasar_payload" "$was_running_at_start"
  fi
done

if [[ "$openasar_requested" == true ]]; then
  cleanup_openasar_payload
fi
