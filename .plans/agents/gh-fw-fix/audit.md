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
