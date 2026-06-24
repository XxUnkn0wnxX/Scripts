# StackExchange-Reveal-Spoilers.user.js

[`userscripts/StackExchange-Reveal-Spoilers.user.js`](../userscripts/StackExchange-Reveal-Spoilers.user.js) is a Tampermonkey userscript that automatically reveals Stack Exchange spoiler blocks by applying the site's visible spoiler class to existing and dynamically added spoilers.

Current documented release: `1.0.1.3`.

## What It Does

- finds spoiler elements that use the `.spoiler` class
- adds the `is-visible` class so the hidden text is shown
- starts early at `document-start`
- watches for new spoiler blocks added later by page updates

## Where It Works

- `stackexchange.com`
- `stackoverflow.com`
- `superuser.com`
- `serverfault.com`
- `askubuntu.com`
- `mathoverflow.net`
- `stackapps.com`
- `stackauth.com`

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`userscripts/StackExchange-Reveal-Spoilers.user.js`](../userscripts/StackExchange-Reveal-Spoilers.user.js).
3. Create a new userscript in Tampermonkey and paste the file contents.
4. Save it, then reload a supported Stack Exchange page.

## Basic Usage

There is nothing to click after install.

When a page contains spoiler blocks, the script makes them visible automatically.

## Example

If a Stack Overflow answer uses hidden spoiler formatting, the script reveals that text as soon as the page loads instead of making you hover or click around it.

## Good To Know

- It is designed for Stack Exchange style spoiler markup only.
- It watches both initial page content and later DOM updates.
- There are no custom options or hotkeys in this script.
