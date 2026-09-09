#!/usr/bin/env zsh

# Keep a caller-provided empty or custom array across plugin reloads.
if (( ! ${+CODEX_PROFILES_FLAGS} )); then
  typeset -ga CODEX_PROFILES_FLAGS
  CODEX_PROFILES_FLAGS=(--yolo --search)
fi

function _codex_profiles_help() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  print -r -- 'Usage:
  cxl | codex-profiles [list]      List available profiles.
  cx [profile] [Codex args...]     Start a new session.
  cxr [profile] [Codex args...]    Open the session resume picker.
  cxlast [profile] [Codex args...] Resume the latest session (--last).

Profile selection:
  Omit the profile for a numbered picker; type its number without Enter.
  There is no profile limit. Type all displayed digits (01, 02... for 10+).
  Backspace edits; q, Esc, Enter or Ctrl-D cancels; Ctrl-C exits with 130.
  Press Tab to complete profile names. A picker requires terminal stdin.
  -p NAME, --profile NAME, or --profile=NAME may replace the first profile.
  Options first (such as cxr --last) pick a profile and forward those options.

Common Codex arguments after the profile:
  --last              Resume the latest session without the session picker.
  --all               Include sessions from every directory.
  --include-non-interactive  Include non-interactive sessions when resuming.
  --cd DIR            Use a different working directory.
  --model NAME        Override the profile model for this launch.
  -c KEY=VALUE        Override a Codex configuration value.
  SESSION_ID          Resume a specific session with cxr.
  "PROMPT"            Supply an initial prompt to cx.

Examples (replace work with a profile name shown by cxl):
  cx work "review this repository"
  cxr work --last
  cxlast work

All helpers accept standalone help, -h or --help. For a profile named help,
use cx --profile help. For full Codex options, run codex resume --help.

Configuration:
  CODEX_HOME           Profile directory (default: $HOME/.codex).
                       Relative paths resolve from the current directory.
  CODEX_PROFILES_BIN   One executable name/path (default: codex on PATH).
  CODEX_PROFILES_FLAGS Zsh array (default: --yolo --search).
                       Set CODEX_PROFILES_FLAGS=() to use no extra flags.'
}

function _codex_profiles_discover() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  # reply is dynamically scoped by callers so this helper returns an array
  # without writing names to stdout.
  reply=()

  local CODEX_PROFILES_HOME
  local CODEX_PROFILES_FILE
  local CODEX_PROFILES_BASENAME
  local CODEX_PROFILES_NAME
  local REPLY

  _codex_profiles_resolve_home || return $?
  CODEX_PROFILES_HOME="$REPLY"
  if [[ ! -e "$CODEX_PROFILES_HOME" ]]; then
    print -u 2 -r -- "codex-profiles: CODEX_HOME does not exist: $CODEX_PROFILES_HOME"
    return 1
  fi
  if [[ ! -d "$CODEX_PROFILES_HOME" ]]; then
    print -u 2 -r -- "codex-profiles: CODEX_HOME is not a directory: $CODEX_PROFILES_HOME"
    return 1
  fi
  if [[ ! -r "$CODEX_PROFILES_HOME" || ! -x "$CODEX_PROFILES_HOME" ]]; then
    print -u 2 -r -- "codex-profiles: CODEX_HOME is not readable: $CODEX_PROFILES_HOME"
    return 1
  fi

  # The CLI accepts standalone names made from letters, numbers, hyphens, and
  # underscores.  A glob with (N) stays safe for an empty directory, while
  # -f/-r follow valid symlinks and reject directories, pipes, and broken links.
  for CODEX_PROFILES_FILE in "$CODEX_PROFILES_HOME"/*.config.toml(N); do
    [[ -f "$CODEX_PROFILES_FILE" && -r "$CODEX_PROFILES_FILE" ]] || continue
    CODEX_PROFILES_BASENAME="${CODEX_PROFILES_FILE:t}"
    [[ "$CODEX_PROFILES_BASENAME" == *.config.toml ]] || continue
    CODEX_PROFILES_NAME="${CODEX_PROFILES_BASENAME%.config.toml}"
    [[ -n "$CODEX_PROFILES_NAME" && "$CODEX_PROFILES_NAME" != *[^A-Za-z0-9_-]* ]] || continue
    reply+=("$CODEX_PROFILES_NAME")
  done

  # zsh glob order is normally sorted; sort the array explicitly so callers
  # get stable menus even if a caller has unusual glob-order options.
  reply=("${(@o)reply}")
  return 0
}

function _codex_profiles_resolve_home() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  local CODEX_PROFILES_REQUESTED_HOME
  if (( ${+CODEX_HOME} )) && [[ -n "$CODEX_HOME" ]]; then
    CODEX_PROFILES_REQUESTED_HOME="$CODEX_HOME"
    # Resolve relative CODEX_HOME from this shell's current directory.  The
    # execute path supplies this same absolute value to a child so --cd cannot
    # make discovery and native loading disagree.
    REPLY="${CODEX_PROFILES_REQUESTED_HOME:A}"
  else
    if [[ -z "${HOME:-}" ]]; then
      print -u 2 -r -- 'codex-profiles: HOME is unset; set CODEX_HOME to a profile directory.'
      return 1
    fi
    REPLY="$HOME/.codex"
  fi
  return 0
}

# A subshell body lets the signal handler exit with an exact status without
# exiting the caller, including when this private helper is invoked directly.
function _codex_profiles_pick() (
  emulate -L zsh
  setopt localoptions localtraps no_shwordsplit no_ksharrays no_globsubst

  local -a CODEX_PROFILES_NAMES
  local -a CODEX_PROFILES_CODES
  CODEX_PROFILES_NAMES=("$@")
  local CODEX_PROFILES_SELECTION=''
  local CODEX_PROFILES_KEY
  local CODEX_PROFILES_CODE
  local CODEX_PROFILES_NAME
  local CODEX_PROFILES_TERMINAL
  local -i CODEX_PROFILES_INDEX=1
  local -i CODEX_PROFILES_COUNT=${#CODEX_PROFILES_NAMES[@]}
  local -i CODEX_PROFILES_WIDTH=${#CODEX_PROFILES_COUNT}

  if (( ${#CODEX_PROFILES_NAMES[@]} == 0 )); then
    print -u 2 -r -- 'codex-profiles: no valid standalone profiles were found.'
    return 1
  fi

  # Read only from an actual stdin TTY.  This avoids blocking pipelines or
  # scripts that have no interactive input; callers can pass a profile.
  if [[ ! -t 0 ]]; then
    print -u 2 -r -- 'codex-profiles: profile picker requires a TTY; pass a profile explicitly.'
    return 1
  fi

  # Use the system stty: third-party implementations may not round-trip the
  # host's terminal state correctly. Keep Ctrl-C as a key while reading so it
  # cancels this picker without signalling the surrounding interactive shell.
  CODEX_PROFILES_TERMINAL="$(command -p stty -g <&0)" || return 1
  # Returning from a signal trap inside command substitution can lose its
  # status in Zsh. Restore explicitly before exiting this isolated picker;
  # `always` handles ordinary returns but does not run after `exit`.
  trap '
    command -p stty "$CODEX_PROFILES_TERMINAL" <&0
    print -u 2
    print -u 2 -r -- "codex-profiles: profile selection cancelled."
    exit 130
  ' INT
  {
    command -p stty -icanon -echo -isig min 1 time 0 <&0 || return 1

    print -u 2 -r -- 'Select a Codex profile:'
    for CODEX_PROFILES_NAME in "${CODEX_PROFILES_NAMES[@]}"; do
      # Fixed-width labels make immediate selection unambiguous at any count:
      # 1..9, 01..99, 001..999, and so on. No profiles are omitted or capped.
      builtin printf -v CODEX_PROFILES_CODE '%0*d' "$CODEX_PROFILES_WIDTH" "$CODEX_PROFILES_INDEX"
      CODEX_PROFILES_CODES+=("$CODEX_PROFILES_CODE")
      print -u 2 -r -- "$CODEX_PROFILES_CODE) $CODEX_PROFILES_NAME"
      (( CODEX_PROFILES_INDEX++ ))
    done
    print -u 2 -r -- 'Type a listed number (no Enter; q, Esc, Enter or Ctrl-C cancels):'

    while true; do
      if ! IFS= read -r -k 1 -u 0 CODEX_PROFILES_KEY; then
        print -u 2 -r -- $'\ncodex-profiles: profile selection cancelled.'
        return 1
      fi

      case "$CODEX_PROFILES_KEY" in
        $'\x03')
          print -u 2 -r -- $'\ncodex-profiles: profile selection cancelled.'
          return 130
          ;;
        q|Q|$'\e'|$'\n'|$'\r'|$'\x04')
          print -u 2 -r -- $'\ncodex-profiles: profile selection cancelled.'
          return 1
          ;;
        $'\x7f'|$'\b')
          if [[ -n "$CODEX_PROFILES_SELECTION" ]]; then
            CODEX_PROFILES_SELECTION="${CODEX_PROFILES_SELECTION%?}"
            print -u 2 -n -- $'\b \b'
          fi
          continue
          ;;
        [0-9])
          CODEX_PROFILES_SELECTION+="$CODEX_PROFILES_KEY"
          print -u 2 -rn -- "$CODEX_PROFILES_KEY"
          (( ${#CODEX_PROFILES_SELECTION} < CODEX_PROFILES_WIDTH )) && continue

          # Compare strings, never evaluate user input as shell arithmetic.
          for (( CODEX_PROFILES_INDEX=1; CODEX_PROFILES_INDEX<=CODEX_PROFILES_COUNT; CODEX_PROFILES_INDEX++ )); do
            if [[ "$CODEX_PROFILES_SELECTION" == "${CODEX_PROFILES_CODES[CODEX_PROFILES_INDEX]}" ]]; then
              print -u 2
              print -r -- "${CODEX_PROFILES_NAMES[CODEX_PROFILES_INDEX]}"
              return 0
            fi
          done
          ;;
      esac

      CODEX_PROFILES_SELECTION=''
      print -u 2 -r -- $'\ncodex-profiles: invalid profile selection; type a listed number (no Enter):'
    done
  } always {
    # Zsh's single-key read alone can leave the terminal changed after a
    # signal. Restore on selection, cancellation and read failure; the SIGINT
    # handler restores before exiting the isolated picker above.
    if ! command -p stty "$CODEX_PROFILES_TERMINAL" <&0; then
      print -u 2 -r -- 'codex-profiles: could not restore terminal settings.'
      # A return in `always` cannot replace a pending return from the try
      # block. Exit this subshell so a failed restore cannot launch Codex.
      exit 1
    fi
  }
)

function _codex_profiles_resolve_bin() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  local CODEX_PROFILES_REQUESTED
  local CODEX_PROFILES_RESOLVED

  if (( ${+CODEX_PROFILES_BIN} )); then
    CODEX_PROFILES_REQUESTED="$CODEX_PROFILES_BIN"
    if [[ -z "$CODEX_PROFILES_REQUESTED" ]]; then
      print -u 2 -r -- 'codex-profiles: CODEX_PROFILES_BIN is empty.'
      return 1
    fi
  else
    CODEX_PROFILES_REQUESTED='codex'
  fi

  if [[ "$CODEX_PROFILES_REQUESTED" == */* ]]; then
    CODEX_PROFILES_RESOLVED="$CODEX_PROFILES_REQUESTED"
  else
    CODEX_PROFILES_RESOLVED="$(whence -p "$CODEX_PROFILES_REQUESTED" 2>/dev/null)"
  fi
  if [[ -z "$CODEX_PROFILES_RESOLVED" || ! -f "$CODEX_PROFILES_RESOLVED" || ! -x "$CODEX_PROFILES_RESOLVED" ]]; then
    print -u 2 -r -- "codex-profiles: executable not found: $CODEX_PROFILES_REQUESTED"
    return 1
  fi

  REPLY="$CODEX_PROFILES_RESOLVED"
  return 0
}

function _codex_profiles_execute() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  local CODEX_PROFILES_ACTION="$1"
  shift
  local -a reply
  local -a CODEX_PROFILES_NAMES
  local -a CODEX_PROFILES_ARGV
  local CODEX_PROFILES_SELECTED
  local CODEX_PROFILES_NAME
  local REPLY
  local CODEX_PROFILES_HOME

  _codex_profiles_discover || return $?
  CODEX_PROFILES_NAMES=("${reply[@]}")
  if (( ${#CODEX_PROFILES_NAMES[@]} == 0 )); then
    print -u 2 -r -- 'codex-profiles: no valid standalone profiles were found.'
    return 1
  fi
  _codex_profiles_resolve_home || return $?
  CODEX_PROFILES_HOME="$REPLY"

  if (( $# == 0 )); then
    CODEX_PROFILES_SELECTED="$(_codex_profiles_pick "${CODEX_PROFILES_NAMES[@]}")" || return $?
  elif [[ "$1" == -p || "$1" == --profile || "$1" == --profile=* ]]; then
    # This is the escape hatch for a profile named "help", which is otherwise
    # reserved for standalone helper usage text.
    if [[ "$1" == --profile=* ]]; then
      CODEX_PROFILES_SELECTED="${1#--profile=}"
      shift
    else
      if (( $# < 2 )); then
        print -u 2 -r -- 'codex-profiles: -p/--profile requires a profile name. Run cx help for usage.'
        return 2
      fi
      CODEX_PROFILES_SELECTED="$2"
      shift 2
    fi
    CODEX_PROFILES_NAME=''
    for CODEX_PROFILES_NAME in "${CODEX_PROFILES_NAMES[@]}"; do
      [[ "$CODEX_PROFILES_NAME" == "$CODEX_PROFILES_SELECTED" ]] && break
    done
    if [[ "$CODEX_PROFILES_NAME" != "$CODEX_PROFILES_SELECTED" ]]; then
      print -u 2 -r -- "codex-profiles: unknown profile: $CODEX_PROFILES_SELECTED"
      return 2
    fi
  else
    CODEX_PROFILES_SELECTED="$1"
    CODEX_PROFILES_NAME=''
    for CODEX_PROFILES_NAME in "${CODEX_PROFILES_NAMES[@]}"; do
      [[ "$CODEX_PROFILES_NAME" == "$CODEX_PROFILES_SELECTED" ]] && break
    done
    if [[ "$CODEX_PROFILES_NAME" == "$CODEX_PROFILES_SELECTED" ]]; then
      shift
    elif [[ "$1" == -* ]]; then
      CODEX_PROFILES_SELECTED="$(_codex_profiles_pick "${CODEX_PROFILES_NAMES[@]}")" || return $?
    else
      print -u 2 -r -- "codex-profiles: unknown profile: $1"
      print -u 2 -r -- 'Pass a discovered profile name, or put Codex options first to use the picker.'
      return 2
    fi
  fi

  if [[ "${(t)CODEX_PROFILES_FLAGS}" != *array* ]]; then
    print -u 2 -r -- 'codex-profiles: CODEX_PROFILES_FLAGS must be a Zsh array, for example (--search) or ().'
    return 2
  fi
  _codex_profiles_resolve_bin || return $?
  CODEX_PROFILES_ARGV=("$REPLY")
  if [[ "$CODEX_PROFILES_ACTION" == resume || "$CODEX_PROFILES_ACTION" == resume-last ]]; then
    CODEX_PROFILES_ARGV+=(resume)
  fi
  CODEX_PROFILES_ARGV+=("${CODEX_PROFILES_FLAGS[@]}")
  # Use one --profile= argument for leading-hyphen names; the native CLI also
  # accepts the conventional -p NAME form for ordinary names.
  if [[ "$CODEX_PROFILES_SELECTED" == -* ]]; then
    CODEX_PROFILES_ARGV+=("--profile=$CODEX_PROFILES_SELECTED")
  else
    CODEX_PROFILES_ARGV+=(-p "$CODEX_PROFILES_SELECTED")
  fi
  if [[ "$CODEX_PROFILES_ACTION" == resume-last ]]; then
    CODEX_PROFILES_ARGV+=(--last)
  fi
  CODEX_PROFILES_ARGV+=("$@")

  # Always pass the resolved home: CODEX_HOME may be set in this shell but not
  # exported, and a relative value must remain anchored to this CWD for --cd.
  CODEX_HOME="$CODEX_PROFILES_HOME" "${CODEX_PROFILES_ARGV[@]}"
  return $?
}

function codex-profiles() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  if (( $# == 1 )) && [[ "$1" == -h || "$1" == --help || "$1" == help ]]; then
    _codex_profiles_help
    return 0
  fi
  if (( $# > 1 )) || { (( $# == 1 )) && [[ "$1" != list ]]; }; then
    print -u 2 -r -- 'Usage: codex-profiles [list]'
    return 2
  fi

  local -a reply
  _codex_profiles_discover || return $?
  if (( ${#reply[@]} == 0 )); then
    print -u 2 -r -- 'codex-profiles: no valid standalone profiles were found.'
    return 1
  fi
  print -rl -- "${reply[@]}"
  return 0
}

function cxl() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst
  codex-profiles "$@"
  return $?
}

function cx() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  if (( $# == 1 )) && [[ "$1" == -h || "$1" == --help || "$1" == help ]]; then
    _codex_profiles_help
    return 0
  fi
  _codex_profiles_execute new "$@"
  return $?
}

function cxr() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  if (( $# == 1 )) && [[ "$1" == -h || "$1" == --help || "$1" == help ]]; then
    _codex_profiles_help
    return 0
  fi
  _codex_profiles_execute resume "$@"
  return $?
}

function cxlast() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst

  if (( $# == 1 )) && [[ "$1" == -h || "$1" == --help || "$1" == help ]]; then
    _codex_profiles_help
    return 0
  fi

  _codex_profiles_execute resume-last "$@"
  return $?
}

function _codex_profiles_complete() {
  emulate -L zsh
  # Completion helpers such as _describe use (#b) captures and rely on the
  # EXTENDED_GLOB option normally set by _main_complete. Restore it after emulate.
  setopt localoptions extendedglob no_shwordsplit no_ksharrays no_globsubst

  local -a reply
  local -a CODEX_PROFILES_NAMES
  local -a CODEX_PROFILES_RESUME_OPTIONS
  local CODEX_PROFILES_COMMAND
  _codex_profiles_discover 2>/dev/null || return 0
  CODEX_PROFILES_NAMES=("${reply[@]}")
  CODEX_PROFILES_COMMAND="${words[1]}"

  if (( CURRENT == 2 )) || { (( CURRENT > 2 )) && [[ "${words[CURRENT - 1]}" == -p || "${words[CURRENT - 1]}" == --profile ]]; }; then
    if (( ${#CODEX_PROFILES_NAMES[@]} > 0 )) && (( $+functions[_describe] )); then
      _describe -t profiles 'Codex profiles' CODEX_PROFILES_NAMES
    fi
    return 0
  fi

  if [[ "$CODEX_PROFILES_COMMAND" == cxr || "$CODEX_PROFILES_COMMAND" == cxlast ]]; then
    CODEX_PROFILES_RESUME_OPTIONS=(--last --all --include-non-interactive --help)
    if (( $+functions[_describe] )); then
      _describe -t options 'resume options' CODEX_PROFILES_RESUME_OPTIONS
    fi
  fi
  if (( $+functions[_files] )); then
    _files
  fi
  return 0
}

function _codex_profiles_register_completion() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays no_globsubst
  if (( $+functions[compdef] )); then
    compdef _codex_profiles_complete cx cxr cxlast
  fi
}

_codex_profiles_register_completion
