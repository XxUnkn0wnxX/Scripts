// ==UserScript==
// @name         PSPrices Show Product SKU
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.1.5
// @description  Displays and copies the public PlayStation product SKU on PSPrices product pages, with Avatar SKU, Theme SKU, or generic SKU labels and matching helper text in a native-style panel below buy, checkout, or unavailable-store sections. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/PSPrices-Show-Product-SKU.user.js
// @match        https://psprices.com/region-*/game/*
// @match        https://www.psprices.com/region-*/game/*
// @run-at       document-idle
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const CARD_ID = 'psprices-product-sku-userscript';
  const NATIVE_SKU_HIDE_ATTR = 'data-psprices-sku-native-hidden';
  const NATIVE_SKU_HIDE_STYLE_ID = 'psprices-sku-native-hide-style';
  const NATIVE_SKU_PANEL_SELECTOR = 'section[data-test-id="avatar-sku-panel"]';
  const NATIVE_SKU_LOCKED_SELECTOR = '[data-test-id="avatar-sku-locked"]';
  const NATIVE_SKU_UNLOCKED_SELECTOR = '[data-test-id="avatar-sku"]';
  const UNAVAILABLE_STORE_TEXT =
    'This item is no longer available for purchase on the PlayStation Store';
  const PRODUCT_PATH = /^\/region-[a-z0-9-]+\/game\/\d+(?:\/[^/]+)?\/?$/i;
  let mountScheduled = false;

  function isProductPage() {
    return PRODUCT_PATH.test(window.location.pathname);
  }

  function hasProductType(type) {
    if (Array.isArray(type)) {
      return type.some(hasProductType);
    }
    return String(type || '').toLowerCase() === 'product';
  }

  function findProductSku(value) {
    if (Array.isArray(value)) {
      for (const entry of value) {
        const sku = findProductSku(entry);
        if (sku) return sku;
      }
      return null;
    }

    if (!value || typeof value !== 'object') {
      return null;
    }

    if (hasProductType(value['@type']) && typeof value.sku === 'string') {
      const sku = value.sku.trim();
      if (sku) return sku;
    }

    if (value['@graph']) {
      return findProductSku(value['@graph']);
    }

    return null;
  }

  function readProductSku() {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');

    for (const script of scripts) {
      try {
        const sku = findProductSku(JSON.parse(script.textContent || ''));
        if (sku) return sku;
      } catch (_) {
        // Ignore unrelated or malformed structured-data blocks.
      }
    }

    return null;
  }

  function readNativeUnlockedSku(gameDetail) {
    for (const panel of gameDetail.querySelectorAll(NATIVE_SKU_PANEL_SELECTOR)) {
      const sku = panel.querySelector(NATIVE_SKU_UNLOCKED_SELECTOR)?.textContent.trim();
      if (sku && !/[•*…]/u.test(sku) && !/\.{2,}/.test(sku)) return sku;
    }

    return null;
  }

  function readSkuLabel(gameDetail) {
    const labels = new Set();
    // Only the product's category badge identifies its kind; navigation and
    // related products can link to both collections on the same page.
    for (const link of gameDetail.querySelectorAll('#platform-badges a[href]')) {
      try {
        const pathname = new URL(link.getAttribute('href'), window.location.href).pathname;
        const category = pathname.match(
          /^\/region-[a-z0-9-]+\/collection\/(avatars|themes)\/?$/i
        )?.[1].toLowerCase();
        if (category === 'avatars') labels.add('Avatar SKU');
        if (category === 'themes') labels.add('Theme SKU');
      } catch (_) {
        // Ignore malformed category links and keep the generic fallback.
      }
    }
    return labels.size === 1 ? [...labels][0] : 'SKU';
  }

  function copyWithFallback(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();

    let copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (_) {}

    textarea.remove();
    return copied;
  }

  async function copySku(sku) {
    try {
      await navigator.clipboard.writeText(sku);
      return true;
    } catch (_) {
      return copyWithFallback(sku);
    }
  }

  function createSkuCard(sku, label) {
    const card = document.createElement('div');
    card.id = CARD_ID;
    card.dataset.sku = sku;
    card.dataset.skuLabel = label;
    card.dataset.testId = 'userscript-product-sku';
    card.className =
      'game-detail-card border-primary/30 bg-primary/5 grid gap-3 p-4 ' +
      'sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-5';
    // Keep the blue accent above the native card's light/dark border rule.
    card.style.borderColor = 'color-mix(in oklab, var(--color-primary) 30%, transparent)';

    const content = document.createElement('div');
    content.className = 'min-w-0 space-y-1.5';

    const heading = document.createElement('h3');
    heading.className = 'flex items-center gap-2 text-sm font-semibold text-base-content';
    const headingIcon = document.createElement('span');
    headingIcon.className = 'material-symbols-outlined text-lg text-base-content/55';
    headingIcon.setAttribute('aria-hidden', 'true');
    headingIcon.textContent = 'code';
    heading.append(headingIcon, document.createTextNode(label));

    const value = document.createElement('code');
    value.className =
      'block max-w-full overflow-x-auto font-mono text-sm font-semibold whitespace-nowrap text-base-content select-all';
    value.textContent = sku;

    const description = document.createElement('p');
    description.className = 'text-xs leading-relaxed text-base-content/60';
    description.textContent = `${label} identifier for third-party utilities.`;
    content.append(heading, value, description);

    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.testId = 'userscript-product-sku-copy';
    button.className = 'btn min-h-11 w-full gap-2 btn-outline sm:w-auto';
    button.title = 'Copy ID to clipboard';

    const icon = document.createElement('span');
    icon.className = 'material-symbols-outlined text-lg';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = 'content_copy';

    const buttonText = document.createElement('span');
    buttonText.className = 'copy-text';
    buttonText.textContent = 'Copy SKU';

    button.append(icon, buttonText);
    button.addEventListener('click', async () => {
      const copied = await copySku(sku);
      icon.textContent = copied ? 'check' : 'error';
      buttonText.textContent = copied ? 'Copied' : 'Copy failed';

      window.setTimeout(() => {
        icon.textContent = 'content_copy';
        buttonText.textContent = 'Copy SKU';
      }, 1000);
    });

    card.append(content, button);
    return card;
  }

  function isUnavailableStoreAlert(element) {
    return Boolean(
      element?.matches?.('.alert.alert-warning') &&
      element.textContent.replace(/\s+/g, ' ').trim().includes(UNAVAILABLE_STORE_TEXT)
    );
  }

  function findUnavailableMountTarget(gameDetail) {
    const checkoutCard = gameDetail.querySelector(
      '[data-test-id="psprices-checkout-card"][data-psprices-checkout-target="unavailable"]'
    );
    if (checkoutCard?.parentElement) {
      return { element: checkoutCard.parentElement, position: 'append-spaced' };
    }

    const alert = [...gameDetail.querySelectorAll('.alert.alert-warning')].find(
      isUnavailableStoreAlert
    );
    if (alert?.parentElement) {
      return { element: alert.parentElement, position: 'append-spaced' };
    }

    return null;
  }

  function findMountTarget(gameDetail) {
    const avatarBuyBlock = gameDetail.querySelector('[data-avatar-buy-block]');
    if (avatarBuyBlock) {
      return { element: avatarBuyBlock, position: 'append' };
    }

    const unavailableTarget = findUnavailableMountTarget(gameDetail);
    if (unavailableTarget) {
      return unavailableTarget;
    }

    const gameActions = gameDetail.querySelector('.game-detail-actions');
    if (gameActions) {
      return { element: gameActions, position: 'prepend-spaced' };
    }

    const hero = gameDetail.querySelector('[data-test-id="game-detail-hero"]');
    if (hero) {
      return { element: hero, position: 'after-spaced' };
    }

    return null;
  }

  function ensureNativeSkuHideStyle() {
    if (document.getElementById(NATIVE_SKU_HIDE_STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = NATIVE_SKU_HIDE_STYLE_ID;
    style.textContent = `#game-detail ${NATIVE_SKU_PANEL_SELECTOR}[${NATIVE_SKU_HIDE_ATTR}="true"] { display: none !important; }`;
    (document.head || document.documentElement).append(style);
  }

  function restoreOwnedNativeSkuPanels(keepPanels = null) {
    document.querySelectorAll(`[${NATIVE_SKU_HIDE_ATTR}="true"]`).forEach((panel) => {
      if (!keepPanels || !keepPanels.has(panel)) {
        panel.removeAttribute(NATIVE_SKU_HIDE_ATTR);
      }
    });
  }

  function isNativeSkuPanelToReplace(panel, gameDetail, injectedCard) {
    return Boolean(
      panel &&
      panel.matches?.(NATIVE_SKU_PANEL_SELECTOR) &&
      panel.closest('#game-detail') === gameDetail &&
      (!injectedCard || !panel.contains(injectedCard)) &&
      (panel.querySelector(NATIVE_SKU_LOCKED_SELECTOR) ||
        panel.querySelector(NATIVE_SKU_UNLOCKED_SELECTOR))
    );
  }

  function hideNativeSkuPanels(gameDetail, injectedCard) {
    if (!gameDetail || !injectedCard?.isConnected || injectedCard.closest('#game-detail') !== gameDetail) {
      restoreOwnedNativeSkuPanels();
      return;
    }

    const panels = Array.from(gameDetail.querySelectorAll(NATIVE_SKU_PANEL_SELECTOR));
    const panelsToReplace = panels.filter((panel) =>
      isNativeSkuPanelToReplace(panel, gameDetail, injectedCard)
    );
    if (panelsToReplace.length === 0) {
      restoreOwnedNativeSkuPanels();
      return;
    }

    ensureNativeSkuHideStyle();
    const keepPanels = new Set(panelsToReplace);
    restoreOwnedNativeSkuPanels(keepPanels);
    panelsToReplace.forEach((panel) => {
      if (panel.getAttribute(NATIVE_SKU_HIDE_ATTR) !== 'true') {
        panel.setAttribute(NATIVE_SKU_HIDE_ATTR, 'true');
      }
    });
  }

  function mountSkuCard() {
    const injectedCard = document.getElementById(CARD_ID);

    if (!isProductPage()) {
      injectedCard?.remove();
      restoreOwnedNativeSkuPanels();
      return;
    }

    const gameDetail = document.getElementById('game-detail');
    if (!gameDetail) {
      injectedCard?.remove();
      restoreOwnedNativeSkuPanels();
      return;
    }

    // Prefer public structured data, with the visible native SKU as a fallback
    // when PSPrices has not exposed JSON-LD for an unlocked panel.
    const sku = readProductSku() || readNativeUnlockedSku(gameDetail);
    if (!sku) {
      injectedCard?.remove();
      restoreOwnedNativeSkuPanels();
      return;
    }

    const target = findMountTarget(gameDetail);
    if (!target) {
      injectedCard?.remove();
      restoreOwnedNativeSkuPanels();
      return;
    }

    const label = readSkuLabel(gameDetail);
    const isRetainedCard =
      injectedCard?.dataset.sku === sku &&
      injectedCard.dataset.skuLabel === label &&
      (target.position === 'after-spaced'
        ? target.element.nextElementSibling === injectedCard
        : injectedCard.parentElement === target.element);
    if (isRetainedCard) {
      if (target.position === 'append-spaced') {
        injectedCard.style.marginTop = '0.75rem';
      }
      hideNativeSkuPanels(gameDetail, injectedCard);
      return;
    }
    injectedCard?.remove();

    const card = createSkuCard(sku, label);

    if (target.position === 'append') {
      target.element.append(card);
    } else if (target.position === 'append-spaced') {
      card.style.marginTop = '0.75rem';
      target.element.append(card);
    } else if (target.position === 'prepend-spaced') {
      card.style.marginBottom = '0.75rem';
      target.element.prepend(card);
    } else {
      card.style.margin = '0 1rem 1.5rem';
      target.element.insertAdjacentElement('afterend', card);
    }

    if (card.isConnected && card.closest('#game-detail') === gameDetail) {
      hideNativeSkuPanels(gameDetail, card);
    } else {
      card.remove();
      restoreOwnedNativeSkuPanels();
    }
  }

  function scheduleMount() {
    if (mountScheduled) return;
    mountScheduled = true;

    window.requestAnimationFrame(() => {
      mountScheduled = false;
      mountSkuCard();
    });
  }

  scheduleMount();

  const observer = new MutationObserver(scheduleMount);
  observer.observe(document.documentElement, {
    childList: true,
    attributes: true,
    attributeFilter: ['href'],
    subtree: true
  });

  window.addEventListener('pageshow', scheduleMount);
  window.addEventListener('popstate', scheduleMount);
  document.addEventListener('htmx:afterSwap', scheduleMount);
})();
