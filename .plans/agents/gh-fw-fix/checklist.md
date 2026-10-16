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

- [x] D01 — Fresh MCP, Copilot, Feed and Search-landing DOM/native findings.
- [x] D02 — Evidence-backed width treatment and affected-layout acceptance.
- [x] D03 — Endpoint report, behavior/changelog docs and develop publication.
- [x] E01 — Full-width override restores/reapplies applicable workspaces and
  has the correct scope on newly checked pages, including Notifications and
  its user-requested Saved filter.
- [x] E02 — Floating issue/PR title hiding and restoration, including review
  of Commits/Checks, preserve regular headings and usable controls.

D01 evidence: `new-surfaces-structure/report.json` plus MCP's rendered direct
root children in `toggles-current/report.json`. MCP results and Feed have
demonstrated missed caps. Copilot's composer/intro and Search landing's local
input/illustration measures remain native by the discretionary layout decision.
Independent Astra D02 review: PASS WITH NOTES. Source/acceptance remain pending.

E01/E02 baseline: `toggles-current/` checks 12 current views at 2048x600;
`pr-secondary-current/` checks Commits plus empty/populated Checks at 2048x400.
Existing full-width targets restore their native widths with the option off;
issue, PR Conversation, Changes and Checks have positive visible/hidden/visible
floating-title evidence. Regular headings survive and Changes retains one
visible commit selector. Short Commits never reveals its native clone, so that
case is not positive hiding proof. Checks demonstrates an unhandled naturally
full-width PR comparison root, including a populated completed-check view.
Repair and final-source toggle acceptance remain open.

E02 final evidence: `followup-final/report.json` on source
`fc83bdd91065eef33efb68c79b1224d3a010dfe38e77465a7a10073192d04e9e`
positively verifies issue, PR Conversation, Changes, longer Commits, and
empty/populated Checks floating titles: visible/hidden/visible. All regular
headings remain rendered; Changes retains one visible commit selector in each
state. The existing header selectors suffice. MCP, Copilot, Feed, Search
landing and Dashboard retain identical owner widths and rendered headings/
controls when the header option changes. `followup-toggle-acceptance.json`
asserts all 17 layout cases and the six positive header cases.

D02 final evidence: `followup-assets-final/` and
`followup-assets-acceptance.json` verify seven current cases, 126 images,
286 SVG icons, 68 viewport/percentage comparisons and five clean landmark
replacements. No asset growth, shrinking, hiding or disconnection is recorded
in the accepted comparisons. Feed/Dashboard rails keep their measured native
widths across both desktop boundaries. MCP keeps its introduction/filter;
Copilot/Search landing remain native. The full-width Checks fallback rejects
a deliberately partial-width root and reclaims it when native fill returns.
E01 remains open for a second demonstrated full-width miss on Notifications;
that page's fresh native baseline is in the same ignored asset report.

E01 final evidence: `notifications-final/` and
`final-followup-acceptance.json` on final source
`34cfdc4b74b7706fade9e8d7bc3cf2e91f3f95a41485cfb7055ca771b3e8300f`
pass both populated All and empty Saved inboxes, 28 responsive/percentage
comparisons, 294 intrinsic-control comparisons, two clean root replacements,
the partial-width rejection/restoration, live override off/on/off, and five
previous-owner regressions. No new hidden/clipped content, asset size changes,
nested owners or document overflow. Saved-filter navigation uses a full page
navigation; the harness reinjects the actual source to simulate manager startup
and verifies one style/owner. It is not credited as retained-instance SPA proof.
Both native proportional inbox columns and padding are preserved. Final browser
and driver shutdown and disposable profile removal are verified.

D03 publication: source/docs commit
`f7b1639f3ef6839f9892316256387138ca10af25` is published to develop.
`published-final-followup.json` records HTTP 200 from both literal raw develop
URLs, exact tested source digest above, exact guide digest
`44e5c3135a9bd273b774ddc1b2f047c2c8e9e3e715452686e6147b1b65399770`,
version 1.0.4, and only the two host-wide matches. Remote master remains at
`781e876a5a3eba40e15c4a67ace50a80e114b9fd`. Syntax, whitespace, current
endpoint tables, four changed Markdown files' relative links and privacy,
and independent final source/docs review pass. This receipt follows verified
publication; Git history identifies its final documentation commit.
