# 🔎 Prowlarr Big Sur audits

[Plan](PLAN.md) · [Checklist](PLAN_checklist.md)

## 2026-11-15 — initial architecture audit

Independent Astra planner result: **PASS WITH NOTES**. Parent accepted the findings as implementation guardrails within the approved contract:

- Record restoration intent before unloading; reconcile failures/timeouts and use idempotent EXIT/HUP/INT/TERM cleanup.
- Match the loaded job and original on-disk plist to the canonical target executable. Program takes precedence over ProgramArguments. Preserve the exact user domain and reject changed/ambiguous binding.
- The disabled toggle must bypass all service lookup/query/mutation, including cleanup. Local no-op must not stop a service.
- Keep explicit states for verified candidate, moved original, installed candidate, verified installation and possible startup. Prevent directory nesting if the destination reappears during rename. Roll back only before bootstrap might have run the new app.
- Preserve every SDK/build-tool tuple; reject unsupported Mach-O layouts and prove the native edit on a disposable fixture without executing it.
- Use isolated, stubbed command boundaries for service/network/registration tests. Verify failures and signals as well as normal loaded/unloaded behavior.

No live application/service tests were performed. Same/older-version download replacement is required by the user's clarification. Local commits are permitted; push is prohibited.

## 2026-11-15 — parent integration review of first draft

Result: **REVISE before acceptance**. The first compact source/test draft was not ready for production: Big Sur does not support its `plutil -extract ... raw` reads, its identity check rejected the actual upstream bundle ID, and its local no-op failed to check the minimum-version fields. Review also found missing-target installation, lock setup, loaded-job binding, unload waits and recovery ownership problems. Simplified fake tools masked native compatibility defects.

The follow-up must use compatible plist reads and actual bundle identity, strengthen no-op/transaction/service guards, use exclusive non-nesting native renames, and make fixture behavior faithful to the real native/JSON interfaces. No scope or acceptance requirements were lowered. Final Astra implementation review remains pending.

## 2026-11-15 — integrated source and fixture review

The serial compatibility repair passed 39 tests in 34.03s. Parent integration then added original-directory identity checks, post-rename recovery ownership verification, retained transactions on unexpected destination changes, bounded network waits, zero-tool handling and validation that plist/executable paths stay inside the bundle. Existing destinations must identify as Prowlarr before replacement; no installed-version comparison was introduced.

The expanded focused group passed **58 tests in 40.12s** (41.29s wall, 18.81s user, 17.17s system). Coverage includes both release families, default stable, draft/pagination/asset/transfer/digest cases, unconditional replacement, loaded/unloaded/custom/disabled/mismatched agents, local no-op without bouncing a loaded agent, unload errors before/after actual unload, bootstrap ambiguity, signals after either rename, competing locks and an ownership change during rollback. Eight service/override/bootstrap cases additionally passed in 11.27s under a deliberately unrelated inherited agent-name export after diagnostic and fixture-environment polish.

Test-cost improvement: 52 cases previously took 55.74s. Using native Apple plist tools when available, with portable fallbacks elsewhere, improved fidelity and reduced the expanded 58-case group to 40.12s. Service/network/signing/process boundaries remain simulated and the runner stays serial; no dependency installation or broad repository suite was needed.

One earlier fixture used the default destination before a fake metadata request failed. It read the actual installed app metadata and created/removed sibling staging/lock directories, without patching/signing/replacing/launching the app or controlling its service. The corrected fixture supplies a temporary path; shared fixture guards now reject actionable default or out-of-root destinations. Read-only confirmation found zero leftover default-target lock/transaction directories. This exception is recorded rather than claiming every earlier probe was isolated.

## 2026-11-15 — real Big Sur native fixture

Result: **PASS** using disposable app bundles containing an inert thin Intel slice copied from a system executable. No fixture executable was run. LaunchAgent and LaunchServices commands were replaced with logging stubs; the forbidden-agent log remained absent.

- Main executable deployment minimum changed from 12.0 to 11.0. SDK 15.5, numeric LD 3/version 1167.5 and CLANG 1/version 17.0 were preserved.
- A separate zero-tool build command remained zero-tool after patching.
- Global and existing Intel-specific plist minima became 11.0.
- A deliberately unsigned nested executable was signed, and real `codesign --verify --deep --strict` passed after installation.
- Executable mode 755 and a fixture extended attribute were preserved; the retained original executable matched its captured SHA256.
- Repeating local patching returned a no-op and did not register the app a second time.
- A full patch/sign run also passed under Big Sur's built-in `/bin/zsh` 5.8.

Ignored evidence: `.tmp/prowlarr-bigsur/native.cgyymmhF/RESULT.txt`, `first-run.log`, `second-run.log`, `after-build.txt`, `zero-after-build.txt`, `builtin-zsh-run.log` and retained fixture/backup bundles. The initial fixture preparation was adjusted to select a thin Intel slice; unsupported universal main executables are intentionally refused by the product.

Both zsh syntax checks, Python fixture compilation and `git diff --check` passed. Real Prowlarr startup, real LaunchAgent behavior, end-to-end live downloads and newer-macOS behavior remain unverified. The user owns actual Prowlarr runtime testing. Documentation positions the utility only for older macOS/Intel Big Sur; no newer-macOS support claim is made.

## 2026-11-15 — final Astra review and subsequent user scope update

Astra result: **REVISE before acceptance**. P1: cleanup must distinguish an original rename that never happened from a rollback original that disappeared or was substituted after moving. Preserve candidate/transaction and prevent startup when recovery identity is unresolved; verify the original before restoring/discarding anything. P2: download parsing must reject duplicate destinations for bare/stable/pre forms before side effects. A selectable service fixture domain should also prove exact `user/` restoration arguments.

The user then authorized a live `--dl pre` install/service-state smoke test after the audit gates. Downloads must persist under `$HOME/Downloads`, use dynamically discovered full-app filenames/URLs and replace matching files after successful validation. Backup preference changed to one `/Applications/Prowlarr.backup.zip`: validate its replacement before replacing the old archive, and clean successful temporary uncompressed originals. The user explicitly selected Ctrl+C rollback **before startup**, retaining the new app after startup may have occurred. These direct user instructions authorize the corresponding plan/checklist updates; no prior acceptance gate was silently lowered.

Updated implementation/native evidence and independent Astra delta review: **pending**. Live test has not yet run.

## 2026-11-15 — repaired transactions, archive flow and compatibility diagnosis

The prior Astra P1/P2 findings are repaired: recovery checks original identities before moving/discarding a candidate, preserves unresolved objects/transactions and prevents unsafe bootstrap; download mode rejects all duplicate-destination forms before side effects. Domain-selectable fixtures now assert complete `gui/` and `user/` restore arguments. Cleanup ignores repeated interruption signals while finishing recovery. Downloads and backup archives use validated temporary files followed by native non-nesting atomic replacement; the backup ZIP is published only after creation and CRC validation. The temporary original is removed after success only when its identity and the published ZIP identity remain expected.

An81-case parent run exposed two intermittent parser failures despite valid mock metadata. Independent diagnosis reproduced4 failures across600 exact calls under Homebrew zsh 5.9.2: valid tuple stdout, producer status0, awk/overall status147. Session isolation did not resolve it. Built-in zsh 5.8 passed 400 calls. Capturing checked `otool` output before feeding unchanged awk through a here-string passed 400 calls on 5.9.2. Status147 corresponds to128+SIGCONT on this host, but explicit signal probes did not establish the underlying C/runtime cause.

The source now avoids that pipeline pattern in metadata, loaded-job parsing and SHA extraction; it does not retry or ignore failed statuses. New negative cases prove valid-looking output from failed metadata/hash producers still aborts and preserves the original app/cache. The frozen-source final suite passed **83 tests in 74.35s** (75.83s wall, 32.12s user, 30.79s system). Evidence: `.tmp/prowlarr-bigsur/pytest-83-final.log` and `pytest-producer-errors.log`; the earlier failure is preserved as `pytest-81-parser-failure.log`. Probe outcomes above are attributed to the read-only analyst's report, preserved as `parser-diagnosis-summary.md`; `parser-probe.log` contains invocation lines only. Compared with the earlier 79-case 93.09s run, the expanded final group costs less; native fixture helpers and fewer pipeline processes retain meaningful coverage with one serial runner.

Real native ZIP proof passed with built-in zsh 5.8: flag0 replacement over an existing archive, native ditto/unzip CRC, original executable SHA256 and mode/xattr round trip, successful cleanup with zero transaction leftovers and zero agent calls. The updated parser then passed native two-tool patch/sign on Homebrew 5.9.2 and zero-tool patch/sign on system 5.8, replacing the same single backup ZIP. Evidence: `.tmp/prowlarr-bigsur/native-zip.KxsvETIq/RESULT.txt` and its run logs.

Both zsh syntax checks, Python compilation and diff checks pass. The local `prowlarr-update` alias was added and its help verified. The user additionally authorized merging to `master` and pushing both branches **if the live test passes**; the initial no-push restriction is superseded only under that condition. Actual read-only preflight confirms the loaded-job/absence output contract and installed version 3.0.1.5752; the live install remains gated on Astra's delta audit.

## 2026-11-15 — Astra delta acceptance

Result: **PASS WITH NOTES; no blocking findings remain.** Astra verified that its original identity-recovery and CLI findings are repaired, the new archive flow and confirmed interrupt boundary are implemented, and the final 83-test/native receipts support T01/T02/T03.01 acceptance. One reporting correction now points post-start failures at the actual retained backup ZIP; four affected tests passed in 6.48s, including assertions against phantom original paths. Astra explicitly found another full/native rerun unnecessary for that reporting-only change.

The code/evidence gate is clear for the authorized live prerelease test. Refresh before-state, compare installed SDK/tool fields against the selected downloaded executable, verify the original payload in the backup ZIP, unchanged plist and restored running/listening service. Publication remains conditional on that live result. The external local alias is not part of repository publication.

## 2026-11-15 — authorized live prerelease smoke test

Result: **PASS**, updater exit status **0**, using the local `prowlarr-update --dl pre` alias with enabled handling, the `Prowlarr` plist name and default backup ZIP. Fresh before-state was captured immediately before execution.

- Dynamically selected **v3.0.1.5752**, with official full `Prowlarr.develop.3.0.1.5752.osx-app-core-x64.zip` saved under `$HOME/Downloads`; its SHA256 independently matched GitHub's asset digest and its `.app` payload was inspected.
- The existing app was replaced even though the installed version was also3.0.1.5752. Directory identity changed, proving unconditional same-version installation.
- Installed global minimum and Mach-O minimum are11.0. SDK 15.5 and numeric LD 3/version 1167.5 match the **selected downloaded executable**. Strict recursive signature verification passed independently.
- The one `/Applications/Prowlarr.backup.zip` passed CRC; archived original executable and Info.plist hashes match the fresh captured original. Temporary transaction/lock folders were removed.
- Targeted LaunchServices `lsregister -f` completed before restoration. The original matching GUI-domain LaunchAgent returned with a different PID, confirmed running/listening across bounded smoke-check samples. Its plist hash is unchanged, preserving the existing arguments/environment.

This validates that selected release and update/service path on the tested Intel Big Sur host. It does not establish future-release, newer-macOS or full application/indexer behavior. The user-authorized publication condition is satisfied; commit/merge/push may proceed. Raw snapshots and `RESULT.json` are ignored under the directory pointed to by `.tmp/prowlarr-bigsur/live-run-path.txt`; no private paths/configuration are published here.

## 2026-11-15 — publication receipt

Implementation commit `543af95039eb2bc78491380b1c00e30c42327736` was fast-forward merged to `master` and atomically pushed to `develop` and `master` after the live pass. Exact remote refs matched that revision; the checkout returned to `develop`. This documentation-only completion receipt updates project status and the completed-outline location without changing the validated source/tests. No userscript documentation, personal aliases file or ignored evidence was published.
