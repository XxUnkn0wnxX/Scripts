# brew-custom-compare.zsh

[`brew-custom-compare.zsh`](../brew-custom-compare.zsh) compares formulas from a custom Homebrew tap against upstream Homebrew data and tells you whether your custom versions are ahead, outdated, equal, or pinned.

## What It Does

- recursively scans Ruby formula files in the tap
- gets local stable versions with `brew info --json=v2`
- compares them against the public Homebrew API
- falls back to other installed taps if the main API has no match
- marks pinned formulas as `PINNED`

That means it can scan formulas in places such as:

- the tap root
- `Formula/`
- other Ruby-formula subfolders

## Basic Usage

Use the default tap:

```bash
zsh brew-custom-compare.zsh
```

Use a specific tap:

```bash
zsh brew-custom-compare.zsh --tap myuser/mytap
```

Check only specific formulas:

```bash
zsh brew-custom-compare.zsh node ffmpeg
```

## Arguments

<table>
  <thead>
    <tr>
      <th>Argument</th>
      <th>Type</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>formula ...</code></nobr></td>
      <td>Positional</td>
      <td>Optional list of formulas to limit the comparison. If omitted, the whole tap is scanned.</td>
    </tr>
    <tr>
      <td><nobr><code>-t</code>, <code>--tap &lt;tap&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Sets the tap to inspect. Default is the script's built-in tap value.</td>
    </tr>
    <tr>
      <td><nobr><code>-h</code>, <code>--help</code></nobr></td>
      <td>Flag</td>
      <td>Prints the built-in help message and exits.</td>
    </tr>
  </tbody>
</table>

## Quick Examples

Scan the default tap:

```bash
zsh brew-custom-compare.zsh
```

Scan a custom tap:

```bash
zsh brew-custom-compare.zsh --tap XxUnkn0wnxX/tap
```

Check just one formula:

```bash
zsh brew-custom-compare.zsh --tap XxUnkn0wnxX/tap bun
```

## Status Labels

- `OK` means the custom version matches upstream
- `AHEAD` means the custom version is newer than upstream
- `OUTDATED` means upstream is newer
- `PINNED` means the formula is pinned locally
- `SKIP` means there was not enough version data to compare cleanly
- `ERROR` means the script could not complete that comparison

## Good To Know

- If you pass no formula names, the script scans every Ruby formula file it finds in the tap.
- If the Homebrew API has no entry or usable version, the script checks other installed taps and skips `homebrew/core` during that fallback path.
- The built-in default tap is `custom/versions`.
- The default tap can also be overridden with the `DEFAULT_CUSTOM_TAP` environment variable before running the script.
