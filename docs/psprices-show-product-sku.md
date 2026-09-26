# PSPrices-Show-Product-SKU.user.js

[`PSPrices-Show-Product-SKU.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js) is a Tampermonkey userscript that displays and copies the public PlayStation product SKU on PSPrices product pages, with Avatar SKU, Theme SKU, or generic SKU labels and matching helper text in a native-style panel below buy, checkout, or unavailable-store sections.

Current documented release: `1.0.1.5`.

## Screenshots

The **Avatar SKU** card for **Afterparty – Wormhorn Avatar** before (left) and
after (right). The script shows the public identifier and adds **Copy SKU**.

![PSPrices Avatar SKU card before and after revealing the product identifier](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/.images/userscripts/psprices-product-sku/comparison.png)

## What It Does

- shows the product SKU in a block matching PSPrices' native avatar SKU design
- labels the panel `Avatar SKU` or `Theme SKU` when the product's category is identifiable, with `SKU` as the fallback
- displays matching helper text below the identifier: `Avatar SKU identifier for third-party utilities.`, `Theme SKU identifier for third-party utilities.`, or `SKU identifier for third-party utilities.`
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
https://www.psprices.com/region-*/game/*
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

## Category Labels and Helper Text

The panel reads the collection link in the current product's category badges (`#platform-badges` inside `#game-detail`). A link to `/region-*/collection/avatars` selects `Avatar SKU`; a link to `/region-*/collection/themes` selects `Theme SKU`. Both relative and absolute links work.

If neither category is identified, or both appear in the product's badges, the heading stays `SKU` and the helper text stays `SKU identifier for third-party utilities.` Other products therefore keep the generic wording. Navigation links, related-product links, product titles, and SKU strings do not determine the label.

The label and helper text refresh when the product markup or category link changes, including HTMX updates. This changes the panel's wording only; the SKU value and `Copy SKU` behavior follow the same extraction and copying rules.

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

## Permissions and Data

The script uses `@grant none`: it does not request userscript-manager APIs.
It reads product data already present in the page, changes the SKU panel, and
copies the displayed identifier only when **Copy SKU** is clicked. Copying
replaces the current clipboard text. The fallback temporarily selects the SKU
in a hidden text field and uses the browser's copy command.

There are no settings, persistent caches, background requests, or data uploads.
Showing a public SKU does not change PSPrices membership or buy a PlayStation
product. Disable the script and reload to restore the native SKU panel.
