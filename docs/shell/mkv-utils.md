<a id="mkv_utilszsh"></a>

# 🎞️ `mkv_utils.zsh`

[← Back to the toolkit](../../README.md)

[`mkv_utils.zsh`](../../shell/mkv_utils.zsh) is a single interactive script for Matroska track analysis, metadata edits, remuxing and extraction. Choose a category, select one or more files, enter the settings, and the batch starts when configuration is complete.

It scans only the chosen directory (not subdirectories) and supports `.mkv`, `.mka`, `.mks` and `.mk3d` files. Examples below use abbreviated transcripts.

<a id="quick-start"></a>

## 🚀 Start here

Run from the repository root:

```zsh
zsh shell/mkv_utils.zsh
```

Pass a working directory as an argument to use another folder. Relative and absolute paths are accepted; quote paths containing spaces.

```zsh
zsh shell/mkv_utils.zsh ../
zsh shell/mkv_utils.zsh "/Volumes/Media/My Show"
zsh shell/mkv_utils.zsh --dry-run "/Volumes/Media/My Show"
zsh shell/mkv_utils.zsh --bypass "/Volumes/Media/My Show"
```

If you already have a `mkvutil` alias, it accepts the same arguments. Help is available with `zsh shell/mkv_utils.zsh --help`.

| Option | Effect |
| --- | --- |
| `[dir]` | Use this directory instead of the current directory. |
| `--dry-run` | Inspect, validate and simulate the configured batch without changing media or creating output files or directories. |
| `--bypass` | Silently skip the Mux removal track-count guard only. Other compatibility and runtime checks remain active. |
| `--help` | Show concise command help and exit. |

Dry-run checks the plan and source identity, but cannot prove that a native write or output validation will succeed. Analyze is read-only with or without this option.

<details>
<summary>Example: dry-run a removal, reorder and metadata batch</summary>

Examples in this guide are abbreviated illustrations. The real prompts include the selected tracks and their descriptions.

```text
Remove IDs: 12
Track order: 4,3
Metadata [none]: 3

Mux (DRYRUN) 1,2: remove + reorder; metadata 3
Processing: Episode 01.mkv

+----------------------------------------------+
| Simulated                                    |
+----------------------------------------------+
| Episode 01.mkv                               |
|   Would write: Episode 01.mkv                |
| Files were not changed.                      |
+----------------------------------------------+
```

</details>

<a id="choose-a-category-and-batch-its-actions"></a>

## 🧭 Choose a category

At **Category**, type one number and press Enter. Action submenus accept one choice, comma lists or ascending ranges, such as `1`, `1,2` or `1-3`, followed by Enter. The file picker supports typing a filename or extension to filter; choose one file or mark several with Tab, then confirm.

Before processing, `e`/`E` goes Back, or exits silently at the main menu. Ctrl+C cancels configuration. In the file picker, `e` remains an fzf search character.

| Category | Actions | Use it for |
| --- | --- | --- |
| **[1. Matroska Edit](#edit)** | `1` forced flag · `2` default flag · `3` language · `4` track name · `5` title | Metadata-only edits with `mkvpropedit`. |
| **[2. Matroska Mux](#mux)** | `1` remove tracks · `2` reorder tracks | One remux per eligible file, optionally with metadata. |
| **[3. Matroska Extract](#extract)** | `1` attachments · `2` selected tracks | Extract either or both kinds of content. |
| **[4. Matroska Analyze](#analyze)** | Select files | Compare track IDs and media formats. |

The last required answer starts preflight and then the eligible queue automatically. There is no separate review/run menu. After processing, the final report prints and the script exits.

<a id="edit"></a>

### ✏️ Edit

Select any combination of actions `1-5`. For track actions, enter the target IDs once; each selected action then asks for a value for each ID, and applies those values to the same IDs in every eligible file. Before each value, the complete track description is shown. Title is a single container-wide value and needs no track IDs; leave its value blank to clear it.

Choose `5` alone to go directly to the title prompt, without a track listing or track-ID/type matching requirement. Selected files may have different track layouts. When title is combined with track actions, the listing and checks still apply to those track actions.

Edit modifies files in place and groups the chosen metadata changes into one `mkvpropedit` operation per file. Its report gives final results without between-file elapsed-time blocks.

<details>
<summary>Example: set both flags on the same tracks</summary>

```text
Category: 1
Actions: 1,2
Set track IDs for batch operations: forced, default
Track IDs: 4,3
Track ID 4: subtitles (S_TEXT/ASS) [Signs & Songs] [eng]
Forced (0/1) [0]: 0
Track ID 3: subtitles (S_TEXT/UTF8) [Dialogue] [jpn]
Forced (0/1) [0]: 1
Track ID 4: subtitles (S_TEXT/ASS) [Signs & Songs] [eng]
Default (0/1) [1]: 1
Track ID 3: subtitles (S_TEXT/UTF8) [Dialogue] [jpn]
Default (0/1) [1]: 0
```

The second action reuses the original ID selection. Values are collected once and applied across the selected files.

For a title-only batch:

```text
Category: 1
Actions: 5
Title [clear]: My series
```

</details>

<a id="mux"></a>

### 🎬 Mux

Choose removal, reorder or `1,2` to combine them. Removal is configured first. Both operations use **original source IDs**. Optional metadata is included in the same `mkvmerge` remux. Successful output is validated before replacing the selected source.

Without removal, the source extension is preserved. With removal, retained content determines the output:

| Tracks remaining | Extension |
| --- | --- |
| Video | `.mkv`, or `.mk3d` when the source uses it |
| Audio without video | `.mka` |
| Subtitles only | `.mks` |
| None | Rejected |

Enter reorder IDs as a comma list with at least two distinct IDs. Ranges and `0:` prefixes are not accepted. If retained source ID `0` is omitted, it is prepended; if included, it stays where entered, so `3,1,0` places video last among those three. Any other retained IDs omitted from the list append in their original order. Removed, unknown and duplicate IDs are rejected and prompt again.

The preview shows the complete resulting track list. Dropped tracks appear in soft red without a selectable ID. Explicitly requested tracks whose positions change appear gold; tracks moved automatically and all retained tracks in remove-only mode keep their normal colour. Colour needs no extra dependency. Redirected output, `NO_COLOR=1` and `TERM=dumb` stay plain; oversized previews use normal scrollback.

Optional Mux track metadata uses **output IDs** from that final layout. Track options use the same list and colours, carried into value entry with the current track's description repeated at each prompt. The utility maps output IDs back to their original source tracks internally. With reorder, track metadata targets the resolved reorder list, including an automatically prepended `0`; tracks appended automatically are not included. With removal alone, each track metadata action asks for its own output IDs. A removed track cannot be selected.

Title metadata is container-wide: choosing `5` alone goes directly to its value without another track listing or ID prompt. It adds no track-matching requirement; the checks required by removal/reorder still apply.

At `Metadata [none]:`, press Enter to skip metadata and begin preflight.

Before processing, Mux compares each selected file with the reference's complete original track layout, including tracks not selected for changes. The shared matching rule below applies. Removal also requires matching total track counts by default. `--bypass` silently permits extra tracks for removal; every expected ID must still match. Missing IDs, output-target mismatches and late source changes also skip the file.

<details>
<summary>Example: remove and reorder, then edit the resulting output tracks</summary>

Suppose source IDs are video `0`, unwanted audio `1`, subtitles `3` and audio `4`. Remove `1`, then enter reorder `4,3`. Retained `0` is prepended, so the resulting order is `0,4,3`; its output IDs are `0,1,2`.

```text
Remove IDs: 1
Track order: 4,3
Metadata [none]: 3,4

Output ID 0 → source ID 0: set language/name
Output ID 1 → source ID 4: set language/name
Output ID 2 → source ID 3: set language/name
```

Each per-track value is asked once and reused across eligible files. Source track `1` is shown as a dropped row without an ID; automatically appended retained tracks do not receive these edits.

</details>

<a id="extract"></a>

### 📤 Extract

Choose attachments, track IDs or both. Attachment extraction needs no IDs or track configuration: it collects every attachment from each file's own attachment list into a shared `Attachments/` folder beside them. Same-name regular attachment files overwrite in selected-file order, which is useful for collecting one common set of fonts or images.

Track extraction asks for original IDs and checks only that those IDs exist in each selected file. Track types, formats and counts can differ; each output uses that file's own track format. Existing regular outputs with the same filename and extension are replaced on a repeat pass. Companion formats stay together: VobSub includes `.sub` and `.idx`; WavPack may also produce `.wvc`. Preflight rejects unsafe attachment names, destinations that alias selected media and output collisions. Extraction stages outputs before publication.

Extract reports between-file progress. In a combined job, its elapsed-time and ETA block covers the track-extraction stage; the final report covers the complete job. Attachment-only and track-only jobs report their own stage.

<details>
<summary>Example: collect attachments from several episodes</summary>

```text
Category: 3
Actions: 1,2
Extract IDs: 3

Attachments from Episode 01.mkv → Attachments/Font.ttf
Attachments from Episode 02.mkv → Attachments/Font.ttf (replaces earlier copy)
Track output: Episode 01 - Track [3].ass
```

The attachment folder is shared. Same-name attachments replace earlier regular files; tracks also replace existing regular outputs on repeat passes. Queue collisions and input aliases remain protected. In this combined job, between-file progress covers track extraction.

The final **Attachments** block lists each extracted filename once, including its extension. Source filenames, attachment IDs and overwrite-history labels are omitted:

```text
Font.ttf
OtherFont.otf
```

</details>

<a id="analyze"></a>

### 🔎 Analyze

Select files in the usual picker. The first usable file becomes the reference. Analyze shows an **Analysing** indicator while it scans, then prints one track listing and reports filenames that differ or could not be inspected. It uses the same track-matching rule as processing; listing order does not matter. Analyze does not create a processing queue or write files.

## 🛡️ Back, validation and stopping

Inputs are checked before processing: selected IDs must exist, flags accept only `0` or `1`, and languages accept supported tags such as `eng` or `fr-CA`. Track-ID lists may include ranges, such as `1,3,4-6`; reorder uses comma lists only. Invalid input repeats the prompt. Blank names or titles clear that value.

Across Edit, Mux and Analyze, track matching uses the **original ID and media format**: ASS matches ASS, SSA matches SSA, SRT matches SRT, and audio formats such as AAC must match. Video must remain video, but its codec may differ. Compression, bitrate, names, languages and default/forced flags do not decide compatibility. Metadata values you explicitly request are checked separately after writing. Extract checks requested ID existence only; attachment extraction has no track-matching requirement.

A file that fails its required track checks is skipped as a whole while eligible files continue. Before each real Edit, Mux or Extract job, the source is checked against its inspected snapshot and applicable track requirements. **Working** appears during quiet preparation; native tool messages show progress once processing starts.

Back from configuration prompts clears the pending file selection and settings, then returns to the relevant action menu. Back from an action menu returns to the main categories. The optional Mux metadata **field** is an exception: `e` returns to metadata choices while preserving the selected files, removal and reorder settings. Choosing `e` at the optional metadata list returns to Mux actions and resets the pending Mux job. Once processing starts, `e` is not a control key.

To enter a literal track name or title of `e`/`E`, type `\e`/`\E`.

Ctrl+C before configuration is complete cancels. During a running batch, Ctrl+C requests a safe stop and the report lists files not started:

| Running action | Stop behavior |
| --- | --- |
| Edit | Finish the active file, inspect its metadata, then stop. |
| Mux | Finish, validate and publish the active remux, then stop. |
| Track extraction | Stop extraction and clear safe owned staging. Earlier published track files remain. |
| Attachment extraction | Stop extraction and clear safe owned staging; completed attachments remain. |

Mux and Extract mark their `.mkvutil-*` temporary folders with a branded `.token`. Once a job stops safely, its whole owned folder is removed, including OS metadata and nested files; symlink targets outside it stay untouched. Launch and exit also check safe leftovers in the working directory and its real `Attachments` collection; startup does not follow a symlinked collection. Active jobs, changed sources and folders without valid ownership are retained; Mux also retains uncertain publication recovery. Extract keeps published outputs and clears safe private staging even after a partial or interrupted job. `--help` and `--dry-run` never run cleanup.

Closing the terminal or sending TERM/HUP does not request the graceful finish. Review any retained staging or recovery filenames in the report before retrying.

<details>
<summary>Example: Back resets a pending job; Ctrl+C stops after the active file</summary>

```text
Category: 2
Actions: 1,2
Select files: Episode 01.mkv, Episode 02.mkv
Remove IDs: e
Back to Mux actions; pending files and settings cleared.

After selecting Mux actions and files again:
Mux 1,2: remove + reorder
Processing: Episode 01.mkv
Ctrl+C: finish the active file, then stop.
  mkvmerge v93.0 ('Goblu') 64-bit
  The file 'Episode 01.mkv' has been opened for writing.
  Multiplexing took 1 second.
Files Done: 1; Files Remaining: 1

+----------------------------------------------+
| Not attempted                                |
+----------------------------------------------+
| Episode 02.mkv                               |
+----------------------------------------------+
```

| Where you enter `e`/`E` | Back destination |
| --- | --- |
| Edit setting or Extract IDs | Its action menu; files and settings reset. |
| Mux removal/order field | Mux actions; files and settings reset. |
| Optional Mux metadata field | Metadata choices; files, removal and order retained. |
| Optional Mux metadata list | Mux actions; files and settings reset. |
| Any action menu | Main categories. |
| Main category menu | Exit. |

Once processing starts, Ctrl+C requests the category-specific stop described above.

</details>

<a id="reports"></a>

## 🧾 Reports

Reports use the directory's basename and filenames; full paths appear only for the working directory. Edit, Mux and Extract show action headings, filenames and indented native messages. Mux and Extract add between-file progress/ETA boxes; Edit reports timing only at the end. Analyze prints its reference listing and final mismatch report.

The final report identifies the actions, outcomes and skipped or failed filenames. Empty groups are omitted, and filenames do not repeat status prefixes. Attachment totals appear only when Extract attachments was selected, alone or in a combined batch. Dry-run results appear under **Simulated**. Warnings, failures, partial/interrupted runs, unresolved skips and Analyze mismatches or inspection failures return a nonzero status. Retry reported files in a fresh invocation, and review any recovery details first.

<details>
<summary>Example: report names and dry-run results</summary>

```text
Mux 1,2: remove + reorder
Processing: Episode 01.mkv
  mkvmerge v93.0 ('Goblu') 64-bit
  The file 'Episode 01.mkv' has been opened for writing.
  Multiplexing took 1 second.

+----------------------------------------------+
| Final report                                 |
+----------------------------------------------+
Directory: My Show
Selected: 3; Done: 2; Skipped: 1

+----------------------------------------------+
| Skipped                                      |
+----------------------------------------------+
| Episode 03.mkv                               |
+----------------------------------------------+
```

```text
+----------------------------------------------+
| Simulated                                    |
+----------------------------------------------+
| Episode 01.mkv                               |
|   Would write: Episode 01.mkv                |
| Files were not changed.                      |
+----------------------------------------------+
```

</details>

<a id="requirements"></a>

## ⚙️ Requirements and maintenance

The script is self-contained in `shell/mkv_utils.zsh`; it adds no `.zsh` runtime dependencies. It uses installed `mkvmerge`, `mkvextract`, `mkvpropedit`, `jq`, `fzf`, and Python with `pymkv`/`pymkv2`. The supported setup is MKVToolNix **v93.0** on macOS Big Sur. No upgrade is required. When the repository `.venv` exists, its Python interpreter is used even if `.venv` is a symlink.

<details>
<summary>Set up Python packages in a fresh checkout</summary>

Keep an existing working environment. For a checkout without one, run these commands from the repository root:

```zsh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

</details>

The Edit and Mux metadata menus share one action registry and corresponding argument builders. Add or change a metadata action there so both `mkvpropedit` and `mkvmerge` use the same definition.

| If you see… | Check… |
| --- | --- |
| No files found | The directory has top-level Matroska files; the scan is not recursive. |
| Missing `pymkv` or `pymkv2` | Check the repository `.venv` and packages from `requirements.txt`. |
| A file skipped for a track mismatch | Compare its original ID and media format with the reference; retry skipped files in a new selection. |
| A source changed after planning | Re-select it in a fresh run so settings match its current tracks. |
| An output already exists | Regular track and attachment outputs with the same filename/extension are replaced. Input aliases, symlinks, directories and conflicting queue destinations are rejected. |

To run the focused utility tests from the repository root:

```zsh
.venv/bin/python -B -m pytest --disable-plugin-autoload tests/mkv_tools/test_mkv_utils.py
```
