# ✅ Prowlarr Big Sur acceptance checklist

[Plan](PLAN.md) · [Handoff](PLAN_handoff.md)

| ID | Mirrored acceptance | Status / evidence |
| --- | --- | --- |
| T01.01 | Side-effect-free help; CLI defaults/selectors/paths/errors and exported/editable globals | Accepted: final 83-case group and Astra PASS WITH NOTES; duplicate bare/stable/pre destinations rejected before side effects, settings/defaults/help pass. |
| T01.02 | Stable/pre full app selection, pagination, assets, transfer/digest, unconditional replacement and validated matching-file replacement under Downloads | Accepted: dynamic release/archive/failure cases pass; live prerelease download independently verified against the official asset digest and full app payload. |
| T02.01 | Preserved metadata, no-op, signatures, one validated replacement backup ZIP, safe missing/substituted-original rollback and Ctrl+C boundary, native fixture | Accepted: native/fixture archive, identity, signal, attributes and rollback gates pass; live app and backup payload/signature checks pass. |
| T02.02 | Loaded/unloaded/idle/missing/overridden/disabled/mismatched/failure service states in both modes; simulation only | Accepted: simulated state/failure cases and exact gui/user arguments pass. Additional authorized live matching GUI agent was restored running/listening with unchanged plist. |
| T03.01 | Syntax, focused tests, Python compilation, native fixture and diff checks; cost and coverage limits; final Astra implementation/evidence review | Accepted: 83 passed in 74.35s, final reporting-only 4 cases passed in 6.48s, both interpreters/native/compile/diff gates pass; Astra PASS WITH NOTES, no remaining blockers. |
| T03.02 | Usage guide/indexes/records consistent; userscript docs untouched | Usage guide and README row added; older-macOS positioning consistent. Completion/status records await final audit. Userscript docs untouched. |
| T03.03 | Authorized live prerelease install: dynamic app selection, Downloads archive, app metadata/signature, one backup ZIP and original agent state/plist preserved | Accepted: updater exit 0 for v3.0.1.5752; full ZIP/digest, same-version replacement, minOS 11, SDK 15.5/tool tuple, signatures, original ZIP payload, unchanged plist and new stable running/listening PID verified. |
| T03.04 | Local `prowlarr-update` alias in existing zsh Scripts section; safe help verification | Added to ignored local `$HOME/.oh-my-zsh/custom/alias.zsh`; syntax and evaluated help invocation passed. No app action invoked by alias validation. |
| T03.05 | Conditional commits, fast-forward `master`, both-branch push and verified remote refs; return to `develop` | Authorized only after live test passes and final review clears. Pending. |
