# 📝 TODO

## iOS 27 mobile-device package discovery

- [ ] Update `fetch-ios-pkgs.zsh` to recognize both MobileDevice package names and read the matching CoreTypes URL from the same catalog product.
  - Follow the [iOS 27 package script agent handoff](docs/ios-27-package-script-plan.md) for the diagnosis, fix scope, implementation steps, and acceptance checks.
  - Keep the existing DeveloperSeed discovery and legacy macOS support; implementation is deferred.

## Cross-platform Discord bundle downloader

- [ ] Create a stripped-down Python CLI that only discovers, lists, and downloads Discord client bundles.
  - Carry over only `--channel`, `--dl`, and `--update-select` from the macOS Discord install manager.
  - Support Discord Stable, PTB, and Canary through `--channel`.
  - Use `--OS` as a target-platform selector with `OSX`/`macOS`, `Linux`, and `Win`/`Windows` aliases.
  - Query the selected platform and channel's Discord manifest, then probe the matching CDN artifacts for selection and download.
  - Keep the tool download-only: no client installation or replacement, data cleanup, relaunch handling, module repair, OpenAsar or BetterDiscord injection, or `VersionLock` changes.

This future Python tool's `--OS` option will select the Discord bundle platform. It is separate from the current macOS manager's numeric `--OS` filter for `LSMinimumSystemVersion`.
