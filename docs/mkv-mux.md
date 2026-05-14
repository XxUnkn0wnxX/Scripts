# mkv_mux.zsh

[`mkv_mux.zsh`](../mkv_mux.zsh) is an interactive Matroska helper for quick remuxing and audio-volume jobs. It is menu-driven, so you launch it, pick an option, then follow the prompts.

## What It Does

- Remux video files into MKV with `ffmpeg`
- Remux video files into MKV with `mkvmerge`
- Boost one audio track and mux the boosted versions back into the file
- Optionally apply a ceiling limiter during supported audio re-encode paths with `--climit`
- Uses `fzf` for interactive file picking
- Uses `jq` with `mkvmerge -J` to inspect audio-track metadata
- Creates backup originals in safe mode before writing changes

## Requirements

Install the tools used by this script:

```bash
brew install mkvtoolnix ffmpeg fzf jq rsync
```

## Basic Usage

Run in the current directory:

```bash
zsh mkv_mux.zsh
```

Run in another directory:

```bash
zsh mkv_mux.zsh /path/to/folder
```

Show help:

```bash
zsh mkv_mux.zsh --help
```

Enable the extra limiter prompt for supported audio re-encode paths:

```bash
zsh mkv_mux.zsh --climit
```

Use both a directory and `--climit`:

```bash
zsh mkv_mux.zsh --climit /path/to/folder
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
      <td><nobr><code>--climit</code></nobr></td>
      <td>Flag</td>
      <td>Adds one extra prompt for supported audio re-encode paths so you can apply an <code>alimiter</code> ceiling filter.</td>
    </tr>
    <tr>
      <td><nobr><code>--help</code>, <code>-h</code></nobr></td>
      <td>Flag</td>
      <td>Prints the built-in help page and exits.</td>
    </tr>
  </tbody>
</table>

## Menu Options

### 1) Remux to MKV (ffmpeg)

What it does:

- Uses `ffmpeg` to put the selected file into an MKV container
- Can keep the current audio as-is
- Can optionally re-encode incompatible audio tracks to AAC
- With <code>--climit</code>, the replacement AAC encode path can also apply the limiter

Good for:

- MP4 to MKV remux jobs
- quick container changes without opening a GUI tool

Example:

```text
1) Remux to MKV (ffmpeg)
Do you wish to replace incompatible audio tracks (Y/N) [N]:
```

Simple example run:

```bash
zsh mkv_mux.zsh /Volumes/Media/My Show
```

Then choose:

```text
1
N
```

If you choose to replace audio tracks and launch the script with `--climit`, it asks one extra limiter prompt before the AAC re-encode starts.

### 2) Remux to MKV (mkvmerge)

What it does:

- Uses `mkvmerge` instead of `ffmpeg`
- Remuxes the selected file into MKV
- Does not use the ffmpeg audio-replace path from option `1`

Good for:

- simple MKV remux work
- users who want the `mkvmerge` path directly

Example:

```bash
zsh mkv_mux.zsh /Volumes/Media/My Show
```

Then choose:

```text
2
```

### 3) Volume Boost

What it does:

- Lets you choose one audio track
- Extracts that track
- Creates one or more boosted AAC versions
- Muxes those boosted versions back into the Matroska file

Good for:

- making quiet audio tracks louder
- generating multiple boosted versions in one run

Example:

```text
3
Enter the amount of dB to change (e.g., 2dB,3.5dB,-5dB):
```

Example input:

```text
2dB,3.5dB
```

That creates two boosted tracks, one at `2dB` and one at `3.5dB`.

## How `--climit` Works

Without `--climit`:

- option `1` re-encodes replacement audio without the limiter
- option `3` applies only the volume filter

With `--climit`:

- option `1` asks one extra limiter prompt if you choose to replace audio tracks
- option `3` asks one extra limiter prompt after the dB prompt
- pressing `Enter` uses the default limiter:

```text
alimiter=limit=0.99:attack=20:release=20
```

- you can also enter a custom limiter such as:

```text
alimiter=limit=0.90:attack=35:release=50
```

The script always appends `:level=0` itself.

Example:

```bash
zsh mkv_mux.zsh --climit /Volumes/Media/My Show
```

Option `1` example:

```text
1
Y
<press Enter for default limiter>
```

Option `3` example:

Then choose:

```text
3
2dB
<press Enter for default limiter>
```

## Prompt Behavior

Important basics:

- invalid menu input is rejected and reprompted
- invalid `Y/N` input is rejected and reprompted
- invalid dB syntax is rejected and reprompted
- invalid limiter syntax is rejected and reprompted

Examples of valid dB input:

- `2dB`
- `3.5dB`
- `-5dB`
- `2dB,3.5dB,-5dB`

Examples of invalid dB input:

- `abc`
- `1dB,`
- `,2dB`

## Safe Mode Note

This script has a safe-mode path built in.

- In safe mode, it writes new filenames instead of overwriting the original file.
- In non-safe mode, it can prompt before overwriting an existing MKV target.

If you decline an overwrite prompt, that file is skipped and the batch moves on to the next selected file.

## Quick Examples

Remux an MP4 to MKV with `ffmpeg`:

```bash
zsh mkv_mux.zsh /Volumes/Media/My Show
```

Then pick:

```text
1
N
```

Boost one track by `2dB` and `3.5dB`:

```bash
zsh mkv_mux.zsh /Volumes/Media/My Show
```

Then pick:

```text
3
2dB,3.5dB
```

Boost one track and apply the default ceiling limiter:

```bash
zsh mkv_mux.zsh --climit /Volumes/Media/My Show
```

Then pick:

```text
3
2dB
<press Enter>
```

## Troubleshooting

- `No files selected. Exiting.`
  Pick at least one file in the `fzf` selector.

- `Invalid dB input.`
  Use values like `2dB,3.5dB,-5dB`.

- `Invalid limiter.`
  Use the full format `alimiter=limit=0.99:attack=20:release=20` or just press `Enter` for the default.

- `Error: Working directory not found`
  Check the path you passed to the script.
