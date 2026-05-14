# strip_audio_tags.zsh

[`Audio/strip_audio_tags.zsh`](../Audio/strip_audio_tags.zsh) removes metadata tags from every `.m4a` file in the current directory.

## What It Does

- scans the current directory for `.m4a` files
- strips metadata with `ffmpeg`
- replaces each file in place

## Requirements

```bash
brew install ffmpeg
```

## Basic Usage

```bash
zsh Audio/strip_audio_tags.zsh
```

## Example

```bash
cd /Volumes/Media/Album
zsh /Users/ovidijus/Apps/Scripts/Audio/strip_audio_tags.zsh
```

## Good To Know

- There are no CLI flags.
- It only works on `.m4a` files in the current directory.
- It overwrites the original files after writing a temporary copy first.
