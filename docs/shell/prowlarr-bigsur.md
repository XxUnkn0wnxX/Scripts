<a id="prowlarr-bigsurzsh"></a>

# 🛠️ prowlarr_bigsur.zsh

[← Back to the toolkit](../../README.md)

[`prowlarr_bigsur.zsh`](../../shell/prowlarr_bigsur.zsh) matches Prowlarr's minimum-version metadata to **older macOS**, targeting **Intel macOS Big Sur 11.x**. It patches a local app, or downloads the latest stable or prerelease full app before patching and installing it.

This is an older-macOS compatibility utility. Lowering metadata and signing the result cannot supply missing macOS or .NET APIs; whether a particular Prowlarr release actually runs still needs testing on Big Sur.

## Basic Usage

Run these commands from the repository root:

```zsh
# Patch /Applications/Prowlarr.app
zsh shell/prowlarr_bigsur.zsh

# Patch a separate local copy without handling the installed app's agent
PROWLARR_MANAGE_LAUNCH_AGENT=false zsh shell/prowlarr_bigsur.zsh "$HOME/Downloads/Prowlarr.app"

# Download and install stable; these are equivalent
zsh shell/prowlarr_bigsur.zsh --dl
zsh shell/prowlarr_bigsur.zsh --dl stable

# Download and install the latest prerelease
zsh shell/prowlarr_bigsur.zsh --dl pre

# Download another copy without handling the installed app's agent
PROWLARR_MANAGE_LAUNCH_AGENT=false zsh shell/prowlarr_bigsur.zsh --dl pre "$HOME/Applications/Prowlarr.app"

zsh shell/prowlarr_bigsur.zsh --help
```

Download mode **always replaces** the destination with the latest selected family, including when its version is equal to or older than the installed version. Each run queries GitHub for the version, asset filename and download URL. The full app ZIP is saved under `$HOME/Downloads` using that filename; a complete, validated download replaces an existing matching archive. The app is extracted from the ZIP. Local mode leaves an already patched, strictly signed app alone.

An optional alias can point to your checkout:

```zsh
alias prowlarr-update='zsh "/path/to/Scripts/shell/prowlarr_bigsur.zsh"'
prowlarr-update --dl pre
```

## Settings

The globals at the top of the script also honor exported environment variables:

| Variable | Default | Behavior |
| --- | --- | --- |
| `PROWLARR_MANAGE_LAUNCH_AGENT` | `true` | Inspect and preserve the matching agent's loaded state. Set exactly `false` to skip all agent handling. |
| `PROWLARR_LAUNCH_AGENT` | `Prowlarr` | Filename under `$HOME/Library/LaunchAgents`; the `.plist` suffix is optional. Paths are rejected. |
| `PROWLARR_BACKUP_ZIP` | `/Applications/Prowlarr.backup.zip` | Single backup ZIP path. The parent folder must already exist and be writable. |

```zsh
export PROWLARR_LAUNCH_AGENT="Prowlarr"
export PROWLARR_MANAGE_LAUNCH_AGENT=true
```

Both local and download modes read the plist's actual label and executable. A matching loaded agent is unloaded only after the candidate has been patched and verified, then restored from the same plist in its original user domain. A loaded but idle job counts as loaded. An initially unloaded agent stays unloaded; a missing plist does not create a job. The plist, arguments and environment are preserved.

The configured agent must point to the selected app. When working on a separate offline copy, disable handling for that invocation as shown above.

Restoring a loaded LaunchAgent can start Prowlarr. The script does not configure Prowlarr's custom updater hook. Invoke it directly or through your alias.

When handling is disabled, you must stop any service using the app yourself. The script still refuses replacement while its executable is in use.

## What Changes

The script stages a copy beside the destination, sets `LSMinimumSystemVersion` to `11.0`, updates an existing Intel architecture-specific minimum, and changes the main executable's `LC_BUILD_VERSION` macOS minimum to `11.0`. It preserves the SDK and build-tool versions, executable permissions and extended attributes.

It then applies a recursive ad hoc signature, strictly verifies the staged and installed bundles, and refreshes that app's LaunchServices registration. Unsupported executable layouts are refused; the supported main executable is a thin `x86_64` Mach-O with one macOS build-version command.

Downloads come from [official Prowlarr GitHub releases](https://github.com/Prowlarr/Prowlarr/releases). The highest numeric release in the requested stable/prerelease family is selected, excluding drafts. The full app asset ends in `.osx-app-core-x64.zip`; the similarly named loose Core `.tar.gz` is excluded. A GitHub-provided SHA256 digest is checked when available. Metadata requests and archive downloads have bounded timeouts.

## Backups and Recovery

Each replacement keeps **one `/Applications/Prowlarr.backup.zip`** containing the previous app. The script creates a new archive separately, validates it, then atomically replaces the existing backup ZIP. Temporary uncompressed originals are cleaned up after successful archival/installation. A per-destination lock prevents overlapping runs of this script. `PROWLARR_BACKUP_ZIP` can select a different archive path.

Ctrl+C and failures before any attempt to restart the new version restore the original bundle and previously loaded agent when possible. If the temporary original is missing or has changed, or a destination changes unexpectedly, the script preserves the remaining app and recovery material and reports their paths.

Once LaunchAgent bootstrap has been attempted, the new version may already have run or migrated its database. Ctrl+C or a bootstrap error therefore leaves the new app and backup ZIP in place and returns an error; it does not automatically roll back only the binary or retry startup. Check the reported state before intervening. A successful bootstrap command is not a health check.

Application data, quarantine attributes and system policy are outside this patch. The script does not alter them. If a run is forcibly killed or the Mac loses power, inspect the sibling backup/transaction folders before removing a stale lock and trying again.

## Requirements and Validation

Run as the signed-in user with write access to the destination, its parent folder and the backup ZIP folder. These parent folders must already exist. Local patching uses zsh, Apple's plist/signing/archive tools, Command Line Tools providing `vtool`, `otool` and `lipo`, plus `unzip`, `lsof`, `shasum`, JXA through `osascript`, and LaunchServices. Download mode also needs `curl`, `jq`, a writable `$HOME/Downloads` and internet access. Python is not a runtime dependency.

Automated validation covers isolated app/HOME fixtures and simulated downloads and service operations. Native Big Sur checks patch and sign disposable inert executables without running them, verifying metadata, signatures, preserved attributes and a repeat-run no-op.

A live `--dl pre` smoke test on Intel Big Sur passed for **3.0.1.5752** on 2026-11-15: the full app download and backup ZIP were verified, minimum-version metadata and signatures passed, and the unchanged LaunchAgent restored a running/listening process. See the [validation record](../../.plans/agents/prowlarr-bigsur-patch/AUDIT.md). This is evidence for that release on the tested host; future releases still need runtime checks.
