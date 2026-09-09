# codex-profiles

Discover Codex CLI profiles, pick one interactively, and start or resume a
session with short Zsh commands. Profile names are completed from the files on
disk, so adding or removing a profile takes effect immediately.

## Requirements

- Zsh 5.8 or newer.
- The system `stty` utility for the interactive picker (included on macOS/Linux).
- Oh My Zsh, or a Zsh configuration that sources the plugin directly.
- Codex CLI with standalone `--profile` files (0.134.0 or newer).
- At least one `<name>.config.toml` profile in your Codex home.

The plugin itself needs no Python, TOML parser, `fzf`, or package manager.
Python and pytest are used only by the contributor test suite.

The default launch flags are `--yolo --search`. `--yolo` bypasses Codex's
approval prompts and sandbox, and `--search` enables live web search. All three
launchers (`cx`, `cxr`, and `cxlast`) pass both flags by default; see
[Configuration](#configuration) to change or remove them.

## Install from this repository and sync changes

The source maintained in this repository is
`shell/oh-my-zsh/plugins/codex-profiles/`. After editing and testing that source,
run these commands from the repository root to install or update the local copy:

```zsh
CODEX_PROFILES_DIR="${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}/plugins/codex-profiles"
mkdir -p "$CODEX_PROFILES_DIR"
cp shell/oh-my-zsh/plugins/codex-profiles/codex-profiles.plugin.zsh "$CODEX_PROFILES_DIR/"
```

This copies only the runtime plugin file. Keep this README in the repository.
Future changes should be made in this repository, validated, then copied again.
A copied installation is not updated automatically by Git-based plugin managers.

Add `codex-profiles` to your existing `plugins=(...)` list in `~/.zshrc`, before
Oh My Zsh is sourced:

```zsh
plugins=(
  git
  pyactivate
  codex-profiles
  # ... all your other existing plugins ...
)
```

Open a new shell, or reload just the plugin in your current Oh My Zsh shell:

```zsh
source "${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}/plugins/codex-profiles/codex-profiles.plugin.zsh"
```

Without Oh My Zsh, initialize Zsh completion before sourcing the plugin:

```zsh
autoload -Uz compinit
compinit
source /path/to/codex-profiles.plugin.zsh
```

## Install a published version without cloning

The single runtime file can also be installed directly from this repository's
`master` branch:

```zsh
CODEX_PROFILES_DIR="${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}/plugins/codex-profiles"
mkdir -p "$CODEX_PROFILES_DIR"
curl -fsSL -o "$CODEX_PROFILES_DIR/codex-profiles.plugin.zsh" \
  "https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/shell/oh-my-zsh/plugins/codex-profiles/codex-profiles.plugin.zsh"
```

Enable and load it as described above. Rerun the download commands to update a
published installation; use the repository copy commands during development.
Documentation stays in this repository rather than the installed plugin folder.

## Usage

The `cx` prefix is a short mnemonic for “CodeX”; `r` means resume and `l` means
list. These are this plugin's convenience commands; Codex's executable is `codex`.

`work` is a generic example profile name. Replace it with a name shown by `cxl`.

| Command | Behavior |
| --- | --- |
| `cxl` or `codex-profiles` | Print available profile names, one per line. |
| `cx` | Pick a profile, then start a new session. |
| `cx work` | Start a new session with the named profile. |
| `cx --profile work` | Select the profile explicitly with `--profile` or `-p`. |
| `cx work "review this repository"` | Start with an initial prompt. |
| `cxr` | Pick a profile, then open Codex's session resume picker. |
| `cxr work` | Open the resume picker with the named profile. |
| `cxr work --last` | Resume the latest session for the current directory. |
| `cxr --last` | Pick a profile, then resume the latest session. |
| `cxr work --all` | Show sessions from all directories in the resume picker. |
| `cxr work <session-id>` | Resume a particular session. |
| `cxlast work` | Shortcut for `cxr work --last`. |
| `cxr help` or `cxr --help` | Show the plugin's short usage guide. |

`cx`, `cxr`, `cxlast`, `cxl`, and `codex-profiles` also accept `-h` and `--help`.
Use `codex --help` or `codex resume --help` for Codex's full option reference.
The word `help` by itself is reserved for the usage guide; use
`cx --profile help` to launch a profile actually named `help`. The
`--profile=NAME` form also works. Put the profile selector before other options.

The numbered profile picker launches as soon as you type the complete displayed
number; no Enter is needed. There is no profile count limit in the picker,
`cxl`, direct selection, or completion. Labels use enough digits for the whole
list so a shorter number cannot accidentally select the wrong profile:

| Number of profiles | Displayed labels | Select the first profile |
| --- | --- | --- |
| 1–9 | `1`, `2`, … | Press `1`. |
| 10–99 | `01`, `02`, … | Type `01`. |
| 100–999 | `001`, `002`, … | Type `001`. |
| 1000 or more | Width grows with the list. | Type the complete displayed label. |

Backspace removes the last digit before selection. `q`, Escape, Enter, or Ctrl-D
cancels with exit status 1; Ctrl-C cancels with exit status 130. Cancellation
does not start Codex, and terminal input settings are restored before returning
to the shell. Invalid choices clear the partial number and let you retry.
Without a terminal, supply a profile explicitly. Direct names and Tab completion
remain convenient for large lists.

The two ordinary launch forms expand to:

```zsh
cx work
# codex --yolo --search -p work

cxr work --last
# codex resume --yolo --search -p work --last
```

Arguments after the profile are passed through with their original quoting,
including prompts, session IDs, `--last`, `--all`, `--model`, `-c`, and `--cd`.
The shell command returns Codex's exit status.

Use `cxlast` without a name to pick a profile before resuming the latest session.
`--last` skips Codex's session picker; it does not skip the plugin's profile
picker when no profile was supplied. Add `--all` to consider other directories.

## Tab completion

For a profile named `work`, type `cx wo` or `cxr wo` and press Tab to complete it.
`cxlast` has the same profile completion. Completion rereads the current Codex
home, so there is no profile cache to refresh after editing files or changing
`CODEX_HOME`. Existing completion for the `codex` command is retained.

## Configuration

Set these before Oh My Zsh loads in `~/.zshrc`:

```zsh
# Optional: relocate Codex configuration/state. Use an existing directory.
export CODEX_HOME="$HOME/config/codex"

# Optional: choose one executable path. The default is codex from PATH.
CODEX_PROFILES_BIN="$HOME/tools/codex"

# Optional: replace the default launch flags with a Zsh array.
CODEX_PROFILES_FLAGS=(--search)
# Or add no launch flags and use Codex's configured defaults:
# CODEX_PROFILES_FLAGS=()
```

`CODEX_PROFILES_BIN` is a single executable name or path, including paths with
spaces. Use `CODEX_PROFILES_FLAGS` for arguments; do not put a shell command in
the executable setting. Flag array elements remain separate arguments. Reloading
the plugin preserves a configured array, including an empty one.

Relative `CODEX_HOME` paths resolve from the directory where you invoke the
helper. The resolved home is passed to the child process, including when the
shell variable was not exported or `--cd` changes Codex's working directory.

The plugin only discovers and selects existing profiles. Codex loads the actual
settings and applies its normal configuration precedence. It does not copy your
profiles into the plugin, parse their private contents, or change an active
session's configuration.

## Paths and platforms

| Environment | Codex profile directory |
| --- | --- |
| macOS or Linux | `$CODEX_HOME` when nonempty, otherwise `$HOME/.codex`. |
| Windows with WSL | The same rule inside the Linux distribution, using its Linux home. |
| Custom Codex location | Set `CODEX_HOME` to the existing directory, using that shell's path syntax. |

For example, `$HOME/.codex/work.config.toml` becomes the profile
`work`. The base `config.toml` is not a named profile. Names may contain
ASCII letters, digits, hyphens, and underscores. Discovery skips invalid names,
directories, unreadable files, and broken symlinks; readable file symlinks work.
Legacy `[profiles.name]` tables in `config.toml` are not listed.

The Codex executable's installation folder and Codex's configuration home are
separate. Homebrew, npm, and standalone installations work when the executable
is on `PATH`, or through `CODEX_PROFILES_BIN`. The plugin does not guess an
installation prefix or use `XDG_CONFIG_HOME` as an alternative Codex home.

For reference, the standalone installer normally places the visible executable
in `$HOME/.local/bin` on macOS/Linux and
`%LOCALAPPDATA%\Programs\OpenAI\Codex\bin` on native Windows.
`CODEX_INSTALL_DIR` changes that installer destination; `CODEX_HOME` controls
configuration and state. See the [official environment variable reference](https://learn.chatgpt.com/docs/config-file/environment-variables).

For Windows, install Zsh, Oh My Zsh, and the Linux Codex CLI inside WSL. WSL runs
a Linux environment on Windows, including its own home directory. Windows
Terminal can host that shell. PowerShell and Command Prompt cannot source a
`.plugin.zsh` file. Native Windows Codex and a WSL installation can have separate
homes; this plugin does not automatically bridge their paths. Cygwin/MSYS2 and
invoking `codex.exe` from WSL have not been validated.

References: [Codex profiles and state locations](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles),
[Codex CLI commands](https://learn.chatgpt.com/docs/developer-commands), and
[Microsoft's WSL overview](https://learn.microsoft.com/en-us/windows/wsl/about).

## Tests

The suite follows the repository's existing pytest approach: temporary homes,
fake executables, parameterized cases, and pseudo-terminal interaction. It never
starts a real Codex session or writes to the installed Codex home.

From the repository root, with the project's Python environment active:

```zsh
python -m pytest --disable-plugin-autoload tests/codex_profiles
python -m compileall -q tests/codex_profiles
zsh -n shell/oh-my-zsh/plugins/codex-profiles/codex-profiles.plugin.zsh
```

To test another installed Zsh version, use `TEST_ZSH`:

```zsh
TEST_ZSH=/bin/zsh python -m pytest --disable-plugin-autoload tests/codex_profiles
```

| Matrix area | Cases |
| --- | --- |
| Discovery | Default/custom homes, changed home, missing/empty directories, valid and invalid filenames, file symlinks. |
| Launching | New, resume, latest session, direct selection, exact argument forwarding and exit status. |
| Configuration | Default/custom/empty flag arrays, executable overrides, paths with spaces, repeated loading. |
| Help and errors | Help variants, unknown profiles, unavailable executable, noninteractive invocation. |
| Picker | Immediate selection, 1/9/10/12/100-profile boundaries, padded numbers, partial input, Backspace, invalid input and retry, cancellation, Ctrl-C/SIGINT, terminal restoration, restoration failure and shell survival. |
| Completion and shell integration | Registered completion, refreshed candidates, real Tab keystrokes in Zsh, existing Codex completion, caller option preservation. |

Portability checks should run this same suite on macOS and Linux/WSL with an
available Zsh. A successful macOS run does not establish that Linux or WSL was
tested.

## Uninstall

Remove `codex-profiles` from your `plugins=(...)` list, then delete its installed
folder:

```zsh
rm -rf "${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}/plugins/codex-profiles"
```

Open a new shell to remove the loaded functions. Your Codex profiles remain in
your Codex home.

## License

See [`COPYING.md`](../../../../COPYING.md) (GPL-3.0).
