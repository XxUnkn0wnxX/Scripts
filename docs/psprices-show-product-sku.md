# PSPrices-Show-Product-SKU.user.js

[`PSPrices-Show-Product-SKU.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js) is a Tampermonkey userscript that displays and copies the public PlayStation product SKU on PSPrices product pages, adding a native-style SKU panel below buy, checkout, or unavailable-store sections and preferring it over a native SKU panel when a valid value is available.

Current documented release: `1.0.1.4`.

## What It Does

- shows the product SKU in a block matching PSPrices' native avatar SKU design
- follows the native card typography and responsive copy-button placement while retaining the SKU panel's blue accent
- includes a `Copy SKU` button
- works with games, DLC, themes, avatars, and other PlayStation products
- supports product pages from every PSPrices region
- prefers its own card over a native SKU block when a valid replacement value is available
- mounts below the checkout userscript card, or below the PlayStation Store unavailable warning when no native buy block exists

## Where It Works

The script only runs on PSPrices product URLs matching:

```text
https://psprices.com/region-*/game/*
```

This includes region paths such as `region-au`, `region-us`, and `region-gb`.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`PSPrices-Show-Product-SKU.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js).
3. Create a new userscript in Tampermonkey and paste the file contents.
4. Save it, then open a PSPrices product page.

## How It Extracts the SKU

PSPrices includes public structured product data in the page source using a JSON-LD block:

```html
<script type="application/ld+json">
```

The userscript reads these blocks, finds the entry whose `@type` is `Product`, and extracts its `sku` value. It does not scrape the visible title or attempt to calculate a product ID. If JSON-LD does not provide a SKU, it can use an unmasked value from PSPrices' native unlocked SKU panel.

For example, a product page may expose:

```json
{
  "@type": "Product",
  "sku": "EP4396-CUSA10659_00-ETH0000000002206"
}
```

That public SKU is then displayed in the injected block.

## Existing SKU Blocks

When PSPrices already renders a native locked or unlocked SKU panel, the userscript prefers its own blue card and hides the native panel only after a valid replacement is mounted. The SKU userscript owns this behavior for both the locked access prompt and the unlocked SKU card.

This works with either PSPrices' native purchase block or the checkout userscript's replacement card. If the checkout userscript has replaced a PlayStation Store unavailable warning, this script mounts the SKU panel below that checkout card. Without the checkout userscript, it mounts below the unavailable warning itself.

The script watches for dynamic page updates and restores its card when possible. If it cannot mount a valid replacement, it restores the native SKU panel. The native panel stays in the DOM, and unrelated access prompts are left alone.

## Compatibility With Other PSPrices Userscripts

This userscript can run alongside:

- [`PSPrices-PlayStation-Checkout-Link.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-PlayStation-Checkout-Link.user.js)
- [`PSPrices-Collection-Live-Search.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Collection-Live-Search.user.js)

The SKU script owns its injected card and suppression of the native locked or unlocked SKU panels. The checkout script replaces supported purchase targets while leaving the SKU mount point available; it does not hide native SKU panels. The collection live-search script owns collection search and product-page fetches used to fill in result details.

## Good To Know

- The displayed value is the base product SKU published in the page's JSON-LD metadata, or an unmasked native unlocked SKU when JSON-LD is unavailable.
- The script does not add or resolve checkout suffixes such as `-E001`.
- If a product page provides neither a `Product` SKU in JSON-LD nor an unmasked native unlocked SKU, no block is added.
- Copying uses the browser clipboard API with a fallback for browsers where direct clipboard access fails.
