# reddit-fluid-width.user.js

Install [`reddit-fluid-width.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/reddit-fluid-width.user.js) with Tampermonkey or Violentmonkey to apply a constrained fluid layout only on Reddit post/comment routes while leaving feeds and landing pages completely native.

Current documented release: `1.1.1`.

## Screenshots

The same public post at Reddit's native width (left) and with the default 95%
fluid width (right). The post column expands while the sidebars remain visible.

![Reddit post before and after applying fluid width](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/reddit-fluid-width/comparison.png)

Full-resolution originals: [before](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/reddit-fluid-width/before.png) · [after](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/reddit-fluid-width/after.png).

The settings panel in dark appearance:

![Reddit Fluid Width settings in dark appearance](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/reddit-fluid-width/settings.png)

<details>
<summary>Settings in light appearance</summary>

![Reddit Fluid Width settings in light appearance](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/reddit-fluid-width/settings-light.png)

</details>

## What It Does

- targets only `/r/<community>/comments/<post-id>/` post routes and their descendant paths
- keeps feed/landing routes such as `https://www.reddit.com/r/satisfactory/` unchanged
- widens only `#subgrid-container` and the direct `.main-container.fixed-sidebar` row
- keeps the native right rail width at `316px` while growing only the main post column
- supports two post-layout modes: pinned-right geometry and centered geometry
- keeps the fluid style active while comments expand or load, and synchronizes it on SPA and back/forward route changes
- provides live settings through the userscript manager's menu, with saved preferences and **Reset defaults**
- makes no network calls; preferences are stored through the userscript manager
- visible `#left-sidebar-container` controls fluid width mode:
  - when a visible rail is present, width uses configured `contentWidthPercent` (default `95%`)
  - when rail content is not visible (empty shell, CSS-hidden, visibility-hidden/collapsed, zero-size, or fully off-left), `--reddit-fluid-width` uses `noLeftSidebarContentWidthPercent` (default `95%`)

The default mode pins the post workspace inline-end/right edge to `100%` with `0px` outer margin and changes only the left edge as width adjusts. Set `pinRightSidebar` to `false` to center the whole grid as Reddit's left nav expands or collapses.

## Where It Works

The userscript loads throughout `reddit.com` and `www.reddit.com` for settings access and client-side navigation. Style applies only on the canonical post route and its deeper in-post paths: `https://www.reddit.com/r/<community>/comments/<post-id>/`

`<community>` is matched case-insensitively after `/r/`, and `comments` must follow immediately.

## Route Gating (SPA)

- style is gated by a root attribute set only when the strict path regex matches
- attribute is removed when navigation leaves the post route
- sidebar state is tracked on post routes only from DOM/geometry inspection of `#left-sidebar-container`:
  - requires `display !== none`
  - requires `visibility` strictly `visible`
  - requires `getBoundingClientRect().width > 0`
  - requires `getBoundingClientRect().height > 0`
  - requires `rect.right > 0`
  - requires at least one descendant element to pass the same visibility checks
  - if any check fails, no-left-sidebar mode activates and `--reddit-fluid-width` becomes `noLeftSidebarContentWidthPercent`
- this is DOM/visible-geometry detection only; no login/account/cookie inference is used
- it works with rendered layouts in both logged-in and logged-out views based on whether the rail is actually present
- hooks:
  - initial startup sync
  - DOM-ready sync (guards against false no-sidebar detection during parse)
  - `resize`
  - wrapped `pushState`
  - wrapped `replaceState`
  - `popstate`
  - `pageshow`
  - one coalesced `MutationObserver` for left-rail relevant insert/remove/attribute changes
    - attributes observed: `style`, `class`, `hidden`, `aria-hidden`
    - callback is filtered to left-sidebar node or its ancestors, descendant insert/remove, and descendant class/style/hidden change transitions so empty↔populated shell updates are captured
- rendered DOM changes also resynchronize the route when sandboxed history wrappers cannot observe page-side navigation, and restore a removed settings host
- observer callbacks are relevance-filtered, and layout reads are coalesced to at most one animation frame

No layout polling or transition overrides are used. Comment expansion and in-thread pagination preserve the style while the route remains active. CSS percentages and `min()`/`max()` are recalculated by the browser as the window or Reddit workspace changes. Settings saves use a short debounce to avoid writing every intermediate slider value.

## Configuration

Choose **Reddit Fluid Width settings** from your userscript manager's menu.
The menu is available on every page of `reddit.com` and `www.reddit.com`,
including the home page and feeds. Fluid width still applies only to supported
post/comment routes.

While settings is open, clicks, hover, keyboard focus, and scrolling stay with
the panel. Long content scrolls inside it. Closing restores page interaction
without activating a background control under the dismissal click.

The translucent backdrop follows the page’s visible background: gentle black
shading over a light page, or a faint white veil over a dark page. The script
checks the page colors when you open settings. If they cannot be determined,
it uses the browser’s preferred appearance, with dark as the fallback.

There is no floating settings button. The panel follows your browser's preferred
light or dark appearance, including changes while it is open. Dark mode is the
fallback when no supported theme preference is exposed. Light mode uses
near-black text and dark mode uses light text. The panel contains:

- separate percentage sliders and numeric fields for layouts with and without the left sidebar
- a minimum gutter control
- a **Pin right sidebar** checkbox
- **Reset defaults** and **Close** buttons

The sliders and numeric arrows use whole-percentage steps. For finer control,
enter a decimal such as `95.1` directly in either percentage field. Changes
apply live without reloading. The page uses the percentage for its currently
visible sidebar state; the other percentage is saved for when that state changes.
The gutter and pin checkbox also update the layout immediately.

**Reset defaults** restores both percentages to `95%`, the gutter to `32px`, and
right-side pinning to enabled. It applies and saves these values immediately.
Clicking outside the panel, choosing **Close**, or pressing Escape keeps changes
already made and saves any pending change.

Preferences are stored separately from the script source. Updates retain saved
values, including decimals and an unchecked pin setting. Only missing settings
are initialized from the defaults. Editing the source defaults after preferences
have been saved does not replace those preferences; use the panel or
**Reset defaults**. If saving is unavailable or fails, the panel reports that
changes only apply to the current page.

The built-in defaults near the top of the script are:

```js
const CONFIG = Object.freeze({
  contentWidthPercent: 95,
  noLeftSidebarContentWidthPercent: 95,
  minGutterPx: 32,
  pinRightSidebar: true,
});
```

- `contentWidthPercent` controls the max container percentage width while a visible left sidebar is present (default `95%`).
- `noLeftSidebarContentWidthPercent` controls the max container percentage width when the left rail is considered absent; default `95%`.
- Both width values are independently clamped to `1..100`:
  - `contentWidthPercent` falls back to `95` if invalid.
  - `noLeftSidebarContentWidthPercent` falls back to `95` if invalid.
- `minGutterPx` controls minimum left/start safety gutter in pinned mode; in centered mode it is used on both sides
- `pinRightSidebar` controls geometry mode:
  - `true` (default): pins the inline-end/right edge at `100%` (`0px` outer margin), only the left edge moves, and only one gutter is subtracted
  - `false` (opt-in): keeps centered margins (`margin-inline: auto`) so width changes affect both sides

Lowering `noLeftSidebarContentWidthPercent` in pinned-right mode creates a larger left inset while leaving the visible-sidebar mode unchanged.

The script validates values at runtime:

- `contentWidthPercent` is clamped to `1-100%` with a `95` fallback
- `noLeftSidebarContentWidthPercent` is also clamped to `1-100%` with an independent `95` fallback
- gutter is clamped to `16-128px`
- `pinRightSidebar` is treated as boolean and defaults to `true`

The settings panel requires native modal-dialog support (`showModal`). If the
browser cannot open a modal, settings stay closed so the script does not expose
an interactive panel over an unblocked page. Use a browser with that support.

## Layout Modes

Shared no-left-sidebar behavior (both geometry modes):

- `.grid-container:not(.grid-full) > #subgrid-container { grid-column: 1 / -1 !important; }`
- `#subgrid-container { max-width: none !important; }`
- the post workspace spans across Reddit's reserved flex-nav track and removes Reddit's old subgrid max-width cap only when the left rail is not rendered
- parent grid-template columns and the native `316px` right rail are unchanged; visible-sidebar mode keeps Reddit's normal tracked behavior

Pinned-right mode (`pinRightSidebar: true`):

- keeps `#subgrid-container`'s inline-end anchored at `100%` with `0px` outer margin
- uses left auto margin so width changes move the left edge first
- width clamp subtracts one gutter: `calc(100% - minGutterPx)`
- preserves the right rail at `316px` and does not resize nav panels
- `pinRightSidebar: true` is the default behavior

Centered mode (`pinRightSidebar: false`):

- uses `margin-inline: auto`
- width changes are distributed symmetrically by side
- keeps `#subgrid-container`, main column, and `316px` right rail centered as one cohesive grid
- width clamp subtracts two gutters: `calc(100% - 2 * minGutterPx)`
- still keeps the existing `1120px` baseline and the post-route scope
- automatically recalculates against Reddit's available workspace as the left nav expands or collapses
- `pinRightSidebar: false` is an opt-in behavior

Both modes stay within the available parent width, including at `100%`.
The `1120px` baseline is retained when it fits; a narrower available track takes
precedence so the workspace cannot overflow merely to preserve that baseline.

## Safety

- `pinRightSidebar` only changes geometry math. It does not click, expand, pin, or resize any Reddit UI panel; styling remains limited to `#subgrid-container` and its direct `.main-container.fixed-sidebar` row under post-only scope.

## Technical Notes

- Reddit layout styling targets only:
  - `#subgrid-container > .main-container.fixed-sidebar`
  - `#subgrid-container`
- Reddit's content structure is not rewritten; the script adds its own isolated settings dialog, with no parent grid-template overrides
- when no-left-sidebar is detected, the rule above lets the post workspace reclaim the full parent-grid span while keeping its right rail at `316px`
- the style block is inserted once and reused for the page lifetime
- `#sticky-comment-composer-wrapper`, left nav, back-button positioning, feeds, and comments are not directly modified

### Floating back button behavior

The floating back-button offset in wide layouts is protected by the `1120px` baseline when space permits, plus a configurable start/left safety gutter in pinned mode or equal per-side gutters in centered mode.

## Basic Install

1. Install a userscript manager such as Tampermonkey or Violentmonkey.
2. Open the script page on your preferred host (Greasy Fork or OpenUserJS) and click **Install**.
3. Open any post URL matching `https://www.reddit.com/r/<community>/comments/<post-id>/`; deeper in-post paths are supported too.

## Compatibility and Safety

- no external dependencies
- no tracking beacons
- no data collection
- settings use the userscript manager's per-script storage
- no layout polling; settings saves are debounced
- supports the legacy and modern GM storage/menu APIs used by Tampermonkey and Violentmonkey

## Permissions and Data

- `GM.getValue` / `GM_getValue` read this script's two percentages, gutter, and pin preference.
- `GM.setValue` / `GM_setValue` save those preferences and explicit resets.
- `GM.registerMenuCommand` / `GM_registerMenuCommand` expose settings throughout the two matched Reddit hosts.

Site-wide loading allows settings access and navigation into a post without a
full reload. It does not extend fluid styling to feeds or the home page. The
script observes the rendered route and sidebar geometry, adds its own styles
and dialog, and makes no network requests or uploads. Disabling it and reloading
restores Reddit's layout; saved preferences remain in the userscript manager.

## Example

If you open:

```text
https://www.reddit.com/r/satisfactory/comments/abc123/example-post/
```

the script applies the fluid post width.

If you return to:

```text
https://www.reddit.com/r/satisfactory/
```

the layout returns to native without the script's width changes.
