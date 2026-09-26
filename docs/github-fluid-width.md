# github-fluid-width.user.js

Install the development build [`github-fluid-width.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js) with Tampermonkey or Violentmonkey to widen selected GitHub workspaces on large desktop screens while preserving GitHub's native rails, split panes, and responsive behavior.

This is the `1.0.2` development build. The raw `develop` URL is intentional:
updates are available there while the script is being tested. A future release
can promote the same file and documentation to `master`.

## What It Does

- activates only at viewport widths of at least `1472px`
- widens capped GitHub regions to the configured percentage of their available parent area
- keeps the captured native workspace floor while it fits inside the available parent, and otherwise fills that parent without overflow
- preserves native in-page rails, source trees, Symbols panels, diff/file rails, workflow navigation, and log scrolling; repository-rendered document previews fill their owning panel while retaining native padding and renderer-local behavior; the legacy Discussion thread keeps its captured `320px` metadata rail while its main column grows, and the dashboard keeps its captured `312px` right rail once its wide-shell rule activates
- keeps Settings feature-card primary CTAs at the widened row's trailing edge without changing the button's intrinsic size
- leaves GitHub's global navigation drawer as an overlay; opening or closing it does not switch width modes or move the page
- keeps already-fluid code, directory, pull-request-files/changes, and Actions-log workspaces at their native fluid width
- follows GitHub client-side navigation, back/forward navigation, Turbo/PJAX rendering, and document/head replacement without polling
- makes no network requests, storage reads/writes, account-state checks, GitHub content restructuring, clicks, or GitHub job operations; it only maintains its own style and ownership markers

The 1.0.2 implementation classifies capped page owners from the rendered GitHub
DOM instead of maintaining a positive URL allowlist. Settings, Security,
Pulse, Actions, search, and other page owners are eligible
when their live structure exposes a bounded workspace. Dialogs, drawers,
popovers, menus, rails, comments, and ordinary form controls remain native;
eligible settings or other page sections may contain forms whose controls keep
their intrinsic sizing.

## Where It Works

The owner model covers repository overviews and branch roots, PageLayout and
legacy capped sections, pull-request and issue workspaces, Discussions,
Actions, Security, Pulse, Settings, dashboards, profiles, and other rendered
GitHub surfaces when their DOM exposes the same kind of bounded owner. It
widens the outer owner once, then fills only demonstrated nested document
surfaces. Repository README and standalone rendered documents therefore lose
their independent `container-lg` measure, while source-code panes, diff/file
workspaces, completed logs, and other already-fluid renderers retain native
behavior. Where an ancestor wrapper only limits the available track, it is
released before the selected owner is widened. The model does not depend on
branch names or filename extensions.

Global Issues releases its rail-aware wrapper and widens the direct content
workspace while preserving the native sibling pane. Settings feature cards keep
their primary CTA at the trailing edge without changing the button's intrinsic
size.

## Desktop and Responsive Behavior

At `1472px` and wider, each eligible owning workspace uses one width
calculation and its measured native floor. A captured `1280px` floor is a
representative repository-section example:

```css
width: min(100%, max(1280px, min(95%, calc(100% - 32px - 32px))));
```

The dashboard uses its captured `1332px` native floor in the same formula. Once the native shell fits beside GitHub's left rail at `1668px`, the captured `312px` right rail stays fixed while the feed column uses the spare width. Between `1472px` and that boundary, the outer rule is active but the feed's internal flex sizing remains native. Other owners retain their own measured floors; the value is not a universal minimum.

The values are configurable, and decimal percentages are preserved. The
percentage excludes external rails that occupy a sibling track, then applies
to the selected owner's available workspace. Fixed rails inside that owner
remain inside its layout and retain their native sizing; the percentage is not
calculated from the main column alone. Remaining width is bounded by the
parent and configured gutters. The floor prevents a lower target from shrinking
an existing workspace, and the same hard boundary applies to `100%` and
over-100% values.

Inner caps demonstrated to belong to the same workspace are removed so nested `95%` limits do not compound. Repository-rendered document previews additionally remove only their independent `1012px` `container-lg` cap and use the available owner width; they do not receive a second percentage or viewport width rule. Native preview padding, typography, images, tables, and local scrolling remain governed by GitHub.

At widths below `1472px`, the desktop CSS rules are inactive and GitHub's native
responsive layout remains in control. Ownership markers are cleared and
recomputed when GitHub replaces page regions or changes page state. CSS handles
ordinary resizing, while the `matchMedia` breakpoint listener rescans when the
viewport crosses `1472px`, without geometry polling.

The global navigation drawer overlays GitHub content and does not reserve a layout track. Its open/closed state therefore does not change the calculation. Native rails inside a repository, discussion, pull request, profile, or workflow remain owned by GitHub and retain their own width, sticky, collapse, resize, and scrolling behavior. Two scoped sizing exceptions preserve captured rendered rails while their owning content grows: the legacy Discussion thread holds its `320px` metadata rail, and the dashboard holds its `312px` right rail from `1668px` upward.

## Configuration

Edit the `CONFIG` object near the top of the script:

```js
const CONFIG = Object.freeze({
  contentWidthPercent: 95,
  minGutterPx: 32,
});
```

- `contentWidthPercent` controls the requested target width of a selected workspace. Values from `1` to `100` are accepted, including decimals; values above `100` are clamped to `100`, and invalid values fall back to `95`. The captured native floor prevents a low target from shrinking an existing workspace.
- `minGutterPx` controls the minimum gutter on each side of a centered workspace when the parent has room to preserve both that gutter and the native floor. Values are clamped to `16..128px` and rounded; invalid values fall back to `32px`.

The script does not expose account-specific settings or remote configuration. Change the local values, save the edited script in the userscript manager, and reload the GitHub page for the new values to take effect. Resizing then updates the loaded layout automatically.

## Route and Lifecycle Safety

The script stores one owned style element and owned DOM ownership markers. It
synchronizes at startup, on DOM-ready/Turbo/PJAX render events, on `pushState`
and `replaceState`, on `popstate` and `pageshow`, and when GitHub replaces
relevant document regions. The mutation observer schedules rescans only for
added candidate regions; it does not poll, measure resize loops, or rewrite
page content.

Before rescanning, the script clears only its own markers and deactivates its
owned rules so native computed widths are used for classification. Reinjection
reuses the existing installation flag and dispatches a sync event instead of
adding duplicate history hooks or styles.

## Basic Install

1. Install a userscript manager such as Tampermonkey or Violentmonkey.
2. Open the [development raw script](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js) and choose the manager's install option.
3. Visit a GitHub page with a bounded workspace at a viewport width of at least `1472px`.

Keep the development URL while this `1.0.2` build is being tested. After a future promotion to `master`, the script metadata and documentation can use the stable `master` URLs.

## Compatibility and Safety

- no external dependencies
- no network requests or tracking beacons
- no cookies, account data, or authentication-state inference
- no storage reads or writes
- no polling, resize loops, or forced transitions
- no GitHub content restructuring or job dispatches; the script only inserts/repairs its own style element and maintains its ownership markers
- native horizontal scrolling remains available for code, files, tables, and logs

Browser evidence uses isolated headless Firefox sessions with WebDriver
injecting the local userscript source into temporary profiles. That checks the
source's layout and lifecycle behavior; it does not install the script into a
userscript manager. The shared-layout regression covers 35 page/login states:
33 passing native/modified pairs and two expected guest Actions access screens.
Additional checks cover repository Actions, Security, Pulse and Settings;
global Issues, Pull Requests, Search and account Settings; and 14 file-renderer
cases with four resize checks. Renderers include Markdown, plain text, source
code, CSV, PDF and an image preview. Native sidebars remain the same width at
the same viewport size, while their position can move with a widened workspace.

The checks include 1440px native layouts, 1920px/2560px desktop layouts,
3200px repository sections, bounded 100%/over-100% settings, and client-side
repository navigation. Visual review covers captured viewports and targeted
below-fold README/document and Settings Features regions, not every scroll
position or every GitHub feature. Detailed source hashes, reports and earlier
verification are recorded in the [implementation plan](plan/github-fluid-width-plan.md).
Manager startup, update and reload behavior remains the user's final check.

## Example

Open a repository overview or an existing pull-request conversation at a desktop viewport wider than `1472px`. The owning capped region grows toward the `95%` target of its available area while its measured native floor and rails remain in place. Even a `100%` setting stops at the parent boundary and keeps the configured gutter whenever the native floor permits. Resize below the threshold and GitHub returns to its native layout; completed Actions run/job pages remain native throughout.
