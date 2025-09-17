// ==UserScript==
// @name         Steam Reveal Spoilers
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.0
// @description  Reveal hidden spoilers by unwrapping span.bb_spoiler elements on Steam community pages.
// @author       OpenAI
// @match        *://steamcommunity.com/*
// @homepageURL  https://discord.gg/slayersicerealm
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/Steam-Reveal-Spoilers.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/Steam-Reveal-Spoilers.user.js
// @grant        none
// @run-at       document-idle
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
