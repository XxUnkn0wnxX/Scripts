# Current layout audit checklist

Authority: `audit.md` records the requested audit scope; the approved product
requirements remain in `.plans/project-plans/completed/github-fluid-width-plan.md`.

- [x] A01 — Workflow header aligns with content using existing width semantics;
  wide and narrow current-page evidence retained.
- [x] A02 — Current affected page-family comparisons reviewed for visibility,
  clipping, overflow, control/rail sizing, nested owners, and missed caps;
  inaccessible or untested surfaces recorded explicitly.
- [ ] A03 — Evidence-backed integration, version/docs, syntax/diff checks, and
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
