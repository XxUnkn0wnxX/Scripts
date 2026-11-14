# 📌 Prowlarr Big Sur handoff

<!-- Parent sessions: 01a1d3cc-62d1-74b1-8c1d-951301265635 — verified 2026-11-15 using runtime thread/session variables and matching parent rollout session_meta.id with source=cli. -->

[Plan](PLAN.md) · [Checklist](PLAN_checklist.md)

## Checkpoint

- User officially started implementation on 2026-11-15. This folder supersedes the rough outline for execution.
- Scripts checkout on `develop`; base `ac9b29bff007d2c6f9229dbaa5584ffc987c0074`, initially clean. The user initially allowed local commits and prohibited pushing, then explicitly authorized merging to `master` and pushing both branches if the live `--dl pre` test passes.
- Serial execution, no concurrent-agent grant. Source and focused tests are one shared-foundation package; parent owns records/docs/integration.
- Dropped scope: Prowlarr custom update hook, PID/sandbox protocol, detached updater job and update settings.
- New scope: standalone local and download/install modes; configurable default-enabled LaunchAgent handling; preserve original loaded state; plist always under `$HOME/Library/LaunchAgents`.
- Superseding user clarification: `--dl` always replaces from the latest selected stable/pre family; do not add installed-version comparisons, downgrade guards or same-version skips. The user performs actual Prowlarr runtime testing; agent validation stays in logic/disposable fixtures.
- User explicitly requires Astra to double-check the implemented work and evidence before final local commits. This is a final review request, not a request for continuous dedicated planning or concurrent agents.
- User clarified platform/documentation intent: an older-macOS compatibility utility targeting Intel Big Sur11.x; no newer-macOS support claim or test requirement. This does not add a new host-version restriction. The user performs actual Prowlarr runtime testing.
- Read-only reference: `$HOME/Apps/update_jackett.zsh` agent state helpers. Do not modify or run that script.

## Validation and permissions

- Earlier fixture-only limits were superseded by explicit user authorization for one live `--dl pre` test. After focused/native checks and an updated Astra audit, the parent may download/install the actual app and stop/restore its matching originally loaded agent. Never directly launch the app, start an initially unloaded job or edit its plist/settings/data. The local alias is separately authorized; merge/push is authorized only after the live test passes and final review clears.
- Use isolated HOME/app fixtures and simulated commands. A small native patch/sign fixture can use an inert executable copy, never execute it.
- Reuse `.venv` Python 3.14/pytest; no dependency installation required. Add the narrow normal test whitelist for `tests/prowlarr_bigsur/`; `.tmp/prowlarr-bigsur/` remains ignored evidence storage.
- The actual authorized live test has now stopped/restored the matching originally running GUI agent. Its plist hash stayed unchanged, preserving all arguments/environment including the IPv6 workaround. No direct app launch or app-data/settings edit was performed.

## Completion and recovery

- No implementation tasks remain. Astra's final audit passed with notes and no blockers; the authorized live alias update passed with exit 0 and independently verified artifacts/service state.
- Implementation checkpoint: `543af95039eb2bc78491380b1c00e30c42327736`, fast-forwarded to `master` and atomically published to both branches. Both exact remote heads were verified at that revision and the checkout returned to `develop`.
- This documentation-only completion receipt follows that checkpoint; source/tests remain unchanged. Resolve `HEAD` for the receipt revision. The completed rough outline is under `.plans/project-plans/completed/prowlarr-bigsur-patch/`.
- Live app: `/Applications/Prowlarr.app`, version 3.0.1.5752, minimum 11.0, strict signature valid. The single backup is `/Applications/Prowlarr.backup.zip`; local alias `prowlarr-update` is in the existing zsh Scripts section.
- Do not rerun the live updater for documentation checks. Future release/runtime work should start with fresh actual app/agent state and its applicable authorization; the current scoped live test is complete.

## Current implementation and evidence

- Product: `shell/prowlarr_bigsur.zsh`; usage: `docs/shell/prowlarr-bigsur.md`; tests: `tests/prowlarr_bigsur/`. Runtime needs no Python.
- Final frozen-source focused group: **83 passed in 74.35s** (75.83s wall, 32.12s user, 30.79s system), log `.tmp/prowlarr-bigsur/pytest-83-final.log`. Coverage expanded for duplicate paths, one backup ZIP, persistent Downloads, missing/substituted originals, exact user-domain restoration, repeated Ctrl+C and valid-output/nonzero-producer rejection.
- Native fixtures passed on this Big Sur host, including a full patch under `/bin/zsh` 5.8. They proved two-tool and zero-tool preservation, SDK 15.5 retained, both plist minima 11.0, strict recursive signatures after unsigned nested code, mode/xattr preservation, original backup SHA256 parity and a local no-op.
- Current native ZIP/parser proof: `.tmp/prowlarr-bigsur/native-zip.KxsvETIq/RESULT.txt`, `run.log`, `new-parser-run.log`, `new-parser-zero-run.log`. Actual flag0 publication replaced an existing ZIP; CRC, original payload hash and mode/xattr extraction round trip passed. Current parser passed real native patch/sign under Homebrew 5.9.2 with two tools and system 5.8 with zero tools; only one ZIP remains and no service commands/fixture binaries ran.
- Two earlier full-suite parser failures were diagnosed, not hidden with retries. The read-only analyst reported valid tuples with pipeline status147 in 4/600 Homebrew 5.9.2 calls; session isolation did not fix it, while system 5.8 passed 400 calls. Checked output capture plus unchanged awk here-string passed 400 calls. Source removes affected metadata/job/SHA pipelines and propagates tool failures explicitly. Underlying C/runtime cause is unproven. The reported result is preserved in `.tmp/prowlarr-bigsur/parser-diagnosis-summary.md`; `parser-probe.log` records invocations only. Old failure log: `pytest-81-parser-failure.log`.
- Native checks stubbed LaunchAgent commands and LaunchServices registration and never executed fixture binaries. Final fixtures force temporary app destinations and isolated HOME; service and network operations are simulated.
- An earlier fixture accidentally used the default destination before a fake metadata download failed. It read the installed app metadata and created/removed sibling lock/staging directories. It did not patch, sign, replace, launch or control the installed app/service. The fixture now supplies a temporary destination, a shared guard rejects actionable default/out-of-root paths, and a read-only check confirmed zero leftover lock/transaction folders.
- Syntax checks passed for both zsh versions; Python compilation and `git diff --check` passed. Local alias `prowlarr-update` is installed in the Scripts section of ignored `$HOME/.oh-my-zsh/custom/alias.zsh`, with syntax and evaluated help verified; never include that external personal file in repository publication. Authenticated GitHub account and target repository were verified; both remote heads still equal base `ac9b29b...` as of pre-publication inspection.
- Live result: v3.0.1.5752 full app ZIP saved in `$HOME/Downloads` and matched the official GitHub digest. The app was replaced despite the same installed version; minimum 11.0, SDK 15.5 and LD tool 3/version 1167.5 match the selected download, and strict signatures pass. The one `/Applications/Prowlarr.backup.zip` passes CRC and matches the captured original main executable and plist payload. Target `lsregister -f` completed before agent restoration. The same GUI-domain job returned with a new stable running/listening PID and identical plist; no staging/lock remains.
- Exact ignored live receipt directory is selected by `.tmp/prowlarr-bigsur/live-run-path.txt`; read its `before.json`, `update.log`, `selected-asset.json`, `RESULT.json` and before/after job snapshots. Publication is now authorized; broader runtime/future-release/newer-macOS claims remain outside the smoke test.

## Native primitive evidence

The parent tested built-in JXA calling `renamex_np` with exclusive flag `4` on harmless temporary files. Moving to an absent destination succeeded; moving onto an existing destination failed and preserved that destination. Evidence is under ignored `.tmp/prowlarr-bigsur/native-move/`. No application or service was started. This primitive prevents the ordinary `mv` destination-directory nesting race.
