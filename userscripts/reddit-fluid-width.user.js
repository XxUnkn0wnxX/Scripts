// ==UserScript==
// @name         Reddit Fluid Width
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.1.2
// @description  Widens Reddit post/comment pages only while preserving native feed and landing layouts. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/reddit-fluid-width.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/reddit-fluid-width.user.js
// @match        https://www.reddit.com/*
// @match        https://reddit.com/*
// @run-at       document-start
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

  const STYLE_ID = 'reddit-fluid-width-style';
  const ROOT_ATTR = 'data-reddit-fluid-width';
  const NO_LEFT_SIDEBAR_ATTR = 'data-reddit-fluid-width-no-left-sidebar';
  const INSTANCE_FLAG = '__redditFluidWidthInstalled';
  const HISTORY_PATCH_FLAG = '__redditFluidWidthHistoryPatched';
  const ROUTE_RE = /^\/r\/[^/]+\/comments\/[^/]+(?:\/|$)/i;
  const LEFT_SIDEBAR_SELECTOR = '#left-sidebar-container';

  if (window[INSTANCE_FLAG]) return;
  window[INSTANCE_FLAG] = true;

  /*** CONFIG ***/
  // Tune visible-sidebar and no-left-sidebar post widths independently (1-100).
  // minGutterPx is the safety inset shared by both sidebar states.
  // true (default) pins the right edge at 100%/0px; false centers the whole grid.
  const CONFIG = Object.freeze({
    contentWidthPercent: 95,
    noLeftSidebarContentWidthPercent: 95,
    minGutterPx: 32,
    pinRightSidebar: true,
  });

  const SETTINGS_SCHEMA_VERSION = 1;
  const SETTINGS_DEFAULTS = CONFIG;
  const SETTINGS_KEYS = Object.freeze({
    contentWidthPercent: 'reddit-fluid-width.contentWidthPercent',
    noLeftSidebarContentWidthPercent: 'reddit-fluid-width.noLeftSidebarContentWidthPercent',
    minGutterPx: 'reddit-fluid-width.minGutterPx',
    pinRightSidebar: 'reddit-fluid-width.pinRightSidebar',
    schemaVersion: 'reddit-fluid-width.schemaVersion',
  });
  const SETTINGS_CONFIG_KEYS = Object.freeze([
    'contentWidthPercent',
    'noLeftSidebarContentWidthPercent',
    'minGutterPx',
    'pinRightSidebar',
  ]);

  let config = normalizeConfig(CONFIG);
  const style = ensureStyle();
  const html = document.documentElement;
  let sidebarSyncScheduled = false;
  let domReadySidebarSync = false;
  let routeSyncScheduled = false;
  let sidebarObserver;

  const settingsController = createSettingsController({
    runtime: {
      GM_getValue: typeof GM_getValue === 'function' ? GM_getValue : undefined,
      GM_setValue: typeof GM_setValue === 'function' ? GM_setValue : undefined,
      GM_registerMenuCommand: typeof GM_registerMenuCommand === 'function' ? GM_registerMenuCommand : undefined,
      GM: typeof GM === 'object' ? GM : undefined,
      setTimeout: (callback, delay) => window.setTimeout(callback, delay),
      clearTimeout: (timer) => window.clearTimeout(timer),
    },
    document,
    defaults: CONFIG,
    onChange: applySettings,
  });

  style.textContent = buildStyles();

  syncRouteState();
  installRouteSyncHooks();
  installLeftSidebarObserver();
  settingsController.ensureMounted();
  document.addEventListener('DOMContentLoaded', () => settingsController.ensureMounted(), {once: true, capture: true});
  settingsController.initialize().catch(() => {});

  function applySettings(next) {
    config = normalizeConfig(next);
    style.textContent = buildStyles();
    syncRouteState();
  }

  function normalizeConfig(source) {
    const percentRaw = Number(source?.contentWidthPercent);
    const noLeftSidebarPercentRaw = Number(source?.noLeftSidebarContentWidthPercent);
    const gutterRaw = Number(source?.minGutterPx);
    const pinRightSidebar = source?.pinRightSidebar;

    const contentWidthPercent = Number.isFinite(percentRaw)
      ? Math.max(1, Math.min(100, percentRaw))
      : 95;

    const noLeftSidebarContentWidthPercent = Number.isFinite(noLeftSidebarPercentRaw)
      ? Math.max(1, Math.min(100, noLeftSidebarPercentRaw))
      : 95;

    const minGutterPx = Number.isFinite(gutterRaw)
      ? Math.max(16, Math.min(128, Math.round(gutterRaw)))
      : 32;

    return Object.freeze({
      contentWidthPercent,
      noLeftSidebarContentWidthPercent,
      minGutterPx,
      pinRightSidebar: typeof pinRightSidebar === 'boolean' ? pinRightSidebar : true,
    });
  }

  function syncRouteState() {
    const isPostRoute = isRedditPostCommentsRoute(location.pathname);
    if (isPostRoute) {
      html.setAttribute(ROOT_ATTR, '');
      scheduleLeftSidebarSync();
      return;
    }

    html.removeAttribute(ROOT_ATTR);
    html.removeAttribute(NO_LEFT_SIDEBAR_ATTR);
  }

  function isRedditPostCommentsRoute(pathname) {
    return ROUTE_RE.test(String(pathname || '').trim());
  }

  function buildStyles() {
    const isPinned = config.pinRightSidebar;
    const horizontalModeStyles = isPinned
      ? `
    margin-inline-start: auto !important;
    margin-inline-end: 0px !important;
    `
      : `
    margin-inline: auto !important;
    `;
    const gutteredWidth = isPinned
      ? `calc(100% - var(--reddit-fluid-gutter))`
      : `calc(100% - var(--reddit-fluid-gutter) - var(--reddit-fluid-gutter))`;

    return `
@media (min-width: 1472px) {
  html[${ROOT_ATTR}] #subgrid-container {
    --reddit-fluid-width: ${config.contentWidthPercent}%;
    --reddit-fluid-gutter: ${config.minGutterPx}px;
    width: min(
      100%,
      max(
        1120px,
        min(var(--reddit-fluid-width), ${gutteredWidth})
      )
    ) !important;
    box-sizing: border-box;
${horizontalModeStyles}
  }

  html[${ROOT_ATTR}][${NO_LEFT_SIDEBAR_ATTR}] #subgrid-container {
    --reddit-fluid-width: ${config.noLeftSidebarContentWidthPercent}%;
  }

  html[${ROOT_ATTR}][${NO_LEFT_SIDEBAR_ATTR}] .grid-container:not(.grid-full) > #subgrid-container {
    grid-column: 1 / -1 !important;
    max-width: none !important;
  }

  html[${ROOT_ATTR}] #subgrid-container > .main-container.fixed-sidebar {
    grid-template-columns: minmax(0, 1fr) minmax(0, 316px) !important;
  }
}
`;
  }

  function ensureStyle() {
    let styleNode = document.getElementById(STYLE_ID);
    if (!styleNode) {
      styleNode = document.createElement('style');
      styleNode.id = STYLE_ID;
      (document.head || document.documentElement).appendChild(styleNode);
    }
    return styleNode;
  }

  function installRouteSyncHooks() {
    if (!history[HISTORY_PATCH_FLAG]) {
      const originalPushState = history.pushState;
      const originalReplaceState = history.replaceState;

      history.pushState = function (...args) {
        const result = originalPushState.apply(this, args);
        syncRouteState();
        return result;
      };

      history.replaceState = function (...args) {
        const result = originalReplaceState.apply(this, args);
        syncRouteState();
        return result;
      };

      history[HISTORY_PATCH_FLAG] = true;
    }

    window.addEventListener('popstate', syncRouteState, true);
    window.addEventListener('pageshow', syncRouteState, true);
    window.addEventListener('resize', scheduleLeftSidebarSync, true);
    for (const event of ['DOMContentLoaded', 'turbo:load', 'turbo:render', 'pjax:end']) {
      document.addEventListener(event, syncRouteState, true);
    }
  }

  function scheduleRouteStateSync() {
    if (routeSyncScheduled) return;
    routeSyncScheduled = true;
    requestAnimationFrame(() => {
      routeSyncScheduled = false;
      syncRouteState();
    });
  }

  function scheduleLeftSidebarSync() {
    if (document.readyState === 'loading') {
      if (!domReadySidebarSync) {
        domReadySidebarSync = true;
        document.addEventListener(
          'DOMContentLoaded',
          () => {
            domReadySidebarSync = false;
            scheduleLeftSidebarSync();
          },
          { once: true }
        );
      }
      return;
    }

    if (sidebarSyncScheduled) return;

    sidebarSyncScheduled = true;
    requestAnimationFrame(() => {
      sidebarSyncScheduled = false;
      syncLeftSidebarState();
    });
  }

  function syncLeftSidebarState() {
    if (!isRedditPostCommentsRoute(location.pathname)) {
      html.removeAttribute(NO_LEFT_SIDEBAR_ATTR);
      return;
    }

    const hasSidebar = isLeftSidebarVisible();
    if (hasSidebar) {
      html.removeAttribute(NO_LEFT_SIDEBAR_ATTR);
      return;
    }

    html.setAttribute(NO_LEFT_SIDEBAR_ATTR, '');
  }

  function isLeftSidebarVisible() {
    const leftSidebar = document.querySelector(LEFT_SIDEBAR_SELECTOR);
    if (!leftSidebar) return false;

    if (!isElementVisiblyRendered(leftSidebar)) return false;
    if (!hasVisiblyRenderedDescendant(leftSidebar)) return false;

    return true;
  }

  function isElementVisiblyRendered(node) {
    const computedStyles = getComputedStyle(node);
    if (!computedStyles) return false;
    if (
      computedStyles.display === 'none' ||
      computedStyles.visibility !== 'visible'
    ) {
      return false;
    }

    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.right > 0;
  }

  function hasVisiblyRenderedDescendant(node) {
    const descendants = node.querySelectorAll('*');
    for (const descendant of descendants) {
      if (isElementVisiblyRendered(descendant)) {
        return true;
      }
    }

    return false;
  }

  function installLeftSidebarObserver() {
    if (sidebarObserver) return;

    const root = document.documentElement || document;
    if (!window.MutationObserver) return;

    const observer = new MutationObserver((mutations) => {
      settingsController.ensureMounted();
      if (mutations.some((mutation) => mutation.type === 'childList')) scheduleRouteStateSync();
      if (!isRedditPostCommentsRoute(location.pathname)) return;
      const currentSidebar = document.querySelector(LEFT_SIDEBAR_SELECTOR);
      if (!isSidebarMutationRelevant(mutations, currentSidebar)) return;
      scheduleLeftSidebarSync();
    });

    observer.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['style', 'class', 'hidden', 'aria-hidden'],
    });
    sidebarObserver = observer;
  }

  function isSidebarMutationRelevant(mutations, currentSidebar) {
    return mutations.some((mutation) => {
      if (mutation.type === 'attributes') {
        const target = mutation.target;
        return target instanceof Element && mutationCouldAffectLeftSidebar(target, currentSidebar);
      }

      if (mutation.type === 'childList') {
        if (
          currentSidebar &&
          (mutation.target === currentSidebar || currentSidebar.contains?.(mutation.target))
        ) {
          return true;
        }

        const nodes = [...mutation.addedNodes, ...mutation.removedNodes];
        return nodes.some((node) => node instanceof Element && isNodeAffectingSidebar(node, currentSidebar));
      }

      return false;
    });
  }

  function mutationCouldAffectLeftSidebar(target, currentSidebar) {
    if (target === null) return false;
    if (target.matches?.(LEFT_SIDEBAR_SELECTOR)) return true;
    if (!currentSidebar) return false;
    return currentSidebar.contains?.(target) || target.contains?.(currentSidebar);
  }

  function isNodeAffectingSidebar(node, currentSidebar) {
    if (!currentSidebar) return node.matches?.(LEFT_SIDEBAR_SELECTOR) || !!node.querySelector?.(LEFT_SIDEBAR_SELECTOR);

    return (
      node.matches?.(LEFT_SIDEBAR_SELECTOR) ||
      currentSidebar.contains?.(node) ||
      node.contains?.(currentSidebar) ||
      node.querySelector?.(LEFT_SIDEBAR_SELECTOR)
    );
  }
  function createSettingsController(options = {}) {
    const runtime = options.runtime || window;
    const settingsDocument = options.document || document;
    const defaults = normalizeSettingsConfig({...SETTINGS_DEFAULTS, ...(options.defaults || {})});
    const onChange = typeof options.onChange === 'function' ? options.onChange : () => {};
    const setTimeoutFn = typeof runtime.setTimeout === 'function' ? runtime.setTimeout.bind(runtime) : setTimeout;
    const clearTimeoutFn = typeof runtime.clearTimeout === 'function' ? runtime.clearTimeout.bind(runtime) : clearTimeout;
    const ROOT_LOCK_ATTRIBUTE = 'data-reddit-fluid-width-settings-open';
    const ROOT_LOCK_STYLE_ID = 'reddit-fluid-width-settings-lock-style';
    const BACKDROP_THEME_ATTRIBUTE = 'data-backdrop-theme';
    let storage = findSettingsStorage(runtime);
    let storageState = storage ? 'loading' : 'unavailable';
    let storageError = null;
    let current = copySettingsConfig(defaults);
    let initializePromise = null;
    let saveTimer = null;
    let writeChain = Promise.resolve();
    let ui = null;
    let lastFocus = null;
    let menuRegistered = false;
    let pointerDownOutside = false;
    let version = 0;
    const keyVersions = new Map();
    const pendingKeys = new Set();
    const readableKeys = new Set();
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
      try {
        onChange(copySettingsConfig(current), {source, storageState});
      } catch (error) {
        setStatus('write-error', `The page updated, but its width callback failed: ${error.message || error}`);
      }
      renderSettings();
    }

    function configStorageKey(key) {
      return SETTINGS_KEYS[key];
    }

    function markUserChange(key) {
      version += 1;
      keyVersions.set(key, version);
      if (!storage) return;
      // A failed read is never silently overwritten. An explicit field edit
      // authorizes a write for that field only.
      readableKeys.add(configStorageKey(key));
      pendingKeys.add(key);
    }

    function setConfig(partial, source = 'input') {
      let changed = false;
      SETTINGS_CONFIG_KEYS.forEach((key) => {
        if (!Object.prototype.hasOwnProperty.call(partial, key)) return;
        const next = normalizeSettingValue(key, partial[key], defaults[key]);
        if (Object.is(next, current[key])) return;
        current[key] = next;
        changed = true;
        markUserChange(key);
      });
      if (source === 'reset') SETTINGS_CONFIG_KEYS.forEach((key) => markUserChange(key));
      if (!changed && source !== 'reset') return copySettingsConfig(current);
      notify(source);
      scheduleSettingsSave();
      return copySettingsConfig(current);
    }

    function scheduleSettingsSave() {
      if (!storage || !setTimeoutFn) return;
      if (saveTimer !== null) clearTimeoutFn(saveTimer);
      saveTimer = setTimeoutFn(() => {
        saveTimer = null;
        if (ui) flushSettings().catch(() => {});
      }, 120);
    }

    function pendingEntries() {
      return Array.from(pendingKeys)
        .filter((key) => readableKeys.has(configStorageKey(key)))
        .map((key) => ({
          configKey: key,
          storageKey: configStorageKey(key),
          value: current[key],
          version: keyVersions.get(key),
        }));
    }

    async function performSettingsWrites(entries) {
      if (!storage || entries.length === 0) return;
      let failed = false;
      setStatus('saving');
      for (const entry of entries) {
        try {
          await Promise.resolve(storage.set(entry.storageKey, entry.value));
          if (keyVersions.get(entry.configKey) === entry.version) pendingKeys.delete(entry.configKey);
        } catch (error) {
          failed = true;
          storageError = error;
        }
      }
      setStatus(failed ? 'write-error' : 'ready', failed
        ? 'Changes apply on this page, but saving failed.'
        : 'Saved in your userscript manager.');
      // Saving changes status only. Rewriting controls here can undo a native
      // checkbox toggle between its input and change events.
    }

    function flushSettings() {
      if (!storage) return writeChain;
      const entries = pendingEntries();
      if (entries.length === 0) return writeChain;
      writeChain = writeChain.then(() => performSettingsWrites(entries));
      return writeChain;
    }

    function queueMissingSettings(entries) {
      if (!storage || entries.length === 0) return writeChain;
      writeChain = writeChain.then(async () => {
        let failed = false;
        setStatus('saving');
        for (const entry of entries) {
          if (entry.configKey && (keyVersions.get(entry.configKey) || 0) !== entry.version) continue;
          try {
            await Promise.resolve(storage.set(entry.storageKey, entry.value));
            readableKeys.add(entry.storageKey);
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
      ensureMounted();
      initializePromise = (async () => {
        if (!storage) {
          setStatus('unavailable');
          notify('defaults');
          registerSettingsMenu();
          return copySettingsConfig(current);
        }

        const values = {};
        const failedReads = new Set();
        const readVersions = new Map(SETTINGS_CONFIG_KEYS.map((key) => [key, keyVersions.get(key) || 0]));
        await Promise.all(Object.values(SETTINGS_KEYS).map(async (key) => {
          try {
            values[key] = await Promise.resolve(storage.get(key));
            readableKeys.add(key);
          } catch (error) {
            failedReads.add(key);
            storageError = error;
          }
        }));
        SETTINGS_CONFIG_KEYS.forEach((key) => {
          const storageKey = configStorageKey(key);
          if (!failedReads.has(storageKey) && values[storageKey] !== undefined &&
              (keyVersions.get(key) || 0) === readVersions.get(key)) {
            current[key] = normalizeSettingValue(key, values[storageKey], defaults[key]);
          }
        });
        notify('load');
        registerSettingsMenu();
        if (failedReads.size > 0) {
          setStatus('read-error', 'Saved values could not be read; unknown values were left untouched.');
          renderSettings();
          return copySettingsConfig(current);
        }

        const missing = SETTINGS_CONFIG_KEYS
          .filter((key) => values[configStorageKey(key)] === undefined)
          .map((key) => ({
            configKey: key,
            storageKey: configStorageKey(key),
            value: current[key],
            version: keyVersions.get(key) || 0,
          }));
        if (values[SETTINGS_KEYS.schemaVersion] === undefined) {
          missing.push({storageKey: SETTINGS_KEYS.schemaVersion, value: SETTINGS_SCHEMA_VERSION});
        }
        await queueMissingSettings(missing);
        if (missing.length === 0) setStatus('ready');
        renderSettings();
        return copySettingsConfig(current);
      })();
      return initializePromise;
    }

    function resetDefaults() {
      return setConfig(defaults, 'reset');
    }

    function registerSettingsMenu() {
      if (menuRegistered) return;
      const legacy = runtime.GM_registerMenuCommand;
      const modern = runtime.GM && runtime.GM.registerMenuCommand;
      const register = typeof legacy === 'function'
        ? legacy.bind(runtime)
        : typeof modern === 'function' ? modern.bind(runtime.GM) : null;
      if (!register) return;
      try {
        const result = register('Reddit Fluid Width settings', show);
        menuRegistered = true;
        if (result && typeof result.catch === 'function') result.catch(() => {});
      } catch (_) {
        // A manager may decline the optional menu command.
      }
    }

    function ensureMounted() {
      ensureRootLockStyle();
      if (!settingsDocument || typeof settingsDocument.createElement !== 'function') return null;
      if (ui && ui.host && ui.host.isConnected) {
        registerSettingsMenu();
        return ui;
      }
      if (ui && ui.host && !ui.host.isConnected) {
        close();
        pointerDownOutside = false;
        setRootLock(false);
        ui = null;
      }
      if (!settingsDocument.body) return null;
      const host = settingsDocument.createElement('div');
      host.id = 'reddit-fluid-width-settings-host';
      const shadow = typeof host.attachShadow === 'function' ? host.attachShadow({mode: 'open'}) : host;
      shadow.innerHTML = `
        <style>
          :host {
            all: initial;
            --settings-panel: #161b22 !important;
            --settings-field: #0d1117 !important;
            --settings-surface: #21262d !important;
            --settings-text: #e6edf3 !important;
            --settings-muted: #9da7b3 !important;
            --settings-border: #484f58 !important;
            --settings-accent: #ff7b72 !important;
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
              --settings-accent: #ff4500 !important;
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
          dialog { width: min(440px, calc(100vw - 32px)); max-height: min(680px, calc(100vh - 32px)); margin: auto; border: 1px solid var(--settings-border) !important; border-radius: 8px; background: var(--settings-panel) !important; color: var(--settings-text) !important; color-scheme: inherit; padding: 0; box-shadow: 0 8px 32px rgb(0 0 0 / 42%); }
          dialog::backdrop { background: rgb(255 255 255 / 12%); }
          @media (prefers-color-scheme: light) {
            dialog::backdrop { background: rgb(0 0 0 / 32%); }
          }
          dialog[data-backdrop-theme="dark"]::backdrop { background: rgb(255 255 255 / 12%); }
          dialog[data-backdrop-theme="light"]::backdrop { background: rgb(0 0 0 / 32%); }
          .panel { overflow: auto; overscroll-behavior: contain; max-height: min(680px, calc(100vh - 32px)); padding: 18px; background: var(--settings-panel) !important; color: var(--settings-text) !important; }
          h2, label { color: var(--settings-text) !important; }
          h2 { font-size: 16px; margin: 0 0 8px; }
          h2.settings-heading:focus { outline: none; }
          .hint, .status { color: var(--settings-muted) !important; font-size: 12px; }
          .status { min-height: 1.4em; margin: 12px 0 0; }
          .row { display: grid; gap: 6px; margin: 14px 0; }
          .range-row { display: grid; grid-template-columns: 1fr 88px; align-items: center; }
          input[type="range"] { width: 100%; accent-color: var(--settings-accent); }
          input[type="number"], input[type="text"], select, textarea { border: 1px solid var(--settings-border) !important; border-radius: 6px; background: var(--settings-field) !important; color: var(--settings-text) !important; padding: 4px 6px; }
          option { background: var(--settings-field) !important; color: var(--settings-text) !important; }
          input[type="number"] { width: 88px; }
          input[type="number"]:hover, input[type="text"]:hover, select:hover, textarea:hover { border-color: var(--settings-accent) !important; }
          .check { display: flex; gap: 8px; align-items: flex-start; }
          .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
          .actions button { border: 1px solid var(--settings-border) !important; border-radius: 6px; background: var(--settings-surface) !important; color: var(--settings-text) !important; padding: 5px 9px; }
          .actions button:hover { background: var(--settings-border) !important; }
          .actions .primary, .actions .primary:hover { background: var(--settings-primary) !important; border-color: var(--settings-primary) !important; color: #fff !important; }
          button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 2px solid var(--settings-focus) !important; outline-offset: 2px; }
          .status[data-state="ready"] { color: var(--settings-success) !important; }
          .status[data-state="read-error"], .status[data-state="write-error"] { color: var(--settings-danger) !important; }
        </style>
        <dialog id="reddit-fluid-width-settings-dialog" aria-labelledby="reddit-fluid-width-settings-title">
          <form class="panel">
            <h2 class="settings-heading" id="reddit-fluid-width-settings-title" tabindex="-1" autofocus>Reddit Fluid Width</h2>
            <p class="hint">Width rules apply from 1472px on post and comment pages. Native sidebars remain in place.</p>
            <div class="row">
              <label for="reddit-fluid-width-percent-range">Post width with left sidebar (%)</label>
              <div class="range-row">
                <input id="reddit-fluid-width-percent-range" type="range" min="1" max="100" step="1" aria-label="Post width with left sidebar percentage">
                <input id="reddit-fluid-width-percent-number" type="number" min="1" max="100" step="1" aria-label="Post width with left sidebar percentage value">
              </div>
            </div>
            <div class="row">
              <label for="reddit-fluid-width-no-left-percent-range">Post width without left sidebar (%)</label>
              <div class="range-row">
                <input id="reddit-fluid-width-no-left-percent-range" type="range" min="1" max="100" step="1" aria-label="Post width without left sidebar percentage">
                <input id="reddit-fluid-width-no-left-percent-number" type="number" min="1" max="100" step="1" aria-label="Post width without left sidebar percentage value">
              </div>
            </div>
            <div class="row">
              <label for="reddit-fluid-width-gutter">Minimum gutter (px)</label>
              <input id="reddit-fluid-width-gutter" type="number" min="16" max="128" step="1">
            </div>
            <label class="check" for="reddit-fluid-width-pin">
              <input id="reddit-fluid-width-pin" type="checkbox">
              <span>Pin right sidebar</span>
            </label>
            <p class="status" role="status" aria-live="polite"></p>
            <div class="actions">
              <button type="button" data-reset>Reset defaults</button>
              <button class="primary" type="button" data-close>Close</button>
            </div>
          </form>
        </dialog>`;
      const root = shadow;
      ui = {
        host,
        shadow,
        dialog: root.querySelector('dialog'),
        heading: root.querySelector('h2.settings-heading'),
        range: root.querySelector('#reddit-fluid-width-percent-range'),
        percent: root.querySelector('#reddit-fluid-width-percent-number'),
        noLeftRange: root.querySelector('#reddit-fluid-width-no-left-percent-range'),
        noLeftPercent: root.querySelector('#reddit-fluid-width-no-left-percent-number'),
        gutter: root.querySelector('#reddit-fluid-width-gutter'),
        pin: root.querySelector('#reddit-fluid-width-pin'),
        status: root.querySelector('.status'),
        reset: root.querySelector('[data-reset]'),
        close: root.querySelector('[data-close]'),
      };
      bindSettingsUi();
      (settingsDocument.body || settingsDocument.documentElement).appendChild(host);
      registerSettingsMenu();
      renderSettings();
      return ui;
    }

    function bindPercentControl(range, number, key) {
      range.addEventListener('input', () => setConfig({[key]: range.value}));
      number.addEventListener('input', () => {
        const value = Number(number.value);
        if (Number.isFinite(value) && value >= 1 && value <= 100) setConfig({[key]: value});
      });
      number.addEventListener('change', () => {
        if (number.value !== '') setConfig({[key]: number.value});
        renderSettings({forceNumbers: true});
        flushSettings().catch(() => {});
      });
      number.addEventListener('blur', () => renderSettings({forceNumbers: true}));
    }

    function bindSettingsUi() {
      if (!ui) return;
      ui.close.addEventListener('click', close);
      ui.reset.addEventListener('click', () => {
        resetDefaults();
        flushSettings().catch(() => {});
      });
      bindPercentControl(ui.range, ui.percent, 'contentWidthPercent');
      bindPercentControl(ui.noLeftRange, ui.noLeftPercent, 'noLeftSidebarContentWidthPercent');
      ui.gutter.addEventListener('input', () => {
        const value = Number(ui.gutter.value);
        if (Number.isFinite(value) && value >= 16 && value <= 128) setConfig({minGutterPx: value});
      });
      ui.gutter.addEventListener('change', () => {
        if (ui.gutter.value !== '') setConfig({minGutterPx: ui.gutter.value});
        renderSettings({forceNumbers: true});
        flushSettings().catch(() => {});
      });
      ui.gutter.addEventListener('blur', () => renderSettings({forceNumbers: true}));
      ui.pin.addEventListener('change', () => {
        setConfig({pinRightSidebar: ui.pin.checked});
        flushSettings().catch(() => {});
      });
      ui.dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        event.stopPropagation();
        close();
      });
      ui.dialog.addEventListener('close', () => {
        pointerDownOutside = false;
        setRootLock(false);
        flushSettings().catch(() => {});
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
        if (event.key !== 'Tab') return;
        const focusable = Array.from(ui.dialog.querySelectorAll('button, input, [href], select, textarea'))
          .filter((element) => !element.disabled && element.offsetParent !== null);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = ui.shadow.activeElement || settingsDocument.activeElement;
        if (event.shiftKey && (active === first || active === ui.heading)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && active === last) {
          event.preventDefault();
          first.focus();
        }
      });
    }

    function isOpen() {
      return !!(ui && ui.dialog && (ui.dialog.open || ui.dialog.hasAttribute('open')));
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

    function show() {
      if (ui && isOpen()) {
        return;
      }
      const mounted = ensureMounted();
      if (!mounted) return;
      lastFocus = ui.shadow.activeElement || settingsDocument.activeElement || null;
      renderSettings();
      updateBackdropTheme();
      if (typeof ui.dialog.showModal !== 'function') {
        if (typeof console !== 'undefined' && typeof console.warn === 'function') console.warn('[Reddit Fluid Width] Native modal dialogs are unavailable; settings remain closed.');
        setRootLock(false);
        return;
      }
      try {
        if (!ui.dialog.open) ui.dialog.showModal();
      } catch (error) {
        setRootLock(false);
        if (typeof console !== 'undefined' && typeof console.warn === 'function') console.warn('[Reddit Fluid Width] Native settings modal could not open; settings remain closed.', error);
        return;
      }
      setRootLock(isOpen());
      if (ui.heading && typeof ui.heading.focus === 'function') ui.heading.focus({preventScroll: true});
    }

    function close() {
      if (!ui) return;
      setRootLock(false);
      flushSettings().catch(() => {});
      if (typeof ui.dialog.close === 'function' && ui.dialog.open) ui.dialog.close();
      else ui.dialog.removeAttribute('open');
      if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
    }

    function renderSettings(options = {}) {
      if (!ui) return;
      const active = ui.shadow && ui.shadow.activeElement;
      const forceNumbers = options.forceNumbers === true;
      ui.range.value = String(current.contentWidthPercent);
      ui.noLeftRange.value = String(current.noLeftSidebarContentWidthPercent);
      if (forceNumbers || active !== ui.percent) ui.percent.value = String(current.contentWidthPercent);
      if (forceNumbers || active !== ui.noLeftPercent) ui.noLeftPercent.value = String(current.noLeftSidebarContentWidthPercent);
      if (forceNumbers || active !== ui.gutter) ui.gutter.value = String(current.minGutterPx);
      ui.pin.checked = current.pinRightSidebar;
      ui.status.textContent = storageError && storageState === 'write-error'
        ? storageError.message || statusText(storageState)
        : statusText(storageState);
      ui.status.dataset.state = storageState;
    }

    return {initialize, ensureMounted, show, close, setConfig, resetDefaults, flush: flushSettings};
  }

  function normalizeSettingValue(key, value, fallback) {
    if (key === 'contentWidthPercent' || key === 'noLeftSidebarContentWidthPercent') {
      const number = Number(value);
      return Number.isFinite(number) ? Math.max(1, Math.min(100, number)) : fallback;
    }
    if (key === 'minGutterPx') {
      const number = Number(value);
      return Math.round(Number.isFinite(number) ? Math.max(16, Math.min(128, number)) : fallback);
    }
    if (key === 'pinRightSidebar') return value !== false;
    return value;
  }

  function normalizeSettingsConfig(values) {
    return {
      contentWidthPercent: normalizeSettingValue('contentWidthPercent', values.contentWidthPercent, SETTINGS_DEFAULTS.contentWidthPercent),
      noLeftSidebarContentWidthPercent: normalizeSettingValue('noLeftSidebarContentWidthPercent', values.noLeftSidebarContentWidthPercent, SETTINGS_DEFAULTS.noLeftSidebarContentWidthPercent),
      minGutterPx: normalizeSettingValue('minGutterPx', values.minGutterPx, SETTINGS_DEFAULTS.minGutterPx),
      pinRightSidebar: normalizeSettingValue('pinRightSidebar', values.pinRightSidebar, SETTINGS_DEFAULTS.pinRightSidebar),
    };
  }

  function copySettingsConfig(values) {
    return {
      contentWidthPercent: values.contentWidthPercent,
      noLeftSidebarContentWidthPercent: values.noLeftSidebarContentWidthPercent,
      minGutterPx: values.minGutterPx,
      pinRightSidebar: values.pinRightSidebar,
    };
  }

  function findSettingsStorage(runtime) {
    const legacyGet = runtime && runtime.GM_getValue;
    const legacySet = runtime && runtime.GM_setValue;
    if (typeof legacyGet === 'function' && typeof legacySet === 'function') {
      return {
        get: (key) => legacyGet.call(runtime, key),
        set: (key, value) => legacySet.call(runtime, key, value),
      };
    }
    const gm = runtime && runtime.GM;
    if (gm && typeof gm.getValue === 'function' && typeof gm.setValue === 'function') {
      return {
        get: (key) => gm.getValue(key),
        set: (key, value) => gm.setValue(key, value),
      };
    }
    return null;
  }

})();
