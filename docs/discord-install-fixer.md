# discord_install_fixer.zsh

[`discord_install_fixer.zsh`](../shell/discord_install_fixer.zsh) is a macOS-only helper that resets Discord's self-managed core installation when its updater fails, without deleting the local login session or settings.

It can also download a fresh Discord DMG, replace the selected app in `/Applications`, and then run the same App Support cleanup.

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
- deletes the detected core installation and updater state
- relaunches a selected client only when that selected client was running when the script started
- with `--channel all`, waits until all selected channels finish before relaunching clients that were previously running
- with `--update`, downloads a fresh DMG, mounts it, replaces the matching app in `/Applications`, unmounts the DMG, and deletes the downloaded DMG

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

## Downloads

When `--update` is used, the DMG is downloaded into the running user's Downloads folder:

```text
$HOME/Downloads/Discord-stable-installer.dmg
$HOME/Downloads/Discord-ptb-installer.dmg
$HOME/Downloads/Discord-canary-installer.dmg
```

Any existing DMG at that path is replaced before downloading. After the app bundle is copied into `/Applications` and the installer volume is unmounted, the downloaded DMG is deleted.

Temporary mountpoints are created beside the script file and are removed after use. In this repository the preferred paths are:

```text
shell/mount-stable
shell/mount-ptb
shell/mount-canary
```

If a preferred mountpoint path already exists as a file or folder, the script chooses a random unused numbered fallback such as `shell/mount-stable-45`. It checks that the fallback path does not exist before creating it.

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

Download, replace, and clean Stable, PTB, and Canary:

```bash
zsh shell/discord_install_fixer.zsh --channel all --update
```

`--update` must be paired with `--channel`. Running `--update` by itself exits with an error because the app replacement target must be explicit.

Running the script with no arguments preserves the old default and cleans Discord Stable only.

## Safety Guards

- The target data directory must exist unless `--update` is used or `--channel all` is selected, where missing channel data folders are reported and skipped.
- Existing data directories must contain `settings.json` or `Local Storage/` so they resemble Discord data directories.
- At least one updater-managed target must exist before any App Support files are deleted.
- The selected Discord client must be fully stopped before replacement or deletion begins.
- If no updater-managed targets are detected, the script prints a warning, leaves the client running, changes nothing, and exits successfully.
- Existing apps in `/Applications` are always replaced during `--update`.

## Good To Know

- Use this script when Discord updates fail or its self-managed installation becomes inconsistent.
- This is narrower than deleting the entire Discord Application Support folder.
- Deleting the entire folder would also remove the local login session and custom settings.
- If the selected Discord client was already closed, the script leaves it closed after cleanup.
