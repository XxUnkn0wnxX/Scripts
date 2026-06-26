// ==UserScript==
// @name         PSPrices Show Product SKU
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.1.3
// @description  Displays and copies the public PlayStation product SKU on PSPrices product pages, adding a native-style SKU panel below buy, checkout, or unavailable-store sections only when PSPrices does not already show one. Vibe coded with OpenAI.
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

  function createSkuCard(sku) {
    const card = document.createElement('div');
    card.id = CARD_ID;
    card.dataset.sku = sku;
    card.dataset.testId = 'userscript-product-sku';
    card.className =
      'rounded-[var(--game-detail-radius-card)] border border-primary/30 bg-primary/5 p-4 space-y-2';

    const heading = document.createElement('div');
    heading.className = 'text-xs text-base-content font-medium uppercase tracking-wider';
    heading.textContent = 'SKU';

    const value = document.createElement('div');
    value.className =
      'overflow-x-auto font-mono text-sm text-base-content font-semibold whitespace-nowrap select-all';
    value.textContent = sku;

    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.testId = 'userscript-product-sku-copy';
    button.className =
      'inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:text-primary/80 cursor-pointer';
    button.title = 'Copy ID to clipboard';

    const icon = document.createElement('span');
    icon.className = 'material-symbols-outlined text-base';
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

    card.append(heading, value, button);
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

  function mountSkuCard() {
    const injectedCard = document.getElementById(CARD_ID);

    if (!isProductPage()) {
      injectedCard?.remove();
      return;
    }

    // Avatar pages already provide the same native SKU card.
    if (document.querySelector('[data-test-id="avatar-sku"]')) {
      injectedCard?.remove();
      return;
    }

    const sku = readProductSku();
    if (!sku) {
      return;
    }

    const gameDetail = document.getElementById('game-detail');
    if (!gameDetail) {
      return;
    }

    const target = findMountTarget(gameDetail);
    if (!target) {
      return;
    }

    if (injectedCard?.dataset.sku === sku && injectedCard.parentElement === target.element) {
      if (target.position === 'append-spaced') {
        injectedCard.style.marginTop = '0.75rem';
      }
      return;
    }
    injectedCard?.remove();

    const card = createSkuCard(sku);

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
    subtree: true
  });

  window.addEventListener('pageshow', scheduleMount);
  window.addEventListener('popstate', scheduleMount);
  document.addEventListener('htmx:afterSwap', scheduleMount);
})();
