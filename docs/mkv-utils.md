# `mkv_utils.zsh`

[← Back to the toolkit](../README.md)

`mkv_utils.zsh` is an interactive Matroska utility for editing metadata, remuxing tracks, and extracting attachments or tracks. It handles `.mkv`, `.mka`, `.mks`, and `.mk3d` files and lets you combine compatible actions into one reviewed batch.

## Quick start

From the repository root, run it against the current directory:

```zsh
zsh shell/mkv_utils.zsh
```

Or choose a directory. Paths containing spaces should be quoted:

```zsh
zsh shell/mkv_utils.zsh ../
zsh shell/mkv_utils.zsh "/Volumes/Media/My Show"
```

With no directory argument, the current directory is used. The scan is top-level only; it does not recurse into subdirectories. You can also pass the same optional directory argument through an existing `mkvutil` alias.

The built-in help is available with:

```zsh
zsh shell/mkv_utils.zsh --help
```

## Requirements

The script uses the installed `mkvmerge`, `mkvextract`, `mkvpropedit`, `jq`, `fzf`, and Python 3 with the existing `pymkv` module and `pymkv2` distribution. The rework adds no dependencies or separate runtime helper scripts. When the repository `.venv` exists, the script uses its Python interpreter, including when `.venv` is a symlink.

This utility is maintained for the installed MKVToolNix **v93.0 (Goblu), 64-bit** on macOS Big Sur. The rework was verified against that installed version; upgrading MKVToolNix is not required.

For a fresh checkout that does not yet have the Python packages, create the repository environment and install the repository requirements:

```zsh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If your existing repository environment already has its dependencies, keep using it. No per-user global Python install is needed when the repository `.venv` is available.

## Choose a category and batch its actions

The main menu keeps the work areas separate:

At the main **Category:** selector, press `1`, `2`, or `3` to open a category immediately; no Enter is needed. The normal terminal cursor remains visible while waiting for this key. Submenu batches and text fields still use Enter to confirm input, with the cursor visible. Hidden `e`/`E` exits the main menu; submenu `e`/`E` goes Back.

When standard input, output and error all use a terminal and `TERM` is set to a value other than `dumb`, navigation uses a transient alternate screen. Adjacent navigation menus share this screen. Each complete menu body is prepared first and printed together over the previous view, erasing old line endings and unused rows. Navigation redraws add no animation or intentional wait. The category and working directory stay visible, followed by the native input prompt. The utility leaves this screen before the file picker, configuration fields, processing, previews, reports or validation errors. It never clears the normal screen or scrollback.

Previews, removal-mismatch details and reports remain in normal terminal history. Press Enter after these views before navigation resumes; a scope report is acknowledged before returning to main. A successful Run prints its final report and exits without an extra pause. Redirected streams and empty or `dumb` terminal settings disable owned views and these acknowledgements. Piped input retains the line-based protocol.

| Main menu | Actions | What it does |
| --- | --- | --- |
| **1. Matroska Edit** | 1 forced flag, 2 default flag, 3 language, 4 name, 5 title | Applies metadata edits with `mkvpropedit`. |
| **2. Matroska Mux** | 1 remove tracks, 2 reorder tracks | Remuxes each eligible file once; optional metadata can be included in that remux. |
| **3. Matroska Extract** | 1 attachments, 2 selected tracks | Extracts attachments, tracks, or both from each selected source. |

Within a category, enter one action, a comma-separated list, or an ascending range. For example, `1`, `1,2`, or `1-3`. The same format is used for optional Mux metadata choices. The file picker is always multi-select: select one file or mark several with Tab, then confirm the selection.

After choosing files, configure all selected operations. The review menu lets you change the configuration, preview planned changes and outputs, or run the batch. Media-changing commands start only after you choose **Run**. A preview is a review step; it does not perform the operation.

Action menus show **e) Back** and accept either `e` or `E`. Before selecting files, Back returns to the main categories. After selection, Back from review, replacement actions, or the optional Mux metadata list returns to the same category's action list, keeping the selected files and explicit exclusions. Choose new actions to configure them afresh; the file picker does not repeat. Back from that action list returns to the main categories. Choosing a new category then scans the directory and opens a fresh picker.

At any metadata track-ID or value prompt, exact `e` or `E` discards all partially entered metadata. In Edit, it returns to the action list with the selected files retained. In Mux, it returns to the optional metadata list while retaining removal and reorder settings; choose metadata again or leave the list blank to skip it. Back from the optional metadata list itself still returns to the category action list.

To enter a literal name or title of `e` or `E`, use `\e` or `\E`. Only those exact text escapes are decoded; other text, including whitespace, backslashes and `cancel`, is preserved. At a metadata track-ID prompt, `cancel` still cancels the invocation. EOF or Ctrl+C ends the invocation. A successful Run prints its final report and ends the invocation.

### Edit

| Action | Edit |
| --- | --- |
| 1 | Set `flag-forced` for selected tracks. Default value: `0`. |
| 2 | Set `flag-default` for selected tracks. Default value: `1`. |
| 3 | Set a language value for selected tracks. |
| 4 | Set a track name. |
| 5 | Set the container title. Leave the title blank to clear it. |

For example, choose category `1`, actions `3,4`, select one or more files, then enter the original track IDs once for both actions. Each action asks for a separate value for each ID in the order you entered them. Each value applies to that same original ID in every eligible selected file. A title is entered once for the whole batch, and title-only Edit asks for no track IDs. Edit changes the selected files in place. Multiple metadata changes for one file are grouped into a single `mkvpropedit` invocation.

Edit is metadata-only: it does not print a between-file elapsed-time/ETA block. Its final report records the selected actions, files and outcomes.

| To do this | Configure |
| --- | --- |
| Change both track flags | Edit `1,2` |
| Set language and track name | Edit `3,4` |
| Set a title or clear it | Edit `5`; enter a title, or leave the title prompt blank |

<details>
<summary>Example: set forced and default flags for the same tracks across several files</summary>

1. Press `1` at **Category**, then enter Edit actions `1,2`.
2. Mark the files with Tab in the picker and confirm.
3. Enter track IDs `4,3` once. This example assumes both IDs exist with compatible track types in the selected files.
4. Supply each track's values when prompted:

| Action | Original ID 4 | Original ID 3 |
| --- | --- | --- |
| Forced flag | `0` | `1` |
| Default flag | `1` | `0` |

The prompts identify the original ID and action. Forced values are collected for ID 4, then ID 3; default values follow in the same order. Each value applies to that ID in every eligible selected file. The second action does not ask for IDs again.

Choose **2) Preview** to inspect the plan, then **3) Run batch** to apply it. Both actions use one grouped `mkvpropedit` command per file.

</details>

### Mux

| Action | Mux operation |
| --- | --- |
| 1 | Remove selected original track IDs. |
| 2 | Reorder tracks using the original track IDs. Omitted retained tracks are appended in their existing order. |

You can choose `1,2` to remove and reorder tracks in the same remux. You can also select optional metadata actions `1` through `5`, using the same definitions and prompts as Edit. For example, choose Mux actions `1,2`, configure the removal and order, then choose optional metadata `3,4` to set languages and names. The track changes and metadata are passed to `mkvmerge` together in one output remux per file; Mux does not run a later `mkvpropedit` pass.

Successful Mux jobs validate a staged output and replace the selected source. If removal changes the extension, the old source path is removed after the new output is published. Warning, partial or interrupted jobs can retain candidates or leave publication incomplete; the final report identifies the actual state and recovery paths to review before retrying.

Track IDs shown by the utility are the original, zero-based IDs for that source file. For order entries, use the form `0:ID`, separated by commas, such as `0:1,0:0,0:2`. This example places original track 1 first, then track 0, then track 2. Any retained IDs left out of the order are appended. An invalid order, including a removed, unknown or duplicate ID, prompts for the order again without repeating removal selection. Removing every track is rejected before asking for an order.

When reorder is selected, optional track metadata inherits exactly the explicit order IDs, shown above the metadata list. No second track-ID entry is needed. For `0:0,0:4,0:3`, each chosen track metadata action asks for values for original IDs `0`, `4`, then `3`; appended retained tracks keep their original metadata. With removal alone, each optional track metadata action instead asks for its own retained track IDs; removed IDs cannot be targeted.

#### Removal compatibility and skipped files

Before running a removal batch, the utility compares every requested original track ID with the corresponding track in the reference file. The first successfully identified selected file is displayed as that reference. For a file to be eligible, each requested ID must have the same track type and exact native `codec_id`. For example, an `.ass` subtitle track does not match an `.srt` track at the same ID. Differences in track names, languages, or flags do not by themselves make a file incompatible.

An incompatible file is skipped as a whole for that removal run. The report names the file and shows the expected and actual track details. Compatible files can still run. After those eligible jobs finish, the review flow can prepare a fresh Mux batch containing only the unresolved mismatch-skipped files. It re-inspects those sources and asks for a new configuration; completed files are not included again. Back at this post-run menu finalizes the original scope's report and returns to the main categories. Unresolved skips or failed outcomes remain reflected in the invocation's exit status. After explicitly preparing a skipped-only batch, Back keeps that subset selected; it does not restore completed files.

Changing the removal configuration causes the selected sources to be checked again. Explicitly excluded files remain excluded. If no eligible jobs remain, the utility does not run a remux.

#### Output extension

When no tracks are removed, the original extension is kept, including `.mk3d`. When removal changes the retained content, the output extension follows it:

| Remaining content | Output extension |
| --- | --- |
| Video remains | `.mk3d` when the source was `.mk3d`; otherwise `.mkv` |
| Audio remains and no video remains | `.mka` |
| Subtitles remain and no video or audio remains | `.mks` |
| No supported tracks remain | The operation is rejected. |

Mux reports elapsed time and queue progress between files. Its final report includes the Mux action numbers and any optional metadata action numbers.

| To do this | Configure |
| --- | --- |
| Remove tracks | Mux `1`, then enter the original IDs to remove. |
| Reorder tracks | Mux `2`, then enter the desired `0:ID` order. |
| Remove and reorder in one pass | Mux `1,2`. |
| Reorder and update language/name | Mux `2`, then optional metadata `3,4`. |
| Remove, reorder, and update language/name | Mux `1,2`, then optional metadata `3,4`. |

<details>
<summary>Example: remove, reorder, set languages and name tracks in one remux</summary>

Assume the reference listing has video ID `0`, subtitle ID `3`, audio ID `4`, another retained track `11`, and unwanted track `12`.

1. Press `2` at **Category**, then enter Mux actions `1,2`.
2. Select the files once and enter removal ID `12`.
3. Enter reorder sequence `0:0,0:4,0:3`.
4. The metadata menu shows **Original track IDs for each track edit: 0,4,3**. Select metadata actions `3,4` for language and track name.
5. Enter values for each inherited ID:

| Original ID | Language | Track name |
| --- | --- | --- |
| 0 | `eng` | `Main video` |
| 4 | `fr-CA` | `French audio` |
| 3 | `de` | `German subtitles` |

Language prompts run through IDs 0, 4 and 3, followed by name prompts for those same IDs. The utility does not ask for another target list.

Preview shows original ID 12 removed and final order `0,4,3,11`. Track 11 appends without receiving the requested language or name changes. **Run batch** combines removal, reorder and metadata in one output-producing `mkvmerge` command per eligible file.

If you accidentally include `0:12` in the order, the utility rejects that order and asks again. The removal selection and file picker do not repeat. Files whose removal ID/type/codec does not match the reference remain skipped as described above.

</details>

<details>
<summary>Example: change or skip metadata after starting to enter values</summary>

With removal and reorder configured, choose metadata `3,4`. If you decide to change the metadata choices while entering a track name, enter `e` at that value prompt:

```text
Original track ID 4 — Track name: e
```

The optional metadata menu returns. All language and name values from this unfinished attempt are cleared; removal IDs, reorder sequence and selected files remain configured.

- Enter a new selection, such as `1,2`, to collect forced and default values afresh for the inherited reorder IDs.
- Press Enter on a blank metadata selection to proceed without metadata edits.
- Enter `e` at the metadata menu itself to return to Mux actions.

In Edit, `e` at a metadata prompt instead returns to Edit actions with the files still selected. To set an actual name or title of `e`, enter `\e`; uppercase `\E` sets `E`.

</details>

### Extract

| Action | Extract |
| --- | --- |
| 1 | Extract embedded attachments into a shared `Attachments/` folder beside the selected source files. |
| 2 | Extract selected original track IDs beside each source file. |

Choose `1,2` to collect attachments and selected tracks in the same batch. Attachments keep their embedded filenames and extensions. If a regular file with the same name already exists, or another selected source publishes that name, the later successful publication overwrites it. The processing order is selected source order, then attachment order within each source. This supports collecting a shared attachment set, such as fonts, from many files.

Track outputs use the source stem and original track ID, for example `Episode - Track [2].srt`. Track outputs are not overwritten. Formats with companion artifacts are handled as a group: VobSub requires both `.sub` and `.idx`; WavPack may also produce an optional `.wvc` correction file.

The utility checks planned destinations before Run. It rejects unsafe attachment names, destinations that alias selected media, unsafe existing destination types, and track/companion filename collisions. Extraction stages outputs before publication. If an extraction or publication has a warning or partial result, the final report distinguishes what was processed, published, superseded, uncertain, or left staged; inspect any reported retained staging directory before removing it.

Extract reports between-file progress. For attachments-only or tracks-only batches, that timing covers the selected stage. For a combined batch, the between-file timing and ETA cover the track-extraction stage; the final report covers the complete job. If a combined job never attempts a track stage, the report says so and does not invent a track ETA.

The attachment collection folder is shared for the whole selected batch. It is not split into per-source subfolders, and same-name regular files are intentionally replaced in the order described above. Use the final report's attachment publication records to see which source supplied the final collected name and whether an earlier publication was superseded or left uncertain.

<details>
<summary>Example: collect episode fonts and extract subtitle tracks together</summary>

1. Press `3` at **Category**, then enter Extract actions `1,2`.
2. Mark the episodes in the picker and confirm.
3. Enter subtitle IDs, such as `3-7`, after checking the displayed listing.
4. Preview the attachment collection and track outputs, then choose **Run batch**.

Attachments from all selected sources collect into one `Attachments/` folder. A later successful `Font.ttf` publication replaces an earlier regular file of that name. Subtitle tracks are written beside each source with its stem and original ID, such as `Episode01 - Track [3].ass`; those track outputs retain collision protection.

For this combined job, between-file timing covers track extraction. The final report covers the complete attachment-and-track batch.

</details>

## Mapping the old menu to the new categories

The former individual actions map to the grouped menus as follows:

| Former choice | New menu |
| --- | --- |
| 1 forced flag | Edit `1` |
| 2 default flag | Edit `2` |
| 3 language | Edit `3` |
| 4 name | Edit `4` |
| 5 title | Edit `5` |
| 6 extract attachments | Extract `1` |
| 7 remove tracks | Mux `1` |
| 8 reorder tracks | Mux `2` |
| 9 extract tracks | Extract `2` |

Common multi-pass work can now be configured as one batch:

| Previous passes | New configuration |
| --- | --- |
| Choices `1` and `2` | Edit actions `1,2` |
| Choices `8`, `4`, and `3` | Mux action `2` plus optional metadata `4,3` |
| Choices `7`, `8`, `4`, and `3` | Mux actions `1,2` plus optional metadata `4,3` |

These are migration examples; choose any supported combination that fits the current job.

## Reports and outcomes

The final report shows the input directory basename, category and action numbers, configuration history, and counts for completed, failed, warning, partial, skipped, excluded, not-attempted, and interrupted files. It records unresolved and resolved removal-skip history, including expected and actual track details. Each original selected file contributes once to the final counts, including when a skipped-only continuation changes its outcome. Paths in per-file records identify the affected source and outputs.

Edit reports appear at the end and do not include a between-file ETA. Mux includes per-file progress and elapsed time. Extract includes per-file progress with the timing behavior described above. A report may include staged paths, native scratch paths, cleanup failures, or uncertain publication details when recovery needs attention. These records distinguish source preservation and output publication state; they do not promise an automatic rollback of already-published extraction artifacts.

Warnings, failed or partial jobs, unresolved removal skips, and interrupted batches produce a nonzero final exit status. Review the reported files and paths before repeating an operation, especially when the output state is uncertain.

## Testing

The repository tests use copied fixtures and controlled tool commands so they can exercise the interactive entry point without modifying user media. Run the affected Matroska test group from the repository root with the existing virtual environment:

```zsh
.venv/bin/python -B -m pytest --disable-plugin-autoload tests/mkv_tools
```

To run only the `mkv_utils` test module:

```zsh
.venv/bin/python -B -m pytest --disable-plugin-autoload tests/mkv_tools/test_mkv_utils.py
```

The fake media commands in the test harness record arguments and isolate the menu tests from user files. The original rework campaign established 128-case coverage: 125 unchanged full-suite cases passed, and 3 corrected cases passed in a separate run. It also included three real-tool menu journeys—Edit title clearing across all four extensions, combined Mux operations with all five optional metadata edits, and combined attachment/track extraction—and one real-fzf terminal journey that selected two files, previewed, and cancelled without Run. These historical results come from separate runs; there was no single 128-case all-pass invocation. Real-tool evidence used installed MKVToolNix v93 with small disposable fixtures. The later Back-navigation change was checked separately with focused state/regression tests and three small mocked entrypoint probes, including blocked-input interruption. The owned-menu follow-up was checked separately using an active-screen ANSI model on a real controlling terminal, with mocked media tools, plus focused pipe regressions. These checks cover menu replacement, normal-history preservation, acknowledgement boundaries and keyboard interruption. The processing engines were unchanged. No full native codec matrix or CI result is implied.

The tests cover the action registry and prompts, batching, removal eligibility and skip-only continuation, track order, destination validation, output extensions, publication outcomes, and final reporting. The real-tool journeys check observed media properties and source preservation for their specific scenarios; they do not represent every possible codec and metadata combination.

The shared-ID and metadata-Back follow-up passed 47 affected checks and two controlling-terminal journeys. A strengthened two-file Mux argument check passed separately after adding explicit per-ID flag assertions. These checks drive the current script with isolated fake media tools; they cover shared targets, inherited reorder IDs, invalid-order retry, metadata reset, source-specific arguments and terminal restoration. They reuse the unchanged processing engines' earlier native evidence and do not claim a new native or full-suite campaign.

The script and tests use the repository's installed tools and environment. To inspect tool resolution without changing anything:

```zsh
command -v mkvmerge mkvextract mkvpropedit jq fzf
mkvmerge --version
.venv/bin/python -c 'import pymkv; from importlib.metadata import version; print(version("pymkv2"))'
```

### Maintaining metadata actions

Metadata choices are declared once through `_mkvutil_metadata_define` in the script. The shared record supplies the menu, scope, prompt, default, validation, `mkvpropedit` property, corresponding `mkvmerge` option, and observed JSON fields. Both argument builders consume those records. When adding an action, provide both tool mappings in that record and extend the parity checks for its actual behavior; the Edit and optional Mux menus then use the same definition.

## Troubleshooting

| Message or symptom | What to check |
| --- | --- |
| No Matroska files were found | Confirm the directory contains top-level `.mkv`, `.mka`, `.mks`, or `.mk3d` files. The scan is not recursive. |
| No file selected | Mark at least one entry in the `fzf` picker and confirm. |
| The Python runtime reports missing `pymkv` or `pymkv2` | Confirm the repository `.venv` points to a working interpreter and has the packages from `requirements.txt`. |
| A file is skipped for a removal mismatch | Compare the requested original track ID, type, and exact codec shown against the reference. Use the skipped-subset flow to configure those unresolved files separately. |
| An output destination already exists | Review the planned path. Track outputs are not overwritten; attachment extraction may overwrite an existing regular same-name file. |
| An interrupted or partial extraction reports retained staging paths | Review the final report and those paths before retrying or cleaning them up. |
