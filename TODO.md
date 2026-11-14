# 📝 TODO

[← Back to the toolkit](README.md)

**Browse:** [🛠️ Prowlarr](#prowlarr-big-sur-patch-and-update-script) · [📦 iOS packages](#ios-27-mobile-device-package-discovery) · [📥 Discord downloader](#cross-platform-discord-bundle-downloader)

## Prowlarr Big Sur patch and update script

<details>
<summary>🛠️ In progress — standalone patcher and download/install utility</summary>

- [ ] Create `shell/prowlarr_bigsur.zsh` using the [active project plan](.plans/agents/prowlarr-bigsur-patch/PLAN.md), [checklist](.plans/agents/prowlarr-bigsur-patch/PLAN_checklist.md), and [handoff](.plans/agents/prowlarr-bigsur-patch/PLAN_handoff.md); retain the [rough outline](.plans/project-plans/todo/prowlarr-bigsur-patch/PLAN.md) as the backlog summary.
  - No arguments target `/Applications/Prowlarr.app`; also support one app-bundle path and `-h` / `--help`.
  - Add `--dl [stable|pre]` to download, patch, sign and install the official full macOS Intel/x64 app ZIP: bare `--dl` defaults to **stable**, while `--dl pre` selects **prereleases**. Support an optional destination app path, exclude the loose Core package and always replace from the selected family regardless of the installed version.
  - Discover versions/assets dynamically and save the full app ZIP under `$HOME/Downloads`, replacing the matching archive after successful validation.
  - Stage the bundle, set plist/executable minimums to macOS `11.0`, preserve SDK/tool metadata, apply and verify a local recursive signature, then replace the app and refresh its registration.
  - In either mode, inspect the matching LaunchAgent and restore it only if it was already loaded and this script unloaded it. Never start an initially unloaded agent; preserve its plist/environment.
  - Expose `PROWLARR_MANAGE_LAUNCH_AGENT` (default `true`) and `PROWLARR_LAUNCH_AGENT` (default `Prowlarr`) as editable/exportable globals. `false` skips all agent handling; resolve names only below `$HOME/Library/LaunchAgents`.
  - Omit Prowlarr's custom-update-script integration, PID/sandbox arguments and detached updater job. Invoke the utility directly or through an alias.
  - Use exclusive locking and one `/Applications/Prowlarr.backup.zip`, replacing it after successful archive creation/validation. Clean temporary uncompressed copies after success.
  - Ctrl+C restores the previous app before startup; retain the new app once startup may have occurred. Preserve recovery material on unresolved failures.
  - Validate with disposable fixtures and simulated service actions, then run the user's explicitly authorized live `--dl pre` smoke test. Declared-version/signature checks do not establish future Big Sur runtime compatibility.

Status: **implementation, Astra review and live prerelease validation passed; publication is being finalized in the active project records.**

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

<details>
<summary>📥 Planned — download-only Discord bundle CLI</summary>

- [ ] Create a stripped-down Python CLI that only discovers, lists, and downloads Discord client bundles.
  - Carry over only `--channel`, `--dl`, and `--update-select` from the macOS Discord install manager.
  - Support Discord Stable, PTB, and Canary through `--channel`.
  - Use `--OS` as a target-platform selector with `OSX`/`macOS`, `Linux`, and `Win`/`Windows` aliases.
  - Query the selected platform and channel's Discord manifest, then probe the matching CDN artifacts for selection and download.

</details>

- Keep the tool download-only: no client installation or replacement, data cleanup, relaunch handling, module repair, OpenAsar or BetterDiscord injection, or `VersionLock` changes.

This future Python tool's `--OS` option will select the Discord bundle platform. It is separate from the current macOS manager's numeric `--OS` filter for `LSMinimumSystemVersion`.
