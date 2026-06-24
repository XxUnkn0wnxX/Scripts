// ==UserScript==
// @name         Steam Reveal Spoilers
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.1.2
// @description  Automatically reveals Steam Community spoiler text by unwrapping spoiler spans on page load and dynamic updates. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/Steam-Reveal-Spoilers.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/Steam-Reveal-Spoilers.user.js
// @match        *://steamcommunity.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==
(function(){
  const reveal = () => {
    document.querySelectorAll('span.bb_spoiler').forEach(sp => {
      const frag = document.createDocumentFragment();
      while (sp.firstChild) frag.appendChild(sp.firstChild);
      sp.replaceWith(frag);
    });
  };
  reveal();
  new MutationObserver(reveal).observe(document.body || document.documentElement, { childList: true, subtree: true });

  // SPA navigation support
  ['pushState','replaceState'].forEach(fn => {
    const orig = history[fn];
    history[fn] = function(...args){
      const res = orig.apply(this, args);
      window.dispatchEvent(new Event('locationchange'));
      return res;
    };
  });
  window.addEventListener('locationchange', () => setTimeout(reveal, 150));
  window.addEventListener('popstate', () => setTimeout(reveal, 150));
})();
