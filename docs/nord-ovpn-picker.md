# Nord OVPN Picker

`nord_ovpn_picker.py` is a local CLI that finds NordVPN OpenVPN servers by country, optional city, protocol, and group, then downloads chosen `.ovpn` files into a `NordOVPNs/` folder in your current working directory.

## Setup

Run these commands from the `Scripts` repo root:

```bash
/usr/local/bin/python3 -m venv .venv
source "$HOME/.zshrc"
pyactivate
.venv/bin/pip install -r requirements.txt
```

The script expects this repo-local `.venv` to exist. If it does not find one, it stops and tells you to follow these setup steps instead of silently using the wrong Python environment.

## Usage

Basic listing:

```bash
./nord_ovpn_picker.py --list-countries
./nord_ovpn_picker.py --country Australia --list-cities
./nord_ovpn_picker.py --list-groups
./nord_ovpn_picker.py --list-technologies
```

Show candidates:

```bash
./nord_ovpn_picker.py --country Australia --protocol udp --group standard --limit 5
./nord_ovpn_picker.py --country Australia --city Melbourne --protocol tcp --group p2p --limit 5 --no-ping
```

Download:

```bash
./nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best
./nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-top 3 --force
./nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
```

Custom output directory:

```bash
./nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-top 2 --output-dir /path/to/output
```

## Invocation From Anywhere

The script can be run directly, through an alias, by absolute path, or through a symlink. On startup it checks whether it is already running inside this repo's `.venv`; if not, it re-execs itself into that interpreter automatically.

That means these styles all work as long as the repo-local `.venv` exists:

```bash
/Users/ovidijus/Apps/Scripts/nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
```

```bash
/some/symlink/to/nord_ovpn_picker.py --country Australia --protocol udp --group standard --download-best --dry-run
```

## Notes

- Live supported groups and OpenVPN protocol identifiers are derived from Nord's current V2 metadata instead of being hard-coded from older examples.
- The current default output path is `./NordOVPNs` relative to where you launch the command, not relative to the repo root.
- `NordOVPNs/` is git-ignored in this repo.
