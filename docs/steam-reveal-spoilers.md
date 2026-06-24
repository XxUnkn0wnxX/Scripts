# Steam-Reveal-Spoilers.user.js

[`userscripts/Steam-Reveal-Spoilers.user.js`](../userscripts/Steam-Reveal-Spoilers.user.js) is a Tampermonkey userscript that automatically reveals Steam Community spoiler text by unwrapping spoiler spans on page load and dynamic updates.

Current documented release: `1.0.0.1`.

## What It Does

- finds Steam spoiler spans such as `span.bb_spoiler`
- unwraps the hidden spoiler content so it becomes readable
- watches page updates so newly loaded spoilers are also revealed
- handles Steam's dynamic page changes after navigation

## Where It Works

- `steamcommunity.com`

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`userscripts/Steam-Reveal-Spoilers.user.js`](../userscripts/Steam-Reveal-Spoilers.user.js).
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
