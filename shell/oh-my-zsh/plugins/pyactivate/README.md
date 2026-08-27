# pyactivate

`pyactivate` is a small Zsh helper for manual Python virtual environment switching.
It supports multiple local venvs via interactive selection (when `fzf` is available), remembers the activated root, and auto-deactivates when you leave that root.
It discovers environments by scanning immediate child directories of the selected/current project root.

## Requirements

- `zsh`
- Oh My Zsh
- Virtual environment layout with `pyvenv.cfg` and `bin/activate`
- `fzf` (optional): required only for interactive selection when multiple venvs are found in the same directory

The plugin works without `fzf` when there is:

- exactly one venv under the target dir,
- an explicit venv path is provided, or
- no interactivity is needed (bare activate/deactivate semantics still work).

## Install without cloning

1. Choose a destination for the custom plugin folder.
2. Download the single plugin file directly:

```zsh
PYACTIVATE_DIR="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/pyactivate"
mkdir -p "${PYACTIVATE_DIR}"
curl -fsSL -o "${PYACTIVATE_DIR}/pyactivate.plugin.zsh" \
  "https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/shell/oh-my-zsh/plugins/pyactivate/pyactivate.plugin.zsh"
```

If you do not have `curl`, use this fallback:

```zsh
PYACTIVATE_DIR="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/pyactivate"
mkdir -p "${PYACTIVATE_DIR}"
wget -O "${PYACTIVATE_DIR}/pyactivate.plugin.zsh" \
  "https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/shell/oh-my-zsh/plugins/pyactivate/pyactivate.plugin.zsh"
```

Full raw file source:

- [`https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/shell/oh-my-zsh/plugins/pyactivate/pyactivate.plugin.zsh`](https://raw.githubusercontent.com/XxUnkn0wnxX/Scripts/master/shell/oh-my-zsh/plugins/pyactivate/pyactivate.plugin.zsh)

To update/reinstall, rerun the same command; it overwrites the file.
If your plugin manager updates only Git-based plugins, raw single-file installs
are not auto-updated. Rerun the `curl`/`wget` command manually to update them.

Enable the plugin in `~/.zshrc`:

```zsh
plugins=(
  git
  pyactivate
  # ... all your existing plugins ...
)
```

Then load it:

```zsh
source ~/.zshrc
```

or open a new shell.

## Usage

- `pyactivate`
  - If the current directory has one local venv, it is activated.
  - If already active in the same project root, it deactivates.
- `pyactivate /path/to/project`
  - Activates in that directory (or switches from an already active env).
- `pyactivate /absolute/path/to/.venv`
  - Activates that exact virtualenv directly, anywhere.
- `pyactivate /path/to/child`
  - In a parent+child layout, works with nested project behavior:
    if already in an active parent venv, running here switches to child when applicable.
- `pyactivate --help`
  - Prints basic usage and behavior.
- `pyactivate -h`
  - Alias for `pyactivate --help`.

When multiple venvs are found in one directory, an `fzf` menu is shown (if available) using arrow keys + Enter.
Without `fzf`, multi-choice paths fail fast and keep your current environment unchanged. Pass the exact virtualenv path to activate one directly.
`Esc` or `q` cancels selection and keeps the current environment.

## Help text (current)

```text
Usage: pyactivate [<project-or-virtualenv-path>]
Without an argument, activates a single local virtual environment.
If multiple virtual environments are found, pick one with arrow keys + Enter (Esc/q cancels).
Running in the active project's root deactivates the current environment.
Running inside a nested project switches environments and leaving the active root deactivates.
An argument may be a project directory or an exact virtualenv path, anywhere.
```

## Lifecycle semantics

- Same-root re-run toggles off:
  running `pyactivate` again from the currently active project root deactivates.
- Nested behavior:
  when a child project has its own venv and one is active at a parent root, `pyactivate` can switch to the child venv.
- Descendants stay active:
  while the current working directory is under the remembered root, the env remains active.
- Leave the active root:
  changing directory outside the remembered root deactivates automatically.
- Selection canceled:
  interactive selection cancellation does not alter the currently active environment.

## Tests

From the Scripts repository root, contributors can run:

```zsh
python -m pytest --disable-plugin-autoload tests/pyactivate
```

## Uninstall

1. Remove `pyactivate` from your `plugins=(...)` list.
2. Delete the folder:

```zsh
rm -rf "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/pyactivate"
```

No separate installer script is used.

## License

See [`COPYING.md`](../../../../COPYING.md) (GPL-3.0).
