# GitHub Fluid Width implementation plan

Status: 1.0.2 implementation, documentation, and browser verification complete; publication target: `develop` only. Baseline captures and verification completed 2026-09-26.

## Goal and defaults

Create `userscripts/github-fluid-width.user.js`, following the lifecycle and
configuration conventions of `userscripts/reddit-fluid-width.user.js`.
Start with `contentWidthPercent: 95` and `minGutterPx: 32`; preserve decimal
percentages for later manual tuning. Center widened content with equal gutters.
Only apply desktop overrides at widths of at least 1472 CSS pixels, matching the
Reddit script's activation threshold. Keep smaller layouts native.

The 1.0.1 follow-up also widens the repository overview when GitHub renders it
at a branch-root URL such as `/tree/master` or `/tree/develop`. It uses the
existing direct overview container selector under the `code` route, so nested
directory and source-file routes remain native without parsing branch names.

The 1.0.2 follow-up removes the independent `container-lg` cap from the shared
repository code-view document renderer. This lets README, branch-root, nested
rendered documents, and standalone blob previews fill their owning panel while
leaving source-code panes, native padding, local scrolling, fixed-size content,
and non-repository Markdown untouched. The implementation broadens this
behavior through one DOM ownership engine for GitHub's capped page surfaces.

GitHub's global navigation drawer overlays the page. It does not reserve a
content track, so opening it must not switch percentage modes or move the page.
No pinning option is planned. Preserve native in-page rails and their collapse,
resize, sticky positioning, and scrolling behavior.

## Evidence and layout ownership

The local baseline is `.tmp/github-fluid-width/CAPTURE-INDEX.md`: 35 captures
cover 18 page types in signed-in and guest states (dashboard is signed-in only).
That 1.0.0 baseline did not include branch-root `/tree/<branch>` aliases; the
1.0.1 focused regression covers those aliases and their native nested-page
neighbors.
They include rendered HTML, computed layout, CSS assets, and screenshots.
Additional captures show a collapsed source tree and an expanded completed job
log. Local captures and cookie exports remain ignored and are not deliverables.

[Primer's PageLayout documentation](https://primer.style/product/components/page-layout/)
and [its React CSS source](https://github.com/primer/react/blob/main/packages/react/src/PageLayout/PageLayout.module.css)
describe independently constrained wrappers and content regions. The baseline
confirms both legacy containers and newer React layouts on GitHub. The broader
engine must classify limiter components from the live DOM under `main`,
`react-app`, and `#repo-content-pjax-container`; it must not infer ownership
from an endpoint list or filename extension.

Use adapter-selected roles for each DOM branch instead of assigning the
percentage to every outermost cap. An `OWNER` receives the percentage once,
preserves its native floor, and stays within the configured gutters and hard
parent boundary. A `RELEASE` removes an ancestor cap so the selected owner can
use the remaining track. A `FILL` removes only a demonstrated descendant
document or prose cap; it receives no second percentage. Adapter precedence is
required because nested cards and layout wrappers can have different roles.
Reject candidates inside dialogs, popovers, menus, drawers, `aside` rails, and
other controls; preserve native padding, controls, fixed-size images/tables,
and local overflow. Already-fluid code, diff, and log roots remain native. The
existing dashboard and Discussion rail adapters remain scoped exceptions.

The concrete adapters include Primer xlarge PageLayout wrappers, SidebarPage
xlarge header/content siblings in the remaining track, legacy `container-xl`
or `container-lg` owners under the repository host, and
`PageLayout-content-centered-xl` relationships where the wrapper is a
`RELEASE` and a demonstrated child is the `OWNER` or `FILL`. In Actions, the
centered xlarge wrapper is a `RELEASE`, while the direct `container-xl` child is
the `OWNER`; the captured `336px` navigation rail remains outside that track.
Settings retains its intrinsic sidebar and controls while widening its outer
cards. For Settings and Pulse, the direct `container-xl` workspace is the
`OWNER`; any internal layout rail remains inside that workspace, while buttons,
inputs, and other controls retain intrinsic sizing. Candidate filtering uses
finite computed caps in the observed range,
block/flex/grid display, and host/branch ownership. It rejects
dialog/menu/listbox/popover/overlay/drawer descendants, `aside` rails,
sidebar/pane regions, and form controls.

Global Issues uses a flex-wrapper `RELEASE` beside its native `297px` pane and
the direct full-width content child as the `OWNER`. Its measured native child
floor is `1384px`, derived from the `1400px` wrapper cap minus its captured
`16px` inline padding. The selected child receives the percentage once; the
wrapper does not receive a second width calculation.

The Settings feature-card adapter only moves the direct CTA wrapper to the
trailing edge of its widened row. The button keeps its intrinsic size and the
adapter does not resize, submit, or otherwise operate the form.

Before each scan, deactivate the owned root state and clear only owned markers
and custom properties so classification sees native computed widths. Rescan
after initial/Turbo/PJAX/path changes, then apply owner markers before paint.
The child-list observer schedules only when added nodes match or contain a
candidate limiter. CSS handles ordinary resize; the `matchMedia` listener
coalesces a rescan when the viewport crosses the `1472px` desktop boundary,
without a ResizeObserver or geometry loop.

| Page family | Intended treatment |
| --- | --- |
| Repository and branch-root overview | Widen the outer capped owner and fill its demonstrated document surface; preserve About/navigation rails. |
| Repository folders, source files, and rendered documents | Keep already-fluid code panes native; remove only demonstrated nested document caps inside the owning repository surface. |
| PageLayout and legacy capped sections | Apply adapter-selected `OWNER`, `RELEASE`, and `FILL` roles once, preserving native child lanes and controls. |
| Pull request, issue, and Discussion content | Widen eligible page owners while rejecting comment, metadata, category, and file rails. |
| Global Issues | Release the rail-aware flex wrapper and widen its direct content owner from the measured `1384px` floor; preserve the native sibling pane. |
| Actions, Security, Pulse, and Settings | Include explicit user-requested page owners when their live DOM exposes a capped workspace; preserve navigation, forms, controls, and rail widths. |
| Pull request files, completed Actions logs, and other already-fluid workspaces | Preserve native workspace sizing and local scrolling. |
| Dashboard and user profile | Widen the owning capped region while retaining native navigation, feed/profile rails, and documented rail adapters. |

The dashboard's outer workspace uses the same desktop floor, but its internal
feed sizing remains native until `1668px`, where the captured `1332px` shell
fits beside GitHub's `336px` left rail. Above that boundary, the main feed
receives added width and the rendered right rail remains `312px`.

Already fluid pages need compatibility verification, not forced shrinkage to
95%. For widened regions, the percentage is relative to the available parent
content area after any external reserved rail, capped by a minimum gutter on
each side when that parent is wide enough. Each owner preserves its measured
native floor; the captured 1280px repository and 1332px dashboard floors are
examples, not a universal minimum. `min(100%, ...)` keeps each floor inside a
narrower parent. The owner engine must compute remaining width after external
rails and apply one target per owner, then fill only explicitly marked nested
surfaces. Internal rails remain part of the selected workspace and retain their
native sizing. This keeps low manual
percentages from shrinking native workspaces while still allowing the
configured percentage to widen them.
Do not impose Reddit's fixed rail dimensions on GitHub.

## Implementation sequence

1. Record this plan before creating the userscript.
2. Map shared limiter components and explicit fill surfaces from captured and
   live DOM, using stable IDs, app names, semantic attributes, and readable
   component class prefixes. Avoid endpoint allowlists, generated hash suffixes,
   filename rules, and position-dependent selectors.
3. Implement one persistent style element and DOM ownership state. Scan the
   relevant page hosts after initial parsing and Turbo/PJAX rendering, history
   navigation, back/forward, and document replacement. Coalesce scans and
   clear/reclassify ownership before applying the shared style; do not poll,
   measure geometry in loops, inspect account state, or
   use storage/network access.
4. Exercise the script in isolated headless Firefox sessions using the existing
   GitHub-only cookie export for the signed-in session. Compare native and
   modified geometry on every captured page/state; save evidence under `.tmp`.
5. Run a focused branch-root regression for `/tree/master` and `/tree/develop`,
   including query/trailing-slash variants, encoded and slash-containing refs,
   and arbitrary owner/repository punctuation. Verify nested directories and
   source files remain native without branch-segment parsing.
6. Run a renderer regression over repository README, branch-root, nested
   rendered-document, standalone blob-document, source-code, and representative
   text/code previews. Compare the shared renderer cap, owner bounds, native
   padding, images/tables, and local scrolling without using filename rules.
7. Check the shared owner engine across repository sections, Actions, Security,
   Pulse, Settings, search, and other user-requested capped surfaces. Verify
   controls, forms, drawers, dialogs, rails, and non-owner Markdown remain
   native; never submit forms or dispatch Actions jobs.
8. Check representative responsive widths, real client-side navigation,
   back/forward, drawer opening, source-tree toggling, and completed log expansion.
   Fix observed failures before declaring coverage complete.
9. Add `docs/github-fluid-width.md` and a README entry, update this plan with
   actual verification results and limits, and leave the final percentage
   preferences for the user to tune.

## Acceptance and boundaries

- On wide desktop pages, capped target regions grow to the configured width;
  already fluid regions retain their native geometry.
- Repository-rendered document previews fill their available owner panel after
  the shared `container-lg` cap is removed; source-code panes and non-repository
  Markdown/comment renderers remain native.
- In-page rails do not stretch with the main content. Dialogs, global navigation,
  account menus, forms, and controls remain native; explicit user-requested
  Settings, Security, Pulse, and Actions owners are eligible only through their
  demonstrated page-level caps.
- Global Issues preserves its native sibling pane while widening the direct
  content owner; the Settings CTA adapter changes row alignment only and leaves
  the button's intrinsic dimensions unchanged.
- The legacy Discussion thread explicitly holds its captured `320px` metadata
  rail while expanding the main column. At `1668px` and wider, the dashboard
  explicitly holds its captured rendered `312px` right rail while expanding
  the main feed; other rails retain their native layout ownership and behavior.
- No new document-level horizontal overflow or overlapping rails; local code,
  table, and log scrolling remains available.
- At representative widths below 1472px, script-on and native geometry match.
- DOM/page transitions neither lose the style nor leave owned markers active on
  a replaced region. Reinjection does not duplicate styles or history hooks.
- Guest Actions authentication restrictions count as expected access limits,
  not proof of guest log rendering. Previously inaccessible Scripts run URLs
  are diagnostic captures only; use the captured completed BetterDiscord run.
- Never dispatch, rerun, cancel, or otherwise operate Actions jobs. Browse only
  past completed runs and open existing log sections.
- Shut down every test browser and driver, and verify temporary profiles are
  removed. Do not install into the user's normal browser profile.
- After implementation, validation, and documentation are complete, commit and
  push `develop` only, as authorized. Do not promote or push `master`.

## Earlier verification

- `node --check userscripts/github-fluid-width.user.js`, `cmark
  docs/github-fluid-width.md`, and `git diff --check` pass. A local mocked
  lifecycle check also covered route transitions, duplicate injection, style
  repair, the 1280px/1332px floors, and the default CSS math.
- The isolated real-browser repository check passed at 1920px, 1440px, and
  1000px: the outer workspace grew to 1824px at 1920px, remained native below
  the 1472px media threshold, preserved its 320px rail, and added no document
  overflow.
- The original 1.0.0 baseline capture set contains 35 states across 18 page
  families. Its Firefox run against the 1.0.0 implementation covers all 35 as 33 passed,
  two expected guest Actions access limits, and zero failures. Its source
  SHA-256 digest is
  `92a57098891738e67ab2e2455eae3a4a04edcd821e848093ca87272fd002f1bb`.
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
- A local VM route regression passes branch-root, trailing-slash, query,
  encoded/slash-containing ref, arbitrary owner/repository, nested-directory,
  source-file, and repository-root cases. It confirms only the rendered
  overview selector is eligible for the new code-scoped width rule.
- An independent 1.0.1 source browser check with digest
  `f6f363e65f7a51dcb06b0b228b836b12e957a98c1e70ef4c914c6f307dfe64f6` passed
  `/XxUnkn0wnxX/Scripts/tree/master` and external `/primer/react/tree/main` at
  1920px: both overview shells grew from `1280px` to `1824px`, retained a
  `1920px` document width, and added no overflow. The isolated browser session
  shut down cleanly.
- The focused 1.0.1 browser report at
  `.tmp/github-fluid-width/verification/tree-regression/report.json` contains
  25 measurements and 45 assertions with zero failures across signed-in and
  signed-out sessions. It covers Scripts `master`, `develop`, and query
  variants, external Primer React and BetterDiscord branch roots, nested
  tree/source native workspaces, 1440px/1920px/2560px viewports, and 100%/125%
  bounds. The report digest is a normalized `trim()` digest
  (`6733384e57f43c6c8762be147b0a4d2e3496e5d67ce953cbbbd1944b1e9499d3`);
  the published raw file digest is
  `f6f363e65f7a51dcb06b0b228b836b12e957a98c1e70ef4c914c6f307dfe64f6`.
  Its live navigation includes query variants but not a trailing-slash page;
  the local VM regression covers trailing slashes, encoded refs, and
  slash-containing refs. The report evaluated saved nested-page measurements
  post-run without relaunching a browser, and all browser sessions and drivers
  closed cleanly.
- Visual review covered native/after screenshot pairs for all 33 accessible
  original states at `1920x1080`; the two guest Actions access screens were
  accounted for as native-only captures. Fresh affected-page captures covered
  Scripts `master` in both auth modes, the branch-root/nested/source cases for
  Scripts, Primer React, and BetterDiscord, plus `2560px`/`100%`. Review was
  viewport-scoped and did not claim every full-page scroll position.
- The full and targeted reports used isolated headless Firefox WebDriver
  sessions; all sessions closed with their drivers and Firefox processes
  stopped. The targeted repository-root interaction also reports
  `globalNavigation: passed` for the drawer open/close/restore check. The
  manager installation path still needs the user's final update/reload check.
- The bounded 1.0.2 renderer report at
  `.tmp/github-fluid-width/verification/rendered-doc-review/report.json`
  contains 21 results with zero failures. It covers README, branch-root,
  standalone blob Markdown, and plain-text/code previews at 1440px, 1920px,
  and 2560px. At 1920px the README article grew from `838px` to `1382px`,
  blob Markdown from `1012px` to `1822px`, and the native plain-text code
  renderer remained fluid; parent scroll widths stayed bounded. Its raw source
  SHA-256 is
  `4356be0b464d9e822794e11630c701cb996d0b6696ec95c1a098c3e38424983e`.

## Final 1.0.2 verification

The shared DOM engine was tested at source SHA-256
`a0dce74594db361619dbd385e77a14fd768823b5ad048e1a8072b0a88b7097f9`.
The final file has SHA-256
`e4fc75875a690df01e0b2cd433a2d2682edd2fdb95ce22aef764ad9746dd780d`.
The sole change between those files extends the existing desktop Settings CTA
alignment selector to the Discussions form wrapper. That final selector has
its own live check below; the shared engine is unchanged.

- `.tmp/github-fluid-width/verification/shared-regression/summary.json`:
  35 page/login states, 33 passing native/modified pairs, two expected guest
  Actions access screens, and zero failures. All captures use a 1920x1080
  viewport; representative 1440px layouts remain native. Every capture has
  zero nested percentage owners. Repository folder/file navigation and
  back/forward checks pass with rendered geometry and URLs recorded. Long code
  stays inside the bounded native horizontal scroller without document overflow.
- `.tmp/github-fluid-width/verification/final-renderer-review/report.json`:
  14 capture cases, four resize checks, and 135 assertions with zero failures.
  README, branch roots, standalone Markdown, plain text, source code, CSV, PDF,
  and image previews are covered. Checks include 100% and 1440px-to-2560px
  resizing without reinjection. PDF checks wait for the rendered iframe;
  native/modified PDF geometry is 1886x1012. CSV, PDF, and image preview pairs
  are byte-identical. An earlier PDF loading-placeholder diagnostic is retained
  separately and superseded by this completed run.
- `.tmp/github-fluid-width/verification/shared-globals/run-2026-09-26T13-20-24-198Z/report.json`:
  global Issues, Pull Requests, Search, and account Settings pass at 1440px,
  1920px, and 2560px, including resizing without reinjection and 100% variants
  for Issues, Pull Requests, and Settings. All captures have zero nested
  owners. At 2560px, Issues content grows from 1384px to 2134.63px, Pull
  Requests from 1280px to 2188.8px, and the account Settings workspace from
  1280px to 2432px. Search is already fluid and remains native. Its right rail
  changes width with GitHub's own responsive layout, so rail comparisons use
  the same viewport. The Issues-to-Pull-Requests click performs a full-document
  navigation; WebDriver injection does not persist into that new document.
  This check is not evidence of userscript-manager reinjection or SPA survival.
- `.tmp/github-fluid-width/verification/repository-sections-final-source/summary.json`
  records Actions, Security, Pulse, and repository Settings at 1440px, 1920px,
  2560px, and 3200px, plus bounded 100%/125% variants and repository-to-Actions
  navigation/drawer checks. That stage used source SHA-256
  `412fcd7598fca0e39622adb87f3f798030db89405e8814aa733da21ff23bc16a`.
  At 2560px, Actions content reaches 2067.2px beside its 336px rail; Security
  reaches 2052px beside its 320px rail; Pulse's workspace reaches 2432px with
  its 296px rail; and Settings reaches 2432px with its 256px rail. The report
  retains one failed Features assertion caused by selecting the heading's next
  sibling instead of the card. The corrected final-source checks below resolve
  that diagnostic. The reported narrow Actions screenshot was not reproduced
  in either direct or client-side navigation at wide desktop sizes.
- `.tmp/github-fluid-width/verification/repository-sections-final-source/settings-features-final-integrated/summary.json`
  confirms the actual Settings main column and Features region fill 2072px at
  2560px on the tested shared engine. The final-file report at
  `.tmp/github-fluid-width/verification/repository-sections-final-source/settings-features-all-cta-final-integrated/summary.json`
  verifies Templates, Sponsor, and Discussions cards and controls. All three
  controls end at their row's right edge, x=2430px, with unchanged intrinsic
  dimensions and no overflow. The new form-wrapper selector matches exactly
  one element. At 1440px, all three cards, rows, wrappers, and controls match
  native geometry exactly.

Native sidebars retain their widths in same-viewport comparisons; their
positions can move with the expanded workspace. Visual review covers all 33
accessible original native/modified viewport pairs and additional section,
global, renderer, and below-fold README/document/Features captures. It does not
claim every scroll position or every GitHub feature. Reports and screenshots
remain ignored local evidence, not published repository content.

Final syntax and Markdown checks pass. Every isolated browser and driver has
stopped, and its temporary profile has been removed. No Actions jobs were
triggered, rerun, or cancelled; no Settings or Security forms were submitted.
Userscript-manager installation, update/reload behavior, and final percentage
preferences remain the user's final checks.
