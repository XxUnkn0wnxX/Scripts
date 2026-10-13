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
| G01 | Checkpoint 1: menu and planning contract | T01.01, T01.02, T01.03 | All three tasks accepted; category configuration and preview consume the shared foundation and meet the existing no-mutation gate. | [ ] | [ ] | [ ] |
| G02 | Checkpoint 2: Edit + Mux execution | T02.01, T02.02, T02.03 | All three tasks accepted and combined Edit/Mux workflows meet their semantic, safety, and reporting gates; this is the approved stage gate before Extract implementation. | [ ] | [ ] | [ ] |
| G03 | Checkpoint 3: extraction integration | T03.01 | T03.01 accepted and both single and batched extraction outcomes verified. G02 acceptance is an existing execution-stage gate, not an assumed extraction API dependency. | [ ] | [ ] | [ ] |
| G04 | Checkpoint 4: integration and documentation | T04.01, T04.02 | Both tasks accepted; all required integration/verification evidence is current, help/docs match the implementation, and parent final review is complete. | [ ] | [ ] | [ ] |

### G01 — Checkpoint 1: menu and planning contract

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [x] | T01.01 | Capture the existing behavior baseline and establish the original-track, per-file job, and output-naming contract for all four formats. Settle consistent single/batch removal naming before complete previews are accepted; preserve existing action semantics, defaults, and conversion behavior. | Required: Existing-behavior assertions and contract review; unresolved naming decisions keep this task pending. Status: accepted after parent review of the original-ID/output contract and source guard; focused pure-contract plus three baseline journeys passed (4 passed, 25 deselected in 2.70s), with syntax/whitespace checks. Consumer wiring remains T01.03. | none | T01.02, T01.03; source discovery, track model, and shared test fixtures |
| [x] | T01.02 | Implement one shared metadata definition/configuration section and both tool argument builders inside the self-contained `shell/mkv_utils.zsh`. The Edit list and optional Mux list share labels, prompts, defaults, validation, and complete mappings; configuration/builders do not execute tools. | Required: Focused configuration/argument tests, both-tool mapping completeness, original-ID/scoped arguments, and focused mapping parity evidence appropriate to the foundation; executor semantics remain a T02.02 gate. Status: accepted after parent source/contract review; five pure foundation/config/argv cases passed in 0.39s, and small native v93 builder integration passed. Shared consumers remain T01.03; full language registry/tool acceptance remains a later preflight/executor check. | T01.01 | T01.03, T02.01, T02.02; canonical owner of shared metadata definitions and builders |
| [ ] | T01.03 | Adapt existing actions into category submenus; implement single/comma/range selections, one target selection, per-file planning, conflicts, optional Mux metadata, and complete track/output previews. Wire the actual configuration consumers without media mutation. | Required: Real entrypoint/configuration wiring, invalid/cancel/EOF behavior, all-format planning, settled output names, and no-write configuration/cancellation evidence. Status: not started; no acceptance evidence. | T01.01, T01.02 | T02.01, T02.02, T03.01; canonical owner of selection, job planning, identity, and preview |

### G02 — Checkpoint 2: Edit + Mux execution

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [ ] | T02.01 | Implement grouped metadata-only Edit jobs through `mkvpropedit`, preserving existing values, input defaults/ranges, title clearing, and retained properties. Report actual in-place state on warnings/failures without rollback claims. | Required: Focused single/multi-file Edit behavior, grouped command arguments, warning/error state, and consumer integration evidence. Status: not started; no acceptance evidence. | T01.02, T01.03 | T02.02, T02.03; common source, metadata builders, and test helpers |
| [ ] | T02.02 | Implement one output-producing `mkvmerge` remux per Mux file, combining removal/order with optional direct metadata. Consume the settled naming contract; validate staged output and checked promotion, collisions, warnings, and interruptions. No post-remux `mkvpropedit`. | Required: Focused failures/safety and command-count proof plus required small real-v93 flag/title/track-mapping and preservation evidence before accepting this executor. Status: not started; no acceptance evidence. | T01.02, T01.03 | T02.01, T02.03, T03.01; common source/test helpers; owns remux staging and promotion |
| [ ] | T02.03 | Integrate complete single/batch Edit and Mux jobs with filename reports, elapsed time, average ETA, correct successful/failed/warning/partial counts, and failure-reflecting batch exit status. Prove the old 1+2, 8+4+3, and 7+8+4+3 workflow equivalents. | Required: Affected queue/consumer tests and partial-failure summaries, without rerunning a full unrelated suite. Status: not started; no acceptance evidence. | T02.01, T02.02 | T04.01; shared executor/reporting code and integration fixtures |

### G03 — Checkpoint 3: extraction integration

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [ ] | T03.01 | Implement single/batched attachment and track extraction within Extract using one target selection, codec-aware names, deterministic stages, collision handling, and partial-failure reporting without changing source media or claiming sidecar rollback. | Required: Affected extraction tests across applicable formats, source-preservation/collision/failure evidence, and selected-source real extraction proof. Status: not started; no acceptance evidence. | T01.01, T01.03, G02 | T02.02, T04.01; common source/output checks and extraction test fixtures |

### G04 — Checkpoint 4: integration and documentation

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [ ] | T04.01 | Verify every adapted single/batch action and shared metadata path together; consolidate task-level receipts and complete all six existing validation groups, including the small real-v93 and all-format integration evidence, plus the user-requested near-end interactive rehearsal with disposable `.tmp` fixtures. | Required: Syntax/static checks, complete affected MKV groups, real-tool integration, retained-property checks, bounded real-entrypoint journeys with mocked/real-tool/TTY boundaries recorded, and final candidate revision evidence; reuse still-valid slice receipts and rerun affected proof only. Status: not started; no acceptance evidence. | T02.03, T03.01 | T04.02; all runtime consumers and test fixtures |
| [ ] | T04.02 | Update help and the existing user guide against validated behavior, then complete parent final-diff review and reconcile acceptance/restart records. | Required: Verified command/menu/docs claims and links, reviewed final diff, and all applicable goal-level gates recorded without publication claims. Status: not started; no acceptance evidence. | T04.01 | none |

### Current readiness and acceptance limits

- T01.01's removal naming policy is user-approved: retained video keeps an
  existing `.mkv`/`.mk3d`, audio without video uses `.mka`, and subtitle-only
  uses `.mks`. Baseline/contract implementation evidence remains pending;
  naming approval alone does not accept T01.01 or T01.03 previews.
- T01.02 completion establishes the shared foundation, not acceptance of Edit,
  Mux, or Extract consumers. T01.03 requires actual configuration wiring and
  configuration/cancellation nonmutation evidence.
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

**Implementation tasks accepted: 2 / 9. Main goals/checkpoints accepted: 0 / 4.** T01.01 and T01.02 are accepted; category consumers, executors, integrated campaign, and final gates remain pending.
