#!/usr/bin/env zsh
# Satisfactory load-balancer helper — pure CLI (zsh)
# Modes:
#   LOAD-BALANCER → 1 input spread across n outputs (1→n)
#   BELT-BALANCER → n inputs evenly mixed across m outputs (n>1, m≥n)
#   BELT-COMPRESSOR → n inputs compressed into m outputs with pack-first priority (n>1, m<n)

__bal_usage() {
  cat <<'USAGE'
Usage: satisfactory_balancer.zsh [options] n:m [n:m ...]
  Helper for Satisfactory splitter/merger layouts that mimic the official Balancer wiki.

Options:
  -h, --help     Show this help and exit.

Examples:
  satisfactory_balancer.zsh 1:48      # LOAD-BALANCER (1 input → 48 outputs)
  satisfactory_balancer.zsh 4:7       # BELT-BALANCER (4 inputs → 7 outputs)
  satisfactory_balancer.zsh 5:2       # BELT-COMPRESSOR (5 inputs → 2 outputs)
  satisfactory_balancer.zsh 1:44:8    # Complex 1→N ratio (auto-detected Nico math)

Notes:
  • Normal ratios automatically detect LOAD-BALANCER, BELT-BALANCER, or BELT-COMPRESSOR mode.
  • Complex 1→N ratios (like 1:44:8) are auto-detected using NicoBuilds-inspired math.
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

__bal_merge_build_steps() {
  local count3=$1 count2=$2
  __bal_best_sequence "$count3" "$count2"
  local seq=${__bal_plan_best_seq}
  if [[ -z "$seq" ]]; then
    return
  fi

  local -a factors=(${=seq})
  local total=1 factor
  for factor in "${factors[@]}"; do
    total=$(( total * factor ))
  done

  local lines=()
  local layer=1 lanes=$total nodes word next verbose short
  for factor in "${factors[@]}"; do
    nodes=$(( lanes / factor ))
    word="merger"
    (( nodes != 1 )) && word+="s"
    verbose="Layer ${layer} – place ${nodes} ${word} to combine ${factor} lanes into 1 (${nodes}× ${factor}→1)"
    short="Layer ${layer} place ${nodes}×${factor}→1"
    lines+=("${verbose}"$'\t'"${short}"$'\t'"${nodes}"$'\t'"${factor}")
    lanes=$nodes
    (( layer++ ))
  done

  printf '%s\n' "${lines[@]}"
}

__bal_recipe_summary() {
  local count3=$1 count2=$2 label=${3:-"Recipe"} mode=${4:-"split"}
  if [[ $mode == "merge" ]]; then
    if (( count3 == 0 && count2 == 0 )); then
      echo "${label}: no merger layers"
      return
    fi
    printf "%s: x%d of 3→1 mergers, x%d of 2→1 mergers (order doesn’t matter)" "$label" "$count3" "$count2"
    return
  fi
  __bal_best_sequence "$count3" "$count2"
  local seq=${__bal_plan_best_seq}
  if [[ -z "$seq" ]]; then
    echo "${label}: no splitter layers"
    return
  fi

  local -a tokens=(${=seq})
  local desc="${label}: Layers → "
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
      desc="${label}: 1 layer of 1→2 splitters"
    else
      desc="${label}: 1 layer of 1→3 splitters"
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
        desc="${label}: ${layers} ${word} of 1→2 splitters"
      else
        desc="${label}: ${layers} ${word} of 1→3 splitters"
      fi
    fi
  fi

  echo "${desc}"
}

__bal_recipe_lines() {
  local count3=$1 count2=$2 label=${3:-"Recipe"} subject=${4:-"Do"} mode=${5:-"split"}
  local summary=$(__bal_recipe_summary "$count3" "$count2" "$label" "$mode")
  echo "${summary}."

  local step_lines
  if [[ $mode == "merge" ]]; then
    step_lines=$(__bal_merge_build_steps "$count3" "$count2")
  else
    step_lines=$(__bal_build_steps "$count3" "$count2")
  fi
  if [[ -z "$step_lines" ]]; then
    echo "  ${subject}: no ${mode} layers required."
  else
    local -a total_counts=()
    local -a factors=()
    local line verbose remainder count factor
    echo "  ${subject}:"
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
      local total_nodes=0
      local factor_expr="${(j:×:)factors}"
      for count in "${total_counts[@]}"; do
        (( total_nodes += count ))
      done
      local plural="splitters"
      if [[ $mode == "merge" ]]; then
        plural="mergers"
      fi
      echo "  Note: Layer order ${factor_expr} (branch sequence) → total ${plural} per belt ${sum_expr} = ${total_nodes}."
    fi
  fi
}

__bal_split_steps_short() {
  local count3=$1 count2=$2
  local step_lines=$(__bal_build_steps "$count3" "$count2")
  if [[ -z "$step_lines" ]]; then
    echo ""
    return
  fi
  local -a steps_short=()
  local line short
  for line in ${(f)step_lines}; do
    short=${line#*$'\t'}
    short=${short%%$'\t'*}
    steps_short+=("$short")
  done
  echo "${(j:; :)steps_short}"
}

__bal_split_lines_and_note() {
  local count3=$1 count2=$2
  local step_lines=$(__bal_build_steps "$count3" "$count2")
  local lines_text=""
  local note=""
  if [[ -z "$step_lines" ]]; then
    lines_text="no split layers required."
  else
    local -a total_counts=()
    local -a factors=()
    local line remainder count factor verbose
    for line in ${(f)step_lines}; do
      verbose=${line%%$'\t'*}
      if [[ -n "$lines_text" ]]; then
        lines_text+=$'\n'
      fi
      lines_text+="$verbose"
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
      local factor_expr="${(j:×:)factors}"
      local total_nodes=0
      local c
      for c in "${total_counts[@]}"; do
        (( total_nodes += c ))
      done
      local noun_phrase="splitters"
      note="Layer order ${factor_expr} (branch sequence) → total ${noun_phrase} per belt ${sum_expr} = ${total_nodes}"
    fi
  fi
  printf '%s\x1F%s\n' "$lines_text" "$note"
}

__bal_merge_steps_lines() {
  local seq=$1
  local -a factors=(${=seq})
  if (( ${#factors[@]} == 0 )); then
    echo ""
    return
  fi
  local idx=1 factor lines=()
  for factor in "${factors[@]}"; do
    lines+=("Layer ${idx} – place 1 merger to combine ${factor} lanes into 1 belt (1× ${factor}→1)")
    (( idx++ ))
  done
  printf '%s\n' "${lines[@]}"
}

__bal_merge_steps_short() {
  local seq=$1
  local -a factors=(${=seq})
  if (( ${#factors[@]} == 0 )); then
    echo ""
    return
  fi
  local idx=1 factor short=()
  for factor in "${factors[@]}"; do
    short+=("Layer ${idx} place 1×${factor}→1")
    (( idx++ ))
  done
  echo "${(j:; :)short}"
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

__bal_gcd() {
  local a=$1 b=$2 tmp
  while (( b != 0 )); do
    tmp=$(( a % b ))
    a=$b
    b=$tmp
  done
  echo $(( a < 0 ? -a : a ))
}

__bal_lcm() {
  local a=$1 b=$2
  local gcd=$(__bal_gcd "$a" "$b")
  echo $(( a / gcd * b ))
}

__bal_priority_label() {
  local idx=$1
  if (( idx < 10 )); then
    printf "O%d" "$idx"
  else
    printf "%d" "$idx"
  fi
}

__bal_priority_chain() {
  local outputs=$1
  local -a labels=()
  local i=1
  while (( i <= outputs )); do
    labels+=("$(__bal_priority_label "$i")")
    (( i++ ))
  done
  echo "${(j:→:)labels}"
}

__bc_priority_lines() {
  local outputs=$1 budgets_str=$2
  local -a budgets=(${=budgets_str})
  local i=1 lanes label prev label_next lane_word
  while (( i <= outputs )); do
    lanes=${budgets[i]:-0}
    (( lanes < 0 )) && lanes=0
    label=$(__bal_priority_label "$i")
    if (( lanes == 1 )); then
      lane_word="lane"
    else
      lane_word="lanes"
    fi
    if (( outputs == 1 )); then
      printf "    %s – consumes %d %s; no overflow because this is the final output.\n" "$label" "$lanes" "$lane_word"
    elif (( i == 1 )); then
      label_next=$(__bal_priority_label "$(( i + 1 ))")
      printf "    %s – consumes the first %d %s from all inputs before overflowing to %s.\n" "$label" "$lanes" "$lane_word" "$label_next"
    elif (( i == outputs )); then
      printf "    %s – receives overflow from %s and absorbs the final %d %s.\n" "$label" "$(__bal_priority_label "$(( i - 1 ))")" "$lanes" "$lane_word"
    else
      prev=$(__bal_priority_label "$(( i - 1 ))")
      label_next=$(__bal_priority_label "$(( i + 1 ))")
      printf "    %s – consumes %d %s after %s, then overflows to %s once saturated.\n" "$label" "$lanes" "$lane_word" "$prev" "$label_next"
    fi
    (( i++ ))
  done
}

__bc_lane_budgets() {
  local lanes=$1 outputs=$2
  local remaining=$lanes remaining_outputs=$outputs
  local -a budgets=()
  local share
  while (( remaining_outputs > 0 )); do
    if (( remaining <= 0 )); then
      share=0
    else
      share=$(( (remaining + remaining_outputs - 1) / remaining_outputs ))
    fi
    budgets+=("$share")
    (( remaining -= share ))
    (( remaining_outputs-- ))
  done
  echo "${budgets[*]}"
}

__bc_plan_single_stack() {
  local lanes=$1
  local remaining=$lanes
  local -a entries=()
  while (( remaining > 1 )); do
    if (( remaining % 3 == 0 || remaining > 4 )); then
      entries+=("1:3")
      (( remaining -= 2 ))
    else
      entries+=("1:2")
      (( remaining -= 1 ))
    fi
  done
  printf "%s\n" "${entries[@]}"
}

__bc_plan_layers_for_budgets() {
  local budgets_str=$1
  local -a budgets=(${=budgets_str})
  local -a lines=()
  local plan budget
  for budget in "${budgets[@]}"; do
    if (( budget <= 1 )); then
      continue
    fi
    plan=$(__bc_plan_single_stack "$budget")
    if [[ -n "$plan" ]]; then
      lines+=("${(@f)plan}")
    fi
  done
  printf "%s\n" "${lines[@]}"
}

__bc_lane_budget_summary() {
  local budgets_str=$1
  local -a budgets=(${=budgets_str})
  if (( ${#budgets[@]} == 0 )); then
    echo ""
    return
  fi
  local -a parts=()
  local idx=1 total=0 lanes label
  for lanes in "${budgets[@]}"; do
    label=$(__bal_priority_label "$idx")
    parts+=("${label}=${lanes}")
    (( total += lanes ))
    (( idx++ ))
  done
  printf "Lane budget %s (total %d lanes)" "${(j:, :)parts}" "$total"
}

__bc_plan_merge_layers() {
  local inputs=$1 outputs=$2 budgets_str=$3
  local budgets="$budgets_str"
  if [[ -z "$budgets" ]]; then
    budgets=$(__bc_lane_budgets "$inputs" "$outputs")
  fi
  __bc_plan_layers_for_budgets "$budgets"
}

__bc_layers_summary() {
  local layers_str=$1
  local -a parts=("${(@f)layers_str}")
  if (( ${#parts[@]} == 0 )); then
    echo "Layers → (no mergers required)"
    return
  fi
  local summary="Layers → "
  local first=1
  local entry count arity
  for entry in "${parts[@]}"; do
    count=${entry%%:*}
    arity=${entry##*:}
    (( count == 0 )) && continue
    if (( ! first )); then
      summary+=", "
    else
      first=0
    fi
    summary+="${count}×${arity}→1"
  done
  if (( first )); then
    summary+="(no mergers required)"
  fi
  echo "$summary"
}

__bb_merge_counts_summary() {
  local layers_str=$1
  local -a parts=("${(@f)layers_str}")
  local total3=0 total2=0 entry count arity
  for entry in "${parts[@]}"; do
    count=${entry%%:*}
    arity=${entry##*:}
    if (( arity == 3 )); then
      (( total3 += count ))
    else
      (( total2 += count ))
    fi
  done
  printf "x%d of 3→1 mergers, x%d of 2→1 mergers (order doesn’t matter)" "$total3" "$total2"
}

__bc_do_lines() {
  local layers_str=$1 indent=${2:-"    "}
  local -a parts=("${(@f)layers_str}")
  local idx=1 entry count arity word total_in
  if (( ${#parts[@]} == 0 )); then
    printf "%sno merger layers required.\n" "$indent"
    return
  fi
  for entry in "${parts[@]}"; do
    count=${entry%%:*}
    arity=${entry##*:}
    (( count == 0 )) && continue
    word="merger"
    (( count != 1 )) && word+="s"
    total_in=$(( count * arity ))
    printf "%sLayer %d – place %d %s to combine %d lanes into %d belt" "$indent" "$idx" "$count" "$word" "$total_in" "$count"
    printf " (%d× %d→1)\n" "$count" "$arity"
    (( idx++ ))
  done
}

__bc_steps_short() {
  local layers_str=$1
  local -a parts=("${(@f)layers_str}")
  if (( ${#parts[@]} == 0 )); then
    echo "no merger layers"
    return
  fi
  local idx=1 entry count arity
  local -a lines=()
  for entry in "${parts[@]}"; do
    count=${entry%%:*}
    arity=${entry##*:}
    lines+=("Layer ${idx} place ${count}×${arity}→1")
    (( idx++ ))
  done
  echo "${(j:; :)lines}"
}

__bc_note_from_plan() {
  local layers_str=$1 label=$2
  local -a parts=("${(@f)layers_str}")
  if (( ${#parts[@]} == 0 )); then
    echo ""
    return
  fi
  local -a factors=()
  local -a counts=()
  local total=0 entry count arity
  for entry in "${parts[@]}"; do
    count=${entry%%:*}
    arity=${entry##*:}
    factors+=("$arity")
    counts+=("$count")
    (( total += count ))
  done
  local branch_expr="${(j:×:)factors}"
  local sum_expr="${(j: + :)counts}"
  printf "%s – Layer order %s (branch sequence) → total mergers per belt %s = %d" "$label" "$branch_expr" "$sum_expr" "$total"
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
  local inputs=$1 outputs=$2
  local descriptor="${inputs}:${outputs}"
  local headline="CLEAN → build 1→${outputs} (no loopback)"
  printf "%s | LOAD-BALANCER | %s\n" "$descriptor" "$headline"
  __bal_recipe_lines 0 0 "Recipe" "Split (single input)"
  return 0
}

__bal_handle_load_clean() {
  local inputs=$1 outputs=$2 count2=$3 count3=$4
  local descriptor="${inputs}:${outputs}"
  local headline="CLEAN → build 1→${outputs} (no loopback)"
  local prev=$(__bal_prev_clean "$outputs")
  printf "%s | LOAD-BALANCER | %s\n" "$descriptor" "$headline"
  __bal_recipe_lines "$count3" "$count2" "Recipe" "Split (single input)"
  if (( prev > 0 && prev < outputs )); then
    printf "Prev clean: 1:%d\n" "$prev"
  fi
  return 0
}

__bal_handle_load_dirty() {
  local inputs=$1 outputs=$2 leftover=$3 count2_clean=$4 count3_clean=$5
  local descriptor="${inputs}:${outputs}"
  local mode="LOAD-BALANCER"
  local headline="NOT clean (leftover ${leftover})"
  local next_clean=$(__bal_next_clean "$outputs")
  local loopback=$(( next_clean - outputs ))
  local prev=$(__bal_prev_clean "$outputs")
  local loop_word="outputs"
  (( loopback == 1 )) && loop_word="output"
  printf "%s | %s | %s\n" "$descriptor" "$mode" "$headline"
  printf "Next clean size: %d → build 1→%d\n" "$next_clean" "$next_clean"
  __bal_recipe_lines "$count3_clean" "$count2_clean" "Recipe" "Split (single input)"
  if (( prev > 0 )); then
    printf "Prev clean: 1:%d\n" "$prev"
  fi
  printf "Split loop back: %d %s (merge them, feed back to input)\n" "$loopback" "$loop_word"
  return 0
}

__bal_handle_nico_ratio() {
  local descriptor=$1
  shift
  local -a weights=("$@")
  local count=${#weights[@]}
  if (( count < 2 )); then
    echo "invalid Nico ratio: ${descriptor}" >&2
    return 2
  fi
  local weight
  for weight in "${weights[@]}"; do
    if ! __bal_is_positive_int "$weight"; then
      echo "invalid Nico ratio: ${descriptor}" >&2
      return 2
    fi
  done

  local denom=0
  for weight in "${weights[@]}"; do
    (( denom += weight ))
  done
  if (( denom == 0 )); then
    echo "invalid Nico ratio: ${descriptor}" >&2
    return 2
  fi

  local clean=$(__bal_next_clean "$denom")
  local loopback=$(( clean - denom ))
  local exp2 exp3 rem
  read exp2 exp3 rem <<< "$(__bal_exponents23 "$clean")"
  local count2=$exp2
  local count3=$exp3

  local ratio_text="${(j/:/)weights}"
  printf "%s | NICO | split 1 input into outputs with ratio %s (clean 1→%d)\n" "$descriptor" "$ratio_text" "$clean"
  __bal_recipe_lines "$count3" "$count2" "Recipe" "Split (single input)"

  echo "  Allocation (ratio ${ratio_text}):"
  local idx=1 start=1 end lane_word range_text
  local -a range_starts=() range_ends=()
  for weight in "${weights[@]}"; do
    end=$(( start + weight - 1 ))
    range_starts+=($start)
    range_ends+=($end)
    lane_word="lanes"
    local positions_label="positions"
    if (( weight == 1 )); then
      lane_word="lane"
      positions_label="position"
    fi
    if (( start == end )); then
      range_text="lane ${start}"
    else
      range_text="lanes ${start}-${end}"
    fi
    printf "    Group %d takes %d %s (%s)\n" "$idx" "$weight" "$lane_word" "$range_text"
    (( idx++ ))
    start=$(( end + 1 ))
  done

  printf "Ratio denominator: %d lanes; clean size: %d.\n" "$denom" "$clean"
  if (( loopback > 0 )); then
    local loop_word="lanes"
    (( loopback == 1 )) && loop_word="lane"
    local loop_start=$(( denom + 1 ))
    local loop_end=$clean
    local loop_range
    if (( loop_start == loop_end )); then
      loop_range="lane ${loop_start}"
    else
      loop_range="lanes ${loop_start}-${loop_end}"
    fi

    local attr_idx=1 attr_weight=${weights[1]}
    local i=1
    while (( i <= count )); do
      local current_weight=${weights[$i]}
      if (( current_weight < attr_weight )); then
        attr_weight=$current_weight
        attr_idx=$i
      fi
      (( i++ ))
    done

    local attr_start=${range_starts[$attr_idx]}
    local attr_end=${range_ends[$attr_idx]}
    local attr_range
    if (( attr_start == attr_end )); then
      attr_range="lane ${attr_start}"
    else
      attr_range="lanes ${attr_start}-${attr_end}"
    fi

    printf "Split loop back: %d %s (route overflow via Group %d’s lane stack; unused %s feed back to input)\n" \
      "$loopback" "$loop_word" "$attr_idx" "$loop_range"
  fi
}

__bal_handle_load_ratio() {
  local inputs=$1 outputs=$2
  if (( outputs == 1 )); then
    __bal_handle_trivial_load "$inputs" "$outputs"
    return $?
  fi
  local a=0 b=0 r=0
  read a b r <<< "$(__bal_exponents23 "$outputs")"
  if (( r == 1 )); then
    __bal_handle_load_clean "$inputs" "$outputs" "$a" "$b"
  else
    local am=0 bm=0 rr=0
    local next_clean=$(__bal_next_clean "$outputs")
    read am bm rr <<< "$(__bal_exponents23 "$next_clean")"
    __bal_handle_load_dirty "$inputs" "$outputs" "$r" "$am" "$bm"
  fi
}

__bal_handle_balancer_ratio() {
  local inputs=$1 outputs=$2
  local descriptor="${inputs}:${outputs}"
  local headline="evenly mix ${inputs} inputs across ${outputs} outputs"
  local split_target=$outputs

  local split_clean=$(__bal_next_clean "$split_target")
  local split_loop=$(( split_clean - split_target ))
  local split_a split_b split_r
  read split_a split_b split_r <<< "$(__bal_exponents23 "$split_clean")"
  local split_count3=$split_b
  local split_count2=$split_a

  local active_per_input=$(( split_clean - split_loop ))
  local active_total=$(( inputs * active_per_input ))
  if (( active_total % outputs != 0 )); then
    echo "belt-balancer: lane mismatch for $descriptor" >&2
    return 1
  fi
  local lanes_per_output=$(( active_total / outputs ))
  local merge_clean=$(__bal_next_clean "$lanes_per_output")
  local merge_pad=$(( merge_clean - lanes_per_output ))
  local merge_a merge_b merge_r
  read merge_a merge_b merge_r <<< "$(__bal_exponents23 "$merge_clean")"
  local merge_count2=$merge_a
  local merge_count3=$merge_b
  __bal_best_sequence "$merge_count3" "$merge_count2"
  local merge_seq=$__bal_plan_best_seq

  printf "%s | BELT-BALANCER | %s\n" "$descriptor" "$headline"
  local split_summary_full=$(__bal_recipe_summary "$split_count3" "$split_count2" "Split recipe" "split")
  local split_summary=${split_summary_full#Split recipe: }
  local merge_summary_full=$(__bal_recipe_summary "$merge_count3" "$merge_count2" "Merge recipe" "merge")
  local merge_summary=${merge_summary_full#Merge recipe: }
  printf "Split & Merge recipe: %s | %s.\n" "$split_summary" "$merge_summary"

  local sep=$'\x1F'
  local split_blob=$(__bal_split_lines_and_note "$split_count3" "$split_count2")
  local split_text=${split_blob%$sep*}
  local split_note_raw=${split_blob##*$sep}

  echo "  Split (per input):"
  if [[ -z "$split_text" ]]; then
    printf "    no split layers required.\n"
  else
    printf "    %s\n" "${(@f)split_text}"
  fi

  echo "  Merge (per output):"
  local merge_lines=$(__bal_merge_steps_lines "$merge_seq")
  if [[ -z "$merge_lines" ]]; then
    printf "    no merge layers required.\n"
  else
    printf "    %s\n" "${(@f)merge_lines}"
  fi

  local split_note=""
  if [[ -n "$split_note_raw" && "$split_text" != "no split layers required." ]]; then
    split_note="per input – ${split_note_raw}"
  fi
  local -a merge_factors=(${=merge_seq})
  local merge_note_raw=""
  if (( ${#merge_factors[@]} > 0 )); then
    local branch_expr="${(j:×:)merge_factors}"
    local merges_total=${#merge_factors[@]}
    merge_note_raw="per output – Layer order ${branch_expr} (branch sequence) → total mergers per belt ${merges_total}"
  fi
  local combined_note=""
  if [[ -n "$split_note" ]]; then
    combined_note="$split_note"
  fi
  if [[ -n "$merge_note_raw" ]]; then
    [[ -n "$combined_note" ]] && combined_note+=" | "
    combined_note+="$merge_note_raw"
  fi
  if [[ -n "$combined_note" ]]; then
    printf "  Note: %s.\n" "$combined_note"
  fi

  if (( split_loop > 0 )); then
    local loop_word="outputs"
    (( split_loop == 1 )) && loop_word="output"
    printf "Split loop back: %d %s per input\n" "$split_loop" "$loop_word"
  fi
  if (( merge_pad > 0 )); then
    local pad_word="dummy lanes"
    (( merge_pad == 1 )) && pad_word="dummy lane"
    printf "Merge pad: %d %s per output\n" "$merge_pad" "$pad_word"
  fi
  return 0
}

__bal_handle_compressor_ratio() {
  local inputs=$1 outputs=$2
  local descriptor="${inputs}:${outputs}"
  local headline="compress ${inputs} into ${outputs} (pack-first)"
  local priority_seq=$(__bal_priority_chain "$outputs")
  local budgets_str=$(__bc_lane_budgets "$inputs" "$outputs")
  local layers_str=$(__bc_plan_merge_layers "$inputs" "$outputs" "$budgets_str")
  local recipe_line=$(__bc_layers_summary "$layers_str")
  recipe_line+=" (order doesn’t matter)"
  local lane_note=$(__bc_lane_budget_summary "$budgets_str")

  printf "%s | BELT-COMPRESSOR | %s\n" "$descriptor" "$headline"
  printf "Merge recipe: %s\n" "$recipe_line"
  if (( outputs == 1 )); then
    echo "  Merge (single output O1):"
    printf "    Do: merge all %d input belts down into one belt so O1 receives the full flow.\n" "$inputs"
    if [[ -n "$lane_note" ]]; then
      printf "Note: Only one output, so all capacity lives on O1. %s.\n" "$lane_note"
    else
      echo "Note: Only one output, so all capacity lives on O1."
    fi
    return 0
  fi
  echo "  Do:"
  __bc_do_lines "$layers_str"
  echo "  Priority:"
  __bc_priority_lines "$outputs" "$budgets_str"
  if [[ -n "$lane_note" ]]; then
    printf "Note: Priority %s. %s. Keep mergers compact so higher-priority outputs fill completely before passing overflow onward.\n" "$priority_seq" "$lane_note"
  else
    printf "Note: Priority %s. Keep mergers compact so higher-priority outputs fill completely before passing overflow onward.\n" "$priority_seq"
  fi
  return 0
}

__bal_process_ratio() {
  local token=$1
  local -a parts=("${(@s/:/)token}")
  if (( ${#parts[@]} >= 3 )); then
    local first=${parts[1]}
    if __bal_is_positive_int "$first" && (( first == 1 )); then
      local -a weights=("${parts[@]:1}")
      __bal_handle_nico_ratio "$token" "${weights[@]}"
      return $?
    fi
  fi
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
      __bal_handle_load_ratio "$inputs" "$outputs"
      ;;
    balancer)
      __bal_handle_balancer_ratio "$inputs" "$outputs"
      ;;
    compressor)
      __bal_handle_compressor_ratio "$inputs" "$outputs"
      ;;
  esac
}

__bal_main() {
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

  local had_error=0 target rc
  for target in "${args[@]}"; do
    __bal_process_ratio "$target"
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
