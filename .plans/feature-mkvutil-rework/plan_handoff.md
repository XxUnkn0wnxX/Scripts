# mkvutil rework handoff

<!--
Verified parent Codex session IDs (append only; no child IDs):
Codex Session: 01a13610-202e-7613-af35-d95dfaa33fa8 | verified 2026-10-14 Australia/Melbourne |
CODEX_THREAD_ID corroborated with matching CLI session_meta ID and repository cwd,
plus the current user's tracking/AGENTS approval in that same session's log.
-->

[Authoritative plan](plan.md) · [Acceptance checklist](plan_checklist.md)

Canonical tracked records: `.plans/feature-mkvutil-rework/`. Source, test commands
and `.tmp` receipt paths below are relative to the repository root.

## Current state and safe restart point

### Accepted owned-menu screen amendment

- User-directed screen ownership and restored Category selector are implemented
  in the same script, on feature in the main Scripts checkout. Baseline signed/
  published `ada2fd4e0476a991f233c8a5f743baaa84fd4b71`. Each navigation menu
  replaces previous choices; main 1/2/3 and hidden e/E act immediately. Submenu
  e/E remains Back, and ordinary value fields remain line-based with literal e.
- Astra's focused audit passed with notes. Navigation alone uses an owned
  alternate screen; normal screen/cursor is restored before picker, fields,
  validation, processing, previews and reports. TTY-only acknowledgements keep
  preview/mismatch details and scope reports readable before menu reentry.
  Final successful Run reports and exits. Redirected/dumb streams retain plain
  input without alternate escapes or extra acknowledgement reads.
- Physical keyboard tests exposed blocked-read Ctrl+C at a line menu and Title.
  Local menu/acknowledgement handling and four lines across the two existing
  prompt boundaries fix this; values/defaults/validation bodies and queue traps
  remain unchanged. Final Title/removal-ID/line-menu Ctrl+C exits are verified.
- Current proof `.tmp/mkvutil-rework/owned-menu.G4F1G9/receipt.json`: 15 affected
  consumer/configuration cases pass on final source. Five earlier presentation
  PTY cases pass; parent verified their source differs by exactly the four
  prompt-trap lines. Three final-source field/line PTY cases pass. This is 22
  distinct cases in separate runs, not one final-revision 22-case invocation.
  Those three accepted runs total 23.55s wall / 21.62s measured CPU. All failed
  attempts remain, including a corrected 98.81s wall / 95.83s CPU harness EOF
  spin, echoed-CRLF oracle corrections and bounded submenu/Title hangs. Guards
  were not raised; no native/full campaign or CI run was repeated.
- Parent review in `parent-review.json` verifies actual logs/runtime-copy hashes,
  exact earlier-PTY source delta, 19 protected engine/builder/safety sections,
  unchanged test helper, source/guide claims and unchanged parent-session ledger.
  Syntax/AST/whitespace and stable-record checks pass. Current source SHA-256:
  `258a8b8581b120469f306da833662002ad180e9d70cf8f2333b3140d7a5410b1`.
  Tests: `2fe04ac509a345fa3a18a9a5133e5ae76231cd13ec8d1864959217563c3e9fb7`.
  Guide: `696a84dbb88b67fd8724ec7229b0eb5a26b964879a299514b0c907deb91da32a`.
- T01.03/T04.01/T04.02 and G01/G04 are reaccepted; current amended scope is
  **9/9 tasks and 4/4 goals**. Original IDs, dependencies, permissions and native
  receipts are preserved. Writer and owned processes are quiescent. No runtime
  dependencies, extra zsh files, worktrees, branches or AGENTS edits were added.
- Feature commit/push remains authorized. After publication, verify the containing
  signed commit and live feature ref against this folder's `publication.json`.
  No implementation/verification work remains; on resume read this boundary and
  the corresponding current checklist rows before selecting any new work.

### Historical: Accepted direct shortcuts and cursor restoration

- User clarified main categories are direct shortcuts, with hidden main e/E
  exit and submenu e/E Back. Baseline signed/published
  `f99b96e7a9ab6c2c46d207ab84f38a40035e2ed0`; stay in feature/main Scripts.
- Interactive main no longer shows a Category input prompt. Cursor is hidden
  during capable-terminal key wait and restored before submenu/data input,
  hidden e exit and one keyboard Ctrl+C. Keys 1–3 remain immediate; optional
  Enter remains harmless. Pipe input/collectors/queues and shared helper are
  unchanged. No worktree, branch, AGENTS or dependency change.
- Initial keyboard Ctrl+C failures are retained. Matching zsh primary source
  explains interrupted unbounded key reads; local traps now use a 0.2s kernel
  read wait to yield, a timeout/EOF sentinel and always cursor restoration.
  Read-only explorer checked primary docs/source; parent integrated and proved
  behavior on installed zsh. No idle busy loop, new tool or raised test guard.
- Proof `.tmp/mkvutil-rework/menu-display.uJfcXR/receipt.json` / `accepted.log`:
  4 passed, 1.55s wall / 1.23s measured CPU. Two controlling-PTY journeys cover
  main keys, no Category prompt, correct hide/show ordering, ICANON/ECHO before
  fields, hidden e and keyboard Ctrl+C; pipe exit/state checks also pass. Source
  payloads are unchanged with zero media/fzf calls. Failed logs/minimal trace
  are retained; no native/broad campaign was repeated.
- Exact source comparison proves only main reader/call changed. Parent final
  source/tests/guide/records and stable-ID/session-ledger checks pass; all 9 tasks
  and 4 goals are accepted. Owners/processes are quiescent. Standing feature
  commit/push permission applies. On resume verify the containing commit and
  this proof folder's publication.json; no implementation/validation remains.

### Historical: Accepted immediate main-menu keys

- User-directed follow-up on the same feature branch/main Scripts checkout,
  baseline signed/published `4d13de3088b5844465ca730208629a44efcadbf9`.
  Main terminal choices now react to one `1`, `2`, `3`, or hidden `e`/`E`
  keypress; no Enter is needed. An optional trailing Enter is harmless.
  Submenu batch selections, text fields and piped input remain line-based.
- Current proof: `.tmp/mkvutil-rework/main-keys.AVETLa/receipt.json` and
  `accepted-final.log`: one real controlling-PTY journey, one piped hidden-exit
  journey and one interruption contract passed (3 cases, 2.58s wall / 1.89s
  measured CPU). PTY proof covers all categories without newline, submenu Back,
  immediate hidden exit and restored ICANON/ECHO before subsequent line input.
  Fake media/fzf boundaries recorded zero calls; source payload is untouched.
- Exact source comparison proves only the new main reader, its call site and
  harmless terminal blank-action reprompt changed. Media engines, data collectors
  and the shared test helper are unchanged. Syntax, diff, docs and stable-ID
  review passed; all 9 tasks and 4 goals remain accepted at current scope.
  Four initial setup/reader/harness failures are preserved with causes; no
  timeout was raised or native/broad campaign repeated. Workers are quiescent.
- Commit/push is authorized. The proof folder's `publication.json` will contain
  the verified signed commit/live feature ref. On resume verify that receipt and
  the containing commit; no implementation/validation remains for this change.

### Historical: Accepted user-directed navigation follow-up

- Stay in the main Scripts checkout on `feature/mkvutil-rework`; the user
  authorized these changes and their push. No worktree, branch, AGENTS or
  dependency change is part of this follow-up. Baseline short-help checkpoint:
  `a30e88cfa09ae3c5149bdeb2a13b5ddbc238bac4`, signed and published.
- The approved Ctrl+C/Back amendment is implemented and accepted. Main lists
  categories 1–3 only; hidden `e`/`E` silently exits. Submenu Back retains the
  current selected sources/exclusions/history and discards configuration/jobs.
  Newly confirmed actions create separate requested-batch rows. Main reentry
  rescans files. Post-Run Back reports the old scope once; fresh skipped-only
  preparation remains explicit, and completed files are never replayed.
- Input fields are unchanged: literal `e` works as a name/title, while IDs,
  flags and languages validate it normally. EOF/Ctrl+C ends without restarting
  or resetting interrupted state. Earlier unresolved failures remain nonzero
  even after a later neutral cancellation. Successful Run reports and returns.
- Astra's intermittent design audit passed with notes; its action-attribution,
  fresh-discovery and pre-Run skip-preservation corrections were incorporated.
  Parent reviewed source, test oracles and guide, independently checked package
  hashes, 21 unchanged protected function sections, unchanged test helper and
  unchanged parent-session ledger, and reconciled all stable plan/checklist IDs.
- T01.03 and affected T04.01/T04.02 gates are accepted with current proof.
  **Current amended-scope acceptance: 9/9 tasks and 4/4 goals.** Combined focused
  evidence: 10 new navigation cases plus 8 existing affected cases; recorded
  serial runs total 32.79s wall / 26.65s measured CPU, no failed attempts and
  no raised guards. Exactly three permitted mocked entrypoint IA probes passed
  with disposable payloads and zero media modifiers. No native/broad campaign
  was repeated; historical unchanged-engine receipts remain reusable.
- Proof: `.tmp/mkvutil-rework/navigation.t1I48Y/receipt.json`, exact logs and
  `parent-review.json`. Final source SHA-256:
  `7c47095dc9eb0c43c26b426597f570d6a924e9c5c6e1c4d8bd43bdf6042561c9`.
  Tests: `209a931b5e7a239aa2ed166c44217c1e4f4390cbd5270548018eeff5ac9654ba`.
  Guide: `3799f989dd2b29d2524c6abb8a6747b49a63df674fd53987a6775422c41397ff`.
  IA source differs only by the subsequently checked registry-error propagation
  guard; parent independently proved that exact delta. All workers/processes
  are quiescent and source ownership is returned to parent.
- Published signed `4d13de3088b5844465ca730208629a44efcadbf9`; live feature ref
  and clean checkout were verified in this proof folder's `publication.json`.
  The small IA grant was used for three probes; it was not a renewed broad grant.

### Historical: Completed original rework and checkout return

Migration evidence: `.tmp/mkvutil-rework/return-main/before-move-inventory.json`
and `after-move-verification.json`. The pre-existing main project scratch was
retained within `return-main/previous-main/`. Historical receipts and drivers
still name Scripts-dev; their preserved artifacts now live under this checkout's
`.tmp/mkvutil-rework`. Preserve original logs rather than rewriting tested paths.

- Final housekeeping is complete: the original `Scripts` checkout now owns
  `feature/mkvutil-rework`; `Scripts-dev` was removed with normal Git worktree
  removal, without force or branch deletion. Only `.tmp/mkvutil-rework` was
  carried back. Its 37,831 inventoried entries and 101,628,108 file bytes were
  verified after the move, including literal symlinks and recovery directories.
  Other retiring-worktree scratch was discarded as the user instructed.
  The existing main `.venv` and unrelated `.tmp` contents remain in place.
- Tracked plans are in `.plans/feature-mkvutil-rework/`. Approved AGENTS rules
  match byte-for-byte on feature, develop and master and all were pushed:
  feature policy `fd9bc72492abfabc5fcfdbeefedba23a2c235b48`,
  develop `ce235f88f32acd620c63b4b906158e468f8b7156`,
  master `b9eb27c883ea3cf57cb230660417baa2f96e0766`. Each policy commit changes
  only AGENTS. The utility rework remains on the same feature branch.
- All four main goals and nine tasks are accepted after parent review,
  current receipts and Astra's independent audits. Current acceptance is
  **9 / 9 tasks and 4 / 4 goals**. The campaign writer is quiescent, with no
  active sessions; source/test/helper hashes and immutable fixtures are verified.
  Current coverage comprises 128 cases: 125 unchanged full-suite passes plus 3
  corrected cases, with all assertions and existing guards retained. Three native v93
  journeys and real-fzf two-file preview/Cancel are verified. Historical
  failures remain preserved and do not represent open runtime defects.
- T04.02 is accepted after complete guide/README/source-help review and actual
  help/syntax/link checks. Executable bodies equal the native-qualified G03
  source byte-for-byte; only comments/help changed. Final parent receipt:
  `.tmp/mkvutil-rework/final-review.icdu2_ji/parent-final-review.json`.
  All runtime/documentation goals and requested checkout operations are done.
  This is the final administrative checkpoint. On resume, verify the commit
  containing this record against the live feature ref; no runtime or
  documentation work remains. All workers are quiescent and no test/native
  process remains active.
- The user-requested real code/checklist audit reopened missing normal
  multi-file Edit proof, added a focused passing test, and corrected stale
  progress/restart statements. Safe snapshot and findings remain under
  `.tmp/mkvutil-rework/checklist-audit.wni4h33r/`; the parent-session ledger is
  unchanged. The two discovered reporting defects were subsequently fixed and
  independently tested; do not treat their historical audit notes as open bugs.
- T02.03 accepted candidate hashes and exact checks are saved in
  `.tmp/mkvutil-rework/reporting/t02.03-receipt.json`, with parent review in
  `parent-integration.json`. Script SHA-256:
  `fed393cdb7c729f219ca1d5d51f059ccdbededd60e840e3bacc245e471d2cc8c`.
  The accepted metadata/executor bodies are unchanged from the native-qualified
  `f44cd98` checkpoint. This is the historical G02 source binding; current G03
  source binding is in its Extract receipt below. Integrated legacy/all-format/
  campaign checks and final documentation remain pending.
- Active workspace: main `Scripts` checkout, on `feature/mkvutil-rework`,
  explicitly requested by the user after final publication. Git inventories
  exactly this one worktree. Resolve its root from Git; no sibling worktree
  is required. The former dedicated-worktree AGENTS rule has been removed.
- Historical initial move to Scripts-dev: all five pending tracked-file changes were copied and SHA-256 verified before
  restoring the original checkout. Existing approved local `AGENTS.md` was
  copied unchanged; current `.tmp/mkvutil-rework` fixtures/receipts were preserved.
  Local recovery snapshot: `.tmp/mkvutil-rework/migration.rbow6b82/manifest.json`
  and its five file copies. This is a pre-migration snapshot, not current code.
- The former worktree reused the original checkout's Python environment through
  an ignored `.venv` link. A narrow `/.venv` entry was added to the common clone's
  local `info/exclude` because the tracked directory-only ignore doesn't cover
  a symlink. No tracked ignore rule or dependency installation changed.
- Historical initial relocation verification passed: same pure foundation contract
  (`1 passed, 28 deselected in 0.15s`), script syntax/whitespace checks, and the
  existing Python package environment. Initial test setup lacked a temporary
  parent directory; rerunning in a fresh owned run directory passed without
  product changes.
- Verified published G04 feature checkpoint:
  `c15f7c81187280dfe449b4a17581ef507e68894a`
  (`test(shell): finish mkvutil integration and guide`), signed. The user
  authorized automatic main-goal pushes; this completes the rework publication.
  G03 remains `b749135cdfa52b7b1ec2fbe1a63de8f064700f1f`, and G02 remains
  `1bb755e1fd033d66dcefb6f431f826cafe89e262`. Develop/master now contain the
  matching AGENTS-only update above. Resolve latest feature HEAD from Git;
  this final administrative handoff checkpoint follows the G04 code checkpoint.
- Prior accepted execution checkpoint at the audit: signed
  `f44cd9841e00d9d86ffaffcae7b2a5ae520de278`
  (`feat(shell): execute grouped mkvutil edit and mux jobs`). It was four
  commits ahead of the published feature ref. Resolve latest local HEAD from
  Git; the audit record correction is a separate documentation checkpoint.
  This execution checkpoint commits only
  the six approved source/test/planning paths and accepted T02.01/T02.02
  evidence; both worktrees were clean immediately afterward. The former pending
  T02.03 source/test work and the audit's additional test are committed at
  signed `1bb755e1fd033d66dcefb6f431f826cafe89e262`; the tree was clean afterward.
  The preceding audit record correction is signed `22eb849`. The attachment
  policy is committed at signed `3567fe7`; the accepted T03.01 package is
  committed/published at signed `b749135`. Both worktrees were clean immediately
  after publication verification. Current uncommitted paths are the parent
  checklist/handoff and T04 utility test/helper; the campaign writer owns those
  test paths and private execution artifacts. Source is unchanged/read-only.
  Accepted G01/G02 implementation is now published on the feature branch;
  no promotion or live deployment has occurred. Prior G01 checkpoint is signed
  `6444e4cbbe65ffe1a81d18213582695ea242cb8e`; the reporting-plan checkpoint
  is signed `66dab50d610d4f011bdae0e685d3fca492c107f3`.
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
  and approved output extensions; T01.03 subsequently integrated their consumers.
- T01.02 is accepted after parent review of the shared registry, configuration,
  flag snapshots and two pure argument builders, five focused unit contracts,
  and small native v93 builder proof. That package is complete; the same writer
  completed T03.01 and T04.01 preparation; it is quiescent pending the campaign
  grant and next bounded execution assignment.
- T01.03 and G01 are now accepted after parent review and final selector/removal
  proof below. Categories, configuration, per-file planning, skip receipts,
  preview and fresh skipped-subset preparation are implemented. Executors
  for Edit/Mux are implemented and their T02.01/T02.02 gates now accepted after
  focused/native proof, parent review and Astra's bounded post-fix PASS.
  T02.03's current reporting/continuation proof subsequently closed G02.
  Extract execution is accepted after its focused/native and review gates.
  Current totals: 9 / 9 tasks and 4 / 4 goals.
- No runtime or documentation package remains pending. G04 is accepted;
  this handoff records the completed publication and checkout operations.
  The approved campaign finished within budget; no repeated broad run is needed.
- T02.03's implementation draft uses an original-source-keyed final-outcome
  ledger separate from current scope/jobs/skip receipts, plus saved per-batch
  action/configuration/time attribution. History is provenance, not unresolved
  status by itself. Completed sources cannot re-enter skipped-only cohorts;
  fresh inspection/configuration/review/Run is required each time. The bounded
  Astra audit returned PASS WITH NOTES before sole-writer implementation.
  Reuse `mkv_metadata_foundation` for the same three source/test paths after
  the audit handback. The completed T02.03 package is now accepted and its
  writer was quiescent at the G02 checkpoint and has since resumed T03.01.
  Extract execution, final guides and broad menu campaigns stayed outside
  T02.03. Parent remains the only record writer.
- The user requested always-multi selection and automatic removal mismatch
  skips with skipped-only follow-up batches. Astra verified this delta before
  any new requirement/code edits; the parent updated the authorized plan and
  checklist, then the same source/test owner implemented the G01 portion.
- Broad interactive campaign permission is active for the prepared T04 scope
  and budgets below. Small isolated probes are notified; ordinary code/static
  checks retain their permissions. No acceptance is implied by the grant.

### Refreshed worktree coordination

- Rediscovered and reread `zr0-git-repository-workflow`,
  `zr0-parallel-execution`, and `zr0-multi-session-projects` on the user's
  refresh request. The Git worktree reference and current handoff template
  loaded successfully. At that earlier refresh, some referenced documents and
  multi-session validators were absent. The latest user-requested refresh
  rediscovered/reloaded the multi-session skill, all four relevant references
  including updated resumption/audits, and both now-installed validators.
  Those structural checks pass; no record migration or approval change applies.
- Canonical records are the tracked `.plans/feature-mkvutil-rework/plan.md`,
  `plan_checklist.md`, and `plan_handoff.md`. The user explicitly requested
  this relocation on2026-10-14 while retaining `feature/mkvutil-rework`.
  The corresponding AGENTS-only policy is signed at `fd9bc72`; propagation
  to develop/master is complete and pushed at the matching commits above. Historical root copies in
  other branches are not competing project masters.
- Runtime default cwd remains the original `../Scripts` checkout. Every tool
  command must explicitly use `../Scripts-dev`; workers must provide a verified
  Git-root/branch/status receipt there before writing. This is explicit tool
  routing, not a claim that a prompt changed the session's process cwd.
- Linked checkout inventory was reverified during the code/checklist audit:
  `../Scripts` owns `develop` at `e6dd2b94fd489796df80270814aa040bc19db8a8`;
  `../Scripts-dev` owns `feature/mkvutil-rework` at signed `f44cd98`.
  Both branch assignments remain unchanged.
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
| `plan.md` | Authoritative requirements, goal/task IDs, dependencies, and four checkpoint identities | Tracked under `.plans/feature-mkvutil-rework/` |
| `plan_checklist.md` | Mirrored checkpoint and validation acceptance evidence | Tracked companion under `.plans/feature-mkvutil-rework/` |
| `plan_handoff.md` | Verified current state, approvals, lineage, and next actions | Tracked companion under `.plans/feature-mkvutil-rework/` |
| `AGENTS.md` | Approved durable project instructions and planning-record locator | Tracked, matching and pushed on feature/develop/master |

On 2026-10-14 the user replied **"for repo plan etc can be tracked & ya
approved"** to the proposal for project instructions. This approves creating
`AGENTS.md` and overrides the private `.tmp/` default for the planning companion
records. The original placement was the repository root; the user now
explicitly changed it to `.plans/feature-mkvutil-rework/`, still tracked. The original local AGENTS file initially reused the
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
  requested. Concurrent agents are authorized for this task and active session.
  Implementation and accepted-goal pushes have their separate user grants;
  concurrency itself grants neither action.

## Historical acceptance before final integration

Planning preparation is verified and remains separate from implementation
acceptance. The four existing checkpoints are now G01-G04, with nine stable
task IDs. At this earlier checkpoint, **7 / 9 tasks and 3 / 4 main goals** were
accepted (T01.01-T01.03, T02.01-T02.03, T03.01, G01-G03); later G04 and menu
amendment acceptance is recorded at the current top boundary.

The executor checkpoint has now closed the following focused gates:

- Verified actual v93 default-flag parity for intended retained-track states,
  plus blank-title clearing and literal-title handling through `mkvmerge`.
- T01.01's approved retained-content naming helper and T01.03's complete
  per-file preview/removal/selection consumer evidence are accepted.
- Validation binds intended track identity and explicit final order per file;
  do not assume track positions or MakeMKV UIDs survive a remux unchanged.
- Checked safe staging/promotion, collisions, warning/error distinctions,
  interruption behavior, and correct success reporting.

T02.03's complete final reporting, timing and fresh skipped-only continuation
are accepted. G02's combined workflow gate passed parent and independent review.
Extract execution, integrated all-format/legacy navigation qualification and the
near-end interactive campaign remain later gates.

### T02.03 and G02 accepted integration checkpoint

- Worker is quiescent; candidate source/test/helper hashes match its receipt
  and all copied final-contract/CLI runtime files. Its 12 focused contracts
  passed in 37.38s (37.95s wall, 35.02s combined user/system CPU); one notified
  mocked continuation journey passed in 7.15s (7.78s wall, 7.18s CPU).
- Parent reviewed the accumulated ledger, category controller, queue/reporting
  code and shared accepted foundations. Two critical independent cases passed
  in 3.59s (4.41s wall, 2.78s CPU): between-job TERM with pending sources and
  mismatch skips; post-tool clock failure with actual completed state retained.
  Exact command/log is in `reporting/parent-integration.json` above.
- Astra independently returned PASS for T02.03 and reviewed G02 gates. Current
  tests prove unique original-source counts, resolved history, distinct initial
  versus retry exclusions, preserved results after cancellation/EOF, separate
  action/optional metadata attribution, directory basename, Mux timing/ETA,
  all Edit choices' final-only reporting and old 1+2 / 8+4+3 / 7+8+4+3 equivalents.
- The actual mocked continuation path selects once, runs one initial eligible
  source, refreshes only the mismatched source, clears old settings, and requires
  a new Preview/explicit Run: two total output remuxes, zero propedit, final
  Done 2/Skipped 0, resolved history. Identification/tag reads are counted
  separately. No broad or new native campaign ran.
- All eight recorded native-qualified core functions plus the shared metadata/
  language prefix remain byte-identical; prior native proof remains scoped to
  those internals. Extract's reporting formatter contract is ready, while its
  executor and real extraction proof remain pending. G02 acceptance does not
  credit the six final validation groups or near-end rehearsal.

### User-requested code/checklist audit — prior correction checkpoint

- Trigger: a stale aggregate checklist count, followed by the user's request
  to pause for a real audit. The sole source/test writer stopped safely with
  no running subprocesses. Snapshot:
  `.tmp/mkvutil-rework/checklist-audit.wni4h33r/snapshot/`;
  machine-readable findings and exact source/test bindings:
  `.tmp/mkvutil-rework/checklist-audit.wni4h33r/audit-receipt.json`.
- Reviewed accepted `f44cd98` and the frozen T02.03 draft SHA-256 `312ff6f…`;
  all nine task requirements, evidence requirements, prerequisites and overlap
  fields match the authoritative plan exactly. G01's source/test/receipt
  mapping remains supported at the accepted revision. The dirty controller
  cannot inherit its old entrypoint proof automatically.
- Astra independently found missing normal multi-file Edit proof. Parent
  reopened T02.01 (temporarily 4/9), added one two-file grouped queue test with
  different source listing positions and unrequested property values, and
  reaccepted after it passed: `1 passed, 11.44s` (12.62s wall, 9.00s combined
  user/system CPU). Exactly one propedit per source; no output remux. The first
  test draft wrongly prohibited read-only tag inspection and was corrected;
  it was not a runtime fix. Logs `two-file-edit.log` and
  `two-file-edit-fixed.log` preserve both attempts in the audit directory.
- One notified existing mocked mismatch/preview/Cancel journey passed on the
  frozen controller: `1 passed, 4.05s` (5.11s wall, 4.00s combined user/system
  CPU). One always-multi selection, exact ID/type/codec mismatch receipts,
  identification-only calls and unchanged files are asserted. Log:
  `controller-cancel.log`. This rechecks one affected G01 path, not the complete
  T02.03 consumer or final interactive gate.
- T02.02 passed independent accepted-executor review with its documented
  TrackUID-zero refusal and SRT timestamp limitation. All three native-receipt
  implementation hashes match `f44cd98`, all five native result records are
  successful/validated, and immutable fixture hashes agree. Eight core
  planner/builder/executor bodies remain unchanged in the draft; their globals
  and call sites were reviewed. Historical native proof does not qualify the
  changed queue/controller/reporters.
- That audit identified two concrete T02.03 defects: its queue trap set only
  a local interruption flag, while the controller used the global flag to
  suppress continuation; and ledger status did not reject required not-attempted
  work after Run. Both were subsequently fixed and verified at the accepted
  G02 checkpoint above: a signal between jobs stops later sources/continuation,
  pending outcomes remain visible and the result is nonzero. Neutral cancellation
  before any Run is preserved.
- Legacy flat-menu journeys remain unmigrated and cannot establish current
  navigation behavior. Their semantic assertions and all six validation groups
  remain required at the existing integration gate. Extract remains guarded.
  No broad menu campaign, native campaign, publication, plan-contract change,
  AGENTS edit, worktree change or dependency installation occurred in this audit.
- All current totals and restart descriptions were reconciled; prior package
  briefs are explicitly historical. The original parent-session ledger, IDs,
  order and provenance are unchanged; SHA-256 `fefdffb5…14cab` verified against
  the snapshot. Structural validators pass separately from code/evidence review.
- At subsequent checkpoints, derive accepted task/goal totals from the actual
  checklist rows and compare every current summary before reporting progress.
  Verify each accepted task's required evidence against the tested revision and
  affected consumers; an unchanged helper hash does not qualify a changed
  consumer. Reopen unsupported acceptance and retain historical receipts.
- Audit handback: parent added only
  `test_mkv_utils_executor_two_file_edit_keeps_source_selectors_and_properties`
  to the utility tests. Resume the existing source/test owner on the same
  feature worktree with that test preserved. First resolve the two T02.03
  defects, then complete its pending focused ledger/continuation/reporting
  tests and the single notified continuation probe. Do not start Extract
  before T02.03 and the G02 goal gate pass.

### Approved attachment-collection amendment and Extract preparation

- The user clarified that attachments are intentionally collected from many
  sources into one shared folder for their existing `mkvmux` workflow, with
  matching names/formats overwritten. This directly authorizes the narrow
  attachment-only overwrite exception now mirrored in plan/checklist T03.01;
  no further approval is pending for it. Keep embedded names and `Attachments/`
  for both single and batched jobs. The last successfully published attachment
  wins in selected-source order, then original attachment-list order.
- Astra's quick amendment audit passed with notes: unique internal staging per
  attachment ID even for repeated names within one source; filesystem-aware
  attachment matches allowed, but input inode aliases, unsafe names, directory/
  symlink leaves and attachment-versus-track collisions remain protected.
  Stage success precedes checked atomic replacement; later failures retain
  earlier collection and truthful staged/partial/supersession records. Do not
  impose content/checksum/MIME equality or add per-file overwrite prompts.
- Track sidecars and companions remain protected from overwriting. No new Mux
  action is inferred: the user's stated downstream `mkvmux` workflow is separate
  from the approved Remove/Reorder utility submenu.
- Read-only installed-v93 manual/source review prepares T03.01. Official source
  archive was downloaded only for reference into ignored
  `.tmp/mkvutil-rework/v93-extraction-source/`; its SHA-256 matches the vendor's
  published checksum. No installation, upgrade or build occurred. Receipt:
  `reference-receipt.json`. VobSub replaces the last extension with `.idx`/`.sub`;
  WavPack may create a `.wvc` correction sidecar; TTA creates temporary files
  relative to child cwd. Attachments and USF use their explicit output paths;
  cue sheets require an option the utility does not pass. Native selected-source
  proof is still required; source inspection is not that proof.
- Parent identified a codec-map integration issue for T03.01: installed
  `pymkv.TypeTrack` keys include PCM/TRUEHD/WAVPACK4/VOBSUB, whereas native IDs
  use `A_PCM/INT/LIT`, `A_TRUEHD`, `A_WAVPACK4` and `S_VOBSUB`. The planner's raw
  last-slash lookup misses several mappings. Correct native-ID translation
  within the existing precedence contract and add actual-ID proof before
  extraction acceptance; avoid treating synthetic short-code tests as native
  format evidence.
- The bounded shared-support/interface audit passed. One static literal
  Python support section in the same `.zsh` owns mechanical identity/inode,
  child execution/shutdown and interruption initialization; engine-specific
  oracles, phase receipts and publishers remain separate. Child `cwd=None`
  preserves Edit/Mux defaults; Extract uses an owned cwd without process-wide
  `chdir`. Current executor/signal/two-file Edit and small native Edit/Mux proof
  are required after changing assembled runtime code; do not claim old whole
  function hashes qualify a refactored engine.
- Physical artifact records distinguish attempted/confirmed/uncertain
  publication and reconcile captured identities. Confirmed attachment records
  retain filesystem-aware destination keys and deterministic order for final
  winner/supersession reporting. Never infer winners from timestamps.
  Unstarted stages have null codes/times. Combined progress still shows file
  counts if attachments fail before tracks, but records track timing as not
  attempted; ETA uses actual track attempts, not artificial zero samples.
- Provisional Extract interface: keep logical requested outputs/one native
  argument per selected item separate from physical artifact families. Reserve
  both VobSub outputs and possible WavPack companions before Run; contain native
  scratch files in an owned cwd. Use per-stage receipts/checked publication,
  attachments first then tracks. Empty attachments/text outputs may be valid;
  require expected regular outputs and identified attachment sizes where known,
  rather than a blanket nonempty rule. Common final reporting/timing consumes
  T02.03's accepted interfaces. The assigned writer has begun codec/artifact
  planning and a focused four-format no-mutation case passed; this is diagnostic
  evidence, not Extract acceptance. Shared-support/source code work remains
  subject to its focused regression and small current native proof.
- Parent prepared and native-validated a tiny VobSub fixture without changing
  source/tests: `.tmp/mkvutil-rework/vobsub-native.88m3m7yy/tiny.mks`
  (6,136 bytes; SHA-256
  `57b1b13a4bff92f3537d28e3f26b5229a0bd75d779cd761a4b913cba52059a99`).
  Installed v93 creation and source-first extraction both returned zero;
  original `.idx`/`.sub` inputs were unchanged and extraction produced both
  required physical artifacts. Track `0` is `S_VOBSUB`; exact commands,
  identification and hashes are in `creation-receipt.json` beside the source.
  This validates the reusable fixture, not the utility's Extract executor.
  Writer receives a copy for current executor proof. The native slot was
  released before the writer's next test/native run.

### Accepted T03.01/G03 checkpoint

- Candidate source SHA-256:
  `997577ccbe412f451ac9cf0c9c4aa9a0604ef964c1d648d91ee38f3dd97e5408`.
  Current package hashes, exact commands, saved logs/CPU timings, API and
  evidence limits: `.tmp/mkvutil-rework/extract/package-receipt.json`.
- The initial 29-case affected pass (93.86s) and one protected-leaf contract
  remain scoped historical proof. After audit corrections, 12 affected cases
  passed (26.70s), the same single notified CLI passed (3.54s), and two current
  consumer checks passed (9.71s). Earlier failures are retained and labelled;
  none is credited as a pass. Syntax/AST/whitespace checks passed.
- Parent independently passed missing-track validation and late-cleanup
  reporting (2 passed, 91 deselected in 4.84s; wall 5.62s, user 2.83s,
  system 1.88s). Parent verified all three current package hashes and native
  payload hashes on disk. Review record and log:
  `.tmp/mkvutil-rework/extract-parent.2846jape/parent-integration.json` and
  `critical-tests.log`. Intermediate assembly is explicitly retained separately.
- Current native Extract proof:
  `.tmp/mkvutil-rework/extract/native.6tkeny9a/native-receipt.json`.
  Execution-start/after package hashes match; source hashes are unchanged;
  selected text/attachment and VobSub pair succeed with installed v93. Native
  SRT adds a UTF-8 BOM and rounds the tested 200ms cue end to 199ms; text/start
  remain unchanged. WavPack/TTA use focused fake plus verified-source evidence,
  not a native codec matrix. Genuine all-format integrated coverage is T04.
- Edit/Mux's current captured program remains byte-identical to its initial
  native requalification (`7687974306897bbb52370aa373eb48122a46a51c464c9a9e839158577acc4b92`).
  Current Extract program:
  `51fa85519fcab6426d19e4d17890af4a251c6e211fc3c4b7a9c4e0419fddd3da`.
  Shared support and metadata/executor invariants are preserved; relevant
  consumer checks passed. No unnecessary repeat native Edit/Mux campaign ran.
- Astra first returned REVISE on active-stage classification, cleanup inventories
  and preview overwrite disclosure. The sole writer fixed/proved these plus
  full-identity reconciliation; independent post-fix review returned PASS WITH
  NOTES. Parent's two checks and intermediate-record refresh close those notes.
  G03's single/batched execution and goal-level integration gates are accepted.
  T04 full affected suite, old navigation migration, broad interactive campaign
  and final docs remain unchecked. No campaign grant, promotion or live change
  is inferred from this milestone.

## Execution route and next actions

The user authorized `parallel-execution` in this active session, then approved
beginning the implementation. Current route B and foundation-first scope are
recorded in the restart section above. The preceding coordinated documentation
package is complete; its receipts below are historical.

### Implementation checkpoint history

This section preserves successive package briefs and receipts. Earlier “next”
steps and pending claims describe their stated checkpoint; use the current
restart section and audit result for present readiness.

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
- Active next package T02.01/T02.02: reuse `mkv_metadata_foundation` as the sole
  writer of `shell/mkv_utils.zsh` and the existing utility test/shared helper
  files in `Scripts-dev`. Prerequisites and G01 goal gate are accepted. Add
  grouped Edit and one-pass Mux execution, read-only result inspection, owned
  staging and corrected publication/recovery phases; connect only these
  executors through a minimal queue consumer. Shared builders/planning stay
  canonical. T02.03's complete ETA/continuation/result-ledger behavior and G03
  extraction execution remain subsequent gates. Parent owns all records.
- A separate read-only `mkv_requirement_mapping` preparation pass may map the
  existing Extract planner, legacy command contracts and focused tests while
  the executor writer works. It owns no files, runs no media-producing commands
  or tests, and cannot start/accept T03.01 before the G02 goal gate.
- That preparation pass is complete: Extract jobs already have ordered
  `outputs` records (attachments, then requested original track IDs) and queue
  collision checks. Installed v93 uses source-first `mkvextract SOURCE
  attachments|tracks ID:OUTPUT...`; preserve separate grouped stages and
  stop later stages for a file after an incomplete stage. Codec extension
  precedence is explicit overrides, full/short TypeTrack map keys, then safe
  normalized fallback. The legacy attachment/OPUS/TrueHD assertions need
  category navigation migration and the fake needs source-first stage/output
  support. This is preparatory evidence only, not T03.01 implementation or
  acceptance; existing planned output names remain unchanged.
- Bounded language evidence is complete: installed `bcp47` provides lookup
  dictionaries, not a full tag canonicalizer; `iso639.Language.match` resolves
  simple ISO aliases but not full or deprecated BCP47 forms. Do not invent
  preferred-subtag mappings from these libraries. The parent approved explicit
  v93 `--normalize-language-ietf off` in both executor commands, subject to
  native support/proof, to preserve untouched and requested IETF forms under
  the existing language-preservation contract. Use exact case-insensitive tags
  plus locally resolvable simple ISO equivalence; the native parser determines
  acceptance. Edge tags and full executor preservation remain native gates.
- Next validation: focused non-interactive executor/queue contracts for actual
  grouped argv, one output merge/zero propedit in Mux, untouched mismatch skips,
  warnings/errors, source/stage/destination changes, failed publication/unlink,
  and interrupted commit reconciliation. Use test-supplied staged JSON with
  media fakes, then small serial real-v93 executor proof including video/stereo,
  nonempty tags, flags, literal/empty titles, intended retained mapping and
  chapter/attachment payload preservation. Owned `.tmp` fixtures only; no
  upgrades, real user media, or broad menu campaign. Parent notice precedes
  one needed tiny mocked Run journey; native function integration is separate.
- The first inline executor draft is written and under review, not accepted.
  Parent review required binding publication to the validated candidate identity,
  final guards after phase-receipt I/O, exact user tag String whitespace, and
  per-request actual Edit values even after validation fails. The writer is
  applying these corrections and preparing focused/native proof. Astra has an
  immutable read-only draft snapshot at
  `.tmp/mkvutil-rework/executor-audit.8kAYGq/mkv_utils.zsh`, SHA-256
  `e3b730bfa04f5a98cb13c4e7314c16bdd96c4874cbab42d76a7d751b5e99df01`,
  for a bounded publication/oracle audit; later source changes require a diff
  reconciliation and cannot inherit a draft verdict as acceptance.
- Astra returned REVISE on that frozen draft: preserve monotonic commit evidence
  when a published destination later changes/disappears; handle TrackUID zero
  wildcard and retained/removed OR-target projection; stop the queue when a
  native child alone terminates by signal. Parent forwarded each finding to
  the sole writer immediately, alongside an uncertain-state correction for
  empty executor results. Required focused/native corrective proof remains
  pending. These corrections enforce existing contracts; no requirements or
  acceptance gate have changed.
- New direct user reporting requests extend T02.03: final reports show the
  input directory basename and category-specific action
  numbers (one number or expanded/deduplicated multiple numbers), with optional
  Mux metadata choices separately labeled. Each skipped-only continuation
  retains its own choice/count/time attribution; failures/partial jobs remain
  truthful. The user clarified these labels are for the final report, including
  done/skipped outcomes; this does not add labels to live progress blocks.
  Plan prose/task/evidence and checklist mirror were updated together;
  the executor writer was informed. This reporting work remains pending.
- The user's optional between-file display enhancement permits retaining the
  familiar Processed In / Files Done / Files Remaining / Estimated Time
  Remaining block. Parent chose to keep it familiar, with truthful completed,
  failed/skipped and queued counts and per-file elapsed/remaining-work ETA.
  Directory/action labels remain final-report-only. Manual integrity checks
  confirmed all nine task requirements, prerequisite/overlap and evidence
  mirrors, three accepted tasks, final-report scope, and path privacy.
- The user explicitly left fast `mkvpropedit` progress optional and said its
  end report is probably enough. Parent selected final-report-only for normal
  fast Edit jobs, with immediate warnings/failures; longer Mux jobs retain
  the familiar between-file elapsed/count/ETA display. Outcomes/timing remain
  collected for every file, with directory/action labels in the final report.
- Latest reporting clarification makes Edit final-report-only mandatory for
  every single/batched choice. Use one consistent final format in all three
  categories. Mux and Extract show between-file elapsed/count/ETA; the user
  explicitly answered the attachment-only question affirmatively. A combined
  attachment-and-track job's between-file display times only the track stage;
  final elapsed covers the whole configured batch. T02.03 owns shared reporting
  and G02 proof; T03.01 consumes/proves Extract reporting after G02 acceptance,
  preserving the existing stage gate. The plan/checklist were mirrored and
  T02.03/T03.01 overlap recorded; no task acceptance is implied.
- The new native wildcard fixture exposed a verified v93 limitation: normal
  remux drops source TrackUID-zero all-tracks tags while preserving the
  mixed retained/removed UID tag's surviving target. The candidate was refused
  and source preserved. Evidence is in
  `.tmp/mkvutil-rework/executors.yGdnvt/native/converted-result.json` and its
  source/output tag XML. Astra rejected a `--global-tags` workaround because
  that option changes all-tracks scope to whole-file scope. Parent accepted
  narrow Mux preflight refusal before output-producing commands for these
  unsupported user tags; it is an ordinary failed job, not a removal mismatch
  skip. Successful tag preservation is still required; no gate was waived.
  Mixed-target native success and wildcard zero-modifier refusal proof are
  pending; keep standalone Edit and the original native failure receipt.
- The worker's pre-write receipt verified the actual `Scripts-dev` Git root,
  assigned feature branch and only the parent-owned handoff diff. Controller
  design uses NUL-safe selection, explicit exclusion for invalid/incompatible
  sources (default N), and independent JSON jobs with safe literal argv reload.
- T02.01/T02.02 writer is now quiescent. Final runtime SHA-256 is
  `dd1ada39acf6f48853f27e6a441cb1a5d5dfc2cf14a5e7c2adb44a3aa21badb0`.
  Focused executor selection reports 21 passed in 67.59s; three affected
  foundation/adapter cases passed in 3.73s and language refinement passed in
  4.81s. Hash-bound receipts are
  `.tmp/mkvutil-rework/executors.yGdnvt/executor-focused-receipt.json` and
  `native/executor-native-receipt.json` under that run directory. Parent verified
  all three current file hashes against native evidence and the unchanged
  immutable-source hashes. Native results distinguish Edit, same-name Mux,
  conversion and both language paths. Chapter XML, attachment bytes, user-tag
  String whitespace and tiny media payloads were checked; one conversion SRT
  end timestamp changed from 200ms to 199ms with unchanged cue text, explicitly
  recorded rather than claimed byte-identical. The verified `i-klingon` native
  pair is `tlh`/`und`; unknown rewrites remain guarded.
- Exactly one notified mocked Run journey initially failed because its fixture
  was inside the harness's resettable state directory. The writer moved only
  that fixture outside the reset directory; reset/isolation assertions remain.
  Parent reran the same journey: 1 passed in 2.16s (2.57s wall, 1.46s user,
  0.96s system) in `.tmp/mkvutil-rework/executor-run-probe-fixed.vxpjIc/pytest`.
  Original failure log remains at `executor-run-probe.N1EoM7/test.log` under
  the same project evidence root. Copied runtime hash matches the final source.
  No native media tools were reached by that menu probe. Parent corrective
  source/test review and focused verification are now complete.
- Parent independently passed four critical candidate/post-publication/signal
  cases in 11.35s (11.90s wall, 6.17s user, 4.41s system), recorded in
  `.tmp/mkvutil-rework/executor-parent-review.4sDXqS/test.log`. Static checks
  and all current receipt bindings passed. Astra's bounded post-fix audit
  returned PASS on the corrected publication, tag, signal and uncertain-result
  findings; no extra campaign was required. Parent accepted T02.01/T02.02.
  This does not accept T02.03 or G02, or replace later accumulated integration
  and all-format qualification.
- Latest continuity refresh successfully reread the installed skill and its
  updated resumption/audits, change-control, location/visibility and dependency
  references. Both now-installed structural validators pass. The handoff is
  about 43KB at that refresh and navigable with current sections refreshed;
  size alone did not trigger consolidation. The subsequent user-requested
  code/checklist audit below was triggered by observed status/evidence drift. The original ordered parent-ID
  ledger and provenance are unchanged (SHA-256
  `fefdffb5cf9dccc158d326be5a53004a599f83d50b2acf73f04ae62e80514cab`).
  That same parent ID was reverified against its CLI session metadata, original
  Scripts cwd, no fork-parent marker, and this user's current refresh request
  in the matching log. No new session ID was appended. Git worktree assignments,
  accepted requirements/permissions and all private recovery evidence remain.
- T02.03 draft audit returned PASS WITH NOTES. Finalize every exit after
  processing begins, including interrupted/not-attempted jobs without a
  continuation offer; preserve prior outcomes on later cancellation/EOF and
  avoid the old unconditional no-changes message. Use immutable original-path
  keys, deduplicated live/preflight skip receipts and separate events for
  exclusions. Save configuration for all-skipped/cancelled cohorts as well as
  Runs, distinguishing requested from completed actions. Time queue processing
  monotonically, excluding user think-time, with zero-attempt-safe ETA over
  remaining eligible work. Astra also identified a stale checklist footer
  (3/9 versus accepted rows at 5/9); parent corrected it without changing gates.
- Current T02.03 writer brief: same three source/test/helper files, preserve
  accepted executor/metadata internals, implement shared final reporting and
  skipped-only post-run workflow, and prove mixed/all-skipped/resolved/unresolved
  outcomes, exclusions, warnings/partials/interruption, truthful action/directory
  labels, Edit final-only display, and zero-work timing. Test source fixtures
  stay outside resettable fake state. Use focused non-interactive contracts;
  exactly one small real-entrypoint mocked continuation probe requires parent
  notice before execution. Adapt affected legacy navigation without weakening
  assertions, but do not run bulk menu campaigns before the later grant.
- T02.03's writer confirmed the correct Git root, feature branch and signed
  `f44cd98` HEAD with only parent checklist/handoff changes before writing.
  The native-proof core baseline is saved at
  `.tmp/mkvutil-rework/executors.yGdnvt/accepted-core-baseline.json`; compare
  unchanged planner/executor function bodies plus relevant globals and the
  final diff before reusing task-level proof. A body hash is supplementary
  evidence, not a replacement for consumer/goal integration review.
- Read-only upcoming Mux validation evidence from `mkv_requirement_mapping`:
  bundled v93 manual confirms output track IDs differ and MakeMKV can regenerate
  track UIDs. Validate planned sequence/properties and metadata without an
  unconditional UID-equality gate. Use exact stdlib integers if UID comparison
  is required; jq arithmetic rounds large UIDs even though untouched serialization
  preserves them on installed 1.8.1. At that earlier foundation checkpoint,
  the real fixture contained no video/stereo or nonempty tags. The accepted
  executor receipt subsequently adds tiny H264/stereo and user-tag proof;
  broader all-format integration remains pending.
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
3. Preserve all accepted tasks and receipts. Complete only any unfinished
   authorized feature publication, AGENTS propagation and checkout housekeeping
   stated at the top; verify the actual branch/ref/state rather than repeating
   completed runtime tests. Keep the parent-session ledger and private receipts.

### Dependency-ready restart map

| Order | Task IDs | Required predecessor/readiness evidence | Writer/consumer boundary |
| --- | --- | --- | --- |
| 1 | T01.01 | Accepted: user instruction/naming choice, focused baseline/pure contract proof, parent review | Canonical original-file model; pure retained-order/output helpers |
| 2 | T01.02 | Accepted: registry/configuration/argv contracts and small native builder proof | Canonical shared metadata definitions/configuration/builders |
| 3 | T01.03 | Accepted: actual category configuration, always-multi selection, per-file/skip/subset proof | Real category selection, planning, conflicts, and preview consumers |
| 4 | T02.01, T02.02 | Accepted: focused/native executor gates, parent review and Astra post-fix PASS | Shared source and helpers verified; preserve corrected publication and result contracts |
| 5 | T02.03 | Accepted: current queue/reporting/continuation proof and independent audit | G02 goal integration gate passed; preserve one-source accounting and timing |
| 6 | T03.01 | Accepted: current Extract native/contracts/entrypoint, parent critical checks and independent post-fix audit | Preserve original-source safety, ordered attachment overwrites, protected tracks, stage/timing/recovery contracts |
| 7 | T04.01, then T04.02 | Runtime task evidence accepted, then integrated candidate verified | Consolidate valid slice receipts; final help/docs follow validated behavior |

The current user instruction authorizes implementation; this readiness map does
not itself accept a code task or authorize concurrent writers of shared files.
Both previous read-only review packages are complete; their planning receipts
contain no media operations, product tests, or CI results.

## Validation evidence and next checks

### T04 preparation while T03 implementation is active

- The existing explorer `mkv_requirement_mapping` completed a read-only
  inventory at `3567fe7` plus T03 work in progress. It ran no tests/media tools
  and edited no files; parent records this finding. This prepares the final
  gate and earns no T04 acceptance.
- Preserve the legacy single-action assertions while adapting their flat-menu
  navigation: flags/defaults, literal languages/names and paths, title clearing,
  multi-file outcomes, attachments, removal/naming/retained layouts, invalid
  inspections/IDs, reorder, and codec extensions. Correct the single-input
  reorder example to file ID `0` throughout and verify observed output order.
  Preserve both established two-file output regressions and the additional
  per-source Edit selector/property test.
- The T03 owner updates the existing fake extractor for source-first arguments,
  requested paths, physical artifact families, and deterministic stage failures.
  Keep those fixture changes in the same package; final navigation adaptation
  waits for accepted T03. No second harness or overlapping writer is needed.
- Proposed final campaign: the adapted legacy menu cases and a few batches
  covering all Edit choices, Mux removal/reorder/optional metadata with a fresh
  mismatch-only continuation, Extract attachments/tracks/combined partial
  outcomes, and invalid/cancel/EOF/help/exit. Use tiny installed-v93 fixtures
  for all four formats and representative semantic/preservation journeys;
  add one bounded real-fzf PTY journey for terminal selection. Distinguish
  mocked, native, and PTY evidence. Keep runs serial in fresh owned `.tmp`
  children and use existing timeouts; obtain the pending bounded project-wide
  interactive approval before campaign execution. Source/task proof proceeds
  independently under the existing implementation permission.

### Accepted T04.01 integration checkpoint

- Campaign receipt:
  `.tmp/mkvutil-rework/interactive/t04-campaign.vqvatjsp/campaign-result-receipt.json`.
  Completed in886.91s against approved900s budget. Source runtime unchanged:
  `997577ccbe412f451ac9cf0c9c4aa9a0604ef964c1d648d91ee38f3dd97e5408`.
  Final test hash: `d90bbc57362c50ce74a3118755566e274ebe5474b6a3ab17bc2cd891f09390a9`;
  helper unchanged from preparation: `41648a36e36f95b2f1d78acb9ef681ed6964b352b5ce45ad25bde59a727b7480`.
- Complete affected run:125 passed,1 planning-test10s timeout in324.21s wall /
  267.20s CPU. Splitting its independent mismatch/invalid-value checks from
  the intact cohort lifecycle retained every assertion and guard; all three
  corrected cases passed in8.44s wall. Current collection is128. Parent and
  Astra independently reconstructed the entire pre-split file at its exact
  preparation hash; all other case bodies are unchanged. Recovery and AST
  evidence: `parent-recovered-full-suite-tests.py`, `parent-case-binding.json`.
  This is aggregated coverage, not a single128-case all-pass run.
- N1: genuine four-format title-clear Edit, four grouped propedit calls.
  N2: removal/reorder and all five metadata actions, exactly one output remux
  and zero propedit calls, observed original UID order, flags/names/language,
  retained PCM payloads, chapters/attachments/user tags. Parent and Astra
  verified exactly one native SRT200ms-to199ms substitution, with every other
  byte including BOM/newlines identical. N3: selected-source attachment/track
  stages and unchanged source hash. Native application exits all0; inspection
  calls and baseline extraction are separate from modifying command counts.
- P1: real fzf on24x240 PTY selected two files, previewed and cancelled; only
  two identification calls, no modifiers, all source hashes unchanged. The
  earlier80-column driver-render wait hit its20s guard; it is a preserved
  failed driver attempt, not proof of a product failure or80-column acceptance.
- Parent verified current package/fixture hashes, native command counts,
  source preservation, actual subtitle bytes and independent test binding.
  Astra returned PASS WITH NOTES; stale group6 collection/binding wording is
  corrected in the receipt, preserving the original worker handback.
  All six integrated groups are accepted. Initial setup, planning timeouts,
  narrow native verifier failure and first PTY attempt remain in saved logs.
  No further test campaign, CI, installation, real-user-media or deployment
  action is needed or claimed. T04.02 and G04 final review subsequently passed; their final receipt is above.

### Completed T04.01 preparation brief (historical)


- Preparation receipt and campaign manifest:
  `.tmp/mkvutil-rework/integration-prep/prep.vqvatjsp/preparation-receipt.json`
  and `campaign-manifest.json`. Parent reviewed independent expected states,
  matched all package hashes, and verified unchanged G03 source at `b749135`.
  Test SHA-256: `edf400948d8ea0d5f717082be7e11ad309575247631d066cf7a654d802aea410`;
  helper: `41648a36e36f95b2f1d78acb9ef681ed6964b352b5ce45ad25bde59a727b7480`.
- All 19 legacy test function identities are retained/adapted; 126 cases
  collect, including 32 prepared adapted/new menu cases. Syntax/AST/whitespace
  checks and the read-only jq adapter contract pass. Actual menu/native/PTY
  campaign outcomes remain unverified; T04.01 and all six integrated groups
  remain unaccepted.
- Genuine small `.mkv`, audio-only `.mka`, subtitle-only `.mks`, and stereo
  `.mk3d` fixtures preserve metadata, chapters and attachments. Their seed
  hash is unchanged; fixture creation ran installed v93 tools in 1.07s wall,
  with no utility entrypoint runs. Fixture hashes/provenance and reference
  products are in `fixture-receipt.json` beside the preparation receipt.
- The preparation handback was quiescent with no active sessions; parent has
  subsequently resumed that writer for the now-completed approved campaign. Parent corrected only
  future campaign locations to the approved owned execution root
  `.tmp/mkvutil-rework/interactive/t04-campaign.vqvatjsp/`; immutable prepared
  fixtures remain in the preparation root. Pre-review manifest/receipt copies
  are preserved beside them. Current manifest SHA-256:
  `e87b8c06aab05adc4cf7b67c587e40659c5f173ac833d14b7558eac6ab88be72`.
  No execution directory or campaign run was created by that path review.
- The preceding preparation brief is retained below as completed assignment
  scope, not a live worker instruction. Resume the same exclusive writer only
  after verifying and conveying the actual execution grant.

- G03 is accepted and published at `b749135`; the hard prerequisite gate is
  satisfied. Reuse route B and the existing sole writer
  `mkv_metadata_foundation`, after root/branch/HEAD/status verification.
- Exclusive writes: `tests/mkv_tools/test_mkv_utils.py`,
  `tests/mkv_tools/_mkv_helpers.py`, and a fresh owned
  `.tmp/mkvutil-rework/integration-prep/<run-id>/` for small real fixtures and
  a bounded campaign manifest. Source is read-only for preparation; parent
  owns all planning records, Git and approvals. No overlapping writer exists.
- Adapt old flat-menu navigation and independent expected fake-tool state,
  retaining each operation/default/literal/path/layout/failure assertion and
  both two-file output regressions. Correct the invalid file-ID reorder
  example and retain an observed-order oracle. Reuse the existing framework;
  prepare a few grouped/negative journeys rather than another matrix.
- Prepare genuine tiny fixtures for `.mkv`, `.mka`, `.mks`, and `.mk3d`,
  preserving stereoscopic metadata for the latter and audio/subtitle-only
  content where appropriate. Reuse native-qualified streams/baselines; do not
  rename text placeholders or merely change an extension. Modest serial fixture
  creation is allowed; no user-facing native journeys run during preparation.
- Allowed checks now: collection, syntax/AST, and any ordinary pure fixture
  contracts. Do not run new/legacy actual-menu journeys, the broad affected
  menu suite, native entrypoint batches, or PTY campaign until the parent
  records the pending bounded project-wide interactive approval.
- Hand back quiescent files, exact candidate/test/helper hashes, the collected
  scope, fixture provenance/hashes, proposed mocked/native/PTY journeys and
  resource/time limits. Parent reviews that concrete campaign before asking
  once for execution approval. T04.01/T04.02 remain unaccepted; final help/docs
  follow the verified integration gate.

- Historical T01.01 foundation proof: pure helper plus three notified legacy
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
- `zsh -n shell/mkv_utils.zsh` and whitespace checks passed at the planning
  checkpoint, before implementation began. That historical result does not
  prove the new behavior.
- Earlier feature-design Astra audit: PASS WITH NOTES for category batching, shared
  metadata definitions, and direct Mux metadata. Its command-count clarification
  was incorporated. No automated or real-media tests were executed.
- The planning structural-rework audit received PASS after preserving the G02
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
- That documentation checkpoint required link, requirement-mirroring,
  whitespace, privacy, and actual Git-visibility checks, not a media test run.
- Document links/anchors, checkpoint identity parity, personal-path checks,
  whitespace/final newlines, and actual Git visibility passed for these records.
  At that documentation checkpoint, the index, utility source, and test files
  were unchanged; this is not the current implementation worktree status.

### Interactive-testing permission

- Status: ACTIVE, project-wide, for the prepared scope and budgets below.
  Parent asked the bounded approval question through `request_user_input_async`
  on 2026-10-14; the user's actual next message was **"ok go"**. This directly
  grants that campaign, including targeted corrective reruns inside its limits.
  Do not re-ask within this scope; no user-media, installation, deployment or
  materially larger campaign permission is inferred.
- Source: the 2026-10-14 user request schedules `zr0-interactive-testing` near
  the end of the project with custom `.tmp` files and existing tests/helpers.
  It authorizes this planning amendment, not immediate campaign execution.
- Prepared scope: the 126-case affected MKV suite (32 adapted/new utility menu
  cases), three native v93 journeys (all-format Edit title clear, combined
  removal/reorder plus all five metadata actions in one Mux, and combined
  attachment/track Extract), and one real-fzf PTY preview/Cancel without Run.
  Use fresh disposable fixture copies under the owned interactive root above,
  serially on this Big Sur host, with installed tools and no user media,
  installations, deployment or external effects. The prepared manifest supplies
  commands, independent oracles and mocked/native/TTY evidence boundaries.
- Approved limits: 15-minute whole-campaign review budget; mocked suite 600s
  wall/480s CPU review budget; native entrypoints and PTY retain 20s child
  guards, native total 120s. Stop on time/resource concern, unexpected command
  resolution, immutable-source hash drift or ownership escape. No hidden
  retries or enlarged timeouts; bounded corrective reruns remain within the
  granted scope and budget. Any material expansion requires a new decision.
- Verify this grant and candidate/fixture state before execution or resumption.
  Stop if it is revoked or limits are reached. Notify before light isolated
  probes; ordinary static/code checks retain their permissions.

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
New unrelated AGENTS edits require their own authorization. The user subsequently
explicitly approved automatic feature-branch pushes after each main goal's tasks
and goal-level gates pass. This includes accepted implementation checkpoints;
verify exact pushed refs and preserve the assigned worktree. It does not authorize
promotion, release tags, worktree changes or live deployment. Earlier planning-only
push receipts remain historical. The rehearsal still has its separate execution
approval boundary. The latest
"ok you may begin" authorizes approved implementation, and the follow-up replies
authorize the self-contained script and retained-content naming contracts.
Deployment, dependency installation, real user-media mutation, and broad
interactive campaigns remain outside the recorded authorization.
