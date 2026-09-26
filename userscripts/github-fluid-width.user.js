// ==UserScript==
// @name         GitHub Fluid Width
// @namespace    https://github.com/XxUnkn0wnxX/Scripts
// @version      1.0.2
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

  /*** CONFIG ***/
  // Same starting percentage and gutter as Reddit Fluid Width; decimals work.
  // Percentages use the available content area after any external in-page rail.
  // Already fluid code/file/log workspaces keep their native width.
  const CONFIG = Object.freeze({
    contentWidthPercent: 95,
    minGutterPx: 32,
  });

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

  const percent = finiteClamp(CONFIG.contentWidthPercent, 95, 1, 100);
  const gutter = Math.round(finiteClamp(CONFIG.minGutterPx, 32, 16, 128));
  const desktopQuery = window.matchMedia(`(min-width: ${MIN_VIEWPORT_PX}px)`);
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = buildStyles();
  let scheduled = false;

  sync();
  installNavigationHooks();
  installObserver();

  function finiteClamp(value, fallback, min, max) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(min, Math.min(max, number)) : fallback;
  }

  function buildStyles() {
    const width = `min(100%, max(var(${FLOOR_VAR}), min(${percent}%, calc(100% - ${gutter}px - ${gutter}px))))`;
    const active = `html[${ACTIVE_ATTR}]`;
    return `
@media (min-width: ${MIN_VIEWPORT_PX}px) {
  ${active} [${OWNER_ATTR}] {
    width: ${width} !important;
    max-width: none !important;
    margin-inline: auto !important;
    box-sizing: border-box !important;
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
      if (!style.isConnected) {
        scheduleSync();
        return;
      }
      for (const record of records) {
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
      node.matches('.feed-content') ||
      Boolean(node.querySelector(`${CANDIDATE_SELECTOR}, ${NESTED_LIMITER_SELECTOR}, ${GLOBAL_ISSUES_CONTENT_SELECTOR}, .feed-content`));
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
})();
