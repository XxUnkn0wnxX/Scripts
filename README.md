# Personal Script Toolkit

A curated set of Python and shell utilities I use on macOS (or other Unix-like systems) for media handling, transcript workflows, and quick automation tasks. Feel free to reuse anything here—some scripts do require third‑party tools, which are noted below.

> Python dependencies: `pip install -r requirements.txt`

## Python Utilities

- `yt-transcribe.py`  
  CLI tool that pulls YouTube captions (manual or auto-generated), cleans them, and exports either plain text or DOCX. Supports language preferences, caption translation, sanitized filenames, and time-based cutoffs.

- `convert.py`  
  Hex/float conversion helper that reads binary values, enforces bounds, and prints them in multiple numeric formats. Useful when inspecting save files or binary blobs.

- `MediaFire.py`  
  Combines two MediaFire quickkeys (one trusted, one blocked) to generate an alternate download URL. Includes Ctrl+C handling so you can abort cleanly.

## Shell Utilities

- `mkv_extract_tracks.sh`  
  Batch-extracts every attachment from each MKV in the current directory using `mkvextract`. Handy for grabbing embedded fonts or images.

- `mkv_mux.zsh`  
  Interactive Matroska toolbox that wraps `mkvmerge`, `ffmpeg`, `fzf`, and `jq` to remux sources, back up originals, boost audio, and inspect tracks with a guided menu.

- `mkv_utils.zsh`  
  Companion script for power users: enumerates MKV tracks, applies codec-to-extension overrides, extracts streams, and leverages Python helpers for tricky cases.

## Userscripts (Tampermonkey)

- [Reveal Steam Spoilers](https://github.com/XxUnkn0wnxX/Scripts/raw/refs/heads/main/userscripts/Steam-Reveal-Spoilers.user.js)
- [Reveal StackExchange Spoilers](https://github.com/XxUnkn0wnxX/Scripts/raw/refs/heads/main/userscripts/StackExchange-Reveal-Spoilers.user.js)
- [Youtube Shorts Switcher](https://github.com/XxUnkn0wnxX/Scripts/raw/refs/heads/main/userscripts/Youtube-shorts-switcher.user.js)

---

Most scripts expect Homebrew-installed tooling (e.g., `mkvtoolnix`, `ffmpeg`, `jq`, `fzf`, or Microsoft Word for DOCX workflows). Check the top of each script for specific prerequisites before running.
