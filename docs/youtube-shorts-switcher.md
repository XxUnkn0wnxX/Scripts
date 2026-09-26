# Youtube-shorts-switcher.user.js

[`Youtube-shorts-switcher.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Youtube-shorts-switcher.user.js) is a Tampermonkey userscript that adds a Shorts action-column button and configurable hotkey to open the current YouTube Short in the normal watch player.

Current documented release: `2.9.3`.

## Screenshots

Click a preview to open its full-resolution image.

The script adds **Full** above the existing actions on a public Short. Playback
is paused in this capture.

<a href="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/youtube-shorts-switcher/after.png"><img src="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/youtube-shorts-switcher/after.png" alt="YouTube Short with the Full player action added" width="900"></a>

Record a shortcut or restore `W` with **Reset defaults**. The settings panel
follows the browser's preferred appearance.

<a href="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/youtube-shorts-switcher/settings.png"><img src="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/youtube-shorts-switcher/settings.png" alt="YouTube Shorts shortcut settings in dark appearance" width="420"></a>

Light appearance: [view settings](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/youtube-shorts-switcher/settings-light.png).

## What It Does

- adds a round `Full` button to the Shorts actions column
- adds a keyboard shortcut for switching a Short to the normal `/watch` player
- lets you record a shortcut in a settings dialog and saves it through your userscript manager
- works by converting the Shorts URL into the standard watch URL
- keeps watching the page so it still works after YouTube navigation changes

## Where It Works

- `www.youtube.com`
- `m.youtube.com`

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`Youtube-shorts-switcher.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Youtube-shorts-switcher.user.js).
3. Create a new userscript in Tampermonkey and paste the file contents.
4. Save it, then open a YouTube Shorts page.

## Basic Usage

After install, you get two ways to switch a Short into the full player:

- click the `Full` button in the Shorts action column
- press the configured hotkey

## Shortcut Settings

Choose **YouTube Shorts settings** from your userscript manager's menu. There
is no floating settings button; the **Full** action button remains in the
Shorts actions column.

The settings menu is available throughout YouTube, including the home page,
regular video pages, and Shorts. It does not require an active Short.

While settings is open, the background page cannot be clicked, hovered, focused,
or scrolled. Any long settings content scrolls inside the panel. Closing restores
normal page interaction without activating anything under the dismissal click.

Opening settings does not preselect a button, slider, or field. Keyboard focus
starts on the panel heading; press Tab to move to the first control, or
Shift+Tab to reach the last. Controls keep a visible focus indicator when you
navigate to them.

The translucent backdrop follows the page’s visible background: gentle black
shading over a light page, or a faint white veil over a dark page. The script
checks the page colors when you open settings. If they cannot be determined,
it uses the browser’s preferred appearance, with dark as the fallback.

The settings panel follows your browser's preferred light or dark appearance,
including changes while it is open. Text, buttons, and status messages adapt
to remain readable in either theme.
Dark mode is the fallback when no supported theme preference is exposed. Light
backgrounds use near-black text, and dark backgrounds use light text.

1. Click **Record shortcut**.
2. Press the key or combination you want to use, including any Ctrl, Alt/Option,
   Shift, or Cmd/Meta modifiers.
3. The captured shortcut applies and saves immediately. Close the panel to use it.

For example, you can record `W`, `Shift+W`, `Ctrl+Alt+W`, a function key, or an
arrow key. Pressing modifier keys alone does not save a shortcut. Escape or
**Cancel recording** stops recording and keeps the previous shortcut. Closing
the panel also cancels unfinished recording.

Modifiers must match exactly: `W` and `Shift+W` are different bindings. Recording
ignores held-key repeats, unfinished text composition, dead keys, and keys the
browser cannot identify.

Choose **Close** or click outside the panel to dismiss it. Escape also closes
the panel when shortcut recording is inactive. Shortcuts already recorded
remain saved; closing cancels an unfinished recording.

**Reset defaults** immediately restores and saves the default shortcut, `W`.
The **Full** button's tooltip updates when the shortcut changes. Saved settings
survive page reloads and script updates. The panel reports storage failures;
the current page can still use the newly selected shortcut.

Be mindful of shortcuts already assigned to your browser, operating system,
or other apps. They may handle a combination before the userscript receives
it; choose a different shortcut if there is a conflict.

The settings panel requires native modal-dialog support (`showModal`). If the
browser cannot open a modal, settings stay closed so the script does not expose
an interactive panel over an unblocked page. Use a browser with that support.

## Built-in Default

The default hotkey in the script is:

```text
W
```

Use the settings panel to change the shortcut. The `HOTKEY` value near the top
of the source defines the initial and reset default; changing it does not
replace a shortcut already saved in the userscript manager.

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

- The player-switch action only acts when a Shorts page is active; settings remain available on other YouTube pages.
- The hotkey does not fire while you are typing in an input, text box, or editable content, or while the settings dialog is open.
- Recording a shortcut does not open the full player. The new shortcut becomes usable after you close settings.
- Preferences use the userscript manager's per-script storage; the script makes no network requests to save settings.

## Permissions and Data

- `GM.getValue` / `GM_getValue` read this script's saved shortcut.
- `GM.setValue` / `GM_setValue` save a recorded shortcut or an explicit reset.
- `GM.registerMenuCommand` / `GM_registerMenuCommand` expose settings on the matched desktop and mobile YouTube hosts.

The script inspects the current route and rendered Shorts player to place its
button. Pressing the shortcut or clicking **Full** navigates the current tab to
`/watch?v=VIDEO_ID` on the same YouTube host. It does not retain the Shorts URL's
other parameters or transfer the playback position. Navigation lets YouTube
load its normal player; the script itself makes no background network requests,
uploads viewing data, or loads remote code. Only the shortcut is saved.

Button placement depends on YouTube's rendered player markup, so a different
mobile or experimental layout may not expose the same action column. Settings
remain available independently of that column. Disabling the script and
reloading removes its controls; saved preferences remain in the manager.
