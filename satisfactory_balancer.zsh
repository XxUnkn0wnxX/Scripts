#!/usr/bin/env zsh
# Satisfactory load-balancer helper — pure CLI (zsh)
# Modes:
#   LOAD BALANCER → 1 input spread across n outputs (1→n)
#   BALANCER      → n inputs evenly mixed across m outputs (n>1, m≥n)
#   COMPRESSOR    → n inputs compressed into m outputs with pack-first priority (n>1, m<n)

__bal_usage() {
  cat <<'USAGE'
Usage: satisfactory_balancer.zsh [options] n:m [n:m ...]
  Helper for Satisfactory splitter/merger layouts that mimic the official Balancer wiki.

Options:
  -q, --quiet    Compact single-line output (same prefix/headline as normal mode).
  -n, --nico     Enable Nico ratio mode for complex 1→N splits (1:A:B[:C...]).
  -h, --help     Show this help and exit.

Notes:
  • Normal ratios automatically detect LOAD BALANCER, BALANCER, or COMPRESSOR mode.
  • Nico mode processes complex 1→N ratios inspired by NicoBuilds' Reddit guide.
  • Inputs and outputs must be positive integers; use explicit 1:n instead of bare n.
USAGE
}

__bal_is_positive_int() {
  local value="$1"
  [[ -n "$value" && "$value" == <-> ]] || return 1
  (( value > 0 )) || return 1
  return 0
}

__bal_join_fields() {
  local fields=("$@")
  printf "%s\n" "${(j: | :)fields}"
}

# Factor n into 2^a * 3^b * r; prints: "a b r"  (r == 1 iff clean)
__bal_exponents23() {
  local x=$1
  local a=0 b=0 r=$x
  while (( r>1 && r%2==0 )); do ((a++)); ((r/=2)); done
  while (( r>1 && r%3==0 )); do ((b++)); ((r/=3)); done
  echo "$a $b $r"
}

typeset -g __bal_plan_best_cost
typeset -g __bal_plan_best_seq

__bal_plan_dfs() {
  local seq=$1
  local rem2=$2
  local rem3=$3
  local branches=$4
  local cost=$5

  if (( rem2 == 0 && rem3 == 0 )); then
    if (( __bal_plan_best_cost < 0 || cost < __bal_plan_best_cost )); then
      __bal_plan_best_cost=$cost
      __bal_plan_best_seq=$seq
    fi
    return
  fi

  if (( rem2 > 0 )); then
    local next=$(( branches * 2 ))
    local new_seq=$seq
    [[ -n "$new_seq" ]] && new_seq+=" "
    new_seq+="2"
    __bal_plan_dfs "$new_seq" $(( rem2 - 1 )) "$rem3" "$next" $(( cost + branches ))
  fi

  if (( rem3 > 0 )); then
    local next=$(( branches * 3 ))
    local new_seq=$seq
    [[ -n "$new_seq" ]] && new_seq+=" "
    new_seq+="3"
    __bal_plan_dfs "$new_seq" "$rem2" $(( rem3 - 1 )) "$next" $(( cost + branches ))
  fi
}

__bal_best_sequence() {
  local count3=$1 count2=$2
  __bal_plan_best_cost=-1
  __bal_plan_best_seq=""
  __bal_plan_dfs "" "$count2" "$count3" 1 0
}

__bal_total_splitters() {
  local count3=$1 count2=$2
  __bal_best_sequence "$count3" "$count2"
  local seq=${__bal_plan_best_seq}
  local branches=1 total=0 factor
  for factor in ${=seq}; do
    total=$(( total + branches ))
    branches=$(( branches * factor ))
  done
  echo $total
}

__bal_pluralize() {
  local count=$1 singular=$2 plural=$3
  [[ -z "$plural" ]] && plural="${singular}s"
  if (( count == 1 )); then
    echo "$singular"
  else
    echo "$plural"
  fi
}

__bal_recipe_block() {
  local count3=$1 count2=$2 total=$3
  [[ -z "$total" ]] && total=$(__bal_total_splitters "$count3" "$count2")
  if (( count3 == 0 && count2 == 0 )); then
    echo "Recipe: no splitters required."
    echo "  Do: feed the input directly to the output."
    local word=$(__bal_pluralize "$total" "splitter" "splitters")
    printf "Components: %d %s\n" "$total" "$word"
    return
  fi
  printf "Recipe: x%d of 1→3 splitters, x%d of 1→2 splitters (order doesn’t matter)\n" "$count3" "$count2"
  if (( count3 > 0 && count2 > 0 )); then
    printf "  Do: split by 3, %d time(s); then split each branch by 2, %d time(s).\n" "$count3" "$count2"
  elif (( count3 > 0 )); then
    printf "  Do: split by 3, %d time(s).\n" "$count3"
  elif (( count2 > 0 )); then
    printf "  Do: split each branch by 2, %d time(s).\n" "$count2"
  fi
  local word=$(__bal_pluralize "$total" "splitter" "splitters")
  printf "Components: %d %s\n" "$total" "$word"
}

__bal_recipe_quiet_field() {
  local count3=$1 count2=$2
  if (( count3 == 0 && count2 == 0 )); then
    echo "Recipe: no splitters required"
    return
  fi
  echo "Recipe: x${count3} of 1→3 splitters, x${count2} of 1→2 splitters (order doesn’t matter)"
}

__bal_components_field() {
  local total=$1
  local word=$(__bal_pluralize "$total" "splitter" "splitters")
  echo "Components: ${total} ${word}"
}

# Smallest clean m = 2^A * 3^B such that m >= n
__bal_next_clean() {
  local n=$1 best=0 pow3=1
  while (( pow3 < n*3 )); do
    local t=$(( (n + pow3 - 1) / pow3 ))
    local p2=1; while (( p2 < t )); do (( p2*=2 )); done
    local m=$(( p2 * pow3 ))
    if (( m >= n && (best==0 || m < best) )); then best=$m; fi
    (( pow3 *= 3 ))
  done
  echo $best
}

# Largest clean p = 2^A * 3^B such that p <= n
__bal_prev_clean() {
  local n=$1 best=0 pow3=1
  while (( pow3 <= n )); do
    local u=$(( n / pow3 ))
    if (( u >= 1 )); then
      local p2=1; while (( p2*2 <= u )); do (( p2*=2 )); done
      local m=$(( p2 * pow3 ))
      if (( m <= n && m > best )); then best=$m; fi
    fi
    (( pow3 *= 3 ))
  done
  echo $best
}

__bal_detect_mode() {
  local inputs=$1 outputs=$2
  if (( inputs == 1 )); then
    if (( outputs >= 1 )); then
      echo "load"
      return 0
    fi
    echo "invalid"
    return 0
  fi
  if (( inputs > 1 && outputs >= inputs )); then
    echo "balancer"
  elif (( inputs > 1 && outputs < inputs )); then
    echo "compressor"
  else
    echo "invalid"
  fi
}

__bal_handle_trivial_load() {
  local inputs=$1 outputs=$2 quiet=$3
  local descriptor="${inputs}:${outputs}"
  local headline="CLEAN → build 1→${outputs} (no loopback)"
  local fields=("$descriptor" "LOAD BALANCER" "$headline")
  local recipe_field=$(__bal_recipe_quiet_field 0 0)
  local components_field=$(__bal_components_field 0)
  if (( quiet )); then
    fields+=("$recipe_field" "$components_field")
    __bal_join_fields "${fields[@]}"
    return 0
  fi
  printf "%s | LOAD BALANCER | %s\n" "$descriptor" "$headline"
  __bal_recipe_block 0 0 0
  return 0
}

__bal_print_previous_clean() {
  local prev=$1
  if (( prev > 0 )); then
    printf "Previous clean size: 1:%d\n" "$prev"
  fi
}

__bal_handle_load_clean() {
  local inputs=$1 outputs=$2 quiet=$3 count2=$4 count3=$5
  local descriptor="${inputs}:${outputs}"
  local headline="CLEAN → build 1→${outputs} (no loopback)"
  local prev=$(__bal_prev_clean "$outputs")
  local total=$(__bal_total_splitters "$count3" "$count2")
  if (( quiet )); then
    local -a fields=("$descriptor" "LOAD BALANCER" "$headline")
    if (( prev > 0 && prev < outputs )); then
      fields+=("Previous clean: 1:${prev}")
    fi
    fields+=("$(__bal_recipe_quiet_field "$count3" "$count2")" "$(__bal_components_field "$total")")
    __bal_join_fields "${fields[@]}"
    return 0
  fi
  printf "%s | LOAD BALANCER | %s\n" "$descriptor" "$headline"
  if (( prev > 0 && prev < outputs )); then
    printf "Previous clean size: 1:%d\n" "$prev"
  fi
  __bal_recipe_block "$count3" "$count2" "$total"
  return 0
}

__bal_handle_load_dirty() {
  local inputs=$1 outputs=$2 quiet=$3 leftover=$4 count2_clean=$5 count3_clean=$6
  local descriptor="${inputs}:${outputs}"
  local mode="LOAD BALANCER"
  local headline="NOT clean (leftover ${leftover})"
  local next_clean=$(__bal_next_clean "$outputs")
  local loopback=$(( next_clean - outputs ))
  local prev=$(__bal_prev_clean "$outputs")
  local total=$(__bal_total_splitters "$count3_clean" "$count2_clean")
  local loop_word="outputs"
  (( loopback == 1 )) && loop_word="output"
  if (( quiet )); then
    local -a fields=("$descriptor" "$mode" "$headline" "Next clean: 1:${next_clean}" "Loop back: ${loopback}")
    if (( prev > 0 )); then
      fields+=("Previous clean: 1:${prev}")
    fi
    fields+=("$(__bal_recipe_quiet_field "$count3_clean" "$count2_clean")" "$(__bal_components_field "$total")")
    __bal_join_fields "${fields[@]}"
    return 0
  fi
  printf "%s | %s | %s\n" "$descriptor" "$mode" "$headline"
  printf "Next clean size: 1:%d → build 1→%d\n" "$next_clean" "$next_clean"
  printf "Loop back: %d %s (merge and feed back to input)\n" "$loopback" "$loop_word"
  __bal_recipe_block "$count3_clean" "$count2_clean" "$total"
  if (( prev > 0 )); then
    printf "Previous clean size: 1:%d\n" "$prev"
  fi
  return 0
}

__bal_handle_load_ratio() {
  local inputs=$1 outputs=$2 quiet=$3
  if (( outputs == 1 )); then
    __bal_handle_trivial_load "$inputs" "$outputs" "$quiet"
    return $?
  fi
  local a=0 b=0 r=0
  read a b r <<< "$(__bal_exponents23 "$outputs")"
  if (( r == 1 )); then
    __bal_handle_load_clean "$inputs" "$outputs" "$quiet" "$a" "$b"
  else
    local am=0 bm=0 rr=0
    local next_clean=$(__bal_next_clean "$outputs")
    read am bm rr <<< "$(__bal_exponents23 "$next_clean")"
    __bal_handle_load_dirty "$inputs" "$outputs" "$quiet" "$r" "$am" "$bm"
  fi
}

__bal_handle_balancer_ratio() {
  local inputs=$1 outputs=$2
  echo "${inputs}:${outputs} → BALANCER mode not implemented yet" >&2
  return 2
}

__bal_handle_compressor_ratio() {
  local inputs=$1 outputs=$2
  echo "${inputs}:${outputs} → COMPRESSOR mode not implemented yet" >&2
  return 2
}

__bal_process_ratio() {
  local token=$1 quiet=$2
  local -a parts=("${(@s/:/)token}")
  if (( ${#parts[@]} != 2 )); then
    echo "invalid ratio: ${token}" >&2
    return 2
  fi
  local inputs=${parts[1]}
  local outputs=${parts[2]}
  if ! __bal_is_positive_int "$inputs" || ! __bal_is_positive_int "$outputs"; then
    echo "invalid ratio: ${token}" >&2
    return 2
  fi
  local mode=$(__bal_detect_mode "$inputs" "$outputs")
  if [[ "$mode" == "invalid" ]]; then
    echo "invalid ratio: ${token}" >&2
    return 2
  fi
  case "$mode" in
    load)
      __bal_handle_load_ratio "$inputs" "$outputs" "$quiet"
      ;;
    balancer)
      __bal_handle_balancer_ratio "$inputs" "$outputs"
      ;;
    compressor)
      __bal_handle_compressor_ratio "$inputs" "$outputs"
      ;;
  esac
}

__bal_process_nico_mode() {
  echo "satisfactory_balancer: --nico mode is not implemented yet" >&2
  return 2
}

__bal_main() {
  local quiet=0 nico=0
  local -a args=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --)
        shift
        while [[ $# -gt 0 ]]; do
          args+=("$1")
          shift
        done
        break
        ;;
      -q|--quiet)
        quiet=1
        shift
        ;;
      -n|--nico)
        nico=1
        shift
        ;;
      -h|--help)
        __bal_usage
        return 0
        ;;
      -* )
        echo "satisfactory_balancer: unknown option: $1" >&2
        __bal_usage >&2
        return 2
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done

  if (( ${#args[@]} == 0 )); then
    __bal_usage >&2
    return 2
  fi

  if (( nico )); then
    __bal_process_nico_mode "$quiet" "${args[@]}"
    return $?
  fi

  local had_error=0 target rc
  for target in "${args[@]}"; do
    __bal_process_ratio "$target" "$quiet"
    rc=$?
    if (( rc != 0 )); then
      if (( had_error == 0 || rc > had_error )); then
        had_error=$rc
      fi
    fi
  done
  return $had_error
}

__bal_main "$@"
