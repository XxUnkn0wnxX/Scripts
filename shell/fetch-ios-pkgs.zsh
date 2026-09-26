#!/usr/bin/env zsh

# Foundation of this script came from a MacRumors post by bogdanw:
# https://forums.macrumors.com/threads/itunes-software-updates.2416893/page-3?post=33894235#post-33894235

usage() {
  cat <<'USAGE'
Usage: fetch-ios-pkgs.zsh [--dry-run | --download-only]

No arguments     Show links, download selected packages, install CoreTypes then
                 MobileDevice and AppleKIS when applicable, and attempt restart.
--dry-run        Fetch the catalog and show the selected product and links only.
--download-only  Show links and download selected packages to ~/Downloads only.
-h, --help       Show this help without fetching anything.

The system's SeedCatalogs.plist is read only. Requires macOS 10.10 or later
with JavaScript for Automation and Foundation available through osascript.
Apple packages have their own macOS requirements; see docs/fetch-ios-pkgs.md.
USAGE
}

# Built-in JXA/Foundation parses XML and binary plists without an added runtime.
# Keep this ES5-compatible for the JavaScript engine shipped with OS X 10.10.
read_catalog_data() {
  /usr/bin/osascript -l JavaScript - "$@" <<'JXA'
ObjC.import('Foundation');

function diagnostic(level, message) {
    $.NSFileHandle.fileHandleWithStandardError.writeData(
        $(level + ': ' + message + '\n').dataUsingEncoding($.NSUTF8StringEncoding));
}

function warn(message) {
    diagnostic('Warning', message);
}

function dictionary(value) {
    return value && typeof value === 'object' && !Array.isArray(value) &&
        !(value instanceof Date);
}

function urlInfo(value) {
    if (typeof value !== 'string' || /[\x00-\x20\x7f]/.test(value) ||
        !/^https?:\/\//i.test(value)) return null;
    var url = $.NSURL.URLWithString(value);
    if (url.isNil() || !ObjC.unwrap(url.host)) return null;
    return {url: value, name: ObjC.unwrap(url.lastPathComponent)};
}

function hostInfo(value) {
    if (typeof value !== 'string' || !/^\d+(?:\.\d+)+$/.test(value)) return null;
    var parts = value.split('.').map(function (part) { return Number(part); });
    return {value: value, modern: parts[0] >= 13};
}

function run(argv) {
    var data = $.NSData.dataWithContentsOfFile(argv[1]);
    if (data.isNil()) throw new Error('Cannot read plist: ' + argv[1]);
    var error = Ref();
    var native = $.NSPropertyListSerialization.propertyListWithDataOptionsFormatError(
        data, 0, null, error);
    if (native.isNil()) throw new Error('Malformed plist: ' + argv[1]);
    var root = ObjC.deepUnwrap(native);
    if (!dictionary(root)) throw new Error('Expected a plist dictionary.');

    if (argv[0] === 'seed') {
        var seed = urlInfo(root.DeveloperSeed);
        if (!seed) throw new Error('Missing or invalid DeveloperSeed catalog URL.');
        return seed.url.replace(/\.gz$/, '');
    }

    var host = hostInfo(argv[2]);
    if (!host) throw new Error('Missing or invalid macOS product version.');
    if (!dictionary(root.Products)) throw new Error('Catalog has no Products dictionary.');
    var candidates = [], unrecognisedProducts = [];
    Object.keys(root.Products).sort().forEach(function (id) {
        var product = root.Products[id];
        if (!dictionary(product) || !Array.isArray(product.Packages)) return;
        var mobile = [], core = [], appleKIS = [], unrecognisedMobile = [];
        var duplicate = false, invalid = false;
        product.Packages.forEach(function (pkg) {
            if (!dictionary(pkg)) return;
            var info = urlInfo(pkg.URL);
            if (!info) {
                // Mention a broken URL when it appears to identify a wanted package.
                if (typeof pkg.URL === 'string' &&
                    /(?:MobileDeviceOnDemand(?:Package)?|CoreTypes)\.pkg(?:[?#]|$)/.test(pkg.URL)) {
                    invalid = true;
                }
                if (host.modern && typeof pkg.URL === 'string' &&
                    /AppleKIS\.pkg(?:[?#]|$)/.test(pkg.URL)) {
                    invalid = true;
                }
                return;
            }
            var list;
            if (info.name === 'CoreTypes.pkg') list = core;
            else if (info.name === 'MobileDeviceOnDemand.pkg' ||
                     info.name === 'MobileDeviceOnDemandPackage.pkg') list = mobile;
            else if (/^MobileDevice.*\.pkg$/.test(info.name)) {
                if (unrecognisedMobile.indexOf(info.name) === -1) unrecognisedMobile.push(info.name);
                return;
            }
            else if (host.modern && info.name === 'AppleKIS.pkg') list = appleKIS;
            else return;
            if (list.some(function (entry) { return entry.url === info.url; })) duplicate = true;
            else list.push(info);
        });
        if (!mobile.length && !core.length && !appleKIS.length && !invalid) return;
        var reason = '';
        if (!id || /[\x00-\x1f\x7f]/.test(id)) reason = 'invalid product ID';
        else if (invalid) reason = 'invalid package URL';
        else if (mobile.length > 1) reason = 'ambiguous MobileDevice package URLs';
        else if (core.length > 1) reason = 'ambiguous CoreTypes package URLs';
        else if (host.modern && appleKIS.length > 1) reason = 'ambiguous AppleKIS package URLs';
        else if (!(product.PostDate instanceof Date) || !isFinite(product.PostDate.getTime())) {
            reason = 'missing or invalid PostDate';
        }
        else if (!core.length) reason = 'missing CoreTypes.pkg';
        else if (!mobile.length) {
            if (unrecognisedMobile.length) {
                // Only classify this as harmless after finding a strictly newer complete product.
                unrecognisedProducts.push({id: id, date: product.PostDate, names: unrecognisedMobile});
                return;
            }
            reason = 'missing MobileDevice package';
        }
        if (reason) {
            warn('Skipping product ' + JSON.stringify(id) + ': ' + reason + '.');
            return;
        }
        if (duplicate) warn('Product ' + id + ': duplicate package URLs were deduplicated.');
        candidates.push({id: id, date: product.PostDate, core: core[0], mobile: mobile[0],
            appleKIS: appleKIS.length ? appleKIS[0] : null});
    });
    candidates.sort(function (a, b) {
        var delta = b.date.getTime() - a.date.getTime();
        return delta || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
    });
    var selected = candidates[0];
    unrecognisedProducts.forEach(function (product) {
        var names = product.names.sort().map(function (name) { return JSON.stringify(name); }).join(', ');
        if (selected && product.date.getTime() < selected.date.getTime()) {
            diagnostic('Info', 'Skipped older package set ' + JSON.stringify(product.id) + ' (' + names +
                '). Newer packages are available; no action is needed for this entry.');
        } else {
            warn('Could not use package set ' + JSON.stringify(product.id) +
                ': unrecognised MobileDevice package filename' + (product.names.length > 1 ? 's ' : ' ') +
                names + '.' + (selected ? ' The selected packages may not be the latest update.' : ''));
        }
    });
    if (!selected) throw new Error('No valid MobileDevice/CoreTypes product found.');
    if (candidates.length > 1 && selected.date.getTime() === candidates[1].date.getTime()) {
        warn('Newest products have equal PostDate values; selected product ' + selected.id +
             ' by ascending product ID. Device applicability has not been checked.');
    }
    var result = [selected.id, selected.date.toISOString().replace('.000Z', 'Z'),
        selected.core.url, selected.mobile.url, selected.mobile.name];
    if (host.modern && selected.appleKIS) result.push(selected.appleKIS.url);
    return result.join('\n');
}
JXA
}

seed_catalog_readable() {
  [[ -f "$1" && -r "$1" ]]
}

locate_seed_catalog_plist() {
  local candidate
  local -a candidates=(
    /System/Library/PrivateFrameworks/Seeding.framework/Resources/SeedCatalogs.plist
    /System/Library/PrivateFrameworks/Seeding.framework/Versions/Current/Resources/SeedCatalogs.plist
    /System/Library/PrivateFrameworks/Seeding.framework/Versions/A/Resources/SeedCatalogs.plist
  )
  for candidate in "${candidates[@]}"; do
    if seed_catalog_readable "$candidate"; then
      print -r -- "$candidate"
      return 0
    fi
  done
  print -u2 -- 'Could not locate a readable SeedCatalogs.plist.'
  return 1
}

get_catalog_url() {
  local seed_path
  if ! seed_path="$(locate_seed_catalog_plist)"; then
    return 1
  fi
  read_catalog_data seed "$seed_path"
}

get_macos_version() {
  SYSTEM_VERSION_COMPAT=0 /usr/bin/sw_vers -productVersion
}

print_password_visibility_notice() {
  if (( EUID == 0 )); then
    return 0
  fi
  local message='Password is invisible as you type.'
  if [[ -t 1 && "${TERM:-dumb}" != dumb ]]; then
    printf '\033[3m%s\033[0m\n' "$message"
  else
    print -r -- "$message"
  fi
}

read_arm64_capability() {
  /usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null
}

read_rosetta_translation() {
  /usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null
}

read_uname_architecture() {
  /usr/bin/uname -m 2>/dev/null
}

get_hardware_architecture() {
  local arm64_capability rosetta_translation raw_architecture
  if arm64_capability="$(read_arm64_capability)"; then
    if [[ "$arm64_capability" == 1 ]]; then
      print -r -- arm64
      return 0
    fi
  fi
  if rosetta_translation="$(read_rosetta_translation)"; then
    if [[ "$rosetta_translation" == 1 ]]; then
      print -r -- arm64
      return 0
    fi
  fi
  if ! raw_architecture="$(read_uname_architecture)" || [[ -z "$raw_architecture" ]]; then
    print -u2 -- 'Failed to determine the hardware architecture.'
    return 1
  fi
  case "$raw_architecture" in
    arm64|arm64e) print -r -- arm64 ;;
    x86_64) print -r -- x86_64 ;;
    *)
      print -u2 -- "Unsupported hardware architecture: $raw_architecture."
      return 1
      ;;
  esac
}

is_valid_product_version() {
  local value="$1" component
  local -a components

  [[ -n "$value" && "$value" != .* && "$value" != *. && "$value" != *..* ]] || return 1
  components=("${(s:.:)value}")
  (( ${#components} >= 2 )) || return 1
  for component in "${components[@]}"; do
    [[ "$component" == <-> ]] || return 1
  done
}

select_catalog_product() {
  local catalog_path="$1"
  local host_version="${2:-}"
  if [[ -z "$host_version" ]]; then
    host_version="$(get_macos_version)" || return 1
  fi
  read_catalog_data select "$catalog_path" "$host_version"
}

install_pkg() {
  local pkg_path="$1"

  if [[ ! -f "$pkg_path" ]]; then
    echo "Missing package: $pkg_path"
    return 1
  fi

  echo "Installing package:"
  echo "$pkg_path"
  "${INSTALLER_CMD[@]}" -verboseR -pkg "$pkg_path" -target / || return 1
  echo
}

usbmuxd_read_pids() {
  /usr/bin/pgrep -x usbmuxd
}

usbmuxd_sleep() {
  sleep "$1"
}

usbmuxd_signal() {
  local signal="$1"
  shift
  if (( EUID == 0 )); then
    /bin/kill "-$signal" "$@"
  else
    sudo /bin/kill "-$signal" "$@"
  fi
}

usbmuxd_launchctl() {
  "${LAUNCHCTL_CMD[@]}" "$@"
}

usbmuxd_plist_exists() {
  [[ -e "$1" ]]
}

usbmuxd_snapshot() {
  local raw result_code pid
  local -a pids

  if raw="$(usbmuxd_read_pids)"; then
    result_code=0
  else
    result_code=$?
  fi
  if (( result_code == 1 )); then
    return 1
  elif (( result_code != 0 )); then
    print -u2 -- "Could not inspect the usbmuxd process list (status $result_code)."
    return "$result_code"
  fi

  [[ -n "$raw" ]] || {
    print -u2 -- "Could not inspect the usbmuxd process list: pgrep returned no PIDs with success."
    return 2
  }

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    if [[ "$pid" != <-> ]] || (( pid <= 0 )); then
      print -u2 -- "Could not inspect the usbmuxd process list: invalid PID '$pid'."
      return 2
    fi
    pids+=("$pid")
  done <<< "$raw"

  (( ${#pids} > 0 )) || return 2
  print -rl -- "${pids[@]}"
}

usbmuxd_pid_is_present() {
  local wanted="$1"
  shift
  local candidate
  for candidate in "$@"; do
    [[ "$candidate" == "$wanted" ]] && return 0
  done
  return 1
}

usbmuxd_signal_live_originals() {
  local signal="$1"
  shift
  local output result_code original
  local -a current targets

  if output="$(usbmuxd_snapshot)"; then
    result_code=0
  else
    result_code=$?
  fi
  if (( result_code == 1 )); then
    return 1
  elif (( result_code != 0 )); then
    return "$result_code"
  fi
  current=("${(@f)output}")
  for original in "$@"; do
    if usbmuxd_pid_is_present "$original" "${current[@]}"; then
      targets+=("$original")
    fi
  done
  (( ${#targets} > 0 )) || return 1
  usbmuxd_signal "$signal" "${targets[@]}"
}

usbmuxd_wait_for_replacement() {
  local baseline_count="$1"
  shift
  local output result_code attempt original
  local -a originals current

  originals=("$@")
  for attempt in {0..10}; do
    if output="$(usbmuxd_snapshot)"; then
      result_code=0
    else
      result_code=$?
    fi
    if (( result_code == 1 )); then
      current=()
    elif (( result_code == 0 )); then
      current=("${(@f)output}")
    else
      return 2
    fi

    if (( ${#current} > 0 )); then
      if (( baseline_count == 0 )); then
        print -- "usbmuxd STARTED with PID(s): ${current[*]}"
        return 0
      fi
      local originals_gone=1
      for original in "${originals[@]}"; do
        if usbmuxd_pid_is_present "$original" "${current[@]}"; then
          originals_gone=0
          break
        fi
      done
      if (( originals_gone )); then
        print -- "usbmuxd RESTARTED with PID(s): ${current[*]}"
        return 0
      fi
    fi

    (( attempt == 10 )) && break
    if ! usbmuxd_sleep 1; then
      print -u2 -- "Could not wait while checking for the usbmuxd replacement."
      return 2
    fi
  done
  return 1
}

restart_mobile_services() {
  local usbmux_label="com.apple.usbmuxd"

  local preferred_plist="/Library/Apple/System/Library/LaunchDaemons/com.apple.usbmuxd.plist"
  local fallback_plist="/System/Library/LaunchDaemons/com.apple.usbmuxd.plist"
  local baseline baseline_status wait_status plist plist_status plist_candidate
  local -a original

  echo "Restarting mobile device services..."
  echo

  if baseline="$(usbmuxd_snapshot)"; then
    baseline_status=0
  else
    baseline_status=$?
  fi
  if (( baseline_status == 1 )); then
    original=()
    echo "No usbmuxd process is running; waiting for a fresh start."
  elif (( baseline_status == 0 )); then
    original=("${(@f)baseline}")
    echo "Observed usbmuxd PID(s): ${original[*]}"
  else
    return 1
  fi

  if (( ${#original} > 0 )); then
    echo "Stopping original usbmuxd process(es) with TERM..."
    if ! usbmuxd_signal_live_originals TERM "${original[@]}"; then
      print -u2 -- "TERM could not be sent to the original usbmuxd process(es); continuing recovery."
    fi
  fi

  if (( ${#original} > 0 )); then
    if usbmuxd_wait_for_replacement "${#original}" "${original[@]}"; then
      return 0
    else
      wait_status=$?
      (( wait_status == 2 )) && return 1
    fi
  fi

  echo "Trying launchctl kickstart -k..."
  if ! usbmuxd_launchctl kickstart -k "system/$usbmux_label"; then
    print -u2 -- "launchctl kickstart -k failed; continuing recovery."
  fi
  if usbmuxd_wait_for_replacement "${#original}" "${original[@]}"; then
    return 0
  else
    wait_status=$?
    (( wait_status == 2 )) && return 1
  fi

  if (( ${#original} > 0 )); then
    echo "Trying force-kill fallback for original usbmuxd process(es)..."
    if ! usbmuxd_signal_live_originals KILL "${original[@]}"; then
      print -u2 -- "Force-kill could not be sent to the original usbmuxd process(es); continuing recovery."
    fi
    if usbmuxd_wait_for_replacement "${#original}" "${original[@]}"; then
      return 0
    else
      wait_status=$?
      (( wait_status == 2 )) && return 1
    fi
  fi

  plist=""
  for plist_candidate in "$preferred_plist" "$fallback_plist"; do
    usbmuxd_plist_exists "$plist_candidate"
    plist_status=$?
    if (( plist_status == 0 )); then
      plist="$plist_candidate"
      break
    fi
    if (( plist_status != 1 )); then
      print -u2 -- "Could not inspect legacy usbmuxd plist: $plist_candidate (status $plist_status)."
      return 1
    fi
  done

  if [[ -n "$plist" ]]; then
    echo "Trying legacy launchctl unload/load with $plist..."
    if ! usbmuxd_launchctl unload "$plist"; then
      print -u2 -- "legacy launchctl unload failed; continuing recovery."
    fi
    if ! usbmuxd_launchctl load "$plist"; then
      print -u2 -- "legacy launchctl load failed; continuing recovery."
    fi
    if usbmuxd_wait_for_replacement "${#original}" "${original[@]}"; then
      return 0
    else
      wait_status=$?
      (( wait_status == 2 )) && return 1
    fi
  else
    echo "No legacy usbmuxd launchd plist was found."
  fi

  echo "Could not confirm usbmuxd restarted."
  echo "Most reliable fallback: unplug the iPhone, reconnect it, or reboot the Mac."
  return 1
}

fetch_ios_pkgs_main() (
  set -euo pipefail

  local mode=install arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run|--download-only)
        if [[ "$mode" != install ]]; then
          print -u2 -- 'Choose only one of --dry-run or --download-only.'
          return 2
        fi
        mode="${arg#--}"
        ;;
      -h|--help) usage; return 0 ;;
      *) print -u2 -- "Unknown argument: $arg"; usage >&2; return 2 ;;
    esac
  done

  local macos_version hardware_architecture catalog_url selection work_dir download_dir='' mobile_name=''
  local apple_kis_url=''
  local target_dir="$HOME/Downloads"
  local -a selected INSTALLER_CMD LAUNCHCTL_CMD

  if ! macos_version="$(get_macos_version)" ||
     ! is_valid_product_version "$macos_version"; then
    print -u2 -- "Failed to determine a valid macOS product version."
    return 1
  fi
  if ! hardware_architecture="$(get_hardware_architecture)" ||
     [[ "$hardware_architecture" != arm64 && "$hardware_architecture" != x86_64 ]]; then
    print -u2 -- "Failed to determine a supported hardware architecture."
    return 1
  fi
  printf 'macOS version: %s\nHardware architecture: %s\n\n' "$macos_version" "$hardware_architecture"

  echo 'Getting DeveloperSeed catalog URL...'
  if ! catalog_url="$(get_catalog_url)" || [[ -z "$catalog_url" ]]; then
    print -u2 -- 'Failed to find a valid DeveloperSeed catalog URL.'
    return 1
  fi
  printf 'Catalog URL:\n%s\n\n' "$catalog_url"

  work_dir="$(mktemp -d "${TMPDIR:-/tmp}/fetch-ios-pkgs.XXXXXX")" || return 1
  trap 'rm -f "$work_dir/catalog.plist"
        rmdir "$work_dir" 2>/dev/null || true
        if [[ -n "$download_dir" ]]; then
          rm -f "$download_dir/CoreTypes.pkg" "$download_dir/$mobile_name" "$download_dir/AppleKIS.pkg"
          rmdir "$download_dir" 2>/dev/null || true
        fi' EXIT

  echo 'Fetching catalog...'
  if ! curl -fsSL --proto '=http,https' --proto-redir '=http,https' \
      "$catalog_url" -o "$work_dir/catalog.plist"; then
    print -u2 -- 'Catalog download failed.'
    return 1
  fi

  echo 'Selecting newest complete MobileDevice/CoreTypes product...'
  selection="$(select_catalog_product "$work_dir/catalog.plist" "$macos_version")" || return 1
  selected=("${(@f)selection}")
  if (( ${#selected} != 5 && ${#selected} != 6 )); then
    print -u2 -- 'Invalid package selection result.'
    return 1
  fi
  mobile_name="$selected[5]"
  if (( ${#selected} == 6 )); then
    apple_kis_url="$selected[6]"
  fi
  printf '\nSelected product: %s\nPostDate: %s\n' "$selected[1]" "$selected[2]"
  printf 'CoreTypes URL:\n%s\nMobileDevice URL:\n%s\n' "$selected[3]" "$selected[4]"
  if [[ -n "$apple_kis_url" ]]; then
    printf 'AppleKIS URL:\n%s\n' "$apple_kis_url"
  fi
  echo

  if [[ "$mode" == dry-run ]]; then
    echo 'Dry run complete. No packages downloaded or installed; no services restarted.'
    return 0
  fi

  mkdir -p "$target_dir" || return 1
  download_dir="$(mktemp -d "$target_dir/.fetch-ios-pkgs.XXXXXX")" || return 1
  printf 'Downloading to: %s\n\n' "$target_dir"
  local pkg_url pkg_name index
  # Preserve the download order; stage every selected package before replacing completed downloads.
  for index in 4 3 6; do
    (( index == 6 && ${#selected} != 6 )) && continue
    pkg_url="$selected[$index]"
    if (( index == 4 )); then
      pkg_name="$mobile_name"
    elif (( index == 3 )); then
      pkg_name=CoreTypes.pkg
    else
      pkg_name=AppleKIS.pkg
    fi
    printf 'Downloading URL:\n%s\n' "$pkg_url"
    if ! curl -fL --show-error --progress-bar --proto '=http,https' --proto-redir '=http,https' \
        -o "$download_dir/$pkg_name" "$pkg_url"; then
      print -u2 -- "Package download failed: $pkg_name. No packages were installed."
      return 1
    fi
    echo
  done
  mv -f "$download_dir/CoreTypes.pkg" "$target_dir/CoreTypes.pkg" || return 1
  mv -f "$download_dir/$mobile_name" "$target_dir/$mobile_name" || return 1
  if [[ -n "$apple_kis_url" ]]; then
    mv -f "$download_dir/AppleKIS.pkg" "$target_dir/AppleKIS.pkg" || return 1
  fi
  printf 'Files saved in: %s\n\n' "$target_dir"

  if [[ "$mode" == download-only ]]; then
    echo 'Download complete. No packages installed; no services restarted.'
    return 0
  fi

  if (( EUID == 0 )); then
    INSTALLER_CMD=(/usr/sbin/installer)
    LAUNCHCTL_CMD=(/bin/launchctl)
  else
    INSTALLER_CMD=(sudo /usr/sbin/installer)
    LAUNCHCTL_CMD=(sudo /bin/launchctl)
  fi

  echo 'Installing downloaded packages...'
  echo
  echo 'Normal install mode will install these packages into system locations on /:'
  echo '  CoreTypes.pkg'
  echo "  $mobile_name"
  if [[ -n "$apple_kis_url" ]]; then
    echo '  AppleKIS.pkg'
  fi
  if (( EUID != 0 )); then
    echo 'The installer may ask for an administrator password for these changes.'
    print_password_visibility_notice
  fi
  echo 'After installation, the script will attempt to restart usbmuxd to reload device support.'
  echo
  install_pkg "$target_dir/CoreTypes.pkg" || return 1
  install_pkg "$target_dir/$mobile_name" || return 1
  if [[ -n "$apple_kis_url" ]]; then
    install_pkg "$target_dir/AppleKIS.pkg" || return 1
  fi
  echo 'Install completed successfully.'
  if (( EUID != 0 )); then
    echo 'Restarting usbmuxd to reload device support; service recovery may ask for an administrator password again.'
    print_password_visibility_notice
  else
    echo 'Restarting usbmuxd to reload device support.'
  fi
  if ! restart_mobile_services; then
    echo 'Mobile device services restart could not be confirmed.'
  fi
  echo 'If the device does not reappear, unlock it and reconnect its cable.'
  echo 'Done.'
)

# Allow offline tests to source the helpers without downloads or privileged work.
if [[ "$ZSH_EVAL_CONTEXT" == toplevel ]]; then
  fetch_ios_pkgs_main "$@"
fi
