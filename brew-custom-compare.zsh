#!/usr/local/bin/zsh

# --- Configuration -----------------------------------------------------------
# Override these via environment variables if needed before running the script.
DEFAULT_CUSTOM_TAP=${DEFAULT_CUSTOM_TAP:-"custom/versions"}
HOMEBREW_API_FORMULA_BASE=${HOMEBREW_API_FORMULA_BASE:-"https://formulae.brew.sh/api/formula"}

# --- Helpers for comparing custom tap vs upstream core using Homebrew's API ---

# Fetch stable versions for a list of specs (e.g., custom/versions/node) in batches.
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

  input_formulas=("$@")

  tap_dir=$(brew --repository "$tap") || {
    echo "Tap $tap not found." >&2
    return 1
  }

  if (( ${#input_formulas[@]} )); then
    formulas=("${input_formulas[@]}")
  else
    for rb in "$tap_dir"/Formula/*.rb; do
      [[ -e "$rb" ]] || continue
      name=${rb:t}
      name=${name%.rb}
      formulas+=("$name")
    done
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
      custom_versions["$full_name"]="$version"
    done <<<"$collect_output"
  fi

  echo "Comparing $tap (local) vs Homebrew API (upstream):"
  echo

  for name in "${formulas[@]}"; do
    [[ -n "$name" ]] || continue

    spec="$tap/$name"
    custom_ver=${custom_versions["$spec"]}
    if [[ -z "$custom_ver" ]]; then
      printf '%-25s %s\n' "$name" "ERROR     (failed to get custom version)"
      continue
    fi

    official_ver=$(brew_get_formula_version_api "$name")
    api_status=$?
    if (( api_status != 0 )); then
      printf '%-25s %s\n' "$name" "SKIP      (custom $custom_ver, not checked since it's not listed in the Homebrew API)"
      continue
    fi
    if [[ -z "$official_ver" ]]; then
      printf '%-25s %s\n' "$name" "SKIP      (custom $custom_ver, upstream version missing)"
      continue
    fi

    cmp=$(brew_compare_versions "$custom_ver" "$official_ver")
    cmp_status=$?
    if (( cmp_status != 0 )); then
      if (( cmp_status == 2 )); then
        printf '%-25s %s\n' "$name" "SKIP      (custom $custom_ver, unable to compare against $official_ver)"
        continue
      else
        printf '%-25s %s\n' "$name" "ERROR     (comparison failed for $custom_ver vs $official_ver)"
        continue
      fi
    fi

    case "$cmp" in
      -1)
        printf '%-25s %s\n' "$name" "OUTDATED  (custom $custom_ver < core $official_ver)"
        ;;
      0)
        printf '%-25s %s\n' "$name" "OK        ($custom_ver)"
        ;;
      1)
        printf '%-25s %s\n' "$name" "AHEAD     (custom $custom_ver > core $official_ver)"
        ;;
      *)
        printf '%-25s %s\n' "$name" "ERROR     (compare failed: $custom_ver vs $official_ver)"
        ;;
    esac
  done
}

usage() {
  cat <<EOF
Usage: brew-custom-compare.zsh [options] [formula ...]

Options:
  -t, --tap <tap>        Custom tap to inspect (default: $DEFAULT_CUSTOM_TAP)
  -a, --all-taps         Compare every tapped repository (excluding $DEFAULT_CUSTOM_TAP and homebrew/core)
  -h, --help             Show this help message

With no formula arguments, every Ruby formula file in the tap is compared.
Provide one or more formulas to limit the comparison set.
EOF
}

main() {
  local tap="$DEFAULT_CUSTOM_TAP"
  local scan_all_taps=0
  local -a formulas

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -t|--tap)
        [[ -n "$2" ]] || { echo "Missing tap after $1" >&2; return 1; }
        tap="$2"
        shift 2
        ;;
      -a|--all-taps)
        scan_all_taps=1
        shift
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

  if (( scan_all_taps )) && [[ "$tap" != "$DEFAULT_CUSTOM_TAP" ]]; then
    echo "--all-taps cannot be combined with --tap" >&2
    return 1
  fi

  if (( scan_all_taps )); then
    local -a taps_to_scan=()
    local tap_name

    while IFS= read -r tap_name; do
      [[ -z "$tap_name" ]] && continue
      [[ "$tap_name" == "$DEFAULT_CUSTOM_TAP" ]] && continue
      [[ "$tap_name" == "homebrew/core" ]] && continue
      taps_to_scan+=("$tap_name")
    done < <(brew tap 2>/dev/null)

    if (( ${#taps_to_scan[@]} == 0 )); then
      echo "No additional taps found to scan." >&2
      return 0
    fi

    for tap_name in "${taps_to_scan[@]}"; do
      if ! brew_compare_custom_vs_core_api "$tap_name" "${formulas[@]}"; then
        echo "Skipping tap $tap_name due to errors." >&2
      fi
      echo
    done
    return 0
  fi

  brew_compare_custom_vs_core_api "$tap" "${formulas[@]}"
}

if [[ "${(%):-%N}" == "$0" ]]; then
  main "$@"
fi
