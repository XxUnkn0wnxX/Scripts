# fetch-ios-pkgs.zsh

[`fetch-ios-pkgs.zsh`](../shell/fetch-ios-pkgs.zsh) finds the newest complete MobileDevice/CoreTypes pair in the Mac's DeveloperSeed catalog. On macOS 13 and later, it also selects `AppleKIS.pkg` when that product contains it. With no arguments it shows the links, downloads the selected packages, installs them, and attempts to restart `usbmuxd`.

## What It Does

- Detects the macOS version and hardware architecture, including Apple Silicon when running under Rosetta, and shows them before discovery.
- Locates the host's `SeedCatalogs.plist` within `Seeding.framework` and reads its DeveloperSeed URL. It never changes that file or the system's software-update configuration.
- Fetches a temporary copy of Apple's remote catalog and parses each product independently.
- Recognises both `MobileDeviceOnDemand.pkg` and `MobileDeviceOnDemandPackage.pkg`, and reads the actual `CoreTypes.pkg` URL from the same product.
- Selects the newest complete, unambiguous product by its `PostDate` and displays its product ID, date, and every selected package URL in every mode.
- Uses a numeric `macOS >= 13` comparison to include that product's `AppleKIS.pkg` when available. Earlier systems retain the two-package flow. Metadata and unrelated packages are excluded.
- In normal mode, installs CoreTypes, MobileDevice, and then the optional AppleKIS package with `installer -verboseR -target /`, followed by a verified `usbmuxd` restart attempt.

## Platform

The compatibility target for the current support update is **macOS 10.13 High Sierra and later on Intel, plus Apple Silicon on its supported macOS versions**. On 2026-09-26, Apple's [distribution for product 142-23719](https://swdist.apple.com/content/downloads/34/26/142-23719-A_6Y4LUO96P3/ytfk8y0jpnp9ud3lpim9ebbts4n7qsrww8/142-23719.English.dist) explicitly rejected systems older than 10.13 in `VolumeCheck` and declared both `x86_64` and `arm64` host architectures. That establishes the product's declared installer targets; it does not prove every device works on every eligible Mac. The installed Intel framework and daemon declare a lower binary minimum of 10.11, which is not evidence that Apple's current distribution supports installation there.

The script uses built-in zsh, curl, `osascript`, Foundation, `pgrep`, `/bin/kill`, and `launchctl`, with no Python, Homebrew package, or third-party XML parser required. The parser uses ES5 JavaScript for Automation (JXA), which [Apple introduced in OS X 10.10](https://developer.apple.com/library/archive/releasenotes/InterapplicationCommunication/RN-JavaScriptForAutomation/index.html). The parser's technical minimum is separate from the selected package's macOS requirements. Restart commands are available by 10.13; the fallback handles both the older system plist location and the updated `/Library/Apple` location.

The script obtains the real macOS version through `sw_vers` with `SYSTEM_VERSION_COMPAT=0`. It checks ARM hardware capability and, if needed, Rosetta's `sysctl.proc_translated` flag before falling back to `uname`, so an Intel process on Apple Silicon is still classified as ARM hardware. Missing capability keys on older Macs are handled by the fallback. It uses numeric version ranges and CPU capabilities rather than a list of OS releases or Mac models. The same current Apple packages contain native Intel and ARM code, so architecture detection does not invent a different download URL. No Rosetta installation or architecture-specific Homebrew prefix is required.

Apple documents **macOS 27 Golden Gate as the last release with general-purpose Rosetta support**; from macOS 28, translation is limited to certain older games. The script can use native system tools on Apple Silicon and has no Rosetta dependency. The commands below explicitly use `/bin/zsh` to avoid accidentally choosing an Intel-only third-party shell from `PATH`. Native execution on future macOS versions remains unverified. See [Apple's Rosetta guidance](https://support.apple.com/en-my/102527).

The `macOS >= 13` AppleKIS rule follows the current Apple distribution's `Script1` predicate. Its package metadata identifies `DeviceInterface.framework` and `DeviceInterfaceClient.framework`. If a product has no AppleKIS entry, only the required MobileDevice/CoreTypes pair is selected. This observed rule is not a general interpreter for future Apple distribution scripts.

The script installs component packages directly, as before; it does not execute or enforce the enclosing product distribution's applicability checks. Catalog availability, package applicability, and the connected device's requirements remain dependent on Apple. Check those requirements before using normal install mode on another host; the observed 10.13 minimum is not hardcoded as a promise about future products.

## OS and Architecture Handling

These ranges describe the intended handling, not a matrix of machines on which installation has been validated:

| Host | Selected packages | Architecture handling |
| --- | --- | --- |
| Intel (`x86_64`), macOS 10.13 through 12.x | MobileDevice and CoreTypes | Uses the host's built-in tools and catalog. |
| Intel (`x86_64`), supported Intel macOS releases with version >= 13 | MobileDevice and CoreTypes, plus AppleKIS when present in that product | Uses the `>= 13` rule without a release-name allowlist. |
| Apple Silicon (`arm64`), macOS 11 through 12.x | MobileDevice and CoreTypes | Detects ARM hardware; the same Apple packages contain native ARM code. |
| Apple Silicon (`arm64`), macOS 13 or later | MobileDevice and CoreTypes, plus AppleKIS when present in that product | Uses the same `>= 13` rule and host catalog. |
| Apple Silicon running an Intel shell through Rosetta, where available | Uses the range for the real host macOS version | ARM capability or a positive translation flag takes precedence over an Intel result from `uname`. |

Unknown architectures, an unreadable OS version, or a missing usable seed file produce a clear error before package download or installation. Future macOS versions follow the numeric range comparison; that does not guarantee compatibility with future changes to Apple's package requirements or service policies.

## Validation Status

**Automated script tests have been performed; end-to-end runtime tests of installation, service recovery, and connected-device behavior have not.** The OS ranges and architectures above have not been fully tested on their corresponding Macs.

All **94 automated tests passed with each of system zsh 5.8, Homebrew zsh 5.9.2, and a temporary upstream zsh 5.3.1 build**, on an Intel Mac running Big Sur 11.7.11. Coverage includes simulated OS ranges through 27 and 28, Intel/native ARM/Rosetta detection, seed-path fallbacks, AppleKIS selection, privilege notices, diagnostic severity, modes, failures, and service recovery. The older-interpreter run still used Big Sur's JXA/Foundation and utilities; it was not a High Sierra runtime test. The temporary interpreter was built only for compatibility testing and was not installed or made a script dependency.

A live `--dry-run` on Big Sur verified catalog discovery only. Downloads, installers, process signals, and launchctl actions in the automated suite are mocked. Native Apple Silicon execution, Rosetta execution, installation on the listed OS ranges, service restart permissions, and device reconnection still need validation on actual matching hardware. No script test result should be read as proof that the connected-device update prompt is resolved.

## Basic Usage

```zsh
/bin/zsh shell/fetch-ios-pkgs.zsh
```

The no-argument behaviour remains automatic: show links, download, install, and attempt a service restart. Before requesting administrator access through `sudo`, it explains that the selected packages will be installed into system locations on `/`, names those packages, and explains the subsequent `usbmuxd` restart. It also explains the service-recovery privilege requirement before that step, in case authentication is requested again. An already-root invocation does not need `sudo`; neither optional mode requests installation or service privileges.

The password notice is kept short: *Password is invisible as you type.* It uses italics in an interactive terminal and plain text when output is redirected or the terminal declares no formatting support.

## Catalog Location

The script checks these read-only framework resource paths in order and uses the first readable file:

```text
/System/Library/PrivateFrameworks/Seeding.framework/Resources/SeedCatalogs.plist
/System/Library/PrivateFrameworks/Seeding.framework/Versions/Current/Resources/SeedCatalogs.plist
/System/Library/PrivateFrameworks/Seeding.framework/Versions/A/Resources/SeedCatalogs.plist
```

The standard resource path resolves through the framework's version links on the inspected Mac. The maintained [Munki macOS installer source](https://github.com/munki/macadmin-scripts/blob/main/installinstallmacos.py) also uses the `Versions/Current` location and reads `DeveloperSeed`. These locations are framework layouts, not Intel/ARM-specific directories. A missing readable plist or invalid DeveloperSeed entry stops discovery before a catalog download; the script does not synthesize or replace the host's catalog URL. Actual file discovery on an Apple Silicon host remains a live validation item.

## Optional Modes

| Invocation | Fetch catalog and show links | Download packages | Install and attempt service restart |
| --- | --- | --- | --- |
| No arguments | Yes | Yes | Yes |
| `--dry-run` | Yes | No | No |
| `--download-only` | Yes | Yes | No |
| `--help` / `-h` | No | No | No |

```zsh
/bin/zsh shell/fetch-ios-pkgs.zsh --dry-run
/bin/zsh shell/fetch-ios-pkgs.zsh --download-only
```

The two optional modes are mutually exclusive. Unknown arguments are rejected before fetching the catalog. A dry run needs network access for the catalog but does not create `~/Downloads`, download packages, request installation privileges, or touch services. The temporary catalog is cleaned up when the command exits.

## Downloads and Failure Handling

Packages are saved to `~/Downloads` using their actual package basenames, without URL query strings. Every selected transfer must succeed before installation starts. Downloads are staged in a temporary directory under `~/Downloads`; a failed transfer removes partial files and preserves previously completed downloads. Successful transfers replace any existing files with the selected names.

Products with an incomplete or ambiguous pair, invalid package URLs, or missing/invalid dates are skipped with a warning. Identical repeated URLs are deduplicated. Equal newest dates are resolved by ascending product ID with a warning. If no valid pair remains, the script exits unsuccessfully without installing anything. Rejected candidates mean the selected pair is the newest *valid* candidate, not proof that every catalog entry is usable.

An otherwise valid entry with an unrecognised MobileDevice filename is informational when a strictly newer complete package set is available. For example: `Info: Skipped older package set "012-08532" ("MobileDeviceSU2.pkg"). Newer packages are available; no action is needed for this entry.` This describes an older catalog entry, not a problem with the Mac's installed packages.

Missing packages, ambiguous URLs, invalid metadata, and unreadable catalogs remain genuine warnings or errors. An unrecognised entry with the same or a newer date stays a warning that the selected packages may not be the latest update. If no usable package set is found, discovery fails instead of reporting a harmless skip.

A catalog or download failure stops before installation. An installer failure stops subsequent installation and service actions; successful earlier installations cannot be rolled back automatically if a later package fails.

## Service Recovery

After a successful installation, the script records the current `usbmuxd` PIDs and attempts these steps in order, stopping when recovery is confirmed:

1. Send TERM to the original `usbmuxd` processes and allow launchd to replace them.
2. Use `launchctl kickstart -k system/com.apple.usbmuxd` to replace a running instance or start a stopped service.
3. If original processes still remain, try KILL on those original PIDs. A newly observed replacement is not a target for this fallback.
4. Try legacy `launchctl unload` / `load`, preferring Apple's updated plist under `/Library/Apple/System/Library/LaunchDaemons` and falling back to `/System/Library/LaunchDaemons`.

Each attempted recovery step allows a bounded wait of up to ten seconds. A restart is confirmed only when every original PID has disappeared and at least one replacement PID is observed. If the service was initially absent, the script reports that it was started. An unchanged PID, an observation error, or a successful command without an observed replacement is not reported as a confirmed restart.

Recovery targets `usbmuxd` only. It does not restart Finder, iTunes, or other MobileDevice framework clients. Static inspection of iMazing 3.6.5 found that its corresponding action force-kills `usbmuxd` and relaunches iMazing itself; this did not establish a need to restart every Apple mobile-device agent.

If recovery cannot be confirmed, the script reports a warning and suggests reconnecting the device or rebooting. Successful package installation remains successful even if service recovery cannot be confirmed. Service recovery has been tested with simulated processes and commands; a live restart remains unverified.

Connected iOS devices are not automatically ejected. Apple's [Finder guidance](https://support.apple.com/en-eg/guide/mac-help/wi-fi-syncing-mchlada1d602/mac) describes ejection before disconnecting a device; it does not establish an eject/restart sequence that guarantees reconnection. A confirmed daemon restart does not prove that Finder or another client has rediscovered the device. If the device does not reappear, unlock it and reconnect its cable.

## Good To Know

- The script does not compare installed receipts or skip an already-installed build. It installs the selected packages in normal mode, as before.
- Live package installation and the connected-device update prompt have not been validated as part of this parser change. A successful dry run proves catalog discovery only.

## Offline Tests

The focused pytest suite builds XML and binary plist fixtures and runs the script with mocked downloads, installers, and service actions. It exercises both package names, product boundaries, CLI modes, and failure handling without downloading real packages or changing services. Restart tests exercise the recovery sequence with simulated PID observations, signals, launchctl calls, and waits.

From a development environment with pytest installed:

```zsh
python -m pytest tests/fetch_ios_pkgs
```

The tests require macOS for the real JXA/Foundation parser. Python and pytest are development-only dependencies. Set `FETCH_IOS_PKGS_ZSH` to an absolute zsh executable path to exercise another interpreter.

The [implementation record and remaining live checks](plans/ios-27-package-script-plan.md) are kept in `docs/plans/`.
