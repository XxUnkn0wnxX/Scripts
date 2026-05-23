#!/usr/bin/env zsh
# Quick launcher for Satisfactory Modeler
# This wrapper keeps the unpacked app files inside a local modeler/ subfolder.
# Default: launches DETACHED so Terminal can be closed immediately.
# --debug: runs in foreground with full logging to this terminal.
# --fupdate: force-download the latest satisfactory-modeler.zip and extract it first.

set -euo pipefail

# -----------------------------
# Config (override via env vars)
# -----------------------------
# MODEL_CPU_LIMIT:
#   0  -> auto-detect physical cores (default)
#   >0 -> force that many "visible" CPUs for the JVM and ForkJoinPool
: "${MODEL_CPU_LIMIT:=0}"

# Heap size (adjust to taste / your RAM)
: "${MODEL_HEAP_MIN:=4g}"
: "${MODEL_HEAP_MAX:=8g}"

# Java version to resolve via /usr/libexec/java_home
#   latest/auto/empty -> newest installed JDK on this Mac
#   23 / 26 / 17 etc. -> exact version via /usr/libexec/java_home -F -v
: "${MODEL_JAVA_VERSION:=latest}"

# Updater timeout in seconds per network request
: "${MODEL_UPDATE_TIMEOUT:=8}"

# Optional override for updater page URL (useful for testing)
: "${MODEL_UPDATE_PAGE_URL:=satisfactorymodeler.itch.io/satisfactorymodeler}"

# -----------------------------
# Locate script directory
# -----------------------------
SCRIPT_PATH=${0:A}
SCRIPT_DIR=${SCRIPT_PATH:h}
cd "${SCRIPT_DIR}"

APP_DIR="${SCRIPT_DIR}/modeler"
UPDATER_DIR="${APP_DIR}/updater"
STATE_FILE="${APP_DIR}/.SMU_conf"
UPDATE_ZIP_NAME="satisfactory-modeler.zip"

normalize_update_url() {
  local raw_url="$1"

  case "${raw_url}" in
    *://*)
      print -r -- "${raw_url}"
      ;;
    *)
      print -r -- "https://${raw_url}"
      ;;
  esac
}

normalize_etag() {
  local raw_etag="$1"
  raw_etag="${raw_etag#\"}"
  raw_etag="${raw_etag%\"}"
  print -r -- "${raw_etag}"
}

UPDATE_PAGE_URL="$(normalize_update_url "${MODEL_UPDATE_PAGE_URL}")"

mkdir -p "${APP_DIR}" "${UPDATER_DIR}"

# -----------------------------
# CLI args
# -----------------------------
DEBUG=false
FORCE_UPDATE=false
JAR_MISSING=false
JAR_RECOVERED_FROM_CACHE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --debug)
      DEBUG=true
      ;;
    --fupdate)
      FORCE_UPDATE=true
      ;;
    --help|-h)
      cat <<'EOF'
Satisfactory Modeler launcher

Usage:
  ./satisfactory-modeler.zsh [options]

Options:
  --debug    Run attached and keep logs in this terminal
  --fupdate  Force-download the latest satisfactory-modeler.zip and extract it
  --help     Show this help page
  -h         Show this help page

Updater:
  Normal launches check the itch.io page first.
  If the page update timestamp changed, the launcher probes the remote ETag.
  It only downloads the ZIP when needed, and only extracts it if the ZIP
  sha256 differs from the stored local state.

Environment overrides:
  MODEL_CPU_LIMIT  0 = auto-detect physical cores, >0 = force that CPU count
  MODEL_HEAP_MIN   JVM minimum heap size (default: 4g)
  MODEL_HEAP_MAX   JVM maximum heap size (default: 8g)
  MODEL_JAVA_VERSION   Java version for /usr/libexec/java_home (default: latest)
  MODEL_UPDATE_TIMEOUT  Updater request timeout in seconds (default: 8)
EOF
      exit 0
      ;;
    *)
      print -u2 -- "Error: Unknown argument: $1"
      exit 1
      ;;
  esac
  shift
done

STATE_PAGE_UPDATED=""
STATE_UPLOAD_ID=""
STATE_REMOTE_ETAG=""
STATE_REMOTE_SIZE=""
STATE_REMOTE_LAST_MODIFIED=""
STATE_ZIP_SHA256=""

load_update_state() {
  local parsed_state_file="${UPDATER_DIR}/state-load.$$"
  local state_invalid=false

  STATE_PAGE_UPDATED=""
  STATE_UPLOAD_ID=""
  STATE_REMOTE_ETAG=""
  STATE_REMOTE_SIZE=""
  STATE_REMOTE_LAST_MODIFIED=""
  STATE_ZIP_SHA256=""

  if [[ -f "${STATE_FILE}" ]]; then
    if ! zsh -n "${STATE_FILE}" >/dev/null 2>&1; then
      rm -f "${STATE_FILE}"
      print -u2 -- "Warning: Broken updater state file detected at ${STATE_FILE}."
      print -u2 -- "Warning: Deleted ${STATE_FILE}; updater will rebuild it from a fresh download."
      return 0
    fi

    if ! (
      set -e
      source "${STATE_FILE}"
      print -r -- "STATE_PAGE_UPDATED=${(qqq)${STATE_PAGE_UPDATED-}}"
      print -r -- "STATE_UPLOAD_ID=${(qqq)${STATE_UPLOAD_ID-}}"
      print -r -- "STATE_REMOTE_ETAG=${(qqq)${STATE_REMOTE_ETAG-}}"
      print -r -- "STATE_REMOTE_SIZE=${(qqq)${STATE_REMOTE_SIZE-}}"
      print -r -- "STATE_REMOTE_LAST_MODIFIED=${(qqq)${STATE_REMOTE_LAST_MODIFIED-}}"
      print -r -- "STATE_ZIP_SHA256=${(qqq)${STATE_ZIP_SHA256-}}"
    ) > "${parsed_state_file}" 2>/dev/null; then
      rm -f "${parsed_state_file}" "${STATE_FILE}"
      print -u2 -- "Warning: Broken updater state file detected at ${STATE_FILE}."
      print -u2 -- "Warning: Deleted ${STATE_FILE}; updater will rebuild it from a fresh download."
      return 0
    fi

    set +u
    source "${parsed_state_file}"
    set -u
    rm -f "${parsed_state_file}"

    STATE_REMOTE_ETAG="$(normalize_etag "${STATE_REMOTE_ETAG}")"

    [[ "${STATE_PAGE_UPDATED}" == *$'\n'* || "${STATE_PAGE_UPDATED}" == *$'\r'* ]] && state_invalid=true
    [[ "${STATE_UPLOAD_ID}" == *$'\n'* || "${STATE_UPLOAD_ID}" == *$'\r'* ]] && state_invalid=true
    [[ "${STATE_REMOTE_ETAG}" == *$'\n'* || "${STATE_REMOTE_ETAG}" == *$'\r'* ]] && state_invalid=true
    [[ "${STATE_REMOTE_SIZE}" == *$'\n'* || "${STATE_REMOTE_SIZE}" == *$'\r'* ]] && state_invalid=true
    [[ "${STATE_REMOTE_LAST_MODIFIED}" == *$'\n'* || "${STATE_REMOTE_LAST_MODIFIED}" == *$'\r'* ]] && state_invalid=true
    [[ "${STATE_ZIP_SHA256}" == *$'\n'* || "${STATE_ZIP_SHA256}" == *$'\r'* ]] && state_invalid=true
    [[ -n "${STATE_UPLOAD_ID}" && "${STATE_UPLOAD_ID}" != <-> ]] && state_invalid=true
    [[ -n "${STATE_REMOTE_SIZE}" && "${STATE_REMOTE_SIZE}" != <-> ]] && state_invalid=true

    if [[ "${state_invalid}" == true ]]; then
      rm -f "${STATE_FILE}"
      STATE_PAGE_UPDATED=""
      STATE_UPLOAD_ID=""
      STATE_REMOTE_ETAG=""
      STATE_REMOTE_SIZE=""
      STATE_REMOTE_LAST_MODIFIED=""
      STATE_ZIP_SHA256=""
      print -u2 -- "Warning: Invalid updater state values detected in ${STATE_FILE}."
      print -u2 -- "Warning: Deleted ${STATE_FILE}; updater will rebuild it from a fresh download."
      return 0
    fi
  fi
}

warn_skip_update() {
  local reason="$1"
  print -u2 -- "Warning: ${reason}"
  print -u2 -- "Warning: Skipping updater for this launch."
}

write_update_state() {
  local page_updated="$1"
  local upload_id="$2"
  local remote_etag="$3"
  local remote_size="$4"
  local remote_last_modified="$5"
  local zip_sha256="$6"
  local state_tmp="${STATE_FILE}.tmp"

  cat > "${state_tmp}" <<EOF
STATE_PAGE_UPDATED=${(qqq)page_updated}
STATE_UPLOAD_ID=${(qqq)upload_id}
STATE_REMOTE_ETAG=${(qqq)remote_etag}
STATE_REMOTE_SIZE=${(qqq)remote_size}
STATE_REMOTE_LAST_MODIFIED=${(qqq)remote_last_modified}
STATE_ZIP_SHA256=${(qqq)zip_sha256}
EOF

  mv "${state_tmp}" "${STATE_FILE}"
}

extract_page_updated() {
  local page_html="$1"
  perl -0ne '
    if (/<div class="update_timestamp">Updated\s*<abbr title="([^"]+)"/s) {
      print $1;
      exit;
    }
    if (/<tr><td>Updated<\/td><td><abbr title="([^"]+)"/s) {
      print $1;
      exit;
    }
  ' "${page_html}"
}

extract_csrf_token() {
  local page_html="$1"
  perl -0ne '
    if (/meta name="csrf_token" value="([^"]+)"/) {
      print $1;
      exit;
    }
  ' "${page_html}"
}

extract_zip_upload_id() {
  local page_html="$1"
  perl -0ne '
    while (/<div class="upload">(.*?)<\/div><\/div><\/div>/sg) {
      my $block = $1;
      next unless $block =~ /title="satisfactory-modeler\.zip"/;
      if ($block =~ /data-upload_id="(\d+)"/) {
        print $1;
        exit;
      }
    }
  ' "${page_html}"
}

extract_signed_url() {
  local response_json="$1"
  perl -ne '
    if (/"url":"([^"]+)"/) {
      my $url = $1;
      $url =~ s#\\/#/#g;
      print $url;
      exit;
    }
  ' "${response_json}"
}

extract_header_value() {
  local header_file="$1"
  local header_name="$2"
  awk -F': ' -v key="${header_name}" '
    tolower($1) == tolower(key) {
      gsub(/\r/, "", $2)
      print $2
      exit
    }
  ' "${header_file}"
}

extract_remote_size() {
  local header_file="$1"
  perl -ne '
    if (/^Content-Range:\s*bytes\s+\d+-\d+\/(\d+)/i) {
      print $1;
      exit;
    }
  ' "${header_file}"
}

extract_zip_into_root() {
  local zip_file="$1"
  local extract_dir="${UPDATER_DIR}/extract"
  local extract_tool="ditto"
  local seven_zip=""

  rm -rf "${extract_dir}"
  mkdir -p "${extract_dir}"

  if seven_zip="$(command -v 7z 2>/dev/null)" && [[ -n "${seven_zip}" ]]; then
    extract_tool="7z"
    if ! "${seven_zip}" x -y -bd "-o${extract_dir}" "${zip_file}" >/dev/null; then
      return 1
    fi
  else
    if ! ditto -x -k "${zip_file}" "${extract_dir}"; then
      return 1
    fi
  fi

  echo "  Extract tool : ${extract_tool}"

  mkdir -p "${APP_DIR}"

  if ! ditto "${extract_dir}" "${APP_DIR}"; then
    return 1
  fi

  return 0
}

restore_missing_jar_from_cache() {
  local zip_file="${UPDATER_DIR}/${UPDATE_ZIP_NAME}"

  if [[ -f "${APP_DIR}/modeler.jar" ]]; then
    return 0
  fi

  JAR_MISSING=true
  print -u2 -- "Warning: modeler.jar is missing from ${APP_DIR}."

  if [[ -f "${zip_file}" ]]; then
    print -u2 -- "Warning: Found cached ${UPDATE_ZIP_NAME} in ${UPDATER_DIR}; extracting it first."
    if extract_zip_into_root "${zip_file}" && [[ -f "${APP_DIR}/modeler.jar" ]]; then
      JAR_RECOVERED_FROM_CACHE=true
      print -u2 -- "Warning: Restored modeler.jar from cached ${UPDATE_ZIP_NAME}."
      return 0
    fi

    print -u2 -- "Warning: Cached ${UPDATE_ZIP_NAME} did not restore modeler.jar."
  else
    print -u2 -- "Warning: No cached ${UPDATE_ZIP_NAME} found in ${UPDATER_DIR}."
  fi

  FORCE_UPDATE=true
  print -u2 -- "Warning: Forcing a fresh updater download before launch."
  return 0
}

run_self_update() {
  local force_update="$1"
  local cookie_jar="${UPDATER_DIR}/cookies.txt"
  local page_html="${UPDATER_DIR}/page.html"
  local file_json="${UPDATER_DIR}/file-response.json"
  local probe_headers="${UPDATER_DIR}/probe-headers.txt"
  local zip_file="${UPDATER_DIR}/${UPDATE_ZIP_NAME}"
  local csrf_token=""
  local page_updated=""
  local upload_id=""
  local signed_url=""
  local remote_etag=""
  local remote_size=""
  local remote_last_modified=""
  local zip_sha256=""

  load_update_state

  rm -rf "${UPDATER_DIR}/extract"
  rm -f "${cookie_jar}" "${page_html}" "${file_json}" "${probe_headers}"

  echo "Checking for Satisfactory Modeler updates..."

  if ! curl -fsSL --compressed \
    --connect-timeout "${MODEL_UPDATE_TIMEOUT}" \
    --max-time "${MODEL_UPDATE_TIMEOUT}" \
    -A 'Mozilla/5.0' \
    -c "${cookie_jar}" \
    -b "${cookie_jar}" \
    "${UPDATE_PAGE_URL}" \
    -o "${page_html}"; then
    warn_skip_update "Update check failed or timed out after ${MODEL_UPDATE_TIMEOUT}s while fetching ${UPDATE_PAGE_URL}."
    return 0
  fi

  page_updated="$(extract_page_updated "${page_html}")"
  csrf_token="$(extract_csrf_token "${page_html}")"
  upload_id="$(extract_zip_upload_id "${page_html}")"

  if [[ -z "${page_updated}" || -z "${csrf_token}" || -z "${upload_id}" ]]; then
    print -u2 -- "Warning: Could not parse the updater metadata from ${UPDATE_PAGE_URL}."
    print -u2 -- "Warning: The itch.io page format may have changed. Update/fix satisfactory-modeler.zsh."
    print -u2 -- "Warning: Skipping updater for this launch."
    return 0
  fi

  echo "  Page updated : ${page_updated}"
  echo "  Upload ID    : ${upload_id}"

  if [[ "${force_update}" != true && -n "${STATE_PAGE_UPDATED}" && "${page_updated}" == "${STATE_PAGE_UPDATED}" ]]; then
    echo "  Update check : page timestamp unchanged; skipping download."
    return 0
  fi

  if ! curl -fsSL \
    --connect-timeout "${MODEL_UPDATE_TIMEOUT}" \
    --max-time "${MODEL_UPDATE_TIMEOUT}" \
    -A 'Mozilla/5.0' \
    -e "${UPDATE_PAGE_URL}" \
    -H 'X-Requested-With: XMLHttpRequest' \
    -H 'Accept: application/json, text/javascript, */*; q=0.01' \
    -c "${cookie_jar}" \
    -b "${cookie_jar}" \
    --data-urlencode "csrf_token=${csrf_token}" \
    "${UPDATE_PAGE_URL}/file/${upload_id}?source=view_game&as_props=1" \
    -o "${file_json}"; then
    warn_skip_update "Update metadata fetch failed or timed out after ${MODEL_UPDATE_TIMEOUT}s."
    return 0
  fi

  signed_url="$(extract_signed_url "${file_json}")"
  if [[ -z "${signed_url}" ]]; then
    warn_skip_update "Could not resolve the signed download URL from the itch.io response."
    return 0
  fi

  if ! curl -fsSL \
    --connect-timeout "${MODEL_UPDATE_TIMEOUT}" \
    --max-time "${MODEL_UPDATE_TIMEOUT}" \
    -r 0-0 \
    -D "${probe_headers}" \
    "${signed_url}" \
    -o /dev/null; then
    warn_skip_update "Remote ZIP probe failed or timed out after ${MODEL_UPDATE_TIMEOUT}s."
    return 0
  fi

  remote_etag="$(extract_header_value "${probe_headers}" "ETag")"
  remote_etag="$(normalize_etag "${remote_etag}")"
  remote_size="$(extract_remote_size "${probe_headers}")"
  remote_last_modified="$(extract_header_value "${probe_headers}" "Last-Modified")"

  echo "  Remote ETag  : ${remote_etag:-unknown}"
  echo "  Remote size  : ${remote_size:-unknown}"
  echo "  Last modified: ${remote_last_modified:-unknown}"

  if [[ "${force_update}" != true && -n "${STATE_REMOTE_ETAG}" && "${remote_etag}" == "${STATE_REMOTE_ETAG}" ]]; then
    echo "  Update check : ETag unchanged; skipping full download."
    write_update_state \
      "${page_updated}" \
      "${upload_id}" \
      "${remote_etag}" \
      "${remote_size}" \
      "${remote_last_modified}" \
      "${STATE_ZIP_SHA256}"
    return 0
  fi

  echo "  Downloading  : ${UPDATE_ZIP_NAME}"
  if ! curl -fsSL \
    --connect-timeout "${MODEL_UPDATE_TIMEOUT}" \
    --max-time "${MODEL_UPDATE_TIMEOUT}" \
    "${signed_url}" \
    -o "${zip_file}"; then
    rm -f "${zip_file}"
    warn_skip_update "ZIP download failed or timed out after ${MODEL_UPDATE_TIMEOUT}s."
    return 0
  fi

  zip_sha256="$(shasum -a 256 "${zip_file}" | awk '{print $1}')"
  if [[ -z "${zip_sha256}" ]]; then
    rm -f "${zip_file}"
    warn_skip_update "Failed to compute the downloaded ZIP sha256."
    return 0
  fi

  echo "  ZIP sha256   : ${zip_sha256}"

  if [[ "${force_update}" != true && -n "${STATE_ZIP_SHA256}" && "${zip_sha256}" == "${STATE_ZIP_SHA256}" ]]; then
    echo "  Update check : ZIP hash unchanged; skipping extraction."
    write_update_state \
      "${page_updated}" \
      "${upload_id}" \
      "${remote_etag}" \
      "${remote_size}" \
      "${remote_last_modified}" \
      "${zip_sha256}"
    return 0
  fi

  echo "  Extracting   : ${UPDATE_ZIP_NAME}"
  if ! extract_zip_into_root "${zip_file}"; then
    warn_skip_update "Failed to extract ${UPDATE_ZIP_NAME} into ${APP_DIR}."
    return 0
  fi

  write_update_state \
    "${page_updated}" \
    "${upload_id}" \
    "${remote_etag}" \
    "${remote_size}" \
    "${remote_last_modified}" \
    "${zip_sha256}"

  echo "  Update check : local files refreshed."
  return 0
}

restore_missing_jar_from_cache
run_self_update "${FORCE_UPDATE}"

# -----------------------------
# Locate jar
# -----------------------------
JAR="${APP_DIR}/modeler.jar"
if [[ ! -f "${JAR}" ]]; then
  print -u2 -- "Error: modeler.jar not found in ${APP_DIR}"
  exit 1
fi

# We'll use this for PID tracking in both modes
JAR_PATH="${JAR:A}"
PID_FILE="${JAR_PATH:h}/modeler.pid"
cd "${APP_DIR}"

# -----------------------------
# Resolve Java explicitly
# -----------------------------
if [[ -z "${JAVA_HOME:-}" ]]; then
  case "${MODEL_JAVA_VERSION}" in
    ""|auto|latest)
      JAVA_HOME="$(/usr/libexec/java_home 2>/dev/null || true)"
      ;;
    *)
      JAVA_HOME="$(/usr/libexec/java_home -F -v "${MODEL_JAVA_VERSION}" 2>/dev/null || true)"
      ;;
  esac
fi

if [[ -z "${JAVA_HOME}" ]]; then
  case "${MODEL_JAVA_VERSION}" in
    ""|auto|latest)
      print -u2 -- "Error: Could not find any Java JDK via /usr/libexec/java_home"
      ;;
    *)
      print -u2 -- "Error: Could not find Java ${MODEL_JAVA_VERSION} via /usr/libexec/java_home -F -v ${MODEL_JAVA_VERSION}"
      ;;
  esac
  exit 1
fi

JAVA_EXE="${JAVA_HOME}/bin/java"
if [[ ! -x "$JAVA_EXE" ]]; then
  print -u2 -- "Error: ${JAVA_EXE} is not executable"
  exit 1
fi

# -----------------------------
# Build CPU-related JVM flags
# -----------------------------
typeset -a CPU_ARGS
CPU_ARGS=()
CPU_DESC="none (JVM default)"

if [[ "$MODEL_CPU_LIMIT" != "0" ]]; then
  CPU_ARGS+=(
    "-XX:ActiveProcessorCount=${MODEL_CPU_LIMIT}"
    "-Djava.util.concurrent.ForkJoinPool.common.parallelism=${MODEL_CPU_LIMIT}"
  )
  CPU_DESC="forced via MODEL_CPU_LIMIT=${MODEL_CPU_LIMIT}"
else
  # Auto-detect physical cores (best for heavy CPU-bound work)
  if command -v sysctl >/dev/null 2>&1; then
    phys_cores="$(sysctl -n hw.physicalcpu 2>/dev/null || echo "")"
    if [[ -n "$phys_cores" && "$phys_cores" -gt 0 ]]; then
      CPU_ARGS+=(
        "-XX:ActiveProcessorCount=${phys_cores}"
        "-Djava.util.concurrent.ForkJoinPool.common.parallelism=${phys_cores}"
      )
      CPU_DESC="auto (hw.physicalcpu=${phys_cores})"
    fi
  fi
fi

# -----------------------------
# Build the Java command
# -----------------------------
typeset -a JAVA_CMD
JAVA_CMD=(
  "$JAVA_EXE"
  "-Xms${MODEL_HEAP_MIN}"
  "-Xmx${MODEL_HEAP_MAX}"
  "${CPU_ARGS[@]}"
  -Dapple.awt.application.name="Satisfactory Modeler"
  -Xdock:name="Satisfactory Modeler"
  -jar "${JAR:t}"
)

# -----------------------------
# Debug logging (pre-launch)
# -----------------------------
echo "Satisfactory Modeler launcher"
echo "  Mode        : $([[ "$DEBUG" == true ]] && echo "DEBUG (attached, logging)" || echo "DETACHED (no logs)")"
echo "  Script dir  : ${SCRIPT_DIR}"
echo "  App dir     : ${APP_DIR}"
echo "  JAR         : ${JAR}"
echo "  JAVA_HOME   : ${JAVA_HOME}"
echo "  Java ver    : ${MODEL_JAVA_VERSION}"
echo "  Heap        : -Xms${MODEL_HEAP_MIN} -Xmx${MODEL_HEAP_MAX}"
echo "  CPU config  : ${CPU_DESC}"
echo "  PID file    : ${PID_FILE}"
echo "  Force update: $([[ "${FORCE_UPDATE}" == true ]] && echo "yes" || echo "no")"
echo "  JAR missing : $([[ "${JAR_MISSING}" == true ]] && echo "yes" || echo "no")"
echo "  Cache restore: $([[ "${JAR_RECOVERED_FROM_CACHE}" == true ]] && echo "yes" || echo "no")"
echo "  State file  : ${STATE_FILE}"

if [[ "${#CPU_ARGS[@]}" -gt 0 ]]; then
  echo "  CPU args    :"
  for a in "${CPU_ARGS[@]}"; do
    echo "    ${a}"
  done
fi

if [[ "$DEBUG" == true ]]; then
  echo "  Launch cmd  :"
  printf '    %q ' "${JAVA_CMD[@]}"
  echo
fi

# -----------------------------
# Launch
# -----------------------------
if [[ "$DEBUG" == true ]]; then
  echo
  echo "Starting Satisfactory Modeler in DEBUG mode (attached)..."
  echo "---------------------------------------------------------"

  # Run in background so we can capture PID, but wait on it so logs stay here
  "${JAVA_CMD[@]}" &
  pid=$!

  echo "$pid" > "$PID_FILE"
  echo "PID (debug)  : $pid"
  echo "PID file     : $PID_FILE"
  echo "---------------------------------------------------------"

  # Temporarily relax -e so we can report the exit code even on error
  set +e
  wait "$pid"
  exit_code=$?
  set -e

  echo "---------------------------------------------------------"
  echo "Satisfactory Modeler exited with code ${exit_code}"
  exit "${exit_code}"
else
  nohup "${JAVA_CMD[@]}" >/dev/null 2>&1 &
  pid=$!
  (disown "$pid" 2>/dev/null || true)

  echo "$pid" > "$PID_FILE"

  echo
  echo "Launched Satisfactory Modeler (PID $pid) in detached mode."
  echo "  stdout/stderr : /dev/null"
  echo "  PID file      : $PID_FILE"
  exit 0
fi
