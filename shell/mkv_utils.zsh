#!/usr/bin/env zsh

# Required third-party tools:
# - mkvmerge, mkvextract, mkvpropedit: Matroska identification, remuxing, extraction and metadata edits
# - jq: for processing JSON output from mkvmerge (-J)
# - fzf: for interactive file selection via fuzzy finding
# - python3: for inline Python scripting support
# - pymkv2 distribution and pymkv module: codec-to-extension mapping
# The script reuses the repository .venv when present, including a symlinked venv.
# The runtime is verified with installed MKVToolNix v93.0.

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

# Native PCM IDs need the canonical library map key; other native prefixes
# translate generically (A_TRUEHD -> TRUEHD, S_VOBSUB -> VOBSUB, etc.).
typeset -gA MKVUTIL_CODEC_ALIASES=(A_PCM/INT/LIT PCM A_PCM/FLOAT/IEEE PCM)

format_duration() {
  local total_seconds="$1"
  printf "%02d:%02d:%02d" \
    $((total_seconds / 3600)) \
    $(((total_seconds % 3600) / 60)) \
    $((total_seconds % 60))
}

# A cached view is shared by listings and per-value metadata context. Native IDs
# remain source IDs; only the final Mux view projects dense output positions.
_mkvutil_track_view() {
  local raw="$1" removed="${2-}" final_ids="${3-}" mode="${4:-source}"
  jq -ec --arg removed "$removed" --arg final "$final_ids" --arg mode "$mode" '
    def row($id):
      (if $id==null then "Track:" else "Track ID \($id):" end) + " \(.type) (\(.properties.codec_id))"
      + (if (.properties.track_name // "")!="" then " [\(.properties.track_name)]" else "" end)
      + (if (.properties.language // .properties.language_ietf // "")!="" then
          " [\(.properties.language // .properties.language_ietf)]" else "" end);
    .tracks as $tracks | ($removed|split(",")|map(select(length>0))) as $removed |
    [$tracks|to_entries[] | .key as $position | .value as $track |
      {source_id:($track.id|tostring),source_position:$position,track:$track,
       dropped:(($removed|index($track.id|tostring))!=null)}] as $rows |
    (if $final=="" then [$rows[]|select(.dropped|not)|.source_id]
     else $final|split(",") end) as $ids |
    if ($mode!="source" and $mode!="output") or
       ($ids|length)!=([$rows[]|select(.dropped|not)]|length) or
       ($ids|unique|length)!=($ids|length) or
       ($ids|sort)!=([$rows[]|select(.dropped|not)|.source_id]|sort)
    then error("invalid track projection") else . end |
    (reduce $rows[] as $row ({rows:[],next:0};
      if $mode=="source" or $row.dropped then .rows+=[$row]
      else .next as $next | .rows+=[($rows[]|select(.source_id==$ids[$next]))] | .next+=1 end) | .rows) as $view |
    [$view[] | . as $row |
      (if .dropped then null elif $mode=="output" then ($ids|index($row.source_id)|tostring) else .source_id end) as $id |
      . + {display_id:$id,moved:($mode=="output" and (.dropped|not) and
             ($ids|index($row.source_id))!=.source_position),
           row:(.track|row($id))} | del(.track)]
  ' <<< "$raw"
}

_mkvutil_track_colours() {
  MKVUTIL_TRACK_RED="" MKVUTIL_TRACK_YELLOW=""
  if [[ -t 1 && -n "${TERM-}" && "$TERM" != dumb && -z "${NO_COLOR-}" ]]; then
    if [[ "$TERM" == *256color* ]]; then
      MKVUTIL_TRACK_RED=$'\033[38;5;203m'
      MKVUTIL_TRACK_YELLOW=$'\033[38;5;220m'
    else
      MKVUTIL_TRACK_RED=$'\033[91m'
      MKVUTIL_TRACK_YELLOW=$'\033[33m'
    fi
  fi
}

_mkvutil_render_track_view() {
  jq -r --arg red "${2-}" --arg yellow "${3-}" --arg selected "${4-*}" '
    .[] | .source_id as $source |
    (if .dropped then $red
     elif .moved and ($selected=="*" or ($selected|split(",")|index($source))!=null)
     then $yellow else "" end) as $colour |
    if $colour=="" then .row else $colour+.row+"\u001b[0m" end
  ' <<< "$1"
}

display_track_info() {
  local source_file="$1" mkv_json="${2-}" view=""
  if (( $# < 2 )); then mkv_json="$(mkvmerge -J "$source_file" < /dev/null)" || return 1; fi
  view="$(_mkvutil_track_view "$mkv_json" "${3-}" "${4-}" "${5:-source}")" || return 1
  _mkvutil_track_colours
  print -r -- '-----------------------  mkvmerge JSON track listing -----------------------'
  _mkvutil_render_track_view "$view" "$MKVUTIL_TRACK_RED" "$MKVUTIL_TRACK_YELLOW"
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

  # Spaces may surround separators, but must never join two numeric tokens.
  [[ ! "$selection" =~ '[0-9][[:space:]]+[0-9]' ]] || return 1
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

  if [[ -n "${removed_input//[[:space:]]/}" ]]; then
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

  [[ ! "$order_input" =~ '[0-9][[:space:]]+[0-9]' ]] || return 1
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
  local result=0 owns_indicator=0
  if [[ -z "$MKVUTIL_INDICATOR_PID" ]]; then
    _mkvutil_indicator_start Working || return 1
    [[ -z "$MKVUTIL_INDICATOR_PID" ]] || owns_indicator=1
  fi
  {
    _mkvutil_clear_plan_layout
    _mkvutil_plan_layout_build "$@" || result=$?
  } always {
    (( ! owns_indicator )) || _mkvutil_indicator_stop
  }
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
# Native v93 parser equivalence verified with normalization disabled. Keep
# this deliberately narrow: unknown preferred-value rewrites remain unproven.
typeset -gA MKVUTIL_LANGUAGE_NATIVE_ALIASES=(i-klingon 'tlh|und')
# Keys are CHOICE:ORIGINAL_TID; container settings use CHOICE:info. An existing
# key with an empty value explicitly clears a name/title; a missing key is idle.
typeset -gA MKVUTIL_METADATA_SETTINGS=()
typeset -gA MKVUTIL_SOURCE_FLAGS=()
typeset -g MKVUTIL_FLAG_LAYOUT=""
typeset -ga MKVUTIL_PROPEDIT_ARGS=()
typeset -ga MKVUTIL_MERGE_METADATA_ARGS=()

_mkvutil_metadata_define() {
  (( $# == 11 )) || return 1
  local choice="$1" field="" key="" i=0
  local -a fields=(label scope prompt default validator property merge snapshot json json_ietf)
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

_mkvutil_metadata_define 1 'Set flag-forced for tracks' track 'Forced (0/1) [0]: ' 0 boolean flag-forced --forced-display-flag forced_track forced_track ''
_mkvutil_metadata_define 2 'Set flag-default for tracks' track 'Default (0/1) [1]: ' 1 boolean flag-default --default-track-flag default_track default_track ''
_mkvutil_metadata_define 3 'Set language for tracks' track 'Language: ' '' language language --language '' language language_ietf
_mkvutil_metadata_define 4 'Set name for tracks' track 'Track name: ' '' text name --track-name '' track_name ''
_mkvutil_metadata_define 5 'Set file title' container 'Title [clear]: ' '' text title --title '' title ''

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
    for field in label scope prompt default validator property merge snapshot json json_ietf; do
      key="${choice}:$field"
      (( ${+MKVUTIL_METADATA_REGISTRY[$key]} )) || return 1
      case "$field" in
        default|snapshot|json_ietf) ;;
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
    [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:json]}" =~ '^[a-z][a-z_]*$' ]] || return 1
    if [[ "$validator" == language ]]; then
      [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:json_ietf]}" =~ '^[a-z][a-z_]*$' ]] || return 1
    fi
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
  if [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" == language ]]; then
    local validation=0
    _mkvutil_indicator_start Working || return 1
    {
      _mkvutil_metadata_value_valid language "$value" || validation=$?
    } always {
      _mkvutil_indicator_stop
    }
    (( validation == 0 )) || return 1
  else
    _mkvutil_metadata_value_valid "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" "$value" || return 1
  fi
  MKVUTIL_METADATA_SETTINGS[${choice}:$target]="$value"
}

# Modes: independent targets per choice, shared Edit targets, or explicit Mux IDs.
_mkvutil_metadata_collect() {
  setopt localtraps
  trap 'MKVUTIL_INTERRUPTED=1; return 2' INT TERM
  local choices="" choice="" selection="" targets_csv="" target="" value=""
  local mode="${2:-independent}" preset="${3-}" shared_targets="" projection="${4-}" context="${5-}"
  local domain="${(j:,:)MKVUTIL_RETAINED_IDS}" display_id="" context_id="" context_row=""
  local -a chosen_targets=() output_ids=()
  local -A output_sources=() source_outputs=() context_rows=()
  if [[ -n "$projection" ]]; then
    [[ "$projection" == "${(j:,:)MKVUTIL_RETAINED_IDS}" ]] || return 1
    local position=0
    for target in "${MKVUTIL_RETAINED_IDS[@]}"; do
      output_ids+=("$position")
      output_sources[$position]="$target"
      source_outputs[$target]="$position"
      (( position+=1 ))
    done
    domain="${(j:,:)output_ids}"
  fi
  if [[ -n "$context" ]]; then
    jq -e 'type=="array" and all(.[]; (.source_id|type)=="string" and (.row|type)=="string")' <<< "$context" >/dev/null || return 1
    while IFS= read -r -d '' context_id && IFS= read -r -d '' context_row; do
      context_rows[$context_id]="$context_row"
    done < <(jq -j '.[]|select(.dropped|not)|.source_id,"\u0000",.row,"\u0000"' <<< "$context")
  fi
  mkvutil_metadata_validate_registry || return 1
  choices="$(mkvutil_expand_ids "$1" "${(j:,:)MKVUTIL_METADATA_IDS}")" || return 1
  case "$mode" in
    independent|shared) ;;
    preset)
      targets_csv="$(mkvutil_expand_ids "$preset" "${(j:,:)MKVUTIL_RETAINED_IDS}")" || return 1
      [[ "$targets_csv" == "$preset" ]] || return 1
      shared_targets="$targets_csv" ;;
    *) return 1 ;;
  esac
  _mkvutil_indicator_stop
  print -u2 -r -- 'e) Back'
  for choice in "${(@s:,:)choices}"; do
    chosen_targets=(info)
    if [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:scope]}" == track ]]; then
      if [[ "$mode" == independent || -z "$shared_targets" ]]; then
        print -u2 -r -- "${MKVUTIL_METADATA_REGISTRY[${choice}:label]}"
        _mkvutil_read_track_ids 'Track IDs: ' "$domain" || return $?
        targets_csv="$REPLY"
        if [[ -n "$projection" ]]; then
          chosen_targets=()
          for display_id in "${(@s:,:)targets_csv}"; do chosen_targets+=("${output_sources[$display_id]}"); done
          targets_csv="${(j:,:)chosen_targets}"
        fi
        [[ "$mode" != shared ]] || shared_targets="$targets_csv"
      else
        targets_csv="$shared_targets"
      fi
      chosen_targets=("${(@s:,:)targets_csv}")
    fi
    for target in "${chosen_targets[@]}"; do
      while true; do
        _mkvutil_indicator_stop
        (( ! MKVUTIL_INTERRUPTED )) || return 2
        if [[ "$target" != info ]]; then
          if [[ -n "${context_rows[$target]-}" ]]; then print -u2 -r -- "${context_rows[$target]}"
          elif [[ -n "$projection" ]]; then printf 'Track ID %s — ' "${source_outputs[$target]}" >&2
          else printf 'Original track ID %s — ' "$target" >&2; fi
        fi
        printf '%s' "${MKVUTIL_METADATA_REGISTRY[${choice}:prompt]}" >&2
        IFS= read -r value || return 2
        case "$value" in e|E) return 4 ;; esac
        if [[ "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" == text ]]; then
          case "$value" in '\e') value=e ;; '\E') value=E ;; esac
        fi
        [[ -n "$value" ]] || value="${MKVUTIL_METADATA_REGISTRY[${choice}:default]}"
        _mkvutil_metadata_value_valid "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" "$value" && break
        case "${MKVUTIL_METADATA_REGISTRY[${choice}:validator]}" in
          boolean) print -u2 -r -- 'Invalid flag. Enter 0 or 1.' ;;
          language) print -u2 -r -- 'Invalid language tag.' ;;
          *) return 1 ;;
        esac
      done
      mkvutil_metadata_set "$choice" "$target" "$value" || return 1
    done
  done
  return 0
}

# Collect once, before execution. Invalid input retries; EOF returns 2, Back 4.
# An incomplete collection leaves no partial settings or argument arrays.
mkvutil_metadata_configure() {
  local result=0
  mkvutil_metadata_reset
  _mkvutil_metadata_collect "${1-}" "${2:-independent}" "${3-}" "${4-}" "${5-}" || result=$?
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

# Category planning controller. Jobs are JSON records, with raw identification
# JSON retained as a string so 64-bit UID evidence never passes through jq math.
typeset -ga MKVUTIL_SCAN_FILES=() MKVUTIL_SELECTED_FILES=() MKVUTIL_SOURCES=() MKVUTIL_JOBS=()
typeset -ga MKVUTIL_REMOVAL_SKIPS=() MKVUTIL_REMOVAL_SKIP_HISTORY=()
typeset -g MKVUTIL_CURRENT_JOB="" MKVUTIL_CONFIG="" MKVUTIL_CODEC_EXT_JSON=""

_mkvutil_json_array() {
  (( $# > 0 )) || { print -r -- '[]'; return 0; }
  printf '%s\0' "$@" | jq -Rs 'split("\u0000")[:-1]'
}

_mkvutil_json_map() {
  _mkvutil_json_array "$@" | jq -c '. as $p | reduce range(0; $p|length; 2) as $i ({}; .[$p[$i]]=$p[$i+1])'
}

_mkvutil_jq_records() {
  local query="$1"
  shift
  printf '%s\n' "$@" | jq -sc "$query"
}


# Session outcomes are keyed by ORIGINAL canonical selected source path. Current
# scope/jobs may shrink or be rebuilt without rewriting these required outcomes.
typeset -gi MKVUTIL_LEDGER_ENABLED=0 MKVUTIL_HAS_RUN=0 MKVUTIL_INTERRUPTED=0 MKVUTIL_BATCH_ID=0 MKVUTIL_DRY_RUN=0
typeset -g MKVUTIL_DIRECTORY_NAME=""
typeset -gF 6 MKVUTIL_TOTAL_ELAPSED=0
typeset -ga MKVUTIL_SCOPE_KEYS=() MKVUTIL_BATCHES=()
typeset -gA MKVUTIL_LEDGER=()
typeset -gi MKVUTIL_ENGINE_PID=0 MKVUTIL_STOP_SIGNAL=0
typeset -g MKVUTIL_ENGINE_CONTROL="" MKVUTIL_ENGINE_CATEGORY=""

# Only the queue owner handles terminal keys during Run. Native writers already
# have their own process group; signal the engine, never the terminal group.
_mkvutil_request_stop() {
  local requested="$1"
  if (( ! MKVUTIL_INTERRUPTED )); then
    print -u2
    if [[ "$requested" == 2 && ( "$MKVUTIL_ENGINE_CATEGORY" == edit || "$MKVUTIL_ENGINE_CATEGORY" == mux ) && -f "$MKVUTIL_ENGINE_CONTROL/admitted" ]]; then
      print -u2 -r -- 'Stop requested; finishing the current file before stopping.'
    else
      print -u2 -r -- 'Stop requested; stopping the current operation.'
    fi
  fi
  MKVUTIL_INTERRUPTED=1
  # Once requested, additional terminal Ctrl+C must not kill result parsing or
  # the final report. TERM/HUP remain available for hard termination.
  trap '' INT
  # A later Ctrl+C must never downgrade a hard termination request.
  if (( MKVUTIL_STOP_SIGNAL == 0 || requested != 2 )); then MKVUTIL_STOP_SIGNAL=$requested; fi
  if [[ -n "$MKVUTIL_ENGINE_CONTROL" ]]; then
    print -r -- "$MKVUTIL_STOP_SIGNAL" > "$MKVUTIL_ENGINE_CONTROL/signal"
    if (( MKVUTIL_ENGINE_PID > 0 )) && [[ -f "$MKVUTIL_ENGINE_CONTROL/ready" ]]; then
      kill -"$MKVUTIL_STOP_SIGNAL" "$MKVUTIL_ENGINE_PID" 2>/dev/null || true
    fi
  fi
}

mkvutil_ledger_reset() {
  local directory="$1" source=""
  shift
  MKVUTIL_LEDGER_ENABLED=1
  MKVUTIL_HAS_RUN=0
  MKVUTIL_INTERRUPTED=0
  MKVUTIL_STOP_SIGNAL=0
  MKVUTIL_BATCH_ID=0
  MKVUTIL_TOTAL_ELAPSED=0
  MKVUTIL_DIRECTORY_NAME="${directory:A:t}"
  MKVUTIL_SCOPE_KEYS=()
  MKVUTIL_BATCHES=()
  MKVUTIL_LEDGER=()
  for source in "$@"; do
    source="${source:A}"
    (( ! ${+MKVUTIL_LEDGER[$source]} )) || continue
    MKVUTIL_SCOPE_KEYS+=("$source")
    MKVUTIL_LEDGER[$source]="$(jq -cn --arg source "$source" '{schema:1,source:$source,required:true,
      status:"pending",destination:null,attempts:[],skip_history:[],excluded_from_retry:false}')" || return 1
  done
}

# Eligibility is keyed by the original selected identity, including retry scopes.
# Return 3 only for a verified exclusion or completed source; malformed state fails.
_mkvutil_cohort_eligible() {
  local file="$1" entry="" eligible=""
  [[ -n "$file" && "$file" == /* && "$file" == "${file:A}" ]] || return 1
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  entry="${MKVUTIL_LEDGER[$file]-}"
  [[ -n "$entry" ]] || return 1
  eligible="$(jq -esr --arg source "$file" '
    (if length==1 then .[0] else error("invalid cohort ledger document count") end) |
    if type=="object" and .source==$source and (.required|type)=="boolean" and
      (.excluded_from_retry|type)=="boolean" and (.attempts|type)=="array" and (.skip_history|type)=="array" and
      (.status as $status|["pending","skipped","success","warning","partial","failed","interrupted","excluded","not_attempted"]|index($status))!=null
    then if .required==false or .status=="excluded" or .excluded_from_retry or .status=="success" then "skip" else "eligible" end
    else error("invalid cohort ledger identity or state") end' <<< "$entry")" || return 1
  case "$eligible" in eligible) return 0 ;; skip) return 3 ;; *) return 1 ;; esac
}

# A configured cohort is archived before its prompts can end with EOF. Requested
# action numbers remain visible even when the cohort never reaches Run.
mkvutil_batch_request() {
  local category="$1" operations="$2" config="${3:-null}" sources="" record="" file="" result=0
  local -a candidates=() paths=()
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  if (( ${#MKVUTIL_SOURCES} > 0 )); then
    for record in "${MKVUTIL_SOURCES[@]}"; do
      IFS= read -r -d '' file < <(jq -esj 'if length==1 and (.[0]|type)=="object" and (.[0].source|type)=="string" and (.[0].source|length)>0 and (.[0].source|contains("\u0000")|not) then .[0].source,"\u0000" else error("invalid source identity") end' <<< "$record") || return 1
      candidates+=("$file")
    done
  elif (( ${#MKVUTIL_SELECTED_FILES} > 0 )); then
    candidates=("${MKVUTIL_SELECTED_FILES[@]}")
  else
    candidates=("${MKVUTIL_SCOPE_KEYS[@]}")
  fi
  for file in "${candidates[@]}"; do
    result=0
    _mkvutil_cohort_eligible "$file" || result=$?
    (( result != 1 )) || return 1
    (( result == 0 )) || continue
    paths+=("$file")
  done
  sources="$(_mkvutil_json_array "${paths[@]}")" || return 1
  MKVUTIL_BATCH_ID=$(( ${#MKVUTIL_BATCHES} + 1 ))
  MKVUTIL_BATCHES+=("$(_mkvutil_jq_records '
    .[0] as $fields | {id:$fields.id,category:$fields.category,action_ids:($fields.operations|split(",")),
      metadata_ids:(.[1].metadata // ""),config:.[1],sources:.[2],state:"requested",eligible:0,
      attempted:0,completed:0,elapsed_seconds:0,outcomes:{},dry_run:$fields.dry_run}' \
    "$(jq -cn --argjson id "$MKVUTIL_BATCH_ID" --arg category "$category" --arg operations "$operations" --argjson dry "$MKVUTIL_DRY_RUN" '{id:$id,category:$category,operations:$operations,dry_run:($dry==1)}')" "$config" "$sources")")
}

mkvutil_batch_configured() {
  (( MKVUTIL_LEDGER_ENABLED && MKVUTIL_BATCH_ID > 0 )) || return 0
  MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]="$(_mkvutil_jq_records '.[0]+{config:.[1],metadata_ids:(.[1].metadata // ""),state:"configured"}' \
    "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}" "$1")"
}

mkvutil_batch_metadata_requested() {
  (( MKVUTIL_LEDGER_ENABLED && MKVUTIL_BATCH_ID > 0 )) || return 0
  local updated=""
  updated="$(jq -c --arg choices "$1" '.metadata_ids=$choices' <<< "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}")" || return 1
  MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]="$updated"
}

mkvutil_batch_outcomes() {
  local source=""
  local -a entries=()
  for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do entries+=("${MKVUTIL_LEDGER[$source]}"); done
  _mkvutil_jq_records '
    .[0].sources as $sources | reduce (.[1:][] | select(.source as $source | $sources|index($source))) as $file
      ({}; (if $file.status=="success" then "done" elif $file.status=="pending" then "not_attempted" else $file.status end) as $key |
       .[$key] = ((.[$key] // 0)+1))' "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}" "${entries[@]}"
}

mkvutil_batch_planned() {
  (( MKVUTIL_LEDGER_ENABLED && MKVUTIL_BATCH_ID > 0 )) || return 0
  local outcomes="$(mkvutil_batch_outcomes)"
  MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]="$(jq -c --argjson eligible "$1" --argjson outcomes "$outcomes" '.+{state:"planned",eligible:$eligible,outcomes:$outcomes}' <<< "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}")"
}

mkvutil_ledger_exclude() {
  local source="${1:A}" reason="$2" entry=""
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  entry="${MKVUTIL_LEDGER[$source]-}"
  [[ -n "$entry" ]] || return 1
  MKVUTIL_LEDGER[$source]="$(jq -c --arg reason "$reason" '
    if .status=="skipped" or (.skip_history|length)>0 then
      .excluded_from_retry=true | .exclusion_reason=$reason
    elif (.attempts|length)==0 then .required=false|.status="excluded"|.exclusion_reason=$reason
    else .excluded_from_retry=true|.exclusion_reason=$reason end' <<< "$entry")"
}

mkvutil_ledger_skip() {
  local receipt="$1" source="" entry="" updated=""
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  IFS= read -r -d '' source < <(jq -esj 'if length==1 and (.[0].source|type)=="string" and (.[0].source|contains("\u0000")|not) then .[0].source,"\u0000" else error("invalid skip source identity") end' <<< "$receipt") || return 1
  entry="${MKVUTIL_LEDGER[$source]-}"
  [[ -n "$entry" ]] || return 1
  updated="$(_mkvutil_jq_records '
    .[0] as $entry | .[1] as $receipt | .[2] as $batch |
    ($entry.skip_history|map(.receipt==$receipt)|index(true)) as $existing |
    $entry|.status="skipped"|
    if $existing==null then .skip_history += [{receipt:$receipt,batch_ids:[$batch],resolved:false}]
    else .skip_history[$existing].batch_ids += [$batch] | .skip_history[$existing].batch_ids |= unique end' \
    "$entry" "$receipt" "$MKVUTIL_BATCH_ID")" || return 1
  MKVUTIL_LEDGER[$source]="$updated"
}

mkvutil_ledger_result() {
  local result="$1" source="${2-}" status_name="${3-}" entry="" updated=""
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  [[ -n "$source" ]] || source="$(jq -r '.source' <<< "$result")" || return 1
  [[ -n "$status_name" ]] || status_name="$(jq -r '.status' <<< "$result")" || return 1
  entry="${MKVUTIL_LEDGER[$source]-}"
  [[ -n "$entry" ]] || return 1
  if [[ "$status_name" == skipped ]]; then
    mkvutil_ledger_skip "$(jq -c '.skip_receipt' <<< "$result")" || return 1
    entry="${MKVUTIL_LEDGER[$source]}"
  fi
  updated="$(_mkvutil_jq_records '
    .[0] as $entry | .[1] as $result | .[2] as $batch |
    $entry + {status:$result.status,destination:$result.destination} |
    .attempts += [{batch_id:$batch,result:$result}] |
    if $result.status=="success" and ($result.simulated // false | not) then .skip_history |= map(.resolved=true) else . end' \
    "$entry" "$result" "$MKVUTIL_BATCH_ID")" || return 1
  MKVUTIL_LEDGER[$source]="$updated"
}

mkvutil_sync_unresolved_skips() {
  local source="" receipt=""
  local -a entries=()
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  MKVUTIL_REMOVAL_SKIPS=()
  for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do entries+=("${MKVUTIL_LEDGER[$source]}"); done
  while IFS= read -r receipt; do MKVUTIL_REMOVAL_SKIPS+=("$receipt"); done < <(
    _mkvutil_jq_records '.[]|select(.required and .status=="skipped" and (.excluded_from_retry|not))|.skip_history[-1].receipt' "${entries[@]}"
  )
}

mkvutil_ledger_status() {
  local source=""
  local -a entries=()
  (( MKVUTIL_INTERRUPTED == 0 )) || return 1
  for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do entries+=("${MKVUTIL_LEDGER[$source]}"); done
  printf '%s\n' "${entries[@]}" | jq -se --argjson has_run "$MKVUTIL_HAS_RUN" '
    all(.[]; (.required|not) or
      (.status=="success") or
      ($has_run==0 and (.status=="pending" or .status=="not_attempted")))' >/dev/null
}

mkvutil_ledger_finalize() {
  local source="" entry=""
  local -a entries=()
  for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do entries+=("${MKVUTIL_LEDGER[$source]}"); done
  while IFS= read -r -d '' source && IFS= read -r -d '' entry; do
    MKVUTIL_LEDGER[$source]="$entry"
  done < <(printf '%s\n' "${entries[@]}" | jq -sj '
    .[]|select(.status=="pending")|.status="not_attempted"|.source,"\u0000",tojson,"\u0000"')
}

# Pure summary/formatters are shared with the future Extract consumer. JSON
# records are streamed; a large selection never becomes one process argument.
mkvutil_final_summary() {
  local source="" header="" batches=""
  local -a records=()
  for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do records+=("${MKVUTIL_LEDGER[$source]}"); done
  batches="$(_mkvutil_jq_records '.' "${MKVUTIL_BATCHES[@]}")" || return 1
  header="$(jq -cn --arg directory "$MKVUTIL_DIRECTORY_NAME" --argjson elapsed "$MKVUTIL_TOTAL_ELAPSED" --argjson interrupted "$MKVUTIL_INTERRUPTED" --argjson dry "$MKVUTIL_DRY_RUN" '{directory:$directory,elapsed_seconds:$elapsed,interrupted:($interrupted==1),dry_run:($dry==1)}')" || return 1
  _mkvutil_jq_records '
    .[0]+{batches:.[1],files:.[2:]} | . as $summary |
    .counts=(reduce .files[] as $file
      ({done:0,failed:0,warning:0,partial:0,skipped:0,excluded:0,not_attempted:0,interrupted:0};
       (if $file.status=="success" then "done" elif $file.status=="pending" then "not_attempted" else $file.status end) as $key | .[$key]+=1)) |
    .selected=(.files|length)|.required=([.files[]|select(.required)]|length) |
    .attachments={processed:([.files[].attempts[].result.attachments_processed // 0]|add // 0),publications:[],winners:{},active:{}} |
    reduce (.files[] as $file | $file.attempts[] as $attempt | $attempt.result.artifacts[]? |
      select(.kind=="attachment" and (.publication_state=="confirmed" or .publication_state=="uncertain")) |
      .+{source:$file.source,batch_id:$attempt.batch_id}) as $record
      (. ; (.attachments.publications|length) as $index | $record.destination_key as $key |
       .attachments.winners[$key] as $previous |
       if $record.publication_state=="confirmed" then
         reduce (.attachments.active[$key] // [])[] as $prior
           (. ; .attachments.publications[$prior].outcome=(if .attachments.publications[$prior].publication_confirmed then "superseded" else "superseded_uncertain" end)) |
         .attachments.active[$key]=[]
       elif $previous!=null then .attachments.publications[$previous].outcome="winner_uncertain" else . end |
       .attachments.publications += [$record+{outcome:(if $record.publication_state=="confirmed" then "winner" else "winner_uncertain" end)}] |
       .attachments.winners[$key]=$index | .attachments.active[$key]=((.attachments.active[$key] // [])+[$index])) |
    .attachments.unique_names=([.attachments.publications[]|select(.outcome=="winner")]|length) |
    .attachments.uncertain_names=([.attachments.winners[] as $index|.attachments.publications[$index]|select(.outcome=="winner_uncertain")]|length) |
    .attachments.published=([.attachments.publications[]|select(.publication_confirmed)]|length) |
    .attachments.superseded=([.attachments.publications[]|select(.outcome=="superseded")]|length) | del(.attachments.active)' \
    "$header" "$batches" "${records[@]}"
}

# Project paths only for display; job, ledger and recovery records stay intact.
_mkvutil_display_record() {
  jq -c '
    def filename: if type=="string" then split("/")[-1] else . end;
    def file_field: IN("source","destination","reference","path","candidate_path",
      "phase_receipt","staging_directory","active_original_source");
    def file_array: IN("sources","not_started_sources","staged_paths","phase_receipts",
      "scratch_paths","unexpected_paths","discarded_partial_tracks","remaining_staging_directories");
    def diagnostic: IN("reason","error","cleanup_error","inventory_errors","exclusion_reason");
    def replace_known_path($path):
      split(($path|tojson))|join(($path|filename|tojson)) |
      split($path)|join($path|filename);
    def shorten($paths):
      if type=="string" then reduce $paths[] as $path (. ; replace_known_path($path))
      elif type=="array" then map(shorten($paths)) else . end;
    def state_description:
      {not_modified_by_job:"Original file was not modified.",
       unpublished:"No replacement was published.",
       edited_observed:"Current metadata was inspected; changes may already be present.",
       edit_unknown:"Metadata changes could not be confirmed; inspect the file.",
       replaced_complete:"The replacement file was saved.",
       published_complete:"The output was saved and the original source removed.",
       published_source_retained:"The output was saved; the original source remains.",
       published_destination_changed:"The output changed after publication; inspect the files.",
       publication_outcome_unknown:"Publication could not be confirmed; inspect the files.",
       publication_uncertain:"Some extracted outputs need inspection.",
       sidecars_published:"Extracted outputs were saved.",
       staged_unpublished:"Unpublished extraction files remain for inspection.",
       no_outputs:"No extracted outputs were saved.",
       unknown_inspect_filesystem:"File state could not be confirmed; inspect retained files."}[.] //
       "File state could not be confirmed; inspect retained files.";
    . as $record | [..|objects|to_entries[]|
      if (.key|file_field) then .value
      elif (.key|file_array) then .value[]? else empty end|
      select(type=="string" and startswith("/"))] |
      unique|sort_by(length)|reverse as $paths |
    $record | walk(if type=="object" then with_entries(
      if (.key|file_field) then .value|=filename
      elif (.key|file_array) then .value|=if type=="array" then map(filename) else . end
      elif (.key|diagnostic) then .value|=shorten($paths) else . end) else . end) |
    walk(if type=="object" and has("actual_state") then
      .state_description=(.actual_state|state_description) else . end)
  ' <<< "$1"
}

mkvutil_ascii_box() {
  _mkvutil_indicator_stop
  (( $# > 0 )) || return 1
  local title="$1" line="" content_width=44 border="" dash_count=0
  setopt localoptions multibyte
  shift
  (( ${(m)#title} > content_width )) && content_width=${(m)#title}
  for line in "$@"; do
    (( ${(m)#line} > content_width )) && content_width=${(m)#line}
  done
  dash_count=$((content_width + 2))
  repeat "$dash_count"; do border+="-"; done
  print || return 1
  print -r -- "+${border}+" || return 1
  print -r -- "| ${(mr:$content_width:)title} |" || return 1
  if (( $# > 0 )); then
    print -r -- "+${border}+" || return 1
    for line in "$@"; do
      print -r -- "| ${(mr:$content_width:)line} |" || return 1
    done
  fi
  print -r -- "+${border}+"
}

mkvutil_format_final_report() {
  local display="" summary_text="" details="" section="" section_lines_text=""
  local heading='Final report'
  local -a sections=(Simulated Outputs Completed Errors Warnings 'Partial results' Skipped Excluded Interrupted 'Not attempted' Attachments) section_lines=()
  display="$(_mkvutil_display_record "$1")" || return 1
  [[ "$(jq -r '.dry_run // false' <<< "$display")" != true ]] || heading+=' (DRYRUN)'
  summary_text="$(jq -r '
    (.dry_run // false) as $dry |
    def duration: floor as $s | (($s/3600|floor|tostring)+"h "+(($s%3600)/60|floor|tostring)+"m "+($s%60|tostring)+"s");
    def outcome_label:
      if .=="done" then (if $dry then "Simulated" else "Done" end) elif .=="not_attempted" then "Not attempted"
      elif .=="warning" then "Warning" elif .=="partial" then "Partial"
      elif .=="failed" then "Failed" elif .=="skipped" then "Skipped"
      elif .=="excluded" then "Excluded" elif .=="interrupted" then "Interrupted"
      else . end;
    "Directory: \(.directory)",
    (.batches[] | "Configuration \(.id) (\(.state)\(if .state=="executed" or .state=="interrupted" then "" else "; requested, not run" end)):",
      "  Category: \(.category); Actions: \(.action_ids|join(","))",
      (if .category=="mux" then "  Optional Mux metadata: \(if .metadata_ids=="" then "none" else .metadata_ids end)" else empty end),
      "  Requested files: \(.sources|length); eligible: \(.eligible); attempted: \(.attempted); \(if $dry then "simulated" else "completed" end): \(.completed); elapsed: \(.elapsed_seconds|duration)",
      "  Outcomes: \(.outcomes | if length==0 then "none" else to_entries | sort_by(.key as $key | [(["done","failed","warning","partial","skipped","excluded","not_attempted","interrupted"] | index($key) // 8), $key]) | map((.key|outcome_label)+": "+(.value|tostring)) | join("; ") end)"),
    (.batches[] | select(.stop!=null) |
      "Stopped configuration \(.id): \(.stop.mode)",
      "  Files not started due to stop: \(.stop.not_started_sources|length)",
      (.stop.not_started_sources[] | "    \(.)")),
    "Selected: \(.selected); required: \(.required)",
    "\(if $dry then "Simulated" else "Done" end): \(.counts.done); Failed: \(.counts.failed); Warning: \(.counts.warning); Partial: \(.counts.partial); Skipped: \(.counts.skipped); Excluded: \(.counts.excluded); Not attempted: \(.counts.not_attempted); Interrupted: \(.counts.interrupted)",
    (if .interrupted then "Batch interrupted; remaining jobs not attempted." else empty end),
    "Complete batch elapsed: \(.elapsed_seconds|duration)"
  ' <<< "$display")" || return 1
  mkvutil_ascii_box "$heading" || return 1
  print -r -- "$summary_text" || return 1
  details="$(jq -c '
    (.dry_run // false) as $dry |
    def outcome_group:
      if (.attempts[-1].result.simulated // false) then "Simulated"
      elif .status=="failed" then "Errors" elif .status=="warning" then "Warnings"
      elif .status=="partial" then "Partial results" elif .status=="skipped" then "Skipped"
      elif .status=="excluded" then "Excluded" elif .status=="interrupted" then "Interrupted"
      elif .status=="not_attempted" or .status=="pending" then "Not attempted"
      elif .status=="success" and ((.destination!=null and .destination!=.source and (.attempts[-1].result.category // "")!="extract") or
        any(.attempts[].result.artifacts[]?; .kind=="track" and (.publication_state=="confirmed" or .publication_state=="uncertain"))) then "Outputs"
      elif (.skip_history|length)>0 or .exclusion_reason!=null or any(.attempts[]; .result.status!="success") then "Completed"
      else null end;
    def outcome_label:
      if .=="done" then (if $dry then "Simulated" else "Done" end) elif .=="not_attempted" then "Not attempted"
      elif .=="warning" then "Warning" elif .=="partial" then "Partial"
      elif .=="failed" then "Failed" elif .=="skipped" then "Skipped"
      elif .=="excluded" then "Excluded" elif .=="interrupted" then "Interrupted" else . end;
    def file_lines:
      (if .attempts[-1].result.simulated==true then "\(.source)"
       elif .status=="success" then
         if (.destination!=null and .destination!=.source and (.attempts[-1].result.category // "")!="extract") then "\(.source) => \(.destination)"
         else "\(.source)" end
       else "\(.source)\(if .destination and .destination!=.source and (.attempts[-1].result.category // "")!="extract" then " => "+.destination else "" end)" end),
      (if .exclusion_reason then "  Excluded\(if .required then " from retry; unresolved outcome retained" else " from required scope" end): \(.exclusion_reason)" else empty end),
      (.skip_history[] | "  Skip history: \(if .resolved then "resolved" else "unresolved" end); configurations \(.batch_ids|map(tostring)|join(",")); reference \(.receipt.reference)",
         (if (.receipt.reason // "")!="" then "    \(.receipt.reason)" else empty end),
         (if .receipt.track_count_mismatch then "    Track count mismatch: expected \(.receipt.track_count_mismatch.expected); actual \(.receipt.track_count_mismatch.actual)" else empty end),
         (.receipt.reasons[] | (if .reason=="output-position-mismatch" then "    Output ID \(.output_id): expected source ID \(.expected.original_id); actual source ID \(.actual.original_id // "missing")"
          else "    Original ID \(.original_id): \(.reason); expected=\(.expected|tojson) actual=\(.actual|tojson)" end))),
      (.attempts[] |
        (.result as $result | .result.planned_outputs[]? |
          "  Would \(if $result.category=="edit" then "update" elif $result.category=="mux" or .kind=="attachment" then "write" else "extract" end): \(.path)\(if .required==false then " (optional)" else "" end)"),
        (if .result.status!="success" then "  Batch \(.batch_id): \(.result.status|outcome_label)\(if (.result.reason // "")!="" then ": "+.result.reason else "" end)",
          "  \(.result.state_description)" else empty end),
        (.result.stages[]? | select(.status!="success" and .status!="complete") | "  \(.kind): \(.status)\(if .native_code!=null then " (tool exit "+(.native_code|tostring)+")" else "" end)"),
        (.result.artifacts[]? | select(.kind=="track" and (.publication_state=="confirmed" or .publication_state=="uncertain")) |
          "  Track \(.id): \(.path)\(if .publication_state=="uncertain" then " (publication uncertain)" else "" end)"),
        (.result.staged_paths[]? | "  Staged: \(.)"),
        (.result.discarded_partial_tracks[]? | "  Discarded unfinished track: \(.)"),
        (.result.scratch_paths[]? | "  Native scratch: \(.)"),
        (.result.unexpected_paths[]? | "  Unexpected artifact: \(.)"),
        (if .result.cleanup_error then "  Cleanup failed: \(.result.cleanup_error)" else empty end),
        (.result.inventory_errors[]? | "  Recovery inventory: \(.)"),
        (.result.remaining_staging_directories[]? | "  Retained staging directory: \(.)"),
        (.result.uncertain_artifacts[]? | "  Uncertain publication: \(.path)"));
    . as $summary |
    (reduce .files[] as $file ({Simulated:[],Outputs:[],Completed:[],Errors:[],Warnings:[],"Partial results":[],Skipped:[],Excluded:[],Interrupted:[],"Not attempted":[],Attachments:[]};
      ($file|outcome_group) as $group | if $group==null then . else .[$group] += [$file|file_lines] end)) as $groups |
    ($groups | if $summary.dry_run then .Simulated += ["Files were not changed."] else . end) as $groups |
    if ($summary.dry_run|not) and any($summary.batches[];.category=="extract") then
      $groups | .Attachments += ["Attachments processed: \($summary.attachments.processed); published: \($summary.attachments.published); final unique published names: \($summary.attachments.unique_names); superseded: \($summary.attachments.superseded); uncertain names: \($summary.attachments.uncertain_names)"] |
      .Attachments += [$summary.attachments.publications[]|"  Attachment \(.outcome): \(.path); source \(.source); ID \(.id)"]
    else $groups end
  ' <<< "$display")" || return 1
  for section in "${sections[@]}"; do
    section_lines_text="$(jq -r --arg section "$section" '.[$section][]?' <<< "$details")" || return 1
    [[ -n "$section_lines_text" ]] || continue
    section_lines=("${(@f)section_lines_text}")
    mkvutil_ascii_box "$section" "${section_lines[@]}" || return 1
  done
}
mkvutil_final_report() { mkvutil_format_final_report "$(mkvutil_final_summary)"; }

mkvutil_clock() { python3 -c 'import time; print(time.monotonic())'; }

mkvutil_format_progress() {
  local category="$1" operations="$2" elapsed="$3" attempted="$4" completed="$5" total="$6" work_elapsed="${7:-$3}" track_elapsed="${8-}" track_work="${9-}" track_samples="${10:-$4}" mode=job
  local output="" source="${11-}"
  local -a progress_lines=()
  [[ "$category" != edit ]] || return 0
  [[ "$category" == mux || "$category" == extract ]] || return 1
  if (( ! MKVUTIL_DRY_RUN )) && [[ "$category" == extract && ",$operations," == *,1,* && ",$operations," == *,2,* ]]; then
    [[ -n "$track_work" ]] || return 1
    work_elapsed="$track_work"
    if [[ -n "$track_elapsed" ]]; then
      elapsed="$track_elapsed";mode=track
    else
      (( $# >= 10 )) || return 1
      mode=track_not_attempted
    fi
  fi
  output="$(python3 -c '
import sys
elapsed=max(0,float(sys.argv[1]));work=max(0,float(sys.argv[2]));attempted,completed,total,samples=map(int,sys.argv[3:7]);mode=sys.argv[7]
remaining=max(0,total-attempted);denominator=samples if mode.startswith("track") else attempted
eta=work/denominator*remaining if denominator else None
if not mode.startswith("track") and not denominator:eta=0
def duration(value):
    value=int(value);return f"{value//3600}h {(value%3600)//60}m {value%60}s"
measured="Track stage: not attempted" if mode=="track_not_attempted" else f"Processed In: {duration(elapsed)}"
estimated="unavailable (no track stages attempted)" if eta is None else duration(eta)
print(f"{measured}\nFiles Done: {completed}\nFiles Attempted: {attempted}\nFiles Remaining: {remaining}\nEstimated Time Remaining: {estimated}")
' "$elapsed" "$work_elapsed" "$attempted" "$completed" "$total" "$track_samples" "$mode")" || return $?
  if (( MKVUTIL_DRY_RUN )); then output="${output/Files Done:/Files Simulated:}"; fi
  progress_lines=("${(@f)output}")
  (( ${#progress_lines} > 0 )) || return 1
  [[ -z "$source" ]] || progress_lines=("File: ${source:t}" "${progress_lines[@]}")
  local heading='File progress'
  (( ! MKVUTIL_DRY_RUN )) || heading+=' (DRYRUN)'
  mkvutil_ascii_box "$heading" "${progress_lines[@]}"
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
    detail = error.strerror if isinstance(error, OSError) else str(error)
    print(f"Cannot inspect source identity: {os.path.basename(sys.argv[1])}: {detail}", file=sys.stderr)
    sys.exit(1)
PYCODE
}

# Identification errors are native text; replace only the supplied file paths.
_mkvutil_display_file_errors() {
  python3 -c '
import os, sys
text = sys.stdin.buffer.read()
for path in sorted(sys.argv[1:], key=len, reverse=True):
    text = text.replace(os.fsencode(path), os.fsencode(os.path.basename(path)))
sys.stderr.buffer.write(text)
' "$@"
}

mkvutil_capture_source() {
  local file="${1:A}" before="" after="" json="" rows=""
  before="$(mkvutil_source_identity "$file")" || return 1
  json="$(
    # Keep JSON on descriptor 3 while the foreground pipeline sanitizes stderr.
    # Waiting for both stages prevents late diagnostics without temporary files
    # owned by an interruptible command substitution.
    unsetopt multios
    setopt pipefail
    { mkvmerge -J "$file" < /dev/null 2>&1 1>&3 | _mkvutil_display_file_errors "$file"; } 3>&1
  )" || return 1
  after="$(mkvutil_source_identity "$file")" || return 1
  [[ "$before" == "$after" ]] || { print -u2 -r -- "Source changed during inspection: ${file:t}"; return 1; }
  rows="$(collect_tracks_for_remux "$file" "$json")" || return 1
  mkvutil_plan_layout "$rows" '' '' "${file:e}" || return 1
  printf '%s\0' "$file" "$before" "$json" | python3 -c '
import json, sys
source, identity, raw = sys.stdin.buffer.read().decode().split("\0")[:-1]
original = json.loads(raw)
fields = ("codec_id", "track_name", "language", "language_ietf", "default_track", "forced_track")
model = {"tracks": [{"id": item["id"], "type": item["type"], "properties":
         {key: item.get("properties", {}).get(key) for key in fields}}
         for item in original["tracks"]],
         "title": original.get("container", {}).get("properties", {}).get("title"),
         "attachments": original.get("attachments", [])}
print(json.dumps({"source": source, "identity": json.loads(identity), "source_json": raw, "model": model}))
'

}

# Foreground execution preflight owns the status row; JSON stays in REPLY.
_mkvutil_capture_execution_source() {
  local file="$1" record="" diagnostics="" result=0
  REPLY=""
  if [[ -t 1 && -n "${TERM-}" && "$TERM" != dumb ]]; then
    diagnostics="$(mktemp "${TMPDIR:-/tmp}/mkvutil-preflight.XXXXXXXX")" || return 1
  fi
  {
    _mkvutil_indicator_start Working || return 1
    if [[ -n "$diagnostics" ]]; then
      record="$(mkvutil_capture_source "$file" 2> "$diagnostics")" || result=$?
    else
      record="$(mkvutil_capture_source "$file")" || result=$?
    fi
  } always {
    _mkvutil_indicator_stop
    if [[ -n "$diagnostics" ]]; then
      [[ ! -s "$diagnostics" ]] || cat "$diagnostics" >&2
      rm -f -- "$diagnostics"
    fi
  }
  REPLY="$record"
  return "$result"
}

mkvutil_scan_files() {
  local directory="${1:A}" file=""
  MKVUTIL_SCAN_FILES=()
  for file in "$directory"/*.(mkv|mka|mks|mk3d)(N.); do
    MKVUTIL_SCAN_FILES+=("$file")
  done
  (( ${#MKVUTIL_SCAN_FILES} > 0 ))
}

mkvutil_scan_files_working() {
  local result=0 directory="${1:-$PWD}"
  {
    _mkvutil_indicator_start Working || result=$?
    (( result )) || mkvutil_scan_files "$directory" || result=$?
  } always {
    _mkvutil_indicator_stop
  }
  (( ! MKVUTIL_INTERRUPTED )) || return 2
  return "$result"
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
  _mkvutil_indicator_stop
  (( ! MKVUTIL_INTERRUPTED )) || return 2
  setopt localtraps
  trap 'MKVUTIL_INTERRUPTED=1; return 2' INT TERM
  printf '%s' "$1" >&2
  IFS= read -r REPLY || return 2
}

# Structured track-ID fields share parsing and retry behavior. Keep validation
# in the foreground so Back, EOF and signals retain their existing ownership.
_mkvutil_read_track_ids() {
  local prompt="$1" domain="$2" expanded=""
  [[ -n "$domain" ]] || return 1
  while true; do
    _mkvutil_read "$prompt" || return 2
    case "$REPLY" in e|E) return 4 ;; esac
    if expanded="$(mkvutil_expand_ids "$REPLY" "$domain")"; then
      REPLY="$expanded"
      return 0
    fi
    (( ! MKVUTIL_INTERRUPTED )) || return 2
    print -u2 -r -- "Invalid IDs. Available: $domain"
  done
}

# Main and submenu choices use the same line-input protocol. The main menu
# accepts one category per line; submenu lists/ranges retain their own grammar.
_mkvutil_read_main() {
  _mkvutil_indicator_stop
  if [[ -t 2 && -n "${TERM-}" && "$TERM" != dumb ]]; then
    printf '\e[?25h' >&2
  fi
  _mkvutil_read 'Category: '
}

# Navigation and its picker share a transient buffer. Pipes and dumb/redirected
# terminals retain normal output and the original line-input protocol.
typeset -gi MKVUTIL_UI_ACTIVE=0 MKVUTIL_UI_REPORT_SHOWN=0 MKVUTIL_BYPASS_TRACK_COUNT=0
typeset -g MKVUTIL_INDICATOR_PID=""
_mkvutil_ui_owned() { [[ -t 0 && -t 1 && -t 2 && -n "${TERM-}" && "$TERM" != dumb ]]; }
_mkvutil_ui_enter() {
  if _mkvutil_ui_owned && (( ! MKVUTIL_UI_ACTIVE )); then
    printf '\e[?1049h' >&2
    MKVUTIL_UI_ACTIVE=1
  fi
  return 0
}
_mkvutil_ui_redraw() {
  (( MKVUTIL_UI_ACTIVE )) || return 0
  local line="" paint=$'\e[H'
  # Build the whole body first. Erase each old line suffix and the old tail;
  # retain the navigation buffer without a blank-screen prepaint.
  for line in "${(@f)1}"; do paint+="$line"$'\e[K\r\n'; done
  paint+=$'\e[J'
  printf '%s' "$paint" >&2
}

_mkvutil_ui_leave() {
  if (( MKVUTIL_UI_ACTIVE )); then
    printf '\e[?25h\e[?1049l' >&2
    MKVUTIL_UI_ACTIVE=0
  fi
  return 0
}
_mkvutil_ui_acknowledge() {
  _mkvutil_ui_leave
  _mkvutil_ui_owned || return 0
  setopt localtraps
  local acknowledgement=""
  trap 'MKVUTIL_INTERRUPTED=1; return 2' INT TERM
  printf '\nPress Enter to continue: ' >&2
  IFS= read -r acknowledgement || return 2
  (( ! MKVUTIL_INTERRUPTED )) || return 2
}

# The indicator owns one terminal row. Callers stop it in foreground control
# flow before prompting, reporting, or handing output to another tool.
_mkvutil_indicator_start() {
  local label="$1" owner_pid="$$" defer_first_frame=0
  (( ! MKVUTIL_INTERRUPTED )) || return 0
  if [[ "$label" == Working ]] && (( MKVUTIL_HAS_RUN )); then return 0; fi
  [[ -t 1 && -n "${TERM-}" && "$TERM" != dumb ]] || return 0
  [[ -z "$MKVUTIL_INDICATOR_PID" ]] || return 0
  [[ "$label" != Working ]] || defer_first_frame=1
  (
    trap - EXIT
    local frame=1 use_zselect=0 painted=0
    trap '(( painted )) && exit 73; exit 0' INT TERM
    local -a frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
    zmodload zsh/zselect 2>/dev/null && use_zselect=1
    while kill -0 "$owner_pid" 2>/dev/null; do
      if (( defer_first_frame )); then
        if (( use_zselect )); then zselect -t10 || true; else sleep 0.1; fi
        defer_first_frame=0
        kill -0 "$owner_pid" 2>/dev/null || break
      fi
      printf '\e[?25l\r  %s %s' "${frames[$frame]}" "$label" || { (( painted )) && exit 73; exit 0; }
      painted=1
      while kill -0 "$owner_pid" 2>/dev/null; do
        if (( use_zselect )); then zselect -t10 || true; else sleep 0.1; fi
        frame=$((frame % ${#frames} + 1))
        printf '\r  %s' "${frames[$frame]}" || { (( painted )) && exit 73; exit 0; }
      done
    done
    (( painted )) && exit 73
    exit 0
  ) &
  MKVUTIL_INDICATOR_PID=$!
  return 0
}

_mkvutil_indicator_stop() {
  local helper_pid="$MKVUTIL_INDICATOR_PID" wait_status=0
  [[ -n "$helper_pid" ]] || return 0
  MKVUTIL_INDICATOR_PID=""
  kill -TERM "$helper_pid" 2>/dev/null || true
  while true; do
    wait "$helper_pid" 2>/dev/null
    wait_status=$?
    kill -0 "$helper_pid" 2>/dev/null || break
  done
  (( wait_status != 73 )) || printf '\r\033[2K' || true
  # Restore even if the helper exited unexpectedly after hiding the cursor.
  printf '\e[?25h' || true
  return 0
}

# Pure rendering runs off-screen. Diagnostics are captured with the body and
# replayed by the parent after leaving; a subshell never changes ACTIVE.
_mkvutil_menu_body() {
  local view="$1" category="${2-}" owned="${3:-0}" targets="${4-}" preview="${5-}" title=""
  case "$view:$category" in
    actions:edit|metadata:mux) mkvutil_metadata_validate_registry || return 1 ;;
  esac
  if (( owned )); then
    case "$category" in edit) title='Matroska Edit' ;; mux) title='Matroska Mux' ;; extract) title='Matroska Extract' ;; *) title='Matroska Utility' ;; esac
    print -r -- "$title — $view"
    print -r -- "Directory: $PWD"
    print
  fi
  case "$view" in
    main) print -r -- $'1) Matroska Edit\n2) Matroska Mux\n3) Matroska Extract\n4) Matroska Analyze' ;;
    actions) mkvutil_category_menu "$category" ;;
    metadata)
      if [[ -n "$preview" ]]; then print -r -- "$preview"; print; fi
      print -r -- 'Optional metadata edits:'
      [[ -z "$targets" ]] || print -r -- "Output IDs for each track edit: $targets"
      mkvutil_metadata_menu || return 1
      print -r -- 'e) Back' ;;
    *) return 1 ;;
  esac
}

# A preview must fit without wrapping or scrolling the alternate buffer. If the
# TTY cannot supply its dimensions, ordinary scrollback keeps every row usable.
_mkvutil_preview_fits() {
  setopt localoptions extendedglob multibyte
  local size="" height="" width="" line="" plain="" count=0
  size="$(stty size <&0 2>/dev/null)" || return 1
  local -a dimensions=( ${=size} )
  (( ${#dimensions} == 2 )) || return 1
  height="${dimensions[1]}" width="${dimensions[2]}"
  [[ "$height" == <1-> && "$width" == <1-> ]] || return 1
  for line in "${(@f)1}" "$2"; do
    plain="${line//$'\e'\[[0-9\;]#m/}"
    # Tabs/control characters and a last-column cursor are not safe to paint.
    [[ "$plain" != *[$'\t\r\b\e']* ]] || return 1
    (( ${(m)#plain} < width )) || return 1
    (( count+=1 ))
  done
  (( count < height ))
}

_mkvutil_menu_read() {
  _mkvutil_indicator_stop
  (( ! MKVUTIL_INTERRUPTED )) || return 2
  setopt localtraps
  local view="$1" category="${2-}" prompt="${3-}" targets="${4-}" result=0 owned=0 body="" validation_message="${5-}" preview="${6-}"
  trap 'MKVUTIL_INTERRUPTED=1; result=2; return 2' INT TERM
  {
    _mkvutil_ui_owned && owned=1
    body="$(_mkvutil_menu_body "$view" "$category" "$owned" "$targets" "$preview" 2>&1)" || result=$?
    if (( result )); then
      _mkvutil_ui_leave
      [[ -z "$body" ]] || print -u2 -r -- "$body"
    else
      [[ -z "$validation_message" ]] || body+=$'\n'"$validation_message"
      if (( owned )) && [[ -n "$preview" ]] && ! _mkvutil_preview_fits "$body" "$prompt"; then
        owned=0
        _mkvutil_ui_leave
        body="$(_mkvutil_menu_body "$view" "$category" 0 "$targets" "$preview" 2>&1)" || return 1
        [[ -z "$validation_message" ]] || body+=$'\n'"$validation_message"
      fi
      if (( owned )); then _mkvutil_ui_enter; fi
      if (( MKVUTIL_UI_ACTIVE )); then
        _mkvutil_ui_redraw "$body"
      else
        printf '%s\n' "$body"
      fi
      if [[ "$view" == main ]]; then
        _mkvutil_read_main || result=$?
      else
        _mkvutil_read "$prompt" || result=$?
      fi
    fi
  } always {
    # Successful navigation retains its buffer for the next view. Durable
    # phases leave explicitly at their call sites; EOF/errors always leave.
    if (( result || MKVUTIL_INTERRUPTED )); then _mkvutil_ui_leave; fi
  }
  return "$result"
}

_mkvutil_menu_choices() {
  local choices="" result=0
  choices="$(mkvutil_category_choices "$1" "$2" 2>&1)" || result=$?
  # A pure selection rejection keeps the owned screen for its retry. Registry
  # and rendering failures still leave it before replaying their diagnostics.
  (( result != 3 )) || return 3
  if (( result )); then
    _mkvutil_ui_leave
    [[ -z "$choices" ]] || print -u2 -r -- "$choices"
    return "$result"
  fi
  REPLY="$choices"
}

_mkvutil_exclude() {
  while true; do
    _mkvutil_read 'Exclude file? [y/N]: ' || return 2
    case "$REPLY" in
      e|E) return 4 ;;
      [yY]|[yY][eE][sS]) return 0 ;;
      ''|[nN]|[nN][oO]) return 1 ;;
      *) print -u2 -r -- 'Invalid answer. Enter y or n.' ;;
    esac
  done
}

mkvutil_select_files() {
  _mkvutil_indicator_stop
  local file=""
  local -a selected=() selector=(--multi --read0 --print0 --height 40% --reverse --border)
  if (( MKVUTIL_UI_ACTIVE )) && _mkvutil_ui_owned; then
    # Keep the menu visible until fzf paints. Leave one row so fzf stays in
    # height mode instead of entering another alternate screen at 100%.
    selector=(--multi --read0 --print0 --height -1 --reverse --border --no-clear --sync)
    printf '\e[H' >&2
  fi
  selector+=(--delimiter / --with-nth -1)
  {
    while IFS= read -r -d '' file; do selected+=("$file"); done < <(
      printf '%s\0' "${MKVUTIL_SCAN_FILES[@]}" | fzf "${selector[@]}"
    )
  } always {
    _mkvutil_ui_leave
  }
  mkvutil_accept_files "${selected[@]}" || { print -u2 -r -- 'No valid scanned files selected.'; return 1; }
}

# Retain these hooks for the Analyze path and its existing instrumentation.
_mkvutil_start_analysis_indicator() { _mkvutil_indicator_start Analysing; }
_mkvutil_stop_analysis_indicator() { _mkvutil_indicator_stop; }

# Reuse identification, listing and the same ID/type/codec signatures as Mux.
mkvutil_analyze_files() {
  local file="" record="" raw="" ids="" signature="" listing="" reference="" expected="" result=0
  local reference_label="" stop_code=0
  local matching=0 analyzed=0
  local -a mismatched=() failed=() missed=() mismatch_names=() error_names=() missed_names=()
  {
    _mkvutil_start_analysis_indicator || result=1
    for file in "${MKVUTIL_SELECTED_FILES[@]}"; do
      if (( MKVUTIL_INTERRUPTED )); then missed+=("$file"); continue; fi
      if ! record="$(mkvutil_capture_source "$file" 2>/dev/null)"; then
        failed+=("$file"); result=1; continue
      fi
      raw="$(jq -r '.source_json' 2>/dev/null <<< "$record")" || { failed+=("$file"); result=1; continue; }
      ids="$(jq -r '.model.tracks|map(.id|tostring)|join(",")' 2>/dev/null <<< "$record")" || { failed+=("$file"); result=1; continue; }
      signature="$(mkvutil_removal_signatures "$record" "$ids" 2>/dev/null)" || { failed+=("$file"); result=1; continue; }
      if [[ -z "$reference" ]]; then
        # Buffer before accepting the reference, so a partial listing is never displayed.
        listing="$(display_track_info "$file" "$raw" 2>/dev/null)" || { failed+=("$file"); result=1; continue; }
        reference="$file"; expected="$signature"
      fi
      analyzed=$((analyzed + 1))
      if jq -en --argjson expected "$expected" --argjson actual "$signature" '$expected==$actual' >/dev/null 2>/dev/null; then
        matching=$((matching + 1))
      else
        mismatched+=("$file"); result=1
      fi
    done
  } always {
    _mkvutil_stop_analysis_indicator || stop_code=$?
    (( stop_code == 0 )) || result=1
  }
  reference_label="Analysis reference file: ${reference:t}"
  [[ -n "$reference" ]] || reference_label='Analysis reference file: none'
  mkvutil_ascii_box 'Analysis' "Current Work Dir: $PWD" "$reference_label" || result=1
  if [[ -n "$reference" ]]; then
    print || result=1
    print -r -- "$listing" || result=1
  fi
  mkvutil_ascii_box 'Final report' || result=1
  print -r -- 'Category: analysis; Main choice: 4'
  print -r -- "Current Work Dir: $PWD"
  print -r -- "Reference file: ${reference:t}"
  [[ -n "$reference" ]] || { print -r -- 'No usable reference file.'; result=1; }
  print -r -- "Files analyzed: $analyzed; Matching: $matching; Mismatched: ${#mismatched}; Failed: ${#failed}; Not attempted: ${#missed}"
  for file in "${mismatched[@]}"; do mismatch_names+=("${file:t}"); done
  for file in "${failed[@]}"; do error_names+=("${file:t}"); done
  for file in "${missed[@]}"; do missed_names+=("${file:t}"); done
  (( ${#mismatch_names} == 0 )) || mkvutil_ascii_box 'Track ID/type/codec mismatch' "${mismatch_names[@]}" || result=1
  (( ${#error_names} == 0 )) || mkvutil_ascii_box 'Errors' "${error_names[@]}" || result=1
  (( ${#missed_names} == 0 )) || mkvutil_ascii_box 'Not attempted' "${missed_names[@]}" || result=1
  (( ! MKVUTIL_INTERRUPTED )) || { print -r -- 'Analysis interrupted.'; result=1; }
  return "$result"
}

mkvutil_inspect_sources() {
  local file="" record="" result=0 capture_result=0 diagnostics_file=""
  local -a sources=()
  MKVUTIL_SOURCES=()
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  if [[ -t 1 && -n "${TERM-}" && "$TERM" != dumb ]]; then
    diagnostics_file="$(mktemp "${TMPDIR:-/tmp}/mkvutil-inspection.XXXXXXXX")" || return 1
  fi
  {
    for file in "${MKVUTIL_SELECTED_FILES[@]}"; do
      result=0
      _mkvutil_cohort_eligible "$file" || result=$?
      (( result != 1 )) || return 1
      (( result == 0 )) || continue
      capture_result=0
      if [[ -n "$diagnostics_file" ]]; then
        : > "$diagnostics_file" || return 1
        [[ -n "$MKVUTIL_INDICATOR_PID" ]] || _mkvutil_indicator_start Working || return 1
        {
          record="$(mkvutil_capture_source "$file" 2>"$diagnostics_file")" || capture_result=$?
        } always {
          (( capture_result == 0 )) || _mkvutil_indicator_stop
        }
        if [[ -s "$diagnostics_file" ]]; then
          _mkvutil_indicator_stop
          cat "$diagnostics_file" >&2 || return 1
        fi
      else
        record="$(mkvutil_capture_source "$file")" || capture_result=$?
      fi
      if (( capture_result == 0 )); then
        jq -es --arg source "$file" 'length==1 and (.[0]|type)=="object" and .[0].source==$source' <<< "$record" >/dev/null || return 1
        sources+=("$record")
      else
        print -u2 -r -- "Inspection failed: ${file:t}"
        _mkvutil_exclude || { result=$?; return "$result"; }
        mkvutil_ledger_exclude "$file" 'Initial inspection failed' || return 1
      fi
    done
    _mkvutil_indicator_stop
    (( ${#sources} > 0 )) || { print -r -- 'No valid sources remain.'; return 1; }
    MKVUTIL_SOURCES=("${sources[@]}")
  } always {
    _mkvutil_indicator_stop
    [[ -z "$diagnostics_file" ]] || rm -f "$diagnostics_file"
  }
}

mkvutil_category_menu() {
  case "$1" in
    edit) mkvutil_metadata_menu || return 1 ;;
    mux) print -r -- $'1) Remove tracks\n2) Reorder tracks' ;;
    extract) print -r -- $'1) Extract attachments\n2) Extract selected tracks' ;;
    *) return 1 ;;
  esac
  print -r -- 'e) Back'
}

mkvutil_category_choices() {
  local domain=""
  case "$1" in
    edit) mkvutil_metadata_validate_registry || return 1; domain="${(j:,:)MKVUTIL_METADATA_IDS}" ;;
    mux|extract) domain=1,2 ;;
    *) return 1 ;;
  esac
  mkvutil_expand_ids "$2" "$domain" || return 3
}

# Configure against the first original model. Every job validates targeted IDs
# and types against its own model afterward; untouched heterogeneous tracks are
# allowed. Optional Mux metadata uses exactly the Edit registry/collector.
# Public ordering accepts bare original IDs. Native 0:ID selectors belong only
# to the internal plan/tool contract. Return the explicit/automatic prefix;
# plan_layout completes unlisted retained tracks independently.
mkvutil_normalize_order() {
  local text="$1" retained="$2" token="" pattern='^[[:space:]]*[0-9]+[[:space:]]*(,[[:space:]]*[0-9]+[[:space:]]*)+$'
  local -a supplied=() allowed=("${(@s:,:)retained}")
  local -A seen=()
  [[ "$text" =~ "$pattern" ]] || return 1
  for token in "${(@s:,:)text}"; do
    token="${token//[[:space:]]/}"
    _mkvutil_canonical_id "$token" || return 1
    token="$REPLY"
    (( ${allowed[(Ie)$token]} > 0 && ! ${+seen[$token]} )) || return 1
    supplied+=("0:$token")
    seen[$token]=1
  done
  (( ${#supplied} >= 2 )) || return 1
  if (( ${allowed[(Ie)0]} > 0 && ! ${+seen[0]} )); then supplied=(0:0 "${supplied[@]}"); fi
  print -r -- "${(j:,:)supplied}"
}

mkvutil_configure_category() {
  local category="$1" operations="$2" reference="${MKVUTIL_SOURCES[1]}"
  local raw="" rows="" source="" removal="" order="" metadata="" extract_ids="" expected="" settings="" signatures='{}'
  local -a order_ids=() removal_ids=()
  local item="" retained_csv="" projection="" track_view="" metadata_preview="" metadata_targets="" preview_yellow="" order_input="" highlight_ids="" output_map='{}'
  local item_position=0
  local metadata_mode=independent result=0 prep_result=0 signature_result=0 signature_diagnostics="" metadata_error=""
  MKVUTIL_CONFIG=""
  MKVUTIL_JOBS=()
  mkvutil_metadata_reset
  {
    _mkvutil_indicator_start Working || prep_result=$?
    (( prep_result )) || raw="$(jq -r '.source_json' <<< "$reference")" || prep_result=$?
    (( prep_result )) || source="$(jq -r '.source' <<< "$reference")" || prep_result=$?
    (( prep_result )) || rows="$(collect_tracks_for_remux "$source" "$raw")" || prep_result=$?
    (( prep_result )) || mkvutil_plan_layout "$rows" '' '' "${source:e}" || prep_result=$?
    (( prep_result )) || expected="$(_mkvutil_json_map "${(@kv)MKVUTIL_TRACK_TYPES}")" || prep_result=$?
  } always {
    _mkvutil_indicator_stop
  }
  (( prep_result == 0 )) || return "$prep_result"
  local -a track_header=("Current Work Dir: $PWD")
  if [[ "$category" == mux && ",$operations," == *,1,* ]]; then
    track_header+=("Removal reference file: ${source:t}")
    (( ! MKVUTIL_BYPASS_TRACK_COUNT )) || track_header+=('Bypass enabled: removal track-count guard only.')
  else
    track_header+=("Reference file: ${source:t}")
  fi
  mkvutil_ascii_box 'Track configuration' "${track_header[@]}" || return 1
  print || return 1
  display_track_info "$source" "$raw" || return 1
  case "$category" in
    edit)
      result=0
      track_view="$(_mkvutil_track_view "$raw")" || return 1
      mkvutil_metadata_configure "$operations" shared '' '' "$track_view" || result=$?
      if (( result == 4 )); then mkvutil_batch_metadata_requested '' || return 1; fi
      (( result == 0 )) || return "$result" ;;
    mux)
      if [[ ",$operations," == *,1,* ]]; then
        while true; do
          _mkvutil_read_track_ids 'Remove IDs: ' "${(j:,:)MKVUTIL_INPUT_IDS}" || return $?
          removal="$REPLY"
          removal_ids=("${(@s:,:)removal}")
          (( ${#removal_ids} < ${#MKVUTIL_INPUT_IDS} )) && break
          print -u2 -r -- 'Invalid removal. Keep one track.'
        done
        if [[ -t 1 && -n "${TERM-}" && "$TERM" != dumb ]]; then
          signature_diagnostics="$(mktemp "${TMPDIR:-/tmp}/mkvutil-signature.XXXXXXXX")" || return 1
        fi
        _mkvutil_indicator_start Working || return 1
        {
          if [[ -n "$signature_diagnostics" ]]; then
            signatures="$(mkvutil_removal_signatures "$reference" "$removal" 2>"$signature_diagnostics")" || signature_result=$?
          else
            signatures="$(mkvutil_removal_signatures "$reference" "$removal")" || signature_result=$?
          fi
        } always {
          _mkvutil_indicator_stop
          if [[ -n "$signature_diagnostics" ]]; then
            [[ ! -s "$signature_diagnostics" ]] || cat "$signature_diagnostics" >&2
            rm -f "$signature_diagnostics" || true
          fi
        }
        (( signature_result == 0 )) || return "$signature_result"
      fi
      # Resolve removal before asking for order; retry only the order input.
      mkvutil_plan_layout "$rows" "$removal" '' "${source:e}" || return 1
      retained_csv="${(j:,:)MKVUTIL_RETAINED_IDS}"
      if [[ ",$operations," == *,2,* ]]; then
        if (( ${#MKVUTIL_RETAINED_IDS} < 2 )); then
          print -u2 -r -- 'Cannot reorder: at least two retained tracks are required.'
          return 4
        fi
        if [[ ",$operations," == *,1,* && -n "$removal" ]]; then
          print || return 1
          display_track_info "$source" "$raw" "$removal" || return 1
        fi
        while true; do
          (( ! MKVUTIL_INTERRUPTED )) || return 2
          _mkvutil_read 'Track order: ' || return 2
          case "$REPLY" in e|E) return 4 ;; esac
          order_input="$REPLY"
          if order="$(mkvutil_normalize_order "$order_input" "$retained_csv")" && mkvutil_plan_layout "$rows" "$removal" "$order" "${source:e}"; then
            (( ! MKVUTIL_INTERRUPTED )) || return 2
            break
          fi
          (( ! MKVUTIL_INTERRUPTED )) || return 2
          print -u2 -r -- "Invalid order. Available: $retained_csv"
        done
        highlight_ids="$(mkvutil_expand_ids "$order_input" "$retained_csv")" || return 1
        print -r -- "Track order: ${order//0:/}"
        for item in "${(@s:,:)order}"; do
          _mkvutil_canonical_id "${item#0:}" || return 1
          order_ids+=("$REPLY")
        done
        metadata_mode=preset
      fi
      projection="${(j:,:)MKVUTIL_RETAINED_IDS}"
      track_view="$(_mkvutil_track_view "$raw" "$removal" "$projection" output)" || return 1
      _mkvutil_track_colours
      [[ -z "$order" ]] || preview_yellow="$MKVUTIL_TRACK_YELLOW"
      metadata_preview=$'--------------------------  Output track layout --------------------------\n'
      metadata_preview+="$(_mkvutil_render_track_view "$track_view" "$MKVUTIL_TRACK_RED" "$preview_yellow" "$highlight_ids")" || return 1
      for item in "${order_ids[@]}"; do
        item_position="${MKVUTIL_RETAINED_IDS[(Ie)$item]}"
        (( item_position > 0 )) || return 1
        [[ -z "$metadata_targets" ]] || metadata_targets+=,
        metadata_targets+="$(( item_position-1 ))"
      done
      while true; do
        mkvutil_batch_metadata_requested '' || return 1
        _mkvutil_menu_read metadata mux 'Metadata [none]: ' "$metadata_targets" "$metadata_error" "$metadata_preview" || return $?
        metadata_error=""
        case "$REPLY" in e|E) return 4 ;; esac
        metadata="$REPLY"
        if [[ -z "${metadata//[[:space:]]/}" ]]; then metadata=""; _mkvutil_ui_leave; break; fi
        result=0
        _mkvutil_menu_choices edit "$metadata" || result=$?
        if (( result == 3 )); then
          metadata_error="Invalid choices. Available: ${(j:,:)MKVUTIL_METADATA_IDS}"
          continue
        fi
        (( result == 0 )) || return "$result"
        metadata="$REPLY"
        _mkvutil_ui_leave
        mkvutil_batch_metadata_requested "$metadata" || return 1
        result=0
        mkvutil_metadata_configure "$metadata" "$metadata_mode" "${(j:,:)order_ids}" "$projection" "$track_view" || result=$?
        if (( result == 4 )); then
          metadata=""
          mkvutil_batch_metadata_requested '' || return 1
          continue
        fi
        (( result == 0 )) || return "$result"
        break
      done
      ;;
    extract)
      if [[ ",$operations," == *,2,* ]]; then
        _mkvutil_read_track_ids 'Extract IDs: ' "${(j:,:)MKVUTIL_INPUT_IDS}" || return $?
        extract_ids="$REPLY"
      fi
      ;;
    *) return 1 ;;
  esac
  settings="$(_mkvutil_json_map "${(@kv)MKVUTIL_METADATA_SETTINGS}")" || return 1
  if [[ "$category" == mux ]]; then
    output_map="$(jq -cn --argjson settings "$settings" --argjson view "$track_view" '
      ([$settings|keys[]|split(":")[1]|select(.!="info")]|unique) as $targets |
      reduce ($view[]|select(.dropped|not)|select(.source_id as $id|$targets|index($id))) as $row
        ({}; .[$row.display_id]=$row.source_id)')" || return 1
  fi
  MKVUTIL_CONFIG="$(jq -cn --arg category "$category" --arg operations "$operations" \
    --arg removal "$removal" --arg order "$order" --arg metadata "$metadata" --arg extract "$extract_ids" \
    --argjson order_ids "$(_mkvutil_json_array "${order_ids[@]}")" \
    --argjson expected_codecs "$(jq -c '[.tracks[]|{key:(.id|tostring),value:.properties.codec_id}]|from_entries' <<< "$raw")" \
    --argjson output_map "$output_map" --argjson settings "$settings" --argjson expected_types "$expected" --arg reference "$source" --argjson signatures "$signatures" \
    --argjson track_count "$(jq '.model.tracks|length' <<< "$reference")" --argjson bypass "$MKVUTIL_BYPASS_TRACK_COUNT" '
    {category:$category, operations:($operations|split(",")), removed_ids:($removal|split(",")|map(select(length>0))),
     order:$order, order_ids:$order_ids, metadata:$metadata, settings:$settings, expected_types:$expected_types,
     extract_ids:($extract|split(",")|map(select(length>0))), reference:$reference, removal_signatures:$signatures,
     reference_track_count:$track_count,bypass_track_count:($bypass==1)}
     + (if $category=="mux" then {metadata_output_map:$output_map,expected_codecs:$expected_codecs} else {} end)')" || return 1
  MKVUTIL_REMOVAL_SKIPS=()
}

# Only requested original IDs define removal compatibility. Reference codec
# values must be usable strings; metadata and other tracks are not signatures.
mkvutil_removal_signatures() {
  printf '%s\n' "$1" | jq -ec --arg ids "$2" '
    . as $reference | reduce ($ids|split(",")[]) as $id ({};
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
  receipt="$(_mkvutil_jq_records '
    .[0] as $record | .[1] as $config | if $config.category!="mux" or ($config.removed_ids|length)==0 then empty else
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
      (if $config.bypass_track_count!=true and ($record.model.tracks|length)!=$config.reference_track_count then
         {expected:$config.reference_track_count,actual:($record.model.tracks|length)} else null end) as $count_mismatch |
      if ($reasons|length)==0 and $count_mismatch==null then empty else
        {schema:1,kind:"removal-mismatch",source:$record.source,identity:$record.identity,
         reference:$config.reference,requested_ids:$config.removed_ids,reasons:$reasons,
         track_count_mismatch:$count_mismatch,outputs:[],propedit_args:[],merge_metadata_args:[]} end
    end' "$1" "$2")" || return 1
  [[ -n "$receipt" ]] || return 0
  print -r -- "$receipt"
  return 3
}

# Share the exact target union between configuration validation and per-source
# eligibility. Container title settings and attachments introduce no track IDs.
_mkvutil_target_rules() {
  print -r -- 'def targeted_ids:
    (.removed_ids + .order_ids + .extract_ids +
      [.settings|keys[]|split(":")[1]|select(.!="info")])|unique;'
}

mkvutil_target_mismatch() {
  local receipt=""
  mkvutil_validate_config "$2" || return 1
  receipt="$(_mkvutil_jq_records "$(_mkvutil_target_rules)"$'\n''
    .[0] as $record | .[1] as $config | ($config|targeted_ids) as $ids |
    if ($record.model.tracks|type)!="array" or
      any($record.model.tracks[]; (.id|type)!="number" or .id<0 or .id!=(.id|floor) or
        (.type!="video" and .type!="audio" and .type!="subtitles")) or
      ($record.model.tracks|map(.id)|unique|length)!=($record.model.tracks|length)
    then error("invalid source track model") else . end |
    [(if ($config|has("metadata_output_map")) then empty else $ids[] end) as $id |
      ([$record.model.tracks[]|select((.id|tostring)==$id)]|first) as $track |
      {original_id:$id,expected:{type:$config.expected_types[$id]},
       actual:(if $track==null then null else {type:$track.type} end),
       reason:(if $track==null then "missing-id"
         elif $track.type!=$config.expected_types[$id] then "type-mismatch" else null end)} |
      select(.reason!=null)] as $target_reasons |
    ([$record.model.tracks[]|.id|tostring] as $actual_ids |
      ($config.order_ids + [$actual_ids[] as $id |
        select(($config.removed_ids|index($id))==null and ($config.order_ids|index($id))==null) | $id]) as $final_ids |
      (reduce ($final_ids|to_entries[]) as $entry ({}; .[$entry.key|tostring]=$entry.value)) as $positions |
      [($config.metadata_output_map // {} | to_entries[]) |
        .key as $output | .value as $source | $positions[$output] as $actual |
        select($actual!=$source) |
        {output_id:$output,original_id:$source,reason:"output-position-mismatch",
         expected:{original_id:$source},actual:(if $actual==null then null else {original_id:$actual} end)}]) as $output_reasons |
    (if ($config|has("metadata_output_map")) then
      [$config.expected_types|to_entries[] | .key as $id | .value as $type |
        $config.expected_codecs[$id] as $codec |
        ([$record.model.tracks[]|select((.id|tostring)==$id)]|first) as $track |
        {original_id:$id,expected:{type:$type,codec_id:$codec},
         actual:(if $track==null then null else {type:$track.type,codec_id:$track.properties.codec_id} end),
         reason:(if $track==null then "missing-id"
           elif $track.type!=$type and $track.properties.codec_id!=$codec then "type-and-codec-mismatch"
           elif $track.type!=$type then "type-mismatch"
           elif $track.properties.codec_id!=$codec then "codec-mismatch" else null end)} |
        select(.reason!=null)] +
      (if ($config.removed_ids|length)>0 and $config.bypass_track_count==true then [] else
        [$record.model.tracks[] | . as $track | (.id|tostring) as $id |
          select(($config.expected_types|has($id))|not) |
          {original_id:$id,reason:"unexpected-id",expected:null,actual:{type:$track.type}}] end)
     else [] end) as $tree_reasons |
    ($target_reasons + $tree_reasons + $output_reasons) as $reasons |
    if ($reasons|length)==0 then empty else
      {schema:1,kind:"track-mismatch",source:$record.source,identity:$record.identity,
       reference:($config.reference // $record.source),requested_ids:$ids,reasons:$reasons,
       track_count_mismatch:null,outputs:[],propedit_args:[],merge_metadata_args:[]} end
    ' "$1" "$2")" || return 1
  [[ -n "$receipt" ]] || return 0
  print -r -- "$receipt"
  return 3
}

_mkvutil_identity_rules() {
  print -r -- 'def valid_identity:
    type=="object" and keys==["dev","ino","mtime_ns","size"] and
    all(.dev,.ino,.size; type=="string" and test("^[0-9]+$")) and
    (.mtime_ns|type)=="string" and (.mtime_ns|test("^-?[0-9]+$"));'
}

# Only a verified comparison of complete stat identities can omit a changed
# source. Missing/malformed evidence remains a failure, never a mismatch skip.
mkvutil_source_mismatch() {
  local receipt=""
  receipt="$(_mkvutil_jq_records "$(_mkvutil_identity_rules)"$'\n''
    if length!=3 then error("invalid source identity records") else . end |
    .[0] as $record | .[1] as $actual | .[2] as $config |
    if ($record.source|type)!="string" or ($record.source|startswith("/")|not) or
      ($record.source|contains("\u0000")) or ($record.identity|valid_identity|not) or
      ($actual|valid_identity|not) then error("invalid source identity")
    elif $record.identity==$actual then empty else
      {schema:1,kind:"source-changed",source:$record.source,identity:$record.identity,
       expected_identity:$record.identity,actual_identity:$actual,
       reference:($config.reference // $record.source),
       reason:"Source changed after inspection/planning; file was not processed",
       requested_ids:[],reasons:[],track_count_mismatch:null,
       outputs:[],propedit_args:[],merge_metadata_args:[]} end
    ' "$1" "$2" "$3")" || return 1
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
  jq -e "$(_mkvutil_target_rules)"$'\n''
    . as $config |
    def canonical_id: type=="string" and test("^(0|[1-9][0-9]*)$");
    def unique_ids: all(.[]; canonical_id) and (unique|length)==length;
    def output_positions: . as $config |
      [.expected_types|keys[] | . as $id | select(($config.removed_ids|index($id))==null)] |
      to_entries | map(.key|tostring);
    (.category=="edit" or .category=="mux" or .category=="extract") and
    (.operations|type)=="array" and (.operations|length)>0 and
    (.removed_ids|type)=="array" and (.order_ids|type)=="array" and (.extract_ids|type)=="array" and
    (.order|type)=="string" and (.settings|type)=="object" and (.expected_types|type)=="object" and
    all(.settings[]; type=="string") and
    all(.removed_ids[],.order_ids[],.extract_ids[]; type=="string" and test("^[0-9]+$")) and
    all(targeted_ids[]; . as $id | type=="string" and test("^[0-9]+$") and
      ($config.expected_types[$id] as $type | $type=="video" or $type=="audio" or $type=="subtitles")) and
    (if .category=="edit" then (.removed_ids|length)==0 and .order=="" and (.extract_ids|length)==0
     elif .category=="mux" then (.extract_ids|length)==0 and all(.operations[]; .=="1" or .=="2")
     else (.removed_ids|length)==0 and .order=="" and (.settings|length)==0 and all(.operations[]; .=="1" or .=="2") end) and
    (if has("metadata_output_map") then
      .category=="mux" and (.metadata_output_map|type)=="object" and
      (.removed_ids|unique_ids) and (.order_ids|unique_ids) and
      all(.order_ids[]; . as $id | ($config.removed_ids|index($id))==null) and
      .order==(.order_ids|map("0:"+.)|join(",")) and
      (.expected_types|length)>0 and (.expected_codecs|type)=="object" and
      (.expected_codecs|keys)==(.expected_types|keys) and
      all(.expected_codecs[]; type=="string" and test("[^[:space:]]")) and
      (.reference_track_count|type)=="number" and .reference_track_count>0 and
      .reference_track_count==(.reference_track_count|floor) and
      (.expected_types|length)==.reference_track_count and
      all(.expected_types|to_entries[]; (.key|canonical_id) and
        (.value=="video" or .value=="audio" or .value=="subtitles")) and
      all(.settings|keys[]; (split(":")) as $key | ($key|length)==2 and
        ($key[0]|canonical_id) and ($key[1]=="info" or ($key[1]|canonical_id))) and
      all(.metadata_output_map|keys[]; . as $key | ($config|output_positions|index($key))!=null) and
      all(.metadata_output_map|to_entries[]; (.key|canonical_id) and (.value|canonical_id) and
        (.value as $id | ($config.removed_ids|index($id))==null)) and
      ([.metadata_output_map[]]|unique|length)==(.metadata_output_map|length) and
      ([.metadata_output_map[]]|sort)==([.settings|keys[]|split(":")[1]|select(.!="info")]|unique|sort)
     else true end) and
    (if .category=="mux" and (.removed_ids|length)>0 then
      (.reference|type)=="string" and (.reference|length)>0 and (.removal_signatures|type)=="object" and
      (.reference_track_count|type)=="number" and .reference_track_count>0 and
      .reference_track_count==(.reference_track_count|floor) and
      .reference_track_count>=(.removed_ids|length) and
      (if has("bypass_track_count") then (.bypass_track_count|type)=="boolean" else true end) and
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
  local args="" input_ids="" retained="" selectors="" types="" flags="" codec_map='{}' overrides="" registry="" choices="" mismatch="" aliases="" result=0
  _mkvutil_clear_plan_layout
  mkvutil_metadata_reset
  MKVUTIL_CURRENT_JOB=""
  mkvutil_validate_config "$config" || return 1
  file="$(jq -r '.source' <<< "$record")" || return 1
  identity="$(mkvutil_source_identity "$file")" || return 1
  mismatch="$(mkvutil_source_mismatch "$record" "$identity" "$config")" || result=$?
  if (( result != 0 )); then
    (( result != 3 )) || print -r -- "$mismatch"
    return "$result"
  fi
  local guard=""
  for guard in mkvutil_removal_mismatch mkvutil_target_mismatch; do
    result=0
    mismatch="$("$guard" "$record" "$config")" || result=$?
    if (( result != 0 )); then
      (( result != 3 )) || print -r -- "$mismatch"
      return "$result"
    fi
  done
  category="$(jq -r '.category' <<< "$config")" || return 1
  raw="$(jq -r '.source_json' <<< "$record")" || return 1
  rows="$(collect_tracks_for_remux "$file" "$raw")" || return 1
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
  aliases="$(_mkvutil_json_map "${(@kv)MKVUTIL_CODEC_ALIASES}")" || return 1
  _mkvutil_jq_records '
    .[0] as $record | .[1] as $config | .[2] as $args | .[3] as $inputs |
    .[4] as $retained | .[5] as $selectors | .[6] as $types | .[7] as $flags |
    .[8] as $options | $options.extension as $extension | $options.track_order as $track_order |
    .[9] as $codec_map | .[10] as $overrides | .[11] as $registry | .[12] as $choices | .[13] as $aliases |
    def codec_extension($cid):
      ($cid|split("/")|last) as $key | ($aliases[$cid] // ($cid|sub("^[AVS]_";""))) as $canonical |
      $overrides[$cid] // $overrides[$key] // $overrides[$canonical] //
      $codec_map[$cid] // $codec_map[$key] // $codec_map[$canonical] // ($key|ascii_downcase|gsub("[^a-z0-9]";""));
    def artifacts($path;$codec):
      if $codec=="S_VOBSUB" then
        [{path:($path|sub("\\.[^.]+$";".sub")),role:"vobsub_data",required:true},
         {path:($path|sub("\\.[^.]+$";".idx")),role:"vobsub_index",required:true}]
      elif $codec=="A_WAVPACK4" then
        [{path:$path,role:"primary",required:true},
         {path:($path|sub("\\.[^.]+$";".wvc")),role:"wavpack_correction",required:false}]
      else [{path:$path,role:"primary",required:true}] end;
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
           ($a.file_name|test("[/\\\\]")) or ($a.file_name|contains("\u0000")) or $a.file_name=="." or $a.file_name==".."
         then error("unsafe attachment filename") else
           {kind:"attachment", id:($a.id|tostring), codec:null,expected_size:($a.size // null),
            path:($job.destination+"/"+$a.file_name)} end
       else empty end,
       $config.extract_ids[] as $id | $record.model.tracks[] | select((.id|tostring)==$id) |
       (.properties.codec_id // "") as $cid | codec_extension($cid) as $ext |
       if ($ext|length)==0 or ($ext|test("^[a-zA-Z0-9]+$")|not) then error("unknown extraction extension")
       else {kind:"track", id:$id, codec:$cid, path:($job.source|sub("\\.[^.]+$";""))+" - Track ["+$id+"]."+$ext} end]
      end) |
    .outputs |= map(if type=="object" then . + {artifacts:artifacts(.path;.codec)} else . end) |
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
  ' "$record" "$config" "$args" "$input_ids" "$retained" "$selectors" "$types" "$flags" \
    "$(jq -cn --arg extension "$MKVUTIL_OUTPUT_EXTENSION" --arg track_order "$MKVUTIL_TRACK_ORDER" '{extension:$extension,track_order:$track_order}')" \
    "$codec_map" "$overrides" "$registry" "$choices" "$aliases"
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
  local protected='[]'
  (( ! MKVUTIL_LEDGER_ENABLED )) || protected="$(_mkvutil_json_array "${MKVUTIL_SCOPE_KEYS[@]}")" || return 1
  printf '%s\0' "$protected" "$@" | python3 -c '
import json, os, stat, sys, unicodedata
from pathlib import Path
try:
    records = [json.loads(record) for record in sys.stdin.buffer.read().split(b"\0") if record]
    protected, jobs = records[0], records[1:]
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
            raise ValueError(f"Output parent is not a regular directory: {parent.name}")
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
            raise ValueError(f"Duplicate source alias: {source.name}")
        sources[key] = source
    input_keys = set(sources)
    input_inodes = set()
    for path in {Path(value) for value in protected} | set(sources.values()):
        input_keys.add(destination_key(path, path))
        if os.path.lexists(path):
            item = path.lstat()
            if stat.S_ISREG(item.st_mode):
                input_inodes.add((item.st_dev, item.st_ino))
    destinations = {}
    for job in jobs:
        source = Path(job["source"])
        source_key = destination_key(source, source)
        for output in job["outputs"]:
            kind = output.get("kind") if isinstance(output, dict) else None
            artifacts = output.get("artifacts", [{"path": output["path"]}]) if isinstance(output, dict) else [{"path": output}]
            for artifact in artifacts:
                path = Path(artifact["path"])
                key = destination_key(path, source)
                previous = destinations.get(key)
                if previous and not (kind == previous["kind"] == "attachment"):
                    raise ValueError(f"Destination collision or filename alias: {path.name}")
                destinations[key] = {"path": path, "kind": kind}
                if job["config"]["category"] != "extract" and key == source_key:
                    continue
                if key in input_keys:
                    raise ValueError(f"Destination aliases input media: {path.name}")
                if os.path.lexists(path):
                    item = path.lstat()
                    if kind != "attachment" or not stat.S_ISREG(item.st_mode):
                        raise ValueError(f"Destination already exists or is unsafe: {path.name}")
                    if (item.st_dev, item.st_ino) in input_inodes:
                        raise ValueError(f"Attachment destination inode aliases input media: {path.name}")
except (OSError, ValueError, KeyError, TypeError) as error:
    if isinstance(error, OSError):
        names = [Path(value).name for value in (error.filename, error.filename2) if value]
        print(f"{error.strerror}: " + ", ".join(names), file=sys.stderr)
    else:
        print(str(error), file=sys.stderr)
    sys.exit(1)
'
}

mkvutil_report_removal_skips() {
  _mkvutil_indicator_stop
  local receipt="" display=""
  for receipt in "$@"; do
    display="$(_mkvutil_display_record "$receipt")" || return 1
    jq -r '
      "Skipped \(if .kind=="source-changed" then "source changed" elif .kind=="track-mismatch" then "track mismatch" else "removal mismatch" end): \(.source)", "  Reference: \(.reference)",
      (if (.reason // "")!="" then "  \(.reason)" else empty end),
      (if .track_count_mismatch then "  Track count mismatch: expected \(.track_count_mismatch.expected); actual \(.track_count_mismatch.actual)" else empty end),
      (.reasons[] | (if .reason=="output-position-mismatch" then "  Output ID \(.output_id): expected source ID \(.expected.original_id); actual source ID \(.actual.original_id // "missing")"
          else "  Original ID \(.original_id): \(.reason); expected=\(.expected|tojson) actual=\(.actual|tojson)" end))
    ' <<< "$display" || return 1
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

# The scope pool survives automatic skips and configuration Back. Only an explicit
# exclusion removes a source. Status 3 means an all-mismatch queue, with receipts
# still available; any other planning error requires the ordinary exclude policy.
mkvutil_plan_queue() {
  local record="" job="" file="" result=0 diagnostics_file=""
  local -a jobs=() scope=()
  if [[ -t 1 && -n "${TERM-}" && "$TERM" != dumb ]]; then
    diagnostics_file="$(mktemp "${TMPDIR:-/tmp}/mkvutil-planning.XXXXXXXX")" || return 1
  fi
  {
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_PROPEDIT_ARGS=()
  MKVUTIL_MERGE_METADATA_ARGS=()
  MKVUTIL_CURRENT_JOB=""
  for record in "${MKVUTIL_SOURCES[@]}"; do
    result=0
    if [[ -n "$diagnostics_file" ]]; then
      : > "$diagnostics_file" || return 1
      [[ -n "$MKVUTIL_INDICATOR_PID" ]] || _mkvutil_indicator_start Working || return 1
      {
        job="$(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG" 2>"$diagnostics_file")" || result=$?
      } always {
        (( result == 0 || result == 3 )) || _mkvutil_indicator_stop
      }
      if [[ -s "$diagnostics_file" ]]; then
        _mkvutil_indicator_stop
        cat "$diagnostics_file" >&2 || return 1
      fi
    else
      job="$(mkvutil_plan_job "$record" "$MKVUTIL_CONFIG")" || result=$?
    fi
    if (( result == 0 )); then
      jobs+=("$job")
      scope+=("$record")
    elif (( result == 3 )); then
      MKVUTIL_REMOVAL_SKIPS+=("$job")
      mkvutil_ledger_skip "$job" || return 1
      scope+=("$record")
    else
      file="$(jq -r '.source' <<< "$record")"
      _mkvutil_indicator_stop
      print -u2 -r -- "Cannot plan source: ${file:t}"
      _mkvutil_exclude || { result=$?; return "$result"; }
      mkvutil_ledger_exclude "$file" 'Source could not be planned' || return 1
      _mkvutil_remove_scope_source "$file"
    fi
  done
  MKVUTIL_SOURCES=("${scope[@]}")
  _mkvutil_indicator_stop
  mkvutil_report_removal_skips "${MKVUTIL_REMOVAL_SKIPS[@]}" || return 1
  mkvutil_batch_planned "${#jobs}" || return 1
  if (( ${#jobs} == 0 )); then
    (( ${#MKVUTIL_REMOVAL_SKIPS} > 0 )) && return 3
    _mkvutil_indicator_stop
    print -u2 -r -- 'No valid jobs remain.'
    return 1
  fi
  mkvutil_check_destinations "${jobs[@]}" || return 1
  MKVUTIL_JOBS=("${jobs[@]}")
  } always {
    _mkvutil_indicator_stop
    [[ -z "$diagnostics_file" ]] || rm -f "$diagnostics_file" || true
  }
}

# Prepare a fresh scope from mismatch receipts only. Pending eligible jobs may
# not be discarded. This internal planning helper does not execute jobs or
# provide a continuation menu in the interactive entrypoint.
mkvutil_prepare_skipped_subset() {
  local receipt="" file="" record="" result=0
  local -a paths=() sources=()
  (( ${#MKVUTIL_JOBS} == 0 && ${#MKVUTIL_REMOVAL_SKIPS} > 0 )) || {
    print -u2 -r -- 'Skipped-subset preparation requires mismatch skips and no pending eligible jobs.'; return 1;
  }
  for receipt in "${MKVUTIL_REMOVAL_SKIPS[@]}"; do
    IFS= read -r -d '' file < <(jq -esj "$(_mkvutil_identity_rules)"$'\n''
      def valid_count:
        type=="object" and (.expected|type)=="number" and (.actual|type)=="number" and
        .expected>0 and .actual>=0 and .expected==(.expected|floor) and .actual==(.actual|floor) and .expected!=.actual;
      if length==1 and (.[0].source|type)=="string" and
        (.[0].source|startswith("/")) and (.[0].source|contains("\u0000")|not) and
        (.[0] | if .kind=="removal-mismatch" then
            (.reasons|type)=="array" and ((.reasons|length)>0 or (.track_count_mismatch|valid_count))
          elif .kind=="track-mismatch" then (.reasons|type)=="array" and (.reasons|length)>0
          elif .kind=="source-changed" then
            (.identity|valid_identity) and (.expected_identity|valid_identity) and (.actual_identity|valid_identity) and
            .identity==.expected_identity and .expected_identity!=.actual_identity and
            (.reason|type)=="string" and (.reason|test("[^[:space:]]"))
          else false end)
      then .[0].source,"\u0000" else error("invalid skipped source receipt") end' <<< "$receipt") || return 1
    paths+=("$file")
  done
  local previous="" duplicate=0
  for receipt in "${MKVUTIL_REMOVAL_SKIPS[@]}"; do
    duplicate=0
    for previous in "${MKVUTIL_REMOVAL_SKIP_HISTORY[@]}"; do
      _mkvutil_jq_records '.[0]==.[1]' "$receipt" "$previous" | jq -e . >/dev/null && duplicate=1
    done
    (( duplicate )) || MKVUTIL_REMOVAL_SKIP_HISTORY+=("$receipt")
  done
  MKVUTIL_CONFIG=""
  MKVUTIL_CURRENT_JOB=""
  MKVUTIL_JOBS=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_SOURCES=()
  MKVUTIL_SELECTED_FILES=("${paths[@]}")
  mkvutil_metadata_reset
  _mkvutil_clear_plan_layout
  for file in "${paths[@]}"; do
    result=0
    _mkvutil_cohort_eligible "$file" || result=$?
    (( result != 1 )) || return 1
    (( result == 0 )) || continue
    if record="$(mkvutil_capture_source "$file")"; then
      jq -es --arg source "$file" 'length==1 and (.[0]|type)=="object" and .[0].source==$source' <<< "$record" >/dev/null || return 1
      sources+=("$record")
    else
      print -u2 -r -- "Fresh skipped-source inspection failed: ${file:t}"
      _mkvutil_exclude || { result=$?; return "$result"; }
      mkvutil_ledger_exclude "$file" 'Fresh skipped-source inspection failed; mismatch remains unresolved' || return 1
    fi
  done
  (( ${#sources} > 0 )) || { print -u2 -r -- 'No valid skipped sources remain.'; return 1; }
  MKVUTIL_SOURCES=("${sources[@]}")
  jq -r '"Fresh skipped-subset reference: \(.source|split("/")[-1])"' <<< "${MKVUTIL_SOURCES[1]}"
}

mkvutil_cancel_status() {
  (( ! MKVUTIL_LEDGER_ENABLED )) || { mkvutil_ledger_status; return $?; }
  (( ${#MKVUTIL_REMOVAL_SKIPS} == 0 && ${#MKVUTIL_REMOVAL_SKIP_HISTORY} == 0 ))
}

mkvutil_preview_jobs() {
  _mkvutil_indicator_stop
  local job="" display="" show_attachment_policy=1
  if (( MKVUTIL_LEDGER_ENABLED )); then
    local source="" entry=""
    for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do
      entry="${MKVUTIL_LEDGER[$source]}"
      display="$(_mkvutil_display_record "$entry")" || return 1
      jq -r '.source as $source | .skip_history[] |
        "Previous skip \(if .resolved then "resolved" else "unresolved" end): \($source)",
        (if (.receipt.reason // "")!="" then "  \(.receipt.reason)" else empty end),
        (if .receipt.track_count_mismatch then "  Track count mismatch: expected \(.receipt.track_count_mismatch.expected); actual \(.receipt.track_count_mismatch.actual)" else empty end),
        (.receipt.reasons[] | (if .reason=="output-position-mismatch" then "  Output ID \(.output_id): expected source ID \(.expected.original_id); actual source ID \(.actual.original_id // "missing")"
          else "  Original ID \(.original_id): \(.reason); expected=\(.expected|tojson) actual=\(.actual|tojson)" end))' <<< "$display" || return 1
    done
  elif (( ${#MKVUTIL_REMOVAL_SKIP_HISTORY} > 0 )); then
    print -r -- 'Previous skipped-scope receipts (execution unresolved):'
    mkvutil_report_removal_skips "${MKVUTIL_REMOVAL_SKIP_HISTORY[@]}" || return 1
  fi
  mkvutil_report_removal_skips "${MKVUTIL_REMOVAL_SKIPS[@]}" || return 1
  for job in "${MKVUTIL_JOBS[@]}"; do
    display="$(_mkvutil_display_record "$job")" || return 1
    jq -r --argjson show_policy "$show_attachment_policy" '
      (if $show_policy==1 and .config.category=="extract" and (.config.operations|index("1")) then
        "Attachments: shared collection; overwrite regular same-name files in selected-source and embedded-list order; last successful publication wins." else empty end),
      "Source: \(.source)", "Category: \(.config.category)", "Destination: \(.destination)",
      "Title: \(.preview.title // "")",
      (.config.removed_ids[] | "Original ID \(.): removed"),
      (.requested_metadata[] | "Metadata: \(.label) — \(.original_id) \(.property)=\(.value|tojson)"),
      (.preview.tracks[] | "Original ID \(.original_id) => final position \(.final_position): \(.type) [\(.codec)] name=\(.name|tojson) language=\(.language|tojson) default=\(.default) forced=\(.forced)"),
      (.outputs[] | select(type=="object") | "Extract \(.kind) \(.id): \(.path)",
        (.artifacts[] | "  Artifact \(.role) (\(if .required then "required" else "optional" end)): \(.path)"))
    ' <<< "$display" || return 1
    show_attachment_policy=0
  done
}

# Executors return one JSON result in MKVUTIL_RESULT_JSON. Queue consumers own
# outcome history; each job receives an explicit immutable plan record.
typeset -g MKVUTIL_RESULT_JSON=""
typeset -ga MKVUTIL_RESULTS=()

_mkvutil_execution_failure() {
  local job="$1" reason="$2" status_name="${3:-failed}"
  _mkvutil_jq_records '. [0] as $job | .[1] as $reason | .[2] as $status |
    {source:$job.source,destination:$job.destination,category:$job.config.category,
     action_ids:$job.config.operations,metadata_ids:$job.config.metadata,
     status:$status,native_code:null,phase:"preflight",actual_state:"not_modified_by_job",
     reason:$reason,candidate_path:null,staging_directory:null}' \
    "$job" "$(_mkvutil_json_array "$reason" | jq -c '.[0]')" "$(_mkvutil_json_array "$status_name" | jq -c '.[0]')"
}

_mkvutil_execution_skip() {
  local job="$1" receipt="$2" reason=""
  reason="$(jq -er '
    if .kind=="source-changed" then .reason
    elif .kind=="removal-mismatch" then "Removal track requirements do not match; file was not processed"
    elif .kind=="track-mismatch" then
      if any(.reasons[]; .reason=="output-position-mismatch") then "Output track positions do not match the configured layout; file was not processed"
      else "Selected track IDs or the original track tree do not match; file was not processed" end
    else error("invalid skip receipt kind") end' <<< "$receipt")" || return 1
  _mkvutil_jq_records '.[0]+{skip_receipt:.[1],artifacts:[],planned_outputs:[],publications:[]}' \
    "$(_mkvutil_execution_failure "$job" "$reason" skipped)" "$receipt"
}

# Both real execution paths recheck the same source identity and eligibility
# before entering an engine. Return the fresh captured source through REPLY.
_mkvutil_preflight_job() {
  local job="$1" config="" file="" fresh="" mismatch="" guard="" result=0 identity=""
  config="$(jq -c '.config' <<< "$job")" || return 1
  if ! mkvutil_validate_config "$config"; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Invalid planned configuration')"
    return 1
  fi
  file="$(jq -r '.source' <<< "$job")" || return 1
  if ! _mkvutil_capture_execution_source "$file"; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Source inspection stopped or failed before execution' "$([[ $MKVUTIL_INTERRUPTED == 1 ]] && print not_attempted || print failed)")"
    return 1
  fi
  fresh="$REPLY"
  if ! jq -e --arg source "$file" '.source==$source' <<< "$fresh" >/dev/null; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Invalid fresh source record')"
    return 1
  fi
  identity="$(jq -c '.identity' <<< "$fresh")" || return 1
  mismatch="$(mkvutil_source_mismatch "$job" "$identity" "$config")" || result=$?
  if (( result == 0 )); then
    for guard in mkvutil_removal_mismatch mkvutil_target_mismatch; do
      mismatch="$("$guard" "$fresh" "$config")" || result=$?
      (( result == 0 )) || break
    done
  fi
  if (( result != 0 )); then
    if (( result == 3 )); then
      MKVUTIL_RESULT_JSON="$(_mkvutil_execution_skip "$job" "$mismatch")" || return 1
    else
      MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Invalid source identity or track requirements before execution')"
    fi
    mkvutil_metadata_reset
    _mkvutil_clear_plan_layout
    return 1
  fi
  REPLY="$fresh"
}

# Consume the already validated plan without native inspection or filesystem
# writes. Only a fresh source stat is needed before reporting intended outputs.
mkvutil_simulate_job() {
  local job="$1" source="" identity="" reason="" mismatch="" config="" result_code=0
  MKVUTIL_RESULT_JSON=""
  source="$(jq -er '.source | select(type=="string" and startswith("/"))' <<< "$job")" || return 1
  config="$(jq -c '.config' <<< "$job")" || return 1
  if ! mkvutil_validate_config "$config"; then
    reason='Invalid planned configuration'; result_code=1
  elif (( MKVUTIL_INTERRUPTED )); then
    reason='Stopped before simulation'; result_code=1
  elif ! identity="$(mkvutil_source_identity "$source")"; then
    reason='Source unavailable before simulation'; result_code=1
  else
    mismatch="$(mkvutil_source_mismatch "$job" "$identity" "$config")" || result_code=$?
    if (( result_code == 3 )); then
      MKVUTIL_RESULT_JSON="$(_mkvutil_execution_skip "$job" "$mismatch")" || return 1
      MKVUTIL_RESULT_JSON="$(jq -c '.+{dry_run:true,simulated:false}' <<< "$MKVUTIL_RESULT_JSON")" || return 1
      return 1
    elif (( result_code != 0 )); then
      reason='Invalid source identity before simulation'
    fi
  fi
  if (( result_code )); then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" "$reason" "$([[ $MKVUTIL_INTERRUPTED == 1 ]] && print not_attempted || print failed)")" || return 1
    MKVUTIL_RESULT_JSON="$(jq -c '.+{dry_run:true,simulated:false,planned_outputs:[],artifacts:[],publications:[]}' <<< "$MKVUTIL_RESULT_JSON")" || return 1
    return 1
  fi
  MKVUTIL_RESULT_JSON="$(jq -c '
    . as $job |
    {source:.source,destination:.destination,category:.config.category,
     action_ids:.config.operations,metadata_ids:.config.metadata,
     status:"success",dry_run:true,simulated:true,native_code:null,
     phase:"simulated",actual_state:"not_modified_by_job",reason:"",
     candidate_path:null,staging_directory:null,artifacts:[],publications:[],stages:[],
     planned_outputs:[.outputs[] |
       if type=="string" then {path:.,kind:$job.config.category,id:null,required:true}
       else . as $output | (.artifacts // [{path:.path,required:true}])[] |
         {path:.path,kind:$output.kind,id:$output.id,required:(.required // false)} end]}
    ' <<< "$job")" || return 1
  return 0
}

_mkvutil_execution_support() {
  cat <<'PYCOMMON'
import os, signal, stat, subprocess, sys, time
import queue
import threading


class NativeOutputRenderer:
    """Replace known paths across chunks before framing native text records."""

    def __init__(self, paths):
        replacements = {os.fsencode(str(path)): os.fsencode(str(label))
                        for path, label in paths if str(path)}
        self.replacements = sorted(replacements.items(), key=lambda item: -len(item[0]))
        self.pending = b""
        self.record = b""
        self.last = b""
        self.line_start = True
        self.initials = {path[0] for path, _ in self.replacements}
        self.max_path = max((len(path) for path, _ in self.replacements), default=0)

    def _sanitize(self, data, final=False):
        pending = self.pending + data
        offset = 0
        output = bytearray()
        while offset < len(pending):
            tail = pending[offset:] if len(pending) - offset <= self.max_path else None
            matches = [(path, label) for path, label in self.replacements
                       if tail is not None and path.startswith(tail)]
            if matches and not final:
                # A full shorter key may also prefix a longer key. Wait until
                # the next chunk distinguishes them; no pathname prefix leaks.
                exact = next(((path, label) for path, label in matches
                              if path == tail), None)
                if exact and len(matches) == 1:
                    output.extend(exact[1]); offset = len(pending)
                break
            complete = next(((path, label) for path, label in self.replacements
                             if pending.startswith(path, offset)), None)
            if complete:
                output.extend(complete[1]); offset += len(complete[0])
            elif matches and final:
                output.extend(b"[path]"); offset = len(pending)
            else:
                # Copy ordinary text in one span, stopping at the next possible
                # pathname start. UTF-8 bytes stay intact across output chunks.
                end = offset + 1
                while end < len(pending) and pending[end] not in self.initials:
                    end += 1
                output.extend(pending[offset:end]); offset = end
        self.pending = pending[offset:]
        return bytes(output)

    def _frame(self, data, final=False):
        self.record += data
        output = bytearray()
        while self.record:
            boundary = next((index + 1 for index, byte in enumerate(self.record)
                             if byte in (10, 13)), None)
            if boundary is None:
                if not final and len(self.record) < 4096:
                    break
                boundary = len(self.record) if final else 4096
                if not final:
                    # A different stream may be displayed before the next
                    # snapshot. Keep an incomplete UTF-8 character together.
                    start = boundary - 1
                    while start > max(0, boundary - 4) and self.record[start] & 0xc0 == 0x80:
                        start -= 1
                    lead = self.record[start]
                    size = 2 if 0xc2 <= lead <= 0xdf else 3 if 0xe0 <= lead <= 0xef else 4 if 0xf0 <= lead <= 0xf4 else 1
                    if boundary - start < size:
                        boundary = start
            fragment = self.record[:boundary]
            if self.line_start and fragment[:1] not in (b"\r", b"\n"):
                output.extend(b"  ")
            output.extend(fragment)
            self.line_start = fragment[-1:] in (b"\r", b"\n")
            self.record = self.record[boundary:]
        if output:
            self.last = bytes(output[-1:])
        if final and self.last and self.last != b"\n":
            output.extend(b"\n"); self.last = b"\n"; self.line_start = True
        return bytes(output)

    def feed(self, data):
        return self._frame(self._sanitize(data))

    def finish(self):
        return self._frame(self._sanitize(b"", final=True), final=True)


class NativeDisplayWriter:
    """A stalled display sink cannot block native ownership or stop checks."""

    def __init__(self, fd=3, max_chunks=64, chunk_size=4096):
        self.fd = fd
        self.chunk_size = chunk_size
        self.queue = queue.Queue(maxsize=max_chunks)
        self.disabled = threading.Event()
        self.finished = threading.Event()
        self.closed = False
        self.thread = None

    def _write(self):
        try:
            while not self.disabled.is_set():
                payload = self.queue.get()
                if payload is None:
                    break
                view = memoryview(payload)
                while view and not self.disabled.is_set():
                    written = os.write(self.fd, view)
                    if written <= 0:
                        raise OSError("Native display sink accepted no bytes")
                    view = view[written:]
        except (OSError, ValueError):
            self.disabled.set()
        finally:
            self.finished.set()

    def submit(self, payload):
        if not payload or self.closed or self.disabled.is_set():
            return
        if self.thread is None:
            self.thread = threading.Thread(target=self._write, daemon=True)
            self.thread.start()
        try:
            for offset in range(0, len(payload), self.chunk_size):
                self.queue.put_nowait(bytes(payload[offset:offset + self.chunk_size]))
        except queue.Full:
            self.disabled.set()

    def finish(self, timeout=0.25):
        if self.closed:
            return
        self.closed = True
        if self.thread is None:
            return
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            self.disabled.set()
        # No queue.join() or unbounded thread join. The daemon never owns native
        # readers and cannot outlive the engine into the following file.
        self.finished.wait(timeout)
        if not self.finished.is_set():
            self.disabled.set()


class NativeCaptureDisplay:
    def __init__(self, paths):
        global native_writer
        if native_writer is None:
            native_writer = NativeDisplayWriter()
        self.renderers = [NativeOutputRenderer(paths), NativeOutputRenderer(paths)]
        self.offsets = [0, 0]

    def observe(self, stdout=None, stderr=None):
        # communicate(timeout) snapshots are cumulative; submit only new bytes.
        try:
            for index, value in enumerate((stdout, stderr)):
                if value is None:
                    continue
                if isinstance(value, str):
                    value = value.encode(errors="replace")
                if len(value) > self.offsets[index]:
                    chunk = value[self.offsets[index]:]
                    self.offsets[index] = len(value)
                    if len(chunk) > native_writer.queue.maxsize * native_writer.chunk_size:
                        native_writer.disabled.set()
                        continue
                    native_writer.submit(self.renderers[index].feed(chunk))
        except Exception:
            # Display is observational; raw native buffers remain authoritative.
            native_writer.disabled.set()

    def finish(self):
        try:
            for renderer in self.renderers:
                native_writer.submit(renderer.finish())
        except Exception:
            native_writer.disabled.set()


native_writer = None
native_display = None


def native_display_paths(paths):
    # Exact output mappings take precedence; known directory prefixes also hide
    # native scratch-file paths which are not known until the tool creates them.
    result = list(paths)
    for path, label in paths:
        parent = os.path.dirname(str(path))
        if parent and parent != os.path.sep:
            result.extend(((parent + os.path.sep, ""), (parent, os.path.basename(parent))))
    return result


def observe_native(stdout=None, stderr=None):
    if native_display is not None:
        native_display.observe(stdout, stderr)


def finish_native_display():
    try:
        if native_display is not None:
            native_display.finish()
        if native_writer is not None:
            native_writer.finish()
    except Exception:
        pass

child = None
native_stopped = True
shutdown_error = ""
interrupted = False
stop_requested = False
stop_signal = 0
cleaning_up = False
admitted = False
stop_before_admission = False
owner_pid = int(sys.argv[2])
control_dir = sys.argv[3]
graceful = sys.argv[1] in ("edit", "mux")

class Interrupted(Exception):
    pass

def identity(path):
    item = os.lstat(path)
    if not stat.S_ISREG(item.st_mode):
        raise ValueError(f"Not a regular file entry: {path}")
    return {key: str(value) for key, value in zip(("dev", "ino", "size", "mtime_ns"),
            (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns))}

def inode(path):
    try:
        value = identity(path)
        return value["dev"], value["ino"]
    except (OSError, ValueError):
        return None

def stop_child():
    global child, cleaning_up, native_stopped, shutdown_error
    cleaning_up = True
    if child:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = child.communicate(timeout=2)
            observe_native(stdout, stderr)
        except subprocess.TimeoutExpired as snapshot:
            observe_native(snapshot.output, snapshot.stderr)
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = child.communicate(timeout=2)
            observe_native(stdout, stderr)
        # A descendant may have closed inherited pipes but still be writing.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 0.5
        while True:
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                native_stopped = True
                break
            except PermissionError:
                # A retiring group can temporarily deny the probe on macOS.
                # Keep shutdown unconfirmed until it disappears or times out.
                pass
            if time.monotonic() >= deadline:
                shutdown_error = "Owned native process group shutdown could not be confirmed; candidates retained"
                break
            time.sleep(0.01)

def interrupt(signum, frame):
    global stop_requested, stop_signal, stop_before_admission
    stop_requested = True
    if not admitted:
        stop_before_admission = True
    if stop_signal == 0 or signum != signal.SIGINT:
        stop_signal = signum
    # Latch only. Raising inside Popen acquisition or publication can lose the
    # owned child/actual-state bookkeeping. Guards act at controlled boundaries.

def owner_guard():
    global interrupted
    # The file also covers signals arriving before the engine installed handlers.
    # Cleanup/observation is permitted after interruption, further writes are not.
    if cleaning_up:
        return
    if os.getppid() != owner_pid:
        interrupt(signal.SIGHUP, None)
    try:
        with open(os.path.join(control_dir, "signal")) as stream:
            requested = stream.read().strip()
    except FileNotFoundError:
        requested = ""
    if requested:
        interrupt(int(requested), None)
    if stop_requested and (stop_signal != signal.SIGINT or not graceful or stop_before_admission):
        interrupted = True
        raise Interrupted(f"Interrupted by signal {stop_signal}")

def admit_file():
    global admitted
    owner_guard()
    admitted = True
    with open(os.path.join(control_dir, "admitted"), "w") as stream:
        stream.write("admitted")

def run(argv, timeout=None, cwd=None, display_paths=None):
    global child, native_stopped, native_display
    owner_guard()
    native_display = NativeCaptureDisplay(display_paths) if display_paths is not None else None
    native_stopped = False
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True, cwd=cwd)
    try:
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            owner_guard()
            remaining = deadline - time.monotonic() if deadline is not None else 0.1
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            try:
                stdout, stderr = child.communicate(timeout=min(0.1, remaining))
                observe_native(stdout, stderr)
                owner_guard()
                # communicate() reaps the leader, not descendants which closed
                # its pipes. Do not lose their group handle or certify shutdown.
                try:
                    os.killpg(child.pid, 0)
                except ProcessLookupError:
                    native_stopped = True
                else:
                    raise RuntimeError("Native leader exited with a surviving process group; stopping owned descendants")
                break
            except subprocess.TimeoutExpired as snapshot:
                observe_native(snapshot.output, snapshot.stderr)
                # A dead leader can leave descendants holding its pipes.
                if child.poll() is not None and child.returncode < 0:
                    stop_child()
                    stdout, stderr = child.communicate(timeout=2)
                    observe_native(stdout, stderr)
                    break
    except BaseException:
        stop_child()
        raise
    finally:
        if native_display is not None:
            native_display.finish()
            native_display = None
    code = child.returncode
    child = None
    return code, stdout.decode(errors="replace"), stderr.decode(errors="replace")

for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(signum, interrupt)
with open(os.path.join(control_dir, "ready"), "w") as stream:
    stream.write(str(os.getpid()))
PYCOMMON
}

# Direct child ownership keeps terminal Ctrl+C out of command-substitution
# teardown. Requests/results are private files, so media names stay out of argv.
_mkvutil_launch_engine() {
  setopt localtraps
  local python_bin="$1" program="$2" category="$3" job="$4" transport="" result_code=0 checker_pid=0 checker_code=0
  shift 4
  MKVUTIL_RESULT_JSON=""
  if (( MKVUTIL_DRY_RUN )); then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Native execution blocked in dry run')"
    return 1
  fi
  if (( MKVUTIL_INTERRUPTED )); then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Stopped before execution' not_attempted)"
    return 1
  fi
  transport="$(mktemp -d "${TMPDIR:-/tmp}/mkvutil-engine.XXXXXXXX")" || return 1
  {
    printf '%s\0' "$job" "$@" > "$transport/request" || return 1
    MKVUTIL_ENGINE_CONTROL="$transport"
    MKVUTIL_ENGINE_CATEGORY="$category"
    trap '_mkvutil_request_stop 2' INT
    trap '_mkvutil_request_stop 15' TERM
    trap '_mkvutil_request_stop 1' HUP
    if (( MKVUTIL_INTERRUPTED )); then
      MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Stopped before execution' not_attempted)"
      return 1
    fi
    "$python_bin" -c "$program" "$category" "$$" "$transport" < "$transport/request" 3>&1 > "$transport/result" 2> "$transport/errors" &
    MKVUTIL_ENGINE_PID=$!
    # A trapped signal interrupts wait without necessarily terminating its child.
    # Reap that same PID before inspecting results or touching any staging file.
    while true; do
      result_code=0
      wait "$MKVUTIL_ENGINE_PID" || result_code=$?
      kill -0 "$MKVUTIL_ENGINE_PID" 2>/dev/null || break
    done
    MKVUTIL_ENGINE_PID=0
    MKVUTIL_RESULT_JSON="$(<"$transport/result")"
    printf '%s\0%s' "$job" "$MKVUTIL_RESULT_JSON" > "$transport/validation"
    # Async read-only checker inherits ignored terminal INT from zsh. Its result
    # cannot be lost merely because Ctrl+C arrived after the writer finished.
    jq -Rse --arg category "$category" '
      split("\u0000") | (.[0]|fromjson) as $job | (.[1]|fromjson) as $result |
      $result.source==$job.source and $result.category==$category and
      (["success","warning","failed","partial","interrupted","not_attempted"]|index($result.status))!=null' < "$transport/validation" >/dev/null 2>&1 &
    checker_pid=$!
    while true; do
      checker_code=0
      wait "$checker_pid" || checker_code=$?
      kill -0 "$checker_pid" 2>/dev/null || break
    done
    if (( checker_code != 0 )); then
      MKVUTIL_RESULT_JSON=""
      print -u2 -r -- "Executor result unavailable or invalid; recovery transport retained: ${transport:t}"
      [[ ! -s "$transport/errors" ]] || cat "$transport/errors" >&2
      transport=""
      return 1
    fi
    return "$result_code"
  } always {
    if (( MKVUTIL_ENGINE_PID > 0 )); then
      _mkvutil_request_stop 15
      while kill -0 "$MKVUTIL_ENGINE_PID" 2>/dev/null; do wait "$MKVUTIL_ENGINE_PID" 2>/dev/null || true; done
      MKVUTIL_ENGINE_PID=0
    fi
    MKVUTIL_ENGINE_CONTROL=""
    MKVUTIL_ENGINE_CATEGORY=""
    if [[ -n "$transport" ]]; then
      rm -f -- "$transport/request" "$transport/result" "$transport/errors" "$transport/ready" "$transport/signal" "$transport/admitted" "$transport/validation"
      rmdir -- "$transport" || true
    fi
  }
}

_mkvutil_execution_engine() {
  local action="$1" job="$2" fresh="$3" registry="$4" python_bin="" program="" aliases=""
  aliases="$(_mkvutil_json_map "${(@kv)MKVUTIL_LANGUAGE_NATIVE_ALIASES}")" || return 1
  python_bin="${VENV_PATH}/bin/python3"
  [[ -x "$python_bin" ]] || python_bin="$(command -v python3)"
  program="$(_mkvutil_execution_support)"$'\n'"$(cat <<'PYCODE'
import copy, json, os, re, signal, stat, subprocess, sys, tempfile, time, xml.etree.ElementTree as ET
from pathlib import Path

job, fresh, registry, language_aliases = [json.loads(value) for value in sys.stdin.buffer.read().decode().split("\0")[:-1]]
action = sys.argv[1]
started = time.monotonic()
source, destination = Path(job["source"]), Path(job["destination"])
original = json.loads(fresh["source_json"])
config = job["config"]
result = dict(source=str(source), destination=str(destination), category=action,
              action_ids=config["operations"], metadata_ids=config["metadata"],
              status="failed", native_code=None, phase="preflight", actual_state="unpublished",
              reason="", candidate_path=None, staging_directory=None, validation_notes=[])
stage_dir = candidate = None
candidate_identity = None
publication_attempted = publication_committed = source_unlinked = False
source_tags = ""


class ValidationFailure(Exception):
    pass



def source_unchanged():
    owner_guard()
    if identity(source) != job["identity"]:
        raise ValueError("Source identity changed since planning")

def phase(name):
    result["phase"] = name
    if stage_dir:
        record = dict(result, source_original_identity=job["identity"], stage_identity=candidate_identity,
                      publication_attempted=publication_attempted, publication_committed=publication_committed,
                      source_unlinked=source_unlinked)
        temporary = stage_dir / "phase.new"
        temporary.write_text(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(temporary, stage_dir / "phase.json")
        result["phase_receipt"] = str(stage_dir / "phase.json")





def identify(path):
    code, raw, error = run(["mkvmerge", "-J", str(path)], 60)
    if code != 0:
        raise ValidationFailure(f"Identification failed ({code}): {error.strip()}")
    parsed = json.loads(raw)
    if not isinstance(parsed.get("tracks"), list):
        raise ValidationFailure("Identification has no track listing")
    return parsed, raw

def tags(path):
    code, text, error = run(["mkvextract", str(path), "tags"], 60)
    if code != 0:
        raise ValidationFailure(f"Tag inspection failed ({code}): {error.strip()}")
    # Parse even an empty tag document, instead of accepting arbitrary output.
    ET.fromstring(text)
    return text

def definition(choice):
    prefix = choice + ":"
    return dict({key[len(prefix):]: value for key, value in registry.items() if key.startswith(prefix)}, choice=choice)

def track_settings(tid):
    return [(definition(key.split(":")[0]), value)
            for key, value in config["settings"].items() if key.split(":", 1)[1] == tid]

def iso(code):
    try:
        from iso639 import Language
        return Language.match(code, strict_case=False)
    except (ImportError, ValueError, KeyError, Exception):
        return None

def equivalent_iso(left, right):
    if str(left).lower() == str(right).lower():
        return True
    a, b = iso(str(left)), iso(str(right))
    return bool(a and b and a.part3 == b.part3)

def language_matches(value, properties, item):
    legacy = properties.get(item["json"])
    ietf = properties.get(item["json_ietf"])
    if not isinstance(ietf, str) or not isinstance(legacy, str):
        return False
    verified = language_aliases.get(value.casefold())
    if verified:
        verified_ietf, verified_legacy = verified.split("|", 1)
        if (ietf.casefold(), legacy.casefold()) == (verified_ietf.casefold(), verified_legacy.casefold()):
            return True
    parts = value.split("-")
    primary = iso(parts[0])
    projected = (primary.part1 or primary.part3) if primary else parts[0]
    expected = "-".join([projected, *parts[1:]])
    # No invented preferred-value mapping: normalization is explicitly off.
    if ietf.casefold() not in (value.casefold(), expected.casefold()):
        return False
    if primary:
        expected_legacy = primary.part2b or primary.part3
        return equivalent_iso(legacy, expected_legacy)
    if value.lower().startswith("x-"):
        return legacy.lower() == "und"
    note = f"Native parser supplied legacy projection for {value!r}; complete IETF spelling verified"
    if note not in result["validation_notes"]:
        result["validation_notes"].append(note)
    return bool(re.fullmatch(r"[a-zA-Z]{3}", legacy))

def property_matches(item, value, properties):
    actual = properties.get(item["json"])
    if item["validator"] == "language":
        return language_matches(value, properties, item)
    if item["validator"] == "boolean":
        # Preservation fields must remain explicit booleans. Optional Matroska
        # flags can be omitted at their registry-declared default.
        if actual is None and not item["snapshot"]:
            actual = item["default"] == "1"
        return type(actual) is bool and actual == (value == "1")
    return ("" if actual is None else actual) == value

volatile_properties = {"uid", "id", "number", "minimum_timestamp", "num_index_entries"}

def unchanged_matches(before, after, tid):
    if before["type"] != after["type"]:
        return False
    changed = {item["json"] for item, value in track_settings(tid)}
    changed |= {item["json_ietf"] for item, value in track_settings(tid) if item["json_ietf"]}
    previous, actual = before.get("properties", {}), after.get("properties", {})
    marker = previous.get("tag__statistics_tags")
    generated = {"tag_" + name.lower() for name in marker.split()} | {"tag__statistics_tags", "tag__statistics_writing_app", "tag__statistics_writing_date_utc"} if isinstance(marker, str) else set()
    for key, expected in previous.items():
        if key in volatile_properties or key in changed or key in generated:
            continue
        observed = actual.get(key)
        if key == "language":
            if not equivalent_iso(expected, observed):
                return False
        elif key == "language_ietf":
            if not isinstance(observed, str) or observed.casefold() != expected.casefold():
                return False
        elif type(expected) is bool:
            if type(observed) is not bool or observed != expected:
                return False
        elif observed != expected:
            return False
    return True

def tag_signature(text, uid_map, retained_uids, source_document):
    root = ET.fromstring(text)
    records = []
    statistics = {"BPS", "DURATION", "NUMBER_OF_FRAMES", "NUMBER_OF_BYTES",
                  "_STATISTICS_WRITING_APP", "_STATISTICS_WRITING_DATE_UTC", "_STATISTICS_TAGS"}
    for tag in root.findall("Tag"):
        targets = tag.find("Targets")
        if targets is not None:
            track_targets = targets.findall("TrackUID")
            if source_document and track_targets and all(int(item.text or "0") != 0 and int(item.text or "0") not in retained_uids for item in track_targets):
                continue
            for target in track_targets:
                value = int(target.text or "0")
                if source_document:
                    if value == 0:
                        target.text = "0"
                    elif value in uid_map:
                        target.text = str(uid_map[value])
                    else:
                        targets.remove(target)
                elif value != 0 and value not in retained_uids:
                    targets.remove(target)
        marker = next((simple for simple in tag.findall("Simple") if simple.findtext("Name") == "_STATISTICS_TAGS"), None)
        generated = set((marker.findtext("String") or "").split()) | statistics if marker is not None else set()
        for simple in list(tag.findall("Simple")):
            if simple.findtext("Name") in generated:
                tag.remove(simple)
        if not tag.findall("Simple"):
            continue
        def canonical(element):
            text = element.text or ""
            if len(element) and not text.strip():
                text = ""
            return (element.tag, text, tuple(sorted(canonical(child) for child in element)))
        records.append(canonical(tag))
    return sorted(records)

def oracle(actual, actual_tags):
    expected_tracks = {str(item["id"]): item for item in original["tracks"]}
    retained = job["retained_ids"] if action == "mux" else job["input_ids"]
    ordered = [expected_tracks[tid] for tid in retained]
    output = actual["tracks"]
    if len(ordered) != len(output):
        raise ValidationFailure("Output track count differs from retained plan")
    applied = {}
    for position, (tid, expected, observed) in enumerate(zip(retained, ordered, output)):
        if not unchanged_matches(expected, observed, tid):
            raise ValidationFailure(f"Track {tid} at output position {position+1}: type/codec/unrequested properties differ")
        for item, value in track_settings(tid):
            ok = property_matches(item, value, observed.get("properties", {}))
            applied[item["choice"] + ":" + tid] = ok
            if not ok:
                raise ValidationFailure(f"Track {tid}: requested {item['property']} differs")
    original_uids = [item.get("properties", {}).get("uid") for item in ordered]
    output_uids = [item.get("properties", {}).get("uid") for item in output]
    preserved_uids = all(type(value) is int for value in original_uids) and len(set(original_uids)) == len(original_uids) and original_uids == output_uids
    if action == "edit" and not preserved_uids:
        raise ValidationFailure("In-place Edit changed or cannot establish track UID mapping")
    if not preserved_uids:
        # Solve only mappings uniquely established by unchanged source fields.
        # Requested names/flags/languages are not circular identity evidence.
        remaining = set(range(len(output)))
        pending = set(range(len(ordered)))
        while pending:
            progress = False
            for index in list(pending):
                candidates = [position for position in remaining if unchanged_matches(ordered[index], output[position], retained[index])]
                if len(candidates) == 1:
                    if candidates[0] != index:
                        raise ValidationFailure("Unique source mapping contradicts planned order")
                    remaining.remove(candidates[0]); pending.remove(index); progress = True
            if not progress:
                raise ValidationFailure("Regenerated/missing UIDs and identical properties leave track mapping ambiguous")
        result["validation_notes"].append("Track mapping established by unique unchanged properties; UIDs were regenerated/missing")
    uid_map = {old: new for old, new in zip(original_uids, output_uids) if type(old) is int and type(new) is int}
    container = actual.get("container", {}).get("properties", {})
    old_container = original.get("container", {}).get("properties", {})
    title_fields = set()
    for key, value in config["settings"].items():
        choice, target = key.split(":", 1)
        item = definition(choice)
        if item["scope"] == "container":
            title_fields.add(item["json"])
            ok = property_matches(item, value, container)
            applied[item["choice"] + ":info"] = ok
            if not ok:
                raise ValidationFailure(f"Requested container {item['property']} differs")
    if "title" not in title_fields and container.get("title", "") != old_container.get("title", ""):
        raise ValidationFailure("Untouched container title differs")
    if actual.get("chapters", []) != original.get("chapters", []):
        raise ValidationFailure("Chapter descriptors differ")
    def attachments(document):
        return [{key: value for key, value in entry.items() if key not in ("id", "properties")}
                for entry in document.get("attachments", [])]
    if attachments(actual) != attachments(original):
        raise ValidationFailure("Attachment descriptors differ")
    result["tag_descriptors"] = {"before": {key: original.get(key, []) for key in ("global_tags", "track_tags")},
                                 "after": {key: actual.get(key, []) for key in ("global_tags", "track_tags")}}
    if tag_signature(source_tags, uid_map, set(original_uids), True) != tag_signature(actual_tags, {}, set(output_uids), False):
        raise ValidationFailure("User tag XML differs after retained-UID projection")
    result["applied_metadata"] = applied
    return True

def reconcile():
    if action == "edit":
        return result.get("actual_state", "edit_unknown")
    stage_inode = (candidate_identity["dev"], candidate_identity["ino"]) if candidate_identity else None
    if stage_inode and inode(destination) == stage_inode:
        if destination == source:
            return "replaced_complete"
        return "published_source_retained" if os.path.lexists(source) else "published_complete"
    if publication_committed:
        return "published_destination_changed"
    if publication_attempted:
        original_inode = (job["identity"]["dev"], job["identity"]["ino"])
        if inode(source) != original_inode or (destination == source and inode(candidate) != stage_inode):
            return "publication_outcome_unknown"
    return "unpublished"

def inspect_edit():
    try:
        actual, raw = identify(source)
        result["actual_json"] = raw
        result["actual_identity"] = identity(source)
        result["actual_state"] = "edited_observed"
        result["edit_changed"] = actual != original
        tracks = {str(item["id"]): item.get("properties", {}) for item in actual["tracks"]}
        result["applied_metadata"] = {}
        result["observed_metadata"] = {}
        for key, value in config["settings"].items():
            choice, target = key.split(":", 1)
            item = definition(choice)
            properties = actual.get("container", {}).get("properties", {}) if target == "info" else tracks.get(target, {})
            result["observed_metadata"][key] = {field: properties.get(field) for field in (item["json"], item["json_ietf"]) if field}
            result["applied_metadata"][key] = property_matches(item, value, properties)
        try:
            oracle(actual, tags(source))
            result["validation_ok"] = True
        except (ValidationFailure, ValueError) as error:
            result["validation_ok"] = False
            result["validation_error"] = str(error)
    except (OSError, ValueError, ValidationFailure) as error:
        result["actual_state"] = "edit_unknown"
        result["inspection_error"] = str(error)

def publish():
    global publication_attempted, publication_committed, source_unlinked
    publication_attempted = True
    phase("publishing")
    source_unchanged()
    if identity(candidate) != candidate_identity:
        raise ValueError("Candidate changed after validation")
    if candidate_identity["size"] == "0":
        raise ValidationFailure("Staged output is empty")
    if destination == source:
        os.replace(candidate, source)
        publication_committed = True
        result["actual_state"] = reconcile()
        phase("replaced")
        if identity(source) != candidate_identity:
            raise ValueError("Published replacement identity differs")
    else:
        if os.path.lexists(destination):
            raise FileExistsError(f"Destination exists: {destination}")
        os.link(candidate, destination, follow_symlinks=False)
        publication_committed = True
        result["actual_state"] = reconcile()
        phase("published_source_retained")
        if identity(destination) != candidate_identity or identity(candidate) != candidate_identity:
            raise ValueError("Published destination/candidate identity differs")
        final, raw = identify(destination)
        oracle(final, tags(destination))
        result["published_json"] = raw
        phase("removing_source")
        source_unchanged()
        # Recheck both identities immediately before old-source cleanup. These
        # are observed-change guards, not a CAS/adversarial-writer guarantee.
        if identity(destination) != candidate_identity:
            raise ValueError("Destination changed before source cleanup")
        os.unlink(source)
        source_unlinked = True
        result["actual_state"] = reconcile()
        phase("published_complete")
    final, raw = identify(destination)
    oracle(final, tags(destination))
    result["published_json"] = raw
    result["actual_state"] = reconcile()
    phase("complete")

try:
    source_unchanged()
    if json.loads(job["source_json"]) != original:
        raise ValidationFailure("Source identification changed since planning")
    if action not in ("edit", "mux"):
        raise ValueError("Executor category is not available")
    source_tags = tags(source)
    if action == "mux" and any(int(target.text or "0") == 0
                                for target in ET.fromstring(source_tags).findall("Tag/Targets/TrackUID")):
        raise ValidationFailure(f"{source}: MKVToolNix v93 remux drops all-track TrackUID=0 tags; Mux refused before modification")
    if action == "edit":
        admit_file()
        phase("native")
        source_unchanged()
        code, stdout, stderr = run(["mkvpropedit", str(source), "--normalize-language-ietf", "off", *job["propedit_args"]],
                                   display_paths=native_display_paths([(source, source.name)]))
        result.update(native_code=code, native_stdout=stdout, native_stderr=stderr)
        inspect_edit()
        if code == 0 and result.get("validation_ok"):
            result["status"] = "success"; phase("complete")
        elif code < 0:
            result["status"] = "interrupted"; result["reason"] = f"Native Edit terminated by signal {-code}; actual in-place state inspected"
        elif code == 1:
            result["status"] = "warning"; result["reason"] = "Native Edit warning; actual in-place state inspected"
        elif code != 0:
            result["reason"] = "Native Edit failed; changes may already be present"
        else:
            result["reason"] = "In-place Edit validation failed"
    else:
        admit_file()
        if destination != source and os.path.lexists(destination):
            raise FileExistsError(f"Destination exists: {destination}")
        stage_dir = Path(tempfile.mkdtemp(prefix=".mkvutil-", dir=destination.parent))
        result["staging_directory"] = str(stage_dir)
        candidate = stage_dir / ("candidate" + destination.suffix)
        result["candidate_path"] = str(candidate)
        phase("staging")
        if destination != source:
            # Fail unsupported hard links before the potentially expensive remux.
            probe, link = stage_dir / "link-probe", stage_dir / "link-probe-copy"
            probe.write_bytes(b"mkvutil\n")
            os.link(probe, link, follow_symlinks=False)
            os.unlink(link); os.unlink(probe)
        source_unchanged()
        argv = ["mkvmerge", "--normalize-language-ietf", "off", "-o", str(candidate), "--track-order", job["track_order"]]
        for kind, option, empty in (("video", "--video-tracks", "--no-video"),
                                    ("audio", "--audio-tracks", "--no-audio"),
                                    ("subtitles", "--subtitle-tracks", "--no-subtitles")):
            ids = [tid for tid in job["retained_ids"] if job["track_types"][tid] == kind]
            argv.extend([option, ",".join(ids)] if ids else [empty])
        argv.extend(job["merge_metadata_args"])
        argv.append(str(source))
        phase("native")
        code, stdout, stderr = run(argv, display_paths=native_display_paths([(source, source.name), (candidate, destination.name),
                                                                           (destination, destination.name)]))
        result.update(native_code=code, native_stdout=stdout, native_stderr=stderr)
        if code != 0:
            result["status"] = "interrupted" if code < 0 else ("warning" if code == 1 else "failed")
            result["reason"] = "Native Mux warning; candidate retained without publication" if code == 1 else "Native Mux failed; source retained"
        else:
            candidate_identity = identity(candidate)
            if candidate_identity["size"] == "0":
                raise ValidationFailure("Staged output is empty")
            phase("validation")
            actual, raw = identify(candidate)
            result["candidate_json"] = raw
            oracle(actual, tags(candidate))
            if identity(candidate) != candidate_identity:
                raise ValueError("Candidate changed during validation")
            result["validation_ok"] = True
            phase("validated")
            publish()
            result["status"] = "success"
            # Only this uniquely owned directory is eligible for cleanup.
            if candidate.exists():
                if identity(candidate) != candidate_identity:
                    raise ValueError("Candidate changed before owned cleanup")
                candidate.unlink()
            for entry in (stage_dir / "phase.json", stage_dir / "phase.new"):
                if entry.exists():
                    entry.unlink()
            stage_dir.rmdir()
            result["candidate_path"] = None
            result["phase_receipt"] = None
except BaseException as error:
    stop_child()
    result["reason"] = str(error)
    result["actual_state"] = reconcile()
    if interrupted or isinstance(error, (Interrupted, KeyboardInterrupt)):
        result["status"] = "interrupted" if admitted else "not_attempted"
        if action == "edit" and admitted:
            # Do not let a second signal prevent a bounded actual-state probe.
            signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)
            inspect_edit()
    elif result["actual_state"] != "unpublished" and action == "mux":
        result["status"] = "partial"
    else:
        result["status"] = "failed"
finally:
    result.update(stop_requested=stop_requested, stop_signal=stop_signal)
    if shutdown_error:result["cleanup_error"] = shutdown_error
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    if action == "mux":
        result["actual_state"] = reconcile()
        result.update(publication_attempted=publication_attempted, publication_committed=publication_committed, source_unlinked=source_unlinked)
        result["source_exists"] = os.path.lexists(source)
        result["destination_exists"] = os.path.lexists(destination)
        if result["status"] != "success" and candidate and not os.path.lexists(candidate):
            result["candidate_path"] = str(destination) if result["actual_state"] != "unpublished" else None
        try:
            if stage_dir and stage_dir.exists():
                phase(result["phase"])
        except BaseException as error:
            result["receipt_error"] = str(error)
    finish_native_display()
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["status"] == "success" else 1)
PYCODE
)"
  _mkvutil_launch_engine "$python_bin" "$program" "$action" "$job" "$fresh" "$registry" "$aliases"
}

_mkvutil_execute_job() {
  local action="$1" job="$2" fresh="" result_code=0 registry=""
  MKVUTIL_RESULT_JSON=""
  if ! mkvutil_load_job "$job"; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Invalid planned job')"
    return 1
  fi
  _mkvutil_preflight_job "$job" || return 1
  fresh="$REPLY"
  registry="$(_mkvutil_json_map "${(@kv)MKVUTIL_METADATA_REGISTRY}")" || return 1
  result_code=0
  if (( MKVUTIL_INTERRUPTED )); then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Stopped before execution' not_attempted)"
    return 1
  fi
  _mkvutil_execution_engine "$action" "$job" "$fresh" "$registry" || result_code=$?
  if [[ -z "$MKVUTIL_RESULT_JSON" ]]; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Executor stopped without a result; inspect any retained phase receipt' interrupted)"
    MKVUTIL_RESULT_JSON="$(jq -c '.phase="unknown"|.actual_state="unknown_inspect_filesystem"' <<< "$MKVUTIL_RESULT_JSON")"
  fi
  return "$result_code"
}


# Extract has its own artifact inventory/publication path. Native programs are
# literal source; source models, paths and settings arrive only as NUL JSON.
_mkvutil_extract_engine() {
  local job="$1" fresh="$2" protected="$3" python_bin="${VENV_PATH}/bin/python3" program=""
  [[ -x "$python_bin" ]] || python_bin="$(command -v python3)"
  program="$(_mkvutil_execution_support)"$'\n'"$(cat <<'PYEXTRACT'
import json, re, sys, tempfile, time, unicodedata
from pathlib import Path
job, fresh, protected = [json.loads(value) for value in sys.stdin.buffer.read().decode().split("\0")[:-1]]
source = Path(job["source"])
original = json.loads(job["source_json"])
started = time.monotonic()
result = dict(source=str(source),destination=job["destination"],category="extract",action_ids=job["config"]["operations"],metadata_ids="",
              status="failed",native_code=None,phase="preflight",actual_state="not_modified_by_job",reason="",stages=[],
              artifacts=[],staging_directories=[],phase_receipts=[],unexpected_paths=[],scratch_paths=[],track_stage_seconds=None)
for kind in ("attachments","tracks"):
    result["stages"].append(dict(kind=kind,status="not_attempted",attempted=False,native_code=None,elapsed_seconds=None,validated_count=0))
parents = {}; directories = {}; directory_identities = {}; leaves = {}; active_stage = None
source_inode = (job["identity"]["dev"],job["identity"]["ino"])
input_inodes = {source_inode}
input_paths = {str(Path(path).resolve()) for path in protected} | {str(source.resolve())}
for path in protected:
    try:
        value=identity(path);input_inodes.add((value["dev"],value["ino"]))
    except (OSError,ValueError):
        pass

def source_guard():
    owner_guard()
    if identity(source)!=job["identity"]:
        raise ValueError("Source identity changed since planning; no source write is performed by Extract")

def parent_guard(lexical):
    guard=parents[str(lexical)]
    current=os.lstat(lexical)
    if (str(current.st_dev),str(current.st_ino))!=guard["entry"] or str(lexical.resolve(strict=True))!=guard["resolved"]:
        raise ValueError(f"Output parent changed: {lexical}")
    target=os.stat(lexical)
    if not stat.S_ISDIR(target.st_mode) or (str(target.st_dev),str(target.st_ino))!=guard["target"]:
        raise ValueError(f"Output directory identity changed: {lexical}")

def output_parent(path):
    lexical=path.parent
    if str(lexical) in parents:
        parent_guard(lexical);return Path(parents[str(lexical)]["resolved"])
    if not os.path.lexists(lexical):
        # The only planned absent output parent is the shared collection.
        if lexical!=source.parent/"Attachments":
            raise ValueError(f"Unplanned missing output parent: {lexical}")
        root=os.stat(lexical.parent)
        os.mkdir(lexical)
        now=os.stat(lexical.parent)
        if (root.st_dev,root.st_ino)!=(now.st_dev,now.st_ino):
            raise ValueError("Source directory changed while creating collection")
    resolved=lexical.resolve(strict=True);entry=os.lstat(lexical);target=os.stat(resolved)
    if not stat.S_ISDIR(target.st_mode):raise ValueError(f"Output parent is not a directory: {lexical}")
    parents[str(lexical)]={"resolved":str(resolved),"entry":(str(entry.st_dev),str(entry.st_ino)),"target":(str(target.st_dev),str(target.st_ino))}
    return resolved

def case_insensitive(parent,path):
    # After confirmed Run, the required unique stage directory provides an
    # existing letter-bearing entry on the actual destination filesystem.
    reference=directories[str(parent)]
    try:return os.path.samefile(reference,reference.with_name(reference.name.swapcase()))
    except FileNotFoundError:return False

def key(parent,path):
    name=path.name
    insensitive=case_insensitive(parent,path)
    if insensitive or sys.platform=="darwin":name=unicodedata.normalize("NFD",name)
    if insensitive:name=name.casefold()
    directory=parent.stat()
    return json.dumps([str(directory.st_dev),str(directory.st_ino),name],ensure_ascii=False)

def leaf(path):
    if not os.path.lexists(path):return None
    value=identity(path)
    if (value["dev"],value["ino"]) in input_inodes:raise ValueError(f"Output inode aliases input media: {path}")
    return value

def owned_directory_guard(directory):
    value=directory.lstat()
    if not stat.S_ISDIR(value.st_mode) or (value.st_dev,value.st_ino)!=directory_identities[str(directory)]:
        raise ValueError(f"Owned staging directory changed: {directory}")

def receipt(phase):
    result["phase"]=phase
    for directory in directories.values():
        owned_directory_guard(directory)
        temporary=directory/"phase.new"
        temporary.write_text(json.dumps(result,ensure_ascii=False)+"\n")
        os.replace(temporary,directory/"phase.json")

def directory_for(parent):
    name=str(parent)
    if name not in directories:
        directory=Path(tempfile.mkdtemp(prefix=".mkvutil-extract-",dir=parent))
        directories[name]=directory
        value=directory.lstat();directory_identities[str(directory)]=(value.st_dev,value.st_ino)
        result["staging_directories"].append(str(directory))
        result["phase_receipts"].append(str(directory/"phase.json"))
    return directories[name]

def reconcile_artifact(artifact):
    expected=artifact.get("stage_identity")
    if not artifact["publication_attempted"] or not expected:return
    if artifact["publication_state"]=="confirmed" and any(later["publication_order"]>artifact["publication_order"] and later["destination_key"]==artifact["destination_key"] and later["publication_attempted"] for later in result["artifacts"]):
        return  # Historical successful publication may have been superseded.
    expected_inode=(expected["dev"],expected["ino"])
    if inode(artifact["path"])==expected_inode:
        artifact["publication_state"]="confirmed" if identity(artifact["path"])==expected else "uncertain"
        if artifact["publication_state"]=="confirmed":artifact["publication_confirmed"]=True
    elif artifact["publication_returned"]:
        artifact["publication_state"]="uncertain"
    else:
        try:current=leaf(Path(artifact["path"]))
        except (OSError,ValueError):current="unsafe"
        artifact["publication_state"]="unpublished" if current==artifact["previous_identity"] else "uncertain"

def publish(artifact):
    destination=Path(artifact["path"]);staged=Path(artifact["stage_path"])
    expected=leaves[artifact["destination_key"]]
    artifact["previous_identity"]=expected
    artifact["publication_attempted"]=True
    receipt("publishing")
    source_guard();parent_guard(destination.parent)
    if identity(staged)!=artifact["stage_identity"]:raise ValueError(f"Staged artifact changed: {staged}")
    if leaf(destination)!=expected:raise ValueError(f"Output changed before publication: {destination}")
    if artifact["kind"]=="attachment":os.replace(staged,destination)
    else:os.link(staged,destination,follow_symlinks=False)
    artifact["publication_returned"]=True
    if identity(destination)!=artifact["stage_identity"]:raise ValueError(f"Published identity differs: {destination}")
    parent_guard(destination.parent)
    artifact["publication_state"]="confirmed";artifact["publication_confirmed"]=True
    leaves[artifact["destination_key"]]=artifact["stage_identity"]
    receipt("published")

def inventory(directory,expected,kind):
    owned_directory_guard(directory)
    for entry in directory.iterdir():
        if entry.name in ("phase.json","phase.new") or str(entry) in expected:continue
        if kind=="tracks" and re.fullmatch(r"mkvextract-\d+-temp-tta-\d+",entry.name):
            if str(entry) not in result["scratch_paths"]:result["scratch_paths"].append(str(entry))
        elif str(entry) not in result["unexpected_paths"]:result["unexpected_paths"].append(str(entry))

def refresh_recovery_inventory():
    remaining=set();result["remaining_staging_directories"]=[]
    for directory in directories.values():
        if not os.path.lexists(directory):continue
        try:
            owned_directory_guard(directory)
            result["remaining_staging_directories"].append(str(directory))
            remaining.update(str(entry) for entry in directory.iterdir())
        except BaseException as error:
            result.setdefault("inventory_errors",[]).append(str(error))
    result["staged_paths"]=[a["stage_path"] for a in result["artifacts"] if a["stage_path"] in remaining]
    result["phase_receipts"]=[str(directory/"phase.json") for directory in directories.values() if str(directory/"phase.json") in remaining]
    for field in ("scratch_paths","unexpected_paths"):
        result[field]=[path for path in result[field] if path in remaining]

def discard_interrupted_tracks():
    if (not interrupted or stop_signal != signal.SIGINT or not active_stage or
            active_stage["status"] != "interrupted" or
            active_stage["kind"] != "tracks" or active_stage["validated_count"] or
            not native_stopped):
        return
    result["discarded_partial_tracks"] = []
    for artifact in result["artifacts"]:
        if artifact["kind"] != "track" or artifact["publication_attempted"]:
            continue
        path = Path(artifact["stage_path"])
        if not os.path.lexists(path):
            continue
        try:
            owned_directory_guard(path.parent)
            expected = artifact["stage_identity"]
            current = identity(path)
            if expected is None or current != expected or (current["dev"], current["ino"]) in input_inodes:
                raise ValueError(f"Partial track identity unsafe for cleanup: {path}")
            path.unlink()
            artifact["present"] = False
            artifact["discarded_partial"] = True
            result["discarded_partial_tracks"].append(str(path))
        except (OSError, ValueError) as error:
            result["cleanup_error"] = (result.get("cleanup_error", "") + "; " + str(error)).lstrip("; ")

def execute_stage(stage,outputs):
    global active_stage
    active_stage=stage
    if not outputs:return
    stage_started=time.monotonic();specs=[];stage_artifacts=[];expected=set();cwd=None
    for logical_index,output in outputs:
        destination=Path(output["path"]);parent=output_parent(destination);directory=directory_for(parent)
        if cwd is None:cwd=directory
        request=directory/f"{stage['kind']}-{logical_index:06d}{destination.suffix}"
        specs.append(output["id"]+":"+str(request))
        for family in output["artifacts"]:
            physical=Path(family["path"]);physical_parent=output_parent(physical)
            if physical_parent!=parent:raise ValueError("Artifact family spans unexpected directories")
            if str(physical.resolve()) in input_paths:raise ValueError(f"Output aliases input path: {physical}")
            namespace=key(parent,physical);existing=leaf(physical)
            if output["kind"]!="attachment" and existing is not None:raise FileExistsError(f"Protected track output exists: {physical}")
            if namespace not in leaves:leaves[namespace]=existing
            staged=request.with_suffix(".sub") if family["role"]=="vobsub_data" else request.with_suffix(".idx") if family["role"]=="vobsub_index" else request.with_suffix(".wvc") if family["role"]=="wavpack_correction" else request
            artifact=dict(logical_index=logical_index,kind=output["kind"],id=output["id"],role=family["role"],required=family["required"],
                          path=str(physical),stage_path=str(staged),destination_key=namespace,stage_identity=None,
                          previous_identity=existing,publication_attempted=False,publication_returned=False,publication_confirmed=False,publication_state="unpublished",present=False)
            artifact["publication_order"]=len(result["artifacts"])
            result["artifacts"].append(artifact);stage_artifacts.append(artifact);expected.add(str(staged))
    source_guard()
    for lexical in parents:parent_guard(Path(lexical))
    stage["attempted"]=True;stage["status"]="running"
    stage["argv"]=["mkvextract",str(source),stage["kind"],*specs]
    try:
        receipt("native_"+stage["kind"])
        code,stdout,stderr=run(stage["argv"],cwd=cwd,display_paths=native_display_paths([(source,source.name),
            *((a["stage_path"],Path(a["path"]).name) for a in stage_artifacts)]))
        stage.update(native_code=code,native_stdout=stdout,native_stderr=stderr)
        result["native_code"]=code
        if code!=0:
            stage["status"]="interrupted" if code<0 else "warning" if code==1 else "failed"
            result["status"]=stage["status"]
        for directory in directories.values():inventory(directory,{a["stage_path"] for a in result["artifacts"]},stage["kind"])
        for artifact in stage_artifacts:
            path=Path(artifact["stage_path"])
            if os.path.lexists(path):
                artifact["stage_identity"]=identity(path);artifact["present"]=True
        if code!=0:
            raise RuntimeError(f"Native {stage['kind']} returned {code}; staged outputs retained without stage publication")
        source_guard()
        if result["unexpected_paths"]:raise ValueError("Unexpected native artifacts; candidates retained")
        attachments={str(item["id"]):item for item in original.get("attachments",[])}
        for artifact in stage_artifacts:
            if not artifact["present"]:
                if artifact["required"]:raise ValueError(f"Required staged artifact missing: {artifact['stage_path']}")
                continue
            value=artifact["stage_identity"]
            if (value["dev"],value["ino"]) in input_inodes:raise ValueError("Staged artifact inode aliases input media")
            if artifact["kind"]=="attachment":
                size=attachments[artifact["id"]].get("size")
                if size is not None and (type(size) is not int or size<0 or str(size)!=value["size"]):
                    raise ValueError(f"Attachment {artifact['id']} staged size differs from source identification")
        stage["validated_count"]=len(outputs);stage["status"]="validated";receipt("validated_"+stage["kind"])
        for artifact in stage_artifacts:
            if artifact["present"]:publish(artifact)
        stage["status"]="complete"
    finally:
        stage["elapsed_seconds"]=time.monotonic()-stage_started
        if stage["kind"]=="tracks":result["track_stage_seconds"]=stage["elapsed_seconds"]

try:
    source_guard()
    if json.loads(fresh["source_json"])!=original:raise ValueError("Source identification changed since planning")
    outputs=list(enumerate(job["outputs"]))
    for stage,kind in zip(result["stages"],("attachment","track")):
        execute_stage(stage,[(index,out) for index,out in outputs if out["kind"]==kind])
    source_guard()
    for artifact in result["artifacts"]:reconcile_artifact(artifact)
    if any(a["publication_state"]=="uncertain" for a in result["artifacts"]):
        raise ValueError("Published output changed before final observation; publication outcome uncertain")
    result["status"]="success";receipt("complete")
except BaseException as error:
    stop_child();result["reason"]=str(error)
    # run() may raise before returning a code. Inspect only still-owned stage
    # directories after bounded child shutdown; preserve scratch and unexpected
    # candidates as evidence instead of omitting them from interruption records.
    for directory in directories.values():
        try:
            inventory(directory,{a["stage_path"] for a in result["artifacts"]},active_stage["kind"] if active_stage else "")
            for artifact in result["artifacts"]:
                if Path(artifact["stage_path"]).parent==directory and os.path.lexists(artifact["stage_path"]):
                    artifact["present"]=True
                    if artifact["stage_identity"] is None:artifact["stage_identity"]=identity(artifact["stage_path"])
        except BaseException as inventory_error:
            result.setdefault("inventory_errors",[]).append(str(inventory_error))
    if interrupted or isinstance(error,(Interrupted,KeyboardInterrupt)):
        result["status"]="interrupted"
    for artifact in result["artifacts"]:
        try:reconcile_artifact(artifact)
        except BaseException:artifact["publication_state"]="uncertain"
    published=any(a["publication_state"] in ("confirmed","uncertain") for a in result["artifacts"])
    if result["status"] not in ("warning","interrupted"):
        result["status"]="partial" if published else "failed"
    if active_stage and active_stage["attempted"] and active_stage["status"]!="complete":
        active_kind="attachment" if active_stage["kind"]=="attachments" else "track"
        stage_published=any(a["kind"]==active_kind and a["publication_state"] in ("confirmed","uncertain") for a in result["artifacts"])
        if result["status"]=="interrupted":active_stage["status"]="interrupted"
        elif active_stage["native_code"]==1:active_stage["status"]="warning"
        elif active_stage["native_code"] not in (0,None):active_stage["status"]="failed"
        else:active_stage["status"]="partial" if stage_published else "failed"
finally:
    for signum in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(signum,signal.SIG_IGN)
    result.update(stop_requested=stop_requested, stop_signal=stop_signal)
    if shutdown_error:result["cleanup_error"] = shutdown_error
    discard_interrupted_tracks()
    result["elapsed_seconds"]=time.monotonic()-started
    result["published_artifacts"]=[a for a in result["artifacts"] if a["publication_state"]=="confirmed"]
    result["uncertain_artifacts"]=[a for a in result["artifacts"] if a["publication_state"]=="uncertain"]
    refresh_recovery_inventory()
    result["actual_state"]="publication_uncertain" if result["uncertain_artifacts"] else "sidecars_published" if result["published_artifacts"] else "staged_unpublished" if result["staged_paths"] else "no_outputs"
    result["attachments_processed"]=next(s["validated_count"] for s in result["stages"] if s["kind"]=="attachments")
    try:
        if result["status"]=="success":
            for directory in directories.values():
                owned_directory_guard(directory)
                for path in directory.iterdir():
                    if str(path) in result["staged_paths"]:
                        artifact=next(a for a in result["artifacts"] if a["stage_path"]==str(path))
                        if identity(path)!=artifact["stage_identity"]:raise ValueError("Owned candidate changed before cleanup")
                    if path.name in ("phase.json","phase.new") or str(path) in result["staged_paths"] or str(path) in result["scratch_paths"]:path.unlink()
                directory.rmdir()
        elif directories:receipt(result["phase"])
    except BaseException as error:
        result["cleanup_error"]=str(error)
        result["reason"]=(result["reason"]+"; " if result["reason"] else "")+"Cleanup failed: "+str(error)
        if result["status"]=="success":result["status"]="partial";result["phase"]="cleanup_failed"
    refresh_recovery_inventory()
    finish_native_display()
    print(json.dumps(result,ensure_ascii=False))
    sys.exit(0 if result["status"]=="success" else 1)
PYEXTRACT
)"
  _mkvutil_launch_engine "$python_bin" "$program" extract "$job" "$fresh" "$protected"
}

mkvutil_execute_extract_job() {
  local job="$1" file="" fresh="" protected="" result=0
  MKVUTIL_RESULT_JSON=""
  file="$(jq -r '.source' <<< "$job")" || return 1
  _mkvutil_preflight_job "$job" || return 1
  fresh="$REPLY"
  if ! mkvutil_check_destinations "$job"; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Extract preflight or source inspection stopped or failed' "$([[ $MKVUTIL_INTERRUPTED == 1 ]] && print not_attempted || print failed)")"
    return 1
  fi
  protected="$(_mkvutil_json_array "${MKVUTIL_SCOPE_KEYS[@]}" "$file")" || return 1
  if (( MKVUTIL_INTERRUPTED )); then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Stopped before extraction' not_attempted)"
    return 1
  fi
  _mkvutil_extract_engine "$job" "$fresh" "$protected" || result=$?
  if [[ -z "$MKVUTIL_RESULT_JSON" ]]; then
    MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Extract stopped without a result; inspect retained stage receipts' interrupted)"
    MKVUTIL_RESULT_JSON="$(jq -c '.actual_state="unknown_inspect_filesystem"' <<< "$MKVUTIL_RESULT_JSON")"
    return 1
  fi
  return "$result"
}

mkvutil_execute_edit_job() { _mkvutil_execute_job edit "$1"; }
mkvutil_execute_mux_job() { _mkvutil_execute_job mux "$1"; }

mkvutil_report_result() {
  _mkvutil_indicator_stop
  local display=""
  display="$(_mkvutil_display_record "$1")" || return 1
  jq -r '(if .simulated==true then "Simulated (DRYRUN): \(.source)"
    elif .status=="success" then
      if .category=="extract" then "Outputs from: \(.source)"
      elif .destination!=null and .destination!=.source then "Output: \(.source) => \(.destination)"
      else empty end
    else "\(.status): \(.source)", (if .category!="extract" and .destination!=null and .destination!=.source then "  Destination: \(.destination)" else empty end),
      "  \(.state_description)" end),
    (if .reason!="" then "  \(.reason)" else empty end),
    (. as $result | .planned_outputs[]? |
      "  Would \(if $result.category=="edit" then "update" elif $result.category=="mux" or .kind=="attachment" then "write" else "extract" end): \(.path)\(if .required==false then " (optional)" else "" end)"),
    (if .candidate_path then "  Candidate: \(.candidate_path)" else empty end),
    (if .phase_receipt then "  Phase receipt: \(.phase_receipt)" else empty end),
    ((.observed_metadata // {})|to_entries[]|"  Actual metadata \(.key): \(.value|tojson)"),
    (.artifacts[]? | select(.kind=="track" and (.publication_state=="confirmed" or .publication_state=="uncertain")) |
      "  Track \(.id): \(.path)\(if .publication_state=="uncertain" then " (publication uncertain)" else "" end)"),
    (.staged_paths[]? | "  Staged: \(.)"),(.phase_receipts[]?|"  Phase receipt: \(.)"),
    (.scratch_paths[]? | "  Native scratch: \(.)"),(.unexpected_paths[]? | "  Unexpected artifact: \(.)"),
    (if .cleanup_error then "  Cleanup failed: \(.cleanup_error)" else empty end),
    (.inventory_errors[]? | "  Recovery inventory: \(.)"),
    (.remaining_staging_directories[]? | "  Retained staging directory: \(.)")' <<< "$display"
}

# Compact headings use the same metadata labels as configuration, before each
# file's native messages. Timing remains separate and final-only for Edit.
mkvutil_action_heading() {
  local category="$1" operations="$2" metadata="${3-}" choice="" label="" title="" suffix=""
  local -a labels=()
  case "$category" in
    edit)
      title=Edit
      for choice in "${(@s:,:)operations}"; do
        label="${MKVUTIL_METADATA_REGISTRY[${choice}:label]}"
        label="${label#Set }"; label="${label% for tracks}"
        labels+=("$label")
      done ;;
    mux)
      title=Mux
      [[ ",$operations," != *,1,* ]] || labels+=(remove)
      [[ ",$operations," != *,2,* ]] || labels+=(reorder)
      [[ -z "$metadata" ]] || suffix="; metadata $metadata" ;;
    extract)
      title=Extract
      [[ ",$operations," != *,1,* ]] || labels+=(attachments)
      [[ ",$operations," != *,2,* ]] || labels+=(tracks) ;;
    *) return 1 ;;
  esac
  print
  (( ! MKVUTIL_DRY_RUN )) || title+=' (DRYRUN)'
  print -r -- "$title $operations: ${(j: + :)labels}$suffix"
}

mkvutil_execute_queue() {
  setopt localtraps
  local job="" category="" operations="" metadata="" source="" config="" outcome="" record="" status_name="" batch=""
  local result_code=0 queue_code=0 interrupted=0 attempted=0 completed=0 total=$# native_returned=0 result_recorded=1 result_accounted=1
  local -F 6 queue_started=0 job_started=0 now=0 job_elapsed=0 work_elapsed=0 queue_elapsed=0 track_work=0
  local track_elapsed="" track_samples=0
  local -a paths=() outcomes=() all_jobs=("$@")
  local queue_index=0 unstarted_offset=0 missed="[]"
  local active_source="" stop_record=null stop_mode="" engine_signal=0
  trap '_mkvutil_request_stop 2' INT
  trap '_mkvutil_request_stop 15' TERM
  trap '_mkvutil_request_stop 1' HUP
  MKVUTIL_RESULTS=()
  (( MKVUTIL_INTERRUPTED == 0 )) || return 1
  (( total > 0 )) || return 0
  if (( ! MKVUTIL_LEDGER_ENABLED )); then
    for job in "$@"; do paths+=("$(jq -r '.source' <<< "$job")"); done
    for record in "${MKVUTIL_REMOVAL_SKIPS[@]}"; do paths+=("$(jq -r '.source' <<< "$record")"); done
    mkvutil_ledger_reset "$PWD" "${paths[@]}" || return 1
  fi
  config="$(jq -c '.config' <<< "$1")" || return 1
  category="$(jq -r '.category' <<< "$config")" || return 1
  operations="$(jq -r '.operations|join(",")' <<< "$config")" || return 1
  metadata="$(jq -r '.metadata // "" | if type=="array" then join(",") else . end' <<< "$config")" || return 1
  if (( MKVUTIL_BATCH_ID == 0 )) || [[ "$(jq -r '.state' <<< "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}")" == executed || "$(jq -r '.state' <<< "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}")" == interrupted ]]; then
    mkvutil_batch_request "$category" "$operations" "$config" || return 1
  fi
  for record in "${MKVUTIL_REMOVAL_SKIPS[@]}"; do mkvutil_ledger_skip "$record" || return 1; done
  _mkvutil_indicator_stop
  MKVUTIL_HAS_RUN=1
  # Always preserve pending outcomes and archive timing, including a signal
  # between jobs or a bookkeeping failure after a tool has already returned.
  {
  queue_started="$(mkvutil_clock)" || return 1
  for job in "$@"; do
    queue_index=$((queue_index + 1))
    source="$(jq -r '.source' <<< "$job")" || return 1
    [[ -n "${MKVUTIL_LEDGER[$source]-}" ]] || { print -u2 -r -- "Job outside original selected scope: ${source:t}"; return 1; }
    if (( MKVUTIL_INTERRUPTED )); then
      MKVUTIL_LEDGER[$source]="$(jq -c 'if .status=="pending" then .status="not_attempted" else . end' <<< "${MKVUTIL_LEDGER[$source]}")"
      continue
    fi
    status_name="$(jq -r '.status' <<< "${MKVUTIL_LEDGER[$source]}")"
    case "$status_name" in
      success|warning|failed|partial|interrupted|excluded|not_attempted)
        print -u2 -r -- "Source already has an outcome; not retried: ${source:t}"
        queue_code=1
        unstarted_offset=$queue_index
        continue ;;
    esac
    mkvutil_action_heading "$category" "$operations" "$metadata" || return 1
    print -r -- "Processing: ${source:t}"
    active_source="$source"
    job_started="$(mkvutil_clock)" || return 1
    result_code=0
    attempted=$(( attempted + 1 ))
    native_returned=0
    result_recorded=0
    result_accounted=0
    if (( MKVUTIL_DRY_RUN )); then
      mkvutil_simulate_job "$job" || result_code=$?
    else
    case "$category" in
      edit) mkvutil_execute_edit_job "$job" || result_code=$? ;;
      mux) mkvutil_execute_mux_job "$job" || result_code=$? ;;
      extract) mkvutil_execute_extract_job "$job" || result_code=$? ;;
      *) MKVUTIL_RESULT_JSON="$(_mkvutil_execution_failure "$job" 'Extract execution is not available')"; result_code=1 ;;
    esac
    fi
    native_returned=1
    (( ! MKVUTIL_INTERRUPTED )) || trap '' INT
    MKVUTIL_RESULTS+=("$MKVUTIL_RESULT_JSON")
    now="$(mkvutil_clock)" || return 1
    job_elapsed=$(( now - job_started ))
    (( job_elapsed >= 0 )) || job_elapsed=0
    work_elapsed=$(( work_elapsed + job_elapsed ))
    MKVUTIL_RESULT_JSON="$(jq -c --argjson elapsed "$job_elapsed" '.+{processing_seconds:$elapsed}' <<< "$MKVUTIL_RESULT_JSON")" || return 1
    MKVUTIL_RESULTS[-1]="$MKVUTIL_RESULT_JSON"
    status_name="$(jq -r '.status' <<< "$MKVUTIL_RESULT_JSON")" || return 1
    if [[ "$status_name" == not_attempted ]]; then
      attempted=$(( attempted - 1 ))
    else
      unstarted_offset=$queue_index
    fi
    result_accounted=1
    if [[ "$(jq -r '.stop_requested // false' <<< "$MKVUTIL_RESULT_JSON")" == true ]]; then
      MKVUTIL_INTERRUPTED=1
      engine_signal="$(jq -r '.stop_signal // 2' <<< "$MKVUTIL_RESULT_JSON")"
      if (( MKVUTIL_STOP_SIGNAL == 0 || engine_signal != 2 )); then MKVUTIL_STOP_SIGNAL=$engine_signal; fi
      trap '' INT
    fi
    mkvutil_ledger_result "$MKVUTIL_RESULT_JSON" "$source" "$status_name" || return 1
    result_recorded=1
    if [[ "$status_name" == success ]]; then
      completed=$(( completed + 1 ))
    else
      mkvutil_report_result "$MKVUTIL_RESULT_JSON" || return 1
      queue_code=1
    fi
    if [[ "$category" == mux ]]; then
      mkvutil_format_progress "$category" "$operations" "$job_elapsed" "$attempted" "$completed" "$total" "$work_elapsed" "" "" "$attempted" "$source" || return 1
    elif [[ "$category" == extract ]]; then
      track_elapsed="$(jq -r '.track_stage_seconds // empty' <<< "$MKVUTIL_RESULT_JSON")"
      if [[ -n "$track_elapsed" ]]; then
        track_samples=$((track_samples + 1));track_work=$((track_work + track_elapsed))
      fi
      mkvutil_format_progress "$category" "$operations" "$job_elapsed" "$attempted" "$completed" "$total" "$work_elapsed" "$track_elapsed" "$track_work" "$track_samples" "$source" || {
        print -u2 -r -- 'Progress formatting unavailable; independent files continue.';queue_code=1
      }
    fi
    if [[ "$status_name" == interrupted ]]; then
      interrupted=1
      MKVUTIL_INTERRUPTED=1
    fi
  done
  } always {
    (( interrupted == 0 )) || MKVUTIL_INTERRUPTED=1
    (( ! MKVUTIL_INTERRUPTED )) || trap '' INT
    if (( native_returned && ! result_recorded )); then
      # A post-tool bookkeeping failure must not relabel changed media as an
      # unattempted file. Retain the executor's actual-state record first.
      status_name="$(jq -r '.status' <<< "${MKVUTIL_RESULTS[-1]}")" || queue_code=1
      if (( ! result_accounted )); then
        if [[ "$status_name" == not_attempted ]]; then attempted=$((attempted - 1)); else unstarted_offset=$queue_index; fi
        result_accounted=1
      fi
      if mkvutil_ledger_result "${MKVUTIL_RESULTS[-1]}" "$source" "$status_name"; then
        [[ "$status_name" != success ]] || completed=$(( completed + 1 ))
      else
        queue_code=1
      fi
    fi
    mkvutil_ledger_finalize || queue_code=1
    now="$(mkvutil_clock)" || queue_code=1
    if (( queue_started > 0 && now >= queue_started )); then
      queue_elapsed=$(( now - queue_started ))
    fi
    MKVUTIL_TOTAL_ELAPSED=$(( MKVUTIL_TOTAL_ELAPSED + queue_elapsed ))
    batch="${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}"
    outcome="$(mkvutil_batch_outcomes)" || queue_code=1
    if (( MKVUTIL_INTERRUPTED )); then
      missed="$(printf '%s\n' "${all_jobs[@]}" | jq -sc --argjson start "$unstarted_offset" '.[$start:]|map(.source)')" || queue_code=1
      stop_mode=immediate
      if (( MKVUTIL_STOP_SIGNAL == 2 )) && [[ "$category" == edit || "$category" == mux ]]; then stop_mode=after_current_file; fi
      stop_record="$(_mkvutil_jq_records '.[0]+{not_started_sources:.[1]}' \
        "$(jq -cn --arg mode "$stop_mode" --arg active "$active_source" --argjson signal "$MKVUTIL_STOP_SIGNAL" \
        '{mode:$mode,signal:$signal,active_original_source:$active}')" "$missed")" || queue_code=1
    fi
    MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]="$(jq -c --argjson elapsed "$queue_elapsed" --argjson attempted "$attempted" --argjson completed "$completed" --argjson eligible "$total" --argjson outcomes "$outcome" --arg state "$([[ $MKVUTIL_INTERRUPTED == 1 ]] && print interrupted || print executed)" '.+{state:$state,elapsed_seconds:$elapsed,attempted:$attempted,completed:$completed,eligible:$eligible,outcomes:$outcomes}' <<< "$batch")" || queue_code=1
    MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]="$(_mkvutil_jq_records '.[0]+{stop:.[1]}' "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}" "$stop_record")" || queue_code=1
    if [[ "$category" == extract ]]; then
      MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]="$(jq -c --argjson seconds "$track_work" --argjson samples "$track_samples" '.+{track_processing_seconds:$seconds,track_stages_attempted:$samples}' <<< "${MKVUTIL_BATCHES[$MKVUTIL_BATCH_ID]}")" || queue_code=1
    fi
    MKVUTIL_JOBS=()
    mkvutil_sync_unresolved_skips || queue_code=1
  }
  (( MKVUTIL_INTERRUPTED == 0 )) || queue_code=1
  mkvutil_ledger_status || queue_code=1
  return "$queue_code"
}

print_help() {
  print -r -- "Usage: ${SCRIPT_NAME} [--dry-run] [--bypass] [working_directory]"
  print -r -- "       ${SCRIPT_NAME} --help"
  print -r -- $'\n  1) Matroska Edit     Flags, language, names and title\n  2) Matroska Mux      Remove/reorder with optional metadata\n  3) Matroska Extract  Attachments and tracks\n  4) Matroska Analyze  List tracks and compare layouts'
  print -r -- $'\nChoose one action or a batch (1,2 or 1-3); select one or more files.\nFiles: .mkv .mka .mks .mk3d. Default: current directory.'
  print -r -- '--bypass  Skip removal count guard.'
  print -r -- '--dry-run Simulate; no writes.'
}

# The final required input commits the configuration. Complete the whole
# preflight before starting; the caller prints one final report and exits.
mkvutil_controller() {
  local category="$1" operations="$2" result=0
  _mkvutil_ui_leave
  mkvutil_configure_category "$category" "$operations" || return $?
  mkvutil_batch_configured "$MKVUTIL_CONFIG" || return 1
  mkvutil_plan_queue || result=$?
  case "$result" in
    0) ;;
    3) return 1 ;; # All removal mismatches: report without starting a writer.
    *) return "$result" ;;
  esac
  (( MKVUTIL_INTERRUPTED == 0 && ${#MKVUTIL_JOBS} > 0 )) || return 1
  mkvutil_execute_queue "${MKVUTIL_JOBS[@]}" || result=$?
  (( MKVUTIL_INTERRUPTED == 0 && result == 0 )) || return 1
  mkvutil_ledger_status
}

mkvutil_finish() {
  setopt localtraps
  (( ! MKVUTIL_INTERRUPTED )) || trap '' INT
  _mkvutil_ui_leave
  local code="$1" final_code=0
  if (( code == 2 )); then
    if (( MKVUTIL_HAS_RUN )); then
      print -r -- 'Continuation cancelled; recorded outcomes retained.'
    else
      print -r -- 'Cancelled; no media changes.'
    fi
  elif (( code != 0 )); then
    final_code=1
  fi
  mkvutil_ledger_finalize || final_code=1
  mkvutil_ledger_status || final_code=1
  MKVUTIL_UI_REPORT_SHOWN=0
  if mkvutil_final_report; then
    MKVUTIL_UI_REPORT_SHOWN=1
  else
    MKVUTIL_UI_REPORT_SHOWN=-1
    final_code=1
  fi
  return "$final_code"
}

# Internal cleanup clears pending configuration while retaining outcome state.
# Public Back uses a separate full-scope reset.
mkvutil_discard_configuration() {
  MKVUTIL_CONFIG=""
  MKVUTIL_CURRENT_JOB=""
  MKVUTIL_JOBS=()
  mkvutil_metadata_reset
}

# A public Back discards the entire unexecuted selection and its ledger. Keep
# this separate from internal recovery, which may intentionally retain scope.
mkvutil_reset_public_selection() {
  (( ! MKVUTIL_HAS_RUN && ! MKVUTIL_INTERRUPTED )) || return 1
  _mkvutil_indicator_stop
  MKVUTIL_SCAN_FILES=()
  MKVUTIL_SELECTED_FILES=()
  MKVUTIL_SOURCES=()
  MKVUTIL_REMOVAL_SKIPS=()
  MKVUTIL_REMOVAL_SKIP_HISTORY=()
  MKVUTIL_LEDGER_ENABLED=0
  MKVUTIL_BATCH_ID=0
  MKVUTIL_SCOPE_KEYS=()
  MKVUTIL_BATCHES=()
  MKVUTIL_LEDGER=()
  MKVUTIL_RESULTS=()
  MKVUTIL_TOTAL_ELAPSED=0
  MKVUTIL_DIRECTORY_NAME=""
  MKVUTIL_UI_REPORT_SHOWN=0
  mkvutil_discard_configuration
  _mkvutil_clear_plan_layout
}

mkvutil_close_scope() {
  MKVUTIL_UI_REPORT_SHOWN=0
  (( MKVUTIL_LEDGER_ENABLED )) || return 0
  if (( ! MKVUTIL_HAS_RUN )); then
    local source=""
    local -a entries=()
    for source in "${MKVUTIL_SCOPE_KEYS[@]}"; do entries+=("${MKVUTIL_LEDGER[$source]}"); done
    # A neutral abandoned request can leave quietly. Failures, exclusions and
    # mismatch history still need the original-scope final report.
    local diagnostic=""
    if diagnostic="$(printf '%s\n' "${entries[@]}" | jq -se 'all(.[]; .status=="pending" and (.skip_history|length)==0)' 2>&1 >/dev/null)"; then
      return 0
    fi
    if [[ -n "$diagnostic" ]]; then _mkvutil_ui_leave; print -u2 -r -- "$diagnostic"; fi
  fi
  mkvutil_finish 0
}

_mkvutil_main_body() {
  setopt localtraps
  local directory="$PWD" category="" operations="" result=0 resolved_directory="" sticky_code=0 selected=0
  local argument="" directory_set=0 main_error="" action_error=""
  MKVUTIL_LEDGER_ENABLED=0
  MKVUTIL_INTERRUPTED=0
  MKVUTIL_BYPASS_TRACK_COUNT=0
  MKVUTIL_DRY_RUN=0
  trap 'MKVUTIL_INTERRUPTED=1' INT TERM
  for argument in "$@"; do
    case "$argument" in
      --help|-h) print_help; return 0 ;;
      --bypass) MKVUTIL_BYPASS_TRACK_COUNT=1 ;;
      --dry-run) MKVUTIL_DRY_RUN=1 ;;
      -*) print -u2 -r -- "Usage: ${SCRIPT_NAME} [--dry-run] [--bypass] [working_directory]"; return 1 ;;
      *)
        (( ! directory_set )) || { print -u2 -r -- "Usage: ${SCRIPT_NAME} [--dry-run] [--bypass] [working_directory]"; return 1; }
        directory="$argument"; directory_set=1 ;;
    esac
  done
  resolved_directory="$(mkvutil_resolve_directory "$directory")" || return 1
  cd "$resolved_directory" || return 1
  _mkvutil_ui_owned || print -r -- "Current Work Dir: $resolved_directory"
  while true; do
    (( MKVUTIL_INTERRUPTED == 0 )) || return 1
    result=0
    _mkvutil_menu_read main '' '' '' "$main_error" || result=$?
    main_error=""
    if (( result )); then
      (( MKVUTIL_INTERRUPTED == 0 && result == 2 )) || return 1
      return "$sticky_code"
    fi
    case "$REPLY" in
      e|E) return "$sticky_code" ;;
      1) category=edit ;;
      2) category=mux ;;
      3) category=extract ;;
      4) category=analysis ;;
      *) main_error='Invalid category. Use 1, 2, 3 or 4.'; continue ;;
    esac
    (( MKVUTIL_INTERRUPTED == 0 )) || return 1
    MKVUTIL_LEDGER_ENABLED=0
    MKVUTIL_SOURCES=()
    MKVUTIL_REMOVAL_SKIPS=()
    MKVUTIL_REMOVAL_SKIP_HISTORY=()
    mkvutil_discard_configuration
    selected=0
    action_error=""
    if [[ "$category" == analysis ]]; then
      mkvutil_scan_files_working "$PWD" || {
        _mkvutil_ui_leave
        print -r -- 'No Matroska files found (.mkv, .mka, .mks, .mk3d).'; return 1;
      }
      mkvutil_select_files || return 1
      mkvutil_analyze_files || sticky_code=1
      return "$sticky_code"
    fi
    while true; do
      result=0
      _mkvutil_menu_read actions "$category" 'Actions: ' '' "$action_error" || result=$?
      action_error=""
      if (( result )); then
        if (( selected )); then
          mkvutil_finish "$result" || sticky_code=1
        elif (( result != 2 )); then
          sticky_code=1
        fi
        (( MKVUTIL_INTERRUPTED == 0 )) || sticky_code=1
        return "$sticky_code"
      fi
      (( MKVUTIL_INTERRUPTED == 0 )) || { (( ! selected )) || mkvutil_finish 1; return 1; }
      case "$REPLY" in
        e|E)
          mkvutil_reset_public_selection || return 1
          selected=0
          break ;;
      esac
      result=0
      _mkvutil_menu_choices "$category" "$REPLY" || result=$?
      if (( result == 3 )); then
        action_error='Invalid operations. Use the listed numbers, comma lists or ascending ranges; e goes back.'
        continue
      fi
      if (( result )); then
        (( ! selected )) || mkvutil_finish 1
        return 1
      fi
      operations="$REPLY"
      if (( ! selected )); then
        mkvutil_scan_files_working "$PWD" || {
          _mkvutil_ui_leave
          print -r -- 'No Matroska files found (.mkv, .mka, .mks, .mk3d).'; return 1;
        }
        mkvutil_select_files || return 1
        (( MKVUTIL_INTERRUPTED == 0 )) || return 1
        mkvutil_ledger_reset "$resolved_directory" "${MKVUTIL_SELECTED_FILES[@]}" || return 1
        selected=1
      fi
      _mkvutil_ui_leave
      mkvutil_batch_request "$category" "$operations" || return 1
      if (( ${#MKVUTIL_SOURCES} == 0 )); then
        result=0
        mkvutil_inspect_sources || result=$?
        if (( MKVUTIL_INTERRUPTED )); then mkvutil_finish 1; return 1; fi
        if (( result == 4 )); then mkvutil_reset_public_selection || return 1; selected=0; continue; fi
        if (( result )); then
          mkvutil_finish "$result" || sticky_code=1
          return "$sticky_code"
        fi
      fi
      result=0
      mkvutil_controller "$category" "$operations" || result=$?
      if (( MKVUTIL_INTERRUPTED )); then mkvutil_finish 1; return 1; fi
      if (( MKVUTIL_HAS_RUN )); then
        mkvutil_finish "$result" || sticky_code=1
        return "$sticky_code"
      fi
      case "$result" in
        4) mkvutil_reset_public_selection || return 1; selected=0; continue ;;
        *) mkvutil_finish "$result" || sticky_code=1; return "$sticky_code" ;;
      esac
    done
  done
}

# Cleanup owns only terminal presentation; never reset outcome/signal state.
mkvutil_main() {
  local result=0
  {
    _mkvutil_main_body "$@" || result=$?
  } always {
    _mkvutil_indicator_stop
    _mkvutil_ui_leave
  }
  return "$result"
}

# Sourcing defines helpers without launching the real category entrypoint.
if [[ "$ZSH_EVAL_CONTEXT" != *:file ]]; then
  mkvutil_main "$@"
  exit $?
fi
