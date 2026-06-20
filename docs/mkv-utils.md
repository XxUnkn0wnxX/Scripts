# mkv_utils.zsh

[`mkv_utils.zsh`](../shell/mkv_utils.zsh) is an interactive Matroska utility menu for metadata edits, attachment extraction, track extraction, track removal, and track reordering. It is the more power-user-oriented companion to `mkv_mux.zsh`.

## What It Does

- edits forced and default flags
- edits language values
- edits track names
- sets or clears the MKV title
- extracts attachments
- extracts selected tracks
- removes selected tracks
- reorders tracks
- enumerates track information before edits or extraction
- uses codec-aware extension mapping when extracting tracks
- relies on Python helper libraries for the codec-to-extension mapping path
- reports the filename after successful or failed metadata edits
- tracks progress, average ETA, failures, and elapsed time for multi-file remux queues

## Requirements

Install the tools used by this script:

```bash
brew install mkvtoolnix jq fzf python3
python3 -m pip install pymkv pymkv2
```

`pymkv` and `pymkv2` are used for the codec-to-extension mapping logic during track extraction.

If this repo has a local virtualenv, install the repo requirements too:

```bash
source "$HOME/.zshrc"
source .venv/bin/activate
pip install -r requirements.txt
```

## Basic Usage

Run in the current directory:

```bash
zsh shell/mkv_utils.zsh
```

Run in another directory:

```bash
zsh shell/mkv_utils.zsh /path/to/folder
```

Show help:

```bash
zsh shell/mkv_utils.zsh --help
```

## Arguments

<table>
  <thead>
    <tr>
      <th>Argument</th>
      <th>Type</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>working_directory</code></nobr></td>
      <td>Positional</td>
      <td>Optional folder path. If omitted, the script works in your current directory.</td>
    </tr>
    <tr>
      <td><nobr><code>--help</code>, <code>-h</code></nobr></td>
      <td>Flag</td>
      <td>Prints the built-in help page and exits.</td>
    </tr>
  </tbody>
</table>

## Menu Options

### 1) Set flag-forced for tracks

What it does:

- sets the forced flag on selected track IDs
- can work on one file or several files

Example:

```bash
zsh shell/mkv_utils.zsh /Volumes/Media/My Show
```

Then choose:

```text
1
N
1
1
```

### 2) Set flag-default for tracks

What it does:

- sets the default flag on selected track IDs
- can work on one file or several files

Example:

```text
2
N
1
1
```

### 3) Set language for tracks

What it does:

- changes the language field for selected track IDs
- language input stays free-form

Example:

```text
3
N
1
eng
```

### 4) Set name for tracks

What it does:

- renames selected track IDs
- name input stays free-form

Example:

```text
4
N
1
English Stereo
```

### 5) Set title for MK file

What it does:

- sets the container title
- blank title removes the existing title
- title input stays free-form

Example:

```text
5
N
My Episode Title
```

To clear the title:

```text
5
N
<press Enter at the title prompt>
```

Options `1` through `5` report the filename after each `mkvpropedit` operation:

```text
Edited File: My Episode.mkv
```

If the edit fails, the original `mkvpropedit` error is followed by:

```text
Failed File: My Episode.mkv
```

Only the filename is displayed, not its directory path.

### 6) Extract all attachments from MK files

What it does:

- extracts embedded attachments such as fonts or images
- writes them into an `Attachments/` folder

Example:

```text
6
```

### 7) Mass Remove tracks for multi-MK files

What it does:

- removes selected Track IDs
- remuxes the remaining tracks back into the file
- reports per-file progress and an average ETA when multi-file mode contains at least two files
- lists failed remuxes in a final queue summary

Example:

```text
7
Y
2
```

That example removes Track ID `2` from the selected files.

### 8) Mass Re-order tracks for multi-MK files

What it does:

- changes track order using `mkvmerge --track-order`
- useful when you want a different audio or subtitle order
- reports per-file progress and an average ETA when multi-file mode contains at least two files
- lists failed remuxes in a final queue summary

Example:

```text
8
N
0:0,0:2,0:1
```

That example keeps the video first and swaps the two audio tracks.

### 9) Extract Tracks for multi-MK files

What it does:

- extracts selected tracks into separate files
- uses codec-aware extensions where possible

Example:

```text
9
N
1
```

That example extracts Track ID `1`.

## Prompt Behavior

Important basics:

- invalid menu input is rejected and reprompted
- invalid `Y/N` input is rejected and reprompted
- invalid Track ID syntax is rejected and reprompted
- invalid track-order syntax is rejected and reprompted
- language, name, and title are still free-form

Valid Track ID examples:

- `0`
- `0,1`
- `1-2`
- `0,2-4`

Invalid Track ID examples:

- `abc`
- `1,`
- `2-1`

Valid track-order examples:

- `0:0,0:1,0:2`
- `0:0,0:2,0:1`

Invalid track-order examples:

- `foo`
- `0:0,`
- `0-0`

## Multi-file Mode

Several options ask:

```text
Enable multi-file target selection? (Y/N) [N]:
```

Behavior:

- `Y` lets you pick multiple files in `fzf`
- `N` picks one file
- pressing `Enter` uses the default `N`

For options `7` and `8`, selecting at least two files enables queue reporting. The total count is printed before the first remux. Each successful remux then reports its filename, processing time, successful-file count, files remaining in the queue, and estimated time remaining:

```text
Total Files Count: 36
My Episode.mkv
  Processed In: 00:00:07
  Files Done: 1
  Files Remaining: 35
  Estimated Time Remaining: 00:04:05
```

The ETA uses the cumulative average duration of all successful remuxes completed so far. Failed remuxes do not increase `Files Done` or contribute to that average:

```text
Failed: Broken Episode.mkv
```

After the queue finishes, the script prints successful and failed totals, lists failed filenames with indentation, and reports total elapsed queue time:

```text
Total Files Done: 33
Failed Files: 03
  Broken Episode.mkv
  Missing Track Episode.mkv
  Damaged Episode.mkv
Elapsed Time: 00:05:04
```

Single-file runs and multi-file mode with only one selected file do not print these queue statistics.

## Quick Examples

Rename one audio track:

```bash
zsh shell/mkv_utils.zsh /Volumes/Media/My Show
```

Then choose:

```text
4
N
1
English Stereo
```

Set one subtitle track language:

```text
3
N
2
eng
```

Extract one audio track:

```text
9
N
1
```

Reorder tracks:

```text
8
N
0:0,0:2,0:1
```

## Troubleshooting

- `No file selected. Exiting.`
  Pick a file in the `fzf` selector.

- `No target files selected. Exiting.`
  Pick at least one file in multi-file mode.

- `Invalid Track ID syntax.`
  Use forms like `0`, `0,1`, or `1-2`.

- `Invalid track order syntax.`
  Use forms like `0:0,0:1,0:2`.

- `Please check if there are Matroska files ...`
  The target directory does not contain `.mkv`, `.mka`, `.mks`, or `.mk3d` files.
