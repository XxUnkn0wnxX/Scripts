# mkv_extract_tracks.sh

[`mkv_extract_tracks.sh`](../mkv_extract_tracks.sh) extracts every attachment from every `.mkv` file in the current directory.

## What It Does

- scans the current directory for `.mkv` files
- counts embedded attachments in each file
- extracts all attachments with `mkvextract`

This is useful for grabbing embedded fonts, images, and other MKV attachments.

## Requirements

```bash
brew install mkvtoolnix
```

## Basic Usage

Run it inside a folder that contains MKV files:

```bash
zsh mkv_extract_tracks.sh
```

## Example

```bash
cd /Volumes/Media/My Show
zsh /Users/ovidijus/Apps/Scripts/mkv_extract_tracks.sh
```

## Good To Know

- There are no CLI flags.
- It works on every `.mkv` file in the current directory.
- If no `.mkv` files are found, it exits with a warning.
