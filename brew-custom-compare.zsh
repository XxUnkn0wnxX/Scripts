#!/usr/local/bin/zsh

# --- Configuration -----------------------------------------------------------
# Override these via environment variables if needed before running the script.
DEFAULT_CUSTOM_TAP=${DEFAULT_CUSTOM_TAP:-"custom/versions"}
HOMEBREW_API_FORMULA_BASE=${HOMEBREW_API_FORMULA_BASE:-"https://formulae.brew.sh/api/formula"}
typeset -gA __brew_pinned=()

# --- Helpers for comparing custom tap vs upstream core using Homebrew's API ---

brew_collect_versions() {
  local -a specs=("$@")
  local -a chunk=()
  local spec
  local chunk_size=8
  local parsed json

  (( ${#specs[@]} )) || return 0

  for spec in "${specs[@]}"; do
    chunk+=("$spec")
    if (( ${#chunk[@]} == chunk_size )); then
      json=$(brew info --json=v2 "${chunk[@]}" 2>/dev/null) || return 1
      parsed=$(printf '%s\n' "$json" | RUBYOPT=-W0 ruby -rjson -e '
        data = JSON.parse(STDIN.read)
        entries = data["formulae"] || []
        entries.each do |entry|
          name = entry["full_name"] || entry["name"]
          next unless name
          version = entry.dig("versions", "stable") || entry["version"]
          next unless version && !version.empty?
          puts "#{name}\t#{version}"
        end
      ') || return 1
      printf '%s\n' "$parsed"
      chunk=()
    fi
  done

  if (( ${#chunk[@]} )); then
    json=$(brew info --json=v2 "${chunk[@]}" 2>/dev/null) || return 1
    parsed=$(printf '%s\n' "$json" | RUBYOPT=-W0 ruby -rjson -e '
      data = JSON.parse(STDIN.read)
      entries = data["formulae"] || []
        entries.each do |entry|
          name = entry["full_name"] || entry["name"]
          next unless name
          version = entry.dig("versions", "stable") || entry["version"]
          next unless version && !version.empty?
          puts "#{name}\t#{version}"
        end
      ') || return 1
    printf '%s\n' "$parsed"
  fi
}

# Query the public Homebrew API directly (https://formulae.brew.sh/api/formula).
# Usage: brew_get_formula_version_api "node"
brew_get_formula_version_api() {
  local name="$1"
  local response status_code body version
  [[ -n "$name" ]] || return 1

  response=$(curl -sSL -w '\n%{http_code}' "${HOMEBREW_API_FORMULA_BASE}/${name}.json") || return 3
  status_code=${response##*$'\n'}
  body=${response%$'\n'*}

  case "$status_code" in
    200) ;;
    404) return 2 ;;
    *) return 3 ;;
  esac

  version=$(printf '%s\n' "$body" | RUBYOPT=-W0 ruby -rjson -e '
    data = JSON.parse(STDIN.read)
    versions = data["versions"]
    version = versions && versions["stable"]
    version = data["version"] if (!version || version.empty?)
    puts version if version && !version.empty?
  ') || return 1

  [[ -n "$version" ]] || return 1
  printf '%s\n' "$version"
}

# Compare two version strings using Ruby's Gem::Version.
# Prints: -1 if v1 < v2, 0 if equal, 1 if v1 > v2
brew_compare_versions() {
  RUBYOPT=-W0 ruby -e '
    require "rubygems"
    begin
      v1 = Gem::Version.new(ARGV[0])
      v2 = Gem::Version.new(ARGV[1])
    rescue ArgumentError
      exit 2
    end
    if v1 < v2
      puts "-1"
    elsif v1 == v2
      puts "0"
    else
      puts "1"
    end
  ' "$1" "$2"
}

brew_list_tap_formulas() {
  local tap_dir="$1"
  local -a files sorted
  typeset -A seen=()
  local file base

  [[ -d "$tap_dir" ]] || return 1

  if command -v rg >/dev/null 2>&1; then
    files=(${(@f)$(rg --files -g '*.rb' "$tap_dir" 2>/dev/null)})
  else
    files=(${(@f)$(find "$tap_dir" -type f -name '*.rb' 2>/dev/null)})
  fi

  (( ${#files[@]} )) || return 0

  for file in "${files[@]}"; do
    [[ -f "$file" ]] || continue
    base=${file:t}
    base=${base%.rb}
    [[ -z "$base" ]] && continue
    seen[$base]=1
  done

  (( ${#seen[@]} )) || return 0

  sorted=(${(@ko)seen})
  printf '%s\n' "${sorted[@]}"
}

brew_cache_pinned() {
  local pinned_output
  __brew_pinned=()

  if ! pinned_output=$(brew list --pinned 2>/dev/null); then
    return 1
  fi

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    __brew_pinned[$name]=1
  done <<<"$pinned_output"

  return 0
}

brew_print_status() {
  local formula="$1"
  local label="$2"
  local detail="$3"
  local final_label="$label"

  if [[ -n ${__brew_pinned[$formula]} ]]; then
    final_label="PINNED"
  fi

  printf '%-25s %-9s %s\n' "$formula" "$final_label" "$detail"
}

brew_tap_has_formula() {
  local tap_dir="$1"
  local formula="$2"
  setopt local_options null_glob extended_glob
  local matches=("${tap_dir}"/**/"${formula}".rb(N-.))
  (( ${#matches[@]} ))
}

brew_find_overlap_version() {
  local base_tap="$1"
  local formula="$2"
  local tap_name tap_dir spec output version

  setopt local_options null_glob

  while IFS= read -r tap_name; do
    [[ -z "$tap_name" ]] && continue
    [[ "$tap_name" == "$base_tap" ]] && continue
    [[ "$tap_name" == "homebrew/core" ]] && continue
    tap_dir=$(brew --repository "$tap_name" 2>/dev/null) || continue
    brew_tap_has_formula "$tap_dir" "$formula" || continue

    spec="$tap_name/$formula"
    if output=$(brew_collect_versions "$spec" 2>/dev/null); then
      version=${output#*$'\t'}
      [[ -z "$version" ]] && continue
      printf '%s\t%s\n' "$tap_name" "$version"
      return 0
    fi
  done < <(brew tap 2>/dev/null)

  return 1
}

brew_compare_against_other_tap() {
  local base_tap="$1"
  local formula="$2"
  local custom_ver="$3"
  local overlap_info overlap_tap overlap_ver cmp cmp_status

  if ! overlap_info=$(brew_find_overlap_version "$base_tap" "$formula"); then
    brew_print_status "$formula" "SKIP" "(custom $custom_ver, not found in Homebrew API or other installed taps)"
    return 0
  fi

  overlap_tap=${overlap_info%%$'\t'*}
  overlap_ver=${overlap_info##*$'\t'}

  cmp=$(brew_compare_versions "$custom_ver" "$overlap_ver")
  cmp_status=$?
  if (( cmp_status != 0 )); then
    if (( cmp_status == 2 )); then
      brew_print_status "$formula" "SKIP" "(custom $custom_ver, unable to compare against $overlap_tap $overlap_ver)"
    else
      brew_print_status "$formula" "ERROR" "(comparison failed for $custom_ver vs $overlap_tap $overlap_ver)"
    fi
    return 0
  fi

  case "$cmp" in
    -1)
      brew_print_status "$formula" "OUTDATED" "(custom $custom_ver < $overlap_tap $overlap_ver)"
      ;;
    0)
      brew_print_status "$formula" "OK" "($custom_ver matches $overlap_tap)"
      ;;
    1)
      brew_print_status "$formula" "AHEAD" "(custom $custom_ver > $overlap_tap $overlap_ver)"
      ;;
    *)
      brew_print_status "$formula" "ERROR" "(compare failed: $custom_ver vs $overlap_tap $overlap_ver)"
      ;;
  esac

  return 0
}

# Main function: compare formulas in a tap against homebrew/core
brew_compare_custom_vs_core_api() {
  local tap=${1:-$DEFAULT_CUSTOM_TAP}

  if (( $# >= 1 )); then
    shift 1
  else
    shift "$#"
  fi

  local tap_dir
  local -a formulas input_formulas spec_list
  local name spec custom_ver cmp official_ver api_status cmp_status
  typeset -A custom_versions

  setopt local_options null_glob

  input_formulas=("$@")

  tap_dir=$(brew --repository "$tap") || {
    echo "Tap $tap not found." >&2
    return 1
  }

  if (( ${#input_formulas[@]} )); then
    formulas=("${input_formulas[@]}")
  else
    local discovered
    discovered=$(brew_list_tap_formulas "$tap_dir")
    formulas=()
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      formulas+=("$name")
    done <<<"$discovered"
  fi

  if (( ${#formulas[@]} )); then
    local sorted_list
    sorted_list=$(printf '%s\n' "${formulas[@]}" | LC_ALL=C sort -V)
    formulas=()
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      formulas+=("$line")
    done <<<"$sorted_list"
  fi

  for name in "${formulas[@]}"; do
    [[ -n "$name" ]] || continue
    spec_list+=("$tap/$name")
  done

  if (( ${#spec_list[@]} )); then
    local collect_output
    if ! collect_output=$(brew_collect_versions "${spec_list[@]}"); then
      echo "Failed to collect versions for $tap." >&2
      return 1
    fi
    while IFS=$'\t' read -r full_name version; do
      [[ -z "$full_name" ]] && continue
      custom_versions[$full_name]=$version
    done <<<"$collect_output"
  fi

  echo "Comparing $tap (local) vs Homebrew API (upstream):"
  echo

  for name in "${formulas[@]}"; do
    [[ -n "$name" ]] || continue

    spec="$tap/$name"
    custom_ver=${custom_versions[$spec]}
    if [[ -z "$custom_ver" ]]; then
      brew_print_status "$name" "ERROR" "(failed to get custom version)"
      continue
    fi

    official_ver=$(brew_get_formula_version_api "$name")
    api_status=$?
    if (( api_status == 0 )); then
      if [[ -z "$official_ver" ]]; then
        brew_compare_against_other_tap "$tap" "$name" "$custom_ver"
        continue
      fi
    elif (( api_status == 2 )); then
      brew_compare_against_other_tap "$tap" "$name" "$custom_ver"
      continue
    else
      brew_print_status "$name" "ERROR" "(custom $custom_ver, failed to query the Homebrew API)"
      continue
    fi

    cmp=$(brew_compare_versions "$custom_ver" "$official_ver")
    cmp_status=$?
    if (( cmp_status != 0 )); then
      if (( cmp_status == 2 )); then
        brew_print_status "$name" "SKIP" "(custom $custom_ver, unable to compare against $official_ver)"
        continue
      else
        brew_print_status "$name" "ERROR" "(comparison failed for $custom_ver vs $official_ver)"
        continue
      fi
    fi

    case "$cmp" in
      -1)
        brew_print_status "$name" "OUTDATED" "(custom $custom_ver < core $official_ver)"
        ;;
      0)
        brew_print_status "$name" "OK" "($custom_ver)"
        ;;
      1)
        brew_print_status "$name" "AHEAD" "(custom $custom_ver > core $official_ver)"
        ;;
      *)
        brew_print_status "$name" "ERROR" "(compare failed: $custom_ver vs $official_ver)"
        ;;
    esac
  done
}

usage() {
  cat <<EOF
Usage: brew-custom-compare.zsh [options] [formula ...]

Options:
  -t, --tap <tap>        Custom tap to inspect (default: $DEFAULT_CUSTOM_TAP)
  -h, --help             Show this help message

With no formula arguments, every Ruby formula file in the tap is compared.
Provide one or more formulas to limit the comparison set.
EOF
}

main() {
  local tap="$DEFAULT_CUSTOM_TAP"
  local -a formulas

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -t|--tap)
        [[ -n "$2" ]] || { echo "Missing tap after $1" >&2; return 1; }
        tap="$2"
        shift 2
        ;;
      -h|--help)
        usage
        return 0
        ;;
      --)
        shift
        formulas+=("$@")
        break
        ;;
      -*)
        echo "Unknown option: $1" >&2
        usage >&2
        return 1
        ;;
      *)
        formulas+=("$1")
        shift
        ;;
    esac
  done

  if ! brew_cache_pinned; then
    echo "Warning: failed to list pinned formulae; continuing without PINNED labels." >&2
  fi

  if ! brew_compare_custom_vs_core_api "$tap" "${formulas[@]}"; then
    return 1
  fi

  return 0
}

if [[ "${(%):-%N}" == "$0" ]]; then
  main "$@"
fi
