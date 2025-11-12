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

__bal_quiet_clean_line() {
  local n=$1 count3=$2 count2=$3 prev=$4
  local fields=("N=$n" "CLEAN" "build 1→$n (no loopback)" "Recipe ${count3}×(1→3), ${count2}×(1→2)")
  if (( prev > 0 && prev < n )); then
    fields+=("Prev clean $prev")
  fi
  __bal_join_fields "${fields[@]}"
}

__bal_quiet_dirty_line() {
  local n=$1 leftover=$2 next=$3 loopback=$4 count3=$5 count2=$6 prev=$7
  local fields=("N=$n" "NOT clean" "build 1→$next" "loop back $loopback output")
  (( loopback != 1 )) && fields[-1]="loop back $loopback outputs"
  fields+=("Recipe ${count3}×(1→3), ${count2}×(1→2)")
  if (( prev > 0 )); then
    fields+=("Prev clean $prev")
  fi
  __bal_join_fields "${fields[@]}"
}

__bal_recipe_lines() {
  local count3=$1 count2=$2
  echo "Recipe: x${count3} of 1→3 splitters, x${count2} of 1→2 splitters (order doesn’t matter)"
  local word3="times"
  local word2="times"
  (( count3 == 1 )) && word3="time"
  (( count2 == 1 )) && word2="time"
  echo "  Do: split by 3, ${count3} ${word3}; then split each branch by 2, ${count2} ${word2}."
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
      printf "Next clean size: %s  → build 1→%s\n" "$m" "$m"
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
