# mkvutil rework handoff

<!--
Verified parent Codex session IDs (append only; no child IDs):
Codex Session: 01a13610-202e-7613-af35-d95dfaa33fa8 | verified 2026-10-14 Australia/Melbourne |
CODEX_THREAD_ID corroborated with matching CLI session_meta ID and repository cwd,
plus the current user's tracking/AGENTS approval in that same session's log.
-->

[Authoritative plan](plan.md) · [Acceptance checklist](plan_checklist.md)

## Current state and safe restart point

- Active workspace: sibling worktree `../Scripts-dev`, on
  `feature/mkvutil-rework`, per the user's explicit instruction to work there
  moving forward. The user confirmed this worktree is dedicated to this rework
  and must remain attached to the current feature branch. The original
  `../Scripts` checkout is clean on `develop`.
  Resolve the current project root from Git rather than using old shell cwd.
- All five pending tracked-file changes were copied and SHA-256 verified before
  restoring the original checkout. Existing approved local `AGENTS.md` was
  copied unchanged; current `.tmp/mkvutil-rework` fixtures/receipts were preserved.
  Local recovery snapshot: `.tmp/mkvutil-rework/migration.rbow6b82/manifest.json`
  and its five file copies. This is a pre-migration snapshot, not current code.
- The new worktree reuses the original checkout's Python environment through
  an ignored `.venv` link. A narrow `/.venv` entry was added to the common clone's
  local `info/exclude` because the tracked directory-only ignore doesn't cover
  a symlink. No tracked ignore rule or dependency installation changed.
- Relocation verification passed: same pure foundation contract
  (`1 passed, 28 deselected in 0.15s`), script syntax/whitespace checks, and the
  existing Python package environment. Initial test setup lacked a temporary
  parent directory; rerunning in a fresh owned run directory passed without
  product changes.
- Latest verified published feature HEAD: `8f7204bc8545a054e58953f8a6c695bcf7bb714f`
  (`docs: share mkvutil worktree instructions`), signed. `develop` and `master`
  share signed `e6dd2b94fd489796df80270814aa040bc19db8a8`; remote refs match.
  Only the instruction file and root ignore exception were synchronized to
  those branches. Utility implementation remains in this feature worktree.
- Current local feature HEAD: `53625bfe69dbfd37100333ce775a60f54a18d313`
  (`feat(shell): add shared mkvutil planning foundations`), signed and one
  commit ahead of the published feature ref. Both worktrees were clean before
  this handoff refresh; no implementation promotion has occurred.
- The user now instructed **"ok you may begin"**, authorizing implementation
  of the approved rework. Their subsequent instruction requires one self-contained
  `shell/mkv_utils.zsh`, with no additional runtime `.zsh` dependencies.
- The user selected **"Use extensions based on retained content"** for removal
  output naming: retain existing `.mkv`/`.mk3d` with video, `.mka` for audio
  without video, `.mks` for subtitle-only. Plan/checklist record this decision.
- Active route B: coordinated approved rework, foundation first (T01.01,
  T01.02, T01.03), then G02 Edit/Mux, G03 Extract after G02 acceptance, and G04
  integration/docs. Route A would stop after T01.01's baseline/contract only;
  B is selected within the user's full implementation instruction. Shared source
  and tests have one writer per package; dependency consumers wait for their gates.
- T01.01 is accepted after parent review and focused proof. Its pure helpers
  establish original-position selectors, bounded ranges, complete retained order,
  and approved output extensions without migrating the old consumers yet.
- T01.02 is accepted after parent review of the shared registry, configuration,
  flag snapshots and two pure argument builders, five focused unit contracts,
  and small native v93 builder proof. The writer is quiescent.
- T01.03 and G01 are now accepted after parent review and final selector/removal
  proof below. Categories, configuration, per-file planning, skip receipts,
  preview and fresh skipped-subset preparation are implemented. Executors
  remain guarded unavailable. Current totals: 3 / 9 tasks and 1 / 4 goals.
- Next package: G02 Edit/Mux executors, T02.01 and T02.02 with one coherent
  source/test/helper owner. T02.03 follows their accepted executor evidence to
  connect full reporting and skipped-only continuation. Parent owns all records.
- The user requested always-multi selection and automatic removal mismatch
  skips with skipped-only follow-up batches. Astra verified this delta before
  any new requirement/code edits; the parent updated the authorized plan and
  checklist, then the same source/test owner implemented the G01 portion.
- Broad interactive campaign permission is still pending and scheduled for the
  integration stage. Small isolated probes are notified; code/static checks and
  focused non-interactive contract proof can proceed.

### Refreshed worktree coordination

- Rediscovered and reread `zr0-git-repository-workflow`,
  `zr0-parallel-execution`, and `zr0-multi-session-projects` on the user's
  refresh request. The Git worktree reference and current handoff template
  loaded successfully. Other referenced ignore/change-control/dependency/
  resumption documents are absent from the installed folders; follow the full
  skill instructions and preserved approved project contracts until available.
- Canonical records are the tracked root `plan.md`, `plan_checklist.md`, and
  `plan_handoff.md` in `../Scripts-dev`. Historical copies in other branches
  and copied fixture receipts are subordinate; do not start another master plan.
- Runtime default cwd remains the original `../Scripts` checkout. Every tool
  command must explicitly use `../Scripts-dev`; workers must provide a verified
  Git-root/branch/status receipt there before writing. This is explicit tool
  routing, not a claim that a prompt changed the session's process cwd.
- Linked checkout inventory was reverified: `../Scripts` owns `develop` at
  `e6dd2b94fd489796df80270814aa040bc19db8a8`; `../Scripts-dev` owns
  `feature/mkvutil-rework` at `53625bfe69dbfd37100333ce775a60f54a18d313`.
  The common Git directory and `info/exclude` belong to the original clone and
  are shared. The ignored environment symlink and migration snapshots remain.
- Keep both branch assignments and all ignored recovery state. Worktree setup,
  concurrency, publication, implementation integration, and cleanup are separate
  permissions. The user's instruction synchronization grant has been fulfilled;
  it does not authorize promotion of unfinished utility implementation.

### Previous planning publication receipts

- Branch: `feature/mkvutil-rework`.
- Verified publication baseline before the rehearsal-planning amendment:
  `b468c0b90c655906083eac0d0fcb6351398d605d`
  (`docs: structure mkvutil goals and continuity records`), with a verified
  signature. Local HEAD and `origin/feature/mkvutil-rework` matched this SHA;
  the worktree was clean before the rehearsal-planning amendment below.
- The committed plan is complete as a planning document. All four
  implementation checkpoints remain open; source, tests, and end-user guide
  have not been modified for this rework.
- The user-requested structural rework is complete: G01-G04 preserve the four
  checkpoints, with nine task IDs and a mirrored acceptance checklist.
  The reviewed dependency/readiness model is recorded in the plan. Companion
  links and local instructions remain in place.
- The authorized structural documentation publication is complete. Verify live
  refs on resumption; this historical receipt does not imply later edits were
  published.
- The user subsequently requested a near-end `zr0-interactive-testing` rehearsal
  with custom `.tmp` files and reuse of existing tests/helpers. This amendment
  is recorded in T04.01 and its mirrored checklist. It is prepared for the same
  authorized feature-branch documentation publication; verify actual Git refs
  and worktree/index state for its publication status.
- These receipts describe the preceding planning stage. The current user
  implementation instruction above supersedes its former planning-only boundary.
  Unrelated acceptance-contract changes still need approval.

## Artifacts and approved repository policy

| File | Purpose | Git visibility at this checkpoint |
| --- | --- | --- |
| `plan.md` | Authoritative requirements, goal/task IDs, dependencies, and four checkpoint identities | Tracked; included in the authorized documentation publication |
| `plan_checklist.md` | Mirrored checkpoint and validation acceptance evidence | Root companion included in the authorized documentation publication |
| `plan_handoff.md` | Verified current state, approvals, lineage, and next actions | Root companion included in the authorized documentation publication |
| `AGENTS.md` | Approved durable project instructions and dedicated worktree/branch locator | Tracked and synchronized on feature, develop, and master |

On 2026-10-14 the user replied **"for repo plan etc can be tracked & ya
approved"** to the proposal for project instructions. This approves creating
`AGENTS.md` and overrides the private `.tmp/` default for the planning companion
records. Keep the plan and companions together at the repository root and
eligible for tracking. The original local AGENTS file initially reused the
existing ignore rule. The user later explicitly requested its publication on
the feature branch, develop and master. Root `!/AGENTS.md` now overrides that
ignore; the instructions and ignore change are identical on all three branches.
Planning records remain at the root of the feature worktree; instructions on
the other branches direct rework sessions to that worktree before reading them.

The previous user instruction to commit `plan.md` was fulfilled by `e3cb187`.
The later explicit push instruction covers the ongoing feature-branch planning
updates; the structural publication was verified at `b468c0b`. Future checkpoints
must refresh the actual commit, remote ref, and worktree/index state rather than
using a pre-publication handoff as proof that an amendment has been pushed.

## Preserved design and decisions

- Main categories are Matroska Edit, Mux, and Extract. Existing actions become
  category sub-actions directly; there is no separate classic menu.
- Single and comma/range multi-selections are supported within each category.
- Target file selection is always multi-select, accepting one or several files
  without a Y/N single-file-mode prompt, per the user's subsequent instruction.
- Mux offers optional metadata choices inside its own workflow. All settings
  are collected before the queue starts.
- One shared metadata definition/configuration section serves both Edit and
  Mux. Every new shared choice needs mappings and verification for both tools.
- Edit uses grouped `mkvpropedit`. Mux uses its corresponding `mkvmerge`
  metadata arguments in the same output-producing remux command; it does not
  perform a post-remux `mkvpropedit` step.
- Support includes `.mkv`, `.mka`, `.mks`, and `.mk3d`, targeting the installed
  MKVToolNix v93.0 on Big Sur. Tool upgrades are outside the approved design.
- Removal compatibility matches each requested original ID's media type and
  native codec against the prominently displayed first valid reference file.
  ASS/SRT differences or missing IDs automatically skip the whole Mux job;
  names/languages/flags may differ. Keep exact mismatch receipts and original
  batch scope, and later offer fresh configured batches for skipped files only.
- Use Astra for intermittent focused audits at meaningful changes, as the user
  requested. The current user instruction authorizes concurrent agents for this
  task and active session; it does not authorize implementation or publication.

## Acceptance and unresolved implementation gates

Planning preparation is verified and remains separate from implementation
acceptance. The four existing checkpoints are now G01-G04, with nine stable
task IDs; **3 / 9 tasks and 1 / 4 main goals** are accepted (T01.01-T01.03, G01).

The recorded audit identified these implementation checks:

- Establish actual v93 default-flag parity for intended retained-track states,
  plus blank-title clearing and literal-title handling through `mkvmerge`.
- T01.01 has implemented/proved the newly approved retained-content naming
  helper. T01.03 still needs consumer evidence for actual per-file output previews.
- Validate intended track identity and explicit final order for every file;
  do not assume track positions or MakeMKV UIDs survive a remux unchanged.
- Verify safe staging/promotion, collisions, warning/error distinctions,
  interruption behavior, and correct success reporting.

These are pending requirements or checks already in the plan, not accepted
runtime behavior or permission to weaken the specification.

## Execution route and next actions

The user authorized `parallel-execution` in this active session, then approved
beginning the implementation. Current route B and foundation-first scope are
recorded in the restart section above. The preceding coordinated documentation
package is complete; its receipts below are historical.

### Active implementation package

- T01.01 baseline/track/output contract: the completed bounded worker owned additions to
  `shell/mkv_utils.zsh` and focused contract cases in the tracked
  `tests/mkv_tools/test_mkv_utils.py`. Parent reviews/integrates; no other writer
  touches either file during that package. Keep the existing flat entrypoint
  behavior temporarily intact until T01.03 migrates the consumers.
- Add sourceable pure contract helpers for bounded ID/range expansion, original
  identity/selectors, retained order, and approved output extensions. Helpers
  must not execute media tools; future consumers reuse this canonical contract.
- Gate: syntax plus focused non-interactive helper tests and parent contract
  review. Before edits, three notified mocked baseline journeys passed at
  `96ae959`: flag default/selector, spaced name arguments, heterogeneous removal
  (`3 passed, 25 deselected in 1.50s`). This is a focused historical baseline,
  not the full affected-group or new-feature acceptance gate.
- Parent found and corrected a range-gap error before acceptance: ranges must
  include every integer, not silently filter to existing IDs. Final retained IDs
  now follow complete output order. Parent syntax/whitespace and focused proof
  passed (`4 passed, 25 deselected in 2.70s`) with the old executed path intact.
- T01.02 owned additions to the same script and utility test file; no second
  writer may touch them during its package. Implement the shared registry,
  canonical configuration, explicit false/clear handling, original-ID mapping,
  and two pure quoted-argument builders. Keep the legacy consumers until T01.03.
- The focused Astra implementation-design audit returned PASS WITH NOTES:
  input-scoped merge args precede source; preserve raw title and double a leading
  `@` only in merge argv; snapshot explicit false flags; support BCP47 and account
  for normalized legacy/IETF output; persist per-file state independently.
- T01.02 gate passed: shared registry/mapping completeness (including generic
  sixth-row coverage), canonical absent/empty values, original selectors,
  explicit false/retained flags and quoted argv; parent selected five pure
  cases (`5 passed, 28 deselected in 0.39s`). Syntax/whitespace passed.
- Native builder receipt:
  `.tmp/mkvutil-rework/metadata-builders.3a7qr84e/receipt.json` (about one second),
  using the actual builders for literal/empty titles, original-ID reorder,
  regional language, flags, chapters and attachment bytes. No actual category
  controller/executor was exercised. Language syntax is broader than ISO3;
  semantic registry/tool acceptance and normalization remain later checks.
- Configuration resets settings/snapshots/args. T01.03 must collect settings
  first, take fresh flags from every file's own JSON afterward, and copy each
  file's arguments/configuration into its own job; current-file globals alone
  are not a queue. Source identity and destination collisions need per-file
  planning; controller cancellation must perform no media writes.
- T01.03 follows accepted T01.01/T01.02. Broad menu campaigns remain scheduled
  and unapproved; focused code/function checks remain permitted.
- T01.03 next writer: existing `mkv_metadata_foundation` worker, exclusive
  ownership of `shell/mkv_utils.zsh`, `tests/mkv_tools/test_mkv_utils.py`, and
  necessary changes in `tests/mkv_tools/_mkv_helpers.py`, all in `../Scripts-dev`.
  Deliver the real category controller, single/comma/range configuration,
  source selection/inspection, independent per-file plans, conflicts and complete
  previews. G02/G03 modifying executors remain outside this package; do not call
  legacy immediate handlers from the new controller. Parent owns all records.
- Focused checks: syntax, pure planning/configuration/serialization contracts,
  literal and empty argv preservation, heterogeneous/all-format plans, and a
  small notified entrypoint preview/cancel probe. No broad menu churn. Media
  tool fakes remain isolated; jq/stdlib Python may use verified real binaries
  in the existing harness where needed. Full affected runtime groups remain
  pending until executor integration. Parent reviews before G01 acceptance.
- Initial controller review receipts on the dirty tree based on `53625bf`:
  worker function selections verified per-file flags/literal reload, generic
  sixth-row preview, extraction names, persistent explicit exclusion/EOF,
  four-format/directory planning, filesystem aliases, and 400KB streamed queue
  collision checks. Two notified mocked preview/cancel and guarded-Run journeys
  passed in 3.50s; they preceded final read-only collision/directory refinements.
  Worker runs used pytest-owned default temporary directories. Parent syntax,
  Python AST and whitespace checks passed; three critical job/format/streaming
  contracts passed in 7.73s using fresh `.tmp/mkvutil-rework/controller-review.kJlnd5/`
  child storage. These are baseline receipts, not the new selector/skip proof
  or full affected runtime acceptance.
- User amendment and review: the user requested automatic removal mismatch
  skips, exact filenames, skipped-only later processing, and always-multi file
  selection; explicitly allowed plan/goals edits, then required planner review
  first. Clarifications require expected ID/type matching and relaxed names/
  languages. Astra returned PASS WITH NOTES before parent applied the delta.
  No additional user decision is required; no AGENTS change is implied.
- Completed T01.03 follow-up: remove Y/N selection; add media-type/codec removal
  signatures with usable reference codec IDs, automatic whole-job mismatch
  receipts, persistent current batch source pool, mixed/all-skipped planning,
  and fresh skipped-subset preparation. Reference is the first successfully
  inspected source, clearly displayed. Eligibility changes must reconsider
  automatically skipped sources; unrelated failures retain explicit handling.
  Actual post-run continuation and final resolved/unresolved counts belong to
  T02.03, preserving the G01-before-G02 gate without a dependency cycle.
- Final delta proof: five affected non-interactive cases passed in 20.02s
  (20.69s wall, 8.17s user + 8.09s system), covering signatures, scope retention,
  source-specific flags/literal argv, subset refresh, and filesystem aliases.
  Exactly one notified mocked menu mismatch-report/Cancel journey passed in
  2.37s. Native modifying tools remained intercepted. Parent independently
  reviewed the source/tests, verified all three SHA-256 receipt bindings, and
  passed two critical skip/subset cases in 11.19s under
  `.tmp/mkvutil-rework/removal-review.3paov0/pytest`. Syntax/AST/whitespace passed.
  Exact receipt: `.tmp/mkvutil-rework/removal-delta.vyycYM/receipt.json`.
- Accepted APIs: `mkvutil_removal_signatures`, `mkvutil_removal_mismatch`
  (0 compatible, 3 mismatch receipt, 1 invalid configuration),
  `mkvutil_prepare_skipped_subset`, and independent schema-1 job reload.
  `MKVUTIL_SOURCES` is the current scope pool, `MKVUTIL_JOBS` eligible jobs,
  `MKVUTIL_REMOVAL_SKIPS` current receipts, and `MKVUTIL_REMOVAL_SKIP_HISTORY`
  preparation provenance. The subset helper rejects pending eligible jobs;
  future execution must archive/clear completed jobs before invoking it.
  Origin history alone is not the future resolved/unresolved result ledger.
- Upcoming G02 promotion audit: Astra returned REVISE on the earlier shell
  `mv` draft. Parent accepts the corrections: inline stdlib `os.replace` for
  same-name replacement, atomic no-overwrite `os.link` for extension conversion,
  regular-entry `lstat` checks, source/destination rechecks before old-source
  cleanup, and filesystem reconciliation after uncertain interrupted outcomes.
  Unsupported publication must preserve source/candidate and fail safely.
  Checks detect observed changes; do not claim compare-and-swap or power-loss
  durability. Implement/prove the corrected commit phases before connection.
  Native language validation/normalization remains partial before the real
  tool/staged-result gate; preserve grandfathered/private BCP47 domain.
- The worker's pre-write receipt verified the actual `Scripts-dev` Git root,
  assigned feature branch and only the parent-owned handoff diff. Controller
  design uses NUL-safe selection, explicit exclusion for invalid/incompatible
  sources (default N), and independent JSON jobs with safe literal argv reload.
- Read-only upcoming Mux validation evidence from `mkv_requirement_mapping`:
  bundled v93 manual confirms output track IDs differ and MakeMKV can regenerate
  track UIDs. Validate planned sequence/properties and metadata without an
  unconditional UID-equality gate. Use exact stdlib integers if UID comparison
  is required; jq arithmetic rounds large UIDs even though untouched serialization
  preserves them on installed 1.8.1. The current real fixture contains no video/
  stereo or nonempty tags, so those retained-property proofs remain pending.
  JSON descriptors establish attachment/chapter counts, not their payload bytes;
  existing extracted chapter/attachment comparisons are the stronger receipt.

### Completed documentation review wave

The existing specification/checklist/handoff remain the durable record before
delegation. Parent owns all writes and integration; both delegated packages are
read-only and independent.

| Package | Owner / child task | Exclusive authority and scope | Outcome |
| --- | --- | --- | --- |
| Structural rework and final records | Parent | Sole writer of the three records; requirements preserved | Goal/task parity and dependency checks passed; review corrections integrated |
| Goal/task and dependency audit | Astra planner / `mkv_goal_structure_audit` | Read-only draft and written-table audit; no tests or further agents | Initial REVISE on naming/evidence timing; corrected written records received PASS |
| Requirements and migration review | Explorer / `mkv_requirement_mapping` | Read-only existing-contract and validator-schema mapping | Confirmed six validation groups, requirement coverage, pending acceptance, and ledger/schema rules |

Concurrency consent is scoped to this task and active session; a fresh session
must re-establish authorization unless applicable project rules permit it.
The previous review wave ended after integrated planning records and structural
checks. New implementation packages follow the current approved route.

1. On resumption, read all three planning records and applicable instructions;
   verify branch, HEAD, worktree/index, pending approvals, and any live agents.
2. Verify the published planning checkpoints and current implementation changes
   from actual Git state; respect the current package's exclusive writer.
3. Preserve accepted G01/T01.01-T01.03 and implement T02.01/T02.02's Edit/Mux
   executors under their focused safety/native gates, then T02.03 reporting
   and skipped-only continuation. Inspect the
   target's prerequisites and overlap before selecting a bounded implementation
   package; present A/B routes only when they materially change scope/order.

### Dependency-ready restart map

| Order | Task IDs | Required predecessor/readiness evidence | Writer/consumer boundary |
| --- | --- | --- | --- |
| 1 | T01.01 | Accepted: user instruction/naming choice, focused baseline/pure contract proof, parent review | Canonical original-file model; pure retained-order/output helpers |
| 2 | T01.02 | Accepted: registry/configuration/argv contracts and small native builder proof | Canonical shared metadata definitions/configuration/builders |
| 3 | T01.03 | Accepted: actual category configuration, always-multi selection, per-file/skip/subset proof | Real category selection, planning, conflicts, and preview consumers |
| 4 | T02.01, T02.02 | T01.02/T01.03 and G01 accepted | Same source and helpers: one coherent owner; each executor needs its own evidence |
| 5 | T02.03 | Both Edit and Mux executors accepted | Integrated reporting and single/batch workflows; G02 goal gate checked |
| 6 | T03.01 | G01 inputs plus G02 goal acceptance | Preserve approved Extract-after-Edit+Mux stage gate |
| 7 | T04.01, then T04.02 | Runtime task evidence accepted, then integrated candidate verified | Consolidate valid slice receipts; final help/docs follow validated behavior |

The current user instruction authorizes implementation; this readiness map does
not itself accept a code task or authorize concurrent writers of shared files.
Both previous read-only review packages are complete; their planning receipts
contain no media operations, product tests, or CI results.

## Validation evidence and next checks

- Current T01.01 foundation proof: pure helper plus three notified legacy
  journeys passed on the dirty source/test tree based on HEAD `96ae959`
  (`4 passed, 25 deselected in 2.70s`); parent syntax and whitespace checks passed.
  These are focused receipts, not the integrated affected-group acceptance gate.
- A tiny native v93 fixture (PCM audio, SRT subtitles, chapter XML and attachment)
  established grouped Edit/direct Mux metadata parity, blank-title clearing,
  literal leading-`@` titles, `fr-CA` legacy/IETF mapping, correct original-track
  remap, forced flags, multiple true defaults and all-false defaults, chapter XML
  and attachment bytes. Local receipt:
  `.tmp/mkvutil-rework/metadata.scfej9t6/receipt.json`. This used direct tools;
  it does not establish integration of the new builders/executors or all formats.
- The attempted read-only `mkvmerge --language ... -J source` validation is not
  supported by v93 identification mode. Do not use it as a language validator.

- Source/test/documentation review and installed v93 version/help/manual checks
  were completed during this parent session. Source baseline was
  `3c4d4247487babcff7fe23e9f05f2ee554e9f730`; the plan-only commit introduced
  no utility code changes. No runtime speedup was benchmarked.
- `zsh -n shell/mkv_utils.zsh` and whitespace checks passed during planning.
  No source changes followed those checks. They do not prove the new behavior.
- Earlier feature-design Astra audit: PASS WITH NOTES for category batching, shared
  metadata definitions, and direct Mux metadata. Its command-count clarification
  was incorporated. No automated or real-media tests were executed.
- The current structural-rework audit received PASS after preserving the G02
  Extract stage gate, moving naming-contract readiness before preview acceptance,
  and requiring focused executor evidence before final integration.
- The existing pytest harness and small real-v93 fixtures remain the planned
  verification route. Use the approved plan's affected-group gates; do not
  invent a full-suite run per edit or claim historic passes as current proof.
- The current read-only inspection confirmed the shared helper drives copied
  script entrypoints with stdin, fake `fzf`, isolated executables, argument logs,
  and a 20-second timeout. Existing utility tests use text `payload` placeholders
  rather than valid media. No maintained real-media fixture/churn launcher was
  identified in the inspected test/helper and shell locations; do not use old
  pytest copies under `.tmp` as the current driver.
- T04.01 now records the requested near-end rehearsal: adapt the maintained
  harness, generate fresh small all-format fixtures in an owned `.tmp` run
  directory, and keep mocked, real-v93, and terminal evidence distinct. Earlier
  focused executor proofs remain required before accepting their tasks.
- This documentation checkpoint requires link, requirement-mirroring,
  whitespace, privacy, and actual Git-visibility checks, not a media test run.
- Document links/anchors, checkpoint identity parity, personal-path checks,
  whitespace/final newlines, and actual Git visibility passed for these records.
  The index, utility source, and test files remain unchanged.

### Interactive-testing permission

- Status: no broad-campaign execution grant recorded.
- Source: the 2026-10-14 user request schedules `zr0-interactive-testing` near
  the end of the project with custom `.tmp` files and existing tests/helpers.
  It authorizes this planning amendment, not immediate campaign execution.
- Planned scope: T04.01's representative single/batch menu journeys, controlled
  failure cases, and a few serial real-v93 fixture journeys on this Big Sur host;
  no real user files, upgrades, or external effects.
- Before the first broad run, verify or obtain one bounded project grant and
  retain its actual source, limits, and active/revoked state here. Notify before
  light isolated probes; ordinary static/code checks retain their permissions.

### Structural validation receipt

At HEAD `e3cb187975d524087e70ad7ce1e48894c21f0d65` with the documentation rework
uncommitted, the installed skill validators were run through the existing venv:

```zsh
.venv/bin/python -B "$HOME/.codex/skills/zr0-multi-session-projects/scripts/check_plan_integrity.py" plan.md
.venv/bin/python -B "$HOME/.codex/skills/zr0-multi-session-projects/scripts/check_plan_dependencies.py" plan.md --target G03
```

The paths above reflect the resolved skill installation for this receipt;
rediscover it from the active catalogue in future sessions.

- Integrity: PASS, nine task IDs and four goal IDs mirrored; zero accepted tasks.
- Dependencies: PASS, no missing references or cycles; the G03 closure includes
  the G01 foundation and G02 stage before T03.01. Same-layer overlaps remain
  subject to exclusive ownership.
- These validate document structure, not actual implementation readiness,
  runtime behavior, approval, or product test/CI acceptance.
- Parent checks also confirmed exact task-result, prerequisite, overlap, and
  evidence-gate mirroring; the original six validation groups and final
  acceptance paragraph are unchanged from the committed plan. Local links,
  privacy, whitespace, code fences, unchanged source/index, and trackability
  checks passed. Both review agents completed; no review job remains active.

For the subsequent rehearsal-planning amendment, the validators were rerun at
HEAD `b468c0b90c655906083eac0d0fcb6351398d605d` before committing the new records:
integrity PASS (nine tasks, four goals, zero accepted) and dependencies PASS
with `--target G04` (no dangling references/cycles, existing sequence preserved).
Exact task-contract/evidence mirroring, local links, privacy, whitespace, and
fences passed. The original six validation groups are preserved. Only the three
planning records changed; no product tests, interactive journeys, or real-media
processing ran for this documentation amendment.

## Approval boundaries

The user approved project-instruction creation and trackable repository planning
records, then explicitly requested this goal/task/dependency restructuring and
authorized concurrent agents for the current task/session. The four checkpoint
requirements and six validation groups are preserved; no gate was waived.
Future sessions must recheck concurrency consent. Any agent-proposed contract change
requires a concrete user-approved proposal before editing plan/checklist rules.
New unrelated AGENTS edits require their own authorization. The user's existing
commit/push authorization covers these feature-branch planning records; the
subsequent request adds the future rehearsal within that scope. The latest
"ok you may begin" authorizes approved implementation, and the follow-up replies
authorize the self-contained script and retained-content naming contracts.
Deployment, dependency installation, real user-media mutation, and broad
interactive campaigns remain outside the recorded authorization.
