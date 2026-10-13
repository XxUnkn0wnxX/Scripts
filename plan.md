# mkvutil rework plan

[Acceptance checklist](plan_checklist.md) · [Current handoff](plan_handoff.md)

This document specifies the approved mkvutil rework. Acceptance status belongs
to the checklist; current authorization and restart state belong to the handoff.

For this rework, use the Astra planner for intermittent, focused audits at
meaningful planning or risk changes. The parent maintains this document and owns
design decisions, implementation integration, and final review.

## Purpose

Turn `mkvutil` into a utility that can collect several operations and process a
selected set of files without requiring another interactive run between passes.
Keep the familiar single-operation behavior available while introducing category
menus and batching within each category. Mux jobs offer optional metadata edits
from the same shared definitions as Edit.

The scope is **all currently supported Matroska files: `.mkv`, `.mka`, `.mks`,
and `.mk3d`**. This applies to file discovery, single actions, batch configuration,
previews, execution, and validation. Keep the existing `mkvutil` command name;
use Matroska category labels so the interface does not imply video-only support.
Keep the utility self-contained in `shell/mkv_utils.zsh`: shared definitions,
configuration, planners, and executors live inside that one script. Do not split
runtime helpers into additional `.zsh` dependencies; existing test helpers remain
separate test infrastructure.

The main performance goal is **one full remux per file** when removing and
reordering tracks together. Names, languages, flags, and titles should join the
same configured job. Metadata-only jobs should use the existing fast header-edit
approach and require no full remux.

## Confirmed baseline

- `mkvutil` resolves to `zsh ~/Apps/Scripts/shell/mkv_utils.zsh`.
- The active `mkvmerge`, `mkvpropedit`, and `mkvextract` all report
  **v93.0 (Goblu), 64-bit**. Their `/usr/local/bin` entries point into
  `/Applications/MKVToolNix-93.0.app/Contents/MacOS`.
- The inspected host reports macOS Big Sur **11.7.11**, build `20G1443`.
- Tool upgrades and dependency installation are outside this rework. Version 93.0
  is the compatibility baseline, including its bundled manuals and local help.
- [The script](shell/mkv_utils.zsh) currently accepts one main-menu choice per
  invocation. Metadata helpers collect a value and immediately edit selected
  files before collecting the next value. Removal and reordering each perform
  their own remux.
- File discovery already includes `.mkv`, `.mka`, `.mks`, and `.mk3d`; preserve
  that set consistently in every new entrypoint and shared file selector.
- [Existing documentation](docs/mkv-utils.md) describes the nine choices and
  queue reporting. [The pytest suite](tests/mkv_tools/test_mkv_utils.py) and
  [shared helpers](tests/mkv_tools/_mkv_helpers.py) provide an existing isolated
  interactive test harness.

Version 93's local help and manuals support track selection, `--track-order`,
track names, languages, default/forced flags, and multiple `mkvpropedit` edits in
one invocation. The design therefore needs no newer MKVToolNix feature.
See the official [mkvmerge manual](https://mkvtoolnix.download/doc/mkvmerge.html)
and [mkvpropedit manual](https://mkvtoolnix.download/doc/mkvpropedit.html) for
general references; use the bundled v93 manuals to resolve version-specific
behavior.

## Proposed menus

```text
Main menu
  1) Matroska Edit      Flags, languages, track names, container title
  2) Matroska Mux       Remove and reorder tracks
  3) Matroska Extract   Attachments and selected tracks
  0) Exit
```

Each category allows a single number, a comma-separated list, or ascending
ranges. Validate selections against that submenu, expand ranges, and deduplicate
overlapping selections. Reject empty or invalid selections before collecting
operation settings.

| Category | Submenu choice | Operation | Current choice |
| --- | --- | --- | --- |
| Matroska Edit | 1 | Set forced flags | 1 |
| Matroska Edit | 2 | Set default flags | 2 |
| Matroska Edit | 3 | Set track languages | 3 |
| Matroska Edit | 4 | Set track names | 4 |
| Matroska Edit | 5 | Set or clear container title | 5 |
| Matroska Mux | 1 | Remove tracks | 7 |
| Matroska Mux | 2 | Reorder tracks | 8 |
| Matroska Extract | 1 | Extract attachments | 6 |
| Matroska Extract | 2 | Extract selected tracks | 9 |

- A single selection opens the corresponding familiar operation workflow.
- Multiple selections, such as Edit `1-3` or Mux `1,2`, open batch configuration.
- Both paths select target files once. Edit and Extract batch their own submenu
  operations. Mux allows removal, reordering, or both, followed by optional
  metadata choices from the Edit list, including for a single Mux selection.
- File selection always uses one multi-select picker in every category. Select
  either one file or several through that same picker; remove the Y/N prompt
  and separate single-file mode. This is the user's approved selection change;
  other operation defaults and metadata prompts remain covered below.
- Category boundaries remain clear: configure Mux metadata inside the Mux
  workflow, using the same metadata choices and prompts as Edit. A general
  cross-category operation builder is outside the agreed design.
- Adapt the existing actions into the corresponding category sub-actions.
  Preserve their operation semantics, track-ID input formats, defaults, and
  metadata value prompts while enhancing configuration and execution for
  single or batched selections. The table's current-choice column records the
  migration mapping; the old flat menu is replaced by the category menus.
- Do not implement comma input by calling the old action handlers in sequence:
  they prompt and mutate immediately, which would repeat remuxes and keep the
  current interruptions.

### Category batching and optional Mux metadata

Each category owns its job configuration. Before execution, offer:

```text
  Configure selected category operations
  Configure optional metadata edits (Mux)
  Review or change configured operations
  Preview resulting tracks and outputs
  Run batch
  Cancel
```

For example, select Mux `1,2` for removal and reordering, then optional metadata
`3,4` for languages and names within that Mux workflow. Select metadata by a
single number, comma-separated list, or ascending ranges, using the same labels
and validation as Edit. Select no metadata to run only the Mux operations.

All optional Mux metadata is applied by `mkvmerge` in the same command as the
remux. Standalone Edit uses `mkvpropedit`. Shared configuration must not invoke
either tool or redirect the user through the other main menu.

Collect every setting and resolve every known conflict before starting the
queue. Processing must not pause for the next track name, language, operation,
or file selection. Cancellation during configuration performs no media writes.

## Track identity and preview

Use each file's original track listing as the reference for configuring a job.
Store that file's input track IDs and the expected final retained-track sequence.
Names, languages, and flags stay attached to the selected original track even
when its final displayed ID changes.

For example, an illustrative source contains:

| Original ID | Track | Requested result |
| --- | --- | --- |
| 0 | Video | Keep first |
| 1 | English audio | Keep third; set name and language |
| 2 | Japanese audio | Keep second; set name and language |
| 3 | Full subtitles | Keep fourth |
| 4 | Extra subtitles | Remove |

The plan produces order `0:0,0:2,0:1,0:3`. Preview both original IDs and final
positions, along with requested metadata and output filenames. Editing original
track 1 still edits the English audio after it becomes the third output track.

- Inspect all selected files, not just the first file shown in the UI. Detect
  missing IDs and incompatible layouts before mutation. Present exceptions for
  exclusion or separate configuration before starting, with automatic removal
  mismatch skipping as specified below; do not guess mappings from language
  or name alone.
- Audio-only `.mka` and subtitle-only `.mks` inputs are valid. Do not require a
  video track or invent missing audio/subtitle tracks. Preserve `.mk3d` track
  properties and stereoscopic metadata unless explicitly changed. A mixed-format
  selection is allowed when each file's configured operations are valid.
- Reject edits to removed tracks, removal of every track, duplicate order
  entries, and references to unavailable tracks.
- A partial order keeps MKVToolNix's existing append behavior, but the planner
  must resolve it into a complete retained-track order for preview and execution.
  Every file ID is `0` for these single-input remuxes. Do not rely on an omitted
  track to disappear or on MKVToolNix's default sorting to match the preview.
- For a new batch that removes tracks without requesting reordering, preserve
  the retained tracks' original relative order explicitly. Test the established
  single-action behavior during migration and document intentional changes.
- Apply Mux metadata using the original input track IDs in that file's
  `mkvmerge` arguments; output positions are for preview and validation. Inspect
  the staged result to verify both order and metadata. Track UIDs are not an
  unconditional identity guarantee: v93 can automatically regenerate UIDs for
  MakeMKV sources. Verify the expected original-to-output mapping without
  assuming source positions or UIDs stay unchanged.
- Preserve 64-bit UID values exactly whenever UID selectors are used. Ambiguous
  identity or unsupported track types must stop that file's job before promotion.

### Removal compatibility and skipped-file batches

For removal jobs, display the full filename and original listing of the first
successfully inspected file in the current batch before collecting settings.
That configured reference defines each requested removal ID's expected media
type and native `codec_id`. The ID, type, and codec must match in every eligible
file: ASS and SRT subtitles at the same ID are incompatible. Require usable,
nonempty codec IDs; two missing values do not constitute a match.

- If any requested removal ID is missing or has a different media type/codec,
  automatically skip the entire Mux job for that file. Perform no removal,
  reordering, optional metadata edit, or output-producing remux on it.
- Names, language tags, flags, UIDs, and untargeted track layouts may differ.
  They do not determine removal compatibility. Existing validation still
  applies to other configured targets, empty retained layouts, unsupported
  tracks, unreadable inputs, and changed-source identity.
- Report the exact skipped filenames and paths before execution and in the
  resulting summary, with each mismatched ID, expected type/codec, and actual
  type/codec or missing-ID reason. Distinguish these skips from tool warnings,
  errors, and explicit exclusions; incomplete selections cannot silently count
  as fully successful batches.
- Preserve the current batch's source pool separately from eligible jobs and
  mismatch receipts. Changing settings recomputes eligibility over that scope;
  it must not permanently lose automatically skipped sources. An explicit
  user exclusion remains outside that scope.
- After a run, offer a new Mux batch for only its mismatch-skipped files,
  without processing completed files again. Reinspect that subset, display its
  new reference, clear/recollect settings, and require complete preflight,
  preview, and explicit Run. Repeat only on the user's choice; do not blindly
  reuse old track IDs or automatically rerun a batch.
- An all-skipped batch has no Run option but retains its report and the
  skipped-subset continuation path. Cancellation/EOF is bounded and leaves the
  skipped list visible. Count each original selected source once in the final
  outcome; preserve historical skip receipts. Unresolved skips/failures require
  a nonzero result; completed continuations may resolve earlier skips.

T01.03 establishes eligibility, skip receipts, and fresh subset planning without
media mutation. T02.03 connects post-execution continuation and final reporting;
runtime continuation is not a prerequisite for G01 acceptance.

## Execution model

Separate file selection, operation configuration, planning/validation, execution,
and reporting. Represent each file's desired result as structured data and build
tool arguments as arrays; free-form metadata must never become evaluated shell
code. Keep new helpers proportionate and reuse the existing tools and test setup.

| Configured operations | Planned processing per file |
| --- | --- |
| Forced + default flags, or other Edit selections | One grouped `mkvpropedit` invocation; no full remux |
| Remove + reorder | One output-producing `mkvmerge` remux invocation using retained-track filters and a complete order |
| Reorder + names + languages | One output-producing `mkvmerge` remux invocation applying order and metadata together |
| Remove + reorder + optional metadata | One output-producing `mkvmerge` remux invocation applying retained-track filters, order, and metadata together |
| Extract selections | Extraction operations using `mkvextract` within the Extract category |

Mux jobs must use `mkvmerge`'s corresponding metadata options directly and must
not invoke `mkvpropedit` as a post-remux metadata step. Each file has one remux
command containing its structural changes and optional metadata. Metadata-only
Edit jobs use one grouped `mkvpropedit` command.

Read-only identification and validation calls are separate from this one
output-producing remux command and remain permitted.

### Shared metadata definitions and configuration

Maintain one shared metadata section responsible for the available operations,
their menu labels/order, track-versus-container scope, prompts, defaults, input
validation, and tool-specific argument mappings. Both Edit and the optional Mux
metadata list are generated from that section.

Use a shared configuration function to collect a structured metadata plan. Keep
execution outside that function. Two small argument builders consume the plan:
one produces `mkvpropedit` arguments for Edit, and one produces `mkvmerge`
arguments for Mux. Builders append arguments to arrays and do not execute tools.
Special actions, such as clearing a title, are represented explicitly rather
than being mistaken for an omitted setting.

| Shared metadata choice | Edit mapping | Mux mapping |
| --- | --- | --- |
| Forced flag | `--set flag-forced=VALUE` with the correct track selector | `--forced-display-flag TID:VALUE` |
| Default flag | `--set flag-default=VALUE` with the correct track selector | `--default-track-flag TID:VALUE` |
| Language | `--set language=VALUE` with the correct track selector | `--language TID:VALUE` |
| Track name | `--set name=VALUE` with the correct track selector | `--track-name TID:VALUE` |
| Container title | `--edit info --set title=VALUE`, or `--delete title` when clearing | `--title VALUE`, with clearing semantics to verify on v93 |

Adding a metadata choice requires its shared definition and mappings for both
tools together, plus focused parity coverage. Validate mapping completeness
before collecting or executing a job so a new Edit choice cannot silently be
missing or ignored in Mux. Every offered shared choice must work in both paths.
Do not assume an arbitrary `mkvpropedit` property has an automatic `mkvmerge`
equivalent; resolve unsupported mappings before adding that shared choice.

Keep this as a small explicit set of definitions and helpers using the existing
script's facilities. Avoid separate copies of metadata menus/prompt logic or a
general plugin framework. The tool-specific mappings stay visible and easy to
maintain in that shared section.

The existing `8 + 4 + 3` workflow performs one full remux plus separate header
edits; batching removes its repeated interaction. Combining `7 + 8` removes
an entire additional remux pass. This is a reduction in processing passes,
not a measured runtime-speed claim.

### Metadata contracts

- Preserve track-ID lists and ranges, filenames/names containing spaces,
  supported language input, forced/default values, and their existing defaults.
- Blank container-title input continues to mean **remove the title**. Grouped
  Edit commands must explicitly select `--edit info` before a title operation,
  including when title edits follow track edits. Mux uses `--title` and must
  establish empty-title clearing and literal-value handling on installed v93.
- Setting one default flag must not implicitly redefine every other requested
  or retained track's intended flag. v93's bundled documentation describes a
  difference between `mkvmerge` and `mkvpropedit` default-flag behavior. Capture
  the desired flag state for all retained tracks, including unchanged flags,
  express it through the relevant tool's own arguments, and prove the actual
  result with a real fixture. Do not introduce a `mkvpropedit` fallback for Mux.
- Preserve retained codecs, chapters, attachments, tags, supported language
  fields, and unrequested track properties subject to the existing remux
  contract. Metadata-only jobs use in-place edits and must not claim automatic
  rollback or transactional behavior.

### Extraction batching

Extraction batching is part of the completed rework, after the first Mux + Edit
checkpoint. Attachments and track extraction remain separate tool operations
within one Extract job. This category uses the selected source files directly
and does not include Edit or Mux operations.

- Select files once, collect attachment/track selections upfront, and extract
  the configured items without changing the source media. Keep displayed track
  identities tied to those selected sources.
- Resolve output names and attachment/track collisions across the entire batch.
  Preserve codec-aware extensions while avoiding overwrites between episodes.
- A failed required stage stops further processing for that file and reports
  which extraction stages completed. Previously created sidecars are not
  silently rolled back. A partial extraction job must not be reported as fully
  completed.

## File safety and queue reporting

The current removal path does not check `mv` before reporting success and can
delete the original when changing extensions even if promotion failed. The
reorder path also reports success after an unchecked `mv`. Both use predictable
temporary filenames and treat all nonzero MKVToolNix exits as failures. Address
these concrete issues in the shared execution path before migrating existing
remux actions to it.

- Use uniquely owned staging paths beside the destination. Preflight destination
  collisions across the queue, including `.mkv` to `.mka` name collisions.
  Jobs without removal retain the input's `.mkv`, `.mka`, `.mks`, or `.mk3d`
  extension. Jobs containing removal use the agreed removal output-naming policy.
  The user approved retained-content naming for both single and batch removal:
  video results retain an existing `.mkv` or `.mk3d` extension (otherwise use
  `.mkv`); no-video results with audio use `.mka`; subtitle-only results use
  `.mks`. This deliberately refines choice 7's old blanket no-video `.mka` rule
  while preserving its audio conversion. Reject empty or unsupported retained
  layouts rather than guessing an extension. Preview the final destination and
  preflight collisions before execution.
- Recheck source identity, size, and modification time before mutation and
  promotion to detect a changed input since preflight.
- Validate the staged result against expected tracks/order/metadata before
  replacing anything. Check the actual promotion result before success counts
  or original deletion. On remux, validation, cancellation, or promotion failure,
  preserve the source and report any staged result retained for recovery.
- Distinguish exit `0` (success), `1` (warnings), `2` (error), and interruption or
  other failure statuses. Report warnings separately. Retain staged warning
  candidates for review when they exist; do not silently discard them or
  automatically replace the source. An in-place metadata edit may already have
  changed the original when returning a warning or error: inspect and report
  its actual state without promising an unchanged source or separate recovery
  candidate. Resolve this conservative policy before the batch runs so warnings
  do not cause interactive prompts halfway through the queue.
- Cleanup applies only to temporary files owned by this run. Avoid collisions
  with another invocation's temporary files or outputs.
- Preserve filename reporting and multi-file progress, elapsed time, average ETA,
  and failed-file summaries. Count success only after the complete configured
  file job succeeds. Report warning, failed, and partially completed jobs clearly.
  Mux jobs show the familiar between-file elapsed/count/ETA block. Standalone
  Edit jobs use the final report without between-file elapsed blocks, with
  warnings or failures visible when they occur; still record their outcomes.
  Extract attachment-only and track jobs also show between-file elapsed/count/
  ETA. For a combined attachment-and-track Extract job, that display times the
  track-extraction stage only. The final report covers the complete configured
  batch. The Edit final-report-only rule applies to every single or batched
  Edit choice.
- Include the input directory's basename and category-specific action numbers
  in the final report, alongside completed/skipped/failed/partial outcomes and
  elapsed time. A single selection shows one
  action number; a batch shows its expanded, deduplicated submenu numbers.
  Report optional Mux metadata numbers separately from structural Mux numbers
  so overlapping submenu IDs remain clear. Attribute each skipped-only
  continuation's counts and time to its own configured choices; failed or
  partial jobs must not be presented as fully completed actions. The directory
  label is the resolved source directory's name, including when invoked with
  a relative or absolute directory argument, rather than its full path.
  Use one shared final-report format across Edit, Mux and Extract. T02.03 owns
  that reporting foundation; T03.01 reuses and verifies it for Extract, after
  the existing G02 gate. This does not require Extract execution before G02
  can be accepted.
- Continue with other independent files after a file failure. The batch's exit
  status must reflect incomplete required jobs rather than always returning zero.
- Report removal mismatch skips separately and preserve their exact source
  subset for a fresh configured continuation. Completed files must not re-enter
  that subset; unresolved skips remain visible in the final result.

## Main goals, tasks, and checkpoint mapping

The four existing checkpoints remain the four main goals below. Their names,
scope, and acceptance requirements are preserved; task IDs make the work and
its evidence traceable. Task IDs remain stable through later reordering.
The checklist owns acceptance status; the handoff owns current work and consent.

| Goal ID | Preserved checkpoint | Required task IDs | Goal-level acceptance gate |
| --- | --- | --- | --- |
| G01 | Checkpoint 1: menu and planning contract | T01.01, T01.02, T01.03 | All three tasks accepted; category configuration and preview consume the shared foundation and meet the existing no-mutation gate. |
| G02 | Checkpoint 2: Edit + Mux execution | T02.01, T02.02, T02.03 | All three tasks accepted and combined Edit/Mux workflows meet their semantic, safety, and reporting gates; this is the approved stage gate before Extract implementation. |
| G03 | Checkpoint 3: extraction integration | T03.01 | T03.01 accepted and both single and batched extraction outcomes verified. G02 acceptance is an existing execution-stage gate, not an assumed extraction API dependency. |
| G04 | Checkpoint 4: integration and documentation | T04.01, T04.02 | Both tasks accepted; all required integration/verification evidence is current, help/docs match the implementation, and parent final review is complete. |

### G01 — Checkpoint 1: menu and planning contract

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T01.01 | Capture the existing behavior baseline and establish the original-track, per-file job, and output-naming contract for all four formats. Settle consistent single/batch removal naming before complete previews are accepted; preserve existing action semantics, defaults, and conversion behavior. | none | T01.02, T01.03; source discovery, track model, and shared test fixtures | Existing-behavior assertions and contract review; unresolved naming decisions keep this task pending. |
| T01.02 | Implement one shared metadata definition/configuration section and both tool argument builders inside the self-contained `shell/mkv_utils.zsh`. The Edit list and optional Mux list share labels, prompts, defaults, validation, and complete mappings; configuration/builders do not execute tools. | T01.01 | T01.03, T02.01, T02.02; canonical owner of shared metadata definitions and builders | Focused configuration/argument tests, both-tool mapping completeness, original-ID/scoped arguments, and focused mapping parity evidence appropriate to the foundation; executor semantics remain a T02.02 gate. |
| T01.03 | Adapt existing actions into category submenus; implement single/comma/range operations, always-multi target selection for one/several files, per-file planning, optional Mux metadata, conflicts, and complete previews. Establish removal ID/type/codec eligibility, automatic mismatch skip receipts, preserved batch scope, and fresh skipped-subset planning without media mutation. | T01.01, T01.02 | T02.01, T02.02, T03.01; canonical owner of selection, job planning, identity, and preview | Real entrypoint/configuration wiring, always-multi selection, invalid/cancel/EOF behavior, all-format planning, settled outputs, removal signature/skip/subset contracts, and no-write configuration/cancellation evidence. |

### G02 — Checkpoint 2: Edit + Mux execution

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T02.01 | Implement grouped metadata-only Edit jobs through `mkvpropedit`, preserving existing values, input defaults/ranges, title clearing, and retained properties. Report actual in-place state on warnings/failures without rollback claims. | T01.02, T01.03 | T02.02, T02.03; common source, metadata builders, and test helpers | Focused single/multi-file Edit behavior, grouped command arguments, warning/error state, and consumer integration evidence. |
| T02.02 | Implement one output-producing `mkvmerge` remux per eligible Mux file, combining removal/order with optional direct metadata. Keep removal mismatch-skipped files wholly untouched. Consume the settled naming contract; validate staged output and checked promotion, collisions, warnings, and interruptions. No post-remux `mkvpropedit`. | T01.02, T01.03 | T02.01, T02.03, T03.01; common source/test helpers; owns remux staging and promotion | Focused failures/safety, eligible-file command counts and zero modifying calls for mismatch skips, plus required small real-v93 flag/title/track-mapping and preservation evidence before accepting this executor. |
| T02.03 | Integrate complete single/batch Edit and Mux jobs with exact filename/skip reports, elapsed time, average ETA, truthful successful/failed/warning/partial/skipped outcomes, and failure-reflecting exit status. Final reports identify the input directory basename, category and single/multiple submenu action numbers, with optional Mux metadata numbers separate and each continuation attributed to its own choices. Offer fresh configured Mux continuations for mismatch-skipped files only, counting each source once. Prove the old 1+2, 8+4+3, and 7+8+4+3 workflow equivalents. | T02.01, T02.02 | T03.01, T04.01; shared executor/reporting code and integration fixtures | Affected queue/consumer tests, final action/directory reporting for single/batch/continuation scopes, mixed/all-skipped reporting, fresh subset continuation excluding completed files, resolved/unresolved final counts/status, and partial failures without a full unrelated suite. |

### G03 — Checkpoint 3: extraction integration

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T03.01 | Implement single/batched attachment and track extraction within Extract using one target selection, codec-aware names, deterministic stages, collision handling, and partial-failure reporting without changing source media or claiming sidecar rollback. Reuse the shared final-report format and show between-file elapsed/count/ETA for attachment-only and track extraction; combined attachment-and-track jobs time only the track stage in that display. | T01.01, T01.03, G02 | T02.02, T02.03, T04.01; common source/output checks, final reporting and extraction test fixtures | Affected extraction tests across applicable formats, source-preservation/collision/failure evidence, selected-source real extraction proof, consistent final reports, and extraction timing with the requested stage scope. |

### G04 — Checkpoint 4: integration and documentation

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T04.01 | Verify every adapted single/batch action, shared metadata path, and removal skip-only continuation together; consolidate task-level receipts and complete all six existing validation groups, including small real-v93/all-format evidence and the near-end interactive rehearsal with disposable `.tmp` fixtures. | T02.03, T03.01 | T04.02; all runtime consumers and test fixtures | Syntax/static checks, complete affected MKV groups, real-tool integration, retained-property checks, bounded real-entrypoint journeys with mocked/real-tool/TTY boundaries recorded, and final candidate revision evidence; reuse still-valid slice receipts and rerun affected proof only. |
| T04.02 | Update help and the existing user guide against validated behavior, then complete parent final-diff review and reconcile acceptance/restart records. | T04.01 | none | Verified command/menu/docs claims and links, reviewed final diff, and all applicable goal-level gates recorded without publication claims. |

### Foundations, stage gates, and shared ownership

- T01.01 owns the original-file job/output contract. Removal output naming must
  be settled here before T01.03 can earn complete-preview acceptance; its
  currently unresolved policy is not a license to accept provisional filenames.
- T01.02 is the single canonical owner of shared metadata definitions,
  configuration, and both argument builders. Edit and Mux reuse this work;
  neither consumer receives automatic acceptance from foundation completion.
- T01.03 owns shared file selection, per-file identity/planning, conflicts, and
  preview. Runtime consumers depend on this contract and real configuration
  wiring. A wireframe or stub alone does not establish an integrated menu.
- T02.02 owns remux-specific staging/promotion; T03.01 owns its extraction output
  handling. Shared file paths and helper edits are overlaps requiring one writer,
  not reasons to invent a new common framework or an executor dependency.
- T03.01's technical inputs come from G01, but the previously approved
  Extract-after-Edit+Mux sequencing remains an explicit G02 acceptance gate.
  The dependency checker expands a goal edge to its tasks; the parent must also
  check that goal's integration/verification gate before starting Extract.
- Focused evidence belongs to each implementation slice before its task is
  accepted. T02.02 must establish its required v93 metadata/flag/title/mapping
  and safety proof before acceptance. T04.01 consolidates valid receipts and
  verifies combined behavior; it is not the first proof for all predecessors.
- Source and tests are currently shared surfaces: `shell/mkv_utils.zsh`,
  `tests/mkv_tools/test_mkv_utils.py`, and `tests/mkv_tools/_mkv_helpers.py`.
  Dependency-ready tasks are not automatically safe concurrent writer packages.
  Keep overlapping edits serial or assign one coherent owner; parallelize only
  genuinely independent read-only reviews or exclusively owned artifacts.
- Final help/docs acceptance follows T04.01's validated runtime behavior.
  Lightweight contract notes may accompany foundation work, labelled as drafts.

Before implementation, inspect the selected target's prerequisite closure and
shared surfaces. Where these materially affect scope/order, present A (smallest
independently completable ready tasks) and B (minimal coordinated dependency/
overlap batch), then record the selected route and ownership in the handoff.
The handoff records the selected route and current implementation authorization;
dependency structure and review verdicts do not themselves authorize a package.

Saved presets and noninteractive CLI operation are possible later extensions of
the internal job plans. They are not requirements for the first completed rework.

## Validation and acceptance

Use the existing pytest/subprocess harness with plugin autoload disabled and
bounded temporary fixtures. Keep heavy media checks small and serial on this
host; reuse fixtures instead of adding a large permutation matrix.

1. Preserve the existing operation assertions, including free-form metadata,
   input defaults/ranges, extraction extensions, extension conversion, multi-file
   failures, and the two-file terminal-variable-output regressions. Adjust
   navigation deliberately for the new category entrypoints without weakening
   the underlying behavior assertions.
2. Add focused observable checks for submenu comma/range parsing, invalid and
   duplicate selections, category batching and optional Mux metadata, conflicts,
   cancellation/EOF, heterogeneous file layouts, and command invocation counts.
   Verify shared metadata definitions cover both tools and that Mux metadata
   remains in its one output-producing `mkvmerge` remux call without invoking
   `mkvpropedit`. Identification/validation calls are counted separately.
   Cover discovery and applicable actions for all four supported extensions,
   including audio-only, subtitle-only, and stereoscopic inputs. Use cheap
   parameterized cases and a few representative real fixtures rather than
   repeating the entire suite for each extension.
   Verify the always-multi picker with one/several files, removal ID/type/codec
   matching and automatic whole-job skips, metadata differences that remain
   eligible, exact skip reasons, changed-setting reconsideration, and fresh
   skipped-only continuation. Cover mixed/all-skipped cases, completed-source
   exclusion, and truthful final counts/status without extra remux passes.
3. Cover collisions, failed promotion, inspection/validation failures, warning
   versus error handling, interruptions, and reporting of incomplete stages.
4. Correct the current reorder test's `0:1,1:0` example: it supplies file ID 1 to
   a single-input command. Its stub only creates an empty output and cannot
   establish real track-order correctness.
5. Use a small reusable real Matroska fixture with the installed v93 tools to
   prove combined removal/reordering/names/languages, stable mapping to intended
   tracks, flag parity, blank-title clearing, and preservation of chapters and
   attachments. Include extraction from selected source files. Real-tool
   results are separate from stubbed command assertions.
6. Run syntax/static checks and all affected MKV test groups once the integrated
   change is ready. Broaden only when shared code changes or discovered failures
   justify it; unrelated repository suites are not automatic requirements.

### Near-end interactive rehearsal

At T04.01, after the runtime tasks are integrated and before final help/docs
acceptance, apply `zr0-interactive-testing` to a bounded rehearsal of the actual
`mkvutil` entrypoint. This is the user's requested addition to the integration
checkpoint; the six validation groups and earlier task-level proof remain
required.

- Reuse `tests/mkv_tools/_mkv_helpers.py` and the existing utility tests. They
  already copy the current script, drive its menus through controlled stdin and
  fake `fzf` selections, isolate command resolution, record arguments/output,
  and stop timed-out runs. Adapt their navigation and assertions to the new
  categories and batches rather than creating a second test framework.
- Generate fresh, small, valid `.mkv`, `.mka`, `.mks`, and `.mk3d` fixtures under
  an owned `.tmp/mkvutil-rework/interactive/<run-id>/` directory. Include
  different track layouts, names/paths with spaces, metadata, chapters, and
  attachments where applicable. Reuse tiny source streams; do not treat a renamed
  extension or the existing text placeholders as real format validation.
  Keep originals, operation copies, outputs, and evidence within that run root.
- Cover help/exit, each adapted single action, representative comma/range
  batches, and the old 1+2, 8+4+3, and 7+8+4+3 workflow equivalents. Exercise
  invalid selections, defaults, cancellation/EOF, interruption, collisions, and
  partial failures through controlled cases rather than every permutation.
  Include always-multi selection of one/several files, removal mismatch skips,
  and a configured continuation for only the skipped sources.
- Use mocked tool boundaries for deterministic menu/failure churn, then a few
  serial installed-v93 journeys for real output and retained-property checks.
  Verify combined Mux jobs produce one remux per file and no `mkvpropedit` call.
  If terminal-specific selector behavior needs proof, use a small PTY journey
  with real `fzf`; scripted fake selections alone do not establish that proof.
- Keep setup and runs bounded for Big Sur, with timeouts and no user-media
  changes or tool upgrades. Use fresh per-run fixture directories; any pytest
  `--basetemp` must target a disposable owned child, never the whole `.tmp`
  directory or durable planning records. Add a small fixture helper at the
  existing test location only if the current harness lacks what is needed.
- Before the broad rehearsal runs, verify or obtain one bounded project-wide
  campaign approval and record its scope in the handoff. The current request
  schedules the rehearsal; it does not start it. Record the exact candidate
  revision, journeys, outcomes, and mocked versus real-tool/TTY evidence.

Acceptance requires category single actions and multi-selection batches to work,
optional Mux metadata to be configurable before processing and applied in the
same `mkvmerge` command, and one shared metadata definition/configuration path
serving both tools. No supported combined Mux job may perform more than one
full remux per file. Support for `.mkv`, `.mka`, `.mks`, and `.mk3d` must remain
intact across the new workflow. All four checkpoints remain required before
declaring this rework complete.

Planning/audit receipts, runtime verification status, active permissions, and
the next safe action are maintained in the checklist and handoff. They do not
alter this specification's requirements or imply acceptance of pending tasks.
