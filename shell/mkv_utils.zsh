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
  [[ -d "$candidate/.git" ]] && return 0
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

print_help() {
  cat <<EOF
Usage: ${SCRIPT_NAME} [working_directory]
       ${SCRIPT_NAME} --help

Interactive Matroska utility script for metadata edits, extraction, and track operations.

Arguments:
  --help, -h            Show this help page and exit.
  working_directory     Directory to scan instead of the current directory.

Menu options:
  1) Set flag-forced for tracks
     Set the forced flag on selected track IDs across one or more Matroska files.

  2) Set flag-default for tracks
     Set the default flag on selected track IDs across one or more Matroska files.

  3) Set language for tracks
     Change the language field on selected track IDs.

  4) Set name for tracks
     Rename selected track IDs.

  5) Set title for MK file
     Set or clear the container title on one or more files.

  6) Extract all attachments from MK files
     Extract every attachment into an Attachments directory.

  7) Mass Remove tracks for multi-MK files
     Remove selected track IDs and remux the remaining tracks.

  8) Mass Re-order tracks for multi-MK files
     Apply a new mkvmerge track order to selected files.

  9) Extract Tracks for multi-MK files
     Extract selected track IDs from one or more files.

Notes:
  - With no working_directory argument, the script uses the current directory.
  - The script requires Matroska files in the target directory before the menu can run.
EOF
}

# Sourcing this file defines its helpers without entering the interactive CLI.
if [[ "$ZSH_EVAL_CONTEXT" != *:file ]]; then
display_dir="$(pwd)"
working_dir_set=false

while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    -*)
      echo "Usage: ${SCRIPT_NAME} [working_directory]" >&2
      exit 1
      ;;
    *)
      if [ "$working_dir_set" = true ]; then
        echo "Usage: ${SCRIPT_NAME} [working_directory]" >&2
        exit 1
      fi
      display_dir="$1"
      working_dir_set=true
      ;;
  esac
  shift
done

current_dir="$display_dir"
if [ ! -d "$current_dir" ]; then
  echo "Error: Working directory not found: $current_dir" >&2
  exit 1
fi

cd "$current_dir" || exit 1
current_dir="$(pwd)"
echo "Current Work Dir: $display_dir"

# Collect Matroska files in current dir
matroska_files=()
for ext in mkv mka mks mk3d; do
  # Use (N) glob qualifier to suppress nomatch errors
  for f in "$current_dir"/*.$ext(N); do
    [ -e "$f" ] && matroska_files+=("$f")
  done
done
if [ ${#matroska_files[@]} -eq 0 ]; then
  echo "Please check if there are Matroska files (.mkv, .mka, .mks, .mk3d) present before running this script again."
  exit 1
fi

print -n "Select an option:
1) Set flag-forced for tracks
2) Set flag-default for tracks
3) Set language for tracks
4) Set name for tracks
5) Set title for MK file
6) Extract all attachments from MK files
7) Mass Remove tracks for multi-MK files
8) Mass Re-order tracks for multi-MK files
9) Extract Tracks for multi-MK files
Enter choice: "
read choice

while [[ -z "$choice" || "$choice" != [1-9] ]]; do
  echo "Invalid choice. Please enter a number from 1 to 9."
  printf "Enter choice: "
  read choice
done

if [ "$choice" = "1" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply forced-flag edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

  # Apply forced-flag edits (prompting per track)
  set_flag_forced_tracks "$track_ids"

elif [ "$choice" = "2" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply default-flag edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

  # Apply default-flag edits (prompting per track)
  set_flag_default_tracks "$track_ids"
  
elif [ "$choice" = "3" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply language edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

  # Perform language setting on selected files (prompting per track)
  set_language_tracks "$track_ids"
  
elif [ "$choice" = "4" ]; then
  # Prompt for multi-file or single-file selection
  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to apply name edits:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for first target
  display_track_info "${targets[1]}"

  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to edit (e.g., 0,1 or 1-2): ")

	# Perform renaming on selected files
	rename_tracks "$track_ids"

		elif [ "$choice" = "5" ]; then
		  # Prompt for multi-file or single-file selection
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

	  # Determine target files
	  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
	    echo "Select Matroska file(s) to apply title edits:"
	    typeset -a targets
	    targets=()
	    while IFS= read -r file; do
	      targets+=("$file")
	    done < <(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
	      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
	    if [ ${#targets[@]} -eq 0 ]; then
	      echo "No target files selected. Exiting."
	      exit 1
	    fi
	  else
	    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
	    source_file=$(find . -maxdepth 1 -type f \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
	      | fzf --height 40% --reverse --border)
	    if [ -z "$source_file" ]; then
	      echo "No file selected. Exiting."
	      exit 1
	    fi
	    typeset -a targets
	    targets=("$source_file")
	  fi

	  printf "Title (empty to unset): "
	  read title

	  set_mkv_title "$title"

	elif [ "$choice" = "6" ]; then
	  echo "Select Matroska file(s) to extract attachments:"
	  typeset -a targets
	  targets=()
	  while IFS= read -r file; do
	    targets+=( "$file" )
  done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")

  if [ ${#targets[@]} -eq 0 ]; then
    echo "No target files selected. Exiting."
    exit 1
  fi
  # Prepare output directory for attachments
  mkdir -p "Attachments"

  for file in "${targets[@]}"; do
    attachment_count=$(count_attachments "$file")
    echo "Processing $file: Extracting $attachment_count attachments..."

    if [ "$attachment_count" -gt 0 ]; then
      # Compute attachment IDs
      attachment_ids=( $(seq 1 $attachment_count) )
      # Determine absolute path to source file
      # Remove leading './' if present
      relpath=${file#./}
      filepath="$current_dir/$relpath"
      # Extract into Attachments directory
      (cd "Attachments" && mkvextract attachments "$filepath" "${attachment_ids[@]}")
    fi
	  done
	  echo "Attachments extraction completed."

		elif [ "$choice" = "7" ]; then
		  # --- Choice 7: Mass Remove tracks ---
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Build fzf args
  fzf_args=(--height 40% --reverse --border --prompt="Select file(s) >")
  [[ $MULTI_FILE_SELECTION == "Y" ]] && fzf_args+=(--multi)

  # Single fzf to pick targets
  targets=()
  while IFS= read -r f; do
    targets+=("$f")
  done < <(
    find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf "${fzf_args[@]}"
  )
  [ ${#targets[@]} -eq 0 ] && { echo "No files selected. Exiting."; exit 1; }

  # Show JSON-based track list for first file
  source_file=${targets[1]}
  source_mkv_json=""
  source_track_rows=""
  if ! source_mkv_json="$(mkvmerge -J "$source_file" < /dev/null)" \
    || ! source_track_rows="$(collect_tracks_for_remux "$source_file" "$source_mkv_json")"; then
    echo "Error on ${source_file}; track inspection failed; file unchanged."
    exit 1
  fi
  if ! display_track_info "$source_file" "$source_mkv_json"; then
    echo "Error on ${source_file}; track inspection failed; file unchanged."
    exit 1
  fi

  # Ask which track IDs to remove
  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to remove (e.g., 0,1 or 1-2): ")

  # Build exclude_ids[] by splitting on commas and ranges
  exclude_ids=()
  for tok in ${(s:,:)track_ids}; do
    if [[ $tok == *-* ]]; then
      start=${tok%-*}; end=${tok#*-}
      for ((i=start; i<=end; i++)); do
        exclude_ids+=($i)
      done
    else
      exclude_ids+=($tok)
    fi
  done
  # sort & dedupe
  exclude_ids=($(printf "%s\n" "${exclude_ids[@]}" | sort -n | uniq))

  echo "Removing tracks: ${exclude_ids[*]}"

  # Helper to filter out excluded IDs
  filter_keep() {
    local arr=("$@") keep=()
    for id in "${arr[@]}"; do
      [[ ! " ${exclude_ids[*]} " == *" $id "* ]] && keep+=($id)
    done
    echo "${keep[@]}"
  }

  # Apply removal to each file
  files_count=${#targets[@]}
  file_index=1
  total_processing_seconds=0
  successful_files=0
  failed_files=()
  queue_start=$SECONDS
  if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
    echo "Total Files Count: $files_count"
  fi
  for target in "${targets[@]}"; do
    typeset -a video_keep audio_keep subtitle_keep raw_tracks
    typeset -A seen_track_ids
    typeset track_rows="" row="" track_type="" track_id="" track_rows_valid="" excluded_id="" requested_ids_valid=""
    video_keep=()
    audio_keep=()
    subtitle_keep=()
    seen_track_ids=()
    track_rows=""
    if [[ "$target" == "$source_file" ]]; then
      track_rows="$source_track_rows"
    elif ! track_rows="$(collect_tracks_for_remux "$target")"; then
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on ${target}; track inspection failed; file unchanged."
      fi
      file_index=$((file_index + 1))
      continue
    fi
    raw_tracks=("${(@f)track_rows}")
    track_rows_valid=true

    for row in "${raw_tracks[@]}"; do
      [[ -z "$row" ]] && continue
      track_type="${row%%$'\t'*}"
      track_id="${row#*$'\t'}"

      if ! [[ "$track_id" == <-> ]]; then
        track_rows_valid=false
        break
      fi
      if [[ -n "${seen_track_ids[$track_id]-}" ]]; then
        track_rows_valid=false
        break
      fi
      seen_track_ids[$track_id]=1

      case "$track_type" in
        video) video_keep+=("$track_id") ;;
        audio) audio_keep+=("$track_id") ;;
        subtitles) subtitle_keep+=("$track_id") ;;
        *) track_rows_valid=false; break ;;
      esac
    done

    if [[ "$track_rows_valid" != true ]]; then
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on ${target}; track inspection failed; file unchanged."
      fi
      file_index=$((file_index + 1))
      continue
    fi

    requested_ids_valid=true
    for excluded_id in "${exclude_ids[@]}"; do
      if [[ -z "${seen_track_ids[$excluded_id]-}" ]]; then
        requested_ids_valid=false
        break
      fi
    done
    if [[ "$requested_ids_valid" != true ]]; then
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on ${target}; requested Track ID not found; file unchanged."
      fi
      file_index=$((file_index + 1))
      continue
    fi

    video_keep=($(filter_keep "${video_keep[@]}"))
    audio_keep=($(filter_keep "${audio_keep[@]}"))
    subtitle_keep=($(filter_keep "${subtitle_keep[@]}"))

    if [[ ${#video_keep[@]} -eq 0 && ${#audio_keep[@]} -eq 0 && ${#subtitle_keep[@]} -eq 0 ]]; then
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on ${target}; no tracks to keep after removal; file unchanged."
      fi
      file_index=$((file_index + 1))
      continue
    fi

    base=${target##*/}; base=${base%.*}; ext=${target##*.}
    [[ ${#video_keep[@]} -eq 0 ]] && out_ext=mka || out_ext=$ext
    tmp="${base}_temp.${out_ext}"

    cmd=(mkvmerge -o "$tmp")
    [[ ${#video_keep[@]} -gt 0 ]] \
      && cmd+=(--video-tracks "$(IFS=,; echo "${video_keep[*]}")") \
      || cmd+=(--no-video)
    [[ ${#audio_keep[@]} -gt 0 ]] \
      && cmd+=(--audio-tracks "$(IFS=,; echo "${audio_keep[*]}")") \
      || cmd+=(--no-audio)
    [[ ${#subtitle_keep[@]} -gt 0 ]] \
      && cmd+=(--subtitle-tracks "$(IFS=,; echo "${subtitle_keep[*]}")") \
      || cmd+=(--no-subtitles)
    cmd+=("$target")

    echo "Executing: ${cmd[*]}"
    remux_start=$SECONDS
    if "${cmd[@]}"; then
      remux_duration=$((SECONDS - remux_start))
      mv "$tmp" "${base}.${out_ext}"
      echo "Replaced: ${base}.${out_ext}"
      [[ "$out_ext" != "$ext" ]] && rm -f "$target" && echo "Removed original: $target"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        total_processing_seconds=$((total_processing_seconds + remux_duration))
        successful_files=$((successful_files + 1))
        files_remaining=$((files_count - file_index))
        estimated_seconds=$(((total_processing_seconds * files_remaining + successful_files / 2) / successful_files))
        echo "${target:t}"
        echo "  Processed In: $(format_duration "$remux_duration")"
        echo "  Files Done: $successful_files"
        echo "  Files Remaining: $files_remaining"
        echo "  Estimated Time Remaining: $(format_duration "$estimated_seconds")"
      fi
    else
      rm -f "$tmp"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on $target; cleaning up."
      fi
	    fi
    file_index=$((file_index + 1))
	  done
  if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
    echo "Total Files Done: $successful_files"
    if [[ ${#failed_files[@]} -gt 0 ]]; then
      printf "Failed Files: %02d\n" ${#failed_files[@]}
      for failed_file in "${failed_files[@]}"; do
        echo "  $failed_file"
      done
    fi
    echo "Elapsed Time: $(format_duration "$((SECONDS - queue_start))")"
  fi

		elif [ "$choice" = "8" ]; then
		  # --- Choice 8: Mass Re-order tracks ---
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  fzf_args=(--height 40% --reverse --border --prompt="Select file(s) >")
  [[ $MULTI_FILE_SELECTION == "Y" ]] && fzf_args+=(--multi)

  targets=()
  while IFS= read -r f; do
    targets+=("$f")
  done < <(
    find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
    | fzf "${fzf_args[@]}"
  )
  [ ${#targets[@]} -eq 0 ] && { echo "No files selected. Exiting."; exit 1; }

  source_file=${targets[1]}
  display_track_info "$source_file"

  track_order=$(prompt_for_track_order "Enter the new track order (e.g., 0:0,0:1,0:2,…): ")

  files_count=${#targets[@]}
  file_index=1
  total_processing_seconds=0
  successful_files=0
  failed_files=()
  queue_start=$SECONDS
  for target in "${targets[@]}"; do
    base=${target##*/}; base=${base%.*}; ext=${target##*.}
    tmp="${base}_temp.${ext}"
    cmd=(mkvmerge -o "$tmp" --track-order "$track_order" "$target")

    if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 && $file_index -eq 1 ]]; then
      echo "Total Files Count: $files_count"
    fi
    echo "Executing: ${cmd[*]}"
    remux_start=$SECONDS
    if "${cmd[@]}"; then
      remux_duration=$((SECONDS - remux_start))
      mv "$tmp" "${base}.${ext}"
      echo "Replaced: ${base}.${ext}"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        total_processing_seconds=$((total_processing_seconds + remux_duration))
        successful_files=$((successful_files + 1))
        files_remaining=$((files_count - file_index))
        estimated_seconds=$(((total_processing_seconds * files_remaining + successful_files / 2) / successful_files))
        echo "${target:t}"
        echo "  Processed In: $(format_duration "$remux_duration")"
        echo "  Files Done: $successful_files"
        echo "  Files Remaining: $files_remaining"
        echo "  Estimated Time Remaining: $(format_duration "$estimated_seconds")"
      fi
    else
      rm -f "$tmp"
      if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
        failed_files+=("${target:t}")
        echo "Failed: ${target:t}"
      else
        echo "Error on $target; cleaning up."
      fi
    fi
    file_index=$((file_index + 1))
	  done
  if [[ $MULTI_FILE_SELECTION == "Y" && $files_count -gt 1 ]]; then
    echo "Total Files Done: $successful_files"
    if [[ ${#failed_files[@]} -gt 0 ]]; then
      printf "Failed Files: %02d\n" ${#failed_files[@]}
      for failed_file in "${failed_files[@]}"; do
        echo "  $failed_file"
      done
    fi
    echo "Elapsed Time: $(format_duration "$((SECONDS - queue_start))")"
  fi
	  
	# --- Choice 9: Extract Tracks ---
	elif [ "$choice" = "9" ]; then
		  # Prompt for multi-file or single-file selection
		  MULTI_FILE_SELECTION=$(prompt_yes_no "Enable multi-file target selection? (Y/N) [N]: " "N")

  # Determine target files
  if [[ "$MULTI_FILE_SELECTION" = "Y" ]]; then
    echo "Select Matroska file(s) to extract tracks:"
    typeset -a targets
    targets=()
    while IFS= read -r file; do
      targets+=("$file")
    done < <(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --multi --height 40% --reverse --border --prompt="Select files > ")
    if [ ${#targets[@]} -eq 0 ]; then
      echo "No target files selected. Exiting."
      exit 1
    fi
  else
    printf "Select the source Matroska file (.mkv, .mka, .mks, .mk3d):\n"
    source_file=$(find . -maxdepth 1 -type f \
      \( -name "*.mkv" -o -name "*.mka" -o -name "*.mks" -o -name "*.mk3d" \) \
      | fzf --height 40% --reverse --border)
    if [ -z "$source_file" ]; then
      echo "No file selected. Exiting."
      exit 1
    fi
    typeset -a targets
    targets=("$source_file")
  fi

  # Display track info for the first target
  source_file=${targets[1]}
  display_track_info "$source_file"

  # Ask once for which tracks to extract
  track_ids=$(prompt_for_track_ids "Enter the Track ID(s) to extract (e.g., 0,1 or 1-2): ")

  # Loop over all selected files
  for source_file in "${targets[@]}"; do
    echo "→ Extracting tracks ${track_ids} from $source_file"
    extract_tracks "$track_ids"
  done

else
  echo "Invalid choice."
fi
fi
