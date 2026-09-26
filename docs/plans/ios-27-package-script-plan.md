# iOS 27 package script plan

Status: **complete — implementation and automated validation passed, Big Sur runtime pass reported by the user, and promotion to `master` explicitly authorized on 2026-09-26.** Handoff recorded on 2026-09-23; implementation and runtime confirmation on 2026-09-26. Detailed runtime logs/device outcomes and testing on other OS/architecture combinations remain optional follow-up checks; completion does not imply runtime coverage of those platforms.

Source: [ChatGPT — iOS 27 package update script](https://chatgpt.com/c/6ab38f6a-6608-83ec-a3a5-bd9e856f20eb), last updated 2026-09-23 at 08:50 UTC. Read through MCP, including the final correction after the catalog evidence was supplied.

Implementation: [`shell/fetch-ios-pkgs.zsh`](../../shell/fetch-ios-pkgs.zsh). Current usage: [`fetch-ios-pkgs.md`](../fetch-ios-pkgs.md). Task index: [`TODO.md`](../../TODO.md).

## Implementation decisions

The user confirmed that running the script without arguments must retain automatic download, installation, and a post-install service-restart attempt. Older macOS compatibility is a platform requirement, not a separate installation mode.

- All operational modes display the detected OS/architecture, selected product, date, and every selected package link.
- `--dry-run` fetches only the temporary catalog and displays the selection; it creates no Downloads directory and performs no package download, installation, or service action.
- `--download-only` also downloads the selected packages to `~/Downloads`, then stops.
- No arguments preserve the current download/install/restart flow. No `--install` or `--legacy` flag is required.
- The host's seed configuration stays read-only. The parser uses JXA/Foundation through built-in `osascript` without a new runtime dependency. JXA requires OS X 10.10, but the current Apple product declares macOS 10.13 as its installer minimum and includes Intel/ARM targets. Automated tests run on Intel Big Sur 11.7.11, and the user subsequently reported that the script worked in a Big Sur runtime test. Other listed OS/CPU combinations remain untested on matching hardware.
- All selected downloads are staged before replacing existing package files or starting installation. Install order is CoreTypes, MobileDevice, then optional AppleKIS.
- macOS versions below 13 retain the two-package flow. A numeric `>= 13` comparison also selects the same product's AppleKIS package when available, following Apple's current distribution. Use version ranges rather than release-name allowlists.
- Detect real macOS version with `SYSTEM_VERSION_COMPAT=0`, and hardware architecture with ARM capability and Rosetta translation probes before an `uname` fallback. Apple Silicon under Rosetta must still be classified as ARM hardware. Current universal package URLs do not change by architecture.
- Explain administrator access before any password request: name the selected packages, installation into system locations on `/`, and the subsequent `usbmuxd` restart. Explain service privileges again before recovery. Add the short italic terminal notice: *Password is invisible as you type.* Keep both optional modes free of privilege requests.
- Service recovery targets `usbmuxd` and must verify that the original processes disappeared and a replacement appeared. The later restart follow-up fixes unchanged-PID false success and strengthens the fallback sequence; it does not add automatic ejection or restart other Apple agents.

The implementation is in the original shell script, with focused tests in `tests/fetch_ios_pkgs/test_fetch_ios_pkgs.py` and updated [usage documentation](../fetch-ios-pkgs.md). Receipt comparison, additional catalogs, and device-specific applicability remain separate follow-ups below.

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

## Original defect and implemented change

Repository inspection on 2026-09-23 confirmed these filename assumptions in the original script:

- The `LATEST_URL` AWK block matched only `MobileDeviceOnDemand.pkg`, then associated it with a following `PostDate` and selected the newest date.
- The URL-list block derived `CoreTypes.pkg` by replacing the old mobile-device filename.
- `CORETYPES_PATH` repeated that same replacement. Merely widening the discovery regex would leave both substitutions broken for the renamed package.

The implementation replaces global filename scanning with selection within each catalog product. It accepts the two known mobile-device basenames, retains the product ID and `PostDate`, and reads both download URLs from that product's `Packages` entries. It selects the newest valid product by `PostDate` without mixing URLs or dates across product boundaries.

On 2026-09-26, the original selector chose product `089-04537`, dated `2026-03-04T19:36:25Z`, from the live catalog. The corrected selector and a full `--dry-run` selected product `142-23719`, dated `2026-09-14T17:26:37Z`, with `MobileDeviceOnDemandPackage.pkg` and that product's actual `CoreTypes.pkg` URL. Product `012-08532`, dated 2022-06-14, contains CoreTypes and the unrecognised `MobileDeviceSU2.pkg` filename. Its initial generic warning is now informational: a newer complete package set was found, so no action is needed for that older entry. Unknown entries with equal/newer dates and genuinely missing/ambiguous packages or invalid metadata remain warnings/errors. Package eligibility is unchanged. Both selected package URLs returned HTTP 200 to HEAD requests; package contents were not downloaded. The seed plist's SHA-256 checksum was unchanged after the live dry run, and the isolated test home had no Downloads directory.

## Service-restart follow-up

The user asked whether iMazing restarts additional mobile-device services. Static inspection of installed iMazing 3.6.5 (build 24380) traced `restartMobileDeviceServices:` to `MobileDeviceServices.restart`. It obtains administrator authorization, enumerates processes, matches `usbmuxd`, and invokes `/bin/kill` with `-9` and the matched PID. On success it launches `iMazingRelauncher` and terminates its own application. This version's path does not directly restart `AMPDevicesAgent`, `AMPDeviceDiscoveryAgent`, or `MobileDeviceUpdater`. No iMazing action or live service restart was executed during inspection.

That evidence supports keeping this script's recovery focused on `usbmuxd`. The original recovery code incorrectly returned success for an unchanged PID and used `launchctl kickstart` without `-k`. Read-only host inspection also found the active service plist at `/Library/Apple/System/Library/LaunchDaemons/com.apple.usbmuxd.plist`, which the original system-path-only legacy fallback missed.

The revised flow tries TERM, `kickstart -k`, a KILL fallback restricted to still-matching original PIDs, and legacy unload/load using the available Apple plist. Each observation wait is bounded; an unchanged PID or command success alone cannot confirm a restart. A previously absent service is reported as started. Installation success and recovery failure remain separate results.

Automatic device ejection was considered and omitted: neither the traced iMazing action nor Apple's documented Finder workflow establishes that ejecting before restarting guarantees reconnection. A new daemon PID does not prove a connected device has reappeared. The script advises unlocking and reconnecting the cable if needed; that outcome remains a live validation item.

## Legacy macOS compatibility evidence

On 2026-09-26, Apple's [English distribution for product 142-23719](https://swdist.apple.com/content/downloads/34/26/142-23719-A_6Y4LUO96P3/ytfk8y0jpnp9ud3lpim9ebbts4n7qsrww8/142-23719.English.dist) defined a fatal `VolumeCheck` for macOS versions below **10.13**. This is the evidence-backed minimum for that current product through Apple's distribution. Read-only inspection of the installed MobileDevice framework and `usbmuxd` showed binary deployment minimum 10.11; do not substitute that lower number for the distribution's installation requirement.

The parser and restart implementation avoid dependencies newer than the 10.13 target: ES5 JXA/Foundation, ordinary zsh arrays and control flow, built-in curl options, `pgrep -x`, direct TERM/KILL signals, `launchctl kickstart -k`, and legacy unload/load. Both service plist locations are supported. No pre-10.10 parser fallback is needed for this product's declared minimum.

Direct component installation preserves the original script's behavior and does not evaluate the enclosing distribution's host/device predicates. The observed 10.13 minimum is recorded here rather than hardcoded into product selection. Newer catalog entries can change applicability; do not promise that every future package or iOS device will work on every legacy Mac. High Sierra runtime and device communication still require validation on an actual eligible host.

## Newer macOS and Apple Silicon handling

Apple's current distribution declares `i386,x86_64,arm64` host architectures. Read-only inspection of the installed MobileDevice framework and `usbmuxd` confirmed native ARM slices alongside Intel slices. The script uses system command paths and Foundation APIs without requiring an Intel-only executable, Rosetta, or a Homebrew prefix. Actual Apple Silicon/Rosetta execution has not been tested.

Apple's [Rosetta guidance](https://support.apple.com/en-my/102527) states that macOS 27 Golden Gate is the final release with general-purpose Rosetta, with a limited legacy-game exception from macOS 28. The script does not install or force Rosetta. It uses native system utilities, and the documented `/bin/zsh` invocation avoids an Intel-only third-party interpreter selected from `PATH`. This removes a Rosetta dependency; it does not establish future-OS runtime compatibility.

The same distribution activates `AppleKIS.pkg` through `Script1` when `system.version.ProductVersion >= 13.0`. Its [Apple package metadata](https://swdist.apple.com/content/downloads/34/26/142-23719-A_6Y4LUO96P3/ytfk8y0jpnp9ud3lpim9ebbts4n7qsrww8/AppleKIS.pkm) identifies `DeviceInterface.framework` and `DeviceInterfaceClient.framework`. The newer-host requirement extends the initial minimal-pair scope: include AppleKIS when present in the selected product on macOS 13+, while preserving the older-host pair. A missing optional entry is allowed for products that do not contain it; ambiguous or invalid AppleKIS entries reject a candidate on the OS range where it would be selected. Do not infer its URL from another package.

Seed-file discovery checks the standard `Seeding.framework/Resources` path, then `Versions/Current/Resources`, then `Versions/A/Resources`, using only the first readable `SeedCatalogs.plist`. Local Apple framework symlinks confirm that topology. The maintained [Munki installer source](https://github.com/munki/macadmin-scripts/blob/main/installinstallmacos.py) also uses the `Versions/Current` path and reads `DeveloperSeed`. These are framework layouts rather than separate Intel/ARM paths. No readable plist or no valid DeveloperSeed entry must stop before catalog fetch; do not synthesize a URL or alter seed configuration. There is no live ARM filesystem verification in this session.

The main [usage document](../fetch-ios-pkgs.md) must distinguish intended OS/architecture handling from test coverage. Automated script tests exercise simulated platform probes and package/service actions. A real Big Sur dry run checks discovery only; the subsequent Big Sur runtime pass was reported by the user. Other Intel/ARM and OS combinations remain untested end to end.

## Implementation checklist

- [x] Re-read this plan and the current script; refresh the live catalog evidence.
- [x] Choose a structured parser without an added runtime dependency: JXA/Foundation, available since OS X 10.10; current Apple distribution requires 10.13, and Big Sur is verified.
- [x] Retain the host's read-only DeveloperSeed discovery, with clear errors and no hardcoded product/build identifiers.
- [x] Parse products independently and accept both exact mobile-device basenames; ignore metadata and unrelated packages.
- [x] Require both URLs from the same product; warn on incomplete/ambiguous candidates, missing/invalid dates, duplicate URLs, and equal dates.
- [x] Remove both CoreTypes filename substitutions and carry the explicit selected URLs through download and installation paths.
- [x] Show the selected product ID, date, and actual selected package URLs in every operational mode.
- [x] Select AppleKIS from the same product only for macOS >= 13; keep earlier systems on the MobileDevice/CoreTypes pair.
- [x] Detect OS version and hardware architecture, including Apple Silicon under Rosetta, without release-name/model allowlists.
- [x] Locate the read-only seed plist across standard and versioned framework resource paths; fail locally when absent.
- [x] Preserve the zsh entry point, `$HOME/Downloads`, root/sudo handling, CoreTypes-first installation, and post-install service-recovery step.
- [x] Stop on parse, download, or installer failures before subsequent actions. Keep install success distinct from service status.
- [x] Add opt-in `--dry-run` and `--download-only`; preserve automatic installation with no arguments.
- [x] Explain package-installation and service-recovery privileges, with a short italic password-visibility notice before possible authentication.
- [x] Update [`fetch-ios-pkgs.md`](../fetch-ios-pkgs.md) for both filenames, modes, dependencies, and compatibility limits.
- [x] Receive explicit user authorization for `master` promotion and completion of the overall iOS TODO and this plan.

## Validation checklist

Parser and installation-flow tests use local fixtures and stubbed system actions. Normal execution still installs packages and attempts service recovery; use `--dry-run` for discovery without package or service actions.

Final automated suite: **94 passed with each of system zsh 5.8, Homebrew zsh 5.9.2, and upstream zsh 5.3.1**, all on Intel Big Sur 11.7.11. The default invocation was `.venv/bin/python -m pytest -q tests/fetch_ios_pkgs`; other-interpreter runs set `FETCH_IOS_PKGS_ZSH` to the relevant executable path. Python compilation, all three zsh syntax checks, and diff/documentation checks passed. The original selector also failed a renamed-only regression fixture that the new selector passed.

The final live `--dry-run` detected Big Sur 11.7.11 / `x86_64`, selected product `142-23719`, and displayed the MobileDevice/CoreTypes pair. It created no Downloads directory, and the seed plist's SHA-256 matched the pre-change baseline. Selection from the cached real catalog with simulated macOS 27.0 also included that product's AppleKIS URL; this was a parser check, not execution on macOS 27.

On 2026-09-26, the user confirmed that the script worked and that Big Sur runtime testing passed. Record this as user-reported runtime success on the session's Intel Big Sur host. Installer logs, final receipts, restart PID evidence, device/iOS details, and a separate update-prompt result were not supplied. The package installer still uses the original `-verboseR` option with output sent directly to the terminal; curl download progress is also retained.

The compatibility interpreter was built from the upstream [zsh 5.3.1 source archive](https://www.zsh.org/pub/old/zsh-5.3.1.tar.xz) in ignored temporary storage, without installation or source changes. Building with Apple clang required `CFLAGS='-O2 -std=gnu89 -Wno-error=implicit-function-declaration'` so its historical configuration probes compiled correctly, plus `--disable-dynamic --without-tcsetpgrp` for the test build. All test runs still used Big Sur's JXA/Foundation and external utilities; this is older-shell evidence, not a High Sierra system test. Test subprocesses run in isolated process groups so a timed-out shell cannot leave descendants holding the test's output pipes open.

- [x] Old-name-only fixture still selects the correct MobileDevice/CoreTypes pair.
- [x] A fixture containing the older pair and product `142-23719` selects the newer renamed package and that product's actual CoreTypes URL.
- [x] Reordered plist keys, package entries, and XML formatting do not change the result or associate another product's `PostDate` with a package; binary plists also pass.
- [x] Different package URL directories and query strings prove that no sibling-path substitution remains.
- [x] Missing CoreTypes, missing/invalid `PostDate`, ambiguous entries, malformed/empty catalogs, and no matches produce the documented rejection/error behavior.
- [x] An otherwise valid unknown filename is informational only when strictly older than a selected complete package set; equal/newer dates, invalid metadata, and no usable selection retain warning/error severity.
- [x] Metadata and unrelated package files are excluded from the download/install list.
- [x] Test numeric OS ranges, Intel/native ARM/Rosetta detection, and optional AppleKIS selection without real platform changes.
- [x] Test each seed-path fallback and missing-file failure before catalog fetch.
- [x] Stubbed downloads/installers prove every selected transfer precedes CoreTypes-first installation, and failures stop subsequent actions without real privileged calls, including optional AppleKIS failures.
- [x] Normal, dry-run, and download-only modes display all selected links and perform only their intended actions. Failed downloads preserve previously completed files and clean staging files.
- [x] Privilege explanations precede installation/service actions, include the selected packages, and omit password notices in modes that do not request privileges.
- [x] Simulated service recovery covers immediate/delayed replacement, unchanged and partially surviving original PIDs, successful and ineffective kickstart, force-kill targeting, initial absence, observation/permission errors, both legacy plist paths, and missing plists. Recovery runs under the same strict shell options and conditional-call context as normal mode.
- [x] A service-recovery warning remains nonfatal after successful installations, and output advises unlocking/reconnecting a device that does not reappear. Automatic ejection is omitted.
- [x] Run system/Homebrew `zsh -n`, focused pytest tests, Python compilation, and final diff/documentation checks.
- [x] User-reported Big Sur runtime pass received on 2026-09-26.
- [ ] When ready for live validation, compare discovery output with the actual host catalog, installer applicability, and installed receipts. Record the tested macOS version and device/iOS version.
- [ ] During an explicitly requested installation test, record the selected product, installed receipts, and reconnect/prompt result. Fixture success alone does not prove that the iOS update prompt is resolved.

## Separate follow-up questions

Keep these distinct from the confirmed filename/parser fix:

- **Device and host applicability:** the chat reported Apple's updater filtering on `DEVICESUPPORT` and device board/chip tags. Investigate this before claiming that the newest product by date is suitable for every Mac and connected device; do not hardcode the one observed device's identifiers.
- **Receipt comparison:** deciding whether to skip an already installed or newer build needs a defined version-comparison policy. It was discussed but is not part of the final minimal fix.
- **Additional catalogs:** revisit only if refreshed evidence shows the host's catalog lacks the required applicable product. The recorded incident did not require replacing the catalog source.
- **Other framework consumers:** verified `usbmuxd` replacement does not prove all clients reloaded or that Finder rediscovered the device. Investigate remaining prompts after checking selection and receipts; keep reconnection and any broader refresh separate from daemon restart verification.

## Remaining live validation

Big Sur already has a user-reported runtime pass. For a detailed evidence run or testing on another OS/architecture, when explicitly requested:

1. Record the Mac's OS version, hardware architecture, native/Rosetta execution state, connected device/iOS version, and installed receipts.
2. Run `--dry-run` and check the current catalog selection and package applicability.
3. Run the normal installation flow, record installer results and receipts (including AppleKIS when selected), then reconnect the device and check whether the update prompt is resolved.
4. Investigate applicability, receipt comparison, or framework reloads only if the new evidence calls for them; keep those findings distinct from the confirmed parser fix.

Offline tests and live catalog selection do not prove that an installation succeeds on every older Mac or resolves the prompt on a connected device.

The original handoff was planning only. Agent-run validation changed the script and tests and performed live catalog discovery; it did not download real packages, install packages, or restart services. The user subsequently ran the script and reported the successful Big Sur runtime result above.
