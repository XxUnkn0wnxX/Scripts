# mkvutil rework plan

[Acceptance checklist](plan_checklist.md) · [Current handoff](plan_handoff.md)

This document specifies the approved mkvutil rework. Acceptance status belongs
to the checklist; current authorization and restart state belong to the handoff.

For this rework, use the Astra planner for intermittent, focused audits at
meaningful planning or risk changes. The parent maintains this document and owns
design decisions, implementation integration, and final review.

## Latest approved execution trigger

The user's 2026-10-15 instruction removes the Review/change, Preview and Run
menu from every category. Confirming the final required setting starts the batch
after the existing complete preflight. Mux starts when optional metadata is
left blank or its final value is entered; Edit starts after its final value;
Extract starts after its selected-track IDs, or file selection for attachments
alone. Before that boundary, e/E, EOF and Ctrl+C retain their cancellation/Back
behavior. All-skipped/no-eligible configurations report and exit without writing.
There is no extra acknowledgement or retry menu. Final reports preserve exact
skipped/failed filenames and removal ID/type/codec mismatch details. Processing
still ends the invocation. These instructions supersede the earlier review/preview, explicit-Run and
skipped-subset-menu requirements; current contracts below follow this trigger.

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
- At the initial review, [the script](../../shell/mkv_utils.zsh) accepted one main-menu choice per
  invocation. Metadata helpers collected a value and immediately edited selected
  files before collecting the next value. Removal and reordering each perform
  their own remux.
- File discovery already includes `.mkv`, `.mka`, `.mks`, and `.mk3d`; preserve
  that set consistently in every new entrypoint and shared file selector.
- The initial [documentation](../../docs/mkv-utils.md) described the nine choices and
  queue reporting. [The pytest suite](../../tests/mkv_tools/test_mkv_utils.py) and
  [shared helpers](../../tests/mkv_tools/_mkv_helpers.py) provide an existing isolated
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

### Menu navigation

Ctrl+C exits the utility. Do not display a dedicated Exit or Cancel choice.
The main menu also accepts hidden `e`/`E` for silent exit. Category action
and optional Mux metadata menus show `e) Back`.
At an interactive terminal, main-menu choices `1`, `2`, `3`, and hidden `e`/`E`
act on a single keypress without Enter. Submenu batch selections and data fields
remain line-based; redirected input retains its existing line-based behavior.
On a capable interactive terminal, navigation menus own a temporary screen:
each active menu replaces the previous menu's choices. Adjacent navigation-only
views retain that screen rather than exiting/reentering it. Buffer the complete
menu body, then overwrite it in one literal-safe write, clearing stale line
endings and unused rows without a blank-before-paint screen clear. Existing
readers emit their prompts; do not add animation, sleeps or artificial delay. Restore the main-menu
`Category:` selector while keeping immediate single-key selection. Keep the
normal terminal cursor visible while waiting, retaining its existing style and
blinking behavior. Restore terminal state before submenu/data input and normal
or interrupted exit. Main `e`/`E` remains hidden exit; submenu `e`/`E` remains Back.

Keep file selection, track models/value collection, processing output
and final reports in normal terminal history. Leave the owned screen before
validation errors or durable output, including picker, configuration, planning
and execution boundaries. Capture navigation diagnostics and restore the screen
in the parent shell before displaying them. Successful navigation reads retain
the view; failed reads, EOF, interruption and final exit restore normal screen/
cursor without changing queue handlers or exit status.
A scope report produced by configuration Back may require acknowledgement
before navigation resumes. Completing configuration has no acknowledgement:
validate all jobs, process eligible files, then print the final report and exit. Redirected/unsupported operation keeps
the existing plain protocol, without alternate-screen escapes or added reads.
Metadata configuration also accepts exact `e`/`E` at its track-ID and value
prompts. Clear all pending metadata when returning: Edit returns to its action
menu with the same file selection; Mux returns to its optional metadata list
with removal and reorder settings preserved. At that list, select a different
metadata range or leave it blank to skip metadata. Exact `\e`/`\E` in a name
or title sets the literal value `e`/`E`; other text remains literal. Removal,
reorder and extraction-ID fields also accept `e`/`E` to discard the pending
configuration and return to the category action menu with files retained.
File-exclusion prompts during inspection/planning accept the same Back control.
EOF, Ctrl+C and existing ID-prompt `cancel` keep their termination semantics.

Before selection, Back from category actions returns to main without opening
the picker. After selection, Back from configuration fields returns to the
same category actions, retaining sources, exclusions and result history while
discarding pending configuration. Each newly confirmed action selection gets a
fresh requested-batch record with its own action numbers. Selecting Back again
returns to main, preserving unresolved skip outcomes before starting a new
selection scope. A new scope rescans the directory and opens a fresh picker.
Optional Mux metadata is the exception: `e` at a metadata value returns to that
list and retains removal/order, while `e` at the list itself closes the current
scope and returns directly to the main categories. Preserve outcomes and show a
scope report only when the existing reporting rules require it.

Publish an inspected source pool only after the complete eligible selected
cohort has been inspected successfully. Back during initial or fresh-subset
inspection leaves no partial published pool. The next confirmed action
reinspects that same selected cohort without another picker or ledger reset.
Retain explicit exclusions and all skip history; never replay completed files
or silently omit uninspected files. Pre-inspection request attribution uses the
complete current selected cohort, including a prepared skipped subset, with
explicit exclusions/completed sources filtered through verified ledger state.
Malformed or missing ledger evidence fails rather than silently dropping a file.

These shortcuts apply to the utility's prompts and menus. The file picker's
search uses its own controls. While a processing command runs, add no `e`
reader or polling: Ctrl+C remains the stop control.

The interactive entrypoint has no skipped-subset preparation menu. Once a
queue has processed, print the final report once and end the invocation: no main
menu, acknowledgement, retry menu or further configuration. This applies to
success, warning, failure, partial and skipped outcomes. Preserve their exit
status. Retrying skipped files requires a new invocation and explicit selection
of those files. EOF or Ctrl+C terminates before a new scope or ledger reset.

Configuration navigation belongs to T01.03; final exit after processing belongs
to T02.03, with affected T04 integration/documentation gates. Verify affected navigation and ledger boundaries with
focused tests and the permitted small isolated interactive probe; reuse unchanged
engine/native/campaign receipts rather than rerunning the completed broad campaign.

### Category batching and optional Mux metadata

Each category collects its required settings, then starts automatically after
all selected sources pass planning/preflight or receive explicit exclusions or
removal-mismatch skips. No Review/change, Preview or Run menu appears.

| Category | Final input that starts processing |
| --- | --- |
| Edit | Last per-ID metadata value or container title. |
| Mux without metadata | Blank optional metadata selection. |
| Mux with metadata | Last value for the selected metadata actions. |
| Extract tracks or tracks + attachments | Track-ID selection. |
| Extract attachments only | File-picker selection. |

Back remains available at configuration fields before that input is accepted.
The final input is the execution boundary; later typed e/EOF does not cancel a
completed configuration. Existing preflight exclusion questions still apply.

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

### Metadata batch targets and configuration recovery

- Edit asks for original track IDs once for the selected batch, only when a
  track-scoped action needs them. Reuse that ordered set for all selected track
  metadata actions. Title-only configuration asks no track IDs; title actions
  do not replace the shared track-target set.
- Each track metadata action asks for a separate value for each original ID,
  with the action and ID clearly identified in the prompt. Reuse each value for
  that same original ID in every eligible selected file. For targets `0,4,3`,
  ask ID 0, then 4, then 3 for each choice. Collect all values before automatic processing.
- Mux removal and reordering keep separate inputs. Validate removal first;
  reject removing every track. If the proposed order includes a removed ID,
  unknown ID, duplicate or malformed entry, explain the error and ask for the
  order again without losing removal settings or the selected file scope.
- When reordering is selected, optional track metadata inherits exactly the
  explicitly entered reorder IDs, in their entered sequence. Display those
  IDs in the optional metadata menu and do not ask for them again. For
  `0:0,0:4,0:3`, targets are 0, 4 and 3; omitted retained tracks still append
  without receiving those requested edits. Metadata never targets removed IDs.
- Removal-only Mux metadata keeps independent ID selection per track action,
  validated against retained original IDs. Container title is one global
  prompt in either path.
- Metadata-field Back clears all partially collected settings, argument arrays
  and the current attempt's metadata-choice attribution. Returning to the Mux
  metadata menu retains structural settings. Completed configuration/history
  records remain intact. EOF retains the truthful requested-choice attribution.

This user-directed amendment belongs to shared foundation T01.02, configuration
T01.03, affected Edit/Mux/reporting consumers T02.01–T02.03 and T04 integration/
documentation. Verify the affected collectors, original-ID mapping, retry and
Back/EOF/history boundaries with existing focused tests and a small isolated
terminal probe. Reuse unchanged builders/engines and their native receipts.

## Track identity and preview

The internal preview data describes each planned result for validation and
diagnostic tests; it is not an interactive preview or confirmation step.

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

The plan produces order `0:0,0:2,0:1,0:3`. Record both original IDs and final
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
- After a run, report mismatch-skipped files and end the invocation. To retry,
  the user starts a new invocation and explicitly selects the skipped files.
  Reinspect that selection, clear/recollect settings, and require complete
  preflight before automatic processing. Do not automatically replay completed files.
- An all-skipped batch prints its final report and exits nonzero without
  writing or showing another menu. Count each selected source once and preserve
  its skip reason. Retrying requires a new invocation. Cancellation/EOF before
  the final required input remains bounded and leaves recorded outcomes intact.

T01.03 establishes eligibility, skip receipts, and fresh subset planning without
media mutation until final input and preflight succeed. T02.03 connects final
reporting and termination after processing;
processing is not a prerequisite for G01 acceptance.

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
- Attachment extraction collects into one shared `Attachments/` folder under
  the source directory for both one-file and multi-file jobs, preserving embedded
  filenames. The user explicitly permits replacing existing regular attachment
  files and earlier collected attachments with the same resolved filename,
  including its extension. Process selected sources in order, then each source's
  original attachment-list order; the last successfully published attachment wins.
  Do not require equal MIME types, sizes, checksums or content before replacement,
  and do not introduce overwrite prompts between files.
- Stage each attachment under a unique internal name, including duplicate names
  within one source, and validate the successful native stage before checked
  replacement. A warning/error stage leaves the existing collection intact;
  a later publication failure keeps earlier published files and reports remaining
  staged candidates. Report processed attachments separately from the final
  unique filenames and their winning source/attachment. Earlier successful jobs
  remain successful when their collected bytes are later superseded.
- Resolve physical output families and collisions across the entire batch.
  Track sidecars and codec-derived companions retain collision/no-overwrite
  protection. The attachment exception permits attachment-to-attachment matches
  under the filesystem's case/Unicode rules; reject directory/symlink leaves,
  aliases of selected input media (including inode aliases), unsafe embedded
  names, and attachment-versus-track output collisions. Preserve codec-aware
  track extensions and include companion files in preview and preflight.
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
  layouts rather than guessing an extension. Plan the final destination and
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
- Ctrl+C during an active Edit/Mux file requests a stop after that file's normal
  validation and publication/actual-state observation. Repeated Ctrl+C has the
  same effect. Stop before starting another file, retain its truthful outcome,
  and list the exact ordered filenames not started because of the stop.
- Extract Ctrl+C stops its native process immediately. Discard declared owned
  partial track artifacts only from an interrupted, unvalidated extraction stage
  after its process has stopped. Preserve completed outputs and attachments;
  retain validated/uncertain recovery artifacts and report cleanup failures.
  TERM/HUP and ordinary failures keep conservative recovery behavior. Actual
  processing does not interpret e/E; configuration Ctrl+C still exits immediately.
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
  so overlapping submenu IDs remain clear. Attribute counts and time to the
  configuration actually processed; failed or partial jobs must not be
  presented as fully completed actions. The directory
  label is the resolved source directory's name, including when invoked with
  a relative or absolute directory argument, rather than its full path.
  Use one shared final-report format across Edit, Mux and Extract. T02.03 owns
  that reporting foundation; T03.01 reuses and verifies it for Extract, after
  the existing G02 gate. This does not require Extract execution before G02
  can be accepted.
- Continue with other independent files after a file failure. The batch's exit
  status must reflect incomplete required jobs rather than always returning zero.
- Report removal mismatch skips separately with their exact filenames. After
  processing, print the final report and exit without another menu or prompt.
  Any retry is a separate invocation; unresolved skips keep the original run
  nonzero and remain visible in its final result.

## Main goals, tasks, and checkpoint mapping

The four existing checkpoints remain the four main goals below. Their names,
scope, and acceptance requirements are preserved; task IDs make the work and
its evidence traceable. Task IDs remain stable through later reordering.
The checklist owns acceptance status; the handoff owns current work and consent.

| Goal ID | Preserved checkpoint | Required task IDs | Goal-level acceptance gate |
| --- | --- | --- | --- |
| G01 | Checkpoint 1: menu and planning contract | T01.01, T01.02, T01.03 | All three tasks accepted; category configuration consumes the shared foundation, with no media mutation until all required input and preflight succeed. |
| G02 | Checkpoint 2: Edit + Mux execution | T02.01, T02.02, T02.03 | All three tasks accepted and combined Edit/Mux workflows meet their semantic, safety, and reporting gates; this is the approved stage gate before Extract implementation. |
| G03 | Checkpoint 3: extraction integration | T03.01 | T03.01 accepted and both single and batched extraction outcomes verified. G02 acceptance is an existing execution-stage gate, not an assumed extraction API dependency. |
| G04 | Checkpoint 4: integration and documentation | T04.01, T04.02 | Both tasks accepted; all required integration/verification evidence is current, help/docs match the implementation, and parent final review is complete. |

### G01 — Checkpoint 1: menu and planning contract

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T01.01 | Capture the existing behavior baseline and establish the original-track, per-file job, and output-naming contract for all four formats. Settle consistent single/batch removal naming before complete job plans are accepted; preserve existing action semantics, defaults, and conversion behavior. | none | T01.02, T01.03; source discovery, track model, and shared test fixtures | Existing-behavior assertions and contract review; unresolved naming decisions keep this task pending. |
| T01.02 | Implement one shared metadata definition/configuration section and both tool argument builders inside the self-contained `shell/mkv_utils.zsh`. The Edit list and optional Mux list share labels, prompts, defaults, validation, and complete mappings; configuration/builders do not execute tools. Apply the metadata batch-target and Back contracts through this shared collector. | T01.01 | T01.03, T02.01, T02.02; canonical owner of shared metadata definitions and builders | Focused configuration/argument tests, both-tool mapping completeness, original-ID/scoped arguments, and focused mapping parity evidence appropriate to the foundation; executor semantics remain a T02.02 gate. |
| T01.03 | Adapt existing actions into category submenus; implement single/comma/range operations, always-multi target selection for one/several files, per-file planning, optional Mux metadata, conflicts, and complete job plans. Start automatically after the final required input and complete preflight; remove Review/change, Preview and Run menus from every category, including post-configuration acknowledgement and skipped-subset menus. All-skipped/no-eligible configurations report and exit without writes. Establish removal ID/type/codec eligibility, automatic mismatch skip receipts, preserved batch scope, and internal skipped-subset planning without media mutation. Follow the menu-navigation contract for Ctrl+C, hidden main-menu exit and menu and metadata Back, preserving scope and truthful result history. Apply the metadata batch-target contract, retry invalid reorder entries while retaining removal, and preserve scope when metadata Back clears pending settings. Support e/E at all utility configuration and preflight-exclusion prompts with atomic full-cohort inspection recovery; Mux metadata-list Back returns directly to main. | T01.01, T01.02 | T02.01, T02.02, T03.01; canonical owner of selection, job planning, identity, and per-file plans | Real entrypoint/configuration wiring, always-multi selection, invalid/cancel/EOF behavior, all-format planning, settled outputs, removal signature/skip contracts, final-input automatic execution and no-write incomplete-configuration/Back/cancellation evidence; focused navigation, field-value and ledger-boundary proof for the approved follow-up. |

### G02 — Checkpoint 2: Edit + Mux execution

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T02.01 | Implement grouped metadata-only Edit jobs through `mkvpropedit`, preserving existing values, input defaults/ranges, title clearing, and retained properties. Report actual in-place state on warnings/failures without rollback claims. Apply each collected per-ID value to the same original ID in every eligible selected file. During processing, Ctrl+C finishes the active Edit file and its actual-state validation, then stops before another file; repeated Ctrl+C keeps the same stop request. | T01.02, T01.03 | T02.02, T02.03; common source, metadata builders, and test helpers | Focused single/multi-file Edit behavior, grouped command arguments, warning/error state, and consumer integration evidence. |
| T02.02 | Implement one output-producing `mkvmerge` remux per eligible Mux file, combining removal/order with optional direct metadata. Keep removal mismatch-skipped files wholly untouched. Consume the settled naming contract; validate staged output and checked promotion, collisions, warnings, and interruptions. No post-remux `mkvpropedit`. Reorder metadata targets only the explicit original reorder IDs; appended retained tracks keep unrequested metadata. During processing, Ctrl+C finishes the active Mux file including validation and checked promotion, then stops before another file; repeated Ctrl+C keeps the same stop request. | T01.02, T01.03 | T02.01, T02.03, T03.01; common source/test helpers; owns remux staging and promotion | Focused failures/safety, eligible-file command counts and zero modifying calls for mismatch skips, plus required small real-v93 flag/title/track-mapping and preservation evidence before accepting this executor. |
| T02.03 | Integrate complete single/batch Edit and Mux jobs with exact filename/skip reports, elapsed time, average ETA, truthful successful/failed/warning/partial/skipped outcomes, and failure-reflecting exit status. Final reports identify the input directory basename, category and single/multiple submenu action numbers, with optional Mux metadata numbers separate and each configuration attributed to its own choices. Report skipped/failed files and mismatch details, counting each source once; all-skipped/no-eligible configurations report and exit without writes. Once a queue has processed, print its final report and exit without menus, acknowledgement or retry prompts; retry skipped files only in a new invocation. Prove the old 1+2, 8+4+3, and 7+8+4+3 workflow equivalents. Clear abandoned current metadata choices on Back without losing requested EOF attribution or earlier outcomes. Preserve complete current-cohort request attribution, exclusions, skip history and sticky outcomes across Back and reinspection. Preserve the active file outcome independently from a stop request and print the exact ordered filenames not started due to stopping, including skipped-only retry cohorts. | T02.01, T02.02 | T03.01, T04.01; shared executor/reporting code and integration fixtures | Affected queue/consumer tests, final action/directory reporting for single/batch/pre-run scopes, mixed/all-skipped reporting, automatic-start/all-skipped behavior and separate-invocation skipped-file retries, resolved/unresolved final counts/status, and partial failures without a full unrelated suite. |

### G03 — Checkpoint 3: extraction integration

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T03.01 | Implement single/batched attachment and track extraction within Extract using one target selection, codec-aware names, deterministic stages, shared attachment collection with approved filename overwrites, track/companion collision protection, and partial-failure reporting without changing source media or claiming sidecar rollback. Reuse the shared final-report format and show between-file elapsed/count/ETA for attachment-only and track extraction; combined attachment-and-track jobs time only the track stage in that display. Ctrl+C stops extraction immediately; after the owned native process stops, discard only declared owned track artifacts from an interrupted unvalidated stage. Keep completed outputs, attachments and validated or uncertain recovery artifacts; report cleanup failures. | T01.01, T01.03, G02 | T02.02, T02.03, T04.01; common source/output checks, final reporting and extraction test fixtures | Affected extraction tests across applicable formats, shared attachment overwrite/order/supersession and protected track/companion collision evidence, source-preservation/failure evidence, selected-source real extraction proof, consistent final reports, and extraction timing with the requested stage scope. |

### G04 — Checkpoint 4: integration and documentation

| Task ID | Required result | Hard prerequisites | Shared/overlap | Task acceptance evidence |
| --- | --- | --- | --- | --- |
| T04.01 | Verify every adapted single/batch action, shared metadata path, automatic start after complete input/preflight, removal mismatch reporting and final exit after processing together; consolidate task-level receipts and complete all six existing validation groups, including small real-v93/all-format evidence and the near-end interactive rehearsal with disposable `.tmp` fixtures. Verify the runtime-stop contract using focused controlling-terminal signal journeys, owned-process cleanup checks and small installed-v93 qualification on fresh disposable fixtures. | T02.03, T03.01 | T04.02; all runtime consumers and test fixtures | Syntax/static checks, complete affected MKV groups, real-tool integration, retained-property checks, bounded real-entrypoint journeys with mocked/real-tool/TTY boundaries recorded, and final candidate revision evidence; reuse still-valid slice receipts and rerun affected proof only. |
| T04.02 | Update help and the existing user guide against validated behavior, then complete parent final-diff review and reconcile acceptance/restart records. Include polished, collapsible examples for Edit batches, combined Mux metadata, metadata Back and extraction. Document all configuration Back destinations and the processing Ctrl+C boundary in the collapsible examples. Explain graceful Edit/Mux stopping, immediate Extract stopping and missed-file reporting using the validated behavior. | T04.01 | none | Verified command/menu/docs claims and links, reviewed final diff, and all applicable goal-level gates recorded without publication claims. |

### Foundations, stage gates, and shared ownership

- T01.01 owns the original-file job/output contract. Removal output naming must
  be settled here before T01.03 can earn complete-plan acceptance; any
  unresolved policy is not a license to accept provisional filenames.
- T01.02 is the single canonical owner of shared metadata definitions,
  configuration, and both argument builders. Edit and Mux reuse this work;
  neither consumer receives automatic acceptance from foundation completion.
- T01.03 owns shared file selection, per-file identity/planning, conflicts, and
  the automatic-start boundary. Runtime consumers depend on this contract and real configuration
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
   eligible, exact skip reasons, changed-setting reconsideration, and pre-run
   skipped-only reconfiguration plus separate-invocation retries. Cover mixed/all-skipped cases, completed-source
   exclusion, and truthful final counts/status without extra remux passes.
3. Cover collisions, the approved attachment-only overwrite exception, failed
   promotion, inspection/validation failures, warning versus error handling,
   interruptions, and reporting of incomplete stages. Include repeated attachment
   names within/across sources, last-successful publication, protected input/
   track aliases, and preservation of earlier collection on a later failure.
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
  and mixed/all-skipped final reports. Verify automatic start after complete
  input/preflight, no review or confirmation prompt, final exit after processing,
  and any later retry through a new invocation.
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
