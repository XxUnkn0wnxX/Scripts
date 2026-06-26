// ==UserScript==
// @name         PSPrices Collection Live Search
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.4
// @description  Adds cached live substring search to PSPrices avatar and theme collection pages across regions, indexing paginated collection results beyond the current page. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Collection-Live-Search.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Collection-Live-Search.user.js
// @match        https://psprices.com/region-*
// @match        https://www.psprices.com/region-*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const SCRIPT_NAME = 'PSPrices Collection Live Search';
  const SCRIPT_VERSION = '1.0.4';
  const LOG_LEVEL = 'info';
  const REGION_PATH = /^\/region-([a-z0-9-]+)(?:\/|$)/i;
  const ROUTE_PATH =
    /^\/region-([a-z0-9-]+)\/collection\/(avatars|themes)\/?$/i;

  /*
   * Logging levels:
   * - info: Published default. Logs startup, route changes, cache/fetch state,
   *   pause reasons, storage failures, and final indexing results.
   * - verbose: Logs detailed route parsing, cache page reads/writes, request
   *   lifecycle, parser counts, stale state checks, and search result counts.
   *
   * Logging must never include cookies, credential headers, full response
   * bodies, session data, or raw localStorage payloads.
   */

  const CACHE_PREFIX = 'psprices-live-search';
  const CACHE_VERSION = 4;
  const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  const CACHE_SCOPE_VERSION = 'v4';
  const CACHE_RESET_ON_SCHEMA_CHANGE = true;
  const CACHE_SCHEMA_VERSION = 8;
  const CACHE_MIGRATION_VERSION = `cache-schema-${CACHE_SCHEMA_VERSION}`;
  const CACHE_MIGRATION_KEY = `${CACHE_PREFIX}:migration-version`;
  const CACHE_MAX_BYTES = 4 * 1024 * 1024;
  const CACHE_TARGET_BYTES = 3 * 1024 * 1024;
  const CACHE_BUDGET_CHECK_INTERVAL_MS = 5 * 1000;
  const CACHE_REVALIDATE_MS = 12 * 60 * 60 * 1000;
  const INPUT_DEBOUNCE_MS = 120;
  const FETCH_CONCURRENCY = 6;
  const FETCH_RETRY_COUNT = 1;
  const FETCH_TIMEOUT_MS = 30000;
  const FETCH_DELAY_MS = 800;
  const FETCH_JITTER_MS = 500;
  const FETCH_QUERY_MIN_LENGTH = 2;
  const MAX_HARD_FAILURES = 2;
  const PAUSED_SEARCH_RESUME_COOLDOWN_MS = 60 * 1000;
  const AUTO_INDEX_ON_LOAD = true;
  const AUTO_INDEX_DELAY_MS = 2500;
  const AUTO_INDEX_ON_SITE_VISIT = true;
  const PREWARM_FETCH_CONCURRENCY = 6;
  const PREWARM_COLLECTION_DELAY_MS = 1500;
  const PREWARM_CONTEXT_GRACE_MS = 60 * 1000;
  const PREWARM_LEASE_HEARTBEAT_MS = 5000;
  const PREWARM_LEASE_STALE_MS = 30 * 1000;
  const PREWARM_COLLECTIONS = Object.freeze([
    'avatars',
    'themes',
  ]);
  const AVATAR_CANONICAL_COLLECTION = 'avatars';
  const THEME_CANONICAL_COLLECTION = 'themes';
  const AVATAR_FILTER_COLLECTIONS = new Set();
  const THEME_FILTER_COLLECTIONS = new Set();
  const INITIAL_RENDER_LIMIT = 108;
  const RENDER_STEP = 54;
  // Set to -1 for no hard render cap. High values can be heavy on low-memory machines.
  const MAX_RENDER_LIMIT = 1200;
  // Live detail hydration fills thumbnails, prices, and platform badges for rendered results.
  // Platform/free filters can also hydrate a small batch of unknown candidates so confirmed matches can appear.
  const LIVE_DETAIL_HYDRATION_ENABLED = true;
  const LIVE_DETAIL_HYDRATION_DELAY_MS = 0;
  const LIVE_DETAIL_FETCH_CONCURRENCY = 7;
  const LIVE_DETAIL_FETCH_DELAY_MS = 0;
  const LIVE_DETAIL_FETCH_JITTER_MS = 0;
  const LIVE_DETAIL_RENDER_DEBOUNCE_MS = 15;
  // Set to -1 to allow all currently rendered results.
  const LIVE_DETAIL_MAX_ITEMS_PER_RENDER = -1;
  // Set to -1 to check every unknown candidate for platform/free filters at once.
  const LIVE_DETAIL_FILTER_CANDIDATE_BATCH = 108;
  const RENDER_STALE_RESULT_GRACE_MS = 2500;

  const STYLE_ID = 'psprices-live-search-style';
  const OWNER_ATTR = 'data-psprices-live-search';
  const RESULTS_ATTR = 'data-psprices-live-search-results';
  const HIDDEN_ATTR = 'data-psprices-live-search-hidden';
  const ROUTE_CLASS_PREFIX = 'pspls-route-';
  const ROUTE_CLASSES = Object.freeze([
    `${ROUTE_CLASS_PREFIX}avatars`,
    `${ROUTE_CLASS_PREFIX}themes`,
  ]);
  const NAV_EVENT = 'psprices-live-search:navigation';
  const HISTORY_PATCH_ATTR = '__pspricesLiveSearchPatched';
  const PREWARM_GLOBAL_LEASE_KEY = `${CACHE_PREFIX}:prewarm-lease:global`;
  const PREWARM_STOP_KEY = `${CACHE_PREFIX}:prewarm-stop`;
  const PREWARM_STOP_GRACE_MS = 10 * 1000;
  const TAB_ID = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

  const effectiveLogLevel = LOG_LEVEL === 'verbose' ? 'verbose' : 'info';
  const loggedMessages = new Map();
  let managerLogWarningShown = false;
  let appState = null;
  let prewarmState = null;
  let prewarmRunId = 0;
  let prewarmCompletedSignature = '';
  let lastPrewarmResumeAttemptAt = 0;
  let prewarmContextTimer = 0;
  let prewarmLeaseSignature = '';
  let prewarmLeaseTimer = 0;
  let prewarmLeaseRetryTimer = 0;
  let routeCheckTimer = null;
  let lastCacheBudgetCheckAt = 0;
  let pageIsUnloading = false;

  function sanitizeLogValue(value) {
    return String(value ?? '')
      .replace(/[\u0000-\u001f\u007f]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 240);
  }

  function formatLogParts(parts) {
    return parts
      .map((part) => {
        if (part instanceof Error) {
          return `${sanitizeLogValue(part.name)}: ${sanitizeLogValue(part.message)}`;
        }
        if (typeof part === 'object' && part !== null) {
          try {
            return sanitizeLogValue(JSON.stringify(part));
          } catch (_) {
            return '[unserializable]';
          }
        }
        return sanitizeLogValue(part);
      })
      .filter(Boolean)
      .join(' ');
  }

  function writeLog(level, ...parts) {
    if (level === 'verbose' && effectiveLogLevel !== 'verbose') return;
    const text = `${SCRIPT_NAME}: ${formatLogParts(parts)}`;
    const dedupeKey = `${level}:${text}`;
    const now = Date.now();
    if (loggedMessages.get(dedupeKey) && now - loggedMessages.get(dedupeKey) < 1500) return;
    loggedMessages.set(dedupeKey, now);

    const consoleMethod =
      level === 'verbose' ? 'debug' : level === 'error' ? 'error' : level;
    const writer = console[consoleMethod] || console.log;
    writer.call(console, text);

    if (typeof GM_log === 'function') {
      try {
        GM_log(text, level);
      } catch (_) {
        if (!managerLogWarningShown && effectiveLogLevel === 'verbose') {
          managerLogWarningShown = true;
          console.warn(`${SCRIPT_NAME}: GM_log failed; console logging will continue.`);
        }
      }
    }
  }

  const logger = Object.freeze({
    verbose: (...parts) => writeLog('verbose', ...parts),
    info: (...parts) => writeLog('info', ...parts),
    warn: (...parts) => writeLog('warn', ...parts),
    error: (...parts) => writeLog('error', ...parts)
  });

  function onReady(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
      return;
    }

    callback();
  }

  function parseRoute(url = window.location.href) {
    const parsed = new URL(url, window.location.origin);
    const match = ROUTE_PATH.exec(parsed.pathname);
    if (!match) return null;

    const queryParams = new URLSearchParams(parsed.search);
    if (Array.from(queryParams.keys()).some((key) => key.toLowerCase() === 'platform')) {
      return null;
    }

    queryParams.delete('page');
    queryParams.sort();

    return {
      host: parsed.host,
      origin: parsed.origin,
      pathname: parsed.pathname.replace(/\/+$/, ''),
      region: match[1].toLowerCase(),
      collection: match[2].toLowerCase(),
      currentPage: readPageNumber(parsed),
      filterQuery: queryParams.toString(),
      language: (document.documentElement.getAttribute('lang') || '').trim(),
    };
  }

  function parseRegionContext(url = window.location.href) {
    const parsed = new URL(url, window.location.origin);
    const match = REGION_PATH.exec(parsed.pathname);
    if (!match) return null;

    return {
      host: parsed.host,
      origin: parsed.origin,
      region: match[1].toLowerCase(),
      language: (document.documentElement.getAttribute('lang') || '').trim(),
    };
  }

  function makeCollectionRoute(context, collection) {
    return {
      host: context.host,
      origin: context.origin,
      pathname: `/region-${context.region}/collection/${collection}`,
      region: context.region,
      collection,
      currentPage: 1,
      filterQuery: '',
      language: context.language,
    };
  }

  function regionSignature(context) {
    if (!context) return '';
    return [context.host, context.region].join('|');
  }

  function prewarmLeaseKey(signature) {
    return `${CACHE_PREFIX}:prewarm-lease:${encodeURIComponent(signature)}`;
  }

  function routeSignature(route) {
    if (!route) return '';
    return [
      route.host,
      route.pathname,
      route.region,
      route.collection,
      route.filterQuery,
      route.language,
    ].join('|');
  }

  function readPageNumber(url) {
    const page = Number(url.searchParams.get('page') || '1');
    return Number.isInteger(page) && page > 0 ? page : 1;
  }

  function makePageUrl(route, page) {
    const url = new URL(route.pathname, route.origin);
    if (route.filterQuery) {
      const params = new URLSearchParams(route.filterQuery);
      for (const [key, value] of params.entries()) {
        url.searchParams.append(key, value);
      }
    }
    if (page > 1) {
      url.searchParams.set('page', String(page));
    }
    return url.href;
  }

  function cacheScope(route) {
    const filterPart = route.filterQuery ? encodeURIComponent(route.filterQuery) : 'nofilter';
    const languagePart = route.language ? encodeURIComponent(route.language.toLowerCase()) : 'nolanguage';
    return [
      CACHE_PREFIX,
      CACHE_SCOPE_VERSION,
      route.host,
      route.region,
      route.collection,
      filterPart,
      languagePart,
    ].join(':');
  }

  function isAvatarFilterCollection(collection) {
    return AVATAR_FILTER_COLLECTIONS.has(String(collection || '').toLowerCase());
  }

  function isThemeFilterCollection(collection) {
    return THEME_FILTER_COLLECTIONS.has(String(collection || '').toLowerCase());
  }

  function isThemeCollection(collection) {
    const value = String(collection || '').toLowerCase();
    return value === THEME_CANONICAL_COLLECTION || isThemeFilterCollection(value);
  }

  function isFilteredCollection(collection) {
    return isAvatarFilterCollection(collection) || isThemeFilterCollection(collection);
  }

  function isFreeCollection(collection) {
    return String(collection || '').toLowerCase().startsWith('free-');
  }

  function defaultPriceTextForCollection(collection) {
    return isFreeCollection(collection) ? 'Free' : '';
  }

  function defaultPlatformTextForCollection(collection) {
    const value = String(collection || '').toLowerCase();
    if (value === 'avatars' || value === 'themes') return '';
    return '';
  }

  function makeCanonicalAvatarRoute(route) {
    return {
      ...route,
      pathname: `/region-${route.region}/collection/${AVATAR_CANONICAL_COLLECTION}`,
      collection: AVATAR_CANONICAL_COLLECTION,
      currentPage: 1,
      filterQuery: '',
    };
  }

  function makeCanonicalThemeRoute(route) {
    return {
      ...route,
      pathname: `/region-${route.region}/collection/${THEME_CANONICAL_COLLECTION}`,
      collection: THEME_CANONICAL_COLLECTION,
      currentPage: 1,
      filterQuery: '',
    };
  }

  function cacheRouteForRoute(route) {
    if (isAvatarFilterCollection(route.collection)) {
      return makeCanonicalAvatarRoute(route);
    }
    if (isThemeFilterCollection(route.collection)) {
      return makeCanonicalThemeRoute(route);
    }
    return route;
  }

  function avatarIdentityKey(item) {
    const id = String(item && item.id || '').trim();
    if (id) return `id:${id}`;

    const url = String(item && item.url || '').trim();
    if (url) return `url:${url.replace(/^https?:\/\/[^/]+/i, '')}`;

    return '';
  }

  function protectedCacheScopesForRoute(route) {
    const context = {
      host: route.host,
      origin: route.origin,
      region: route.region,
      language: route.language,
    };
    return new Set(PREWARM_COLLECTIONS.map((collection) => cacheScope(makeCollectionRoute(context, collection))));
  }

  function cacheRegionKeyFromScope(scope) {
    const parts = String(scope || '').split(':');
    if (parts.length < 4 || parts[0] !== CACHE_PREFIX || parts[1] !== CACHE_SCOPE_VERSION) return '';
    return [parts[0], parts[1], parts[2], parts[3]].join(':');
  }

  function cacheMetaKey(scope) {
    return `${scope}:meta`;
  }

  function cachePageKey(scope, page) {
    return `${scope}:page:${page}`;
  }

  function isScriptCacheKey(key) {
    return String(key || '').startsWith(`${CACHE_PREFIX}:`);
  }

  function estimateCacheBytes() {
    let bytes = 0;
    try {
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (!isScriptCacheKey(key)) continue;
        const value = localStorage.getItem(key) || '';
        bytes += (key.length + value.length) * 2;
      }
    } catch (_) {
      return 0;
    }
    return bytes;
  }

  function canUseLocalStorage() {
    try {
      const key = `${CACHE_PREFIX}:probe`;
      localStorage.setItem(key, '1');
      localStorage.removeItem(key);
      return true;
    } catch (_) {
      return false;
    }
  }

  function readJsonStorage(key) {
    try {
      const value = localStorage.getItem(key);
      return value ? JSON.parse(value) : null;
    } catch (_) {
      return null;
    }
  }

  function storageKeyExists(key) {
    try {
      return localStorage.getItem(key) !== null;
    } catch (_) {
      return false;
    }
  }

  function writeJsonStorage(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function removeStorageKey(key) {
    try {
      localStorage.removeItem(key);
    } catch (_) {
      // Ignore storage cleanup errors.
    }
  }

  function runCacheMigration() {
    if (!CACHE_RESET_ON_SCHEMA_CHANGE) return;
    if (!canUseLocalStorage()) return;

    let storedVersion = '';
    try {
      storedVersion = localStorage.getItem(CACHE_MIGRATION_KEY) || '';
    } catch (_) {
      return;
    }

    if (storedVersion === CACHE_MIGRATION_VERSION) return;

    let removed = 0;
    try {
      for (let index = localStorage.length - 1; index >= 0; index -= 1) {
        const key = localStorage.key(index);
        if (isScriptCacheKey(key)) {
          removeStorageKey(key);
          removed += 1;
        }
      }
      localStorage.setItem(CACHE_MIGRATION_KEY, CACHE_MIGRATION_VERSION);
    } catch (error) {
      logger.warn('Unable to complete collection-search cache migration.', error);
      return;
    }

    logger.info(
      'Collection-search cache migration completed.',
      'from',
      storedVersion || 'none',
      'to',
      CACHE_MIGRATION_VERSION,
      'removedKeys',
      removed
    );
  }

  function readCache(scope) {
    const meta = readJsonStorage(cacheMetaKey(scope));
    const now = Date.now();
    if (!meta || meta.version !== CACHE_VERSION) {
      return null;
    }

    const pages = new Map();
    const stalePages = [];
    let metaChanged = false;
    for (const page of Object.keys(meta.pages || {})) {
      const pageNumber = Number(page);
      const payload = readJsonStorage(cachePageKey(scope, pageNumber));
      if (!payload || payload.version !== CACHE_VERSION || !Array.isArray(payload.items)) {
        stalePages.push(pageNumber);
        removeStorageKey(cachePageKey(scope, pageNumber));
        delete meta.pages[page];
        metaChanged = true;
        continue;
      }

      if (now - Number(payload.fetchedAt || 0) > CACHE_TTL_MS) {
        stalePages.push(pageNumber);
        removeStorageKey(cachePageKey(scope, pageNumber));
        delete meta.pages[page];
        metaChanged = true;
        continue;
      }

      pages.set(pageNumber, payload.items.map((item) => expandStoredItem(item, payload, pageNumber)));
    }

    if (metaChanged) {
      try {
        updateCacheMetaProgress(meta);
        writeJsonStorage(cacheMetaKey(scope), meta);
      } catch (_) {
        // Stale page keys were already removed; metadata cleanup can wait.
      }
    }

    updateCacheMeta(scope, (payload) => {
      payload.lastAccessedAt = now;
      return payload;
    });

    return {
      indexedAt: meta.indexedAt,
      lastPage: Number(meta.lastPage || 1),
      pages,
      stalePages,
      complete: Boolean(meta.complete),
      completedPageCount: Number(meta.completedPageCount || pages.size),
      itemCount: Number(meta.itemCount || 0),
      inFlightPage: Number(meta.inFlightPage || 0),
      inFlightPages: Object.keys(meta.inFlightPages || {})
        .map((page) => Number(page))
        .filter((page) => Number.isInteger(page) && page > 0),
    };
  }

  function readCanonicalAvatarItemMap(route) {
    if (!route || !isAvatarFilterCollection(route.collection)) {
      return new Map();
    }

    const canonicalScope = cacheScope(makeCanonicalAvatarRoute(route));
    const canonical = readCache(canonicalScope);
    const itemMap = new Map();
    if (!canonical) return itemMap;

    for (const items of canonical.pages.values()) {
      for (const item of items) {
        const key = avatarIdentityKey(item);
        if (key) itemMap.set(key, item);
      }
    }

    logger.verbose('Loaded canonical avatar cache for filter enrichment.', 'items', itemMap.size);
    return itemMap;
  }

  function expandStoredItem(item, payload, pageNumber) {
    const collection = payload && payload.collection ? payload.collection : '';
    const region = payload && payload.region ? payload.region : '';
    const defaultPriceText = defaultPriceTextForCollection(collection);
    const defaultPlatformText = defaultPlatformTextForCollection(collection);

    if (Array.isArray(item)) {
      const url = String(item[1] || '');
      const filterFlags = sanitizeCompactFilterFlags(parseFilterFlags(item[2]), collection).join(',');
      return {
        id: extractGameId(url),
        title: String(item[0] || ''),
        url,
        page: Number(pageNumber || 1),
        priceText: defaultPriceText,
        platformText: defaultPlatformText,
        extraText: '',
        image: '',
        filterFlags,
        collection,
        region,
      };
    }

    const itemCollection = String(item && item.collection || collection);
    return {
      id: String(item && item.id || ''),
      title: String(item && item.title || ''),
      url: String(item && item.url || ''),
      page: Number(item && item.page || pageNumber || 1),
      priceText: String(item && item.priceText || defaultPriceTextForCollection(itemCollection)),
      platformText: String(item && item.platformText || defaultPlatformTextForCollection(itemCollection)),
      extraText: String(item && item.extraText || ''),
      image: String(item && item.image || ''),
      filterFlags: parseFilterFlags(item && item.filterFlags).join(','),
      collection: itemCollection,
      region: String(item && item.region || region),
    };
  }

  function sanitizeCompactFilterFlags(flags, collection) {
    const values = parseFilterFlags(flags);
    const platformFlags = values.filter((flag) => /^ps[345]$/.test(flag));
    const flagSet = new Set(values);
    const value = String(collection || '').toLowerCase();
    const looksLikeOldDefault =
      (value === AVATAR_CANONICAL_COLLECTION && flagSet.has('ps3') && flagSet.has('ps4') && flagSet.has('ps5')) ||
      (value === THEME_CANONICAL_COLLECTION && flagSet.has('ps3') && flagSet.has('ps4') && !flagSet.has('ps5'));

    if (!looksLikeOldDefault || platformFlags.length === 0) {
      return values;
    }

    return values.filter((flag) => !/^ps[345]$/.test(flag));
  }

  function titleFromUrl(url) {
    const slug = String(url || '')
      .replace(/^https?:\/\/[^/]+/i, '')
      .split('/')
      .filter(Boolean)
      .pop();
    if (!slug) return '';

    return slug
      .replace(/[-_]+/g, ' ')
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
      .trim();
  }

  function enrichCachedItemsForRoute(route, items, canonicalMap) {
    if (isFilteredCollection(route.collection)) {
      return deriveItemsForRoute(route, items);
    }

    return items;
  }

  function clearCache(scope) {
    const meta = readJsonStorage(cacheMetaKey(scope));
    if (meta && meta.pages) {
      for (const page of Object.keys(meta.pages)) {
        removeStorageKey(cachePageKey(scope, Number(page)));
      }
    }
    removeStorageKey(cacheMetaKey(scope));
  }

  function clearRegionCache(route) {
    let removed = 0;
    const prefix = [
      CACHE_PREFIX,
      CACHE_SCOPE_VERSION,
      route.host,
      route.region,
      '',
    ].join(':');
    try {
      for (let index = localStorage.length - 1; index >= 0; index -= 1) {
        const key = localStorage.key(index);
        if (key && key.startsWith(prefix)) {
          removeStorageKey(key);
          removed += 1;
        }
      }
    } catch (error) {
      logger.warn('Unable to clear local collection-search region cache.', error);
    }
    logger.info('Cleared local collection-search region cache.', 'region', route.region, 'removedKeys', removed);
    return removed;
  }

  function collectCacheScopes() {
    const scopes = [];
    try {
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (!key || !key.startsWith(`${CACHE_PREFIX}:`) || !key.endsWith(':meta')) continue;
        const scope = key.slice(0, -':meta'.length);
        const meta = readJsonStorage(key);
        scopes.push({
          scope,
          meta,
          lastAccessedAt: Number(meta && meta.lastAccessedAt || meta && meta.indexedAt || 0),
        });
      }
    } catch (_) {
      return [];
    }
    return scopes;
  }

  function collectCacheRegions() {
    const regions = new Map();
    for (const entry of collectCacheScopes()) {
      const regionKey = cacheRegionKeyFromScope(entry.scope);
      if (!regionKey) continue;

      const existing = regions.get(regionKey) || {
        regionKey,
        scopes: [],
        lastAccessedAt: 0,
      };
      existing.scopes.push(entry);
      existing.lastAccessedAt = Math.max(existing.lastAccessedAt, entry.lastAccessedAt);
      regions.set(regionKey, existing);
    }
    return Array.from(regions.values());
  }

  function removeCacheScope(scope) {
    const meta = readJsonStorage(cacheMetaKey(scope));
    let removed = 0;
    if (meta && meta.pages) {
      for (const page of Object.keys(meta.pages)) {
        removeStorageKey(cachePageKey(scope, Number(page)));
        removed += 1;
      }
    }
    removeStorageKey(cacheMetaKey(scope));
    removed += 1;
    return removed;
  }

  function enforceCacheBudget(activeScope = '', protectedScopes = new Set()) {
    if (!canUseLocalStorage()) return;

    const now = Date.now();
    if (now - lastCacheBudgetCheckAt < CACHE_BUDGET_CHECK_INTERVAL_MS) return;
    lastCacheBudgetCheckAt = now;

    let currentBytes = estimateCacheBytes();
    if (!currentBytes || currentBytes <= CACHE_MAX_BYTES) return;

    const activeRegionKey = cacheRegionKeyFromScope(activeScope);
    const protectedRegionKeys = new Set(
      Array.from(protectedScopes)
        .map((scope) => cacheRegionKeyFromScope(scope))
        .filter(Boolean)
    );
    if (activeRegionKey) {
      protectedRegionKeys.add(activeRegionKey);
    }

    const regions = collectCacheRegions()
      .filter((entry) => !protectedRegionKeys.has(entry.regionKey))
      .sort((a, b) => a.lastAccessedAt - b.lastAccessedAt);
    let removedRegions = 0;
    let removedScopes = 0;

    for (const region of regions) {
      if (currentBytes <= CACHE_TARGET_BYTES) break;
      for (const entry of region.scopes) {
        removeCacheScope(entry.scope);
        removedScopes += 1;
      }
      removedRegions += 1;
      currentBytes = estimateCacheBytes();
    }

    if (removedRegions > 0) {
      logger.info(
        'Pruned old collection-search cache regions.',
        'removedRegions',
        removedRegions,
        'removedScopes',
        removedScopes,
        'estimatedBytes',
        currentBytes
      );
    } else if (currentBytes > CACHE_MAX_BYTES) {
      logger.warn(
        'Collection-search cache is over budget, but only the active/protected region remains.',
        'estimatedBytes',
        currentBytes
      );
    }
  }

  function shouldRevalidateCache(meta) {
    if (!meta || !meta.complete) return true;
    return Date.now() - Number(meta.lastValidatedAt || 0) > CACHE_REVALIDATE_MS;
  }

  function isCacheScopeFresh(scope) {
    const meta = readJsonStorage(cacheMetaKey(scope));
    if (!meta || meta.version !== CACHE_VERSION || !meta.complete) return false;
    if (shouldRevalidateCache(meta)) return false;
    if (meta.inFlightPage || Object.keys(meta.inFlightPages || {}).length > 0) return false;

    const now = Date.now();
    const lastPage = Math.max(1, Number(meta.lastPage || 1));
    for (let page = 1; page <= lastPage; page += 1) {
      const pageMeta = meta.pages && meta.pages[String(page)];
      if (!pageMeta) return false;
      if (now - Number(pageMeta.fetchedAt || 0) > CACHE_TTL_MS) return false;
      if (!storageKeyExists(cachePageKey(scope, page))) return false;
    }

    return true;
  }

  function arePrewarmCachesFresh(context) {
    return PREWARM_COLLECTIONS.every((collection) => {
      const route = makeCollectionRoute(context, collection);
      return isCacheScopeFresh(cacheScope(route));
    });
  }

  function updateCacheMetaProgress(meta) {
    const pageNumbers = Object.keys(meta.pages || {})
      .map((page) => Number(page))
      .filter((page) => Number.isInteger(page) && page > 0);
    const lastPage = Math.max(1, Number(meta.lastPage || 1));
    const completed = pageNumbers.filter((page) => page <= lastPage).length;
    const inFlightPages = Object.keys(meta.inFlightPages || {});
    const hasLegacyInFlightPage = Boolean(meta.inFlightPage);
    meta.completedPageCount = completed;
    meta.complete = completed >= lastPage && inFlightPages.length === 0 && !hasLegacyInFlightPage;
    meta.lastCompletedAt = meta.complete ? Date.now() : Number(meta.lastCompletedAt || 0);
    meta.itemCount = Object.values(meta.pages || {}).reduce((total, entry) => {
      return total + Number(entry.count || 0);
    }, 0);
    return meta;
  }

  function applyCacheProgressToState(state, meta) {
    if (!state || !meta) return;

    state.progressLoadedPages = Number(meta.completedPageCount || 0);
    state.progressItemCount = Number(meta.itemCount || 0);
    state.progressTotalPages = Math.max(1, Number(meta.lastPage || 1));
    state.progressTotalApproximate = !Boolean(meta.complete);
    state.lastPage = Math.max(state.lastPage || 1, Number(meta.lastPage || 1));
  }

  function updateCacheMeta(scope, updater) {
    const meta = readJsonStorage(cacheMetaKey(scope));
    if (!meta || meta.version !== CACHE_VERSION) return null;

    const updated = updater(meta) || meta;
    updateCacheMetaProgress(updated);
    try {
      writeJsonStorage(cacheMetaKey(scope), updated);
    } catch (_) {
      // Metadata is best-effort; page chunks remain the source of truth.
    }
    return updated;
  }

  function markCachePageInFlight(state, page) {
    if (!state.cacheEnabled) return;

    const meta = updateCacheMeta(state.cacheScope, (payload) => {
      payload.inFlightPages = {
        ...(payload.inFlightPages || {}),
        [String(page)]: Date.now(),
      };
      payload.complete = false;
      return payload;
    });
    if (meta) state.cacheMeta = meta;
  }

  function pruneCacheAfterLastPage(state, lastPage) {
    const meta = state.cacheMeta || readJsonStorage(cacheMetaKey(state.cacheScope));
    if (!meta || !meta.pages) return;

    let removed = 0;
    for (const page of Object.keys(meta.pages)) {
      const pageNumber = Number(page);
      if (Number.isInteger(pageNumber) && pageNumber > lastPage) {
        removeStorageKey(cachePageKey(state.cacheScope, pageNumber));
        delete meta.pages[page];
        removed += 1;
      }
    }

    if (removed > 0) {
      meta.lastPage = lastPage;
      updateCacheMetaProgress(meta);
      writeJsonStorage(cacheMetaKey(state.cacheScope), meta);
      state.cacheMeta = meta;
      removeIndexedPagesAfter(state, lastPage);
      logger.info('Pruned cached pages after page-count change.', 'lastPage', lastPage, 'removedPages', removed);
    }
  }

  function syncCacheLastPage(state, lastPage) {
    if (!state.cacheEnabled) return;

    const meta = updateCacheMeta(state.cacheScope, (payload) => {
      payload.lastPage = Math.max(1, Number(lastPage || 1));
      return payload;
    });
    if (meta) {
      state.cacheMeta = meta;
      applyCacheProgressToState(state, meta);
    }
  }

  function removeIndexedPagesAfter(state, lastPage) {
    const keptItems = [];
    state.itemsByKey.clear();
    for (const item of state.items) {
      if (item.page > lastPage) continue;
      keptItems.push(item);
      state.itemsByKey.set(itemKey(item), item);
    }
    state.items = keptItems;
    for (const page of Array.from(state.loadedPages)) {
      if (page > lastPage) state.loadedPages.delete(page);
    }
  }

  function removeIndexedPage(state, page) {
    const keptItems = [];
    state.itemsByKey.clear();
    for (const item of state.items) {
      if (item.page === page) continue;
      keptItems.push(item);
      state.itemsByKey.set(itemKey(item), item);
    }
    state.items = keptItems;
    state.loadedPages.delete(page);
  }

  function reconcileLastPage(state, detectedLastPage) {
    const lastPage = Math.max(1, Number(detectedLastPage || 1));
    if (state.lastPage !== lastPage) {
      logger.info('Collection page count changed.', 'from', state.lastPage, 'to', lastPage);
    }
    state.lastPage = lastPage;
    state.progressTotalApproximate = true;
    syncCacheLastPage(state, lastPage);
    pruneCacheAfterLastPage(state, lastPage);
  }

  function queueMissingPages(state, startPage, endPage) {
    let queued = 0;
    for (let page = Math.max(1, Number(startPage || 1)); page <= endPage; page += 1) {
      if (state.loadedPages.has(page) || state.queuedPages.has(page) || state.pendingPages.includes(page)) continue;
      state.pendingPages.push(page);
      state.queuedPages.add(page);
      queued += 1;
    }

    if (queued > 0) {
      state.totalPagesQueued += queued;
      logger.info('Queued newly discovered pages.', 'pages', queued, 'lastPage', state.lastPage);
    }
  }

  function saveCachePage(state, page, items) {
    if (!state.cacheEnabled) return;

    const compactItems = items.map((item) => compactItemForStorage(item, state.route));
    const pagePayload = {
      version: CACHE_VERSION,
      format: 'compact-v4',
      fetchedAt: Date.now(),
      collection: state.route.collection,
      region: state.route.region,
      items: compactItems,
    };

    const existingMeta = readJsonStorage(cacheMetaKey(state.cacheScope));
    const canReuseMeta =
      existingMeta &&
      existingMeta.version === CACHE_VERSION &&
      !state.forceRefresh;
    const meta = state.cacheMeta || (canReuseMeta ? existingMeta : null) || {
      version: CACHE_VERSION,
      indexedAt: Date.now(),
      sourceUrl: makePageUrl(state.route, 1),
      lastPage: state.lastPage,
      itemCount: 0,
      pages: {},
    };

    try {
      writeJsonStorage(cachePageKey(state.cacheScope, page), pagePayload);
      meta.version = CACHE_VERSION;
      meta.indexedAt = Date.now();
      meta.lastAccessedAt = Date.now();
      if (page === 1) {
        meta.lastValidatedAt = Date.now();
      }
      meta.sourceUrl = makePageUrl(state.route, 1);
      meta.lastPage = Math.max(1, Number(state.lastPage || 1));
      if (meta.inFlightPages) {
        delete meta.inFlightPages[String(page)];
        if (Object.keys(meta.inFlightPages).length === 0) {
          delete meta.inFlightPages;
        }
      }
      delete meta.inFlightPage;
      meta.pages[String(page)] = {
        fetchedAt: pagePayload.fetchedAt,
        count: compactItems.length,
      };
      updateCacheMetaProgress(meta);
      writeJsonStorage(cacheMetaKey(state.cacheScope), meta);
      state.cacheMeta = meta;
      applyCacheProgressToState(state, meta);
      enforceCacheBudget(state.cacheScope, protectedCacheScopesForRoute(state.route));
      logger.verbose(
        'Cached page chunk.',
        'page',
        page,
        'items',
        compactItems.length,
        'cachedPages',
        Object.keys(meta.pages).length,
        'complete',
        meta.complete
      );
    } catch (error) {
      state.cacheEnabled = false;
      state.cacheError = 'LocalStorage quota or access failed; using in-memory results only.';
      logger.warn(state.cacheError, error);
      updateStatus(state);
    }
  }

  function compactItemForStorage(item, route) {
    const row = [
      item.title || '',
      compactUrlForStorage(item.url),
    ];
    const flags = itemFilterFlags(item).join(',');
    if (flags) {
      row.push(flags);
    }
    return row;
  }

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[‘’‚‛]/g, "'")
      .replace(/[“”„‟]/g, '"')
      .replace(/[‐‑‒–—―]/g, '-')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  function normalizeQuery(value) {
    return normalizeText(value).replace(/^\*+|\*+$/g, '').trim();
  }

  function sortableTitle(value) {
    return normalizeText(value).replace(/^[^a-z0-9]+/i, '');
  }

  function sortBucketForTitle(value) {
    const first = sortableTitle(value).charAt(0);
    if (/^[a-z]$/i.test(first)) return 0;
    if (/^\d$/.test(first)) return 1;
    return 2;
  }

  function compareItemsForDisplay(a, b) {
    const aTitle = sortableTitle(a && a.title);
    const bTitle = sortableTitle(b && b.title);
    const bucketDiff = sortBucketForTitle(aTitle) - sortBucketForTitle(bTitle);
    if (bucketDiff) return bucketDiff;

    const titleDiff = aTitle.localeCompare(bTitle, undefined, {
      numeric: true,
      sensitivity: 'base',
    });
    if (titleDiff) return titleDiff;

    const pageDiff = (Number(a && a.page) || 0) - (Number(b && b.page) || 0);
    if (pageDiff) return pageDiff;

    return (Number(a && a.sequence) || 0) - (Number(b && b.sequence) || 0);
  }

  function textContent(node) {
    return String(node && node.textContent ? node.textContent : '').replace(/\s+/g, ' ').trim();
  }

  function attr(node, name) {
    return String(node && node.getAttribute(name) ? node.getAttribute(name) : '').trim();
  }

  function absoluteUrl(value, baseUrl = window.location.href) {
    if (!value) return '';
    try {
      return new URL(value, baseUrl).href;
    } catch (_) {
      return '';
    }
  }

  function isPlaceholderImageUrl(value) {
    return /placeholder|\/staticfiles\/i\/svg\//i.test(String(value || ''));
  }

  function srcsetUrls(value) {
    return String(value || '')
      .split(',')
      .map((entry) => entry.trim().split(/\s+/)[0])
      .filter(Boolean);
  }

  function imageCandidatesFromNode(node) {
    if (!node) return [];

    return [
      ...srcsetUrls(attr(node, 'srcset')),
      ...srcsetUrls(attr(node, 'data-srcset')),
      attr(node, 'data-src'),
      attr(node, 'data-lazy-src'),
      attr(node, 'data-original'),
      attr(node, 'src'),
    ].filter(Boolean);
  }

  function isPlatformImage(node) {
    if (!node) return false;
    const alt = attr(node, 'alt');
    const src = attr(node, 'src');
    return Boolean(node.closest('.deal-strip')) || /platforms-unified/i.test(src) || /^PlayStation\s+\d/i.test(alt);
  }

  function findVisualImage(root) {
    const images = Array.from(root.querySelectorAll('img'));
    return (
      images.find((image) => attr(image, 'aria-hidden') !== 'true' && attr(image, 'alt') && !isPlatformImage(image)) ||
      images.slice().reverse().find((image) => !isPlatformImage(image)) ||
      images.slice().reverse()[0] ||
      null
    );
  }

  function uniqueNodes(nodes) {
    const seen = new Set();
    return nodes.filter((node) => {
      if (!node || seen.has(node)) return false;
      seen.add(node);
      return true;
    });
  }

  function bestImageUrl(primaryNode, fallbackRoot, baseUrl) {
    const searchRoots = uniqueNodes([
      primaryNode,
      primaryNode && primaryNode.closest('.aspect-square'),
      primaryNode && primaryNode.closest('.relative.overflow-hidden'),
      fallbackRoot,
    ]);
    const nodes = searchRoots.flatMap((root) => {
      if (!root) return [];
      const self = root.matches && root.matches('source[srcset], source[data-srcset], img[srcset], img[data-srcset], img[data-src], img[data-lazy-src], img[data-original], img[src]')
        ? [root]
        : [];
      return self.concat(Array.from(root.querySelectorAll('source[srcset], source[data-srcset], img[srcset], img[data-srcset], img[data-src], img[data-lazy-src], img[data-original], img[src]')));
    });
    for (const node of nodes) {
      if (node.tagName && node.tagName.toLowerCase() === 'img' && isPlatformImage(node)) continue;
      for (const candidate of imageCandidatesFromNode(node)) {
        const url = absoluteUrl(candidate, baseUrl);
        if (url && !isPlaceholderImageUrl(url)) {
          return url;
        }
      }
    }
    return '';
  }

  function compactUrlForStorage(value) {
    return String(value || '').replace(/^https?:\/\/[^/]+/i, '');
  }

  function itemKey(item) {
    return item.id ? `${item.collection}:${item.id}` : `${item.collection}:${item.url}`;
  }

  function buildSearchText(item) {
    const slugText = item.url
      .replace(/^https?:\/\/[^/]+/i, '')
      .replace(/[-_/]+/g, ' ');

    return normalizeText([
      item.title,
      item.priceText,
      item.platformText,
      item.extraText,
      slugText,
      item.collection,
      item.region,
    ].join(' '));
  }

  function itemFilterFlags(item) {
    const flags = new Set(parseFilterFlags(item && item.filterFlags));
    const priceText = String(item && item.priceText || '');
    const platformText = String(item && item.platformText || '');

    if (/\bfree\b/i.test(priceText)) {
      flags.add('free');
    }
    if (/(?:^|\s)(?:PS3|PlayStation\s*3)(?:\s|$)/i.test(platformText)) {
      flags.add('ps3');
    }
    if (/(?:^|\s)(?:PS4|PlayStation\s*4)(?:\s|$)/i.test(platformText)) {
      flags.add('ps4');
    }
    if (/(?:^|\s)(?:PS5|PlayStation\s*5)(?:\s|$)/i.test(platformText)) {
      flags.add('ps5');
    }

    return Array.from(flags).sort();
  }

  function parseFilterFlags(value) {
    if (Array.isArray(value)) {
      return value.map((entry) => String(entry || '').trim().toLowerCase()).filter(Boolean);
    }
    return String(value || '')
      .split(',')
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean);
  }

  function itemMatchesCollectionFilter(item, collection) {
    const value = String(collection || '').toLowerCase();
    if (!isFilteredCollection(value)) return true;

    const flags = new Set(itemFilterFlags(item));
    if (value.startsWith('free-')) return flags.has('free');
    if (value.startsWith('ps3-')) return flags.has('ps3');
    if (value.startsWith('ps4-')) return flags.has('ps4');
    return true;
  }

  function deriveItemsForRoute(route, items) {
    if (!isFilteredCollection(route.collection)) {
      return items;
    }

    return items
      .filter((item) => itemMatchesCollectionFilter(item, route.collection))
      .map((item) => ({
        ...item,
        collection: route.collection,
        region: route.region,
        priceText: defaultPriceTextForCollection(route.collection) || item.priceText || '',
        platformText: defaultPlatformTextForCollection(route.collection) || item.platformText || '',
        filterFlags: itemFilterFlags(item).join(','),
      }));
  }

  function addItemsToIndex(state, items, source, options = {}) {
    let added = 0;
    for (const rawItem of items) {
      if (!rawItem || !rawItem.url) continue;

      const item = {
        ...rawItem,
        searchText: buildSearchText(rawItem),
        sequence: state.sequence++,
      };
      const key = itemKey(item);
      if (state.itemsByKey.has(key)) continue;

      state.itemsByKey.set(key, item);
      state.items.push(item);
      added += 1;
    }

    if (added > 0) {
      if (!options.deferRender) {
        finalizeIndexMutation(state);
      }
    }

    if (source === 'network') {
      state.networkItemCount += added;
    }

    return added;
  }

  function finalizeIndexMutation(state) {
    state.items.sort(compareItemsForDisplay);
    updateStatus(state);
    runSearch(state);
  }

  function parsePageItems(doc, route, page, pageUrl = window.location.href) {
    return isThemeCollection(route.collection)
      ? parseThemeItems(doc, route, page, pageUrl)
      : parseAvatarItems(doc, route, page, pageUrl);
  }

  function parseAvatarItems(doc, route, page, pageUrl) {
    const cards = Array.from(doc.querySelectorAll('.avatar-card'));
    const items = [];

    for (const card of cards) {
      const link = card.querySelector('a[href*="/region-"][href*="/game/"]');
      if (!link) continue;

      const visualImage = findVisualImage(link);
      const href = absoluteUrl(attr(link, 'href'), pageUrl);
      const title =
        attr(visualImage, 'alt') ||
        textContent(link.querySelector('.line-clamp-1')) ||
        textContent(link);
      const id = extractGameId(href);
      const image = bestImageUrl(visualImage, link, pageUrl);
      const cardText = textContent(card);
      const priceText = extractPriceText(cardText) || defaultPriceTextForCollection(route.collection);

      if (!title || !href) continue;

      items.push({
        id,
        title,
        url: href,
        image,
        priceText,
        page,
        region: route.region,
        collection: route.collection,
        platformText: extractAvatarPlatformText(card, route.collection),
        extraText: limitText(cardText, 500),
      });
      items[items.length - 1].filterFlags = itemFilterFlags(items[items.length - 1]).join(',');
    }

    return items;
  }

  function parseThemeItems(doc, route, page, pageUrl) {
    let roots = Array.from(doc.querySelectorAll('.game-fragment')).filter((root) => {
      return root.querySelector('a[href*="/region-"][href*="/game/"]');
    });

    if (roots.length === 0) {
      roots = Array.from(doc.querySelectorAll('[data-test-id^="game-card-"]'))
        .map((node) => node.closest('.game-fragment') || node.parentElement)
        .filter(Boolean);
    }

    const seenRoots = new Set();
    const items = [];

    for (const root of roots) {
      if (seenRoots.has(root)) continue;
      seenRoots.add(root);

      const link = root.querySelector('a[href*="/region-"][href*="/game/"]');
      if (!link) continue;

      const visualImage = findVisualImage(link);
      const href = absoluteUrl(attr(link, 'href'), pageUrl);
      const title =
        textContent(link.querySelector('h3')) ||
        attr(visualImage, 'alt') ||
        textContent(link);
      const id = extractGameId(href) || attr(root.querySelector('[data-game-id]'), 'data-game-id');
      const image = bestImageUrl(visualImage, link, pageUrl);
      const cardText = textContent(root);
      const priceText = extractPriceText(cardText) || defaultPriceTextForCollection(route.collection);
      const platformText = Array.from(root.querySelectorAll('.deal-strip img[alt], img[alt*="PlayStation"]'))
        .map((imageNode) => attr(imageNode, 'alt'))
        .filter(Boolean)
        .join(' ') || defaultPlatformTextForCollection(route.collection);

      if (!title || !href) continue;

      items.push({
        id,
        title,
        url: href,
        image,
        priceText,
        page,
        region: route.region,
        collection: route.collection,
        platformText,
        extraText: limitText(cardText, 700),
      });
      items[items.length - 1].filterFlags = itemFilterFlags(items[items.length - 1]).join(',');
    }

    return items;
  }

  function parseProductDetailItem(doc, item, route, pageUrl) {
    const product = findProductSchema(doc);
    const image = firstUsableImageUrl([
      schemaImageUrl(product && product.image),
      attr(doc.querySelector('meta[property="og:image:secure_url"]'), 'content'),
      attr(doc.querySelector('meta[property="og:image"]'), 'content'),
      attr(doc.querySelector('meta[name="twitter:image"]'), 'content'),
      bestImageUrl(
        doc.querySelector('.game-detail-hero__cover img[alt]:not([aria-hidden="true"])') ||
          doc.querySelector('.game-detail-hero__cover img[src]') ||
          doc.querySelector('[data-test-id="game-detail-hero"] img[src]'),
        doc.querySelector('[data-test-id="game-detail-hero"]') || doc,
        pageUrl
      ),
    ], pageUrl);

    return {
      id: item.id || extractGameId(pageUrl),
      title: String(product && product.name || item.title || '').trim(),
      url: item.url,
      image,
      priceText: productPriceText(product, route.collection),
      platformText: extractProductDetailPlatformText(doc, route.collection),
      collection: item.collection || route.collection,
      region: item.region || route.region,
      page: item.page || 0,
    };
  }

  function findProductSchema(doc) {
    const scripts = Array.from(doc.querySelectorAll('script[type="application/ld+json"]'));
    for (const script of scripts) {
      const value = parseJsonSafe(script.textContent);
      const product = findProductSchemaNode(value);
      if (product) return product;
    }
    return null;
  }

  function parseJsonSafe(value) {
    try {
      return JSON.parse(String(value || '').trim());
    } catch (_) {
      return null;
    }
  }

  function findProductSchemaNode(value) {
    if (!value) return null;
    if (Array.isArray(value)) {
      for (const entry of value) {
        const product = findProductSchemaNode(entry);
        if (product) return product;
      }
      return null;
    }
    if (typeof value !== 'object') return null;

    const type = value['@type'];
    const types = Array.isArray(type) ? type : [type];
    if (types.some((entry) => String(entry || '').toLowerCase() === 'product')) {
      return value;
    }

    return findProductSchemaNode(value['@graph']);
  }

  function schemaImageUrl(value) {
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) {
      for (const entry of value) {
        const url = schemaImageUrl(entry);
        if (url) return url;
      }
      return '';
    }
    if (typeof value === 'object') {
      return String(value.url || value.contentUrl || value.thumbnailUrl || '').trim();
    }
    return '';
  }

  function firstUsableImageUrl(values, baseUrl) {
    for (const value of values) {
      const url = absoluteUrl(value, baseUrl);
      if (url && !isPlaceholderImageUrl(url)) return url;
    }
    return '';
  }

  function productPriceText(product, collection) {
    if (defaultPriceTextForCollection(collection)) {
      return defaultPriceTextForCollection(collection);
    }

    const offer = firstOffer(product && product.offers);
    const rawPrice = offer && (offer.lowPrice ?? offer.price ?? offer.highPrice);
    const currency = String(offer && offer.priceCurrency || '').trim().toUpperCase();
    if (rawPrice === undefined || rawPrice === null || rawPrice === '') return '';

    const numericPrice = Number(String(rawPrice).replace(/,/g, ''));
    if (Number.isFinite(numericPrice) && numericPrice <= 0) return 'Free';
    if (!Number.isFinite(numericPrice)) return '';

    return `${currencyPrefix(currency)}${formatPriceNumber(numericPrice)}`;
  }

  function firstOffer(value) {
    if (!value) return null;
    if (Array.isArray(value)) {
      return value.find(Boolean) || null;
    }
    if (typeof value === 'object') return value;
    return null;
  }

  function currencyPrefix(currency) {
    const prefixes = {
      AUD: 'AU$',
      CAD: 'CA$',
      NZD: 'NZ$',
      USD: '$',
      EUR: '€',
      GBP: '£',
      JPY: '¥',
    };
    return prefixes[currency] || (currency ? `${currency} ` : '');
  }

  function formatPriceNumber(value) {
    return Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function extractProductDetailPlatformText(doc, collection) {
    const root = doc.querySelector('#platform-badges') || doc;
    return extractAvatarPlatformText(root, collection);
  }

  function extractGameId(url) {
    const match = String(url || '').match(/\/game\/(\d+)(?:\/|$)/i);
    return match ? match[1] : '';
  }

  function extractPriceText(value) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    const freeMatch = text.match(/\bFree\b/i);
    if (freeMatch) return freeMatch[0];

    const priceMatch = text.match(/(?:[A-Z]{1,4}\$|[$€£¥])\s*\d[\d.,]*(?:\s*[-–]\s*(?:[A-Z]{1,4}\$|[$€£¥])?\s*\d[\d.,]*)?/);
    return priceMatch ? priceMatch[0].replace(/\s+/g, ' ').trim() : '';
  }

  function extractAvatarPlatformText(root, collection) {
    const labels = Array.from(root.querySelectorAll('span, img[alt]'))
      .map((node) => node.tagName && node.tagName.toLowerCase() === 'img' ? attr(node, 'alt') : textContent(node))
      .map((text) => String(text || '').trim())
      .filter((text) => /^PS[345]$|^PlayStation\s+[345]$/i.test(text))
      .map((text) => text.replace(/^PlayStation\s+/i, 'PS').toUpperCase());

    return Array.from(new Set(labels)).join(' ') || defaultPlatformTextForCollection(collection);
  }

  function limitText(value, maxLength) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    return text.length > maxLength ? text.slice(0, maxLength) : text;
  }

  function detectLastPage(doc, route) {
    let lastPage = Math.max(1, route.currentPage || 1);
    const links = Array.from(doc.querySelectorAll('a[href], link[href]'));

    for (const link of links) {
      const href = attr(link, 'href');
      if (!href) continue;

      let url;
      try {
        url = new URL(href, window.location.href);
      } catch (_) {
        continue;
      }

      if (url.pathname.replace(/\/+$/, '') !== route.pathname) continue;
      const page = Number(url.searchParams.get('page') || '1');
      if (Number.isInteger(page) && page > lastPage) {
        lastPage = page;
      }
    }

    return lastPage;
  }

  function createState(route, forceRefresh = false, options = {}) {
    const cacheRoute = cacheRouteForRoute(route);
    const scope = cacheScope(cacheRoute);
    const background = Boolean(options.background);
    return {
      token: Math.random().toString(36).slice(2),
      route,
      cacheRoute,
      trackedRoute: route,
      signature: routeSignature(route),
      cacheScope: scope,
      background,
      cacheEnabled: canUseLocalStorage(),
      cacheMeta: null,
      cacheError: '',
      forceRefresh,
      lastPage: 1,
      loadedPages: new Set(),
      failedPages: new Set(),
      queuedPages: new Set(),
      pendingPages: [],
      progressLoadedPages: 0,
      progressItemCount: 0,
      progressTotalPages: 1,
      progressTotalApproximate: true,
      waitingForLease: false,
      waitingOwnerRegion: '',
      waitingOwnerCollection: '',
      waitingReason: '',
      items: [],
      itemsByKey: new Map(),
      sequence: 0,
      networkItemCount: 0,
      nativeGrid: background ? null : findNativeGrid(),
      nativePagination: [],
      ui: null,
      renderedResultNodes: new Map(),
      renderedResultVersions: new Map(),
      renderedResultStaleUntil: new Map(),
      renderedResultRemovalTimer: 0,
      query: '',
      platformFilter: '',
      freeOnly: false,
      controlsLocked: true,
      resultLimit: INITIAL_RENDER_LIMIT,
      searchTimer: null,
      liveDetailHydrationTimer: 0,
      liveDetailItemQueue: [],
      liveDetailQueuedItems: new Set(),
      liveDetailInFlightItems: new Set(),
      liveDetailFetchedItems: new Set(),
      liveDetailFailedItems: new Set(),
      liveDetailFetching: false,
      liveDetailRenderTimer: 0,
      liveDetailAbortControllers: new Map(),
      liveDetailTargetItems: new Set(),
      liveDetailRunId: 0,
      liveDetailSignature: '',
      liveDetailContextSignature: '',
      autoIndexTimer: 0,
      autoIndexEnabled: Boolean(AUTO_INDEX_ON_LOAD),
      autoIndexReady: background,
      indexingDone: false,
      indexStarted: false,
      fetchingStarted: false,
      fetchingPromise: null,
      indexingPaused: false,
      pauseReason: '',
      pausedAt: 0,
      lastResumeAttemptAt: 0,
      hardFailureCount: 0,
      abortControllers: new Set(),
      fetchConcurrency: options.fetchConcurrency || FETCH_CONCURRENCY,
      totalPagesQueued: 0,
    };
  }

  function isStateActive(state) {
    if (!state) return false;
    return state.background ? prewarmState === state : appState === state;
  }

  function findNativeGrid() {
    const themeGrid = document.querySelector('.listing-card-grid');
    if (themeGrid) return themeGrid;

    const avatarCard = document.querySelector('.avatar-card');
    if (avatarCard) {
      return avatarCard.closest('.grid') || avatarCard.parentElement;
    }

    return document.querySelector('[class*="grid"]');
  }

  function findNativePagination(nativeGrid) {
    if (!nativeGrid || !nativeGrid.parentElement) return [];

    const parent = nativeGrid.parentElement;
    const candidates = Array.from(parent.querySelectorAll('nav, .join, .pagination, [class*="pagination"], [class*="join"]'));
    return candidates.filter((element) => {
      if (element.closest(`[${OWNER_ATTR}]`)) return false;
      return Boolean(element.querySelector('a[href*="page="]'));
    });
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      html.pspls-route-avatars div[role="tablist"].tabs.tabs-box { display: none !important; }
      html.pspls-route-avatars .avatar-card[hx-swap] { display: none !important; }
      html.pspls-route-avatars nav[aria-label="Pagination"] { display: none !important; }
      html.pspls-route-avatars nav:has(a[href*="/collection/avatars?page="]),
      html.pspls-route-avatars .join:has(a[href*="/collection/avatars?page="]),
      html.pspls-route-avatars .pagination:has(a[href*="/collection/avatars?page="]),
      html.pspls-route-avatars [class*="pagination"]:has(a[href*="/collection/avatars?page="]) { display: none !important; }
      html.pspls-route-avatars a[href*="/collection/avatars?page="] { display: none !important; }
      html.pspls-route-themes [data-test-id="platforms-stripe"] { display: none !important; }
      html.pspls-route-themes .flex.items-center.gap-2.shrink-0 { display: none !important; }
      html.pspls-route-themes .listing-card-grid:not([${RESULTS_ATTR}="true"]) { display: none !important; }
      html.pspls-route-themes nav[aria-label="Pagination"] { display: none !important; }
      html.pspls-route-themes nav:has(a[href*="/collection/themes?page="]),
      html.pspls-route-themes .join:has(a[href*="/collection/themes?page="]),
      html.pspls-route-themes .pagination:has(a[href*="/collection/themes?page="]),
      html.pspls-route-themes [class*="pagination"]:has(a[href*="/collection/themes?page="]) { display: none !important; }
      html.pspls-route-themes a[href*="/collection/themes?page="] { display: none !important; }
      [${OWNER_ATTR}] input[type="search"]::-webkit-search-cancel-button,
      [${OWNER_ATTR}] input[type="search"]::-webkit-search-decoration {
        -webkit-appearance: none;
        appearance: none;
        display: none;
      }
      [${OWNER_ATTR}] .pspls-hidden { display: none !important; }
      [${HIDDEN_ATTR}="true"] { display: none !important; }
      [${OWNER_ATTR}] .pspls-status-spinner {
        display: inline-block;
        width: 0.45rem;
        height: 0.45rem;
        margin-left: 0.45rem;
        border-radius: 9999px;
        background: currentColor;
        opacity: 0.65;
        vertical-align: 0.08em;
        animation: pspls-status-pulse 900ms ease-in-out infinite;
      }
      @keyframes pspls-status-pulse {
        0%, 100% { transform: scale(0.75); opacity: 0.35; }
        50% { transform: scale(1); opacity: 0.95; }
      }
      @media (prefers-reduced-motion: reduce) {
        [${OWNER_ATTR}] .pspls-status-spinner { animation: none; opacity: 0.75; }
      }
    `;
    const styleRoot = document.head || document.documentElement || document.body;
    if (styleRoot) {
      styleRoot.appendChild(style);
    }
  }

  function updateRouteClass(route = parseRoute()) {
    const root = document.documentElement;
    if (!root) return;

    root.classList.remove(...ROUTE_CLASSES);
    if (route) {
      root.classList.add(`${ROUTE_CLASS_PREFIX}${route.collection}`);
    }
  }

  function buildUi(state) {
    injectStyles();

    const panel = document.createElement('section');
    panel.setAttribute(OWNER_ATTR, 'panel');
    panel.className = 'rounded-lg border border-border bg-elevation1 p-3 sm:p-4 mb-4 shadow-sm';

    const header = document.createElement('div');
    header.className = 'flex flex-col sm:flex-row sm:items-center gap-3';

    const inputWrap = document.createElement('label');
    inputWrap.className = 'relative flex-1 block';

    const searchIcon = document.createElement('span');
    searchIcon.className = 'material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-base-content/50 text-[20px]';
    searchIcon.textContent = 'search';

    const input = document.createElement('input');
    input.type = 'search';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.placeholder = 'Search this collection...';
    input.className = 'input input-sm w-full pl-10 pr-10';

    const clearButton = iconButton('close', 'Clear search');
    clearButton.type = 'button';
    clearButton.className += ' pspls-hidden absolute right-1.5 top-1/2 -translate-y-1/2';
    clearButton.addEventListener('click', () => {
      input.value = '';
      state.query = '';
      state.resultLimit = INITIAL_RENDER_LIMIT;
      runSearch(state);
      input.focus();
    });

    inputWrap.append(searchIcon, input, clearButton);

    const actions = document.createElement('div');
    actions.className = 'flex items-center gap-2';

    const clearRegionButton = textButton(`Clear Cache (${state.route.region.toUpperCase()})`);
    clearRegionButton.type = 'button';
    clearRegionButton.className = 'btn btn-sm btn-outline whitespace-nowrap shadow-sm';
    clearRegionButton.title = `Clear and rebuild live-search cache for ${state.route.region.toUpperCase()}`;
    clearRegionButton.addEventListener('click', () => {
      if (!window.confirm(`Clear and rebuild PSPrices live-search cache for ${state.route.region.toUpperCase()}?`)) {
        return;
      }
      clearRegionCache(state.route);
      teardownApp();
      startApp(false);
      startRegionPrewarm(true);
    });

    const status = document.createElement('div');
    status.className = 'text-xs sm:text-sm text-secondary tabular-nums min-w-0';
    status.textContent = 'Preparing index...';

    actions.append(clearRegionButton);
    header.append(inputWrap, actions);

    const filterRow = document.createElement('div');
    filterRow.className = 'mt-3 flex flex-col sm:flex-row sm:items-center gap-3';

    const platformWrap = document.createElement('div');
    platformWrap.className = 'relative w-full sm:w-44 h-9 min-h-9';

    const platformSelectShell = document.createElement('div');
    platformSelectShell.className = 'input input-sm w-full h-9 min-h-9 flex items-center justify-between gap-2 py-0 font-semibold pointer-events-none';

    const platformSelectText = document.createElement('span');
    platformSelectText.className = 'flex items-center h-full leading-none font-semibold';
    platformSelectText.textContent = 'All platforms';

    const platformSelectIcon = document.createElement('span');
    platformSelectIcon.className = 'material-symbols-outlined text-[20px] text-secondary';
    platformSelectIcon.textContent = 'expand_more';

    platformSelectShell.append(platformSelectText, platformSelectIcon);

    const platformSelect = document.createElement('select');
    platformSelect.className = 'absolute inset-0 h-9 w-full cursor-pointer opacity-0';
    platformSelect.title = 'Filter by platform';
    platformSelect.setAttribute('aria-label', 'Filter by platform');
    for (const [value, label] of [
      ['', 'All platforms'],
      ['ps3', 'PS3'],
      ['ps4', 'PS4'],
      ['ps5', 'PS5'],
    ]) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      platformSelect.appendChild(option);
    }
    platformWrap.append(platformSelectShell, platformSelect);

    const freeOnlyLabel = document.createElement('label');
    freeOnlyLabel.className = 'label cursor-pointer justify-start gap-2 px-0 py-0 min-h-9';

    const freeOnlyCheckbox = document.createElement('input');
    freeOnlyCheckbox.type = 'checkbox';
    freeOnlyCheckbox.className = 'checkbox checkbox-sm checkbox-primary self-center';
    freeOnlyCheckbox.setAttribute('aria-label', 'Show free items only');

    const freeOnlyText = document.createElement('span');
    freeOnlyText.className = 'label-text text-sm font-semibold text-secondary whitespace-nowrap leading-9';
    freeOnlyText.textContent = 'Free only';

    freeOnlyLabel.append(freeOnlyCheckbox, freeOnlyText);
    filterRow.append(platformWrap, freeOnlyLabel);

    const statusRow = document.createElement('div');
    statusRow.className = 'mt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2';

    const progress = document.createElement('progress');
    progress.className = 'progress progress-primary w-full sm:max-w-xs h-1.5';
    progress.max = 1;
    progress.value = 0;

    statusRow.append(status, progress);

    const resultGrid = document.createElement('div');
    resultGrid.setAttribute(RESULTS_ATTR, 'true');
    resultGrid.className = resultGridClass(state.route.collection);

    const empty = document.createElement('div');
    empty.className = 'pspls-hidden text-sm text-secondary py-6';

    const showMore = document.createElement('button');
    showMore.type = 'button';
    showMore.className = 'btn btn-sm btn-outline mt-4 pspls-hidden';
    showMore.textContent = 'Show more';
    showMore.addEventListener('click', () => {
      if (isInteractionLocked(state)) {
        syncInteractionLock(state);
        runSearch(state, { preserveStaleResults: false });
        return;
      }
      const nextLimit = state.resultLimit + RENDER_STEP;
      state.resultLimit = MAX_RENDER_LIMIT < 0 ? nextLimit : Math.min(MAX_RENDER_LIMIT, nextLimit);
      cancelLiveDetailHydration(state);
      runSearch(state);
    });

    panel.append(header, filterRow, statusRow, empty, resultGrid, showMore);

    input.addEventListener('input', () => {
      state.query = input.value;
      state.resultLimit = INITIAL_RENDER_LIMIT;
      cancelLiveDetailHydration(state);
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(() => runSearch(state), INPUT_DEBOUNCE_MS);
    });

    platformSelect.addEventListener('change', () => {
      state.platformFilter = platformSelect.value;
      platformSelectText.textContent = platformSelect.options[platformSelect.selectedIndex].textContent || 'All platforms';
      applyFilterChange(state);
    });

    freeOnlyCheckbox.addEventListener('change', () => {
      state.freeOnly = freeOnlyCheckbox.checked;
      applyFilterChange(state);
    });

    const mountBefore = state.nativeGrid || document.querySelector('main') || document.body.firstElementChild;
    if (mountBefore && mountBefore.parentElement) {
      mountBefore.parentElement.insertBefore(panel, mountBefore);
    } else {
      document.body.prepend(panel);
    }

    state.nativePagination = findNativePagination(state.nativeGrid);
    setNativeHidden(true, state);

    state.ui = {
      panel,
      input,
      clearButton,
      platformSelect,
      platformSelectText,
      freeOnlyCheckbox,
      clearRegionButton,
      status,
      progress,
      resultGrid,
      empty,
      showMore,
    };
    syncInteractionLock(state);

    return state.ui;
  }

  function iconButton(icon, label) {
    const button = document.createElement('button');
    button.className = 'btn btn-sm btn-ghost btn-square';
    button.title = label;
    button.setAttribute('aria-label', label);

    const iconNode = document.createElement('span');
    iconNode.className = 'material-symbols-outlined text-[20px]';
    iconNode.textContent = icon;
    button.appendChild(iconNode);

    return button;
  }

  function textButton(label) {
    const button = document.createElement('button');
    button.className = 'btn btn-sm btn-ghost whitespace-nowrap';
    button.textContent = label;
    return button;
  }

  function resultGridClass(collection) {
    if (isThemeCollection(collection)) {
      return 'listing-card-grid mt-4';
    }

    return 'grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-7 xl:grid-cols-9 gap-4 sm:gap-5 md:gap-6 mt-4';
  }

  function displayRegion(region) {
    return String(region || '').toUpperCase();
  }

  function displayCollection(collection) {
    const value = String(collection || '').toLowerCase();
    if (value === 'avatars') return 'Avatars';
    if (value === 'themes') return 'Themes';
    return value ? value.replace(/-/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : 'Collection';
  }

  function updateStatus(state) {
    if (!state.ui) return;

    const loaded = Number(state.progressLoadedPages || 0);
    const total = Math.max(state.progressTotalPages || 1, loaded || 1);
    const itemCount = Number(state.progressItemCount || 0);
    const statusFailedPages = state.statusFailedPages || state.failedPages;
    const failedCount = statusFailedPages.size;
    const cacheNote = state.cacheError ? ` ${state.cacheError}` : '';
    const failureNote = failedCount ? ` ${failedCount} page${failedCount === 1 ? '' : 's'} failed.` : '';
    const trackedRoute = state.trackedRoute || state.cacheRoute || state.route;
    const trackedScope = cacheScope(cacheRouteForRoute(trackedRoute));
    const totalSuffix = state.progressTotalApproximate && trackedScope !== state.cacheScope ? '+' : '';
    const trackedTarget = `${displayCollection(trackedRoute.collection)} (${displayRegion(trackedRoute.region)})`;
    let stateNote = 'Loading cached pages; background indexing continues.';

    if (state.indexingPaused) {
      stateNote = `Paused: ${state.pauseReason}`;
    } else if (state.fetchingStarted) {
      stateNote = isFilteredCollection(trackedRoute.collection)
        ? `Loading ${trackedTarget} filter...`
        : `Indexing ${trackedTarget}...`;
    } else if (state.indexingDone && loaded >= total) {
      stateNote = 'Indexed cached pages.';
    } else if (state.indexingDone) {
      stateNote = 'Using cached pages; background indexing continues.';
    } else if (loaded >= total) {
      stateNote = 'Indexed cached pages.';
    }

    if (state.waitingForLease) {
      const localCollection = cacheRouteForRoute(state.route).collection;
      const localTarget = `${displayCollection(localCollection)} (${displayRegion(state.route.region)})`;
      const ownerTarget = state.waitingOwnerRegion
        ? `${displayCollection(state.waitingOwnerCollection)} (${displayRegion(state.waitingOwnerRegion)})`
        : 'another tab';
      stateNote = `Queued ${localTarget}; ${ownerTarget} is indexing. ${stateNote}`;
    }

    const wasControlsLocked = Boolean(state.controlsLocked);
    state.ui.status.textContent = `${stateNote} ${itemCount} item${itemCount === 1 ? '' : 's'} from ${loaded} / ${total}${totalSuffix} page${total === 1 ? '' : 's'}.${failureNote}${cacheNote}`;
    const regionProgress = readRegionCacheProgress(state);
    state.ui.progress.max = regionProgress.totalPages;
    state.ui.progress.value = Math.min(regionProgress.loadedPages, regionProgress.totalPages);
    state.ui.progress.title = `Region cache progress: ${regionProgress.loadedPages} / ${regionProgress.totalPages}${regionProgress.approximate ? '+' : ''} pages across avatars and themes.`;
    syncInteractionLock(state);
    refreshResultStatusWorking(state);
    if (wasControlsLocked && !state.controlsLocked) {
      logger.info('Region caches complete; rendering collection results.', state.route.region, state.route.collection);
      runSearch(state, { preserveStaleResults: false });
    }
  }

  function useLocalStatusProgress(state) {
    if (!state) return;

    state.trackedRoute = state.cacheRoute || state.route;
    state.statusFailedPages = new Set(state.failedPages);
    state.waitingForLease = false;
    state.waitingOwnerRegion = '';
    state.waitingOwnerCollection = '';
    state.waitingReason = '';
    state.fetchingStarted = false;
    state.indexingPaused = false;
    state.pauseReason = '';

    const meta = readJsonStorage(cacheMetaKey(state.cacheScope));
    if (meta && meta.version === CACHE_VERSION) {
      updateCacheMetaProgress(meta);
      applyCacheProgressToState(state, meta);
      state.indexingDone = Boolean(meta.complete);
      return;
    }

    state.progressLoadedPages = state.loadedPages.size;
    state.progressItemCount = state.items.length;
    state.progressTotalPages = Math.max(1, state.lastPage || state.loadedPages.size || 1);
    state.progressTotalApproximate = state.loadedPages.size < state.progressTotalPages;
    state.indexingDone = state.progressLoadedPages >= state.progressTotalPages;
  }

  function collectionCacheProgress(state, collection) {
    const route = makeCollectionRoute({
      host: state.route.host,
      origin: state.route.origin,
      region: state.route.region,
      language: state.route.language,
    }, collection);
    const scope = cacheScope(route);
    const progress = {
      loadedPages: 0,
      totalPages: 1,
      itemCount: 0,
      approximate: true,
      complete: false,
    };

    const meta = readJsonStorage(cacheMetaKey(scope));
    if (meta && meta.version === CACHE_VERSION) {
      updateCacheMetaProgress(meta);
      progress.loadedPages = Number(meta.completedPageCount || 0);
      progress.totalPages = Math.max(1, Number(meta.lastPage || 1));
      progress.itemCount = Number(meta.itemCount || 0);
      progress.approximate = !Boolean(meta.complete);
      progress.complete = Boolean(meta.complete);
    }

    if (prewarmState && prewarmState.cacheScope === scope) {
      const loaded = Number(prewarmState.progressLoadedPages || prewarmState.loadedPages.size || 0);
      const total = Math.max(1, Number(prewarmState.progressTotalPages || prewarmState.lastPage || loaded || 1));
      progress.loadedPages = Math.max(progress.loadedPages, loaded);
      progress.totalPages = Math.max(progress.totalPages, total);
      progress.itemCount = Math.max(progress.itemCount, Number(prewarmState.progressItemCount || prewarmState.items.length || 0));
      progress.approximate = Boolean(prewarmState.progressTotalApproximate || !prewarmState.indexingDone);
      progress.complete = Boolean(prewarmState.indexingDone && !prewarmState.indexingPaused && progress.loadedPages >= progress.totalPages);
    } else if (state.cacheScope === scope) {
      const loaded = Number(state.loadedPages.size || 0);
      const total = Math.max(1, Number(state.lastPage || loaded || 1));
      progress.loadedPages = Math.max(progress.loadedPages, loaded);
      progress.totalPages = Math.max(progress.totalPages, total);
      progress.itemCount = Math.max(progress.itemCount, Number(state.items.length || 0));
      if (!progress.complete) {
        progress.approximate = progress.loadedPages < progress.totalPages;
        progress.complete = Boolean(state.indexingDone && !state.indexingPaused && progress.loadedPages >= progress.totalPages);
      }
    }

    return progress;
  }

  function readRegionCacheProgress(state) {
    if (!state) {
      return {
        loadedPages: 0,
        totalPages: 1,
        itemCount: 0,
        approximate: true,
        complete: false,
      };
    }

    const combined = PREWARM_COLLECTIONS
      .map((collection) => collectionCacheProgress(state, collection))
      .reduce((total, progress) => ({
        loadedPages: total.loadedPages + progress.loadedPages,
        totalPages: total.totalPages + progress.totalPages,
        itemCount: total.itemCount + progress.itemCount,
        approximate: total.approximate || progress.approximate,
        complete: total.complete && progress.complete,
      }), {
        loadedPages: 0,
        totalPages: 0,
        itemCount: 0,
        approximate: false,
        complete: true,
      });

    combined.totalPages = Math.max(1, combined.totalPages);
    combined.loadedPages = Math.min(combined.loadedPages, combined.totalPages);
    return combined;
  }

  function isRegionCacheProgressKey(state, key) {
    if (!state || !key) return false;
    return Array.from(protectedCacheScopesForRoute(state.route))
      .some((scope) => key === cacheMetaKey(scope));
  }

  function setNativeHidden(hidden, state) {
    const value = hidden ? 'true' : 'false';
    if (state.nativeGrid) {
      state.nativeGrid.setAttribute(HIDDEN_ATTR, value);
    }
    for (const element of state.nativePagination) {
      element.setAttribute(HIDDEN_ATTR, value);
    }
  }

  function isCacheScopeComplete(scope) {
    if (!scope) return false;

    const meta = readJsonStorage(cacheMetaKey(scope));
    if (meta && meta.version === CACHE_VERSION) {
      updateCacheMetaProgress(meta);
      if (meta.complete) return true;
    }

    return false;
  }

  function isStateCacheScopeComplete(state) {
    if (!state) return false;

    if (isCacheScopeComplete(state.cacheScope)) return true;

    if (!state.cacheEnabled) {
      return Boolean(
        state.indexingDone &&
          state.loadedPages.size >= Math.max(1, state.lastPage || 1) &&
          state.failedPages.size === 0 &&
          !state.indexingPaused
      );
    }

    return Boolean(
      state.indexingDone &&
        state.loadedPages.size >= Math.max(1, state.lastPage || 1) &&
        state.failedPages.size === 0 &&
        !state.fetchingStarted &&
        !state.indexingPaused &&
        !isBackgroundIndexingScope(state.cacheScope)
    );
  }

  function isRegionCacheComplete(state) {
    if (!state) return false;

    if (!state.cacheEnabled) {
      return isStateCacheScopeComplete(state);
    }

    const context = {
      host: state.route.host,
      origin: state.route.origin,
      region: state.route.region,
      language: state.route.language,
    };

    return PREWARM_COLLECTIONS.every((collection) => {
      const route = makeCollectionRoute(context, collection);
      const scope = cacheScope(route);
      return scope === state.cacheScope
        ? isStateCacheScopeComplete(state)
        : isCacheScopeComplete(scope);
    });
  }

  function isInteractionLocked(state) {
    return !isRegionCacheComplete(state);
  }

  function resetInteractiveFiltersForLock(state) {
    if (!state || !state.ui) return;

    state.query = '';
    state.platformFilter = '';
    state.freeOnly = false;
    state.resultLimit = INITIAL_RENDER_LIMIT;

    state.ui.input.value = '';
    state.ui.platformSelect.value = '';
    state.ui.platformSelectText.textContent = 'All platforms';
    state.ui.freeOnlyCheckbox.checked = false;
    state.ui.clearButton.classList.add('pspls-hidden');
  }

  function syncInteractionLock(state) {
    if (!state || !state.ui) return;

    const locked = isInteractionLocked(state);
    const target = displayRegion(state.route.region);
    const title = locked
      ? `Search, filters, Show more, and full detail loading unlock when all ${target} region caches reach 100%.`
      : '';

    if (locked) {
      resetInteractiveFiltersForLock(state);
    }

    state.controlsLocked = locked;
    state.ui.input.disabled = locked;
    state.ui.input.title = title;
    state.ui.platformSelect.disabled = locked;
    state.ui.platformSelect.title = title || 'Filter by platform';
    state.ui.freeOnlyCheckbox.disabled = locked;
    state.ui.freeOnlyCheckbox.title = title;
    state.ui.showMore.disabled = locked;
    state.ui.showMore.title = title;
  }

  function applyFilterChange(state) {
    if (!state || !state.ui) return;
    if (isInteractionLocked(state)) {
      resetInteractiveFiltersForLock(state);
      runSearch(state, { preserveStaleResults: false });
      return;
    }

    clearTimeout(state.searchTimer);
    state.resultLimit = INITIAL_RENDER_LIMIT;
    cancelLiveDetailHydration(state);
    clearRenderedResults(state);
    runSearch(state, { preserveStaleResults: false });
  }

  function runSearch(state, options = {}) {
    if (!state || !state.ui) return;

    const controlsLocked = isInteractionLocked(state);
    if (controlsLocked) {
      resetInteractiveFiltersForLock(state);
    }

    const query = normalizeQuery(state.query);
    const hasQuery = query.length > 0;
    setNativeHidden(true, state);

    if (hasQuery) {
      state.ui.clearButton.classList.remove('pspls-hidden');
      tryResumePausedIndexing(state, query);
    } else {
      state.ui.clearButton.classList.add('pspls-hidden');
    }

    const terms = query.split(/\s+/).filter(Boolean);
    const queryMatches = state.items.filter((item) => {
      if (!hasQuery) return true;
      if (item.searchText.includes(query)) return true;
      return terms.length > 1 && terms.every((term) => item.searchText.includes(term));
    }).sort(compareItemsForDisplay);
    const needsConfirmedDetails = !controlsLocked && filteredResultsNeedConfirmedDetails(state);
    const emptyQueryFilterWindowLimit = needsConfirmedDetails && !hasQuery
      ? Math.min(state.resultLimit, maxRenderableResults(queryMatches.length))
      : queryMatches.length;
    const filterCandidatePool = needsConfirmedDetails && !hasQuery
      ? queryMatches.slice(0, emptyQueryFilterWindowLimit)
      : queryMatches;
    const resultPool = needsConfirmedDetails && !hasQuery
      ? filterCandidatePool
      : queryMatches;
    const results = resultPool.filter((item) => itemMatchesUiFilters(item, state));
    const hydrationCandidates = needsConfirmedDetails
      ? limitLiveDetailFilterCandidates(filterCandidatePool.filter((item) => itemNeedsUiFilterHydration(item, state)))
      : [];
    const totalResultCount = needsConfirmedDetails && !hasQuery
      ? queryMatches.length
      : results.length;
    const checkedResultCount = needsConfirmedDetails && !hasQuery
      ? emptyQueryFilterWindowLimit
      : results.length;

    logger.verbose(
      'Search updated.',
      'queryLength',
      query.length,
      'platform',
      state.platformFilter || 'all',
      'freeOnly',
      state.freeOnly,
      'results',
      results.length,
      'candidateResults',
      queryMatches.length,
      'detailCandidates',
      hydrationCandidates.length,
      'checkedCandidates',
      checkedResultCount,
      'indexedItems',
      state.items.length,
      'controlsLocked',
      controlsLocked
    );
    renderResults(state, results, {
      ...options,
      hydrationCandidates,
      confirmedMode: needsConfirmedDetails,
      totalResultCount,
      checkedResultCount,
    });
  }

  function itemMatchesUiFilters(item, state) {
    if (filteredResultsNeedConfirmedDetails(state) && needsLiveDetailHydration(item)) {
      return false;
    }

    const flags = new Set(itemFilterFlags(item));
    if (state.platformFilter && !flags.has(state.platformFilter)) {
      return false;
    }
    if (state.freeOnly && !flags.has('free')) {
      return false;
    }
    return true;
  }

  function filteredResultsNeedConfirmedDetails(state) {
    return Boolean(state && (state.platformFilter || state.freeOnly));
  }

  function hasKnownPlatformFlags(item) {
    const flags = new Set(itemFilterFlags(item));
    return flags.has('ps3') || flags.has('ps4') || flags.has('ps5');
  }

  function hasKnownPriceFlags(item) {
    return Boolean(String(item && item.priceText || '').trim());
  }

  function itemNeedsUiFilterHydration(item, state) {
    if (!item || !item.url || !needsLiveDetailHydration(item)) return false;

    const flags = new Set(itemFilterFlags(item));
    const hasPlatformFlags = hasKnownPlatformFlags(item);
    const hasPriceFlags = hasKnownPriceFlags(item);

    if (state.platformFilter) {
      if (!hasPlatformFlags) return true;
      if (!flags.has(state.platformFilter)) return false;
    }
    if (state.freeOnly) {
      if (!hasPriceFlags) return true;
      if (!flags.has('free')) return false;
    }
    return true;
  }

  function limitLiveDetailFilterCandidates(items) {
    if (LIVE_DETAIL_FILTER_CANDIDATE_BATCH < 0) return items;
    return items.slice(0, LIVE_DETAIL_FILTER_CANDIDATE_BATCH);
  }

  function tryResumePausedIndexing(state, query) {
    if (!state || state.background || query.length < FETCH_QUERY_MIN_LENGTH) {
      return;
    }

    const context = parseRegionContext();
    if (!context) return;

    const signature = regionSignature(context);
    const now = Date.now();
    const pausedAt = prewarmState && prewarmState.signature === signature && prewarmState.indexingPaused
      ? prewarmState.pausedAt || 0
      : 0;
    const lastAttemptAt = Math.max(pausedAt, lastPrewarmResumeAttemptAt);
    if (now - lastAttemptAt < PAUSED_SEARCH_RESUME_COOLDOWN_MS) {
      logger.verbose('Paused background indexing resume deferred by cooldown.', 'remainingMs', PAUSED_SEARCH_RESUME_COOLDOWN_MS - (now - lastAttemptAt));
      return;
    }

    lastPrewarmResumeAttemptAt = now;
    if (prewarmState && prewarmState.signature === signature && prewarmState.indexingPaused) {
      logger.info('Resuming paused background region indexing from search input.', context.region);
      teardownRegionPrewarm();
    }
    startRegionPrewarm(false);
  }

  function isBackgroundIndexingScope(scope) {
    return Boolean(
      prewarmState &&
      prewarmState.cacheScope === scope &&
      !prewarmState.indexingDone &&
      !prewarmState.indexingPaused
    );
  }

  function isBackgroundIndexingRegion(state) {
    return Boolean(
      state &&
        prewarmState &&
        prewarmState.route &&
        prewarmState.route.host === state.route.host &&
        prewarmState.route.region === state.route.region &&
        prewarmState.route.language === state.route.language &&
        !prewarmState.indexingDone &&
        !prewarmState.indexingPaused
    );
  }

  function maxRenderableResults(total) {
    if (MAX_RENDER_LIMIT < 0) return total;
    return Math.min(MAX_RENDER_LIMIT, total);
  }

  function renderResults(state, results, options = {}) {
    const totalResultCount = Number.isFinite(options.totalResultCount)
      ? Math.max(0, Number(options.totalResultCount))
      : results.length;
    const checkedResultCount = Number.isFinite(options.checkedResultCount)
      ? Math.max(0, Number(options.checkedResultCount))
      : results.length;
    const hardLimit = maxRenderableResults(totalResultCount);
    const limit = Math.min(state.resultLimit, hardLimit);
    const visibleResults = results.slice(0, limit);
    const hydrationCandidates = Array.isArray(options.hydrationCandidates)
      ? options.hydrationCandidates
      : [];
    const confirmedMode = Boolean(options.confirmedMode);
    const controlsLocked = isInteractionLocked(state);

    if (controlsLocked) {
      clearRenderedResults(state);
      cancelLiveDetailHydration(state);
      state.ui.showMore.classList.add('pspls-hidden');
      setResultStatus(
        state,
        `Region caches are building. Results unlock when avatars and themes reach 100%.`,
        isResultStatusWorking(state, hydrationCandidates)
      );
      state.ui.empty.classList.remove('pspls-hidden');
      return;
    }

    reconcileRenderedResults(state, visibleResults, {
      preserveStaleResults: options.preserveStaleResults !== false,
    });

    if (results.length === 0) {
      const moreCacheMayArrive = state.loadedPages.size < state.lastPage || isBackgroundIndexingScope(state.cacheScope);
      setResultStatus(state, confirmedMode
        ? '0 confirmed results found.'
        : !moreCacheMayArrive
        ? 'No collection items found.'
        : 'No indexed items found yet. More pages are still indexing.',
        isResultStatusWorking(state, hydrationCandidates)
      );
      state.ui.empty.classList.remove('pspls-hidden');
    } else {
      const capNote = MAX_RENDER_LIMIT >= 0 && results.length > MAX_RENDER_LIMIT
        ? ` Showing ${limit} of ${results.length}; refine search to narrow results.`
        : '';
      const resultLabel = confirmedMode
        ? `confirmed result${results.length === 1 ? '' : 's'}`
        : `result${results.length === 1 ? '' : 's'}`;
      setResultStatus(
        state,
        `${results.length} ${resultLabel} found.${capNote}`,
        isResultStatusWorking(state, hydrationCandidates)
      );
      state.ui.empty.classList.remove('pspls-hidden');
    }

    if (limit < hardLimit) {
      state.ui.showMore.textContent = `Show more (${hardLimit - limit} remaining)`;
      state.ui.showMore.classList.remove('pspls-hidden');
    } else {
      state.ui.showMore.classList.add('pspls-hidden');
    }

    if (!options.skipLiveDetailHydration) {
      scheduleLiveDetailHydration(state, visibleResults, hydrationCandidates);
    }
  }

  function scheduleLiveDetailHydration(state, visibleResults, hydrationCandidates = []) {
    if (!LIVE_DETAIL_HYDRATION_ENABLED || !state || state.background || !state.ui) return;

    const maxItems = LIVE_DETAIL_MAX_ITEMS_PER_RENDER < 0 ? Number.POSITIVE_INFINITY : LIVE_DETAIL_MAX_ITEMS_PER_RENDER;
    const combinedResults = [];
    const seenKeys = new Set();
    for (const item of visibleResults.concat(hydrationCandidates)) {
      const key = itemKey(item);
      if (!key || seenKeys.has(key)) continue;
      seenKeys.add(key);
      combinedResults.push(item);
    }

    const targetItems = [];
    for (const item of combinedResults) {
      if (!item || !item.url || !needsLiveDetailHydration(item)) continue;
      const key = itemKey(item);
      if (
        state.liveDetailFetchedItems.has(key) ||
        state.liveDetailFailedItems.has(key)
      ) {
        continue;
      }

      targetItems.push(item);
      if (targetItems.length >= maxItems) break;
    }

    const signature = targetItems.map(itemKey).join('|');
    if (!signature) {
      cancelLiveDetailHydration(state);
      state.liveDetailSignature = '';
      state.liveDetailContextSignature = '';
      refreshResultStatusWorking(state);
      return;
    }

    const contextSignature = liveDetailContextSignature(state);
    if (state.liveDetailFetching && contextSignature === state.liveDetailContextSignature) {
      refreshResultStatusWorking(state);
      return;
    }

    if (signature !== state.liveDetailSignature || contextSignature !== state.liveDetailContextSignature) {
      retargetLiveDetailHydration(state, targetItems, signature, contextSignature);
    }

    if (state.liveDetailItemQueue.length === 0 || state.liveDetailFetching) return;

    clearTimeout(state.liveDetailHydrationTimer);
    state.liveDetailHydrationTimer = setTimeout(() => {
      hydrateLiveDetailQueue(state).catch((error) => {
        logger.warn('Live detail hydration failed.', error);
      });
    }, LIVE_DETAIL_HYDRATION_DELAY_MS);
  }

  function setResultStatus(state, text, working = false) {
    if (!state || !state.ui || !state.ui.empty) return;

    state.ui.empty.replaceChildren(document.createTextNode(text || ''));
    setResultStatusWorking(state, working || isCacheIndexingActive(state));
  }

  function setResultStatusWorking(state, working) {
    if (!state || !state.ui || !state.ui.empty) return;

    const existing = state.ui.empty.querySelector('.pspls-status-spinner');
    if (!working) {
      if (existing) existing.remove();
      return;
    }

    if (existing) return;

    const spinner = document.createElement('span');
    spinner.className = 'pspls-status-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    state.ui.empty.appendChild(spinner);
  }

  function isLiveDetailHydrationActive(state) {
    return Boolean(
      state &&
        (
          state.liveDetailFetching ||
          state.liveDetailItemQueue.length > 0 ||
          state.liveDetailQueuedItems.size > 0 ||
          state.liveDetailInFlightItems.size > 0
        )
    );
  }

  function isCacheIndexingActive(state) {
    return Boolean(
      state &&
        (
          state.waitingForLease ||
          (state.fetchingStarted && !state.indexingDone && !state.indexingPaused) ||
          Boolean(state.fetchingPromise && !state.indexingDone && !state.indexingPaused) ||
          (Array.isArray(state.pendingPages) && state.pendingPages.length > 0 && !state.indexingDone && !state.indexingPaused) ||
          (state.queuedPages && state.queuedPages.size > 0 && !state.indexingDone && !state.indexingPaused) ||
          isBackgroundIndexingScope(state.cacheScope) ||
          isBackgroundIndexingRegion(state)
        )
    );
  }

  function isResultStatusWorking(state, hydrationCandidates = []) {
    return Boolean(
      (Array.isArray(hydrationCandidates) && hydrationCandidates.length > 0) ||
        isLiveDetailHydrationActive(state) ||
        isCacheIndexingActive(state)
    );
  }

  function refreshResultStatusWorking(state) {
    setResultStatusWorking(state, isResultStatusWorking(state));
  }

  function needsLiveDetailHydration(item) {
    return Boolean(item && (!item.image || !item.priceText || !item.platformText));
  }

  function clearRenderedResults(state) {
    if (!state || !state.ui) return;
    clearTimeout(state.renderedResultRemovalTimer);
    state.renderedResultRemovalTimer = 0;
    state.ui.resultGrid.replaceChildren();
    state.renderedResultNodes.clear();
    state.renderedResultVersions.clear();
    state.renderedResultStaleUntil.clear();
  }

  function reconcileRenderedResults(state, visibleResults, options = {}) {
    const visibleKeys = new Set();
    const fragment = document.createDocumentFragment();
    const now = Date.now();
    const preserveStaleResults = options.preserveStaleResults !== false;

    for (const item of visibleResults) {
      const key = itemKey(item);
      if (!key || visibleKeys.has(key)) continue;
      visibleKeys.add(key);
      state.renderedResultStaleUntil.delete(key);

      const version = renderedItemVersion(item);
      let node = state.renderedResultNodes.get(key);
      if (!node || state.renderedResultVersions.get(key) !== version) {
        const nextNode = renderItem(item, item.collection || state.route.collection);
        if (node && node.parentElement === state.ui.resultGrid) {
          state.ui.resultGrid.replaceChild(nextNode, node);
        }
        node = nextNode;
        state.renderedResultNodes.set(key, node);
        state.renderedResultVersions.set(key, version);
      }

      fragment.appendChild(node);
    }

    for (const [key, node] of Array.from(state.renderedResultNodes)) {
      if (visibleKeys.has(key)) continue;
      if (!preserveStaleResults) {
        if (node && node.parentElement === state.ui.resultGrid) {
          node.remove();
        }
        state.renderedResultNodes.delete(key);
        state.renderedResultVersions.delete(key);
        state.renderedResultStaleUntil.delete(key);
        continue;
      }
      if (!state.renderedResultStaleUntil.has(key)) {
        state.renderedResultStaleUntil.set(key, now + RENDER_STALE_RESULT_GRACE_MS);
      }
      fragment.appendChild(node);
    }

    state.ui.resultGrid.appendChild(fragment);
    scheduleStaleResultCleanup(state);
  }

  function scheduleStaleResultCleanup(state) {
    if (!state || !state.ui) return;
    clearTimeout(state.renderedResultRemovalTimer);

    let nextDeadline = 0;
    const now = Date.now();
    for (const deadline of state.renderedResultStaleUntil.values()) {
      if (!nextDeadline || deadline < nextDeadline) {
        nextDeadline = deadline;
      }
    }

    if (!nextDeadline) {
      state.renderedResultRemovalTimer = 0;
      return;
    }

    state.renderedResultRemovalTimer = setTimeout(() => {
      removeExpiredStaleResults(state);
    }, Math.max(0, nextDeadline - now));
  }

  function removeExpiredStaleResults(state) {
    if (!state || !state.ui) return;

    const now = Date.now();
    for (const [key, deadline] of Array.from(state.renderedResultStaleUntil)) {
      if (deadline > now) continue;

      const node = state.renderedResultNodes.get(key);
      if (node && node.parentElement === state.ui.resultGrid) {
        node.remove();
      }
      state.renderedResultNodes.delete(key);
      state.renderedResultVersions.delete(key);
      state.renderedResultStaleUntil.delete(key);
    }

    scheduleStaleResultCleanup(state);
  }

  function renderedItemVersion(item) {
    return [
      item && item.collection,
      item && item.title,
      item && item.url,
      item && item.image,
      item && item.priceText,
      item && item.platformText,
      item && item.liveDetailVersion || 0,
    ].join('\u001f');
  }

  function liveDetailContextSignature(state) {
    return [
      state && state.route && state.route.collection,
      normalizeQuery(state && state.query),
      state && state.platformFilter || '',
      state && state.freeOnly ? 'free' : 'all',
      state && state.resultLimit,
    ].join('\u001f');
  }

  async function hydrateLiveDetailQueue(state) {
    if (!state || state.background || state.liveDetailFetching || !isStateActive(state)) return;
    state.liveDetailFetching = true;

    let changed = false;
    const runId = state.liveDetailRunId;
    const route = state.cacheRoute || state.route;
    const workerCount = Math.min(LIVE_DETAIL_FETCH_CONCURRENCY, state.liveDetailItemQueue.length);
    const workers = Array.from({ length: workerCount }, async () => {
      while (isLiveDetailRunActive(state, runId) && state.liveDetailItemQueue.length > 0) {
        const item = state.liveDetailItemQueue.shift();
        if (!item) break;
        const key = itemKey(item);

        state.liveDetailQueuedItems.delete(key);
        state.liveDetailInFlightItems.add(key);

        const delayMs = LIVE_DETAIL_FETCH_DELAY_MS + Math.floor(Math.random() * LIVE_DETAIL_FETCH_JITTER_MS);
        if (delayMs > 0) {
          await sleep(delayMs);
        }
        if (!isLiveDetailRunActive(state, runId)) break;

        try {
          const itemUrl = absoluteUrl(item.url, window.location.href);
          const html = await fetchPageHtml(state, itemUrl, state.liveDetailAbortControllers, key);
          if (!isLiveDetailRunActive(state, runId)) break;
          if (!state.liveDetailTargetItems.has(key)) {
            logger.verbose('Live detail result ignored after retarget.', 'item', item.title || item.url);
            continue;
          }

          const doc = new DOMParser().parseFromString(html, 'text/html');
          const detail = parseProductDetailItem(doc, item, route, itemUrl);
          if (
            isLiveDetailRunActive(state, runId) &&
            state.liveDetailTargetItems.has(key) &&
            applyLiveDetailToItem(state, item, detail)
          ) {
            changed = true;
            scheduleLiveDetailRender(state);
          }
          if (needsLiveDetailHydration(item)) {
            state.liveDetailFetchedItems.delete(key);
            logger.verbose('Live result detail response incomplete.', 'item', item.title || item.url);
          } else {
            state.liveDetailFetchedItems.add(key);
            logger.verbose('Hydrated live result details.', 'item', item.title || item.url);
          }
        } catch (error) {
          if (error && error.name === 'AbortError') {
            logger.verbose('Live detail fetch aborted.', 'item', item.title || item.url);
          } else {
            state.liveDetailFailedItems.add(key);
            logger.warn('Failed to hydrate live result details.', 'item', item.title || item.url, error);
          }
        } finally {
          state.liveDetailInFlightItems.delete(key);
        }
      }
    });

    await Promise.all(workers);
    if (!isLiveDetailRunActive(state, runId)) return;

    state.liveDetailFetching = false;
    if (changed && isStateActive(state) && !state.liveDetailRenderTimer) {
      runSearch(state, { skipLiveDetailHydration: !filteredResultsNeedConfirmedDetails(state) });
    }

    if (isStateActive(state) && state.liveDetailItemQueue.length > 0) {
      clearTimeout(state.liveDetailHydrationTimer);
      state.liveDetailHydrationTimer = setTimeout(() => {
        hydrateLiveDetailQueue(state).catch((error) => {
          logger.warn('Live detail hydration failed.', error);
        });
      }, LIVE_DETAIL_HYDRATION_DELAY_MS);
    } else if (isStateActive(state) && !isLiveDetailHydrationActive(state)) {
      refreshResultStatusWorking(state);
    }
  }

  function applyLiveDetailToItem(state, item, detail) {
    if (!item || !detail) return false;

    let changed = false;
    if (detail.image && item.image !== detail.image) {
      item.image = detail.image;
      changed = true;
    }
    if (detail.priceText && item.priceText !== detail.priceText) {
      item.priceText = detail.priceText;
      changed = true;
    }
    if (detail.platformText && item.platformText !== detail.platformText) {
      item.platformText = detail.platformText;
      changed = true;
    }
    if (changed) {
      item.filterFlags = itemFilterFlags(item).join(',');
      item.liveDetailVersion = (Number(item.liveDetailVersion) || 0) + 1;
      item.searchText = buildSearchText(item);
      state.itemsByKey.set(itemKey(item), item);
    }
    return changed;
  }

  function isLiveDetailRunActive(state, runId) {
    return Boolean(state && isStateActive(state) && state.liveDetailRunId === runId);
  }

  function retargetLiveDetailHydration(state, targetItems, signature, contextSignature = liveDetailContextSignature(state)) {
    if (!state) return;

    const targetKeys = new Set(targetItems.map(itemKey));
    clearTimeout(state.liveDetailHydrationTimer);
    state.liveDetailHydrationTimer = 0;
    state.liveDetailSignature = signature;
    state.liveDetailContextSignature = contextSignature;
    state.liveDetailTargetItems = targetKeys;
    state.liveDetailItemQueue = [];
    state.liveDetailQueuedItems.clear();

    for (const key of Array.from(state.liveDetailInFlightItems)) {
      if (!targetKeys.has(key)) {
        state.liveDetailInFlightItems.delete(key);
      }
    }
    abortLiveDetailFetches(state, targetKeys);

    for (const item of targetItems) {
      const key = itemKey(item);
      if (state.liveDetailInFlightItems.has(key)) continue;
      state.liveDetailItemQueue.push(item);
      state.liveDetailQueuedItems.add(key);
    }
  }

  function cancelLiveDetailHydration(state) {
    if (!state) return;

    state.liveDetailRunId += 1;
    clearTimeout(state.liveDetailHydrationTimer);
    clearTimeout(state.liveDetailRenderTimer);
    state.liveDetailHydrationTimer = 0;
    state.liveDetailRenderTimer = 0;
    state.liveDetailItemQueue = [];
    state.liveDetailQueuedItems.clear();
    state.liveDetailInFlightItems.clear();
    state.liveDetailFetching = false;
    state.liveDetailTargetItems.clear();
    state.liveDetailSignature = '';
    state.liveDetailContextSignature = '';
    abortLiveDetailFetches(state);
    refreshResultStatusWorking(state);
  }

  function abortLiveDetailFetches(state, keepKeys = new Set()) {
    if (!state) return;
    for (const [key, controller] of state.liveDetailAbortControllers) {
      if (keepKeys.has(key)) continue;
      try {
        controller.abort();
      } catch (_) {
        // Ignore abort cleanup errors.
      }
      state.liveDetailAbortControllers.delete(key);
    }
  }

  function scheduleLiveDetailRender(state) {
    if (!state || !state.ui || !isStateActive(state)) return;
    if (state.liveDetailRenderTimer) return;

    state.liveDetailRenderTimer = setTimeout(() => {
      state.liveDetailRenderTimer = 0;
      if (isStateActive(state)) {
        runSearch(state, { skipLiveDetailHydration: !filteredResultsNeedConfirmedDetails(state) });
      }
    }, LIVE_DETAIL_RENDER_DEBOUNCE_MS);
  }

  function renderItem(item, collection) {
    return isThemeCollection(collection) ? renderThemeItem(item) : renderAvatarItem(item);
  }

  function renderAvatarItem(item) {
    const outer = document.createElement('div');
    outer.className = 'col-span-1';

    const card = document.createElement('div');
    card.className = 'avatar-card group flex flex-col text-xs mb-1';

    const link = document.createElement('a');
    link.href = item.url;
    link.className = 'flex flex-col gap-1 relative z-10 rounded text-text';

    const imageWrap = document.createElement('span');
    imageWrap.className = 'card-wrapper relative';

    const imageShell = document.createElement('div');
    imageShell.className = 'relative overflow-hidden aspect-square rounded-cover-lg border border-slate-200 dark:border-slate-700 bg-gray-50 dark:bg-gray-800';

    if (item.image) {
      const blurImage = document.createElement('img');
      blurImage.alt = '';
      blurImage.setAttribute('aria-hidden', 'true');
      blurImage.src = item.image;
      blurImage.className = 'absolute inset-0 h-full w-full object-cover blur-xl scale-125 opacity-55 saturate-150 brightness-110';
      imageShell.appendChild(blurImage);
    }

    const gradient = document.createElement('div');
    gradient.className = 'absolute inset-0 bg-gradient-to-b from-black/20 via-black/0 to-black/25';

    const image = document.createElement('img');
    image.loading = 'lazy';
    image.alt = item.title;
    image.src = item.image || '/staticfiles/i/svg/placeholder__cover.1153ef2292d9.svg';
    image.className = 'relative z-10 w-full h-full object-contain';

    imageShell.append(gradient, image);
    imageWrap.appendChild(imageShell);

    const titleWrap = document.createElement('div');
    titleWrap.className = 'flex items-center gap-1 h-4 opacity-30 group-hover:opacity-100 transition-opacity duration-200';

    const title = document.createElement('span');
    title.className = 'line-clamp-1 flex-1 text-[11px] leading-tight';
    title.textContent = item.title;

    titleWrap.appendChild(title);

    for (const platform of String(item.platformText || '').split(/\s+/).filter(Boolean)) {
      const platformBadge = document.createElement('span');
      platformBadge.className = 'inline-flex items-center px-1 py-0.5 rounded text-[8px] font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 flex-shrink-0';
      platformBadge.textContent = platform;
      titleWrap.appendChild(platformBadge);
    }

    link.append(imageWrap, titleWrap);

    if (item.priceText) {
      const priceWrap = document.createElement('span');
      priceWrap.className = 'flex flex-col gap-0.5 opacity-30 group-hover:opacity-100 transition-opacity duration-200';

      const priceLine = document.createElement('span');
      priceLine.className = 'flex gap-x-0.5 items-baseline flex-wrap';

      const price = document.createElement('span');
      price.className = 'text-sm font-medium tabular-nums';
      price.textContent = item.priceText;

      priceLine.appendChild(price);
      priceWrap.appendChild(priceLine);
      link.appendChild(priceWrap);
    }

    card.appendChild(link);
    outer.appendChild(card);
    return outer;
  }

  function renderThemeItem(item) {
    const fragment = document.createElement('div');
    fragment.className = 'game-fragment group flex flex-col text-sm';

    const link = document.createElement('a');
    link.href = item.url;
    link.className = 'flex flex-col gap-[5px] relative rounded-cover-md text-text active:scale-[0.99] transition-[transform,box-shadow] duration-200 focus:outline-2 focus:outline-primary focus:outline-offset-2 focus:z-10';

    const cardWrap = document.createElement('div');
    cardWrap.className = 'card-wrapper relative shadow-sm hover:shadow-md rounded-cover-md overflow-clip';

    const platformStrip = document.createElement('span');
    platformStrip.className = 'deal-strip bg-brand-playstation gap-3 justify-center';
    platformStrip.textContent = item.platformText || 'PlayStation';

    const imageFrame = document.createElement('div');
    imageFrame.className = 'relative overflow-hidden aspect-square bg-elevation2';

    const image = document.createElement('img');
    image.loading = 'lazy';
    image.alt = item.title;
    image.src = item.image || '/staticfiles/i/svg/placeholder__cover.1153ef2292d9.svg';
    image.className = 'relative z-10 w-full h-full object-contain';

    imageFrame.appendChild(image);
    cardWrap.append(platformStrip, imageFrame);

    const textWrap = document.createElement('div');
    textWrap.className = 'flex flex-col gap-1.5';

    const title = document.createElement('h3');
    title.className = 'line-clamp-2 min-h-[2.5rem] text-base font-medium text-text text-pretty underline-offset-2 group-hover:underline group-hover:text-primary dark:group-hover:text-white leading-tight mt-1';
    title.textContent = item.title;

    textWrap.appendChild(title);

    if (item.priceText) {
      const price = document.createElement('div');
      price.className = 'text-xl font-bold text-text tabular-nums';
      price.textContent = item.priceText;
      textWrap.appendChild(price);
    }

    link.append(cardWrap, textWrap);
    fragment.appendChild(link);
    return fragment;
  }

  function absorbIndexedPage(state, page, items, source, options = {}) {
    removeIndexedPage(state, page);
    state.loadedPages.add(page);
    return addItemsToIndex(state, items, source, options);
  }

  function syncAppWithBackgroundState(backgroundState = prewarmState) {
    if (!backgroundState || !backgroundState.background || !appState || !appState.ui) return;
    if (
      appState.route.host !== backgroundState.route.host ||
      appState.route.region !== backgroundState.route.region
    ) {
      return;
    }

    const sameSearchScope = appState.cacheScope === backgroundState.cacheScope;
    const backgroundIsActive = Boolean(backgroundState.fetchingStarted && !backgroundState.indexingDone && !backgroundState.indexingPaused);

    if (sameSearchScope || backgroundIsActive) {
      appState.trackedRoute = backgroundState.route;
      appState.statusFailedPages = new Set(backgroundState.failedPages);
      appState.progressLoadedPages = backgroundState.progressLoadedPages;
      appState.progressItemCount = backgroundState.progressItemCount;
      appState.progressTotalPages = backgroundState.progressTotalPages;
      appState.progressTotalApproximate = backgroundState.progressTotalApproximate;
      appState.waitingForLease = false;
      appState.waitingOwnerRegion = '';
      appState.waitingOwnerCollection = '';
      appState.waitingReason = '';
      appState.totalPagesQueued = backgroundState.totalPagesQueued;
      appState.fetchingStarted = backgroundState.fetchingStarted;
      appState.indexingDone = backgroundState.indexingDone;
      appState.indexingPaused = backgroundState.indexingPaused;
      appState.pauseReason = backgroundState.pauseReason;
      appState.networkItemCount = backgroundState.networkItemCount;
    } else {
      useLocalStatusProgress(appState);
    }

    if (sameSearchScope) {
      appState.lastPage = Math.max(appState.lastPage, backgroundState.lastPage || 1);
      appState.loadedPages = new Set(backgroundState.loadedPages);
      appState.failedPages = new Set(backgroundState.failedPages);
      appState.queuedPages = new Set(backgroundState.queuedPages);
      appState.pendingPages = backgroundState.pendingPages.slice();
      appState.ui.resultGrid.className = resultGridClass(appState.route.collection);

      const canonicalAvatarMap = readCanonicalAvatarItemMap(appState.route);
      const appItems = enrichCachedItemsForRoute(appState.route, backgroundState.items, canonicalAvatarMap);
      appState.items = [];
      appState.itemsByKey.clear();
      appState.sequence = 0;
      addItemsToIndex(appState, appItems, 'cache');
    }

    logger.verbose(
      'Synced visible collection UI with background worker.',
      backgroundState.route.collection,
      'sameSearchScope',
      sameSearchScope,
      'loadedPages',
      backgroundState.loadedPages.size,
      'lastPage',
      backgroundState.lastPage
    );
    updateStatus(appState);
    if (sameSearchScope) {
      runSearch(appState);
    }
  }

  function markAppWaitingForLease(context, ownerRegion, reason, ownerCollection = '') {
    if (!appState || !appState.ui) return;
    if (appState.route.host !== context.host || appState.route.region !== context.region) return;

    appState.waitingForLease = Boolean(ownerRegion || reason);
    appState.waitingOwnerRegion = ownerRegion || '';
    appState.waitingOwnerCollection = ownerCollection || '';
    appState.waitingReason = reason || '';
    updateStatus(appState);
  }

  async function startIndexing(state) {
    if (!state || state.indexStarted) return;
    state.indexStarted = true;

    const currentPageItems = parsePageItems(document, state.route, state.route.currentPage, window.location.href);
    const detectedLastPage = Math.max(1, detectLastPage(document, state.route));
    if (state.lastPage !== detectedLastPage) {
      logger.info('Collection page count detected from DOM.', 'from', state.lastPage, 'to', detectedLastPage);
    }
    state.lastPage = detectedLastPage;
    logger.info(
      'Route indexed from DOM.',
      state.route.region,
      state.route.collection,
      'page',
      state.route.currentPage,
      'items',
      currentPageItems.length,
      'lastPage',
      state.lastPage
    );
    absorbIndexedPage(state, state.route.currentPage, currentPageItems, 'dom');

    if (state.cacheEnabled && !state.forceRefresh) {
      const cached = readCache(state.cacheScope);
      if (cached) {
        state.cacheMeta = readJsonStorage(cacheMetaKey(state.cacheScope));
        applyCacheProgressToState(state, state.cacheMeta);
        state.lastPage = Math.max(state.lastPage, cached.lastPage || 1);
        const canonicalAvatarMap = readCanonicalAvatarItemMap(state.route);
        logger.info(
          'Loaded cached collection pages.',
          'pages',
          cached.pages.size,
          'items',
          cached.itemCount,
          'lastPage',
          cached.lastPage,
          'complete',
          cached.complete
        );
        if (cached.stalePages.length > 0) {
          logger.info('Queued stale cached pages for rebuild.', 'pages', cached.stalePages.length);
          logger.verbose('Stale cached page numbers.', cached.stalePages.join(','));
        }
        if (cached.inFlightPage) {
          logger.info('Resuming after incomplete cached page.', 'page', cached.inFlightPage);
        }
        if (cached.inFlightPages.length > 0) {
          logger.info('Resuming after incomplete cached pages.', 'pages', cached.inFlightPages.join(','));
        }
        let cachedAdded = 0;
        for (const [page, items] of cached.pages.entries()) {
          if (!isFilteredCollection(state.route.collection) && page === state.route.currentPage) continue;
          if (page > state.lastPage) continue;
          const pageItems = enrichCachedItemsForRoute(state.route, items, canonicalAvatarMap);
          logger.verbose('Loaded cached page.', 'page', page, 'items', pageItems.length);
          cachedAdded += absorbIndexedPage(state, page, pageItems, 'cache', { deferRender: true });
        }
        if (cachedAdded > 0) {
          finalizeIndexMutation(state);
        }
      }
    }

    state.pendingPages = [];
    state.totalPagesQueued = 0;
    state.indexingDone = true;
    logger.info(
      'Prepared collection from DOM and local cache.',
      'loadedPages',
      state.loadedPages.size,
      'lastPage',
      state.lastPage
    );
    syncAppWithBackgroundState();
    updateStatus(state);
    runSearch(state);
    ensureNetworkIndexing(state);
  }

  async function startBackgroundIndexing(state) {
    if (!state || state.indexStarted) return;
    state.indexStarted = true;

    let cached = null;
    let needsRevalidation = true;
    if (state.cacheEnabled && !state.forceRefresh) {
      cached = readCache(state.cacheScope);
      if (cached) {
        state.cacheMeta = readJsonStorage(cacheMetaKey(state.cacheScope));
        applyCacheProgressToState(state, state.cacheMeta);
        state.lastPage = Math.max(1, cached.lastPage || 1);
        needsRevalidation = shouldRevalidateCache(state.cacheMeta);
        const canonicalAvatarMap = readCanonicalAvatarItemMap(state.route);
        let cachedAdded = 0;
        for (const [page, items] of cached.pages.entries()) {
          state.loadedPages.add(page);
          cachedAdded += addItemsToIndex(state, enrichCachedItemsForRoute(state.route, items, canonicalAvatarMap), 'cache', { deferRender: true });
        }
        if (cachedAdded > 0) {
          finalizeIndexMutation(state);
        }
        logger.info(
          'Background cache loaded.',
          state.route.region,
          state.route.collection,
          'pages',
          cached.pages.size,
          'items',
          cached.itemCount,
          'lastPage',
          state.lastPage,
          'complete',
          cached.complete,
          'revalidate',
          needsRevalidation
        );
        if (cached.inFlightPage) {
          logger.info('Background resume after incomplete cached page.', state.route.collection, 'page', cached.inFlightPage);
        }
        if (cached.inFlightPages.length > 0) {
          logger.info('Background resume after incomplete cached pages.', state.route.collection, 'pages', cached.inFlightPages.join(','));
        }
      }
    }

    if (needsRevalidation) {
      await fetchAndIndexPage(state, 1);
    } else {
      logger.info('Background cache is fresh; skipped page-count revalidation.', state.route.region, state.route.collection);
    }

    if (!isStateActive(state) || state.indexingPaused) return;

    removeIndexedPagesAfter(state, state.lastPage);

    const pagesToFetch = [];
    for (let page = 1; page <= state.lastPage; page += 1) {
      if (state.loadedPages.has(page)) continue;
      pagesToFetch.push(page);
      state.queuedPages.add(page);
    }

    state.pendingPages = pagesToFetch;
    state.totalPagesQueued = pagesToFetch.length;
    state.indexingDone = pagesToFetch.length === 0;
    logger.info(
      'Background collection queue prepared.',
      state.route.region,
      state.route.collection,
      'pendingPages',
      pagesToFetch.length,
      'loadedPages',
      state.loadedPages.size
    );

    syncAppWithBackgroundState(state);
    ensureNetworkIndexing(state);
    if (state.fetchingPromise) {
      await state.fetchingPromise;
    }
  }

  function shouldFetchMissingPages(state) {
    return (
      state.forceRefresh ||
      state.autoIndexReady ||
      normalizeQuery(state.query).length >= FETCH_QUERY_MIN_LENGTH
    );
  }

  function ensureNetworkIndexing(state) {
    const canFetch = Boolean(state && state.background);
    if (!state || !canFetch || !isStateActive(state) || state.fetchingStarted || state.indexingDone || state.indexingPaused) {
      return;
    }

    if (state.pendingPages.length === 0) {
      state.indexingDone = true;
      state.progressTotalApproximate = false;
      syncAppWithBackgroundState(state);
      updateStatus(state);
      runSearch(state);
      return;
    }

    if (!shouldFetchMissingPages(state)) {
      logger.verbose('Network indexing deferred until auto-index, query threshold, or refresh.', 'pendingPages', state.pendingPages.length);
      updateStatus(state);
      return;
    }

    state.fetchingStarted = true;
    logger.info('Network indexing started.', 'pendingPages', state.pendingPages.length, 'concurrency', state.fetchConcurrency);
    syncAppWithBackgroundState(state);
    state.fetchingPromise = fetchPages(state).catch((error) => {
      if (!isStateActive(state)) return;
      pauseIndexing(state, `Unexpected indexing error: ${error.message || error}`);
    });
    updateStatus(state);
  }

  function scheduleAutoIndex(state) {
    if (!state.autoIndexEnabled || state.indexingDone || state.pendingPages.length === 0) {
      return;
    }

    clearTimeout(state.autoIndexTimer);
    state.autoIndexTimer = setTimeout(() => {
      if (!isStateActive(state) || state.indexingPaused || state.indexingDone) {
        return;
      }
      state.autoIndexReady = true;
      logger.info('Auto-index started for active route.', 'pendingPages', state.pendingPages.length);
      ensureNetworkIndexing(state);
    }, AUTO_INDEX_DELAY_MS);
    logger.info('Auto-index scheduled.', 'delayMs', AUTO_INDEX_DELAY_MS, 'pendingPages', state.pendingPages.length);
  }

  async function fetchPages(state) {
    const shouldStopForPrewarm = () => state.background && handlePrewarmStopSignal();
    const workerCount = Math.min(state.fetchConcurrency, state.pendingPages.length);
    const workers = Array.from({ length: workerCount }, async () => {
      while (
        isStateActive(state) &&
        !shouldStopForPrewarm() &&
        !state.indexingPaused &&
        shouldFetchMissingPages(state) &&
        state.pendingPages.length > 0
      ) {
        const page = state.pendingPages.shift();
        if (!page) break;
        await waitBeforeFetch(state);
        if (!isStateActive(state) || shouldStopForPrewarm() || state.indexingPaused || !shouldFetchMissingPages(state)) {
          state.pendingPages.unshift(page);
          break;
        }
        await fetchAndIndexPage(state, page);
        await yieldToBrowser();
      }
    });

    await Promise.all(workers);

    if (isStateActive(state)) {
      state.fetchingStarted = false;
      state.indexingDone = !state.indexingPaused && state.pendingPages.length === 0;
      if (state.indexingDone) {
        state.progressTotalApproximate = false;
      }
      syncAppWithBackgroundState(state);
      updateStatus(state);
      runSearch(state);
      if (state.indexingDone) {
        logger.info('Network indexing completed.', 'items', state.items.length, 'failedPages', state.failedPages.size);
      } else if (!state.indexingPaused) {
        logger.info('Network indexing deferred.', 'pendingPages', state.pendingPages.length);
      }
    }
  }

  async function fetchAndIndexPage(state, page) {
    if (!state) return;

    for (let attempt = 0; attempt <= FETCH_RETRY_COUNT; attempt += 1) {
      try {
        logger.verbose('Fetching collection page.', 'page', page, 'attempt', attempt + 1);
        markCachePageInFlight(state, page);
        const html = await fetchPageHtml(state, makePageUrl(state.route, page));
        if (!isStateActive(state)) return;

        const doc = new DOMParser().parseFromString(html, 'text/html');
        const items = parsePageItems(doc, state.route, page, makePageUrl(state.route, page));
        removeIndexedPage(state, page);
        state.loadedPages.add(page);
        state.queuedPages.delete(page);
        saveCachePage(state, page, items);
        addItemsToIndex(state, items, 'network');

        const detectedLastPage = detectLastPage(doc, state.route);
        const previousLastPage = state.lastPage;
        if (detectedLastPage > previousLastPage) {
          reconcileLastPage(state, detectedLastPage);
          queueMissingPages(state, previousLastPage + 1, state.lastPage);
        } else if (detectedLastPage < state.lastPage) {
          logger.info(
            'Ignored lower background page count.',
            'detected',
            detectedLastPage,
            'current',
            state.lastPage,
            'page',
            page
          );
        } else if (page >= state.lastPage) {
          state.progressTotalApproximate = false;
        }
        syncAppWithBackgroundState(state);

        updateStatus(state);
        logger.verbose('Indexed fetched page.', 'page', page, 'items', items.length);
        return;
      } catch (error) {
        if (!isStateActive(state) || state.indexingPaused || error.name === 'AbortError') {
          logger.verbose('Fetch ignored after state change or abort.', 'page', page);
          return;
        }

        if (isHardFetchError(error)) {
          pauseIndexing(state, error.message || 'PSPrices blocked collection fetching.');
          return;
        }

        if (attempt < FETCH_RETRY_COUNT) {
          await sleep(FETCH_DELAY_MS + FETCH_JITTER_MS);
          continue;
        }

        state.hardFailureCount += 1;
        state.failedPages.add(page);
        state.queuedPages.delete(page);
        logger.warn(`Failed to index page ${page}.`, error);
        if (state.hardFailureCount >= MAX_HARD_FAILURES) {
          pauseIndexing(state, 'Too many page fetch failures; refresh later to retry.');
          return;
        }
        updateStatus(state);
      }
    }
  }

  async function fetchPageHtml(state, url, controllerSet = state.abortControllers, controllerKey = null) {
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const key = controllerKey || controller;
    const timer = controller
      ? setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
      : null;

    if (controller) {
      addFetchController(controllerSet, key, controller);
    }

    try {
      const response = await fetch(url, {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
        signal: controller ? controller.signal : undefined,
      });

      if (!response.ok) {
        throw makeFetchError(`HTTP ${response.status}`, response.status === 403 || response.status === 429);
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType && !contentType.toLowerCase().includes('text/html')) {
        throw new Error(`Unexpected content type: ${contentType}`);
      }

      const html = await response.text();
      if (looksLikeChallengePage(html)) {
        throw makeFetchError('PSPrices returned a bot-protection or rate-limit page.', true);
      }

      return html;
    } finally {
      if (timer) clearTimeout(timer);
      if (controller) {
        deleteFetchController(controllerSet, key, controller);
      }
    }
  }

  function addFetchController(controllerSet, key, controller) {
    if (controllerSet && typeof controllerSet.set === 'function') {
      controllerSet.set(key, controller);
      return;
    }
    if (controllerSet && typeof controllerSet.add === 'function') {
      controllerSet.add(controller);
    }
  }

  function deleteFetchController(controllerSet, key, controller) {
    if (controllerSet && typeof controllerSet.delete === 'function') {
      controllerSet.delete(controllerSet && typeof controllerSet.get === 'function' ? key : controller);
    }
  }

  function makeFetchError(message, hard) {
    const error = new Error(message);
    error.pspricesHardFetchError = Boolean(hard);
    return error;
  }

  function isHardFetchError(error) {
    return Boolean(error && error.pspricesHardFetchError);
  }

  function looksLikeChallengePage(html) {
    const sample = String(html || '').slice(0, 120000).toLowerCase();
    return (
      sample.includes('cf-browser-verification') ||
      sample.includes('cf-challenge') ||
      sample.includes('challenge-platform') ||
      sample.includes('just a moment') ||
      sample.includes('checking your browser') ||
      sample.includes('rate limit')
    );
  }

  async function waitBeforeFetch(state) {
    const delay = FETCH_DELAY_MS + Math.floor(Math.random() * FETCH_JITTER_MS);
    await sleep(delay);
    if (document.hidden && !state.forceRefresh) {
      await sleep(delay);
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function yieldToBrowser() {
    return new Promise((resolve) => {
      if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(() => resolve(), { timeout: 250 });
        return;
      }
      setTimeout(resolve, 0);
    });
  }

  function pauseIndexing(state, reason) {
    if (!state || !isStateActive(state)) return;
    state.indexingPaused = true;
    state.pauseReason = reason;
    state.pausedAt = Date.now();
    state.fetchingStarted = false;
    abortStateFetches(state);
    logger.warn(reason);
    syncAppWithBackgroundState(state);
    updateStatus(state);
    runSearch(state);
  }

  function abortStateFetches(state) {
    abortLiveDetailFetches(state);
    for (const controller of state.abortControllers) {
      try {
        controller.abort();
      } catch (_) {
        // Ignore abort cleanup errors.
      }
    }
    state.abortControllers.clear();
  }

  function teardownRegionPrewarm() {
    prewarmRunId += 1;
    clearRegionPrewarmGraceTimer();
    releasePrewarmLease();
    if (!prewarmState) return;

    clearTimeout(prewarmState.autoIndexTimer);
    abortStateFetches(prewarmState);
    prewarmState = null;
  }

  function clearRegionPrewarmGraceTimer() {
    if (!prewarmContextTimer) return;
    clearTimeout(prewarmContextTimer);
    prewarmContextTimer = 0;
  }

  function scheduleRegionPrewarmGraceTeardown() {
    if (!prewarmState || prewarmContextTimer) return;

    logger.info('Region prewarm waiting for region route to return.', 'graceMs', PREWARM_CONTEXT_GRACE_MS);
    prewarmContextTimer = setTimeout(() => {
      prewarmContextTimer = 0;
      if (parseRegionContext()) return;

      logger.warn('Region prewarm paused after region route was unavailable.', 'graceMs', PREWARM_CONTEXT_GRACE_MS);
      teardownRegionPrewarm();
    }, PREWARM_CONTEXT_GRACE_MS);
  }

  function readLeaseKey(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function readPrewarmLease(signature) {
    return readLeaseKey(prewarmLeaseKey(signature));
  }

  function readGlobalPrewarmLease() {
    return readLeaseKey(PREWARM_GLOBAL_LEASE_KEY);
  }

  function isFreshForeignPrewarmLease(lease) {
    return Boolean(
      lease &&
      lease.owner &&
      lease.owner !== TAB_ID &&
      Date.now() - Number(lease.updatedAt || 0) < PREWARM_LEASE_STALE_MS
    );
  }

  function writeLeaseKey(key, context, signature) {
    try {
      localStorage.setItem(key, JSON.stringify({
        owner: TAB_ID,
        host: context.host,
        region: context.region,
        collection: context.collection || '',
        signature,
        updatedAt: Date.now(),
      }));
      return true;
    } catch (error) {
      logger.warn('Unable to write prewarm lease; continuing without cross-tab lock.', error);
      return false;
    }
  }

  function writePrewarmLease(context, signature) {
    const wroteGlobal = writeLeaseKey(PREWARM_GLOBAL_LEASE_KEY, context, signature);
    const wroteRegion = writeLeaseKey(prewarmLeaseKey(signature), context, signature);
    if (wroteGlobal && wroteRegion) {
      prewarmLeaseSignature = signature;
      return true;
    }

    const globalLease = readGlobalPrewarmLease();
    const regionLease = readPrewarmLease(signature);
    if (globalLease && globalLease.owner === TAB_ID) {
      removeStorageKey(PREWARM_GLOBAL_LEASE_KEY);
    }
    if (regionLease && regionLease.owner === TAB_ID) {
      removeStorageKey(prewarmLeaseKey(signature));
    }
    return false;
  }

  function refreshPrewarmLease(context, signature) {
    if (!prewarmLeaseSignature || prewarmLeaseSignature !== signature) return;
    writePrewarmLease({
      ...context,
      collection: prewarmState && prewarmState.route ? prewarmState.route.collection : context.collection,
    }, signature);
  }

  function clearPrewarmLeaseTimer() {
    if (!prewarmLeaseTimer) return;
    clearInterval(prewarmLeaseTimer);
    prewarmLeaseTimer = 0;
  }

  function clearPrewarmLeaseRetryTimer() {
    if (!prewarmLeaseRetryTimer) return;
    clearTimeout(prewarmLeaseRetryTimer);
    prewarmLeaseRetryTimer = 0;
  }

  function schedulePrewarmLeaseRetry() {
    if (prewarmLeaseRetryTimer || prewarmState) return;

    prewarmLeaseRetryTimer = setTimeout(() => {
      prewarmLeaseRetryTimer = 0;
      startRegionPrewarm(false);
    }, PREWARM_LEASE_HEARTBEAT_MS);
  }

  function releasePrewarmLease() {
    clearPrewarmLeaseTimer();
    if (!prewarmLeaseSignature) return;

    const signature = prewarmLeaseSignature;
    prewarmLeaseSignature = '';
    const lease = readPrewarmLease(signature);
    const globalLease = readGlobalPrewarmLease();

    if (lease && lease.owner === TAB_ID) {
      removeStorageKey(prewarmLeaseKey(signature));
    }
    if (globalLease && globalLease.owner === TAB_ID) {
      removeStorageKey(PREWARM_GLOBAL_LEASE_KEY);
    }
  }

  function readPrewarmStopSignal() {
    try {
      const raw = localStorage.getItem(PREWARM_STOP_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function clearStalePrewarmStopSignal() {
    const signal = readPrewarmStopSignal();
    if (!signal || Date.now() - Number(signal.updatedAt || 0) <= PREWARM_STOP_GRACE_MS) return;
    removeStorageKey(PREWARM_STOP_KEY);
  }

  function broadcastPrewarmStop(reason) {
    try {
      localStorage.setItem(PREWARM_STOP_KEY, JSON.stringify({
        owner: TAB_ID,
        reason,
        updatedAt: Date.now(),
      }));
    } catch (_) {
      // Best-effort cross-tab stop only.
    }
  }

  function shouldHonorPrewarmStopSignal(signal) {
    if (!(
      signal &&
      signal.owner &&
      signal.owner !== TAB_ID &&
      Date.now() - Number(signal.updatedAt || 0) <= PREWARM_STOP_GRACE_MS
    )) {
      return false;
    }

    if (signal.reason === 'page-unload') {
      const context = parseRegionContext();
      const signature = context ? regionSignature(context) : '';
      const globalLease = readGlobalPrewarmLease();
      const regionLease = signature ? readPrewarmLease(signature) : null;
      if (!isFreshForeignPrewarmLease(globalLease) && !isFreshForeignPrewarmLease(regionLease)) {
        removeStorageKey(PREWARM_STOP_KEY);
        return false;
      }
    }

    return true;
  }

  function handlePrewarmStopSignal(signal = readPrewarmStopSignal()) {
    if (!shouldHonorPrewarmStopSignal(signal)) return false;

    logger.warn('Received shared prewarm stop signal; pausing local worker.', signal.reason || 'unknown');
    teardownRegionPrewarm();
    schedulePrewarmLeaseRetry();
    return true;
  }

  function acquirePrewarmLease(context, signature) {
    if (!canUseLocalStorage()) return true;
    clearPrewarmLeaseRetryTimer();

    const globalLease = readGlobalPrewarmLease();
    if (isFreshForeignPrewarmLease(globalLease)) {
      logger.info(
        'Site prewarm owned by another tab; this region will wait.',
        context.region,
        'ownerRegion',
        globalLease.region || 'unknown'
      );
      markAppWaitingForLease(context, globalLease.region || '', 'site', globalLease.collection || '');
      schedulePrewarmLeaseRetry();
      return false;
    }

    const existingLease = readPrewarmLease(signature);
    if (isFreshForeignPrewarmLease(existingLease)) {
      logger.info('Region prewarm owned by another tab; this tab will not start a duplicate worker.', context.region);
      markAppWaitingForLease(context, existingLease.region || context.region, 'region', existingLease.collection || '');
      schedulePrewarmLeaseRetry();
      return false;
    }

    if (!writePrewarmLease(context, signature)) return true;
    markAppWaitingForLease(context, '', '');

    clearPrewarmLeaseTimer();
    prewarmLeaseTimer = setInterval(() => {
      const globalLease = readGlobalPrewarmLease();
      if (isFreshForeignPrewarmLease(globalLease)) {
        logger.warn('Site prewarm lease moved to another tab; pausing this worker.', context.region);
        teardownRegionPrewarm();
        return;
      }

      const lease = readPrewarmLease(signature);
      if (isFreshForeignPrewarmLease(lease)) {
        logger.warn('Region prewarm lease moved to another tab; pausing this worker.', context.region);
        teardownRegionPrewarm();
        return;
      }
      refreshPrewarmLease(context, signature);
    }, PREWARM_LEASE_HEARTBEAT_MS);

    return true;
  }

  function handlePrewarmLeaseStorage(event) {
    if (appState && appState.ui && isRegionCacheProgressKey(appState, event.key)) {
      updateStatus(appState);
    }

    if (event.key === PREWARM_STOP_KEY) {
      handlePrewarmStopSignal(readPrewarmStopSignal());
      return;
    }

    if (event.key === PREWARM_GLOBAL_LEASE_KEY && !prewarmState) {
      const context = parseRegionContext();
      if (context && !isFreshForeignPrewarmLease(readGlobalPrewarmLease())) {
        setTimeout(() => startRegionPrewarm(false), 250);
      }
      return;
    }

    if (!prewarmState || !prewarmLeaseSignature) return;
    if (event.key !== prewarmLeaseKey(prewarmLeaseSignature) && event.key !== PREWARM_GLOBAL_LEASE_KEY) return;

    const lease = event.key === PREWARM_GLOBAL_LEASE_KEY
      ? readGlobalPrewarmLease()
      : readPrewarmLease(prewarmLeaseSignature);
    if (!isFreshForeignPrewarmLease(lease)) return;

    logger.warn('Prewarm lease taken by another tab; pausing this worker.', prewarmState.route.region);
    teardownRegionPrewarm();
  }

  function handlePageUnload() {
    if (pageIsUnloading) return;
    pageIsUnloading = true;
    if (prewarmState || prewarmLeaseSignature) {
      broadcastPrewarmStop('page-unload');
    }
    teardownRegionPrewarm();
  }

  async function startRegionPrewarm(forceRefresh = false) {
    if (!AUTO_INDEX_ON_SITE_VISIT) return;
    clearStalePrewarmStopSignal();
    if (handlePrewarmStopSignal()) return;

    const context = parseRegionContext();
    if (!context) {
      scheduleRegionPrewarmGraceTeardown();
      return;
    }
    clearRegionPrewarmGraceTimer();

    const signature = regionSignature(context);
    if (prewarmCompletedSignature === signature && !forceRefresh && arePrewarmCachesFresh(context)) {
      return;
    }

    if (prewarmState && prewarmState.signature === signature && !forceRefresh) {
      return;
    }

    if (forceRefresh || (prewarmState && prewarmState.signature !== signature)) {
      prewarmCompletedSignature = '';
    }

    teardownRegionPrewarm();
    if (!acquirePrewarmLease(context, signature)) {
      return;
    }

    const runId = prewarmRunId;
    logger.info('Region prewarm started.', context.region, forceRefresh ? 'refresh' : 'normal');

    for (const collection of PREWARM_COLLECTIONS) {
      if (runId !== prewarmRunId) return;

      const route = makeCollectionRoute(context, collection);
      const state = createState(route, forceRefresh, {
        background: true,
        fetchConcurrency: PREWARM_FETCH_CONCURRENCY,
      });
      state.signature = signature;
      state.autoIndexReady = true;
      prewarmState = state;
      refreshPrewarmLease({ ...context, collection }, signature);

      logger.info('Region prewarm collection started.', context.region, collection);
      try {
        await startBackgroundIndexing(state);
      } catch (error) {
        if (prewarmState === state) {
          pauseIndexing(state, `Background indexing error: ${error.message || error}`);
        }
      }

      if (prewarmState !== state || state.indexingPaused) {
        return;
      }

      logger.info(
        'Region prewarm collection finished.',
        context.region,
        collection,
        'items',
        state.items.length,
        'failedPages',
        state.failedPages.size
      );
      const nextCollection = PREWARM_COLLECTIONS[PREWARM_COLLECTIONS.indexOf(collection) + 1];
      if (nextCollection) {
        refreshPrewarmLease({ ...context, collection: nextCollection }, signature);
        logger.info('Region prewarm holding site lease for next collection.', context.region, nextCollection);
      }
      await sleep(PREWARM_COLLECTION_DELAY_MS);
      if (runId !== prewarmRunId) return;
    }

    if (prewarmState && prewarmState.signature === signature) {
      logger.info('Region prewarm completed.', context.region);
      prewarmCompletedSignature = signature;
      prewarmState = null;
      releasePrewarmLease();
    }
  }

  function teardownApp() {
    if (!appState) return;

    clearTimeout(appState.searchTimer);
    clearTimeout(appState.autoIndexTimer);
    cancelLiveDetailHydration(appState);
    abortStateFetches(appState);
    if (appState.ui && appState.ui.panel) {
      appState.ui.panel.remove();
    }
    setNativeHidden(false, appState);
    appState = null;
  }

  function startApp(forceRefresh = false) {
    const route = parseRoute();
    updateRouteClass(route);
    if (!route) {
      teardownApp();
      return;
    }

    if (appState && appState.signature === routeSignature(route) && !forceRefresh) {
      return;
    }

    teardownApp();

    const state = createState(route, forceRefresh);
    appState = state;
    logger.info(
      'Route active.',
      route.region,
      route.collection,
      'page',
      route.currentPage,
      forceRefresh ? 'refresh' : 'normal'
    );
    buildUi(state);
    updateStatus(state);
    startIndexing(state).catch((error) => {
      logger.error('Indexing failed.', error);
      state.indexingDone = true;
      updateStatus(state);
      runSearch(state);
    });
  }

  function installNavigationWatcher() {
    if (!history[HISTORY_PATCH_ATTR]) {
      const originalPushState = history.pushState;
      const originalReplaceState = history.replaceState;

      history.pushState = function patchedPushState(...args) {
        const result = originalPushState.apply(this, args);
        window.dispatchEvent(new Event(NAV_EVENT));
        return result;
      };

      history.replaceState = function patchedReplaceState(...args) {
        const result = originalReplaceState.apply(this, args);
        window.dispatchEvent(new Event(NAV_EVENT));
        return result;
      };

      Object.defineProperty(history, HISTORY_PATCH_ATTR, {
        value: true,
        configurable: false,
      });
    }

    window.addEventListener('popstate', () => window.dispatchEvent(new Event(NAV_EVENT)));
    window.addEventListener('storage', handlePrewarmLeaseStorage);
    window.addEventListener('pagehide', handlePageUnload);
    window.addEventListener('beforeunload', handlePageUnload);
    window.addEventListener(NAV_EVENT, () => {
      injectStyles();
      updateRouteClass();
      clearTimeout(routeCheckTimer);
      routeCheckTimer = setTimeout(() => {
        startApp(false);
        startRegionPrewarm(false);
      }, 150);
    });
  }

  onReady(() => {
    runCacheMigration();
    installNavigationWatcher();
    startApp(false);
    startRegionPrewarm(false);
    logger.info(`Loaded v${SCRIPT_VERSION}.`, 'logLevel', effectiveLogLevel);
  });

  injectStyles();
  updateRouteClass();
})();
