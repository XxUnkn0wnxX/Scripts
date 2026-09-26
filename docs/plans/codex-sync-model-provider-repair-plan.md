# Codex provider sync: evidence-based repair plan

Date: 2026-09-27. Status: planning only; implementation has not started.

## Requested outcome and execution boundary

Replace `--unlock` in [`shell/codex-sync-model-provider.zsh`](../../shell/codex-sync-model-provider.zsh) with `--repair [sessionID]`. Support full repair when no ID follows `--repair`, targeted session repair when an ID is supplied, database corruption recovery in both modes, and backups containing only files that will change. Preserve `--dry-run` and existing provider-sync safeguards.

**Implementation validation is limited to tests and dry runs.** The assistant may exercise write paths only inside disposable test fixtures with an isolated `HOME`, `CODEX_HOME`, SQLite directory, and controlled processes. It must not run a live repair/provider sync, signal real Codex processes, replace live databases, edit live rollouts, or deploy a candidate while testing. Any eventual production repair is a separate user action. This plan itself authorizes no implementation or live repair.

## Evidence and what it establishes

Primary incident directory: `$HOME/.codex/backups/thread-history-repair-20260927`.

| Evidence | Finding | Design consequence |
| --- | --- | --- |
| `HANDOFF.txt`, lines 27–64; original DB header/file size independently inspected during this planning task | `thread_history_1.original.sqlite` declares 286,743 pages of 4,096 bytes, but contains 286,395 pages. It is short by 348 pages / 1,425,408 bytes. Resume failed with SQLite code 11, `database disk image is malformed`. | Clearing process ownership cannot repair this damage. Check the history DB as well as the state DB. |
| `HANDOFF.txt`, lines 77–95; `recovery-row-comparison.json` | Only the history DB failed the recorded database checks. All 6,838 records of the failing rollout parsed. SQLite recovery preserved 222,448 readable item rows and passed integrity checks, but missing item rows still needed reconstruction. | Separate structural database health from history completeness. `.recover` followed by `integrity_check = ok` is insufficient. |
| `HANDOFF.txt`, lines 97–152; `repair-merge-report.json` | Ten histories were projected from copied JSONL using Codex 0.157.1. Four per-thread tables were replaced, including projection checkpoints. The original failing history went from 1,995 to 2,000 items, with 19 turns. | Rebuild from canonical rollout data and validate checkpoint boundaries and history contents. |
| `completion-checks.json`; `final-app-server-validation.json` | The recorded final candidate passed integrity/foreign-key checks and ten unloaded reads. Its counts were 222,718 items, 4,573 turns, 1,222 checkpoints and 44 realtime items. Those table counts were independently rechecked read-only during planning. | Retain separate structural, content-preservation, and app-server validation stages. |
| Script lines 351–956 and 2830–2847 | `--unlock` examines real lock holders and can signal narrowly classified orphaned processes, then falls through to provider sync. It contains no database repair. | Preserve useful lock diagnosis within repair, while adding an actual corruption path. |
| Script lines 2399–2402 and 2918–2926 | Only `state_5.sqlite` is checked; corrupt state fails preflight. | Move repair diagnosis ahead of provider-only health/schema gates. |
| Script lines 4035–4079 and 2141–2178 | Backup includes the complete `sessions/` tree and sometimes unchanged `config.toml`. Restore replaces the whole sessions tree. | Change backup and rollback together to use an explicit changed-file manifest. |
| Script lines 2919, 3763–3788 and 3828 onward | Dry-run exits before intentional writes, but several read queries open SQLite without an explicit read-only mode. | Audit SQLite open modes and sidecar effects, in addition to preserving the dry-run branch. |

The incident proves truncation, not its cause. Sudden crashes and interrupted repairs are required recovery scenarios, but this evidence does not establish that a crash caused this particular file to become short. The handoff's installation status is historical; this planning task did not determine the current live installation state.

## Proposed command contract

| Invocation | Session/provider scope | Database scope |
| --- | --- | --- |
| No repair flag | Existing provider synchronization | Existing sync requirements; no automatic corruption repair |
| `--repair` | Inspect/reconcile all sessions; repair history and perform needed provider sync | Inspect every supported Codex DB; stage repairs for damaged DBs |
| `--repair <sessionID>` | Repair that session's history and any needed provider fields for that same ID | Still inspect every supported Codex DB and handle corruption globally |
| `--dry-run` | Existing provider plan only | Read-only checks |
| `--dry-run --repair [sessionID]` | Describe the corresponding repair scope and planned changes | Read-only global diagnosis; never apply recovery |

Examples:

```zsh
zsh shell/codex-sync-model-provider.zsh --dry-run
zsh shell/codex-sync-model-provider.zsh --repair --dry-run
zsh shell/codex-sync-model-provider.zsh --repair <sessionID> --dry-run
```

Parser and scope decisions:

- Consume at most one UUID immediately following `--repair`. Other options may precede or follow it. Reject malformed IDs, extra positional arguments and repeated/conflicting repair selectors before mutation.
- Remove the `--unlock` execution path. Give the obsolete flag a clear migration error directing the user to `--repair`; do not silently alias a lock-only command to a broader write operation.
- No flags continues to mean ordinary provider sync. Only `--repair` with no ID means full repair.
- Resolve identity using state rows and `session_meta.payload.id`, not filename substring matching. If state is corrupt, defer final target resolution until its staged recovery is validated; a dry run must report that dependency rather than guess.
- Keep session and provider scopes aligned. Targeted repair must not accidentally apply today's global provider UPDATE, global `--force`, padding preparation, or legacy-header edits to unrelated sessions.
- A shared database can need broader repair than the selected ID. Report this explicitly as database recovery, including any additional projections that must be rebuilt. That does not authorize unrelated provider or rollout edits.
- Diagnose missing, duplicate and ambiguous identities. Unique target resolution is a mutation gate for the entire invocation: an invalid, nonexistent or ambiguous target permits global diagnosis but no production changes, including database replacements. Resolve targets that depend on state recovery against the validated scratch candidate before passing this gate.
- Retain existing configuration/root resolution, split-layout refusal, schema/trigger checks and paginated first-line byte-offset protection. Database repair must not be skipped just because provider values already match or no explicit provider synchronization is needed.
- Keep `--yes` for the normal write confirmation. Preserve the existing separate confirmation for actual orphan-process signals. Reject `--repair --skip-backup`: repair must preserve the files it may replace. Ordinary sync retains its existing `--skip-backup` behavior.

## Implementation structure

Keep the zsh command as the public entry point and owner of argument parsing, existing provider planning, progress and confirmation. Put structured database discovery, manifests, candidate recovery and verification in a focused standard-library Python helper, proposed at `python/codex_repair.py`. Do not add a Python reimplementation of Codex's rollout-to-history decoder.

Resolve the helper relative to the script, and preserve that relative script/helper layout in fixture setup. Detect dependencies and SQLite recovery capabilities before planning a write; report missing capabilities without installing packages. The existing `/usr/local/opt/sqlite/bin/sqlite3` was verified as SQLite 3.51.0 with `.recover` support. Do not assume the PATH-selected macOS SQLite has that capability.

Use one structured plan as the input to reporting, backup, staging, installation and rollback. It should distinguish read dependencies, temporary candidate inputs, changed production files, changed DB rows and unresolved findings. A temporary copy used to validate a projection is not automatically a retained backup.

## Global database diagnosis and recovery

The incident's exact Codex source, release `rust-v0.157.1` at commit `36650394c5b38c2990ccf2a3457165ca3e9d9726`, enumerates seven runtime databases:

```text
state_5.sqlite
thread_history_1.sqlite
logs_2.sqlite
goals_1.sqlite
memories_1.sqlite
memories_v2_1.sqlite
queue_1.sqlite
```

Use a version-aware inventory in the effective SQLite root, without recursively sweeping backups, other projects or arbitrary third-party DBs. Report absent optional DBs without creating them. Report unknown/new database versions as unsupported for mutation until their contract is checked; tolerate unrelated additive schema changes where required structures remain compatible.

For every present DB:

1. Identify its DB/WAL/SHM/rollback-journal file set. Distinguish locks, permissions, unavailable files, unsupported schema, I/O errors and actual corruption. A busy database is not a corrupt database.
2. Inspect health through a genuinely read-only path. Use full integrity and foreign-key checks where applicable, plus role-specific schema/content checks. Account for WAL state before interpreting raw main-file header/extent differences.
3. Collect all findings instead of stopping at the first broken DB. Preserve exact error text and identify the affected file.
4. For a user-invoked write run, establish that writers are stopped and take a verified snapshot of the original file set into scratch. Work on a separate candidate, retaining the snapshot until the final backup/install decision. Never try `.recover`, `REINDEX`, a checkpoint, or a header modification on the live original. Promote snapshots to retained backups only for files the final plan will change.
5. Let SQLite handle normal journal recovery on the candidate first. Use index rebuilding only for verified index damage with intact table data. For actual damage, run `.recover` into a new candidate with strict import failure handling. Prefer excluding freelist content so previously deleted rows are not silently resurrected; retain/report ambiguous salvage separately.
6. Validate the candidate's schema, migration metadata, constraints and recovered content. Never equate a successful command or `integrity_check` with complete recovery.

Apply this recovery framework to every corrupted supported DB, including in single-session mode after its selector gate passes. Add per-database validation rather than silently resetting unfamiliar databases:

- **History:** rebuild derived content from canonical rollouts as described below.
- **State:** preserve recoverable thread IDs, paths, provider values, archive state and other metadata. Reconcile against rollouts, but do not fabricate non-rollout state or drop unrelated tables. State recovery precedes any provider UPDATE or history target resolution that depends on it.
- **Goals, memories, queue and logs:** salvage and validate their actual schema/data. Do not treat them as interchangeable disposable caches, silently erase them, rerun queued work, or invent missing records.

Before enabling installation for any DB role, document its source-backed required schema/migrations, semantic invariants, authoritative recovery sources, readable-row comparison rules, prohibited side effects and refusal conditions. The default loss policy for non-projection data is no unverified loss: a candidate whose preservation cannot be established remains diagnostic and is not installed. Give each of the seven roles at least one corruption/recovery fixture and one refusal case; generic SQLite checks are only part of these validators.

Unrecoverable or ambiguous authoritative data must produce a non-success result identifying the loss/uncertainty. Preserve originals and diagnostic candidates; do not install an unverified result or claim that every kind of corruption is losslessly repairable. This is a recovery limit, not an excuse to omit global checks or the recoverable cases.

## History reconstruction

The exact source states that JSONL is canonical and the history DB may lag it. The incident demonstrated recovery through exact-release projection code; use that contract rather than guessing a JSON-to-SQL mapping.

1. Inventory canonical sources, including archived/compressed rollouts and lineage/history-base dependencies when the pinned implementation needs them. Keep state paths, session IDs, history mode and archive state consistent. Unsupported source representations must be reported, not omitted from a supposedly complete repair.
2. Validate complete records, identity, ordinals, history-base metadata and inherited subagent boundaries. A JSON parse alone does not prove that the installed Rust decoder accepts every record. Preserve trailing incomplete bytes; never silently discard transcript content to make a repair pass.
3. For a healthy shared DB and targeted repair, independently reconstruct the selected history in scratch and compare its logical records/checkpoint with the stored projection. Full repair performs this reconciliation across the session inventory, but installs changes only where needed.
4. When structural corruption makes the affected set uncertain, rebuild all potentially affected paginated projections. Do not infer a complete affected set just from surviving index entries or valid-looking checkpoints. A whole-history rebuild may be required even with one requested ID; report that database-level expansion.
5. Clear/repopulate all four row sets together in a candidate transaction: `thread_items`, `thread_realtime_items`, `thread_turns`, and `thread_history_projection_state`. Deleting only items leaves checkpoints able to skip missing history.
6. Use the matching installed release's projection behavior in an isolated fixture/home. `thread/resume` can materialize history; unloaded `thread/read` validates the stored result. `migrate-rollouts` skips already-paginated sessions and is not a rebuild command.
7. The incident's V2 child workaround changed only copied `multi_agent_version` metadata from `v2` to `v1`. This is **not a generic migration rule**. Before supporting it, prove with exact-release fixtures that the copied change leaves projected content identical, preserves byte lengths, and retains history-base/inherited-history rules. Never transfer altered child metadata back to live files. If that adapter cannot be established for a release, report unsupported children and do not label the repair complete. Supporting the affected child histories is a required implementation milestone, not an optional omission.
8. The isolated runtime must have remapped SQLite/rollout paths and an empty workspace, no user auth, hooks, MCP/plugin configuration or inherited live-home overrides. Disable background migration/compression and other unrelated features. Never send `turn/start`; validate that preconnection/background behavior cannot access production services or mutate source data. Fully reap any spawned test server.
9. Record each original snapshot's byte length, complete-record boundary, hash and next ordinal. Exclude isolated `thread_settings_applied` suffixes from the installed checkpoint; verify item/turn offsets and update ordinals against the original source. Account for history bases rather than assuming ordinals begin at zero.
10. Compare decoded record contents and preserve unaffected recovered data. Reopen the final candidate and use unloaded reads in a separate isolated verifier. Check counts and ordering, not merely whether resume returns success. Reject silent decoder-skip/anomaly output as proof of complete reconstruction.

A helper that merely deletes projection rows and relies on a future live resume is incomplete: this incident needs a validated reconstructed candidate before replacement.

## Back up exactly the changed production files

Build a manifest from the final mutation plan after candidate validation. Before final write confirmation, show its exact scope and backup membership; if any subsequent discovery changes that scope, invalidate the plan and obtain confirmation for the revised plan under the existing `--yes` rules. For each path, store its relative location, role, pre-change existence, size, hash, mode, proposed operation and associated session/DB. Constrain paths to the approved roots and reject symlink/path traversal escapes.

- Archive only JSONL files that will actually be rewritten. JSONLs merely read to rebuild a DB do not need retained backup copies.
- Back up only databases being changed or replaced. A shared SQLite database is the file-level recovery unit: a one-session row update still requires that database's complete original file, not every session file.
- Preserve matching WAL/SHM/rollback-journal companions when present as part of that DB's original file set. Record absence as well as presence. Never attach old sidecars to a replacement DB.
- Stop copying unchanged `config.toml`, healthy untouched DBs, or the entire session list/tree.
- No changes means no backup directory/archive. A pure history repair normally backs up only the history DB and its existing companions.
- Verify archive members and hashes against the manifest before production mutation. Backups retain original bytes, including already-corrupt bytes; validation of a backup is different from validation of a repaired candidate.
- Restore only listed paths. Remove the whole-`sessions/` swap from rollback, and prove that unrelated/new session files survive a failed operation.

Temporary reprojection inputs can be copied in bounded batches and removed after validation. Report scratch space separately from retained backup size. The old incident directory is evidence and must not be modified or cleaned up by implementation tests.

## Interrupted execution and safe replacement

Retain early OS/process/filesystem checks and immediately-pre-write quiescence checks. When the original state DB is unreadable, defer state-dependent target, backfill and ownership checks until a recovered state candidate is validated; do not let the old preflight abort before recovery. Require the recovered state to satisfy the applicable guards before provider/history mutation. Extend ownership checks to database companions and every file that will be replaced. Use an exclusive repair-run lock to prevent two utility invocations from racing; it does not replace checking for Codex writers.

Keep the existing guarded orphan-owner recovery as a repair substep: actual held UUID locks, same user, fresh process identity checks, separate confirmation, TERM before any existing guarded escalation, and no deletion of lock paths. In targeted mode, do not signal a process that also owns unrelated sessions; report the conflict. No process signals occur in dry-run.

Before installation, all required candidates and backups must validate. Recheck source hashes/identities and quiescence immediately before replacement. Stage candidates on the destination filesystem; preserve permissions, flush candidate and manifest state, and use atomic per-file replacement. Multiple files/databases are not one atomic filesystem transaction.

Extend the durable recovery marker into a versioned operation journal with per-file states: planned, backed up, candidate validated, original held, replacement installed, verified, complete. Record separate durable intent and applied entries for each operation, with expected hashes/identities and absence for original, candidate and holding paths. Flush files and journal records, perform the rename, flush affected directories, then persist the applied record. An intent alone never proves a rename happened: restart must reconcile actual on-disk identities against both allowed outcomes. An incomplete journal tail must not erase earlier durable records.

Treat a DB and its companions as one recoverable set. First journal and hold the old companions and main file while writers are stopped; install only a closed standalone validated candidate, with no old companions alongside it. Journal any newly created companions. On rollback, hold the candidate and its companions separately, restore the original main file and matching companions, and verify original bytes before opening SQLite. Test crashes between every one of these operations. The commit point is a flushed run-level completion record written only after all replacements validate; retain recovery material until that point, and never restart Codex from a mixed or unresolved file set.

Catchable failures restore only affected entries. A later `--repair` must recognize an interrupted run and safely reconcile/restore it before starting another plan; `--dry-run --repair` only reports the proposed recovery. Never discard ambiguous originals, candidates or journals automatically.

The current restore function requires the restored DB to pass `quick_check`; that is unsuitable when the backup is intentionally the pre-existing corrupt original. Rollback must verify byte-exact restoration and report the original corruption separately. Keep old/new DB companions distinct throughout rollback.

This design addresses interrupted repair and recoverable crash damage. It cannot guarantee recovery of bytes absent from both SQLite and all canonical sources, or guarantee durability against failing storage.

## Dry-run guarantees

- Use the same discovery, scope selection and mutation-plan rules as repair, but stop before backup, recovery, signals, prompts, markers or production writes.
- Do not invoke normal Codex database initialization, `thread/resume`, migration, `.recover`, `REINDEX`, or checkpoints. These are not read-only diagnostics.
- Open existing sources explicitly read-only. Test WAL/SHM/journal behavior: `query_only` alone does not make a normal writable connection safe, and read-only SQLite can still involve shared-memory sidecars.
- Preserve the existing no-scratch-under-`CODEX_HOME` behavior. If a coherent WAL-aware read requires an analysis snapshot, use only private disposable scratch outside production roots and identify that in the implementation contract. Do not use `immutable=1` on a changing live database or ignore its WAL. If a safe coherent read is unavailable, report the affected check as inconclusive rather than healthy.
- Remain useful while Codex is active: report bounded/read-consistent findings and any busy/changing inputs; do not stop processes to complete analysis.
- Show the requested session scope, every DB's status, proposed repairs, estimated space, unsupported cases and any database-wide expansion. Distinguish confirmed backup members from conditional members that depend on salvage/reprojection; dry-run cannot discover every logical history difference without those operations. Finalize exact membership in the write run after candidate validation and before confirmation/mutation. A corrupt DB should reach the repair report instead of the current early generic abort.
- Distinguish a successful analysis with proposed changes from blocked/incomplete analysis. Never print a repair-complete message in dry-run. A dry run does not prove that later salvage/reprojection will succeed.

## Implementation sequence and acceptance tests

### 1. Establish the recovery adapter and fixtures

Create minimal synthetic fixtures for this failure class: truncated history pages, missing items behind an advanced checkpoint, valid canonical JSONL, and a V2 child with inherited history. Verify the installed binary/release identity, schema/migration contract and recovery-capable SQLite selection. Prove exact-release projection and child handling in isolation before integrating any production write path.

Do not import the incident's multi-gigabyte databases, personal transcripts or obsolete generated tests into the repository. Tests may use read-only evidence summaries to construct small equivalents.

### 2. Implement planning, CLI scope and dry-run

Add `--repair [sessionID]`, seven-DB inventory, diagnosis and structured plans. Wire target scope through provider SQL, rollout selection, force/padding behavior and reporting. Repair discovery must work before today's state-health failure/provider no-op exits. Preserve ordinary sync behavior.

Test argument ordering, full/targeted repair, malformed/unknown/ambiguous IDs, obsolete `--unlock`, split roots, absent optional DBs, unsupported versions, provider no-op, targeted force, global corruption with a healthy target, and strict dry-run source/sidecar invariance.

### 3. Implement selected-file backups and crash recovery

Replace full-tree backup/restore with manifest-driven file sets for both normal sync and repair. Extend marker/journal handling without losing existing normal-sync safeguards. Account for the older marker format explicitly; an old marker must remain recoverable or receive a precise manual-recovery report, never be silently discarded.

Test exact archive membership; DB-only and session-only changes; unchanged config/DB omission; WAL/SHM/journal sets; no-op behavior; unrelated files surviving rollback; byte-exact restoration of a corrupt original; insufficient space; candidate/hash changes; and failures before/after each swap. Simulate signals, SIGKILL and restart in fixtures, including interruption during rollback.

### 4. Implement candidate salvage and verified reprojection

Add the database recovery ladder and per-role validators, then the pinned history projection adapter. Validate all candidates before installation. Reconcile all four history tables/checkpoints, and verify affected/unaffected data. Include repair of recoverable non-history corruption rather than merely reporting it.

Test index-only damage, truncated tables, readable-row preservation, unrecoverable authoritative data, malformed/partial JSONL, compressed/archived sources, missing history-base dependencies, realtime items, V2 children, decoder anomalies, and schema/version mismatches. Cover the approved recovery/refusal contract for each of the seven DB roles. For an unbounded corruption scope, verify full history reconstruction despite a selected ID while unrelated provider/JSONL data remains unchanged.

### 5. Integrate docs and run permitted validation

Update `docs/codex-sync-model-provider.md`, the script's help/comments and the README description. Replace/extend `test_unlock.py` with repair tests while retaining applicable orphan-owner safety coverage. Update `_helpers.py` to isolate all roots and support the helper and controlled app-server fixtures.

Run zsh syntax checking, Python compilation, the focused `tests/codex_sync_model_provider/` suite and `git diff --check`. All mutating integration tests operate on fixtures. Only after proving dry-run cannot alter production files may it be exercised against the live root. Do not run the live write mode, signal production processes or install a candidate as part of validation.

Completion requires evidence that the truncation/checkpoint case is actually recovered in fixtures, not just detected; both repair scopes work; all supported databases are checked; backup/rollback touch only manifested files; dry-run is non-mutating; interrupted runs can be reconstructed; and unsupported/lossy cases are honestly reported. Production runtime recovery remains unverified until the user separately performs it.

## Source references

- Incident files named above, especially `HANDOFF.txt`, `recovery-row-comparison.json`, `repair-merge-report.json`, `reprojection-manifest.json`, `final-app-server-validation.json` and `completion-checks.json`.
- Current script and [`docs/codex-sync-model-provider.md`](../codex-sync-model-provider.md); script line references above describe the planning baseline and will shift during implementation.
- Exact Codex commit `36650394c5b38c2990ccf2a3457165ca3e9d9726`: `codex-rs/state/src/sqlite.rs` (runtime DB inventory and open modes), `state/src/runtime.rs` (integrity checks), `state/src/runtime/recovery.rs` (DB/companion preservation), `thread-store/src/local/live_writer.rs` (canonical JSONL and persistence), `thread_history.rs` (four-table reset), `thread_history_materialization.rs` (checkpoint/ordinal/lineage semantics), `rollout_migration.rs` (already-paginated handling), and `app-server/src/request_processors/thread_processor.rs` / `thread_input.rs` (resume and child ownership).
- [Official OpenAI app-server documentation: reading a stored thread](https://learn.chatgpt.com/docs/app-server#read-a-stored-thread-without-resuming) distinguishes reading persisted history from resuming a thread.
- [SQLite recovery documentation](https://sqlite.org/recovery.html) explains recovery limitations and `.recover` options; [SQLite corruption documentation](https://sqlite.org/howtocorrupt.html) explains journal pairing, live-file replacement and crash behavior; [SQLite integrity checking](https://sqlite.org/pragma.html#pragma_integrity_check) documents structural checks.
