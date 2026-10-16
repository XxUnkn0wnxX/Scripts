# GitHub Fluid Width audit handoff

<!-- Parent session ledger: 01a142c7-acef-7863-b1d6-6c7ef4a0c329; verified from CODEX_THREAD_ID on 2026-10-16. -->

- Task folder: `.plans/agents/gh-fw-fix/`. New sessions may identify this work by
  the folder name `gh-fw-fix` and read this handoff, `audit.md`, and `checklist.md`.
- Branch/base: `develop`, `781e876a5a3eba40e15c4a67ace50a80e114b9fd`.
- Product contract: `.plans/project-plans/completed/github-fluid-width-plan.md`.
  The current user-requested scope and endpoint findings are in `audit.md`.
- Execution was serial. Parent owns integration and these records. All delegated
  work and disposable test browsers have finished; no child writers remain.
- Initial repair and site-wide follow-up implementation/browser acceptance are
  complete. Version remains `1.0.4` under the user's explicit follow-up override.
  Current validated source SHA-256:
  `e30304c43ef8b26783e3bc4a82588ef913bb0419d097cd1eb86a0947fd05ab7a`.
- Publication is authorized to `develop` only, after the version increment.
  Do not update `master` or install into a live userscript manager.
  Remote `master` must remain at the base SHA above.
- Release commit `bedc9321294ee95ae7c9eb6dad78e0351a80dc6b` is published to
  `develop`; remote refs were verified. Published raw source returned HTTP 200,
  version `1.0.4`, and initial repair digest
  `34152b61b2b5c27c0265d58828bd15b0ec73887bb9ded31552617b5fd2bb4659`.
  Follow-up publication is pending final review; its base is `b73eb8a`.

## Accepted behavior

- The workflow's semantic PageLayout header lane now aligns with its content:
  1641.6px at x363.2 in a 2048px viewport, retaining native 24px padding.
  Expanded and collapsed workflow sidebars were checked.
- Current issue lanes, Search results, nested PR conversation, dashboard feed,
  and optional floating issue/PR titles now use observed semantic landmarks,
  component attributes, and direct parent relationships. Older selectors remain
  for existing variants. Existing native floors, gutters and breakpoints remain.
- Issue metadata rail (296px), Search sidebars, dashboard right rail (312px),
  ordinary buttons and toolbar controls retain their intended dimensions.
  Native full-width filters, textareas and reply rows expand with their content.
- Four landmark replacement simulations reclassify owners without nested
  ownership. Live full-width settings and optional-title off/on/off pass.
- A native-visible PR Changes title clone at actual 2048x600 was positively
  checked: visible/hidden/visible, with exactly one visible commit selector and
  preserved tree/review controls throughout.
- Pulse initially exposed real avatar clipping: SVG label x became -280.07
  after chart expansion, with matching screen-coordinate projection. A narrow
  desktop rule gives only image-bearing Highcharts x-axis label bodies intrinsic
  width. It keeps the chart fluid without offsets, fixed chart widths or polling.
  Integrated final source passes 2048→1280→2560→2048 and live 95→80→95 settings;
  bars, axes and avatar remain aligned and visible. Chart width reaches 738px
  at 2048 and 982px at 2560. No new clipping/hiding; controls/rail unchanged.

## Evidence and validation

All raw evidence is ignored under
`.tmp/github-fluid-width/actions-pageheader-20261016/`.

- `focused-fixed/` and `broad-fixed/`: initial 26 representative page cases.
- `semantic-final/`: seven affected cases; resolves the Discussion-list hidden
  loading-panel readiness issue. Pulse clipping remained open in this run.
- `live-final/`: semantic source, live settings, four landmark replacements,
  workflow responsive checks and collapsed screenshot.
- `pulse-and-sticky/`: corrected actual 600px-height positive Changes clone proof.
- `svg-probe/`: actual failing SVG coordinates and uninjected resize control.
- `chart-intrinsic-trial/`: successful broad diagnostic mechanism only.
- `pulse-integrated-final/report.json`: accepted final source digest above,
  narrowed image-only rule, responsive chart geometry and percentage changes.
  Disposable driver and Firefox stopped; profile removal verified.
- The first root report's visibility counters were invalidated after an oracle
  bug. Later reports retain native references and use deliberately failing
  visibility/clipping sentinels to verify the oracle. Earlier recovery snapshots
  are not proof of the actual failing Pulse state.
- Independent Astra reviews accepted the semantic changes with corrections for
  insertion sentinels, direct toolbar targeting and a positive visible clone.
  Final Pulse review: PASS WITH NOTES, accepted image-only scope and integrated
  responsive/percentage-setting checks; those gates now pass.
- Syntax and whitespace checks pass. Independent final organization/privacy
  review passes: 13 Markdown files, 33 relative links, and all moved MKV records
  preserved apart from path changes. No literal personal paths, credential
  values, or private host details were found in the reviewed planning records
  and generic instructions. Published source bytes match the accepted source.
- Evidence was collected from current authenticated Firefox pages in disposable
  profiles. This is representative page/layout coverage, not all GitHub
  variants or every browser/userscript-manager runtime. No account forms or
  workflows were submitted.

## Repository organization and privacy

- `.plans/agents/` holds this task and `feature-mkvutil-rework/` records.
- `.plans/project-plans/` is the broader todo list: the completed GitHub Fluid
  Width and iOS plans are in `completed/`; the Codex repair plan is in `todo/`.
- Old `docs/plan/` and `docs/plans/` directories were removed after moving their
  contents. Relative Markdown links and task-path references were updated.
- Generic root `AGENTS.md` now explains resuming by agent task folder name.
  It contains no personal paths or credentials. Its ignore rules were removed.
  `.plans/` is Git-visible by the user's explicit policy.
- Raw captures and the user-supplied GitHub-only cookie export stay ignored in
  `.tmp/`; no cookie values are printed or published.
- The only ongoing userscript changelog is the collapsible details section in
  `docs/github-fluid-width.md`; source release metadata is `@version`.

## Site-wide follow-up

The user requested a broader coverage/gap map and identified Gist as a miss.
B01/B02 in `audit.md` now pass; A01–A03 remain complete. Gist was excluded by
the old metadata. The fix adds its host-wide match and updates the description;
runtime code is byte-identical to the initial repair. Fresh authenticated Gist
and broader GitHub captures found no additional selector repair requirement.
The semantic parent, native cap, gutter and rail contract is retained. Publication remains
`develop` only. The user explicitly chose to keep `@version 1.0.4` and append
the existing documentation changelog for this follow-up. Use two host-wide
matches (`github.com/*`, `gist.github.com/*`); test endpoints do not become
individual match rules. Leave `docs.github.com` excluded. No live installation.

- `sitewide-followup/report.json`: 37 additional URL cases, 36 usable layouts and
  one not-found signed-in Gist Shared path. All usable comparisons have no new
  hiding/clipping, nested owners or added horizontal overflow.
- Gist coverage includes home, Discover, Forked, Starred, owner profile, the
  exact user-selected gist, its revisions, and its forks. Common capped owners
  grow to 1945.6px at 2048px. No Gist-specific selector was added.
- `sitewide-responsive/report.json`: profile/revisions at 1280/2048/2560px and
  live 95→80→95 settings pass. Commits graph data loaded on the bounded retry;
  the rendered graph also passes responsive checks.
- All current Insights sidebar destinations were checked. Community is in its
  feature-disabled state; Actions metrics and forks have empty data states.
  Project listings were checked; project boards are a separate untested app.
  PR Checks and Notifications are native full-width layouts with no eligible cap.
- Explore's sole recorded aside-width change is its inline feed-ending message,
  not a navigation rail. Intrinsic buttons remain unchanged; native full-width
  controls/callouts grow with their owner. `sitewide-followup/explore/native.html`
  and `sitewide-followup/explore-aside-proof.json` establish the aria-label.
- The final parent captures supersede deleted delegated raw artifacts. Gist
  feed content/screenshots are omitted from exports; no secrets are tracked.
- Both test runs shut down driver/Firefox and removed their disposable profiles.
- Next: final source/docs/records review, commit and push `develop` only; verify
  published bytes/version and remote master, close B03, and report coverage.

## Previous release completion

A01–A03 are complete. No implementation or acceptance work remains. This final
record update follows the verified release publication and is committed on
`develop`; the Git log identifies the final documentation commit without a
self-referential hash. Future changes should start from the user's newly stated
scope, fetch fresh affected endpoint DOM, and update only the dedicated
collapsible changelog for release history. The endpoint tables and verification
limits are in `audit.md` for the final user report.
