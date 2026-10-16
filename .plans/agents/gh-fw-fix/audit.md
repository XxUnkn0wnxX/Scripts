# Current GitHub layout audit — 2026-10-16

The product contract remains `.plans/project-plans/completed/github-fluid-width-plan.md`.
This record scopes the user's requested workflow-header repair and fresh
compatibility audit; it does not replace or revise that specification.

- A01: Repair the demonstrated Actions header lane using current semantic DOM
  attributes and the existing owner/fill calculations. Preserve native padding,
  the 1472px breakpoint, one percentage per owner, rails, and controls.
- A02: Compare native and modified current pages across the page families in
  `.tmp/github-fluid-width/links.txt`, plus workflow details, global pages, and
  repository/account sections when accessible. Inspect visible content, new
  clipping, overflow, control/rail dimensions, nested owners, and unhandled
  page-level caps. Require positive ownership and width response for recognized
  full-width families so an inert renamed selector cannot pass unnoticed.
  Verify capture readiness, expected content, and authentication before credit.
  Use representative responsive checks rather than a full
  viewport Cartesian product. Record inaccessible pages as unverified.
- A03: Integrate only evidence-backed fixes within the existing contract;
  update userscript version/documentation, run syntax/diff checks, and report
  coverage and limits. The user subsequently authorized a version increment and
  commit/push to `develop` only. No account mutation or workflow operation.

Dependencies: A02 establishes whether A01 alone is sufficient. Any additional
fixes require their affected pages to be rechecked before A03 closes.

Execution is serial. One temporary Firefox session at a time; reuse the local
WebDriver helper. Snapshots/reports remain ignored. The user's second message
explicitly requested this broader read-only compatibility check.

Initial evidence: current `HeaderInner__O2ZDqd[data-width="xlarge"]` under
`[data-component="PageLayout.Header"]` has a native 1280px cap and 24px inline
padding. The child PageHeader has no independent cap. The script only recognizes
the older module-prefixed header class. See `.tmp/github-fluid-width/actions-pageheader-20261016/native-layout.json` and `.tmp/github-fluid-width/actions-pageheader-20261016/page.html`.

Independent Astra review: PASS WITH NOTES. The semantic candidate is compatible
with current host/cap/owner guards. Accepted audit corrections are positive
full-width behavior checks, explicit capture readiness, same-current-DOM
disable/recheck attribution for suspected visibility loss, and profile-cleanup
verification. Source and browser verification remain parent-owned acceptance.

## User-directed repository organization

- Agent task records live together under `.plans/agents/<task>/`; new sessions
  can identify ongoing work by folder name and read that folder's records.
- `.plans/project-plans/` is the broader project todo list, with `todo/` and
  `completed/` subfolders. Other project folders may coexist under `.plans/`.
- Move both the current GitHub task and the existing MKV task under
  `.plans/agents/`. Move the old documentation plans into the project todo
  hierarchy, update Markdown references, and remove the empty old directories.
- Keep safe `.plans/` records and generic `AGENTS.md` Git-visible after privacy
  review. Raw captures and cookies remain ignored in `.tmp/`.
- Keep the only ongoing GitHub Fluid Width changelog in the collapsible details
  section of `docs/github-fluid-width.md`.

## Endpoint findings

Fresh representative pages were fetched before the affected selectors changed.
The userscript matches GitHub broadly and detects layout primitives; these are
the 26 page cases audited, rather than an exhaustive list of GitHub routes.
Source and rendered Markdown share an endpoint pattern but exercise different
rendering paths.

### Required patches

| Endpoint pattern | Demonstrated repair |
| --- | --- |
| `/:owner/:repo/actions/workflows/:workflow` | Current semantic PageLayout header lane expands with the run list. |
| `/:owner/:repo/actions` | Same renamed header lane recognized. |
| `/:owner/:repo/pulls` | Same renamed header lane recognized. |
| `/pulls` | Same renamed header lane recognized. |
| `/:owner/:repo/issues/:number` | Four capped issue lanes recognized; optional sticky metadata spacing restored. |
| `/search` | Results lane recognized through its header landmark; native sidebars retained. |
| `/:owner/:repo/pull/:number` | Nested conversation cap released; optional repeated floating title recognized. |
| `/:owner/:repo/pull/:number/files` (redirects to `/changes`) | Optional repeated Changes title hidden while normal commit selector and toolbar controls remain available. |
| `/dashboard` | Feed expands through its dashboard landmark; right rail retained. |
| `/:owner/:repo/pulse` | Intrinsic image-label measurement prevents avatar clipping during chart expansion. |

### Still working without a page-specific repair

| Endpoint pattern | Checked surface |
| --- | --- |
| `/:owner/:repo` | Repository overview and file listing. |
| `/:owner/:repo/tree/:ref/:path` | Folder and file-tree workspace. |
| `/:owner/:repo/blob/:ref/:path` | Source-code view. |
| `/:owner/:repo/blob/:ref/:path` | Rendered Markdown view. |
| `/:owner/:repo/commits/:ref` | Commit history. |
| `/:owner/:repo/branches` | Branch listing and search. |
| `/:owner/:repo/actions/runs/:id` | Actions run summary. |
| `/:owner/:repo/actions/runs/:id/job/:job` | Completed job log. |
| `/:owner/:repo/issues` | Repository issue listing. |
| `/orgs/:org/discussions` | Discussion listing. |
| `/orgs/:org/discussions/:number` | Discussion thread and reply rows. |
| `/:user` | Profile and activity. |
| `/issues` | Global issue workspace. |
| `/settings/profile` | Account profile settings. |
| `/:owner/:repo/settings` | Repository settings. |
| `/:owner/:repo/security` | Repository security overview. |

## Evidence and limits

Raw evidence remains in `.tmp/github-fluid-width/actions-pageheader-20261016/`.
`focused-fixed/` and `broad-fixed/` cover the 26 initial cases. The initial
Discussion-list readiness rejection was resolved by distinguishing a hidden
loading panel from visible loading state; `semantic-final/` confirms that page.
`live-final/` validates the final semantic adapters, live settings and four
landmark replacement simulations. `pulse-and-sticky/` positively checks a
native-visible Changes title clone at 2048x600: visible/hidden/visible, with one
visible commit selector throughout. Earlier recovery snapshots do not establish
Pulse correctness; `svg-probe/` proves the actual negative SVG coordinate and
`chart-intrinsic-trial/` establishes the CSS measurement mechanism.

The broad visibility oracle keeps native DOM references, detects deliberately
hidden/clipped sentinels, and compares new clipping against native clipping.
The first root report's visibility counters were invalidated after an oracle
bug; its geometry and screenshots are diagnostic only. Native full-width reply
rows, filters and textareas are expected to grow with their workspaces; ordinary
intrinsic buttons and rails retain their sizing.

Checks use current authenticated Firefox pages in disposable profiles. They
cover representative content, responsive widths and settings transitions;
they do not establish every possible GitHub rollout, offscreen interaction, or
another browser/userscript-manager implementation. No workflow or account form
was submitted. Final integrated Pulse acceptance and publication are recorded
in the companion checklist and handoff.

Final acceptance: `pulse-integrated-final/report.json` passes on final source
SHA-256 `34152b61b2b5c27c0265d58828bd15b0ec73887bb9ded31552617b5fd2bb4659`,
including image-only label scoping, viewport 2048→1280→2560→2048 and live
95→80→95 percentage changes. The release is `1.0.4`, published in commit
`bedc9321294ee95ae7c9eb6dad78e0351a80dc6b` on `develop` only. Published raw
source matches the accepted bytes; `master` remains at the original base.

## Site-wide follow-up requested by the user

The user asked which other pages may be affected or missed, clarified that
coverage should be site-wide, and identified `https://gist.github.com/` as a
concrete miss. Continue from the completed 1.0.4 audit with these tasks:

- B01: Fetch current Gist layouts and remaining representative GitHub Insights
  and site sections. Separate host exclusion, recognized capped workspaces,
  already-fluid layouts, missed workspace caps, and inaccessible pages. Do not
  mistake intentional card/control dimensions for page-width defects.
- B02: Repair demonstrated coverage gaps within the existing owner/rail/gutter
  contract, using fresh semantic parent/layout evidence before selector changes.
  Verify affected pages, append the single documentation changelog, and publish
  only `develop` under standing authority. The user's later explicit override
  keeps `@version 1.0.4` for this follow-up.
- B03: Reconcile the coverage report and limitations, update the handoff and
  checklist, and verify any published source/ref state. Existing A01–A03 evidence
  remains accepted for unchanged behavior.

Execution remains serial, using disposable browser profiles. Keep captures and
credentials in ignored `.tmp/`; no account submissions or workflow operations.
Use only the two host-wide matches `https://github.com/*` and
`https://gist.github.com/*`; endpoint URLs are test cases, never match rules.
The user chose to leave `docs.github.com` outside the script's scope.

## Site-wide follow-up findings

The demonstrated source gap was the missing Gist host match. The follow-up adds
only `https://gist.github.com/*` beside `https://github.com/*` and updates the
description. The executable userscript body is byte-identical to the accepted
initial repair. No endpoint-specific matches, route allowlist, Gist selectors,
or broader cap-removal rules were added. Version stays `1.0.4` by the user's
explicit override; the existing collapsible changelog entry records the change.

Final follow-up source SHA-256:
`e30304c43ef8b26783e3bc4a82588ef913bb0419d097cd1eb86a0947fd05ab7a`.

### Newly enabled Gist coverage

All paths below are on `gist.github.com`. Current authenticated captures of
these eight cases pass the native-versus-modified visibility/clipping checks.

| Endpoint pattern | Result after host enablement |
| --- | --- |
| `/` | Home/create workspace widened with native form/control behavior. |
| `/discover` | Discovery feed widened. |
| `/forked` | Forked feed widened. |
| `/starred` | Starred feed widened. |
| `/:owner` | Owner profile/listing widened. |
| `/:owner/:gist` | Gist file/code workspace widened; local scrolling retained. |
| `/:owner/:gist/revisions` | Revision diff workspace widened; controls retained. |
| `/:owner/:gist/forks` | Fork listing widened. |

The exact user-selected gist and revision endpoint were tested. Its `container-lg`
workspace grows to 1945.6px at a 2048px viewport. The profile uses the existing
`container-xl` owner; no new selector is required. `/:owner/shared` returned a
not-found page for the expected signed-in owner. The host match covers the path,
but no content layout is credited for that unavailable endpoint.

### Additional GitHub cases requiring no new repair

These are in addition to the initial 26 page cases. The Insights routes were
read from the current sidebar before capture. All 28 layouts below were usable
and had no newly hidden/clipped content, nested owners, or added horizontal
overflow. Data/feature availability is listed separately from layout behavior.

| Endpoint pattern | Observed treatment |
| --- | --- |
| `/:owner/:repo/releases` | Existing owner widens release listing. |
| `/:owner/:repo/tags` | Existing owner widens tags. |
| `/:owner/:repo/commit/:sha` | Existing owner widens commit details. |
| `/:owner/:repo/compare/:base...:head` | Existing owner widens comparison. |
| `/:owner/:repo/wiki` | Existing owner widens Wiki. |
| `/:owner/:repo/pull/:number/commits` | Existing owner widens PR commits. |
| `/:owner/:repo/pull/:number/checks` | Native full-width layout; no eligible capped owner. |
| `/notifications` | Native full-width layout; no eligible capped owner. |
| `/explore` | Existing owner widens the feed. |
| `/trending` | Existing owners widen content/header lanes. |
| `/topics` | Existing owners widen content/header lanes. |
| `/marketplace` | Existing owners widen the marketplace. |
| `/:org` | Organization profile widens. |
| `/orgs/:org/repositories` | Organization repository listing widens. |
| `/users/:owner/projects` | Project listing widens; project boards are a separate untested renderer. |
| `/codespaces` | Codespaces listing widens; external editor hosts remain outside the two matches. |
| `/:user?tab=repositories` | Profile repository listing widens. |
| `/:owner/:repo/graphs/contributors` | Rendered contribution charts expand; data and axes visible. |
| `/:owner/:repo/graphs/community` | Feature-disabled Community page widens; Discussions was not enabled. |
| `/:owner/:repo/community` | Community standards page widens. |
| `/:owner/:repo/graphs/traffic` | Four rendered charts remain visible in widened workspace. |
| `/:owner/:repo/graphs/commit-activity` | Chart loaded on the bounded recheck and passed responsive resizing. |
| `/:owner/:repo/graphs/code-frequency` | Rendered additions/deletions chart expands with visible axes/legend. |
| `/:owner/:repo/network/dependencies` | Dependency listing widens. |
| `/:owner/:repo/network` | Network canvas page widens. |
| `/:owner/:repo/forks` | Empty fork listing widens. |
| `/:owner/:repo/actions/metrics/usage` | Metrics page widens; current repository has an empty data state. |
| `/:owner/:repo/actions/metrics/performance` | Metrics page widens; current repository has an empty data state. |

### Follow-up evidence and limits

`.tmp/github-fluid-width/actions-pageheader-20261016/sitewide-followup/report.json`
records 37 additional requested/discovered URL cases: 36 substantive layouts and
one not-found Gist Shared page. Source digest matches the follow-up above.
Visibility/clipping sentinel self-checks pass. All substantive comparisons have
zero new hiding/clipping, nested owners, or horizontal overflow. Intrinsic
buttons are preserved. The sole recorded aside-width change is Explore's inline
`aside[aria-label="The End"]` feed-ending message, which naturally fills the
widened feed; it is not a navigation rail. Full-width inputs/textareas retain
their native filling behavior.
The native `explore/native.html` and the sanitized `explore-aside-proof.json`
within `sitewide-followup/` establish that label and its 608→940.8px width change.

The parent regenerated the final Gist evidence after the initial delegated
capture cleanup removed its saved artifacts. Only the final parent reports
establish follow-up acceptance; early observations are diagnostic context.
Gist feed text and screenshots were omitted from saved exports to avoid copying
unrelated public code contents. No credential values enter tracked records.
Authenticated identity was verified on both hosts. Browser/driver shutdown and
profile removal are verified in the report.

`sitewide-responsive/report.json` under the same evidence root verifies current
Gist profile and exact revisions layouts at 1280/2048/2560px. Below the desktop
threshold, active/deactivated geometry matches native. At 2560px each owner
reaches 2432px. Live 95→80→95 changes give 1945.6→1638.4→1945.6px at 2048px,
without new hiding/clipping. The Commits graph loaded on this bounded recheck
(one rendered Highcharts graph, no Crunching state) and passed both responsive
widths with no new visibility/clipping issue. All three focused cases pass;
driver/Firefox shutdown and temporary profile removal are verified.

Site-wide execution means both hosts and every path are eligible for the
existing layout engine. It does not force each element to 95%: drawers, menus,
controls, narrow native forms, and already-fluid custom workspaces retain their
native behavior unless they expose an eligible owner. Only the two named hosts
are included; the user explicitly chose to leave `docs.github.com` alone.
