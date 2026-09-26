# GitHub Fluid Width implementation plan

Status: Implementation and browser verification complete; publication target: `develop` only. Baseline captures completed 2026-09-26.

## Goal and defaults

Create `userscripts/github-fluid-width.user.js`, following the lifecycle and
configuration conventions of `userscripts/reddit-fluid-width.user.js`.
Start with `contentWidthPercent: 95` and `minGutterPx: 32`; preserve decimal
percentages for later manual tuning. Center widened content with equal gutters.
Only apply desktop overrides at widths of at least 1472 CSS pixels, matching the
Reddit script's activation threshold. Keep smaller layouts native.

GitHub's global navigation drawer overlays the page. It does not reserve a
content track, so opening it must not switch percentage modes or move the page.
No pinning option is planned. Preserve native in-page rails and their collapse,
resize, sticky positioning, and scrolling behavior.

## Evidence and layout ownership

The local baseline is `.tmp/github-fluid-width/CAPTURE-INDEX.md`: 35 captures
cover 18 page types in signed-in and guest states (dashboard is signed-in only).
They include rendered HTML, computed layout, CSS assets, and screenshots.
Additional captures show a collapsed source tree and an expanded completed job
log. Local captures and cookie exports remain ignored and are not deliverables.

[Primer's PageLayout documentation](https://primer.style/product/components/page-layout/)
and [its React CSS source](https://github.com/primer/react/blob/main/packages/react/src/PageLayout/PageLayout.module.css)
describe independently constrained wrappers and content regions. The baseline
confirms both legacy containers and newer React layouts on GitHub. Widen the
owning region and remove only its demonstrated inner caps; do not globally
override `.container-*`, all `data-width` elements, Markdown, dialogs, or panels.

| Page family | Intended treatment |
| --- | --- |
| Repository overview | Widen the capped repository workspace and main content; preserve the About rail. |
| Folder, source file, rendered Markdown | Preserve already fluid split panes, source tree, Symbols panel, and native Markdown measure. |
| Commit history and branches | Widen the outer capped React PageLayout wrapper. |
| Pull request and issue lists | Widen the content and corresponding header inside any reserved navigation rail. |
| Pull request conversation | Widen the owning conversation workspace; preserve metadata and file rails. |
| Pull request files changed | Preserve the already-fluid diff/file workspace and its native file rails. |
| Issue conversation | Widen the owning discussion layout and its demonstrated nested cap; preserve metadata rail. |
| Discussions list and thread | Widen the owning list/conversation region; preserve category and metadata rails. The legacy thread keeps its captured `320px` metadata rail while the main column grows. |
| Actions overview | Widen the capped run list within the native workflow navigation. |
| Completed Actions run and job logs | Preserve already fluid native workspaces; verify expanded past logs. |
| Dashboard | Widen the feed's owning capped region while retaining native navigation, feed cards, and the captured `312px` right rail. |
| User profile | Widen the owning profile region while preserving the profile rail and native content limits. |

The dashboard's outer workspace uses the same desktop floor, but its internal
feed sizing remains native until `1668px`, where the captured `1332px` shell
fits beside GitHub's `336px` left rail. Above that boundary, the main feed
receives added width and the rendered right rail remains `312px`.

Already fluid pages need compatibility verification, not forced shrinkage to
95%. For widened regions, the percentage is relative to the available parent
content area after any native reserved rail, capped by a minimum gutter on each
side when that parent is wide enough. Generic widened regions preserve their
captured 1280px native floor, and the dashboard preserves its captured 1332px
floor; `min(100%, ...)` keeps either floor inside a narrower parent. This keeps
low manual percentages from shrinking native workspaces while still allowing
the configured percentage to widen them. Apply the percentage once per owning
workspace to avoid nested 95% caps.
Do not impose Reddit's fixed rail dimensions on GitHub.

## Implementation sequence

1. Record this plan before creating the userscript.
2. Map owning containers and inner caps from the captured layouts, using stable
   IDs, app names, semantic attributes, and readable component class prefixes.
   Avoid generated hash suffixes and position-dependent selectors.
3. Implement one persistent style element and route-scoped root state. Support
   initial parsing, GitHub Turbo/PJAX rendering, history navigation, back/forward,
   and style reinsertion after document updates. Coalesce mutation work without
   polling, geometry loops, account detection, or storage/network access.
4. Exercise the script in isolated headless Firefox sessions using the existing
   GitHub-only cookie export for the signed-in session. Compare native and
   modified geometry on every captured page/state; save evidence under `.tmp`.
5. Check representative responsive widths, real client-side navigation,
   back/forward, drawer opening, source-tree toggling, and completed log expansion.
   Fix observed failures before declaring coverage complete.
6. Add `docs/github-fluid-width.md` and a README entry, update this plan with
   actual verification results and limits, and leave the final percentage
   preferences for the user to tune.

## Acceptance and boundaries

- On wide desktop pages, capped target regions grow to the configured width;
  already fluid regions retain their native geometry.
- In-page rails do not stretch with the main content. Dialogs, global navigation,
  account menus, and unrelated settings/authentication routes remain native.
- The legacy Discussion thread explicitly holds its captured `320px` metadata
  rail while expanding the main column. At `1668px` and wider, the dashboard
  explicitly holds its captured rendered `312px` right rail while expanding
  the main feed; other rails retain their native layout ownership and behavior.
- No new document-level horizontal overflow or overlapping rails; local code,
  table, and log scrolling remains available.
- At representative widths below 1472px, script-on and native geometry match.
- Route transitions neither lose the style nor leave it active on unsupported
  pages. Reinjection does not duplicate styles or history hooks.
- Guest Actions authentication restrictions count as expected access limits,
  not proof of guest log rendering. Previously inaccessible Scripts run URLs
  are diagnostic captures only; use the captured completed BetterDiscord run.
- Never dispatch, rerun, cancel, or otherwise operate Actions jobs. Browse only
  past completed runs and open existing log sections.
- Shut down every test browser and driver, and verify temporary profiles are
  removed. Do not install into the user's normal browser profile.
- After implementation, validation, and documentation are complete, commit and
  push `develop` only, as authorized. Do not promote or push `master`.

## Verification record

- `node --check userscripts/github-fluid-width.user.js`, `cmark
  docs/github-fluid-width.md`, and `git diff --check` pass. A local mocked
  lifecycle check also covered route transitions, duplicate injection, style
  repair, the 1280px/1332px floors, and the default CSS math.
- The isolated real-browser repository check passed at 1920px, 1440px, and
  1000px: the outer workspace grew to 1824px at 1920px, remained native below
  the 1472px media threshold, preserved its 320px rail, and added no document
  overflow.
- The baseline capture set contains 35 states across 18 page families. The
  full current-source Firefox run covers all 35 as 33 passed, two expected
  guest Actions access limits, and zero failures. Its source SHA-256 digest
  is `92a57098891738e67ab2e2455eae3a4a04edcd821e848093ca87272fd002f1bb`.
  The logged-out pull-files page retains its native `#files_bucket` and
  `.js-diff-container` targets at `1856px`.
- Dashboard measurements keep the inner flex layout native at 1472px and
  1600px (outer/feed widths `1136/759.83` and `1264/879.55`, rails `256.17`
  and `264.45`). At 1920px, the default 95% target is
  `1504.78px` with a `1072.78px` main and `312px` rail; 100% is `1520px`
  with a `1088px` main and the same rail. At 2560px, the corresponding 95%
  and 100% targets are `2112.8/1680.8/312` and `2160/1728/312` for
  outer/main/rail. The over-100% variant clamps to 100%, and the 1% variant
  preserves the `1332px` dashboard floor with a `900px` main and `312px`
  rail at 1920px and 2560px. These runs added no document overflow.
- The full and targeted reports used isolated headless Firefox WebDriver
  sessions; all sessions closed with their drivers and Firefox processes
  stopped. The targeted repository-root interaction also reports
  `globalNavigation: passed` for the drawer open/close/restore check. The
  manager installation path still needs the user's final update/reload check.
