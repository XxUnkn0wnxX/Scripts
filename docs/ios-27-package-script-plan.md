# iOS 27 package script plan

Status: deferred agent handoff; implementation has not started. Recorded on 2026-09-23.

Source: [ChatGPT — iOS 27 package update script](https://chatgpt.com/c/6ab38f6a-6608-83ec-a3a5-bd9e856f20eb), last updated 2026-09-23 at 08:50 UTC. Read through MCP, including the final correction after the catalog evidence was supplied.

Implementation: [`shell/fetch-ios-pkgs.zsh`](../shell/fetch-ios-pkgs.zsh). Current usage: [`fetch-ios-pkgs.md`](fetch-ios-pkgs.md). Task index: [`TODO.md`](../TODO.md).

## Instructions for the next agent

When asked to implement this plan, own the fix through code changes, focused offline tests, documentation updates, and final review. This document contains the working diagnosis and scope; reopening ChatGPT is optional for deeper evidence, not a prerequisite for starting.

1. Read applicable repository instructions and inspect the current branch, working tree, and script. This handoff was prepared on `develop`; preserve any unrelated work present when resuming.
2. Reproduce the filename mismatch with a small valid catalog fixture, then implement selection within catalog products. Choose the parser based on actual legacy-host tooling; resolve routine implementation choices without sending them back to the user.
3. Follow the implementation and validation checklists below. Keep the initial change focused on the two known filenames and same-product URL selection. Treat the separate follow-up questions as optional future work unless evidence makes one necessary for correctness.
4. Deliver the reviewed code, relevant tests, updated usage documentation, and a concise account of what passed and what remains unverified. Keep live-install validation explicitly pending if it has not been requested.

Expected files to change are `shell/fetch-ios-pkgs.zsh`, `docs/fetch-ios-pkgs.md`, this handoff, and the iOS entry in `TODO.md`, plus a focused test/fixture location chosen under repository conventions. No unrelated script refactor or dependency installation is needed just to start.

## Goal

Keep the mobile-device support updater useful on legacy Macs after new iOS releases. Fix the package discovery that missed the iOS 27 support update, while retaining compatibility with the older package name and the existing installation flow.

The reported symptom was that the phone could communicate with the Mac after running the script, but Apple's updater still requested a software update. Successful communication or a running `usbmuxd` process does not establish that the required support package was installed.

## Findings to carry forward

These are historical findings from the conversation and its uploaded diagnostics, not a fresh check of Apple's catalog or the current Mac's installed packages.

| Evidence | Recorded result |
| --- | --- |
| Script's installation | `MobileDeviceOnDemand.1940D10` and `CoreTypes.1940D10` |
| Apple's subsequent updater selection | Product `142-23719`, with `com.apple.pkg.MobileDeviceOnDemand.2000A36g` and `com.apple.pkg.CoreTypes.2000A36g` |
| Catalog product date | `2026-09-14T17:26:37Z` |
| Old mobile-device filename | `MobileDeviceOnDemand.pkg` |
| New mobile-device filename | `MobileDeviceOnDemandPackage.pkg` |
| Other packages in the new product | `CoreTypes.pkg` and `AppleKIS.pkg`; the reported updater installation selected the MobileDevice/CoreTypes pair |
| Existing catalog discovery | The DeveloperSeed URL from the legacy Mac's own `SeedCatalogs.plist` already exposed product `142-23719` |

The source attachments are `fetch-ios-pkgs.zsh`, `mobiledevice-diagnostics.txt`, and `mobiledevice-catalog-check.txt`. They can be consulted through the linked conversation if more evidence is needed. The catalog check is a filtered excerpt, so obtain a complete catalog or construct a valid reduced fixture before testing a structured parser.

The final conclusion superseded the chat's earlier suggestions that a separate DeviceSupport package or a stale catalog pointer caused this incident. Keep the existing discovery source:

```text
/System/Library/PrivateFrameworks/Seeding.framework/Resources/SeedCatalogs.plist
  -> DeveloperSeed URL
  -> Apple's remotely updated catalog
```

This observed success does not establish that every legacy macOS release will always receive applicable future packages. Keep compatibility claims tied to the hosts and catalogs actually checked.

## Current code and required change

Repository inspection on 2026-09-23 confirmed the same filename assumptions in the current script:

- The `LATEST_URL` AWK block matches only `MobileDeviceOnDemand.pkg`, then associates it with a following `PostDate` and selects the newest date.
- The URL-list block derives `CoreTypes.pkg` by replacing the old mobile-device filename.
- `CORETYPES_PATH` repeats that same replacement. Merely widening the discovery regex would leave both substitutions broken for the renamed package.

Replace global filename scanning with selection within each catalog product. Accept the two known mobile-device basenames, retain the product ID and `PostDate`, and read both download URLs from that product's `Packages` entries. Select the newest valid product by `PostDate` without mixing URLs or dates across product boundaries.

## Implementation checklist

- [ ] Re-read this plan and the current script; use the final chat response if additional context is needed. Refresh the catalog evidence before making current compatibility claims.
- [ ] Choose a structured plist parser available on the intended legacy macOS versions. Record any added runtime requirement explicitly; avoid silently requiring a modern OS or a newly installed dependency.
- [ ] Retain the host's DeveloperSeed discovery. Diagnose missing or unreadable catalog data clearly; do not hardcode product `142-23719`, build `2000A36g`, or an iOS/macOS generation into selection.
- [ ] Parse products independently and accept `MobileDeviceOnDemand.pkg` and `MobileDeviceOnDemandPackage.pkg` as exact package basenames. Ignore `.pkm`/`.smd` metadata and unrelated packages.
- [ ] Require the MobileDevice and CoreTypes URLs to come from the same product. Define clear handling for missing dates, missing packages, duplicate candidates, and equal dates; report rejected candidates rather than silently implying the result is fully current.
- [ ] Remove both CoreTypes filename substitutions. Carry explicit selected URLs through download naming and `CORETYPES_PATH`/`MOBILEDEVICE_PATH` construction.
- [ ] Show the selected product ID, date, and both actual package URLs before downloads and installation, so future failures can be diagnosed from the output.
- [ ] Download only the selected MobileDevice/CoreTypes pair. Do not add `AppleKIS.pkg` merely because it shares the product.
- [ ] Preserve the zsh entry point, `$HOME/Downloads` destination, root/sudo handling, and installation order: CoreTypes first, MobileDevice second. Retain the existing service-restart behavior unless separate evidence warrants changing it.
- [ ] Ensure parse or download failures stop before installation. Keep package installation status distinct from whether `usbmuxd` is running or was confirmed to restart.
- [ ] Update [`fetch-ios-pkgs.md`](fetch-ios-pkgs.md) for both filenames, selection behavior, dependencies, and verified compatibility. Mark this task complete only after the relevant validation below.

## Validation checklist

Perform parser and installation-flow tests with local fixtures and stubbed system actions before any live installation. The current script has no dry-run flag and normally installs packages and restarts services when executed.

- [ ] Old-name-only fixture still selects the correct MobileDevice/CoreTypes pair.
- [ ] A fixture containing the older pair and product `142-23719` selects the newer renamed package and that product's actual CoreTypes URL.
- [ ] Reordered plist keys, package entries, and XML formatting do not change the result or associate another product's `PostDate` with a package.
- [ ] A fixture with different package URL directories proves that no sibling-path substitution remains.
- [ ] Missing CoreTypes, missing/invalid `PostDate`, ambiguous mobile-device entries, malformed/empty catalogs, and no matches produce the documented rejection/error behavior.
- [ ] Metadata files and `AppleKIS.pkg` are excluded from the download/install list.
- [ ] Stubbed downloads and installer calls prove that both downloads succeed before installation, each intended file is installed once, and CoreTypes is installed first. Failure cases must not invoke real privileged commands or restart services.
- [ ] Run `zsh -n shell/fetch-ios-pkgs.zsh` and the focused fixture tests; inspect the final diff and documentation links.
- [ ] When ready for live validation, compare discovery output with the actual host catalog, installer applicability, and installed receipts. Record the tested macOS version and device/iOS version.
- [ ] During an explicitly requested installation test, record the selected product, installed receipts, and reconnect/prompt result. Fixture success alone does not prove that the iOS update prompt is resolved.

## Separate follow-up questions

Keep these distinct from the confirmed filename/parser fix:

- **Device and host applicability:** the chat reported Apple's updater filtering on `DEVICESUPPORT` and device board/chip tags. Investigate this before claiming that the newest product by date is suitable for every Mac and connected device; do not hardcode the one observed device's identifiers.
- **Receipt comparison:** deciding whether to skip an already installed or newer build needs a defined version-comparison policy. It was discussed but is not part of the final minimal fix.
- **Additional catalogs:** revisit only if refreshed evidence shows the host's catalog lacks the required applicable product. The recorded incident did not require replacing the catalog source.
- **Service reloads:** a running `usbmuxd` PID does not prove all framework consumers reloaded. Investigate remaining prompts after verifying package selection and receipts; do not make an automatic reboot part of the parser fix.

## Resume here

Suggested task prompt for the future session:

> Implement `docs/ios-27-package-script-plan.md`. Fix `shell/fetch-ios-pkgs.zsh` to accept both MobileDevice filenames and obtain MobileDevice/CoreTypes URLs from the same catalog product, preserving DeveloperSeed discovery and legacy macOS support. Add focused offline validation, update the usage docs and checklist, and review the final diff. Keep package installation and service restarts out of this run unless I explicitly request a live test.

Implementation is ready for review when the parser regression is reproduced and fixed, the old and renamed packages both pass focused tests, the same-product and failure-path checks pass, and documentation matches the resulting behavior. Record live verification separately; do not imply that offline tests prove the prompt is resolved on a connected device.

The work captured by this document is planning only: no script changes, package downloads, installations, or service restarts were performed while creating it.
