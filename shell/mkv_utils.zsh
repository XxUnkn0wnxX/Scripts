#!/usr/bin/env zsh

# Required third-party tools:
# - mkvmerge, mkvinfo, mkvextract, mkvpropedit: for remuxing, inspecting, extracting, and editing tracks and metadata in Matroska files
# - jq: for processing JSON output from mkvmerge (-J)
# - fzf: for interactive file and track selection via fuzzy finding
# - python3: for inline Python scripting support
# - pymkv2, pymkv Python library: provides the type_files mapping for codec→extension resolution (install via python3 -m pip install pymkv2 pymkv)
#
# On macOS, install dependencies via Homebrew:
#   brew install mkvtoolnix jq fzf python3
#   python3 -m pip install pymkv pymkv2
#
# Ensure that python3 and pip are in your PATH.

SCRIPT_NAME="${0:t}"
SCRIPT_ROOT=${0:A:h}
looks_like_repo_root() {
  local candidate="$1"
  [[ -d "$candidate/.git" || -f "$candidate/.git" ]] && return 0
  [[ -f "$candidate/requirements.txt" && -d "$candidate/docs" ]] && return 0
  return 1
}

resolve_repo_root() {
  local start_dir="$1"
  local max_depth="${2:-1}"
  local candidate="${start_dir:A}"
  local depth=0
  local fallback="$candidate"

  while (( depth <= max_depth )); do
    if (( depth == 1 )); then
      fallback="$candidate"
    fi
    if looks_like_repo_root "$candidate"; then
      print -r -- "$candidate"
      return 0
    fi
    [[ "$candidate" == / ]] && break
    candidate="${candidate:h}"
    (( depth++ ))
  done

  print -r -- "$fallback"
}

REPO_ROOT="$(resolve_repo_root "$SCRIPT_ROOT" 1)"
VENV_PATH="$REPO_ROOT/.venv"
PYTHON_BIN=""
typeset -gi _PY_READY=0

_verify_python_runtime() {
  local py_bin="$1"
  "$py_bin" - <<'PYCODE'
import sys
import importlib

try:
    import pymkv  # primary module used by the script
except ModuleNotFoundError as exc:
    sys.exit(f"pymkv unavailable: {exc}")

try:
    import importlib.metadata as metadata
except ImportError:  # pragma: no cover
    import importlib_metadata as metadata  # type: ignore

try:
    metadata.version("pymkv2")
except metadata.PackageNotFoundError as exc:
    sys.exit("pymkv2 distribution is not installed in this environment.")
PYCODE
}

ensure_venv_python() {
  if [[ $_PY_READY -eq 1 ]]; then
    return 0
  fi

  if [[ -d "$VENV_PATH" ]]; then
    local activate_file="$VENV_PATH/bin/activate"
    if [[ ! -f "$activate_file" ]]; then
      echo "Virtualenv detected at $VENV_PATH but activate script missing. Recreate the venv." >&2
      exit 1
    fi

    if [[ "$VIRTUAL_ENV" != "$VENV_PATH" ]]; then
      if ! source "$activate_file"; then
        echo "Failed to activate virtualenv at $VENV_PATH." >&2
        exit 1
      fi
    fi

    PYTHON_BIN="$VENV_PATH/bin/python3"
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Virtualenv python missing at $PYTHON_BIN." >&2
      exit 1
    fi

    if ! _verify_python_runtime "$PYTHON_BIN"; then
      echo "Required Python packages (pymkv, pymkv2) are not installed in the virtualenv." >&2
      echo "Activate the venv and run: pip install -r requirements.txt" >&2
      exit 1
    fi

    _PY_READY=1
    return 0
  fi

  local global_python
  if ! global_python=$(command -v python3 2>/dev/null); then
    echo "python3 is not available and no .venv exists. Create .venv (python3 -m venv .venv) and install requirements." >&2
    exit 1
  fi

  if ! _verify_python_runtime "$global_python"; then
    echo "Global python at $global_python lacks pymkv/pymkv2. Create .venv and run pip install -r requirements.txt." >&2
    exit 1
  fi

  PYTHON_BIN="$global_python"
  _PY_READY=1
}

# Extension overrides for Plex / VLC compatibility
typeset -A ext_override=(
  # Video elementary streams
  ["V_MPEG4/ISO/AVC"]="h264"     # raw H.264 → .h264
  ["V_MPEGH/ISO/HEVC"]="h265"    # raw HEVC/H.265 → .h265

  # Audio elementary streams
  ["A_AAC"]="aac"                # AAC audio → .aac
  ["A_AC3"]="ac3"                # AC-3 (Dolby Digital) → .ac3
  ["A_DTS"]="dts"                # DTS audio → .dts
  ["A_OPUS"]="opus"              # Opus → .opus
  ["A_MPEG/L3"]="mp3"            # MPEG-1/2 Layer III → .mp3

  # Subtitle sidecars
  ["S_TEXT/SRT"]="srt"           # SubRip → .srt
  ["S_TEXT/ASS"]="ass"           # SubStation Alpha → .ass
  ["S_HDMV/PGS"]="pgs"           # PGS subtitles → .pgs
)

# Multi-file target selection mode for menu choices (Y/N)
MULTI_FILE_SELECTION=""

function count_attachments() {
  local file="$1"
  mkvmerge --identify "$file" | grep -c "Attachment ID"
}

format_duration() {
  local total_seconds="$1"
  printf "%02d:%02d:%02d" \
    $((total_seconds / 3600)) \
    $(((total_seconds % 3600) / 60)) \
    $((total_seconds % 60))
}

reset_propedit_summary() {
  propedit_summary_started=0
  propedit_files_count=${#targets[@]}
  propedit_failed_files=()
  typeset -gA propedit_failed_track_ids
  propedit_failed_track_ids=()
}

start_propedit_summary() {
  if [[ $propedit_summary_started -eq 0 ]]; then
    propedit_summary_started=1
    if [[ $MULTI_FILE_SELECTION == "Y" && $propedit_files_count -gt 1 ]]; then
      echo "Total Files To Edit: $propedit_files_count"
    fi
  fi
}

record_propedit_failure() {
  local failed_file="$1"
  local track_id="${2:-}"
  local existing_file
  local existing_id
  local existing_ids

  for existing_file in "${propedit_failed_files[@]}"; do
    [[ "$existing_file" == "$failed_file" ]] && break
  done
  if [[ "$existing_file" != "$failed_file" ]]; then
    propedit_failed_files+=("$failed_file")
  fi

  [[ -z "$track_id" ]] && return
  existing_ids="${propedit_failed_track_ids[$failed_file]:-}"
  for existing_id in ${(s:,:)existing_ids}; do
    [[ "$existing_id" == "$track_id" ]] && return
  done
  propedit_failed_track_ids[$failed_file]="${existing_ids:+$existing_ids,}$track_id"
}

finish_propedit_summary() {
  if [[ $MULTI_FILE_SELECTION == "Y" && $propedit_files_count -gt 1 ]]; then
    local successful_files=$((propedit_files_count - ${#propedit_failed_files[@]}))
    local failed_file
    local track_id

    echo "Total Files Edited: $successful_files"
    if [[ ${#propedit_failed_files[@]} -gt 0 ]]; then
      printf "Failed Files: %02d\n" ${#propedit_failed_files[@]}
      for failed_file in "${propedit_failed_files[@]}"; do
        echo "  ${failed_file:t}"
        for track_id in ${(s:,:)${propedit_failed_track_ids[$failed_file]:-}}; do
          [[ -n "$track_id" ]] && echo "    Track ID: $track_id"
        done
      done
    fi
  fi
}

prompt_yes_no() {
  local prompt_text="$1"
  local default_choice="$2"
  local response=""

  while true; do
    printf "%s" "$prompt_text" >&2
    read response
    if [[ -z "$response" && -n "$default_choice" ]]; then
      response="$default_choice"
    fi

    case "${response:u}" in
      Y) print -r -- "Y"; return 0 ;;
      N) print -r -- "N"; return 0 ;;
      *) echo "Invalid choice. Please enter Y or N." >&2 ;;
    esac
  done
}

normalize_track_id_input() {
  local track_input="$1"
  track_input=$(printf '%s' "$track_input" | tr -d '[:space:]')
  printf '%s' "$track_input"
}

validate_track_id_list() {
  local track_input="$1"
  if ! printf '%s' "$track_input" | grep -Eq '^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$'; then
    return 1
  fi

  local -a track_parts
  IFS=',' read -rA track_parts <<< "$track_input"

  local part=""
  for part in "${track_parts[@]}"; do
    if [[ "$part" == *-* ]]; then
      local start=${part%-*}
      local end=${part#*-}
      if (( start > end )); then
        return 1
      fi
    fi
  done

  return 0
}

prompt_for_track_ids() {
  local prompt_text="$1"
  local track_ids=""

  while true; do
    printf "%s" "$prompt_text" >&2
    read track_ids
    track_ids=$(normalize_track_id_input "$track_ids")
    if [[ -z "$track_ids" ]]; then
      echo "Track ID(s) cannot be empty. Please enter at least one Track ID." >&2
      continue
    fi
    if validate_track_id_list "$track_ids"; then
      print -r -- "$track_ids"
      return 0
    fi
    echo "Invalid Track ID syntax. Use values like 0,1 or 1-2." >&2
  done
}

normalize_track_order() {
  local track_order="$1"
  track_order=$(printf '%s' "$track_order" | tr -d '[:space:]')
  printf '%s' "$track_order"
}

validate_track_order() {
  local track_order="$1"
  printf '%s' "$track_order" | grep -Eq '^[0-9]+:[0-9]+(,[0-9]+:[0-9]+)*$'
}

prompt_for_track_order() {
  local prompt_text="$1"
  local track_order=""

  while true; do
    printf "%s" "$prompt_text" >&2
    read track_order
    track_order=$(normalize_track_order "$track_order")
    if [[ -z "$track_order" ]]; then
      echo "Track order cannot be empty. Please enter at least one mapping." >&2
      continue
    fi
    if validate_track_order "$track_order"; then
      print -r -- "$track_order"
      return 0
    fi
    echo "Invalid track order syntax. Use values like 0:0,0:1,0:2." >&2
  done
}
 
# Function to display track information safely, projecting only the fields we need
display_track_info() {
  local source_file="$1"
  local mkv_json="${2-}"

  echo "-----------------------  mkvmerge JSON track listing -----------------------"
  if (( $# < 2 )); then
    if ! mkv_json="$(mkvmerge -J "$source_file" < /dev/null)"; then
      return 1
    fi
  fi

  printf '%s\n' "$mkv_json" | jq -r '
        .tracks[]
        | {
            id:    .id,
            type:  .type,
            codec: .properties.codec_id,
            name:  (.properties.track_name // ""),
            lang:  (.properties.language      // .properties.language_ietf // "")
          }
        | "Track ID \(.id): \(.type) (\(.codec))"
          + (if .name != "" then " [\(.name)]" else "" end)
          + (if .lang != "" then " [\(.lang)]" else "" end)
      '
}

collect_tracks_for_remux() {
  local source_file="$1"
  local mkv_json="${2-}"
  local track_rows

  if (( $# < 2 )); then
    if ! mkv_json="$(mkvmerge -J "$source_file" < /dev/null)"; then
      return 1
    fi
  fi

  if ! track_rows="$(printf '%s\n' "$mkv_json" \
    | jq -er '.tracks as $tracks
        | if ($tracks | type) != "array" then error("missing or invalid tracks array")
          elif ($tracks | length) == 0 then error("empty tracks array")
          elif any($tracks[]; .type != "video" and .type != "audio" and .type != "subtitles") then error("unsupported track type")
          elif any($tracks[]; (.id | type) != "number") then error("non-numeric track ID")
          elif any($tracks[]; .id < 0 or .id != (.id | floor)) then error("invalid track ID")
          elif (($tracks | map(.id) | unique | length) != ($tracks | length)) then error("duplicate track ID")
          else $tracks[]
          end
        | [.type, .id] | @tsv')"; then
    return 1
  fi

  print -r -- "$track_rows"
}

# Pure planning state shared by the rework helpers. These values describe the
# original Matroska track IDs and listing positions; they never address UIDs.
typeset -ga MKVUTIL_INPUT_IDS=()
typeset -ga MKVUTIL_RETAINED_IDS=()
typeset -gA MKVUTIL_TRACK_TYPES=()
typeset -gA MKVUTIL_PROPEDIT_SELECTORS=()
typeset -g MKVUTIL_TRACK_ORDER=""
typeset -g MKVUTIL_OUTPUT_EXTENSION=""

_mkvutil_canonical_id() {
  local value="${1//[[:space:]]/}"
  [[ "$value" == <-> ]] || return 1
  while [[ ${#value} -gt 1 && "$value" == 0* ]]; do
    value="${value#0}"
  done
  REPLY="$value"
}

_mkvutil_compare_ids() {
  local left="$1" right="$2"
  if (( ${#left} < ${#right} )); then
    REPLY=-1
  elif (( ${#left} > ${#right} )); then
    REPLY=1
  elif [[ "$left" == "$right" ]]; then
    REPLY=0
  elif [[ "$left" < "$right" ]]; then
    REPLY=-1
  else
    REPLY=1
  fi
}

_mkvutil_decimal_successor() {
  local value="$1" digit="" next_digit="" result="" carry=1 i=0
  for (( i = ${#value}; i >= 1; i-- )); do
    digit="${value[$i]}"
    if (( carry )); then
      case "$digit" in
        9) next_digit=0 ;;
        *) next_digit=$(( digit + 1 )); carry=0 ;;
      esac
    else
      next_digit="$digit"
    fi
    result="$next_digit$result"
  done
  (( carry )) && result="1$result"
  REPLY="$result"
}

# Expand menu selections against an explicit ID domain. The range walk is
# bounded by that domain, even when the requested endpoints are enormous.
mkvutil_expand_ids() {
  local selection="${1-}" allowed_csv="${2-}" token="" start="" end=""
  local candidate="" key="" output="" successor=""
  local i=0 j=0
  local -a allowed_ids=() tokens=() range_ids=() selected_ids=()
  local -A allowed_set=() selected_set=()

  for token in "${(@s:,:)allowed_csv}"; do
    token="${token//[[:space:]]/}"
    [[ -n "$token" ]] || return 1
    _mkvutil_canonical_id "$token" || return 1
    candidate="$REPLY"
    [[ -z "${allowed_set[$candidate]-}" ]] || return 1
    allowed_set[$candidate]=1
    allowed_ids+=("$candidate")
  done
  (( ${#allowed_ids} > 0 )) || return 1

  selection="${selection//[[:space:]]/}"
  [[ -n "$selection" ]] || return 1
  tokens=("${(@s:,:)selection}")
  for token in "${tokens[@]}"; do
    [[ -n "$token" ]] || return 1
    if [[ "$token" == *-* ]]; then
      [[ "$token" != -* && "$token" != *- && "${token#*-}" != *-* ]] || return 1
      start="${token%%-*}"
      end="${token#*-}"
      _mkvutil_canonical_id "$start" || return 1
      start="$REPLY"
      _mkvutil_canonical_id "$end" || return 1
      end="$REPLY"
      [[ -n "${allowed_set[$start]-}" && -n "${allowed_set[$end]-}" ]] || return 1
      _mkvutil_compare_ids "$start" "$end"
      (( REPLY <= 0 )) || return 1

      range_ids=()
      for candidate in "${allowed_ids[@]}"; do
        _mkvutil_compare_ids "$candidate" "$start"
        (( REPLY >= 0 )) || continue
        _mkvutil_compare_ids "$candidate" "$end"
        (( REPLY <= 0 )) && range_ids+=("$candidate")
      done
      (( ${#range_ids} > 0 )) || return 1

      # A range means ascending numeric selection order, independent of the
      # ordering of the allowed-domain CSV.
      for (( i = 2; i <= ${#range_ids}; i++ )); do
        key="${range_ids[$i]}"
        j=$(( i - 1 ))
        while (( j >= 1 )); do
          _mkvutil_compare_ids "${range_ids[$j]}" "$key"
          (( REPLY <= 0 )) && break
          range_ids[$(( j + 1 ))]="${range_ids[$j]}"
          (( j-- ))
        done
        range_ids[$(( j + 1 ))]="$key"
      done

      for (( i = 2; i <= ${#range_ids}; i++ )); do
        _mkvutil_decimal_successor "${range_ids[$(( i - 1 ))]}"
        successor="$REPLY"
        [[ "$successor" == "${range_ids[$i]}" ]] || return 1
      done

      for candidate in "${range_ids[@]}"; do
        if [[ -z "${selected_set[$candidate]-}" ]]; then
          selected_set[$candidate]=1
          selected_ids+=("$candidate")
        fi
      done
    else
      _mkvutil_canonical_id "$token" || return 1
      candidate="$REPLY"
      [[ -n "${allowed_set[$candidate]-}" ]] || return 1
      if [[ -z "${selected_set[$candidate]-}" ]]; then
        selected_set[$candidate]=1
        selected_ids+=("$candidate")
      fi
    fi
  done

  (( ${#selected_ids} > 0 )) || return 1
  output="${(j:,:)selected_ids}"
  print -r -- "$output"
}

_mkvutil_plan_layout_build() {
  local rows="${1-}" removed_input="${2-}" order_input="${3-}" input_extension="${4-}"
  local row="" track_type="" raw_id="" track_id="" removed_ids="" order=""
  local order_item="" order_id="" extension="" selector="" output_order=""
  local position=0 retained_count=0 has_video=0 has_audio=0 has_subtitles=0
  local -a ordered_ids=() final_ids=()
  local -A input_set=() removed_set=() order_set=()

  MKVUTIL_INPUT_IDS=()
  MKVUTIL_RETAINED_IDS=()
  MKVUTIL_TRACK_TYPES=()
  MKVUTIL_PROPEDIT_SELECTORS=()
  MKVUTIL_TRACK_ORDER=""
  MKVUTIL_OUTPUT_EXTENSION=""

  [[ -n "$rows" ]] || return 1
  while IFS= read -r row || [[ -n "$row" ]]; do
    [[ -n "$row" && "$row" == *$'\t'* ]] || return 1
    track_type="${row%%$'\t'*}"
    raw_id="${row#*$'\t'}"
    [[ "$raw_id" != *$'\t'* ]] || return 1
    [[ "$track_type" == video || "$track_type" == audio || "$track_type" == subtitles ]] || return 1
    _mkvutil_canonical_id "$raw_id" || return 1
    track_id="$REPLY"
    [[ -z "${input_set[$track_id]-}" ]] || return 1

    input_set[$track_id]=1
    MKVUTIL_INPUT_IDS+=("$track_id")
    MKVUTIL_TRACK_TYPES[$track_id]="$track_type"
    (( position++ ))
    selector="track:$position"
    MKVUTIL_PROPEDIT_SELECTORS[$track_id]="$selector"
  done <<< "$rows"
  (( ${#MKVUTIL_INPUT_IDS} > 0 )) || return 1

  removed_input="${removed_input//[[:space:]]/}"
  if [[ -n "$removed_input" ]]; then
    removed_ids="$(mkvutil_expand_ids "$removed_input" "${(j:,:)MKVUTIL_INPUT_IDS}")" || return 1
    for track_id in "${(@s:,:)removed_ids}"; do
      removed_set[$track_id]=1
    done
  fi

  for track_id in "${MKVUTIL_INPUT_IDS[@]}"; do
    [[ -z "${removed_set[$track_id]-}" ]] || continue
    MKVUTIL_RETAINED_IDS+=("$track_id")
  done
  (( ${#MKVUTIL_RETAINED_IDS} > 0 )) || return 1

  order="${order_input//[[:space:]]/}"
  if [[ -n "$order" ]]; then
    local -a order_items=("${(@s:,:)order}")
    for order_item in "${order_items[@]}"; do
      [[ "$order_item" == 0:* ]] || return 1
      order_id="${order_item#0:}"
      _mkvutil_canonical_id "$order_id" || return 1
      order_id="$REPLY"
      [[ -n "${input_set[$order_id]-}" ]] || return 1
      [[ -z "${removed_set[$order_id]-}" ]] || return 1
      [[ -z "${order_set[$order_id]-}" ]] || return 1
      order_set[$order_id]=1
      ordered_ids+=("$order_id")
    done
  fi

  final_ids=("${ordered_ids[@]}")
  for track_id in "${MKVUTIL_RETAINED_IDS[@]}"; do
    [[ -n "${order_set[$track_id]-}" ]] || final_ids+=("$track_id")
  done
  for track_id in "${final_ids[@]}"; do
    (( retained_count++ ))
    case "${MKVUTIL_TRACK_TYPES[$track_id]}" in
      video) has_video=1 ;;
      audio) has_audio=1 ;;
      subtitles) has_subtitles=1 ;;
    esac
    [[ -n "$output_order" ]] && output_order+=","
    output_order+="0:$track_id"
  done
  (( retained_count > 0 )) || return 1

  extension="${input_extension#.}"
  extension="${extension:l}"
  case "$extension" in
    mkv|mka|mks|mk3d) ;;
    *) return 1 ;;
  esac

  if (( ${#removed_set} == 0 )); then
    MKVUTIL_OUTPUT_EXTENSION="$extension"
  elif (( has_video )); then
    if [[ "$extension" == mk3d ]]; then
      MKVUTIL_OUTPUT_EXTENSION="mk3d"
    else
      MKVUTIL_OUTPUT_EXTENSION="mkv"
    fi
  elif (( has_audio )); then
    MKVUTIL_OUTPUT_EXTENSION="mka"
  elif (( has_subtitles )); then
    MKVUTIL_OUTPUT_EXTENSION="mks"
  else
    return 1
  fi

  MKVUTIL_RETAINED_IDS=("${final_ids[@]}")
  MKVUTIL_TRACK_ORDER="$output_order"
}

_mkvutil_clear_plan_layout() {
  MKVUTIL_INPUT_IDS=()
  MKVUTIL_RETAINED_IDS=()
  MKVUTIL_TRACK_TYPES=()
  MKVUTIL_PROPEDIT_SELECTORS=()
  MKVUTIL_TRACK_ORDER=""
  MKVUTIL_OUTPUT_EXTENSION=""
}

mkvutil_plan_layout() {
  local result=0
  _mkvutil_clear_plan_layout
  _mkvutil_plan_layout_build "$@" || result=$?
  if (( result != 0 )); then
    _mkvutil_clear_plan_layout
    return "$result"
  fi
  return 0
}

# Shared metadata foundation. Definitions are the sole source of menu order,
# prompts, defaults, validators and both tool mappings. No helper in this
# section edits media or invokes mkvmerge/mkvpropedit.
typeset -ga MKVUTIL_METADATA_IDS=()
typeset -gA MKVUTIL_METADATA_REGISTRY=()
# Keys are CHOICE:ORIGINAL_TID; container settings use CHOICE:info. An existing
# key with an empty value explicitly clears a name/title; a missing key is idle.
typeset -gA MKVUTIL_METADATA_SETTINGS=()
typeset -gA MKVUTIL_SOURCE_FLAGS=()
typeset -g MKVUTIL_FLAG_LAYOUT=""
typeset -ga MKVUTIL_PROPEDIT_ARGS=()
typeset -ga MKVUTIL_MERGE_METADATA_ARGS=()

_mkvutil_metadata_define() {
  (( $# == 9 )) || return 1
  local choice="$1" field="" key="" i=0
  local -a fields=(label scope prompt default validator property merge snapshot)
  _mkvutil_canonical_id "$choice" || return 1
  choice="$REPLY"
  [[ "$choice" != 0 ]] || return 1
  (( ${MKVUTIL_METADATA_IDS[(Ie)$choice]} == 0 )) || return 1
  MKVUTIL_METADATA_IDS+=("$choice")
  for (( i = 1; i <= ${#fields}; i++ )); do
    field="${fields[$i]}"
    key="${choice}:$field"
    MKVUTIL_METADATA_REGISTRY[$key]="${argv[$(( i + 1 ))]}"
  done
}

_mkvutil_metadata_define 1 'Set flag-forced for tracks' track 'Flag-forced (1 or 0) [0]: ' 0 boolean flag-forced --forced-display-flag forced_track
_mkvutil_metadata_define 2 'Set flag-default for tracks' track 'Flag-default (1 or 0) [1]: ' 1 boolean flag-default --default-track-flag default_track
_mkvutil_metadata_define 3 'Set language for tracks' track 'Language: ' '' language language --language ''
_mkvutil_metadata_define 4 'Set name for tracks' track 'Name: ' '' text name --track-name ''
_mkvutil_metadata_define 5 'Set title for MK file' container 'Title (empty to unset): ' '' text title --title ''

# BCP 47 structural syntax plus grandfathered tags; this deliberately does not
# assert IANA/ISO membership or tool acceptance. Preserve the user's spelling.
_mkvutil_metadata_language_valid() {
  local value="$1" language='([A-Za-z]{2,3}(-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})'
  local script='(-[A-Za-z]{4})?' region='(-([A-Za-z]{2}|[0-9]{3}))?'
  local variants='(-([A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*'
  local extensions='(-[0-9A-WY-Za-wy-z](-[A-Za-z0-9]{2,8})+)*'
  local private='(-[xX](-[A-Za-z0-9]{1,8})+)?' pattern=""
  local subtag="" in_extension=0 i=0
  local -a subtags=()
  local -A seen_variants=() seen_extensions=()
  case "${value:l}" in
    en-gb-oed|i-ami|i-bnn|i-default|i-enochian|i-hak|i-klingon|i-lux|i-mingo|i-navajo|i-pwn|i-tao|i-tay|i-tsu|sgn-be-fr|sgn-be-nl|sgn-ch-de|art-lojban|cel-gaulish|no-bok|no-nyn|zh-guoyu|zh-hakka|zh-min|zh-min-nan|zh-xiang) return 0 ;;
  esac
  pattern="^($language$script$region$variants$extensions$private|[xX](-[A-Za-z0-9]{1,8})+)$"
  [[ "$value" =~ "$pattern" ]] || return 1
  value="${value:l}"
  [[ "$value" != x-* ]] || return 0
  subtags=("${(@s:-:)value}")
  for (( i = 2; i <= ${#subtags}; i++ )); do
    subtag="${subtags[$i]}"
    [[ "$subtag" != x ]] || break
    if (( ${#subtag} == 1 )); then
      (( ! ${+seen_extensions[$subtag]} )) || return 1
      seen_extensions[$subtag]=1
      in_extension=1
    elif (( ! in_extension )) && [[ "$subtag" =~ '^([a-z0-9]{5,8}|[0-9][a-z0-9]{3})$' ]]; then
      (( ! ${+seen_variants[$subtag]} )) || return 1
      seen_variants[$subtag]=1
    fi
  done
  return 0
}

_mkvutil_metadata_value_valid() {
  case "$1" in
    boolean) [[ "$2" == 0 || "$2" == 1 ]] ;;
    language) _mkvutil_metadata_language_valid "$2" ;;
    text) return 0 ;;
    *) return 1 ;;
  esac
}

mkvutil_metadata_validate_registry() {
  local choice="" field="" key="" scope="" validator="" snapshot="" value=""
  local -A seen=()
  (( ${#MKVUTIL_METADATA_IDS} > 0 )) || return 1
  for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
    _mkvutil_canonical_id "$choice" || return 1
    [[ "$choice" == "$REPLY" && "$choice" != 0 && -z "${seen[$choice]-}" ]] || return 1
    seen[$choice]=1
    for field in label scope prompt default validator property merge snapshot; do
      key="${choice}:$field"
      (( ${+MKVUTIL_METADATA_REGISTRY[$key]} )) || return 1
      case "$field" in
        default|snapshot) ;;
        *) [[ -n "${MKVUTIL_METADATA_REGISTRY[$key]}" ]] || return 1 ;;
      esac
    done
    scope="${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}"
    validator="${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}"
    snapshot="${MKVUTIL_METADATA_REGISTRY[${choice}:snapshot]}"
    [[ "$scope" == track || "$scope" == container ]] || return 1
    [[ "$validator" == boolean || "$validator" == language || "$validator" == text ]] || return 1
    [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:property]}" =~ '^[a-z][a-z0-9-]*$' ]] || return 1
    [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:merge]}" =~ '^--[a-z][a-z0-9-]*$' ]] || return 1
    value="${MKVUTIL_METADATA_REGISTRY[${choice}:default]}"
    if [[ "$validator" == boolean || -n "$value" ]]; then
      _mkvutil_metadata_value_valid "$validator" "$value" || return 1
    fi
    if [[ -n "$snapshot" ]]; then
      [[ "$scope" == track && "$validator" == boolean && "$snapshot" =~ '^[a-z][a-z_]*$' ]] || return 1
    fi
  done
  return 0
}

mkvutil_metadata_menu() {
  local choice=""
  mkvutil_metadata_validate_registry || return 1
  for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
    print -r -- "$choice) ${MKVUTIL_METADATA_REGISTRY[${choice}:label]}"
  done
}

mkvutil_metadata_reset() {
  MKVUTIL_METADATA_SETTINGS=()
  MKVUTIL_SOURCE_FLAGS=()
  MKVUTIL_FLAG_LAYOUT=""
  MKVUTIL_PROPEDIT_ARGS=()
  MKVUTIL_MERGE_METADATA_ARGS=()
}

_mkvutil_metadata_target_valid() {
  local choice="$1" target="$2"
  (( ${MKVUTIL_METADATA_IDS[(Ie)$choice]} > 0 )) || return 1
  if [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == container ]]; then
    [[ "$target" == info ]] || return 1
  else
    _mkvutil_canonical_id "$target" || return 1
    [[ "$target" == "$REPLY" ]] || return 1
    (( ${MKVUTIL_RETAINED_IDS[(Ie)$target]} > 0 && ${MKVUTIL_INPUT_IDS[(Ie)$target]} > 0 )) || return 1
    [[ -n "${MKVUTIL_TRACK_TYPES[$target]-}" && -n "${MKVUTIL_PROPEDIT_SELECTORS[$target]-}" ]] || return 1
  fi
  return 0
}

# Pure setter: mkvutil_metadata_set CHOICE ORIGINAL_TID_OR_info VALUE.
mkvutil_metadata_set() {
  MKVUTIL_PROPEDIT_ARGS=()
  MKVUTIL_MERGE_METADATA_ARGS=()
  (( $# == 3 )) || return 1
  local choice="$1" target="$2" value="$3"
  mkvutil_metadata_validate_registry || return 1
  _mkvutil_canonical_id "$choice" || return 1
  choice="$REPLY"
  if [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]-}" == track ]]; then
    _mkvutil_canonical_id "$target" || return 1
    target="$REPLY"
  fi
  _mkvutil_metadata_target_valid "$choice" "$target" || return 1
  _mkvutil_metadata_value_valid "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" "$value" || return 1
  MKVUTIL_METADATA_SETTINGS[${choice}:$target]="$value"
}

_mkvutil_metadata_collect() {
  local choices="" choice="" selection="" targets_csv="" target="" value=""
  local -a chosen_targets=()
  mkvutil_metadata_validate_registry || return 1
  choices="$(mkvutil_expand_ids "$1" "${(j:,:)MKVUTIL_METADATA_IDS}")" || return 1
  for choice in "${(@s:,:)choices}"; do
    chosen_targets=(info)
    if [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == track ]]; then
      printf '%s — Track IDs (comma/range; cancel to return): ' "${MKVUTIL_METADATA_REGISTRY[${choice}:label]}" >&2
      IFS= read -r selection || return 2
      [[ "$selection" != cancel ]] || return 2
      targets_csv="$(mkvutil_expand_ids "$selection" "${(j:,:)MKVUTIL_RETAINED_IDS}")" || return 1
      chosen_targets=("${(@s:,:)targets_csv}")
    fi
    for target in "${chosen_targets[@]}"; do
      [[ "$target" == info ]] || printf 'Track ID %s — ' "$target" >&2
      printf '%s' "${MKVUTIL_METADATA_REGISTRY[${choice}:prompt]}" >&2
      IFS= read -r value || return 2
      [[ -n "$value" ]] || value="${MKVUTIL_METADATA_REGISTRY[${choice}:default]}"
      mkvutil_metadata_set "$choice" "$target" "$value" || return 1
    done
  done
  return 0
}

# Collect once, before execution. EOF/cancel returns 2; invalid input returns 1.
# A failed/cancelled collection leaves no partial settings or argument arrays.
mkvutil_metadata_configure() {
  local result=0
  mkvutil_metadata_reset
  _mkvutil_metadata_collect "${1-}" || result=$?
  if (( result != 0 )); then
    mkvutil_metadata_reset
    return "$result"
  fi
  return 0
}

_mkvutil_metadata_validate_settings() {
  local key="" choice="" target=""
  mkvutil_metadata_validate_registry || return 1
  (( ${#MKVUTIL_INPUT_IDS} > 0 && ${#MKVUTIL_RETAINED_IDS} > 0 )) || return 1
  for key in "${(@k)MKVUTIL_METADATA_SETTINGS}"; do
    [[ "$key" == *:* ]] || return 1
    choice="${key%%:*}"
    target="${key#*:}"
    _mkvutil_metadata_target_valid "$choice" "$target" || return 1
    _mkvutil_metadata_value_valid "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" "${MKVUTIL_METADATA_SETTINGS[$key]}" || return 1
  done
  return 0
}

_mkvutil_metadata_layout_rows() {
  local track_id=""
  for track_id in "${MKVUTIL_INPUT_IDS[@]}"; do
    print -r -- "$track_id"$'\t'"${MKVUTIL_TRACK_TYPES[$track_id]}"
  done
}

# Accept already-identified JSON; jq is the only subprocess. Check the current
# original listing and snapshot boolean fields for retained tracks, including
# explicit false. Never infer defaults from absent/null/non-boolean properties.
mkvutil_metadata_snapshot_flags() {
  local json="${1-}" choice="" field="" definitions="" expected="" rows=""
  local track_id="" value="" key=""
  local -A flags=()
  MKVUTIL_SOURCE_FLAGS=()
  MKVUTIL_FLAG_LAYOUT=""
  MKVUTIL_MERGE_METADATA_ARGS=()
  _mkvutil_metadata_validate_settings || return 1
  expected="$(_mkvutil_metadata_layout_rows)" || return 1
  for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
    field="${MKVUTIL_METADATA_REGISTRY[${choice}:snapshot]}"
    [[ -n "$field" ]] || continue
    [[ -z "$definitions" ]] || definitions+=$'\n'
    definitions+="$choice"$'\t'"$field"
  done
  rows="$(jq -er --arg expected "$expected" --arg definitions "$definitions" \
    --arg retained "${(j:,:)MKVUTIL_RETAINED_IDS}" '
    .tracks as $tracks |
    if ($tracks | type) != "array" or
       any($tracks[]; (.id | type) != "number" or .id < 0 or .id != (.id | floor))
    then error("invalid original track listing") else . end |
    if ($tracks | map([(.id | tostring), .type] | @tsv) | join("\n")) != $expected
    then error("snapshot/layout mismatch") else . end |
    ($retained | split(",")) as $keep |
    ($definitions | split("\n") | map(select(length > 0) | split("\t"))) as $fields |
    $tracks[] | (.id | tostring) as $id | select($keep | index($id)) |
    .properties as $properties | $fields[] |
    .[0] as $choice | .[1] as $field | $properties[$field] as $value |
    if ($value | type) != "boolean" then error("invalid preserved flag")
    else [$choice, $id, (if $value then "1" else "0" end)] | @tsv end
    ' <<< "$json")" || return 1
  while IFS=$'\t' read -r choice track_id value; do
    [[ -n "$choice" && -n "$track_id" && ( "$value" == 0 || "$value" == 1 ) ]] || return 1
    key="${choice}:$track_id"
    (( ! ${+flags[$key]} )) || return 1
    flags[$key]="$value"
  done <<< "$rows"
  MKVUTIL_SOURCE_FLAGS=("${(@kv)flags}")
  MKVUTIL_FLAG_LAYOUT="$expected|${(j:,:)MKVUTIL_RETAINED_IDS}"
  return 0
}

# Build one grouped mkvpropedit argv suffix in MKVUTIL_PROPEDIT_ARGS. Original
# listing-position selectors are independent of reordered output positions.
mkvutil_build_propedit_args() {
  local track_id="" choice="" key="" property="" value=""
  local -a args=() changes=()
  MKVUTIL_PROPEDIT_ARGS=()
  _mkvutil_metadata_validate_settings || return 1
  for track_id in "${MKVUTIL_INPUT_IDS[@]}"; do
    changes=()
    for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
      [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == track ]] || continue
      key="${choice}:$track_id"
      (( ${+MKVUTIL_METADATA_SETTINGS[$key]} )) || continue
      property="${MKVUTIL_METADATA_REGISTRY[${choice}:property]}"
      changes+=(--set "$property=${MKVUTIL_METADATA_SETTINGS[$key]}")
    done
    (( ${#changes} > 0 )) || continue
    args+=(--edit "${MKVUTIL_PROPEDIT_SELECTORS[$track_id]}" "${changes[@]}")
  done
  changes=()
  for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
    [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == container ]] || continue
    key="${choice}:info"
    (( ${+MKVUTIL_METADATA_SETTINGS[$key]} )) || continue
    property="${MKVUTIL_METADATA_REGISTRY[${choice}:property]}"
    value="${MKVUTIL_METADATA_SETTINGS[$key]}"
    if [[ -z "$value" ]]; then
      changes+=(--delete "$property")
    else
      changes+=(--set "$property=$value")
    fi
  done
  (( ${#changes} == 0 )) || args+=(--edit info "${changes[@]}")
  MKVUTIL_PROPEDIT_ARGS=("${args[@]}")
  return 0
}

# Build metadata-only mkvmerge argv in MKVUTIL_MERGE_METADATA_ARGS. The caller
# must place this complete array BEFORE its source filename. Emit one resolved
# flag per retained original TID; untouched languages/names remain untouched.
mkvutil_build_merge_metadata_args() {
  local track_id="" choice="" key="" value="" option="" expected=""
  local -a args=()
  MKVUTIL_MERGE_METADATA_ARGS=()
  _mkvutil_metadata_validate_settings || return 1
  expected="$(_mkvutil_metadata_layout_rows)|${(j:,:)MKVUTIL_RETAINED_IDS}"
  for track_id in "${MKVUTIL_RETAINED_IDS[@]}"; do
    for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
      [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == track ]] || continue
      key="${choice}:$track_id"
      if (( ${+MKVUTIL_METADATA_SETTINGS[$key]} )); then
        value="${MKVUTIL_METADATA_SETTINGS[$key]}"
      elif [[ -n "${MKVUTIL_METADATA_REGISTRY[${choice}:snapshot]}" ]]; then
        [[ "$MKVUTIL_FLAG_LAYOUT" == "$expected" ]] || return 1
        (( ${+MKVUTIL_SOURCE_FLAGS[$key]} )) || return 1
        value="${MKVUTIL_SOURCE_FLAGS[$key]}"
        [[ "$value" == 0 || "$value" == 1 ]] || return 1
      else
        continue
      fi
      option="${MKVUTIL_METADATA_REGISTRY[${choice}:merge]}"
      args+=("$option" "${track_id}:$value")
    done
  done
  for choice in "${MKVUTIL_METADATA_IDS[@]}"; do
    [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == container ]] || continue
    key="${choice}:info"
    (( ${+MKVUTIL_METADATA_SETTINGS[$key]} )) || continue
    value="${MKVUTIL_METADATA_SETTINGS[$key]}"
    # mkvmerge interprets an argument starting @ as an option file. Escape only
    # this emitted literal; canonical configuration and preview stay unchanged.
    [[ "$value" != @* ]] || value="@$value"
    args+=("${MKVUTIL_METADATA_REGISTRY[${choice}:merge]}" "$value")
  done
  MKVUTIL_MERGE_METADATA_ARGS=("${args[@]}")
  return 0
}

# Function to rename tracks using mkvpropedit
rename_tracks() {
  local track_ids="$1"
  # Split track_ids by comma and space into array ids
  IFS=', ' read -rA ids <<< "$track_ids"
  reset_propedit_summary
  # Loop over each track ID
  for id in "${ids[@]}"; do
    # Determine range or single ID
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Name ---------------------"
        printf "Name: "
        read name
        # Apply name change to each target file
        start_propedit_summary
        for file in "${targets[@]}"; do
          if (trap '' SIGINT; exec mkvpropedit "$file" --edit track:$((i+1)) --set name="$name" < /dev/null); then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
            record_propedit_failure "$file" "$i"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Name ---------------------"
      printf "Name: "
      read name
      start_propedit_summary
      for file in "${targets[@]}"; do
        if (trap '' SIGINT; exec mkvpropedit "$file" --edit track:$((id+1)) --set name="$name" < /dev/null); then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
          record_propedit_failure "$file" "$id"
        fi
      done
    fi
  done
  finish_propedit_summary
}

set_mkv_title() {
  local title="$1"

  reset_propedit_summary
  start_propedit_summary
  for file in "${targets[@]}"; do
    if [[ -z "$title" ]]; then
      if mkvpropedit "$file" --delete title < /dev/null; then
        echo "Edited File: ${file:t}"
      else
        echo "Failed File: ${file:t}"
        record_propedit_failure "$file"
      fi
    else
      if mkvpropedit "$file" --set title="$title" < /dev/null; then
        echo "Edited File: ${file:t}"
      else
        echo "Failed File: ${file:t}"
        record_propedit_failure "$file"
      fi
    fi
  done
  finish_propedit_summary
}


# Function to set language of tracks across multiple files
set_language_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<< "$track_ids"
  reset_propedit_summary
  for id in "${ids[@]}"; do
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Language ---------------------"
        printf "Language: "
        read lang
        start_propedit_summary
        for file in "${targets[@]}"; do
          if mkvpropedit "$file" --edit track:$((i+1)) --set language="$lang"; then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
            record_propedit_failure "$file" "$i"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Language ---------------------"
      printf "Language: "
      read lang
      start_propedit_summary
      for file in "${targets[@]}"; do
        if mkvpropedit "$file" --edit track:$((id+1)) --set language="$lang"; then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
          record_propedit_failure "$file" "$id"
        fi
      done
    fi
  done
  finish_propedit_summary
}

# Function to set forced flag for tracks across multiple files
set_flag_forced_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<< "$track_ids"
  reset_propedit_summary
  for id in "${ids[@]}"; do
    # Determine range or single ID
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Forced Flag ---------------------"
        printf "Flag-forced (1 or 0) [0]: "
        read value
        value=${value:-0}
        start_propedit_summary
        for file in "${targets[@]}"; do
          if mkvpropedit "$file" --edit track:$((i+1)) --set flag-forced=$value; then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
            record_propedit_failure "$file" "$i"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Forced Flag ---------------------"
      printf "Flag-forced (1 or 0) [0]: "
      read value
      value=${value:-0}
      start_propedit_summary
      for file in "${targets[@]}"; do
        if mkvpropedit "$file" --edit track:$((id+1)) --set flag-forced=$value; then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
          record_propedit_failure "$file" "$id"
        fi
      done
    fi
  done
  finish_propedit_summary
}

# Function to set default flag for tracks across multiple files
set_flag_default_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<< "$track_ids"
  reset_propedit_summary
  for id in "${ids[@]}"; do
    # Determine range or single ID
    if [[ $id == *-* ]]; then
      local start=${id%-*}
      local end=${id#*-}
      for ((i=start; i<=end; i++)); do
        echo "--------------------  Track ID $i Default Flag ---------------------"
        printf "Flag-default (1 or 0) [1]: "
        read value
        value=${value:-1}
        start_propedit_summary
        for file in "${targets[@]}"; do
          if mkvpropedit "$file" --edit track:$((i+1)) --set flag-default=$value; then
            echo "Edited File: ${file:t}"
          else
            echo "Failed File: ${file:t}"
            record_propedit_failure "$file" "$i"
          fi
        done
      done
    else
      echo "--------------------  Track ID $id Default Flag ---------------------"
      printf "Flag-default (1 or 0) [1]: "
      read value
      value=${value:-1}
      start_propedit_summary
      for file in "${targets[@]}"; do
        if mkvpropedit "$file" --edit track:$((id+1)) --set flag-default=$value; then
          echo "Edited File: ${file:t}"
        else
          echo "Failed File: ${file:t}"
          record_propedit_failure "$file" "$id"
        fi
      done
    fi
  done
  finish_propedit_summary
}

# Helper: extract one track by id, with enhanced output
extract_single() {
  local tid=$1
  local src_base=${source_file##*/}
  local base=${src_base%.*}

  # Pull the JSON for this file directly, then grab codec_id
  local cid
  cid=$(mkvmerge -J "$source_file" < /dev/null \
        | jq -r ".tracks[] | select(.id==${tid}) | .properties.codec_id")

  # 1) Try a full‐ID override
  local ext=${ext_override[$cid]:-}

  # 2) Fallback to the short key
  if [[ -z $ext ]]; then
    local key=${cid##*/}
    ext=${ext_override[$key]:-}
  fi

  # 3) Fallback to pymkv2 map or lowercase key
  if [[ -z $ext ]]; then
    ext=${codec_ext[$key]:-}
    [[ -z $ext ]] && ext=${(L)${key//[^[:alnum:]]/}}
  fi

  echo "Matched codec ID: ${cid} → extension: .${ext}"
  echo "Extracting track ${tid} (${cid}) → ${base} - Track [${tid}].${ext}"
  mkvextract tracks "$source_file" \
    ${tid}:"${base} - Track [${tid}].${ext}"
}

# Function to extract selected tracks from a single MKV
extract_tracks() {
  local track_ids="$1"
  IFS=', ' read -rA ids <<<"$track_ids"

  # build the codec→ext map
  typeset -A codec_ext
  ensure_venv_python
  eval "$(
    "$PYTHON_BIN" - <<'PYCODE'
from pymkv.TypeTrack import type_files
flat = {k:v for cat in type_files.values() for k,v in cat.items()}
items = ' '.join(f"['{k}']='{v}'" for k, v in flat.items())
print(f"typeset -A codec_ext=( {items} )")
PYCODE
  )"

  for id in "${ids[@]}"; do
    if [[ $id == *-* ]]; then
      local start=${id%-*} end=${id#*-}
      for ((i=start; i<=end; i++)); do
        extract_single "$i"
      done
    else
      extract_single "$id"
    fi
  done
}

# Category planning controller. Jobs are JSON records, with raw identification
# JSON retained as a string so 64-bit UID evidence never passes through jq math.
typeset -ga MKVUTIL_SCAN_FILES=() MKVUTIL_SELECTED_FILES=() MKVUTIL_SOURCES=() MKVUTIL_JOBS=()
typeset -ga MKVUTIL_REMOVAL_SKIPS=() MKVUTIL_REMOVAL_SKIP_HISTORY=()
typeset -g MKVUTIL_CURRENT_JOB="" MKVUTIL_CONFIG="" MKVUTIL_CODEC_EXT_JSON=""

_mkvutil_json_array() {
  jq -cn '$ARGS.positional' --args -- "$@"
}

_mkvutil_json_map() {
  jq -cn '$ARGS.positional as $p | reduce range(0; $p|length; 2) as $i ({}; .[$p[$i]]=$p[$i+1])' --args -- "$@"
}

mkvutil_source_identity() {
  python3 - "$1" <<'PYCODE'
import json, os, stat, sys
try:
    item = os.stat(sys.argv[1])
    if not stat.S_ISREG(item.st_mode):
        raise ValueError("source is not a regular file")
    # Decimal strings preserve nanosecond/inode precision in shell/jq records.
    print(json.dumps(dict(zip(("dev", "ino", "size", "mtime_ns"),
          map(str, (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)))), sort_keys=True))
except (OSError, ValueError) as error:
    print(f"Cannot inspect source identity: {error}", file=sys.stderr)
    sys.exit(1)
PYCODE
}

mkvutil_capture_source() {
  local file="${1:A}" before="" after="" json="" rows=""
  before="$(mkvutil_source_identity "$file")" || return 1
  json="$(mkvmerge -J "$file" < /dev/null)" || return 1
  after="$(mkvutil_source_identity "$file")" || return 1
  [[ "$before" == "$after" ]] || { print -u2 -r -- "Source changed during inspection: $file"; return 1; }
  rows="$(collect_tracks_for_remux "$file" "$json")" || return 1
  mkvutil_plan_layout "$rows" '' '' "${file:e}" || return 1
  jq -cn --arg source "$file" --argjson identity "$before" --arg source_json "$json" '
    ($source_json | fromjson) as $j |
    {source:$source, identity:$identity, source_json:$source_json,
     model:{tracks:[$j.tracks[] | {id,type,properties:{codec_id:.properties.codec_id,
       track_name:.properties.track_name, language:.properties.language,
       language_ietf:.properties.language_ietf, default_track:.properties.default_track,
       forced_track:.properties.forced_track}}],
       title:($j.container.properties.title // null), attachments:($j.attachments // [])}}
  '
}

mkvutil_scan_files() {
  local directory="${1:A}" file=""
  MKVUTIL_SCAN_FILES=()
  for file in "$directory"/*.(mkv|mka|mks|mk3d)(N.); do
    MKVUTIL_SCAN_FILES+=("$file")
  done
  (( ${#MKVUTIL_SCAN_FILES} > 0 ))
}

mkvutil_resolve_directory() {
  local directory="${1:-$PWD}"
  [[ -d "$directory" ]] || { print -u2 -r -- "Error: Working directory not found: $directory"; return 1; }
  print -r -- "${directory:A}"
}

# Pure domain check also rejects duplicate aliases, directories and injected
# fzf choices. Both scan and selected paths become canonical absolute paths.
mkvutil_accept_files() {
  local file="" canonical=""
  local -a accepted=()
  local -A domain=() seen=()
  MKVUTIL_SELECTED_FILES=()
  for file in "${MKVUTIL_SCAN_FILES[@]}"; do domain[${file:A}]=1; done
  for file in "$@"; do
    canonical="${file:A}"
    [[ -n "${domain[$canonical]-}" && -f "$canonical" && -z "${seen[$canonical]-}" ]] || return 1
    seen[$canonical]=1
    accepted+=("$canonical")
  done
  (( ${#accepted} > 0 )) || return 1
  MKVUTIL_SELECTED_FILES=("${accepted[@]}")
}

_mkvutil_read() {
  printf '%s' "$1" >&2
  IFS= read -r REPLY || return 2
}

_mkvutil_exclude() {
  _mkvutil_read 'Exclude this file from the batch? (Y/N) [N]: ' || return 2
  [[ "${REPLY:u}" == Y || "${REPLY:u}" == YES ]]
}

mkvutil_select_files() {
  local file=""
  local -a selected=() selector=(--multi --read0 --print0 --height 40% --reverse --border)
  while IFS= read -r -d '' file; do selected+=("$file"); done < <(
    printf '%s\0' "${MKVUTIL_SCAN_FILES[@]}" | fzf "${selector[@]}"
  )
  mkvutil_accept_files "${selected[@]}" || { print -u2 -r -- 'No valid scanned files selected.'; return 1; }
}

mkvutil_inspect_sources() {
  local file="" record="" result=0
  MKVUTIL_SOURCES=()
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_REMOVAL_SKIP_HISTORY=()
  for file in "${MKVUTIL_SELECTED_FILES[@]}"; do
    if record="$(mkvutil_capture_source "$file")"; then
      MKVUTIL_SOURCES+=("$record")
    else
      print -u2 -r -- "Inspection failed: $file"
      _mkvutil_exclude || { result=$?; return "$result"; }
    fi
  done
  (( ${#MKVUTIL_SOURCES} > 0 )) || { print -u2 -r -- 'No valid sources remain.'; return 1; }
}

mkvutil_category_menu() {
  case "$1" in
    edit) mkvutil_metadata_menu ;;
    mux) print -r -- $'1) Remove tracks\n2) Reorder tracks' ;;
    extract) print -r -- $'1) Extract attachments\n2) Extract selected tracks' ;;
    *) return 1 ;;
  esac
}

mkvutil_category_choices() {
  local domain=""
  case "$1" in
    edit) mkvutil_metadata_validate_registry || return 1; domain="${(j:,:)MKVUTIL_METADATA_IDS}" ;;
    mux|extract) domain=1,2 ;;
    *) return 1 ;;
  esac
  mkvutil_expand_ids "$2" "$domain"
}

# Configure against the first original model. Every job validates targeted IDs
# and types against its own model afterward; untouched heterogeneous tracks are
# allowed. Optional Mux metadata uses exactly the Edit registry/collector.
mkvutil_configure_category() {
  local category="$1" operations="$2" reference="${MKVUTIL_SOURCES[1]}"
  local raw="" rows="" source="" removal="" order="" metadata="" extract_ids="" expected="" settings="" signatures='{}'
  local -a order_ids=()
  local item=""
  MKVUTIL_CONFIG=""
  MKVUTIL_JOBS=()
  mkvutil_metadata_reset
  raw="$(jq -r '.source_json' <<< "$reference")" || return 1
  source="$(jq -r '.source' <<< "$reference")" || return 1
  rows="$(collect_tracks_for_remux "$source" "$raw")" || return 1
  mkvutil_plan_layout "$rows" '' '' "${source:e}" || return 1
  expected="$(_mkvutil_json_map "${(@kv)MKVUTIL_TRACK_TYPES}")" || return 1
  if [[ "$category" == mux && ",$operations," == *,1,* ]]; then
    print -r -- "Removal reference file: $source"
  fi
  display_track_info "$source" "$raw" || return 1
  case "$category" in
    edit) mkvutil_metadata_configure "$operations" || return $? ;;
    mux)
      if [[ ",$operations," == *,1,* ]]; then
        _mkvutil_read 'Track IDs to remove (comma/range): ' || return 2
        removal="$(mkvutil_expand_ids "$REPLY" "${(j:,:)MKVUTIL_INPUT_IDS}")" || return 1
        signatures="$(mkvutil_removal_signatures "$reference" "$removal")" || return 1
      fi
      if [[ ",$operations," == *,2,* ]]; then
        _mkvutil_read 'Track order (e.g. 0:1,0:0; omitted retained tracks append): ' || return 2
        order="${REPLY//[[:space:]]/}"
        [[ -n "$order" ]] || return 1
      fi
      mkvutil_plan_layout "$rows" "$removal" "$order" "${source:e}" || return 1
      for item in "${(@s:,:)order}"; do
        [[ -n "$item" ]] || continue
        _mkvutil_canonical_id "${item#0:}" || return 1
        order_ids+=("$REPLY")
      done
      print -r -- 'Optional metadata edits:'
      mkvutil_metadata_menu || return 1
      _mkvutil_read 'Metadata choices (comma/range; blank for none): ' || return 2
      metadata="$REPLY"
      if [[ -n "${metadata//[[:space:]]/}" ]]; then
        metadata="$(mkvutil_category_choices edit "$metadata")" || return 1
        mkvutil_metadata_configure "$metadata" || return $?
      fi
      ;;
    extract)
      if [[ ",$operations," == *,2,* ]]; then
        _mkvutil_read 'Track IDs to extract (comma/range): ' || return 2
        extract_ids="$(mkvutil_expand_ids "$REPLY" "${(j:,:)MKVUTIL_INPUT_IDS}")" || return 1
      fi
      ;;
    *) return 1 ;;
  esac
  settings="$(_mkvutil_json_map "${(@kv)MKVUTIL_METADATA_SETTINGS}")" || return 1
  MKVUTIL_CONFIG="$(jq -cn --arg category "$category" --arg operations "$operations" \
    --arg removal "$removal" --arg order "$order" --arg metadata "$metadata" --arg extract "$extract_ids" \
    --argjson order_ids "$(_mkvutil_json_array "${order_ids[@]}")" \
    --argjson settings "$settings" --argjson expected_types "$expected" --arg reference "$source" --argjson signatures "$signatures" '
    {category:$category, operations:($operations|split(",")), removed_ids:($removal|split(",")|map(select(length>0))),
     order:$order, order_ids:$order_ids, metadata:$metadata, settings:$settings, expected_types:$expected_types,
     extract_ids:($extract|split(",")|map(select(length>0))), reference:$reference, removal_signatures:$signatures}')" || return 1
  MKVUTIL_REMOVAL_SKIPS=()
}

# Only requested original IDs define removal compatibility. Reference codec
# values must be usable strings; metadata and other tracks are not signatures.
mkvutil_removal_signatures() {
  jq -en --argjson reference "$1" --arg ids "$2" '
    reduce ($ids|split(",")[]) as $id ({};
      ([$reference.model.tracks[]|select((.id|tostring)==$id)]|first) as $track |
      if $track==null or ($track.properties.codec_id|type)!="string" or
        ($track.properties.codec_id|test("[^[:space:]]")|not) or
        ($track.type!="video" and $track.type!="audio" and $track.type!="subtitles")
      then error("unusable removal reference signature for original ID " + $id)
      else .[$id]={type:$track.type, codec_id:$track.properties.codec_id} end)
  '
}

# 0: compatible/no removal; 3: mismatch receipt on stdout; 1: invalid config.
# This is the single eligibility rule for planning and later executor preflight.
mkvutil_removal_mismatch() {
  local receipt=""
  mkvutil_validate_config "$2" || return 1
  receipt="$(jq -cn --argjson record "$1" --argjson config "$2" '
    if $config.category!="mux" or ($config.removed_ids|length)==0 then empty else
      [$config.removed_ids[] as $id |
        $config.removal_signatures[$id] as $expected |
        ([$record.model.tracks[]|select((.id|tostring)==$id)]|first) as $track |
        (if $track==null then null else {type:$track.type,codec_id:$track.properties.codec_id} end) as $actual |
        {original_id:$id,expected:$expected,actual:$actual,
         reason:(if $track==null then "missing-id"
           elif $actual.type!=$expected.type and $actual.codec_id!=$expected.codec_id then "type-and-codec-mismatch"
           elif $actual.type!=$expected.type then "type-mismatch"
           elif $actual.codec_id!=$expected.codec_id then "codec-mismatch" else null end)} |
        select(.reason!=null)] as $reasons |
      if ($reasons|length)==0 then empty else
        {schema:1,kind:"removal-mismatch",source:$record.source,identity:$record.identity,
         reference:$config.reference,requested_ids:$config.removed_ids,reasons:$reasons,
         outputs:[],propedit_args:[],merge_metadata_args:[]} end
    end')" || return 1
  [[ -n "$receipt" ]] || return 0
  print -r -- "$receipt"
  return 3
}

_mkvutil_load_settings() {
  local json="$1" key="" value=""
  mkvutil_metadata_reset
  while IFS= read -r -d '' key && IFS= read -r -d '' value; do
    MKVUTIL_METADATA_SETTINGS[$key]="$value"
  done < <(jq -j '.settings|to_entries[]|.key,"\u0000",.value,"\u0000"' <<< "$json")
}

_mkvutil_codec_map() {
  [[ -z "$MKVUTIL_CODEC_EXT_JSON" ]] || return 0
  ensure_venv_python
  MKVUTIL_CODEC_EXT_JSON="$("$PYTHON_BIN" - <<'PYCODE'
import json
from pymkv.TypeTrack import type_files
flat = {k:v for category in type_files.values() for k,v in category.items()}
print(json.dumps(flat))
PYCODE
  )" || return 1
}

mkvutil_validate_config() {
  jq -e '
    . as $config |
    (.category=="edit" or .category=="mux" or .category=="extract") and
    (.operations|type)=="array" and (.operations|length)>0 and
    (.removed_ids|type)=="array" and (.order_ids|type)=="array" and (.extract_ids|type)=="array" and
    (.order|type)=="string" and (.settings|type)=="object" and (.expected_types|type)=="object" and
    all(.settings[]; type=="string") and
    all(.removed_ids[],.order_ids[],.extract_ids[]; type=="string" and test("^[0-9]+$")) and
    (if .category=="edit" then (.removed_ids|length)==0 and .order=="" and (.extract_ids|length)==0
     elif .category=="mux" then (.extract_ids|length)==0 and all(.operations[]; .=="1" or .=="2")
     else (.removed_ids|length)==0 and .order=="" and (.settings|length)==0 and all(.operations[]; .=="1" or .=="2") end) and
    (if .category=="mux" and (.removed_ids|length)>0 then
      (.reference|type)=="string" and (.reference|length)>0 and (.removal_signatures|type)=="object" and
      all(.removed_ids[]; . as $id | $config.removal_signatures[$id] as $signature |
        ($signature.type=="video" or $signature.type=="audio" or $signature.type=="subtitles") and
        $config.expected_types[$id]==$signature.type and
        ($signature.codec_id|type)=="string" and ($signature.codec_id|test("[^[:space:]]")))
     else true end)
  ' <<< "$1" > /dev/null
}

# Pure per-file job builder, apart from a read-only identity recheck. Configuration
# and both argv arrays are embedded in the returned record, never shared by jobs.
mkvutil_plan_job() {
  local record="$1" config="$2" file="" identity="" raw="" rows="" category="" removal="" order=""
  local args="" input_ids="" retained="" selectors="" types="" flags="" codec_map='{}' overrides="" registry="" choices="" mismatch="" result=0
  _mkvutil_clear_plan_layout
  mkvutil_metadata_reset
  MKVUTIL_CURRENT_JOB=""
  mkvutil_validate_config "$config" || return 1
  file="$(jq -r '.source' <<< "$record")" || return 1
  identity="$(mkvutil_source_identity "$file")" || return 1
  jq -e --argjson identity "$identity" '.identity == $identity' <<< "$record" > /dev/null || {
    print -u2 -r -- "Source changed after inspection: $file"; return 1;
  }
  mismatch="$(mkvutil_removal_mismatch "$record" "$config")" || result=$?
  if (( result != 0 )); then
    (( result != 3 )) || print -r -- "$mismatch"
    return "$result"
  fi
  category="$(jq -r '.category' <<< "$config")" || return 1
  raw="$(jq -r '.source_json' <<< "$record")" || return 1
  rows="$(collect_tracks_for_remux "$file" "$raw")" || return 1
  jq -en --argjson record "$record" --argjson config "$config" '
    ($config.removed_ids + $config.order_ids + $config.extract_ids +
      [$config.settings|keys[]|split(":")[1]|select(. != "info")]|unique) as $targeted |
    all($targeted[]; . as $id | any($record.model.tracks[];
      (.id|tostring)==$id and .type==$config.expected_types[$id]))
    ' > /dev/null || { print -u2 -r -- "Missing or incompatible original track IDs: $file"; return 1; }
  removal="$(jq -r '.removed_ids|join(",")' <<< "$config")" || return 1
  order="$(jq -r '.order' <<< "$config")" || return 1
  mkvutil_plan_layout "$rows" "$removal" "$order" "${file:e}" || return 1
  _mkvutil_load_settings "$config" || return 1
  case "$category" in
    edit) mkvutil_build_propedit_args || return 1; args="$(_mkvutil_json_array "${MKVUTIL_PROPEDIT_ARGS[@]}")" || return 1 ;;
    mux)
      mkvutil_metadata_snapshot_flags "$raw" || return 1
      mkvutil_build_merge_metadata_args || return 1
      args="$(_mkvutil_json_array "${MKVUTIL_MERGE_METADATA_ARGS[@]}")" || return 1
      ;;
    extract)
      args='[]'
      if [[ "$(jq -r '.extract_ids|length' <<< "$config")" != 0 ]]; then
        _mkvutil_codec_map || return 1
        codec_map="$MKVUTIL_CODEC_EXT_JSON"
      fi
      ;;
    *) return 1 ;;
  esac
  input_ids="$(_mkvutil_json_array "${MKVUTIL_INPUT_IDS[@]}")" || return 1
  retained="$(_mkvutil_json_array "${MKVUTIL_RETAINED_IDS[@]}")" || return 1
  selectors="$(_mkvutil_json_map "${(@kv)MKVUTIL_PROPEDIT_SELECTORS}")" || return 1
  types="$(_mkvutil_json_map "${(@kv)MKVUTIL_TRACK_TYPES}")" || return 1
  flags="$(_mkvutil_json_map "${(@kv)MKVUTIL_SOURCE_FLAGS}")" || return 1
  overrides="$(_mkvutil_json_map "${(@kv)ext_override}")" || return 1
  registry="$(_mkvutil_json_map "${(@kv)MKVUTIL_METADATA_REGISTRY}")" || return 1
  choices="$(_mkvutil_json_array "${MKVUTIL_METADATA_IDS[@]}")" || return 1
  jq -cn --argjson record "$record" --argjson config "$config" --argjson args "$args" \
    --argjson inputs "$input_ids" --argjson retained "$retained" --argjson selectors "$selectors" \
    --argjson types "$types" --argjson flags "$flags" --arg extension "$MKVUTIL_OUTPUT_EXTENSION" \
    --arg track_order "$MKVUTIL_TRACK_ORDER" --argjson codec_map "$codec_map" --argjson overrides "$overrides" \
    --argjson registry "$registry" --argjson choices "$choices" '
    def codec_extension($cid):
      ($cid|split("/")|last) as $key |
      $overrides[$cid] // $overrides[$key] // $codec_map[$cid] // $codec_map[$key] // ($key|ascii_downcase|gsub("[^a-z0-9]";""));
    $record + {schema:1, config:$config, removal_signatures:($config.removal_signatures // {}), input_ids:$inputs, retained_ids:$retained,
      selectors:$selectors, track_types:$types, source_flags:$flags,
      output_extension:$extension, track_order:$track_order,
      propedit_args:(if $config.category=="edit" then $args else [] end),
      merge_metadata_args:(if $config.category=="mux" then $args else [] end)} |
    .destination=(if $config.category=="mux" then (.source|sub("\\.[^.]+$";"."+$extension))
      elif $config.category=="edit" then .source else (.source|sub("/[^/]*$";"/Attachments")) end) |
    . as $job |
    .outputs=(if $config.category!="extract" then [.destination] else
      [if ($config.operations|index("1")) then
         $record.model.attachments[] | . as $a |
         if ($a.file_name|type)!="string" or ($a.file_name|length)==0 or
           ($a.file_name|test("[/\\\\]")) or $a.file_name=="." or $a.file_name==".."
         then error("unsafe attachment filename") else
           {kind:"attachment", id:($a.id|tostring), codec:null,
            path:($job.destination+"/"+$a.file_name)} end
       else empty end,
       $config.extract_ids[] as $id | $record.model.tracks[] | select((.id|tostring)==$id) |
       (.properties.codec_id // "") as $cid | codec_extension($cid) as $ext |
       if ($ext|length)==0 or ($ext|test("^[a-zA-Z0-9]+$")|not) then error("unknown extraction extension")
       else {kind:"track", id:$id, codec:$cid, path:($job.source|sub("\\.[^.]+$";""))+" - Track ["+$id+"]."+$ext} end]
      end) |
    .requested_metadata=[$choices[] as $choice | $config.settings|to_entries[] |
      select((.key|split(":")[0])==$choice) |
      {choice:$choice, original_id:(.key|split(":")[1]), value:.value,
       label:$registry[$choice+":label"], scope:$registry[$choice+":scope"], property:$registry[$choice+":property"]}] |
    .preview={title:(if ($config.settings|has("5:info")) then $config.settings["5:info"] else .model.title end),
      tracks:[$retained|to_entries[] | .key as $position | .value as $id |
        $record.model.tracks[] | select((.id|tostring)==$id) |
        {original_id:$id, final_position:($position+1), type:.type, codec:.properties.codec_id,
         name:(if ($config.settings|has("4:"+$id)) then $config.settings["4:"+$id] else (.properties.track_name // "") end),
         language:(if ($config.settings|has("3:"+$id)) then $config.settings["3:"+$id] else (.properties.language_ietf // .properties.language // "") end),
         forced:(if ($config.settings|has("1:"+$id)) then ($config.settings["1:"+$id]=="1") else .properties.forced_track end),
         default:(if ($config.settings|has("2:"+$id)) then ($config.settings["2:"+$id]=="1") else .properties.default_track end)}]}
  '
}

# Reload known job fields with NUL framing: empty arguments and trailing newlines
# survive. Queue consumers must pass a specific record, never use last-file data.
mkvutil_load_job() {
  local job="$1" key="" field="" value=""
  MKVUTIL_CURRENT_JOB=""
  _mkvutil_clear_plan_layout
  mkvutil_metadata_reset
  jq -e '.schema==1 and (.input_ids|type)=="array" and (.retained_ids|type)=="array" and
    (.selectors|type)=="object" and (.track_types|type)=="object" and (.source_flags|type)=="object" and
    (.config.settings|type)=="object" and (.propedit_args|type)=="array" and (.merge_metadata_args|type)=="array"' \
    <<< "$job" > /dev/null || return 1
  while IFS= read -r -d '' value; do MKVUTIL_INPUT_IDS+=("$value"); done < <(jq -j '.input_ids[]|.,"\u0000"' <<< "$job")
  while IFS= read -r -d '' value; do MKVUTIL_RETAINED_IDS+=("$value"); done < <(jq -j '.retained_ids[]|.,"\u0000"' <<< "$job")
  for key in selectors track_types source_flags settings; do
    while IFS= read -r -d '' field && IFS= read -r -d '' value; do
      case "$key" in
        selectors) MKVUTIL_PROPEDIT_SELECTORS[$field]="$value" ;;
        track_types) MKVUTIL_TRACK_TYPES[$field]="$value" ;;
        source_flags) MKVUTIL_SOURCE_FLAGS[$field]="$value" ;;
        settings) MKVUTIL_METADATA_SETTINGS[$field]="$value" ;;
      esac
    done < <(jq -j --arg key "$key" '(if $key=="settings" then .config.settings else .[$key] end)|to_entries[]|.key,"\u0000",.value,"\u0000"' <<< "$job")
  done
  while IFS= read -r -d '' value; do MKVUTIL_PROPEDIT_ARGS+=("$value"); done < <(jq -j '.propedit_args[]|.,"\u0000"' <<< "$job")
  while IFS= read -r -d '' value; do MKVUTIL_MERGE_METADATA_ARGS+=("$value"); done < <(jq -j '.merge_metadata_args[]|.,"\u0000"' <<< "$job")
  MKVUTIL_TRACK_ORDER="$(jq -r '.track_order' <<< "$job")" || return 1
  MKVUTIL_OUTPUT_EXTENSION="$(jq -r '.output_extension' <<< "$job")" || return 1
  MKVUTIL_FLAG_LAYOUT="$(_mkvutil_metadata_layout_rows)|${(j:,:)MKVUTIL_RETAINED_IDS}"
  MKVUTIL_CURRENT_JOB="$job"
}

# Validate every destination before offering Run. Same-source Edit/Mux is
# intentional; cross-job collisions, existing sidecars and other inputs reject.
mkvutil_check_destinations() {
  printf '%s\0' "$@" | python3 -c '
import json, os, sys, unicodedata
from pathlib import Path
try:
    jobs = [json.loads(record) for record in sys.stdin.buffer.read().split(b"\0") if record]
    def case_insensitive(source):
        alternate = source.with_name(source.name.swapcase())
        try:
            return os.path.samefile(source, alternate)
        except FileNotFoundError:
            return False
    def destination_key(path, source):
        # Use the nearest existing directory identity, plus pending components.
        # A letter-bearing existing source establishes case behavior read-only.
        parent = path.parent
        tail = [path.name]
        while not os.path.lexists(parent):
            tail.insert(0, parent.name)
            parent = parent.parent
        if not parent.is_dir():
            raise ValueError(f"Output parent is not a directory: {parent}")
        item = parent.stat()
        insensitive = case_insensitive(source)
        if item.st_dev != source.parent.stat().st_dev:
            # This uncommon redirected directory has no source-name probe on
            # its filesystem. Conservatively compare folded names on macOS.
            insensitive = sys.platform == "darwin"
        if insensitive:
            tail = [unicodedata.normalize("NFD", part).casefold() for part in tail]
        return item.st_dev, item.st_ino, tuple(tail)
    sources = {}
    for job in jobs:
        source = Path(job["source"])
        key = destination_key(source, source)
        if key in sources:
            raise ValueError(f"Duplicate source alias: {source}")
        sources[key] = source
    destinations = {}
    for job in jobs:
        source = Path(job["source"])
        source_key = destination_key(source, source)
        for output in job["outputs"]:
            path = Path(output["path"] if isinstance(output, dict) else output)
            key = destination_key(path, source)
            if key in destinations:
                raise ValueError(f"Destination collision or filename alias: {path}")
            destinations[key] = path
            if job["config"]["category"] != "extract" and key == source_key:
                continue
            if key in sources or os.path.lexists(path):
                raise ValueError(f"Destination already exists or is another source: {path}")
except (OSError, ValueError, KeyError, TypeError) as error:
    print(str(error), file=sys.stderr)
    sys.exit(1)
'
}

mkvutil_report_removal_skips() {
  local receipt=""
  for receipt in "$@"; do
    jq -r '
      "Skipped removal mismatch: \(.source)", "  Reference: \(.reference)",
      (.reasons[] | "  Original ID \(.original_id): \(.reason); expected=\(.expected|tojson) actual=\(.actual|tojson)")
    ' <<< "$receipt" || return 1
  done
}

_mkvutil_remove_scope_source() {
  local record="" file="$1"
  local -a remaining=()
  for record in "${MKVUTIL_SOURCES[@]}"; do
    [[ "$(jq -r '.source' <<< "$record")" == "$file" ]] || remaining+=("$record")
  done
  MKVUTIL_SOURCES=("${remaining[@]}")
}

# The scope pool survives automatic skips and Review/change. Only an explicit
# exclusion removes a source. Status 3 means an all-mismatch queue, with receipts
# still available; any other planning error requires the ordinary exclude policy.
mkvutil_plan_queue() {
  local record="" job="" file="" result=0
  local -a jobs=() scope=()
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_PROPEDIT_ARGS=()
  MKVUTIL_MERGE_METADATA_ARGS=()
  MKVUTIL_CURRENT_JOB=""
  for record in "${MKVUTIL_SOURCES[@]}"; do
    result=0
    job="$(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG")" || result=$?
    if (( result == 0 )); then
      jobs+=("$job")
      scope+=("$record")
    elif (( result == 3 )); then
      MKVUTIL_REMOVAL_SKIPS+=("$job")
      scope+=("$record")
    else
      file="$(jq -r '.source' <<< "$record")"
      print -u2 -r -- "Cannot plan source: $file"
      _mkvutil_exclude || { result=$?; return "$result"; }
      _mkvutil_remove_scope_source "$file"
    fi
  done
  MKVUTIL_SOURCES=("${scope[@]}")
  mkvutil_report_removal_skips "${MKVUTIL_REMOVAL_SKIPS[@]}" || return 1
  if (( ${#jobs} == 0 )); then
    (( ${#MKVUTIL_REMOVAL_SKIPS} > 0 )) && return 3
    print -u2 -r -- 'No valid jobs remain.'
    return 1
  fi
  mkvutil_check_destinations "${jobs[@]}" || return 1
  MKVUTIL_JOBS=("${jobs[@]}")
}

# Prepare a fresh scope from mismatch receipts only. Pending eligible jobs may
# not be discarded. G02's post-execution controller can archive/clear those jobs
# before calling this helper; configuration and confirmation remain separate.
mkvutil_prepare_skipped_subset() {
  local receipt="" file="" record="" result=0
  local -a paths=() sources=()
  (( ${#MKVUTIL_JOBS} == 0 && ${#MKVUTIL_REMOVAL_SKIPS} > 0 )) || {
    print -u2 -r -- 'Skipped-subset preparation requires mismatch skips and no pending eligible jobs.'; return 1;
  }
  for receipt in "${MKVUTIL_REMOVAL_SKIPS[@]}"; do
    jq -e '.kind=="removal-mismatch" and (.reasons|length)>0 and (.source|type)=="string"' <<< "$receipt" > /dev/null || return 1
    file="$(jq -r '.source' <<< "$receipt")" || return 1
    paths+=("$file")
  done
  MKVUTIL_REMOVAL_SKIP_HISTORY+=("${MKVUTIL_REMOVAL_SKIPS[@]}")
  MKVUTIL_CONFIG=""
  MKVUTIL_CURRENT_JOB=""
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_SOURCES=()
  MKVUTIL_SELECTED_FILES=("${paths[@]}")
  mkvutil_metadata_reset
  _mkvutil_clear_plan_layout
  for file in "${paths[@]}"; do
    if record="$(mkvutil_capture_source "$file")"; then
      sources+=("$record")
    else
      print -u2 -r -- "Fresh skipped-source inspection failed: $file"
      _mkvutil_exclude || { result=$?; return "$result"; }
    fi
  done
  (( ${#sources} > 0 )) || { print -u2 -r -- 'No valid skipped sources remain.'; return 1; }
  MKVUTIL_SOURCES=("${sources[@]}")
  print -r -- "Fresh skipped-subset reference: $(jq -r '.source' <<< "${MKVUTIL_SOURCES[1]}")"
}

mkvutil_cancel_status() {
  (( ${#MKVUTIL_REMOVAL_SKIPS} == 0 && ${#MKVUTIL_REMOVAL_SKIP_HISTORY} == 0 ))
}

mkvutil_review_menu() {
  print -r -- $'1) Review/change configured operations\n2) Preview resulting tracks and outputs'
  if (( ${#MKVUTIL_JOBS} > 0 )); then
    print -r -- '3) Run batch'
  elif (( ${#MKVUTIL_REMOVAL_SKIPS} > 0 )); then
    print -r -- '4) Prepare a fresh batch for mismatch-skipped files'
  fi
  print -r -- '0) Cancel'
}

mkvutil_preview_jobs() {
  local job=""
  if (( ${#MKVUTIL_REMOVAL_SKIP_HISTORY} > 0 )); then
    print -r -- 'Previous skipped-scope receipts (execution unresolved):'
    mkvutil_report_removal_skips "${MKVUTIL_REMOVAL_SKIP_HISTORY[@]}" || return 1
  fi
  mkvutil_report_removal_skips "${MKVUTIL_REMOVAL_SKIPS[@]}" || return 1
  for job in "${MKVUTIL_JOBS[@]}"; do
    jq -r '
      "Source: \(.source)", "Category: \(.config.category)", "Destination: \(.destination)",
      "Title: \(.preview.title // "")",
      (.config.removed_ids[] | "Original ID \(.): removed"),
      (.requested_metadata[] | "Metadata: \(.label) — \(.original_id) \(.property)=\(.value|tojson)"),
      (.preview.tracks[] | "Original ID \(.original_id) => final position \(.final_position): \(.type) [\(.codec)] name=\(.name|tojson) language=\(.language|tojson) default=\(.default) forced=\(.forced)"),
      (.outputs[] | select(type=="object") | "Extract \(.kind) \(.id): \(.path)")
    ' <<< "$job" || return 1
  done
}

print_help() {
  print -r -- "Usage: ${SCRIPT_NAME} [working_directory]"
  print -r -- "       ${SCRIPT_NAME} --help"
  print -r -- $'\nMatroska categories:\n  1) Matroska Edit — flags, languages, names and title\n  2) Matroska Mux — remove/reorder with optional metadata\n  3) Matroska Extract — attachments and selected tracks\n  0) Exit\n\nSubmenus accept a single choice, comma lists or ranges. Select targets once,\nconfigure all operations, then review/change, preview, Run or Cancel.\nSupports .mkv, .mka, .mks and .mk3d. Execution is pending implementation.'
}

mkvutil_main() {
  local directory="$PWD" category="" choice="" operations="" review="" result=0
  MKVUTIL_SOURCES=()
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_REMOVAL_SKIP_HISTORY=()
  MKVUTIL_CONFIG=""
  MKVUTIL_CURRENT_JOB=""
  mkvutil_metadata_reset
  (( $# <= 1 )) || { print -u2 -r -- "Usage: ${SCRIPT_NAME} [working_directory]"; return 1; }
  case "${1-}" in
    --help|-h) print_help; return 0 ;;
    -*) print -u2 -r -- "Usage: ${SCRIPT_NAME} [working_directory]"; return 1 ;;
    '') ;;
    *) directory="$1" ;;
  esac
  local resolved_directory=""
  resolved_directory="$(mkvutil_resolve_directory "$directory")" || return 1
  cd "$resolved_directory" || return 1
  print -r -- "Current Work Dir: $directory"
  mkvutil_scan_files "$PWD" || {
    print -r -- 'Please check if there are Matroska files (.mkv, .mka, .mks, .mk3d) present before running this script again.'; return 1;
  }
  print -r -- $'1) Matroska Edit\n2) Matroska Mux\n3) Matroska Extract\n0) Exit'
  _mkvutil_read 'Category: ' || return 0
  case "$REPLY" in
    0) return 0 ;;
    1) category=edit ;;
    2) category=mux ;;
    3) category=extract ;;
    *) print -u2 -r -- 'Invalid category.'; return 1 ;;
  esac
  mkvutil_category_menu "$category" || return 1
  _mkvutil_read 'Operations (single/comma/range): ' || return 0
  [[ "$REPLY" != 0 ]] || return 0
  operations="$(mkvutil_category_choices "$category" "$REPLY")" || return 1
  mkvutil_select_files || { result=$?; (( result == 2 )) && return 0; return "$result"; }
  mkvutil_inspect_sources || { result=$?; (( result == 2 )) && return 0; return "$result"; }
  while true; do
    mkvutil_configure_category "$category" "$operations" || { result=$?; (( result == 2 )) && { mkvutil_cancel_status; return $?; }; return "$result"; }
    result=0
    mkvutil_plan_queue || result=$?
    (( result == 0 || result == 3 )) || { (( result == 2 )) && { mkvutil_cancel_status; return $?; }; return "$result"; }
    while true; do
      mkvutil_review_menu
      _mkvutil_read 'Review choice: ' || { mkvutil_cancel_status; return $?; }
      review="$REPLY"
      case "$review" in
        0) print -r -- 'Cancelled; no media changes.'; mkvutil_cancel_status; return $? ;;
        1)
          mkvutil_category_menu "$category" || return 1
          _mkvutil_read 'Replacement operations: ' || { mkvutil_cancel_status; return $?; }
          operations="$(mkvutil_category_choices "$category" "$REPLY")" || return 1
          break ;;
        2) mkvutil_preview_jobs || return 1 ;;
        3)
          (( ${#MKVUTIL_JOBS} > 0 )) || { print -u2 -r -- 'No eligible jobs; change settings or prepare the skipped subset.'; continue; }
          print -u2 -r -- 'Execution is not available at this implementation checkpoint; no media changes.'; return 1 ;;
        4)
          mkvutil_prepare_skipped_subset || return 1
          category=mux
          mkvutil_category_menu "$category" || return 1
          _mkvutil_read 'New skipped-subset operations: ' || return 1
          operations="$(mkvutil_category_choices "$category" "$REPLY")" || return 1
          break ;;
        *) print -u2 -r -- 'Invalid review choice.'; return 1 ;;
      esac
    done
  done
}

# Sourcing defines helpers without launching the real category entrypoint.
if [[ "$ZSH_EVAL_CONTEXT" != *:file ]]; then
  mkvutil_main "$@"
  exit $?
fi
