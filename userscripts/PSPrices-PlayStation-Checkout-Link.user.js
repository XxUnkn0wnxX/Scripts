// ==UserScript==
// @name         PSPrices PlayStation Checkout Link
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.2
// @description  Generate regional PlayStation checkout links on PSPrices product pages.
// @homepageURL  https://discord.gg/slayersicerealm
// @author       OpenAI
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/PSPrices-PlayStation-Checkout-Link.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/PSPrices-PlayStation-Checkout-Link.user.js
// @match        https://psprices.com/*
// @match        https://www.psprices.com/*
// @run-at       document-start
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @grant        GM_setClipboard
// @grant        GM.setClipboard
// @grant        GM_log
// @connect      store.playstation.com
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const SCRIPT_NAME = 'PSPrices-Checkout Script';
  const SCRIPT_VERSION = '1.0.2';
  const LOG_LEVEL = 'info';
  const SHOW_DIAGNOSTICS = false;
  const FORCE_CLIPBOARD_FALLBACK = false;
  const FORCE_MANUAL_LINK_FALLBACK = false;

  /*
   * Logging levels:
   * - info: Published default. Logs startup, important state changes, warnings,
   *   categorized failures, HTTP/status codes, and final success/failure results.
   * - verbose: Logs the complete safe execution flow, including route checks,
   *   selector decisions, DOM replacement/restoration, extracted public product
   *   and region data, URL construction, request lifecycle, cache decisions,
   *   stale-result rejection, popup handling, and clipboard fallback.
   *
   * Logging must never include cookies, tokens, CSRF values, account/session
   * data, credential-bearing headers, or raw response bodies.
   */

  const CLIENT_ID = '2eb25762-877f-4140-b341-7c7e14c19f98';
  const CHECKOUT_BASE_URL = 'https://checkout.playstation.com/add';
  const LOOKUP_BASE_URL =
    'https://store.playstation.com/store/api/chihiro/00_09_000/container';

  const REQUEST_TIMEOUT_MS = 20_000;
  const CLICK_COOLDOWN_MS = 3_000;
  const CLIPBOARD_CALLBACK_WAIT_MS = 1_000;

  const OWNER_ATTR = 'data-psprices-checkout-userscript';
  const TARGET_TYPE_ATTR = 'data-psprices-checkout-target';
  const CARD_TEST_ID = 'psprices-checkout-card';
  const ACTION_TEST_ID = 'psprices-checkout-action';
  const STATUS_TEST_ID = 'psprices-checkout-status';
  const DIAGNOSTICS_TEST_ID = 'psprices-checkout-diagnostics';
  const MANUAL_LINK_TEST_ID = 'psprices-checkout-manual-link';
  const STICKY_OWNER_ATTR = 'data-psprices-checkout-sticky';
  const HEADER_BADGE_ATTR = 'data-psprices-checkout-unlocked-badge';
  const HEADER_BADGE_HOST_ATTR = 'data-psprices-checkout-header-badge-ready';
  const WRAPPER_READY_ATTR = 'data-psprices-checkout-ready';
  const BOOTSTRAP_CLASS = 'psprices-checkout-pending';
  const TRANSITION_SUPPRESS_CLASS = 'psprices-checkout-transition-pending';
  const BOOTSTRAP_STYLE_ID = 'psprices-checkout-bootstrap-style';
  const WRAPPER_ENTER_CLASS = 'psprices-checkout-wrapper-enter';
  const WRAPPER_ENTER_ACTIVE_CLASS = 'psprices-checkout-wrapper-enter-active';
  const WRAPPER_ENTER_MS = 450;
  const LINKGEN_START_DELAY_MS = 150;
  const HEADER_WORDMARK_CLASS =
    'text-base font-bold leading-none group-hover:underline text-text ' +
    'group-hover:text-primary dark:group-hover:text-white';
  const HEADER_BADGE_CLASS =
    'text-[8px] font-bold bg-blue-700 dark:bg-blue-600 text-white ' +
    'px-1 py-0 rounded lowercase overflow-hidden';

  const PRODUCT_PATH =
    /^\/region-([a-z0-9-]+)\/game\/(\d+)(?:\/[^/]+)?\/?$/i;
  const FULL_SKU_SUFFIX_RE = /-[A-Z]\d{3}$/i;

  function enableBootstrapSuppression() {
    if (!PRODUCT_PATH.test(window.location.pathname)) return;
    if (!document.documentElement.classList.contains(BOOTSTRAP_CLASS)) {
      document.documentElement.classList.add(BOOTSTRAP_CLASS);
    }
    if (document.getElementById(BOOTSTRAP_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = BOOTSTRAP_STYLE_ID;
    style.textContent = `
      html.${BOOTSTRAP_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]
        #avatar-buy-block[data-avatar-buy-block]:not([${WRAPPER_READY_ATTR}]),
      html.${TRANSITION_SUPPRESS_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]
        #avatar-buy-block[data-avatar-buy-block] {
        opacity: 0 !important;
        pointer-events: none !important;
        transition: none !important;
      }
      html.${BOOTSTRAP_CLASS}
        [x-data*="stickyReveal"][x-data*="#avatar-buy-block"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
      }
      #avatar-buy-block[data-avatar-buy-block].${WRAPPER_ENTER_CLASS} {
        opacity: 0 !important;
        pointer-events: none !important;
      }
      #avatar-buy-block[data-avatar-buy-block].${WRAPPER_ENTER_ACTIVE_CLASS} {
        opacity: 1;
        transition: opacity ${WRAPPER_ENTER_MS}ms ease-out;
      }
      @media (prefers-reduced-motion: reduce) {
        #avatar-buy-block[data-avatar-buy-block].${WRAPPER_ENTER_ACTIVE_CLASS} {
          transition: none;
        }
      }
    `;
    (document.head || document.documentElement).append(style);
  }

  function releaseTransitionSuppression() {
    if (document.documentElement.classList.contains(TRANSITION_SUPPRESS_CLASS)) {
      document.documentElement.classList.remove(TRANSITION_SUPPRESS_CLASS);
    }
  }

  function disableBootstrapSuppression() {
    releaseTransitionSuppression();
    document.documentElement.classList.remove(BOOTSTRAP_CLASS);
  }

  function enableTransitionSuppression() {
    enableBootstrapSuppression();
    if (!document.documentElement.classList.contains(TRANSITION_SUPPRESS_CLASS)) {
      document.documentElement.classList.add(TRANSITION_SUPPRESS_CLASS);
    }
  }

  function markBuyBlockReady(buyBlock, value) {
    if (!buyBlock?.isConnected) return;
    if (buyBlock.getAttribute(WRAPPER_READY_ATTR) !== value) {
      buyBlock.setAttribute(WRAPPER_READY_ATTR, value);
    }
    releaseTransitionSuppression();
  }

  function revealCurrentNativeBuyBlock() {
    const gameDetails = document.querySelectorAll(
      '#game-detail.game-detail--unlockable[data-game-id]'
    );
    if (gameDetails.length !== 1) return false;
    const buyBlocks = gameDetails[0].querySelectorAll(
      '#avatar-buy-block[data-avatar-buy-block]'
    );
    if (buyBlocks.length !== 1) return false;
    markBuyBlockReady(buyBlocks[0], 'native');
    return true;
  }

  function ensureHeaderUnlockedBadge() {
    if (headerBadgeHost?.isConnected) {
      const ownedBadges = [...headerBadgeHost.children].filter((child) =>
        child.hasAttribute(HEADER_BADGE_ATTR)
      );
      const competingBadges = [...headerBadgeHost.children].filter(
        (child) =>
          !child.hasAttribute(HEADER_BADGE_ATTR) &&
          child.matches('span') &&
          child.textContent.trim().toLowerCase() === 'unlocked'
      );
      if (
        ownedBadges.length === 1 &&
        ownedBadges[0].className === HEADER_BADGE_CLASS &&
        ownedBadges[0].textContent === '🏴‍☠️ unlocked' &&
        competingBadges.length === 0
      ) {
        return;
      }
    }
    headerBadgeHost = null;
    for (const homeLink of document.querySelectorAll(
      'a[aria-label="PSprices Home"]'
    )) {
      const wordmark = [...homeLink.querySelectorAll('span')].find(
        (span) =>
          span.className === HEADER_WORDMARK_CLASS &&
          span.textContent.trim().toLowerCase() === 'psprices'
      );
      const line = wordmark?.parentElement;
      if (!line?.classList.contains('leading-5')) continue;
      const existingBadges = [...line.children].filter(
        (child) =>
          child !== wordmark &&
          child.matches('span') &&
          (
            child.hasAttribute(HEADER_BADGE_ATTR) ||
            child.textContent.trim().toLowerCase() === 'unlocked'
          )
      );
      for (const existingBadge of existingBadges) {
        if (
          existingBadge.hasAttribute(HEADER_BADGE_ATTR) &&
          existingBadge.previousSibling?.nodeType === Node.TEXT_NODE &&
          existingBadge.previousSibling.textContent === ' '
        ) {
          existingBadge.previousSibling.remove();
        }
        existingBadge.remove();
      }
      const badge = document.createElement('span');
      badge.className = HEADER_BADGE_CLASS;
      badge.textContent = '🏴‍☠️ unlocked';
      badge.setAttribute(HEADER_BADGE_ATTR, '');
      wordmark.after(document.createTextNode(' '), badge);
      line.setAttribute(HEADER_BADGE_HOST_ATTR, '');
      headerBadgeHost = line;
      return;
    }
  }

  function clearBuyBlockFade(buyBlock) {
    wrapperFadeSequence += 1;
    buyBlock?.classList.remove(
      WRAPPER_ENTER_CLASS,
      WRAPPER_ENTER_ACTIVE_CLASS
    );
  }

  function fadeInBuyBlock(buyBlock, ownerId, onComplete = null) {
    clearBuyBlockFade(buyBlock);
    const fadeSequence = ++wrapperFadeSequence;
    buyBlock.classList.add(WRAPPER_ENTER_CLASS);
    markBuyBlockReady(buyBlock, ownerId);
    window.requestAnimationFrame(() => {
      if (!buyBlock.isConnected || fadeSequence !== wrapperFadeSequence) return;
      buyBlock.classList.add(WRAPPER_ENTER_ACTIVE_CLASS);
      buyBlock.classList.remove(WRAPPER_ENTER_CLASS);
      window.setTimeout(() => {
        if (!buyBlock.isConnected || fadeSequence !== wrapperFadeSequence) return;
        buyBlock.classList.remove(WRAPPER_ENTER_ACTIVE_CLASS);
        if (typeof onComplete === 'function') onComplete();
      }, WRAPPER_ENTER_MS + 40);
    });
  }

  enableBootstrapSuppression();

  const REGION_CONFIG = Object.freeze({
    ar: { country: 'Argentina', defaultLocale: 'es-AR', locales: ['en-AR', 'es-AR'] },
    au: { country: 'Australia', defaultLocale: 'en-AU', locales: ['en-AU'] },
    at: { country: 'Austria', defaultLocale: 'de-AT', locales: ['de-AT'] },
    bh: { country: 'Bahrain', defaultLocale: 'ar-BH', locales: ['ar-BH', 'en-BH'] },
    be: { country: 'Belgium', defaultLocale: 'nl-BE', locales: ['fr-BE', 'nl-BE'] },
    br: { country: 'Brazil', defaultLocale: 'pt-BR', locales: ['en-BR', 'es-BR', 'pt-BR'] },
    bg: { country: 'Bulgaria', defaultLocale: 'en-BG', locales: ['en-BG'] },
    ca: { country: 'Canada', defaultLocale: 'en-CA', locales: ['en-CA', 'fr-CA'] },
    cl: { country: 'Chile', defaultLocale: 'es-CL', locales: ['en-CL', 'es-CL'] },
    cn: { country: 'China', defaultLocale: 'zh-CN', locales: ['zh-CN'] },
    co: { country: 'Colombia', defaultLocale: 'es-CO', locales: ['en-CO', 'es-CO'] },
    cr: { country: 'Costa Rica', defaultLocale: 'es-CR', locales: ['en-CR', 'es-CR'] },
    hr: { country: 'Croatia', defaultLocale: 'en-HR', locales: ['en-HR'] },
    cy: { country: 'Cyprus', defaultLocale: 'en-CY', locales: ['en-CY'] },
    cz: { country: 'Czechia', defaultLocale: 'cs-CZ', locales: ['cs-CZ', 'en-CZ'] },
    dk: { country: 'Denmark', defaultLocale: 'da-DK', locales: ['da-DK', 'en-DK'] },
    ec: { country: 'Ecuador', defaultLocale: 'es-EC', locales: ['en-EC', 'es-EC'] },
    sv: { country: 'El Salvador', defaultLocale: 'es-SV', locales: ['es-SV'] },
    fi: { country: 'Finland', defaultLocale: 'fi-FI', locales: ['en-FI', 'fi-FI'] },
    fr: { country: 'France', defaultLocale: 'fr-FR', locales: ['fr-FR'] },
    de: { country: 'Germany', defaultLocale: 'de-DE', locales: ['de-DE'] },
    gr: { country: 'Greece', defaultLocale: 'el-GR', locales: ['el-GR', 'en-GR'] },
    gt: { country: 'Guatemala', defaultLocale: 'es-GT', locales: ['es-GT'] },
    hn: { country: 'Honduras', defaultLocale: 'es-HN', locales: ['es-HN'] },
    hk: { country: 'Hong Kong', defaultLocale: 'zh-HK', locales: ['ch-HK', 'en-HK', 'zh-HK'] },
    hu: { country: 'Hungary', defaultLocale: 'hu-HU', locales: ['en-HU', 'hu-HU'] },
    is: { country: 'Iceland', defaultLocale: 'en-IS', locales: ['en-IS'] },
    in: { country: 'India', defaultLocale: 'en-IN', locales: ['en-IN'] },
    id: { country: 'Indonesia', defaultLocale: 'id-ID', locales: ['en-ID', 'id-ID'] },
    il: { country: 'Israel', defaultLocale: 'en-IL', locales: ['en-IL'] },
    it: { country: 'Italy', defaultLocale: 'it-IT', locales: ['it-IT'] },
    jp: { country: 'Japan', defaultLocale: 'ja-JP', locales: ['ja-JP'] },
    kw: { country: 'Kuwait', defaultLocale: 'ar-KW', locales: ['ar-KW', 'en-KW'] },
    lb: { country: 'Lebanon', defaultLocale: 'ar-LB', locales: ['ar-LB', 'en-LB'] },
    lu: { country: 'Luxembourg', defaultLocale: 'fr-LU', locales: ['de-LU', 'fr-LU'] },
    my: { country: 'Malaysia', defaultLocale: 'en-MY', locales: ['en-MY'] },
    mt: { country: 'Malta', defaultLocale: 'en-MT', locales: ['en-MT'] },
    mx: { country: 'Mexico', defaultLocale: 'es-MX', locales: ['en-MX', 'es-MX'] },
    nl: { country: 'Netherlands', defaultLocale: 'nl-NL', locales: ['nl-NL'] },
    nz: { country: 'New Zealand', defaultLocale: 'en-NZ', locales: ['en-NZ'] },
    no: { country: 'Norway', defaultLocale: 'no-NO', locales: ['en-NO', 'no-NO'] },
    om: { country: 'Oman', defaultLocale: 'ar-OM', locales: ['ar-OM', 'en-OM'] },
    pa: { country: 'Panama', defaultLocale: 'es-PA', locales: ['en-PA', 'es-PA'] },
    py: { country: 'Paraguay', defaultLocale: 'es-PY', locales: ['es-PY'] },
    pe: { country: 'Peru', defaultLocale: 'es-PE', locales: ['en-PE', 'es-PE'] },
    pl: { country: 'Poland', defaultLocale: 'pl-PL', locales: ['en-PL', 'pl-PL'] },
    pt: { country: 'Portugal', defaultLocale: 'pt-PT', locales: ['pt-PT'] },
    qa: { country: 'Qatar', defaultLocale: 'ar-QA', locales: ['ar-QA', 'en-QA'] },
    ro: { country: 'Romania', defaultLocale: 'ro-RO', locales: ['en-RO', 'ro-RO'] },
    ru: { country: 'Russia', defaultLocale: 'ru-RU', locales: ['ru-RU'] },
    sa: { country: 'Saudi Arabia', defaultLocale: 'ar-SA', locales: ['ar-SA', 'en-SA'] },
    sg: { country: 'Singapore', defaultLocale: 'en-SG', locales: ['en-SG'] },
    sk: { country: 'Slovakia', defaultLocale: 'en-SK', locales: ['en-SK'] },
    si: { country: 'Slovenia', defaultLocale: 'en-SI', locales: ['en-SI'] },
    za: { country: 'South Africa', defaultLocale: 'en-ZA', locales: ['en-ZA'] },
    kr: { country: 'South Korea', defaultLocale: 'ko-KR', locales: ['ko-KR'] },
    es: { country: 'Spain', defaultLocale: 'es-ES', locales: ['en-ES', 'es-ES'] },
    se: { country: 'Sweden', defaultLocale: 'sv-SE', locales: ['en-SE', 'sv-SE'] },
    ch: { country: 'Switzerland', defaultLocale: 'de-CH', locales: ['de-CH', 'fr-CH', 'it-CH'] },
    tw: { country: 'Taiwan', defaultLocale: 'zh-TW', locales: ['ch-TW', 'en-TW', 'zh-TW'] },
    th: { country: 'Thailand', defaultLocale: 'th-TH', locales: ['en-TH', 'th-TH'] },
    tr: { country: 'Türkiye', defaultLocale: 'tr-TR', locales: ['en-TR', 'tr-TR'] },
    ua: { country: 'Ukraine', defaultLocale: 'ru-UA', locales: ['ru-UA'] },
    ae: { country: 'United Arab Emirates', defaultLocale: 'ar-AE', locales: ['ar-AE', 'en-AE'] },
    gb: { country: 'United Kingdom', defaultLocale: 'en-GB', locales: ['en-GB'], aliases: ['uk'] },
    us: { country: 'United States', defaultLocale: 'en-US', locales: ['en-US'] },
    vn: { country: 'Vietnam', defaultLocale: 'vi-VN', locales: ['vi-VN'] }
  });

  const REGION_ALIASES = new Map();
  const VALID_SONY_LOCALES = new Set();
  for (const [region, config] of Object.entries(REGION_CONFIG)) {
    REGION_ALIASES.set(region, region);
    for (const alias of config.aliases || []) REGION_ALIASES.set(alias, region);
    for (const locale of config.locales) VALID_SONY_LOCALES.add(locale);
  }

  const effectiveLogLevel = LOG_LEVEL === 'verbose' ? 'verbose' : 'info';
  const successfulSkuCache = new Map();
  const loggedMessages = new Map();
  let managerLogWarningShown = false;
  let activeMount = null;
  let transitionActive = false;
  let requestGeneration = 0;
  let mountSequence = 0;
  let scheduledFrame = 0;
  let stabilizationFrame = 0;
  let stabilizationCandidate = null;
  let htmxSwapPending = false;
  let wrapperFadeSequence = 0;
  let headerBadgeHost = null;

  function sanitizeLogValue(value) {
    return String(value ?? '')
      .replace(/[\u0000-\u001f\u007f]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 200);
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

  function normalizeRegionAlias(value) {
    const candidate = String(value || '').trim().toLowerCase();
    return REGION_ALIASES.get(candidate) || null;
  }

  function parseProductPath(pathname) {
    const match = PRODUCT_PATH.exec(pathname);
    if (!match) return null;
    return {
      regionAlias: normalizeRegionAlias(match[1]),
      rawRegionAlias: match[1].toLowerCase(),
      productId: match[2],
      pathname
    };
  }

  function normalizeProductId(value) {
    let productId = String(value || '').trim().toUpperCase();
    if (!productId) return null;
    if (FULL_SKU_SUFFIX_RE.test(productId)) {
      const candidate = productId.replace(FULL_SKU_SUFFIX_RE, '');
      if (candidate.split('-').length - 1 === 2) productId = candidate;
    }
    if (productId.split('-').length - 1 !== 2 || !productId.includes('_')) return null;
    return productId;
  }

  function encodeSku(value) {
    return encodeURIComponent(value).replace(/%2D/gi, '-').replace(/%5F/gi, '_');
  }

  function hasProductType(type) {
    if (Array.isArray(type)) return type.some(hasProductType);
    return String(type || '').toLowerCase() === 'product';
  }

  function collectProductObjects(value, output) {
    if (Array.isArray(value)) {
      for (const entry of value) collectProductObjects(entry, output);
      return;
    }
    if (!value || typeof value !== 'object') return;
    if (hasProductType(value['@type']) && typeof value.sku === 'string') output.push(value);
    if (value['@graph']) collectProductObjects(value['@graph'], output);
  }

  function normalizeOffer(offers) {
    if (!offers || typeof offers !== 'object' || Array.isArray(offers)) return null;
    const parsePrice = (value) => {
      if (typeof value === 'string' && !value.trim()) return null;
      const number = Number(value);
      return Number.isFinite(number) && number >= 0 ? number : null;
    };
    const lowPrice = parsePrice(offers.lowPrice);
    const highPrice = parsePrice(offers.highPrice);
    const priceCurrency = String(offers.priceCurrency || '').trim().toUpperCase();
    if (lowPrice === null || highPrice === null || lowPrice > highPrice) return null;
    if (!/^[A-Z]{3}$/.test(priceCurrency)) return null;
    return { lowPrice, highPrice, priceCurrency };
  }

  function readProductMetadata() {
    const products = [];
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        collectProductObjects(JSON.parse(script.textContent || ''), products);
      } catch (_) {
        logger.verbose('Ignored malformed JSON-LD block.');
      }
    }

    const candidates = products
      .map((product) => ({
        product,
        baseProductId: normalizeProductId(product.sku)
      }))
      .filter((candidate) => candidate.baseProductId);

    if (!candidates.length) return { valid: false, reason: 'missing-product-jsonld' };
    const productIds = [...new Set(candidates.map((candidate) => candidate.baseProductId))];
    if (productIds.length !== 1) {
      logger.error('Conflicting Product JSON-LD SKUs found.');
      logger.verbose('Conflicting public candidate IDs:', productIds);
      return { valid: false, reason: 'conflicting-product-jsonld' };
    }

    const baseProductId = productIds[0];
    const offerMap = new Map();
    for (const candidate of candidates) {
      if (candidate.baseProductId !== baseProductId) continue;
      const offerEntries = Array.isArray(candidate.product.offers)
        ? candidate.product.offers
        : [candidate.product.offers];
      for (const entry of offerEntries) {
        const offer = normalizeOffer(entry);
        if (offer) offerMap.set(JSON.stringify(offer), offer);
      }
    }

    const offers = [...offerMap.values()];
    if (offers.length > 1) {
      logger.warn('Matching Product JSON-LD prices conflict; price will be unavailable.');
      logger.verbose('Normalized matching offer sets:', offers);
    }
    return {
      valid: true,
      baseProductId,
      offer: offers.length === 1 ? offers[0] : null,
      priceConflict: offers.length > 1
    };
  }

  function readHeaderRegionState() {
    const element = document.getElementById('header-config');
    if (!element) return { present: false, region: null };
    const candidates = [
      element.textContent,
      element.getAttribute('value'),
      element.getAttribute('data-config')
    ];
    for (const candidate of candidates) {
      if (!candidate) continue;
      try {
        const parsed = JSON.parse(candidate);
        if (parsed && Object.prototype.hasOwnProperty.call(parsed, 'currentRegion')) {
          const rawRegion = String(parsed.currentRegion || '').trim();
          return {
            present: Boolean(rawRegion),
            region: normalizeRegionAlias(rawRegion)
          };
        }
      } catch (_) {}
    }
    const rawRegion = String(element.dataset?.currentRegion || '').trim();
    return {
      present: Boolean(rawRegion),
      region: normalizeRegionAlias(rawRegion)
    };
  }

  function parseCanonicalProduct() {
    const canonical = document.querySelector('link[rel="canonical"]');
    if (!canonical) return { present: false, productId: null };
    try {
      const url = new URL(canonical.href, document.baseURI);
      const parsed = parseProductPath(url.pathname);
      if (!parsed || !parsed.regionAlias) return { present: true, invalid: true };
      return { present: true, productId: parsed.productId };
    } catch (_) {
      return { present: true, invalid: true };
    }
  }

  function selectPurchaseTarget(gameDetail, buyBlock) {
    const avatarTargets = buyBlock.querySelectorAll(
      ':scope > div.flex.flex-col > [data-test-id="avatar-two-step-flow"]'
    );
    if (avatarTargets.length === 1) {
      return { type: 'avatar', element: avatarTargets[0] };
    }
    if (avatarTargets.length > 1) return { invalid: true, reason: 'multiple-avatar-targets' };
    if (buyBlock.querySelector('[data-test-id="avatar-two-step-flow"]')) {
      return { invalid: true, reason: 'unsupported-avatar-target' };
    }
    const themeTargets = buyBlock.querySelectorAll(':scope > div.flex-shrink-0');
    if (themeTargets.length === 1) return { type: 'theme', element: themeTargets[0] };
    return {
      invalid: true,
      reason: themeTargets.length ? 'multiple-theme-targets' : 'missing-purchase-target'
    };
  }

  function sonyLocaleForRegion(regionAlias) {
    return REGION_CONFIG[regionAlias]?.defaultLocale || null;
  }

  function readPageLocale(regionAlias) {
    const values = [];
    const headerConfig = document.getElementById('header-config');
    if (headerConfig) {
      for (const source of [
        headerConfig.textContent,
        headerConfig.getAttribute('value'),
        headerConfig.getAttribute('data-config')
      ]) {
        if (!source) continue;
        try {
          const parsed = JSON.parse(source);
          values.push(parsed?.locale, parsed?.language, parsed?.currentLocale);
        } catch (_) {}
      }
    }
    values.push(document.documentElement.lang);
    const expectedCountry = sonyLocaleForRegion(regionAlias)?.split('-')[1];
    for (const value of values) {
      const match = /^([a-z]{2,3})[-_]([a-z]{2})$/i.exec(String(value || '').trim());
      if (!match || match[2].toUpperCase() !== expectedCountry) continue;
      const locale = `${match[1].toLowerCase()}-${match[2].toUpperCase()}`;
      const intlLocale = locale === 'ch-HK' ? 'zh-HK' : locale === 'ch-TW' ? 'zh-TW' : locale;
      try {
        if (Intl.NumberFormat.supportedLocalesOf([intlLocale]).length) return intlLocale;
      } catch (_) {}
    }
    for (const locale of REGION_CONFIG[regionAlias]?.locales || []) {
      const intlLocale = locale === 'ch-HK' ? 'zh-HK' : locale === 'ch-TW' ? 'zh-TW' : locale;
      try {
        if (Intl.NumberFormat.supportedLocalesOf([intlLocale]).length) return intlLocale;
      } catch (_) {}
    }
    const fallback = `en-${expectedCountry}`;
    try {
      if (Intl.NumberFormat.supportedLocalesOf([fallback]).length) return fallback;
    } catch (_) {}
    return null;
  }

  function formatPrice(offer, intlLocale) {
    if (!offer) return 'Price unavailable';
    if (offer.lowPrice === 0 && offer.highPrice === 0) return 'Free';
    const plainSingle = (value) => `${offer.priceCurrency} ${value}`;
    const plainRange = () =>
      `${offer.priceCurrency} ${offer.lowPrice}–${offer.highPrice}`;
    if (!intlLocale) {
      return offer.lowPrice === offer.highPrice
        ? plainSingle(offer.lowPrice)
        : plainRange();
    }
    try {
      const formatter = new Intl.NumberFormat(intlLocale, {
        style: 'currency',
        currency: offer.priceCurrency
      });
      if (offer.lowPrice === offer.highPrice) return formatter.format(offer.lowPrice);
      return `${formatter.format(offer.lowPrice)}–${formatter.format(offer.highPrice)}`;
    } catch (_) {
      if (offer.lowPrice === offer.highPrice) return plainSingle(offer.lowPrice);
      return plainRange();
    }
  }

  function regionButtonMatches(button, regionAlias) {
    const text = `${button.textContent || ''} ${button.getAttribute('aria-label') || ''}`.toLowerCase();
    const codes = [regionAlias, ...(REGION_CONFIG[regionAlias]?.aliases || [])];
    return codes.some((code) => new RegExp(`(^|\\W)${code}(\\W|$)`, 'i').test(text));
  }

  function getRegionPresentation(regionAlias, excludedRoot) {
    let flagSource = null;
    let flagKind = null;
    let countryName = null;
    const regionButton = [...document.querySelectorAll('[data-region-button]')].find((button) =>
      !excludedRoot?.contains(button) && regionButtonMatches(button, regionAlias)
    );
    if (regionButton) {
      const image = regionButton.querySelector('img');
      if (image?.src) {
        flagSource = image;
        flagKind = 'image';
        const altMatch = /(?:^|,)([^,]+?)\s+flag$/i.exec(image.alt || '');
        if (altMatch) countryName = altMatch[1].trim();
      }
    }

    const selectorEntry = [...document.querySelectorAll('[data-flag], [aria-label]')].find((entry) => {
      if (entry === regionButton) return false;
      if (excludedRoot?.contains(entry)) return false;
      const flag = normalizeRegionAlias(entry.getAttribute('data-flag'));
      if (flag === regionAlias) return true;
      return regionButtonMatches(entry, regionAlias);
    });
    if (!flagSource && selectorEntry) {
      const image = selectorEntry.querySelector('img');
      const sprite = selectorEntry.matches('.flag-sprite')
        ? selectorEntry
        : selectorEntry.querySelector('.flag-sprite');
      if (image?.src) {
        flagSource = image;
        flagKind = 'image';
      } else if (sprite?.textContent?.trim()) {
        flagSource = sprite.textContent.trim();
        flagKind = 'emoji';
      }
    }

    if (!flagSource) {
      const image = [...document.querySelectorAll(
        '[data-test-id="game-detail-region-flag"] img'
      )].find((candidate) => !excludedRoot?.contains(candidate));
      if (image?.src) {
        flagSource = image;
        flagKind = 'image';
      }
    }

    if (!countryName) {
      const breadcrumb = [...document.querySelectorAll('a[href]')].find((link) => {
        if (excludedRoot?.contains(link)) return false;
        try {
          return new URL(link.href, document.baseURI).pathname === `/region-${regionAlias}/index`;
        } catch (_) {
          return false;
        }
      });
      countryName = breadcrumb?.querySelector('[itemprop="name"]')?.textContent?.trim() || null;
    }
    if (!countryName && selectorEntry) {
      countryName =
        selectorEntry.getAttribute('aria-label')?.replace(/\s+flag$/i, '').trim() ||
        selectorEntry.querySelector('[data-country-name], [itemprop="name"]')?.textContent?.trim() ||
        null;
    }
    countryName = countryName || REGION_CONFIG[regionAlias]?.country || regionAlias.toUpperCase();
    return { flagSource, flagKind, countryName };
  }

  function gatherPageContext() {
    const route = parseProductPath(window.location.pathname);
    if (
      !route ||
      !route.regionAlias ||
      (
        route.rawRegionAlias !== route.regionAlias &&
        !REGION_CONFIG[route.regionAlias]?.aliases?.includes(route.rawRegionAlias)
      )
    ) {
      return { valid: false, reason: 'unsupported-route' };
    }

    const rawBodyRegion = String(document.body?.dataset?.region || '').trim();
    const bodyRegion = normalizeRegionAlias(rawBodyRegion);
    const headerRegionState = readHeaderRegionState();
    if (
      (rawBodyRegion && bodyRegion !== route.regionAlias) ||
      (headerRegionState.present && headerRegionState.region !== route.regionAlias)
    ) {
      return { valid: false, temporary: true, reason: 'region-source-conflict', route };
    }

    const gameDetails = document.querySelectorAll(
      '#game-detail.game-detail--unlockable[data-game-id]'
    );
    if (gameDetails.length !== 1) {
      return { valid: false, reason: 'invalid-game-detail-count', route };
    }
    const gameDetail = gameDetails[0];
    if (String(gameDetail.dataset.gameId || '') !== route.productId) {
      return { valid: false, temporary: true, reason: 'route-game-id-conflict', route };
    }

    const canonical = parseCanonicalProduct();
    if (canonical.invalid || (canonical.productId && canonical.productId !== route.productId)) {
      return { valid: false, temporary: true, reason: 'canonical-product-conflict', route };
    }

    const buyBlocks = gameDetail.querySelectorAll('#avatar-buy-block[data-avatar-buy-block]');
    if (buyBlocks.length !== 1) {
      return { valid: false, reason: 'invalid-buy-block-count', route };
    }
    const buyBlock = buyBlocks[0];
    const metadata = readProductMetadata();
    if (!metadata.valid) return { ...metadata, route };

    const target = selectPurchaseTarget(gameDetail, buyBlock);
    if (target.invalid) return { valid: false, reason: target.reason, route };
    const existingOwner = target.element.getAttribute(OWNER_ATTR);
    if (
      existingOwner &&
      (!activeMount ||
        activeMount.targetElement !== target.element ||
        activeMount.ownerId !== existingOwner)
    ) {
      return { valid: false, reason: 'target-already-managed', route };
    }

    const sonyLocale = sonyLocaleForRegion(route.regionAlias);
    if (!sonyLocale || !VALID_SONY_LOCALES.has(sonyLocale)) {
      return { valid: false, reason: 'unsupported-sony-locale', route };
    }
    const [language, country] = sonyLocale.split('-');
    if (!language || !country) return { valid: false, reason: 'invalid-sony-locale', route };

    const intlLocale = readPageLocale(route.regionAlias);
    const presentation = getRegionPresentation(route.regionAlias, target.element);
    const productKey = `${route.regionAlias}:${route.productId}:${metadata.baseProductId}`;
    const signatureKey = [
      route.pathname,
      route.productId,
      canonical.productId || '',
      route.regionAlias,
      sonyLocale,
      metadata.baseProductId,
      target.type
    ].join('|');
    return {
      valid: true,
      route,
      gameDetail,
      buyBlock,
      targetType: target.type,
      targetElement: target.element,
      baseProductId: metadata.baseProductId,
      offer: metadata.offer,
      priceConflict: metadata.priceConflict,
      regionAlias: route.regionAlias,
      sonyLocale,
      language,
      country,
      intlLocale,
      presentation,
      productKey,
      signatureKey
    };
  }

  function sameSignature(left, right) {
    return Boolean(
      left &&
      right &&
      left.signatureKey === right.signatureKey &&
      left.targetElement === right.targetElement &&
      left.targetElement?.isConnected &&
      right.targetElement?.isConnected
    );
  }

  function buildLookupUrl(context) {
    const encodedProductId = encodeSku(context.baseProductId);
    const url = new URL(
      `${LOOKUP_BASE_URL}/${context.country}/${context.language}/19/${encodedProductId}/`
    );
    const expectedPath =
      `/store/api/chihiro/00_09_000/container/${context.country}/` +
      `${context.language}/19/${encodedProductId}/`;
    if (
      url.protocol !== 'https:' ||
      url.hostname !== 'store.playstation.com' ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      url.pathname !== expectedPath
    ) {
      throw new Error('Invalid Sony lookup URL.');
    }
    return url.href;
  }

  function buildCheckoutUrl(fullSku) {
    const encodedSku = encodeSku(fullSku);
    const url = new URL(`${CHECKOUT_BASE_URL}/${encodedSku}`);
    url.searchParams.set('clientId', CLIENT_ID);
    const entries = [...url.searchParams.entries()];
    if (
      url.protocol !== 'https:' ||
      url.hostname !== 'checkout.playstation.com' ||
      url.username ||
      url.password ||
      url.hash ||
      url.pathname !== `/add/${encodedSku}` ||
      entries.length !== 1 ||
      entries[0][0] !== 'clientId' ||
      entries[0][1] !== CLIENT_ID
    ) {
      throw new Error('Invalid checkout URL.');
    }
    return url.href;
  }

  function createTextElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    return element;
  }

  function createFlagElement(presentation) {
    if (!presentation.flagSource) return null;
    const wrapper = document.createElement('span');
    wrapper.className = 'inline-flex bg-white/90 rounded px-0.5 py-px';
    if (presentation.flagKind === 'image') {
      const image = presentation.flagSource.cloneNode(false);
      image.removeAttribute('id');
      image.width = 14;
      image.height = 14;
      image.alt = `${presentation.countryName} flag`;
      wrapper.append(image);
    } else {
      wrapper.textContent = presentation.flagSource;
    }
    return wrapper;
  }

  function setButtonMode(mount, mode, label) {
    const button = mount.ui?.button;
    if (!button) return;
    button.classList.remove('btn-disabled', 'btn-primary', 'btn-success');
    button.style.removeProperty('background-color');
    button.style.removeProperty('border-color');
    button.style.removeProperty('color');
    button.style.removeProperty('opacity');
    mount.ui.buttonLabel.textContent = label;
    if (mode === 'ready') {
      button.classList.add('btn-primary');
      button.disabled = false;
      button.removeAttribute('aria-disabled');
    } else if (mode === 'success') {
      button.classList.add('btn-success');
      button.style.setProperty('background-color', 'var(--color-success)', 'important');
      button.style.setProperty('border-color', 'var(--color-success)', 'important');
      button.style.setProperty('color', 'var(--color-success-content)', 'important');
      button.style.setProperty('opacity', '1', 'important');
      button.disabled = true;
      button.setAttribute('aria-disabled', 'true');
    } else {
      button.classList.add('btn-disabled');
      button.disabled = true;
      button.setAttribute('aria-disabled', 'true');
    }
  }

  function setStatus(mount, message) {
    if (!mount.ui?.status) return;
    mount.ui.status.textContent = message || '';
    mount.ui.status.hidden = !message;
  }

  function removeManualLink(mount) {
    mount.ui?.manualLink?.remove();
    if (mount.ui) mount.ui.manualLink = null;
  }

  function showManualLink(mount) {
    if (mount.ui.manualLink?.isConnected) return;
    const link = document.createElement('a');
    link.dataset.testId = MANUAL_LINK_TEST_ID;
    link.className =
      'flex items-center justify-center gap-2 text-sm text-primary transition-colors hover:text-primary/80';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.href = mount.checkoutUrl;
    const label = createTextElement('span', 'underline', 'Manual Link');
    link.append(label);
    mount.ui.button.insertAdjacentElement('afterend', link);
    mount.ui.manualLink = link;
  }

  function renderCard(mount) {
    const section = document.createElement('section');
    section.dataset.testId = CARD_TEST_ID;
    section.setAttribute(OWNER_ATTR, mount.ownerId);
    section.setAttribute(TARGET_TYPE_ATTR, mount.targetType);
    section.className =
      'rounded-[var(--game-detail-radius-card)] border border-black/40 ' +
      'dark:border-white/15 p-4 space-y-4';

    const headingRow = document.createElement('div');
    headingRow.className = 'flex items-center justify-between gap-2';
    const headingInner = document.createElement('div');
    headingInner.className = 'space-y-1';
    headingInner.append(
      createTextElement(
        'p',
        'text-[11px] text-base-content/40 uppercase tracking-[0.15em] font-medium',
        'PlayStation Store'
      ),
      createTextElement(
        'p',
        'text-3xl font-bold text-base-content tracking-tight leading-none',
        formatPrice(mount.offer, mount.intlLocale)
      )
    );
    headingRow.append(headingInner);

    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.testId = ACTION_TEST_ID;
    button.className =
      'btn btn-md w-full justify-between items-start text-left h-auto ' +
      'min-h-[3.5rem] py-3 px-4';
    const buttonText = document.createElement('span');
    buttonText.className = 'flex flex-col items-start gap-1.5';
    const buttonLabel = createTextElement(
      'span',
      'text-base sm:text-lg font-semibold leading-snug',
      'Add to Cart'
    );
    const regionRow = document.createElement('span');
    regionRow.className = 'inline-flex items-center gap-1 text-sm';
    const flag = createFlagElement(mount.presentation);
    if (flag) regionRow.append(flag);
    regionRow.append(document.createTextNode(mount.presentation.countryName));
    buttonText.append(buttonLabel, regionRow);
    const arrow = createTextElement(
      'span',
      'material-symbols-outlined text-base mt-1',
      'arrow_forward'
    );
    button.append(buttonText, arrow);

    const diagnostics = document.createElement('div');
    diagnostics.dataset.testId = DIAGNOSTICS_TEST_ID;
    diagnostics.className = 'space-y-1 text-xs text-base-content/60 break-words';
    diagnostics.hidden = !SHOW_DIAGNOSTICS;
    const locale = createTextElement('div', '', `Locale: ${mount.sonyLocale}`);
    const sku = createTextElement(
      'div',
      '',
      mount.fullSku ? `SKU: ${mount.fullSku}` :
        mount.state === 'terminal-error' ? 'SKU: Unavailable' :
          mount.state === 'loading' ? 'SKU: Resolving...' : 'SKU: Pending'
    );
    diagnostics.append(locale, sku);

    const status = createTextElement('p', 'text-xs text-base-content/70', '');
    status.dataset.testId = STATUS_TEST_ID;
    status.hidden = true;

    section.append(headingRow, button, diagnostics, status);
    mount.ui = { section, button, buttonLabel, diagnostics, sku, status, manualLink: null };
    button.addEventListener('click', () => handleCheckoutClick(mount));

    if (mount.clickAttempt) {
      setButtonMode(mount, 'success', mount.clickAttempt.label);
    } else if (mount.state === 'ready') {
      setButtonMode(mount, 'ready', 'Add to Cart');
    } else {
      setButtonMode(mount, 'disabled', 'Add to Cart');
    }
    if (mount.state === 'loading') {
      setStatus(mount, 'Resolving regional PlayStation SKU...');
    } else if (mount.state === 'terminal-error') {
      setStatus(mount, 'Checkout link unavailable. See browser console.');
    } else if (mount.popupStatus) {
      setStatus(mount, mount.popupStatus);
    }
    if (mount.manualLinkVisible && mount.checkoutUrl) showManualLink(mount);
    return section;
  }

  function removeChildren(element) {
    while (element.firstChild) element.firstChild.remove();
  }

  function activeTargetIsOwned(mount) {
    return Boolean(
      mount &&
      mount.targetElement?.isConnected &&
      mount.targetElement.getAttribute(OWNER_ATTR) === mount.ownerId &&
      mount.targetElement.getAttribute(TARGET_TYPE_ATTR) === mount.targetType
    );
  }

  function targetStillMatchesType(mount) {
    if (!mount.targetElement?.isConnected) return false;
    if (mount.targetType === 'avatar') {
      return mount.targetElement.matches('[data-test-id="avatar-two-step-flow"]') &&
        mount.targetElement.parentElement?.matches('div.flex.flex-col') &&
        mount.targetElement.parentElement?.parentElement === mount.buyBlock;
    }
    return mount.targetElement.matches('div.flex-shrink-0') &&
      mount.targetElement.parentElement === mount.buyBlock;
  }

  function activeCardIsIntact(mount) {
    if (!activeTargetIsOwned(mount)) return false;
    const expectedCard = [...mount.targetElement.children].find(
      (child) => child.getAttribute(OWNER_ATTR) === mount.ownerId
    );
    return Boolean(
      expectedCard?.dataset.testId === CARD_TEST_ID &&
      mount.targetElement.childNodes.length === 1
    );
  }

  function restoreSticky(mount) {
    const sticky = mount?.managedStickyElement;
    if (!sticky) return;
    if (sticky.isConnected && sticky.getAttribute(STICKY_OWNER_ATTR) === mount.ownerId) {
      if (mount.managedStickyHadStyle) {
        sticky.setAttribute('style', mount.managedStickyOriginalStyle);
      } else {
        sticky.removeAttribute('style');
      }
      sticky.removeAttribute(STICKY_OWNER_ATTR);
      logger.info('Native sticky Buy Unlocked bar restored.');
    }
    mount.managedStickyElement = null;
  }

  function findStickyBar() {
    return [...document.querySelectorAll('[x-data]')].find((element) => {
      const value = element.getAttribute('x-data') || '';
      return /stickyReveal\(\s*['"]#avatar-buy-block['"]\s*\)/.test(value);
    }) || null;
  }

  function hideSticky(mount) {
    if (mount.managedStickyElement && !mount.managedStickyElement.isConnected) {
      mount.managedStickyElement = null;
      mount.managedStickyOriginalStyle = '';
      mount.managedStickyHadStyle = false;
    }
    const sticky = findStickyBar();
    if (!sticky) return;
    if (mount.managedStickyElement === sticky) {
      const displayPriority =
        typeof sticky.style.getPropertyPriority === 'function'
          ? sticky.style.getPropertyPriority('display')
          : 'important';
      if (
        sticky.style.getPropertyValue('display') !== 'none' ||
        displayPriority !== 'important'
      ) {
        sticky.style.setProperty('display', 'none', 'important');
      }
      return;
    }
    restoreSticky(mount);
    mount.managedStickyElement = sticky;
    mount.managedStickyHadStyle = sticky.hasAttribute('style');
    mount.managedStickyOriginalStyle = sticky.getAttribute('style') || '';
    sticky.setAttribute(STICKY_OWNER_ATTR, mount.ownerId);
    sticky.style.setProperty('display', 'none', 'important');
    logger.verbose('Matching sticky Buy Unlocked bar hidden.');
  }

  function cancelClickAttempt(mount) {
    if (!mount?.clickAttempt) return;
    if (mount.clickAttempt.timer) window.clearTimeout(mount.clickAttempt.timer);
    mount.clickAttempt = null;
  }

  function invalidateMountAsync(mount, expectedAbort = true) {
    if (!mount) return;
    cancelClickAttempt(mount);
    if (mount.linkgenStartTimer) {
      window.clearTimeout(mount.linkgenStartTimer);
      mount.linkgenStartTimer = 0;
    }
    mount.checkoutUrl = null;
    if (mount.requestAbort) {
      mount.requestAbort.expected = expectedAbort;
      mount.requestAbort.abort();
      mount.requestAbort = null;
    }
  }

  function clearMarkers(mount) {
    if (!mount?.targetElement) return;
    if (mount.targetElement.getAttribute(OWNER_ATTR) === mount.ownerId) {
      mount.targetElement.removeAttribute(OWNER_ATTR);
      mount.targetElement.removeAttribute(TARGET_TYPE_ATTR);
    }
  }

  function canRestoreNative(mount, requireOwnership = true) {
    if (!mount.targetElement.isConnected) return false;
    if (requireOwnership && !activeTargetIsOwned(mount)) return false;
    const route = parseProductPath(window.location.pathname);
    if (
      !route ||
      route.productId !== mount.routeProductId ||
      route.regionAlias !== mount.regionAlias
    ) {
      return false;
    }
    const rawBodyRegion = String(document.body?.dataset?.region || '').trim();
    const bodyRegion = normalizeRegionAlias(rawBodyRegion);
    const headerRegionState = readHeaderRegionState();
    if (
      (rawBodyRegion && bodyRegion !== mount.regionAlias) ||
      (headerRegionState.present && headerRegionState.region !== mount.regionAlias)
    ) {
      return false;
    }
    const canonical = parseCanonicalProduct();
    if (canonical.invalid || (canonical.productId && canonical.productId !== mount.routeProductId)) {
      return false;
    }
    const gameDetail = mount.buyBlock?.closest(
      '#game-detail.game-detail--unlockable[data-game-id]'
    );
    return Boolean(
      gameDetail?.isConnected &&
      gameDetail.dataset.gameId === mount.routeProductId &&
      mount.buyBlock.parentElement &&
      gameDetail.contains(mount.buyBlock) &&
      mount.targetElement.parentElement &&
      mount.buyBlock.contains(mount.targetElement)
    );
  }

  function teardownMount({ restore = false, reason = 'teardown' } = {}) {
    const mount = activeMount;
    if (!mount) return;
    requestGeneration += 1;
    invalidateMountAsync(mount, true);
    restoreSticky(mount);
    clearBuyBlockFade(mount.buyBlock);

    if (restore && canRestoreNative(mount)) {
      removeChildren(mount.targetElement);
      mount.targetElement.append(mount.savedChildren);
      clearMarkers(mount);
      markBuyBlockReady(mount.buyBlock, 'native');
      logger.info('Native purchase target restored.', reason);
    } else {
      if (activeTargetIsOwned(mount)) removeChildren(mount.targetElement);
      clearMarkers(mount);
      logger.verbose('Owned replacement removed and native fragment discarded.', reason);
    }
    activeMount = null;
  }

  function enterTransition(reason) {
    if (!transitionActive) logger.info('Page context changed; invalidating old checkout state.', reason);
    transitionActive = true;
    enableTransitionSuppression();
    stabilizationCandidate = null;
    if (stabilizationFrame) {
      window.cancelAnimationFrame(stabilizationFrame);
      stabilizationFrame = 0;
    }
    teardownMount({ restore: false, reason });
  }

  function rerenderActiveMount() {
    const mount = activeMount;
    if (!activeTargetIsOwned(mount)) return;
    removeChildren(mount.targetElement);
    mount.targetElement.append(renderCard(mount));
    hideSticky(mount);
    fadeInBuyBlock(
      mount.buyBlock,
      mount.ownerId,
      mount.state === 'waiting' ? () => scheduleRegionalSkuResolution(mount) : null
    );
    logger.verbose('Replacement card re-rendered after native overwrite.');
  }

  function beginRegionalSkuResolution(mount) {
    if (activeMount !== mount || !activeCardIsIntact(mount)) return;
    mount.linkgenStartTimer = 0;
    mount.state = 'loading';
    mount.ui.sku.textContent = 'SKU: Resolving...';
    setButtonMode(mount, 'disabled', 'Add to Cart');
    setStatus(mount, 'Resolving regional PlayStation SKU...');
    void resolveRegionalSku(mount);
  }

  function scheduleRegionalSkuResolution(mount) {
    if (activeMount !== mount || !activeCardIsIntact(mount)) return;
    if (mount.linkgenStartTimer) window.clearTimeout(mount.linkgenStartTimer);
    mount.linkgenStartTimer = window.setTimeout(
      () => beginRegionalSkuResolution(mount),
      LINKGEN_START_DELAY_MS
    );
  }

  function chooseRequestApi() {
    try {
      if (typeof GM === 'object' && typeof GM.xmlHttpRequest === 'function') {
        return { name: 'GM.xmlHttpRequest', call: GM.xmlHttpRequest.bind(GM) };
      }
    } catch (_) {}
    if (typeof GM_xmlhttpRequest === 'function') {
      return { name: 'GM_xmlhttpRequest', call: GM_xmlhttpRequest };
    }
    return null;
  }

  function parseSonyResponse(response) {
    let status = 0;
    try {
      status = Number.parseInt(response?.status, 10) || 0;
    } catch (_) {}
    if (status < 200 || status > 299) {
      const error = new Error(`HTTP ${status || 'unknown'}`);
      error.category = status === 404 ? 'not-found' : 'http';
      error.status = status;
      throw error;
    }
    try {
      if (response?.finalUrl) {
        const finalUrl = new URL(response.finalUrl);
        if (finalUrl.protocol !== 'https:' || finalUrl.hostname !== 'store.playstation.com') {
          const error = new Error('Unexpected redirect.');
          error.category = 'redirect';
          throw error;
        }
      }
    } catch (error) {
      if (error.category) throw error;
      const redirectError = new Error('Malformed final URL.');
      redirectError.category = 'redirect';
      throw redirectError;
    }

    let payload = null;
    let text = '';
    try {
      if (response?.response && typeof response.response === 'object') {
        payload = response.response;
      } else if (typeof response?.response === 'string' && response.response.trim()) {
        text = response.response.trim();
      } else if (typeof response?.responseText === 'string' && response.responseText.trim()) {
        text = response.responseText.trim();
      }
    } catch (_) {
      const error = new Error('Unable to read response fields.');
      error.category = 'internal';
      throw error;
    }
    if (!payload && !text) {
      const error = new Error('Empty response.');
      error.category = 'empty-response';
      throw error;
    }
    if (!payload) {
      try {
        payload = JSON.parse(text);
      } catch (_) {
        const error = new Error('Malformed JSON.');
        error.category = 'malformed-json';
        throw error;
      }
    }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      const error = new Error('Unexpected JSON type.');
      error.category = 'unexpected-json-type';
      throw error;
    }
    return payload;
  }

  function requestSonyJson(url, generation) {
    const api = chooseRequestApi();
    if (!api) {
      const error = new Error('No supported userscript request API.');
      error.category = 'unsupported-manager';
      return { promise: Promise.reject(error), control: null };
    }

    let settled = false;
    let abortHandle = null;
    let watchdog = 0;
    let expectedAbort = false;
    let resolvePromise;
    let rejectPromise;
    const promise = new Promise((resolve, reject) => {
      resolvePromise = resolve;
      rejectPromise = reject;
    });
    const settle = (kind, value) => {
      if (settled) {
        logger.verbose('Ignored duplicate request settlement.', kind, generation);
        return;
      }
      settled = true;
      if (watchdog) window.clearTimeout(watchdog);
      if (kind === 'resolve') resolvePromise(value);
      else rejectPromise(value);
    };
    const fail = (category, message, source) => {
      const error = new Error(message);
      error.category = category;
      error.source = source;
      settle('reject', error);
    };
    const options = {
      method: 'GET',
      url,
      responseType: 'json',
      timeout: REQUEST_TIMEOUT_MS,
      anonymous: true,
      withCredentials: false,
      onload: (response) => {
        try {
          settle('resolve', parseSonyResponse(response));
        } catch (error) {
          settle('reject', error);
        }
      },
      onerror: () => fail('network', 'Network error.', 'onerror'),
      ontimeout: () => fail('timeout', 'Request timed out.', 'ontimeout'),
      onabort: () => fail(expectedAbort ? 'expected-abort' : 'unexpected-abort', 'Request aborted.', 'onabort')
    };

    const control = {
      expected: false,
      abort() {
        expectedAbort = control.expected;
        if (watchdog) window.clearTimeout(watchdog);
        try {
          abortHandle?.();
        } catch (_) {}
        if (!settled) fail(expectedAbort ? 'expected-abort' : 'unexpected-abort', 'Request aborted.', 'abort');
      }
    };

    watchdog = window.setTimeout(() => {
      const error = new Error('Request watchdog timed out.');
      error.category = 'timeout';
      error.source = 'watchdog';
      settle('reject', error);
      expectedAbort = true;
      try {
        abortHandle?.();
      } catch (_) {}
    }, REQUEST_TIMEOUT_MS);

    try {
      const result = api.call(options);
      if (result && typeof result.abort === 'function') {
        abortHandle = result.abort.bind(result);
      }
      if (result && typeof result.then === 'function') {
        result.then(
          (response) => {
            try {
              settle('resolve', parseSonyResponse(response));
            } catch (error) {
              settle('reject', error);
            }
          },
          (error) => {
            if (expectedAbort) {
              fail('expected-abort', 'Request aborted.', 'promise');
            } else {
              const failure = new Error(sanitizeLogValue(error?.message || error || 'Request rejected.'));
              failure.category = 'network';
              settle('reject', failure);
            }
          }
        );
      }
      logger.verbose('Sony request API selected:', api.name);
    } catch (error) {
      const failure = new Error(sanitizeLogValue(error?.message || 'Request API threw.'));
      failure.category = 'internal';
      settle('reject', failure);
    }
    return { promise, control };
  }

  function isCurrentMount(mount, generation) {
    return Boolean(
      activeMount === mount &&
      mount.generation === generation &&
      requestGeneration === generation &&
      activeTargetIsOwned(mount) &&
      mount.targetElement.isConnected
    );
  }

  function markTerminalFailure(mount, category, error) {
    mount.state = 'terminal-error';
    mount.terminalFailureCategory = category;
    mount.fullSku = null;
    mount.checkoutUrl = null;
    if (mount.ui) {
      mount.ui.sku.textContent = 'SKU: Unavailable';
      setButtonMode(mount, 'disabled', 'Add to Cart');
      setStatus(mount, 'Checkout link unavailable. See browser console.');
    }
    const status = error?.status;
    if (category === 'not-found') {
      logger.error('Product was not found in the selected region. HTTP 404.');
    } else if (category === 'http') {
      logger.error(`Sony regional-SKU lookup returned HTTP ${status || 'unknown'}.`);
    } else if (category === 'timeout') {
      logger.error('Sony regional-SKU lookup timed out.');
    } else if (category === 'network') {
      logger.error('Sony regional-SKU lookup failed due to a network error.');
    } else if (category === 'unexpected-abort') {
      logger.error('Sony regional-SKU lookup was aborted unexpectedly.');
    } else if (category === 'empty-response') {
      logger.error('Sony regional-SKU lookup returned an empty response.');
    } else if (category === 'malformed-json') {
      logger.error('Sony regional-SKU lookup returned malformed JSON.');
    } else if (category === 'unexpected-json-type') {
      logger.error('Sony regional-SKU lookup returned an unexpected JSON type.');
    } else if (category === 'redirect') {
      logger.error('Sony regional-SKU lookup redirected unexpectedly.');
    } else if (category === 'missing-sku') {
      logger.error(error?.safeCause || 'No regional SKU was returned.');
    } else if (category === 'unexpected-sku') {
      logger.error('Sony returned an unexpected regional SKU.');
    } else if (category === 'unsupported-manager') {
      logger.error('No supported userscript request API is available.');
    } else {
      logger.error('Sony regional-SKU lookup failed internally.');
    }
    logger.error('Add to Cart disabled because checkout-link generation failed.', category);
    logger.verbose('Terminal failure was not cached.', category, sanitizeLogValue(error?.message));
  }

  async function resolveRegionalSku(mount) {
    const cacheKey = `${mount.sonyLocale}:${mount.baseProductId}`;
    const cached = successfulSkuCache.get(cacheKey);
    if (cached) {
      logger.verbose('Regional SKU cache hit.', cacheKey);
      applyResolvedSku(mount, cached, mount.generation);
      return;
    }
    logger.verbose('Regional SKU cache miss.', cacheKey);

    let lookupUrl;
    try {
      lookupUrl = buildLookupUrl(mount);
    } catch (error) {
      markTerminalFailure(mount, 'internal', error);
      return;
    }
    logger.info('Sony regional-SKU lookup started.', mount.baseProductId, mount.sonyLocale);
    logger.verbose('Public lookup URL:', lookupUrl, 'generation:', mount.generation);

    const request = requestSonyJson(lookupUrl, mount.generation);
    mount.requestAbort = request.control;
    try {
      const payload = await request.promise;
      if (!isCurrentMount(mount, mount.generation)) {
        logger.verbose('Ignored stale Sony lookup result.', mount.generation);
        return;
      }
      mount.requestAbort = null;
      const rawSku = payload?.default_sku?.id;
      if (typeof rawSku !== 'string' || !rawSku.trim()) {
        const error = new Error('Missing regional SKU.');
        error.category = 'missing-sku';
        error.safeCause = sanitizeLogValue(payload?.cause || 'No regional SKU was returned.');
        throw error;
      }
      const fullSku = rawSku.trim().toUpperCase();
      const expected = new RegExp(`^${mount.baseProductId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}-[A-Z]\\d{3}$`);
      if (!expected.test(fullSku)) {
        const error = new Error('Unexpected regional SKU.');
        error.category = 'unexpected-sku';
        throw error;
      }
      successfulSkuCache.set(cacheKey, fullSku);
      logger.verbose('Validated regional SKU cached.', cacheKey);
      applyResolvedSku(mount, fullSku, mount.generation);
    } catch (error) {
      if (error?.category === 'expected-abort' || !isCurrentMount(mount, mount.generation)) {
        logger.info('Sony regional-SKU lookup was aborted because the page context changed.');
        return;
      }
      mount.requestAbort = null;
      markTerminalFailure(mount, error?.category || 'internal', error);
    }
  }

  function applyResolvedSku(mount, fullSku, generation) {
    if (!isCurrentMount(mount, generation)) return;
    try {
      const checkoutUrl = buildCheckoutUrl(fullSku);
      mount.fullSku = fullSku;
      mount.checkoutUrl = checkoutUrl;
      mount.state = 'ready';
      mount.terminalFailureCategory = null;
      mount.ui.sku.textContent = `SKU: ${fullSku}`;
      setButtonMode(mount, 'ready', 'Add to Cart');
      setStatus(mount, '');
      logger.info('Sony regional-SKU lookup completed.', fullSku);
      logger.info('Validated checkout URL prepared.');
      logger.verbose('Public checkout URL:', checkoutUrl);
    } catch (error) {
      markTerminalFailure(mount, 'internal', error);
    }
  }

  function copyWithTextarea(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    let copied = false;
    try {
      document.body.append(textarea);
      textarea.select();
      copied = document.execCommand('copy') === true;
    } catch (_) {
      copied = false;
    } finally {
      textarea.remove();
    }
    return copied;
  }

  async function invokeManagerClipboard(call, text, name) {
    return new Promise((resolve) => {
      let settled = false;
      let callbackTimer = 0;
      const finish = (success) => {
        if (settled) return;
        settled = true;
        if (callbackTimer) window.clearTimeout(callbackTimer);
        resolve(success ? name : null);
      };
      try {
        const expectsCallback = call.length >= 3;
        const result = call(text, 'text', () => finish(true), () => finish(false));
        if (result && typeof result.then === 'function') {
          result.then(() => finish(true), () => finish(false));
        } else if (result === false) {
          finish(false);
        } else if (expectsCallback) {
          callbackTimer = window.setTimeout(
            () => finish(true),
            CLIPBOARD_CALLBACK_WAIT_MS
          );
        } else {
          finish(true);
        }
      } catch (_) {
        finish(false);
      }
    });
  }

  async function copyCheckoutUrl(text) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return 'browser Clipboard API';
      }
    } catch (_) {}
    if (copyWithTextarea(text)) return 'temporary textarea';
    try {
      if (typeof GM === 'object' && typeof GM.setClipboard === 'function') {
        const result = await invokeManagerClipboard(GM.setClipboard.bind(GM), text, 'GM.setClipboard');
        if (result) return result;
      }
    } catch (_) {}
    if (typeof GM_setClipboard === 'function') {
      const result = await invokeManagerClipboard(GM_setClipboard, text, 'GM_setClipboard');
      if (result) return result;
    }
    return null;
  }

  function clickAttemptStillCurrent(mount, attempt) {
    return Boolean(
      activeMount === mount &&
      mount.clickAttempt === attempt &&
      mount.productKey === attempt.productKey &&
      mount.regionAlias === attempt.regionAlias &&
      mount.generation === attempt.generation &&
      mount.checkoutUrl === attempt.checkoutUrl &&
      activeTargetIsOwned(mount)
    );
  }

  function maybeReleaseClick(mount, attempt) {
    if (!clickAttemptStillCurrent(mount, attempt)) return;
    if (!attempt.minimumElapsed || !attempt.asyncSettled) return;
    mount.clickAttempt = null;
    setButtonMode(mount, 'ready', 'Add to Cart');
    logger.info('Add to Cart ready state restored after cooldown.');
  }

  async function handleCheckoutClick(mount) {
    if (
      activeMount !== mount ||
      mount.state !== 'ready' ||
      !mount.checkoutUrl ||
      !activeTargetIsOwned(mount)
    ) {
      return;
    }
    if (mount.clickAttempt) {
      logger.info('Duplicate Add to Cart activation ignored.');
      return;
    }

    const attempt = {
      acceptedAt: Date.now(),
      productKey: mount.productKey,
      regionAlias: mount.regionAlias,
      generation: mount.generation,
      checkoutUrl: mount.checkoutUrl,
      minimumElapsed: false,
      asyncSettled: false,
      timer: 0,
      label: 'Opening...'
    };
    mount.clickAttempt = attempt;
    setButtonMode(mount, 'success', 'Opening...');
    logger.info('Add to Cart click accepted; cooldown started.');
    attempt.timer = window.setTimeout(() => {
      attempt.minimumElapsed = true;
      maybeReleaseClick(mount, attempt);
    }, CLICK_COOLDOWN_MS);

    let opened = false;
    let blankTab = null;
    const forceManualLink = FORCE_MANUAL_LINK_FALLBACK;
    const forceClipboard = FORCE_CLIPBOARD_FALLBACK && !forceManualLink;
    if (!forceClipboard && !forceManualLink) {
      try {
        blankTab = window.open('about:blank', '_blank');
        if (blankTab) {
          try {
            blankTab.opener = null;
          } catch (_) {}
          blankTab.location.href = attempt.checkoutUrl;
          opened = true;
        }
      } catch (error) {
        logger.verbose('New-tab creation or navigation failed.', error);
        try {
          blankTab?.close();
        } catch (_) {}
      }
    } else {
      logger.info(
        forceManualLink
          ? 'Manual Link fallback forced for testing.'
          : 'Clipboard fallback forced for testing.'
      );
    }

    if (!clickAttemptStillCurrent(mount, attempt)) return;
    if (opened) {
      attempt.label = 'Opened';
      setButtonMode(mount, 'success', 'Opened');
      mount.popupStatus = null;
      setStatus(mount, '');
      mount.manualLinkVisible = false;
      removeManualLink(mount);
      logger.info('New tab opened and checkout navigation assigned.');
    } else {
      logger.warn('New tab blocked; attempting checkout-link clipboard fallback.');
      const clipboardMethod = forceManualLink
        ? null
        : await copyCheckoutUrl(attempt.checkoutUrl);
      if (!clickAttemptStillCurrent(mount, attempt)) return;
      if (clipboardMethod) {
        attempt.label = 'Link copied';
        setButtonMode(mount, 'success', 'Link copied');
        mount.popupStatus = 'New tab blocked — checkout link copied.';
        setStatus(mount, mount.popupStatus);
        mount.manualLinkVisible = false;
        removeManualLink(mount);
        logger.info('Clipboard fallback succeeded.', clipboardMethod);
      } else {
        attempt.label = 'Manual Link Rendered';
        setButtonMode(mount, 'success', attempt.label);
        mount.popupStatus = 'New tab blocked — use the Manual Link above.';
        setStatus(mount, mount.popupStatus);
        mount.manualLinkVisible = true;
        showManualLink(mount);
        logger.error('Clipboard fallback failed; Manual Link shown.');
      }
    }
    attempt.asyncSettled = true;
    maybeReleaseClick(mount, attempt);
  }

  function mountReplacement(context) {
    const ownerId = `${Date.now()}-${++mountSequence}`;
    const savedChildren = document.createDocumentFragment();
    const mount = {
      ownerId,
      targetType: context.targetType,
      targetElement: context.targetElement,
      buyBlock: context.buyBlock,
      savedChildren,
      route: context.route.pathname,
      routeProductId: context.route.productId,
      baseProductId: context.baseProductId,
      regionAlias: context.regionAlias,
      sonyLocale: context.sonyLocale,
      language: context.language,
      country: context.country,
      intlLocale: context.intlLocale,
      presentation: context.presentation,
      offer: context.offer,
      productKey: context.productKey,
      signatureKey: context.signatureKey,
      generation: ++requestGeneration,
      requestAbort: null,
      linkgenStartTimer: 0,
      state: 'waiting',
      fullSku: null,
      checkoutUrl: null,
      terminalFailureCategory: null,
      managedStickyElement: null,
      managedStickyOriginalStyle: '',
      managedStickyHadStyle: false,
      clickAttempt: null,
      popupStatus: null,
      manualLinkVisible: false,
      ui: null
    };
    const card = renderCard(mount);

    try {
      const current = gatherPageContext();
      if (!sameSignature(context, current)) {
        logger.verbose('Mount cancelled because page signature changed before mutation.');
        scheduleLifecycle('mount-signature-changed');
        return;
      }
      while (mount.targetElement.firstChild) {
        savedChildren.append(mount.targetElement.firstChild);
      }
      mount.targetElement.setAttribute(OWNER_ATTR, ownerId);
      mount.targetElement.setAttribute(TARGET_TYPE_ATTR, mount.targetType);
      mount.targetElement.append(card);
      activeMount = mount;
      transitionActive = false;
      hideSticky(mount);
      fadeInBuyBlock(
        mount.buyBlock,
        ownerId,
        () => scheduleRegionalSkuResolution(mount)
      );
      logger.info(
        'Eligible purchase flow found and replacement mounted.',
        mount.targetType,
        mount.baseProductId,
        mount.regionAlias,
        mount.sonyLocale
      );
    } catch (error) {
      logger.error('Checkout replacement mount failed internally.', error);
      if (activeMount === mount) activeMount = null;
      invalidateMountAsync(mount, true);
      restoreSticky(mount);
      const restoredNative = canRestoreNative(mount, false);
      if (restoredNative) {
        removeChildren(mount.targetElement);
        mount.targetElement.append(savedChildren);
      } else if (mount.targetElement.isConnected) {
        removeChildren(mount.targetElement);
      }
      clearMarkers(mount);
      clearBuyBlockFade(mount.buyBlock);
      if (restoredNative) {
        markBuyBlockReady(mount.buyBlock, 'native');
      } else {
        releaseTransitionSuppression();
      }
    }
  }

  function activeContextChanged(context) {
    const mount = activeMount;
    if (!mount) return false;
    if (!context.valid) {
      const routeChanged =
        !context.route ||
        context.route.productId !== mount.routeProductId ||
        context.route.regionAlias !== mount.regionAlias;
      if (routeChanged || context.temporary) {
        enterTransition(context.reason);
      } else {
        teardownMount({ restore: true, reason: context.reason });
      }
      return true;
    }
    if (
      context.productKey !== mount.productKey ||
      context.targetElement !== mount.targetElement ||
      context.targetType !== mount.targetType ||
      context.signatureKey !== mount.signatureKey
    ) {
      enterTransition('active-signature-changed');
      return true;
    }
    if (!activeTargetIsOwned(mount) || !targetStillMatchesType(mount)) {
      enterTransition('active-target-lost');
      return true;
    }
    return false;
  }

  function lifecyclePass() {
    ensureHeaderUnlockedBadge();
    if (PRODUCT_PATH.test(window.location.pathname)) {
      enableBootstrapSuppression();
    }
    const context = gatherPageContext();
    logger.verbose('Lifecycle pass.', context.valid ? context.signatureKey : context.reason);

    if (activeMount) {
      if (activeContextChanged(context)) {
        scheduleLifecycle('post-transition');
        return;
      }
      hideSticky(activeMount);
      if (!activeCardIsIntact(activeMount)) {
        rerenderActiveMount();
      }
      return;
    }

    if (!context.valid) {
      stabilizationCandidate = null;
      if (context.reason === 'unsupported-route') {
        transitionActive = false;
        disableBootstrapSuppression();
      } else if (context.temporary || htmxSwapPending) {
        enableTransitionSuppression();
      } else {
        transitionActive = false;
        if (!revealCurrentNativeBuyBlock() && document.readyState !== 'loading') {
          releaseTransitionSuppression();
        }
      }
      return;
    }
    if (htmxSwapPending) {
      stabilizationCandidate = null;
      return;
    }

    if (!sameSignature(context, stabilizationCandidate)) {
      stabilizationCandidate = context;
      if (stabilizationFrame) window.cancelAnimationFrame(stabilizationFrame);
      stabilizationFrame = window.requestAnimationFrame(() => {
        stabilizationFrame = 0;
        const stable = gatherPageContext();
        if (sameSignature(stabilizationCandidate, stable)) {
          mountReplacement(stable);
          stabilizationCandidate = null;
        } else {
          stabilizationCandidate = stable.valid ? stable : null;
          scheduleLifecycle('stabilization-restart');
        }
      });
      return;
    }
  }

  function scheduleLifecycle(reason = 'mutation') {
    if (scheduledFrame) return;
    logger.verbose('Lifecycle scheduled.', reason);
    scheduledFrame = window.requestAnimationFrame(() => {
      scheduledFrame = 0;
      lifecyclePass();
    });
  }

  function htmxTargetAffectsProductArea(event) {
    const target = event.detail?.target;
    if (!(target instanceof Element)) return false;
    const gameDetail = document.getElementById('game-detail');
    const activeTarget = activeMount?.targetElement;
    return Boolean(
      target.id === 'main-content' ||
      target.id === 'game-detail' ||
      target.id === 'avatar-buy-block' ||
      target === activeTarget ||
      activeTarget?.contains(target) ||
      (gameDetail && target.contains(gameDetail)) ||
      (activeTarget && target.contains(activeTarget)) ||
      gameDetail?.contains(target)
    );
  }

  logger.info(`has started (v${SCRIPT_VERSION})`);
  try {
    logger.verbose('Userscript manager:', GM_info?.scriptHandler || 'unknown');
  } catch (_) {
    logger.verbose('Userscript manager: unknown');
  }

  const observer = new MutationObserver(() => {
    ensureHeaderUnlockedBadge();
    if (PRODUCT_PATH.test(window.location.pathname)) {
      enableBootstrapSuppression();
    }
    if (activeMount && !activeCardIsIntact(activeMount)) {
      enableTransitionSuppression();
      activeMount.buyBlock?.removeAttribute(WRAPPER_READY_ATTR);
    }
    scheduleLifecycle('mutation');
  });
  observer.observe(document.documentElement, {
    childList: true,
    attributes: true,
    attributeFilter: [
      'class',
      'data-avatar-buy-block',
      'data-game-id',
      'data-region',
      'data-test-id',
      'href',
      'id',
      'style',
      'x-data'
    ],
    subtree: true
  });
  window.addEventListener('pageshow', () => {
    ensureHeaderUnlockedBadge();
    enableBootstrapSuppression();
    scheduleLifecycle('pageshow');
  });
  window.addEventListener('popstate', () => {
    enableBootstrapSuppression();
    scheduleLifecycle('popstate');
  });
  document.addEventListener('DOMContentLoaded', () => {
    ensureHeaderUnlockedBadge();
    scheduleLifecycle('DOMContentLoaded');
  });
  document.addEventListener('htmx:beforeSwap', (event) => {
    if (htmxTargetAffectsProductArea(event)) {
      htmxSwapPending = true;
      enterTransition('htmx-beforeSwap');
    }
  });
  document.addEventListener('htmx:afterSwap', (event) => {
    if (htmxSwapPending || htmxTargetAffectsProductArea(event)) {
      htmxSwapPending = false;
      scheduleLifecycle('htmx-afterSwap');
    }
  });
  scheduleLifecycle('initial');
})();
