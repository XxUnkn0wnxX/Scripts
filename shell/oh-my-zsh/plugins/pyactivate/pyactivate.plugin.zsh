#!/usr/bin/env zsh

function _pyactivate_deactivate() {
  # Normal Python venv usually provides deactivate as a shell function
  if (( $+functions[deactivate] )); then
    deactivate
  # pyenv-virtualenv wants deactivate sourced
  elif command -v deactivate >/dev/null 2>&1; then
    source deactivate 2>/dev/null || true
  fi

  unset VIRTUAL_ENV
  unset VIRTUAL_ENV_PROMPT
  unset VENV_ROOT
}

function pyactivate() {
  if (( $# == 1 )) && ( [[ "$1" == -h ]] || [[ "$1" == --help ]] ); then
    print "Usage: pyactivate [<project-or-virtualenv-path>]"
    print "Without an argument, activates a single local virtual environment."
    print "If multiple virtual environments are found, pick one with arrow keys + Enter (Esc/q cancels)."
    print "Running in the active project's root deactivates the current environment."
    print "Running inside a nested project switches environments and leaving the active root deactivates."
    print "An argument may be a project directory or an exact virtualenv path, anywhere."
    return 0
  fi

  if (( $# > 1 )); then
    print -u 2 "Usage: pyactivate [<project-or-virtualenv-path>]"
    return 2
  fi

  local SEARCH_ROOT
  local SEARCH_ROOT_CANON
  local -a CANDIDATE_DIRS=()
  local VENV_DIR
  local ACTIVATE_PATH
  local FZF_RESULT
  local TARGET_ROOT
  local -i IS_BARE=0
  local PREV_VIRTUAL_ENV
  local PREV_VENV_ROOT
  local PREV_ACTIVE_PATH
  local PREV_PATH
  local -i PREV_VENV_ROOT_WAS_SET=0
  local -i PREV_ACTIVE_PATH_WAS_SET=0
  local -i PREV_PATH_WAS_SET=0

  SEARCH_ROOT="${1:-.}"
  SEARCH_ROOT="${SEARCH_ROOT:A}"
  SEARCH_ROOT_CANON="${SEARCH_ROOT:A}"

  if [[ ! -d "$SEARCH_ROOT" ]]; then
    echo "Directory not found: $SEARCH_ROOT"
    return 1
  fi

  if (( $# == 0 )); then
    IS_BARE=1
    if [[ -n "$VIRTUAL_ENV" && -n "$VENV_ROOT" && "$SEARCH_ROOT_CANON" == "${VENV_ROOT:A}" ]]; then
      echo "Deactivating virtual environment."
      _pyactivate_deactivate
      return 0
    fi
  fi

  # If target is itself a venv, prefer it directly
  if [[ -f "$SEARCH_ROOT/pyvenv.cfg" ]]; then
    CANDIDATE_DIRS=("$SEARCH_ROOT")
  else
    local CANDIDATE
    # Search immediate child directories (including hidden), then pick venvs.
    for CANDIDATE in "$SEARCH_ROOT"/*(ND/); do
      if [[ -d "$CANDIDATE" && -f "$CANDIDATE/pyvenv.cfg" ]]; then
        CANDIDATE_DIRS+=("$CANDIDATE")
      fi
    done
  fi

  if (( ${#CANDIDATE_DIRS[@]} == 0 )); then
    if (( IS_BARE == 1 )) && [[ -n "$VIRTUAL_ENV" ]]; then
      echo "Deactivating virtual environment."
      _pyactivate_deactivate
      return 0
    fi
    echo "No virtual environment found in $SEARCH_ROOT or immediate subdir."
    return 1
  fi

  if (( ${#CANDIDATE_DIRS[@]} == 1 )); then
    VENV_DIR="${CANDIDATE_DIRS[1]}"
  else
    if [[ -t 0 ]]; then
      if ! command -v fzf >/dev/null 2>&1; then
        echo "Multiple virtual environments found in $SEARCH_ROOT."
        echo "Install fzf to pick interactively, or pass an exact virtual environment path to pyactivate."
        return 1
      fi

      if ! FZF_RESULT="$(for CANDIDATE in "${CANDIDATE_DIRS[@]}"; do
        printf '%s\n' "${CANDIDATE:t}"
      done | fzf \
        --height=12 \
        --layout=reverse \
        --border=rounded \
        --no-sort \
        --no-mouse \
        --no-input \
        --header='Select a virtual environment (arrow keys + Enter; Esc/q cancels)' \
        --bind 'q:abort' \
        --bind 'esc:abort' )"; then
        echo "Selection cancelled."
        return 1
      fi

      VENV_DIR="${SEARCH_ROOT}/${FZF_RESULT}"
    else
      echo "Multiple virtual environments found in $SEARCH_ROOT."
      for CANDIDATE in "${CANDIDATE_DIRS[@]}"; do
        echo "  $CANDIDATE"
      done
      echo "Pass one exact virtual-environment path to pyactivate."
      return 1
    fi
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Invalid virtual environment directory: $VENV_DIR"
    return 1
  fi

  ACTIVATE_PATH="$VENV_DIR/bin/activate"

  if [[ ! -f "$ACTIVATE_PATH" ]]; then
    echo "Activation script not found: $ACTIVATE_PATH"
    return 1
  fi

  if [[ "$VENV_DIR:A" == "$SEARCH_ROOT:A" ]]; then
    TARGET_ROOT="${SEARCH_ROOT_CANON:h}"
  else
    TARGET_ROOT="$SEARCH_ROOT_CANON"
  fi

  if (( IS_BARE == 1 )) && [[ -n "$VIRTUAL_ENV" && "${VENV_DIR:A}" == "${VIRTUAL_ENV:A}" ]]; then
    echo "Deactivating virtual environment."
    _pyactivate_deactivate
    return 0
  fi

  if [[ -n "$VIRTUAL_ENV" ]]; then
    PREV_VIRTUAL_ENV="$VIRTUAL_ENV"
    if (( ${+VENV_ROOT} )); then
      PREV_VENV_ROOT="$VENV_ROOT"
      PREV_VENV_ROOT_WAS_SET=1
    fi
    if (( ${+PATH} )); then
      PREV_ACTIVE_PATH="$PATH"
      PREV_ACTIVE_PATH_WAS_SET=1
    fi

    echo "Switching virtual environment."
    _pyactivate_deactivate
  fi
  if (( ${+PATH} )); then
    PREV_PATH="$PATH"
    PREV_PATH_WAS_SET=1
  fi

  echo "Activating virtual environment in $VENV_DIR"
  if ! source "$ACTIVATE_PATH"; then
    echo "Failed to source activation script: $ACTIVATE_PATH"
    _pyactivate_deactivate
    if (( PREV_PATH_WAS_SET == 1 )); then
      PATH="$PREV_PATH"
    else
      unset PATH
    fi
    rehash
    if [[ -n "$PREV_VIRTUAL_ENV" ]]; then
      print "Restoring previous virtual environment."
      if [[ -f "${PREV_VIRTUAL_ENV}/bin/activate" ]] && source "${PREV_VIRTUAL_ENV}/bin/activate"; then
        if (( PREV_VENV_ROOT_WAS_SET == 1 )); then
          VENV_ROOT="$PREV_VENV_ROOT"
        else
          unset VENV_ROOT
        fi
        if (( PREV_ACTIVE_PATH_WAS_SET == 1 )); then
          PATH="$PREV_ACTIVE_PATH"
        else
          unset PATH
        fi
        rehash
        print "Restored previous virtual environment."
        return 1
      fi

      _pyactivate_deactivate
      if (( PREV_PATH_WAS_SET == 1 )); then
        PATH="$PREV_PATH"
      else
        unset PATH
      fi
      rehash
      return 1
    fi
    return 1
  fi

  VENV_ROOT="$TARGET_ROOT"
}

function check_venv_dir() {
  if [[ -n "$VENV_ROOT" && -n "$VIRTUAL_ENV" ]]; then
    local CURR_ROOT="${PWD:A}"
    local ROOT="${VENV_ROOT:A}"
    local -i ROOT_LEN=${#ROOT}
    local -i CURR_LEN=${#CURR_ROOT}

    if [[ "$ROOT" == "/" ]]; then
      return 0
    fi

    if [[ "$CURR_ROOT" == "$ROOT" ]]; then
      return 0
    fi

    if (( CURR_LEN > ROOT_LEN )) \
      && [[ "${CURR_ROOT[1,$ROOT_LEN]}" == "$ROOT" && "${CURR_ROOT[$(( ROOT_LEN + 1 ))]}" == "/" ]]; then
      return 0
    fi

    echo "Deactivated virtual environment due to leaving $VENV_ROOT."
    _pyactivate_deactivate
  fi
}

autoload -U add-zsh-hook

# Avoid duplicate hooks when re-sourcing .zshrc
add-zsh-hook -d chpwd check_venv_dir 2>/dev/null
add-zsh-hook chpwd check_venv_dir
