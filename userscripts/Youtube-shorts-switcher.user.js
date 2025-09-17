// ==UserScript==
// @name         YouTube Shorts → Full Player (Action Button + Hotkey)
// @namespace    https://github.com/XxUnkn0wnxX
// @homepageURL  https://discord.gg/slayersicerealm
// @author       OpenAI
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/Youtube-shorts-switcher.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/main/userscripts/Youtube-shorts-switcher.user.js
// @version      2.8.0
// @description  Round button in the Shorts actions column + configurable hotkey to open the full player. No fallback pill or debug flags. Trusted-Types safe.
// @match        https://www.youtube.com/*
// @match        https://m.youtube.com/*
// @run-at       document-idle
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  /*** CONFIG ***/
  // Examples: 'W', 'Shift+W', 'Ctrl+Alt+W', 'Space', 'Enter', 'F2', 'ArrowRight'
  const HOTKEY = 'W';

  // ---------- URL / DOM helpers ----------
  function isShortsViewActive() {
    return !!document.querySelector('ytd-reel-player-overlay-renderer, ytd-reel-video-renderer');
  }
  function isWatchViewActive() {
    // IMPORTANT: rely on URL/canonical only; ytd-watch-flexy can exist on Shorts pages too.
    if (location.pathname === '/watch') return true;
    const canon = document.querySelector('link[rel="canonical"]')?.href || '';
    const og = document.querySelector('meta[property="og:url"]')?.content || '';
    return canon.includes('/watch') || og.includes('/watch');
  }
  function isShortsUrl() {
    try {
      if (location.pathname.startsWith('/shorts/')) return true;
      const canon = document.querySelector('link[rel="canonical"]')?.href || '';
      const og = document.querySelector('meta[property="og:url"]')?.content || '';
      return canon.includes('/shorts/') || og.includes('/shorts/');
    } catch { return false; }
  }
  function extractShortsId() {
    const from = (s) => {
      if (!s) return null;
      const i = s.indexOf('/shorts/');
      if (i === -1) return null;
      const rest = s.slice(i + 8);
      const end = rest.search(/[/?#]/);
      return end === -1 ? rest : rest.slice(0, end);
    };
    return from(location.href)
        || from(document.querySelector('link[rel="canonical"]')?.href)
        || from(document.querySelector('meta[property="og:url"]')?.content);
  }
  function buildWatchUrlFromShorts() {
    const id = extractShortsId();
    if (!id) return null;
    const u = new URL('/watch', location.origin);
    u.searchParams.set('v', id);
    return u.toString();
  }
  function redirectToWatch() {
    const dest = buildWatchUrlFromShorts();
    if (dest) location.href = dest;
  }

  // ---------- Hotkey parsing ----------
  const keyNameMap = {
    esc: 'escape', escape: 'escape',
    space: ' ', spacebar: ' ',
    enter: 'enter', return: 'enter',
    backspace: 'backspace', delete: 'delete',
    tab: 'tab',
    arrowleft: 'arrowleft', arrowright: 'arrowright',
    arrowup: 'arrowup', arrowdown: 'arrowdown',
    home: 'home', end: 'end', pageup: 'pageup', pagedown: 'pagedown'
  };
  function parseHotkey(spec) {
    const parts = String(spec).split('+').map(s => s.trim()).filter(Boolean);
    const mods = { shift: false, ctrl: false, alt: false, meta: false };
    let key = '';
    for (const raw of parts) {
      const p = raw.toLowerCase();
      if (p === 'shift') mods.shift = true;
      else if (p === 'ctrl' || p === 'control') mods.ctrl = true;
      else if (p === 'alt' || p === 'option') mods.alt = true;
      else if (p === 'meta' || p === 'cmd' || p === 'command' || p === 'win' || p === 'super') mods.meta = true;
      else key = p;
    }
    if (keyNameMap[key]) key = keyNameMap[key];
    else if (/^f\d{1,2}$/.test(key)) key = key;
    else if (key.length === 1) key = key.toLowerCase();
    else key = key.toLowerCase();
    return { key, ...mods };
  }
  const HOTKEY_CONF = parseHotkey(HOTKEY);

  function matchesHotkey(e, conf) {
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable)) return false;

    let key = (e.key || '').toLowerCase();
    if (key === ' ') key = ' ';

    return (
      key === conf.key &&
      (!!e.shiftKey === conf.shift) &&
      (!!e.ctrlKey === conf.ctrl) &&
      (!!e.altKey === conf.alt) &&
      (!!e.metaKey === conf.meta)
    );
  }

  // Capture phase so YT/extensions can’t swallow it
  window.addEventListener('keydown', (e) => {
    if (isWatchViewActive()) return;
    if (!(isShortsUrl() || isShortsViewActive())) return;
    if (matchesHotkey(e, HOTKEY_CONF)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      redirectToWatch();
    }
  }, true);

  // ---------- Column button ----------
  let colHost = null;

  function findActionsColumn() {
    const selectors = [
      'ytd-reel-player-overlay-renderer #actions',
      'ytd-reel-video-renderer #actions',
      '#actions.ytd-reel-player-overlay-renderer',
      'ytd-reel-player-overlay-renderer [id="actions"]'
    ];
    for (const s of selectors) {
      const el = document.querySelector(s);
      if (el) return el;
    }
    return null;
  }

  function makeSvgIcon() {
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '24');
    svg.setAttribute('height', '24');
    svg.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS(svgNS, 'path');
    p.setAttribute('d', 'M14 3h7v7h-2V6.41l-5.29 5.3-1.42-1.42 5.3-5.29H14V3zM5 5h7v2H7v10h10v-5h2v7H5V5z');
    svg.appendChild(p);
    return svg;
  }

  function ensureColumnButton() {
    if (!(isShortsUrl() || isShortsViewActive())) return tearDownColumnButton();
    const column = findActionsColumn();
    if (!column) return tearDownColumnButton();
    if (colHost && colHost.isConnected) return; // already mounted

    colHost = document.createElement('div');
    const shadow = colHost.attachShadow({ mode: 'open' });

    const style = document.createElement('style');
    style.textContent = `
      .btnwrap { display: flex; flex-direction: column; align-items: center; gap: 6px; margin: 6px 0; }
      .round { width: 48px; height: 48px; border-radius: 50%; display: grid; place-items: center;
               background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.12);
               color: #fff; cursor: pointer; }
      .round:hover { background: rgba(255,255,255,.14); }
      .label { font: 500 12px/1.1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
               color: #fff; opacity: .9; text-align: center; }
      svg { fill: currentColor; }
    `;

    const wrap = document.createElement('div');
    wrap.className = 'btnwrap';

    const btn = document.createElement('button');
    btn.className = 'round';
    btn.type = 'button';
    btn.title = `Open in Full Player (${HOTKEY})`;
    btn.setAttribute('aria-label', 'Open in Full Player');
    btn.addEventListener('click', redirectToWatch, { capture: true });
    btn.appendChild(makeSvgIcon());

    const lbl = document.createElement('div');
    lbl.className = 'label';
    lbl.textContent = 'Full';

    wrap.append(btn, lbl);
    shadow.append(style, wrap);

    // Put it at the top (above Like)
    column.insertBefore(colHost, column.firstChild);
  }

  function tearDownColumnButton() {
    if (colHost && colHost.isConnected) colHost.remove();
    colHost = null;
  }

  // ---------- Lifecycle ----------
  function refreshMounts() {
    if (isShortsUrl() || isShortsViewActive()) ensureColumnButton();
    else tearDownColumnButton();
  }

  const _ps = history.pushState;
  history.pushState = function (...a) { const r = _ps.apply(this, a); queueMicrotask(refreshMounts); return r; };
  const _rs = history.replaceState;
  history.replaceState = function (...a) { const r = _rs.apply(this, a); queueMicrotask(refreshMounts); return r; };
  window.addEventListener('popstate', () => queueMicrotask(refreshMounts), true);

  let lastHref = location.href;
  setInterval(() => { if (location.href !== lastHref) { lastHref = location.href; refreshMounts(); } }, 400);
  const mo = new MutationObserver(() => refreshMounts());
  mo.observe(document.documentElement, { subtree: true, childList: true });

  refreshMounts();
})();
