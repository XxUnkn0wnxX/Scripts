// ==UserScript==
// @name         GitHub Fluid Width
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.0
// @description  Widens GitHub content on desktop while preserving native sidebars and responsive layouts. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js
// @match        https://github.com/*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

(() => {
  'use strict';

  const STYLE_ID = 'github-fluid-width-style';
  const ROOT_ATTR = 'data-github-fluid-width';
  const INSTANCE_FLAG = '__githubFluidWidthInstalled';
  const SYNC_EVENT = 'github-fluid-width:sync';
  const GENERIC_NATIVE_FLOOR_PX = 1280;
  const DASHBOARD_NATIVE_FLOOR_PX = 1332;

  /*** CONFIG ***/
  // Same starting percentage and gutter as Reddit Fluid Width; decimals work.
  // Percentages use the available content area after any native in-page rail.
  // Already fluid code/file/log workspaces keep their native width.
  const CONFIG = Object.freeze({
    contentWidthPercent: 95,
    minGutterPx: 32,
  });

  if (window[INSTANCE_FLAG]) {
    window.dispatchEvent(new Event(SYNC_EVENT));
    return;
  }
  window[INSTANCE_FLAG] = true;

  const percent = finiteClamp(CONFIG.contentWidthPercent, 95, 1, 100);
  const gutter = Math.round(finiteClamp(CONFIG.minGutterPx, 32, 16, 128));
  const css = buildStyles();
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = css;
  let scheduled = false;
  let lastPath;

  sync();
  installNavigationHooks();

  // React/Turbo may replace whole regions or the head. CSS handles new matching
  // elements directly; this observer only repairs our style or a missed route.
  new MutationObserver(() => {
    if (!style.isConnected || location.pathname !== lastPath) scheduleSync();
  }).observe(document, {childList: true, subtree: true});

  function finiteClamp(value, fallback, min, max) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(min, Math.min(max, number)) : fallback;
  }

  function routeFor(pathname) {
    const path = String(pathname).replace(/\/+$/, '') || '/';
    if (path === '/' || path === '/dashboard') return 'dashboard';
    if (/^\/orgs\/[^/]+\/discussions(?:\/\d+)?$/i.test(path)) {
      return /\/\d+$/.test(path) ? 'discussion' : 'discussions';
    }

    const parts = path.slice(1).split('/');
    const reserved = /^(?:settings|login|logout|sessions|signup|join|search|explore|marketplace|notifications|pulls|issues|discussions|dashboard|orgs|organizations|enterprises|account|accounts|apps|codespaces|copilot|features|topics|trending|collections|sponsors|pricing|about|security|site|contact|new|import)$/i;
    if (reserved.test(parts[0])) return '';
    if (parts.length === 1) return 'profile';
    if (parts.length === 2) return 'repository';

    const section = parts[2];
    const tail = parts.slice(3);
    if (section === 'tree' || section === 'blob') return tail.length ? 'code' : '';
    if (section === 'commits') return 'commits';
    if (section === 'branches' && (!tail.length || (tail.length === 1 && /^(active|stale|all)$/.test(tail[0])))) return 'branches';
    if (section === 'pulls' && !tail.length) return 'lists';
    if (section === 'issues') {
      if (!tail.length) return 'lists';
      if (tail.length === 1 && /^\d+$/.test(tail[0])) return 'issue';
    }
    if (section === 'pull' && /^\d+$/.test(tail[0] || '')) {
      if (tail.length === 1) return 'pull';
      if (tail.length === 2 && /^(?:files|changes)$/.test(tail[1])) return 'pull-files';
    }
    if (section === 'discussions') {
      if (!tail.length) return 'discussions';
      if (tail.length === 1 && /^\d+$/.test(tail[0])) return 'discussion';
    }
    if (section === 'actions') {
      if (!tail.length || (tail.length === 2 && tail[0] === 'workflows')) return 'actions';
      if (tail[0] === 'runs' && /^\d+$/.test(tail[1] || '') &&
          (tail.length === 2 || (tail.length === 4 && tail[2] === 'job' && /^\d+$/.test(tail[3])))) return 'action-run';
    }
    return '';
  }

  function buildStyles() {
    const scoped = (route, selector) => `html[${ROOT_ATTR}="${route}"] ${selector}`;
    const widthFor = (nativeFloor) => `min(100%, max(${nativeFloor}px, min(${percent}%, calc(100% - ${gutter}px - ${gutter}px))))`;
    const wrapper = '[class*="prc-PageLayout-PageLayoutWrapper-"]';
    const content = '[class*="prc-PageLayout-Content-"]';
    const overview = 'react-app[app-name="code-view"] #repos-split-pane-content > .container-xl';
    const listApp = 'react-app:is([app-name="repo"], [app-name="issues-react"])';
    const discussionList = 'main .container-xl.p-responsive:has(> .container-xl > .Layout)';
    const discussionThread = 'main .container-xl.p-responsive:has(> #discussion_bucket)';
    const targets = [
      scoped('repository', overview),
      scoped('commits', `react-app[app-name="repo"] ${wrapper}[data-width="xlarge"]`),
      scoped('branches', `react-app[app-name="repos-branches"] ${wrapper}[data-width="xlarge"]`),
      scoped('lists', `${listApp} [class*="SidebarPageLayout-module__HeaderInner__"][data-width="xlarge"]`),
      scoped('lists', `${listApp} ${content}[data-width="xlarge"]`),
      scoped('issue', 'react-app[app-name="issues-react"] [class*="ContentWrapper-module__contentContainer__"]'),
      scoped('pull', '#diff-comparison-viewer-container.container-xl'),
      scoped('discussions', discussionList),
      scoped('discussion', discussionThread),
      scoped('actions', '#repo-content-pjax-container .PageLayout-content-centered-xl > .container-xl'),
      scoped('profile', 'body.page-profile main > .container-xl:has(> .Layout)'),
    ];
    const dashboard = scoped('dashboard', '.feed-content:has(#dashboard)');
    const dashboardMain = `${dashboard} > .feed-main`;
    const dashboardRightRail = `${dashboard} > .feed-right-sidebar`;
    const innerCaps = [
      scoped('repository', `${overview} ${content}[data-width="large"]`),
      scoped('pull', '#diff-comparison-viewer-container [class*="Conversations-module__content__"]'),
      scoped('pull', `#diff-comparison-viewer-container [class*="Conversations-module__content__"] > ${content}`),
      scoped('discussions', `${discussionList} > .container-xl`),
      scoped('actions', '#repo-content-pjax-container .PageLayout-content-centered-xl'),
    ];
    return `
@media (min-width: 1472px) {
  ${targets.join(',\n  ')} {
    width: ${widthFor(GENERIC_NATIVE_FLOOR_PX)} !important;
    max-width: none !important;
    margin-inline: auto !important;
    box-sizing: border-box !important;
  }

  ${dashboard} {
    width: ${widthFor(DASHBOARD_NATIVE_FLOOR_PX)} !important;
    max-width: none !important;
    margin-inline: auto !important;
    box-sizing: border-box !important;
  }

  ${innerCaps.join(',\n  ')} {
    max-width: none !important;
  }

  /* This older discussion layout uses 75/25 percent columns. Retain its
     320px desktop sidebar (25% of the native 1280px shell), growing the body. */
  ${scoped('discussion', '#discussion_bucket > #partial-discussion-sidebar')} {
    width: 320px !important;
  }
  ${scoped('discussion', '#discussion_bucket > .col-md-9')} {
    width: calc(100% - 320px) !important;
    min-width: 0 !important;
  }
}

/* GitHub's 336px left rail plus the native 1332px dashboard shell first fit
   at 1668px. Below that boundary, leave the feed's internal flex sizing alone. */
@media (min-width: 1668px) {
  ${dashboardMain} {
    /* Let the feed use the width released by the outer workspace. */
    flex: 1 1 0 !important;
    width: auto !important;
    max-width: none !important;
    min-width: 0 !important;
  }

  ${dashboardRightRail} {
    /* The native 1332px shell renders this rail at 312px after flex sizing. */
    flex: 0 0 312px !important;
    width: 312px !important;
  }
}
`;
  }

  function sync() {
    scheduled = false;
    const html = document.documentElement;
    if (!html) return;
    lastPath = location.pathname;
    const route = routeFor(lastPath);
    if (route) {
      if (html.getAttribute(ROOT_ATTR) !== route) html.setAttribute(ROOT_ATTR, route);
    } else {
      html.removeAttribute(ROOT_ATTR);
    }
    if (!style.isConnected) {
      // One owned node survives head replacement and Turbo's cached snapshots.
      const previous = document.getElementById(STYLE_ID);
      if (previous && previous !== style) previous.remove();
      (document.head || html).appendChild(style);
    }
  }

  function scheduleSync() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(sync);
  }

  function installNavigationHooks() {
    for (const name of ['pushState', 'replaceState']) {
      const original = history[name];
      history[name] = function (...args) {
        const result = original.apply(this, args);
        sync();
        return result;
      };
    }
    for (const event of ['popstate', 'pageshow', SYNC_EVENT]) {
      window.addEventListener(event, sync, true);
    }
    for (const event of ['DOMContentLoaded', 'turbo:load', 'turbo:render', 'pjax:end']) {
      document.addEventListener(event, sync, true);
    }
  }
})();
