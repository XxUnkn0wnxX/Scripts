# discord_install_manager.zsh

[`discord_install_manager.zsh`](../shell/discord_install_manager.zsh) is a macOS-only helper that resets Discord's self-managed core installation when its updater fails, without deleting the local login session or settings.

It can also remove or preserve a supported BetterDiscord app wrapper, download a fresh Discord DMG, replace the selected app in `/Applications`, inject OpenAsar into the appropriate ASAR payload, and then run the same App Support cleanup.

## Channels

The script supports Discord Stable, PTB, and Canary:

```text
stable:
  /Applications/Discord.app
  $HOME/Library/Application Support/discord
  https://discord.com/api/download/stable?platform=osx

ptb:
  /Applications/Discord PTB.app
  $HOME/Library/Application Support/discordptb
  https://discord.com/api/download/ptb?platform=osx

canary:
  /Applications/Discord Canary.app
  $HOME/Library/Application Support/discordcanary
  https://discord.com/api/download/canary?platform=osx
```

Use `--channel all` to apply the selected action to all three channels. You can also name multiple channels in one run, for example `--channel stable ptb`.

## What It Does

- selects Stable, PTB, Canary, multiple named channels, or all channels with `--channel`
- detects each selected channel's updater-managed installation files
- snapshots whether each selected Discord client was running when the script starts
- gracefully quits only the selected Discord client and waits up to 10 seconds
- with multiple selected channels, stops all selected Discord clients before replacement or cleanup starts
- force-kills only processes running from the selected channel's app bundle if its main process or helpers do not quit cleanly
- deletes the detected core installation and updater state before app replacement or OpenAsar injection
- validates BetterDiscord's marked app-wrapper layout before cleanup and refuses incomplete or ambiguous layouts
- normally removes a valid BetterDiscord wrapper and restores `betterdiscord.app.asar` to `app.asar`, whether the restored payload is stock Discord or OpenAsar
- with `--BD`, preserves a valid BetterDiscord wrapper and targets its nested `betterdiscord.app.asar`; channels without a wrapper use normal standalone `app.asar`
- relaunches a selected client only when that selected client was running when the script started
- with multiple selected channels, processes them sequentially after the initial stop-all pass and relaunches each previously running client as soon as that client's work finishes
- with `--update`, downloads a fresh DMG, mounts it, replaces the matching app in `/Applications`, unmounts the DMG, and deletes the downloaded DMG
- with `--update <version>`, downloads that channel's direct CDN DMG for a version such as `0.0.1177` instead of the latest API redirect
- with `--dl [version]`, downloads only the selected channel's DMG, leaves it beside the script, and exits
- with `--update-select`, prints available direct CDN DMG versions for one selected channel and exits without changing files
- with `--openasar`, downloads OpenAsar or uses a local OpenAsar `app.asar`, stages and verifies it, then atomically replaces the selected standalone or BetterDiscord-nested target
- before relaunching a client after replacement, waits for the app bundle executable, refreshes LaunchServices registration, and falls back to launching the executable directly if `open` fails or the main process does not appear

## What It Deletes

The script removes the following paths from the selected channel's `$HOME/Library/Application Support/...` folder when they exist:

```text
installer.db
ShipIt_request.json
0.0.*/
app-*/
modules/
module_data/
download/
Cache/
Code Cache/
```

The `0.0.*/` and `app-*/` patterns are version-independent, so the script continues to match future Discord version directories.

These paths contain Discord's updater database, downloaded packages, core host installation, native modules, and module runtime data. They must be reset together so the updater does not retain installation state for files that were removed separately.

## What It Preserves

The script does not delete Discord's login session or local settings.

Important preserved paths include:

```text
Local Storage/
settings.json
Preferences
Cookies
```

It also does not modify the macOS Keychain item used by Discord's Electron storage.

Discord stores the local login token in `Local Storage/leveldb/`. Preserving the complete `Local Storage/` directory prevents the reset from signing the user out.

## BetterDiscord App Wrapper

Every cleanup run checks the selected app bundle for BetterDiscord's marked `Contents/Resources/app/` wrapper. A supported wrapper must contain the expected ownership marker, loader, package file, and nested `betterdiscord.app.asar`, with no competing top-level `app.asar`.

Without `--BD`, when that complete layout is found, the script stops the selected client and performs this exact unwrap:

```text
remove Contents/Resources/app/
rename Contents/Resources/betterdiscord.app.asar to Contents/Resources/app.asar
```

Before unwrapping a client, the manager disables BetterDiscord's detached
update-recovery helper so the deliberate unwrap cannot be mistaken for a
Discord application update. A later BetterDiscord injection re-enables that
recovery path.

The script does not inspect or classify the restored ASAR. It may be stock Discord or OpenAsar. Without `--openasar`, it is left untouched. With `--openasar`, the restored `app.asar` is then overwritten by the selected OpenAsar payload. With `--update`, the app is subsequently replaced by the fresh Discord bundle, and `--openasar` remains optional.

With `--BD`, a fully validated wrapper is preserved instead. The manager does not disable BetterDiscord recovery or remove `Contents/Resources/app/`; it atomically replaces only `Contents/Resources/betterdiscord.app.asar`. If no wrapper exists for a selected channel, that channel falls back to normal standalone `Contents/Resources/app.asar`. A partial, invalid, or ambiguous wrapper is always refused rather than treated as absent.

Wrapper messages use app-relative paths such as `Discord.app/Contents/Resources/app/`, `Discord PTB.app/...`, or `Discord Canary.app/...`; they do not print the `/Applications` prefix.

## DMG Downloads

When `--update` is used without a version, the DMG is downloaded from Discord's latest macOS download API for the selected channel.

When `--update <version>` is used, the script downloads that channel's direct CDN DMG instead. Versions can be passed as either `0.0.1177` or `1177`. Pinned versions only support a single selected channel, not `--channel all` or multiple named channels.

Use `--dl` to download the selected channel's DMG without mounting, replacing, cleaning, injecting OpenAsar, or relaunching:

```bash
zsh shell/discord_install_manager.zsh --channel canary --dl 0.0.1177
```

`--dl` only supports one selected channel. It uses the same latest-versus-pinned DMG URL resolution as `--update`; without a version it downloads the latest API DMG, and with a version it downloads that direct CDN build.

Use `--update-select` to print known direct CDN DMG versions for one selected channel:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select
```

Pass a minimum version to stop the probe at that version:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 900
```

Pass a range to start and stop at explicit versions:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 600-300
```

Discord's CDN does not expose a browsable directory index for these builds, so `--update-select` starts from the channel's current update manifest version and probes older numeric CDN DMG URLs from newest to oldest. If a minimum version is provided, the scan stops there. If a range is provided, the scan starts at the first version and stops at the second version inclusively, even when the lower bound itself is not found on the CDN. If the requested start or minimum version is newer than the current manifest version, the scan uses the detected latest version instead. It prints matching builds as they are discovered with the CDN `Last-Modified` date first, followed by version, and does not clean, update, inject OpenAsar, or relaunch Discord.

The DMG is downloaded beside the script file. In this repository that means:

```text
shell/Discord-stable-installer (0.0.xxx).dmg
shell/Discord-ptb-installer (0.0.xxx).dmg
shell/Discord-canary-installer (0.0.xxx).dmg
```

The version in the filename is resolved before downloading. For `--update <version>` and `--dl <version>`, the requested version is normalized into the filename. For latest downloads, the script reads Discord's channel update manifest first and uses that latest version in the filename.

Any existing DMG at the resolved versioned path is replaced before downloading. After the app bundle is copied into `/Applications` and the installer volume is unmounted, the downloaded DMG is deleted.

When `--dl` is used, the completed downloaded DMG is not deleted by the script.

If the DMG download fails, the script deletes the partial DMG, waits briefly, and retries up to three total attempts. Before each new remote download attempt, it removes the target file and any matching aria2 control file such as `Discord-canary-installer (0.0.xxx).dmg.aria2`. If all attempts fail, the selected app is not replaced and the script exits with an error.

When `aria2c` is available, remote Discord DMG and OpenAsar downloads use it with up to 16 split connections. Set `DISCORD_DOWNLOAD_CONNECTIONS` to a lower value to reduce the split count. If `aria2c` is not available, the script uses `curl`.

After mounting the DMG, the script checks again for a self-restarted Discord client immediately before deleting and copying the app. If detected, it stops that client and repeats the App Support purge. App deletion/copying is attempted up to three times; each failed attempt repeats the running-client guard before retrying.

With multiple selected channels, each channel's DMG and mountpoint are cleaned up immediately after that channel's app replacement finishes, before the script moves to the next channel.

Temporary mountpoints are created beside the script file and are removed after use. In this repository the preferred paths are:

```text
shell/mount-stable
shell/mount-ptb
shell/mount-canary
```

If a preferred mountpoint path already exists as a file or folder, the script chooses a random unused numbered fallback such as `shell/mount-stable-45`. It checks that the fallback path does not exist before creating it.

## OpenAsar

Use `--openasar` with `--channel` to inject OpenAsar into the selected Discord app bundle:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar
```

It can also be combined with `--update`:

```bash
zsh shell/discord_install_manager.zsh --channel all --update --openasar
```

To update and inject only specific channels in one pass:

```bash
zsh shell/discord_install_manager.zsh --channel stable ptb --update --openasar
```

Use `--openasar-source` to inject a specific OpenAsar payload from a local file, a GitHub repo URL, or a direct download URL:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar"
```

`--openasar-source` implies `--openasar`; the only difference is that it uses the source you provide.

By default, the script uses the fork repo URL and resolves it to the latest release asset internally:

```zsh
DEFAULT_OPENASAR_SOURCE="https://github.com/XxUnkn0wnxX/OpenAsar"
```

For a plain GitHub repo URL such as `https://github.com/XxUnkn0wnxX/OpenAsar`, the script downloads from that repo's `releases/latest/download/app.asar` asset.

Set `OPENASAR_SOURCE` when running the script if you prefer an environment override instead of the CLI option:

```bash
OPENASAR_SOURCE="$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" \
  zsh shell/discord_install_manager.zsh --channel stable --openasar
```

Local sources can be absolute paths, relative paths, `~/...`, `$HOME/...`, or `file://...` paths. Remote sources can be plain GitHub repo URLs or direct `http://` / `https://` `app.asar` URLs.

For remote URLs, the downloaded payload is temporary. The script downloads it beside the script file, injects it into each selected Discord app, and deletes it after the selected channel set finishes. Local `app.asar` sources are used in place and are not deleted by the script. It does not keep an archived copy and does not create `.stock` backups.

By default, a supported BetterDiscord wrapper is unwrapped before OpenAsar injection, so OpenAsar is written to the normal top-level `Contents/Resources/app.asar`. BetterDiscord can then be injected again afterward and will wrap that payload.

Use `--BD` when BetterDiscord is already installed and should remain installed:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar --BD
```

It works with the normal OpenAsar download and with a custom source:

```bash
zsh shell/discord_install_manager.zsh --channel stable ptb \
  --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" \
  --BD
```

For every selected channel, `--BD` preserves and revalidates a supported wrapper before replacing `betterdiscord.app.asar`. If no wrapper was present at preflight, it revalidates that absence and uses top-level `app.asar`. If wrapper presence or validity changes while the manager is running, it stops rather than switching targets.

`--BD` requires `--openasar` or `--openasar-source`. It cannot be combined with `--update`, because replacing the Discord application also replaces the BetterDiscord wrapper. That invalid combination is rejected before downloads, cleanup, or app changes begin.

OpenAsar downloads are retried up to three times. Local OpenAsar sources must already exist and be non-empty. If the initial payload cannot be prepared, OpenAsar injection is skipped without stopping the channel cleanup/update flow. Before each injection, the script checks that the payload still exists; if it is missing, the script retries remote downloads or revalidates local sources and skips only that injection if the payload remains unavailable.

OpenAsar injection happens before any selected client is relaunched. The installed ASAR is verified immediately before relaunch and monitored for ten seconds afterward. If Discord replaces it during that first startup, the manager stops only that channel, reinjects once, relaunches it once, and fails clearly if the retry is also replaced.

## Relaunch Behavior

If a selected client was running when the script started, the script relaunches it after cleanup, update, and optional OpenAsar injection finish.

Before calling `open`, the script waits for the selected channel's app bundle to contain both `Contents/Info.plist` and the expected executable under `Contents/MacOS/`. It then refreshes LaunchServices registration only for that selected app bundle so macOS does not reuse stale metadata from the app that was just replaced.

If `open` fails or its accepted launch request does not produce the matching main Discord process, the script retries. After three unsuccessful `open` attempts, it launches the app's executable directly and again requires the matching process to appear.

## Usage

```text
discord_install_manager.zsh --channel stable|ptb|canary|all [...] [--update [version]] [--openasar] [--openasar-source url-or-path] [--BD]
discord_install_manager.zsh --channel stable|ptb|canary --dl [version]
discord_install_manager.zsh --channel stable|ptb|canary --update-select [minimum-version|start-end]
discord_install_manager.zsh --help
```

## Arguments

<table>
  <thead>
    <tr>
      <th>Argument</th>
      <th>Type</th>
      <th>Values</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>--channel &lt;channel&gt; [...]</code></nobr></td>
      <td>Option</td>
      <td><nobr><code>stable</code>, <code>ptb</code>, <code>canary</code>, <code>all</code></nobr></td>
      <td>Selects the Discord client or clients to purge, unwrap, update, or inject. Multiple named channels can be passed in one run. <code>all</code> processes Stable, PTB, and Canary sequentially and cannot be mixed with named channels.</td>
    </tr>
    <tr>
      <td><nobr><code>--update [version]</code></nobr></td>
      <td>Flag / option</td>
      <td><nobr>optional version</nobr></td>
      <td>Downloads a fresh Discord DMG for each selected channel, replaces the app in <code>/Applications</code>, then deletes the DMG. With a version such as <code>0.0.1177</code> or <code>1177</code>, downloads that direct CDN build. Requires <code>--channel</code>; pinned versions only support one selected channel.</td>
    </tr>
    <tr>
      <td><nobr><code>--dl [version]</code></nobr></td>
      <td>Flag / option</td>
      <td><nobr>optional version</nobr></td>
      <td>Downloads only the selected channel's DMG and exits without mounting, replacing, cleaning, injecting, or relaunching. With a version such as <code>0.0.1177</code> or <code>1177</code>, downloads that direct CDN build. Requires one selected channel and does not support <code>all</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--update-select [minimum-version|start-end]</code></nobr></td>
      <td>Flag</td>
      <td><nobr>optional version</nobr></td>
      <td>Prints available direct CDN DMG versions for one selected channel from newest to oldest as they are discovered, with CDN <code>Last-Modified</code> date first and version second, then exits without making changes. With a minimum version such as <code>900</code> or <code>0.0.900</code>, stops scanning at that version. With a range such as <code>600-300</code>, starts at <code>0.0.600</code> and stops at <code>0.0.300</code>. Requested starts or floors newer than the current manifest version are clamped to the detected latest version. Does not support <code>all</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--openasar</code></nobr></td>
      <td>Flag</td>
      <td><nobr>none</nobr></td>
      <td>Downloads OpenAsar and replaces standalone <code>Contents/Resources/app.asar</code> by default, or the validated nested target when combined with <code>--BD</code>. Requires <code>--channel</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--openasar-source &lt;url-or-path&gt;</code></nobr></td>
      <td>Option</td>
      <td><nobr>URL or path</nobr></td>
      <td>Injects OpenAsar from a specific GitHub repo URL, direct remote URL, or local <code>app.asar</code> file. Implies <code>--openasar</code> and requires <code>--channel</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--BD</code></nobr></td>
      <td>Modifier</td>
      <td><nobr>none</nobr></td>
      <td>Preserves a validated BetterDiscord wrapper and injects OpenAsar into <code>Contents/Resources/betterdiscord.app.asar</code>. A channel without a wrapper falls back to standalone <code>app.asar</code>. Requires <code>--openasar</code> or <code>--openasar-source</code> and cannot be combined with <code>--update</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--help</code>, <code>-h</code></nobr></td>
      <td>Flag</td>
      <td><nobr>none</nobr></td>
      <td>Prints the built-in help message and exits.</td>
    </tr>
  </tbody>
</table>

Notes:

- Running the script with no arguments exits without changing anything and prints the help text.
- `--channel` alone purges the selected client or clients' App Support updater files and unwraps a valid BetterDiscord app wrapper when present.
- `--update` and `--openasar` must be paired with `--channel` so the app bundle target is explicit.
- `--dl` must be paired with one selected channel and cannot be combined with `--update`, `--update-select`, or `--openasar`.
- Plain `--update` supports multiple selected channels and downloads the latest API DMG for each one sequentially.
- `--update <version>`, `--dl`, and `--update-select` only support one selected channel at a time.
- `--update-select` only prints versions and exits.
- `--update` and `--openasar` can be combined.
- `--openasar-source` implies `--openasar`.
- `--BD` preserves valid BetterDiscord wrappers, requires OpenAsar input, and is rejected with `--update` before any work starts.
- With multiple channels, `--BD` independently chooses nested or standalone injection for each channel.

## Examples

Show help:

```bash
zsh shell/discord_install_manager.zsh --help
```

Clean Discord Stable's updater/core files:

```bash
zsh shell/discord_install_manager.zsh --channel stable
```

Clean Discord PTB's updater/core files:

```bash
zsh shell/discord_install_manager.zsh --channel ptb
```

Download, replace, and clean Discord Canary:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update
```

Download, replace, clean, and inject OpenAsar for Stable and PTB:

```bash
zsh shell/discord_install_manager.zsh --channel stable ptb --update --openasar
```

Download only a pinned Discord Canary DMG:

```bash
zsh shell/discord_install_manager.zsh --channel canary --dl 0.0.1177
```

List direct CDN DMG versions for Discord Canary:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select
```

List direct CDN DMG versions for Discord Canary down to `0.0.900`:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 900
```

List direct CDN DMG versions for Discord Canary from `0.0.600` down to `0.0.300`:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 600-300
```

Download, replace, and clean Discord Canary with a pinned direct CDN build:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update 0.0.1177
```

Inject OpenAsar and clean Discord Stable:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar
```

Inject a locally built OpenAsar payload and clean Discord Stable:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar"
```

Refresh OpenAsar inside an existing BetterDiscord wrapper:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar --BD
```

Refresh a local OpenAsar build inside wrappers where present, with standalone fallback per channel:

```bash
zsh shell/discord_install_manager.zsh --channel stable ptb --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" --BD
```

Inject OpenAsar from a specific repo URL:

```bash
zsh shell/discord_install_manager.zsh --channel stable --openasar-source "https://github.com/XxUnkn0wnxX/OpenAsar"
```

Download, replace, and clean Stable, PTB, and Canary:

```bash
zsh shell/discord_install_manager.zsh --channel all --update
```

Download, replace, inject OpenAsar, and clean all channels:

```bash
zsh shell/discord_install_manager.zsh --channel all --update --openasar
```

## Safety Guards

- The target data directory must exist unless `--update` is used, multiple channels are selected, or a valid BetterDiscord app wrapper is present for removal or nested injection; missing channel data folders are then reported and skipped.
- Existing data directories must contain `settings.json` or `Local Storage/` so they resemble Discord data directories.
- A BetterDiscord wrapper is removed or preserved only when its JSON ownership contract, loader token and target, package entry point, nested ASAR, and surrounding layout all validate.
- Partial or ambiguous BetterDiscord wrapper layouts are refused before App Support or app-bundle changes begin.
- `--BD` revalidates its wrapper/absence before every target lookup. It refuses wrappers that disappear or become invalid and refuses a wrapper that appears after an absent preflight.
- `--BD` with `--update` is rejected during argument validation before downloads or filesystem changes.
- At least one updater-managed target must exist before any App Support files are deleted.
- The selected Discord client must be fully stopped before replacement or deletion begins.
- During `--update`, the selected client is checked again before app deletion/copying and after failed replacement attempts.
- Pinned `--update <version>` downloads only one selected channel's matching CDN DMG filename, for example Canary uses `DiscordCanary.dmg`.
- `--dl` does not inspect or modify Discord App Support data and does not touch the app in `/Applications`.
- OpenAsar injection only runs after the selected app has been stopped.
- OpenAsar is staged beside the target, byte-verified, atomically moved into place, and checked again after relaunch.
- A failed OpenAsar download skips injection instead of aborting the selected channel's purge/update flow.
- Remote downloads use `aria2c` when available and fall back to `curl`; `DISCORD_DOWNLOAD_CONNECTIONS` can lower the aria2c split count from the default 16.
- In cleanup-only runs, if no updater-managed targets and no valid BetterDiscord wrapper are detected, the script prints a warning, leaves the client running, changes nothing, and exits successfully. A valid wrapper is normally removed; with `--BD`, it is preserved for nested OpenAsar injection.
- Existing apps in `/Applications` are always replaced during `--update`.

## Good To Know

- Use this script when Discord updates fail or its self-managed installation becomes inconsistent.
- This is narrower than deleting the entire Discord Application Support folder.
- Deleting the entire folder would also remove the local login session and custom settings.
- If the selected Discord client was already closed, the script leaves it closed after cleanup.
