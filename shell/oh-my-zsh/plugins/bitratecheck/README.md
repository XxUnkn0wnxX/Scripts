<a id="bitratecheck"></a>

# 🎞️ bitratecheck

`bitratecheck` (shortcut `brc`) lists the video and audio streams in one or more
ffprobe-readable files and reports each stream's bitrate in decimal kb/s
(1000 bits/s). It does not use the container's overall bitrate as a track rate.

## Requirements

- Zsh and `ffprobe` from FFmpeg.
- Standard `awk` for packet calculations (included with macOS).
- No `jq`, Python, or MKVToolNix dependency.

## Install

From the repository root, copy the plugin:

```zsh
mkdir -p "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/bitratecheck"
cp shell/oh-my-zsh/plugins/bitratecheck/bitratecheck.plugin.zsh \
  "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/bitratecheck/"
```

Add `bitratecheck` to the existing `plugins=(...)` list in `~/.zshrc`, then
open a new shell. To load it immediately in the current shell:

```zsh
source "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/bitratecheck/bitratecheck.plugin.zsh"
```

Oh My Zsh is optional: source the plugin directly from your shell configuration,
or run it as a standalone script with `zsh bitratecheck.plugin.zsh FILE...`.

## Usage

```zsh
brc movie.mkv clip.mp4 song.m4a
bitratecheck song.flac
brc --scan movie.mkv
brc -- ./-named-file
```

The default mode uses each stream's stored bitrate, or a positive `BPS` metadata
tag (including language-suffixed tags such as `BPS-eng`) when available. If any
audio or video stream lacks a stored rate, the command scans that file's packets
once and calculates an average from packet
sizes and timestamps. `--scan` forces packet-based averages for all streams.
Rates are labelled `stored` or `calculated`; when a reliable rate cannot be
derived, the output says `unknown`. Scanning reads the whole file without
decoding, so large files can take longer. Bitrates describe encoded stream
data; container overhead is excluded from calculated rates.

`Track ID N` is the stream's ffprobe global stream index. It is useful for
identifying the stream in ffprobe output, but may differ from a container's
native track ID. Attached cover art is omitted from video results. Subtitle,
data, and other stream types are omitted.

Run `bitratecheck --help` for options. An unreadable or invalid file does not
prevent later files from being checked; the command returns a failure status if
any input fails.
