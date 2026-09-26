# 📝 TODO

[← Back to the toolkit](README.md)

## iOS 27 mobile-device package discovery

<details>
<summary>✅ Completed — implementation and validation record</summary>

- [x] Complete the `fetch-ios-pkgs.zsh` update, with promotion to `master` authorized by the user on 2026-09-26.
  - Implementation and automated validation are complete; the user also confirmed a successful Big Sur runtime test on 2026-09-26.
  - Implemented with read-only DeveloperSeed discovery, unchanged no-argument installation, and optional `--dry-run` / `--download-only` modes. See the [implementation and validation record](docs/plans/ios-27-package-script-plan.md).
  - Handles numeric OS ranges, Intel/Apple Silicon detection, read-only seed-path fallbacks, optional AppleKIS on macOS >= 13, and verified-PID service recovery. See [capabilities and validation limits](docs/fetch-ios-pkgs.md).
  - Automated tests, live catalog discovery, and a user-reported runtime test pass on Big Sur. Apple's current product declares a 10.13 minimum; other OS/CPU combinations remain untested on matching hardware.
  - Optional additional validation: record detailed installer/service/device-prompt evidence and test other OS/CPU combinations using the [remaining live checks](docs/plans/ios-27-package-script-plan.md#remaining-live-validation).

</details>

## Cross-platform Discord bundle downloader

- [ ] Create a stripped-down Python CLI that only discovers, lists, and downloads Discord client bundles.
  - Carry over only `--channel`, `--dl`, and `--update-select` from the macOS Discord install manager.
  - Support Discord Stable, PTB, and Canary through `--channel`.
  - Use `--OS` as a target-platform selector with `OSX`/`macOS`, `Linux`, and `Win`/`Windows` aliases.
  - Query the selected platform and channel's Discord manifest, then probe the matching CDN artifacts for selection and download.
  - Keep the tool download-only: no client installation or replacement, data cleanup, relaunch handling, module repair, OpenAsar or BetterDiscord injection, or `VersionLock` changes.

This future Python tool's `--OS` option will select the Discord bundle platform. It is separate from the current macOS manager's numeric `--OS` filter for `LSMinimumSystemVersion`.
