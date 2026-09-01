// ==UserScript==
// @name         Reddit Fluid Width
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.1
// @description  Widens Reddit post/comment pages only while preserving native feed and landing layouts. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/reddit-fluid-width.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/userscripts/reddit-fluid-width.user.js
// @match        https://www.reddit.com/r/*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const STYLE_ID = 'reddit-fluid-width-style';
  const ROOT_ATTR = 'data-reddit-fluid-width';
  const NO_LEFT_SIDEBAR_ATTR = 'data-reddit-fluid-width-no-left-sidebar';
  const HISTORY_PATCH_FLAG = '__redditFluidWidthHistoryPatched';
  const ROUTE_RE = /^\/r\/[^/]+\/comments\/[^/]+(?:\/|$)/i;
  const LEFT_SIDEBAR_SELECTOR = '#left-sidebar-container';

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

  const config = normalizeConfig(CONFIG);
  const style = ensureStyle();
  const html = document.documentElement;
  let sidebarSyncScheduled = false;
  let domReadySidebarSync = false;
  let sidebarObserver;

  style.textContent = buildStyles();

  syncRouteState();
  installRouteSyncHooks();
  installLeftSidebarObserver();

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
    width: max(
      1120px,
      min(var(--reddit-fluid-width), ${gutteredWidth})
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
})();
