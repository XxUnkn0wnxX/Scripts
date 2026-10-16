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
representative cases, rather than an exhaustive list of GitHub routes. The
initial audit covered 26 cases; follow-up coverage reached 63. These tables
include the subsequently demonstrated Explore and Gist profile repairs.
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
| `/explore` | Preserve both measured native side columns so card avatars keep their size while the center feed expands. |
| `gist.github.com/:owner` | Preserve the measured native profile column, avatar and profile button while the gist list expands. |
| `gist.github.com/:owner/starred` | Apply the same native profile-column preservation to the owner's starred listing. |

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
these nine cases pass the native-versus-modified visibility/clipping checks.

| Endpoint pattern | Result after host enablement |
| --- | --- |
| `/` | Home/create workspace widened with native form/control behavior. |
| `/discover` | Discovery feed widened. |
| `/forked` | Forked feed widened. |
| `/starred` | Starred feed widened. |
| `/:owner` | Owner listing widened; the later native profile-column repair preserves avatar/button size. |
| `/:owner/starred` | Owner's starred listing widened with the same native profile-column repair. |
| `/:owner/:gist` | Gist file/code workspace widened; local scrolling retained. |
| `/:owner/:gist/revisions` | Revision diff workspace widened; controls retained. |
| `/:owner/:gist/forks` | Fork listing widened. |

The exact user-selected gist and revision endpoint were tested. Its `container-lg`
workspace grows to 1945.6px at a 2048px viewport. Host enablement used the existing
`container-xl` profile owner; the later profile-column correction below fixes
the proportional rail/avatar growth missed by the initial checks. The earlier `/:owner/shared`
URL returned not-found; the user corrected it to `/:owner/starred`, which was
fetched and verified. No Shared endpoint is claimed or left outstanding.

### Additional GitHub cases requiring no new repair

These are in addition to the initial 26 page cases. The Insights routes were
read from the current sidebar before capture. Explore's subsequently required
repair is listed above; these other 27 layouts required no new repair. Their
initial comparisons found no newly hidden/clipped content, nested owners or
added horizontal overflow. Data/feature availability is listed separately from
layout behavior.

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

`gist-owner-starred/report.json` verifies the corrected owner-specific Starred
view on the same final source: authenticated, native match at 1280px, wide growth
at 2560px, live 95→80→95 response, and zero new hiding/clipping. This adds one
usable URL to the first batch: 37 usable additional page cases overall, plus the
discarded Shared URL. Browser/driver shutdown and profile removal are verified.

Follow-up source commit `a2c0733c9b02e8d9ced1dd1cb71b5b1e267dbab2` is published
on `develop` only. The literal raw develop URL returned HTTP 200, the exact
validated digest, version `1.0.4`, and the two requested host matches. Remote
`master` remains at `781e876a5a3eba40e15c4a67ace50a80e114b9fd`. The ignored
publication receipt is `published-gist-source.json` in the evidence root.

## Gist profile-size correction requested by the user

The user supplied native/widened screenshots showing the profile avatar and
profile button growing with the widened workspace. The previous visibility and
clipping checks did not test proportional image/rail growth. Continue with:

- C01: Verify fresh native profile DOM and fix only the demonstrated profile
  column relationship. Preserve its measured native width, avatar size, padding
  and status control while the adjacent gist list receives added space.
- C02: Add explicit profile-rail/avatar geometry checks, verify profile and
  owner-Starred views with live width changes and responsive/native restoration,
  and retain unaffected Gist file/revision and GitHub profile behavior. Freshly
  compare rendered image dimensions across the affected main GitHub page
  families as requested, including avatars, profile pictures and content images;
  investigate growth with same-DOM native restoration before accepting it.
- C03: Append the existing collapsible changelog, keep version 1.0.4 under the
  standing user override, update acceptance records, and publish develop only.

Fresh evidence: `gist-avatar-native-probe/report.json` in the existing ignored
evidence root. Native profile rail is 312px including 16px padding per side;
avatar is 280px. Its parent is a two-child flex row. The profile is identified
by `#gist-pjax-container .h-card[itemtype$="schema.org/Person"]`. Source remains
unchanged at the start of this probe. No selector change precedes fresh DOM.

Independent Astra review accepted the measured-column approach with three
requirements: a direct relationship to an actual owning workspace, cleanup of
both column roles independently, and child-list invalidation for either column
replacement or rail removal. All three are implemented. The adapter measures
with fluid styles inactive, preserves the rail's border-box width and padding,
and lets its direct content sibling absorb additional space. It does not set
an avatar size, hard-code a rail width or depend on profile URL paths.

`asset-profile-final/report.json` verifies source SHA-256
`e0654933e4ca88ca444eece80aefae2c138eebee515dd781a6e318c33784ba8c`.
At a 2048px viewport and 95% width:

| Element | Native | Repaired fluid layout |
| --- | --- | --- |
| Gist profile rail, including padding | 312px wide | 312px wide |
| Gist profile picture | 280 × 280px | 280 × 280px |
| Gist profile button | 280 × 32px | 280 × 32px |
| Adjacent gist list | 936px wide | 1601.6px wide |
| Main GitHub profile picture | 296 × 296px | 296 × 296px |

Both Gist `/:owner` and `/:owner/starred` receive this correction. Gist file
and revision pages, and the main GitHub profile, receive no profile-column
markers. Fifty focused settings/viewport comparisons across those five pages
cover 640/1280/2048/2560px, the return to desktop, and live 80%/95% changes.
Rendered image/icon sizes match each same-viewport native state, including
the profile rail, avatar and anchor button. No nested owners or added document
overflow occur. Rail replacement, main-only replacement, rail removal and
reinsertion reclassify correctly; the survivor has no stale marker after
removal. The disposable browser/driver stopped and its profile was removed.

The user explicitly confirmed that content images should retain automatic
sizing as their content workspace widens. The main-site image audit therefore
distinguishes native responsive attachments from unintended avatar/logo/icon
growth. Content images keep their existing CSS sizing and aspect ratios,
including author-defined percentage sizes. No new image-size override is added.

The first fresh size campaign covers 63 substantive page cases: 54 on GitHub
and nine on Gist, with 657 rendered images and 3,482 SVG icons measured. See
`asset-profile-final/report.json` and `asset-sitewide-final/report.json`.
The campaign found an additional real profile-image case on Explore: five
percentage-sized feed-card avatars grow with their containers. This initial
campaign left C02 open for fresh parent-DOM inspection, a bounded repair and
affected-page checks, subsequently completed below.
Other reported growth is automatic content-image sizing on Discussion, Wiki,
Explore and the organization profile. Attachments remain under GitHub control
by the user's explicit follow-up direction. None of those counts is a claim
that the remaining Explore avatar defect has passed.

Fresh Explore parent evidence is in `explore-avatar-parent-probe/report.json`
and its freshly fetched authenticated `fresh.html` (HTTP 200). The actual
owning container has a direct three-column `.gutter-md` flex row, using the
stable global `col-lg-3` / `col-lg-6` / `col-lg-3` grid utilities. The native
side columns are 320px each, with a 640px center feed. Both side columns grow
with the widened parent, causing the demonstrated avatar and side-card growth.
The bounded repair preserves those measured side columns and gives the
center the remaining width. Content images retain GitHub's sizing rules.

Independent Astra review of this delta: PASS WITH NOTES. Keep Gist and the
three-column discovery functions separate and share only the measured rail/main
roles, CSS, cleanup and invalidation. Require direct ownership, the complete
observed grid signature, flex/row/nowrap, exactly three visible children,
unblocked row, no child-role conflicts or nested owners, valid independent rail
measurements and a wider center. Add scoped insertion landmarks. The final
compatibility gate is a census of every eligible/adapted three-column row in a
fresh native-versus-active page pass; manually reconcile any match outside
Explore. Focused Gist and Explore acceptance must use the final source.

The user additionally requested domain-wide documentation and an OpenUserJS
disclosure check. Current official sources reviewed:
[Terms of Service](https://openuserjs.org/about/Terms-of-Service) (complete
descriptions are recommended; source licensing and abuse/obfuscation rules)
and [FAQ](https://openuserjs.org/about/Frequently-Asked-Questions) (relevant
`@antifeature` disclosures). The product guide now lists exactly
`https://github.com/*` and `https://gist.github.com/*`, explains the path wildcard
and top-level-page scope, describes optional title hiding and native image
behavior, and states storage, network/update-source and monetization behavior.
Endpoint acceptance tables stay in this audit. The existing OSI-approved
`AGPL-3.0-or-later` source declaration is retained. No listing was published or
changed on OpenUserJS; this work updates the repository guide.

### Final native-column and site-wide image acceptance

Final integrated source SHA-256:
`208b2a73583be5b90aaa157762aadf8604bdff3b71a9330ce49ebb2a3aefe8e9`.
The ignored `native-rails-acceptance.json` reconciles final-source reports:

- `native-rails-focused-final/`: six views, 64 responsive/live comparisons,
  Gist column replacements/removal, and Explore column/row replacements/removals.
- `native-rails-sitewide-final/`: the other 57 page cases, native-versus-active
  image measurements and the complete eligible three-column-row census.
- `native-rails-hydration-recheck/`: stable native baselines and final comparisons
  for PR Changes, repository Issues and global Pull Requests. Earlier transient
  server-rendered icon references were replaced during page hydration and
  remained gone with fluid styles disabled. Those early references are
  superseded, not counted as intact. Fresh baselines were verified quiet with
  no installed script, style or active flag before injection; all three final
  comparisons have no hidden/disconnected assets or size changes.
- `native-rails-clipping-final/`: six affected views have no newly hidden,
  disconnected or clipped content, nested owners or added document overflow.
  Explore also passes three remove/reinsert tests with all detached role markers
  deliberately stripped, proving the new insertion landmark reclassifies each
  column after survivor cleanup.

| Final check | Result |
| --- | --- |
| Page cases | 63: 54 main GitHub, nine Gist. |
| Rendered image measurements | 658 images; no avatar size changes. |
| SVG icon measurements | 3,482 icons; no icon size changes. |
| Three-column census | Exactly one matching/adapted row, on Explore; no unexpected matches. |
| Explore native side columns | 320px each, retained at all tested desktop widths. |
| Explore center at 2048px / 95% | 640px native → 1305.6px fluid. |
| Explore avatars | 95.3167px and 51.5px native widths retained. |
| Gist native rail/avatar/button | 312px / 280px / 280px widths retained. |
| Main GitHub profile avatar | 296 × 296px retained. |
| Narrow fallback | Native 640/1280px layouts; new rail roles cleared. |
| Content-image resizing | 17 native automatic-size changes across Discussion, Wiki, Explore and organization-profile content; retained by user direction. |
| Disposable runtime cleanup | All sessions closed, browser/driver processes stopped, profiles removed. |

Explore additionally covers the 1472/1668px desktop boundaries and 2560px, with
80%/95% settings and return to 2048px. Gist profile/Starred, file/revisions and
the GitHub profile cover 640/1280/2048/2560px and the return to desktop. No
native rail width varies unexpectedly across those desktop breakpoints.
The repairs use actual owner relationships, the Gist profile microformat and
observed global grid utilities. There are no per-endpoint matches, fixed image
dimensions, global avatar overrides or geometry polling. Version remains
1.0.4; the existing collapsible changelog is the only ongoing release history.

Implementation and browser acceptance are complete. C03 publication verification
remains pending until the tested source is pushed to develop and retrieved back.
