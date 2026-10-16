# GitHub Fluid Width audit handoff

<!-- Parent session ledger: 01a142c7-acef-7863-b1d6-6c7ef4a0c329; verified from CODEX_THREAD_ID on 2026-10-16. -->

- Task folder: `.plans/agents/gh-fw-fix/`. New sessions may identify this work by
  the folder name `gh-fw-fix` and read this handoff, `audit.md`, and `checklist.md`.
- Master promotion authorized on 2026-10-16: the user approved merging the
  audited develop release and pushing master. This supersedes the earlier
  develop-only publication restriction. The reviewed source and documentation
  candidate is `f5c12e899b07a5e8a527e3dceccf4ae3d0c3e8b7`; this handoff update
  changes no product code. Earlier publication receipts describe their own
  checkpoints; inspect current Git refs for the latest publication state.
- Documentation relocation: all eight userscript guides now live under
  `docs/userscripts/`, with README and project references updated. Guide
  contents and userscript sources are unchanged. Earlier publication receipts
  describe the documentation's location at those checkpoints.
- Latest follow-up: D01–D03 and E01/E02 implementation, acceptance and
  publication are complete. A–C are completed historical
  checkpoints. The requested MCP, Feed, Copilot, Search landing, Notifications
  and Saved-filter outcomes are reconciled in the current audit tables.
- The user added E01/E02: recheck full-width override and optional floating
  issue/PR header hiding, including PR Commits/Checks and new surfaces. Both
  toggles pass; Checks and Notifications needed additional full-width targets.
- D01 found missed MCP results and Feed workspace caps. Preserve the native
  Copilot composer and Search-landing input/artwork dimensions. Their outer
  workspaces are already fluid. `toggles-current/` and `pr-secondary-current/`
  captured fresh E01/E02 evidence before any new selector.
- The full-width option overrides only GitHub's already-full-width workspaces;
  capped-page widening remains independent. Header hiding covers issues/PRs
  only. This is the user's explicit clarification for the E01/E02 review.
- Astra D02 review passed with notes; the source-only worker package is
  integrated for MCP/Feed and the demonstrated full-width PR Checks gap. The
  parent corrected the Checks target to the outer comparison root before
  testing. The parent owns all browser acceptance and records. Header selectors
  positively pass on issues, PR Conversation/Changes and populated/empty
  Checks; no header selector change was needed. The short initial Commits
  sample had no visible clone; the longer final sample supplies positive proof.
- `followup-final/` completes 17 MCP/Feed/Checks-stage comparisons at 2048x400: no new
  hiding/clipping, nested owners or added document overflow. Live override
  off/on/off passes; a longer Commits view now supplies positive floating-title
  proof alongside issue, Conversation, Changes and Checks. Source digest is
  `fc83bdd91065eef33efb68c79b1224d3a010dfe38e77465a7a10073192d04e9e`.
  `followup-assets-final/` passes responsive assets and insertion behavior.
  Its native Notifications case identified another E01 full-width miss.
  The completed Notifications follow-up is published as recorded below.
- Notifications follow-up: Astra's bounded review passed with notes. The
  final guarded root list now includes `main > .js-notifications-container`,
  using the existing eligibility/fill checks and native proportional columns.
  Fresh Saved-filter DOM was fetched before this selector was added.
  `notifications-final/` passes All/Saved, 28 responsive asset/visibility/clipping
  comparisons, 294 intrinsic-control comparisons, live settings, root/partial-
  width fixtures, Saved-filter full navigation with simulated manager startup,
  and five existing-owner regressions. All campaigns are cleaned up.
  `final-followup-acceptance.json` reconciles current and unchanged-group
  evidence without relabelling earlier source campaigns. Final source digest:
  `34cfdc4b74b7706fade9e8d7bc3cf2e91f3f95a41485cfb7055ca771b3e8300f`.
- Final source/docs commit `f7b1639f3ef6839f9892316256387138ca10af25` is
  published to develop. Both raw develop source/guide URLs returned HTTP 200
  and exact validated bytes. Guide digest:
  `44e5c3135a9bd273b774ddc1b2f047c2c8e9e3e715452686e6147b1b65399770`.
  Version remains 1.0.4 and the only matches are the two named hosts. Master
  remained at the original base at that checkpoint. Receipt:
  `published-final-followup.json`.
  No required task work remains; the final documentation receipt is identified
  by Git history. Live manager installation/OpenUserJS publication were not done.
- Branch/base: `develop`, `781e876a5a3eba40e15c4a67ace50a80e114b9fd`.
- Product contract: `.plans/project-plans/completed/github-fluid-width-plan.md`.
  The current user-requested scope and endpoint findings are in `audit.md`.
- Execution was serial. Parent owns integration and these records. Child writers
  and all disposable browser campaigns have finished and cleaned up.
- Initial repair and site-wide follow-up implementation/browser acceptance are
  complete. Version remains `1.0.4` under the user's explicit follow-up override.
  C01–C03 implementation, acceptance and publication are complete.
  The published source before the D/E follow-up had SHA-256:
  `208b2a73583be5b90aaa157762aadf8604bdff3b71a9330ce49ebb2a3aefe8e9`.
- Earlier follow-up publication was authorized to `develop` only; the user
  subsequently approved master promotion as recorded above. The explicit
  version-increment waiver remains in effect. Live userscript-manager
  installation remains outside this task.
- Release commit `bedc9321294ee95ae7c9eb6dad78e0351a80dc6b` is published to
  `develop`; remote refs were verified. Published raw source returned HTTP 200,
  version `1.0.4`, and initial repair digest
  `34152b61b2b5c27c0265d58828bd15b0ec73887bb9ded31552617b5fd2bb4659`.
  Follow-up commit `a2c0733c9b02e8d9ced1dd1cb71b5b1e267dbab2` is published to
  `develop`. Its then-current raw digest was
  `e30304c43ef8b26783e3bc4a82588ef913bb0419d097cd1eb86a0947fd05ab7a`.
- Native-column repair commit `60043404062967a31ca4f6b5981d05f390ad02bd`
  is published to develop. At that checkpoint, the raw develop URL returned
  the tested native-column digest, version 1.0.4 and exactly the two requested
  host patterns. Master remained at the original base. Historical receipt:
  `published-native-rails-source.json`.

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
  `docs/userscripts/github-fluid-width.md`; source release metadata is `@version`.

## Site-wide follow-up

The user requested a broader coverage/gap map and identified Gist as a miss.
B01–B03 in `audit.md` now pass; A01–A03 remain complete. Gist was excluded by
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
  owner's Starred listing, selected gist, revisions, and forks. Capped owners
  grow to 1945.6px at 2048px. No Gist-specific selector was added at this
  host-enablement stage; the later native-column adapter is recorded below.
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
- The user corrected the unavailable Shared path to `/:owner/starred`.
  `gist-owner-starred/report.json` verifies that signed-in page, responsive
  widths and live percentages. Its browser/profile cleanup passes too. Shared
  is a discarded URL, not an outstanding requested page.
- Final follow-up coverage is 37 usable additional cases, plus the discarded
  URL. Current source is published and matches the tested bytes.
- No implementation or acceptance work remains. This completion receipt follows
  verified source publication; the final documentation commit is in Git history.

## Native-column correction completion

C01–C03 in audit/checklist are complete after user screenshots
showed Gist avatar/profile column growth. The prior clipping oracle missed
proportional sizing. Fresh `gist-avatar-native-probe/report.json` proves native
profile rail 312px/avatar 280px; the widened flex column grows with its 25%
width. Preserve the measured native rail and let only the adjacent main lane
absorb added width. Keep 1.0.4, two host-wide matches, and develop-only authority.
The source adapter is implemented and the native owner-profile geometry,
responsive/live changes and column replacement/removal probes pass. Broader
asset and clipping acceptance is complete; this correction is published.
Gist-only probe source SHA-256 before the Explore delta:
`e0654933e4ca88ca444eece80aefae2c138eebee515dd781a6e318c33784ba8c`.
The user also requested a fresh main-GitHub audit for unintended image/avatar
growth across the affected page families. This is part of C02; prior visibility
and clipping reports alone do not establish that image sizes were preserved.
The first size campaign captured all 63 cases (54 GitHub, nine Gist), measuring
657 images and 3,482 SVG icons. Five Explore avatars initially grew because its
two 25% side columns also widened. Fresh parent DOM proves the direct-owner
3/6/3 global-grid layout. Astra accepted preserving both measured native rails
and giving the center the remainder, subject to a final eligible-row census,
focused responsive/replacement acceptance and shared-role cleanup. The user
explicitly confirmed automatic content/attachment image sizing stays native.
The integrated source now has SHA-256
`208b2a73583be5b90aaa157762aadf8604bdff3b71a9330ce49ebb2a3aefe8e9`.
`native-rails-focused-final/report.json` passes six pages and 64 responsive/live
comparisons, plus Gist and Explore column/row replacements and removals. Both
Explore rails remain 320px; center grows to 1305.6px at 2048px/95%. Main GitHub
profile avatar remains 296px, Gist avatar 280px. The final other-page census and
focused clipping/clean-insertion checks now also pass. The final acceptance
receipt is `native-rails-acceptance.json`: 63 cases, 658 images, 3,482 icons,
zero new avatar/icon size changes, and exactly one three-column match on
Explore. Three early hydration-sensitive cases passed fresh native-quiet
rechecks; no early detached references are counted as preserved. All profiles
are removed and browser/driver processes stopped. Source and product docs are
published on develop; raw-source retrieval matches the tested bytes and remote
master remains at the original base. Version stays 1.0.4. The product guide
also records the exact host-wide matches and runtime/data/update behavior after
checking official OpenUserJS description/disclosure guidance. No OpenUserJS
listing was published or changed.

A01–A03 are complete. No implementation or acceptance work remains. This final
record update follows the verified release publication and is committed on
`develop`; the Git log identifies the final documentation commit without a
self-referential hash. Future changes should start from the user's newly stated
scope, fetch fresh affected endpoint DOM, and update only the dedicated
collapsible changelog for release history. The endpoint tables and verification
limits are in `audit.md` for the final user report.
