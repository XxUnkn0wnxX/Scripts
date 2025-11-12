#!/usr/bin/env zsh
# Satisfactory load-balancer helper — pure CLI (zsh)
# Usage:
#   zsh satisfactory_balancer.zsh [options] <N...>
# Options:
#   -q, --quiet  Compact one-line output
#   -h, --help   Show help and exit

__bal_usage() {
  cat <<'USAGE'
Usage: satisfactory_balancer.zsh [options] <N...>
  Friendly helper for 1→n Satisfactory load balancers (splitters only 1→2 / 1→3).

Options:
  -q, --quiet  Compact, single-line output (Prev clean shows the largest clean size below N).
  -h, --help   Show this help

Examples:
  zsh satisfactory_balancer.zsh 48
  zsh satisfactory_balancer.zsh 52
  zsh satisfactory_balancer.zsh 44 95 72
USAGE
}

# Factor n into 2^a * 3^b * r; prints: "a b r"  (r == 1 iff clean)
__bal_exponents23() {
  local x=$1
  local a=0 b=0 r=$x
  while (( r>1 && r%2==0 )); do ((a++)); ((r/=2)); done
  while (( r>1 && r%3==0 )); do ((b++)); ((r/=3)); done
  echo "$a $b $r"
}

__bal_join_fields() {
  local fields=("$@")
  printf "%s\n" "${(j: | :)fields}"
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

  # Find minimal-splitter ordering of 1→2 and 1→3 layers
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

  # Expand concise cases
  if (( ${#tokens[@]} == 1 )); then
    if [[ ${tokens[1]} == 2 ]]; then
      desc="Recipe: 1 layer of 1→2 splitters"
    else
      desc="Recipe: 1 layer of 1→3 splitters"
    fi
  elif (( ${#tokens[@]} > 1 )); then
    # Check if all factors identical
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
  local n=$1 count3=$2 count2=$3 prev=$4
  local recipe=$(__bal_recipe_summary "$count3" "$count2")
  local fields=("N=$n" "CLEAN" "build 1→$n (no loopback)" "$recipe")
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
  if (( prev > 0 && prev < n )); then
    fields+=("Prev clean $prev")
  fi
  __bal_join_fields "${fields[@]}"
}

__bal_quiet_dirty_line() {
  local n=$1 leftover=$2 next=$3 loopback=$4 count3=$5 count2=$6 prev=$7
  local loop_text="loop back $loopback outputs"
  (( loopback == 1 )) && loop_text="loop back 1 output"
  local recipe=$(__bal_recipe_summary "$count3" "$count2")
  local fields=("N=$n" "NOT clean" "build 1→$next" "$loop_text" "$recipe")
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
    fields+=("Prev clean $prev")
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
  # For each 3^B, choose the minimal 2^A (power of two) to reach >= n; keep the smallest m
  while (( pow3 < n*3 )); do
    local t=$(( (n + pow3 - 1) / pow3 ))   # ceil(n / 3^B)
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
    local u=$(( n / pow3 ))   # floor(n / 3^B)
    if (( u >= 1 )); then
      local p2=1; while (( p2*2 <= u )); do (( p2*=2 )); done
      local m=$(( p2 * pow3 ))
      if (( m <= n && m > best )); then best=$m; fi
    fi
    (( pow3 *= 3 ))
  done
  echo $best
}

# ---- Main ----
__bal_main() {
  local quiet=0

  # Parse flags
  local args=()
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
      -h|--help)
        __bal_usage
        return 0
        ;;
      -*)
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

  # Collect any trailing positional arguments
  while [[ $# -gt 0 ]]; do
    args+=("$1")
    shift
  done

  local had_error=0
  if (( ${#args[@]} == 0 )); then
    __bal_usage >&2
    return 2
  fi
  for n in "${args[@]}"; do
    if [[ ! "$n" == <-> ]] || (( n <= 0 )); then
      echo "N=$n  ->  invalid (must be a positive integer)" >&2
      had_error=2
      continue
    fi

    local a=0 b=0 r=0; read a b r <<< "$(__bal_exponents23 "$n")"
    if (( r == 1 )); then
      local p_clean=$(__bal_prev_clean "$n")
      if (( quiet )); then
        __bal_quiet_clean_line "$n" "$b" "$a" "$p_clean"
      else
        printf "N=%s | CLEAN → build 1→%s (no loopback)\n" "$n" "$n"
        __bal_recipe_lines "$b" "$a"
        if (( p_clean > 0 && p_clean < n )); then
          echo "Prev clean: $p_clean"
        fi
      fi
      continue
    fi

    local m=$(__bal_next_clean "$n")
    local k=$(( m - n ))
    local am=0 bm=0 rr=0; read am bm rr <<< "$(__bal_exponents23 "$m")"
    local p=$(__bal_prev_clean "$n")

    if (( quiet )); then
      __bal_quiet_dirty_line "$n" "$r" "$m" "$k" "$bm" "$am" "$p"
    else
      echo "N=$n | NOT clean (leftover $r)"
      printf "Next clean size: %s → build 1→%s\n" "$m" "$m"
      printf "Loop back: %d outputs (merge them, feed back to input)\n" "$k"
      __bal_recipe_lines "$bm" "$am"
      if (( p > 0 )); then
        echo "Prev clean: $p"
      fi
    fi
  done

  return $had_error
}

__bal_main "$@"
