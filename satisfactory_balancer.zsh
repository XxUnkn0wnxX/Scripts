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

__bal_build_steps() {
  local count3=$1 count2=$2
  local branches=1 layer=1
  local -a lines=()

  __bal_best_sequence "$count3" "$count2"

  local factor splitters word next verbose short
  for factor in ${=__bal_plan_best_seq}; do
    splitters=$branches
    word="splitter"
    (( splitters != 1 )) && word+="s"
    next=$(( branches * factor ))
    if (( factor == 3 )); then
      verbose="Layer ${layer} – place ${splitters} ${word} to create ${next} outputs (${splitters}× 1→3)"
      short="Layer ${layer} place ${splitters}×1→3"
    else
      verbose="Layer ${layer} – place ${splitters} ${word} to create ${next} outputs (${splitters}× 1→2)"
      short="Layer ${layer} place ${splitters}×1→2"
    fi
    lines+=("${verbose}"$'\t'"${short}"$'\t'"${splitters}"$'\t'"${factor}")
    branches=$next
    (( layer++ ))
  done

  printf '%s\n' "${lines[@]}"
}

__bal_recipe_summary() {
  local count3=$1 count2=$2
  __bal_best_sequence "$count3" "$count2"
  local seq=${__bal_plan_best_seq}
  if [[ -z "$seq" ]]; then
    echo "Recipe: no splitter layers"
    return
  fi

  local -a tokens=(${=seq})
  local desc="Recipe: Layers → "
  local factor first=1 branches=1
  for factor in "${tokens[@]}"; do
    if (( first )); then
      first=0
    else
      desc+=", "
    fi
    desc+="${branches}×1→${factor}"
    branches=$(( branches * factor ))
  done

  if (( ${#tokens[@]} == 1 )); then
    if [[ ${tokens[1]} == 2 ]]; then
      desc="Recipe: 1 layer of 1→2 splitters"
    else
      desc="Recipe: 1 layer of 1→3 splitters"
    fi
  elif (( ${#tokens[@]} > 1 )); then
    local all_same=1
    for factor in "${tokens[@]:1}"; do
      if [[ $factor != ${tokens[1]} ]]; then
        all_same=0
        break
      fi
    done
    if (( all_same )); then
      local layers=${#tokens[@]}
      local word="layers"
      (( layers == 1 )) && word="layer"
      if (( tokens[1] == 2 )); then
        desc="Recipe: ${layers} ${word} of 1→2 splitters"
      else
        desc="Recipe: ${layers} ${word} of 1→3 splitters"
      fi
    fi
  fi

  echo "${desc}"
}

__bal_quiet_clean_line() {
  local inputs=$1 outputs=$2 count3=$3 count2=$4 prev=$5
  local recipe=$(__bal_recipe_summary "$count3" "$count2")
  local fields=("${inputs}:${outputs}" "LOAD BALANCER" "CLEAN → build 1→$outputs (no loopback)" "$recipe")
  local step_lines=$(__bal_build_steps "$count3" "$count2")
  if [[ -n "$step_lines" ]]; then
    local -a steps_short=()
    local line short
    for line in ${(f)step_lines}; do
      short=${line#*$'\t'}
      short=${short%%$'\t'*}
      steps_short+=("$short")
    done
    fields+=("Steps: ${(j:; :)steps_short}")
  fi
  if (( prev > 0 && prev < outputs )); then
    fields+=("Prev clean 1:$prev")
  fi
  __bal_join_fields "${fields[@]}"
}

__bal_quiet_dirty_line() {
  local inputs=$1 outputs=$2 leftover=$3 next=$4 loopback=$5 count3=$6 count2=$7 prev=$8
  local descriptor="${inputs}:${outputs}"
  local loop_text="loop back $loopback outputs"
  (( loopback == 1 )) && loop_text="loop back 1 output"
  local recipe=$(__bal_recipe_summary "$count3" "$count2")
  local fields=("$descriptor" "LOAD BALANCER" "NOT clean (leftover $leftover)" "build 1→$next" "$loop_text" "$recipe")
  local step_lines=$(__bal_build_steps "$count3" "$count2")
  if [[ -n "$step_lines" ]]; then
    local -a steps_short=()
    local line short
    for line in ${(f)step_lines}; do
      short=${line#*$'\t'}
      short=${short%%$'\t'*}
      steps_short+=("$short")
    done
    fields+=("Steps: ${(j:; :)steps_short}")
  fi
  if (( prev > 0 )); then
    fields+=("Prev clean 1:$prev")
  fi
  __bal_join_fields "${fields[@]}"
}

__bal_recipe_lines() {
  local count3=$1 count2=$2
  local summary=$(__bal_recipe_summary "$count3" "$count2")
  echo "${summary}."

  local step_lines=$(__bal_build_steps "$count3" "$count2")
  if [[ -z "$step_lines" ]]; then
    echo "  Do: no splitter layers required."
  else
    local -a total_counts=()
    local -a factors=()
    local line verbose remainder count factor
    echo "  Do:"
    for line in ${(f)step_lines}; do
      verbose=${line%%$'\t'*}
      echo "    ${verbose}"
      remainder=${line#*$'\t'}
      remainder=${remainder#*$'\t'}
      count=${remainder%%$'\t'*}
      remainder=${remainder#*$'\t'}
      factor=$remainder
      total_counts+=("$count")
      factors+=("$factor")
    done
    if (( ${#total_counts[@]} > 0 )); then
      local sum_expr="${(j: + :)total_counts}"
      local total_splitters=0
      local factor_expr="${(j:×:)factors}"
      for count in "${total_counts[@]}"; do
        (( total_splitters += count ))
      done
      echo "  Note: Layer order ${factor_expr} (branch sequence) → total splitters ${sum_expr} = ${total_splitters}."
    fi
  fi
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
  if (( quiet )); then
    __bal_quiet_clean_line "$inputs" "$outputs" 0 0 0
    return 0
  fi
  printf "%s | LOAD BALANCER | %s\n" "$descriptor" "$headline"
  __bal_recipe_lines 0 0
  return 0
}

__bal_handle_load_clean() {
  local inputs=$1 outputs=$2 quiet=$3 count2=$4 count3=$5
  local descriptor="${inputs}:${outputs}"
  local headline="CLEAN → build 1→${outputs} (no loopback)"
  local prev=$(__bal_prev_clean "$outputs")
  if (( quiet )); then
    __bal_quiet_clean_line "$inputs" "$outputs" "$count3" "$count2" "$prev"
    return 0
  fi
  printf "%s | LOAD BALANCER | %s\n" "$descriptor" "$headline"
  __bal_recipe_lines "$count3" "$count2"
  if (( prev > 0 && prev < outputs )); then
    printf "Prev clean: 1:%d\n" "$prev"
  fi
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
  local loop_word="outputs"
  (( loopback == 1 )) && loop_word="output"
  if (( quiet )); then
    __bal_quiet_dirty_line "$inputs" "$outputs" "$leftover" "$next_clean" "$loopback" "$count3_clean" "$count2_clean" "$prev"
    return 0
  fi
  printf "%s | %s | %s\n" "$descriptor" "$mode" "$headline"
  printf "Next clean size: %d → build 1→%d\n" "$next_clean" "$next_clean"
  printf "Loop back: %d %s (merge them, feed back to input)\n" "$loopback" "$loop_word"
  __bal_recipe_lines "$count3_clean" "$count2_clean"
  if (( prev > 0 )); then
    printf "Prev clean: 1:%d\n" "$prev"
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
