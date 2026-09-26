# StackExchange-Reveal-Spoilers.user.js

[`StackExchange-Reveal-Spoilers.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/StackExchange-Reveal-Spoilers.user.js) is a Tampermonkey userscript that automatically reveals Stack Exchange spoiler blocks by applying the site's visible spoiler class to existing and dynamically added spoilers.

Current documented release: `1.0.1.3`.

## Screenshots

Click the preview to open its full-resolution image.

The same Arqade answer before (left) and after (right) the script runs. All
three spoiler blocks become visible automatically, including the text and
video links. The crops show the answer area at its original resolution.

<a href="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/stackexchange-reveal-spoilers/comparison.png"><img src="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/stackexchange-reveal-spoilers/comparison.png" alt="Arqade answer with three hidden spoiler blocks before and revealed text and links after" width="900"></a>

Full-resolution crops: [hidden](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/stackexchange-reveal-spoilers/before.png) · [revealed](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/stackexchange-reveal-spoilers/after.png).

Example: [user3389's answer to “What happens when the God King is defeated?”](https://gaming.stackexchange.com/questions/13719/what-happens-when-the-god-king-is-defeated/13722#13722) on Arqade, discussing *Infinity Blade*.

## What It Does

- finds spoiler elements that use the `.spoiler` class
- adds the `is-visible` class so the hidden text is shown
- starts early at `document-start`
- watches for new spoiler blocks added later by page updates

## Where It Works

- `stackexchange.com` and its subdomains, including individual communities such as `gaming.stackexchange.com`
- `stackoverflow.com`
- `superuser.com`
- `serverfault.com`
- `askubuntu.com`
- `mathoverflow.net`
- `stackapps.com`
- `stackauth.com`

The metadata matches HTTP and HTTPS pages on these hosts. The standalone hosts
listed above use exact host matches; their other subdomains are not separately
included. Embedded frames are excluded with `@noframes`.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`StackExchange-Reveal-Spoilers.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/StackExchange-Reveal-Spoilers.user.js).
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

## Permissions and Page Changes

The script uses `@grant none` and requests no userscript-manager APIs. It adds
`is-visible` to `.spoiler` elements and relies on the site's CSS to reveal them.
It observes added elements and class changes, including a spoiler becoming
hidden again, then reapplies visibility. It also checks restored and newly
loaded pages.

Revealing is automatic for all matching spoiler blocks. There is no settings
dialog, per-spoiler opt-in, or hide-again control. Disable the script and reload
to restore the site's spoiler behavior. It does not store preferences, fetch
answers, send page content anywhere, or change the text of an answer.
