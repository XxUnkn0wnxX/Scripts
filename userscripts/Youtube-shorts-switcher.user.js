// ==UserScript==
// @name         YouTube Shorts → Full Player (Action Button + Hotkey)
// @namespace    https://github.com/XxUnkn0wnxX
// @version      2.9.2
// @description  Adds a Shorts action-column button and configurable hotkey that open the current YouTube Short in the normal watch player. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Youtube-shorts-switcher.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/Youtube-shorts-switcher.user.js
// @match        https://www.youtube.com/*
// @match        https://m.youtube.com/*
// @run-at       document-idle
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM.getValue
// @grant        GM.setValue
// @grant        GM.registerMenuCommand
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const INSTANCE_FLAG = '__youtubeShortsSwitcherInstalled';
  const SETTINGS_SCHEMA_VERSION = 1;
  const SETTINGS_KEYS = Object.freeze({
    hotkey: 'youtube-shorts-switcher.hotkey',
    schemaVersion: 'youtube-shorts-switcher.schemaVersion',
  });

  /*** CONFIG ***/
  // This remains the source default, so changing it in a future release only
  // changes the Reset defaults value; a saved manager value still wins.
  const HOTKEY = 'W';

  if (window[INSTANCE_FLAG]) return;
  window[INSTANCE_FLAG] = true;

  let currentHotkey = 'W';
  let colHost = null;
  let colButton = null;
  let settingsController = null;

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

  function composedPath(event) {
    if (event && typeof event.composedPath === 'function') return event.composedPath();
    return event && event.target ? [event.target] : [];
  }

  function isEditableEventTarget(event) {
    return composedPath(event).some((node) => {
      if (!node || node.nodeType !== 1) return false;
      const tag = String(node.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
      if (node.isContentEditable === true) return true;
      const editable = typeof node.getAttribute === 'function'
        ? node.getAttribute('contenteditable')
        : null;
      return editable !== null && String(editable).toLowerCase() !== 'false';
    });
  }

  function patchHistoryMethod(historyObject, name) {
    if (!historyObject) return false;
    const original = historyObject[name];
    if (typeof original !== 'function') return false;
    const patched = function (...args) {
      const result = original.apply(this, args);
      queueMicrotask(refreshMounts);
      return result;
    };
    try {
      historyObject[name] = patched;
      return historyObject[name] === patched;
    } catch (_) {
      // Some pages expose a non-writable history method. Leave it untouched.
      return false;
    }
  }

  // ---------- Hotkey parsing / matching ----------
  const keyNameMap = Object.freeze({
    esc: 'escape', escape: 'escape',
    space: ' ', spacebar: ' ',
    enter: 'enter', return: 'enter',
    backspace: 'backspace', delete: 'delete',
    tab: 'tab',
    arrowleft: 'arrowleft', arrowright: 'arrowright',
    arrowup: 'arrowup', arrowdown: 'arrowdown',
    home: 'home', end: 'end', pageup: 'pageup', pagedown: 'pagedown',
    plus: '+',
  });

  const displayKeyMap = Object.freeze({
    ' ': 'Space',
    '+': 'Plus',
    escape: 'Escape',
    enter: 'Enter',
    backspace: 'Backspace',
    delete: 'Delete',
    tab: 'Tab',
    arrowleft: 'ArrowLeft', arrowright: 'ArrowRight',
    arrowup: 'ArrowUp', arrowdown: 'ArrowDown',
    home: 'Home', end: 'End', pageup: 'PageUp', pagedown: 'PageDown',
  });

  const modifierKeys = new Set(['shift', 'control', 'ctrl', 'alt', 'option', 'meta', 'cmd', 'command', 'win', 'super', 'os', 'altgraph']);

  function normalizeKey(key) {
    const value = String(key == null ? '' : key);
    if (value === ' ') return ' ';
    const raw = value.trim();
    if (raw === '+') return '+';
    const lower = raw.toLowerCase();
    if (keyNameMap[lower]) return keyNameMap[lower];
    return raw.length === 1 ? raw.toLowerCase() : lower;
  }

  function parseHotkey(spec) {
    const source = String(spec == null ? '' : spec).trim();
    const parts = source === '+' ? ['+'] : source.split('+');
    const mods = {shift: false, ctrl: false, alt: false, meta: false};
    let key = '';
    parts.forEach((raw, index) => {
      const trimmed = raw.trim();
      if (!trimmed) {
        // A trailing empty token is the safe textual form of a literal '+',
        // e.g. Ctrl++ or Ctrl+Shift++.
        if (source && index === parts.length - 1) key = '+';
        return;
      }
      const p = trimmed.toLowerCase();
      if (p === 'shift') mods.shift = true;
      else if (p === 'ctrl' || p === 'control') mods.ctrl = true;
      else if (p === 'alt' || p === 'option') mods.alt = true;
      else if (p === 'meta' || p === 'cmd' || p === 'command' || p === 'win' || p === 'super') mods.meta = true;
      else key = normalizeKey(trimmed);
    });
    return {key, ...mods};
  }

  function isUsableHotkey(conf) {
    return !!conf && typeof conf.key === 'string' && conf.key.length > 0 && !modifierKeys.has(conf.key);
  }

  function formatHotkey(conf) {
    if (!isUsableHotkey(conf)) return null;
    const labels = [];
    if (conf.ctrl) labels.push('Ctrl');
    if (conf.alt) labels.push('Alt');
    if (conf.shift) labels.push('Shift');
    if (conf.meta) labels.push('Cmd');
    let key = displayKeyMap[conf.key];
    if (!key) key = /^f\d{1,2}$/.test(conf.key) ? conf.key.toUpperCase() : conf.key.length === 1 ? conf.key.toUpperCase() : conf.key;
    return labels.concat(key).join('+');
  }

  function canonicalHotkey(spec) {
    return formatHotkey(typeof spec === 'object' && spec ? spec : parseHotkey(spec));
  }

  const DEFAULT_HOTKEY = canonicalHotkey(HOTKEY) || 'W';
  currentHotkey = DEFAULT_HOTKEY;

  function eventKey(event) {
    const key = normalizeKey(event && event.key);
    return key === 'dead' || key === 'unidentified' || key === 'process' || key === 'compose' ? '' : key;
  }

  function matchesHotkey(event, conf) {
    if (event.isComposing || !isUsableHotkey(conf) || isEditableEventTarget(event)) return false;
    return eventKey(event) === conf.key
      && (!!event.shiftKey === conf.shift)
      && (!!event.ctrlKey === conf.ctrl)
      && (!!event.altKey === conf.alt)
      && (!!event.metaKey === conf.meta);
  }

  function recordingHotkey(event) {
    const key = eventKey(event);
    if (!key || modifierKeys.has(key) || event.repeat || event.isComposing) return null;
    const conf = {
      key,
      shift: !!event.shiftKey,
      ctrl: !!event.ctrlKey,
      alt: !!event.altKey,
      meta: !!event.metaKey,
    };
    return isUsableHotkey(conf) ? canonicalHotkey(conf) : null;
  }

  // ---------- Column button ----------
  function findActionsColumn() {
    const selectors = [
      '.ytReelPlayerOverlayViewModelActionsContainer reel-action-bar-view-model',
      'yt-reel-player-overlay-view-model reel-action-bar-view-model',
      'reel-action-bar-view-model.ytwReelActionBarViewModelHost',
      '.ytReelPlayerOverlayViewModelActionsContainer',
      'ytd-reel-player-overlay-renderer #actions',
      'ytd-reel-video-renderer #actions',
      '#actions.ytd-reel-player-overlay-renderer',
      'ytd-reel-player-overlay-renderer [id="actions"]',
    ];
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element) return element;
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
    const path = document.createElementNS(svgNS, 'path');
    path.setAttribute('d', 'M14 3h7v7h-2V6.41l-5.29 5.3-1.42-1.42 5.3-5.29H14V3zM5 5h7v2H7v10h10v-5h2v7H5V5z');
    svg.appendChild(path);
    return svg;
  }

  function updateColumnButtonTooltip() {
    if (!colButton) return;
    colButton.title = `Open in Full Player (${currentHotkey})`;
    colButton.setAttribute('aria-label', `Open in Full Player (${currentHotkey})`);
  }

  function ensureColumnButton() {
    if (!(isShortsUrl() || isShortsViewActive())) return tearDownColumnButton();
    const column = findActionsColumn();
    if (!column) return tearDownColumnButton();
    if (colHost && colHost.isConnected) {
      if (colHost.parentNode === column) {
        updateColumnButtonTooltip();
        return;
      }
      colHost.remove();
    }

    colHost = document.createElement('div');
    colHost.className = 'ytwReelActionBarViewModelHostDesktopActionButton';
    const shadow = colHost.attachShadow({mode: 'open'});
    const style = document.createElement('style');
    style.textContent = `
      :host { display: block; }
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
    colButton = document.createElement('button');
    colButton.className = 'round';
    colButton.type = 'button';
    colButton.addEventListener('click', redirectToWatch, {capture: true});
    colButton.appendChild(makeSvgIcon());
    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = 'Full';
    wrap.append(colButton, label);
    shadow.append(style, wrap);
    updateColumnButtonTooltip();
    column.insertBefore(colHost, column.firstChild);
  }

  function tearDownColumnButton() {
    if (colHost && colHost.isConnected) colHost.remove();
    colHost = null;
    colButton = null;
  }

  // ---------- Settings ----------
  function findSettingsStorage(runtime) {
    const gm = runtime && runtime.GM;
    if (gm && typeof gm.getValue === 'function' && typeof gm.setValue === 'function') {
      return {
        get: (key) => gm.getValue(key),
        set: (key, value) => gm.setValue(key, value),
      };
    }
    const legacyGet = runtime && runtime.GM_getValue;
    const legacySet = runtime && runtime.GM_setValue;
    if (typeof legacyGet === 'function' && typeof legacySet === 'function') {
      return {
        get: (key) => legacyGet.call(runtime, key),
        set: (key, value) => legacySet.call(runtime, key, value),
      };
    }
    return null;
  }

  function createSettingsController(options = {}) {
    const runtime = options.runtime || window;
    const settingsDocument = options.document || document;
    const defaultHotkey = canonicalHotkey(options.defaultHotkey || DEFAULT_HOTKEY) || DEFAULT_HOTKEY;
    const setTimeoutFn = typeof runtime.setTimeout === 'function'
      ? (callback, delay) => window.setTimeout(callback, delay)
      : setTimeout;
    const clearTimeoutFn = typeof runtime.clearTimeout === 'function'
      ? (timer) => window.clearTimeout(timer)
      : clearTimeout;
    const storage = findSettingsStorage(runtime);
    const ROOT_LOCK_ATTRIBUTE = 'data-youtube-shorts-switcher-settings-open';
    const ROOT_LOCK_STYLE_ID = 'youtube-shorts-switcher-settings-lock-style';
    const BACKDROP_THEME_ATTRIBUTE = 'data-backdrop-theme';
    let storageState = storage ? 'loading' : 'unavailable';
    let storageError = null;
    let current = defaultHotkey;
    let initializePromise = null;
    let saveTimer = null;
    let writeChain = Promise.resolve();
    let ui = null;
    let lastFocus = null;
    let menuRegistered = false;
    let menuRegistrationPromise = null;
    let bindingVersion = 0;
    let pendingBinding = false;
    let bindingReadable = false;
    let pointerDownOutside = false;
    let rootLockStyle = null;

    function ensureRootLockStyle() {
      if (!settingsDocument || typeof settingsDocument.createElement !== 'function') return;
      if (rootLockStyle && rootLockStyle.isConnected) return;
      const parent = settingsDocument.head || settingsDocument.documentElement;
      if (!parent) return;
      let style = typeof settingsDocument.getElementById === 'function'
        ? settingsDocument.getElementById(ROOT_LOCK_STYLE_ID)
        : null;
      if (!style && typeof settingsDocument.querySelector === 'function') {
        style = settingsDocument.querySelector(`#${ROOT_LOCK_STYLE_ID}`);
      }
      if (!style) {
        style = settingsDocument.createElement('style');
        style.id = ROOT_LOCK_STYLE_ID;
        style.textContent = `
          :root[${ROOT_LOCK_ATTRIBUTE}] { scrollbar-gutter: stable !important; overflow: hidden !important; overscroll-behavior: none !important; }
          :root[${ROOT_LOCK_ATTRIBUTE}] body { overflow: hidden !important; overscroll-behavior: none !important; }
        `;
        parent.appendChild(style);
      }
      rootLockStyle = style;
    }

    function setRootLock(locked) {
      const root = settingsDocument && settingsDocument.documentElement;
      if (!root || typeof root.setAttribute !== 'function' || typeof root.removeAttribute !== 'function') return;
      if (locked) {
        ensureRootLockStyle();
        root.setAttribute(ROOT_LOCK_ATTRIBUTE, '');
      } else {
        root.removeAttribute(ROOT_LOCK_ATTRIBUTE);
      }
    }

    function parseCssColor(value) {
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

    function relativeLuminance(color) {
      const channel = (value) => {
        const normalized = value / 255;
        return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
      };
      return channel(color[0]) * 0.2126 + channel(color[1]) * 0.7152 + channel(color[2]) * 0.0722;
    }

    function sampleElementLuminance(element, view) {
      let composite = null;
      let node = element;
      while (node && node.nodeType === 1) {
        let computed;
        try {
          computed = view.getComputedStyle(node);
        } catch (_) {
          computed = null;
        }
        const opacity = computed ? Math.max(0, Math.min(1, Number(computed.opacity || 1))) : 0;
        if (computed && computed.display !== 'none' && computed.visibility !== 'hidden' && opacity > 0) {
          const color = parseCssColor(computed.backgroundColor);
          if (color) {
            color[3] *= opacity;
            if (!composite) composite = color;
            else {
              const front = composite;
              const back = color;
              const alpha = front[3] + back[3] * (1 - front[3]);
              composite = [
                (front[0] * front[3] + back[0] * back[3] * (1 - front[3])) / (alpha || 1),
                (front[1] * front[3] + back[1] * back[3] * (1 - front[3])) / (alpha || 1),
                (front[2] * front[3] + back[2] * back[3] * (1 - front[3])) / (alpha || 1),
                alpha,
              ];
            }
            if (composite[3] >= 0.96) return relativeLuminance(composite);
          }
        }
        if (node === settingsDocument.documentElement) break;
        node = node.parentNode;
      }
      return composite && composite[3] >= 0.96 ? relativeLuminance(composite) : null;
    }

    function preferredBackdropTheme(view) {
      try {
        return view && typeof view.matchMedia === 'function' && view.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
      } catch (_) {
        return 'dark';
      }
    }

    function detectBackdropTheme() {
      const view = settingsDocument.defaultView || runtime.window || runtime;
      const width = Number(view && view.innerWidth);
      const height = Number(view && view.innerHeight);
      if (!settingsDocument || typeof settingsDocument.elementFromPoint !== 'function' || !view || typeof view.getComputedStyle !== 'function' || width <= 0 || height <= 0) {
        return preferredBackdropTheme(view);
      }
      const luminances = [];
      [0.2, 0.5, 0.8].forEach((xRatio) => [0.36, 0.56, 0.76].forEach((yRatio) => {
        try {
          const element = settingsDocument.elementFromPoint(width * xRatio, height * yRatio);
          const luminance = element ? sampleElementLuminance(element, view) : null;
          if (luminance !== null) luminances.push(luminance);
        } catch (_) {
          // A page can reject elementFromPoint while it is transitioning layouts.
        }
      }));
      if (luminances.length < 3) return preferredBackdropTheme(view);
      luminances.sort((a, b) => a - b);
      return luminances[Math.floor(luminances.length / 2)] < 0.5 ? 'dark' : 'light';
    }

    function updateBackdropTheme() {
      if (ui && ui.dialog) ui.dialog.setAttribute(BACKDROP_THEME_ATTRIBUTE, detectBackdropTheme());
    }

    function statusText(state) {
      if (state === 'loading') return 'Loading saved settings…';
      if (state === 'ready') return 'Saved in your userscript manager.';
      if (state === 'saving') return 'Saving…';
      if (state === 'read-error') return 'Saved values could not be read; unknown values were left untouched.';
      if (state === 'write-error') return 'Changes apply on this page, but saving failed.';
      return 'Page-only controls: manager storage is unavailable.';
    }

    function setStatus(state, message) {
      storageState = state;
      storageError = message || null;
      if (ui && ui.status) {
        ui.status.textContent = message || statusText(state);
        ui.status.dataset.state = state;
      }
    }

    function notify(source) {
      currentHotkey = current;
      updateColumnButtonTooltip();
      try {
        if (typeof options.onChange === 'function') options.onChange(current, {source, storageState});
      } catch (error) {
        setStatus('write-error', `The page updated, but its hotkey callback failed: ${error.message || error}`);
      }
      renderSettings();
    }

    function markUserChange() {
      bindingVersion += 1;
      pendingBinding = true;
      // An explicit edit is authorization to save this field even if an older
      // manager read failed. A failed read alone never writes the field.
      bindingReadable = true;
    }

    function setBinding(value, source = 'record') {
      const next = canonicalHotkey(value);
      if (!next) return current;
      if (next === current && source !== 'reset') return current;
      current = next;
      markUserChange();
      notify(source);
      scheduleSave();
      return current;
    }

    function scheduleSave() {
      if (!storage || !setTimeoutFn) return;
      if (saveTimer !== null) clearTimeoutFn(saveTimer);
      saveTimer = setTimeoutFn(() => {
        saveTimer = null;
        flush().catch(() => {});
      }, 120);
    }

    function performWrite(value, version) {
      if (!storage || !pendingBinding || !bindingReadable) return Promise.resolve();
      setStatus('saving');
      return Promise.resolve().then(() => storage.set(SETTINGS_KEYS.hotkey, value)).then(() => {
        if (bindingVersion === version) pendingBinding = false;
        setStatus('ready');
      }).catch((error) => {
        storageError = error;
        setStatus('write-error', 'Changes apply on this page, but saving failed.');
      });
    }

    function flush() {
      if (!storage || !pendingBinding || !bindingReadable) return writeChain;
      const value = current;
      const version = bindingVersion;
      writeChain = writeChain.then(() => performWrite(value, version));
      return writeChain;
    }

    function queueMissing(entries) {
      if (!storage || entries.length === 0) return writeChain;
      writeChain = writeChain.then(async () => {
        let failed = false;
        setStatus('saving');
        for (const entry of entries) {
          if (entry.key === SETTINGS_KEYS.hotkey && bindingVersion !== entry.version) continue;
          try {
            await Promise.resolve(storage.set(entry.key, entry.value));
          } catch (error) {
            failed = true;
            storageError = error;
          }
        }
        setStatus(failed ? 'write-error' : 'ready', failed
          ? 'The page works, but default settings could not be saved.'
          : 'Saved in your userscript manager.');
      });
      return writeChain;
    }

    async function initialize() {
      if (initializePromise) return initializePromise;
      initializePromise = (async () => {
        registerMenu();
        try {
          ensureMounted();
        } catch (error) {
          // Layout setup is optional; manager storage and the menu must still initialize.
          if (typeof console !== 'undefined' && typeof console.warn === 'function') {
            console.warn('[YouTube Shorts Switcher] Settings UI could not be mounted.', error);
          }
        }
        if (!storage) {
          setStatus('unavailable');
          notify('defaults');
          return current;
        }

        const readVersion = bindingVersion;
        let saved;
        let schema;
        let bindingReadFailed = false;
        let schemaReadFailed = false;
        try {
          saved = await Promise.resolve(storage.get(SETTINGS_KEYS.hotkey));
          bindingReadable = true;
        } catch (error) {
          bindingReadFailed = true;
          storageError = error;
        }
        try {
          schema = await Promise.resolve(storage.get(SETTINGS_KEYS.schemaVersion));
        } catch (error) {
          schemaReadFailed = true;
          storageError = error;
        }

        if (!bindingReadFailed && bindingVersion === readVersion && saved !== undefined) {
          const loaded = canonicalHotkey(saved);
          if (loaded) current = loaded;
        }
        notify('load');

        const missing = [];
        if (!bindingReadFailed && saved === undefined) {
          missing.push({key: SETTINGS_KEYS.hotkey, value: current, version: bindingVersion});
        }
        if (!schemaReadFailed && schema === undefined) {
          missing.push({key: SETTINGS_KEYS.schemaVersion, value: SETTINGS_SCHEMA_VERSION, version: bindingVersion});
        }
        if (missing.length) await queueMissing(missing);
        if (bindingReadFailed || schemaReadFailed) {
          setStatus('read-error');
          renderSettings();
        } else if (!missing.length) {
          setStatus('ready');
          renderSettings();
        }
        return current;
      })();
      return initializePromise;
    }

    function resetDefaults() {
      if (ui && ui.recording) cancelRecording();
      return setBinding(defaultHotkey, 'reset');
    }

    function registerMenu() {
      if (menuRegistered) return Promise.resolve(true);
      if (menuRegistrationPromise) return menuRegistrationPromise;
      const modern = runtime.GM && runtime.GM.registerMenuCommand;
      const legacy = runtime.GM_registerMenuCommand;
      const invoke = (fn, receiver) => {
        let result;
        try {
          result = fn.call(receiver, 'YouTube Shorts settings', show);
        } catch (_) {
          return Promise.resolve(false);
        }
        return Promise.resolve(result).then(() => {
          menuRegistered = true;
          return true;
        }, () => false);
      };
      if (typeof modern !== 'function' && typeof legacy !== 'function') return null;
      const attempt = typeof modern === 'function'
        ? invoke(modern, runtime.GM).then((registered) => registered || (typeof legacy === 'function' ? invoke(legacy, runtime) : false))
        : invoke(legacy, runtime);
      menuRegistrationPromise = Promise.resolve(attempt).then((registered) => {
        if (!registered && !menuRegistered) menuRegistrationPromise = null;
        return registered;
      }, (error) => {
        if (!menuRegistered) menuRegistrationPromise = null;
        return false;
      });
      return menuRegistrationPromise;
    }

    function ensureMounted() {
      registerMenu();
      ensureRootLockStyle();
      if (!settingsDocument || typeof settingsDocument.createElement !== 'function' || !settingsDocument.body) return null;
      if (ui && ui.host && ui.host.isConnected) {
        return ui;
      }
      if (ui && ui.host && !ui.host.isConnected) {
        close();
        pointerDownOutside = false;
        setRootLock(false);
        ui = null;
      }
      const host = settingsDocument.createElement('div');
      host.id = 'youtube-shorts-switcher-settings-host';
      host.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none;';
      const shadow = typeof host.attachShadow === 'function' ? host.attachShadow({mode: 'open'}) : host;
      const style = settingsDocument.createElement('style');
      style.textContent = `
        :host {
          all: initial;
          --settings-panel: #161b22 !important;
          --settings-field: #0d1117 !important;
          --settings-surface: #21262d !important;
          --settings-text: #e6edf3 !important;
          --settings-muted: #9da7b3 !important;
          --settings-border: #484f58 !important;
          --settings-accent: #58a6ff !important;
          --settings-primary: #238636 !important;
          --settings-focus: #58a6ff !important;
          --settings-danger: #ff7b72 !important;
          --settings-success: #3fb950 !important;
          color: var(--settings-text) !important;
          color-scheme: dark;
          font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        @media (prefers-color-scheme: light) {
          :host {
            --settings-panel: #ffffff !important;
            --settings-field: #ffffff !important;
            --settings-surface: #f6f8fa !important;
            --settings-text: #1f2328 !important;
            --settings-muted: #656d76 !important;
            --settings-border: #d0d7de !important;
            --settings-accent: #0969da !important;
            --settings-primary: #1f883d !important;
            --settings-focus: #0969da !important;
            --settings-danger: #cf222e !important;
            --settings-success: #1a7f37 !important;
            color-scheme: light;
          }
        }
        *, *::before, *::after { box-sizing: border-box; }
        button, input, select, textarea { font: inherit; }
        button { cursor: pointer; }
        dialog { width: min(430px, calc(100vw - 32px)); max-height: min(560px, calc(100vh - 32px)); margin: auto; border: 1px solid var(--settings-border) !important; border-radius: 8px; background: var(--settings-panel) !important; color: var(--settings-text) !important; color-scheme: inherit; padding: 0; box-shadow: 0 8px 32px rgb(0 0 0 / 42%); pointer-events: auto; }
        dialog::backdrop { background: rgb(255 255 255 / 12%); }
        @media (prefers-color-scheme: light) {
          dialog::backdrop { background: rgb(0 0 0 / 32%); }
        }
        dialog[data-backdrop-theme="dark"]::backdrop { background: rgb(255 255 255 / 12%); }
        dialog[data-backdrop-theme="light"]::backdrop { background: rgb(0 0 0 / 32%); }
        .panel { overflow: auto; overscroll-behavior: contain; max-height: min(560px, calc(100vh - 32px)); padding: 18px; background: var(--settings-panel) !important; color: var(--settings-text) !important; }
        h2, label, .binding span { color: var(--settings-text) !important; }
        h2 { font-size: 16px; margin: 0 0 8px; }
        h2.settings-heading:focus { outline: none; }
        .binding { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 18px 0 10px; }
        .binding code { min-width: 90px; padding: 7px 9px; border: 1px solid var(--settings-border) !important; border-radius: 6px; background: var(--settings-field) !important; color: var(--settings-text) !important; text-align: center; font: 600 13px ui-monospace, SFMono-Regular, Menlo, monospace; }
        input, select, textarea { border: 1px solid var(--settings-border) !important; border-radius: 6px; background: var(--settings-field) !important; color: var(--settings-text) !important; padding: 4px 6px; }
        option { background: var(--settings-field) !important; color: var(--settings-text) !important; }
        input:hover, select:hover, textarea:hover { border-color: var(--settings-accent) !important; }
        .hint, .status { color: var(--settings-muted) !important; font-size: 12px; }
        .hint { margin: 0 0 10px; }
        .status { min-height: 1.4em; margin: 12px 0 0; }
        .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
        .actions button { border: 1px solid var(--settings-border) !important; border-radius: 6px; background: var(--settings-surface) !important; color: var(--settings-text) !important; padding: 5px 9px; }
        .actions button:hover { background: var(--settings-border) !important; }
        .actions .primary, .actions .primary:hover { background: var(--settings-primary) !important; border-color: var(--settings-primary) !important; color: #fff !important; }
        button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 2px solid var(--settings-focus) !important; outline-offset: 2px; }
        .status[data-state="ready"] { color: var(--settings-success) !important; }
        .status[data-state="read-error"], .status[data-state="write-error"] { color: var(--settings-danger) !important; }
      `;
      const dialog = settingsDocument.createElement('dialog');
      dialog.setAttribute('aria-labelledby', 'youtube-shorts-settings-title');
      const form = settingsDocument.createElement('form');
      form.className = 'panel';
      const heading = settingsDocument.createElement('h2');
      heading.id = 'youtube-shorts-settings-title';
      heading.className = 'settings-heading';
      heading.setAttribute('tabindex', '-1');
      heading.setAttribute('autofocus', '');
      heading.textContent = 'YouTube Shorts settings';
      const binding = settingsDocument.createElement('div');
      binding.className = 'binding';
      const bindingLabel = settingsDocument.createElement('span');
      bindingLabel.textContent = 'Current binding';
      const bindingValue = settingsDocument.createElement('code');
      bindingValue.setAttribute('data-binding', '');
      binding.append(bindingLabel, bindingValue);
      const hint = settingsDocument.createElement('p');
      hint.className = 'hint';
      hint.textContent = 'Choose a single key or combination such as Shift+W. Some browser or OS shortcuts never reach this page; if one is intercepted, choose another.';
      const actions = settingsDocument.createElement('div');
      actions.className = 'actions';
      const record = settingsDocument.createElement('button');
      record.type = 'button';
      record.setAttribute('data-record', '');
      record.textContent = 'Record shortcut';
      const reset = settingsDocument.createElement('button');
      reset.type = 'button';
      reset.setAttribute('data-reset', '');
      reset.textContent = 'Reset defaults';
      const closeButton = settingsDocument.createElement('button');
      closeButton.className = 'primary';
      closeButton.type = 'button';
      closeButton.setAttribute('data-close', '');
      closeButton.textContent = 'Close';
      actions.append(record, reset, closeButton);
      const status = settingsDocument.createElement('p');
      status.className = 'status';
      status.setAttribute('role', 'status');
      status.setAttribute('aria-live', 'polite');
      form.append(heading, binding, hint, actions, status);
      dialog.appendChild(form);
      shadow.append(style, dialog);
      ui = {
        host,
        shadow,
        dialog,
        heading,
        binding: bindingValue,
        record,
        reset,
        close: closeButton,
        status,
        recording: false,
      };
      bindUi();
      (settingsDocument.body || settingsDocument.documentElement).appendChild(host);
      renderSettings();
      return ui;
    }

    function bindUi() {
      ui.close.addEventListener('click', close);
      ui.reset.addEventListener('click', () => {
        resetDefaults();
        flush().catch(() => {});
      });
      ui.record.addEventListener('click', () => {
        if (ui.recording) cancelRecording();
        else startRecording();
      });
      ui.dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (ui.recording) cancelRecording();
        else close();
      });
      ui.dialog.addEventListener('close', () => {
        pointerDownOutside = false;
        setRootLock(false);
        if (ui && ui.recording) cancelRecording();
        if (ui) flush().catch(() => {});
        if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
      });
      ui.dialog.addEventListener('pointerdown', handleDialogPointerDown);
      ui.dialog.addEventListener('pointercancel', () => { pointerDownOutside = false; });
      ui.dialog.addEventListener('click', handleDialogClick);
      ui.dialog.addEventListener('wheel', (event) => {
        if (isOpen() && event.target === ui.dialog && isOutsideDialogPoint(event)) event.preventDefault();
      }, {passive: false});
      ui.dialog.addEventListener('submit', (event) => event.preventDefault());
      ui.dialog.addEventListener('keydown', (event) => {
        if (eventKey(event) !== 'tab' || ui.recording) return;
        const focusable = [ui.record, ui.reset, ui.close].filter((element) => element && typeof element.focus === 'function');
        if (focusable.length === 0) return;
        const active = ui.shadow && ui.shadow.activeElement || settingsDocument.activeElement;
        const index = focusable.indexOf(active);
        const target = event.shiftKey
          ? (index <= 0 ? focusable[focusable.length - 1] : null)
          : (index < 0 || index === focusable.length - 1 ? focusable[0] : null);
        if (!target) return;
        event.preventDefault();
        target.focus();
      });
    }

    function isOpen() {
      return !!(ui && ui.host && ui.host.isConnected && ui.dialog && (ui.dialog.open || ui.dialog.hasAttribute('open')));
    }

    function isPrimaryPointer(event) {
      if (!event || event.isPrimary === false) return false;
      return event.pointerType !== 'mouse' || event.button === undefined || event.button === 0;
    }

    function isOutsideDialogPoint(event) {
      if (!ui || !ui.dialog || !event || typeof ui.dialog.getBoundingClientRect !== 'function') return false;
      const rect = ui.dialog.getBoundingClientRect();
      const x = Number(event.clientX);
      const y = Number(event.clientY);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
      return x < rect.left || x > rect.right || y < rect.top || y > rect.bottom;
    }

    function handleDialogPointerDown(event) {
      pointerDownOutside = isOpen()
        && isPrimaryPointer(event)
        && event.target === ui.dialog
        && isOutsideDialogPoint(event);
    }

    function handleDialogClick(event) {
      const shouldClose = pointerDownOutside
        && isOpen()
        && isPrimaryPointer(event)
        && event.target === ui.dialog
        && isOutsideDialogPoint(event);
      pointerDownOutside = false;
      if (shouldClose) {
        event.preventDefault();
        event.stopPropagation();
        close();
      }
    }

    function startRecording() {
      if (!isOpen()) return;
      ui.recording = true;
      ui.record.textContent = 'Cancel recording';
      ui.status.textContent = 'Press a key or combination… Escape cancels.';
      ui.status.dataset.state = 'recording';
    }

    function cancelRecording() {
      if (!ui) return;
      ui.recording = false;
      ui.record.textContent = 'Record shortcut';
      renderSettings();
    }

    function handleKeydown(event) {
      if (!ui || !isOpen()) return false;
      if (ui.recording) {
        if (eventKey(event) === 'escape') {
          event.preventDefault();
          event.stopImmediatePropagation();
          cancelRecording();
          return true;
        }
        if (isEditableEventTarget(event)) return true;
        const rawKey = normalizeKey(event && event.key);
        if (modifierKeys.has(rawKey)) return true;
        // Once a non-modifier reaches the page, keep YouTube controls from
        // handling it even when it is a repeat or an IME/dead-key event.
        event.preventDefault();
        event.stopImmediatePropagation();
        const recorded = recordingHotkey(event);
        if (recorded) setBinding(recorded, 'record');
        if (recorded) {
          ui.recording = false;
          ui.record.textContent = 'Record shortcut';
          renderSettings();
        }
        return true;
      }
      return true;
    }

    function show() {
      if (ui && isOpen()) {
        return;
      }
      const mounted = ensureMounted();
      if (!mounted) return;
      lastFocus = settingsDocument.activeElement || null;
      renderSettings();
      updateBackdropTheme();
      if (typeof ui.dialog.showModal !== 'function') {
        if (typeof console !== 'undefined' && typeof console.warn === 'function') console.warn('[YouTube Shorts Switcher] Native modal dialogs are unavailable; settings remain closed.');
        setRootLock(false);
        return;
      }
      try {
        if (!ui.dialog.open) ui.dialog.showModal();
      } catch (error) {
        setRootLock(false);
        if (typeof console !== 'undefined' && typeof console.warn === 'function') console.warn('[YouTube Shorts Switcher] Native settings modal could not open; settings remain closed.', error);
        return;
      }
      setRootLock(isOpen());
      if (ui.heading && typeof ui.heading.focus === 'function') ui.heading.focus({preventScroll: true});
    }

    function close() {
      if (!ui) return;
      setRootLock(false);
      if (ui.recording) cancelRecording();
      flush().catch(() => {});
      if (typeof ui.dialog.close === 'function' && ui.dialog.open) ui.dialog.close();
      else ui.dialog.removeAttribute('open');
      if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    }

    function renderSettings() {
      if (!ui) return;
      ui.binding.textContent = current;
      if (!ui.recording) ui.record.textContent = 'Record shortcut';
      ui.status.textContent = ui.recording
        ? 'Press a key or combination… Escape cancels.'
        : storageError && storageState === 'write-error' ? storageError.message || statusText(storageState) : statusText(storageState);
      ui.status.dataset.state = ui.recording ? 'recording' : storageState;
    }

    return {
      initialize,
      ensureMounted,
      show,
      close,
      isOpen,
      handleKeydown,
      resetDefaults,
      flush,
      getCurrent: () => current,
    };
  }

  // Window capture sees keyboard events retargeted from the settings shadow
  // root. It therefore handles recording and the dialog guard before Shorts'
  // normal redirect path.
  window.addEventListener('keydown', (event) => {
    if (settingsController && settingsController.isOpen()) {
      settingsController.handleKeydown(event);
      return;
    }
    if (isEditableEventTarget(event)) return;
    if (isWatchViewActive()) return;
    if (!(isShortsUrl() || isShortsViewActive())) return;
    if (matchesHotkey(event, parseHotkey(currentHotkey))) {
      event.preventDefault();
      event.stopImmediatePropagation();
      redirectToWatch();
    }
  }, true);

  function refreshMounts() {
    if (isShortsUrl() || isShortsViewActive()) ensureColumnButton();
    else tearDownColumnButton();
    if (settingsController) settingsController.ensureMounted();
  }

  patchHistoryMethod(history, 'pushState');
  patchHistoryMethod(history, 'replaceState');
  window.addEventListener('popstate', () => queueMicrotask(refreshMounts), true);

  let lastHref = location.href;
  setInterval(() => {
    if (location.href !== lastHref) {
      lastHref = location.href;
      refreshMounts();
    }
  }, 400);
  const mutationObserver = new MutationObserver(() => refreshMounts());
  mutationObserver.observe(document.documentElement, {subtree: true, childList: true});

  settingsController = createSettingsController({
    runtime: {
      GM_getValue: typeof GM_getValue === 'function' ? GM_getValue : undefined,
      GM_setValue: typeof GM_setValue === 'function' ? GM_setValue : undefined,
      GM_registerMenuCommand: typeof GM_registerMenuCommand === 'function' ? GM_registerMenuCommand : undefined,
      GM: typeof GM === 'object' ? GM : undefined,
      // Preserve the native Window receiver for managers whose timer methods
      // are receiver-sensitive.
      setTimeout: (callback, delay) => window.setTimeout(callback, delay),
      clearTimeout: (timer) => window.clearTimeout(timer),
      window,
    },
    document,
    defaultHotkey: DEFAULT_HOTKEY,
    onChange: (next) => {
      currentHotkey = next;
      updateColumnButtonTooltip();
    },
  });

  document.addEventListener('DOMContentLoaded', () => settingsController.ensureMounted(), {once: true, capture: true});
  settingsController.initialize().catch((error) => {
    if (typeof console !== 'undefined' && typeof console.error === 'function') {
      console.error('[YouTube Shorts Switcher] Settings initialization failed.', error);
    }
  });
  refreshMounts();

})();
