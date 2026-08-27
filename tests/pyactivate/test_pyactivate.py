from __future__ import annotations

import os
import pty
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "shell/oh-my-zsh/plugins/pyactivate/pyactivate.plugin.zsh"
ZSH_PATH = shutil.which("zsh")

if ZSH_PATH is None:
    pytest.skip("zsh is required", allow_module_level=True)
assert PLUGIN_PATH.is_file(), f"Missing pyactivate plugin: {PLUGIN_PATH}"


HELP_TEXT = (
    "Usage: pyactivate [<project-or-virtualenv-path>]\n"
    "Without an argument, activates a single local virtual environment.\n"
    "If multiple virtual environments are found, pick one with arrow keys + Enter (Esc/q cancels).\n"
    "Running in the active project's root deactivates the current environment.\n"
    "Running inside a nested project switches environments and leaving the active root deactivates.\n"
    "An argument may be a project directory or an exact virtualenv path, anywhere.\n"
)


def _shell_quote(value: Path | str) -> str:
    return shlex.quote(str(value))


def _run_zsh(
    body: str,
    *,
    cwd: Path,
    pty_stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = f"source {_shell_quote(PLUGIN_PATH)}\n{body}"
    args = [ZSH_PATH, "-f", "-c", command]
    if pty_stdin is None:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdin=slave_fd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    os.close(slave_fd)
    try:
        if pty_stdin:
            os.write(master_fd, pty_stdin.encode())
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
    finally:
        os.close(master_fd)
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _make_fake_venv(path: Path, *, fail: bool = False) -> Path:
    path.mkdir(parents=True)
    (path / "pyvenv.cfg").write_text(
        "home = /fake/python\nversion = 3.12.0\n", encoding="utf-8"
    )
    activate = path / "bin" / "activate"
    activate.parent.mkdir()
    activate.write_text(
        f"""VIRTUAL_ENV={_shell_quote(path.resolve())}
export VIRTUAL_ENV
_OLD_VIRTUAL_PATH="$PATH"
PATH="$VIRTUAL_ENV/bin:$PATH"
export PATH
deactivate() {{
    PATH="$_OLD_VIRTUAL_PATH"
    export PATH
    unset _OLD_VIRTUAL_PATH
    unset VIRTUAL_ENV VIRTUAL_ENV_PROMPT
    unfunction deactivate 2>/dev/null || true
}}
{"return 1" if fail else ""}
""",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("flag", ("-h", "--help"))
def test_help_is_exact_and_side_effect_free(tmp_path: Path, flag: str):
    result = _run_zsh(
        f"""before_path="$PATH"
export VIRTUAL_ENV=sentinel-venv
export VENV_ROOT=sentinel-root
pyactivate {flag}
print -u 2 -- "$VIRTUAL_ENV"
print -u 2 -- "$VENV_ROOT"
print -u 2 -- "$before_path"
print -u 2 -- "$PATH"
print -u 2 -- "$PWD"
""",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout == HELP_TEXT
    stderr_lines = result.stderr.splitlines()
    assert len(stderr_lines) == 5
    assert stderr_lines[0] == "sentinel-venv"
    assert stderr_lines[1] == "sentinel-root"
    assert stderr_lines[2] == stderr_lines[3]
    assert stderr_lines[4] == str(tmp_path)


def test_source_twice_deduplicates_chpwd_hook(tmp_path: Path):
    result = _run_zsh(
        f"""source {_shell_quote(PLUGIN_PATH)}
count=0
for hook in $chpwd_functions; do
    if [[ "$hook" == check_venv_dir ]]; then
        (( count++ ))
    fi
done
print -r -- "$count"
""",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout == "1\n"
    assert result.stderr == ""


def test_multiple_arguments_preserve_environment(tmp_path: Path):
    result = _run_zsh(
        """before_path="$PATH"
export VIRTUAL_ENV=sentinel-venv
export VENV_ROOT=sentinel-root
pyactivate first second
exit_code=$?
print -u 2 -- "$VIRTUAL_ENV"
print -u 2 -- "$VENV_ROOT"
print -u 2 -- "$before_path"
print -u 2 -- "$PATH"
exit $exit_code
""",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    stderr_lines = result.stderr.splitlines()
    assert stderr_lines[0] == "Usage: pyactivate [<project-or-virtualenv-path>]"
    assert stderr_lines[1:3] == ["sentinel-venv", "sentinel-root"]
    assert stderr_lines[3] == stderr_lines[4]
    assert result.stdout == ""


def test_project_paths_with_spaces_and_exact_venv_path(tmp_path: Path):
    project = tmp_path / "project with spaces"
    descendant = project / "nested" / "descendant"
    outside = tmp_path / "outside"
    descendant.mkdir(parents=True)
    outside.mkdir()
    venv = _make_fake_venv(project / ".venv")

    result = _run_zsh(
        f"""initial_path="$PATH"
cd {_shell_quote(project)}
pyactivate
print -r -- "state=activated:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$VIRTUAL_ENV/bin:$initial_path" ]]; then print -r -- "path=activated"; fi
cd {_shell_quote(descendant)}
print -r -- "state=descendant:$VIRTUAL_ENV:$VENV_ROOT"
cd {_shell_quote(outside)}
print -r -- "state=outside:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$initial_path" ]]; then print -r -- "path=restored"; fi
pyactivate {_shell_quote(venv)}
print -r -- "state=exact:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$VIRTUAL_ENV/bin:$initial_path" ]]; then print -r -- "path=exact"; fi
cd {_shell_quote(project)}
pyactivate
print -r -- "state=toggled-off:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$initial_path" ]]; then print -r -- "path=toggled-off"; fi
""",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert f"state=activated:{venv}:{project}" in lines
    assert "path=activated" in lines
    assert f"state=descendant:{venv}:{project}" in lines
    assert "Deactivated virtual environment due to leaving" in result.stdout
    assert "state=outside::" in lines
    assert "path=restored" in lines
    assert f"state=exact:{venv}:{project}" in lines
    assert "path=exact" in lines
    assert "state=toggled-off::" in lines
    assert "path=toggled-off" in lines


def test_nested_project_switches_and_parent_cd_deactivates(tmp_path: Path):
    parent = tmp_path / "parent project"
    child = parent / "child project"
    parent.mkdir()
    child.mkdir()
    parent_venv = _make_fake_venv(parent / ".venv")
    child_venv = _make_fake_venv(child / ".venv")

    result = _run_zsh(
        f"""initial_path="$PATH"
cd {_shell_quote(parent)}
pyactivate
print -r -- "state=parent:$VIRTUAL_ENV:$VENV_ROOT"
cd {_shell_quote(child)}
pyactivate
print -r -- "state=child:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$VIRTUAL_ENV/bin:$initial_path" ]]; then print -r -- "path=child"; fi
cd {_shell_quote(parent)}
print -r -- "state=back:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$initial_path" ]]; then print -r -- "path=restored"; fi
""",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert f"state=parent:{parent_venv}:{parent}" in lines
    assert f"state=child:{child_venv}:{child}" in lines
    assert "path=child" in lines
    assert "Deactivated virtual environment due to leaving" in result.stdout
    assert "state=back::" in lines
    assert "path=restored" in lines


def test_interactive_selection_uses_fake_fzf(tmp_path: Path):
    parent = tmp_path / "parent"
    child = parent / "child"
    parent.mkdir()
    child.mkdir()
    parent_venv = _make_fake_venv(parent / ".venv")
    _make_fake_venv(child / ".venv")
    selected_venv = _make_fake_venv(child / ".venv-test")

    result = _run_zsh(
        f"""unset VIRTUAL_ENV VENV_ROOT
initial_path="$PATH"
fzf() {{
    while IFS= read -r candidate; do
        :
    done
    print -r -- ".venv-test"
}}
cd {_shell_quote(parent)}
pyactivate
cd {_shell_quote(child)}
pyactivate
exit_code=$?
print -r -- "state=$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$VIRTUAL_ENV/bin:$initial_path" ]]; then print -r -- "path=selected"; fi
exit $exit_code
""",
        cwd=tmp_path,
        pty_stdin="",
    )

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert f"state={selected_venv}:{child}" in lines
    assert "path=selected" in lines
    assert f"Activating virtual environment in {parent_venv}" in result.stdout


def test_interactive_cancel_preserves_parent_environment(tmp_path: Path):
    parent = tmp_path / "parent"
    child = parent / "child"
    parent.mkdir()
    child.mkdir()
    parent_venv = _make_fake_venv(parent / ".venv")
    _make_fake_venv(child / ".venv")
    _make_fake_venv(child / ".venv-test")

    result = _run_zsh(
        f"""unset VIRTUAL_ENV VENV_ROOT
initial_path="$PATH"
fzf() {{
    while IFS= read -r candidate; do
        :
    done
    return 1
}}
cd {_shell_quote(parent)}
pyactivate
cd {_shell_quote(child)}
pyactivate
exit_code=$?
print -r -- "state=$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$VIRTUAL_ENV/bin:$initial_path" ]]; then print -r -- "path=parent"; fi
exit $exit_code
""",
        cwd=tmp_path,
        pty_stdin="",
    )

    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert "Selection cancelled." in lines
    assert f"state={parent_venv}:{parent}" in lines
    assert "path=parent" in lines


def test_ambiguous_child_without_fzf_preserves_parent_environment(tmp_path: Path):
    parent = tmp_path / "parent"
    child = parent / "child"
    parent.mkdir()
    child.mkdir()
    parent_venv = _make_fake_venv(parent / ".venv")
    _make_fake_venv(child / ".venv")
    _make_fake_venv(child / ".venv-test")

    result = _run_zsh(
        f"""unset VIRTUAL_ENV VENV_ROOT
PATH=""
export PATH
initial_path="$PATH"
cd {_shell_quote(parent)}
pyactivate
cd {_shell_quote(child)}
pyactivate
exit_code=$?
print -r -- "state=$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$VIRTUAL_ENV/bin:$initial_path" ]]; then print -r -- "path=parent"; fi
exit $exit_code
""",
        cwd=tmp_path,
        pty_stdin="",
    )

    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert "Multiple virtual environments found" in result.stdout
    assert f"state={parent_venv}:{parent}" in lines
    assert "path=parent" in lines


def test_failed_switch_restores_previous_environment(tmp_path: Path):
    parent = tmp_path / "parent"
    failed_project = tmp_path / "failed"
    parent.mkdir()
    failed_project.mkdir()
    parent_venv = _make_fake_venv(parent / ".venv")
    failed_venv = _make_fake_venv(failed_project / ".venv", fail=True)

    result = _run_zsh(
        f"""unset VIRTUAL_ENV VENV_ROOT
initial_path="$PATH"
cd {_shell_quote(parent)}
pyactivate
PATH="/pyactivate-active-path-marker:$PATH"
export PATH
active_path="$PATH"
pyactivate {_shell_quote(failed_venv)}
exit_code=$?
print -r -- "state=$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$active_path" ]]; then print -r -- "path=restored"; fi
exit $exit_code
""",
        cwd=tmp_path,
    )

    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert "Failed to source activation script" in result.stdout
    assert "Restored previous virtual environment." in lines
    assert f"state={parent_venv}:{parent}" in lines
    assert "path=restored" in lines


def test_failed_first_activation_cleans_environment(tmp_path: Path):
    failed_venv = _make_fake_venv(tmp_path / "failed" / ".venv", fail=True)

    result = _run_zsh(
        f"""unset VIRTUAL_ENV VENV_ROOT
initial_path="$PATH"
pyactivate {_shell_quote(failed_venv)}
exit_code=$?
print -r -- "state=first:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$initial_path" ]]; then print -r -- "path=restored"; fi
exit $exit_code
""",
        cwd=tmp_path,
    )

    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert "Failed to source activation script" in result.stdout
    assert "state=first::" in lines
    assert "path=restored" in lines


def test_check_venv_dir_handles_root_and_prefix_boundary(tmp_path: Path):
    foo = tmp_path / "foo"
    foobar = tmp_path / "foobar"
    non_root = tmp_path / "non-root"
    foo.mkdir()
    foobar.mkdir()
    non_root.mkdir()

    result = _run_zsh(
        f"""chpwd_functions=()
initial_path="$PATH"
deactivate() {{
    PATH="$initial_path"
    export PATH
    unset VIRTUAL_ENV VIRTUAL_ENV_PROMPT
    unfunction deactivate
}}
export VIRTUAL_ENV=sentinel-venv
export VENV_ROOT=/
cd {_shell_quote(non_root)}
check_venv_dir
print -r -- "state=root:$VIRTUAL_ENV:$VENV_ROOT"
export VIRTUAL_ENV=sentinel-venv
export VENV_ROOT={_shell_quote(foo)}
cd {_shell_quote(foobar)}
check_venv_dir
print -r -- "state=prefix:$VIRTUAL_ENV:$VENV_ROOT"
if [[ "$PATH" == "$initial_path" ]]; then print -r -- "path=restored"; fi
""",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert "state=root:sentinel-venv:/" in lines
    assert f"Deactivated virtual environment due to leaving {foo}." in lines
    assert "state=prefix::" in lines
    assert "path=restored" in lines
