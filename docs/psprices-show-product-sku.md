# PSPrices-Show-Product-SKU.user.js

[`userscripts/PSPrices-Show-Product-SKU.user.js`](../userscripts/PSPrices-Show-Product-SKU.user.js) is a Tampermonkey userscript that displays and copies the public PlayStation product SKU on PSPrices product pages, adding a native-style SKU panel below buy, checkout, or unavailable-store sections only when PSPrices does not already show one.

Current documented release: `1.0.1.3`.

## What It Does

- shows the product SKU in a block matching PSPrices' native avatar SKU design
- includes a `Copy SKU` button
- works with games, DLC, themes, avatars, and other PlayStation products
- supports product pages from every PSPrices region
- avoids replacing or duplicating a native SKU block when PSPrices already displays one
- mounts below the checkout userscript card, or below the PlayStation Store unavailable warning when no native buy block exists

## Where It Works

The script only runs on PSPrices product URLs matching:

```text
https://psprices.com/region-*/game/*
```

This includes region paths such as `region-au`, `region-us`, and `region-gb`.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open [`userscripts/PSPrices-Show-Product-SKU.user.js`](../userscripts/PSPrices-Show-Product-SKU.user.js).
3. Create a new userscript in Tampermonkey and paste the file contents.
4. Save it, then open a PSPrices product page.

## How It Extracts the SKU

PSPrices includes public structured product data in the page source using a JSON-LD block:

```html
<script type="application/ld+json">
```

The userscript reads these blocks, finds the entry whose `@type` is `Product`, and extracts its `sku` value. It does not scrape the visible title or attempt to calculate a product ID.

For example, a product page may expose:

```json
{
  "@type": "Product",
  "sku": "EP4396-CUSA10659_00-ETH0000000002206"
}
```

That public SKU is then displayed in the injected block.

## Existing SKU Blocks

Some avatar pages already contain a native PSPrices SKU block. When one exists, the userscript leaves it untouched and does not add another.

On pages without that block, the script injects its matching SKU panel into the product detail area. If the checkout userscript has replaced a PlayStation Store unavailable warning, this script mounts the SKU panel below that checkout card. If the checkout userscript is not running, it mounts below the unavailable warning itself. It also watches for dynamic page updates so the panel can be restored when PSPrices changes product content without a full reload.

## Good To Know

- The displayed value is the base product SKU published in the page's JSON-LD metadata.
- The script does not add or resolve checkout suffixes such as `-E001`.
- If a product page does not publish a `Product` SKU in JSON-LD, no block is added.
- Copying uses the browser clipboard API with a fallback for browsers where direct clipboard access fails.
