<a id="prowlarr-big-sur-patch-and-update-script-plan"></a>

# 📋 Prowlarr Big Sur standalone script outline

[← TODO](../../../../TODO.md) · [Execution records](../../../agents/prowlarr-bigsur-patch/PLAN.md)

Status: **completed and published on 2026-11-15**. Implementation, 83 focused tests, native checks, Astra review and the authorized live prerelease update passed. The [full plan](../../../agents/prowlarr-bigsur-patch/PLAN.md), [checklist](../../../agents/prowlarr-bigsur-patch/PLAN_checklist.md), and [handoff](../../../agents/prowlarr-bigsur-patch/PLAN_handoff.md) hold the execution and acceptance record.

## Standalone interface

- Script: `shell/prowlarr_bigsur.zsh`, suitable for an alias.
- Purpose: match compatibility metadata for older macOS, targeting Intel Big Sur 11.x. Newer macOS support is outside the project's support claims.
- No arguments patch `/Applications/Prowlarr.app`; one app path patches that local bundle.
- `--dl` and `--dl stable` download, patch, sign and install the stable full macOS Intel/x64 app; `--dl pre` selects prereleases. A supplied app path selects the destination.
- Include `-h` / `--help`. Distinguish the app ZIP from the loose Core package. Download mode always replaces with the latest selected stable/pre release, without checking the current version or skipping same/older versions.
- Discover each version/asset/URL dynamically; save the full app ZIP in `$HOME/Downloads`, replacing the matching archive after a successful validated download, then extract it.

## LaunchAgent handling

- `PROWLARR_MANAGE_LAUNCH_AGENT` defaults to `true`; `false` skips all LaunchAgent handling.
- `PROWLARR_LAUNCH_AGENT` defaults to `Prowlarr`. Both settings honor exported values and can be edited at the top.
- Always resolve the configured filename below `$HOME/Library/LaunchAgents`, and read its actual Label.
- Both patch/download modes stop and restore only a matching agent that was already loaded. Unloaded agents remain unloaded. Preserve the plist and its environment/arguments.
- Stage and verify before downtime. Keep one `/Applications/Prowlarr.backup.zip`, replacing it only after its new archive is built and validated; clean successful temporary uncompressed copies.
- Ctrl+C restores the previous app before startup; retain the new app after startup may have occurred. Validate failure/state handling with isolated fixtures, followed by the explicitly authorized live `--dl pre` smoke test.

## Scope change

The user dropped Prowlarr custom-update-script integration on 2026-11-15. There is no PID/sandbox protocol, update-hook setup, or detached updater job. This is a directly invoked standalone utility.

## Compatibility limit

Minimum-version metadata and valid local signatures do not add missing macOS APIs or prove that a .NET/Prowlarr release runs on Big Sur. Native app/service tests remain separate from implementation validation.

The live smoke test passed for prerelease 3.0.1.5752 on the tested Intel Big Sur host. Future releases and broader application behavior still need runtime checks; see the [audit](../../../agents/prowlarr-bigsur-patch/AUDIT.md).
