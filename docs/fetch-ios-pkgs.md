# fetch-ios-pkgs.zsh

[`fetch-ios-pkgs.zsh`](../fetch-ios-pkgs.zsh) downloads the newest Apple mobile-device support packages from the current DeveloperSeed catalog, installs them, and tries to restart the relevant background service afterward.

## What It Does

- finds the current DeveloperSeed catalog URL
- locates the newest `MobileDeviceOnDemand.pkg`
- also downloads the matching `CoreTypes.pkg`
- installs both packages with `installer -verboseR`
- attempts a cross-version-safe `usbmuxd` restart
- checks PIDs so it can confirm whether the restart actually happened

## Platform

This script is for macOS.

## Basic Usage

```bash
zsh fetch-ios-pkgs.zsh
```

## What To Expect

- the packages download into `~/Downloads`
- the script may prompt for `sudo` during install or service restart
- the script tries multiple restart methods for `usbmuxd`

## Example

```bash
zsh fetch-ios-pkgs.zsh
```

After the downloads finish, it installs:

- `CoreTypes.pkg`
- `MobileDeviceOnDemand.pkg`

## Good To Know

- There are no CLI flags.
- The script uses the live DeveloperSeed catalog, so results depend on what Apple currently publishes.
- If `usbmuxd` cannot be confirmed as restarted, the script prints fallback advice instead of pretending it succeeded.
- The restart logic is there so iPhone and iPad support can come back without forcing a full reboot when possible.
