# PSPrices companion userscript audit

Requested on 2026-10-21. Audit the Checkout Link and Show Product SKU scripts at the current checkout against fresh public PSPrices markup and bounded local behavior checks.

## Boundaries

- Never send cart-add requests or navigate to checkout/add URLs. Simulate purchase actions locally; block external browser traffic in fixture checks.
- Public product-page GET requests and read-only source inspection are allowed. Use disposable browser state and mocked userscript-manager APIs.
- Preserve account state, unrelated files and Git refs. The user's subsequent request authorizes a bounded Checkout Link fix: bypass the new native availability loader so our panel still mounts, with a small avatar/theme warning only when its availability checker is detected. The user also authorized standalone SKU placement below the new native availability card. Update both guides/versions to describe the verified behavior. Publication was initially withheld; the user subsequently authorized committing, merging into master and pushing both branches.
- Keep records in the user-approved `.plans/agents/psprices-audit/`; raw captures and test artifacts belong in ignored `.tmp/psprices-audit/`.

## Main goal G01: Establish current compatibility and report evidence

| Task | Required outcome | Evidence | Prerequisites |
| --- | --- | --- | --- |
| T01.01 | Trace both scripts' entry points, selectors, lifecycle and side effects; compare with fresh representative product markup. | Source references and sanitized capture findings. | None |
| T01.02 | Exercise representative SKU labeling, checkout-panel rendering, price metadata and navigation/HTMX behavior without external mutations. | Focused local tests and the approved bounded browser checks; explicit untested boundaries. | T01.01 |
| T01.03 | Reconcile findings with an independent read-only reviewer and report compatibility, defects, repairs and limits. | Parent-owned audit record and final report tied to the reviewed revision. | T01.01, T01.02, T01.04, T01.05 |
| T01.04 | Make Checkout Link mount through current availability placeholders/results, retaining prior purchase flows; show a small avatar/theme warning only when the native availability checker is detected. | Exact supplied theme reproduction plus focused local/browser regression checks with all cart traffic forbidden. | T01.01 |
| T01.05 | Mount the SKU panel below the native availability loader/result when Checkout Link is disabled; retain coexistence with Checkout Link. | Standalone saved loader/result browser cases and both-script regression checks. | T01.01 |
| T01.06 | Finalize affected guide versions and bottom changelogs, commit the scoped repairs and audit records, fast-forward master and push develop/master. | Source-digest and documentation checks, scoped commit review and verified remote refs. | T01.03, T01.04, T01.05 |

Completion means the requested audit and evidence report are complete; it does not certify untested cart or signed-in purchase behavior.

## Approved scope update

On 2026-10-21 the user supplied theme `2763195` and a screenshot of theme `2997875`, then requested: bypass the new loader so our panel still mounts and show a small warning that adding themes may not work while availability is unverified. This explicitly authorizes T01.04 and its corresponding checklist entry.

The user clarified that checker detection and the warning apply to both avatars and themes; no detected checker means no warning. On 2026-10-21 the user also requested T01.05 so the SKU card mounts below the new native unavailable card without Checkout Link. The user reports the live card has returned, so saved captures remain the reproduction evidence. Publication was held at this stage until the user gave explicit authorization.

The user accepted validation against saved dumps for standalone SKU placement and the availability repair, requested a short guide note to revisit the live behavior, and retained the explicit no-push gate. Live availability reproduction is therefore an acknowledged follow-up, not a claim made by this audit.

On 2026-10-21, after reviewing normal-page screenshots and the illustrative mockups, the user explicitly instructed: “ensure affected docs are updated also for version & changelog at the bottom bit then merge & push all.” This authorizes T01.06 and supersedes the previous no-push hold for the scoped PSPrices changes and audit records. It does not convert the captured availability-state checks into live confirmation.
