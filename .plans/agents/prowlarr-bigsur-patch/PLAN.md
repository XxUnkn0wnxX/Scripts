# 📋 Prowlarr Big Sur standalone script

[← TODO](../../../TODO.md) · [Rough outline](../../project-plans/todo/prowlarr-bigsur-patch/PLAN.md)

Status: **implementation, final review and live validation complete; publication in progress**, started by the user on 2026-11-15. This folder is authoritative for implementation and acceptance.

## Approved interface

Implement `shell/prowlarr_bigsur.zsh` with `#!/usr/bin/env zsh`, suitable for an alias. The user dropped Prowlarr's custom-update-script integration: no PID/sandbox protocol, detached updater job, or update-hook settings.

Position the script and its help/docs as an older-macOS compatibility utility targeting **Intel macOS Big Sur 11.x**, not a general-purpose updater for newer macOS. Use Big Sur-available interfaces. Newer macOS support/testing is not an acceptance requirement or a support claim; the user cannot test it.

| Invocation | Behavior |
| --- | --- |
| No arguments | Patch `/Applications/Prowlarr.app` |
| One app path | Patch that local bundle |
| `--dl` or `--dl stable` | Download, patch, sign and install the latest stable Intel/x64 app |
| `--dl pre` | Use the latest prerelease Intel/x64 app |
| Download mode plus one app path | Use that installation destination |
| `-h` / `--help` | Explain usage/configuration without side effects |

Select the official full `osx-app-core-x64.zip`, never loose Core `.tar.gz`. Distinguish stable/prerelease metadata, paginate as needed, reject drafts or missing/ambiguous app assets, and show version/source. Download mode always replaces with the latest selected family, regardless of the existing version: no current-version checks, downgrade refusal, or same-version skip. It installs to the default app path unless a path is supplied.

The user's 2026-11-15 update requires dynamic GitHub version/asset/URL lookup and persistent downloads: save the selected app ZIP under `$HOME/Downloads` using its upstream filename. Replace an existing matching archive only after the new download is complete and validated; extract the `.app`. Current official app releases use ZIP, so no DMG mounting is involved in this path.

## Configurable LaunchAgent handling

Editable globals must honor exported values: `PROWLARR_MANAGE_LAUNCH_AGENT` defaults to `true`; `PROWLARR_LAUNCH_AGENT` defaults to `Prowlarr`.

- Resolve only `$HOME/Library/LaunchAgents/<name>.plist`, accepting an optional suffix and rejecting paths/traversal. Read its actual Label and preserve the original plist, arguments, working directory and environment.
- In both local and download modes, inspect service state when handling is enabled. Only unload an agent whose executable matches the requested app. Loaded-but-idle KeepAlive jobs count as loaded; never stop an unrelated job.
- Stage and verify before downtime, then recheck binding/state. Abort if the user changed loaded state during preparation. Remember which original user domain owned the job.
- Unload a matching loaded agent, confirm it stopped, replace the app, and restore the same plist only if this script unloaded it. An initially unloaded agent stays unloaded. Missing plists never create/load a service.
- `false` skips all LaunchAgent inspection, plist lookup, unload and reload. The independent refusal to replace an executable used by an unmanaged process remains; callers own service quiescence in this mode.
- Never use Finder `open` or directly run Prowlarr. Match Jackett's restore-only-if-unloaded behavior, adding failure cleanup.

## Transaction and patching

Validate Prowlarr identity, Intel architecture, executable, permissions and native tools. Stage on the installation filesystem using `ditto`, preserving modes and extended attributes. Set relevant plist minima and the main executable's macOS deployment minimum to `11.0`, preserving SDK/build-tool entries. Reject unsupported layouts rather than guessing.

Use an exclusive per-target lock, unique staging and recoverable bundle renames. The user's latest backup preference supersedes persistent uncompressed backups: keep **one `/Applications/Prowlarr.backup.zip`**, create and validate its replacement separately, then atomically replace the old ZIP. A configurable `PROWLARR_BACKUP_ZIP` may select another path for fixtures/custom installations while keeping this default. Keep the old app temporarily for rollback; clean temporary uncompressed copies after successful archival/installation, retaining recovery material only on unresolved failure. Ad hoc sign recursively and strictly verify before replacement and again after installation. A corrected, valid local app is a no-op. Refresh only the target's Launch Services registration. Do not remove quarantine, change Gatekeeper/system policy, or modify application data.

Before attempting new-version startup, installation failures must restore the old bundle and previously loaded service. Immediately before bootstrap, record that the new version may run; after possible startup/migration, do not blindly roll back only the binary. Report errors and retain recovery material. No service-health or Big Sur runtime claim follows merely from successful registration/signing.

The user explicitly confirmed the Ctrl+C boundary: restore the previous app before startup; retain the new app after startup may have occurred. Preserve this behavior and test interruptions on both sides. Reconcile original/backup identities before discarding a candidate: a missing or substituted rollback original must preserve remaining apps and transactions and prevent unsafe startup.

## Tasks and acceptance

| ID | Required outcome and acceptance |
| --- | --- |
| T01.01 | CLI/configuration: help is side-effect-free; defaults, selectors, paths, invalid inputs and both globals verified |
| T01.02 | Download: stable/pre app selection, pagination, missing/wrong assets, failed transfer/digest, unconditional replacement and validated matching-file replacement under Downloads verified with fixtures |
| T02.01 | Patching: preserved metadata, no-op, staged signatures, one validated replacement backup ZIP and safe rollback including missing/substituted originals and Ctrl+C startup boundary; disposable native Mach-O fixture passes strict signing/archive checks |
| T02.02 | Service integration: both modes cover loaded/unloaded/idle/missing/overridden/disabled/mismatched/failure states using simulated commands only |
| T03.01 | Validation: zsh syntax, focused tests, Python compilation, native fixture and diff checks pass; measured cost and simulated/native/live limits recorded; final Astra review of implementation and evidence passes |
| T03.02 | Docs: usage guide, README, TODO/outline, checklist, handoff and audit consistent; userscript docs untouched |
| T03.03 | Authorized live `--dl pre` test: dynamic full-app selection, Downloads archive, app metadata/signatures, one valid backup ZIP and original agent loaded state/plist preserved; agent restart only if originally loaded and handling enabled |
| T03.04 | Add local `prowlarr-update` alias in the existing zsh Scripts section and verify its help invocation without app/service side effects |
| T03.05 | After the live test passes and final review is clear, commit, fast-forward merge to `master` and push both `develop`/`master`; verify remote refs and return to `develop` |

T01.01 is foundational. T01.02/T02.01 share one script; T02.02 integrates their staged result. T03.01 verifies those contracts; final T03.02 follows validated behavior. One coherent serial implementation owner avoids overlapping writers. Parent owns records, integration, documentation and final acceptance.

## Validation boundary

Reuse existing `.venv`/pytest without installing dependencies. Use logic tests with isolated HOME/app fixtures and simulated network/process/service boundaries with modest process counts. Small real-native checks may patch/sign a copied harmless executable, without executing it.

The user subsequently authorized one live `--dl pre` test, including installing the real app and stopping/restoring a matching originally loaded LaunchAgent when handling is enabled. Run it after repaired/new behavior passes focused/native gates and Astra's updated audit. Capture before/after state and plist integrity. Do not start an initially unloaded job, directly launch the GUI/binary or alter app data/settings. This narrowly supersedes the earlier fixture-only boundary. The user separately authorized the local `prowlarr-update` alias, and explicitly authorized merging to `master` and pushing both branches **if the live test passes**. T03.03 follows T03.01; finalize T03.02 records after the live result. Publication remains blocked until that condition and final review are satisfied. Broader runtime testing remains with the user. Lowered declarations do not supply missing macOS/.NET APIs.
