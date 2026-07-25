#!/usr/bin/env zsh
emulate -L zsh
set -o errexit
set -o pipefail
set -o nounset

# codex-sync-model-provider.zsh
#
# Location:
#   /Users/ovidijus/Apps/Scripts/shell/codex-sync-model-provider.zsh
#
# Platform:
#   macOS-only.
#
# Codex root resolution:
#   1. $CODEX_HOME when it is set.
#   2. $HOME/.codex otherwise.
#
# Purpose:
#   Reads root-level model_provider from $CODEX_HOME/config.toml
#   and updates ONLY the persisted Codex thread provider fields:
#
#     $CODEX_HOME/state_5.sqlite
#     table: threads
#     field: model_provider
#
#     $CODEX_HOME/sessions/**/*.jsonl
#     first line only, when type=session_meta, or a guarded legacy repair
#     JSON field: payload.model_provider
#
# Safety:
#   - Refuses to run if config.toml has no valid root-level model_provider.
#   - Refuses to run if state_5.sqlite is missing.
#   - Refuses to run if Codex appears active.
#   - Refuses to run if the threads schema contract for provider migration is not met.
#   - Allows idx_threads_provider drift as a warning.
#   - Blocks dangerous user UPDATE triggers against threads.
#   - Refuses to rewrite session files whose first line is invalid JSON.
#   - Refuses to rewrite session files if line 1 is not valid first-line session_meta payload JSON.
#   - Repairs missing legacy session_meta only when every transcript line is valid and identity/history checks pass.
#   - Never grows line 1 for paginated sessions, preserving their stored byte offsets.
#   - Preflights file modes with /usr/bin/stat and finishes session writes before the DB update.
#   - Shows values/counts before changing anything.
#   - Creates timestamped backups before writing unless --skip-backup is used.
#   - When backup is enabled, archives the full sessions folder.
#   - When backup is enabled, archives only DB files this script is changing,
#     plus config.toml.
#   - With live --skip-backup, keeps preflight interruptible, then ignores
#     INT/TERM/HUP/QUIT from the first write through final validation.
#   - --skip-backup cannot protect against SIGKILL, power loss, or write errors.
#   - Supports --dry-run.
#
# Non-native/Homebrew tools used:
#   - /usr/local/bin/zsh        Homebrew zsh, preferred on this machine.
#   - jq                        JSON validation and first-line session_meta edits.
#   - 7zz                       7-Zip backups; Homebrew package is usually p7zip.
#
# Native macOS/standard CLI tools also used:
#   sqlite3, awk, grep, date, mkdir, mv, tail, rm, sort, uniq,
#   chmod, /usr/bin/stat, touch, wc, dd, ps.

DRY_RUN=0
YES=0
FORCE=0
SKIP_BACKUP=0
PREPARE_BUCKET=1
PADDING_BYTES=256
session_write_total=0
db_update_total=0
db_update_sql_file=""
backup_root=""
backup_dir=""
journal_file=""
backup_verified=0
backup_work_dir=""
sync_started=0
signal_handling=0
phase="preflight"
active_child_pid=0
active_child_kind=""
active_child_scratch=""
active_monitor_pid=0
restore_marker_path=""
backup_db_has_wal=0
backup_db_has_shm=0
restore_in_progress=0
restore_work_dir=""
restore_failure_detail=""
restore_marker_name=".sync-model-provider-in-progress"

fail() {
  progress_finish_line
  echo "ERROR: $*" >&2
  exit 1
}

skip() {
  progress_finish_line
  echo "SKIP: $*"
  exit 0
}

is_safe_backup_run_dir() {
  local candidate_dir="$1"
  local root_abs
  local path_abs
  local base

  [[ -n "$candidate_dir" && -n "$backup_root" ]] || return 1
  root_abs="${backup_root:A}"
  path_abs="${candidate_dir:A}"
  base="${candidate_dir:t}"

  [[ "${candidate_dir:h:A}" == "$root_abs" ]] || return 1
  [[ "$path_abs" != "$root_abs" ]] || return 1
  [[ ! -L "$candidate_dir" ]] || return 1
  [[ "$base" == model-provider-sync-* || "$base" == .model-provider-sync.* ]]
}

remove_backup_run_dir() {
  local backup_path="$1"

  [[ -e "$backup_path" ]] || return 0
  is_safe_backup_run_dir "$backup_path" || return 1
  rm -rf -- "$backup_path"
}

is_safe_scratch_dir() {
  local scratch_path="$1"
  local root_abs

  [[ -n "$scratch_path" && -n "${scratch_dir:-}" ]] || return 1
  root_abs="${scratch_dir:A}"
  [[ "${scratch_path:h:A}" == "$root_abs" ]] || return 1
  [[ "${scratch_path:A}" != "$root_abs" ]] || return 1
  [[ ! -L "$scratch_path" ]] || return 1
  [[ "${scratch_path:t}" == .sync-model-provider.* || "${scratch_path:t}" == .restore.* ]]
}

remove_active_scratch() {
  local scratch_path="${1:-$active_child_scratch}"

  [[ -n "$scratch_path" && -e "$scratch_path" ]] || return 0
  is_safe_scratch_dir "$scratch_path" || return 1
  rm -rf -- "$scratch_path"
}

set_active_child() {
  active_child_pid="$1"
  active_child_kind="$2"
  active_child_scratch="${3:-}"
}

clear_active_child() {
  active_child_pid=0
  active_child_kind=""
  active_child_scratch=""
  active_monitor_pid=0
}

terminate_active_child() {
  local pid="$active_child_pid"
  local child_scratch="$active_child_scratch"
  local -i attempts=0

  if (( pid > 0 )); then
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -TERM "$pid" >/dev/null 2>&1 || true
      while (( attempts < 20 )); do
        kill -0 "$pid" >/dev/null 2>&1 || break
        sleep 0.1
        (( attempts += 1 ))
      done
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill -KILL "$pid" >/dev/null 2>&1 || true
      fi
    fi
    wait "$pid" 2>/dev/null || true
  fi

  if (( active_monitor_pid > 0 )); then
    kill -TERM "$active_monitor_pid" >/dev/null 2>&1 || true
    wait "$active_monitor_pid" 2>/dev/null || true
  fi

  clear_active_child
  [[ -n "$child_scratch" ]] && remove_active_scratch "$child_scratch" || true
}

test_checkpoint() {
  local checkpoint="$1"
  local hook_dir="${SYNC_MODEL_PROVIDER_TEST_DIR:-}"
  local pause_phase="${SYNC_MODEL_PROVIDER_TEST_PAUSE_PHASE:-}"
  local fail_phase="${SYNC_MODEL_PROVIDER_TEST_FAIL_PHASE:-}"
  local ready_file
  local continue_file

  [[ -n "$hook_dir" && -d "$hook_dir" ]] || return 0
  [[ -n "$checkpoint" && "$checkpoint" != *[^A-Za-z0-9_.-]* ]] || return 1

  ready_file="$hook_dir/${checkpoint}.ready"
  continue_file="$hook_dir/${checkpoint}.continue"
  : > "$ready_file" || return 1

  if [[ "$fail_phase" == "$checkpoint" ]]; then
    return 1
  fi

  if [[ "$pause_phase" == "$checkpoint" ]]; then
    while [[ ! -e "$continue_file" ]]; do
      sleep 0.1
    done
  fi

  return 0
}

progress_is_tty_stderr=0
if [[ -t 2 ]]; then
  progress_is_tty_stderr=1
fi

progress_last_line_render_sec=0
progress_active_line=0

progress_now_sec() {
  date +%s
}

progress_emit_line() {
  local line="$1"
  local now_sec
  local emit=1

  if (( ! progress_is_tty_stderr )); then
    now_sec="$(progress_now_sec)"
    if (( now_sec - progress_last_line_render_sec < 1 )); then
      emit=0
    fi
    progress_last_line_render_sec="$now_sec"
  fi

  (( emit == 0 )) && return 0

  if (( progress_is_tty_stderr )); then
    printf '\r\033[2K%s' "$line" >&2 || true
  else
    printf '%s\n' "$line" >&2 || true
  fi
  progress_active_line=1
}

progress_finish_line() {
  if (( progress_active_line == 0 )); then
    return
  fi

  if (( progress_is_tty_stderr )); then
    printf '\r\033[2K' >&2 || true
  fi
  progress_active_line=0
  progress_last_line_render_sec=0
}

progress_emit_final_line() {
  local line="$1"
  if (( progress_is_tty_stderr )); then
    printf '\r\033[2K%s\n' "$line" >&2 || true
  else
    printf '%s\n' "$line" >&2 || true
  fi
  progress_active_line=0
  progress_last_line_render_sec=0
}

progress_percent_text() {
  local seconds="$1"
  local mins
  local secs

  if (( seconds <= 0 )); then
    print -r -- "00:00"
    return
  fi

  if (( seconds < 60 )); then
    print -r -- "$(printf '%02d:%02d' 0 "$seconds")"
    return
  fi

  mins=$(( seconds / 60 ))
  secs=$(( seconds % 60 ))
  print -r -- "$(printf '%02d:%02d' "$mins" "$secs")"
}

format_backup_progress() {
  local percent="$1"
  local started_at="$2"
  local now_sec
  local elapsed
  local eta_sec
  local eta_text

  if [[ "$percent" != <-> ]] || (( percent < 0 || percent > 100 )); then
    return
  fi

  if (( percent == 0 || started_at <= 0 )); then
    eta_text="calculating..."
  else
    now_sec="$(progress_now_sec)"
    elapsed=$(( now_sec - started_at ))

    if (( elapsed > 0 )); then
      eta_sec=$(( (elapsed * 100 / percent) - elapsed ))
    else
      eta_sec=-1
    fi

    if (( eta_sec < 0 )); then
      eta_text="calculating..."
    else
      eta_text="$(progress_percent_text "$eta_sec")"
    fi
  fi

  progress_emit_line "Working: Backup (${percent}% | ETA ${eta_text})"
}

parse_7zz_progress() {
  local track_progress="$1"
  local started_at="$2"
  local percent
  local output_chunk
  local last_percent=0
  local clean_chunk
  local percent_pattern='([0-9]{1,3})%'

  while IFS= read -d $'\b' -r output_chunk || [[ -n "$output_chunk" ]]; do
    [[ -n "$output_chunk" ]] || continue

    clean_chunk="${output_chunk//$'\r'/}"
    if [[ ! "$clean_chunk" =~ $percent_pattern ]]; then
      continue
    fi
    percent="${match[1]}"

    if (( percent < 0 || percent > 100 )); then
      continue
    fi
    if (( percent < last_percent )); then
      continue
    fi

    last_percent=$percent
    if (( track_progress )); then
      format_backup_progress "$percent" "$started_at"
    fi
  done

  return 0
}

parse_db_update_progress() {
  local expected_total="$1"
  local db_output_line
  local marker_value
  local -i completed_count=0
  local -i commit_seen=0
  local -i invalid_marker=0

  while IFS= read -r db_output_line; do
    case "$db_output_line" in
      __DB_UPDATE_DONE__*)
        marker_value="${db_output_line#__DB_UPDATE_DONE__:}"
        if [[ "$marker_value" == 1 ]]; then
          (( completed_count += 1 ))
          if (( completed_count < expected_total )); then
            show_count_progress "DB Syncing" "$completed_count" "$expected_total"
          fi
        else
          invalid_marker=1
        fi
        ;;
      __DB_COMMIT_DONE__)
        commit_seen=1
        ;;
      *)
        ;;
    esac
  done

  (( invalid_marker == 0 && commit_seen == 1 && completed_count == expected_total ))
}

show_count_progress() {
  local label="$1"
  local done_count="$2"
  local total_count="$3"

  progress_emit_line "Working: ${label} (${done_count}/${total_count})"
}

# The recovery layer below intentionally avoids shell pipelines and FIFOs for
# long-running producers. The main shell owns the real 7zz/sqlite3 PID while a
# small monitor reads an ordinary per-run progress file.
latest_7zz_percent() {
  local progress_file="$1"

  [[ -f "$progress_file" ]] || return 1
  LC_ALL=C awk '
    BEGIN { RS = sprintf("%c", 8) }
    {
      text = $0
      while (match(text, /[0-9][0-9]*%/)) {
        value = substr(text, RSTART, RLENGTH - 1)
        if ((value + 0) >= 0 && (value + 0) <= 100) {
          last = value + 0
        }
        text = substr(text, RSTART + RLENGTH)
      }
    }
    END {
      if (last != "") {
        print last
      }
    }
  ' "$progress_file"
}

monitor_7zz_progress() {
  local producer_pid="$1"
  local progress_file="$2"
  local track_progress="$3"
  local started_at="$4"
  local percent=""
  local -i last_percent=-1

  while kill -0 "$producer_pid" >/dev/null 2>&1; do
    if (( track_progress )); then
      percent="$(latest_7zz_percent "$progress_file" 2>/dev/null || true)"
      if [[ "$percent" == <-> ]] && (( percent >= last_percent && percent < 100 )); then
        if (( percent > last_percent )); then
          format_backup_progress "$percent" "$started_at"
          last_percent="$percent"
        fi
      fi
    fi
    sleep 0.2
  done
}

run_7zz_archive_with_progress() {
  local archive_path="$1"
  local track_progress="$2"
  local -i backup_started_at="${3:-0}"
  shift 3
  local -a source_paths=("$@")
  local work_dir
  local progress_file
  local producer_pid
  local monitor_pid
  local -i producer_status=0
  local -i rearm_traps=0

  (( ${#source_paths[@]} > 0 )) || return 2
  (( backup_started_at > 0 )) || backup_started_at="$(progress_now_sec)"

  work_dir="$(mktemp -d "$scratch_dir/.sync-model-provider.7zz.XXXXXX")" || return 1
  progress_file="$work_dir/progress.bin"
  : > "$progress_file" || {
    remove_active_scratch "$work_dir" || true
    return 1
  }

  if (( ! DRY_RUN && signal_handling == 0 )); then
    rearm_traps=1
    trap '' INT TERM HUP QUIT
  fi

  (
    (( signal_handling == 0 )) && trap - INT TERM HUP QUIT
    exec 7zz a -mx=5 -mmt=on -bb0 -bso0 -bse2 -bsp1 \
      "$archive_path" "${source_paths[@]}"
  ) > "$progress_file" &
  producer_pid=$!
  set_active_child "$producer_pid" "7zz backup" "$work_dir"

  (
    trap '' INT TERM HUP QUIT
    monitor_7zz_progress "$producer_pid" "$progress_file" "$track_progress" "$backup_started_at"
  ) &
  monitor_pid=$!
  active_monitor_pid="$monitor_pid"

  (( rearm_traps )) && setup_signal_traps

  set +e
  wait "$producer_pid"
  producer_status=$?
  kill -TERM "$monitor_pid" >/dev/null 2>&1 || true
  wait "$monitor_pid" 2>/dev/null || true
  remove_active_scratch "$work_dir" || true
  clear_active_child
  (( signal_handling == 0 )) && set -e

  if (( producer_status != 0 )); then
    return "$producer_status"
  fi

  if (( track_progress )); then
    progress_emit_final_line "Working: Backup (100% | ETA 00:00)"
  fi
  return 0
}

run_tracked_7zz_test() {
  local archive_path="$1"
  local producer_pid
  local -i producer_status=0
  local -i rearm_traps=0

  if (( ! DRY_RUN && signal_handling == 0 )); then
    rearm_traps=1
    trap '' INT TERM HUP QUIT
  fi

  (
    (( signal_handling == 0 )) && trap - INT TERM HUP QUIT
    exec 7zz t -bd -bb0 -bso0 -bse2 "$archive_path"
  ) >/dev/null &
  producer_pid=$!
  set_active_child "$producer_pid" "7zz archive test"
  (( rearm_traps )) && setup_signal_traps

  set +e
  wait "$producer_pid"
  producer_status=$?
  clear_active_child
  (( signal_handling == 0 )) && set -e

  return "$producer_status"
}

write_7zz_member_list() {
  local archive_path="$1"
  local output_file="$2"
  local producer_pid
  local -i producer_status=0
  local -i rearm_traps=0

  if (( ! DRY_RUN && signal_handling == 0 )); then
    rearm_traps=1
    trap '' INT TERM HUP QUIT
  fi

  (
    (( signal_handling == 0 )) && trap - INT TERM HUP QUIT
    exec 7zz l -ba -slt "$archive_path"
  ) > "$output_file" &
  producer_pid=$!
  set_active_child "$producer_pid" "7zz archive listing" "${output_file:h}"
  (( rearm_traps )) && setup_signal_traps

  set +e
  wait "$producer_pid"
  producer_status=$?
  clear_active_child
  (( signal_handling == 0 )) && set -e

  return "$producer_status"
}

array_has_exact_value() {
  local needle="$1"
  shift
  local value

  for value in "$@"; do
    [[ "$value" == "$needle" ]] && return 0
  done
  return 1
}

verify_7zz_archive() {
  local archive_path="$1"
  local archive_kind="$2"
  local work_dir
  local list_file
  local member
  local expected_member
  local session_file
  local -a members=()

  [[ -f "$archive_path" ]] || {
    echo "Backup archive was not created: $archive_path" >&2
    return 1
  }

  run_tracked_7zz_test "$archive_path" || {
    echo "Backup archive test failed: $archive_path" >&2
    return 1
  }

  work_dir="$(mktemp -d "$scratch_dir/.sync-model-provider.list.XXXXXX")" || return 1
  list_file="$work_dir/members.txt"
  if ! write_7zz_member_list "$archive_path" "$list_file"; then
    remove_active_scratch "$work_dir" || true
    echo "Could not list backup archive members: $archive_path" >&2
    return 1
  fi

  members=("${(@f)$(awk -F' = ' '/^Path = / { print $2 }' "$list_file")}")
  remove_active_scratch "$work_dir" || true

  if (( ${#members[@]} == 0 )); then
    echo "Backup archive has no members: $archive_path" >&2
    return 1
  fi

  case "$archive_kind" in
    db)
      array_has_exact_value "config.toml" "${members[@]}" || {
        echo "DB backup archive is missing config.toml." >&2
        return 1
      }
      array_has_exact_value "$db_base" "${members[@]}" || {
        echo "DB backup archive is missing $db_base." >&2
        return 1
      }

      if (( backup_db_has_wal )); then
        array_has_exact_value "${db_base}-wal" "${members[@]}" || {
          echo "DB backup archive is missing ${db_base}-wal." >&2
          return 1
        }
      elif array_has_exact_value "${db_base}-wal" "${members[@]}"; then
        echo "DB backup archive unexpectedly contains ${db_base}-wal." >&2
        return 1
      fi

      if (( backup_db_has_shm )); then
        array_has_exact_value "${db_base}-shm" "${members[@]}" || {
          echo "DB backup archive is missing ${db_base}-shm." >&2
          return 1
        }
      elif array_has_exact_value "${db_base}-shm" "${members[@]}"; then
        echo "DB backup archive unexpectedly contains ${db_base}-shm." >&2
        return 1
      fi

      for member in "${members[@]}"; do
        case "$member" in
          config.toml|"$db_base"|"${db_base}-wal"|"${db_base}-shm")
            ;;
          *)
            echo "DB backup archive contains an unexpected member: $member" >&2
            return 1
            ;;
        esac
      done
      ;;
    sessions)
      array_has_exact_value "sessions" "${members[@]}" || {
        echo "Sessions backup archive is missing the top-level sessions directory." >&2
        return 1
      }

      for member in "${members[@]}"; do
        if [[ "$member" != "sessions" && "$member" != sessions/* ]]; then
          echo "Sessions backup archive contains a path outside sessions/: $member" >&2
          return 1
        fi
        if [[ "$member" == */../* || "$member" == ../* || "$member" == /* ]]; then
          echo "Sessions backup archive contains an unsafe path: $member" >&2
          return 1
        fi
      done

      for session_file in "${session_files_to_update[@]}"; do
        expected_member="${session_file#$codex_dir/}"
        array_has_exact_value "$expected_member" "${members[@]}" || {
          echo "Sessions backup archive is missing a planned file: $expected_member" >&2
          return 1
        }
      done
      ;;
    *)
      echo "Unknown backup archive kind: $archive_kind" >&2
      return 1
      ;;
  esac

  return 0
}

set_restore_marker() {
  local marker_dir="$1"
  local temp_marker
  local -i db_archive_expected=0
  local -i sessions_archive_expected=0

  is_safe_backup_run_dir "$marker_dir" || return 1
  restore_marker_path="$marker_dir/$restore_marker_name"
  temp_marker="$marker_dir/.${restore_marker_name}.tmp.$$.$RANDOM"
  (( rows_to_update > 0 )) && db_archive_expected=1
  [[ -d "$sessions_dir" ]] && sessions_archive_expected=1

  if ! {
    printf 'SYNC_PROVIDER_BACKUP_DIR=%s\n' "$marker_dir"
    printf 'PHASE=syncing\n'
    printf 'DB_ARCHIVE=%d\n' "$db_archive_expected"
    printf 'SESSIONS_ARCHIVE=%d\n' "$sessions_archive_expected"
    printf 'DB_HAS_WAL=%d\n' "$backup_db_has_wal"
    printf 'DB_HAS_SHM=%d\n' "$backup_db_has_shm"
    printf 'STARTED_AT=%s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)"
  } > "$temp_marker"; then
    rm -f -- "$temp_marker" 2>/dev/null || true
    return 1
  fi

  if ! mv "$temp_marker" "$restore_marker_path"; then
    rm -f -- "$temp_marker" 2>/dev/null || true
    return 1
  fi
  return 0
}

read_restore_marker_flag() {
  local marker_path="$1"
  local key="$2"

  awk -v key="$key" '
    index($0, key "=") == 1 {
      count += 1
      if ($0 == key "=0" || $0 == key "=1") {
        value = substr($0, length(key) + 2)
      } else {
        invalid = 1
      }
    }
    END {
      if (count == 1 && invalid == 0 && (value == "0" || value == "1")) {
        print value
      } else {
        exit 1
      }
    }
  ' "$marker_path"
}

remove_restore_marker() {
  local expected_marker

  [[ -n "$backup_dir" ]] || return 1
  is_safe_backup_run_dir "$backup_dir" || return 1
  expected_marker="$backup_dir/$restore_marker_name"
  [[ "$restore_marker_path" == "$expected_marker" ]] || return 1
  [[ ! -L "$expected_marker" ]] || return 1
  rm -f -- "$expected_marker"
}

ensure_no_pending_marker() {
  local marker
  local partial_dir

  backup_root="$codex_dir/backups"

  for marker in "$backup_root"/model-provider-sync-*/"$restore_marker_name"(N); do
    echo
    echo "Refusing to run: found an incomplete model-provider sync."
    echo "  marker: $marker"
    echo "  backup: ${marker:h}"
    echo
    echo "A prior run may have ended through SIGKILL, power loss, or a failed restore."
    echo "Inspect or restore this backup manually before retrying."
    exit 1
  done

  for partial_dir in "$backup_root"/.model-provider-sync.*(N); do
    [[ -d "$partial_dir" ]] || continue
    echo
    echo "Refusing to run: found an incomplete backup work directory."
    echo "  path: $partial_dir"
    echo
    echo "A prior run may have ended during backup creation."
    echo "Confirm no sync/7zz process is using it before removing it manually."
    exit 1
  done
}

emit_restore_progress() {
  local started_at="$1"
  local percent="$2"
  local eta_text="calculating..."
  local now_sec
  local elapsed
  local eta_sec

  (( percent >= 0 && percent <= 100 )) || return 0
  if (( percent > 0 && started_at > 0 )); then
    now_sec="$(progress_now_sec)"
    elapsed=$(( now_sec - started_at ))
    if (( elapsed > 0 )); then
      eta_sec=$(( (elapsed * 100 / percent) - elapsed ))
      (( eta_sec < 0 )) || eta_text="$(progress_percent_text "$eta_sec")"
    fi
  fi
  progress_emit_line "Working: Restoring Backup (${percent}% | ETA ${eta_text})"
}

run_tracked_7zz_extract() {
  local archive_path="$1"
  local output_dir="$2"
  local producer_pid
  local -i producer_status=0

  7zz x -y -bd -bb0 -bso0 -bse2 -mmt=on -o"$output_dir" "$archive_path" &
  producer_pid=$!
  set_active_child "$producer_pid" "7zz restore extraction"

  set +e
  wait "$producer_pid"
  producer_status=$?
  clear_active_child

  return "$producer_status"
}

current_db_marker_count() {
  local output_file="$1"

  [[ -f "$output_file" ]] || {
    print -r -- 0
    return 0
  }
  awk -F: '
    $1 == "__DB_UPDATE_DONE__" && $2 == "1" { count += 1 }
    END { print count + 0 }
  ' "$output_file"
}

monitor_db_progress() {
  local producer_pid="$1"
  local output_file="$2"
  local expected_total="$3"
  local current_count
  local -i shown_count=0

  while kill -0 "$producer_pid" >/dev/null 2>&1; do
    current_count="$(current_db_marker_count "$output_file" 2>/dev/null || print -r -- 0)"
    if [[ "$current_count" == <-> ]] && (( current_count > shown_count )); then
      while (( shown_count < current_count && shown_count < expected_total )); do
        (( shown_count += 1 ))
        show_count_progress "DB Syncing" "$shown_count" "$expected_total"
      done
    fi
    sleep 0.1
  done
}

validate_db_progress_file() {
  local output_file="$1"
  local expected_total="$2"
  local line
  local marker_value
  local -i completed=0
  local -i commit_seen=0

  while IFS= read -r line; do
    case "$line" in
      __DB_UPDATE_DONE__:*)
        marker_value="${line#__DB_UPDATE_DONE__:}"
        [[ "$marker_value" == "1" ]] || return 1
        (( completed += 1 ))
        ;;
      __DB_COMMIT_DONE__)
        commit_seen=1
        ;;
    esac
  done < "$output_file"

  (( completed == expected_total && commit_seen == 1 ))
}

run_sqlite_updates_with_progress() {
  local -i expected_total="$1"
  local sql_file="$2"
  local work_dir
  local output_file
  local producer_pid
  local monitor_pid
  local -i sqlite_status=0
  local -i current_count=0
  local -i progress_valid=0
  local -i rearm_traps=0

  (( expected_total > 0 )) || return 0
  work_dir="$(mktemp -d "$scratch_dir/.sync-model-provider.sqlite.XXXXXX")" || return 1
  output_file="$work_dir/progress.txt"
  : > "$output_file" || {
    remove_active_scratch "$work_dir" || true
    return 1
  }

  if (( ! DRY_RUN && signal_handling == 0 )); then
    rearm_traps=1
    trap '' INT TERM HUP QUIT
  fi

  (
    (( signal_handling == 0 )) && trap - INT TERM HUP QUIT
    exec sqlite3 "$db_file"
  ) < "$sql_file" > "$output_file" &
  producer_pid=$!
  set_active_child "$producer_pid" "sqlite3 update" "$work_dir"

  (
    trap '' INT TERM HUP QUIT
    monitor_db_progress "$producer_pid" "$output_file" "$expected_total"
  ) &
  monitor_pid=$!
  active_monitor_pid="$monitor_pid"
  (( rearm_traps )) && setup_signal_traps

  set +e
  wait "$producer_pid"
  sqlite_status=$?
  kill -TERM "$monitor_pid" >/dev/null 2>&1 || true
  wait "$monitor_pid" 2>/dev/null || true

  current_count="$(current_db_marker_count "$output_file" 2>/dev/null || print -r -- 0)"
  if [[ "$current_count" == <-> ]]; then
    show_count_progress "DB Syncing" "$current_count" "$expected_total"
  fi

  if (( sqlite_status == 0 )) && validate_db_progress_file "$output_file" "$expected_total"; then
    progress_valid=1
  fi

  remove_active_scratch "$work_dir" || true
  clear_active_child
  (( signal_handling == 0 )) && set -e

  (( progress_valid == 1 ))
}

restore_from_backup() {
  local db_backup_path="$backup_dir/codex-dbs.7z"
  local sessions_backup_path="$backup_dir/sessions.7z"
  local holding_dir
  local staged_db_dir
  local staged_sessions_dir
  local failed_dir
  local staged_session_file
  local session_file
  local restored_first_line
  local expected_mode
  local restored_mode
  local quick_check_output
  local marker_db_archive
  local marker_sessions_archive
  local marker_db_has_wal
  local marker_db_has_shm
  local -i restore_db=0
  local -i restore_sessions=0
  local -i db_swap_started=0
  local -i db_main_held=0
  local -i db_wal_held=0
  local -i db_shm_held=0
  local -i sessions_held=0
  local -i rollback_problem=0
  local -i started_at=0

  set +e
  restore_in_progress=1
  restore_failure_detail=""
  restore_work_dir=""

  if ! is_safe_backup_run_dir "$backup_dir"; then
    restore_failure_detail="The active backup directory failed its path-safety check."
    restore_in_progress=0
    return 1
  fi

  restore_marker_path="$backup_dir/$restore_marker_name"
  if [[ ! -f "$restore_marker_path" || -L "$restore_marker_path" ]]; then
    restore_failure_detail="The recovery marker is missing or unsafe: $restore_marker_path"
    restore_in_progress=0
    return 1
  fi

  if ! grep -Fqx "SYNC_PROVIDER_BACKUP_DIR=$backup_dir" "$restore_marker_path" ||
     ! grep -Fqx "PHASE=syncing" "$restore_marker_path"; then
    restore_failure_detail="The recovery marker does not match the active backup."
    restore_in_progress=0
    return 1
  fi

  if ! marker_db_archive="$(read_restore_marker_flag "$restore_marker_path" DB_ARCHIVE)" ||
     ! marker_sessions_archive="$(read_restore_marker_flag "$restore_marker_path" SESSIONS_ARCHIVE)" ||
     ! marker_db_has_wal="$(read_restore_marker_flag "$restore_marker_path" DB_HAS_WAL)" ||
     ! marker_db_has_shm="$(read_restore_marker_flag "$restore_marker_path" DB_HAS_SHM)"; then
    restore_failure_detail="The recovery marker has missing, duplicated, or invalid archive flags."
    restore_in_progress=0
    return 1
  fi
  backup_db_has_wal="$marker_db_has_wal"
  backup_db_has_shm="$marker_db_has_shm"

  [[ -f "$db_backup_path" ]] && restore_db=1
  [[ -f "$sessions_backup_path" ]] && restore_sessions=1
  if (( restore_db != marker_db_archive )); then
    restore_failure_detail="The DB backup archive does not match the durable recovery marker."
    restore_in_progress=0
    return 1
  fi
  if (( restore_sessions != marker_sessions_archive )); then
    restore_failure_detail="The sessions backup archive does not match the durable recovery marker."
    restore_in_progress=0
    return 1
  fi
  if (( marker_db_archive == 0 && (marker_db_has_wal != 0 || marker_db_has_shm != 0) )); then
    restore_failure_detail="The recovery marker declares DB sidecars without a DB archive."
    restore_in_progress=0
    return 1
  fi
  if (( restore_db == 0 && restore_sessions == 0 )); then
    restore_failure_detail="No restorable archive exists in $backup_dir."
    restore_in_progress=0
    return 1
  fi

  restore_work_dir="$(mktemp -d "$scratch_dir/.restore.XXXXXX")" || {
    restore_failure_detail="Could not create a restore staging directory."
    restore_in_progress=0
    return 1
  }
  holding_dir="$restore_work_dir/holding"
  staged_db_dir="$restore_work_dir/staged-db"
  staged_sessions_dir="$restore_work_dir/staged-sessions"
  failed_dir="$restore_work_dir/failed-installed"

  if ! mkdir -p "$holding_dir/db" "$staged_db_dir" "$staged_sessions_dir" "$failed_dir"; then
    restore_failure_detail="Could not prepare restore staging under $restore_work_dir."
    restore_in_progress=0
    return 1
  fi

  restore_abort_current() {
    local message="$1"

    rollback_problem=0

    if (( sessions_held )); then
      if [[ -d "$sessions_dir" ]]; then
        mv "$sessions_dir" "$failed_dir/sessions-from-backup" 2>/dev/null || rollback_problem=1
      fi
      mv "$holding_dir/sessions-live" "$sessions_dir" 2>/dev/null || rollback_problem=1
    fi

    if (( db_swap_started )); then
      mkdir -p "$failed_dir/db-from-backup" 2>/dev/null || rollback_problem=1
      [[ ! -e "$db_file" ]] ||
        mv "$db_file" "$failed_dir/db-from-backup/$db_base" 2>/dev/null ||
        rollback_problem=1
      [[ ! -e "${db_file}-wal" ]] ||
        mv "${db_file}-wal" "$failed_dir/db-from-backup/${db_base}-wal" 2>/dev/null ||
        rollback_problem=1
      [[ ! -e "${db_file}-shm" ]] ||
        mv "${db_file}-shm" "$failed_dir/db-from-backup/${db_base}-shm" 2>/dev/null ||
        rollback_problem=1

      if (( db_main_held )); then
        mv "$holding_dir/db/$db_base" "$db_file" 2>/dev/null || rollback_problem=1
      fi
      if (( db_wal_held )); then
        mv "$holding_dir/db/${db_base}-wal" "${db_file}-wal" 2>/dev/null || rollback_problem=1
      fi
      if (( db_shm_held )); then
        mv "$holding_dir/db/${db_base}-shm" "${db_file}-shm" 2>/dev/null || rollback_problem=1
      fi
    fi

    restore_failure_detail="$message"
    if (( rollback_problem )); then
      restore_failure_detail+=" The attempt to return the interrupted live state also encountered an error."
    fi
    restore_in_progress=0
    return 1
  }

  started_at="$(progress_now_sec)"
  emit_restore_progress "$started_at" 0

  if (( restore_db )); then
    if ! verify_7zz_archive "$db_backup_path" db; then
      restore_abort_current "DB backup verification failed before restore."
      return 1
    fi
    if ! run_tracked_7zz_extract "$db_backup_path" "$staged_db_dir"; then
      restore_abort_current "DB backup extraction failed."
      return 1
    fi
    emit_restore_progress "$started_at" 20

    if [[ ! -f "$staged_db_dir/$db_base" ]]; then
      restore_abort_current "The staged DB backup is missing $db_base."
      return 1
    fi
    if (( backup_db_has_wal )) && [[ ! -f "$staged_db_dir/${db_base}-wal" ]]; then
      restore_abort_current "The staged DB backup is missing ${db_base}-wal."
      return 1
    fi
    if (( backup_db_has_shm )) && [[ ! -f "$staged_db_dir/${db_base}-shm" ]]; then
      restore_abort_current "The staged DB backup is missing ${db_base}-shm."
      return 1
    fi

    quick_check_output="$(sqlite3 -readonly "$staged_db_dir/$db_base" 'PRAGMA quick_check;' 2>/dev/null || true)"
    if [[ "$quick_check_output" != "ok" ]]; then
      restore_abort_current "The staged DB quick_check failed: ${quick_check_output:-<empty>}."
      return 1
    fi
    if (( backup_db_has_wal )); then
      [[ -f "$staged_db_dir/${db_base}-wal" ]] || {
        restore_abort_current "The staged DB WAL disappeared during validation."
        return 1
      }
    else
      rm -f -- "$staged_db_dir/${db_base}-wal" 2>/dev/null || true
    fi
    if (( backup_db_has_shm )); then
      [[ -f "$staged_db_dir/${db_base}-shm" ]] || {
        restore_abort_current "The staged DB SHM disappeared during validation."
        return 1
      }
    else
      rm -f -- "$staged_db_dir/${db_base}-shm" 2>/dev/null || true
    fi
  fi

  if (( restore_sessions )); then
    if ! verify_7zz_archive "$sessions_backup_path" sessions; then
      restore_abort_current "Sessions backup verification failed before restore."
      return 1
    fi
    if ! run_tracked_7zz_extract "$sessions_backup_path" "$staged_sessions_dir"; then
      restore_abort_current "Sessions backup extraction failed."
      return 1
    fi
    emit_restore_progress "$started_at" 45

    if [[ ! -d "$staged_sessions_dir/sessions" ]]; then
      restore_abort_current "The staged sessions backup has no top-level sessions directory."
      return 1
    fi

    for session_file in "${session_files_to_update[@]}"; do
      staged_session_file="$staged_sessions_dir/${session_file#$codex_dir/}"
      if [[ ! -f "$staged_session_file" ]]; then
        restore_abort_current "A planned session is missing from staged restore: $session_file"
        return 1
      fi

      IFS= read -r restored_first_line < "$staged_session_file" || restored_first_line=""
      if [[ "$restored_first_line" != "${session_first_line_map[$session_file]-}" ]]; then
        restore_abort_current "A staged session does not match its pre-sync first line: $session_file"
        return 1
      fi

      expected_mode="${session_file_mode_map[$session_file]-}"
      restored_mode="$("$STAT_CMD" -f %Lp "$staged_session_file" 2>/dev/null || true)"
      if [[ -n "$expected_mode" && "$restored_mode" != "$expected_mode" ]]; then
        restore_abort_current "A staged session has the wrong mode: $session_file"
        return 1
      fi
    done
  fi

  if ! test_checkpoint "restore_after_extract"; then
    restore_abort_current "A fixture-requested restore failure occurred after extraction."
    return 1
  fi

  if (( restore_db )); then
    if ! mv "$db_file" "$holding_dir/db/$db_base"; then
      restore_abort_current "Could not move the live DB into restore holding."
      return 1
    fi
    db_swap_started=1
    db_main_held=1

    if [[ -e "${db_file}-wal" ]]; then
      if ! mv "${db_file}-wal" "$holding_dir/db/${db_base}-wal"; then
        restore_abort_current "Could not move the live DB WAL into restore holding."
        return 1
      fi
      db_wal_held=1
    fi
    if [[ -e "${db_file}-shm" ]]; then
      if ! mv "${db_file}-shm" "$holding_dir/db/${db_base}-shm"; then
        restore_abort_current "Could not move the live DB SHM into restore holding."
        return 1
      fi
      db_shm_held=1
    fi

    if ! mv "$staged_db_dir/$db_base" "$db_file"; then
      restore_abort_current "Could not install the staged DB."
      return 1
    fi
    if (( backup_db_has_wal )); then
      if ! mv "$staged_db_dir/${db_base}-wal" "${db_file}-wal"; then
        restore_abort_current "Could not install the staged DB WAL."
        return 1
      fi
    fi
    if (( backup_db_has_shm )); then
      if ! mv "$staged_db_dir/${db_base}-shm" "${db_file}-shm"; then
        restore_abort_current "Could not install the staged DB SHM."
        return 1
      fi
    fi

    quick_check_output="$(sqlite3 -readonly "$db_file" 'PRAGMA quick_check;' 2>/dev/null || true)"
    if [[ "$quick_check_output" != "ok" ]]; then
      restore_abort_current "The restored live DB quick_check failed: ${quick_check_output:-<empty>}."
      return 1
    fi

    if ! test_checkpoint "restore_after_db_swap"; then
      restore_abort_current "A fixture-requested restore failure occurred after the DB swap."
      return 1
    fi
    emit_restore_progress "$started_at" 70
  fi

  if (( restore_sessions )); then
    if [[ ! -d "$sessions_dir" ]]; then
      restore_abort_current "The live sessions tree disappeared before restore."
      return 1
    fi
    if ! mv "$sessions_dir" "$holding_dir/sessions-live"; then
      restore_abort_current "Could not move the live sessions tree into restore holding."
      return 1
    fi
    sessions_held=1

    if ! mv "$staged_sessions_dir/sessions" "$sessions_dir"; then
      restore_abort_current "Could not install the staged sessions tree."
      return 1
    fi

    for session_file in "${session_files_to_update[@]}"; do
      if [[ ! -f "$session_file" ]]; then
        restore_abort_current "A planned session is missing after restore: $session_file"
        return 1
      fi
      IFS= read -r restored_first_line < "$session_file" || restored_first_line=""
      if [[ "$restored_first_line" != "${session_first_line_map[$session_file]-}" ]]; then
        restore_abort_current "A restored session does not match its pre-sync first line: $session_file"
        return 1
      fi
      expected_mode="${session_file_mode_map[$session_file]-}"
      restored_mode="$("$STAT_CMD" -f %Lp "$session_file" 2>/dev/null || true)"
      if [[ -n "$expected_mode" && "$restored_mode" != "$expected_mode" ]]; then
        restore_abort_current "A restored session has the wrong mode: $session_file"
        return 1
      fi
    done

    if ! test_checkpoint "restore_after_sessions_swap"; then
      restore_abort_current "A fixture-requested restore failure occurred after the sessions swap."
      return 1
    fi
    emit_restore_progress "$started_at" 90
  fi

  if ! test_checkpoint "restore_before_cleanup"; then
    restore_abort_current "A fixture-requested restore failure occurred before cleanup."
    return 1
  fi

  progress_emit_final_line "Working: Restoring Backup (100% | ETA 00:00)"

  if ! remove_backup_run_dir "$backup_dir"; then
    restore_failure_detail="The data was restored, but the backup could not be removed: $backup_dir"
    restore_in_progress=0
    return 1
  fi
  restore_marker_path=""

  if ! remove_active_scratch "$restore_work_dir"; then
    echo "WARNING: Restored data is safe, but restore scratch could not be removed: $restore_work_dir" >&2
  fi
  restore_work_dir=""
  restore_in_progress=0
  phase="complete"
  unfunction restore_abort_current 2>/dev/null || true
  return 0
}

recover_and_exit() {
  local reason_kind="$1"
  local reason_text="$2"
  local exit_code="$3"

  signal_handling=1
  trap '' INT TERM HUP QUIT
  set +e
  progress_finish_line
  terminate_active_child
  phase="restoring"

  if [[ "$reason_kind" == "error" ]]; then
    echo "ERROR: $reason_text" >&2
  fi
  echo "Restoring the verified backup before exit."

  if restore_from_backup; then
    echo "Backup restored and removed. No changes were kept."
  else
    echo "Restore failed. Manual recovery is required." >&2
    echo "Backup retained at: $backup_dir" >&2
    [[ -z "$restore_work_dir" ]] ||
      echo "Restore staging retained at: $restore_work_dir" >&2
    [[ -z "$restore_failure_detail" ]] ||
      echo "Reason: $restore_failure_detail" >&2
  fi

  exit "$exit_code"
}

sync_signal_handler() {
  local signal_label="$1"
  local signal_code="$2"

  (( signal_handling == 0 )) || return 0
  signal_handling=1
  trap '' INT TERM HUP QUIT
  set +e
  progress_finish_line
  echo "Signal detected ($signal_label); initiating safe shutdown."
  terminate_active_child

  case "$phase" in
    preflight)
      echo "No backup or sync had started. Nothing was changed."
      exit "$signal_code"
      ;;
    backup_partial)
      if [[ -n "$backup_work_dir" && -e "$backup_work_dir" ]]; then
        if remove_backup_run_dir "$backup_work_dir"; then
          echo "Partial backup removed. Sync had not started; nothing was changed."
        else
          echo "Partial backup could not be removed; sync had not started." >&2
          echo "Retained partial backup: $backup_work_dir" >&2
        fi
      else
        echo "Backup setup stopped before a partial archive was created. Nothing was changed."
      fi
      exit "$signal_code"
      ;;
    backup_verified)
      if [[ -n "$backup_dir" && -e "$backup_dir" ]]; then
        if remove_backup_run_dir "$backup_dir"; then
          echo "Verified backup removed. Sync had not started; nothing was changed."
        else
          echo "Verified backup could not be removed; sync had not started." >&2
          echo "Retained verified backup: $backup_dir" >&2
        fi
      else
        echo "Verified-backup phase stopped before a backup remained. Nothing was changed."
      fi
      exit "$signal_code"
      ;;
    syncing|post_sync)
      recover_and_exit "signal" "$signal_label" "$signal_code"
      ;;
    restoring)
      # All catchable signals are already ignored before restore begins.
      return 0
      ;;
    *)
      echo "No sync mutation was active. Nothing was changed."
      exit "$signal_code"
      ;;
  esac
}

setup_signal_traps() {
  unsetopt localtraps
  trap 'sync_signal_handler "SIGINT" 130' INT
  trap 'sync_signal_handler "SIGHUP" 129' HUP
  trap 'sync_signal_handler "SIGQUIT" 131' QUIT
  trap 'sync_signal_handler "SIGTERM" 143' TERM
}

clear_signal_traps() {
  unsetopt localtraps
  trap - INT HUP QUIT TERM
}

sync_failure() {
  local message="$1"
  local exit_code="${2:-1}"

  if (( sync_started == 1 && backup_verified == 1 )) &&
     [[ -n "$backup_dir" && -d "$backup_dir" ]]; then
    recover_and_exit "error" "$message" "$exit_code"
  fi
  fail "$message"
}

usage() {
  cat <<'USAGE'
Usage:
  ./codex-sync-model-provider.zsh [--dry-run] [--yes] [--force] [--skip-backup] [--no-prepare-bucket] [--padding-bytes N]

Options:
  --dry-run            Show what would be changed, but do not write anything.
  --yes                Do not ask for interactive confirmation before writing.
  --force              Rewrite provider fields even when they already match config.toml.
  --skip-backup        Skip 7zz backups. Live writes ignore catchable termination
                       signals from the first write through final validation.
  --no-prepare-bucket  Do not add first-line padding for faster future provider switches.
  --padding-bytes N    Padding bytes to reserve on session_meta first lines. Default: 256.
  -h, --help           Show this help.

Environment:
  CODEX_HOME           Codex state root. Defaults to $HOME/.codex.

Examples:
  ./codex-sync-model-provider.zsh --dry-run
  ./codex-sync-model-provider.zsh
  ./codex-sync-model-provider.zsh --yes
  ./codex-sync-model-provider.zsh --yes --force
  ./codex-sync-model-provider.zsh --dry-run --skip-backup
  ./codex-sync-model-provider.zsh --yes --skip-backup
  ./codex-sync-model-provider.zsh --yes --padding-bytes 512
USAGE
}

while (( $# > 0 )); do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --yes)
      YES=1
      ;;
    --force)
      FORCE=1
      ;;
    --skip-backup)
      SKIP_BACKUP=1
      ;;
    --no-prepare-bucket)
      PREPARE_BUCKET=0
      ;;
    --padding-bytes)
      shift
      [[ $# -gt 0 ]] || fail "--padding-bytes requires a positive integer."
      [[ "$1" == <-> ]] || fail "--padding-bytes requires a positive integer."
      (( $1 > 0 )) || fail "--padding-bytes requires a positive integer."
      PADDING_BYTES="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1"
      usage
      exit 2
      ;;
  esac
  shift
done

if [[ -n "${CODEX_HOME:-}" ]]; then
  codex_dir="${CODEX_HOME:A}"
else
  codex_dir="${HOME}/.codex"
fi
codex_dir="${codex_dir:A}"
config_file="$codex_dir/config.toml"
db_file="$codex_dir/state_5.sqlite"
db_base="state_5.sqlite"
sessions_dir="$codex_dir/sessions"
backup_root="$codex_dir/backups"

if (( ! DRY_RUN )); then
  ensure_no_pending_marker
fi

show_backup_location() {
  if [[ -n "${backup_dir:-}" ]]; then
    echo "Backup is here:"
    echo "  $backup_dir"
  else
    echo "No backup was created (--skip-backup was used)."
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 not found in PATH."
}

need_cmd sqlite3
need_cmd jq
if (( ! DRY_RUN && ! SKIP_BACKUP )); then
  need_cmd 7zz
fi
need_cmd awk
need_cmd grep
need_cmd date
need_cmd mkdir
need_cmd mktemp
need_cmd mv
need_cmd tail
need_cmd rm
need_cmd sort
need_cmd uniq
need_cmd chmod
need_cmd touch
need_cmd wc
need_cmd dd
need_cmd ps
[[ -x /usr/bin/stat ]] || fail "/usr/bin/stat is required for permission preflight."
STAT_CMD=/usr/bin/stat

escape_sqlite_string() {
  local value="$1"
  print -r -- "${value//\'/\'\'}"
}

is_text_compatible_type() {
  local declared_type="${(U)1}"
  [[ "$declared_type" == *CHAR* || "$declared_type" == *CLOB* || "$declared_type" == *TEXT* ]]
}

legacy_transcript_status() {
  local session_file="$1"
  local line=""
  local line_number=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line_number=$(( line_number + 1 ))

    if [[ -z "$line" ]]; then
      print -r -- "blank line $line_number"
      return
    fi

    if ! jq -e 'type == "object"' <<< "$line" >/dev/null 2>&1; then
      print -r -- "invalid JSON object on line $line_number"
      return
    fi

    if jq -e '.type == "session_meta"' <<< "$line" >/dev/null 2>&1; then
      print -r -- "session_meta already exists on line $line_number"
      return
    fi
  done < "$session_file"

  if (( line_number == 0 )); then
    print -r -- "empty transcript"
  else
    print -r -- "ok"
  fi
}

[[ -f "$config_file" ]] || skip "config.toml not found at: $config_file"
[[ -f "$db_file" ]] || skip "$db_base not found at: $db_file"

# Extract ONLY the root-level model_provider before the first TOML section.
# Ignores comments and ignores example/provider values lower in the file.
provider="$(
  awk '
    /^[[:space:]]*#/ { next }

    # Stop at first TOML section.
    /^[[:space:]]*\[/ { exit }

    /^[[:space:]]*model_provider[[:space:]]*=/ {
      line = $0
      sub(/^[[:space:]]*model_provider[[:space:]]*=[[:space:]]*/, "", line)

      # Quoted value: model_provider = "openai"
      if (match(line, /^"[^"]+"/)) {
        print substr(line, 2, RLENGTH - 2)
        exit
      }

      # Bare value fallback: model_provider = openai
      if (match(line, /^[A-Za-z0-9_.-]+/)) {
        print substr(line, RSTART, RLENGTH)
        exit
      }
    }
  ' "$config_file"
)"

[[ -n "$provider" ]] || skip "No root-level model_provider found in config.toml."

if ! print -r -- "$provider" | grep -Eq '^[A-Za-z0-9._-]+$'; then
  skip "Invalid/suspicious model_provider value: $provider"
fi

# Built-in provider does not need a [model_providers.openai] block.
# Custom providers should exist in config.toml.
if [[ "$provider" != "openai" ]]; then
  provider_block_found="$(
    awk -v target="[model_providers.$provider]" '
      /^[[:space:]]*#/ { next }
      {
        line = $0
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
        if (line == target) {
          print "yes"
          exit
        }
      }
    ' "$config_file"
  )"

  if [[ "$provider_block_found" != "yes" ]]; then
    skip "model_provider is '$provider', but [model_providers.$provider] was not found in config.toml."
  fi
fi

echo "Codex dir:       $codex_dir"
echo "Config file:     $config_file"
echo "Target DB:       $db_file"
echo "Target table:    threads"
echo "Target field:    model_provider"
echo "Sessions dir:    $sessions_dir"
echo "Target provider: $provider"
echo

if (( ! DRY_RUN )); then
  progress_emit_final_line "Working: Preflight (DB Checking)"
fi

# Basic DB health check.
quick_check="$(sqlite3 "$db_file" 'PRAGMA quick_check;' 2>/dev/null || true)"
if [[ "$quick_check" != "ok" ]]; then
  fail "SQLite quick_check did not return ok. Output: $quick_check"
fi

# Ensure the expected base table exists.
threads_exists="$(sqlite3 "$db_file" "SELECT name FROM sqlite_master WHERE type='table' AND name='threads';")"
[[ "$threads_exists" == "threads" ]] || fail "Expected table 'threads' was not found in $db_base."

if ! thread_columns="$(
  sqlite3 "$db_file" <<'SQL'
.mode list
.headers off
SELECT
  name || '|' ||
  COALESCE(type, '') || '|' ||
  COALESCE("notnull", 0) || '|' ||
  COALESCE(hidden, 0) || '|' ||
  COALESCE(pk, 0)
FROM pragma_table_xinfo('threads')
ORDER BY cid;
SQL
)"
then
  fail "Could not inspect threads with PRAGMA table_xinfo."
fi

typeset -A thread_columns_map_type
typeset -A thread_columns_map_notnull
typeset -A thread_columns_map_hidden
typeset -A thread_columns_map_pk

while IFS='|' read -r col_name col_type col_notnull col_hidden col_pk; do
  [[ -n "$col_name" ]] || continue
  thread_columns_map_type[$col_name]="$col_type"
  thread_columns_map_notnull[$col_name]="$col_notnull"
  thread_columns_map_hidden[$col_name]="$col_hidden"
  thread_columns_map_pk[$col_name]="$col_pk"
done <<< "$thread_columns"

required_columns=(
  id
  rollout_path
  model_provider
)

for req_column in "${required_columns[@]}"; do
  if [[ -z "${thread_columns_map_type[$req_column]-}" ]]; then
    fail "threads table contract mismatch: required column '$req_column' is missing."
  fi
  if ! is_text_compatible_type "${thread_columns_map_type[$req_column]}"; then
    fail "threads table contract mismatch: required column '$req_column' should be TEXT-compatible."
  fi
  if [[ "${thread_columns_map_hidden[$req_column]}" != "0" ]]; then
    fail "threads table contract mismatch: required column '$req_column' is a generated/hidden column."
  fi
done

has_threads_history_mode="${+thread_columns_map_type[history_mode]}"
has_threads_cwd="${+thread_columns_map_type[cwd]}"
has_threads_cli_version="${+thread_columns_map_type[cli_version]}"
has_threads_source="${+thread_columns_map_type[source]}"
has_threads_thread_source="${+thread_columns_map_type[thread_source]}"
has_threads_created_at="${+thread_columns_map_type[created_at]}"
has_threads_created_at_ms="${+thread_columns_map_type[created_at_ms]}"
has_threads_updated_at_ms="${+thread_columns_map_type[updated_at_ms]}"
has_threads_model="${+thread_columns_map_type[model]}"
has_threads_title="${+thread_columns_map_type[title]}"
legacy_schema_without_history=0

if (( ! has_threads_history_mode )); then
  migrations_table_exists="$(
    sqlite3 "$db_file" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='_sqlx_migrations';"
  )"

  if (( migrations_table_exists == 1 )); then
    if legacy_migration_probe="$(
      sqlite3 "$db_file" "SELECT CASE WHEN COUNT(version) > 0 AND MAX(version) < 40 THEN 1 ELSE 0 END FROM _sqlx_migrations;"
    )"; then
      legacy_schema_without_history="$legacy_migration_probe"
    fi
  fi
fi

provider_index_count="$(
  sqlite3 "$db_file" <<'SQL'
SELECT COUNT(*)
FROM pragma_index_list('threads') AS index_list
WHERE EXISTS (
  SELECT 1
  FROM pragma_index_info(index_list.name)
  WHERE name = 'model_provider'
);
SQL
)"

if (( provider_index_count == 0 )); then
  echo "WARNING: No threads index currently covers model_provider."
  echo "The update is still compatible, but provider queries may be slower."
  echo
fi

if ! provider_update_explain="$(
  sqlite3 "$db_file" <<'SQL'
PRAGMA query_only = ON;
EXPLAIN
UPDATE threads
SET model_provider = model_provider
WHERE 0;
SQL
)"; then
  fail "SQLite cannot compile a provider-only UPDATE against threads."
fi

if print -r -- "$provider_update_explain" | grep -Eq -- '(^|[|[:space:]])Program([|[:space:]]|$)|-- TRIGGER '; then
  echo "ERROR: SQLite would execute a trigger/program for a model_provider-only UPDATE."
  echo "Refusing the write because the provider update is not isolated:"
  print -r -- "$provider_update_explain" | grep -E -- '(^|[|[:space:]])Program([|[:space:]]|$)|-- TRIGGER ' | awk 'NR <= 20'
  exit 1
fi

echo "Schema contract: OK"
echo "Integrity check: OK"
echo

echo "Current model_provider counts:"
sqlite3 "$db_file" <<'SQL'
.headers on
.mode column
SELECT
  model_provider,
  COUNT(*) AS threads
FROM threads
GROUP BY model_provider
ORDER BY threads DESC;
SQL

invalid_threads_shape="$(
  sqlite3 "$db_file" <<'SQL'
SELECT COUNT(*)
FROM threads
WHERE typeof(id) <> 'text'
   OR length(id) = 0
   OR typeof(rollout_path) <> 'text'
   OR length(trim(rollout_path)) = 0
   OR typeof(model_provider) NOT IN ('text', 'null');
SQL
)"

if (( invalid_threads_shape > 0 )); then
  fail "SQLite threads contains rows with invalid id, rollout_path, or model_provider values."
fi

duplicate_thread_ids="$(
  sqlite3 "$db_file" <<'SQL'
SELECT COUNT(*)
FROM (
  SELECT id
  FROM threads
  GROUP BY id
  HAVING COUNT(*) > 1
);
SQL
)"

duplicate_rollout_paths="$(
  sqlite3 "$db_file" <<'SQL'
SELECT COUNT(*)
FROM (
  SELECT rollout_path
  FROM threads
  GROUP BY rollout_path
  HAVING COUNT(*) > 1
);
SQL
)"

if (( duplicate_thread_ids > 0 || duplicate_rollout_paths > 0 )); then
  fail "SQLite threads contains duplicate id or rollout_path values."
fi

session_files=()
session_files_to_update=()
session_files_missing_provider=()
session_files_changed_provider=()
session_files_forced_provider=()
session_files_to_insert=()
session_files_to_prepare=()
session_files_paginated=()
session_files_paginated_blocked=()
session_files_invalid=()
session_files_unexpected=()
session_files_missing_db=()
db_rollout_paths_missing=()
typeset -A session_files_update_map
typeset -A session_files_insert_map
typeset -A session_files_prepare_map
typeset -A session_db_id_map
typeset -A session_db_history_mode_map
typeset -A session_db_path_seen
typeset -A session_file_seen_map
typeset -A session_file_mode_map
typeset -A db_thread_id_seen
typeset -A session_first_line_map
typeset -A session_old_provider_map
typeset -A session_history_mode_map
typeset -A session_new_first_line_map
typeset -A session_old_first_line_bytes_map
typeset -A session_new_first_line_bytes_map
typeset -A session_write_mode_map
typeset -A session_change_mode_map

queue_session_update() {
  local session_file="$1"
  if [[ -z "${session_files_update_map[$session_file]-}" ]]; then
    session_files_to_update+=("$session_file")
    session_files_update_map[$session_file]=1
  fi
}

queue_session_prepare() {
  local session_file="$1"
  if [[ -z "${session_files_prepare_map[$session_file]-}" ]]; then
    session_files_to_prepare+=("$session_file")
    session_files_prepare_map[$session_file]=1
  fi
  queue_session_update "$session_file"
}

byte_len() {
  local value="$1"
  local bytes
  bytes="$(wc -c <<< "$value")"
  bytes="${bytes//[!0-9]/}"
  print -r -- $(( bytes - 1 ))
}

print_list_preview() {
  local array_name="$1"
  local max_items=$2
  local i
  local shown_count
  local -a items

  items=("${(@P)array_name}")

  (( max_items < 1 )) && max_items=20
  shown_count=${#items[@]}
  (( shown_count > max_items )) && shown_count=$max_items

  for (( i = 1; i <= shown_count; i++ )); do
    print -r -- "  ${items[i]}"
  done

  if (( ${#items[@]} > max_items )); then
    print -r -- "  ... and $(( ${#items[@]} - shown_count )) more entries."
  fi
}

if (( ! DRY_RUN )); then
  # Refuse real writes while Codex is active.
  # Codex can appear as node, codex.js, or the vendored codex binary, so check args.
  codex_processes="$(
    ps -axo pid=,comm=,args= | awk '
      /(^|[\/])(codex-)?sync-model-provider[.]zsh( |$)/ { next }
      /[\/]codex( |$)/ || /codex[.]js/ || /@openai[+]codex/ { print }
    '
  )"

  if [[ -n "$codex_processes" ]]; then
    echo
    echo "Codex appears to be running."
    echo "Close all Codex sessions first, then re-run this script."
    echo
    print -r -- "$codex_processes"
    exit 1
  fi

  setup_signal_traps
fi

if [[ -d "$sessions_dir" ]]; then
  session_files=("$sessions_dir"/**/*.jsonl(N))
fi

db_history_mode_expr="'__COLUMN_MISSING__'"
if (( has_threads_history_mode )); then
  db_history_mode_expr="CASE WHEN typeof(history_mode) = 'text' THEN history_mode ELSE '__INVALID__' END"
fi

while IFS=$'\t' read -r db_thread_id db_rollout_path db_history_mode; do
  if [[ -z "$db_thread_id" || -z "$db_rollout_path" ]]; then
    session_files_unexpected+=("SQLite returned an empty thread id or rollout path")
    continue
  fi

  if [[ -n "${db_thread_id_seen[$db_thread_id]-}" ]]; then
    session_files_unexpected+=("threads id $db_thread_id is duplicated in SQLite: ${db_thread_id_seen[$db_thread_id]} and $db_rollout_path")
    continue
  fi

  db_thread_id_seen[$db_thread_id]="$db_rollout_path"

  if [[ "$db_rollout_path" != "$sessions_dir"/* ]]; then
    session_files_unexpected+=("$db_rollout_path :: rollout_path is outside the expected sessions directory")
    continue
  fi

  if [[ -n "${session_db_path_seen[$db_rollout_path]-}" ]]; then
    session_files_unexpected+=("$db_rollout_path :: duplicate rollout_path in SQLite threads table")
    continue
  fi

  session_db_id_map[$db_rollout_path]="$db_thread_id"
  session_db_history_mode_map[$db_rollout_path]="$db_history_mode"
  session_db_path_seen[$db_rollout_path]=1

  if [[ ! -f "$db_rollout_path" ]]; then
    db_rollout_paths_missing+=("$db_rollout_path")
  fi
done < <(
  sqlite3 -separator $'\t' "$db_file" <<SQL
SELECT id, rollout_path, $db_history_mode_expr
FROM threads
ORDER BY rollout_path;
SQL
)

  session_scan_total="${#session_files[@]}"
  scanned_session_count=0
  if (( DRY_RUN )); then
    show_count_progress "Dry-run Scanning Sessions" 0 "$session_scan_total"
  else
    progress_emit_line "Working: Preflight (Sessions Checking 0/${session_scan_total})"
  fi

  for session_file in "${session_files[@]}"; do
    (( scanned_session_count += 1 ))
    if (( DRY_RUN )); then
      show_count_progress "Dry-run Scanning Sessions" "$scanned_session_count" "$session_scan_total"
    else
      progress_emit_line "Working: Preflight (Sessions Checking ${scanned_session_count}/${session_scan_total})"
    fi

    session_file_seen_map[$session_file]=1
    expected_thread_id="${session_db_id_map[$session_file]-}"

  if [[ -z "$expected_thread_id" ]]; then
    session_files_missing_db+=("$session_file")
    continue
  fi

  if [[ ! -s "$session_file" ]]; then
    session_files_unexpected+=("$session_file :: empty transcript cannot be repaired safely")
    continue
  fi

  IFS= read -r first_line < "$session_file" || first_line=""

  if ! session_status="$(
    jq -er --arg expected_id "$expected_thread_id" '
      if type != "object" then
        "__UNEXPECTED__: line 1 is " + type + ", not an object"
      elif .type != "session_meta" then
        "__NO_LINE1_META__"
      elif (.payload | type) != "object" then
        "__UNEXPECTED__: line 1 payload is " + (.payload | type)
      elif (.payload.id | type) != "string" then
        "__UNEXPECTED__: payload.id is " + (.payload.id | type)
      elif .payload.id != $expected_id then
        "__UNEXPECTED__: payload.id " + .payload.id + " does not match SQLite thread id " + $expected_id
      elif ((.payload | has("model_provider") | not) or .payload.model_provider == null) then
        "__MISSING__"
      elif (.payload.model_provider | type) != "string" then
        "__UNEXPECTED__: payload.model_provider is " + (.payload.model_provider | type)
      else
        "__PROVIDER__:" + .payload.model_provider
      end
    ' <<< "$first_line" 2>/dev/null
  )"; then
    session_files_invalid+=("$session_file")
    continue
  fi

  if [[ "$session_status" == "__NO_LINE1_META__" ]]; then
    legacy_status="$(legacy_transcript_status "$session_file")"
    if [[ "$legacy_status" != "ok" ]]; then
      session_files_unexpected+=("$session_file :: legacy repair blocked: $legacy_status")
      continue
    fi

    session_name="${session_file:t:r}"
    if [[ "$session_name" != rollout-????-??-??T??-??-??-* ]]; then
      session_files_unexpected+=("$session_file :: legacy repair cannot derive metadata from filename")
      continue
    fi

    session_stamp="${session_name#rollout-}"
    session_stamp="${session_stamp[1,19]}"
    filename_session_id="${session_name#rollout-$session_stamp-}"

    if ! print -r -- "$filename_session_id" | grep -Eq '^[A-Fa-f0-9-]+$'; then
      session_files_unexpected+=("$session_file :: legacy repair filename id is invalid")
      continue
    fi

    if [[ "$filename_session_id" != "$expected_thread_id" ]]; then
      session_files_unexpected+=("$session_file :: filename id $filename_session_id does not match SQLite thread id $expected_thread_id")
      continue
    fi

    db_history_mode="${session_db_history_mode_map[$session_file]-__INVALID__}"
    if [[ "$db_history_mode" == "__COLUMN_MISSING__" && "$legacy_schema_without_history" == "1" ]]; then
      db_history_mode="legacy"
    fi

    if [[ "$db_history_mode" != "legacy" ]]; then
      session_files_unexpected+=("$session_file :: legacy repair requires DB history_mode=legacy; found $db_history_mode")
      continue
    fi

    if (( ! has_threads_cwd || ! has_threads_cli_version )); then
      session_files_unexpected+=("$session_file :: legacy repair requires threads.cwd and threads.cli_version")
      continue
    fi

    if (( ! has_threads_source )); then
      session_files_unexpected+=("$session_file :: legacy repair requires threads.source to preserve primary/subagent identity")
      continue
    fi

    session_files_to_insert+=("$session_file")
    session_files_insert_map[$session_file]=1
    session_history_mode_map[$session_file]="legacy"
    session_first_line_map[$session_file]="$first_line"
    session_old_provider_map[$session_file]="missing-session_meta"
    queue_session_update "$session_file"
    continue
  fi

  if [[ "$session_status" == "__UNEXPECTED__:"* ]]; then
    session_files_unexpected+=("$session_file :: $session_status")
    continue
  fi

  json_history_mode="$(
    jq -r '
      if ((.payload | has("history_mode") | not) or .payload.history_mode == null) then
        "legacy"
      elif (.payload.history_mode | type) != "string" then
        "__INVALID__"
      elif .payload.history_mode == "legacy" or .payload.history_mode == "paginated" then
        .payload.history_mode
      else
        "__UNKNOWN__:" + .payload.history_mode
      end
    ' <<< "$first_line"
  )"

  if [[ "$json_history_mode" == "__INVALID__" || "$json_history_mode" == "__UNKNOWN__:"* ]]; then
    session_files_unexpected+=("$session_file :: unsupported payload.history_mode: $json_history_mode")
    continue
  fi

  db_history_mode="${session_db_history_mode_map[$session_file]-__INVALID__}"
  case "$db_history_mode" in
    "__COLUMN_MISSING__")
      effective_history_mode="$json_history_mode"
      ;;
    "legacy"|"paginated")
      if [[ "$db_history_mode" == "paginated" || "$json_history_mode" == "paginated" ]]; then
        effective_history_mode="paginated"
      else
        effective_history_mode="legacy"
      fi
      ;;
    *)
      session_files_unexpected+=("$session_file :: unsupported SQLite history_mode: $db_history_mode")
      continue
      ;;
  esac

  session_history_mode_map[$session_file]="$effective_history_mode"
  session_first_line_map[$session_file]="$first_line"
  if [[ "$session_status" == "__MISSING__" ]]; then
    session_old_provider_map[$session_file]="missing"
    session_files_missing_provider+=("$session_file")
    queue_session_update "$session_file"
  elif [[ "$session_status" == "__PROVIDER__:"* ]]; then
    current_session_provider="${session_status#__PROVIDER__:}"
    session_old_provider_map[$session_file]="$current_session_provider"
    if [[ "$current_session_provider" != "$provider" ]]; then
      session_files_changed_provider+=("$session_file")
      queue_session_update "$session_file"
    elif (( FORCE )); then
      session_files_forced_provider+=("$session_file")
      queue_session_update "$session_file"
    fi
  else
    session_files_unexpected+=("$session_file :: internal provider validation status was not recognized")
    continue
  fi

  rendered_first_line="$(
    jq -c --arg provider "$provider" '.payload.model_provider = $provider' <<< "$first_line"
  )"

  before_without_provider="$(jq -cS 'del(.payload.model_provider)' <<< "$first_line")"
  after_without_provider="$(jq -cS 'del(.payload.model_provider)' <<< "$rendered_first_line")"
  if [[ "$before_without_provider" != "$after_without_provider" ]]; then
    session_files_unexpected+=("$session_file :: provider render changed unrelated session metadata")
    continue
  fi

  current_first_line_bytes="$(byte_len "$first_line")"
  rendered_first_line_bytes="$(byte_len "$rendered_first_line")"

  if [[ "$effective_history_mode" == "paginated" ]]; then
    session_files_paginated+=("$session_file")
    if [[ -n "${session_files_update_map[$session_file]-}" ]] && (( rendered_first_line_bytes > current_first_line_bytes )); then
      session_files_paginated_blocked+=("$session_file :: provider render grows line 1 from $current_first_line_bytes to $rendered_first_line_bytes bytes")
    fi
  elif (( PREPARE_BUCKET )) && (( current_first_line_bytes < rendered_first_line_bytes + PADDING_BYTES )); then
    queue_session_prepare "$session_file"
  fi

  if [[ -n "${session_files_update_map[$session_file]-}" ]]; then
    if [[ -n "${session_files_prepare_map[$session_file]-}" ]]; then
      rendered_first_line="${rendered_first_line}$(printf '%*s' "$PADDING_BYTES" '')"
    fi
    session_new_first_line_map[$session_file]="$rendered_first_line"
  fi

done

  if (( DRY_RUN )); then
    progress_emit_final_line "Working: Dry-run Scanning Sessions (${scanned_session_count}/${session_scan_total})"
  else
    progress_emit_final_line "Working: Preflight (Sessions Checking ${scanned_session_count}/${session_scan_total})"
  fi
for db_rollout_path in "${(@k)session_db_id_map}"; do
  if [[ -z "${session_file_seen_map[$db_rollout_path]-}" ]]; then
    db_rollout_paths_missing+=("$db_rollout_path :: not found by the sessions JSONL scan")
  fi
done

if (( ${#session_files_invalid[@]} > 0 )); then
  echo
  echo "ERROR: Some session JSONL files have an invalid first line."
  echo "Refusing to rewrite session metadata until these are checked:"
  print_list_preview session_files_invalid 20
  exit 1
fi

if (( ${#session_files_missing_db[@]} > 0 )); then
  echo
  echo "ERROR: Some session JSONL files are not referenced by state_5.sqlite threads.rollout_path."
  echo "Refusing to rewrite session metadata until these are checked:"
  print_list_preview session_files_missing_db 20
  exit 1
fi

if (( ${#db_rollout_paths_missing[@]} > 0 )); then
  echo
  echo "ERROR: Some SQLite threads.rollout_path entries point to missing files."
  echo "Refusing to rewrite session metadata until these are checked:"
  print_list_preview db_rollout_paths_missing 20
  exit 1
fi

if (( ${#session_files_unexpected[@]} > 0 )); then
  echo
  echo "ERROR: Some session JSONL files do not have the expected first-line session metadata shape."
  echo "Refusing to rewrite session metadata until these are checked:"
  print_list_preview session_files_unexpected 20
  exit 1
fi

if (( ${#session_files_paginated_blocked[@]} > 0 )); then
  echo
  echo "ERROR: Some paginated sessions would require line-1 growth."
  echo "That would invalidate stored byte offsets, so no files or DB rows were changed:"
  print_list_preview session_files_paginated_blocked 20
  exit 1
fi

repair_thread_source_expr="'__COLUMN_MISSING__'"
if (( has_threads_thread_source )); then
  repair_thread_source_expr="CASE
    WHEN typeof(thread_source) = 'text' THEN thread_source
    WHEN thread_source IS NULL THEN '__NULL__'
    ELSE '__INVALID__'
  END"
fi

for session_file in "${session_files_to_insert[@]}"; do
  session_id="${session_db_id_map[$session_file]}"
  escaped_session_id="$(escape_sqlite_string "$session_id")"

  repair_row_valid="$(
    sqlite3 "$db_file" <<SQL
SELECT COUNT(*)
FROM threads
WHERE id = '$escaped_session_id'
  AND typeof(cwd) = 'text'
  AND typeof(cli_version) = 'text'
  AND typeof(source) = 'text'
  AND length(source) > 0;
SQL
  )"

  if (( repair_row_valid != 1 )); then
    fail "Legacy repair requires text cwd/cli_version/source values for thread $session_id."
  fi

  created_timestamp_expr="''"
  if (( has_threads_created_at_ms && has_threads_created_at )); then
    created_timestamp_expr="CASE
      WHEN typeof(created_at_ms) IN ('integer', 'real') THEN strftime('%Y-%m-%dT%H:%M:%fZ', created_at_ms / 1000.0, 'unixepoch')
      WHEN typeof(created_at) IN ('integer', 'real') THEN strftime('%Y-%m-%dT%H:%M:%fZ', created_at, 'unixepoch')
      ELSE ''
    END"
  elif (( has_threads_created_at_ms )); then
    created_timestamp_expr="CASE
      WHEN typeof(created_at_ms) IN ('integer', 'real') THEN strftime('%Y-%m-%dT%H:%M:%fZ', created_at_ms / 1000.0, 'unixepoch')
      ELSE ''
    END"
  elif (( has_threads_created_at )); then
    created_timestamp_expr="CASE
      WHEN typeof(created_at) IN ('integer', 'real') THEN strftime('%Y-%m-%dT%H:%M:%fZ', created_at, 'unixepoch')
      ELSE ''
    END"
  fi

  repair_separator=$'\x1f'
  db_insert_values="$(
    sqlite3 -separator "$repair_separator" "$db_file" <<SQL
SELECT cwd, cli_version, $created_timestamp_expr, source, $repair_thread_source_expr
FROM threads
WHERE id = '$escaped_session_id'
LIMIT 1;
SQL
  )"

  IFS="$repair_separator" read -r insert_cwd insert_cli_version db_session_timestamp insert_db_source insert_thread_source <<< "$db_insert_values"

  if parsed_db_source="$(jq -ce '.' <<< "$insert_db_source" 2>/dev/null)"; then
    parsed_db_source_type="$(jq -r 'type' <<< "$parsed_db_source")"
    case "$parsed_db_source_type" in
      object|string)
        repair_source_json="$parsed_db_source"
        ;;
      *)
        repair_source_json="$(jq -cn --arg source "$insert_db_source" '$source')"
        ;;
    esac
  else
    if print -r -- "$insert_db_source" | grep -Eq '^[[:space:]]*[\{\[\"]'; then
      fail "Legacy repair found malformed structured source metadata for thread $session_id."
    fi
    repair_source_json="$(jq -cn --arg source "$insert_db_source" '$source')"
  fi

  repair_source_type="$(jq -r 'type' <<< "$repair_source_json")"
  repair_source_has_subagent=0
  repair_parent_thread_id=""

  if [[ "$repair_source_type" == "object" ]] &&
     jq -e 'has("subagent")' <<< "$repair_source_json" >/dev/null 2>&1; then
    repair_source_has_subagent=1
    if ! repair_parent_thread_id="$(
      jq -er '
        .subagent
        | select(type == "object")
        | .thread_spawn
        | select(type == "object")
        | .parent_thread_id
        | select(type == "string" and length > 0)
      ' <<< "$repair_source_json"
    )"; then
      fail "Legacy repair found subagent source metadata without a valid parent_thread_id for thread $session_id."
    fi
  fi

  case "$insert_thread_source" in
    subagent)
      if (( ! repair_source_has_subagent )); then
        fail "Legacy repair found thread_source=subagent without matching source metadata for thread $session_id."
      fi
      ;;
    __COLUMN_MISSING__|__NULL__)
      ;;
    __INVALID__)
      fail "Legacy repair found a non-text thread_source for thread $session_id."
      ;;
    *)
      if (( repair_source_has_subagent )); then
        fail "Legacy repair found conflicting source/thread_source metadata for thread $session_id."
      fi
      ;;
  esac

  if (( repair_source_has_subagent )); then
    if [[ "$repair_parent_thread_id" == "$session_id" ]]; then
      fail "Legacy repair found a self-referencing subagent parent for thread $session_id."
    fi

    escaped_parent_thread_id="$(escape_sqlite_string "$repair_parent_thread_id")"
    repair_parent_row_count="$(
      sqlite3 "$db_file" "SELECT COUNT(*) FROM threads WHERE id = '$escaped_parent_thread_id';"
    )"
    if (( repair_parent_row_count != 1 )); then
      fail "Legacy repair could not verify parent thread $repair_parent_thread_id for subagent $session_id."
    fi
  fi

  session_name="${session_file:t:r}"
  session_stamp="${session_name#rollout-}"
  session_stamp="${session_stamp[1,19]}"
  session_timestamp="${session_stamp[1,13]}:${session_stamp[15,16]}:${session_stamp[18,19]}.000Z"
  if [[ "$db_session_timestamp" == ????-??-??T??:??:??*Z ]]; then
    session_timestamp="$db_session_timestamp"
  fi

  new_first_line="$(
    jq -cn \
      --arg timestamp "$session_timestamp" \
      --arg id "$session_id" \
      --arg cwd "$insert_cwd" \
      --arg cli_version "$insert_cli_version" \
      --arg provider "$provider" \
      --argjson source "$repair_source_json" \
      '{
        timestamp: $timestamp,
        type: "session_meta",
        payload: {
          session_id: $id,
          id: $id,
          timestamp: $timestamp,
          cwd: $cwd,
          originator: "legacy-repair",
          cli_version: $cli_version,
          source: $source,
          model_provider: $provider,
          history_mode: "legacy"
        }
      }'
  )"

  if (( PREPARE_BUCKET )); then
    new_first_line="${new_first_line}$(printf '%*s' "$PADDING_BYTES" '')"
  fi

  if ! jq -e \
    --arg id "$session_id" \
    --arg provider "$provider" \
    --argjson source "$repair_source_json" '
    type == "object"
    and .type == "session_meta"
    and (.payload | type) == "object"
    and .payload.session_id == $id
    and .payload.id == $id
    and .payload.originator == "legacy-repair"
    and .payload.source == $source
    and .payload.model_provider == $provider
    and .payload.history_mode == "legacy"
  ' <<< "$new_first_line" >/dev/null; then
    fail "Generated legacy session metadata did not validate for $session_file."
  fi

  session_new_first_line_map[$session_file]="$new_first_line"
done

preflight_update_total="${#session_files_to_update[@]}"
preflight_update_count=0
if (( ! DRY_RUN && preflight_update_total > 0 )); then
  progress_emit_line "Working: Preflight (Update Checking 0/${preflight_update_total})"
fi

for session_file in "${session_files_to_update[@]}"; do
  (( preflight_update_count += 1 ))
  if (( ! DRY_RUN )); then
    progress_emit_line "Working: Preflight (Update Checking ${preflight_update_count}/${preflight_update_total})"
  fi

  old_first_line="${session_first_line_map[$session_file]}"
  new_first_line="${session_new_first_line_map[$session_file]}"
  old_first_line_bytes="$(byte_len "$old_first_line")"
  new_first_line_bytes="$(byte_len "$new_first_line")"

  write_mode="rewrite"
  if [[ -z "${session_files_insert_map[$session_file]-}" ]] && (( new_first_line_bytes <= old_first_line_bytes )); then
    write_mode="in_place_first_line"
  fi

  if [[ "${session_history_mode_map[$session_file]}" == "paginated" && "$write_mode" != "in_place_first_line" ]]; then
    session_files_paginated_blocked+=("$session_file :: paginated session cannot use a growing rewrite")
    continue
  fi

  file_mode="$("$STAT_CMD" -f %Lp "$session_file" 2>/dev/null || true)"
  if ! print -r -- "$file_mode" | grep -Eq '^[0-7]{3,4}$'; then
    session_files_unexpected+=("$session_file :: /usr/bin/stat returned an invalid permission mode: ${file_mode:-<empty>}")
    continue
  fi

  if [[ ! -w "$session_file" ]]; then
    session_files_unexpected+=("$session_file :: session file is not writable")
    continue
  fi

  if [[ "$write_mode" == "rewrite" && ! -w "${session_file:h}" ]]; then
    session_files_unexpected+=("$session_file :: parent directory is not writable for atomic replacement")
    continue
  fi

  change_mode="update_provider"
  if [[ -n "${session_files_insert_map[$session_file]-}" ]]; then
    change_mode="insert_session_meta"
  elif [[ -n "${session_files_prepare_map[$session_file]-}" && "${session_old_provider_map[$session_file]}" != "$provider" ]]; then
    change_mode="update_provider_with_padding"
  elif (( FORCE )) && [[ -n "${session_files_prepare_map[$session_file]-}" ]]; then
    change_mode="force_provider_rewrite_with_padding"
  elif [[ -n "${session_files_prepare_map[$session_file]-}" ]]; then
    change_mode="prepare_padding"
  elif (( FORCE )) && [[ "${session_old_provider_map[$session_file]}" == "$provider" ]]; then
    change_mode="force_provider_rewrite"
  elif [[ "${session_old_provider_map[$session_file]}" == "missing" ]]; then
    change_mode="add_provider"
  fi

  session_file_mode_map[$session_file]="$file_mode"
  session_old_first_line_bytes_map[$session_file]="$old_first_line_bytes"
  session_new_first_line_bytes_map[$session_file]="$new_first_line_bytes"
  session_write_mode_map[$session_file]="$write_mode"
  session_change_mode_map[$session_file]="$change_mode"
done

if (( ! DRY_RUN && preflight_update_total > 0 )); then
  progress_emit_final_line "Working: Preflight (Update Checking ${preflight_update_count}/${preflight_update_total})"
fi

if (( ${#session_files_paginated_blocked[@]} > 0 )); then
  echo
  echo "ERROR: Paginated session safety preflight failed:"
  print_list_preview session_files_paginated_blocked 20
  exit 1
fi

if (( ${#session_files_unexpected[@]} > 0 )); then
  echo
  echo "ERROR: Session write preflight failed:"
  print_list_preview session_files_unexpected 20
  exit 1
fi

if (( FORCE )); then
  db_provider_where="1 = 1"
else
  db_provider_where="model_provider IS NULL OR model_provider <> '$provider'"
fi

if ! sqlite3 "$db_file" >/dev/null <<SQL
PRAGMA query_only = ON;
EXPLAIN
UPDATE threads
SET model_provider = '$provider'
WHERE hex(id) = '00' AND ($db_provider_where);
SQL
then
  fail "SQLite could not compile the intended provider UPDATE: $db_provider_where"
fi

rows_to_update="$(
  sqlite3 "$db_file" <<SQL
SELECT COUNT(*)
FROM threads
WHERE $db_provider_where;
SQL
)"

typeset -a db_rows_to_update=()
if (( rows_to_update > 0 )); then
  db_rows_to_update=("${(@f)$(sqlite3 -separator $'\t' "$db_file" <<SQL
SELECT hex(id)
FROM threads
WHERE $db_provider_where
ORDER BY id;
SQL
)}")
fi

if (( rows_to_update != ${#db_rows_to_update[@]} )); then
  fail "SQLite provider-update row count drifted between count and id collection."
fi

echo
if (( FORCE )); then
  echo "Rows that would be overwritten to '$provider': $rows_to_update"
else
  echo "Rows that would be changed to '$provider': $rows_to_update"
fi

echo
echo "Session metadata files scanned: ${#session_files[@]}"
echo "Session files needing provider change: ${#session_files_changed_provider[@]}"
if (( FORCE )); then
  echo "Session files forced provider rewrite: ${#session_files_forced_provider[@]}"
fi
echo "Session files missing provider field:  ${#session_files_missing_provider[@]}"
echo "Session files missing session_meta:    ${#session_files_to_insert[@]}"
echo "Paginated session files scanned:       ${#session_files_paginated[@]}"
if (( PREPARE_BUCKET )); then
  echo "Session files needing bucket padding:  ${#session_files_to_prepare[@]}"
else
  echo "Session bucket padding:               disabled"
fi
echo "Session files that would be updated:  ${#session_files_to_update[@]}"

if (( rows_to_update == 0 && ${#session_files_to_update[@]} == 0 )); then
  echo "No changes needed."
  if (( DRY_RUN )); then
    echo "Dry run complete. No DB or session file changes were made."
  fi
  exit 0
fi

if (( DRY_RUN )); then
  echo
  echo "Dry-run plan:"
  echo "  DB rows to update: ${rows_to_update}"
  echo "  Session files to update: ${#session_files_to_update[@]}"
  if (( SKIP_BACKUP )); then
    echo "  Backup: skipped (--skip-backup)"
  else
    echo "  Backup directory: $codex_dir/backups"
    if (( rows_to_update > 0 )); then
      echo "  DB archive: 1 (rows would change)"
    else
      echo "  DB archive: 0 (no DB rows to update)"
    fi
    if [[ -d "$sessions_dir" ]]; then
      echo "  Sessions archive: 1 (sessions folder exists)"
    else
      echo "  Sessions archive: 0 (sessions folder missing)"
    fi
  fi
  echo
  echo "Dry run complete. No DB or session file changes were made."
  exit 0
fi

if (( rows_to_update > 0 )); then
  echo
  if (( FORCE )); then
    echo "Values that would be overwritten in SQLite:"
  else
    echo "Values that would be changed in SQLite:"
  fi
  sqlite3 "$db_file" <<SQL
.headers on
.mode column
SELECT
  model_provider AS old_provider,
  '$provider' AS new_provider,
  COUNT(*) AS rows
FROM threads
WHERE $db_provider_where
GROUP BY model_provider
ORDER BY rows DESC;
SQL

  echo
  if (( FORCE )); then
    echo "Recent SQLite rows that would be overwritten:"
  else
    echo "Recent SQLite rows that would be changed:"
  fi

if (( has_threads_updated_at_ms && has_threads_model && has_threads_cwd && has_threads_title )); then
  sqlite3 "$db_file" <<SQL
.headers on
.mode column
SELECT
  datetime(updated_at_ms / 1000, 'unixepoch', 'localtime') AS updated,
  model_provider,
  model,
  substr(cwd, 1, 42) AS cwd,
  substr(title, 1, 55) AS title
FROM threads
WHERE $db_provider_where
ORDER BY updated_at_ms DESC
LIMIT 10;
SQL
else
  sqlite3 "$db_file" <<SQL
.headers on
.mode column
SELECT
  substr(id, 1, 36) AS id,
  model_provider,
  substr(rollout_path, 1, 70) AS rollout_path
FROM threads
WHERE $db_provider_where
ORDER BY id DESC
LIMIT 10;
SQL
fi
fi

if (( ${#session_files_to_update[@]} > 0 )); then
  echo
  echo "Recent session metadata files that would be updated:"
  recent_start=$(( ${#session_files_to_update[@]} - 9 ))
  (( recent_start < 1 )) && recent_start=1
  for (( recent_i = recent_start; recent_i <= ${#session_files_to_update[@]}; recent_i++ )); do
    print -r -- "${session_files_to_update[$recent_i]}"
  done
fi

if (( ! YES )); then
  echo
  echo "About to update ONLY these persisted provider fields:"
  echo "  DB:            $db_file"
  echo "  DB table:      threads"
  echo "  DB field:      model_provider"
  echo "  DB rows:       $rows_to_update"
  echo "  Session files: ${#session_files_to_update[@]}"
  echo "  JSON field:    first-line payload.model_provider"
  if (( SKIP_BACKUP )); then
    echo "  Backup:        skipped"
  else
    echo "  Backup:        7zz archives under $codex_dir/backups"
    echo "                 Full sessions folder; DB archive only when DB rows will change"
    echo "  Journal:       session-changes.jsonl in backup folder"
  fi
  echo
  echo -n "Continue? [y/N] "
  read -k 1 reply || reply=""
  echo

  case "${reply:l}" in
    y)
      ;;
    *)
      echo "Not confirmed. No changes were made."
      exit 0
      ;;
  esac
fi

scratch_dir="$codex_dir/tmp/sync-model-provider"
mkdir -p "$scratch_dir"
if (( ${#session_files_to_update[@]} > 0 )); then
  final_preflight_total="${#session_files_to_update[@]}"
  final_preflight_count=0
  progress_emit_line "Working: Preflight (Final Checking 0/${final_preflight_total})"

  for session_file in "${session_files_to_update[@]}"; do
    IFS= read -r current_first_line < "$session_file" || current_first_line=""
    if [[ "$current_first_line" != "${session_first_line_map[$session_file]}" ]]; then
      fail "Session changed after planning; re-run instead of writing: $session_file"
    fi

    current_file_mode="$("$STAT_CMD" -f %Lp "$session_file" 2>/dev/null || true)"
    if [[ "$current_file_mode" != "${session_file_mode_map[$session_file]}" ]]; then
      fail "Session permissions changed after preflight; re-run instead of writing: $session_file"
    fi

    (( final_preflight_count += 1 ))
    progress_emit_line "Working: Preflight (Final Checking ${final_preflight_count}/${final_preflight_total})"
  done

  progress_emit_final_line "Working: Preflight (Final Checking ${final_preflight_count}/${final_preflight_total})"
fi

if (( SKIP_BACKUP )); then
  echo
  echo "Backup skipped by --skip-backup."
  echo
else
  backup_root="$codex_dir/backups"
  backup_date="$(date +%Y-%m-%d)"
  backup_dir="$backup_root/model-provider-sync-$backup_date"
  backup_work_dir=""
  backup_start_dir="$PWD"

  if [[ -e "$backup_dir" ]]; then
    backup_dir="$backup_root/model-provider-sync-$(date +%Y-%m-%d-%H%M%S)"
  fi

  if [[ -e "$backup_dir" ]]; then
    fail "Backup directory already exists even with time suffix: $backup_dir"
  fi

  mkdir -p "$backup_root" || fail "Could not create backup root: $backup_root"
  phase="backup_partial"
  backup_work_dir="$(mktemp -d "$backup_root/.model-provider-sync.XXXXXX")" ||
    fail "Could not create a unique backup work directory."

  track_db_backup=0
  track_session_backup=0
  if [[ -d "$sessions_dir" ]]; then
    track_session_backup=1
  elif (( rows_to_update > 0 )); then
    track_db_backup=1
  fi

  backup_started_at=0
  if (( track_db_backup || track_session_backup )); then
    backup_started_at="$(progress_now_sec)"
    progress_emit_line "Working: Backup (0% | ETA calculating...)"
  fi

  if (( rows_to_update > 0 )); then
    backup_db_has_wal=0
    backup_db_has_shm=0
    [[ -f "$db_file-wal" ]] && backup_db_has_wal=1
    [[ -f "$db_file-shm" ]] && backup_db_has_shm=1
  fi

  if ! cd "$codex_dir"; then
    remove_backup_run_dir "$backup_work_dir" || true
    fail "Could not enter Codex directory for backup: $codex_dir"
  fi

  db_backup_files=()
  if (( rows_to_update > 0 )); then
    db_backup_files=(config.toml(N))
    [[ -f "$db_base" ]] && db_backup_files+=("$db_base")
    [[ -f "${db_base}-wal" ]] && db_backup_files+=("${db_base}-wal")
    [[ -f "${db_base}-shm" ]] && db_backup_files+=("${db_base}-shm")

    if [[ ! -f "$db_base" ]]; then
      cd "$backup_start_dir" 2>/dev/null || true
      remove_backup_run_dir "$backup_work_dir" || true
      fail "Target DB disappeared before backup."
    fi

    if ! run_7zz_archive_with_progress \
      "$backup_work_dir/codex-dbs.7z" \
      "$track_db_backup" \
      "$backup_started_at" \
      "${db_backup_files[@]}"; then
      cd "$backup_start_dir" 2>/dev/null || true
      remove_backup_run_dir "$backup_work_dir" || true
      fail "7zz failed while creating the DB backup."
    fi

    if ! verify_7zz_archive "$backup_work_dir/codex-dbs.7z" db; then
      cd "$backup_start_dir" 2>/dev/null || true
      remove_backup_run_dir "$backup_work_dir" || true
      fail "DB backup verification failed."
    fi
  fi

  if [[ -d sessions ]]; then
    if ! run_7zz_archive_with_progress \
      "$backup_work_dir/sessions.7z" \
      "$track_session_backup" \
      "$backup_started_at" \
      sessions; then
      cd "$backup_start_dir" 2>/dev/null || true
      remove_backup_run_dir "$backup_work_dir" || true
      fail "7zz failed while creating the sessions backup."
    fi

    if ! verify_7zz_archive "$backup_work_dir/sessions.7z" sessions; then
      cd "$backup_start_dir" 2>/dev/null || true
      remove_backup_run_dir "$backup_work_dir" || true
      fail "Sessions backup verification failed."
    fi
  fi

  if ! cd "$backup_start_dir"; then
    remove_backup_run_dir "$backup_work_dir" || true
    fail "Could not return to the original directory after backup."
  fi

  progress_active_line=0
  progress_last_line_render_sec=0

  if ! mv "$backup_work_dir" "$backup_dir"; then
    remove_backup_run_dir "$backup_work_dir" || true
    fail "Could not move backup directory into final location."
  fi

  backup_work_dir=""
  backup_verified=1
  phase="backup_verified"

  if ! test_checkpoint "after_backup_verified"; then
    remove_backup_run_dir "$backup_dir" || true
    fail "Fixture-requested failure after backup verification."
  fi

  echo
  echo "Backup created:"
  echo "  $backup_dir"
  if (( rows_to_update > 0 )); then
    echo "  $backup_dir/codex-dbs.7z"
  else
    echo "  DB archive skipped: no DB rows need changing"
  fi
  if [[ -d "$sessions_dir" ]]; then
    echo "  $backup_dir/sessions.7z"
  else
    echo "  Sessions archive skipped: sessions folder not found"
  fi
  if (( ${#session_files_to_update[@]} > 0 )); then
    journal_file="$backup_dir/session-changes.jsonl"
    echo "  $journal_file"
  fi
  echo
fi

if (( rows_to_update > 0 || ${#session_files_to_update[@]} > 0 )); then
  if (( SKIP_BACKUP )); then
    trap '' INT TERM HUP QUIT
    echo "Catchable signals are now ignored until unbacked sync validation completes."
  else
    if ! set_restore_marker "$backup_dir"; then
      remove_backup_run_dir "$backup_dir" || true
      fail "Could not create the durable recovery marker."
    fi
  fi
  sync_started=1
  phase="syncing"
  if ! test_checkpoint "after_recovery_marker"; then
    sync_failure "Fixture-requested failure after recovery marker creation."
  fi
fi

if (( ${#session_files_to_update[@]} > 0 )); then
  session_write_total="${#session_files_to_update[@]}"
  session_write_done=0
  show_count_progress "Sessions Syncing" 0 "$session_write_total"
  for session_file in "${session_files_to_update[@]}"; do
    session_file_mode="${session_file_mode_map[$session_file]-}"
    session_old_first_line="${session_first_line_map[$session_file]-}"
    session_new_first_line="${session_new_first_line_map[$session_file]-}"
    session_old_provider="${session_old_provider_map[$session_file]-missing}"
    session_old_first_line_bytes="${session_old_first_line_bytes_map[$session_file]-0}"
    session_new_first_line_bytes="${session_new_first_line_bytes_map[$session_file]-0}"
    session_write_mode="${session_write_mode_map[$session_file]-rewrite}"
    session_change_mode="${session_change_mode_map[$session_file]-update_provider}"
    session_thread_id="${session_db_id_map[$session_file]-}"
    session_history_mode="${session_history_mode_map[$session_file]-legacy}"

    if [[ -z "$session_file_mode" ]]; then
      sync_failure "Could not determine session file mode for write plan: $session_file"
    fi
    if [[ -z "$session_thread_id" ]]; then
      sync_failure "Missing thread id while applying session write: $session_file"
    fi
    if [[ -z "$session_new_first_line" ]]; then
      sync_failure "Missing replacement first line while applying session write: $session_file"
    fi

    timestamp_marker="$scratch_dir/sync-model-provider-time.$$.$RANDOM"
    if ! : > "$timestamp_marker"; then
      sync_failure "Could not create timestamp marker for: $session_file"
    fi
    if ! touch -r "$session_file" "$timestamp_marker"; then
      rm -f -- "$timestamp_marker" 2>/dev/null || true
      sync_failure "Could not preserve the timestamp for: $session_file"
    fi
    patch_file=""

    if [[ "$session_write_mode" == "in_place_first_line" ]]; then
      pad_to_old=$(( session_old_first_line_bytes - session_new_first_line_bytes ))
      if (( pad_to_old < 0 )); then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Session write would grow first-line bytes in-place: $session_file"
      fi

      patch_file="$scratch_dir/sync-model-provider-line.$$.$RANDOM"
      if ! printf '%s%*s\n' "$session_new_first_line" "$pad_to_old" '' > "$patch_file"; then
        rm -f -- "$patch_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not prepare the in-place line patch for: $session_file"
      fi
      if ! patch_file_bytes="$(wc -c < "$patch_file")"; then
        rm -f -- "$patch_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not measure the prepared line patch for: $session_file"
      fi
      patch_file_bytes="${patch_file_bytes//[!0-9]/}"
      if (( patch_file_bytes != session_old_first_line_bytes + 1 )); then
        rm -f -- "$patch_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "Prepared line patch has the wrong byte length for: $session_file"
      fi
      dd if="$patch_file" of="$session_file" bs=1 seek=0 conv=notrunc >/dev/null 2>&1 || {
        rm -f -- "$patch_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "dd write failed for session file: $session_file"
      }
      rm -f -- "$patch_file" 2>/dev/null || true
    else
      tmp_file="$scratch_dir/sync-model-provider-rewrite.$$.$RANDOM"
      if [[ "$session_change_mode" == "insert_session_meta" ]]; then
        if ! {
          print -r -- "$session_new_first_line"
          tail -n +1 "$session_file"
        } > "$tmp_file"; then
          rm -f -- "$tmp_file" "$timestamp_marker" 2>/dev/null || true
          sync_failure "Could not build the repaired session file: $session_file"
        fi
      else
        if ! {
          print -r -- "$session_new_first_line"
          tail -n +2 "$session_file"
        } > "$tmp_file"; then
          rm -f -- "$tmp_file" "$timestamp_marker" 2>/dev/null || true
          sync_failure "Could not build the updated session file: $session_file"
        fi
      fi

      if ! chmod "$session_file_mode" "$tmp_file"; then
        rm -f -- "$tmp_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not set the staged session mode for: $session_file"
      fi
      if ! touch -r "$timestamp_marker" "$tmp_file"; then
        rm -f -- "$tmp_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not set the staged session timestamp for: $session_file"
      fi
      if ! mv "$tmp_file" "$session_file"; then
        rm -f -- "$tmp_file" "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not atomically replace the session file: $session_file"
      fi
    fi

    if ! chmod "$session_file_mode" "$session_file"; then
      rm -f -- "$timestamp_marker" 2>/dev/null || true
      sync_failure "Could not restore the session mode for: $session_file"
    fi
    if ! touch -r "$timestamp_marker" "$session_file"; then
      rm -f -- "$timestamp_marker" 2>/dev/null || true
      sync_failure "Could not restore the session timestamp for: $session_file"
    fi
    if [[ -n "$journal_file" ]]; then
      if ! jq -cn \
        --arg path "$session_file" \
        --arg thread_id "$session_thread_id" \
        --arg mode "$session_change_mode" \
        --arg write_mode "$session_write_mode" \
        --arg old_provider "$session_old_provider" \
        --arg new_provider "$provider" \
        --argjson old_first_line_bytes "$session_old_first_line_bytes" \
        --argjson new_first_line_bytes "$session_new_first_line_bytes" \
        '{
          path: $path,
          thread_id: $thread_id,
          mode: $mode,
          write_mode: $write_mode,
          old_provider: $old_provider,
          new_provider: $new_provider,
          old_first_line_bytes: $old_first_line_bytes,
          new_first_line_bytes: $new_first_line_bytes
        }' >> "$journal_file"; then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not append the backup journal for: $session_file"
      fi
    fi

    IFS= read -r actual_first_line < "$session_file" || actual_first_line=""
    if [[ "$session_change_mode" == "insert_session_meta" ]]; then
      if ! jq -e --arg id "$session_thread_id" --arg provider "$provider" --arg history_mode "$session_history_mode" '
        type == "object"
        and .type == "session_meta"
        and (.payload | type) == "object"
        and .payload.id == $id
        and .payload.session_id == $id
        and .payload.model_provider == $provider
        and .payload.originator == "legacy-repair"
        and .payload.history_mode == $history_mode
      ' <<< "$actual_first_line" >/dev/null; then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Inserted session metadata did not validate for: $session_file"
      fi
    else
      if ! jq -e --arg provider "$provider" '
        type == "object"
        and .type == "session_meta"
        and (.payload | type) == "object"
        and .payload.model_provider == $provider
      ' <<< "$actual_first_line" >/dev/null; then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Updated session metadata did not validate for: $session_file"
      fi

      if ! before_without_provider="$(jq -cS 'del(.payload.model_provider)' <<< "$session_old_first_line")"; then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not revalidate old session metadata for: $session_file"
      fi
      if ! after_without_provider="$(jq -cS 'del(.payload.model_provider)' <<< "$actual_first_line")"; then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Could not revalidate updated session metadata for: $session_file"
      fi
      if [[ "$before_without_provider" != "$after_without_provider" ]]; then
        rm -f -- "$timestamp_marker" 2>/dev/null || true
        sync_failure "Session metadata payload drifted beyond model_provider for: $session_file"
      fi
    fi

    (( session_write_done += 1 ))
    show_count_progress "Sessions Syncing" "$session_write_done" "$session_write_total"

    rm -f -- "$timestamp_marker" 2>/dev/null || true
    if ! test_checkpoint "after_session_${session_write_done}"; then
      sync_failure "Fixture-requested failure after session $session_write_done."
    fi
  done
  if (( session_write_total > 0 )); then
    progress_emit_final_line "Working: Sessions Syncing (${session_write_done}/${session_write_total})"
  fi
fi

if (( rows_to_update > 0 )); then
  db_update_total="$rows_to_update"
  db_update_sql_file=""

  show_count_progress "DB Syncing" 0 "$db_update_total"

  db_update_sql_file="$scratch_dir/sync-model-provider-db-update.$$.$RANDOM.sql"
  if ! {
    print ".bail on"
    print "PRAGMA busy_timeout = 5000;"
    print "PRAGMA foreign_keys = ON;"
    print "BEGIN IMMEDIATE;"
    print "CREATE TEMP TABLE sync_model_provider_guard (changed INTEGER NOT NULL CHECK (changed = 1));"

    for db_update_hex_id in "${db_rows_to_update[@]}"; do
      print "UPDATE threads"
      print "SET model_provider = '$provider'"
      print "WHERE hex(id) = '$db_update_hex_id' AND ($db_provider_where);"
      print "SELECT '__DB_UPDATE_DONE__:' || changes();"
      print "INSERT INTO sync_model_provider_guard(changed) VALUES (changes());"
      print "DELETE FROM sync_model_provider_guard;"
    done

    print "COMMIT;"
    print "PRAGMA wal_checkpoint(FULL);"
    print "SELECT '__DB_COMMIT_DONE__';"
  } > "$db_update_sql_file"; then
    rm -f -- "$db_update_sql_file" 2>/dev/null || true
    sync_failure "Could not prepare the SQLite update transaction."
  fi

  if ! test_checkpoint "before_db_sync"; then
    rm -f -- "$db_update_sql_file" 2>/dev/null || true
    sync_failure "Fixture-requested failure before DB sync."
  fi

  if ! run_sqlite_updates_with_progress "$db_update_total" "$db_update_sql_file" 1 0; then
    rm -f -- "$db_update_sql_file" 2>/dev/null || true
    sync_failure "SQLite update failed while persisting model_provider."
  fi
  rm -f -- "$db_update_sql_file" 2>/dev/null || true

  if ! test_checkpoint "after_db_sync"; then
    sync_failure "Fixture-requested failure after DB sync."
  fi

  progress_emit_final_line "Working: DB Syncing (${db_update_total}/${db_update_total})"

fi

if ! test_checkpoint "before_post_check"; then
  sync_failure "Fixture-requested failure before post-update validation."
fi

post_check="$(sqlite3 "$db_file" 'PRAGMA quick_check;' 2>/dev/null || true)"
if [[ "$post_check" != "ok" ]]; then
  echo "WARNING: Post-update quick_check did not return ok."
  echo "Output: $post_check"
  echo
  show_backup_location
  sync_failure "Post-update quick_check did not return ok."
fi

if (( rows_to_update > 0 )); then
  db_validation_id_list=""
  for db_validation_hex_id in "${db_rows_to_update[@]}"; do
    [[ -z "$db_validation_id_list" ]] || db_validation_id_list+=","
    db_validation_id_list+="'$db_validation_hex_id'"
  done
  db_validation_count="$(
    sqlite3 "$db_file" <<SQL
SELECT COUNT(*)
FROM threads
WHERE hex(id) IN ($db_validation_id_list)
  AND model_provider = '$provider';
SQL
  )" || sync_failure "Could not validate the updated SQLite provider rows."

  if [[ "$db_validation_count" != <-> ]]; then
    sync_failure "Post-update SQLite validation returned a non-numeric row count."
  fi
  if (( db_validation_count != rows_to_update )); then
    sync_failure "Post-update SQLite validation found only $db_validation_count of $rows_to_update expected provider rows."
  fi
fi

if ! test_checkpoint "after_post_check"; then
  sync_failure "Fixture-requested failure after post-update validation."
fi

if (( session_write_total > 0 || rows_to_update > 0 )); then
  phase="post_sync"
  trap '' INT TERM HUP QUIT
  if (( ! SKIP_BACKUP )); then
    if ! remove_restore_marker; then
      sync_failure "The sync validated, but its recovery marker could not be removed."
    fi
  fi
  restore_marker_path=""
  sync_started=0
  phase="complete"
fi
clear_signal_traps

echo "Update complete."
echo

echo "New model_provider counts:"
sqlite3 "$db_file" <<'SQL'
.headers on
.mode column
SELECT
  model_provider,
  COUNT(*) AS threads
FROM threads
GROUP BY model_provider
ORDER BY threads DESC;
SQL

if [[ -d "$sessions_dir" ]]; then
  echo
  echo "New session_meta model_provider counts:"
  for session_file in "$sessions_dir"/**/*.jsonl(N); do
    IFS= read -r first_line < "$session_file" || first_line=""
    jq -r '
      if .type == "session_meta" and (.payload | type) == "object" then
        (.payload.model_provider // "missing")
      else
        "not-session-meta"
      end
    ' <<< "$first_line" 2>/dev/null || print -r -- "invalid-json"
  done | sort | uniq -c
fi

echo
echo "Done."
