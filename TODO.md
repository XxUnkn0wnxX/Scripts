# 📝 TODO

[← Back to the toolkit](README.md)

## Prowlarr Big Sur patch and update script

<details>
<summary>🛠️ Planned — standalone patcher and Prowlarr update integration</summary>

- [ ] Create `shell/prowlarr_bigsur.zsh` using the [dedicated project plan](.plans/project-plans/todo/prowlarr-bigsur-patch/PLAN.md).
  - No arguments target `/Applications/Prowlarr.app`; also support one app-bundle path and `-h` / `--help`.
  - Add `--dl` to fetch the official full macOS Intel/x64 app ZIP (`osx-app-core-x64.zip`, containing `Prowlarr.app`), then prepare it with the Big Sur patch/sign operation; exclude the loose Core `.tar.gz` package. Finalize download destination and installation/release policy before implementation.
  - Stage and back up the bundle, set plist/executable minimums to macOS `11.0`, preserve SDK/tool metadata, apply and verify a local recursive signature, then replace the app and refresh its registration.
  - Keep manual mode free of app launches and service changes; refuse a running app or matching loaded KeepAlive job.
  - Support Prowlarr's updater arguments and already-downloaded payload without re-downloading it or requiring an API key; keep that handoff separate from `--dl`.
  - Hand automatic installation to an independent temporary launchd job so it can prepare the replacement, unload Prowlarr, swap the app, and reload the existing LaunchAgent without being killed with Prowlarr's process group.
  - Preserve the existing LaunchAgent and its environment, coordinate exclusive locks and payload ownership, and distinguish pre-start bundle recovery from recovery after possible database migration.
  - Start with disposable fixtures and simulated service actions; native launches/restarts and end-to-end update tests need separate authorization. Declared-version/signature checks do not establish future Big Sur runtime compatibility.

Status: **planning only; no script or updater integration has been implemented.**

</details>

## iOS 27 mobile-device package discovery

<details>
<summary>✅ Completed — implementation and validation record</summary>

- [x] Complete the `fetch-ios-pkgs.zsh` update, with promotion to `master` authorized by the user on 2026-09-26.
  - Implementation and automated validation are complete; the user also confirmed a successful Big Sur runtime test on 2026-09-26.
  - Implemented with read-only DeveloperSeed discovery, unchanged no-argument installation, and optional `--dry-run` / `--download-only` modes. See the [implementation and validation record](.plans/project-plans/completed/ios-27-package-script-plan.md).
  - Handles numeric OS ranges, Intel/Apple Silicon detection, read-only seed-path fallbacks, optional AppleKIS on macOS >= 13, and verified-PID service recovery. See [capabilities and validation limits](docs/shell/fetch-ios-pkgs.md).
  - Automated tests, live catalog discovery, and a user-reported runtime test pass on Big Sur. Apple's current product declares a 10.13 minimum; other OS/CPU combinations remain untested on matching hardware.
  - Optional additional validation: record detailed installer/service/device-prompt evidence and test other OS/CPU combinations using the [remaining live checks](.plans/project-plans/completed/ios-27-package-script-plan.md#remaining-live-validation).

</details>

## Cross-platform Discord bundle downloader

- [ ] Create a stripped-down Python CLI that only discovers, lists, and downloads Discord client bundles.
  - Carry over only `--channel`, `--dl`, and `--update-select` from the macOS Discord install manager.
  - Support Discord Stable, PTB, and Canary through `--channel`.
  - Use `--OS` as a target-platform selector with `OSX`/`macOS`, `Linux`, and `Win`/`Windows` aliases.
  - Query the selected platform and channel's Discord manifest, then probe the matching CDN artifacts for selection and download.
  - Keep the tool download-only: no client installation or replacement, data cleanup, relaunch handling, module repair, OpenAsar or BetterDiscord injection, or `VersionLock` changes.

This future Python tool's `--OS` option will select the Discord bundle platform. It is separate from the current macOS manager's numeric `--OS` filter for `LSMinimumSystemVersion`.
