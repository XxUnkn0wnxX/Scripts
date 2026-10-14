# `mkv_utils.zsh`

[← Back to the toolkit](../README.md)

`mkv_utils.zsh` is an interactive Matroska utility for analyzing track layouts, editing metadata, remuxing tracks, and extracting attachments or tracks. It handles `.mkv`, `.mka`, `.mks`, and `.mk3d` files and lets you combine compatible actions into one batch.

Choose a category for the job:

| If you want to… | Choose |
| --- | --- |
| Change flags, language, track names, or the container title | **1. Matroska Edit** |
| Remove tracks, set track order, or combine either with metadata | **2. Matroska Mux** |
| Collect attachments, extract selected tracks, or do both | **3. Matroska Extract** |
| Compare selected files' track IDs, types, and codecs | **4. Matroska Analyze** |

The utility asks for the settings required by the selected actions, performs its complete preflight after the last required answer, and then starts eligible files automatically. There is no separate review, preview, or run menu. A dry run is available when you want the normal inspection and planning flow without media writes.

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

The command shape is `mkvutil [--dry-run] [--bypass] [dir]`; both options are optional and have category-specific effects described below.

To inspect real files and rehearse a configured batch without changing them, add `--dry-run`:

```zsh
mkvutil --dry-run "/Volumes/Media/My Show"
```

Configuration and planning still inspect the selected files and enforce the usual track and destination checks. When the queue starts, the utility simulates the jobs and marks its headings **(DRYRUN)**. It shows simulated counts and intended output names, without editing media, remuxing, extracting, creating output directories or publishing files. The simulation checks the current plan and source identity; it does not establish that a native write or output validation would succeed. Analyze remains its normal read-only operation.

<details>
<summary>Example: rehearse removal, reorder and metadata</summary>

This illustrative, abbreviated transcript summarizes a dry-run after configuring a Mux that removes track `12`, reorders to `4,3`, and sets language for the resolved IDs `0,4,3`. Prompt and report wording is shortened for clarity:

```text
Track IDs to remove: 12
Track order: 4,3
Resolved track IDs for metadata: 0,4,3
Language for original track ID 0: eng
Language for original track ID 4: fr-CA
Language for original track ID 3: de

Mux (DRYRUN) 1,2: remove + reorder; metadata 3
Processing: Episode 01.mkv

+----------------------------------------------+
| Final report (DRYRUN)                        |
+----------------------------------------------+
Directory: My Show
Complete batch elapsed: 0h 0m 0s

+----------------------------------------------+
| Simulated                                    |
+----------------------------------------------+
| Simulated: Episode 01.mkv                    |
|   Would write: Episode 01.mkv                |
| Files were not changed.                      |
+----------------------------------------------+
```

The report's detailed rows are grouped under **Simulated** and describe intended names; they do not claim native success. The selected media and directory contents remain unchanged. For an actual run, invoke the utility again without `--dry-run` and configure the desired batch.

</details>

The built-in help is available with:

```zsh
zsh shell/mkv_utils.zsh --help
```

For a Mux removal run, `--bypass` can skip the total-track-count guard. Put it before or after the optional directory:

```zsh
zsh shell/mkv_utils.zsh --bypass "/Volumes/Media/My Show"
zsh shell/mkv_utils.zsh "/Volumes/Media/My Show" --bypass
```

The bypass is off by default and applies only to Mux removal in that invocation. Its exact scope is described under [Mux](#mux).

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

At the main **Category:** selector, type `1`, `2`, `3`, or `4`, then press Enter. The main menu, submenu batches and text fields all use Enter to confirm input, with the normal terminal cursor visible. Hidden `e`/`E` plus Enter exits the main menu; submenu `e`/`E` plus Enter goes Back.

When standard input, output and error all use a terminal and `TERM` is set to a value other than `dumb`, navigation uses a transient alternate screen. Adjacent navigation menus share this screen. Each complete menu body is prepared first and printed together over the previous view, erasing old line endings and unused rows. Navigation redraws add no animation or intentional wait. The category and working directory stay visible, followed by the native input prompt; the owned menu avoids printing a duplicate initial working-directory line. Invalid menu input shows a validation message in the same screen and waits for another choice. The file picker takes over the same screen and uses nearly its full height, avoiding a return to the old terminal view between the menu and fzf. The utility restores normal history after selection or cancellation, before configuration fields, processing, reports or fatal diagnostics. It never clears the normal screen or scrollback.

Removal-mismatch details and reports remain in normal terminal history. Redirected streams and empty or `dumb` terminal settings disable owned navigation views. Piped input retains the line-based protocol.

| Main menu | Actions | What it does |
| --- | --- | --- |
| **1. Matroska Edit** | 1 forced flag, 2 default flag, 3 language, 4 name, 5 title | Applies metadata edits with `mkvpropedit`. |
| **2. Matroska Mux** | 1 remove tracks, 2 reorder tracks | Remuxes each eligible file once; optional metadata can be included in that remux. |
| **3. Matroska Extract** | 1 attachments, 2 selected tracks | Extracts attachments, tracks, or both from each selected source. |
| **4. Matroska Analyze** | Select files | Lists tracks and compares each file's original track ID, type, and codec with a reference file. |

Within a category, enter one action, a comma-separated list, or an ascending range. For example, `1`, `1,2`, or `1-3`. The same format is used for optional Mux metadata choices. The file picker displays and searches filenames within the chosen directory, hiding the parent path. It is always multi-select: select one file or mark several with Tab, then confirm the selection.

Every prompt validates its own input before continuing. Unknown menu choices, malformed lists, descending ranges, unavailable track IDs, invalid reorder entries, invalid flags or language syntax, and unknown Y/N answers show an error and repeat that prompt. Valid earlier settings remain in place. Removal must leave at least one track; reorder cannot include removed tracks. Only exact `e`/`E` navigates Back or exits before processing. `0` and `cancel` are not navigation shortcuts; `0` remains a valid track ID or flag value where requested. Blank input uses a displayed default, clears a text field, or skips optional Mux metadata where applicable.

<details>
<summary>Valid combinations and rejected input</summary>

| Prompt | Valid input | Meaning or validation |
| --- | --- | --- |
| Edit actions | `3` | Select language editing. |
| Edit actions or optional Mux metadata | `1-4,2` | Select `1,2,3,4` once each. |
| Track IDs | `1,3,4-6` | Select `1,3,4,5,6`, provided every ID exists. |
| Mux or Extract actions | `1,2` or `1-2` | Combine the two available actions; `3` is invalid here. |
| Reorder | `0,4,1` | Put these retained tracks first in that order; unlisted retained tracks follow. |

Whitespace around separators is accepted, such as `1 - 4, 2` for action/track-ID ranges or `0, 4, 3` for reorder. Reorder uses bare comma lists and requires at least two different explicitly entered IDs; it accepts neither ranges nor `0:` prefixes. Whitespace inside a number is rejected: `1 2` never becomes ID `12`. Empty comma items (`1,,2`, `1,`), malformed ranges (`1--3`), unavailable IDs and repeated reorder IDs are rejected. An invalid attempt does not start the batch.

Names and titles are text, so words, numbers, commas and hyphens are literal values there. Flags accept only `0` or `1`; languages use the supported language-tag syntax, such as `eng` or `fr-CA`. The main category selector accepts one number followed by Enter, rather than a batch list.

</details>

After choosing files, enter the requested settings. When the last required setting is complete, the utility runs its full preflight and automatically processes eligible jobs, then prints the final report and exits. Edit starts after its last per-ID value or title; Mux starts after its last selected metadata value, or after a blank optional-metadata choice; Extract with track actions starts after the track IDs, while attachments-only starts after file selection. A preflight with no eligible jobs prints the report and exits without writing outputs.

Before a real file is written, preflight checks each requested original track ID against the expected track type for that action. If an ID is missing or has the wrong type in a selected file, that whole file is skipped; other eligible files can continue. Mux removal adds its codec and total-track-count checks below. Immediately before each real file, the utility also checks that the source still matches the inspected snapshot. A source changed during configuration or while waiting in the queue is omitted with the report reason **Source changed after inspection/planning; file was not processed**. These checks prevent a shifted or changed track layout from receiving edits or outputs intended for the earlier inspection.

Track configuration shows its full working directory and reference filename in a shared ASCII header box before the track listing. A Mux removal header keeps the **Removal reference file** label and shows the bypass cue when that guard is disabled.

While configuration is incomplete, prompts that support Back accept exact `e` or `E`. Except for optional Mux metadata fields, Back from a field returns to the category's action list and clears the selected files, inspected sources, explicit exclusions, unexecuted ledger, and pending configuration. Choose actions again to rescan the directory and open a fresh picker. Back from the action list returns to the main categories. Once processing starts, `e` is not a cancellation key.

At any metadata track-ID or value prompt, exact `e` or `E` discards all partially entered metadata. In Edit, it returns to the action list and clears the selection, so choosing actions again opens a fresh picker. In Mux optional metadata fields, it returns to the metadata list while retaining the selected files, removal IDs, and reorder settings; choose metadata again or leave the list blank to skip it. **e) Back to main categories** in the optional metadata list clears the whole unexecuted selection and configuration.

The **Working** indicator appears during quiet scans, source inspection, layout and signature preparation, language validation and queue planning before processing starts, when standard output is a terminal and `TERM` is nonempty and not `dumb`. It stays visible across consecutive preparation steps and pauses before diagnostics or prompts. The typing cursor is hidden while the indicator runs and restored before the next input or output. Once the queue starts, Working stays off, including during each file's fresh source check; action headings, native messages and progress reports show the ongoing work. Redirected output has no indicator. Analyze uses **Analysing** during its track analysis.

To enter a literal name or title of `e` or `E`, use `\e` or `\E`. Only those exact text escapes are decoded; other text, including whitespace, backslashes and `cancel`, is preserved. Inspection or planning errors offer a Y/N/`e` exclusion prompt: `Y`/`YES` excludes the file, `N`/`NO` or blank declines, and `e`/`E` goes Back. Other answers are rejected. An explicit exclusion applies to the current selection. Public Back clears that selection and its exclusions, so a fresh picker can select the file again.

EOF or Ctrl+C before configuration is complete cancels the invocation. After configuration completes, Ctrl+C requests the category's stop behavior described below. In the file picker, `e` remains a search character under fzf's own controls. Processing ends with the final report and exit.

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

For two selected files, enter the IDs once. This illustrative transcript shows how each action collects one value per original ID and reuses those answers across both files; prompt labels are shortened:

```text
Edit actions: 1,2
Original track IDs: 4,3
Forced flag for ID 4: 0
Forced flag for ID 3: 1
Default flag for ID 4: 1
Default flag for ID 3: 0

All required values entered; preflight starts automatically.
Each eligible file receives both edits in one grouped metadata operation.
```

The second action does not ask for IDs again. After the last value, preflight runs and the batch starts automatically.

</details>

### Mux

| Action | Mux operation |
| --- | --- |
| 1 | Remove selected original track IDs. |
| 2 | Reorder tracks using the original track IDs. Omitted retained tracks are appended in their existing order. |

You can choose `1,2` to remove and reorder tracks in the same remux. You can also select optional metadata actions `1` through `5`, using the same definitions and prompts as Edit. For example, choose Mux actions `1,2`, configure the removal and order, then choose optional metadata `3,4` to set languages and names. The track changes and metadata are passed to `mkvmerge` together in one output remux per file; Mux does not run a later `mkvpropedit` pass.

Successful Mux jobs validate a staged output and replace the selected source. If removal changes the extension, the old source path is removed after the new output is published. Warning, partial or interrupted jobs can retain candidates or leave publication incomplete; the final report identifies the actual state and recovery filenames to review before retrying.

Track IDs shown by the utility are the original, zero-based IDs for that source file. Enter reorder IDs as a bare comma list, such as `1,0,2`: first track 1, then track 0, then track 2. At least two different IDs must be entered; `7` alone is invalid. If retained track 0 is omitted, it is prepended automatically: `4,3` becomes `0,4,3`. Explicit track 0 keeps its entered position; absent or removed track 0 is never added. Other retained IDs follow the listed tracks. The utility converts this to native `0:ID` syntax internally. Invalid, removed, unknown or duplicate IDs re-prompt without repeating removal selection. Removing every track is rejected before asking for an order; fewer than two retained tracks cannot be reordered and returns to the action list.

When reorder is selected, optional track metadata inherits the resolved listed IDs, including automatically prepended track 0, shown above the metadata list. No second track-ID entry is needed. For `0,4,3` or `4,3` with retained 0, each chosen track metadata action asks for values for original IDs `0`, `4`, then `3`; other appended tracks keep their original metadata. With removal alone, each optional track metadata action instead asks for its own retained track IDs; removed IDs cannot be targeted.

#### Removal compatibility and skipped files

During preflight, the utility compares every requested original track ID with the corresponding track in the reference file. The first successfully identified selected file is displayed as that reference. For a file to be eligible, each requested ID must have the same track type and exact native `codec_id`. For example, an `.ass` subtitle track does not match an `.srt` track at the same ID. Differences in track names, languages, or flags do not by themselves make a file incompatible.

An incompatible file is skipped as a whole for that removal run. The report names the file and shows the expected and actual track details. Compatible files can still run. After processing, the final report ends the invocation; unresolved skips or failed outcomes produce a nonzero exit status. To retry skipped files, start `mkvutil` again, select only those files, and configure a new batch.

For removal, preflight also requires each selected file to have the same total number of original tracks as the reference. This guard catches unexpected layout differences beyond the requested IDs. `--bypass` skips only this total-track-count comparison; selected-ID presence, track type, exact native codec ID, source identity, configuration, collision, layout, and publication checks remain active. The flag is stored in that invocation's Mux configuration, defaults to off for each new invocation, and does not affect Analyze. The removal reference display shows a visible cue when it is enabled. This is currently the only bypassable guard; additional guards may become bypassable in the future.

<details>
<summary>Example: bypass only the total-track-count guard</summary>

```zsh
zsh shell/mkv_utils.zsh --bypass "/Volumes/Media/My Show"
```

Choose **2. Matroska Mux**, select removal, and enter the original IDs to remove. The reference display includes `Bypass enabled: removal track-count guard only.` Files may then have a different total number of tracks, but every requested original ID must still exist with the same type and exact native `codec_id` as in the reference. Any file that fails those per-ID checks is skipped as a whole; compatible files can continue.

</details>

If preflight leaves no eligible jobs, the utility prints the final report and exits without running a remux or writing outputs. To retry skipped files, start a new invocation and explicitly select them; their settings are collected afresh.

<details>
<summary>Example: mixed track-count, track-type, and changed-source outcomes</summary>

Suppose Episode01 is the reference and has five tracks. A removal batch targets original ID `4`. Episode02 has an extra track, Episode03 lacks ID `4`, Episode04 has an audio track where the reference has subtitles, and Episode05 is overwritten while settings are being entered. Episode01 can process; the other four are omitted.

A shortened, illustrative excerpt of the separate final **Skipped** block looks like this. The full report also includes reference/history fields and the expected and actual type/codec values:

```text
+----------------------------------------------------------------------+
| Skipped                                                              |
+----------------------------------------------------------------------+
| skipped: Episode02.mkv                                               |
|     Track count mismatch: expected 5; actual 6                       |
| skipped: Episode03.mkv                                               |
|     Original ID 4: missing-id                                        |
| skipped: Episode04.mkv                                               |
|     Original ID 4: type-and-codec-mismatch                           |
| skipped: Episode05.mkv                                               |
|     Source changed after inspection/planning; file was not processed |
+----------------------------------------------------------------------+
```

The source-change reason covers the file that was replaced before the final answer or while queued. The utility retains the initial inspection snapshot and checks again before processing each file. To retry omitted files, start a new invocation and select only those reported names; their settings and reference are collected afresh.

</details>

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
| Reorder tracks | Mux `2`, then enter at least two distinct bare IDs in the desired order. |
| Remove and reorder in one pass | Mux `1,2`. |
| Reorder and update language/name | Mux `2`, then optional metadata `3,4`. |
| Remove, reorder, and update language/name | Mux `1,2`, then optional metadata `3,4`. |

<details>
<summary>Example: remove, reorder, set languages and name tracks in one remux</summary>

Assume the reference listing has video ID `0`, subtitle ID `3`, audio ID `4`, another retained track `11`, and unwanted track `12`.

1. Press `2` at **Category**, then enter Mux actions `1,2`.
2. Select the files once and enter removal ID `12`.
3. Enter reorder sequence `0,4,3`, or `4,3` to prepend retained 0 automatically.
4. The metadata menu shows **Original track IDs for each track edit: 0,4,3**. Select metadata actions `3,4` for language and track name.
5. Enter values for each inherited ID:

| Original ID | Language | Track name |
| --- | --- | --- |
| 0 | `eng` | `Main video` |
| 4 | `fr-CA` | `French audio` |
| 3 | `de` | `German subtitles` |

Language prompts run through IDs 0, 4 and 3, followed by name prompts for those same IDs. The utility does not ask for another target list.

After entering the last track-name value, preflight runs and the batch starts automatically. Original ID 12 is removed and the resulting order is `0,4,3,11`; track 11 appends without receiving the requested language or name changes. Removal, reorder and metadata use one output-producing `mkvmerge` command per eligible file.

If you accidentally include removed ID `12`, a duplicate such as `4,3,1,1`, a single ID, or old `0:` syntax, the utility rejects that order and asks again. The removal selection and file picker do not repeat. Files whose removal ID/type/codec does not match the reference remain skipped as described above.

For example, the order prompt retries in place after a removed ID is entered. The lines below summarize the interaction rather than reproduce a captured terminal session; prompt and validation wording is illustrative:

```text
Track IDs to remove: 12
Track order: 12,4,3
  Rejected: 12 is being removed.
Track order: 4,3
Resolved order: 0,4,3
Metadata actions: 3,4
Language for ID 0: eng
Language for ID 4: fr-CA
Language for ID 3: de
Track name for ID 0: Main video
Track name for ID 4: French audio
Track name for ID 3: German subtitles
```

Here track 0 is retained and prepended because it was omitted. The metadata prompts follow the resolved IDs; the removed ID cannot be included in reorder or metadata.

</details>

<details>
<summary>Example: change optional metadata or reset a selection with Back</summary>

With removal and reorder configured, choose metadata `3,4`. If you decide to change the metadata choices while entering a track name, enter `e` at that value prompt:

```text
Original track ID 4 — Track name: e
```

The optional metadata menu returns. All language and name values from this unfinished attempt are cleared; removal IDs, reorder sequence and selected files remain configured.

- Enter a new selection, such as `1,2`, to collect forced and default values afresh for the inherited reorder IDs.
- Press Enter on a blank metadata selection to start preflight without metadata edits.
- Enter `e` at the metadata menu itself to return directly to the main categories.

For a fresh selection, choose Mux actions `1,2`, select files, then enter `e` at the removal-ID or track-order prompt. The utility returns to Mux actions and clears that selection and its settings. Enter `1,2` again: fzf opens again, allowing you to choose a different set of files.

Edit metadata Back and Extract track-ID Back follow the same reset rule: return to their action list, clear the unexecuted selection, and reopen fzf after new actions are chosen. Back from the optional Mux metadata list itself returns to the main categories and clears the entire pending Mux configuration.

To set an actual name or title of `e`, enter `\e`; uppercase `\E` sets `E`. After processing starts, `e` is ordinary typeahead; use Ctrl+C for the runtime stop behavior below.

</details>

### Extract

| Action | Extract |
| --- | --- |
| 1 | Extract embedded attachments into a shared `Attachments/` folder beside the selected source files. |
| 2 | Extract selected original track IDs beside each source file. |

Choose `1,2` to collect attachments and selected tracks in the same batch. Attachments keep their embedded filenames and extensions. If a regular file with the same name already exists, or another selected source publishes that name, the later successful publication overwrites it. The processing order is selected source order, then attachment order within each source. This supports collecting a shared attachment set, such as fonts, from many files.

Track outputs use the source stem and original track ID, for example `Episode - Track [2].srt`. Track outputs are not overwritten. Formats with companion artifacts are handled as a group: VobSub requires both `.sub` and `.idx`; WavPack may also produce an optional `.wvc` correction file.

The utility checks planned destinations during preflight. It rejects unsafe attachment names, destinations that alias selected media, unsafe existing destination types, and track/companion filename collisions. Extraction stages outputs before publication. If an extraction or publication has a warning or partial result, the final report distinguishes what was processed, published, superseded, uncertain, or left staged; inspect any reported retained staging directory before removing it.

Extract reports between-file progress. For attachments-only or tracks-only batches, that timing covers the selected stage. For a combined batch, the between-file timing and ETA cover the track-extraction stage; the final report covers the complete job. If a combined job never attempts a track stage, the report says so and does not invent a track ETA.

The attachment collection folder is shared for the whole selected batch. It is not split into per-source subfolders, and same-name regular files are intentionally replaced in the order described above. Use the final report's attachment publication records to see which source supplied the final collected name and whether an earlier publication was superseded or left uncertain.

<details>
<summary>Example: collect attachments, extract tracks, or do both</summary>

```text
Extract actions: 1
Files selected: Episode01.mkv, Episode02.mkv
All attachments selected automatically; no attachment-ID prompt.
Preflight starts automatically.

Extract actions: 2
Files selected: Episode01.mkv
Track IDs: 44
  Rejected: the reference only has IDs 0,1,2,3.
Track IDs: 3
Preflight starts automatically for track ID 3.

Extract actions: 1,2
Files selected: Episode01.mkv, Episode02.mkv
Track IDs: 3-7
Attachments and tracks run as one batch.
```

This is an illustrative flow; prompt and validation wording is shortened, not copied from a captured session. In a combined job, attachments from all sources collect into one shared `Attachments/` folder, where a later successful same-name regular file replaces the earlier one. Track outputs use the source stem and original ID, such as `Episode01 - Track [3].ass`, and retain collision protection. The final report lists published track filenames. For combined extraction, between-file timing covers the track stage; the final report covers the complete job.

If a requested track ID exists in some selected files but not others, preflight skips each file that cannot satisfy the whole requested track set; eligible files can continue.

</details>

### Analyze

Choose **4. Matroska Analyze**, then select files in the same multi-select picker used by the other categories. The first selected file with a usable complete original-ID/type/native-codec map becomes the reference. The utility buffers its track listing and silently compares every selected file with that complete map. It displays the one reference listing when analysis finishes. The reference is counted as matching. Track names, languages, flags, and listing order do not affect the comparison.

Analyze ends after its report. It does not ask for actions or settings, create a processing queue, or write media. Of the selected files, only the reference filename and its track listing are shown before the final report; mismatch and inspection-failure filenames appear in the final report. The report also shows the full `Current Work Dir`, matching and mismatched counts, and files not started after an interruption. A mismatch, failed inspection, or interruption returns a nonzero status.

During the scan, a ten-frame **Analysing** spinner appears only when standard output is a terminal and `TERM` is set to a nonempty, non-`dumb` value. It stops before the results are displayed; redirected output has no spinner. After the complete scan, Analyze shows a boxed header with the full working directory and reference filename, a blank spacer, the single reference listing, and a boxed **Final report** heading. If no usable reference exists, it omits the listing and reports the failure.

<details>
<summary>Example: compare a selected batch with its first usable reference</summary>

1. Choose `4` at **Category**.
2. Mark the files in the picker and confirm.
3. Review the single displayed listing. The first file with a usable track signature becomes the reference; remaining selected files are inspected without intermediate output.
4. Check the final counts and any listed mismatched, failed, or not-started filenames. To compare mismatches separately, start a new invocation and select only the reported mismatched files.

For example, tracks with the same IDs, types, and native codec IDs match even if their names or language flags differ. A different codec at original ID `3`, or an additional original track ID, makes that file a mismatch.

This illustrative excerpt shows the reference listing first and a mismatched filename in the final report; counts and directory details vary by selection:

```text
Analysis reference file: Episode 01.mkv

-----------------------  mkvmerge JSON track listing -----------------------
Track ID 0: video (V_MPEG4/ISO/AVC)

Final report
Analyzed: 3; Matching: 2; Mismatched: 1; Failed: 0; Not attempted: 0
Track ID/type/codec mismatch: Episode 03.mkv
```

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

The processing report starts with a shared ASCII heading box, then shows the input directory basename, category and action numbers, configuration history, and counts for completed, failed, warning, partial, skipped, excluded, not-attempted, and interrupted files. Configuration outcome counts use readable labels, such as `Done: 3; Failed: 1`; an empty outcome set is shown as `none`. After **Complete batch elapsed**, meaningful per-file details appear in separately labelled ASCII blocks: **Simulated**, **Outputs**, **Errors**, **Warnings**, **Partial results**, **Skipped**, **Excluded**, **Interrupted**, **Not attempted**, **Completed** (for retained history), and **Attachments**, as applicable. Empty groups are omitted. Per-file records retain the exact filenames for skipped and failed jobs. Removal-skip history includes the expected and actual original track ID, type, codec and total-track-count details. Each original selected file contributes once to the final counts. Displayed source, destination, stage, and recovery-file references use filenames; the full path is shown for the working directory in `Current Work Dir` and the owned navigation menu's `Directory` line. A processed queue always ends here; starting another batch requires a new invocation.

Edit, Mux and Extract show a short action heading and `Processing: filename.ext` before each job, followed by the native tool's live messages indented two spaces. For example, a combined Mux heading is `Mux 1,2: remove + reorder; metadata 1,3`. Native messages show source filenames and logical output filenames, with their parent paths hidden. Identification JSON and tag-inspection payloads stay hidden. Edit prints timing only in its final report; Mux and Extract follow each file's messages with elapsed-time, file-count and ETA summaries in a **File progress** ASCII box that names that source. Final reports count routine successful edits and same-name remuxes without repeating each success or internal phase/state. Renamed outputs, extracted track filenames, skips, failures, interruptions and useful recovery information remain visible.

<details>
<summary>Example: utility headings and native messages</summary>

```text
Mux 2: reorder
Processing: Episode01.mkv
  mkvmerge v93.0 ('Goblu') 64-bit
  The file 'Episode01.mkv' has been opened for writing.
  Multiplexing took 1 second.
```

Native messages stay indented beneath the utility's headings. The next **File progress** box separates this file from the next job. A successful same-name remux appears in the final totals; it does not add a repeated success/phase/state row at the end.

</details>

Report and progress boxes use ASCII borders and a minimum content width of 44 display columns, expanding for longer lines; their padding uses zsh's multibyte display-width accounting so wide and combining text aligns without changing the border characters. The renderer retains complete lines; a terminal narrower than a box may wrap them. A report may include staged filenames, native scratch filenames, cleanup failures, or uncertain publication details when recovery needs attention. These records distinguish source preservation and output publication state; they do not promise an automatic rollback of already-published extraction artifacts.

Warnings, failed or partial jobs, unresolved track/source skips, and interrupted batches produce a nonzero final exit status. Review the reported filenames and recovery details before repeating an operation, especially when the output state is uncertain.

### Stopping a running batch

Press **Ctrl+C** after configuration completes and processing starts. The final report lists the exact filenames that were not started because of the stop.

| Category | What happens after Ctrl+C |
| --- | --- |
| Edit | Finish the active file and inspect its metadata, then stop before the next file. |
| Mux | Finish the active remux, validate its output and complete normal publication, then stop before the next file. |
| Extract tracks | Stop the active extraction tool and discard its unfinished, unvalidated track files. Previously published outputs remain. |
| Extract attachments | Stop the active extraction tool. Completed attachments remain; no rollback is attempted. |

For Edit and Mux, pressing Ctrl+C again keeps the same stop request. The current file still receives its actual success, warning or failure result. A stopped invocation returns nonzero even when that current file completed successfully. During processing, `e` is not read as a command.

Extraction cleanup is limited to identifiable partial track files in the run's own staging directory. Validated recovery files, uncertain publications and unexpected artifacts are retained and reported. If shutdown or cleanup cannot be confirmed, the report identifies the retained filenames. Closing the terminal or sending TERM/HUP aborts processing and retains recoverable staging where possible; it does not request the graceful Edit/Mux finish.

<details>
<summary>Example: stop a three-file Mux batch after the active file</summary>

Complete the Mux settings; preflight runs and processing starts automatically. Suppose `Episode 01.mkv` has finished and `Episode 02.mkv` is being remuxed. Press Ctrl+C once. The utility prints:

```text
Stop requested; finishing the current file before stopping.
```

Wait for the active file's validation and publication to finish. If it succeeds, the final report counts both episodes as done and lists `Episode 03.mkv` under **Files not started due to stop**. A warning or validation failure for Episode 02 keeps its actual outcome and recovery details.

For an attachments-and-tracks Extract batch, Ctrl+C during track extraction keeps the attachments already published and removes the unfinished track candidates. Completed earlier files are left in place.

This is the graceful path: Ctrl+C asks the category to stop at its documented safe boundary. Closing the terminal or sending TERM/HUP is immediate process termination and does not request that boundary:

```text
Ctrl+C once
  Edit/Mux: finish the active file, report its real result, then stop.
  Extract: stop the active extraction tool and apply its stage-specific cleanup.

Close terminal or TERM/HUP
  Processing aborts; recoverable staging is retained where possible and reported.
```

</details>

## Testing

The repository tests use copied fixtures and controlled tool commands so they can exercise the interactive entry point without modifying user media. Run the affected Matroska test group from the repository root with the existing virtual environment:

```zsh
.venv/bin/python -B -m pytest --disable-plugin-autoload tests/mkv_tools
```

To run only the `mkv_utils` test module:

```zsh
.venv/bin/python -B -m pytest --disable-plugin-autoload tests/mkv_tools/test_mkv_utils.py
```

The final-block and track/source-preflight changes passed **22 focused checks** on one frozen source/test pair. These cover per-category missing-ID/type guards, valid and malformed configuration, source replacement before planning and runtime preflight, mixed/all-skipped counts and histories, count-only removal bypass, dry-run safety, final report groups and indicator lifecycle. Native writers are controlled in these checks.

One additional quick controlling-terminal journey used installed v93 identification on five tiny real files, a controlled selector and `--dry-run`. It overwrote one selected fixture at the final title prompt. The result was **1 simulated, 4 skipped and 0 failed**: a total-count mismatch, a missing ID, a type/codec mismatch and a changed source. Five read-only identification calls and zero modifying-call attempts were recorded. The nonzero exit was expected for unresolved skips. The check also verified separate final blocks, no exclusion prompt, no Working after processing began, and no output/staging additions beyond the deliberate input replacement. It does not claim a new installed-fzf, loaded-alias or native-write campaign.

The earlier dry-run and bare-ID reorder update passed **10 focused checks** for ordering, concise reports, native indentation and dry-run safety. A separate bounded interactive pass qualified **seven distinct journeys across recorded runs** through the loaded shell alias outside the repository, using installed fzf and MKVToolNix v93 on disposable tiny files. Those journeys cover track 0 handling, invalid-order retries, shared per-ID answers across two files, dry-run's zero modifying calls and unchanged inventory, Edit title, and combined extraction. Captured output checks include indentation, filenames, aligned boxes and final exit; this focused pass does not repeat every earlier choice or codec combination.

Earlier controlled checks include **70 input-validation cases** (22 controlling-terminal journeys), **184 output-audit cases** across module and corrective runs, and **51 affected reporting/extraction cases** after an output correction. Their coverage includes action validation, Back and reselection, Working status, live native output, removal guards, warning/partial outcomes and report placement. These counts are from separate recorded revisions and aggregated runs; they do not describe one entirely passing invocation.

A separate logged campaign passed **20 native menu journeys** on disposable fixtures with MKVToolNix v93, across all four supported extensions, Edit, Mux, Extract and matching/mismatched Analyze. Three terminal qualifications separately checked fzf filtering and multi-select at 80 columns, a three-file reorder at 100 columns, and a Back/reselection journey. Renderer checks cover ASCII, wide and combining text on zsh 5.9.2 and 5.8. Captured widths do not establish every font or viewport; signal timing and injected failures use controlled writers; native checks do not cover every codec combination. No CI result is implied.

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
| A file is skipped for a missing or incompatible target ID | Check that each selected original ID exists with the expected type. Choose only the reported files in a fresh invocation to configure them separately. |
| A file is reported as changed after inspection/planning | The source was replaced or changed after its snapshot was taken. Start a fresh invocation to inspect that version before applying settings. |
| A file is skipped for a removal mismatch | Compare the requested original track ID, type, and exact codec shown against the reference. Start a new invocation and explicitly select the files to retry. |
| An output destination already exists | Review the planned path. Track outputs are not overwritten; attachment extraction may overwrite an existing regular same-name file. |
| An interrupted or partial extraction reports retained staging paths | Review the final report and those paths before retrying or cleaning them up. |
