# discord_install_fixer.zsh

[`discord_install_fixer.zsh`](../shell/discord_install_fixer.zsh) is a macOS-only helper that resets Discord's self-managed core installation when its updater fails, without deleting the local login session or settings.

It can also download a fresh Discord DMG, replace the selected app in `/Applications`, inject OpenAsar into the app bundle, and then run the same App Support cleanup.

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

Use `--channel all` to apply the selected action to all three channels.

## What It Does

- selects Stable, PTB, Canary, or all channels with `--channel`
- detects each selected channel's updater-managed installation files
- snapshots whether each selected Discord client was running when the script starts
- gracefully quits only the selected Discord client and waits up to 10 seconds
- with `--channel all`, stops all selected Discord clients before replacement or cleanup starts
- force-kills only the selected channel's executable if it does not quit cleanly
- deletes the detected core installation and updater state before app replacement or OpenAsar injection
- relaunches a selected client only when that selected client was running when the script started
- with `--channel all`, processes Stable, PTB, and Canary sequentially after the initial stop-all pass and relaunches each previously running client as soon as that client's work finishes
- with `--update`, downloads a fresh DMG, mounts it, replaces the matching app in `/Applications`, unmounts the DMG, and deletes the downloaded DMG
- with `--openasar`, downloads OpenAsar, overwrites the selected app's `Contents/Resources/app.asar`, and deletes the downloaded payload afterward

## What It Deletes

The script removes the following paths from the selected channel's `$HOME/Library/Application Support/...` folder when they exist:

```text
installer.db
0.0.*/
app-*/
modules/
module_data/
download/
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

## DMG Downloads

When `--update` is used, the DMG is downloaded beside the script file. In this repository that means:

```text
shell/Discord-stable-installer.dmg
shell/Discord-ptb-installer.dmg
shell/Discord-canary-installer.dmg
```

Any existing DMG at that path is replaced before downloading. After the app bundle is copied into `/Applications` and the installer volume is unmounted, the downloaded DMG is deleted.

If the DMG download fails, the script deletes the partial DMG, waits briefly, and retries up to three total attempts. If all attempts fail, the selected app is not replaced and the script exits with an error.

With `--channel all`, each channel's DMG and mountpoint are cleaned up immediately after that channel's app replacement finishes, before the script moves to the next channel.

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
zsh shell/discord_install_fixer.zsh --channel stable --openasar
```

It can also be combined with `--update`:

```bash
zsh shell/discord_install_fixer.zsh --channel all --update --openasar
```

The OpenAsar download URL is defined inside the script:

```zsh
OPENASAR_RELEASE_URL="https://github.com/XxUnkn0wnxX/OpenAsar/releases/latest/download/app.asar"
```

Change `OPENASAR_RELEASE_URL` in the script if you want to use a different OpenAsar fork or the main upstream OpenAsar release channel.

The downloaded payload is temporary. The script downloads it beside the script file, injects it into each selected Discord app, and deletes it after the selected channel set finishes. It does not keep an archived copy and does not create `.stock` backups.

OpenAsar injection happens before any selected client is relaunched.

## Usage

Show help:

```bash
zsh shell/discord_install_fixer.zsh --help
```

Clean Discord Stable's updater/core files:

```bash
zsh shell/discord_install_fixer.zsh --channel stable
```

Clean Discord PTB's updater/core files:

```bash
zsh shell/discord_install_fixer.zsh --channel ptb
```

Download, replace, and clean Discord Canary:

```bash
zsh shell/discord_install_fixer.zsh --channel canary --update
```

Inject OpenAsar and clean Discord Stable:

```bash
zsh shell/discord_install_fixer.zsh --channel stable --openasar
```

Download, replace, and clean Stable, PTB, and Canary:

```bash
zsh shell/discord_install_fixer.zsh --channel all --update
```

Download, replace, inject OpenAsar, and clean all channels:

```bash
zsh shell/discord_install_fixer.zsh --channel all --update --openasar
```

`--update` must be paired with `--channel`. Running `--update` by itself exits with an error because the app replacement target must be explicit.

`--openasar` must also be paired with `--channel`.

Running the script with no arguments preserves the old default and cleans Discord Stable only.

## Safety Guards

- The target data directory must exist unless `--update` is used or `--channel all` is selected, where missing channel data folders are reported and skipped.
- Existing data directories must contain `settings.json` or `Local Storage/` so they resemble Discord data directories.
- At least one updater-managed target must exist before any App Support files are deleted.
- The selected Discord client must be fully stopped before replacement or deletion begins.
- OpenAsar injection only runs after the selected app has been stopped.
- If no updater-managed targets are detected, the script prints a warning, leaves the client running, changes nothing, and exits successfully.
- Existing apps in `/Applications` are always replaced during `--update`.

## Good To Know

- Use this script when Discord updates fail or its self-managed installation becomes inconsistent.
- This is narrower than deleting the entire Discord Application Support folder.
- Deleting the entire folder would also remove the local login session and custom settings.
- If the selected Discord client was already closed, the script leaves it closed after cleanup.
