# mkvutil rework acceptance checklist

[Authoritative plan](plan.md) · [Current handoff](plan_handoff.md)

This checklist mirrors the plan's four main goals, nine task IDs, required
results, dependencies, and approved validation requirements. The four original
checkpoint identities remain intact. `plan.md` owns requirements; this file
records acceptance status and evidence. A commit, planner verdict,
or passing diagnostic check does not establish implementation acceptance.

The final-after-processing amendment is accepted: every processed queue ends
with its report and exit, including mixed eligible/skipped runs. All 9/9 tasks
and 4/4 goals are accepted after 13 current affected checks and parent review.
Proof: `.tmp/mkvutil-rework/run-final/receipt.json`. Earlier receipts retain
their revision-specific evidence.

The user-requested code/evidence audit reconciled all nine mirrored contracts
and the accepted task gates. Accepted boxes refer to the recorded revisions and
corrective receipts. T02.03's affected-consumer proof and G02 integration review
subsequently passed. Audit: `.tmp/mkvutil-rework/checklist-audit.wni4h33r/audit-receipt.json`.

The direct-shortcut display and keyboard Ctrl+C correction are accepted with
current terminal evidence. Earlier failures are retained in
`.tmp/mkvutil-rework/menu-display.uJfcXR/receipt.json`; unchanged engine
receipts remain separate historical proof.

The owned-menu screen amendment is accepted at T01.03 and affected T04 gates.
Current proof verifies menu replacement, restored immediate Category selection,
readable previews/reports, plain redirected input and keyboard interruption at
menus and value fields. Earlier key/cursor/engine receipts remain historical.
Proof: `.tmp/mkvutil-rework/owned-menu.G4F1G9/receipt.json` and `parent-review.json`.

The visible main-cursor amendment is accepted at T01.03 and affected T04 gates.
Two existing terminal cases verify visible Category cursor, immediate keys, Back,
normal history and main Ctrl+C. Exact source comparison confirms only cursor
visibility/naming changed; all read mechanics and engine code are unchanged.
Proof: `.tmp/mkvutil-rework/cursor-visible.Jumdct/receipt.json`.

The immediate buffered-redraw amendment is accepted at T01.03 and affected T04
gates. Current proof verifies retained adjacent-menu buffers, complete literal
body writes, clean shorter views, readable diagnostics and unchanged instant/
visible-cursor input. Prior native and engine receipts remain valid. Proof:
`.tmp/mkvutil-rework/redraw.NtaUm3/receipt.json` and `parent-review.json`.

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
| G02 | Checkpoint 2: Edit + Mux execution | T02.01, T02.02, T02.03 | All three tasks accepted and combined Edit/Mux workflows meet their semantic, safety, and reporting gates; this is the approved stage gate before Extract implementation. | [x] | [x] | [x] |
| G03 | Checkpoint 3: extraction integration | T03.01 | T03.01 accepted and both single and batched extraction outcomes verified. G02 acceptance is an existing execution-stage gate, not an assumed extraction API dependency. | [x] | [x] | [x] |
| G04 | Checkpoint 4: integration and documentation | T04.01, T04.02 | Both tasks accepted; all required integration/verification evidence is current, help/docs match the implementation, and parent final review is complete. | [x] | [x] | [x] |

### G01 — Checkpoint 1: menu and planning contract

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [x] | T01.01 | Capture the existing behavior baseline and establish the original-track, per-file job, and output-naming contract for all four formats. Settle consistent single/batch removal naming before complete previews are accepted; preserve existing action semantics, defaults, and conversion behavior. | Required: Existing-behavior assertions and contract review; unresolved naming decisions keep this task pending. Status: accepted after parent review of the original-ID/output contract and source guard; focused pure-contract plus three baseline journeys passed (4 passed, 25 deselected in 2.70s), with syntax/whitespace checks. Consumer wiring remains T01.03. | none | T01.02, T01.03; source discovery, track model, and shared test fixtures |
| [x] | T01.02 | Implement one shared metadata definition/configuration section and both tool argument builders inside the self-contained `shell/mkv_utils.zsh`. The Edit list and optional Mux list share labels, prompts, defaults, validation, and complete mappings; configuration/builders do not execute tools. Apply the metadata batch-target and Back contracts through this shared collector. | Status: accepted after current source/receipt review. Shared Edit and preset Mux targets, per-ID ordered values, title positioning, exact text escapes and transactional Back reset pass current foundation tests. Both builders and mappings are byte-identical to the baseline. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Focused configuration/argument tests, both-tool mapping completeness, original-ID/scoped arguments, and focused mapping parity evidence appropriate to the foundation; executor semantics remain a T02.02 gate. Prior status: accepted after parent source/contract review; five pure foundation/config/argv cases passed in 0.39s, and small native v93 builder integration passed. Shared consumers remain T01.03; full language registry/tool acceptance remains a later preflight/executor check. | T01.01 | T01.03, T02.01, T02.02; canonical owner of shared metadata definitions and builders |
| [x] | T01.03 | Adapt existing actions into category submenus; implement single/comma/range operations, always-multi target selection for one/several files, per-file planning, optional Mux metadata, conflicts, and complete previews. Establish removal ID/type/codec eligibility, automatic mismatch skip receipts, preserved batch scope, and fresh skipped-subset planning without media mutation. Follow the menu-navigation contract for Ctrl+C, hidden main-menu exit and menu and metadata Back, preserving scope and truthful result history. Apply the metadata batch-target contract, retry invalid reorder entries while retaining removal, and preserve scope when metadata Back clears pending settings. Support e/E at all utility configuration and preflight-exclusion prompts with atomic full-cohort inspection recovery; Mux metadata-list Back returns directly to main. | Status: accepted after Back source and parent review; 33 affected cases pass across separate runs (one unchanged-guard timeout followed by a single isolated pass), plus two final-source controlling-PTY journeys. Proof: `.tmp/mkvutil-rework/back-everywhere.obdrls35/receipt.json` and `parent-review.json`. Historical accepted evidence: Status: accepted after current source/receipt review. Reorder retry retains removal; explicit target inheritance, appended-track exclusion, all-removed rejection, interruption, metadata Back/reselection/skip and same-picker scope pass current configuration and real entrypoint tests. Two controlling-terminal cases prove inherited-ID display, metadata Back and keyboard interruption/restoration. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Real entrypoint/configuration wiring, always-multi selection, invalid/cancel/EOF behavior, all-format planning, settled outputs, removal signature/skip/subset contracts, and no-write configuration/cancellation evidence; focused navigation, field-value and ledger-boundary proof for the approved follow-up. Prior status: accepted after current source/test review. Adjacent navigation retains its owned screen; complete bodies use one literal-safe print with line/tail erasure, without blank-before-paint clears or artificial delay. Main Category/visible cursor/instant reader, data readers, fields and engine code remain byte-identical. Parent-owned diagnostics and explicit picker/configuration/planning/execution/preview/report boundaries preserve input, outcomes and history. Seven PTY cases, affected normal/pipe consumers and literal/shorter-view/error/EOF cases establish current behavior. Proof: `.tmp/mkvutil-rework/redraw.NtaUm3/receipt.json` and `parent-review.json`. Original removal proof remains `.tmp/mkvutil-rework/removal-delta.vyycYM/receipt.json`; earlier scope/key/cursor receipts are preserved in the handoff. | T01.01, T01.02 | T02.01, T02.02, T03.01; canonical owner of selection, job planning, identity, and preview |

### G02 — Checkpoint 2: Edit + Mux execution

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [x] | T02.01 | Implement grouped metadata-only Edit jobs through `mkvpropedit`, preserving existing values, input defaults/ranges, title clearing, and retained properties. Report actual in-place state on warnings/failures without rollback claims. Apply each collected per-ID value to the same original ID in every eligible selected file. During Run, Ctrl+C finishes the active Edit file and its actual-state validation, then stops before another file; repeated Ctrl+C keeps the same stop request. | Status: accepted after final-source regression, terminal and installed-v93 review. Ctrl+C finishes an admitted Edit and actual-state observation, repeated Ctrl+C preserves the result, and no next writer starts. Early stop is not attempted; hard termination remains distinct. Grouped arguments, literal values and in-place warning/failure outcomes pass. Current proof: `.tmp/mkvutil-rework/runtime-stop.4mgf2nx6/receipt.json`, `final-source-coverage.json`, `native-receipt.json` and `parent-review.json`. Historical revision evidence: Status: accepted after current source/receipt review. Two selected files with different listing positions receive original-ID-specific values through one grouped propedit per source. Shared IDs are asked once; current grouped flags/name/language/title consumers pass. Native executor remains byte-identical. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Focused single/multi-file Edit behavior, grouped command arguments, warning/error state, and consumer integration evidence. Prior status: reaccepted after the user-requested audit reopened missing normal multi-file proof. A two-file grouped Edit queue passed (1 test, 11.44s), with different original listing positions, source-specific expected properties, exactly one propedit per source and no output remux. Existing single-file/native/partial-state evidence remains bound to `f44cd98`. Full reporting/continuation remains T02.03. Receipts: `.tmp/mkvutil-rework/executors.yGdnvt/`; audit and corrective proof: `.tmp/mkvutil-rework/checklist-audit.wni4h33r/audit-receipt.json`. | T01.02, T01.03 | T02.02, T02.03; common source, metadata builders, and test helpers |
| [x] | T02.02 | Implement one output-producing `mkvmerge` remux per eligible Mux file, combining removal/order with optional direct metadata. Keep removal mismatch-skipped files wholly untouched. Consume the settled naming contract; validate staged output and checked promotion, collisions, warnings, and interruptions. No post-remux `mkvpropedit`. Reorder metadata targets only the explicit original reorder IDs; appended retained tracks keep unrequested metadata. During Run, Ctrl+C finishes the active Mux file including validation and checked promotion, then stops before another file; repeated Ctrl+C keeps the same stop request. | Status: accepted after final-source regression, terminal and installed-v93 review. Ctrl+C finishes the active Mux through checked publication and stops the next file. One output merge and zero propedit calls, removal conversion, exact retained UID order, flags, chapters and attachments pass. Parent loss and surviving descendant checks prevent unsafe publication; hard-signal recovery remains conservative. Current proof: `.tmp/mkvutil-rework/runtime-stop.4mgf2nx6/receipt.json`, `final-source-coverage.json`, `native-receipt.json` and `parent-review.json`. Historical revision evidence: Status: accepted after current source/receipt review. Two-file combined Mux passes with exact explicit order0,4,3, all five metadata actions, source-specific preserved appended-track flags, one output merge per source and zero propedit calls. Strengthened exact flag argv assertions pass separately. Engines/builders remain byte-identical; prior native v93 proof is reused. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Focused failures/safety, eligible-file command counts and zero modifying calls for mismatch skips, plus required small real-v93 flag/title/track-mapping and preservation evidence before accepting this executor. Prior status: accepted after source/receipt review, 21 focused executor cases (67.59s), four parent critical cases (11.35s), and real-v93 grouped flags/titles/order/conversion/stereo/codec/chapter/attachment/user-tag proof. All runtime/hash and immutable-source bindings verified; Astra post-fix audit passed. TrackUID-zero tags are refused before modification; conversion SRT end 200ms to 199ms is documented. Receipt: `.tmp/mkvutil-rework/executors.yGdnvt/native/executor-native-receipt.json`. | T01.02, T01.03 | T02.01, T02.03, T03.01; common source/test helpers; owns remux staging and promotion |
| [x] | T02.03 | Integrate complete single/batch Edit and Mux jobs with exact filename/skip reports, elapsed time, average ETA, truthful successful/failed/warning/partial/skipped outcomes, and failure-reflecting exit status. Final reports identify the input directory basename, category and single/multiple submenu action numbers, with optional Mux metadata numbers separate and each configuration attributed to its own choices. Allow skipped-only reconfiguration before processing, counting each source once. Once a queue has processed, print its final report and exit without menus, acknowledgement or retry prompts; retry skipped files only in a new invocation. Prove the old 1+2, 8+4+3, and 7+8+4+3 workflow equivalents. Clear abandoned current metadata choices on Back without losing requested EOF attribution or earlier outcomes. Preserve complete current-cohort request attribution, exclusions, skip history and sticky outcomes across Back and reinspection. Preserve the active file outcome independently from a stop request and print the exact ordered filenames not started due to stopping, including skipped-only retry cohorts. | Required: Affected queue/consumer tests, final action/directory reporting for single/batch/pre-run scopes, mixed/all-skipped reporting, pre-run subset replanning and separate-invocation skipped-file retries, resolved/unresolved final counts/status, and partial failures without a full unrelated suite. Status: Accepted after final-source consumer review: mixed Mux completes only the eligible file, reports unresolved skips once, leaves skipped bytes untouched and exits nonzero without reading more input. A separate invocation explicitly retries only the skipped file. Three-category finality and pre-run navigation pass. Current proof: `.tmp/mkvutil-rework/run-final/receipt.json` and `tests.log`. Historical revision evidence: Status: accepted after current consumer and parent review. Full-cohort Back/reinspection retains exclusions, retry scope and result history. Stopped reports preserve actual active-file outcomes and exact ordered not-started filenames, including skipped-only retries. Late Ctrl+C, repeated Ctrl+C, hard-signal precedence and post-result bookkeeping failure preserve truthful counts and nonzero stop status. Current proof: `.tmp/mkvutil-rework/runtime-stop.4mgf2nx6/receipt.json`, `final-source-coverage.json`, `native-receipt.json` and `parent-review.json`. Historical revision evidence: Status: pending corrected full-cohort/recovery/navigation implementation and current consumer/IA/parent review. Historical accepted evidence: Status: accepted after current source/receipt review. Current request/history tests preserve EOF metadata attribution, clear only discarded active choices on e/skip/Back, retain prior batch outcomes and verify skipped-only continuation/reporting. Reporting and queue functions remain byte-identical. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Affected queue/consumer tests, final action/directory reporting for single/batch/continuation scopes, mixed/all-skipped reporting, fresh subset continuation excluding completed files, resolved/unresolved final counts/status, and partial failures without a full unrelated suite. Prior status: accepted after source/receipt review, 12 focused contracts (37.38s), one notified mocked fresh-subset Run journey (7.15s), two parent interruption/bookkeeping cases (3.59s), and Astra integration PASS. Original-source counts, per-configuration action/metadata/directory reporting, Edit final-only display, Mux timing/ETA, resolved/unresolved skips and all three legacy workflow equivalents are verified. Receipts: `.tmp/mkvutil-rework/reporting/t02.03-receipt.json` and `parent-integration.json`. | T02.01, T02.02 | T03.01, T04.01; shared executor/reporting code and integration fixtures |

### G03 — Checkpoint 3: extraction integration

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [x] | T03.01 | Implement single/batched attachment and track extraction within Extract using one target selection, codec-aware names, deterministic stages, shared attachment collection with approved filename overwrites, track/companion collision protection, and partial-failure reporting without changing source media or claiming sidecar rollback. Reuse the shared final-report format and show between-file elapsed/count/ETA for attachment-only and track extraction; combined attachment-and-track jobs time only the track stage in that display. Ctrl+C stops extraction immediately; after the owned native process stops, discard only declared owned track artifacts from an interrupted unvalidated stage. Keep completed outputs, attachments and validated or uncertain recovery artifacts; report cleanup failures. | Status: accepted after final-source regression, terminal and installed-v93 review. Extract interrupts its owned native process and confirms group shutdown before discarding declared unvalidated track artifacts. Completed outputs, attachments, warning candidates, validated/uncertain recovery and unexpected files remain protected. Source/payload checks and existing extraction timing/collision/overwrite contracts pass. Current proof: `.tmp/mkvutil-rework/runtime-stop.4mgf2nx6/receipt.json`, `final-source-coverage.json`, `native-receipt.json` and `parent-review.json`. Historical revision evidence: Required: Affected extraction tests across applicable formats, shared attachment overwrite/order/supersession and protected track/companion collision evidence, source-preservation/failure evidence, selected-source real extraction proof, consistent final reports, and extraction timing with the requested stage scope. Status: accepted after parent source/receipt review and two critical checks (4.84s), 12 current audit contracts (26.70s), one notified CLI preview/Run probe (3.54s), two current consumer checks (9.71s), current native v93 attachment/text/VobSub proof, and Astra post-fix PASS WITH NOTES. Source hashes and payloads are verified; prior native-qualified Edit/Mux assembly is unchanged. Package receipt: `.tmp/mkvutil-rework/extract/package-receipt.json`; parent review: `.tmp/mkvutil-rework/extract-parent.2846jape/parent-integration.json`. Broad integrated/all-format/campaign gates remain T04. | T01.01, T01.03, G02 | T02.02, T02.03, T04.01; common source/output checks, final reporting and extraction test fixtures |

### G04 — Checkpoint 4: integration and documentation

| Accepted | Task ID | Required result (mirror plan) | Required evidence / current status | Hard prerequisites | Shared/overlap |
| --- | --- | --- | --- | --- | --- |
| [x] | T04.01 | Verify every adapted single/batch action, shared metadata path, pre-run removal skip-only reconfiguration and final exit after processing together; consolidate task-level receipts and complete all six existing validation groups, including small real-v93/all-format evidence and the near-end interactive rehearsal with disposable `.tmp` fixtures. Verify the runtime-stop contract using focused controlling-terminal signal journeys, owned-process cleanup checks and small installed-v93 qualification on fresh disposable fixtures. | Required: Syntax/static checks, complete affected MKV groups, real-tool integration, retained-property checks, bounded real-entrypoint journeys with mocked/real-tool/TTY boundaries recorded, and final candidate revision evidence; reuse still-valid slice receipts and rerun affected proof only. Status: Accepted after 13 affected checks passed in 31.68s (32.52s wall; 29.10s measured user+system CPU). Coverage includes whole-entrypoint mixed-skip processing/new-invocation retry, three-category finality, grouped workflows, extraction, pre-run subset/Back, report visibility and interruption. Copied source hashes match; syntax and Python AST checks pass. Engines/builders/queue/report formatter are byte-identical to the prior accepted source; no new native or IA campaign is claimed. Current proof: `.tmp/mkvutil-rework/run-final/receipt.json` and `tests.log`. Historical revision evidence: Status: accepted after parent integration review. 79 distinct affected cases are bound to final source across separate runs: 24 current-source cases from the 77-case first run plus 55 final-source reruns/new cases. Eight controlling-PTY signal journeys are included; three separate installed-v93 normal-processing journeys pass. Earlier Back/metadata/all-format evidence remains linked at its revision. Syntax, inline Python, fixture hashes and unchanged shared test helper pass. No single 79-case invocation, new full-suite campaign, native signal codec matrix or CI result is claimed. Current proof: `.tmp/mkvutil-rework/runtime-stop.4mgf2nx6/receipt.json`, `final-source-coverage.json`, `native-receipt.json` and `parent-review.json`. Historical revision evidence: Status: pending corrected full-cohort/recovery/navigation implementation and current consumer/IA/parent review. Historical accepted evidence: Status: accepted after current source/receipt review. 47 complete affected cases plus two distinct controlling-terminal cases pass in separate runs. The sole final assertion strengthening is verified by a focused consumer rerun; reversing that test-only delta reproduces the tested file hash. All38 copied runtimes match current source. No single49-case run, new full/native campaign or CI pass is claimed. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Syntax/static checks, complete affected MKV groups, real-tool integration, retained-property checks, bounded real-entrypoint journeys with mocked/real-tool/TTY boundaries recorded, and final candidate revision evidence; reuse still-valid slice receipts and rerun affected proof only. Prior status: accepted after final candidate integration review. Current proof comprises 25 distinct cases across 14 original passing normal cases, one corrected raw-byte case, seven controlling-PTY cases and three pipe journeys; no single 25-case all-pass invocation is claimed. The initial text-mode CRLF oracle failure is retained; source was unchanged and the helper default protocol independently verified. Total recorded cost including that attempt: 30.24s wall / 25.53s measured CPU. Existing guards remain. Parent verified actual logs/runtime hashes and 22 unchanged reader/engine/builder/safety sections plus shared helper. Receipt: `.tmp/mkvutil-rework/redraw.NtaUm3/receipt.json`. Original six-group, 125+3 aggregated suite, native and real-fzf receipts remain in `.tmp/mkvutil-rework/interactive/t04-campaign.vqvatjsp/`; no new native/full campaign or CI result is claimed. | T02.03, T03.01 | T04.02; all runtime consumers and test fixtures |
| [x] | T04.02 | Update help and the existing user guide against validated behavior, then complete parent final-diff review and reconcile acceptance/restart records. Include polished, collapsible examples for Edit batches, combined Mux metadata, metadata Back and extraction. Document all configuration Back destinations and the processing Ctrl+C boundary in the collapsible examples. Explain graceful Edit/Mux stopping, immediate Extract stopping and missed-file reporting using the validated behavior. | Required: Verified command/menu/docs claims and links, reviewed final diff, and all applicable goal-level gates recorded without publication claims. Status: Accepted after source/docs/final-diff and mirrored-record review. Guide states that every processed queue reports and exits with no follow-up menu or pause; skipped-file retry requires a new invocation, while pre-run configuration/Back remain available. Source/links/privacy and the unchanged parent-session ledger were reviewed. Current proof: `.tmp/mkvutil-rework/run-final/receipt.json` and `tests.log`. Historical revision evidence: Status: accepted after parent final-diff, help, guide and record review. Five balanced collapsible examples cover Edit, combined Mux, metadata Back, Extract and stopping. Graceful versus immediate stopping, exact missed files, recovery limits and all Back destinations match verified behavior. Local links, fences, privacy, stable task/goal contracts and parent-session ledger pass; publication follows under existing authorization. Current proof: `.tmp/mkvutil-rework/runtime-stop.4mgf2nx6/receipt.json`, `final-source-coverage.json`, `native-receipt.json` and `parent-review.json`. Historical revision evidence: Status: pending corrected full-cohort/recovery/navigation implementation and current consumer/IA/parent review. Historical accepted evidence: Status: accepted after current source/receipt review. Guide reviewed against verified prompts/contracts with four balanced collapsible examples for Edit, Mux, metadata recovery and Extract. Local links, code fences, privacy, exact source/test scope and paired records pass parent review; source and tests are unchanged by final prose edits. Current proof: `.tmp/mkvutil-rework/metadata-targets.a_k68kyk/receipt.json`, `parent-review.json` and `docs-review.json`. Historical receipt: Required: Verified command/menu/docs claims and links, reviewed final diff, and all applicable goal-level gates recorded without publication claims. Prior status: accepted after current source/help/guide/test and paired record review. Guide describes shared navigation screen, buffered bodies with native prompts, no intentional redraw delay, readable normal output, e/E Back and existing cursor/instant selection. Parent verified protected functions, hashes, default helper protocol and unchanged session ledger; stable 9 tasks/4 goals, requirements/dependencies/gates and local links remain intact. Review: `.tmp/mkvutil-rework/redraw.NtaUm3/parent-review.json`. Canonical plans stay in `.plans/feature-mkvutil-rework/`; checkout and AGENTS policies are unchanged. | T04.01 | none |

### Current readiness and acceptance limits

- The owned-menu amendment is accepted at T01.03 and T04 with current focused
  proof. Earlier menu/key and original campaign statements retain their historical
  bindings; unchanged engine receipts remain valid.
- T01.01's removal naming policy is user-approved and its pure helper accepted:
  retained video keeps an
  existing `.mkv`/`.mk3d`, audio without video uses `.mka`, and subtitle-only
  uses `.mks`. Focused baseline/contract evidence is recorded above;
  T01.03's per-file preview consumer and removal/selection evidence are accepted.
- T01.02 completion establishes the shared foundation, not acceptance of Edit,
  Mux, or Extract consumers. T01.03 requires actual configuration wiring and
  configuration/cancellation nonmutation evidence.
- The user-approved selector/removal amendment applies to T01.03, T02.02,
  T02.03, and T04.01. One always-multi picker accepts one/several files; removal
  eligibility matches requested original IDs plus media type and native codec,
  allowing name/language/flag differences. Automatic mismatch skips retain
  exact filenames/reasons and the current source scope. Fresh skipped-subset
  planning before processing is a G01 gate; final reporting/exit is a G02 gate.
  The initial controller receipts and final selector/removal delta proof establish T01.03 planning acceptance; accepted T02.03 proof separately establishes result aggregation at its historical revision; current post-run exit passes the final-after-processing checks.
- T02.01's missing normal multi-file Edit gate was reopened and closed by the
  focused two-file corrective proof. T02.02's focused executor, safety and
  small real-v93 semantic gates remain accepted at `f44cd98`.
  T02.03 final reporting/exit and the G02 goal gate are accepted after
  current consumer proof and parent integration review. Extract is now accepted at its separate G03 gate.
  T04.01 consolidates valid slice receipts and integrated affected
  groups; it does not defer all prerequisite proof until the end.
- T03.01 has G01 technical prerequisites plus the approved G02 acceptance-stage
  gate. Verify that goal's own integration gate as well as its task checkboxes.
- These are mirrored readiness rules, not new requirements. Progress and
  acceptance require observed results at the relevant revision/platform.

## Required validation

These are the six existing [plan validation requirements](plan.md#validation-and-acceptance),
accepted for the original rework at T04.01 with aggregated test/native/terminal
evidence. Affected navigation proof for the follow-up is recorded in the task rows:

1. [x] Preserve existing operation assertions, including free-form metadata,
   input defaults/ranges, extraction extensions, extension conversion,
   multi-file failures, and the two-file terminal-variable-output regressions.
   Adjust navigation for the new category entrypoints without weakening
   underlying behavior assertions.
2. [x] Verify submenu comma/range parsing, invalid and duplicate selections,
   category batching, optional Mux metadata, conflicts, cancellation/EOF,
   heterogeneous file layouts, and command counts. Both tools must be covered
   by the shared definitions; Mux must use one output-producing remux command
   and zero `mkvpropedit` calls, counting identification/validation separately.
   Cover applicable behavior for `.mkv`, `.mka`, `.mks`, and `.mk3d`, including
   audio-only, subtitle-only, and stereoscopic inputs, using proportionate cases.
   Verify always-multi selection of one/several files, removal ID/type/codec
   compatibility, automatic whole-job skips, allowed metadata differences,
   exact skipped filenames/reasons, eligibility after configuration changes,
   and fresh pre-run skipped-only reconfiguration. Cover mixed/all-skipped cases, zero
   modifying calls for skipped files, completed-source exclusion, and truthful
   resolved/unresolved final counts/status, and final exit after processing.
3. [x] Verify collisions, the approved attachment-only overwrite exception,
   failed promotion, inspection/validation failures, warning versus error handling,
   interruptions, and incomplete-stage reporting. Include repeated attachment
   names within/across sources, last-successful publication, protected input/
   track aliases, and preservation of earlier collection on a later failure.
4. [x] Correct the reorder test's single-input `0:1,1:0` example and establish
   actual ordering beyond the stub's empty-output behavior.
5. [x] Use a small real fixture on installed v93 tools to prove combined
   removal/reordering/names/languages, mapping to intended tracks, flag parity,
   blank-title clearing, chapters/attachments preservation, and extraction from
   selected sources. Keep real-tool evidence distinct from stub assertions.
6. [x] Run syntax/static checks and all affected MKV test groups once the
   integrated change is ready; broaden only for shared changes or discovered
   failures. Unrelated repository suites are not automatic requirements.

### User-requested near-end interactive rehearsal

- [x] Reuse and adapt the existing menu harness for category single actions,
  representative batches, optional Mux metadata, and controlled input/failure
  journeys; avoid a duplicate test framework.
  Include always-multi selection, removal mismatch reports, and a fresh
  reconfiguration for only the skipped sources before processing, followed by
  final exit after Run; a later retry uses a separate invocation.
- [x] Generate small valid fixtures for all four formats in an owned per-run
  `.tmp` directory, and verify a few real-v93 workflows alongside mocked churn.
- [x] Verify the campaign's bounded approval before execution; record exact
  candidate revision and distinguish mocked, real-tool, and terminal evidence.

These items mirror [the plan's rehearsal](plan.md#near-end-interactive-rehearsal)
within the original accepted T04.01. Their receipts preserve mocked, native and
real-terminal evidence separately; current navigation/help/docs follow-up
acceptance is recorded in the task rows above.

All [track identity](plan.md#track-identity-and-preview),
[metadata](plan.md#metadata-contracts),
[file safety](plan.md#file-safety-and-queue-reporting), format, and acceptance
contracts remain those in the authoritative plan.

**Current amended-scope acceptance: 9 / 9 tasks and 4 / 4 goals.** Final exit,
integration and documentation checks passed. Signed feature publication is
authorized; its exact commit/live-ref verification is recorded separately.
