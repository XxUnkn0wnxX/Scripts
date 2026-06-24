// ==UserScript==
// @name         StackExchange Reveal All Spoilers
// @namespace    https://github.com/XxUnkn0wnxX
// @version      1.0.1.3
// @description  Automatically reveals Stack Exchange spoiler blocks by applying the site's visible spoiler class to existing and dynamically added spoilers. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/StackExchange-Reveal-Spoilers.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/StackExchange-Reveal-Spoilers.user.js
// @match        *://*.stackexchange.com/*
// @match        *://stackoverflow.com/*
// @match        *://superuser.com/*
// @match        *://serverfault.com/*
// @match        *://askubuntu.com/*
// @match        *://mathoverflow.net/*
// @match        *://stackapps.com/*
// @match        *://stackauth.com/*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

(function () {
  'use strict';

  const SELECTOR = '.spoiler:not(.is-visible)';

  function revealAll(root = document) {
    try {
      root.querySelectorAll(SELECTOR).forEach((el) => el.classList.add('is-visible'));
    } catch (_) {}
  }

  // --- Early observer (document-start): catch spoilers as they are inserted ---
  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === 'childList') {
        for (const node of m.addedNodes) {
          if (!(node instanceof Element)) continue;
          if (node.matches && node.matches(SELECTOR)) {
            node.classList.add('is-visible');
          }
          if (node.querySelectorAll) {
            node.querySelectorAll(SELECTOR).forEach((el) => el.classList.add('is-visible'));
          }
        }
      } else if (m.type === 'attributes' && m.attributeName === 'class') {
        const t = m.target;
        if (t instanceof Element && t.matches && t.matches(SELECTOR)) {
          t.classList.add('is-visible');
        }
      }
    }
  });

  try {
    mo.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class']
    });
  } catch (_) {}

  // --- Defer bulk reveal to DOM readiness to reduce flicker ---
  function onDomReady(cb) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', cb, { once: true });
    } else {
      cb();
    }
  }

  onDomReady(() => {
    // Ensure styles are applied before flipping classes
    setTimeout(() => revealAll(), 0);
  });

  // Handle bfcache restores or SPA-like transitions
  window.addEventListener('pageshow', () => revealAll());

  // Optional: if the site swaps content after load, do a light pass
  window.addEventListener('load', () => revealAll());
})();
