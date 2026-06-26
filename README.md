# Personal Script Toolkit

A small collection of Python scripts, shell helpers, Cronus Zen files, and Tampermonkey userscripts I use for media work, quick automation, and a few game-specific tasks.

> Python dependencies: `pip install -r requirements.txt`

Repo layout:
- Python CLIs live under [`python/`](python/)
- Shell scripts live under [`shell/`](shell/)
- Audio shell helpers live under [`shell/audio/`](shell/audio/)
- Downloadable tools live under [`tools/`](tools/)

## [Python Utilities](python/)

- [`yt-transcribe.py`](python/yt-transcribe.py) - Download YouTube captions and export them as text or DOCX. [Docs](docs/yt-transcribe.md)
- [`pyconvert.py`](python/pyconvert.py) - Convert decimal and hex values between common numeric formats. [Docs](docs/pyconvert.md)
- [`MediaFire.py`](python/MediaFire.py) - Combine two MediaFire quickkeys into one shareable link. [Docs](docs/mediafire.md)
- [`nord_ovpn_picker.py`](python/nord_ovpn_picker.py) - Browse and download NordVPN OpenVPN configs. [Docs](docs/nord-ovpn-picker.md)
- [`vpnroute.py`](python/vpnroute.py) - Turn domains or URLs into VPN route output. [Docs](docs/vpnroute.md)
- [`safari_bookmarks_export.py`](python/safari_bookmarks_export.py) - Export selected Safari bookmark folders to Firefox/Chrome HTML. [Docs](docs/safari-bookmarks-export.md)

## [Shell Utilities](shell/)

- [`mkv_extract_tracks.sh`](shell/mkv_extract_tracks.sh) - Extract every attachment from each MKV in the current folder. [Docs](docs/mkv-extract-tracks.md)
- [`mkv_mux.zsh`](shell/mkv_mux.zsh) - Interactive MKV remux and volume-boost helper. [Docs](docs/mkv-mux.md)
- [`mkv_utils.zsh`](shell/mkv_utils.zsh) - Interactive MKV metadata, extraction, and track-edit helper. [Docs](docs/mkv-utils.md)
- [`satisfactory_balancer.zsh`](shell/satisfactory_balancer.zsh) - Satisfactory splitter, balancer, and compressor planner. [Docs](docs/satisfactory-balancer.md)
- [`satisfactory-modeler.zsh`](shell/satisfactory-modeler.zsh) - macOS-only launcher and updater wrapper for Satisfactory Modeler. [Docs](docs/satisfactory-modeler.md)
- [`discord_install_fixer.zsh`](shell/discord_install_fixer.zsh) - macOS-only Discord Stable/PTB/Canary updater reset, app replacement, and OpenAsar injection helper. [Docs](docs/discord-install-fixer.md)
- [`brew-custom-compare.zsh`](shell/brew-custom-compare.zsh) - Compare custom tap formulas against upstream Homebrew versions. [Docs](docs/brew-custom-compare.md)
- [`fetch-ios-pkgs.zsh`](shell/fetch-ios-pkgs.zsh) - Download and install current Apple mobile-device support packages. [Docs](docs/fetch-ios-pkgs.md)

## [Audio Helpers](shell/audio/)

- [`shell/audio/strip_audio_tags.zsh`](shell/audio/strip_audio_tags.zsh) - Strip metadata from `.m4a` files in the current folder. [Docs](docs/strip-audio-tags.md)
- [`shell/audio/fix_tags.zsh`](shell/audio/fix_tags.zsh) - Rebuild `.m4a` metadata by exporting, stripping, and reapplying tags. [Docs](docs/fix-tags.md)

## [Zen Scripts](Zen%20Scripts/)

- [`BO3 AO-Mod (Version 2.4c) [ZEN].gpc`](Zen%20Scripts/BO3%20AO-Mod%20%28Version%202.4c%29%20%5BZEN%5D.gpc) - Cronus Zen Black Ops 3 mod script with in-game toggles and feedback. [Docs](docs/bo3-ao-mod.md)

## [Tools](tools/)

- [`GPC Builder by Jimmy CrakCrn.zip`](tools/GPC%20Builder%20by%20Jimmy%20CrakCrn.zip) - Portable Cronus Zen GPC scripting IDE by Jimmy CrakCrn with a code editor, validator, component builder, OLED layout designer, embedded references, and Anthropic API-powered assistance.

## [Userscripts (Tampermonkey)](userscripts/)

- [`PSPrices-PlayStation-Checkout-Link.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-PlayStation-Checkout-Link.user.js) - Replaces PSPrices paywalled avatar/theme purchase panels or unavailable-store warnings with custom regional PS Store checkout-link panels, adds an unlocked badge, and hides unlock prompts. [Docs](docs/psprices-playstation-checkout-link.md)
- [`PSPrices-Collection-Live-Search.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Collection-Live-Search.user.js) - Adds cached live substring search to PSPrices avatar and theme collection pages, with background region indexing, platform/free filters, and progressive result hydration. [Docs](docs/psprices-collection-live-search.md)
- [`PSPrices-Show-Product-SKU.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js) - Displays and copies the public PlayStation product SKU on PSPrices product pages, adding a native-style SKU panel below buy, checkout, or unavailable-store sections only when PSPrices does not already show one. [Docs](docs/psprices-show-product-sku.md)
- [`Steam-Reveal-Spoilers.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Steam-Reveal-Spoilers.user.js) - Automatically reveals Steam Community spoiler text by unwrapping spoiler spans on page load and dynamic updates. [Docs](docs/steam-reveal-spoilers.md)
- [`StackExchange-Reveal-Spoilers.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/StackExchange-Reveal-Spoilers.user.js) - Automatically reveals Stack Exchange spoiler blocks by applying the site's visible spoiler class to existing and dynamically added spoilers. [Docs](docs/stackexchange-reveal-spoilers.md)
- [`Youtube-shorts-switcher.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Youtube-shorts-switcher.user.js) - Adds a Shorts action-column button and configurable hotkey that open the current YouTube Short in the normal watch player. [Docs](docs/youtube-shorts-switcher.md)

---

Some scripts expect Homebrew-installed tooling such as `mkvtoolnix`, `ffmpeg`, `jq`, `fzf`, or Microsoft Word for DOCX workflows. Check the linked doc page for each script before running it.

_All tools and scripts in this repo were vibe coded with OpenAI agents._
