# Current layout audit checklist

Authority: `audit.md` records the requested audit scope; the approved product
requirements remain in `.plans/project-plans/completed/github-fluid-width-plan.md`.

- [x] A01 — Workflow header aligns with content using existing width semantics;
  wide and narrow current-page evidence retained.
- [x] A02 — Current affected page-family comparisons reviewed for visibility,
  clipping, overflow, control/rail sizing, nested owners, and missed caps;
  inaccessible or untested surfaces recorded explicitly.
- [x] A03 — Evidence-backed integration, version/docs, syntax/diff checks, and
  user-facing results with limitations complete.

A01 evidence: `.tmp/github-fluid-width/actions-pageheader-20261016/focused-fixed/report.json`, source SHA-256
`277d07ea1c8122378f9df2e5cdf400a761224a060c2742a794001cae19ae16ba`.
Authenticated header/content both 1641.6px at x363.2 at 2048px; 24px native
padding retained. 1280px native behavior and 2560px expansion verified without
reinjection. Corrected visibility/clipping oracle detects deliberate sentinel
failures and finds no new loss on workflow/source/issue/Search. Initial
`.tmp/github-fluid-width/actions-pageheader-20261016/report.json` visibility counts were invalidated and do not establish a pass.

A02 evidence: 26 representative page cases reconciled in `audit.md`. Semantic
adapter checks, live settings and four landmark replacement simulations pass.
`pulse-and-sticky/` proves the optional Changes clone from a native-visible
state; `pulse-integrated-final/report.json` closes the last clipping issue on
final source SHA-256
`34152b61b2b5c27c0265d58828bd15b0ec73887bb9ded31552617b5fd2bb4659`.
Those evidence folders are under
`.tmp/github-fluid-width/actions-pageheader-20261016/`.
The final Pulse chart and avatar remain aligned at 1280/2048/2560px and after
live percentage changes to 80 then 95. No new hidden/clipped content, rail/control
changes or added horizontal overflow remain in the accepted affected captures.
Disposable browser/driver shutdown and profile removal are verified.

A03 evidence: release commit `bedc9321294ee95ae7c9eb6dad78e0351a80dc6b`
published to `develop`. Published raw userscript returned HTTP 200, version
`1.0.4`, and the exact validated source digest above. Remote `master` remains
`781e876a5a3eba40e15c4a67ace50a80e114b9fd`. Syntax, whitespace, staged privacy,
13 Markdown-file/33-link checks, and independent relocation/privacy review
pass. MKV records differ only in moved path references and deeper link prefixes.
Endpoint tables and validation limits are retained in `audit.md` for reporting.

- [x] B01 — Fresh site-wide coverage map, including Gist and Insights siblings.
- [x] B02 — Evidence-backed coverage repairs and affected-page acceptance.
- [x] B03 — Reconciled report, release documentation and publication verification.

B01/B02 evidence: `sitewide-followup/report.json` and
`sitewide-responsive/report.json` under the existing ignored evidence root.
37 additional cases: 36 usable layouts, one not-found Gist Shared path. All
usable comparisons have no newly hidden/clipped content, nested owners or added
horizontal overflow. Gist profile/revisions pass responsive and live percentage
changes. The initially loading Commits chart rendered on the bounded recheck.
Feature-disabled Community, empty metric/fork data states and project-listing
versus board scope are explicitly distinguished in `audit.md`.

Only metadata changes: two host-wide matches, updated description, unchanged
runtime body and unchanged `@version 1.0.4` by explicit user direction.
Validated follow-up SHA-256:
`e30304c43ef8b26783e3bc4a82588ef913bb0419d097cd1eb86a0947fd05ab7a`.

B03 evidence: the user corrected Shared to owner-specific Starred.
`gist-owner-starred/report.json` verifies that exact authenticated view,
responsive widths and live percentages with no new hiding/clipping. The final
follow-up covers 37 usable additional cases and one discarded URL. Source
commit `a2c0733c9b02e8d9ced1dd1cb71b5b1e267dbab2` is published to `develop`;
the raw develop URL returns exact tested bytes, version 1.0.4, and two host
matches. Master remains at its original base. Syntax, whitespace, metadata and
runtime equivalence, docs/privacy and final evidence review pass.

- [x] C01 — Preserve the measured native Gist profile column and avatar size.
- [x] C02 — Explicit size, live settings, responsive and affected-page checks,
  including fresh main-GitHub image/avatar growth comparisons and repair of
  demonstrated unintended avatar growth.
- [x] C03 — Changelog, acceptance records and develop-only publication verified.

C01/C02 final evidence: `native-rails-acceptance.json` under the existing ignored
evidence root reconciles final-source reports `native-rails-focused-final/`,
`native-rails-sitewide-final/`, `native-rails-hydration-recheck/` and
`native-rails-clipping-final/`. Source SHA-256:
`208b2a73583be5b90aaa157762aadf8604bdff3b71a9330ce49ebb2a3aefe8e9`.
63 cases (54 GitHub, nine Gist), 658 images, 3,482 SVG icons, no avatar/icon
size changes. The new three-column signature matches only Explore. Six
affected-view comparisons find no new hiding/clipping or document overflow;
64 responsive/live comparisons and three insertion tests with deliberately
stripped markers pass. All disposable profiles and browser/driver processes
are cleaned up. Attachments and other content images keep native automatic
sizing by explicit user instruction. OpenUserJS official description/disclosure
guidance was checked and reflected in the product guide's domain-wide scope,
behavior, permissions, data and update-source descriptions.

C03 evidence: source commit `60043404062967a31ca4f6b5981d05f390ad02bd`
published to develop. `published-native-rails-source.json` records HTTP 200
from the literal raw develop URL, exact tested digest, version 1.0.4 and only
the two host-wide matches. Remote master remains at
`781e876a5a3eba40e15c4a67ace50a80e114b9fd`. Syntax, whitespace, metadata,
product-guide disclosure and changed-file privacy checks pass. This receipt
is committed after verified source publication; the final documentation commit
is identified by Git history.
