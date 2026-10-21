# PSPrices audit handoff

Parent session ID: unavailable/unverified; no resume ID is asserted.

## Current checkpoint

- Branch `develop`, baseline HEAD `235a86f16700355f99c8bfc917d4e931c94a55e9`. This was the initial pre-publication baseline. The user has now authorized committing and pushing the scoped PSPrices changes.
- Local edits: Checkout Link 1.1.4, Show Product SKU 1.0.1.6 and their two guides. Task records are untracked/Git-visible in the user-selected folder. Preserve unrelated `.plans/agents/reddit-fw-audit/`.
- T01.01–T01.05 complete within the user's accepted saved-dump validation boundary. See [audit.md](audit.md) for findings, reviewed source digests, exact coverage and limits.
- Both scripts passed the combined final capture-based browser run: 22 cases / 133 assertions, zero cart/checkout requests, 28.352s harness / 29.42s command wall time. Firefox and driver cleanup verified. Offer normalization and settings checks passed; all eight userscript guides have matching release lines.
- Independent reviewer passed final checkout and SKU diffs. Worker `sku_availability_mount` completed its two-file package. No delegated write work remains active.

## User authorization and limits

- User selected this task folder and explicitly approved a short disposable-browser campaign using public captures, all cart/checkout requests blocked, and local purchase simulations. No signed-in account automation or real purchase/cart requests.
- The user explicitly authorized checkout availability bypass and a warning for avatars AND themes only when the checker is detected. Without a checker there must be no warning; a valid Sony regional SKU still enables our custom action despite native unavailability.
- The user also requested standalone SKU below the new native unavailable card, without Checkout Link. SKU mounts after the whole loader/result wrapper; both-script mode mounts below the custom checkout card.
- The native card resumed appearing during work. The user accepted saved-dump validation and requested the guide note that live availability behavior is unconfirmed and must be revisited. No backend change is asserted as fact.
- **Publication is now explicitly authorized.** The user directed final documentation/version/changelog checks, merge into master and push all scoped PSPrices changes on 2026-10-21. This supersedes the earlier no-push hold; live availability behavior remains unconfirmed.
- A narrow temporary AdGuard request-block rule was supplied to the user as an optional manual failure-state probe; no host/browser filtering settings were changed. Blocking the endpoint cannot force the checker into HTML if the backend no longer includes it.

## Evidence and recovery

Raw saved captures, HAR, Sony read-only GET results, private harness and result receipts remain in ignored `.tmp/psprices-audit/`. Candidate receipt is `browser-candidate-results.json`; baseline receipt is `browser-baseline-results.json`. The user HAR includes theme 2997875 initial HTML and availability result, so another intermediate capture was unnecessary. Avatar checker coverage is a derived fixture, explicitly disclosed.

The browser harness `browser-audit.mjs` uses deny-proxy canaries, sanitized fixture HTML, restrictive CSP, mocked manager/network/clipboard/window APIs and one disposable Firefox session. Existing cheap checks: `node .tmp/psprices-checkout/offer-normalization-regression.cjs` and `node .tmp/userscript-settings/checkout/settings-vm.cjs`. Do not rerun the browser solely for a documentation change. A relevant source change invalidates affected evidence and requires a focused recheck.

Next action: finish T01.06, commit only scoped PSPrices source/guides/audit records, fast-forward master and push both branches. Verify actual remote refs and retain the documented live-validation limit. Maintain `Current documented release` and bottom collapsible changelogs in both guides. Raw captures/credentials must never be staged.

Follow-up: the user's HAR exported at 17:03:51 contains only two historical availability requests, at 16:39:45.953 and 16:48:18.668 (+11:00). First response is the unconfirmed notice; second returns the normal purchase wrapper. It contains no 17:02/17:03 requests or blocked entries, so the old 200 rows do not prove that current blocking failed. See audit follow-up; no source/docs version change or new browser run was needed.

Publication preparation: production source digests still match the passed 22-case/133-assertion browser run. Both guides now state the exact warning/SKU placement and saved-capture/live-state validation boundary. Preview mockups remain ignored alongside the raw captures; no screenshots or HAR data are to be published.
