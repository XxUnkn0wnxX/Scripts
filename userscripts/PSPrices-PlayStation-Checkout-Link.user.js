// ==UserScript==
// @name         PSPrices PlayStation Checkout Link
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.1.1
// @description  Replaces PSPrices paywalled avatar/theme purchase panels, availability placeholders, or unavailable-store warnings with custom regional PS Store checkout-link panels, adds an unlocked badge, and hides unlock prompts and the site-wide ads-free and publisher-filter promos. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-PlayStation-Checkout-Link.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-PlayStation-Checkout-Link.user.js
// @match        https://psprices.com/*
// @match        https://www.psprices.com/*
// @run-at       document-start
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @grant        GM_setClipboard
// @grant        GM.setClipboard
// @grant        GM_log
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM.getValue
// @grant        GM.setValue
// @grant        GM.registerMenuCommand
// @connect      store.playstation.com
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const SCRIPT_NAME = 'PSPrices-Checkout Script';
  const SCRIPT_VERSION = '1.1.1';

  const DEFAULT_SETTINGS = Object.freeze({
    LOG_LEVEL: 'info',
    SHOW_DIAGNOSTICS: false,
    FORCE_CLIPBOARD_FALLBACK: false,
    FORCE_MANUAL_LINK_FALLBACK: false,
    REQUEST_TIMEOUT_MS: 20_000,
    CLICK_COOLDOWN_MS: 3_000,
    CLIPBOARD_CALLBACK_WAIT_MS: 1_000,
    WRAPPER_ENTER_MS: 450,
    LINKGEN_START_DELAY_MS: 150
  });

  const SETTINGS_STORAGE_PREFIX = 'psprices-checkout-link.setting:';
  const SETTINGS_STORAGE_MISSING = '__psprices_checkout_setting_missing__';
  const SETTINGS_MENU_LABEL = 'PSPrices Checkout Link settings';
  const SETTINGS_ROOT_OPEN_ATTR = 'data-psprices-checkout-settings-open';
  const SETTINGS_GLOBAL_STYLE_ID = 'psprices-checkout-settings-global-style';
  const SETTINGS_WARNING =
    'Advanced users only. Changing these settings can break checkout-link generation or fallback behavior. You are responsible for problems caused by your changes.';
  const SETTINGS_DEFINITIONS = Object.freeze([
    { name: 'LOG_LEVEL', label: 'Log level', type: 'select' },
    { name: 'SHOW_DIAGNOSTICS', label: 'Show diagnostics', type: 'boolean' },
    { name: 'FORCE_CLIPBOARD_FALLBACK', label: 'Force clipboard fallback', type: 'boolean' },
    { name: 'FORCE_MANUAL_LINK_FALLBACK', label: 'Force Manual Link fallback', type: 'boolean' },
    { name: 'REQUEST_TIMEOUT_MS', label: 'Request timeout (ms)', type: 'number', min: 1, max: 120_000 },
    { name: 'CLICK_COOLDOWN_MS', label: 'Click cooldown (ms)', type: 'number', min: 0, max: 120_000 },
    { name: 'CLIPBOARD_CALLBACK_WAIT_MS', label: 'Clipboard callback wait (ms)', type: 'number', min: 0, max: 10_000 },
    { name: 'WRAPPER_ENTER_MS', label: 'Wrapper fade duration (ms)', type: 'number', min: 0, max: 10_000 },
    { name: 'LINKGEN_START_DELAY_MS', label: 'Link generation start delay (ms)', type: 'number', min: 0, max: 10_000 }
  ]);

  let LOG_LEVEL = DEFAULT_SETTINGS.LOG_LEVEL;
  let SHOW_DIAGNOSTICS = DEFAULT_SETTINGS.SHOW_DIAGNOSTICS;
  let FORCE_CLIPBOARD_FALLBACK = DEFAULT_SETTINGS.FORCE_CLIPBOARD_FALLBACK;
  let FORCE_MANUAL_LINK_FALLBACK = DEFAULT_SETTINGS.FORCE_MANUAL_LINK_FALLBACK;

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

  let REQUEST_TIMEOUT_MS = DEFAULT_SETTINGS.REQUEST_TIMEOUT_MS;
  let CLICK_COOLDOWN_MS = DEFAULT_SETTINGS.CLICK_COOLDOWN_MS;
  let CLIPBOARD_CALLBACK_WAIT_MS = DEFAULT_SETTINGS.CLIPBOARD_CALLBACK_WAIT_MS;

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
  const COSMETIC_STYLE_ID = 'psprices-checkout-cosmetic-style';
  const WRAPPER_ENTER_CLASS = 'psprices-checkout-wrapper-enter';
  const WRAPPER_ENTER_ACTIVE_CLASS = 'psprices-checkout-wrapper-enter-active';
  let WRAPPER_ENTER_MS = DEFAULT_SETTINGS.WRAPPER_ENTER_MS;
  let LINKGEN_START_DELAY_MS = DEFAULT_SETTINGS.LINKGEN_START_DELAY_MS;
  const HEADER_BADGE_CLASS =
    'text-[8px] font-bold bg-blue-700 dark:bg-blue-600 text-white ' +
    'px-1 py-0 rounded lowercase overflow-hidden';
  const SKU_SCRIPT_CARD_ID = 'psprices-product-sku-userscript';
  const UNAVAILABLE_STORE_TEXT =
    'This item is no longer available for purchase on the PlayStation Store';
  const THEME_TARGET_SELECTOR = 'div.flex-shrink-0, div.shrink-0';

  const PRODUCT_PATH =
    /^\/region-([a-z0-9-]+)\/game\/(\d+)(?:\/[^/]+)?\/?$/i;
  const FULL_SKU_SUFFIX_RE = /-[A-Z0-9]{4}$/i;
  const SONY_SKU_SUFFIX_RE = /^[A-Z0-9]{4}$/;

  function enablePermanentCosmeticSuppression() {
    if (document.getElementById(COSMETIC_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = COSMETIC_STYLE_ID;
    style.textContent = `
      [data-test-id="avatar-collection-bridge"],
      [data-notice="ads-free"][data-test-id="notice-tip"],
      [data-notice="no-ai-slop"][data-test-id="notice-tip"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
      }
    `;
    (document.head || document.documentElement).append(style);
  }

  function enableBootstrapSuppression() {
    enablePermanentCosmeticSuppression();
    if (!PRODUCT_PATH.test(window.location.pathname)) return;
    if (!document.documentElement.classList.contains(BOOTSTRAP_CLASS)) {
      document.documentElement.classList.add(BOOTSTRAP_CLASS);
    }
    const styleText = buildBootstrapStyleText();
    const existingStyle = document.getElementById(BOOTSTRAP_STYLE_ID);
    if (existingStyle) {
      if (existingStyle.textContent !== styleText) existingStyle.textContent = styleText;
      return;
    }
    const style = document.createElement('style');
    style.id = BOOTSTRAP_STYLE_ID;
    style.textContent = styleText;
    (document.head || document.documentElement).append(style);
  }

  function buildBootstrapStyleText() {
    return `
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
        #game-detail.game-detail--unlockable[data-game-id]:not(:has(#avatar-buy-block[data-avatar-buy-block]))
        .order-last.lg\\:order-1.lg\\:col-span-4 > .alert.alert-warning,
      html.${BOOTSTRAP_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]:not(:has(#avatar-buy-block[data-avatar-buy-block]))
        .order-last.lg\\:order-1.lg\\:col-span-4 > [hx-get*="/game/fragment/availability/"],
      html.${BOOTSTRAP_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]:not(:has(#avatar-buy-block[data-avatar-buy-block]))
        .order-last.lg\\:order-1.lg\\:col-span-4 > [data-hx-get*="/game/fragment/availability/"],
      html.${TRANSITION_SUPPRESS_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]:not(:has(#avatar-buy-block[data-avatar-buy-block]))
        .order-last.lg\\:order-1.lg\\:col-span-4 > .alert.alert-warning,
      html.${TRANSITION_SUPPRESS_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]:not(:has(#avatar-buy-block[data-avatar-buy-block]))
        .order-last.lg\\:order-1.lg\\:col-span-4 > [hx-get*="/game/fragment/availability/"],
      html.${TRANSITION_SUPPRESS_CLASS}
        #game-detail.game-detail--unlockable[data-game-id]:not(:has(#avatar-buy-block[data-avatar-buy-block]))
        .order-last.lg\\:order-1.lg\\:col-span-4 > [data-hx-get*="/game/fragment/availability/"] {
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
      [${TARGET_TYPE_ATTR}].${WRAPPER_ENTER_CLASS},
      #avatar-buy-block[data-avatar-buy-block].${WRAPPER_ENTER_CLASS} {
        opacity: 0 !important;
        pointer-events: none !important;
      }
      [${TARGET_TYPE_ATTR}].${WRAPPER_ENTER_ACTIVE_CLASS},
      #avatar-buy-block[data-avatar-buy-block].${WRAPPER_ENTER_ACTIVE_CLASS} {
        opacity: 1;
        transition: opacity ${WRAPPER_ENTER_MS}ms ease-out;
      }
      @media (prefers-reduced-motion: reduce) {
        [${TARGET_TYPE_ATTR}].${WRAPPER_ENTER_ACTIVE_CLASS},
        #avatar-buy-block[data-avatar-buy-block].${WRAPPER_ENTER_ACTIVE_CLASS} {
          transition: none;
        }
      }
    `;
  }

  function refreshBootstrapStyle() {
    const style = document.getElementById(BOOTSTRAP_STYLE_ID);
    if (style) style.textContent = buildBootstrapStyleText();
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
      'a[aria-label]'
    )) {
      const homeLabel = (homeLink.getAttribute('aria-label') || '')
        .trim()
        .toLowerCase()
        .replace(/\s+/g, ' ');
      if (homeLabel !== 'psprices home') continue;

      const matchingWords = [...homeLink.querySelectorAll('*')].filter(
        (node) =>
          node.namespaceURI === 'http://www.w3.org/1999/xhtml' &&
          node.textContent
            .trim()
            .replace(/\s+/g, ' ')
            .toLowerCase() === 'psprices'
      );
      let wordmark;
      for (let i = matchingWords.length - 1; i >= 0; i--) {
        const candidate = matchingWords[i];
        const hasNestedMatch = matchingWords.some(
          (other) => other !== candidate && candidate.contains(other)
        );
        if (!hasNestedMatch) {
          wordmark = candidate;
          break;
        }
      }
      const line = wordmark?.parentElement;
      if (!line) continue;
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

  let effectiveLogLevel = LOG_LEVEL === 'verbose' ? 'verbose' : 'info';
  const successfulSkuCache = new Map();
  const loggedMessages = new Map();
  let managerLogWarningShown = false;
  let settingsReady = false;
  let settingsStartupPromise = null;
  let settingsMutationGeneration = 0;
  let settingsStorage = null;
  let settingsStorageWriteChain = Promise.resolve();
  let settingsStorageWarning = null;
  const settingsProtectedKeys = new Set();
  let settingsMenuRegistered = false;
  let settingsDialogUi = null;
  let settingsDialogOpen = false;
  let settingsDialogPending = false;
  let settingsDialogDraft = null;
  let settingsDialogTouched = new Set();
  let settingsDialogPointerDownOutside = false;
  let settingsLastSavedSnapshot = null;
  let settingsDialogLastFocus = null;
  let runtimeStarted = false;
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

  // Cosmetic/bootstrap suppression remains document-start; only checkout
  // lifecycle startup waits for the asynchronous settings read.
  ensureHeaderUnlockedBadge();
  startSettingsInitialization();

  function copySettings(settings) {
    return SETTINGS_DEFINITIONS.reduce((copy, definition) => {
      copy[definition.name] = settings[definition.name];
      return copy;
    }, {});
  }

  function normalizeSettingValue(definition, value) {
    if (definition.type === 'select') {
      return value === 'info' || value === 'verbose' ? value : null;
    }
    if (definition.type === 'boolean') {
      return typeof value === 'boolean' ? value : null;
    }
    if (typeof value !== 'number' && typeof value !== 'string') return null;
    if (typeof value === 'string' && value.trim() === '') return null;
    const numeric = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(numeric) || numeric < definition.min || numeric > definition.max) {
      return null;
    }
    return numeric;
  }

  function validateSettings(settings) {
    const normalized = {};
    for (const definition of SETTINGS_DEFINITIONS) {
      const value = normalizeSettingValue(definition, settings[definition.name]);
      if (value === null) {
        return {
          ok: false,
          error: `${definition.label} must be a valid ${
            definition.type === 'number'
              ? `finite number from ${definition.min} to ${definition.max}`
              : definition.type === 'boolean' ? 'boolean' : "'info' or 'verbose'"
          }.`
        };
      }
      normalized[definition.name] = value;
    }
    return { ok: true, settings: normalized };
  }

  function activeSettingsSnapshot() {
    return {
      LOG_LEVEL,
      SHOW_DIAGNOSTICS,
      FORCE_CLIPBOARD_FALLBACK,
      FORCE_MANUAL_LINK_FALLBACK,
      REQUEST_TIMEOUT_MS,
      CLICK_COOLDOWN_MS,
      CLIPBOARD_CALLBACK_WAIT_MS,
      WRAPPER_ENTER_MS,
      LINKGEN_START_DELAY_MS
    };
  }

  function applyRuntimeSettings(settings) {
    const validated = validateSettings(settings);
    if (!validated.ok) return false;
    const values = validated.settings;
    LOG_LEVEL = values.LOG_LEVEL;
    SHOW_DIAGNOSTICS = values.SHOW_DIAGNOSTICS;
    FORCE_CLIPBOARD_FALLBACK = values.FORCE_CLIPBOARD_FALLBACK;
    FORCE_MANUAL_LINK_FALLBACK = values.FORCE_MANUAL_LINK_FALLBACK;
    REQUEST_TIMEOUT_MS = values.REQUEST_TIMEOUT_MS;
    CLICK_COOLDOWN_MS = values.CLICK_COOLDOWN_MS;
    CLIPBOARD_CALLBACK_WAIT_MS = values.CLIPBOARD_CALLBACK_WAIT_MS;
    WRAPPER_ENTER_MS = values.WRAPPER_ENTER_MS;
    LINKGEN_START_DELAY_MS = values.LINKGEN_START_DELAY_MS;
    effectiveLogLevel = LOG_LEVEL === 'verbose' ? 'verbose' : 'info';
    return true;
  }

  function getSettingsStorage() {
    let modern = null;
    try {
      modern = typeof GM === 'object' && GM ? GM : null;
    } catch (_) {}
    if (
      modern &&
      typeof modern.getValue === 'function' &&
      typeof modern.setValue === 'function'
    ) {
      return {
        name: 'modern',
        get(key) {
          return modern.getValue(key, SETTINGS_STORAGE_MISSING);
        },
        set(key, value) {
          return modern.setValue(key, value);
        }
      };
    }
    if (typeof GM_getValue === 'function' && typeof GM_setValue === 'function') {
      return {
        name: 'legacy',
        get(key) {
          return GM_getValue(key, SETTINGS_STORAGE_MISSING);
        },
        set(key, value) {
          return GM_setValue(key, value);
        }
      };
    }
    return null;
  }

  function settingsStorageKey(name) {
    return `${SETTINGS_STORAGE_PREFIX}${name}`;
  }

  async function readSetting(definition, storage) {
    try {
      const raw = await Promise.resolve(storage.get(settingsStorageKey(definition.name)));
      if (raw === SETTINGS_STORAGE_MISSING) return { kind: 'missing' };
      if (typeof raw === 'undefined') {
        return { kind: 'failed', error: new Error('Storage returned an unknown value.') };
      }
      const value = normalizeSettingValue(definition, raw);
      if (value === null) {
        return { kind: 'failed', error: new Error('Stored setting failed validation.') };
      }
      return { kind: 'value', value };
    } catch (error) {
      return { kind: 'failed', error };
    }
  }

  function setSettingsDialogStatus(message, state = 'info') {
    if (!settingsDialogUi?.status) return;
    settingsDialogUi.status.textContent = message;
    settingsDialogUi.status.dataset.state = state;
  }

  function ensureSettingsGlobalStyle() {
    if (!document || typeof document.createElement !== 'function') return;
    const existing = document.getElementById(SETTINGS_GLOBAL_STYLE_ID);
    if (existing && existing.isConnected !== false) return;
    const style = document.createElement('style');
    style.id = SETTINGS_GLOBAL_STYLE_ID;
    style.textContent = `
      html[${SETTINGS_ROOT_OPEN_ATTR}] {
        scrollbar-gutter: stable;
        overflow: hidden !important;
        overscroll-behavior: none !important;
      }
      html[${SETTINGS_ROOT_OPEN_ATTR}] body {
        overflow: hidden !important;
        overscroll-behavior: none !important;
      }
    `;
    const parent = document.head || document.documentElement;
    if (parent) parent.append(style);
  }

  function markSettingsRootOpen() {
    ensureSettingsGlobalStyle();
    document.documentElement?.setAttribute(SETTINGS_ROOT_OPEN_ATTR, '');
  }

  function clearSettingsRootOpen() {
    document.documentElement?.removeAttribute(SETTINGS_ROOT_OPEN_ATTR);
  }

  function parseSettingsCssColor(value) {
    const text = String(value || '').trim().toLowerCase();
    if (text === 'transparent') return [0, 0, 0, 0];
    const match = text.match(/^rgba?\((.*)\)$/);
    if (!match) return null;
    const parts = match[1].replace(/[,/]/g, ' ').trim().split(/\s+/);
    if (parts.length < 3) return null;
    const channel = (part) => {
      const number = Number.parseFloat(part);
      if (!Number.isFinite(number)) return null;
      return part.endsWith('%') ? Math.max(0, Math.min(255, number * 2.55)) : Math.max(0, Math.min(255, number));
    };
    const red = channel(parts[0]);
    const green = channel(parts[1]);
    const blue = channel(parts[2]);
    if (red === null || green === null || blue === null) return null;
    let alpha = parts.length > 3 ? Number.parseFloat(parts[3]) : 1;
    if (parts.length > 3 && parts[3].endsWith('%')) alpha /= 100;
    return [red, green, blue, Number.isFinite(alpha) ? Math.max(0, Math.min(1, alpha)) : 1];
  }

  function settingsRelativeLuminance(color) {
    const channel = (value) => {
      const normalized = value / 255;
      return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
    };
    return channel(color[0]) * 0.2126 + channel(color[1]) * 0.7152 + channel(color[2]) * 0.0722;
  }

  function sampleSettingsElementLuminance(element, view) {
    let composite = null;
    let node = element;
    while (node && node.nodeType === 1) {
      let computed;
      try {
        computed = view.getComputedStyle(node);
      } catch (_) {
        computed = null;
      }
      if (computed && computed.display !== 'none' && computed.visibility !== 'hidden' && Number(computed.opacity || 1) > 0) {
        const color = parseSettingsCssColor(computed.backgroundColor);
        if (color) {
          if (!composite) composite = color;
          else {
            const alpha = composite[3] + color[3] * (1 - composite[3]);
            composite = [
              (composite[0] * composite[3] + color[0] * color[3] * (1 - composite[3])) / (alpha || 1),
              (composite[1] * composite[3] + color[1] * color[3] * (1 - composite[3])) / (alpha || 1),
              (composite[2] * composite[3] + color[2] * color[3] * (1 - composite[3])) / (alpha || 1),
              alpha
            ];
          }
          if (composite[3] >= 0.96) return settingsRelativeLuminance(composite);
        }
      }
      if (node === document.documentElement) break;
      node = node.parentNode;
    }
    return composite && composite[3] >= 0.96 ? settingsRelativeLuminance(composite) : null;
  }

  function preferredSettingsBackdropTheme(view = window) {
    try {
      return view && typeof view.matchMedia === 'function' && view.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light'
        : 'dark';
    } catch (_) {
      return 'dark';
    }
  }

  function detectSettingsBackdropTheme() {
    const view = document.defaultView || window;
    const width = Number(view && view.innerWidth);
    const height = Number(view && view.innerHeight);
    if (!document || typeof document.elementFromPoint !== 'function' || !view || typeof view.getComputedStyle !== 'function' || width <= 0 || height <= 0) {
      return preferredSettingsBackdropTheme(view);
    }
    const luminances = [];
    [0.2, 0.5, 0.8].forEach((xRatio) => [0.36, 0.56, 0.76].forEach((yRatio) => {
      try {
        const element = document.elementFromPoint(width * xRatio, height * yRatio);
        const luminance = element ? sampleSettingsElementLuminance(element, view) : null;
        if (luminance !== null) luminances.push(luminance);
      } catch (_) {
        // Layout can reject elementFromPoint while the page is transitioning.
      }
    }));
    if (luminances.length < 3) return preferredSettingsBackdropTheme(view);
    luminances.sort((a, b) => a - b);
    return luminances[Math.floor(luminances.length / 2)] < 0.5 ? 'dark' : 'light';
  }

  function updateSettingsBackdropTheme() {
    if (settingsDialogUi?.dialog) {
      settingsDialogUi.dialog.setAttribute('data-backdrop-theme', detectSettingsBackdropTheme());
    }
  }

  function queueSettingsWrites(entries) {
    if (!settingsStorage) {
      return Promise.reject(new Error('Userscript-manager settings storage is unavailable.'));
    }
    const write = settingsStorageWriteChain.then(async () => {
      const failures = [];
      for (const entry of entries) {
        try {
          await Promise.resolve(settingsStorage.set(entry.key, entry.value));
        } catch (error) {
          failures.push({ key: entry.key, error });
        }
      }
      if (failures.length) {
        const failedKeys = failures.map((failure) => failure.key).join(', ');
        const error = new Error(`Failed to save settings: ${failedKeys}`);
        error.failures = failures;
        throw error;
      }
    });
    settingsStorageWriteChain = write.catch(() => {});
    return write;
  }

  function settingsWriteEntries(settings) {
    return SETTINGS_DEFINITIONS.map((definition) => ({
      key: settingsStorageKey(definition.name),
      value: settings[definition.name]
    }));
  }

  function closeSettingsDialog() {
    clearSettingsRootOpen();
    if (!settingsDialogUi) return;
    settingsDialogOpen = false;
    settingsDialogDraft = null;
    settingsDialogPointerDownOutside = false;
    settingsDialogTouched = new Set();
    if (typeof settingsDialogUi.dialog.close === 'function' && settingsDialogUi.dialog.open) {
      settingsDialogUi.dialog.close();
    } else {
      settingsDialogUi.dialog.removeAttribute('open');
    }
    window.removeEventListener('keydown', settingsDialogKeydown, true);
    if (settingsDialogLastFocus && typeof settingsDialogLastFocus.focus === 'function') {
      settingsDialogLastFocus.focus();
    }
    settingsDialogLastFocus = null;
  }

  function handleSettingsDialogNativeClose(event = {}) {
    if (event.currentTarget && settingsDialogUi?.dialog !== event.currentTarget) return;
    clearSettingsRootOpen();
    settingsDialogPointerDownOutside = false;
    if (!settingsDialogOpen) return;
    settingsDialogOpen = false;
    settingsDialogDraft = null;
    settingsDialogTouched = new Set();
    window.removeEventListener('keydown', settingsDialogKeydown, true);
    if (settingsDialogLastFocus && typeof settingsDialogLastFocus.focus === 'function') {
      settingsDialogLastFocus.focus();
    }
    settingsDialogLastFocus = null;
  }

  function settingsDialogKeydown(event) {
    if (settingsDialogOpen && event.key === 'Escape') {
      event.preventDefault();
      closeSettingsDialog();
    }
  }

  function settingsDialogOutsideBounds(event) {
    const dialog = settingsDialogUi?.dialog;
    if (!settingsDialogOpen || !dialog?.open || event.target !== dialog) return false;
    const rect = dialog.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right ||
      event.clientY < rect.top || event.clientY > rect.bottom;
  }

  function settingsDialogPrimaryPointer(event) {
    return event.isPrimary !== false && (typeof event.button !== 'number' || event.button === 0);
  }

  function settingsDialogFields() {
    if (!settingsDialogUi) return {};
    return settingsDialogUi.fields;
  }

  function renderSettingsDialogDraft() {
    if (!settingsDialogUi || !settingsDialogDraft) return;
    for (const definition of SETTINGS_DEFINITIONS) {
      const field = settingsDialogFields()[definition.name];
      if (!field) continue;
      if (definition.type === 'boolean') field.checked = settingsDialogDraft[definition.name];
      else field.value = String(settingsDialogDraft[definition.name]);
    }
  }

  function readSettingsDialogDraft() {
    const draft = {};
    for (const definition of SETTINGS_DEFINITIONS) {
      const field = settingsDialogFields()[definition.name];
      const raw = definition.type === 'boolean' ? field.checked : field.value;
      draft[definition.name] = raw;
    }
    return validateSettings(draft);
  }

  function saveSettingsDialogDraft(settings, source) {
    settingsMutationGeneration += 1;
    settingsDialogDraft = copySettings(settings);
    if (!settingsStorage) {
      setSettingsDialogStatus(
        'Settings could not be saved because userscript-manager storage is unavailable. Reload will keep the current built-in values.',
        'error'
      );
      return;
    }
    setSettingsDialogStatus('Saving settings…', 'saving');
    const entries = settingsWriteEntries(settings).filter((entry) =>
      source === 'reset' ||
      !settingsProtectedKeys.has(entry.key.slice(SETTINGS_STORAGE_PREFIX.length)) ||
      settingsDialogTouched.has(entry.key.slice(SETTINGS_STORAGE_PREFIX.length))
    );
    if (!entries.length) {
      setSettingsDialogStatus(
        'No protected settings were changed. Unknown stored values were left untouched; reload to apply any saved changes.',
        'info'
      );
      return;
    }
    queueSettingsWrites(entries).then(
      () => {
        const nextSaved = copySettings(settingsLastSavedSnapshot || activeSettingsSnapshot());
        entries.forEach((entry) => {
          const name = entry.key.slice(SETTINGS_STORAGE_PREFIX.length);
          nextSaved[name] = entry.value;
          settingsProtectedKeys.delete(name);
        });
        settingsLastSavedSnapshot = nextSaved;
        settingsStorageWarning = settingsProtectedKeys.size
          ? new Error('Some protected settings remain unreadable.')
          : null;
        const savedStatus = settingsProtectedKeys.size
          ? 'Settings saved. Unknown stored values remain protected; reload will apply the saved fields only.'
          : source === 'reset'
            ? 'Defaults saved. Reload this page to apply them; active checkout state was left unchanged.'
            : 'Settings saved. Reload this page to apply them; active checkout state was left unchanged.';
        setSettingsDialogStatus(
          savedStatus,
          settingsProtectedKeys.size ? 'error' : 'saved'
        );
      },
      (error) => {
        const failedKeys = new Set(
          (error?.failures || []).map((failure) => failure.key)
        );
        const nextSaved = copySettings(settingsLastSavedSnapshot || activeSettingsSnapshot());
        entries.forEach((entry) => {
          const name = entry.key.slice(SETTINGS_STORAGE_PREFIX.length);
          if (failedKeys.has(entry.key)) return;
          nextSaved[name] = entry.value;
          settingsProtectedKeys.delete(name);
        });
        settingsLastSavedSnapshot = nextSaved;
        settingsStorageWarning = error;
        setSettingsDialogStatus(
          'Settings could not be saved completely. Active checkout state was left unchanged; fix storage and save again before reloading.',
          'error'
        );
      }
    );
  }

  function resetSettingsDialog() {
    const defaults = copySettings(DEFAULT_SETTINGS);
    settingsDialogDraft = defaults;
    renderSettingsDialogDraft();
    saveSettingsDialogDraft(defaults, 'reset');
  }

  function bindSettingsDialogUi() {
    const ui = settingsDialogUi;
    if (!ui) return;
    for (const definition of SETTINGS_DEFINITIONS) {
      const field = ui.fields[definition.name];
      field.addEventListener('input', () => settingsDialogTouched.add(definition.name));
      field.addEventListener('change', () => settingsDialogTouched.add(definition.name));
    }
    ui.save.addEventListener('click', () => {
      const result = readSettingsDialogDraft();
      if (!result.ok) {
        setSettingsDialogStatus(result.error, 'error');
        return;
      }
      saveSettingsDialogDraft(result.settings, 'save');
    });
    ui.reset.addEventListener('click', resetSettingsDialog);
    ui.close.addEventListener('click', closeSettingsDialog);
    ui.dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      closeSettingsDialog();
    });
    ui.dialog.addEventListener('submit', (event) => event.preventDefault());
    ui.dialog.addEventListener('close', handleSettingsDialogNativeClose);
    ui.dialog.addEventListener('pointerdown', (event) => {
      settingsDialogPointerDownOutside = settingsDialogPrimaryPointer(event) && settingsDialogOutsideBounds(event);
      if (settingsDialogPointerDownOutside) {
        event.preventDefault?.();
        event.stopPropagation?.();
      }
    });
    ui.dialog.addEventListener('pointercancel', () => {
      settingsDialogPointerDownOutside = false;
    });
    ui.dialog.addEventListener('click', (event) => {
      const shouldClose = settingsDialogPointerDownOutside &&
        settingsDialogPrimaryPointer(event) && settingsDialogOutsideBounds(event);
      if (settingsDialogOutsideBounds(event)) {
        event.preventDefault?.();
        event.stopPropagation?.();
      }
      settingsDialogPointerDownOutside = false;
      if (shouldClose) closeSettingsDialog();
    });
    ui.dialog.addEventListener('wheel', (event) => {
      if (settingsDialogOutsideBounds(event)) {
        event.preventDefault?.();
        event.stopPropagation?.();
      }
    }, { passive: false });
  }

  function settingsDialogMarkup() {
    return `
      <style>
        :host {
          all: initial;
          color-scheme: dark;
          --settings-panel-bg: #161b22;
          --settings-field-bg: #0d1117;
          --settings-text: #e6edf3;
          --settings-muted: #9da7b3;
          --settings-border: #484f58;
          --settings-control-border: #6e7681;
          --settings-button-bg: #21262d;
          --settings-primary-bg: #1f6feb;
          --settings-primary-border: #1f6feb;
          --settings-focus: #58a6ff;
          --settings-warning-bg: #3d2f00;
          --settings-warning-text: #ffdf70;
          --settings-warning-border: #d29922;
          --settings-error: #ff7b72;
          --settings-success: #3fb950;
          color: var(--settings-text);
          font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        @media (prefers-color-scheme: light) {
          :host {
            color-scheme: light;
            --settings-panel-bg: #fff;
            --settings-field-bg: #fff;
            --settings-text: #1f2328;
            --settings-muted: #57606a;
            --settings-border: #d0d7de;
            --settings-control-border: #8c959f;
            --settings-button-bg: #f6f8fa;
            --settings-primary-bg: #0969da;
            --settings-primary-border: #0969da;
            --settings-focus: #0969da;
            --settings-warning-bg: #fff8c5;
            --settings-warning-text: #533f03;
            --settings-warning-border: #e0a500;
            --settings-error: #82071e;
            --settings-success: #1a7f37;
          }
        }
        *, *::before, *::after { box-sizing: border-box; }
        button, input, select { color: inherit; font: inherit; }
        button { cursor: pointer; }
        dialog { width: min(560px, calc(100vw - 32px)); max-height: min(760px, calc(100vh - 32px)); margin: auto; border: 1px solid var(--settings-border); border-radius: 8px; background: var(--settings-panel-bg); color: var(--settings-text); padding: 0; }
        dialog::backdrop { background: rgb(255 255 255 / 12%); }
        dialog { box-shadow: 0 8px 32px rgb(0 0 0 / 58%); }
        @media (prefers-color-scheme: light) { dialog { box-shadow: 0 8px 32px rgb(31 35 40 / 28%); } dialog::backdrop { background: rgb(0 0 0 / 32%); } }
        dialog[data-backdrop-theme="dark"]::backdrop { background: rgb(255 255 255 / 12%); }
        dialog[data-backdrop-theme="light"]::backdrop { background: rgb(0 0 0 / 32%); }
        .panel { overflow: auto; overscroll-behavior: contain; max-height: min(760px, calc(100vh - 32px)); padding: 18px; }
        h2 { font-size: 17px; margin: 0 0 8px; }
        .warning { border: 1px solid var(--settings-warning-border); border-radius: 7px; background: var(--settings-warning-bg); color: var(--settings-warning-text); padding: 9px 10px; }
        .note { color: var(--settings-muted); font-size: 12px; }
        .field { display: grid; gap: 5px; margin: 13px 0; }
        .field label { font-weight: 600; }
        input[type="number"], select { width: 100%; border: 1px solid var(--settings-control-border); border-radius: 6px; background: var(--settings-field-bg); color: var(--settings-text); padding: 5px 7px; }
        input::placeholder { color: var(--settings-muted); opacity: 1; }
        :focus-visible { outline: 2px solid var(--settings-focus); outline-offset: 2px; }
        .check { display: flex; gap: 8px; align-items: flex-start; margin: 13px 0; }
        .status { min-height: 1.5em; margin: 14px 0 0; color: var(--settings-muted); }
        .status[data-state="error"] { color: var(--settings-error); }
        .status[data-state="saved"] { color: var(--settings-success); }
        .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
        .actions button { border: 1px solid var(--settings-border); border-radius: 6px; background: var(--settings-button-bg); color: var(--settings-text); padding: 6px 10px; }
        .actions .primary { background: var(--settings-primary-bg); border-color: var(--settings-primary-border); color: #fff; }
      </style>
      <dialog id="psprices-checkout-settings-dialog" aria-labelledby="psprices-checkout-settings-title">
        <form class="panel">
          <h2 id="psprices-checkout-settings-title">PSPrices Checkout Link settings</h2>
          <p class="warning" role="alert">${SETTINGS_WARNING}</p>
          <p class="note">Changes save for the next reload. Saving never changes active checkout state, reloads the page, clears checkout cache, or starts requests.</p>
          <div class="field"><label for="psprices-checkout-setting-LOG_LEVEL">Log level</label><select id="psprices-checkout-setting-LOG_LEVEL" name="LOG_LEVEL"><option value="info">info</option><option value="verbose">verbose</option></select></div>
          <label class="check" for="psprices-checkout-setting-SHOW_DIAGNOSTICS"><input id="psprices-checkout-setting-SHOW_DIAGNOSTICS" name="SHOW_DIAGNOSTICS" type="checkbox"> <span>Show diagnostics</span></label>
          <label class="check" for="psprices-checkout-setting-FORCE_CLIPBOARD_FALLBACK"><input id="psprices-checkout-setting-FORCE_CLIPBOARD_FALLBACK" name="FORCE_CLIPBOARD_FALLBACK" type="checkbox"> <span>Force clipboard fallback</span></label>
          <label class="check" for="psprices-checkout-setting-FORCE_MANUAL_LINK_FALLBACK"><input id="psprices-checkout-setting-FORCE_MANUAL_LINK_FALLBACK" name="FORCE_MANUAL_LINK_FALLBACK" type="checkbox"> <span>Force Manual Link fallback (takes priority)</span></label>
          <div class="field"><label for="psprices-checkout-setting-REQUEST_TIMEOUT_MS">Request timeout (ms)</label><input id="psprices-checkout-setting-REQUEST_TIMEOUT_MS" name="REQUEST_TIMEOUT_MS" type="number" min="1" max="120000" step="any" inputmode="decimal"></div>
          <div class="field"><label for="psprices-checkout-setting-CLICK_COOLDOWN_MS">Click cooldown (ms)</label><input id="psprices-checkout-setting-CLICK_COOLDOWN_MS" name="CLICK_COOLDOWN_MS" type="number" min="0" max="120000" step="any" inputmode="decimal"></div>
          <div class="field"><label for="psprices-checkout-setting-CLIPBOARD_CALLBACK_WAIT_MS">Clipboard callback wait (ms)</label><input id="psprices-checkout-setting-CLIPBOARD_CALLBACK_WAIT_MS" name="CLIPBOARD_CALLBACK_WAIT_MS" type="number" min="0" max="10000" step="any" inputmode="decimal"></div>
          <div class="field"><label for="psprices-checkout-setting-WRAPPER_ENTER_MS">Wrapper fade duration (ms)</label><input id="psprices-checkout-setting-WRAPPER_ENTER_MS" name="WRAPPER_ENTER_MS" type="number" min="0" max="10000" step="any" inputmode="decimal"></div>
          <div class="field"><label for="psprices-checkout-setting-LINKGEN_START_DELAY_MS">Link generation start delay (ms)</label><input id="psprices-checkout-setting-LINKGEN_START_DELAY_MS" name="LINKGEN_START_DELAY_MS" type="number" min="0" max="10000" step="any" inputmode="decimal"></div>
          <p class="status" role="status" aria-live="polite"></p>
          <div class="actions"><button type="button" data-settings-reset>Reset defaults</button><button type="button" data-settings-close>Close</button><button class="primary" type="button" data-settings-save>Save settings</button></div>
        </form>
      </dialog>`;
  }

  function ensureSettingsDialogMounted() {
    if (!document || typeof document.createElement !== 'function') return null;
    if (settingsDialogUi && !settingsDialogUi.host.isConnected) {
      clearSettingsRootOpen();
      settingsDialogPointerDownOutside = false;
      settingsDialogOpen = false;
      settingsDialogDraft = null;
      settingsDialogTouched = new Set();
      window.removeEventListener('keydown', settingsDialogKeydown, true);
      if (settingsDialogLastFocus && typeof settingsDialogLastFocus.focus === 'function') {
        settingsDialogLastFocus.focus();
      }
      settingsDialogLastFocus = null;
      settingsDialogUi = null;
    }
    if (!settingsDialogUi) {
      const host = document.createElement('div');
      host.id = 'psprices-checkout-settings-host';
      const shadow = typeof host.attachShadow === 'function'
        ? host.attachShadow({ mode: 'open' })
        : host;
      shadow.innerHTML = settingsDialogMarkup();
      const fields = {};
      for (const definition of SETTINGS_DEFINITIONS) {
        fields[definition.name] = shadow.querySelector(`[name="${definition.name}"]`);
      }
      settingsDialogUi = {
        host,
        shadow,
        dialog: shadow.querySelector('dialog'),
        fields,
        save: shadow.querySelector('[data-settings-save]'),
        reset: shadow.querySelector('[data-settings-reset]'),
        close: shadow.querySelector('[data-settings-close]'),
        status: shadow.querySelector('.status')
      };
      bindSettingsDialogUi();
    }
    const parent = document.body || document.documentElement;
    if (parent && settingsDialogUi.host.parentNode !== parent) parent.append(settingsDialogUi.host);
    if (settingsDialogOpen && settingsDialogUi.dialog && !settingsDialogUi.dialog.open) handleSettingsDialogNativeClose();
    if (settingsDialogOpen && settingsDialogUi.dialog?.open) markSettingsRootOpen();
    return settingsDialogUi;
  }

  function openSettingsDialog() {
    if (!settingsReady) {
      settingsDialogPending = true;
      return;
    }
    const ui = ensureSettingsDialogMounted();
    if (!ui) {
      settingsDialogPending = true;
      return;
    }
    settingsDialogPending = false;
    if (ui.dialog.open) {
      ui.close.focus();
      return;
    }
    if (!settingsDialogOpen) {
      settingsDialogLastFocus = document.activeElement;
      settingsDialogTouched = new Set();
      settingsDialogPointerDownOutside = false;
      settingsDialogDraft = copySettings(
        settingsLastSavedSnapshot || activeSettingsSnapshot()
      );
      renderSettingsDialogDraft();
    }
    if (settingsStorageWarning) {
      setSettingsDialogStatus(
        'Some settings could not be loaded or saved. Unread values remain protected; review your changes and save again.',
        'error'
      );
    } else {
      setSettingsDialogStatus('', 'info');
    }
    settingsDialogOpen = true;
    window.addEventListener('keydown', settingsDialogKeydown, true);
    updateSettingsBackdropTheme();
    try {
      if (typeof ui.dialog.showModal !== 'function') throw new Error('Native modal dialogs are unavailable.');
      ui.dialog.showModal();
    } catch (_) {
      closeSettingsDialog();
      return;
    }
    markSettingsRootOpen();
    ui.close.focus();
  }

  function registerSettingsMenu() {
    if (settingsMenuRegistered) return;
    let modern = null;
    try {
      modern = typeof GM === 'object' && GM ? GM : null;
    } catch (_) {}
    try {
      if (modern && typeof modern.registerMenuCommand === 'function') {
        const result = modern.registerMenuCommand(SETTINGS_MENU_LABEL, openSettingsDialog);
        settingsMenuRegistered = true;
        if (result && typeof result.catch === 'function') result.catch(() => {});
        return;
      }
      if (typeof GM_registerMenuCommand === 'function') {
        GM_registerMenuCommand(SETTINGS_MENU_LABEL, openSettingsDialog);
        settingsMenuRegistered = true;
      }
    } catch (_) {
      // Optional menu APIs may be unavailable or declined by the manager.
    }
  }

  async function initializeSettings() {
    settingsStorage = getSettingsStorage();
    registerSettingsMenu();
    if (!settingsStorage) {
      settingsStorageWarning = new Error('Userscript-manager settings storage is unavailable.');
      settingsLastSavedSnapshot = copySettings(DEFAULT_SETTINGS);
      return;
    }

    const readGeneration = settingsMutationGeneration;
    const results = await Promise.all(
      SETTINGS_DEFINITIONS.map((definition) => readSetting(definition, settingsStorage))
    );
    if (readGeneration !== settingsMutationGeneration) return;

    const next = copySettings(DEFAULT_SETTINGS);
    const missingEntries = [];
    results.forEach((result, index) => {
      const definition = SETTINGS_DEFINITIONS[index];
      if (result.kind === 'value') {
        next[definition.name] = result.value;
      } else if (result.kind === 'missing') {
        missingEntries.push({
          key: settingsStorageKey(definition.name),
          value: DEFAULT_SETTINGS[definition.name]
        });
      } else if (!settingsStorageWarning) {
        settingsProtectedKeys.add(definition.name);
        settingsStorageWarning = result.error || new Error('A saved setting could not be read.');
      } else {
        settingsProtectedKeys.add(definition.name);
      }
    });
    applyRuntimeSettings(next);
    settingsLastSavedSnapshot = copySettings(next);

    if (missingEntries.length && settingsMutationGeneration === readGeneration) {
      try {
        await queueSettingsWrites(missingEntries);
      } catch (error) {
        settingsStorageWarning = error;
      }
    }
  }

  function finishSettingsStartup() {
    if (settingsReady) return;
    settingsReady = true;
    refreshBootstrapStyle();
    ensureHeaderUnlockedBadge();
    startRuntime();
    if (settingsDialogPending) openSettingsDialog();
  }

  function startSettingsInitialization() {
    if (settingsStartupPromise) return settingsStartupPromise;
    settingsStartupPromise = initializeSettings().catch((error) => {
      settingsStorageWarning = error;
    }).then(() => {
      finishSettingsStartup();
    });
    return settingsStartupPromise;
  }

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

  function normalizeSonyFullSku(value, baseProductId) {
    if (typeof value !== 'string') return null;
    const fullSku = value.trim().toUpperCase();
    const expectedPrefix = `${baseProductId}-`;
    if (!fullSku.startsWith(expectedPrefix)) return null;
    const suffix = fullSku.slice(expectedPrefix.length);
    if (!SONY_SKU_SUFFIX_RE.test(suffix)) return null;
    return fullSku;
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
      if (typeof value === 'number') {
        return Number.isFinite(value) && value >= 0 ? value : null;
      }
      if (typeof value !== 'string' || !value.trim()) return null;
      const number = Number(value.trim());
      return Number.isFinite(number) && number >= 0 ? number : null;
    };
    const hasLowPrice = offers.lowPrice !== undefined;
    const hasHighPrice = offers.highPrice !== undefined;
    let lowPrice;
    let highPrice;
    if (hasLowPrice || hasHighPrice) {
      if (hasLowPrice && hasHighPrice) {
        lowPrice = parsePrice(offers.lowPrice);
        highPrice = parsePrice(offers.highPrice);
        if (lowPrice === null || highPrice === null || lowPrice > highPrice) return null;
      } else {
        const price = parsePrice(hasLowPrice ? offers.lowPrice : offers.highPrice);
        if (price === null) return null;
        lowPrice = price;
        highPrice = price;
      }
    } else {
      const price = parsePrice(offers.price);
      if (price === null) return null;
      lowPrice = price;
      highPrice = price;
    }
    const priceCurrency = String(offers.priceCurrency || '').trim().toUpperCase();
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
    const themeTargets = [...buyBlock.children].filter((element) =>
      element.matches(THEME_TARGET_SELECTOR)
    );
    if (themeTargets.length === 1) return { type: 'theme', element: themeTargets[0] };
    return {
      invalid: true,
      reason: themeTargets.length ? 'multiple-theme-targets' : 'missing-purchase-target'
    };
  }

  function isUnavailableStoreAlert(element) {
    return Boolean(
      element?.matches?.('.alert.alert-warning') &&
      element.textContent.replace(/\s+/g, ' ').trim().includes(UNAVAILABLE_STORE_TEXT)
    );
  }

  function isAvailabilityPlaceholder(element) {
    const fragmentUrl =
      element?.getAttribute?.('hx-get') ||
      element?.getAttribute?.('data-hx-get') ||
      '';
    return fragmentUrl.includes('/game/fragment/availability/');
  }

  function selectUnavailablePurchaseTarget(gameDetail) {
    if (
      activeMount?.targetType === 'unavailable' &&
      activeMount.targetElement?.isConnected &&
      gameDetail.contains(activeMount.targetElement)
    ) {
      return {
        type: 'unavailable',
        element: activeMount.targetElement,
        buyBlock: activeMount.buyBlock
      };
    }

    const targets = [
      ...gameDetail.querySelectorAll('.alert.alert-warning'),
      ...gameDetail.querySelectorAll('[hx-get*="/game/fragment/availability/"]'),
      ...gameDetail.querySelectorAll('[data-hx-get*="/game/fragment/availability/"]')
    ].filter((element, index, elements) =>
      elements.indexOf(element) === index &&
      (isUnavailableStoreAlert(element) || isAvailabilityPlaceholder(element))
    );
    if (targets.length !== 1) {
      return {
        invalid: true,
        reason: targets.length ? 'multiple-unavailable-targets' : 'missing-purchase-target'
      };
    }
    const target = targets[0];
    const container = target.parentElement;
    const unexpectedChildren = container
      ? [...container.children].filter(
        (child) => child !== target && child.id !== SKU_SCRIPT_CARD_ID
      )
      : [];
    if (
      !container ||
      unexpectedChildren.length ||
      !gameDetail.contains(container)
    ) {
      return { invalid: true, reason: 'unsupported-unavailable-target' };
    }
    return { type: 'unavailable', element: container, buyBlock: container };
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
    if (offer.highPrice === 0) return 'Free';
    const plainPrice = `${offer.priceCurrency} ${offer.highPrice}`;
    if (!intlLocale) return plainPrice;
    try {
      const formatter = new Intl.NumberFormat(intlLocale, {
        style: 'currency',
        currency: offer.priceCurrency
      });
      return formatter.format(offer.highPrice);
    } catch (_) {
      return plainPrice;
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
    if (buyBlocks.length > 1) {
      return { valid: false, reason: 'invalid-buy-block-count', route };
    }
    const metadata = readProductMetadata();
    if (!metadata.valid) return { ...metadata, route };

    let buyBlock = null;
    let target = null;
    if (buyBlocks.length === 1) {
      buyBlock = buyBlocks[0];
      target = selectPurchaseTarget(gameDetail, buyBlock);
    } else {
      target = selectUnavailablePurchaseTarget(gameDetail);
      buyBlock = target.buyBlock || null;
    }
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

  function checkoutFailureStatusMessage(category, error = null) {
    const status = error?.status;
    if (category === 'not-found') {
      return 'Not found on PSN Store.';
    }
    if (category === 'http') {
      return `PlayStation Store lookup failed with HTTP ${status || 'unknown'}.`;
    }
    if (category === 'timeout') {
      return 'PlayStation Store lookup timed out.';
    }
    if (category === 'network') {
      return 'PlayStation Store lookup failed due to a network error.';
    }
    if (category === 'empty-response') {
      return 'PlayStation Store returned an empty SKU response.';
    }
    if (category === 'malformed-json' || category === 'unexpected-json-type') {
      return 'PlayStation Store returned an unreadable SKU response.';
    }
    if (category === 'redirect') {
      return 'PlayStation Store lookup redirected unexpectedly.';
    }
    if (category === 'missing-sku') {
      return 'PlayStation Store did not return a regional SKU.';
    }
    if (category === 'unexpected-sku') {
      return 'PlayStation Store returned an unexpected regional SKU.';
    }
    if (category === 'unsupported-manager') {
      return 'Userscript manager does not support the required request API.';
    }
    return 'Checkout link unavailable.';
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
    section.className = 'game-detail-card p-4 space-y-4';

    const headingRow = document.createElement('div');
    headingRow.className = 'flex items-center justify-between gap-2';
    const headingInner = document.createElement('div');
    headingInner.className = 'space-y-1';
    headingInner.append(
      createTextElement(
        'p',
        'text-xs font-medium tracking-wider text-base-content/60 uppercase',
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
      'min-h-14 py-3 px-4';
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
      setStatus(
        mount,
        mount.terminalFailureStatus ||
          checkoutFailureStatusMessage(mount.terminalFailureCategory)
      );
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
    if (mount.targetType === 'unavailable') {
      const gameDetail = mount.targetElement.closest(
        '#game-detail.game-detail--unlockable[data-game-id]'
      );
      return Boolean(
        mount.targetElement === mount.buyBlock &&
        gameDetail?.dataset.gameId === mount.routeProductId
      );
    }
    return mount.targetElement.matches(THEME_TARGET_SELECTOR) &&
      mount.targetElement.parentElement === mount.buyBlock;
  }

  function activeCardIsIntact(mount) {
    if (!activeTargetIsOwned(mount)) return false;
    const expectedCard = [...mount.targetElement.children].find(
      (child) => child.getAttribute(OWNER_ATTR) === mount.ownerId
    );
    if (expectedCard?.dataset.testId !== CARD_TEST_ID) return false;
    if (mount.targetType === 'unavailable') {
      return [...mount.targetElement.children].every(
        (child) => child === expectedCard || child.id === SKU_SCRIPT_CARD_ID
      );
    }
    return mount.targetElement.childNodes.length === 1;
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
    mount.terminalFailureStatus = checkoutFailureStatusMessage(category, error);
    mount.fullSku = null;
    mount.checkoutUrl = null;
    if (mount.ui) {
      mount.ui.sku.textContent = 'SKU: Unavailable';
      setButtonMode(mount, 'disabled', 'Add to Cart');
      setStatus(mount, mount.terminalFailureStatus);
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
      const fullSku = normalizeSonyFullSku(rawSku, mount.baseProductId);
      if (!fullSku) {
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
    if (document.readyState === 'loading') {
      stabilizationCandidate = null;
      if (stabilizationFrame) {
        window.cancelAnimationFrame(stabilizationFrame);
        stabilizationFrame = 0;
      }
      return;
    }

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
      terminalFailureStatus: null,
      managedStickyElement: null,
      managedStickyOriginalStyle: '',
      managedStickyHadStyle: false,
      clickAttempt: null,
      popupStatus: null,
      manualLinkVisible: false,
      ui: null
    };
    try {
      const current = gatherPageContext();
      if (!sameSignature(context, current)) {
        logger.verbose('Mount cancelled because page signature changed before mutation.');
        scheduleLifecycle('mount-signature-changed');
        return;
      }
      const card = renderCard(mount);
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
    // The HTML parser may still be writing prices into children we would detach.
    if (document.readyState === 'loading') {
      stabilizationCandidate = null;
      if (stabilizationFrame) {
        window.cancelAnimationFrame(stabilizationFrame);
        stabilizationFrame = 0;
      }
      return;
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
    if (!settingsReady) {
      return;
    }
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
      (activeTarget && target.contains(activeTarget))
    );
  }

  function startRuntime() {
    if (runtimeStarted) return;
    runtimeStarted = true;
    logger.info(`has started (v${SCRIPT_VERSION})`);
    try {
      logger.verbose('Userscript manager:', GM_info?.scriptHandler || 'unknown');
    } catch (_) {
      logger.verbose('Userscript manager: unknown');
    }
    if (settingsStorageWarning) {
      logger.warn('Some saved settings were unavailable; built-in values were retained.');
    }

    const observer = new MutationObserver(() => {
      ensureHeaderUnlockedBadge();
      if (settingsDialogUi) ensureSettingsDialogMounted();
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
      if (settingsDialogPending) openSettingsDialog();
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
  }
})();
