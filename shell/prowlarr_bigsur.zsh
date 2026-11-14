#!/usr/bin/env zsh
set -euo pipefail

PROWLARR_MANAGE_LAUNCH_AGENT="${PROWLARR_MANAGE_LAUNCH_AGENT:-true}"
PROWLARR_LAUNCH_AGENT="${PROWLARR_LAUNCH_AGENT:-Prowlarr}"
PROWLARR_BACKUP_ZIP="${PROWLARR_BACKUP_ZIP:-/Applications/Prowlarr.backup.zip}"

usage() {
  cat <<'EOF'
Usage:
  prowlarr_bigsur.zsh [APP.app]
  prowlarr_bigsur.zsh --dl [stable|pre] [APP.app]
  prowlarr_bigsur.zsh -h|--help

Match Prowlarr's compatibility metadata to older macOS: Intel Big Sur 11.x.
APP.app defaults to /Applications/Prowlarr.app. --dl defaults to stable;
--dl pre selects prereleases. Download mode always replaces with the latest
full x64 app in that family, regardless of the installed version.

PROWLARR_MANAGE_LAUNCH_AGENT=true (default) preserves the loaded agent state.
Set it to false to skip all agent handling. PROWLARR_LAUNCH_AGENT=Prowlarr
selects ~/Library/LaunchAgents/Prowlarr.plist; a .plist suffix is optional.

Downloads are saved in ~/Downloads with the selected upstream filename.
One backup ZIP is kept at /Applications/Prowlarr.backup.zip; override with
PROWLARR_BACKUP_ZIP. New archives replace existing files after validation.
Ctrl+C restores before startup; after startup may have occurred, the new
app and backup ZIP are retained.
EOF
}

fail() { print -u2 -- "Prowlarr patch: $*"; return 0; }
has_tool() { command -v "$1" >/dev/null 2>&1; }
log() { print -- "Prowlarr patch: $*"; }

# Help is deliberately handled before resolving a target or checking tools.
for arg in "$@"; do
  if [[ "$arg" == -h || "$arg" == --help ]]; then usage; exit 0; fi
done

download_mode=0
family=stable
target=/Applications/Prowlarr.app
if (( $# )); then
  if [[ "$1" == --dl ]]; then
    download_mode=1
    shift
    if (( $# )) && [[ "$1" == stable || "$1" == pre ]]; then family="$1"; shift; fi
    if (( $# == 1 )); then target="$1"; shift; fi
  elif (( $# == 1 )); then target="$1"; shift
  fi
fi
(( $# == 0 )) || { usage >&2; print -u2 -- "Prowlarr patch: invalid arguments"; exit 2; }
[[ "$target" == *.app ]] || { print -u2 -- "Prowlarr patch: target must be an .app bundle"; exit 2; }
[[ "$PROWLARR_MANAGE_LAUNCH_AGENT" == true || "$PROWLARR_MANAGE_LAUNCH_AGENT" == false ]] || { print -u2 -- "Prowlarr patch: PROWLARR_MANAGE_LAUNCH_AGENT must be true or false"; exit 2; }

for tool in plutil codesign ditto vtool otool lipo lsof shasum osascript unzip; do
    has_tool "$tool" || { fail "required tool not found: $tool"; exit 1; }
done
if [[ "$PROWLARR_MANAGE_LAUNCH_AGENT" == true ]]; then has_tool launchctl || { fail "required tool not found: launchctl"; exit 1; }; fi
if (( download_mode )); then
  for tool in curl jq shasum; do has_tool "$tool" || { fail "required tool not found: $tool"; exit 1; }; done
fi

target="${target:A}"
[[ "$target" != / ]] || { fail "invalid target"; exit 2; }
parent="${target:h}"
[[ -d "$parent" ]] || { fail "target parent does not exist: $parent"; exit 1; }
[[ "$PROWLARR_BACKUP_ZIP" == *.zip ]] || { fail "backup path must end in .zip"; exit 2; }
backup_zip="${PROWLARR_BACKUP_ZIP:a}"
backup_zip="${${backup_zip:h}:A}/${backup_zip:t}"
[[ -d "${backup_zip:h}" && "$backup_zip" != "$target"/* ]] || { fail "invalid backup parent"; exit 1; }
base="${target:t}"
lock="$parent/.${base}.prowlarr-lock"
mkdir "$lock" 2>/dev/null || { fail "target lock exists: $lock"; exit 1; }
txn=""
stage="$txn/candidate.app"
backup=""
original_moved=0
candidate_installed=0
installed_verified=0
startup_possible=0
restore_required=0
initial_loaded=0
plist_path=""
domain=""
original_domain=""
label=""
target_exec=""
cleanup_running=0
candidate_identity=""
plist_hash=""
plist_present=0
original_present=0
original_identity=""
preserve_txn=0
download_temp=""
backup_temp=""
backup_published=0
backup_identity=""

exclusive_rename() {
  osascript -l JavaScript -e 'ObjC.import("Foundation"); ObjC.bindFunction("renamex_np", ["int", ["string", "string", "unsigned int"]]); function run(args) { if ($.renamex_np(args[0], args[1], 4) !== 0) { throw new Error("exclusive rename failed"); } }' "$1" "$2"
}
atomic_replace() {
  osascript -l JavaScript -e 'ObjC.import("Foundation"); ObjC.bindFunction("renamex_np", ["int", ["string", "string", "unsigned int"]]); function run(args) { if ($.renamex_np(args[0], args[1], 0) !== 0) { throw new Error("atomic rename failed"); } }' "$1" "$2"
}
identity() { /usr/bin/stat -f '%d:%i' "$1"; }
sha256_file() {
  local output digest
  output="$(shasum -a 256 "$1")" || return 1
  digest="${output%% *}"
  [[ "$digest" =~ '^[0-9a-f]{64}$' ]] || return 1
  print -r -- "$digest"
}

restore_service() {
  [[ "$PROWLARR_MANAGE_LAUNCH_AGENT" == true ]] || return 0
  (( restore_required && ! startup_possible )) || return 0
  [[ -f "$plist_path" && "$(sha256_file "$plist_path")" == "$plist_hash" ]] || { fail "cannot restore changed or missing agent plist"; return 1; }
  validate_bundle "$target" || return 1
  job_state "$domain" || return 1
  if [[ "$REPLY" == loaded ]]; then return 0; fi
  wait_users || return 1
  startup_possible=1
  launchctl bootstrap "$domain" "$plist_path" || { fail "failed to restore LaunchAgent in $domain"; return 1; }
  restore_required=0
}

cleanup() {
  local rc=$?
  (( cleanup_running == 0 )) || return
  cleanup_running=1
  trap - EXIT
  trap "" HUP INT TERM
  if (( rc != 0 && ! startup_possible )); then
    # Reconcile both objects before touching either: a missing or replaced
    # original leaves the candidate and all transaction material in place.
    if (( original_moved )); then
      if [[ -e "$backup" && "$(identity "$backup" 2>/dev/null)" == "$original_identity" ]]; then
        :
      elif [[ ! -e "$backup" && -e "$target" && "$(identity "$target" 2>/dev/null)" == "$original_identity" ]]; then
        original_moved=0
      else
        fail "original identity unresolved; preserving transaction and target"
        preserve_txn=1
      fi
    elif (( original_present )) && [[ ! -e "$target" || "$(identity "$target" 2>/dev/null)" != "$original_identity" ]]; then
      fail "original identity changed; preserving transaction and target"
      preserve_txn=1
    fi
    if (( candidate_installed )) && [[ -e "$stage" ]]; then candidate_installed=0; fi
    if (( ! preserve_txn && candidate_installed )); then
      if [[ -e "$target" && "$(identity "$target" 2>/dev/null)" == "$candidate_identity" ]] && exclusive_rename "$target" "$txn/failed-candidate.app"; then
        if [[ "$(identity "$txn/failed-candidate.app" 2>/dev/null)" == "$candidate_identity" ]]; then candidate_installed=0
        else
          preserve_txn=1
          exclusive_rename "$txn/failed-candidate.app" "$target" || true
          fail "replacement changed during recovery; preserving all recovery material"
        fi
      else
        fail "candidate identity changed or could not be removed; preserving target and original"
        preserve_txn=1
      fi
    fi
    if (( ! preserve_txn && original_moved )); then
      if [[ "$(identity "$backup" 2>/dev/null)" == "$original_identity" ]] && exclusive_rename "$backup" "$target" && [[ "$(identity "$target" 2>/dev/null)" == "$original_identity" ]]; then original_moved=0
      else fail "CRITICAL: original recovery identity unresolved"; preserve_txn=1; fi
    fi
    if (( ! preserve_txn && ! original_moved && ! candidate_installed )); then restore_service || rc=1; fi
  elif (( original_moved )); then
    if [[ "$(identity "$backup" 2>/dev/null)" != "$original_identity" || $backup_published != 1 || "$(identity "$backup_zip" 2>/dev/null)" != "$backup_identity" ]]; then
      fail "backup identity unresolved; preserving transaction"
      preserve_txn=1; rc=1
    fi
  fi
  [[ -z "$download_temp" || ! -e "$download_temp" ]] || rm -f "$download_temp"
  [[ -z "$backup_temp" || ! -e "$backup_temp" ]] || rm -f "$backup_temp"
  if (( preserve_txn )); then log "recovery transaction retained at: $txn"; rc=1
  else [[ -z "$txn" || ! -d "$txn" ]] || rm -rf "$txn"; fi
  rmdir "$lock" 2>/dev/null || true
  if (( rc != 0 && original_moved )); then
    if (( preserve_txn )) && [[ -d "$backup" && "$(identity "$backup" 2>/dev/null)" == "$original_identity" ]]; then
      log "recoverable original bundle: $backup"
    elif (( backup_published )) && [[ -f "$backup_zip" && "$(identity "$backup_zip" 2>/dev/null)" == "$backup_identity" ]]; then
      log "recoverable backup ZIP: $backup_zip"
    fi
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
txn="$(mktemp -d "$parent/.${base}.txn.XXXXXXXX")" || { fail "could not create transaction directory"; exit 1; }
stage="$txn/candidate.app"
mkdir "$txn/original" || exit 1
backup="$txn/original/$base"

plist_get() {
  local buddy
  buddy="$(command -v PlistBuddy 2>/dev/null || print /usr/libexec/PlistBuddy)"
  "$buddy" -c "Print :$2" "$1" 2>/dev/null
}

read_bundle() {
  local app="$1" info="$1/Contents/Info.plist" bid exe
  [[ -d "$app" && -f "$info" ]] || return 1
  [[ "${info:A}" == "${app:A}/Contents/Info.plist" ]] || return 1
  bid="$(plist_get "$info" CFBundleIdentifier)" || return 1
  exe="$(plist_get "$info" CFBundleExecutable)" || return 1
  [[ "$bid" == com.osx.prowlarr.com ]] || return 1
  [[ -n "$exe" && "$exe" != */* && -f "$app/Contents/MacOS/$exe" && -x "$app/Contents/MacOS/$exe" ]] || return 1
  [[ "${app:A}/Contents/MacOS/$exe" == "${${:-$app/Contents/MacOS/$exe}:A}" ]] || return 1
  REPLY="$app/Contents/MacOS/$exe"
}

check_macho() {
  local exe="$1"
  local archs
  archs="$(lipo -archs "$exe" 2>/dev/null)" || return 1
  [[ "$archs" == x86_64 ]] || { fail "only thin x86_64 Prowlarr executables are supported"; return 1; }
  otool -l "$exe" >/dev/null || { fail "invalid Mach-O executable"; return 1; }
}

parse_build_tuple() {
  local load_commands
  load_commands="$(otool -l "$1")" || return 1
  awk '
    function finish() {
      if (!kind) return
      count++
      if (kind != "build" || p != "1" || m !~ /^[0-9]+([.][0-9]+)*$/ || s !~ /^[0-9]+([.][0-9]+)*$/ || n !~ /^[0-9]+$/ || seen != n || pending != "") bad=1
      row=m "|" s "|" tools
      kind=""; p=""; m=""; s=""; n=""; seen=0; pending=""; tools=""
    }
    /^Load command / { finish(); next }
    $1 == "cmd" && ($2 == "LC_BUILD_VERSION" || $2 == "LC_VERSION_MIN_MACOSX") { kind=($2 == "LC_BUILD_VERSION" ? "build" : "legacy"); next }
    kind && $1 == "platform" { p=$2; next }
    kind && $1 == "minos" { m=$2; next }
    kind && $1 == "sdk" { s=$2; next }
    kind && $1 == "ntools" { n=$2; next }
    kind && $1 == "tool" { if (pending != "" || $2 !~ /^[0-9]+$/) bad=1; pending=$2; next }
    kind && $1 == "version" { if (pending == "" || $2 !~ /^[0-9]+([.][0-9]+)*$/) bad=1; tools=tools (tools=="" ? "" : " ") pending "=" $2; pending=""; seen++; next }
    END { finish(); if (count != 1 || bad) exit 1; print row }
  ' <<< "$load_commands"
}

patch_native() {
  local exe="$1"
  local parsed
  parsed="$(parse_build_tuple "$exe")" || { fail "unsupported or ambiguous macOS build-version load commands"; return 1; }
  local minimum sdk tools rest
  minimum="${parsed%%|*}"; rest="${parsed#*|}"; sdk="${rest%%|*}"; tools="${rest#*|}"
  [[ "$minimum" =~ '^[0-9]+(\.[0-9]+){0,2}$' && "$sdk" =~ '^[0-9]+(\.[0-9]+){0,2}$' ]] || { fail "malformed Mach-O version tuple"; return 1; }
  local -a args
  args=(-set-build-version macos 11 "$sdk")
  local -a tool_pairs
  tool_pairs=()
  [[ -z "$tools" ]] || tool_pairs=("${(z)tools}")
  for pair in "$tool_pairs[@]"; do
    [[ "$pair" == *=* ]] || { fail "malformed Mach-O tool/version tuple"; return 1; }
    local tid="${pair%%=*}" ver="${pair#*=}"
    [[ "$ver" =~ '^[0-9]+(\.[0-9]+){0,2}$' ]] || { fail "malformed Mach-O tool version"; return 1; }
    args+=(-tool "$tid" "$ver")
  done
  local out="$exe.patched"
  vtool "${args[@]}" -replace -output "$out" "$exe" || { rm -f "$out"; fail "vtool failed"; return 1; }
  local after_tuple after_min after_rest
  after_tuple="$(parse_build_tuple "$out")" || { rm -f "$out"; fail "vtool output has unsupported or ambiguous build-version commands"; return 1; }
  after_min="${after_tuple%%|*}"
  after_rest="${after_tuple#*|}"
  [[ "$after_min" == 11 || "$after_min" == 11.0 || "$after_min" == 11.0.0 ]] || { rm -f "$out"; fail "vtool output did not set macOS minimum 11"; return 1; }
  [[ "$after_rest" == "$sdk|$tools" ]] || { rm -f "$out"; fail "vtool changed SDK or build-tool versions"; return 1; }
  cat "$out" > "$exe" || { rm -f "$out"; fail "could not replace staged executable bytes"; return 1; }
  rm -f "$out"
}

validate_bundle() {
  local app="$1" exe
  read_bundle "$app" || { fail "not a valid Prowlarr app bundle: $app"; return 1; }
  exe="$REPLY"
  check_macho "$exe" || { fail "unsupported executable architecture"; return 1; }
  REPLY="$exe"
}

download_release() {
  local page=1 all="$txn/releases.json" response="$txn/page.json"
  print '[]' > "$all"
  while (( page <= 20 )); do
    curl --fail --silent --show-error --connect-timeout 15 --max-time 60 "https://api.github.com/repos/Prowlarr/Prowlarr/releases?per_page=100&page=$page" -o "$response" || { fail "GitHub release metadata request failed"; return 1; }
    jq -e 'type == "array"' "$response" >/dev/null || { fail "invalid release metadata response"; return 1; }
    local n
    n="$(jq 'length' "$response")"
    jq -s '.[0] + .[1]' "$all" "$response" > "$all.next" && mv "$all.next" "$all" || { fail "could not collect release metadata"; return 1; }
    (( n < 100 )) && break
    (( page == 20 )) && { fail "release enumeration exceeded pagination cap"; return 1; }
    (( page += 1 ))
  done
  local chosen
  chosen="$(jq -cer --arg family "$family" '
    def nums: (.tag_name | capture("(?<v>[0-9]+(\\.[0-9]+)+)").v | split(".") | map(tonumber));
    [ .[] | select(.draft == false) | select((.prerelease == true) == ($family == "pre"))
      | select(.tag_name | test("[0-9]+(\\.[0-9]+)+"))
      | . as $r | {r:$r, n:($r|nums)} ]
    | sort_by(.n) | last | .r
  ' "$all")" || { fail "no eligible $family release found"; return 1; }
  local asset_url digest asset_count release_name tag asset_name downloads
  release_name="$(jq -r '.name // .tag_name' <<< "$chosen")"
  tag="$(jq -r '.tag_name' <<< "$chosen")"
  asset_count="$(jq '[.assets[] | select(.name | endswith(".osx-app-core-x64.zip"))] | length' <<< "$chosen")"
  [[ "$asset_count" == 1 ]] || { fail "selected release must contain exactly one full x64 app archive"; return 1; }
  asset_name="$(jq -r '.assets[] | select(.name | endswith(".osx-app-core-x64.zip")) | .name' <<< "$chosen")"
  [[ "$asset_name" != */* && "$asset_name" != *..* && "$asset_name" == *.osx-app-core-x64.zip ]] || { fail "invalid archive filename"; return 1; }
  downloads="$HOME/Downloads"
  [[ -d "$downloads" ]] || { fail "Downloads directory does not exist"; return 1; }
  download_temp="$(mktemp "$downloads/.prowlarr-download.XXXXXXXX")" || { fail "could not create download temporary file"; return 1; }
  asset_url="$(jq -r '.assets[] | select(.name | endswith(".osx-app-core-x64.zip")) | .browser_download_url' <<< "$chosen")"
  [[ "$asset_url" == https://github.com/Prowlarr/Prowlarr/releases/download/* ]] || { fail "untrusted release asset URL"; return 1; }
  digest="$(jq -r '.assets[] | select(.name | endswith(".osx-app-core-x64.zip")) | .digest // empty' <<< "$chosen")"
  log "downloading $tag ($family): $asset_url"
  curl --fail --location --progress-bar --show-error --connect-timeout 15 --max-time 900 "$asset_url" -o "$download_temp" || { fail "release archive download failed"; return 1; }
  if [[ "$digest" == sha256:* ]]; then
    local actual
    actual="$(sha256_file "$download_temp")" || { fail "could not hash downloaded archive"; return 1; }
    [[ "$actual" == "${digest#sha256:}" ]] || { fail "release archive SHA256 mismatch"; return 1; }
  fi
  mkdir "$txn/unpack" || { fail "could not create archive directory"; return 1; }
  ditto -x -k "$download_temp" "$txn/unpack" || { fail "could not unpack release archive"; return 1; }
  local -a apps
  apps=("$txn/unpack"/*.app(N))
  (( ${#apps} == 1 )) || { fail "archive must contain exactly one top-level .app"; return 1; }
  ditto "${apps[1]}" "$stage" || { fail "could not stage downloaded app"; return 1; }
  validate_bundle "$stage" || return 1
  atomic_replace "$download_temp" "$downloads/$asset_name" || { fail "could not publish downloaded archive"; return 1; }
  download_temp=""
  log "saved downloaded archive: $downloads/$asset_name"
  log "selected $release_name ($tag) from $family releases"
}

# A failed launchctl lookup is only an unloaded job when launchctl explicitly says so.
job_state() {
  local output rc program
  output="$(launchctl print "$1/$label" 2>&1)" && rc=0 || rc=$?
  if (( rc )); then
    [[ "$output" == *"Could not find service"* ]] || { fail "cannot determine LaunchAgent state: $output"; return 1; }
    REPLY=unloaded; return 0
  fi
  program="$(awk '/^[[:space:]]*program = / { sub(/^[[:space:]]*program = /, ""); print; n++ } END { if (n != 1) exit 1 }' <<< "$output")" || { fail "loaded LaunchAgent has ambiguous program"; return 1; }
  [[ "${program:A}" == "$target_exec" ]] || { fail "loaded LaunchAgent binding differs from its plist"; return 1; }
  REPLY=loaded
}
wait_users() {
  local users rc i
  [[ -e "$target_exec" ]] || { (( original_present == 0 )) && return 0; fail "target executable disappeared"; return 1; }
  for i in {1..20}; do
    users="$(lsof -t "$target_exec" 2>"$txn/lsof-error")" && rc=0 || rc=$?
    [[ ! -s "$txn/lsof-error" ]] || { fail "could not inspect executable users"; return 1; }
    (( rc == 0 || rc == 1 )) || { fail "could not inspect executable users"; return 1; }
    [[ -z "$users" && $rc == 1 ]] && return 0
    [[ -z "$users" && $rc == 0 ]] && return 0
    (( i == 20 )) || sleep 1
  done
  fail "target executable is still in use by process(es): ${(j:,:)${(f)users}}"; return 1
}
wait_unloaded() {
  local i
  for i in {1..20}; do
    job_state "$domain" || return 1
    [[ "$REPLY" == unloaded ]] && return 0
    (( i == 20 )) || sleep 1
  done
  fail "LaunchAgent did not unload"; return 1
}
agent_snapshot() {
  [[ "$PROWLARR_MANAGE_LAUNCH_AGENT" == true ]] || return 0
  local name="$PROWLARR_LAUNCH_AGENT" program found=0 d
  [[ "$name" != */* && "$name" != *..* && -n "$name" ]] || { fail "LaunchAgent name must be a simple plist name"; return 1; }
  [[ "$name" == *.plist ]] || name+=".plist"
  plist_path="$HOME/Library/LaunchAgents/$name"
  [[ -f "$plist_path" ]] || return 0
  plist_present=1
  plist_hash="$(sha256_file "$plist_path")" || { fail "could not hash agent plist"; return 1; }
  program="$(plist_get "$plist_path" Program || plist_get "$plist_path" 'ProgramArguments:0')" || { fail "agent plist has no Program or ProgramArguments[0]"; return 1; }
  target_exec="${program:A}"
  label="$(plist_get "$plist_path" Label)" || { fail "agent plist has no Label"; return 1; }
  for d in "gui/$(id -u)" "user/$(id -u)"; do
    job_state "$d" || return 1
    if [[ "$REPLY" == loaded ]]; then (( found += 1 )); original_domain="$d"; fi
  done
  (( found <= 1 )) || { fail "LaunchAgent loaded in multiple domains"; return 1; }
  initial_loaded=$found
  domain="$original_domain"
}
recheck_agent() {
  [[ "$PROWLARR_MANAGE_LAUNCH_AGENT" == true ]] || return 0
  if (( ! plist_present )); then [[ ! -e "$plist_path" ]] || { fail "LaunchAgent appeared during preparation"; return 1; }; return 0; fi
  [[ -f "$plist_path" && "$(sha256_file "$plist_path")" == "$plist_hash" ]] || { fail "LaunchAgent changed during preparation"; return 1; }
  local found=0 d nowdomain=""
  for d in "gui/$(id -u)" "user/$(id -u)"; do
    job_state "$d" || return 1
    if [[ "$REPLY" == loaded ]]; then (( found += 1 )); nowdomain="$d"; fi
  done
  (( found == initial_loaded )) && [[ "$nowdomain" == "$original_domain" ]] || { fail "LaunchAgent loaded state changed during preparation"; return 1; }
}

# Validate/download into staging before touching the live bundle or service.
if [[ -e "$target" || -L "$target" ]]; then
  validate_bundle "$target" || exit 1
  original_present=1
  original_identity="$(identity "$target")" || exit 1
fi
if (( download_mode )); then download_release || exit 1
else ditto "$target" "$stage" || { fail "could not stage target app"; exit 1; }
fi
validate_bundle "$stage" || exit 1
stage_exec="$REPLY"
target_exec="$target/Contents/MacOS/${stage_exec:t}"
agent_snapshot || exit 1
if (( plist_present )) && [[ "$target_exec" != "${target}/Contents/MacOS/${stage_exec:t}" ]]; then fail "LaunchAgent executable differs from bundle executable"; exit 1; fi
if (( ! download_mode )) && [[ -x "$target/Contents/MacOS/${stage_exec:t}" ]]; then
  live_tuple="$(parse_build_tuple "$target/Contents/MacOS/${stage_exec:t}" 2>/dev/null || true)"
  live_min="${live_tuple%%|*}"
  live_plist="$(plist_get "$target/Contents/Info.plist" LSMinimumSystemVersion || true)"
  arch_plist="$(plist_get "$target/Contents/Info.plist" 'LSMinimumSystemVersionByArchitecture:x86_64' || true)"
  if [[ "$live_min" == 11 || "$live_min" == 11.0 || "$live_min" == 11.0.0 ]] && [[ "$live_plist" == 11 || "$live_plist" == 11.0 || "$live_plist" == 11.0.0 ]] && [[ -z "$arch_plist" || "$arch_plist" == 11 || "$arch_plist" == 11.0 || "$arch_plist" == 11.0.0 ]] && codesign --verify --deep --strict "$target" >/dev/null 2>&1; then
    log "local app is already strictly valid; no changes made"; exit 0
  fi
fi
patch_native "$stage_exec" || exit 1
info="$stage/Contents/Info.plist"
if plist_get "$info" LSMinimumSystemVersion >/dev/null; then
  plutil -replace LSMinimumSystemVersion -string 11.0 "$info" || exit 1
else
  plutil -insert LSMinimumSystemVersion -string 11.0 "$info" || exit 1
fi
if plist_get "$info" 'LSMinimumSystemVersionByArchitecture:x86_64' >/dev/null; then
  plutil -replace LSMinimumSystemVersionByArchitecture.x86_64 -string 11.0 "$info" || exit 1
fi
codesign --force --deep --sign - "$stage" || { fail "candidate signing failed"; exit 1; }
codesign --verify --deep --strict "$stage" || { fail "candidate signature verification failed"; exit 1; }
installed_exec="$stage/Contents/MacOS/${stage_exec:t}"
check_macho "$installed_exec" || exit 1
recheck_agent || exit 1

if (( initial_loaded )); then
  restore_required=1
  if ! launchctl bootout "$domain/$label"; then fail "LaunchAgent unload failed"; exit 1; fi
  wait_unloaded || exit 1
fi
wait_users || exit 1
[[ ! -e "$backup" ]] || { fail "backup path already exists: $backup"; exit 1; }
if (( original_present )); then
  [[ -e "$target" && "$(identity "$target")" == "$original_identity" ]] || { fail "original bundle changed during preparation"; exit 1; }
  original_moved=1
  exclusive_rename "$target" "$backup" || { fail "could not move original app"; exit 1; }
  [[ "$(identity "$backup")" == "$original_identity" ]] || { fail "original bundle changed during rename"; exit 1; }
else
  [[ ! -e "$target" && ! -L "$target" ]] || { fail "target appeared during preparation"; exit 1; }
fi
candidate_identity="$(identity "$stage")" || { fail "could not identify candidate"; exit 1; }
candidate_installed=1
exclusive_rename "$stage" "$target" || { fail "could not install candidate app"; exit 1; }

codesign --verify --deep --strict "$target" || { fail "installed signature verification failed"; exit 1; }
installed_verified=1
if (( original_moved )); then
  [[ "$(identity "$backup" 2>/dev/null)" == "$original_identity" ]] || { fail "original identity changed before backup"; exit 1; }
  backup_temp="$(mktemp "${backup_zip:h}/.prowlarr-backup.XXXXXXXX")" || { fail "could not create backup temporary file"; exit 1; }
  ditto -c -k --sequesterRsrc --keepParent "$backup" "$backup_temp" || { fail "could not create backup ZIP"; exit 1; }
  unzip -tq "$backup_temp" >/dev/null || { fail "backup ZIP validation failed"; exit 1; }
  [[ "$(identity "$backup" 2>/dev/null)" == "$original_identity" ]] || { fail "original identity changed while creating backup"; exit 1; }
  backup_identity="$(identity "$backup_temp")" || exit 1
  atomic_replace "$backup_temp" "$backup_zip" || { fail "could not publish backup ZIP"; exit 1; }
  backup_temp=""
  [[ "$(identity "$backup_zip" 2>/dev/null)" == "$backup_identity" ]] || { fail "published backup ZIP identity changed"; preserve_txn=1; exit 1; }
  backup_published=1
fi
lsregister="$(command -v lsregister 2>/dev/null || print /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister)"
"$lsregister" -f "$target" || { fail "Launch Services registration failed"; exit 1; }
if (( initial_loaded )); then
  startup_possible=1
  restore_required=1
  launchctl bootstrap "$domain" "$plist_path" || { fail "LaunchAgent bootstrap failed; Prowlarr may have started. New app and backup retained; inspect service state before manual recovery."; exit 1; }
  restore_required=0
fi
log "installed and verified: $target"
(( original_moved )) && log "original bundle archived at: $backup_zip"
exit 0
