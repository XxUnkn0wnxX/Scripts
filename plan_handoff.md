# mkvutil rework handoff

<!--
Verified parent Codex session IDs (append only; no child IDs):
Codex Session: 01a13610-202e-7613-af35-d95dfaa33fa8 | verified 2026-10-14 Australia/Melbourne |
CODEX_THREAD_ID corroborated with matching CLI session_meta ID and repository cwd,
plus the current user's tracking/AGENTS approval in that same session's log.
-->

[Authoritative plan](plan.md) · [Acceptance checklist](plan_checklist.md)

## Current state and safe restart point

- Branch: `feature/mkvutil-rework`.
- Committed baseline before publishing this documentation revision:
  `e3cb187975d524087e70ad7ce1e48894c21f0d65`
  (`docs: plan mkvutil category and batch rework`), with a verified signature.
- The committed plan is complete as a planning document. All four
  implementation checkpoints remain open; source, tests, and end-user guide
  have not been modified for this rework.
- The user-requested structural rework is complete: G01-G04 preserve the four
  checkpoints, with nine task IDs and a mirrored acceptance checklist.
  The reviewed dependency/readiness model is recorded in the plan. Companion
  links and local instructions remain in place.
- The user subsequently instructed **"you can also push those changes"**.
  Commit and push the three planning records on `feature/mkvutil-rework` and
  verify the local/remote refs. This snapshot is prepared before publication;
  actual Git refs are the publication receipt and must be checked on resumption.
- Current scope is planning records and their authorized branch publication.
  Starting implementation or changing acceptance requirements is not authorized.

## Artifacts and approved repository policy

| File | Purpose | Git visibility at this checkpoint |
| --- | --- | --- |
| `plan.md` | Authoritative requirements, goal/task IDs, dependencies, and four checkpoint identities | Tracked; included in the authorized documentation publication |
| `plan_checklist.md` | Mirrored checkpoint and validation acceptance evidence | Root companion included in the authorized documentation publication |
| `plan_handoff.md` | Verified current state, approvals, lineage, and next actions | Root companion included in the authorized documentation publication |
| `AGENTS.md` | Approved durable project instructions | Local, ignored by the existing tracked `.gitignore` rule |

On 2026-10-14 the user replied **"for repo plan etc can be tracked & ya
approved"** to the proposal for project instructions. This approves creating
`AGENTS.md` and overrides the private `.tmp/` default for the planning companion
records. Keep the plan and companions together at the repository root and
eligible for tracking. Existing ignore mechanisms were reused without changes.
The local AGENTS file does not accompany a fresh clone; the tracked plan and
published companions provide the portable restart record after ref verification.

The previous user instruction to commit `plan.md` was fulfilled by `e3cb187`.
The later explicit push instruction authorizes committing and pushing the
current three-record change set to the feature branch. Future checkpoints must
refresh the actual commit, remote ref, and worktree/index state rather than
treating this pre-publication snapshot as permanently current.

## Preserved design and decisions

- Main categories are Matroska Edit, Mux, and Extract. Existing actions become
  category sub-actions directly; there is no separate classic menu.
- Single and comma/range multi-selections are supported within each category.
- Mux offers optional metadata choices inside its own workflow. All settings
  are collected before the queue starts.
- One shared metadata definition/configuration section serves both Edit and
  Mux. Every new shared choice needs mappings and verification for both tools.
- Edit uses grouped `mkvpropedit`. Mux uses its corresponding `mkvmerge`
  metadata arguments in the same output-producing remux command; it does not
  perform a post-remux `mkvpropedit` step.
- Support includes `.mkv`, `.mka`, `.mks`, and `.mk3d`, targeting the installed
  MKVToolNix v93.0 on Big Sur. Tool upgrades are outside the approved design.
- Use Astra for intermittent focused audits at meaningful changes, as the user
  requested. The current user instruction authorizes concurrent agents for this
  task and active session; it does not authorize implementation or publication.

## Acceptance and unresolved implementation gates

Planning preparation is verified and remains separate from implementation
acceptance. The four existing checkpoints are now G01-G04, with nine stable
task IDs; **0 / 9 tasks and 0 / 4 main goals** are accepted.

The recorded audit identified these implementation checks:

- Establish actual v93 default-flag parity for intended retained-track states,
  plus blank-title clearing and literal-title handling through `mkvmerge`.
- T01.01 must settle consistent single/batch removal output naming for audio-only,
  subtitle-only, and 3D results while preserving established conversions before
  T01.03 can earn complete-preview acceptance. This contract is unresolved.
- Validate intended track identity and explicit final order for every file;
  do not assume track positions or MakeMKV UIDs survive a remux unchanged.
- Verify safe staging/promotion, collisions, warning/error distinctions,
  interruption behavior, and correct success reporting.

These are pending requirements or checks already in the plan, not accepted
runtime behavior or permission to weaken the specification.

## Execution route and next actions

The user explicitly requested this documentation restructuring and authorized
`parallel-execution` in the active session. The selected package was the minimal
coordinated plan/checklist/handoff rework, with independent read-only reviews
and parent-owned writes. That documentation package is complete. No implementation
A/B route or code package has been selected; no broader goal delivery is implied.

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
The review wave stops after integrated planning records and structural checks.

1. On resumption, read all three planning records and applicable instructions;
   verify branch, HEAD, worktree/index, pending approvals, and any live agents.
2. Verify completion of the authorized documentation publication from actual
   Git refs; finish it if still pending. Keep the planning boundary until the
   user requests implementation.
3. When implementation is authorized, start with T01.01's baseline and original
   file/job/output contract, including the naming decision; then T01.02's shared
   metadata foundation and T01.03's real configuration consumers. Inspect the
   target's prerequisites and overlap before selecting a bounded implementation
   package; present A/B routes only when they materially change scope/order.

### Dependency-ready restart map

| Order | Task IDs | Required predecessor/readiness evidence | Writer/consumer boundary |
| --- | --- | --- | --- |
| 1 | T01.01 | Implementation instruction and applicable test consent; settled output contract and baseline proof | One owner of original-file model and fixture baseline; naming is still unresolved |
| 2 | T01.02 | T01.01 accepted | Canonical shared metadata definitions/configuration/builders |
| 3 | T01.03 | T01.01 and T01.02 accepted | Real category selection, planning, conflicts, and preview consumers |
| 4 | T02.01, T02.02 | T01.02 and T01.03 accepted | Same source and helpers: serialize or use one coherent owner; each executor needs its own evidence |
| 5 | T02.03 | Both Edit and Mux executors accepted | Integrated reporting and single/batch workflows; G02 goal gate checked |
| 6 | T03.01 | G01 inputs plus G02 goal acceptance | Preserve approved Extract-after-Edit+Mux stage gate |
| 7 | T04.01, then T04.02 | Runtime task evidence accepted, then integrated candidate verified | Consolidate valid slice receipts; final help/docs follow validated behavior |

No code task is authorized or accepted by this readiness map. Dependency layers
do not authorize concurrent writers of shared files. Both read-only review
packages are complete; no media operations, product tests, or CI jobs were run.

## Validation evidence and next checks

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
- No interactive campaign approval is recorded. Ordinary static/code checks
  retain their permissions. Notify before light isolated interactive probes;
  seek one scoped approval before substantial interactive menu campaigns.
- This documentation checkpoint requires link, requirement-mirroring,
  whitespace, privacy, and actual Git-visibility checks, not a media test run.
- Document links/anchors, checkpoint identity parity, personal-path checks,
  whitespace/final newlines, and actual Git visibility passed for these records.
  The index and utility source remain unchanged.

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

## Approval boundaries

The user approved project-instruction creation and trackable repository planning
records, then explicitly requested this goal/task/dependency restructuring and
authorized concurrent agents for the current task/session. The four checkpoint
requirements and six validation groups are preserved; no gate was waived.
Future sessions must recheck concurrency consent. Any agent-proposed contract change
requires a concrete user-approved proposal before editing plan/checklist rules.
New unrelated AGENTS edits require their own authorization. Commit/push of these
three records to `feature/mkvutil-rework` is explicitly authorized. Deployment,
dependency installation, real user-media mutation, implementation, and broad
interactive campaigns remain outside the recorded authorization.
