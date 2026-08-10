// ==UserScript==
// @name         Reddit Fluid Width
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.0
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
  const HISTORY_PATCH_FLAG = '__redditFluidWidthHistoryPatched';
  const ROUTE_RE = /^\/r\/[^/]+\/comments\/[^/]+(?:\/|$)/i;

  /*** CONFIG ***/
  // Set 85-95 here for narrower/wider post containers.
  // true (default) pins the right edge at 100%/0px; false centers the whole grid.
  const CONFIG = Object.freeze({
    contentWidthPercent: 95,
    minGutterPx: 32,
    pinRightSidebar: true,
  });

  const config = normalizeConfig(CONFIG);
  const style = ensureStyle();
  const html = document.documentElement;
  style.textContent = buildStyles();

  syncRouteState();
  installRouteSyncHooks();

  function normalizeConfig(source) {
    const percentRaw = Number(source?.contentWidthPercent);
    const gutterRaw = Number(source?.minGutterPx);
    const pinRightSidebar = source?.pinRightSidebar;

    const contentWidthPercent = Number.isFinite(percentRaw)
      ? Math.max(1, Math.min(100, percentRaw))
      : 95;

    const minGutterPx = Number.isFinite(gutterRaw)
      ? Math.max(16, Math.min(128, Math.round(gutterRaw)))
      : 32;

    return Object.freeze({
      contentWidthPercent,
      minGutterPx,
      pinRightSidebar: typeof pinRightSidebar === 'boolean' ? pinRightSidebar : true,
    });
  }

  function syncRouteState() {
    const isPostRoute = isRedditPostCommentsRoute(location.pathname);
    if (isPostRoute) {
      html.setAttribute(ROOT_ATTR, '');
      return;
    }

    html.removeAttribute(ROOT_ATTR);
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
  }
})();
