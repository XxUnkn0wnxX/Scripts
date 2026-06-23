# PSPrices-PlayStation-Checkout-Link.user.js

[`userscripts/PSPrices-PlayStation-Checkout-Link.user.js`](../userscripts/PSPrices-PlayStation-Checkout-Link.user.js) is a Tampermonkey userscript that injects working purchase panels for PSNPrices avatar and theme pages.

## What It Does

- reads the public base product SKU and price from PSPrices' JSON-LD product metadata
- resolves the regional full PlayStation SKU through Sony's public store endpoint
- builds a regional `checkout.playstation.com/add/` URL
- replaces the first supported avatar or theme purchase panel with a PSPrices-style checkout card
- keeps the Add to Cart button disabled until a validated checkout URL is ready
- supports PSPrices product pages across all configured PlayStation regions
- preserves the visual-map and SKU panels outside the replaced purchase target
- hides the matching logged-out sticky Buy Unlocked bar while the replacement is active
- adds a dominant `🏴‍☠️ unlocked` badge beside the PSPrices header wordmark

## Where It Works

The userscript runs on product URLs matching:

```text
https://psprices.com/region-*/game/*
https://www.psprices.com/region-*/game/*
```

It only replaces a purchase target when the page contains one exact supported avatar or theme structure. If no supported target exists, it does not insert a checkout card.

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

A returned SKU must match the page's base SKU plus a regional suffix such as `-E001`. After validation, the script creates:

```text
https://checkout.playstation.com/add/FULL_SKU?clientId=...
```

Only successfully validated full SKUs are cached for the current page session. Failures, malformed responses, and mismatched SKUs are never cached.

## Rendering and Timing

The script starts at `document-start` and temporarily suppresses the shared PSPrices purchase wrapper while it validates and replaces the purchase target. The completed wrapper then fades into view.

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

The script adds this badge immediately after the PSPrices wordmark:

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
