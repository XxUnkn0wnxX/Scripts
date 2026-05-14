# Personal Script Toolkit

A small collection of Python scripts, shell helpers, Cronus Zen files, and Tampermonkey userscripts I use for media work, quick automation, and a few game-specific tasks.

> Python dependencies: `pip install -r requirements.txt`

## Python Utilities

- [`yt-transcribe.py`](yt-transcribe.py) - Download YouTube captions and export them as text or DOCX. Docs: [`docs/yt-transcribe.md`](docs/yt-transcribe.md)
- [`pyconvert.py`](pyconvert.py) - Convert decimal and hex values between common numeric formats. Docs: [`docs/pyconvert.md`](docs/pyconvert.md)
- [`MediaFire.py`](MediaFire.py) - Combine two MediaFire quickkeys into one shareable link. Docs: [`docs/mediafire.md`](docs/mediafire.md)
- [`nord_ovpn_picker.py`](nord_ovpn_picker.py) - Browse and download NordVPN OpenVPN configs. Docs: [`docs/nord-ovpn-picker.md`](docs/nord-ovpn-picker.md)
- [`vpnroute.py`](vpnroute.py) - Turn domains or URLs into VPN route output. Docs: [`docs/vpnroute.md`](docs/vpnroute.md)

## Shell Utilities

- [`mkv_extract_tracks.sh`](mkv_extract_tracks.sh) - Extract every attachment from each MKV in the current folder. Docs: [`docs/mkv-extract-tracks.md`](docs/mkv-extract-tracks.md)
- [`mkv_mux.zsh`](mkv_mux.zsh) - Interactive MKV remux and volume-boost helper. Docs: [`docs/mkv-mux.md`](docs/mkv-mux.md)
- [`mkv_utils.zsh`](mkv_utils.zsh) - Interactive MKV metadata, extraction, and track-edit helper. Docs: [`docs/mkv-utils.md`](docs/mkv-utils.md)
- [`satisfactory_balancer.zsh`](satisfactory_balancer.zsh) - Satisfactory splitter, balancer, and compressor planner. Docs: [`docs/satisfactory-balancer.md`](docs/satisfactory-balancer.md)
- [`brew-custom-compare.zsh`](brew-custom-compare.zsh) - Compare custom tap formulas against upstream Homebrew versions. Docs: [`docs/brew-custom-compare.md`](docs/brew-custom-compare.md)
- [`fetch-ios-pkgs.zsh`](fetch-ios-pkgs.zsh) - Download and install current Apple mobile-device support packages. Docs: [`docs/fetch-ios-pkgs.md`](docs/fetch-ios-pkgs.md)

## [Audio Helpers](Audio/)

- [`Audio/strip_audio_tags.zsh`](Audio/strip_audio_tags.zsh) - Strip metadata from `.m4a` files in the current folder. Docs: [`docs/strip-audio-tags.md`](docs/strip-audio-tags.md)
- [`Audio/fix_tags.zsh`](Audio/fix_tags.zsh) - Rebuild `.m4a` metadata by exporting, stripping, and reapplying tags. Docs: [`docs/fix-tags.md`](docs/fix-tags.md)

## [Zen Scripts](Zen%20Scripts/)

- [`BO3 AO-Mod (Version 2.4b) [ZEN].gpc`](Zen%20Scripts/BO3%20AO-Mod%20%28Version%202.4b%29%20%5BZEN%5D.gpc) - Cronus Zen Black Ops 3 mod script with in-game toggles and feedback. Docs: [`docs/bo3-ao-mod.md`](docs/bo3-ao-mod.md)

## [Userscripts (Tampermonkey)](userscripts/)

- [`Steam-Reveal-Spoilers.user.js`](userscripts/Steam-Reveal-Spoilers.user.js) - Reveal Steam community spoilers automatically. Docs: [`docs/steam-reveal-spoilers.md`](docs/steam-reveal-spoilers.md)
- [`StackExchange-Reveal-Spoilers.user.js`](userscripts/StackExchange-Reveal-Spoilers.user.js) - Reveal Stack Exchange spoilers automatically. Docs: [`docs/stackexchange-reveal-spoilers.md`](docs/stackexchange-reveal-spoilers.md)
- [`Youtube-shorts-switcher.user.js`](userscripts/Youtube-shorts-switcher.user.js) - Open YouTube Shorts in the full player with a button or hotkey. Docs: [`docs/youtube-shorts-switcher.md`](docs/youtube-shorts-switcher.md)

---

Some scripts expect Homebrew-installed tooling such as `mkvtoolnix`, `ffmpeg`, `jq`, `fzf`, or Microsoft Word for DOCX workflows. Check the linked doc page for each script before running it.
