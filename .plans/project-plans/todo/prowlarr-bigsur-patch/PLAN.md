# Prowlarr Big Sur patch and update script plan

[← Task index](../../../../TODO.md) · [Back to the toolkit](../../../../README.md)

Date: 2026-11-13. Status: **rough outline — implementation pending**.

Create one dedicated zsh script that patches an installed Prowlarr app for Big Sur and can also serve as Prowlarr's custom update installer. This document records the proposed behavior; publishing it does not authorize implementation, live app launches, service changes, or automatic-update tests.

## Proposed command contract

Planned script: `shell/prowlarr-bigsur-patch.zsh`, with `#!/usr/bin/env zsh` and executable permissions.

| Invocation | Proposed behavior |
| --- | --- |
| No arguments | Patch `/Applications/Prowlarr.app` |
| One `/path/to/Prowlarr.app` argument | Patch that app bundle |
| `-h` or `--help` | Explain usage, dependencies, service boundaries, and updater integration without changing anything |
| Prowlarr's updater arguments | Recognize the validated PID/sandbox/executable contract and hand installation to an independent updater job |

Manual patching must not launch Prowlarr or unload/reload its service. Refuse a running target or a matching loaded KeepAlive job, even when that job temporarily has no PID; it could respawn during replacement. Require the service to have already been unloaded, and recheck immediately before swapping the bundle.

## Shared patching operation

- Validate the Prowlarr bundle identity, requested path, architecture, permissions, free space, and required tools. Use the installed zsh and Apple tools; fail clearly if the required Command Line Tools are unavailable.
- Acquire an exclusive lock shared by manual and updater modes. Validate ownership before recovering stale state.
- Prepare a separate candidate on the installation filesystem and preserve a recoverable original bundle. Preserve file modes and extended attributes when copying.
- Set the applicable plist minimum-version declarations and the main executable's Mach-O deployment minimum to macOS `11.0`. Inspect existing values and slices; preserve SDK and linker/tool metadata rather than hardcoding the values from one release.
- Apply a local ad hoc signature to the app and its nested components, then verify the complete candidate with strict recursive signature checks. Earlier manual work required recursive signing because the bundle includes unsigned nested .NET files.
- Replace the bundle recoverably and refresh only that app's Launch Services registration. Make an already-correct, validly signed installation a no-op.
- Report declared-version, signing, registration, and runtime results separately. Do not remove quarantine attributes or change Gatekeeper/system policy.

## Prowlarr's custom updater contract

The reviewed source is Prowlarr **v3.0.1.5752**, commit `a01c7efcf8be603eed8dc76adfd425ea0172803d`. Recheck the contract when implementing or adapting to a different release.

Prowlarr downloads the update, verifies it, extracts it, and creates an application-data update backup before invoking the script. The script does not need its own downloader. Prowlarr removes the extracted built-in updater and passes these arguments:

| Argument | Meaning |
| --- | --- |
| `$1` | Running Prowlarr PID |
| `$2` | Update sandbox root; extracted application files are under `$2/Prowlarr` |
| `$3` | Currently executing application path |
| `$4` onward | Preserved startup options: currently `/data=…` and `/nobrowser`, when applicable |

Sources: [update preparation](https://github.com/Prowlarr/Prowlarr/blob/a01c7efcf8be603eed8dc76adfd425ea0172803d/src/NzbDrone.Core/Update/InstallUpdateService.cs#L105-L150), [script invocation and arguments](https://github.com/Prowlarr/Prowlarr/blob/a01c7efcf8be603eed8dc76adfd425ea0172803d/src/NzbDrone.Core/Update/InstallUpdateService.cs#L198-L227), and [preserved startup arguments](https://github.com/Prowlarr/Prowlarr/blob/a01c7efcf8be603eed8dc76adfd425ea0172803d/src/NzbDrone.Common/EnvironmentInfo/StartupContext.cs#L61-L79).

The updater interface requires no special event environment variables, API key, or callback. On macOS, Prowlarr executes the supplied path directly, so the script needs a valid shebang and executable permissions. It launches asynchronously, redirects output, and does not wait for installation completion or check the script's final exit status. Maintain a durable updater log and transaction state rather than relying on Prowlarr to report completion. Sources: [process launch](https://github.com/Prowlarr/Prowlarr/blob/a01c7efcf8be603eed8dc76adfd425ea0172803d/src/NzbDrone.Common/Processes/ProcessProvider.cs#L109-L198) and [platform-specific command handling](https://github.com/Prowlarr/Prowlarr/blob/a01c7efcf8be603eed8dc76adfd425ea0172803d/src/NzbDrone.Common/Processes/ProcessProvider.cs#L355-L373).

The extracted update contains loose application files, not a complete `.app`. Build a fresh `Contents/MacOS` payload without overlaying obsolete files, preserve the bundle's plist/resources, and refresh its version metadata from an authoritative package source. Identify and validate that version source before implementation. [Prowlarr's app packaging](https://github.com/Prowlarr/Prowlarr/blob/a01c7efcf8be603eed8dc76adfd425ea0172803d/build.sh#L178-L195)

## LaunchAgent integration and update sequence

Support the existing per-user LaunchAgent at `$HOME/Library/LaunchAgents/Prowlarr.plist`, with label `Prowlarr`. Its relevant behavior is direct executable startup, `-nobrowser`, `KeepAlive=true`, and `RunAtLoad=true`. Reloading the same plist preserves its working directory, arguments, and environment, including any existing IPv6 workaround. Do not permanently rewrite the plist.

1. Validate the updater arguments, target bundle, and service ownership. Claim the payload into a private transaction directory outside the entire Prowlarr sandbox before expensive work; a later update can delete the sandbox. Handle missing or incomplete payloads without touching the installed app.
2. Start an independent temporary launchd updater job with its own logging and file descriptors. Confirm that it has accepted the transaction and lock before the entry script exits. Exit traps must not remove state owned by the worker.
3. Keep Prowlarr running while the worker constructs, patches, signs, and verifies the replacement. A successful payload-directory rename alone does not prove completeness if sandbox cleanup had already begun.
4. Revalidate the loaded job's domain, owner, executable, and current PID. Unload only the matching Prowlarr job and wait for it to stop.
5. Swap in the verified candidate, preserve the old bundle, and refresh the target's Launch Services registration.
6. Record that the new version **may run** immediately before bootstrapping the original plist. `RunAtLoad` can start the application before `bootstrap` returns; its exit status does not prove whether startup occurred.
7. Report the outcome, finalize recovery information, and release transaction resources before removing the temporary updater job.

The separate job is essential to this design: Big Sur's `launchd.plist(5)` manual documents cleanup of remaining processes in a departing job's process group. A background child or `nohup` alone does not establish that the updater will survive unloading Prowlarr. Verify the independent-job handoff in an explicitly authorized native test before claiming reliable automatic updates.

When implemented and validated, configure Prowlarr's update mechanism as **Script** and supply the script's absolute path. Strict recognition of Prowlarr's argument format allows the same executable to serve both interfaces without requiring extra flags in that setting.

## Failure recovery and validation

- Preparation, payload, patching, or signing failures must leave the current installation and running service untouched.
- Before attempting to start the new version, installation failures can restore the original bundle and the previously loaded service. Preserve the original loaded/unloaded state.
- Once bootstrap is about to be attempted, treat the new version as potentially started. Do not blindly restore only the old executable after a possible database migration; retain recovery evidence and use a deliberate procedure with the matching application-data backup.
- Use bounded waits, clear exit/error reporting, persistent updater logs, and recoverable state for interrupted transactions. Avoid two updater/manual instances changing the same installation.
- Begin with disposable bundle fixtures and simulated service commands. Cover help/path parsing, loaded-but-idle KeepAlive jobs, lock handoff, disappearing/incomplete payloads, patch/signing failures, failure between bundle renames, and bootstrap failure after possible startup.
- Keep actual app launches, service changes, and end-to-end automatic-update tests separately authorized. Fixture success does not establish native launchd behavior or runtime compatibility.

## Implementation checklist

- [ ] Recheck the target release's updater arguments, payload layout, package-version metadata, and available native tools.
- [ ] Implement the CLI, preconditions, locking, shared staging/patch/sign operation, and recoverable manual replacement.
- [ ] Implement updater argument recognition, stable payload ownership, and confirmed handoff to an independent launchd job.
- [ ] Implement the service stop/swap/reload sequence, transaction logs, and recovery boundaries.
- [ ] Add focused disposable-fixture coverage and documentation under `docs/shell/`.
- [ ] Obtain explicit authorization before native app-launch, service, or end-to-end update validation; record the actual outcomes and remaining limits.

## Evidence and open limits

Earlier manual patching established that the plist and main executable can declare macOS `11.0`, recursive local signing can pass strict verification, and Launch Services can clear `unsupported-format`. A separate `launch-disabled` flag remained; Finder launching and application runtime were not tested. Do not treat that flag alone as a diagnosis or claim it has been resolved.

The inspected updater path has no explicit minimum-macOS-version gate, but update-server filtering, future package availability, and future .NET/macOS API requirements remain unverified. This script would automate the declared-version workaround; lowering metadata cannot supply missing operating-system APIs.
