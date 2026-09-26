# github-fluid-width.user.js

Install the development build [`github-fluid-width.user.js`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js) with Tampermonkey or Violentmonkey to widen selected GitHub workspaces on large desktop screens while preserving GitHub's native rails, split panes, and responsive behavior.

This is an unreleased `1.0.0` development build. The raw `develop` URL is intentional: updates are available there while the script is being tested. A future release can promote the same file and documentation to `master`.

## What It Does

- activates only at viewport widths of at least `1472px`
- widens capped GitHub regions to the configured percentage of their available parent area
- keeps the captured native workspace floor while it fits inside the available parent, and otherwise fills that parent without overflow
- preserves native in-page rails, source trees, Symbols panels, Markdown reading measures, diff/file rails, workflow navigation, and log scrolling; the legacy Discussion thread keeps its captured `320px` metadata rail while its main column grows, and the dashboard keeps its captured `312px` right rail once its wide-shell rule activates
- leaves GitHub's global navigation drawer as an overlay; opening or closing it does not switch width modes or move the page
- keeps already-fluid code, directory, rendered-Markdown, pull-request-files/changes, and Actions-log workspaces at their native fluid width
- follows GitHub client-side navigation, back/forward navigation, Turbo/PJAX rendering, and document/head replacement without polling
- makes no network requests, storage reads/writes, account-state checks, GitHub content restructuring, clicks, or GitHub job operations; it only maintains its own style and route attribute

The script is intentionally scoped to the GitHub app routes and workspace selectors covered by the implementation baseline. Authentication, settings, search, marketing, and unrelated GitHub routes remain native.

## Where It Works

The current route set covers these page families when GitHub renders a matching capped workspace:

- repository overview, commit history, and branches
- pull-request and issue lists
- pull-request conversations and issue conversations
- Discussions lists and threads
- Actions overview
- the signed-in dashboard feed
- user profiles

Repository folders, source files, rendered Markdown, pull-request files/changes, and completed Actions job logs are checked for compatibility but are not forcibly narrowed or given a second percentage cap when GitHub already supplies a fluid workspace. GitHub may canonicalize a pull-request files URL to `/changes`; both route forms remain native. The script does not inspect job state or target completed run/job routes, so those native workspaces remain unaffected. GitHub may vary the exact component markup by page or rollout; unmatched markup remains native.

## Desktop and Responsive Behavior

At `1472px` and wider, each selected owning workspace uses one width calculation. Generic workspaces use the captured `1280px` native floor:

```css
width: min(100%, max(1280px, min(95%, calc(100% - 32px - 32px))));
```

The dashboard uses its captured `1332px` native floor in the same formula. Once the native shell fits beside GitHub's left rail at `1668px`, the captured `312px` right rail stays fixed while the feed column uses the spare width. Between `1472px` and that boundary, the outer rule is active but the feed's internal flex sizing remains native.

The values are configurable, and decimal percentages are preserved. The percentage is relative to the selected workspace's available parent area, after any native in-page rail. The minimum gutter applies whenever the parent is wide enough; the outer `min(100%, ...)` keeps a narrower parent from overflowing. The floor prevents a lower percentage setting from shrinking a native workspace.

Inner caps demonstrated to belong to the same workspace are removed so nested `95%` limits do not compound.

At widths below `1472px`, the desktop CSS rules are inactive and GitHub's native responsive layout remains in control. The root route attribute can remain present on supported paths so the same style can respond immediately when the viewport grows; navigating to an unsupported route removes the attribute and its width rules without requiring a page reload.

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

The script stores one owned style element and a root route attribute. It synchronizes at startup, on DOM-ready/Turbo/PJAX render events, on `pushState` and `replaceState`, on `popstate` and `pageshow`, and when GitHub replaces relevant document regions. The mutation observer only repairs a detached style or a changed path; it does not poll or rewrite page content.

The root attribute is removed for unsupported routes. Reinjection reuses the existing installation flag and dispatches a sync event instead of adding duplicate history hooks or styles.

## Basic Install

1. Install a userscript manager such as Tampermonkey or Violentmonkey.
2. Open the [development raw script](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/develop/userscripts/github-fluid-width.user.js) and choose the manager's install option.
3. Visit a supported GitHub page at a viewport width of at least `1472px`.

Keep the development URL while this `1.0.0` build is being tested. After a future promotion to `master`, the script metadata and documentation can use the stable `master` URLs.

## Compatibility and Safety

- no external dependencies
- no network requests or tracking beacons
- no cookies, account data, or authentication-state inference
- no storage reads or writes
- no polling, timers, or forced transitions
- no GitHub content restructuring or job dispatches; the script only inserts/repairs its own style element and maintains its root route attribute
- native horizontal scrolling remains available for code, files, tables, and logs

The checked browser evidence uses isolated headless Firefox sessions with
WebDriver injecting the local userscript source into temporary profiles. This
checks the layout and lifecycle behavior of the source; it does not install the
script into Tampermonkey or Violentmonkey. After the development build is
published, verify the manager's update and reload behavior separately. The
current 35-state evidence has 33 passing states and two expected guest Actions
access limits; the dashboard's current-source checks preserve its `312px` rail
from `1668px` upward and keep the `100%` and over-100% variants within their
parent bounds.

## Example

Open a repository overview or an existing pull-request conversation at a desktop viewport wider than `1472px`. The owning capped region grows toward the `95%` target of its available area while its native floor and rails remain in place. Even a `100%` setting stops at the parent boundary and keeps the configured gutter whenever the native floor permits. Resize below the threshold or navigate to an unsupported route and GitHub returns to its native layout; completed Actions run/job pages remain native throughout.
