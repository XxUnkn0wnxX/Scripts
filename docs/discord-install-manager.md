# discord_install_manager.zsh

[`discord_install_manager.zsh`](../shell/discord_install_manager.zsh) is a macOS-only helper that resets Discord's self-managed core installation when its updater fails, without deleting the local login session or settings.

It can also remove or preserve a supported BetterDiscord app wrapper, download a fresh Discord DMG, replace the selected app in `/Applications`, inject OpenAsar into the appropriate ASAR payload, optionally lock OpenAsar to that pinned Discord version, and then run the same App Support cleanup.

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
- with unpinned `--update --OS <version>`, resolves and downloads the newest direct CDN build whose validated `LSMinimumSystemVersion` matches the OS filter
- with `--dl [version]`, downloads only the selected channel's DMG, leaves it beside the script, and exits
- with `--update-select`, prints available direct CDN DMG builds for one selected channel; `--OS` limits output to filter matches
- with `--openasar`, downloads OpenAsar or uses a local OpenAsar `app.asar`, stages and verifies it, then atomically replaces the selected standalone or BetterDiscord-nested target
- with `--lock`, writes the pinned `--update <version>` suffix to the selected channel's `openasar.VersionLock` only after the app replacement and OpenAsar injection both succeed
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

The script does not delete Discord's login session or local settings. Normal runs leave `settings.json` unchanged. A requested `--lock` changes only `openasar.VersionLock`, preserving the rest of the file.

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

The script does not inspect or classify the restored ASAR. It may be stock Discord or OpenAsar. Without `--openasar`, it is left untouched. With `--openasar`, the restored `app.asar` is then overwritten by the selected OpenAsar payload. With either latest `--update` or pinned `--update <version>`, the manager skips this unwrap because the complete application is replaced by the fresh Discord bundle; `--openasar` remains optional.

With `--BD`, a fully validated wrapper is preserved instead. The manager does not disable BetterDiscord recovery or remove `Contents/Resources/app/`; it atomically replaces only `Contents/Resources/betterdiscord.app.asar`. If no wrapper exists for a selected channel, that channel falls back to normal standalone `Contents/Resources/app.asar`. A partial, invalid, or ambiguous wrapper is always refused rather than treated as absent.

Wrapper messages use app-relative paths such as `Discord.app/Contents/Resources/app/`, `Discord PTB.app/...`, or `Discord Canary.app/...`; they do not print the `/Applications` prefix.

## DMG Downloads

When `--update` is used without a version or `--OS`, the DMG is downloaded from Discord's latest macOS download API for the selected channel.

When `--update <version>` is used, the script downloads that channel's direct CDN DMG instead. Versions can be passed as either `0.0.1177` or `1177`. Pinned versions only support a single selected channel, not `--channel all` or multiple named channels.

Use `--update --OS <macos-version>` to select the newest recent direct CDN build whose validated `LSMinimumSystemVersion` matches the requested filter:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update --OS 11
zsh shell/discord_install_manager.zsh --channel all --update --OS 12
```

`--OS` accepts major-family values such as `10`, which matches literal `10` plus every validated `10.x` value—for example `10.0`, `10.13`, `10.99`, and `10.15.7`. Values with a minor or patch component, such as `10.13` or `10.15.7`, require exact metadata matches. Major-family matching compares the complete major component, so `--OS 10` never includes `11.x` or `100.x`. This is a package-metadata filter, not a claim that every build which requires an older macOS version will run on the requested system. The manifest supplies only a discovery seed. The selected version must exist as a direct CDN DMG and its matching ZIP metadata must validate before that exact versioned DMG URL is used.

Every selected channel is resolved before the manager prepares OpenAsar, changes BetterDiscord recovery state, stops Discord, removes updater files, downloads a DMG, or replaces an app. Multiple named channels and `--channel all` are supported. If any channel has no match, the run fails before changing any channel.

`--OS` can be combined with unpinned `--update`, `--openasar`, and `--openasar-source`. It cannot be used alone, with `--dl`, with pinned `--update <version>`, or with `--lock`. It is also accepted by `--update-select` as described below.

Use `--dl` to download the selected channel's DMG without mounting, replacing, cleaning, injecting OpenAsar, or relaunching:

```bash
zsh shell/discord_install_manager.zsh --channel canary --dl 0.0.1177
```

`--dl` only supports one selected channel. It uses the same latest-versus-pinned DMG URL resolution as `--update`; without a version it downloads the latest API DMG, and with a version it downloads that direct CDN build.

Use `--update-select` to print known direct CDN DMG builds for one selected channel without modifying local files:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select
```

Pass a minimum version to stop the probe at that version:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 900
```

Pass a range to start and stop at explicit versions:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 500-400
```

Add `--OS` to filter selector output by major-family or exact minimum macOS metadata:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select --OS 11
zsh shell/discord_install_manager.zsh --channel canary --update-select 1215-1201 --OS 11
```

Discord's CDN does not expose a browsable directory index for these builds. Bare `--update-select` reads the channel's current update manifest, probes a bounded window above it, and prints only the highest DMG artifact found. This catches newer CDN builds that Discord has uploaded without advertising through the manifest. If a minimum version is provided, the scan starts from the manifest version and stops at the requested floor; a floor newer than the manifest is clamped to the manifest version. If an explicit range is provided, both endpoints are honored exactly—even when the range is newer than the manifest—and the scan stops at the second version inclusively whether or not that lower bound exists on the CDN.

Bare `--update-select --OS <version>` starts at that highest direct CDN artifact, scans downward in version order, and prints only the first matching `LSMinimumSystemVersion` build. With a floor or explicit range, it prints every matching build in that requested interval, still newest to oldest. Builds with missing or invalid metadata appear as `[unknown]` during an ordinary selector scan but never qualify for an OS-filtered result.

For each reported version, the script checks DMG availability with a `HEAD` request and reads `Last-Modified`, then performs bounded ZIP byte-range reads for `Info.plist` metadata only. Bare discovery candidates use only the DMG `HEAD` probe until the highest artifact is selected. No full ZIP download is used.

Update-selection scratch files are kept in a hidden per-run directory beside the manager script, rather than in the system temporary directory. The directory and its nested range files are removed after success, a handled failure, or a handled interruption.

For selectors, each build is printed in deterministic newest-to-oldest version order, even though metadata workers run in parallel. The bounded reorder window holds at most the configured worker count (eight by default). A ready lower version waits behind an unfinished higher version; otherwise each contiguous row is emitted immediately when the next required version completes. Bare mode prints only its highest discovered artifact. It then exits without changing the installed apps or Discord data:

```text
Last-Modified  Version - [Minimum macOS]
Mon, 01 Jan 2024 00:00:00 GMT  0.0.401 - [12.0]
unknown  0.0.401 - [unknown]
```

Rows are always printed as `Last-Modified  Version - [minimum]`. The minimum value comes from the ZIP metadata and is `unknown` when metadata is missing or invalid.

Defaults and limits appear in the scan header:

```text
  scan workers: 8
  manifest: 0.0.402
  upward discovery: 10 versions above the manifest
  highest CDN artifact: 0.0.403
  OS filter: LSMinimumSystemVersion major family 11 (11 or 11.x)
  OS scan range: 0.0.403 down to 0.0.304
  scan floor: 0.0.400
  scan range: 0.0.500 down to 0.0.400
  scan limit: newest 4 builds because DISCORD_UPDATE_SELECT_SCAN_LIMIT is set
```

`scan workers` defaults to 8. A positive `DISCORD_UPDATE_SELECT_JOBS` value selects the worker count up to a maximum of 8; zero or an invalid value falls back to 8.

To lower update-select scans to four workers in the current shell:

```bash
export DISCORD_UPDATE_SELECT_JOBS=4
zsh shell/discord_install_manager.zsh --channel canary --update-select 500-400
```

Bare discovery checks 10 versions above the manifest by default. Set `DISCORD_UPDATE_SELECT_UPWARD_LIMIT` to change that window; positive values are accepted up to 100, while zero or invalid values fall back to 10:

```bash
export DISCORD_UPDATE_SELECT_UPWARD_LIMIT=20
zsh shell/discord_install_manager.zsh --channel stable --update-select
```

Bare OS selection checks 100 candidate suffixes downward from the highest discovered artifact by default. `DISCORD_UPDATE_OS_SCAN_LIMIT` can change that window from 1 to 1000 candidates; zero or an invalid value falls back to 100, and larger values are capped at 1000:

```bash
export DISCORD_UPDATE_OS_SCAN_LIMIT=250
zsh shell/discord_install_manager.zsh --channel canary --update-select --OS 11
```

Because Discord exposes no CDN directory index or dependable historical manifest lookup, this is a bounded latest-first search. The command reports its exact scan interval and fails rather than choosing an unverified or mismatched build when no match is found. Increase the OS scan limit when a compatible build may be further behind the current artifact.

Range scanning is limited to 100 version steps (101 inclusive builds), accepts floor-only or explicit descending ranges, and prints a usage error when the span is exceeded.

It does not clean, update, inject OpenAsar, or relaunch Discord.

The `--update` and `--dl` DMG files are downloaded beside the script file. In this repository that means:

```text
shell/Discord-stable-installer (0.0.xxx).dmg
shell/Discord-ptb-installer (0.0.xxx).dmg
shell/Discord-canary-installer (0.0.xxx).dmg
```

The version in the filename is resolved before downloading. For `--update <version>` and `--dl <version>`, the requested version is normalized into the filename. For ordinary latest downloads, the script reads Discord's channel update manifest first and uses that latest version in the filename. For `--update --OS`, the filename and direct CDN URL both use the exact OS-matched version resolved during preflight.

Any existing DMG at the resolved versioned path is replaced before downloading. After the app bundle is copied into `/Applications` and the installer volume is unmounted, the downloaded DMG is deleted.

When `--dl` is used, the completed downloaded DMG is not deleted by the script.

If the DMG download fails, the script deletes the partial DMG, waits briefly, and retries up to three total attempts. Before each new remote download attempt, it removes the target file and any matching aria2 control file such as `Discord-canary-installer (0.0.xxx).dmg.aria2`. If all attempts fail, the selected app is not replaced and the script exits with an error.

For `--update-select`, a failed DMG `HEAD` probe omits that candidate. If the DMG exists but its ZIP metadata is unavailable, malformed, or rejects byte ranges, the DMG row remains visible with `[unknown]`; the script never falls back to downloading the full ZIP.

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

OpenAsar downloads are retried up to three times. Local OpenAsar sources must already exist and be non-empty. If the initial payload cannot be prepared, OpenAsar injection is normally skipped without stopping the channel cleanup/update flow. With `--lock`, the manager instead stops before cleanup or app replacement because it must not install a pinned Discord build without the requested OpenAsar payload. Before each injection, the script checks that the payload still exists; if it is missing, the script retries remote downloads or revalidates local sources and skips only that injection if the payload remains unavailable.

OpenAsar injection happens before any selected client is relaunched. The installed ASAR is verified immediately before relaunch and monitored for ten seconds afterward. If Discord replaces it during that first startup, the manager stops only that channel, reinjects once, relaunches it once, and fails clearly if the retry is also replaced.

## OpenAsar Version Lock

Use `--lock` to update one Discord channel to an explicit build, inject OpenAsar, and set that channel's `openasar.VersionLock` before the client can relaunch. `--lock` requires the custom OpenAsar build from [XxUnkn0wnxX/OpenAsar](https://github.com/XxUnkn0wnxX/OpenAsar). Plain `--openasar` already downloads this fork by default; a custom `--openasar-source` must point to a compatible build:

```bash
zsh shell/discord_install_manager.zsh \
  --channel stable \
  --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" \
  --update 401 \
  --lock
```

The argument order does not matter. For example, `--update 401` can appear before or after `--lock`, `--channel`, or the OpenAsar option.

`--lock` requires all of the following:

- exactly one channel: `stable`, `ptb`, or `canary`
- a pinned `--update <version>`, not plain `--update`
- either `--openasar` or `--openasar-source <url-or-path>`

It cannot be combined with `--BD` or `--update-select`. It also cannot be used with `--channel all` or multiple named channels. `--dl` remains a download-only mode and cannot be combined with the required update and OpenAsar actions.

The manager accepts the same pinned version forms as `--update`. Both `--update 401` and `--update 0.0.401` write the shorthand JSON string:

```json
{
  "openasar": {
    "VersionLock": "401"
  }
}
```

For a lock, the numeric suffix must not contain leading zeroes. Use `401` or `0.0.401`, not `0401`.

The selected channel controls the settings path:

```text
stable: $HOME/Library/Application Support/discord/settings.json
ptb:    $HOME/Library/Application Support/discordptb/settings.json
canary: $HOME/Library/Application Support/discordcanary/settings.json
```

If `VersionLock` already exists, only its value changes. If `openasar` is missing, the manager adds an `openasar` object containing only `VersionLock`; OpenAsar adds its other defaults when it starts. If the selected channel has no settings file or data directory yet, the manager creates the known channel path and the same minimal JSON object.

Existing root and `openasar` values are preserved. The manager refuses malformed JSON, non-object roots, non-object `openasar` values, symlinked settings targets, and numeric values that JavaScript cannot round-trip safely. It stages and validates two-space JSON beside `settings.json`, preserves existing file metadata where possible, compares a content-and-metadata snapshot immediately before commit, atomically renames the staged file, and verifies the final value. Immediately before the write, the manager verifies that Discord is still stopped and revalidates the target; a relaunched client or detected external settings change is refused without changing `settings.json`.

The endpoint and snapshot checks protect normal concurrent edits and reject symlinked settings or data-directory targets. The final atomic rename is still path-based, so it does not claim protection against a malicious same-user process replacing a parent directory in the final check-to-rename interval.

The lock is committed only after the pinned Discord app replacement and verified OpenAsar injection succeed, immediately before any relaunch. If payload preparation or injection fails, the settings file is not locked. A custom `--openasar-source` must contain an OpenAsar build that supports `VersionLock`; the manager can safely write the setting but cannot add that capability to an older payload.

## Relaunch Behavior

If a selected client was running when the script started, the script relaunches it after cleanup, update, and optional OpenAsar injection finish.

Before calling `open`, the script waits for the selected channel's app bundle to contain both `Contents/Info.plist` and the expected executable under `Contents/MacOS/`. It then refreshes LaunchServices registration only for that selected app bundle so macOS does not reuse stale metadata from the app that was just replaced.

If `open` fails or its accepted launch request does not produce the matching main Discord process, the script retries. After three unsuccessful `open` attempts, it launches the app's executable directly and again requires the matching process to appear.

## Usage

```text
discord_install_manager.zsh --channel stable|ptb|canary|all [...] [--update [version]] [--OS macos-version] [--openasar] [--openasar-source url-or-path] [--lock] [--BD]
discord_install_manager.zsh --channel stable|ptb|canary --dl [version]
discord_install_manager.zsh --channel stable|ptb|canary --update-select [minimum-version|start-end] [--OS macos-version]
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
      <td>Downloads a fresh Discord DMG for each selected channel, replaces the app in <code>/Applications</code>, then deletes the DMG. Any detected BetterDiscord wrapper is discarded with the old app instead of being unwrapped first. With a version such as <code>0.0.1177</code> or <code>1177</code>, downloads that direct CDN build. Requires <code>--channel</code>; pinned versions only support one selected channel.</td>
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
      <td>Prints available direct CDN DMG builds (with <code>Last-Modified</code> and <code>LSMinimumSystemVersion</code>) for one selected channel, then exits without making changes. Without a selector, it probes a bounded window above the manifest and prints only the highest discovered artifact. With a minimum version such as <code>900</code> or <code>0.0.900</code>, it scans from the manifest version down to that floor; a newer floor is clamped to the manifest. With a range such as <code>500-400</code>, it scans exactly from <code>0.0.500</code> down to <code>0.0.400</code>, including ranges newer than the manifest. A range is capped at 100 steps (101 inclusive builds). <code>--OS</code> optionally limits rows to matching minimum-macOS values. It does not support <code>all</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--OS &lt;macos-version&gt;</code></nobr></td>
      <td>Modifier</td>
      <td><nobr><code>11</code>, <code>11.0</code>, or another numeric macOS version</nobr></td>
      <td>Treats a major value such as <code>11</code> as major-family matching (<code>11</code> or <code>11.x</code>) and treats values such as <code>11.0</code> or <code>10.13</code> as exact matches. With bare <code>--update-select</code>, prints the newest matching build in the bounded OS scan; with a selector or range, prints only matching rows in descending order. With unpinned <code>--update</code>, resolves every selected channel first and downloads each matching versioned direct CDN DMG. Requires <code>--update</code> or <code>--update-select</code>; cannot be combined with <code>--dl</code>, pinned <code>--update &lt;version&gt;</code>, or <code>--lock</code>.</td>
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
      <td><nobr><code>--lock</code></nobr></td>
      <td>Modifier</td>
      <td><nobr>none</nobr></td>
      <td>After a successful pinned Discord update and verified OpenAsar injection, sets the selected channel's <code>openasar.VersionLock</code> to the numeric version suffix. Requires exactly one channel, <code>--update &lt;version&gt;</code>, and the custom OpenAsar build from <a href="https://github.com/XxUnkn0wnxX/OpenAsar">XxUnkn0wnxX/OpenAsar</a>. Plain <code>--openasar</code> downloads that fork by default; a custom <code>--openasar-source</code> must provide a compatible build. Cannot be combined with <code>--BD</code> or <code>--update-select</code>.</td>
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
- Plain `--update` supports multiple selected channels and downloads the latest API DMG for each one sequentially. Adding `--OS` instead resolves and downloads each channel's newest matching build from a bounded direct CDN search.
- `--update <version>`, `--dl`, and `--update-select` only support one selected channel at a time.
- `--update-select` only prints versions and exits.
- `--update` and `--openasar` can be combined.
- `--openasar-source` implies `--openasar`.
- `--OS` requires unpinned `--update` or `--update-select`. With unpinned `--update`, it remains compatible with `--openasar` and `--openasar-source`, including multiple named channels and `all`.
- `--OS` uses major-family or exact minimum-version matching: `--OS 11` matches `[11.0]` and `[11.3]` but not `[12.0]` or `[unknown]`.
- `--lock` requires one named channel, a pinned `--update <version>`, and OpenAsar input; it is rejected with `--BD`, `--update-select`, multiple channels, and `all`.
- `--lock` writes the numeric suffix as a string, so both `--update 401` and `--update 0.0.401` produce `"VersionLock": "401"`.
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

List direct CDN DMG builds for Discord Canary:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select
```

List direct CDN DMG builds for Discord Canary down to `0.0.900`:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 900
```

List direct CDN DMG builds for Discord Canary from `0.0.500` down to `0.0.400`:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 500-400
```

Show only the newest recent Canary build whose minimum macOS metadata is in the major family `11`:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select --OS 11
```

Filter a Canary version range to major-family macOS `11` builds:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update-select 1215-1201 --OS 11
```

Resolve and install the newest recent major-family macOS `11` build for every channel:

```bash
zsh shell/discord_install_manager.zsh --channel all --update --OS 11
```

Resolve an exact macOS `11.0` build, replace Discord Stable, and inject a local OpenAsar payload:

```bash
zsh shell/discord_install_manager.zsh \
  --channel stable \
  --update \
  --OS 11.0 \
  --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar"
```

Download, replace, and clean Discord Canary with a pinned direct CDN build:

```bash
zsh shell/discord_install_manager.zsh --channel canary --update 0.0.1177
```

Download Discord Stable `0.0.401`, inject a local OpenAsar build, and lock OpenAsar to that version:

```bash
zsh shell/discord_install_manager.zsh \
  --channel stable \
  --openasar-source "$HOME/Apps/Dev/BD/OpenAsar/tmp/app.asar" \
  --update 401 \
  --lock
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

## Testing Notes

Run the Python test matrix for this script with:

```bash
.venv/bin/python -m pytest --disable-plugin-autoload tests/discord_install_manager
```

The direct `--disable-plugin-autoload` option requires pytest 8.4 or newer, as pinned by this repository's minimum requirement.

Compile-check the test sources with:

```bash
.venv/bin/python -m compileall tests/discord_install_manager
```

Run the complete repository test suite with:

```bash
.venv/bin/python -m pytest --disable-plugin-autoload
```

The suite is split by behavior so CLI parsing, cleanup, downloads, version selection, application replacement, OpenAsar, BetterDiscord wrappers, relaunch/recovery guards, and `--lock` are tested independently. Each test exercises one contract; parameterized cases are used only for equivalent variants of that same contract.

Every test copies the script into a temporary fixture, replaces only that copy's fixed Applications root, and uses a temporary Home. Network, disk-image, application-copy, relaunch, wait, and normal quit commands resolve to controllable fakes, while filesystem changes stay inside the fixture. The lock settings mutation deliberately still runs through the real macOS `/usr/bin/osascript` JavaScript bridge. The suite does not modify live Discord settings, live Discord processes, or `/Applications`.

Alternatively, disable third-party pytest plugin autoload once for the current shell and omit the command-line flag:

```bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
.venv/bin/python -m pytest tests/discord_install_manager
.venv/bin/python -m pytest
```

## Safety Guards

- The target data directory must exist unless `--update` is used, multiple channels are selected, or a valid BetterDiscord app wrapper is present for removal or nested injection; missing channel data folders are then reported and skipped.
- Existing data directories must contain `settings.json` or `Local Storage/` so they resemble Discord data directories.
- A BetterDiscord wrapper is removed or preserved only when its JSON ownership contract, loader token and target, package entry point, nested ASAR, and surrounding layout all validate.
- Partial or ambiguous BetterDiscord wrapper layouts are refused before App Support or app-bundle changes begin.
- `--BD` revalidates its wrapper/absence before every target lookup. It refuses wrappers that disappear or become invalid and refuses a wrapper that appears after an absent preflight.
- `--BD` with `--update` is rejected during argument validation before downloads or filesystem changes.
- `--OS` is rejected with usage unless unpinned `--update` or `--update-select` is present. It is also rejected with `--dl`, pinned `--update <version>`, and `--lock`.
- Before an OS-selected update changes any channel, the manager resolves a validated direct CDN match under the requested major-family or exact rule for every selected channel. A missing match or metadata failure stops the whole run before OpenAsar preparation, BetterDiscord recovery changes, client shutdown, cleanup, DMG download, mounting, or app replacement.
- `--lock` is rejected unless one named channel, a pinned update version, and OpenAsar input are all present; `--BD`, `--update-select`, multiple channels, and `all` are rejected before downloads or filesystem changes.
- Before OpenAsar or Discord is downloaded for a locked update, the manager validates any existing `settings.json` root and `openasar` object and refuses malformed, non-object, non-regular, symlinked, or unsafe-number targets.
- At least one updater-managed target must exist before any App Support files are deleted.
- The selected Discord client must be fully stopped before replacement or deletion begins.
- During `--update`, the selected client is checked again before app deletion/copying and after failed replacement attempts.
- Immediately before a requested VersionLock is committed, the selected client is checked again. If it has reappeared, the manager leaves `settings.json` unchanged and does not stop that newly launched process.
- Pinned `--update <version>` downloads only one selected channel's matching CDN DMG filename, for example Canary uses `DiscordCanary.dmg`.
- `--dl` does not inspect or modify Discord App Support data and does not touch the app in `/Applications`.
- OpenAsar injection only runs after the selected app has been stopped.
- Before deliberately removing or replacing a validated BetterDiscord wrapper, the manager checks for this fork's real, non-symlinked `betterdiscord-update-helper.zsh`. Only that fork-specific recovery setup receives `recovery-disabled`, process-group shutdown, and recovery-state cleanup. Standard BetterDiscord wrappers are restored normally during cleanup, while `--update` discards them with the old application without creating or changing fork recovery files. For the fork, stale PID files are cleaned, while symlinked, reused, or mismatched PIDs are never signalled.
- OpenAsar is staged beside the target, byte-verified, atomically moved into place, and checked again after relaunch.
- A failed OpenAsar download normally skips injection instead of aborting the selected channel's purge/update flow. With `--lock`, payload preparation must succeed before the pinned update starts.
- A requested lock is staged beside `settings.json`, compared against a strong content-and-metadata snapshot, atomically committed only after verified OpenAsar injection, and verified again before relaunch. This path-based commit rejects symlinked endpoints but cannot eliminate a malicious same-user parent-directory swap during the final check-to-rename interval.
- Remote downloads use `aria2c` when available and fall back to `curl`; `DISCORD_DOWNLOAD_CONNECTIONS` can lower the aria2c split count from the default 16.
- In cleanup-only runs, if no updater-managed targets and no valid BetterDiscord wrapper are detected, the script prints a warning, leaves the client running, changes nothing, and exits successfully. A valid wrapper is normally removed; with `--BD`, it is preserved for nested OpenAsar injection.
- Existing apps in `/Applications` are always replaced during `--update`.

## Good To Know

- Use this script when Discord updates fail or its self-managed installation becomes inconsistent.
- This is narrower than deleting the entire Discord Application Support folder.
- Deleting the entire folder would also remove the local login session and custom settings.
- If the selected Discord client was already closed, the script leaves it closed after cleanup.
