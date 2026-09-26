# Steam-Reveal-Spoilers.user.js

[`Steam-Reveal-Spoilers.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Steam-Reveal-Spoilers.user.js) is a Tampermonkey userscript that automatically reveals Steam Community spoiler text by unwrapping spoiler spans on page load and dynamic updates.

Current documented release: `1.0.1.3`.

## What It Does

- finds Steam spoiler spans such as `span.bb_spoiler`
- unwraps the hidden spoiler content so it becomes readable
- watches page updates so newly loaded spoilers are also revealed
- handles Steam's dynamic page changes after navigation

## Where It Works

- `http://steamcommunity.com/*` and `https://steamcommunity.com/*`, including guides, discussions, and comments that use Steam's spoiler spans.

It also runs inside embedded frames whose own URL matches that host.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`Steam-Reveal-Spoilers.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Steam-Reveal-Spoilers.user.js).
3. Create a new userscript in Tampermonkey and paste the file contents.
4. Save it, then reload a Steam community page.

## Basic Usage

There are no buttons or CLI arguments.

Once installed, just browse a Steam page with hidden spoilers and the text should be revealed automatically.

## Example

If a guide comment or discussion post contains hidden spoiler text, this script removes the spoiler wrapper so the content is visible without clicking each spoiler manually.

## Good To Know

- It runs automatically at page load.
- It also watches for content inserted later, so it still works on pages that update dynamically.
- There are no user settings in the script right now.

## Permissions and Page Changes

The script uses `@grant none` and requests no userscript-manager APIs. It moves
the children out of each `span.bb_spoiler`, removing the spoiler wrapper while
retaining its content. It watches inserted content and navigation so new
spoilers are revealed too.

Revealing is automatic for every matching spoiler on a loaded page; there is no
per-spoiler opt-in, settings dialog, or hide-again button. Disable the script
and reload to restore Steam's original spoiler behavior. It stores no preferences
or page content and makes no network requests or uploads.
