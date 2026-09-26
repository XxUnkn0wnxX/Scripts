// ==UserScript==
// @name         GitHub Fluid Width
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.0
// @description  Controls GitHub workspace widths with live settings while preserving native sidebars and responsive layouts. Vibe coded with OpenAI.
// @homepageURL  https://github.com/XxUnkn0wnxX/Scripts
// @supportURL   https://discord.gg/slayersicerealm
// @author       XxUnkn0wnxX
// @license      AGPL-3.0-or-later
// @updateURL    https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js
// @downloadURL  https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js
// @match        https://github.com/*
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

  const STYLE_ID = 'github-fluid-width-style';
  const ACTIVE_ATTR = 'data-github-fluid-width-active';
  const OWNER_ATTR = 'data-github-fluid-width-owner';
  const RELEASE_ATTR = 'data-github-fluid-width-release';
  const FILL_ATTR = 'data-github-fluid-width-fill';
  const FLOOR_VAR = '--github-fluid-width-native-floor';
  const INSTANCE_FLAG = '__githubFluidWidthInstalled';
  const SYNC_EVENT = 'github-fluid-width:sync';
  const MIN_VIEWPORT_PX = 1472;
  const MIN_NATIVE_FLOOR_PX = 512;
  const MAX_NATIVE_FLOOR_PX = 2048;
  const FULL_WORKSPACE_FLOOR_PX = 1012;
  const SEARCH_MAIN_FLOOR_PX = 768;

  /*** CONFIG ***/
  // Same starting percentage and gutter as Reddit Fluid Width; decimals work.
  // Percentages use the available content area after any external in-page rail.
  // Full workspaces use this percentage too. Set false to retain their native
  // full width while still widening GitHub's explicitly capped layouts.
  const CONFIG = Object.freeze({
    contentWidthPercent: 95,
    minGutterPx: 32,
    overrideFullWidthPages: true,
  });

  const SETTINGS_SCHEMA_VERSION = 1;
  const SETTINGS_DEFAULTS = CONFIG;
  const SETTINGS_KEYS = Object.freeze({
    contentWidthPercent: 'github-fluid-width.contentWidthPercent',
    minGutterPx: 'github-fluid-width.minGutterPx',
    overrideFullWidthPages: 'github-fluid-width.overrideFullWidthPages',
    schemaVersion: 'github-fluid-width.schemaVersion',
  });
  const SETTINGS_CONFIG_KEYS = Object.freeze([
    'contentWidthPercent',
    'minGutterPx',
    'overrideFullWidthPages',
  ]);

  // These are GitHub layout primitives, rather than a list of URL routes. The
  // scan intentionally does not treat arbitrary cards or every max-width as a
  // workspace limiter.
  const CANDIDATE_SELECTOR = [
    '.container-xl',
    '.container-lg',
    '[class*="prc-PageLayout-PageLayoutWrapper-"][data-width="xlarge"]',
    '[class*="prc-PageLayout-Content-"][data-width="xlarge"]',
    '[class*="SidebarPageLayout-module__HeaderInner__"][data-width="xlarge"]',
    '[class*="ContentWrapper-module__contentContainer__"]',
    '[class*="prc-PageLayout-ContentWrapper-"].px-2.mx-auto',
    '.PageLayout-content-centered-xl',
  ].join(', ');
  const NESTED_LIMITER_SELECTOR = [
    '.container-xl',
    '.container-lg',
    '[class*="prc-PageLayout-Content-"][data-width="large"]',
    '[class*="Conversations-module__content__"]',
    '.Layout-main-centered-xl',
    'article.markdown-body.entry-content.container-lg',
  ].join(', ');
  const GLOBAL_ISSUES_CONTENT_SELECTOR = '[class*="prc-PageLayout-Content-"][data-width="full"]';
  const FULL_PRIMER_CONTENT_SELECTOR = [
    '[class*="prc-PageLayout-ContentWrapper-"]',
    '> [class*="prc-PageLayout-Content-"][data-width="full"]',
  ].join(' ');
  const ACTIONS_SPLIT_CONTENT_SELECTOR = '.PageLayout-content[data-target="split-page-layout.content"]';
  const LEGACY_PR_FILES_SELECTOR = '#repo-content-pjax-container #files_bucket.files-bucket';
  const SEARCH_TWO_COLUMN_SELECTOR = '[class*="Search-module__twoColumnOuter__"]';
  const SEARCH_MAIN_SELECTOR = '[class*="Search-module__mainColumn__"]';
  const SEARCH_RIGHT_SIDEBAR_SELECTOR = '[class*="Search-module__rightSidebar__"]';
  const BLOCKED_ANCESTOR_SELECTOR = [
    'nav',
    'aside',
    '[role="complementary"]',
    'dialog',
    '[role="dialog"]',
    '[role="menu"]',
    '[role="listbox"]',
    '[popover]',
    '.dropdown-menu',
    '.Layout-sidebar',
    '.PageLayout-pane',
    '[data-target$=".pane"]',
    '[data-component="PageLayout.Pane"]',
    '[data-component="PageLayout.Sidebar"]',
    '[class*="Popover-module__"]',
    '[class*="Overlay-module__"]',
    '[class*="Drawer-module__"]',
    '[class*="Dialog-module__"]',
  ].join(', ');
  const CONTROL_SELECTOR = 'input, select, textarea, button, option, [contenteditable="true"]';
  const SIDEBAR_PAGE_ROOT_SELECTOR = [
    '[class*="SidebarPageLayout-module__PageLayoutRoot__"]',
    '[class*="SidebarPageLayout-module__Root__"]',
  ].join(', ');

  if (window[INSTANCE_FLAG]) {
    window.dispatchEvent(new Event(SYNC_EVENT));
    return;
  }
  window[INSTANCE_FLAG] = true;

  let percent = finiteClamp(CONFIG.contentWidthPercent, 95, 1, 100);
  let gutter = Math.round(finiteClamp(CONFIG.minGutterPx, 32, 16, 128));
  let overrideFullWidthPages = CONFIG.overrideFullWidthPages !== false;
  const desktopQuery = window.matchMedia(`(min-width: ${MIN_VIEWPORT_PX}px)`);
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = buildStyles();
  let scheduled = false;

  const settingsController = createSettingsController({
    runtime: {
      GM_getValue: typeof GM_getValue === 'function' ? GM_getValue : undefined,
      GM_setValue: typeof GM_setValue === 'function' ? GM_setValue : undefined,
      GM_registerMenuCommand: typeof GM_registerMenuCommand === 'function' ? GM_registerMenuCommand : undefined,
      GM: typeof GM === 'object' ? GM : undefined,
      // Keep Firefox's native timer receiver when the controller binds its
      // injected runtime methods.
      setTimeout: (callback, delay) => window.setTimeout(callback, delay),
      clearTimeout: (timer) => window.clearTimeout(timer),
    },
    document,
    defaults: CONFIG,
    onChange: applySettings,
  });

  sync();
  installNavigationHooks();
  installObserver();
  settingsController.ensureMounted();
  document.addEventListener('DOMContentLoaded', () => settingsController.ensureMounted(), {once: true, capture: true});
  settingsController.initialize().catch(() => {});

  function applySettings(next) {
    percent = finiteClamp(next.contentWidthPercent, 95, 1, 100);
    gutter = Math.round(finiteClamp(next.minGutterPx, 32, 16, 128));
    overrideFullWidthPages = next.overrideFullWidthPages !== false;
    style.textContent = buildStyles();
    scheduleSync();
  }

  function finiteClamp(value, fallback, min, max) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(min, Math.min(max, number)) : fallback;
  }

  function buildStyles() {
    const width = `min(100%, max(var(${FLOOR_VAR}), min(${percent}%, calc(100% - ${gutter}px - ${gutter}px))))`;
    // Search's results lane and optional 25% sidebar are flex siblings. A
    // generic percentage on the lane is resolved against both lanes, then
    // flex-shrunk back to native. These formulas resolve within the native
    // remaining lane: 75% of the two-column content box, minus its 24px gap;
    // or the full content box without the optional sidebar.
    const searchWidth = (trackPercent, chrome) => {
      const ratio = percent / 100;
      const track = `calc(${trackPercent}% - ${chrome}px)`;
      const requested = `calc(${trackPercent * ratio}% - ${chrome * ratio}px)`;
      const guttered = `calc(${trackPercent}% - ${chrome + gutter + gutter}px)`;
      return `min(${track}, max(var(${FLOOR_VAR}), min(${requested}, ${guttered})))`;
    };
    const searchWidthWithSidebar = searchWidth(75, 24);
    const searchWidthWithoutSidebar = searchWidth(100, 0);
    const active = `html[${ACTIVE_ATTR}]`;
    return `
@media (min-width: ${MIN_VIEWPORT_PX}px) {
  ${active} [${OWNER_ATTR}] {
    width: ${width} !important;
    max-width: none !important;
    margin-inline: auto !important;
    box-sizing: border-box !important;
  }

  /* These are flex items in otherwise full workspaces. Their native grow rule
     would consume the configured gutters after width is applied. */
  ${active} [${OWNER_ATTR}="full-workspace"],
  ${active} [${OWNER_ATTR}^="search-main"] {
    flex: 0 1 auto !important;
    min-width: 0 !important;
  }

  ${active} [${OWNER_ATTR}="search-main-with-sidebar"] {
    width: ${searchWidthWithSidebar} !important;
  }

  ${active} [${OWNER_ATTR}="search-main-full"] {
    width: ${searchWidthWithoutSidebar} !important;
  }

  /* A release expands the shell for a child owner; it is never a second
     percentage calculation. */
  ${active} [${RELEASE_ATTR}] {
    max-width: none !important;
  }

  /* Nested content limiters fill their already-fluid owner. */
  ${active} [${FILL_ATTR}] {
    width: 100% !important;
    max-width: none !important;
    box-sizing: border-box !important;
  }

  /* Settings feature cards use a direct trailing primary-CTA wrapper. Keep
     that intrinsic button at the widened row's trailing edge. */
  ${active} #options_bucket .flash > .d-flex.flex-md-row.flex-column.flex-md-items-center.flex-items-start > :has(> .btn.btn-primary),
  ${active} #options_bucket .flash > .d-flex.flex-md-row.flex-column.flex-md-items-center.flex-items-start > :has(> form > .btn.btn-primary) {
    margin-inline-start: auto !important;
  }

  /* Older discussion pages retain their native 320px desktop rail. */
  ${active} [${OWNER_ATTR}] #discussion_bucket > #partial-discussion-sidebar {
    width: 320px !important;
  }
  ${active} [${OWNER_ATTR}] #discussion_bucket > .col-md-9 {
    width: calc(100% - 320px) !important;
    min-width: 0 !important;
  }
}

/* GitHub's dashboard rail fits beside its native 1332px shell from 1668px.
   Leave the native flex sizing alone below that point. */
@media (min-width: 1668px) {
  ${active} .feed-content[${OWNER_ATTR}] > .feed-main {
    flex: 1 1 0 !important;
    width: auto !important;
    max-width: none !important;
    min-width: 0 !important;
  }

  ${active} .feed-content[${OWNER_ATTR}] > .feed-right-sidebar {
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

    ensureStyle(html);
    // Measure only native styles. Attribute removal and restoration happen in
    // this one task, before the browser can paint an intermediate layout.
    html.removeAttribute(ACTIVE_ATTR);
    clearOwnedMarkers();
    if (document.body) classifyNativeLayout();
    html.setAttribute(ACTIVE_ATTR, '');
  }

  function ensureStyle(html) {
    const previous = document.getElementById(STYLE_ID);
    if (previous && previous !== style) previous.remove();
    if (!style.isConnected) (document.head || html).appendChild(style);
  }

  function clearOwnedMarkers() {
    document.querySelectorAll(`[${OWNER_ATTR}], [${RELEASE_ATTR}], [${FILL_ATTR}]`).forEach((element) => {
      element.removeAttribute(OWNER_ATTR);
      element.removeAttribute(RELEASE_ATTR);
      element.removeAttribute(FILL_ATTR);
      element.style.removeProperty(FLOOR_VAR);
    });
  }

  function classifyNativeLayout() {
    const candidates = Array.from(document.querySelectorAll(CANDIDATE_SELECTOR))
      .filter(isEligibleCandidate);

    applyDashboardAdapter();
    applyGlobalIssuesAdapter(candidates);
    applyCenteredShellAdapters(candidates);
    applySidebarPageLanes(candidates);
    applyPrimerAndIssueOwners(candidates);
    applyGenericCandidates(candidates);
    applyFullWidthWorkspaceAdapters();
    applyNestedFillAdapters();
  }

  function applyDashboardAdapter() {
    document.querySelectorAll('.feed-content').forEach((element) => {
      if (!element.querySelector('#dashboard') || hasBlockedAncestor(element)) return;
      const metrics = nativeMetrics(element, 1332);
      if (metrics) markOwner(element, metrics.floor, 'dashboard');
    });
  }

  function applyGlobalIssuesAdapter(candidates) {
    candidates.filter(isGlobalIssuesWrapper).forEach((wrapper) => {
      const content = Array.from(wrapper.children).find((element) => element.matches(
        GLOBAL_ISSUES_CONTENT_SELECTOR
      ));
      if (!content || !isInPageHost(content) || hasBlockedAncestor(content)) return;

      const wrapperMetrics = nativeMetrics(wrapper);
      if (!wrapperMetrics) return;
      const contentFloor = nativeContentFloor(wrapper, wrapperMetrics.floor);
      if (!isReasonableFloor(contentFloor)) return;

      // The global Issues wrapper is a flex item beside a 297px pane. Making
      // it the owner lets flex-shrink consume its gutters. Release that
      // rail-aware shell and size its padded direct content instead.
      markRelease(wrapper);
      markOwner(content, contentFloor, 'global-issues-content');
    });
  }

  function applyCenteredShellAdapters(candidates) {
    candidates.filter((element) => element.matches('.PageLayout-content-centered-xl')).forEach((shell) => {
      const child = Array.from(shell.children).find((element) => element.matches('.container-xl'));
      if (!child || !isEligibleCandidate(child)) return;
      const metrics = nativeMetrics(child);
      if (!metrics) return;
      // Actions has a rail-inclusive 1616px shell and a 1280px content cap.
      // Release the first and apply the percentage once to the latter.
      markRelease(shell);
      markOwner(child, metrics.floor, 'actions-content');
    });
  }

  function applySidebarPageLanes(candidates) {
    candidates.forEach((element) => {
      if (!element.closest(SIDEBAR_PAGE_ROOT_SELECTOR)) return;
      if (!element.matches(
        '[class*="SidebarPageLayout-module__HeaderInner__"][data-width="xlarge"], ' +
        '[class*="prc-PageLayout-Content-"][data-width="xlarge"]'
      )) return;
      if (hasOwnerAncestor(element)) {
        markFillIfCapped(element);
        return;
      }
      const metrics = nativeMetrics(element);
      if (metrics) markOwner(element, metrics.floor, 'sidebar-page-lane');
    });
  }

  function applyPrimerAndIssueOwners(candidates) {
    candidates.forEach((element) => {
      if (hasRole(element)) return;
      if (!element.matches(
        '[class*="prc-PageLayout-PageLayoutWrapper-"][data-width="xlarge"], ' +
        '[class*="ContentWrapper-module__contentContainer__"]'
      )) return;
      if (hasOwnerAncestor(element)) {
        markFillIfCapped(element);
        return;
      }
      const metrics = nativeMetrics(element);
      if (metrics) markOwner(element, metrics.floor, 'component');
    });
  }

  function applyGenericCandidates(candidates) {
    for (const element of candidates) {
      if (hasRole(element)) continue;
      if (isRenderedDocument(element)) {
        markFillIfCapped(element);
        continue;
      }

      const metrics = nativeMetrics(element);
      if (!metrics) continue;

      // A semantic header/content lane can be selected before its containing
      // legacy limiter. Release that parent so siblings remain independent.
      if (element.querySelector(`[${OWNER_ATTR}]`)) {
        markRelease(element);
        continue;
      }

      if (hasOwnerAncestor(element)) {
        markFillIfCapped(element);
      } else {
        // A child of a released shell is the percentage owner. This is the
        // Action-shell relationship; generic roots use the same safe rule.
        markOwner(element, metrics.floor, 'workspace');
      }
    }
  }

  function applyFullWidthWorkspaceAdapters() {
    if (!overrideFullWidthPages) return;

    document.querySelectorAll(ACTIONS_SPLIT_CONTENT_SELECTOR).forEach((element) => {
      if (!isEligibleFullWorkspace(element)) return;
      markOwner(element, FULL_WORKSPACE_FLOOR_PX, 'actions-workspace');
    });

    document.querySelectorAll(LEGACY_PR_FILES_SELECTOR).forEach((element) => {
      if (!isEligibleFullWorkspace(element)) return;
      // Guest PR Files uses this full-width legacy bucket rather than Primer's
      // direct Content. Its diff scrollers remain nested, unmarked surfaces.
      markOwner(element, FULL_WORKSPACE_FLOOR_PX, 'legacy-pr-files');
    });

    document.querySelectorAll(FULL_PRIMER_CONTENT_SELECTOR).forEach((content) => {
      if (!isEligibleFullWorkspace(content) || isGlobalIssuesContent(content)) return;
      const twoColumn = directChildMatching(content, SEARCH_TWO_COLUMN_SELECTOR);
      if (twoColumn) {
        applySearchMainOwner(twoColumn);
        return;
      }
      // Files, folders, rendered Markdown, and PR Files place this direct
      // full Content in the remaining track beside their native pane/rail.
      markOwner(content, FULL_WORKSPACE_FLOOR_PX, 'full-workspace');
    });
  }

  function applySearchMainOwner(twoColumn) {
    const main = directChildMatching(twoColumn, SEARCH_MAIN_SELECTOR);
    const sidebar = directChildMatching(twoColumn, SEARCH_RIGHT_SIDEBAR_SELECTOR);
    if (!main || !isEligibleFullWorkspace(main)) return;
    // The right search pane is a sibling with its own responsive width. Size
    // only the results lane, never the full wrapper that contains both panes.
    // When it is absent or hidden, the results lane owns the full padded row.
    markOwner(main, SEARCH_MAIN_FLOOR_PX,
      isVisibleLayoutElement(sidebar) ? 'search-main-with-sidebar' : 'search-main-full');
  }

  function applyNestedFillAdapters() {
    // Code views are already workspace-fluid. Only the renderer's Markdown
    // reading measure is capped; text, CSV, PDF, virtualized code, and logs
    // have no matching cap and receive no marker.
    document.querySelectorAll('article.markdown-body.entry-content.container-lg').forEach((element) => {
      if (element.closest('#repos-split-pane-content')) markFillIfCapped(element);
    });

    document.querySelectorAll(`[${OWNER_ATTR}]`).forEach((owner) => {
      owner.querySelectorAll(NESTED_LIMITER_SELECTOR).forEach((element) => {
        if (element === owner || element.hasAttribute(OWNER_ATTR) || hasBlockedAncestor(element)) return;
        markFillIfCapped(element);
      });
    });
  }

  function isEligibleCandidate(element) {
    return isInPageHost(element) && !hasBlockedAncestor(element) && !element.matches(CONTROL_SELECTOR);
  }

  function isInPageHost(element) {
    return Boolean(element.closest('main, [role="main"], react-app, #repo-content-pjax-container'));
  }

  function hasBlockedAncestor(element) {
    return Boolean(element.closest(BLOCKED_ANCESTOR_SELECTOR));
  }

  function isRenderedDocument(element) {
    return element.matches('article.markdown-body.entry-content.container-lg') &&
      Boolean(element.closest('#repos-split-pane-content'));
  }

  function isGlobalIssuesWrapper(element) {
    return element.matches('[class*="prc-PageLayout-ContentWrapper-"].px-2.mx-auto');
  }

  function isGlobalIssuesContent(element) {
    return element.matches(GLOBAL_ISSUES_CONTENT_SELECTOR) && element.parentElement &&
      isGlobalIssuesWrapper(element.parentElement);
  }

  function isEligibleFullWorkspace(element) {
    return isEligibleCandidate(element) && !hasRole(element) && !hasOwnerAncestor(element) &&
      !element.querySelector(`[${OWNER_ATTR}]`);
  }

  function directChildMatching(parent, selector) {
    return Array.from(parent.children).find((element) => element.matches(selector)) || null;
  }

  function isVisibleLayoutElement(element) {
    if (!element || !element.isConnected) return false;
    const computed = window.getComputedStyle(element);
    return computed.display !== 'none' && computed.visibility !== 'hidden' &&
      element.getClientRects().length > 0 && element.getBoundingClientRect().width > 0;
  }

  function isSearchMainWorkspace(element) {
    if (!element.matches(SEARCH_MAIN_SELECTOR)) return false;
    const twoColumn = element.parentElement;
    return Boolean(twoColumn && isSearchTwoColumnWorkspace(twoColumn));
  }

  function isSearchSidebarWorkspace(element) {
    return element.matches(SEARCH_RIGHT_SIDEBAR_SELECTOR) && element.parentElement &&
      isSearchTwoColumnWorkspace(element.parentElement);
  }

  function isSearchTwoColumnWorkspace(element) {
    const content = element.parentElement;
    return Boolean(content && element.matches(SEARCH_TWO_COLUMN_SELECTOR) &&
      content.matches(GLOBAL_ISSUES_CONTENT_SELECTOR) &&
      content.parentElement && content.parentElement.matches('[class*="prc-PageLayout-ContentWrapper-"]'));
  }

  function isRelevantFullWorkspaceInsertion(element) {
    if (element.matches(ACTIONS_SPLIT_CONTENT_SELECTOR) ||
        element.matches(LEGACY_PR_FILES_SELECTOR) ||
        element.matches(FULL_PRIMER_CONTENT_SELECTOR) ||
        isSearchMainWorkspace(element) ||
        isSearchSidebarWorkspace(element)) return true;
    if (element.querySelector(
      `${FULL_PRIMER_CONTENT_SELECTOR}, ${ACTIONS_SPLIT_CONTENT_SELECTOR}, ${LEGACY_PR_FILES_SELECTOR}`
    )) return true;
    return Array.from(element.querySelectorAll(`${SEARCH_MAIN_SELECTOR}, ${SEARCH_RIGHT_SIDEBAR_SELECTOR}`))
      .some((child) => isSearchMainWorkspace(child) || isSearchSidebarWorkspace(child));
  }

  function hasRole(element) {
    return element.hasAttribute(OWNER_ATTR) || element.hasAttribute(RELEASE_ATTR) || element.hasAttribute(FILL_ATTR);
  }

  function hasOwnerAncestor(element) {
    return Boolean(element.parentElement && element.parentElement.closest(`[${OWNER_ATTR}]`));
  }

  function nativeMetrics(element, knownFloor) {
    if (!element.isConnected || hasBlockedAncestor(element)) return null;
    const computed = window.getComputedStyle(element);
    if (!/^(?:block|flex|grid|flow-root)$/.test(computed.display)) return null;
    if (computed.visibility === 'hidden' || element.getClientRects().length === 0) return null;

    const observedFloor = pixelValue(computed.maxWidth);
    if (isReasonableFloor(observedFloor)) return {floor: observedFloor};

    // At a narrow first load, GitHub expresses desktop limiters as 100%.
    // Metadata supplies only known component caps in that responsive state;
    // an explicit `none` remains untouched when the viewport later widens.
    if (computed.maxWidth === '100%') {
      const responsiveFloor = knownFloor || knownFloorFor(element);
      if (isReasonableFloor(responsiveFloor)) return {floor: responsiveFloor};
    }
    return null;
  }

  function nativeContentFloor(container, outerFloor) {
    const computed = window.getComputedStyle(container);
    if (computed.boxSizing !== 'border-box') return outerFloor;
    const inlineChrome = [
      computed.paddingInlineStart || computed.paddingLeft,
      computed.paddingInlineEnd || computed.paddingRight,
      computed.borderInlineStartWidth || computed.borderLeftWidth,
      computed.borderInlineEndWidth || computed.borderRightWidth,
    ].reduce((total, value) => total + (pixelValue(value) || 0), 0);
    return outerFloor - inlineChrome;
  }

  function knownFloorFor(element) {
    if (element.matches('.container-xl')) return 1280;
    if (element.matches('.container-lg')) return 1012;
    if (element.matches('[class*="prc-PageLayout-ContentWrapper-"].px-2.mx-auto')) return 1400;
    if (element.matches('[data-width="xlarge"], [class*="ContentWrapper-module__contentContainer__"]')) return 1280;
    return null;
  }

  function pixelValue(value) {
    if (!String(value).endsWith('px')) return null;
    const number = Number.parseFloat(value);
    return Number.isFinite(number) ? number : null;
  }

  function isReasonableFloor(value) {
    return Number.isFinite(value) && value >= MIN_NATIVE_FLOOR_PX && value <= MAX_NATIVE_FLOOR_PX;
  }

  function markOwner(element, floor, role) {
    if (!isReasonableFloor(floor) || hasRole(element) || hasOwnerAncestor(element) ||
        element.querySelector(`[${OWNER_ATTR}]`)) return;
    element.setAttribute(OWNER_ATTR, role);
    element.style.setProperty(FLOOR_VAR, `${floor}px`);
  }

  function markRelease(element) {
    if (hasRole(element) || hasBlockedAncestor(element)) return;
    element.setAttribute(RELEASE_ATTR, '');
  }

  function markFillIfCapped(element) {
    if (hasRole(element) || hasBlockedAncestor(element)) return;
    if (nativeMetrics(element)) element.setAttribute(FILL_ATTR, '');
  }

  function scheduleSync() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(sync);
  }

  function installObserver() {
    new MutationObserver((records) => {
      settingsController.ensureMounted();
      if (!style.isConnected) {
        scheduleSync();
        return;
      }
      for (const record of records) {
        if (isRelevantSearchSidebarRemoval(record)) {
          scheduleSync();
          return;
        }
        for (const node of record.addedNodes) {
          if (isRelevantInsertion(node)) {
            scheduleSync();
            return;
          }
        }
      }
    }).observe(document, {childList: true, subtree: true});
  }

  function isRelevantInsertion(node) {
    if (node.nodeType !== Node.ELEMENT_NODE || node === style || node.id === STYLE_ID) return false;
    return node.matches(CANDIDATE_SELECTOR) ||
      node.matches(NESTED_LIMITER_SELECTOR) ||
      isGlobalIssuesContent(node) ||
      isRelevantFullWorkspaceInsertion(node) ||
      node.matches('.feed-content') ||
      Boolean(node.querySelector(`${CANDIDATE_SELECTOR}, ${NESTED_LIMITER_SELECTOR}, ${GLOBAL_ISSUES_CONTENT_SELECTOR}, .feed-content`));
  }

  function isRelevantSearchSidebarRemoval(record) {
    if (!isSearchTwoColumnWorkspace(record.target)) return false;
    return Array.from(record.removedNodes).some((node) => node.nodeType === Node.ELEMENT_NODE &&
      node.matches(SEARCH_RIGHT_SIDEBAR_SELECTOR));
  }

  function installNavigationHooks() {
    for (const name of ['pushState', 'replaceState']) {
      const original = history[name];
      history[name] = function (...args) {
        const result = original.apply(this, args);
        scheduleSync();
        return result;
      };
    }
    for (const event of ['popstate', 'pageshow', SYNC_EVENT]) {
      window.addEventListener(event, scheduleSync, true);
    }
    for (const event of ['DOMContentLoaded', 'turbo:load', 'turbo:render', 'pjax:end']) {
      document.addEventListener(event, scheduleSync, true);
    }
    const onBreakpointChange = () => scheduleSync();
    if (desktopQuery.addEventListener) desktopQuery.addEventListener('change', onBreakpointChange);
    else desktopQuery.addListener(onBreakpointChange);
  }

  function createSettingsController(options = {}) {
    const runtime = options.runtime || window;
    const settingsDocument = options.document || document;
    const defaults = normalizeSettingsConfig({...SETTINGS_DEFAULTS, ...(options.defaults || {})});
    const onChange = typeof options.onChange === 'function' ? options.onChange : () => {};
    const setTimeoutFn = typeof runtime.setTimeout === 'function' ? runtime.setTimeout.bind(runtime) : setTimeout;
    const clearTimeoutFn = typeof runtime.clearTimeout === 'function' ? runtime.clearTimeout.bind(runtime) : clearTimeout;
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
    let version = 0;
    const keyVersions = new Map();
    const pendingKeys = new Set();
    const readableKeys = new Set();

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
        flushSettings().catch(() => {});
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
        const result = register('GitHub Fluid Width settings', show);
        menuRegistered = true;
        if (result && typeof result.catch === 'function') result.catch(() => {});
      } catch (_) {
        // The launcher remains available if a manager declines menu access.
      }
    }

    function ensureMounted() {
      if (!settingsDocument || typeof settingsDocument.createElement !== 'function') return null;
      if (ui && ui.host && ui.host.isConnected) {
        registerSettingsMenu();
        return ui;
      }
      if (!settingsDocument.body) return null;
      const host = settingsDocument.createElement('div');
      host.id = 'github-fluid-width-settings-host';
      host.style.position = 'fixed';
      host.style.right = '16px';
      host.style.bottom = '16px';
      host.style.zIndex = '20';
      const shadow = typeof host.attachShadow === 'function' ? host.attachShadow({mode: 'open'}) : host;
      shadow.innerHTML = `
        <style>
          :host { all: initial; color: var(--fgColor-default, #1f2328); font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
          *, *::before, *::after { box-sizing: border-box; }
          button, input { font: inherit; }
          button { cursor: pointer; }
          .launcher { border: 1px solid var(--borderColor-default, #d0d7de); border-radius: 999px; background: var(--bgColor-default, #fff); color: inherit; box-shadow: 0 2px 8px rgb(31 35 40 / 18%); padding: 5px 11px; }
          dialog { width: min(420px, calc(100vw - 32px)); max-height: min(640px, calc(100vh - 32px)); margin: auto; border: 1px solid var(--borderColor-default, #d0d7de); border-radius: 8px; background: var(--bgColor-default, #fff); color: inherit; padding: 0; box-shadow: 0 8px 32px rgb(31 35 40 / 28%); }
          dialog::backdrop { background: rgb(31 35 40 / 28%); }
          .panel { overflow: auto; max-height: min(640px, calc(100vh - 32px)); padding: 18px; }
          h2 { font-size: 16px; margin: 0 0 8px; }
          .hint, .status { color: var(--fgColor-muted, #656d76); font-size: 12px; }
          .status { min-height: 1.4em; margin: 12px 0 0; }
          .row { display: grid; gap: 6px; margin: 14px 0; }
          .range-row { display: grid; grid-template-columns: 1fr 88px; align-items: center; }
          input[type="range"] { width: 100%; accent-color: var(--fgColor-accent, #0969da); }
          input[type="number"] { width: 88px; border: 1px solid var(--borderColor-default, #d0d7de); border-radius: 6px; background: var(--bgColor-default, #fff); color: inherit; padding: 4px 6px; }
          .check { display: flex; gap: 8px; align-items: flex-start; }
          .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
          .actions button { border: 1px solid var(--borderColor-default, #d0d7de); border-radius: 6px; background: var(--bgColor-muted, #f6f8fa); color: inherit; padding: 5px 9px; }
          .actions .primary { background: var(--button-primary-bgColor-rest, #1f883d); border-color: var(--button-primary-bgColor-rest, #1f883d); color: #fff; }
        </style>
        <button class="launcher" type="button" title="GitHub Fluid Width settings" aria-label="GitHub Fluid Width settings" aria-haspopup="dialog" aria-controls="github-fluid-width-settings-dialog">Width</button>
        <dialog id="github-fluid-width-settings-dialog" aria-labelledby="github-fluid-width-settings-title">
          <form class="panel">
            <h2 id="github-fluid-width-settings-title">GitHub Fluid Width</h2>
            <p class="hint">Width rules apply from 1472px. A native minimum can limit very low percentages.</p>
            <div class="row">
              <label for="github-fluid-width-percent-range">Content width percentage</label>
              <div class="range-row">
                <input id="github-fluid-width-percent-range" type="range" min="1" max="100" step="0.1" aria-label="Content width percentage">
                <input id="github-fluid-width-percent-number" type="number" min="1" max="100" step="0.1" aria-label="Content width percentage value">
              </div>
            </div>
            <div class="row">
              <label for="github-fluid-width-gutter">Minimum gutter (px)</label>
              <input id="github-fluid-width-gutter" type="number" min="16" max="128" step="1">
            </div>
            <label class="check" for="github-fluid-width-override">
              <input id="github-fluid-width-override" type="checkbox">
              <span>Override full-width pages</span>
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
        launcher: root.querySelector('.launcher'),
        dialog: root.querySelector('dialog'),
        range: root.querySelector('#github-fluid-width-percent-range'),
        percent: root.querySelector('#github-fluid-width-percent-number'),
        gutter: root.querySelector('#github-fluid-width-gutter'),
        override: root.querySelector('#github-fluid-width-override'),
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

    function bindSettingsUi() {
      if (!ui) return;
      ui.launcher.addEventListener('click', show);
      ui.close.addEventListener('click', close);
      ui.reset.addEventListener('click', () => {
        resetDefaults();
        flushSettings().catch(() => {});
      });
      ui.range.addEventListener('input', () => setConfig({contentWidthPercent: ui.range.value}));
      ui.percent.addEventListener('input', () => {
        const value = Number(ui.percent.value);
        if (Number.isFinite(value) && value >= 1 && value <= 100) setConfig({contentWidthPercent: value});
      });
      ui.percent.addEventListener('change', () => {
        if (ui.percent.value !== '') setConfig({contentWidthPercent: ui.percent.value});
        renderSettings({forceNumbers: true});
        flushSettings().catch(() => {});
      });
      ui.percent.addEventListener('blur', () => renderSettings({forceNumbers: true}));
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
      ui.range.addEventListener('change', () => flushSettings().catch(() => {}));
      ui.override.addEventListener('change', () => {
        setConfig({overrideFullWidthPages: ui.override.checked});
        flushSettings().catch(() => {});
      });
      ui.dialog.addEventListener('cancel', (event) => {
        event.preventDefault();
        close();
      });
      ui.dialog.addEventListener('submit', (event) => event.preventDefault());
      ui.dialog.addEventListener('keydown', (event) => {
        if (event.key !== 'Tab') return;
        const focusable = Array.from(ui.dialog.querySelectorAll('button, input, [href], select, textarea'))
          .filter((element) => !element.disabled && element.offsetParent !== null);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = ui.shadow.activeElement || settingsDocument.activeElement;
        if (event.shiftKey && active === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && active === last) {
          event.preventDefault();
          first.focus();
        }
      });
    }

    function show() {
      const mounted = ensureMounted();
      if (!mounted) return;
      lastFocus = ui.shadow.activeElement || settingsDocument.activeElement || ui.launcher;
      renderSettings();
      if (typeof ui.dialog.showModal === 'function') {
        try {
          if (!ui.dialog.open) ui.dialog.showModal();
        } catch (_) {
          ui.dialog.setAttribute('open', '');
        }
      } else {
        ui.dialog.setAttribute('open', '');
      }
      if (ui.range && typeof ui.range.focus === 'function') ui.range.focus();
    }

    function close() {
      if (!ui) return;
      flushSettings().catch(() => {});
      if (typeof ui.dialog.close === 'function' && ui.dialog.open) ui.dialog.close();
      else ui.dialog.removeAttribute('open');
      if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
      else if (ui.launcher && typeof ui.launcher.focus === 'function') ui.launcher.focus();
    }

    function renderSettings(options = {}) {
      if (!ui) return;
      const active = ui.shadow && ui.shadow.activeElement;
      const forceNumbers = options.forceNumbers === true;
      ui.range.value = String(current.contentWidthPercent);
      if (forceNumbers || active !== ui.percent) ui.percent.value = String(current.contentWidthPercent);
      if (forceNumbers || active !== ui.gutter) ui.gutter.value = String(current.minGutterPx);
      ui.override.checked = current.overrideFullWidthPages;
      ui.status.textContent = storageError && storageState === 'write-error'
        ? storageError.message || statusText(storageState)
        : statusText(storageState);
      ui.status.dataset.state = storageState;
    }

    return {initialize, ensureMounted, show, close, setConfig, resetDefaults, flush: flushSettings};
  }

  function normalizeSettingValue(key, value, fallback) {
    if (key === 'contentWidthPercent') return finiteClamp(value, fallback, 1, 100);
    if (key === 'minGutterPx') return Math.round(finiteClamp(value, fallback, 16, 128));
    if (key === 'overrideFullWidthPages') return value !== false;
    return value;
  }

  function normalizeSettingsConfig(values) {
    return {
      contentWidthPercent: normalizeSettingValue('contentWidthPercent', values.contentWidthPercent, SETTINGS_DEFAULTS.contentWidthPercent),
      minGutterPx: normalizeSettingValue('minGutterPx', values.minGutterPx, SETTINGS_DEFAULTS.minGutterPx),
      overrideFullWidthPages: normalizeSettingValue('overrideFullWidthPages', values.overrideFullWidthPages, SETTINGS_DEFAULTS.overrideFullWidthPages),
    };
  }

  function copySettingsConfig(values) {
    return {
      contentWidthPercent: values.contentWidthPercent,
      minGutterPx: values.minGutterPx,
      overrideFullWidthPages: values.overrideFullWidthPages,
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
