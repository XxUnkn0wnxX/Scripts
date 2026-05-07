# vpnroute

[`vpnroute.py`](../vpnroute.py) is a local CLI that converts websites/domains into OpenVPN/Viscosity route commands. Dependencies are installed from [`requirements.txt`](../requirements.txt).

## Features

- File input mode for domain lists such as `sites.txt`
- Interactive paste mode when you launch the script without an input file
- Repo-local `.venv` detection with automatic re-exec into the correct Python
- Short setup/dependency errors that point back to this document
- IPv4 `A` record resolution with global route deduplication
- CIDR-aware `--netmask` handling for values like `32`, `/32`, `24`, `/24`, or `255.255.255.255`
- Optional `--gateway`, `--metric`, `--no-comments` (also `--no-comment` / `--nocom`), `--iponly`, and `--verbose` flags
- Plain-text output suitable for OpenVPN and Viscosity route blocks
- Rich terminal panels, progress, warnings, tables, and final summaries

## Setup

Run these commands from the `Scripts` repo root:

```bash
python3 -m venv .venv
source "$HOME/.zshrc"
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, use the repo-local `.venv` in the normal Windows location:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Repo-local `.venv` behavior

`vpnroute.py` expects a repo-local `.venv` next to the script. If that `.venv` exists but the script was started from a different Python interpreter, it re-execs itself into the repo-local `.venv` automatically.

This does not activate your parent shell session. It only reruns the script through the correct interpreter.

The re-exec path is OS-aware:

- macOS and Linux use `.venv/bin/python` or `.venv/bin/python3`
- Windows uses `.venv\Scripts\python.exe`

If `.venv` is missing, the script does not create it for you. It exits with a short message and points you back to this document.

## Dependency checking behavior

The startup path is stdlib-only until the script confirms that:

- `requirements.txt` exists next to `vpnroute.py`
- the repo-local `.venv` exists
- a usable Python executable exists inside that `.venv`

After the re-exec step, runtime imports such as Rich and dnspython are loaded. If a required dependency is still missing, the script exits with a short docs-based error instead of trying to install packages automatically.

## Input modes

### File input mode

Use a text file as the first positional argument:

```bash
python3 vpnroute.py sites.txt
```

Each line may be a domain or URL:

```text
https://whatismyipaddress.com/
whatismyipaddress.com
https://example.com/some/page
ifconfig.me
```

The script strips schemes, paths, query strings, fragments, trailing dots, blank lines, and comments so only hostnames are resolved.

### Interactive paste mode

Run the script without an input file:

```bash
python3 vpnroute.py
```

You will see a Rich instruction panel, then you can type or paste one domain/URL per line. Press `Enter` on a blank line after at least one entry to start processing.

If the first line is blank, the script exits cleanly with `No input provided.`

## CLI examples

Basic file usage:

```bash
python3 vpnroute.py sites.txt
```

Full OpenVPN/Viscosity route usage:

```bash
python3 vpnroute.py sites.txt --netmask 32 --gateway vpn_gateway
```

With gateway and metric:

```bash
python3 vpnroute.py sites.txt --netmask 32 --gateway vpn_gateway --metric default
```

Using default gateway/metric values:

```bash
python3 vpnroute.py sites.txt --netmask 255.255.255.255 --gateway default --metric default
```

Custom output path:

```bash
python3 vpnroute.py sites.txt --output viscosity_routes.txt
```

Interactive mode:

```bash
python3 vpnroute.py --gateway vpn_gateway
```

IP-only output:

```bash
python3 vpnroute.py sites.txt --iponly
```

IP-only output with no comments:

```bash
python3 vpnroute.py sites.txt --iponly --no-comments
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
      <td><nobr><code>input_file</code></nobr></td>
      <td>Positional</td>
      <td>Optional file path. This is the only input source that is file/CLI-only. When omitted, the script switches to interactive paste mode.</td>
    </tr>
    <tr>
      <td><nobr><code>--output &lt;path&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. If omitted, the script writes <code>vpn_routes.txt</code> into the current working directory and overwrites it automatically.</td>
    </tr>
    <tr>
      <td><nobr><code>--netmask &lt;value&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. Defaults to <code>255.255.255.255</code>. Accepts dotted-quad masks plus CIDR-like values such as <code>32</code>, <code>/32</code>, <code>24</code>, or <code>/24</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--gateway &lt;value&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. Optional route gateway. Ignored when <code>--iponly</code> is used because that mode outputs only raw IPv4 addresses.</td>
    </tr>
    <tr>
      <td><nobr><code>--metric &lt;value&gt;</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. Optional route metric. If used without <code>--gateway</code>, the script inserts <code>default</code> as the gateway in route-output mode. Ignored by <code>--iponly</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--no-comments</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. Removes domain headings and the grouped <code># invalid urls</code> block from the output file. Aliases: <code>--no-comment</code> and <code>--nocom</code>.</td>
    </tr>
    <tr>
      <td><nobr><code>--iponly</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. Outputs only IPv4 addresses instead of full <code>route ...</code> lines. Still shows comments unless one of the no-comments flags is used.</td>
    </tr>
    <tr>
      <td><nobr><code>--verbose</code></nobr></td>
      <td>Flag</td>
      <td>Works in both interactive and file-input runs. Enables debug logging for troubleshooting.</td>
    </tr>
  </tbody>
</table>

## Route output format

Default output uses plain-text route lines:

```conf
route 104.19.222.79 255.255.255.255
route 104.19.223.79 255.255.255.255
```

By default the file also includes domain grouping comments:

```conf
# whatismyipaddress.com
route 104.19.222.79 255.255.255.255
route 104.19.223.79 255.255.255.255
```

Failed lookups are grouped under an `invalid urls` comment section unless `--no-comments` is used:

```conf
# invalid urls
https://example.invalid/some/path
```

With `--iponly`, the output switches from route commands to plain IPv4 lines. By default it still keeps domain headings and the grouped invalid-URL comment section:

```text
# api.ipify.org
104.26.12.205
104.26.13.205
172.67.74.152
```

## `--netmask`, `--gateway`, and `--metric`

`--netmask` defaults to `255.255.255.255`, but it also accepts CIDR forms such as `32`, `/32`, `24`, or `/24`.

Examples:

- `--netmask 32` becomes `255.255.255.255`
- `--netmask /24` becomes `255.255.255.0`

`--gateway` is optional. `--metric` is also optional. If you provide `--metric` without `--gateway`, the script inserts `default` as the gateway so the route line still has the correct shape.

Examples:

```conf
route 104.19.222.79 255.255.255.255 vpn_gateway
route 104.19.222.79 255.255.255.255 default default
route 104.19.222.79 255.255.255.255 vpn_gateway default
```

## `--no-comments` behavior

By default, comments stay enabled because they make the generated route file easier to read and debug.

If you want pure route lines only, pass:

```bash
python3 vpnroute.py sites.txt --no-comments
```

Aliases:

```bash
python3 vpnroute.py sites.txt --no-comment
python3 vpnroute.py sites.txt --nocom
```

That removes domain headings and failed-domain comments from the output file, but failures are still shown in the terminal UI.

## `--iponly` behavior

If you want only IPv4 addresses with no `route`, subnet mask, gateway, or metric fields, pass:

```bash
python3 vpnroute.py sites.txt --iponly
```

That changes each generated output line to just the IPv4 address itself.

Examples:

```text
# example.com
104.20.23.154
172.66.147.243
```

If you combine it with `--no-comments`, the file becomes one plain block of IP addresses with one IP per line:

```bash
python3 vpnroute.py sites.txt --iponly --no-comments
```

```text
104.20.23.154
172.66.147.243
```

`--iponly` works independently of `--no-comments`. It only changes the per-line payload from route commands to raw IPs.

## Output file behavior

The default output file is `vpn_routes.txt`.

By default that file is written to your current working directory, not the directory where `vpnroute.py` lives. That means:

- if you run the script from the repo root, `vpn_routes.txt` is created in the repo root
- if you run the script from somewhere else by absolute path, `vpn_routes.txt` is created in that caller directory instead
- if you pass `--output`, that path is used instead

Use `--output` to pick another path. The script writes output atomically so interrupted writes do not leave a partially written destination file behind.

If the destination already exists, the script overwrites it with the new output automatically.

The route file itself stays plain text. Rich formatting is only used in the terminal.

## Platform support

- macOS: supported
- Linux and other Unix-like systems: supported
- Windows: supported for repo-local `.venv` detection and re-exec

DNS resolution is limited to IPv4 `A` records.

## Testing notes

Run the focused test suite for this utility with:

```bash
python -m pytest tests/vpnroute
```

Run the full repo test suite with:

```bash
python -m pytest
```

When editing the Python sources, it is also useful to run:

```bash
python -m compileall vpnroute.py tests/vpnroute
```

## CDN-backed domains and DNS changes

Many CDN-backed domains resolve to multiple IPs and those IPs can change over time. The generated routes are only as current as the DNS answers returned when you run the script.

If a site changes providers, adds new edge IPs, or rotates addresses frequently, regenerate the route file instead of assuming an older output is still complete.
