# codex-sync-model-provider.zsh

[`codex-sync-model-provider.zsh`](../shell/codex-sync-model-provider.zsh) is a macOS-only utility that synchronizes the root-level Codex `model_provider` setting into persisted thread and session metadata.

It updates only:

```text
state_5.sqlite
  threads.model_provider

sessions/**/*.jsonl
  first-line session_meta.payload.model_provider
```

It does not change the selected model, transcript events, prompts, tool calls, worker roles, or subagent parent links.

## Codex root and environment

The script resolves the Codex state root in this order:

1. `CODEX_HOME`, when it is set.
2. `$HOME/.codex` otherwise.

The normal macOS default therefore resolves to:

```text
/Users/your-name/.codex
```

`CODEX_HOME` is an **environment variable**, not a CLI flag.

Codex documents `CODEX_HOME` as the root for config, sessions, skills, logs, and other local state, with `~/.codex` as its default. See [Config and state locations](https://learn.chatgpt.com/docs/config-file/config-advanced#config-and-state-locations).

Use another Codex root explicitly:

```zsh
CODEX_HOME="/path/to/codex-home" \
  zsh shell/codex-sync-model-provider.zsh --dry-run
```

The script uses these paths under the resolved root:

```text
<resolved-codex-root>/config.toml
<resolved-codex-root>/state_5.sqlite
<resolved-codex-root>/sessions
<resolved-codex-root>/backups
```

`config.toml` and `state_5.sqlite` must already exist. The `sessions` directory is
scanned when present, and the `backups` directory is created when a backed live
run needs it.

An empty `CODEX_HOME` is treated as unset and falls back to `$HOME/.codex`. If
`config.toml` or `state_5.sqlite` is missing, execution prints `SKIP:` and exits
`0`.

Codex also supports placing SQLite-backed state elsewhere with
`CODEX_SQLITE_HOME` or the higher-precedence root-level `sqlite_home`
configuration key; see [Core location environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables#core-locations).
This script resolves the effective SQLite directory with the following
precedence:

1. A valid root-level `sqlite_home` in `config.toml`.
2. A nonempty `CODEX_SQLITE_HOME`.
3. The resolved `CODEX_HOME` root.

Relative values resolve from the invocation working directory. The script still
targets `<resolved-codex-root>/state_5.sqlite`; when the effective SQLite
directory differs from the resolved Codex root, it fails closed and reports the
source, raw value, resolved directory, effective DB path, and supported script
DB path. It never redirects to an alternate DB, so keep the effective SQLite
directory equal to the Codex root for this utility.

The script alias is defined in:

```zsh
$ZSH_CUSTOM/alias.zsh
```

After updating the alias file, use a fresh shell or:

```zsh
source "$ZSH_CUSTOM/alias.zsh"
```

`codex-sync` is preferred, while direct script invocation remains available as the portable fallback:

```zsh
zsh shell/codex-sync-model-provider.zsh --dry-run
```

## Requirements

- macOS
- zsh
- `sqlite3`
- `jq`
- native `ps` for live active-process checks
- native `sleep` for bounded signal/recovery waits
- native `lsof` when using `--unlock`
- `7zz` for normal backed live runs
- `/usr/bin/stat` for permission checks and preservation

Homebrew can provide the non-native dependencies:

```zsh
brew install jq sevenzip
```

Live runs check for active Codex processes early and again immediately before
the first production filesystem mutation. Close the Codex app, CLI, IDE
sessions, workers, and subagents before live execution. `--dry-run` bypasses
the active-process check and remains available while Codex is active.

## Usage modes

### Default (no arguments)

```zsh
codex-sync
```

Default live behavior (no flags):

- Resolves root from `CODEX_HOME`/`$HOME/.codex`, reads `config.toml`, and validates the live execution path.
- Resolves effective SQLite home as root `sqlite_home`, then nonempty `CODEX_SQLITE_HOME`, then the Codex root; a split layout is rejected rather than redirected.
- Checks for active Codex early and immediately before the first production filesystem mutation.
- Accepts an absent `backfill_state`; when present, requires the exact singleton `id=1` with text status `complete` at the early guard and again at the live final gate.
- Runs full preflight and safety validation before any backup or write.
- Writes SQLite/session updates only when needed.
- Creates `7zz` backup archives before live writes.
- Prompts before provider writes when there is something to do, unless `--yes` is supplied.
- If `--unlock` is supplied, performs its separate lock-recovery analysis and dedicated prompt before provider synchronization; `--yes` does not bypass that unlock prompt.
- If there are no pending updates, exits `0` with `No changes needed.` **before** any prompt, backup, or writes.

### Dry run

```zsh
codex-sync --dry-run
```

`--dry-run` performs full read-only analysis and planning:

- It keeps all read-side checks and compatibility validation.
- It prints planned targets (root, DB, sessions, change summary).
- It bypasses the live active-Codex check, recovery-marker handling, and `7zz` checks.
- With `--unlock`, it still performs read-only lock ownership analysis; dry-run unlock never prompts, signals, or edits data or lock paths.
- It does not write, backup, prompt, or apply live recovery behavior.
- On a successful dry-run, it exits `0` after reporting that no DB or session changes were made.

### Live with `--yes`

```zsh
codex-sync --yes
```

This skips only the provider-write confirmation step. All other live behavior
remains active, and `--unlock` still requires its dedicated y/N prompt.

## Option guide

Each option below includes scope, exact effect, non-effects, caveats, and validation behavior.

### `--dry-run`

- Syntax: `codex-sync --dry-run`
- Exact effect:
  - Full read-only plan is executed.
  - No DB or session file writes.
  - No backups created and no live recovery mutation is applied.
  - No interactive prompts.
- Does not bypass:
  - Configuration load/shape validation
  - SQLite contract checks
  - Session index and rollout-path validation
  - Duplicate and integrity checks
- Caveats:
  - Active-Codex/pending-marker/`7zz` requirements are not enforced because write path is not entered.
  - A dry-run with `--unlock` still performs ownership analysis with `lsof` and `ps`, but never prompts, signals, or mutates data or lock paths.
  - `--skip-backup` only changes dry-run plan output.
  - `--yes` has no extra effect in dry-run mode.
  - `--force` still queues overwrite logic, but still performs no writes.

### `--yes`

- Syntax: `codex-sync --yes`
- Exact effect:
  - Skips confirmation prompt before live writes.
- Exact non-effect:
  - Does not alter dry-run behavior.
  - Does not alter signal or unlock-recovery behavior.
  - Does not disable preflight validation.
  - Does not disable backup creation unless `--skip-backup` is set.
  - Does not bypass active-Codex refusal.
  - Does not bypass the dedicated `--unlock` confirmation prompt.
  - Does not relax preflight, schema checks, signal policy, or recovery handling.
  - Does not allow positional arguments.

### `--force`

- Syntax: `codex-sync --yes --force`
- Exact effect:
  - Expands DB selection to all thread rows (`1 = 1`) and applies the same safety filters.
  - Expands the session queue to every validated transcript, including first-line metadata whose provider already matches.
- Padding behavior and scope:
  - `--force` can produce writes that do not change provider text because the first-line JSON may be compacted or its padding prepared.
- Exact non-effect:
  - Cannot override invalid schema/rollout/path violations.
  - Does not change non-provider field values, transcript lines after line 1, prompts, or worker/subagent relationships.
  - A rewritten line 1 may use compact JSON formatting or different trailing padding even though its non-provider values stay the same.
  - Missing and changed values already follow the same preflight validation and queueing rules without `--force`.
  - Without `--force`, DB work is limited to missing/mismatched provider rows. Session work can still include missing/mismatched providers, guarded legacy metadata repair, or padding preparation.

### `--skip-backup`

- Syntax: `codex-sync --yes --skip-backup`
- Exact effect:
  - Skips all `7zz` backup archive creation.
  - Live execution ignores `INT`, `TERM`, `HUP`, `QUIT` from just before first write through final validation.
- Does not bypass:
  - Active-Codex refusal on a live run
  - The confirmation prompt unless `--yes` is also supplied
  - Preflight checks
  - Schema validation
  - Session-file reconciliation logic
- Risk profile:
  - No restore marker or archive is produced.
  - Nonrecoverable events can leave partial writes: `SIGKILL`, `SIGSTOP`, crash, power loss, disk failure, or write errors.

### `--no-prepare-bucket`

- Syntax: `codex-sync --yes --no-prepare-bucket`
- Exact effect:
  - Disables first-line padding preallocation for future in-place edits.
- Exact non-effect:
  - Does not disable live checks or backups by itself.
  - Does not alter existing data outside provider metadata.
- Caveat:
  - `--padding-bytes N` has no effect when this flag is set.
  - The flag does not proactively strip existing padding. A provider rewrite can still change the available trailing room when the new compact JSON needs a different number of bytes.

### `--padding-bytes N`

- Syntax: `codex-sync --padding-bytes 512`
- Exact effect:
  - Sets the desired spare capacity after compact, non-paginated/legacy `session_meta` line-1 JSON.
  - When a line does not already have enough room, the script queues a padding preparation and appends `N` ASCII spaces after the compact JSON.
  - A file that already has at least that much room is not queued solely for padding.
  - Default value is `256`.
  - The value is the number of single-byte spaces to reserve, not a target total line size.
- What this enables:
  - Future in-place provider updates can reuse preallocated room.
  - Padding preparation can itself cause a session-file write even when its provider already matches.
- Caveat:
  - It does not apply to paginated line growth; paginated files are blocked for growth and only rewritten where safe.
  - `--no-prepare-bucket` disables this behavior entirely.
- Validation and precedence:
  - `N` must be a separate positive integer token.
  - `--padding-bytes=512` is invalid (parser requires separate argument).
  - Repeated values are allowed; the last value wins.
  - No effect when `--no-prepare-bucket` is active.
  - No effect on paginated first-line growth.

### `-h`, `--help`

- Syntax:
  - `codex-sync --help`
  - `codex-sync -h`
- Exact effect:
  - Shows usage text and exits.
  - No validation, no writes, no backups.
- Exit:
  - `0`

### Invalid argument behavior

- Unknown flags or positional tokens fail with `ERROR: Unknown option` and usage, then exit `2`.
- `--padding-bytes` without a following positive integer fails validation and exits `1`.
- `--padding-bytes=512` is treated as an unknown option and exits `2`; use `--padding-bytes 512`.

### Option interactions

- `--dry-run + --skip-backup`: dry-run mode never writes anyway; only plan output differs (`Backup: skipped`).
- `--dry-run + --yes`: `--yes` has no additional effect because no prompt is shown in dry-run.
- `--dry-run + --force`: previewed scope becomes full overwrite scope, but no writes are executed.
- `--dry-run + --unlock`: performs read-only `lsof`/`ps` ownership analysis without a prompt, signal, or mutation.
- `--yes + --unlock`: skips only the provider-write prompt; the dedicated unlock prompt remains mandatory before live signaling.
- Option order is generally irrelevant for boolean flags.
- Repeated `--padding-bytes N` uses the final value.
- Repeated boolean options are harmless duplicates.

## SQLite layout and runtime guards

The script never redirects its target database. It computes an effective SQLite
directory from root-level `config.toml` `sqlite_home`, then nonempty
`CODEX_SQLITE_HOME`, then the resolved `CODEX_HOME` root. Relative values use
the invocation working directory. If the effective directory differs from the
Codex root, the run exits `1` before looking up or changing the root database
and reports the source, raw value, resolved directory, effective DB path, and
script target DB path.

`backfill_state` is optional for compatibility. If it is present, the table
must have the expected visible `INTEGER` `id` and `TEXT` `status` columns and
exactly one row: `id = 1` with text status `complete`. The script checks this
early on every run and checks it again at the live final write gate. Missing,
running, malformed, or extra state fails closed with recovery guidance.

Live active-Codex detection runs early and again immediately before the first
production filesystem mutation. Dry-run bypasses this active check, while
`--dry-run --unlock` still performs its separate read-only lock analysis. The
second live check narrows the start-after-check window but cannot atomically
prevent a process from starting after the check and before the write.

### `--unlock`

- Syntax: `codex-sync --unlock`
- Exact effect:
  - Inspects `thread-writer-locks` ownership with `lsof` and correlates owners with a fresh `ps` snapshot.
  - Groups every affected UUID thread lock under its owner for review.
  - On a live run, permits signaling only for a same-EUID, PPID-1, stable-`lstart` process classified as a `comm`/`argv[0]` basename-matched Codex candidate; this does not prove native ownership or orphan status.
  - Sends `TERM`, waits a bounded interval, and obtains fresh ownership/process evidence before each target and before any `KILL` escalation. `KILL` is sent only while the original lock remains held.
- Safety behavior:
  - Zero-byte UUID `.lock` targets and `.coordination.lock` may persist; their existence alone is not proof of ownership. `lsof` ownership is decisive.
  - Any protected or unconfirmed holder refuses all signaling.
  - The dedicated `Continue with lock recovery? [y/N]` prompt is always required for live signaling, even with `--yes`.
  - No lock target, JSONL file, or SQLite file is edited or deleted by unlock recovery.
- Dry-run behavior:
  - `--dry-run --unlock` is analysis only: it never prompts, signals, or mutates data or lock paths.
  - If no holder is reported by `lsof`, the state is already unlocked and no recovery action is planned.
- Final race:
  - The script revalidates immediately before each signal, but a PID can still be recycled in the unavoidable interval after the final check and before `kill`; this cannot be made atomic.

## Backups and interruptions

Normal live runs create verified 7-Zip archives under:

```text
<resolved-codex-root>/backups/model-provider-sync-*/
```

When `CODEX_HOME` is unset, this resolves to `$HOME/.codex/backups/model-provider-sync-*`.

When present, the full `sessions/` tree is archived. The SQLite/config archive
is created only when database rows need to change.

Backup archives use 7-Zip compression level `5` (`-mx=5`, normal compression)
with multithreading enabled (`-mmt=on`). Each archive is tested and its expected
members are checked before the script treats the backup as usable.

During a backed run:

- interruption during preflight exits without changing anything
- interruption during backup removes the incomplete backup
- interruption after syncing starts restores the verified backup
- repeated catchable signals are ignored while restoration is running
- a durable recovery marker blocks the next live run after an uncatchable interruption such as `SIGKILL`

## Progress output

Live runs report the current stage without changing the data being processed:

```text
Working: Preflight (DB Checking)
Working: Preflight (Sessions Checking <count>/<total>)
Working: Preflight (Update Checking <count>/<total>)
Working: Preflight (Final Checking <count>/<total>)
Working: Backup (<percent>% | ETA <mm:ss>)
Working: Sessions Syncing (<count>/<total>)
Working: DB Syncing (<count>/<total>)
Working: Restoring Backup (<percent>% | ETA <mm:ss>)
```

The backup percentage comes from `7zz` progress for the archive currently being
tracked. The ETA is an estimate derived from elapsed time and the reported
percentage, so it can move as compression speed changes. On an interactive
terminal the status updates in place; redirected output is rate-limited to
roughly one line per second.

## Live `--skip-backup`

```zsh
codex-sync --yes --skip-backup
```

In this mode:

- preflight remains interruptible
- immediately before the first write, `INT`, `TERM`, `HUP`, and `QUIT` are ignored
- those signals remain ignored through final validation
- normal signal handling returns after successful sync
- no backup, recovery marker, or automatic rollback is created

`--skip-backup` cannot protect against `SIGKILL`, `SIGSTOP`, power loss, a process crash, disk failure, or an internal write error. Those events can leave an unbacked sync partially applied.

## Safety checks

Before writing, the script:

- verifies the required SQLite table and provider columns
- rejects unsafe update triggers, invalid rows, and duplicate IDs or rollout paths
- matches every session JSONL path and thread ID against SQLite
- validates first-line session metadata without requiring an exact whole-schema fingerprint
- preserves file permissions and timestamps
- refuses paginated first-line growth that would invalidate stored offsets
- keeps existing worker/subagent source metadata and parent-thread relationships unchanged
- creates missing legacy `session_meta` only when its identity and history can be proven
- restores a legacy subagent source and parent link only when the referenced parent exists

Progress is shown for preflight, backup, session writes, database updates, and restoration.

## Common combinations

- Preview only:

```zsh
codex-sync --dry-run
```

- Live with explicit confirmation disabled:

```zsh
codex-sync --yes
```

- Preview the full forced rewrite scope:

```zsh
codex-sync --dry-run --force
```

- Apply the full forced rewrite scope:

```zsh
codex-sync --yes --force
```

- Skip backup for a one-shot live run:

```zsh
codex-sync --yes --skip-backup
```

- Analyze held writer locks without prompting or signaling:

```zsh
codex-sync --dry-run --unlock
```

- Recover an actionable basename-matched Codex candidate, then continue with provider sync:

```zsh
codex-sync --unlock
```

The unlock prompt remains mandatory even when `--yes` is also supplied.

- Skip future bucket prep:

```zsh
codex-sync --yes --no-prepare-bucket
```

- Tune future first-line growth before provider flips:

```zsh
codex-sync --yes --padding-bytes 512
```

## Quick reference

| Option | Meaning |
|---|---|
| `--dry-run` | Read-only planning mode. No writes, backups, or prompts. |
| `--unlock` | Analyze `lsof`-owned UUID locks; live recovery has a dedicated prompt and strict revalidation. |
| `--yes` | Skip the provider-write prompt only; `--unlock` still prompts separately. |
| `--force` | Rewrite provider values even when already equal. |
| `--skip-backup` | Run without backups and enable extended signal-ignore behavior during write phases. |
| `--no-prepare-bucket` | Disable first-line padding reserve for future changes. |
| `--padding-bytes N` | Set reserve size for future first-line growth. Must be separate positive integer, default `256`. |
| `-h`, `--help` | Display built-in usage and exit. |

## Testing Notes

The repository requires `pytest>=8.4`. From the repository root, create and
activate a virtual environment, then install the declared dependencies:

```zsh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run syntax, compile, focused, and full-suite checks:

```zsh
zsh -n shell/codex-sync-model-provider.zsh
python -m compileall tests/codex_sync_model_provider
python -m pytest --disable-plugin-autoload tests/codex_sync_model_provider
python -m pytest --disable-plugin-autoload
```

The focused tests execute a copied script against a synthetic temporary Codex
root, fake `ps`/`lsof`, and disposable child processes where needed. They never
read or write the real `$HOME/.codex` and never signal real Codex PIDs.
