# PSPrices-PlayStation-Checkout-Link.user.js

[`userscripts/PSPrices-PlayStation-Checkout-Link.user.js`](../userscripts/PSPrices-PlayStation-Checkout-Link.user.js) is a Tampermonkey userscript that replaces PSPrices paywalled avatar/theme purchase panels with custom regional PS Store checkout-link panels, adds an unlocked badge, and hides unlock prompts.

Current documented release: `1.0.4.1`.

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

- reads the public base product SKU and price from PSPrices' JSON-LD product metadata
- resolves the regional full PlayStation SKU through Sony's public store endpoint
- builds a regional `checkout.playstation.com/add/` URL
- replaces the first supported avatar or theme purchase panel with a PSPrices-style checkout card
- keeps the Add to Cart button disabled until a validated checkout URL is ready
- supports PSPrices product pages across all configured PlayStation regions
- preserves the visual-map and SKU panels outside the replaced purchase target
- blocks the matching bottom Buy Unlocked banner from painting on supported product pages
- blocks the avatar collection's `Avatars available for purchase` bridge before it paints
- adds a dominant `🏴‍☠️ unlocked` badge beside the PSPrices header wordmark

## Where It Works

The userscript loads across PSNPrices so the `🏴‍☠️ unlocked` header badge can be displayed globally:

```text
https://psprices.com/*
https://www.psprices.com/*
```

Checkout-panel replacement remains restricted to supported `/region-*/game/*` product pages containing one exact avatar or theme structure. On other pages, the script only maintains the global header badge and does not insert a checkout card.

On regional `/collection/*` pages, the script also permanently hides `[data-test-id="avatar-collection-bridge"]`. This covers collection routes such as `/collection/avatars`, `/collection/ps4-avatars`, and equivalent paths in every region.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open the [raw userscript](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/PSPrices-PlayStation-Checkout-Link.user.js).
3. Confirm the installation in the userscript manager.
4. Open a supported PSPrices avatar or theme product page.

## How Checkout-Link Generation Works

PSPrices publishes public product data in JSON-LD:

```html
<script type="application/ld+json">
```

The userscript finds an unambiguous `Product` entry and reads:

- the base PlayStation product SKU
- the current price and currency when available

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

The script starts at `document-start` and temporarily suppresses the shared PSPrices purchase wrapper while it validates and replaces the purchase target. The completed wrapper then fades into view.

The bottom sticky Buy Unlocked banner is suppressed by bootstrap CSS as soon as its matching `stickyReveal('#avatar-buy-block')` element is parsed. It remains `display: none` on supported avatar and theme product pages, preventing the native banner from flashing before the JavaScript mount completes.

The avatar collection bridge uses a separate permanent cosmetic stylesheet installed at `document-start`. This gives it traditional content-blocker behavior and prevents the `Avatars available for purchase` panel from flashing while collection pages render.

The normal-use timing constants are near the top of the userscript:

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

The user-adjustable flags are grouped near the log settings:

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

## Compatibility With the SKU Userscript

This userscript can run alongside [`PSPrices-Show-Product-SKU.user.js`](../userscripts/PSPrices-Show-Product-SKU.user.js).

The checkout script replaces only the first exact supported purchase target. It leaves the surrounding buy wrapper and separate SKU panel intact. The SKU userscript can therefore retain a native SKU block or inject its fallback SKU panel without the checkout script treating that change as a new purchase target.

## Failure Handling

The Add to Cart button remains disabled when:

- the userscript manager does not expose a supported cross-origin request API
- product, region, locale, or target data is missing or contradictory
- Sony returns HTTP, timeout, network, redirect, JSON, or SKU-validation failures
- a correct checkout URL cannot be constructed

Safe error information is written to the browser console. The card displays a shorter user-facing status such as:

```text
Checkout link unavailable. See browser console.
```

Navigation and dynamic PSPrices updates invalidate stale requests, checkout URLs, click attempts, and pending LinkGen timers before another supported context is mounted.

## Permissions

The metadata grants support both modern and legacy userscript-manager APIs:

- `GM.xmlHttpRequest` and `GM_xmlhttpRequest`: anonymous Sony regional-SKU requests
- `GM.setClipboard` and `GM_setClipboard`: clipboard fallbacks
- `GM_log`: optional userscript-manager log mirroring
- `@connect store.playstation.com`: permission for the Sony lookup host

Sony requests are sent without account cookies or credential-bearing headers.
