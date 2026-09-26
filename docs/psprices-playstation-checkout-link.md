# PSPrices-PlayStation-Checkout-Link.user.js

[`PSPrices-PlayStation-Checkout-Link.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-PlayStation-Checkout-Link.user.js) is a Tampermonkey userscript that replaces PSPrices paywalled avatar/theme purchase panels, availability placeholders, or unavailable-store warnings with custom regional PS Store checkout-link panels, adds an unlocked badge, and hides unlock prompts and the site-wide ads-free and publisher-filter promos.

Current documented release: `1.1.2`.

## Screenshots

Click a preview to open its full-resolution image.

The purchase panel for **Afterparty – Wormhorn Avatar** before (left) and after
(right). The script replaces the access-purchase prompt with the regional
PlayStation Store checkout card.

<a href="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/psprices-checkout-link/comparison.png"><img src="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/psprices-checkout-link/comparison.png" alt="PSPrices purchase panel before and after applying Checkout Link" width="900"></a>

The advanced settings panel in dark appearance:

<a href="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/psprices-checkout-link/settings.png"><img src="https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/psprices-checkout-link/settings.png" alt="PSPrices Checkout Link advanced settings in dark appearance" width="560"></a>

Light appearance: [view settings](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/psprices-checkout-link/settings-light.png).

## Advanced Settings

Choose **PSPrices Checkout Link settings** from your userscript manager's menu.
The menu is available throughout PSPrices, including its home page. Checkout
cards still require a supported regional product page.
There is no floating settings button.

While settings is open, the background page cannot be clicked, hovered, focused,
or scrolled. Long settings content scrolls inside the panel. Closing restores
page interaction without activating anything under the dismissal click.

Opening settings does not preselect a button, slider, or field. Keyboard focus
starts on the panel heading; press Tab to move to the first control, or
Shift+Tab to reach the last. Controls keep a visible focus indicator when you
navigate to them.

The translucent backdrop follows the page’s visible background: gentle black
shading over a light page, or a faint white veil over a dark page. The script
checks the page colors when you open settings. If they cannot be determined,
it uses the browser’s preferred appearance, with dark as the fallback.

The panel follows your browser's preferred light or dark appearance and updates
when that preference changes. Text and controls use matching colors; the
advanced-user warning stays yellow/amber with readable text in both themes.
Dark mode is the fallback when no supported theme preference is exposed. Light
mode uses near-black text on light surfaces and dark text on the pale-yellow
warning. Dark mode uses light text on dark surfaces and bright-yellow text on
the dark-amber warning.

> [!WARNING]
> **Advanced users only.** Changing these settings can break checkout-link
> generation or fallback behavior. You are responsible for problems caused by
> your changes.

The panel contains the nine controls documented below:
request timeout, click cooldown, clipboard callback wait, fade duration,
link-generation delay, logging level, diagnostics visibility, and the two
forced fallback modes.

Click **Save settings**, then reload the page when ready to apply the saved
values. Changes do not reconfigure a checkout request already in progress.
Closing without saving leaves stored settings unchanged. Clicking outside the
panel or pressing Escape also closes it and discards unsaved edits. Reopening
shows the last saved values.

**Reset defaults** restores and saves all nine built-in values. Reload to apply
them. Saving or resetting settings does not open a checkout link, copy anything
to the clipboard, or trigger an Add to Cart action.

Preferences live in the userscript manager's per-script storage and survive
script updates. Missing settings receive their defaults; saved values are not
replaced merely because source defaults change. The panel validates input and
reports failed saves. The code examples below identify the settings and their
built-in values; use the panel to customize them.

The settings panel requires native modal-dialog support (`showModal`). If the
browser cannot open a modal, settings stay closed so the script does not expose
an interactive panel over an unblocked page. Use a browser with that support.

## PlayStation Store Setup and Redirect Caveat

Before using any PSNPrices Add to Cart button:

1. Open [https://store.playstation.com](https://store.playstation.com).
2. Sign in to the PlayStation account for the region being used on PSNPrices.
3. Ideally, leave the signed-in PlayStation Store page open in another tab.

The generated checkout link does not sign the user in. Opening the store first gives the checkout redirect an existing PlayStation session and makes the Add to Cart flow more reliable.

The PlayStation checkout redirect may occasionally display an error page even when the item was added successfully.

If this happens, return to the signed-in PlayStation Store tab, refresh it, and check the shopping cart before trying the Add to Cart action again.

> Some items cannot be added, or will not remain in the cart, because their regional SKU is no longer valid on Sony's servers.

## What It Does

- reads the public base product SKU and highest published JSON-LD offer price
- resolves the regional full PlayStation SKU through Sony's public store endpoint
- builds a regional `checkout.playstation.com/add/` URL
- replaces the first supported avatar or theme purchase panel with a PSPrices-style checkout card
- uses PSPrices' native `game-detail-card` surface and corners for the replacement panel
- accepts both current `shrink-0` and legacy `flex-shrink-0` direct theme purchase wrappers
- also replaces the PlayStation Store availability loading placeholder or unavailable warning column when no native buy block is present
- keeps the Add to Cart button disabled until a validated checkout URL is ready
- shows the specific checkout-link failure reason in the card status area when Sony lookup fails
- supports PSPrices product pages across all configured PlayStation regions
- preserves the visual-map and SKU panels outside the replaced purchase target
- blocks the native PlayStation Store availability loading placeholder and unavailable warning from painting before replacement
- blocks the matching bottom Buy Unlocked banner from painting on supported product pages
- blocks the avatar collection's `Avatars available for purchase` bridge before it paints
- permanently hides PSPrices' ads-free and publisher-filter Pro promos site-wide, including collection pages, avatar/theme product pages, and dynamically mounted notices
- adds a dominant `🏴‍☠️ unlocked` badge beside the PSPrices header wordmark

## Where It Works

The userscript loads across PSNPrices so the `🏴‍☠️ unlocked` header badge can be displayed globally:

```text
https://psprices.com/*
https://www.psprices.com/*
```

Checkout-panel replacement remains restricted to supported `/region-*/game/*` product pages containing one exact avatar/theme buy structure, or one PlayStation Store availability placeholder/unavailable warning where the buy block would normally be. On other pages, the script maintains the global header badge and cosmetic suppression without inserting a checkout card.

On regional `/collection/*` pages, the script also permanently hides `[data-test-id="avatar-collection-bridge"]`. This covers collection routes such as `/collection/avatars`, `/collection/ps4-avatars`, and equivalent paths in every region.

The same document-start cosmetic stylesheet permanently hides notices with `data-test-id="notice-tip"` and either `data-notice="ads-free"` or `data-notice="no-ai-slop"` wherever PSPrices mounts them, including collection pages and individual avatar/theme product pages. These identify the ad-free browsing and publisher-filter Pro promos. Other notice types remain visible.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open the [raw userscript](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-PlayStation-Checkout-Link.user.js).
3. Confirm the installation in the userscript manager.
4. Open a supported PSPrices avatar or theme product page.

## How Checkout-Link Generation Works

PSPrices publishes public product data in JSON-LD:

```html
<script type="application/ld+json">
```

The userscript finds an unambiguous `Product` entry and reads:

- the base PlayStation product SKU
- the published offer price and currency when available

For a complete valid `lowPrice`/`highPrice` range, the card displays the higher bound. If exactly one bound is present and valid, it is normalized as both bounds. If neither bound is present, a valid `price` value is accepted.

The normalized zero upper bound displays `Free`; invalid or conflicting offers display `Price unavailable`, and an invalid bound never falls back to another field. This published JSON-LD value is not a guarantee of the live amount charged by the PlayStation Store. No price is inferred from labels or from a separate network request.

It validates the product ID and region against the URL, canonical link, product container, and available page-region data. It then requests the matching full regional SKU from:

```text
https://store.playstation.com/store/api/chihiro/00_09_000/container/
```

A returned SKU must match the page's exact base SKU plus Sony's four-character alphanumeric regional suffix. Supported Sony examples include `-E001`, `-U001`, and `-UA01`. The complete suffix is taken from Sony's `default_sku.id`; it is not guessed or generated locally.

The local validator remains as a response-integrity check. It rejects an empty SKU, a SKU belonging to another base product, a missing or incorrectly sized suffix, and suffixes containing URL/path punctuation. It does not require one specific letter-and-digit arrangement within Sony's four-character suffix.

After validation, the script creates:

```text
https://checkout.playstation.com/add/FULL_SKU?clientId=...
```

Only successfully validated full SKUs are cached for the current page session. Failures, malformed responses, and mismatched SKUs are never cached.

## Rendering and Timing

The script starts at `document-start` to install bootstrap/cosmetic suppression and the global header badge. It defers purchase-target validation, stabilization, and replacement while the initial HTML is still being parsed; `DOMContentLoaded` schedules the normal mounting pass so parser-owned purchase children finish loading before replacement.

The completed wrapper then fades into view, and later DOM, HTMX, and route changes remain event-driven. Related lazy fragments outside the validated product targets leave the checkout card intact.

The bottom sticky Buy Unlocked banner is suppressed by bootstrap CSS as soon as its matching `stickyReveal('#avatar-buy-block')` element is parsed. It remains `display: none` on supported avatar and theme product pages, preventing the native banner from flashing before the JavaScript mount completes.

The avatar collection bridge uses a separate permanent cosmetic stylesheet installed at `document-start`. This gives it traditional content-blocker behavior and prevents the `Avatars available for purchase` panel from flashing while collection pages render.

The same permanent stylesheet suppresses both the ad-free browsing notice and the “Cleaner catalog, less noise” notice promoting one-click hiding of mass-release publishers. It identifies their containers by the exact attributes above, without matching message text, and applies as soon as a matching notice is inserted, including during later dynamic page updates.

The timing controls in advanced settings have these built-in values:

```js
const REQUEST_TIMEOUT_MS = 20_000;
const CLICK_COOLDOWN_MS = 3_000;
const CLIPBOARD_CALLBACK_WAIT_MS = 1_000;
const WRAPPER_ENTER_MS = 450;
const LINKGEN_START_DELAY_MS = 150;
```

Their purposes are:

- `REQUEST_TIMEOUT_MS`: maximum time allowed for Sony's regional-SKU request
- `CLICK_COOLDOWN_MS`: minimum disabled period after accepting an Add to Cart click
- `CLIPBOARD_CALLBACK_WAIT_MS`: wait used for callback-style userscript clipboard APIs
- `WRAPPER_ENTER_MS`: checkout-wrapper fade-in duration
- `LINKGEN_START_DELAY_MS`: additional delay after the fade completes before Sony/SKU work begins

The sequence is:

1. validate and mount the checkout card
2. fade the wrapper in for `WRAPPER_ENTER_MS`
3. wait `LINKGEN_START_DELAY_MS`
4. begin regional SKU and checkout-link generation
5. turn the Add to Cart button blue only after the checkout URL is valid

The initial action remains grey and disabled. During lookup, the card status reports `Resolving regional PlayStation SKU...`. Errors and fallback results use the same status area.

## Optional Flags

The flags in advanced settings have these built-in values:

```js
const LOG_LEVEL = 'info';
const SHOW_DIAGNOSTICS = false;
const FORCE_CLIPBOARD_FALLBACK = false;
const FORCE_MANUAL_LINK_FALLBACK = false;
```

### `LOG_LEVEL`

Supported values:

- `'info'`: normal startup, state changes, warnings, categorized failures, HTTP status information, and final results
- `'verbose'`: the complete safe flow, including route checks, selector decisions, public product data, request lifecycle, cache decisions, navigation handling, popup behavior, and clipboard fallback

Unknown values fall back to normal `info` behavior.

Logging does not intentionally include cookies, account/session data, CSRF values, credential-bearing headers, or raw Sony response bodies.

### `SHOW_DIAGNOSTICS`

Set this to `true` to display the technical diagnostics inside the checkout card:

- selected Sony locale, such as `en-AU`
- regional full SKU or its current resolution state

This only changes visibility. It does not change checkout generation.

### `FORCE_CLIPBOARD_FALLBACK`

Set this to `true` to test the clipboard fallback after clicking Add to Cart:

```js
const FORCE_CLIPBOARD_FALLBACK = true;
```

The script skips opening a new tab, copies the checkout URL, changes the button to `Link copied`, and displays the clipboard result in the status area.

### `FORCE_MANUAL_LINK_FALLBACK`

Set this to `true` to test the final Manual Link fallback:

```js
const FORCE_MANUAL_LINK_FALLBACK = true;
```

The script skips both new-tab creation and clipboard copying. It renders a clickable Manual Link beneath the button, changes the button to `Manual Link Rendered`, and displays:

```text
New tab blocked — use the Manual Link above.
```

If both force flags are `true`, Manual Link mode takes priority.

The force flags only alter what happens after a valid Add to Cart click. They do not bypass product validation or checkout-link generation.

## Normal Click and Fallback Flow

With both force flags disabled:

1. Add to Cart opens a blank tab synchronously and assigns the validated checkout URL.
2. If the tab cannot be opened, the script attempts clipboard copying.
3. If clipboard copying also fails, it renders the Manual Link.

The temporary successful button states use PSPrices' native success styling:

- `Opened`
- `Link copied`
- `Manual Link Rendered`

After the click cooldown, the button returns to the blue Add to Cart state when the same checkout context is still valid.

## Header Badge

The script adds this badge immediately after the PSPrices wordmark on every PSNPrices page where the standard header exists:

```text
🏴‍☠️ unlocked
```

It uses PSPrices' native badge classes, including `bg-blue-700` for light mode and `dark:bg-blue-600` for dark mode.

If the native `unlocked` badge already exists, the userscript replaces it with its own marked version so the pirate-flag badge remains authoritative. Header remounts are detected without creating duplicate badges.

## Compatibility With Other PSPrices Userscripts

This userscript can run alongside:

- [`PSPrices-Show-Product-SKU.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js)
- [`PSPrices-Collection-Live-Search.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Collection-Live-Search.user.js)

The checkout script replaces only the first exact supported purchase target. It leaves the surrounding buy wrapper and separate SKU panel available. The SKU userscript prefers its own blue card and hides the native locked or unlocked SKU panel after a valid replacement mounts, restoring the native panel if no replacement can mount. The SKU script owns that behavior without the checkout script treating it as a new purchase target.

The collection live-search script primarily owns the canonical avatar/theme collection pages and fetches product pages only for visible result hydration. The checkout script primarily owns supported product-page purchase targets, so the two scripts do not compete for the same mounted UI.

## Failure Handling

The Add to Cart button remains disabled when:

- the userscript manager does not expose a supported cross-origin request API
- product, region, locale, or target data is missing or contradictory
- Sony returns HTTP, timeout, network, redirect, JSON, or SKU-validation failures
- a correct checkout URL cannot be constructed

Safe error information is written to the browser console. The card displays a shorter user-facing status such as:

```text
Not found on PSN Store.
```

Navigation and dynamic PSPrices updates invalidate stale requests, checkout URLs, click attempts, and pending LinkGen timers before another supported context is mounted.

## Permissions

The metadata grants support both modern and legacy userscript-manager APIs:

- `GM.xmlHttpRequest` and `GM_xmlhttpRequest`: anonymous Sony regional-SKU requests
- `GM.setClipboard` and `GM_setClipboard`: clipboard fallbacks
- `GM_log`: optional userscript-manager log mirroring
- `GM.getValue` / `GM_getValue` and `GM.setValue` / `GM_setValue`: saved advanced preferences
- `GM.registerMenuCommand` / `GM_registerMenuCommand`: access to the settings panel
- `@connect store.playstation.com`: permission for the Sony lookup host

Sony requests are sent without account cookies or credential-bearing headers.

## Scope of Account and Purchase Changes

The replacement cards, hidden prompts, and `🏴‍☠️ unlocked` badge are local page
changes. They do not purchase a PSPrices subscription or change the account's
membership or server-side permissions.

Regional SKU lookup happens automatically after a supported product card mounts.
The request sends Sony the public product identifier and selected locale; the
successful result is cached in memory for that page session. Advanced preferences
are saved separately in userscript-manager storage.

The cart action requires a click. Opening the generated link may add the item
to the signed-in PlayStation account's cart through Sony's checkout redirect;
the script does not confirm an order or pay for an item. A clipboard fallback
replaces the clipboard with that checkout URL only after the action is clicked.
The manual-link fallback waits for the user to open the displayed link.

Disabling the script and reloading restores the native PSPrices page. It does
not undo an item already added to the PlayStation cart. Saved preferences remain
in the manager until reset or removed there.
