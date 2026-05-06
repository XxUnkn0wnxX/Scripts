# Nord OVPN Picker

`nord_ovpn_picker.py` is a local CLI that finds NordVPN OpenVPN servers by country, optional city, protocol, and group, then downloads chosen `.ovpn` files into a `NordOVPNs/` folder in your current working directory.

## Features

- Interactive mode when you run the script with no filter arguments.
- Type-to-filter autocomplete for country, city, protocol, and group prompts.
- Non-interactive CLI mode for direct scripted use.
- Recommendation-first server selection using Nord's recommendation API.
- Automatic fallback to Nord's V2 dataset when recommendations are not enough or `--full-data` is used.
- Optional ping scoring for the top candidates.
- Rich results table with hostname, location, protocol, group, load, ping, score, station IP, and the recommended marker.
- Direct `.ovpn` downloads for the best candidate, the top N, or an interactive selection.
- Automatic re-exec into the repo-local `.venv` when the script is started from the wrong Python interpreter.
- Current-working-directory output folder so aliases, symlinks, and absolute-path calls still write where you launched them from.
- API response caching under `~/.cache/nord-ovpn-picker/`.

## Setup

Run these commands from the `Scripts` repo root:

```bash
python3 -m venv .venv
source "$HOME/.zshrc"
source .venv/bin/activate
pip install -r requirements.txt
```

The script expects this repo-local `.venv` to exist. If it does not find one, it stops and tells you to follow these setup steps instead of silently using the wrong Python environment.

If the repo-local `.venv` exists but the script was launched from the wrong Python interpreter, it re-execs itself into that `.venv` automatically. This works whether you run it from the repo root, by absolute path, through an alias, or through a symlink. It does not activate your current shell session globally; it only reruns the script with the correct interpreter.

## How It Chooses Servers

The default flow is:

1. Resolve the country from Nord's country list.
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

The interactive country, city, protocol, and group prompts use live prefix filtering as you type. Instead of printing the full city list first, the menu narrows in place so you can keep typing until the option you want is visible, then press `Tab` or `Enter`.

Interactive defaults:

- Country: required
- City: blank means country-wide results
- Protocol: `udp`
- Group: `standard`
- Result limit: `10`
- Ping test: `yes`

If you leave the final download selection blank, the script only prints the candidate table and exits without downloading anything.

Interactive download selection accepts:

- `1`
- `1,3,5`
- `top5`
- `all`
- `none`
- blank input to skip downloading

Examples of the interactive prefix matching:

- typing `US` narrows the country list to `United States`
- typing `Ch` then `Chic` narrows United States cities down to `Chicago`
- typing `T` narrows protocol choices to `TCP`
- typing `P` narrows the default group list to `P2P`

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
python3 nord_ovpn_picker.py --country AU --city Melb --protocol udp --group standard --limit 10
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

Because the default output path is based on your current working directory, these invocations write into `./NordOVPNs` wherever you launched the command from, not beside the script itself.

## Arguments

### Filters

- `--country <name-or-code>`
  Required in non-interactive mode. Accepts names and common short matches such as `Australia`, `AU`, `aus`, and common aliases for some countries such as `USA`, `UK`, and `UAE`.
- `--city <name>`
  Optional city filter. Partial matches such as `Melb` work when they resolve cleanly.
- `--protocol <key>`
  Protocol key to use. Supported values are driven by Nord's current live metadata.
- `--group <key>`
  Group key to use. Supported values are driven by Nord's current live metadata.
- `--limit <number>`
  Number of candidate rows to return. Must be a positive integer.

If you omit `--protocol`, `--group`, or `--limit` in non-interactive mode, the defaults are `udp`, `standard`, and `10`.

### Download Control

- `--output-dir <path>`
  Override the default output directory.
- `--download-best`
  Download only the top candidate.
- `--download-top <number>`
  Download the top N candidates. Must be a positive integer.
- `--force`
  Overwrite existing files without prompting.
- `--dry-run`
  Show what would be downloaded without writing files.

### Query Behavior

- `--full-data`
  Skip the recommendation-first shortcut and use the V2 dataset path.
- `--no-ping`
  Disable ping testing and rank only from load-based scoring.
- `--ping-count <number>`
  Ping attempts per host. Must be a positive integer. Default: `3`.
- `--refresh-cache`
  Ignore cached API payloads and fetch fresh data.
- `--advanced`
  Expose advanced live-supported options such as XOR OpenVPN protocols when Nord's current metadata supports them.
- `--verbose`
  Enable debug logging for HTTP requests, cache usage, and ping execution.

If you do not pass `--no-ping`, non-interactive mode pings candidates by default.

### Listing Commands

- `--list-countries`
  Print all countries returned by Nord.
- `--list-cities`
  Print cities for the selected country. Requires `--country`.
- `--list-groups`
  Print the currently supported group keys from live V2 metadata.
- `--list-technologies`
  Print the currently available Nord technologies from live V2 metadata.

## Supported Keys

The script exposes friendly keys, but only accepts keys that Nord's live V2 metadata currently supports.

Common protocol keys:

- `udp` = OpenVPN UDP
- `tcp` = OpenVPN TCP
- `xor_udp` = OpenVPN XOR UDP when available and `--advanced` is used
- `xor_tcp` = OpenVPN XOR TCP when available and `--advanced` is used

Common group keys:

- `standard` = Standard
- `p2p` = P2P
- `obfuscated` = Obfuscated when available and `--advanced` is used
- `double` = Double VPN when available and `--advanced` is used
- `onion` = Onion over VPN when available and `--advanced` is used
- `dedicated` = Dedicated IP when available and `--advanced` is used

If you request a key that is not currently supported by Nord's live metadata, the script exits with a clear error listing the currently supported values.

## Download Behavior

- Download URLs are built from the selected hostname and protocol.
- Output filenames include country, country code, city, protocol, group, and hostname.
- The default output directory is `./NordOVPNs` relative to your current working directory.
- The script creates the output directory if it does not exist.
- Existing files cause an error in non-interactive mode unless you pass `--force`.
- In interactive mode, existing files trigger an overwrite prompt.
- If you selected multiple downloads and one fails, the script continues the rest and reports a partial-failure summary at the end.
- Downloaded payloads are validated before being written as `.ovpn` files.
- `--download-best` and `--download-top` skip the interactive download-selection prompt.

## Caching

The script caches Nord API responses under:

```text
~/.cache/nord-ovpn-picker/
```

Current cache behavior:

- Countries are cached.
- Recommendation queries are cached.
- The V2 server dataset is cached.
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
