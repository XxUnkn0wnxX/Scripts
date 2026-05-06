# Nord OVPN Picker

[`nord_ovpn_picker.py`](../nord_ovpn_picker.py) is a local CLI that finds NordVPN OpenVPN servers by country, optional city, protocol, and group, then downloads chosen `.ovpn` files into a `NordOVPNs/` folder in your current working directory.

## Features

- Interactive mode when you run the script with no filter arguments.
- Type-to-filter autocomplete for country, city, protocol, and group prompts.
- Non-interactive CLI mode for direct scripted use.
- V2-backed metadata for countries, cities, groups, and technologies.
- Recommendation-first server selection using Nord's recommendation API.
- Automatic fallback to Nord's V2 dataset when recommendations are not enough or `--full-data` is used.
- Optional ping scoring for the top candidates.
- Rich results table with hostname, location, protocol, group, load, ping, score, station IP, and the recommended marker.
- Visible per-host ping progress in TTY sessions before the final ranked table.
- Direct `.ovpn` downloads for the best candidate, the top N, or an interactive selection.
- Automatic re-exec into the repo-local `.venv` when the script is started from the wrong Python interpreter.
- Current-working-directory output folder so aliases, symlinks, and absolute-path calls still write where you launched them from.
- API response caching under an OS-native cache directory.

## Setup

Run these commands from the `Scripts` repo root on macOS or Linux:

```bash
python3 -m venv .venv
source "$HOME/.zshrc"
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, create and activate the same repo-local `.venv` with the usual Windows venv path:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The script expects this repo-local `.venv` to exist when you actually run the picker. If it does not find one, it stops and tells you to follow these setup steps instead of silently using the wrong Python environment.

If the repo-local `.venv` exists but the script was launched from the wrong Python interpreter, it re-execs itself into that `.venv` automatically. This works whether you run it from the repo root, by absolute path, through an alias, or through a symlink. It does not activate your current shell session globally; it only reruns the script with the correct interpreter.

Plain imports and `--help` can still work without the repo-local `.venv`. Normal picker execution still expects that repo-local environment.

The re-exec path is OS-aware:

- macOS and Linux use `.venv/bin/python` or `.venv/bin/python3`
- Windows uses `.venv\Scripts\python.exe`

## Platform Support

Current support status:

- macOS: supported
- Linux and other Unix-like systems: supported when `python3`, `ping`, and the repo-local `.venv` are available
- Windows: supported for repo-local venv re-exec and ping handling, but Windows users should run the script with the normal Windows Python launcher such as `py -3` or `python`

Ping handling is OS-aware:

- macOS and Linux use `ping -c <count> -q <host>`
- Windows uses `ping -n <count> <host>`

If `ping` is unavailable or blocked on the local machine, use `--no-ping`.

## How It Chooses Servers

The default flow is:

1. Resolve the country from Nord's V2 metadata.
2. Resolve the city if you supplied one.
3. Query Nord's recommendation API first for the requested country, group, and OpenVPN technology.
4. Filter the recommendation results by city if needed.
5. If recommendations are missing or not enough, fall back to the V2 server dataset.
6. Optionally ping the top candidates.
7. Score candidates using ping plus load, then mark the top result as recommended.
8. Optionally download one or more configs.

By default the score is based on:

```text
score = average_ping_ms + (load * 2)
```

Lower is better.

That means a slightly higher ping can still win if the load is lower enough. For example, `3.6 ms` with load `11` scores `25.6`, which still beats `3.2 ms` with load `12` scoring `27.2`.

## Interactive Usage

Run the script with no filter arguments to enter the prompt flow:

```bash
python3 nord_ovpn_picker.py
```

The prompts run in this order:

1. Country
2. City
3. Protocol
4. Group
5. Result limit
6. Run ping test
7. Download selection

The interactive country, city, protocol, and group prompts use live filtering against the visible option names as you type. Instead of printing the full city list first, the menu narrows in place so you can keep typing until the option you want is visible, then press `Tab` or `Enter`.

Interactive defaults:

- Country: required
- City: blank means country-wide results
- Protocol: `udp`
- Group: `standard`
- Result limit: `5`
- Ping test: `yes`

If you leave the final download selection blank, the script only prints the candidate table and exits without downloading anything.

When ping testing is enabled in a terminal, the script shows each ping test as it runs before printing the final ranked table.

Interactive download selection accepts:

- `1`
- `1-5`
- `1,3-7,10`
- `all`
- blank input to skip downloading

Examples of the interactive prefix matching:

- typing `uni` narrows the country list to entries such as `United States` and `United Kingdom`
- typing `Ch` then `Chic` narrows United States cities down to `Chicago`
- typing `T` narrows protocol choices to `TCP`
- typing `P` narrows the default group list to `P2P`

For the interactive prompts, filtering follows the visible labels instead of hidden country-code aliases. Country-code and alias shortcuts such as `USA`, `UK`, `UAE`, or `AU` are still supported on the non-interactive `--country` argument path.

## Mode Behavior

The script has three practical run styles:

- Pure interactive: run `python3 nord_ovpn_picker.py` in a TTY and answer prompts for the full flow.
- Mixed TTY: pass some arguments, then let the prompt UI fill in any missing filter values.
- Non-interactive: run from a non-TTY or provide all needed arguments up front and skip prompt-only steps.

Examples:

```bash
python3 nord_ovpn_picker.py
python3 nord_ovpn_picker.py --country AU
python3 nord_ovpn_picker.py --country AU --protocol udp --group standard --download-best
```

Mode notes:

- If you run in a TTY and omit some of `--country`, `--city`, `--protocol`, `--group`, or `--limit`, the script prompts only for the missing pieces.
- `--country` aliases such as `AU`, `USA`, `UK`, and `UAE` are accepted on the CLI argument path. The interactive country prompt filters only against the visible country names.
- The live autocomplete prompt UI exists only in TTY interactive mode.
- Listing commands such as `--list-countries` and `--list-cities` are CLI-only and do not enter the prompt flow.
- Flags such as `--advanced`, `--full-data`, `--refresh-cache`, `--force`, `--dry-run`, and `--verbose` are argument-driven switches. They can still affect a TTY run, but they are not separate interactive prompts.
- `--advanced` controls which optional protocol/group keys appear in interactive prompts. Explicit CLI values are still accepted if Nord's live V2 metadata supports them.

## Common Usage

Basic listing:

```bash
python3 nord_ovpn_picker.py --list-countries
python3 nord_ovpn_picker.py --country Australia --list-cities
python3 nord_ovpn_picker.py --list-groups
python3 nord_ovpn_picker.py --list-technologies
```

Show candidates:

```bash
python3 nord_ovpn_picker.py --country Australia
python3 nord_ovpn_picker.py --country Australia --protocol udp --group standard --limit 5
python3 nord_ovpn_picker.py --country Australia --city Melbourne --protocol tcp --group p2p --limit 5 --no-ping
python3 nord_ovpn_picker.py --country AU --city Melb --protocol udp --group standard --limit 5
```

Download:

```bash
python3 nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best
python3 nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-top 3 --force
python3 nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
python3 nord_ovpn_picker.py --country Australia --city Melbourne --protocol udp --group p2p --download-top 5
```

Custom output directory:

```bash
python3 nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-top 2 --output-dir /path/to/output
```

Force the V2 dataset path:

```bash
python3 nord_ovpn_picker.py --country Australia --city Melbourne --protocol udp --group standard --full-data
```

Refresh cached Nord API payloads:

```bash
python3 nord_ovpn_picker.py --country Australia --refresh-cache
```

Show debug logging:

```bash
python3 nord_ovpn_picker.py --country Australia --verbose
```

## Invocation From Anywhere

The script can be run directly, through an alias, by absolute path, or through a symlink. On startup it checks whether it is already running inside this repo's `.venv`; if not, it re-execs itself into that interpreter automatically.

That means these styles all work as long as the repo-local `.venv` exists:

```bash
python3 /Users/USER/Apps/Scripts/nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
```

```bash
python3 /some/symlink/to/nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
```

On Windows, use the same script path with the normal Windows launcher:

```powershell
py -3 C:\path\to\nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
```

Because the default output path is based on your current working directory, these invocations write into `./NordOVPNs` wherever you launched the command from, not beside the script itself.

## Arguments

<table>
  <thead>
    <tr>
      <th>Argument</th>
      <th>Prompt UI</th>
      <th>CLI flag</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><nobr><code>--country &lt;name-or-code&gt;</code></nobr></td>
      <td>Yes</td>
      <td>Yes</td>
      <td>Required in non-interactive mode. CLI accepts names, short forms, and aliases such as <code>Australia</code>, <code>AU</code>, <code>aus</code>, <code>USA</code>, <code>UK</code>, and <code>UAE</code>. The interactive prompt filters by visible country names only.</td>
    </tr>
    <tr>
      <td><nobr><code>--city &lt;name&gt;</code></nobr></td>
      <td>Yes</td>
      <td>Yes</td>
      <td>Optional in both paths. Blank in the prompt means no city filter. CLI partial matches such as <code>Melb</code> work when they resolve cleanly.</td>
    </tr>
    <tr>
      <td><nobr><code>--protocol &lt;key&gt;</code></nobr></td>
      <td>Yes</td>
      <td>Yes</td>
      <td>Prompted in TTY mode when missing. Defaults to <code>udp</code> when omitted in non-interactive mode.</td>
    </tr>
    <tr>
      <td><nobr><code>--group &lt;key&gt;</code></nobr></td>
      <td>Yes</td>
      <td>Yes</td>
      <td>Prompted in TTY mode when missing. Defaults to <code>standard</code> when omitted in non-interactive mode.</td>
    </tr>
    <tr>
      <td><nobr><code>--limit &lt;number&gt;</code></nobr></td>
      <td>Yes</td>
      <td>Yes</td>
      <td>Prompted in TTY mode when missing. Default is <code>5</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--no-ping</code></nobr></td>
      <td>Yes</td>
      <td>Yes</td>
      <td>In UI mode this maps to the ping yes/no prompt. On the CLI it disables ping immediately.</td>
    </tr>
    <tr>
      <td><nobr><code>--output-dir &lt;path&gt;</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only setting. Overrides the default <code>./NordOVPNs</code> output path.</td>
    </tr>
    <tr>
      <td><nobr><code>--download-best</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only shortcut. Downloads only the top-ranked candidate and skips the interactive download-selection prompt. Mutually exclusive with <code>--download-top</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--download-top &lt;number&gt;</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only shortcut. Downloads the top N candidates and skips the interactive download-selection prompt. Mutually exclusive with <code>--download-best</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--force</code></nobr></td>
      <td>Partial</td>
      <td>Yes</td>
      <td>There is no dedicated <code>--force</code> prompt. In interactive mode, existing files normally trigger an overwrite confirmation; <code>--force</code> skips that prompt.</td>
    </tr>
    <tr>
      <td><nobr><code>--dry-run</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only flag. Works in TTY or non-TTY runs, but there is no prompt equivalent.</td>
    </tr>
    <tr>
      <td><nobr><code>--full-data</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only flag. Skips the recommendation-first shortcut and forces the V2 dataset path.</td>
    </tr>
    <tr>
      <td><nobr><code>--ping-count &lt;number&gt;</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only tuning flag for how many ping attempts to run per host. Default is <code>3</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--refresh-cache</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only flag to bypass cached Nord API payloads.</td>
    </tr>
    <tr>
      <td><nobr><code>--advanced</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only switch for prompt visibility. When present, advanced live-supported options such as XOR or advanced groups appear in TTY prompts. Explicit CLI values are still accepted when Nord's live V2 metadata supports them.</td>
    </tr>
    <tr>
      <td><nobr><code>--verbose</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only flag. Enables debug logging for HTTP requests, cache usage, and ping execution.</td>
    </tr>
    <tr>
      <td><nobr><code>--list-countries</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only listing mode. Prints all countries and exits.</td>
    </tr>
    <tr>
      <td><nobr><code>--list-cities</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only listing mode. Requires <code>--country</code>, prints that country's cities, then exits.</td>
    </tr>
    <tr>
      <td><nobr><code>--list-groups</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only listing mode. Prints currently supported live group keys, then exits.</td>
    </tr>
    <tr>
      <td><nobr><code>--list-technologies</code></nobr></td>
      <td>No</td>
      <td>Yes</td>
      <td>CLI-only listing mode. Prints live Nord technologies from V2, then exits.</td>
    </tr>
  </tbody>
</table>

If you do not pass `--no-ping`, non-interactive mode pings candidates by default.

When ping testing is enabled in a TTY session, the script prints per-host ping progress and the measured average before the candidate table.

## Supported Keys

The script exposes friendly keys, but only accepts keys that Nord's live V2 metadata currently supports.

Common protocol keys:

- `udp` = OpenVPN UDP
- `tcp` = OpenVPN TCP
- `xor_udp` = OpenVPN XOR UDP when available
- `xor_tcp` = OpenVPN XOR TCP when available

Common group keys:

- `standard` = Standard
- `p2p` = P2P
- `obfuscated` = Obfuscated when available
- `double` = Double VPN when available
- `onion` = Onion over VPN when available
- `dedicated` = Dedicated IP when available

Without `--advanced`, the interactive prompts only show the default common choices. On the CLI, explicit advanced keys are still allowed when Nord's live V2 metadata supports them.

If you request a key that is not currently supported by Nord's live metadata, the script exits with a clear error listing the currently supported values.

## Download Behavior

- Download URLs are built from the selected hostname and protocol.
- Output filenames include country, country code, city, protocol, group, and the short server label such as `au654`.
- The default output directory is `./NordOVPNs` relative to your current working directory.
- The script creates the output directory if it does not exist.
- `--dry-run` does not create the output directory or any files.
- Existing files cause an error in non-interactive mode unless you pass `--force`.
- In interactive mode, existing files trigger an overwrite prompt.
- `Ctrl+C` and normal termination signals are handled cleanly and exit with a cancellation status instead of a raw traceback.
- If you selected multiple downloads and one fails, the script continues the rest and reports a partial-failure summary at the end.
- Downloaded payloads are validated before being written as `.ovpn` files.
- Downloads are written through a temp file and atomically renamed into place so an interrupt does not leave a partial final `.ovpn`.
- A forced `SIGKILL` cannot be trapped by Python, but the script keeps the final destination path safe and cleans any stale temp files on the next run.
- `--download-best` and `--download-top` skip the interactive download-selection prompt.

## Caching

The script caches Nord API responses under:

```text
macOS: ~/Library/Caches/nord-ovpn-picker/
Linux: $XDG_CACHE_HOME/nord-ovpn-picker/ or ~/.cache/nord-ovpn-picker/
Windows: %LOCALAPPDATA%\nord-ovpn-picker\
```

Current cache behavior:

- Recommendation queries are cached.
- The V2 metadata and server dataset are cached together in the V2 payload cache.
- Default cache TTL is `6 hours`.
- `--refresh-cache` bypasses the cache and refreshes those payloads.

## Result Table

The candidate table includes:

- result index
- hostname
- country
- city
- protocol
- group
- load
- average ping
- computed score
- station IP
- recommended marker

## Notes

- Live supported groups and OpenVPN protocol identifiers are derived from Nord's current V2 metadata instead of being hard-coded from older examples.
- In non-interactive mode, `--country` is required unless you are using one of the pure listing commands.
- `--list-cities` requires `--country`.
- If you run in a non-TTY context without `--download-best` or `--download-top`, the script prints the candidate table and exits without downloading anything.
- The current default output path is `./NordOVPNs` relative to where you launch the command, not relative to the repo root.
- `NordOVPNs/` is git-ignored in this repo.
