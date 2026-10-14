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

The script uses the installed `mkvmerge`, `mkvextract`, `mkvpropedit`, `jq`, `fzf`, and Python 3. Track extraction also needs the `pymkv` module and `pymkv2` distribution. When the repository `.venv` exists, the script uses its Python interpreter, including when `.venv` is a symlink.

This utility is maintained for the installed MKVToolNix **v93.0 (Goblu), 64-bit** on macOS Big Sur. The rework was verified against that installed version; upgrading MKVToolNix is not required.

For a fresh checkout that does not yet have the Python packages, create the repository environment and install the repository requirements:

```zsh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If your existing repository environment already has its dependencies, keep using it. No per-user global Python install is needed when the repository `.venv` is available.

## Choose a category and batch its actions

The main menu keeps the work areas separate:

| Main menu | Actions | What it does |
| --- | --- | --- |
| **1. Matroska Edit** | 1 forced flag, 2 default flag, 3 language, 4 name, 5 title | Applies metadata edits with `mkvpropedit`. |
| **2. Matroska Mux** | 1 remove tracks, 2 reorder tracks | Remuxes each eligible file once; optional metadata can be included in that remux. |
| **3. Matroska Extract** | 1 attachments, 2 selected tracks | Extracts attachments, tracks, or both from each selected source. |
| **0. Exit** | — | Leaves without starting an operation. |

Within a category, enter one action, a comma-separated list, or an ascending range. For example, `1`, `1,2`, or `1-3`. The same format is used for optional Mux metadata choices. The file picker is always multi-select: select one file or mark several with Tab, then confirm the selection.

After choosing files, configure all selected operations. The review menu lets you change the configuration, preview planned changes and outputs, run the batch, or cancel. Media-changing commands start only after you choose **Run**. A preview is a review step; it does not perform the operation.

### Edit

| Action | Edit |
| --- | --- |
| 1 | Set `flag-forced` for selected tracks. Default value: `0`. |
| 2 | Set `flag-default` for selected tracks. Default value: `1`. |
| 3 | Set a language value for selected tracks. |
| 4 | Set a track name. |
| 5 | Set the container title. Leave the title blank to clear it. |

For example, choose category `1`, actions `3,4`, select one or more files, then enter the language and name settings when prompted. Edit changes the selected files in place. Multiple metadata changes for one file are grouped into a single `mkvpropedit` invocation.

Edit is metadata-only: it does not print a between-file elapsed-time/ETA block. Its final report records the selected actions, files and outcomes.

| To do this | Configure |
| --- | --- |
| Change both track flags | Edit `1,2` |
| Set language and track name | Edit `3,4` |
| Set a title or clear it | Edit `5`; enter a title, or leave the title prompt blank |

### Mux

| Action | Mux operation |
| --- | --- |
| 1 | Remove selected original track IDs. |
| 2 | Reorder tracks using the original track IDs. Omitted retained tracks are appended in their existing order. |

You can choose `1,2` to remove and reorder tracks in the same remux. You can also select optional metadata actions `1` through `5`, using the same definitions and prompts as Edit. For example, choose Mux actions `1,2`, configure the removal and order, then choose optional metadata `3,4` to set languages and names. The track changes and metadata are passed to `mkvmerge` together in one output remux per file; Mux does not run a later `mkvpropedit` pass.

Successful Mux jobs validate a staged output and replace the selected source. If removal changes the extension, the old source path is removed after the new output is published. Warning, partial or interrupted jobs can retain candidates or leave publication incomplete; the final report identifies the actual state and recovery paths to review before retrying.

Track IDs shown by the utility are the original, zero-based IDs for that source file. For order entries, use the form `0:ID`, separated by commas, such as `0:1,0:0,0:2`. This example places original track 1 first, then track 0, then track 2. Any retained IDs left out of the order are appended.

#### Removal compatibility and skipped files

Before running a removal batch, the utility compares every requested original track ID with the corresponding track in the reference file. The first successfully identified selected file is displayed as that reference. For a file to be eligible, each requested ID must have the same track type and exact native `codec_id`. For example, an `.ass` subtitle track does not match an `.srt` track at the same ID. Differences in track names, languages, or flags do not by themselves make a file incompatible.

An incompatible file is skipped as a whole for that removal run. The report names the file and shows the expected and actual track details. Compatible files can still run. After those eligible jobs finish, the review flow can prepare a fresh Mux batch containing only the unresolved mismatch-skipped files. It re-inspects those sources and asks for a new configuration; completed files are not included again. You can finish with the skip recorded instead.

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

The fake media commands in the test harness record arguments and isolate the menu tests from user files. The current rework evidence is 128-case coverage: 125 unchanged full-suite cases passed, and 3 corrected cases passed in a separate run. It also includes three real-tool menu journeys—Edit title clearing across all four extensions, combined Mux operations with all five optional metadata edits, and combined attachment/track extraction—and one real-fzf terminal journey that selected two files, previewed, and cancelled without Run. These results come from separate runs; there was no single 128-case all-pass invocation. Real-tool evidence used installed MKVToolNix v93 with small disposable fixtures. No full native codec matrix or CI result is implied.

The tests cover the action registry and prompts, batching, removal eligibility and skip-only continuation, track order, destination validation, output extensions, publication outcomes, and final reporting. The real-tool journeys check observed media properties and source preservation for their specific scenarios; they do not represent every possible codec and metadata combination.

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
