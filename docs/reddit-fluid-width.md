# reddit-fluid-width.user.js

Install [`reddit-fluid-width.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/reddit-fluid-width.user.js) with Tampermonkey or Violentmonkey to apply a constrained fluid layout only on Reddit post/comment routes while leaving feeds and landing pages completely native.

Current documented release: `1.0.0`.

## What It Does

- targets only `/r/<community>/comments/<post-id>/...` post routes
- keeps feed/landing routes such as `https://www.reddit.com/r/satisfactory/` unchanged
- widens only `#subgrid-container` and the direct `.main-container.fixed-sidebar` row
- keeps the native right rail width at `316px` while growing only the main post column
- supports two post-layout modes: pinned-right geometry and centered geometry
- keeps the fluid style active while comments expand or load, and synchronizes it on SPA and back/forward route changes
- includes no network calls and no storage reads/writes

The default mode pins the post workspace inline-end/right edge to `100%` with `0px` outer margin and changes only the left edge as width adjusts. Set `pinRightSidebar` to `false` to center the whole grid as Reddit's left nav expands or collapses.

## Where It Works

The userscript loads on Reddit `/r/*` routes so it is already present when Reddit opens a post through client-side navigation. Style still applies only on the strict route pattern:

```text
https://www.reddit.com/r/<community>/comments/<post-id>/...
```

`<community>` is matched case-insensitively after `/r/`, and `comments` must follow immediately.

## Route Gating (SPA)

- style is gated by a root attribute set only when the strict path regex matches
- attribute is removed when navigation leaves the post route
- hooks:
  - initial startup sync
  - wrapped `pushState`
  - wrapped `replaceState`
  - `popstate`
  - `pageshow`

No DOM-wide observers or resize loops are used, and no transition overrides are applied. Comment expansion and in-thread pagination preserve the style while the route remains active. CSS percentages and `min()`/`max()` are recalculated by the browser as the window or Reddit workspace changes.

## Configuration

Edit near the top of the script:

```js
const CONFIG = Object.freeze({
  contentWidthPercent: 95,
  minGutterPx: 32,
  pinRightSidebar: true,
});
```

- `contentWidthPercent` controls the max container percentage width
- `minGutterPx` controls minimum left/start safety gutter in pinned mode; in centered mode it is used on both sides
- `pinRightSidebar` controls geometry mode:
  - `true` (default): pins the inline-end/right edge at `100%` (`0px` outer margin), only the left edge moves, and only one gutter is subtracted
  - `false` (opt-in): keeps centered margins (`margin-inline: auto`) so width changes affect both sides

The script validates values at runtime:

- width percentage is clamped to `1-100%`
- gutter is clamped to `16-128px`
- `pinRightSidebar` is treated as boolean and defaults to `true`

## Layout Modes

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

## Safety

- `pinRightSidebar` only changes geometry math. It does not click, expand, pin, or resize any Reddit UI panel; it only rewrites two CSS selectors under post-only scope.

## Technical Notes

- only two selector targets are styled:
  - `#subgrid-container > .main-container.fixed-sidebar`
  - `#subgrid-container`
- no DOM structure changes
- the style block is inserted once and reused for the page lifetime
- `#sticky-comment-composer-wrapper`, left nav, back-button positioning, feeds, and comments are not directly modified

### Floating back button behavior

The floating back-button offset in wide layouts is protected by the fixed `1120px` baseline plus a configurable start/left safety gutter in pinned mode, or equal per-side gutters in centered mode.

## Basic Install

1. Install a userscript manager such as Tampermonkey or Violentmonkey.
2. Open the script page on your preferred host (Greasy Fork or OpenUserJS) and click **Install**.
3. Open any post URL matching `https://www.reddit.com/r/<community>/comments/<post-id>/...`.

## Compatibility and Safety

- no external dependencies
- no tracking beacons
- no data collection
- no remote settings storage
- no mutation polling or timers
- compatible with current Tampermonkey and Violentmonkey releases

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
