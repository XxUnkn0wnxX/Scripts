# mkvutil rework plan

Status: planning only. This plan and the `feature/mkvutil-rework` branch are
authorized; script implementation has not started.

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

The main performance goal is **one full remux per file** when removing and
reordering tracks together. Names, languages, flags, and titles should join the
same configured job. Metadata-only jobs should use the existing fast header-edit
approach and require no full remux.

## Confirmed baseline

Reviewed on 2026-10-14 from commit
`3c4d4247487babcff7fe23e9f05f2ee554e9f730` on `develop`. The working tree was
clean before creating `feature/mkvutil-rework`.

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
  exclusion or separate configuration before starting; do not guess mappings
  from language or name alone.
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

The current `8 + 4 + 3` workflow already performs one full remux plus separate
header edits; batching primarily removes its repeated interaction. Combining
`7 + 8` removes an entire additional remux pass. No runtime speedup has been
benchmarked during this planning review.

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
  Current choice 7 chooses `.mka` whenever no video remains; preserve its
  established conversions during migration. Before implementing removal,
  explicitly settle consistent single/batch output naming for audio-only,
  subtitle-only, and 3D results, including this existing `.mka` rule. Do not
  silently force every new batch output to `.mkv` or assume every no-video
  result contains audio.
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
- Continue with other independent files after a file failure. The batch's exit
  status must reflect incomplete required jobs rather than always returning zero.

## Implementation checkpoints

- [x] Review the current script, documentation, and existing test harness.
- [x] Verify installed tools and the Big Sur compatibility baseline.
- [x] Create the rework branch and write this planning document.
- [x] Independently audit the proposal and incorporate material corrections.
- [ ] **Checkpoint 1: menu and planning contract.** Capture the existing behavior
  baseline with the focused suite; adapt existing actions into category submenus.
  Implement selection parsing, category job configuration, shared metadata
  definitions, optional Mux metadata, conflicts, and preview. Prove that
  configuration and cancellation produce no media mutations.
- [ ] **Checkpoint 2: Edit + Mux execution.** Implement grouped metadata-only jobs
  and one-command Mux jobs using `mkvmerge`'s own metadata arguments, safe
  promotion, output validation, and queue reporting. Prove `1 + 2`, `8 + 4 + 3`,
  and `7 + 8 + 4 + 3` equivalents using the category mappings above.
- [ ] **Checkpoint 3: extraction integration.** Implement multi-selection in
  Extract, one target-file selection for its batched operations, codec-aware
  output names, deterministic stage ordering, and collision/failure reporting.
- [ ] **Checkpoint 4: integration and documentation.** Verify every adapted
  single/batch action and shared metadata path, update help and the existing
  guide, complete affected validation, and review the final diff.

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

Acceptance requires category single actions and multi-selection batches to work,
optional Mux metadata to be configurable before processing and applied in the
same `mkvmerge` command, and one shared metadata definition/configuration path
serving both tools. No supported combined Mux job may perform more than one
full remux per file. Support for `.mkv`, `.mka`, `.mks`, and `.mk3d` must remain
intact across the new workflow. All four checkpoints remain required before
declaring this rework complete.

### Evidence from this planning session

- Source/documentation/test inspection and installed version/help/manual checks
  completed.
- `zsh -n shell/mkv_utils.zsh` and `git diff --check` passed for the reviewed tree.
- Latest selective Astra audit: **PASS WITH NOTES** for category batching,
  optional Mux metadata, direct `mkvmerge` execution, and shared metadata
  definitions serving both tools. The distinction between read-only tool calls
  and the one output-producing remux call is incorporated above.
- Existing actions move directly into category submenus, following the user's
  clarified navigation requirement. Operation behavior and format support remain
  regression requirements for those adapted single and batch paths.
- Automated tests and real media operations were not executed during this review.
  Proposed combined behavior and metadata parity remain implementation gates.
- No utility implementation, media replacement, dependency upgrade, publication,
  or push is part of this planning change.
