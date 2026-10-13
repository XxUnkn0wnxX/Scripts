# mkvutil rework acceptance checklist

[Authoritative plan](plan.md) · [Current handoff](plan_handoff.md)

This checklist mirrors the plan's four main goals, nine task IDs, required
results, dependencies, and approved validation requirements. The four original
checkpoint identities remain intact. `plan.md` owns requirements; this file
records acceptance status and evidence. A commit, planner verdict,
or passing diagnostic check does not establish implementation acceptance.

## Planning preparation

- [x] Review the current script, documentation, and existing test harness.
- [x] Verify installed tools and the Big Sur compatibility baseline.
- [x] Create the rework branch and write the planning document.
- [x] Independently audit the proposal and incorporate material corrections.

Evidence: the current parent session reviewed the source and test harness,
verified the v93.0 binaries and bundled documentation, and completed selective
Astra audits. Commit `e3cb187975d524087e70ad7ce1e48894c21f0d65` contains the
approved plan. At that planning checkpoint, implementation and automated/real-media validation had not run.

## Main-goal acceptance

Each main goal preserves the corresponding existing checkpoint. A goal is
accepted only after its own tasks and goal-level integration/verification gate
pass. Planning-preparation history above is outside these implementation totals.

| Goal ID | Preserved checkpoint | Required task IDs | Goal-level acceptance gate | Tasks accepted | Goal gate passed | Goal accepted |
| --- | --- | --- | --- | --- | --- | --- |
| G01 | Checkpoint 1: menu and planning contract | T01.01, T01.02, T01.03 | All three tasks accepted; category configuration and preview consume the shared foundation and meet the existing no-mutation gate. | [x] | [x] | [x] |
| G02 | Checkpoint 2: Edit + Mux execution | T02.01, T02.02, T02.03 | All three tasks accepted and combined Edit/Mux workflows meet their semantic, safety, and reporting gates; this is the approved stage gate before Extract implementation. | [ ] | [ ] | [ ] |
| G03 | Checkpoint 3: extraction integration | T03.01 | T03.01 accepted and both single and batched extraction outcomes verified. G02 acceptance is an existing execution-stage gate, not an assumed extraction API dependency. | [ ] | [ ] | [ ] |
| G04 | Checkpoint 4: integration and documentation | T04.01, T04.02 | Both tasks accepted; all required integration/verification evidence is current, help/docs match the implementation, and parent final review is complete. | [ ] | [ ] | [ ] |

### G01 — Checkpoint 1: menu and planning contract

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [x] | T01.01 | Capture the existing behavior baseline and establish the original-track, per-file job, and output-naming contract for all four formats. Settle consistent single/batch removal naming before complete previews are accepted; preserve existing action semantics, defaults, and conversion behavior. | Required: Existing-behavior assertions and contract review; unresolved naming decisions keep this task pending. Status: accepted after parent review of the original-ID/output contract and source guard; focused pure-contract plus three baseline journeys passed (4 passed, 25 deselected in 2.70s), with syntax/whitespace checks. Consumer wiring remains T01.03. | none | T01.02, T01.03; source discovery, track model, and shared test fixtures |
| [x] | T01.02 | Implement one shared metadata definition/configuration section and both tool argument builders inside the self-contained `shell/mkv_utils.zsh`. The Edit list and optional Mux list share labels, prompts, defaults, validation, and complete mappings; configuration/builders do not execute tools. | Required: Focused configuration/argument tests, both-tool mapping completeness, original-ID/scoped arguments, and focused mapping parity evidence appropriate to the foundation; executor semantics remain a T02.02 gate. Status: accepted after parent source/contract review; five pure foundation/config/argv cases passed in 0.39s, and small native v93 builder integration passed. Shared consumers remain T01.03; full language registry/tool acceptance remains a later preflight/executor check. | T01.01 | T01.03, T02.01, T02.02; canonical owner of shared metadata definitions and builders |
| [x] | T01.03 | Adapt existing actions into category submenus; implement single/comma/range operations, always-multi target selection for one/several files, per-file planning, optional Mux metadata, conflicts, and complete previews. Establish removal ID/type/codec eligibility, automatic mismatch skip receipts, preserved batch scope, and fresh skipped-subset planning without media mutation. | Required: Real entrypoint/configuration wiring, always-multi selection, invalid/cancel/EOF behavior, all-format planning, settled outputs, removal signature/skip/subset contracts, and no-write configuration/cancellation evidence. Status: accepted after parent code/schema review, initial category/format/directory/argv/collision contracts, five final affected selector/removal cases, one notified mocked mismatch-report/Cancel journey, and two parent skip/subset cases (11.19s). Hash-bound receipt: `.tmp/mkvutil-rework/removal-delta.vyycYM/receipt.json`. No modifying media calls; runtime continuation remains T02.03. | T01.01, T01.02 | T02.01, T02.02, T03.01; canonical owner of selection, job planning, identity, and preview |

### G02 — Checkpoint 2: Edit + Mux execution

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [ ] | T02.01 | Implement grouped metadata-only Edit jobs through `mkvpropedit`, preserving existing values, input defaults/ranges, title clearing, and retained properties. Report actual in-place state on warnings/failures without rollback claims. | Required: Focused single/multi-file Edit behavior, grouped command arguments, warning/error state, and consumer integration evidence. Status: implementation in progress after accepted G01 prerequisites; no executor acceptance evidence yet. | T01.02, T01.03 | T02.02, T02.03; common source, metadata builders, and test helpers |
| [ ] | T02.02 | Implement one output-producing `mkvmerge` remux per eligible Mux file, combining removal/order with optional direct metadata. Keep removal mismatch-skipped files wholly untouched. Consume the settled naming contract; validate staged output and checked promotion, collisions, warnings, and interruptions. No post-remux `mkvpropedit`. | Required: Focused failures/safety, eligible-file command counts and zero modifying calls for mismatch skips, plus required small real-v93 flag/title/track-mapping and preservation evidence before accepting this executor. Status: implementation in progress under the corrected promotion design; native and failure-safety acceptance gates remain pending. | T01.02, T01.03 | T02.01, T02.03, T03.01; common source/test helpers; owns remux staging and promotion |
| [ ] | T02.03 | Integrate complete single/batch Edit and Mux jobs with exact filename/skip reports, elapsed time, average ETA, truthful successful/failed/warning/partial/skipped outcomes, and failure-reflecting exit status. Final reports identify the input directory basename, category and single/multiple submenu action numbers, with optional Mux metadata numbers separate and each continuation attributed to its own choices. Offer fresh configured Mux continuations for mismatch-skipped files only, counting each source once. Prove the old 1+2, 8+4+3, and 7+8+4+3 workflow equivalents. | Required: Affected queue/consumer tests, final action/directory reporting for single/batch/continuation scopes, mixed/all-skipped reporting, fresh subset continuation excluding completed files, resolved/unresolved final counts/status, and partial failures without a full unrelated suite. Status: not started; no acceptance evidence. | T02.01, T02.02 | T04.01; shared executor/reporting code and integration fixtures |

### G03 — Checkpoint 3: extraction integration

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [ ] | T03.01 | Implement single/batched attachment and track extraction within Extract using one target selection, codec-aware names, deterministic stages, collision handling, and partial-failure reporting without changing source media or claiming sidecar rollback. | Required: Affected extraction tests across applicable formats, source-preservation/collision/failure evidence, and selected-source real extraction proof. Status: not started; no acceptance evidence. | T01.01, T01.03, G02 | T02.02, T04.01; common source/output checks and extraction test fixtures |

### G04 — Checkpoint 4: integration and documentation

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [ ] | T04.01 | Verify every adapted single/batch action, shared metadata path, and removal skip-only continuation together; consolidate task-level receipts and complete all six existing validation groups, including small real-v93/all-format evidence and the near-end interactive rehearsal with disposable `.tmp` fixtures. | Required: Syntax/static checks, complete affected MKV groups, real-tool integration, retained-property checks, bounded real-entrypoint journeys with mocked/real-tool/TTY boundaries recorded, and final candidate revision evidence; reuse still-valid slice receipts and rerun affected proof only. Status: not started; no acceptance evidence. | T02.03, T03.01 | T04.02; all runtime consumers and test fixtures |
| [ ] | T04.02 | Update help and the existing user guide against validated behavior, then complete parent final-diff review and reconcile acceptance/restart records. | Required: Verified command/menu/docs claims and links, reviewed final diff, and all applicable goal-level gates recorded without publication claims. Status: not started; no acceptance evidence. | T04.01 | none |

### Current readiness and acceptance limits

- T01.01's removal naming policy is user-approved and its pure helper accepted:
  retained video keeps an
  existing `.mkv`/`.mk3d`, audio without video uses `.mka`, and subtitle-only
  uses `.mks`. Focused baseline/contract evidence is recorded above;
  complete T01.03 per-file preview consumer evidence remains pending.
- T01.02 completion establishes the shared foundation, not acceptance of Edit,
  Mux, or Extract consumers. T01.03 requires actual configuration wiring and
  configuration/cancellation nonmutation evidence.
- The user-approved selector/removal amendment applies to T01.03, T02.02,
  T02.03, and T04.01. One always-multi picker accepts one/several files; removal
  eligibility matches requested original IDs plus media type and native codec,
  allowing name/language/flag differences. Automatic mismatch skips retain
  exact filenames/reasons and the current source scope. Fresh skipped-subset
  planning is a G01 gate; post-execution continuation/reporting is a G02 gate.
  The initial controller receipts and final selector/removal delta proof establish T01.03 planning acceptance; runtime continuation and result aggregation remain pending.
- T02.02 requires its focused safety and small real-v93 semantic evidence before
  acceptance. T04.01 consolidates valid slice receipts and integrated affected
  groups; it does not defer all prerequisite proof until the end.
- T03.01 has G01 technical prerequisites plus the approved G02 acceptance-stage
  gate. Verify that goal's own integration gate as well as its task checkboxes.
- These are mirrored readiness rules, not new requirements. Progress and
  acceptance require observed results at the relevant revision/platform.

## Required validation

These are the six existing [plan validation requirements](plan.md#validation-and-acceptance),
with their acceptance still pending:

1. [ ] Preserve existing operation assertions, including free-form metadata,
   input defaults/ranges, extraction extensions, extension conversion,
   multi-file failures, and the two-file terminal-variable-output regressions.
   Adjust navigation for the new category entrypoints without weakening
   underlying behavior assertions.
2. [ ] Verify submenu comma/range parsing, invalid and duplicate selections,
   category batching, optional Mux metadata, conflicts, cancellation/EOF,
   heterogeneous file layouts, and command counts. Both tools must be covered
   by the shared definitions; Mux must use one output-producing remux command
   and zero `mkvpropedit` calls, counting identification/validation separately.
   Cover applicable behavior for `.mkv`, `.mka`, `.mks`, and `.mk3d`, including
   audio-only, subtitle-only, and stereoscopic inputs, using proportionate cases.
   Verify always-multi selection of one/several files, removal ID/type/codec
   compatibility, automatic whole-job skips, allowed metadata differences,
   exact skipped filenames/reasons, eligibility after configuration changes,
   and fresh skipped-only continuations. Cover mixed/all-skipped cases, zero
   modifying calls for skipped files, completed-source exclusion, and truthful
   resolved/unresolved final counts/status.
3. [ ] Verify collisions, failed promotion, inspection/validation failures,
   warning versus error handling, interruptions, and incomplete-stage reporting.
4. [ ] Correct the reorder test's single-input `0:1,1:0` example and establish
   actual ordering beyond the stub's empty-output behavior.
5. [ ] Use a small real fixture on installed v93 tools to prove combined
   removal/reordering/names/languages, mapping to intended tracks, flag parity,
   blank-title clearing, chapters/attachments preservation, and extraction from
   selected sources. Keep real-tool evidence distinct from stub assertions.
6. [ ] Run syntax/static checks and all affected MKV test groups once the
   integrated change is ready; broaden only for shared changes or discovered
   failures. Unrelated repository suites are not automatic requirements.

### User-requested near-end interactive rehearsal

- [ ] Reuse and adapt the existing menu harness for category single actions,
  representative batches, optional Mux metadata, and controlled input/failure
  journeys; avoid a duplicate test framework.
  Include always-multi selection, removal mismatch reports, and a fresh
  continuation for only the skipped sources.
- [ ] Generate small valid fixtures for all four formats in an owned per-run
  `.tmp` directory, and verify a few real-v93 workflows alongside mocked churn.
- [ ] Verify the campaign's bounded approval before execution; record exact
  candidate revision and distinguish mocked, real-tool, and terminal evidence.

These items mirror [the plan's rehearsal](plan.md#near-end-interactive-rehearsal)
within T04.01. They are pending and do not defer earlier task acceptance gates.

All [track identity](plan.md#track-identity-and-preview),
[metadata](plan.md#metadata-contracts),
[file safety](plan.md#file-safety-and-queue-reporting), format, and acceptance
contracts remain those in the authoritative plan.

**Implementation tasks accepted: 3 / 9. Main goals/checkpoints accepted: 1 / 4.** G01 and T01.01-T01.03 are accepted; executors, post-execution continuation, integrated campaign, and final gates remain pending.
