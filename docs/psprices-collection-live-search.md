# PSPrices-Collection-Live-Search.user.js

[`userscripts/PSPrices-Collection-Live-Search.user.js`](../userscripts/PSPrices-Collection-Live-Search.user.js) is a Tampermonkey userscript that adds cached live substring search to PSPrices avatar and theme collection pages across regions, indexing paginated collection results beyond the current visible page.

Current documented release: `1.0.19`.

## What It Does

- adds a native-style live search panel to the main avatar and theme collection pages
- adds a same-region `Go To Themes` / `Go To Avatars` shortcut beside the native collection heading
- searches cached collection titles with simple substring matching as the user types
- indexes all pages for the current region in the background
- prewarms both avatar and theme indexes after any regional PSPrices page is visited
- keeps separate caches per host, region, and collection type
- provides local platform filtering for `PS3`, `PS4`, and `PS5`
- provides a `Free only` checkbox that can combine with text and platform filters
- progressively hydrates visible results with thumbnails, prices, and platform badges from each product page
- supports light and dark themes by reusing PSPrices utility classes where practical
- hides the native avatar tablist plus theme platform stripe and Likes/Filter controls on the mounted collection routes before they paint

## Where It Works

The userscript loads on regional PSPrices pages so background indexing can start before the user opens the collection page:

```text
https://psprices.com/region-*
https://www.psprices.com/region-*
```

The visible search UI mounts only on the canonical collection endpoints:

```text
https://psprices.com/region-*/collection/avatars
https://psprices.com/region-*/collection/themes
```

Equivalent `www.psprices.com` routes are also covered.

The UI intentionally does not mount on the old PSPrices filter endpoints:

```text
/collection/free-avatars
/collection/ps3-avatars
/collection/ps4-avatars
/collection/free-themes
/collection/ps3-themes
/collection/ps4-themes
```

It also does not mount on collection URLs containing a `platform` query parameter, such as:

```text
/collection/themes?platform=iOS%2CPS3
```

Those routes are left to PSPrices' native page behavior.

## Basic Install

1. Install a userscript manager such as Tampermonkey.
2. Open the [raw userscript](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Collection-Live-Search.user.js).
3. Confirm the installation in the userscript manager.
4. Open any regional PSPrices page, or go directly to `/collection/avatars` or `/collection/themes`.

## How Search Works

The search box performs case-insensitive substring matching against cached item text.

Typing:

```text
batman
```

matches item text containing `batman` anywhere in the title or hydrated searchable text.

Typing a short partial query such as:

```text
ba
```

matches cached item text containing `ba` anywhere in the string.

Multi-word queries are handled in two passes:

- exact normalized query substring match first
- if there are multiple terms, all terms may match separately inside the searchable text

Search runs with a small input debounce so fast typing does not rebuild the result grid on every key event.

The native PSPrices collection grid and native pagination are hidden on the canonical mounted routes. The userscript keeps its custom result grid empty while the current region cache is still building.

After the current region's avatar and theme caches are both complete, an empty query with `All platforms` selected renders the first `108` indexed items sorted alphabetically. Typing in the search box or enabling platform/free filters narrows that same sorted result set.

Search, platform/free filters, `Show more`, the result grid, and product-page detail hydration stay locked until the current region's avatar and theme caches are both 100% complete. Nothing populates in the custom grid while the user is still waiting on those caches. If the user stays on the page, the grid automatically populates when both caches hit 100%; a refresh is not required. This lock is still region-scoped: AU unlocks only after AU avatars and AU themes finish, while another region has its own queued or paused cache state. Clearing the current region cache also clears the grid until both rebuilt caches finish.

Text-query changes can keep matching partial results on screen briefly while the next live result set hydrates. Platform and `Free only` changes are treated as hard filter changes: the visible grid is rebuilt from scratch, the render limit resets to `108`, and in-flight detail hydration is abandoned for the previous filter state.

Leading punctuation is ignored for sorting. Result order is:

- titles beginning with `A-Z`
- titles beginning with `0-9`
- remaining titles without a letter or number after normalization

## Built-In Filters

The userscript replaces reliance on PSPrices' separate collection filter URLs with local filters:

- `All platforms`
- `PS3`
- `PS4`
- `PS5`
- `Free only`

The platform dropdown and `Free only` checkbox can be combined. For example, selecting `PS4` and enabling `Free only` shows only free PS4 matches from the current collection's cached results.

The filter data is kept small in the stored index. Product page details are hydrated live for visible matched results, and platform/free filters can also hydrate unknown matching candidates in small batches so unconfirmed rows are not rendered as final results.

## Background Indexing

The script starts background indexing for the current region as soon as it runs on a regional PSPrices page.

For each region, the background worker indexes:

```text
/collection/avatars
/collection/themes
```

The old filtered endpoints are not separately cached. Platform and free filters are derived from the indexed collection data and live result hydration.

Indexing runs in page chunks. A completed page is written to localStorage immediately, and incomplete or failed pages are retried later instead of being treated as valid cache.

The UI status line mirrors the background worker when the search UI is visible. Example states include:

```text
Indexing Avatars (AU)... 648 items from 6 / 149 pages.
Indexed cached pages. 2293 items from 64 / 64 pages.
Queued Themes (US); Avatars (AU) is indexing. 0 items from 0 / 1 page.
Paused: PSPrices returned a bot-protection or rate-limit page.
```

The progress bar tracks combined current-region cache progress across both canonical collections, so it reaches the end only after both avatars and themes are fully cached. It refreshes from local worker state and cache metadata written by other tabs.

If the user navigates away from the mounted collection page but stays on PSPrices, indexing continues in the background. If the regional route disappears, the worker waits for a grace period before pausing.

## Region and Tab Handling

Caches are scoped per host, region, and collection. Changing from `region-au` to `region-us` starts or resumes a separate regional cache.

Only one background prewarm worker is intended to run across open PSPrices tabs at a time. The script uses localStorage leases for a best-effort cross-tab lock:

- one global site prewarm lease prevents multiple regions from indexing at once
- one region lease prevents duplicate workers for the same region
- another tab can show a queued status when a different tab owns indexing
- stale leases expire automatically if the owning tab disappears

If a tab unloads while indexing, it broadcasts a short stop signal so other active tabs can pause and retry cleanly instead of duplicating work immediately.

## Cache Storage

The index is stored in browser `localStorage` under keys beginning with:

```text
psprices-live-search:
```

The stored page data is intentionally compact. It primarily stores:

- item title
- relative product URL
- lightweight filter flags where available
- page-level metadata such as collection, region, completion state, and timestamps

Thumbnails, prices, and detailed platform text are not bulk-cached for every collection item. They are fetched live for visible matched results when needed.

The clear-cache button only clears the current region:

```text
Clear Cache (AU)
```

After clearing, background indexing starts again for that region.

## Cache Freshness and Migration

The main cache freshness constants are near the top of the userscript:

```js
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const CACHE_REVALIDATE_MS = 12 * 60 * 60 * 1000;
const CACHE_SCHEMA_VERSION = 8;
const CACHE_RESET_ON_SCHEMA_CHANGE = true;
```

Their purposes are:

- `CACHE_TTL_MS`: maximum age of a cached page before it is removed and rebuilt
- `CACHE_REVALIDATE_MS`: age after which an otherwise complete collection can be checked again
- `CACHE_SCHEMA_VERSION`: manual cache migration marker for incompatible cache changes
- `CACHE_RESET_ON_SCHEMA_CHANGE`: when `true`, changing the schema version purges old script caches on next load

When `CACHE_SCHEMA_VERSION` changes, the script removes previous `psprices-live-search:` localStorage entries and stores the new migration marker. This prevents stale incompatible cache formats from consuming space or causing wrong results.

## localStorage Budget

The script tracks its own approximate localStorage usage:

```js
const CACHE_MAX_BYTES = 4 * 1024 * 1024;
const CACHE_TARGET_BYTES = 3 * 1024 * 1024;
```

If the script cache grows too large, it prunes older script-owned caches first. It tries to avoid purging the active region currently being used.

Browser quota is still controlled by the browser and userscript manager environment. If localStorage writes fail, the UI and console report cache write failures, and already indexed in-memory data can still be used during the current page session.

## Fetch and Rate-Limit Controls

This userscript can be network-heavy. Cache indexing walks the collection pages with concurrent requests, and live detail hydration can fetch product pages for the currently visible or filter-confirmation candidates. The defaults are intended to be moderately fast, but lowering the concurrency or adding delay is the safest option if PSPrices starts responding slowly, shows bot protection, or rate-limits the browser session.

Collection indexing uses these main knobs:

```js
const FETCH_CONCURRENCY = 6;
const FETCH_RETRY_COUNT = 1;
const FETCH_TIMEOUT_MS = 30000;
const FETCH_DELAY_MS = 800;
const FETCH_JITTER_MS = 500;
const MAX_HARD_FAILURES = 2;
```

Their purposes are:

- `FETCH_CONCURRENCY`: number of collection pages fetched in parallel for foreground indexing
- `FETCH_RETRY_COUNT`: retry attempts for a failed page request
- `FETCH_TIMEOUT_MS`: maximum time allowed for each fetch
- `FETCH_DELAY_MS`: base wait before page fetches
- `FETCH_JITTER_MS`: random extra wait added to avoid perfectly synchronized requests
- `MAX_HARD_FAILURES`: hard failure threshold before indexing pauses

Background prewarm uses:

```js
const PREWARM_FETCH_CONCURRENCY = 6;
const PREWARM_COLLECTION_DELAY_MS = 1500;
const PREWARM_CONTEXT_GRACE_MS = 60 * 1000;
const PREWARM_LEASE_HEARTBEAT_MS = 5000;
const PREWARM_LEASE_STALE_MS = 30 * 1000;
```

Their purposes are:

- `PREWARM_FETCH_CONCURRENCY`: page fetch concurrency for background region indexing
- `PREWARM_COLLECTION_DELAY_MS`: pause between avatar and theme collection prewarm passes
- `PREWARM_CONTEXT_GRACE_MS`: time to wait after losing the regional page context before pausing
- `PREWARM_LEASE_HEARTBEAT_MS`: how often an indexing tab refreshes its cross-tab lease
- `PREWARM_LEASE_STALE_MS`: how long before another tab can treat a lease as abandoned

If PSPrices returns a rate-limit, bot-protection, or challenge-like page, indexing pauses and writes a console warning. A paused background worker can retry when the user types into the search box, subject to this cooldown:

```js
const PAUSED_SEARCH_RESUME_COOLDOWN_MS = 60 * 1000;
```

## Result Rendering Limits

The script does not render every indexed item or match at once on large collections. It starts with a practical sorted batch and expands on demand:

```js
const INITIAL_RENDER_LIMIT = 108;
const RENDER_STEP = 54;
const MAX_RENDER_LIMIT = -1;
```

Their purposes are:

- `INITIAL_RENDER_LIMIT`: number of custom collection results shown first, including the empty-query default view
- `RENDER_STEP`: number of additional results added by each `Show more` click
- `MAX_RENDER_LIMIT`: hard cap for rendered results; the default `-1` means no hard cap

Set `MAX_RENDER_LIMIT` to `-1` for no hard cap. This can be heavy on low-memory machines.

When a result set exceeds the hard cap, the UI reports that only part of the match list is shown and suggests refining the search.

## Live Detail Hydration

The cache keeps the stored index small. Detail hydration waits until the current region's avatar and theme caches are both 100% complete. During cache builds, the grid stays empty and no product-page URL fetches are started, avoiding extra product requests on top of collection-page cache indexing.

When `PS3`, `PS4`, `PS5`, or `Free only` filters are active, compact cached rows with unknown platform or price data are checked by fetching their product pages before they are shown as confirmed matches. If the search box is empty, candidate checks are limited to the current render window, starting at `108` sorted items and expanding only when `Show more` is clicked. Once text is typed, that query builds the broad candidate pool while platform and free filters trim confirmed matches from it.

While a visible result batch is hydrating, partial re-renders keep that batch's hydration queue stable. Search text, filter, or `Show more` changes still cancel and retarget hydration so stale result details are not fetched longer than needed. When the active metadata worker batch drains, the grid is forced through one final render so completed theme details cannot stay hidden behind a pending debounce. If compact cached rows are reloaded without metadata, they can be hydrated again even when their key was fetched earlier in the same page session.

Result cards use detail-confirmed rendering, including blank All platforms views, so grids fill progressively with real thumbnails, prices, and platform badges instead of painting a full page of placeholders first. All platforms is treated as a `PS3`/`PS4`/`PS5` union while compact rows are being confirmed. On collection page launch, initial hydration waits for the page `load` event and mounted userscript UI before restarting, and retries if the grid stays empty. Product detail rows that fail hydration are not rendered for avatars or themes; the status line reports how many matching rows failed metadata fetching.

While candidate hydration, same-region collection cache indexing, or queued same-region lease work is still running, the UI labels already verified matches as confirmed results and shows a small pulsing indicator beside that status. The indicator is refreshed from cache status updates as well as result renders, so the avatar page can pulse while the theme cache builds and the theme page can pulse while the avatar cache builds, including after page reloads or region navigation. Remaining undisplayed items are reported through the `Show more` button.

The main controls are:

```js
const LIVE_DETAIL_HYDRATION_ENABLED = true;
const LIVE_DETAIL_FETCH_CONCURRENCY = 7;
const LIVE_DETAIL_FETCH_DELAY_MS = 0;
const LIVE_DETAIL_FETCH_JITTER_MS = 0;
const LIVE_DETAIL_RENDER_DEBOUNCE_MS = 15;
const LIVE_DETAIL_MAX_ITEMS_PER_RENDER = -1;
const LIVE_DETAIL_FILTER_CANDIDATE_BATCH = 108;
```

Their purposes are:

- `LIVE_DETAIL_HYDRATION_ENABLED`: enables product-page detail fetching for rendered results and filter candidate checks
- `LIVE_DETAIL_FETCH_CONCURRENCY`: number of product pages fetched in parallel
- `LIVE_DETAIL_FETCH_DELAY_MS`: base delay before each live detail fetch
- `LIVE_DETAIL_FETCH_JITTER_MS`: random extra delay for live detail fetches
- `LIVE_DETAIL_RENDER_DEBOUNCE_MS`: small delay before applying hydrated card updates
- `LIVE_DETAIL_MAX_ITEMS_PER_RENDER`: maximum visible rendered cards to hydrate, or `-1` for no cap
- `LIVE_DETAIL_FILTER_CANDIDATE_BATCH`: maximum unknown platform/free candidate rows checked per filter pass, or `-1` for no cap

Hydration is retargeted as the query changes. Results that still match the new query can remain on screen, while clearly stale result cards are removed after:

```js
const RENDER_STALE_RESULT_GRACE_MS = 2500;
```

This avoids repeatedly clearing and rebuilding the entire grid while the user is typing quickly.

## Early Cosmetic Hides

The userscript runs at `document-start` so selected native PSPrices controls can be hidden before they paint:

- on canonical `/collection/avatars`, it hides the native tablist block
- on canonical `/collection/themes`, it hides the native platform stripe and native Likes/Filter controls
- native collection grids, native pagination blocks, and anything marked `data-psprices-live-search-hidden="true"` are hidden with bootstrap CSS

The theme platform stripe and Likes/Filter hides are scoped to the route class for `/collection/themes` only. The Likes/Filter action row hide is additionally constrained to the collection `main` content and the native filter toggle, so it does not hide the PSPrices header/home block. These hides do not apply on product pages, avatar pages, or `/collection/themes?platform=...` query-filter URLs.

## Console Logging

Logging is controlled near the top of the userscript:

```js
const LOG_LEVEL = 'info';
```

Supported values:

- `'info'`: startup, route changes, cache state, pause reasons, storage failures, and final indexing results
- `'verbose'`: detailed route parsing, cache reads and writes, request lifecycle, parser counts, stale checks, and search result counts

Logs are prefixed with:

```text
PSPrices Collection Live Search:
```

Logging is designed not to include cookies, credential headers, full response bodies, session data, or raw localStorage payloads.

## Compatibility With Other PSPrices Userscripts

This userscript can run alongside:

- [`PSPrices-PlayStation-Checkout-Link.user.js`](../userscripts/PSPrices-PlayStation-Checkout-Link.user.js)
- [`PSPrices-Show-Product-SKU.user.js`](../userscripts/PSPrices-Show-Product-SKU.user.js)

The collection live-search script primarily owns the canonical avatar/theme collection pages and product-page fetches used for visible result hydration. The checkout script primarily owns supported product-page purchase targets, and the SKU script owns the product-page SKU panel. These ownership boundaries let the three PSPrices userscripts coexist without intentionally replacing each other's UI.

## Failure Handling

The UI status line reports failed pages, queued indexing, paused indexing, and cache write problems when they occur.

Common failure modes include:

- localStorage quota errors
- expired or incompatible cache pages
- request timeouts
- PSPrices challenge or bot-protection pages
- too many hard page-fetch failures
- another tab owning the current indexing lease

Incomplete pages are not treated as valid finished cache. On the next run, the script resumes from completed pages and rebuilds missing, stale, or corrupt chunks.
