# Youtube-shorts-switcher.user.js

[`userscripts/Youtube-shorts-switcher.user.js`](../userscripts/Youtube-shorts-switcher.user.js) is a Tampermonkey userscript that adds a Shorts action-column button and configurable hotkey to open the current YouTube Short in the normal watch player.

Current documented release: `2.8.1.1`.

## What It Does

- adds a round `Full` button to the Shorts actions column
- adds a keyboard shortcut for switching a Short to the normal `/watch` player
- works by converting the Shorts URL into the standard watch URL
- keeps watching the page so it still works after YouTube navigation changes

## Where It Works

- `www.youtube.com`
- `m.youtube.com`

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`userscripts/Youtube-shorts-switcher.user.js`](../userscripts/Youtube-shorts-switcher.user.js).
3. Create a new userscript in Tampermonkey and paste the file contents.
4. Save it, then open a YouTube Shorts page.

## Basic Usage

After install, you get two ways to switch a Short into the full player:

- click the `Full` button in the Shorts action column
- press the configured hotkey

## Default Hotkey

The default hotkey in the script is:

```text
W
```

If you want a different key, edit the `HOTKEY` value near the top of the script.

Examples:

- `W`
- `Shift+W`
- `Ctrl+Alt+W`
- `Enter`
- `F2`

## Example

If you are watching:

```text
https://www.youtube.com/shorts/VIDEO_ID
```

the script sends you to the normal player version:

```text
https://www.youtube.com/watch?v=VIDEO_ID
```

## Good To Know

- It only acts when a Shorts page is active.
- The hotkey does not fire while you are typing in an input or text box.
- There are no on-screen settings menus. If you want a different hotkey, edit the script constant directly.
