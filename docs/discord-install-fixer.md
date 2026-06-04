# discord_install_fixer.zsh

[`discord_install_fixer.zsh`](../shell/discord_install_fixer.zsh) is a macOS-only helper that resets Discord Stable's self-managed core installation when its updater fails, without deleting the local login session or settings.

## Platform And Discord Channel

This script is exclusively for macOS and currently affects Discord Stable only.

It targets:

```text
/Applications/Discord.app
$HOME/Library/Application Support/discord
```

Discord PTB and Discord Canary use different application and data paths, so the script does not quit, clean, or relaunch them.

## What It Does

- detects Discord Stable's updater-managed installation files
- exits without changing anything when none of the expected files are present
- remembers whether Discord Stable was running before cleanup
- gracefully quits Discord Stable and waits up to 10 seconds
- force-kills only the Discord Stable executable if it does not quit cleanly
- deletes the detected core installation and updater state
- relaunches Discord Stable only when it was running before cleanup

After cleanup, Discord's updater downloads a fresh core installation the next time Stable launches.

## What It Deletes

The script removes the following paths from `$HOME/Library/Application Support/discord` when they exist:

```text
installer.db
0.0.*/
app-*/
modules/
module_data/
download/
```

The `0.0.*/` and `app-*/` patterns are version-independent, so the script continues to match future Discord Stable version directories.

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

## Usage

Run it directly from any location:

```bash
/path/to/discord_install_fixer.zsh
```

Or run it from this repository:

```bash
zsh shell/discord_install_fixer.zsh
```

The script starts immediately without a confirmation prompt.

## Safety Guards

- The target data directory must exist.
- The target must contain `settings.json` or `Local Storage/` so it resembles a Discord data directory.
- At least one updater-managed target must exist before Discord is quit or any files are deleted.
- Discord Stable must be fully stopped before deletion begins.
- If no updater-managed targets are detected, the script prints a warning, leaves Discord running, changes nothing, and exits successfully.

## Good To Know

- Use this script when Discord Stable updates fail or its self-managed installation becomes inconsistent.
- This is narrower than deleting the entire Discord Application Support folder.
- Deleting the entire folder would also remove the local login session and custom settings.
- If Discord Stable was already closed, the script leaves it closed after cleanup.
