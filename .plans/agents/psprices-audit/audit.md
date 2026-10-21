# PSPrices companion userscript audit — 2026-10-21

Status: capture-based audit, authorized repairs and release publication complete. Both remote branches were verified after the atomic release push. Live availability behavior remains unconfirmed and is documented for follow-up.

## Findings and repairs

| Script | Finding | Local revision |
| --- | --- | --- |
| Checkout Link | New availability root lacks the old native-buy attribute. Its root and nested Retry were counted separately; the new result warning also differs from the older unavailable-store wording. The custom checkout therefore did not mount on captured affected themes. | 1.1.4 recognizes the unique loader/result root, protects the owned panel from matching availability requests/swaps, and adds an independent warning only when the checker is detected. |
| Show Product SKU | Without Checkout Link, new loader/result markup fell through to a general page placement rather than below the native availability card. | 1.0.1.6 places the SKU immediately after the whole native wrapper; with Checkout Link active it remains below the custom checkout card. |

Checkout protection applies to avatars and themes. It validates ownership, current route/product/region, exact target, same origin and the matching availability endpoint. Related fragments and ancestor product navigation remain allowed. A successful Sony SKU lookup still enables the custom action despite PSPrices' unavailable/unconfirmed result. It does not establish cart availability. Lookup failure leaves the action disabled. Native restoration exposes Retry after an intercepted check rather than an indefinite spinner.

The warning reads “Availability is unverified. Adding this avatar/theme to your cart may not work.” The category supplies the item word. Ordinary native purchase panels without the checker show no warning. Presentation-only category changes preserve the checkout mount and native restoration snapshot.

## Evidence

- Baseline commit: `235a86f16700355f99c8bfc917d4e931c94a55e9` on `develop`; this identifies the pre-repair source baseline.
- Fresh public captures include avatar 381220, PS3 theme 332798, PS4 theme 2987438 and supplied theme 2763195. User-provided HAR supplies the initial HTML and result for theme 2997875. Initial and result markup reproduce the reported defect without another capture.
- The captured availability request is a same-site GET to `/game/fragment/availability/<product-id>/<token>`. The saved response returned HTTP 200 with “Could not confirm availability. Please try again later.” This was an application result, not an HTTP failure.
- Earlier anonymous Sony metadata GETs, with redirect following disabled, returned valid regional SKUs for the first four products. Those reads were separate from browser mocks and do not prove purchase availability.
- Baseline browser campaign: 15 cases, three failures on affected checkout loader/result states, 12 other groups passed. Candidate: **22 cases / 133 assertions passed**, 28.352 seconds in the harness, 29.42 seconds command wall time. One disposable Firefox session; driver and Firefox both stopped afterward.
- Command accounting: 36.91 seconds user CPU, 6.93 seconds system CPU and 630,153,216 bytes maximum resident set size reported by macOS time. No second candidate run was needed; saved fixtures and one browser startup kept the expanded validation bounded.
- Offer normalization: 32 shapes plus locale fallbacks passed in 0.13 seconds. Settings VM passed in 0.11 seconds; its obsolete hardcoded 1.1.3 log expectation was updated to require the metadata version exactly.
- Both source syntax checks and `git diff --check` passed. All eight userscript guides retain a matching `Current documented release` line.

### Browser coverage

Saved real theme loader and result states mount Checkout Link; theme 2997875 also proves SKU-first load order. Normal avatar and PS3-theme panels show no warning; affected PS4-theme panels show one. A derived avatar-checker variant uses real avatar metadata with the captured checker contract and proves avatar wording and category-neutral protection; it is not a live avatar-checker capture.

Automatic root requests, a detached native Retry source and late responses are cancelled. The exact custom cards, valid action and one warning survive. Other-product and unrelated-fragment requests are not cancelled; ownership loss releases the guard. Category changes preserve the checkout card and lookup; metadata loss restores the original native Retry visibly with the old spinner hidden.

Standalone SKU cases cover both supplied theme dumps through loader-to-result replacement, plus startup directly on the result. They require the SKU to be visible immediately after the entire native wrapper, without Checkout Link or Sony requests. Other checks cover dummy purchase popup generation, stubbed SKU copy, related HTMX retention, real native-wrapper replacement, native unlocked-SKU fallback, ambiguous category fallback, category refresh, missing-SKU native recovery, lookup failure and scoped promo hiding.

### Safety and limits

All browser fixtures have site JavaScript, event attributes and active navigation removed, with a restrictive CSP. Page network and clipboard/popup APIs are stubbed. A deny-only proxy rejects all external traffic; HTTP and HTTPS canaries verified both paths before fixture injection. All cart/checkout request counts were **zero**. Purchase-link generation used a JavaScript dummy popup; no native purchase or Retry control was activated. Raw HTML, HAR, browser results and harness files stay in ignored `.tmp/psprices-audit/`.

The site resumed rendering the native card during this work, according to the user. A backend change is possible but unproven. The user accepted saved-dump validation and requested a note to revisit the availability bypass/warning on a live affected page. That note is in the Checkout Link guide. Actual native frontend execution, userscript-manager sandbox behavior, signed-in purchase flow and real cart availability remain untested.

For a manual failure-state probe, a temporary AdGuard User rule can block `||psprices.com/game/fragment/availability/$xmlhttprequest,domain=psprices.com`. This can exercise the loader's failure/Retry state only when the server still includes the checker; it does not create a backend unavailable response. The assistant did not install this rule.

## Independent review

Astra's safety/design review identified concrete proxy/sanitization and lifecycle requirements; the parent implemented them. The source reviewer passed the final checkout repair and the standalone SKU delta with no concrete defects. The parent integrated the worker's SKU package and verified the combined production tree in the capture-based browser campaign. The earlier theme-only warning suggestion was superseded by the user's explicit avatar-and-theme requirement.

## Documentation and publication

Both guides have synchronized release lines and bottom collapsible changelogs. Checkout documentation explicitly marks live availability behavior as unconfirmed and asks for a revisit. Publication was initially held for user review. On 2026-10-21 the user explicitly authorized the final guide/version/changelog update, merge into master and push of the scoped source, guides and audit records. Unrelated task files, raw captures and illustrative mockups remain outside this publication.

Tested SHA-256:

- Checkout Link: `035bda3c52d3197f5974a80298102fa3051e949994b262b9e3365c114a8e39be`
- Show Product SKU: `5a61db108f69a0753ab9e3f4172e4c35d37923cb8f32d6aba1d4ff1dec2d2dbb`

## Follow-up HAR: 17:03:51 export

The user supplied a new HAR in the same ignored evidence folder. It contains only two availability GETs: 16:39:45.953 (+11:00), returning HTTP 200 with the unconfirmed-availability notice and Retry (1,453-byte response content), and 16:48:18.668, returning HTTP 200 with the normal native purchase wrapper (18,073 bytes). Both are historical entries; the export contains no requests from the 17:02/17:03 reloads and no blocked/error entries. The shown 200 rows therefore do not establish failure of the newly enabled blocking rules. Why no later availability calls were recorded is unconfirmed; backend availability state or rendering may differ. This follow-up does not confirm the live bypass/warning, and the guide note remains in force. The no-push hold was subsequently superseded by the user's explicit publication instruction. No network requests or source changes were made for this HAR inspection.

## User review and final documentation

The user supplied screenshots showing the normal native purchase/SKU layout and normal custom checkout/SKU layout. These observations do not reproduce the live unavailable path. The user reviewed illustrative warning and standalone-SKU mockups, confirmed that the native alert is thinner in reality, and accepted SKU placement below the whole warning/Retry group. Mockups illustrate placement only and are not runtime evidence. The final Checkout guide specifies warning placement between price and Add to Cart; the SKU guide specifies the 12px gap below native warning/Retry. Both guides preserve matching release lines and bottom collapsible changelogs, and both retain the live-state revisit note.

## Publication receipt

On 2026-10-21, following the user's explicit instruction, release commit `e35820c213d3c7c4cb672bff8e744b376dee04af` was created on develop and master was fast-forwarded to it. An atomic push updated both remote branches, and `git ls-remote --heads origin develop master` verified both at that full commit. A records-only follow-up records completion; the production source hashes above remain unchanged. Final guide checks confirmed Checkout Link 1.1.4 and SKU 1.0.1.6 with bottom collapsible changelogs and live-state revisit notes. All eight userscript guide release lines matched their scripts. Source syntax, whitespace, privacy and independent documentation checks passed. Raw captures, illustrative mockups and the unrelated Reddit audit were not staged. No real cart or checkout requests were made.
