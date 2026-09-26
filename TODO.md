# 📝 TODO

## iOS 27 mobile-device package discovery

- [ ] Complete the `fetch-ios-pkgs.zsh` update and promote it to `master` after explicit user authorization.
  - Implementation and automated validation are complete on `develop`. Keep this overall task and its plan open until the user authorizes the `master` push, then mark them done after successful promotion.
  - Implemented with read-only DeveloperSeed discovery, unchanged no-argument installation, and optional `--dry-run` / `--download-only` modes. See the [implementation and validation record](docs/plans/ios-27-package-script-plan.md).
  - Handles numeric OS ranges, Intel/Apple Silicon detection, read-only seed-path fallbacks, optional AppleKIS on macOS >= 13, and verified-PID service recovery. See [capabilities and validation limits](docs/fetch-ios-pkgs.md).
  - Automated script tests and live catalog discovery pass on Big Sur. Apple's current product declares a 10.13 minimum; installation, service restart, and device communication across the documented OS/CPU ranges remain unverified on actual matching hardware.
- [ ] Validate a live installation and the connected-device update prompt using the [remaining live checks](docs/plans/ios-27-package-script-plan.md#remaining-live-validation).

## Cross-platform Discord bundle downloader

- [ ] Create a stripped-down Python CLI that only discovers, lists, and downloads Discord client bundles.
  - Carry over only `--channel`, `--dl`, and `--update-select` from the macOS Discord install manager.
  - Support Discord Stable, PTB, and Canary through `--channel`.
  - Use `--OS` as a target-platform selector with `OSX`/`macOS`, `Linux`, and `Win`/`Windows` aliases.
  - Query the selected platform and channel's Discord manifest, then probe the matching CDN artifacts for selection and download.
  - Keep the tool download-only: no client installation or replacement, data cleanup, relaunch handling, module repair, OpenAsar or BetterDiscord injection, or `VersionLock` changes.

This future Python tool's `--OS` option will select the Discord bundle platform. It is separate from the current macOS manager's numeric `--OS` filter for `LSMinimumSystemVersion`.
