#!/usr/bin/env zsh
# Satisfactory load-balancer helper — pure CLI (zsh)
# Modes:
#   LOAD-BALANCER → 1 input spread across n outputs (1→n)
#   BELT-BALANCER → n inputs evenly mixed across m outputs (n>1, m≥n)
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
  • Normal ratios automatically detect LOAD-BALANCER, BELT-BALANCER, or COMPRESSOR mode.
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

__bal_quiet_clean_line() {
  local inputs=$1 outputs=$2 count3=$3 count2=$4 prev=$5
  local recipe=$(__bal_recipe_summary "$count3" "$count2")
  local fields=("${inputs}:${outputs}" "LOAD-BALANCER" "CLEAN → build 1→$outputs (no loopback)" "$recipe")
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
  local fields=("$descriptor" "LOAD-BALANCER" "NOT clean (leftover $leftover)" "build 1→$next" "$loop_text" "$recipe")
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
      local noun="splitter"
      local plural="splitters"
      if [[ $mode == "merge" ]]; then
        noun="merger"
        plural="mergers"
      fi
      (( total_nodes == 1 )) && plural="$noun"
      echo "  Note: Layer order ${factor_expr} (branch sequence) → total ${plural} ${sum_expr} = ${total_nodes}."
    fi
  fi
}

__bal_stage_steps_short() {
  local mode=$1 count3=$2 count2=$3
  local step_lines
  if [[ $mode == "merge" ]]; then
    step_lines=$(__bal_merge_build_steps "$count3" "$count2")
  else
    step_lines=$(__bal_build_steps "$count3" "$count2")
  fi
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

__bal_stage_lines_and_note() {
  local mode=$1 count3=$2 count2=$3
  local builder="__bal_build_steps"
  local noun="splitter" noun_plural="splitters"
  if [[ $mode == "merge" ]]; then
    builder="__bal_merge_build_steps"
    noun="merger"
    noun_plural="mergers"
  fi
  local step_lines=$($builder "$count3" "$count2")
  local lines_text=""
  local note=""
  if [[ -z "$step_lines" ]]; then
    lines_text="no ${mode} layers required."
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
      local noun_phrase=$noun_plural
      (( total_nodes == 1 )) && noun_phrase=$noun
      note="Layer order ${factor_expr} (branch sequence) → total ${noun_phrase} ${sum_expr} = ${total_nodes}"
    fi
  fi
  printf '%s\x1F%s\n' "$lines_text" "$note"
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

__bal_priority_chain() {
  local outputs=$1
  if (( outputs <= 6 )); then
    local -a labels=()
    local i=1
    while (( i <= outputs )); do
      labels+=("O${i}")
      (( i++ ))
    done
    echo "${(j:→:)labels}"
  else
    echo "O1→O2→...→O${outputs}"
  fi
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
  printf "%s | LOAD-BALANCER | %s\n" "$descriptor" "$headline"
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
  printf "%s | LOAD-BALANCER | %s\n" "$descriptor" "$headline"
  __bal_recipe_lines "$count3" "$count2"
  if (( prev > 0 && prev < outputs )); then
    printf "Prev clean: 1:%d\n" "$prev"
  fi
  return 0
}

__bal_handle_load_dirty() {
  local inputs=$1 outputs=$2 quiet=$3 leftover=$4 count2_clean=$5 count3_clean=$6
  local descriptor="${inputs}:${outputs}"
  local mode="LOAD-BALANCER"
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
  local inputs=$1 outputs=$2 quiet=$3
  local descriptor="${inputs}:${outputs}"
  local headline="evenly mix ${inputs} inputs across ${outputs} outputs"
  local split_target=$outputs
  local merge_target=$inputs

  local split_clean=$(__bal_next_clean "$split_target")
  local split_loop=$(( split_clean - split_target ))
  local split_a split_b split_r
  read split_a split_b split_r <<< "$(__bal_exponents23 "$split_clean")"
  local split_count3=$split_b
  local split_count2=$split_a

  local merge_clean=$(__bal_next_clean "$merge_target")
  local merge_pad=$(( merge_clean - merge_target ))
  local merge_a merge_b merge_r
  read merge_a merge_b merge_r <<< "$(__bal_exponents23 "$merge_clean")"
  local merge_count3=$merge_b
  local merge_count2=$merge_a

  if (( quiet )); then
    local -a fields=("$descriptor" "BELT-BALANCER" "$headline")
    if (( split_loop > 0 )); then
      local loop_label="outputs"
      (( split_loop == 1 )) && loop_label="output"
      fields+=("Split loop back: ${split_loop} ${loop_label} per input")
    fi
    if (( merge_pad > 0 )); then
      local pad_label="dummy lanes"
      (( merge_pad == 1 )) && pad_label="dummy lane"
      fields+=("Merge pad: ${merge_pad} ${pad_label} per output")
    fi
    local split_summary=$(__bal_recipe_summary "$split_count3" "$split_count2" "Split recipe" "split")
    fields+=("$split_summary")
    local split_steps=$(__bal_stage_steps_short "split" "$split_count3" "$split_count2")
    if [[ -n "$split_steps" ]]; then
      fields+=("Split steps: $split_steps")
    fi
    local merge_summary=$(__bal_recipe_summary "$merge_count3" "$merge_count2" "Merge recipe" "merge")
    fields+=("$merge_summary")
    local merge_steps=$(__bal_stage_steps_short "merge" "$merge_count3" "$merge_count2")
    if [[ -n "$merge_steps" ]]; then
      fields+=("Merge steps: $merge_steps")
    fi
    __bal_join_fields "${fields[@]}"
    return 0
  fi

  printf "%s | BELT-BALANCER | %s\n" "$descriptor" "$headline"
  local split_summary_full=$(__bal_recipe_summary "$split_count3" "$split_count2" "Split recipe" "split")
  local merge_summary_full=$(__bal_recipe_summary "$merge_count3" "$merge_count2" "Merge recipe" "merge")
  local split_summary=${split_summary_full#Split recipe: }
  local merge_summary=${merge_summary_full#Merge recipe: }
  printf "Split & Merge recipe: %s | %s.\n" "$split_summary" "$merge_summary"

  local sep=$'\x1F'
  local split_blob=$(__bal_stage_lines_and_note "split" "$split_count3" "$split_count2")
  local split_text=${split_blob%$sep*}
  local split_note_raw=${split_blob##*$sep}
  local merge_blob=$(__bal_stage_lines_and_note "merge" "$merge_count3" "$merge_count2")
  local merge_text=${merge_blob%$sep*}
  local merge_note_raw=${merge_blob##*$sep}

  local -a split_lines merge_lines
  if [[ -n "$split_text" ]]; then
    split_lines=("${(@f)split_text}")
  else
    split_lines=()
  fi
  if [[ -n "$merge_text" ]]; then
    merge_lines=("${(@f)merge_text}")
  else
    merge_lines=()
  fi

  echo "  Split & Merge (per input):"
  local line
  if (( ${#split_lines[@]} == 0 )); then
    printf "    no split layers required.\n"
  else
    for line in "${split_lines[@]}"; do
      printf "    %s\n" "$line"
    done
  fi

  echo "  Split & Merge (per output):"
  if (( ${#merge_lines[@]} == 0 )); then
    printf "    no merge layers required.\n"
  else
    for line in "${merge_lines[@]}"; do
      printf "    %s\n" "$line"
    done
  fi

  local split_note="" merge_note=""
  if [[ -n "$split_note_raw" && ( ${#split_lines[@]} == 0 || "$split_lines[1]" != "no split layers required." ) ]]; then
    split_note="per input – ${split_note_raw}"
  fi
  if [[ -n "$merge_note_raw" && ( ${#merge_lines[@]} == 0 || "$merge_lines[1]" != "no merge layers required." ) ]]; then
    merge_note="per output – ${merge_note_raw}"
  fi
  local combined_note=""
  if [[ -n "$split_note" ]]; then
    combined_note="$split_note"
  fi
  if [[ -n "$merge_note" ]]; then
    [[ -n "$combined_note" ]] && combined_note+=" | "
    combined_note+="$merge_note"
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
  local inputs=$1 outputs=$2 quiet=$3
  local descriptor="${inputs}:${outputs}"
  local headline="compress ${inputs} into ${outputs} (pack-first)"
  local priority_seq=$(__bal_priority_chain "$outputs")
  local recipe_line="Merge recipe: use 3→1 and 2→1 mergers in short priority stacks (order doesn’t matter)"

  if (( quiet )); then
    local guide="Guide: build a priority chain so overflow cascades ${priority_seq}."
    local -a fields=("$descriptor" "COMPRESSOR" "$headline" "Priority: ${priority_seq}" "$recipe_line" "$guide")
    __bal_join_fields "${fields[@]}"
    return 0
  fi

  printf "%s | COMPRESSOR | %s\n" "$descriptor" "$headline"
  echo "$recipe_line"
  if (( outputs == 1 )); then
    echo "  Merge (single output O1):"
    printf "    Do: merge all %d input belts down into one belt so O1 receives the full flow.\n" "$inputs"
    echo "Note: Only one output, so all capacity lives on O1."
    return 0
  fi

  echo "  Merge (per output):"
  printf "    O1: build a compact merger stack so all %d inputs converge on O1 first.\n" "$inputs"
  if (( outputs == 2 )); then
    echo "    O2: capture overflow from O1 with another short merger stack so it fills after O1."
  else
    printf "    O2...O%d: daisy-chain overflow from the previous output so each fills only after the earlier ones are saturated.\n" "$outputs"
  fi
  echo "Note: Priority ${priority_seq}. Keep mergers compact so higher-priority outputs fill completely before passing overflow onward."
  return 0
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
      __bal_handle_balancer_ratio "$inputs" "$outputs" "$quiet"
      ;;
    compressor)
      __bal_handle_compressor_ratio "$inputs" "$outputs" "$quiet"
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
