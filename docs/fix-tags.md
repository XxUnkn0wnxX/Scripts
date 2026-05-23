# fix_tags.zsh

[`shell/audio/fix_tags.zsh`](../shell/audio/fix_tags.zsh) tries to repair `.m4a` metadata by exporting the tags, stripping them, then applying the clean metadata back onto the file.

## What It Does

- extracts metadata into a temporary sidecar file
- strips tags from the audio file
- reapplies the metadata to a clean output file
- replaces the original file

## Requirements

```bash
brew install ffmpeg
```

## Basic Usage

```bash
zsh shell/audio/fix_tags.zsh
```

## Example

```bash
cd /Volumes/Media/Album
zsh /Users/ovidijus/Apps/Scripts/shell/audio/fix_tags.zsh
```

## Good To Know

- There are no CLI flags.
- It only works on `.m4a` files in the current directory.
- It creates temporary metadata and audio files during processing, then removes them at the end.
