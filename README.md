# Personal Script Toolkit

A curated set of Python and shell utilities I use on macOS (or other Unix-like systems) for media handling, transcript workflows, and quick automation tasks. Feel free to reuse anything here—some scripts do require third‑party tools, which are noted below.

> Python dependencies: `pip install -r requirements.txt`

## Python Utilities

- `yt-transcribe.py`  
  CLI tool that pulls YouTube captions (manual or auto-generated), cleans them, and exports either plain text or DOCX. Supports language preferences, caption translation, sanitized filenames, and time-based cutoffs.

- `convert.py`  
  Hex/float conversion helper that reads binary values, enforces bounds, and prints them in multiple numeric formats. Useful when inspecting save files or binary blobs.

- `MediaFire.py`  
  Automates MediaFire quickkey pairing. Supply a blocked file link while you’re logged in, and it builds a shareable URL by combining that ID with one from a folder you control. Includes Ctrl+C handling so you can abort cleanly.

## Shell Utilities

- `mkv_extract_tracks.sh`  
  Batch-extracts every attachment from each MKV in the current directory using `mkvextract`. Handy for grabbing embedded fonts or images.

- `mkv_mux.zsh`  
  Interactive Matroska toolbox that wraps `mkvmerge`, `ffmpeg`, `fzf`, and `jq` to remux sources, back up originals, boost audio, and inspect tracks with a guided menu.

- `mkv_utils.zsh`  
  Companion script for power users: enumerates MKV tracks, applies codec-to-extension overrides, extracts streams, and leverages Python helpers for tricky cases.

- `satisfactory_balancer.zsh`  
  CLI helper that mirrors the official [Satisfactory Balancer wiki](https://satisfactory.wiki.gg/wiki/Balancer) layouts (load balancer, belt balancer, belt compressor) plus NicoBuilds’ complex ratio math.
  - **Usage:** `zsh satisfactory_balancer.zsh [options] n:m [n:m ...]` (ratios must be positive integers; bare `44` is invalid).
  
  - **Flags:** only `-h/--help` for usage info.
  
  - **Auto-detected modes:**
    - `LOAD-BALANCER` (`1:n`) – classic splitter trees; non-clean sizes are rounded up and loop-back lanes are reported.
    - `BELT-BALANCER` (`n>1`, `m≥n`) – describes split stages per input and merge stages per output, including loop-back/padding info.
    - `BELT-COMPRESSOR` (`n>1`, `m<n`) – pack-first merger stacks with explicit lane budgets and priority chains.
    - `NICO` complex ratios (`1:A:B[:C...]`) – automatically detected; the script reuses the clean 1→N planner, then prints a lane allocation table just like [NicoBuilds’ guide](https://www.reddit.com/r/SatisfactoryGame/comments/1mitmza/guide_how_to_load_balance_weird_ratios_without/).
    
  - **Examples:**
    
    - `zsh satisfactory_balancer.zsh 1:48` → LOAD-BALANCER blueprint for a clean 1→48 split.
    - `zsh satisfactory_balancer.zsh 4:7` → BELT-BALANCER showing split layers, merge layers, lane budgets, and loop-back counts.
    - `zsh satisfactory_balancer.zsh 5:2` → BELT-COMPRESSOR with pack-first priority notes (`O1→O2`).
    - `zsh satisfactory_balancer.zsh 1:44:8` → Nico-style split that divides 54 clean lanes into `44:8` plus loop-back.
    
    > Recipes and layer steps always enumerate the exact number of splitters/mergers per layer (`place 6 splitters to create 18 outputs`), followed by a branch-sequence summary so you can double-check the math in game.

- `brew-custom-compare.zsh`  
  Recursively scans every `*.rb` in a tap (root, `Formula/`, `Casks/`, etc.), fetches their stable versions via `brew info --json=v2`, and compares them with the official Homebrew JSON API so you can see which of your patched formulae are ahead, behind, or missing upstream equivalents. When the API lacks an entry or version, the script immediately checks all other tapped repos (excluding `homebrew/core`) and reports the first match inline—handy when your custom formula or cask mirrors one in another tap.
  > *Hard-coded to `custom/versions` by default; edit the `DEFAULT_CUSTOM_TAP` variable near the top of the script if your overrides live elsewhere.*

### Audio Helpers (`Audio/`)

- `strip_audio_tags.zsh`  
  Removes all metadata tags from `.m4a` files in the current directory using `ffmpeg`, overwriting each file in place.

- `fix_tags.zsh`  
  Extracts `.m4a` metadata to a sidecar file, strips the tags, then re-applies the clean metadata—useful when tags get corrupted but you want to keep the originals.

## Userscripts (Tampermonkey)

- [Reveal Steam Spoilers](https://github.com/XxUnkn0wnxX/Scripts/raw/refs/heads/main/userscripts/Steam-Reveal-Spoilers.user.js)
- [Reveal StackExchange Spoilers](https://github.com/XxUnkn0wnxX/Scripts/raw/refs/heads/main/userscripts/StackExchange-Reveal-Spoilers.user.js)
- [Youtube Shorts Switcher](https://github.com/XxUnkn0wnxX/Scripts/raw/refs/heads/main/userscripts/Youtube-shorts-switcher.user.js)

---

Most scripts expect Homebrew-installed tooling (e.g., `mkvtoolnix`, `ffmpeg`, `jq`, `fzf`, or Microsoft Word for DOCX workflows). Check the top of each script for specific prerequisites before running.
