from __future__ import annotations

import errno
import fcntl
import os
import pty
import re
import select
import shlex
import shutil
import subprocess
import termios
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "shell/oh-my-zsh/plugins/codex-profiles/codex-profiles.plugin.zsh"
ZSH_PATH = os.environ.get("TEST_ZSH") or shutil.which("zsh")

if ZSH_PATH is None:
    pytest.skip("zsh is required", allow_module_level=True)
assert PLUGIN_PATH.is_file(), f"Missing codex-profiles plugin: {PLUGIN_PATH}"


def _shell_quote(value: Path | str) -> str:
    return shlex.quote(str(value))


def _normalise_stty_snapshot(path: Path) -> tuple[str, ...]:
    snapshot = path.read_text(encoding="utf-8").strip()
    fields: dict[str, str] = {}
    for field in snapshot.split(":"):
        if "=" not in field:
            continue
        key, value = field.split("=", 1)
        fields[key] = value
    pendin = getattr(termios, "PENDIN", 0)
    if fields:
        # Darwin's named gfmt1 output can leave PENDIN set after bytes were
        # typed into a raw tty even when the picker restored every mode it
        # changed. Ignore that kernel bookkeeping bit only.
        if "lflag" in fields and pendin:
            fields["lflag"] = f"{int(fields['lflag'], 16) & ~pendin:x}"
        return tuple(f"{key}={fields[key]}" for key in sorted(fields))

    # GNU stty uses positional hexadecimal fields (iflag:oflag:cflag:lflag:...).
    # Keep this path meaningful on alternate zsh hosts instead of treating an
    # unparsed snapshot as an empty dictionary.
    positional = snapshot.split(":")
    if len(positional) >= 4 and pendin:
        positional[3] = f"{int(positional[3], 16) & ~pendin:x}"
    return tuple(positional)


@dataclass
class ProfileEnvironment:
    root: Path
    home: Path
    codex_home: Path
    log: Path
    child_home_log: Path
    env: dict[str, str]

    def profile(self, name: str, directory: Path | None = None) -> Path:
        target = (directory or self.codex_home) / f"{name}.config.toml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# test profile\n", encoding="utf-8")
        return target

    def argv(self) -> list[str]:
        return self.log.read_bytes().decode().split("\0")[:-1]

    def child_home(self) -> str:
        return self.child_home_log.read_text(encoding="utf-8")

    def run(
        self,
        body: str,
        *,
        before: str = "",
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = f"{before}\nsource {_shell_quote(PLUGIN_PATH)}\n{body}"
        return subprocess.run(
            [ZSH_PATH, "-f", "-c", command],
            cwd=cwd or self.root,
            env=env or self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def run_terminal(
        self,
        body: str,
        responses: bytes,
        *,
        env: dict[str, str] | None = None,
        ready_marker: bytes = b"pro",
        interactive: bool = False,
        response_stages: tuple[bytes, ...] | None = None,
        stage_checks: tuple[Callable[[], None], ...] = (),
        stage_pause: float = 0.1,
    ) -> tuple[int, str]:
        response_stages = response_stages or (responses,)
        if len(stage_checks) > max(0, len(response_stages) - 1):
            raise ValueError("stage_checks can only inspect non-final response stages")
        command = f"source {_shell_quote(PLUGIN_PATH)}\n{body}"
        shell_args = [ZSH_PATH, "-f", "-c", command]
        if interactive:
            # A fixture-owned rc file exercises the actual ZLE Tab binding and
            # _describe implementation, without loading the user's shell setup.
            (self.home / ".zshrc").write_text(
                "autoload -Uz compinit\ncompinit -D -i\n"
                + command
                + "\nPROMPT='CODEX_TEST_READY> '\nRPROMPT=''\n",
                encoding="utf-8",
            )
            shell_args = [ZSH_PATH, "-d", "-i"]
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            shell_args,
            cwd=self.root,
            env=env or self.env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0),
        )
        os.close(slave_fd)
        output = bytearray()
        sent = False
        stage_index = 0
        next_stage_deadline: float | None = None
        timed_out = True
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if select.select([master_fd], [], [], 0.05)[0]:
                    try:
                        chunk = os.read(master_fd, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not chunk:
                        break
                    output.extend(chunk)
                    # The picker prints the profile name before reading. Wait
                    # for that output so Ctrl-C and EOF reach the picker rather
                    # than the shell's command reader.
                    if not sent and ready_marker in output:
                        os.write(master_fd, response_stages[stage_index])
                        stage_index += 1
                        sent = True
                        if stage_index < len(response_stages):
                            next_stage_deadline = time.monotonic() + stage_pause
                if (
                    sent
                    and next_stage_deadline is not None
                    and stage_index < len(response_stages)
                    and time.monotonic() >= next_stage_deadline
                ):
                    stage_checks[stage_index - 1]()
                    os.write(master_fd, response_stages[stage_index])
                    stage_index += 1
                    if stage_index < len(response_stages):
                        next_stage_deadline = time.monotonic() + stage_pause
                    else:
                        next_stage_deadline = None
                if process.poll() is not None:
                    timed_out = False
                    break
            if process.poll() is None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    timed_out = False
            else:
                timed_out = False
            if timed_out:
                process.kill()
            process.wait(timeout=5)
            if timed_out:
                raise AssertionError(
                    "PTY command timed out:\n" + output.decode(errors="replace")
                )
            return process.returncode, output.decode(errors="replace")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(master_fd)


@pytest.fixture
def profile_env(tmp_path: Path) -> ProfileEnvironment:
    home = tmp_path / "user home"
    home.mkdir()
    codex_home = tmp_path / "custom [profiles] home"
    codex_home.mkdir()
    bin_dir = tmp_path / "bin with spaces"
    bin_dir.mkdir()
    log = tmp_path / "argv.log"
    child_home_log = tmp_path / "child-home.log"
    fake = bin_dir / "codex"
    fake.write_text(
        "#!/usr/bin/env zsh\n"
        "printf '%s' \"$CODEX_HOME\" > \"$CODEX_TEST_HOME_LOG\"\n"
        "printf '%s\\0' \"$@\" > \"$CODEX_TEST_LOG\"\n"
        "exit \"${CODEX_TEST_EXIT:-0}\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "ZDOTDIR": str(home),
        "CODEX_HOME": str(codex_home),
        "CODEX_TEST_LOG": str(log),
        "CODEX_TEST_HOME_LOG": str(child_home_log),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "TERM": "xterm-256color",
    }
    env.pop("CODEX_PROFILES_BIN", None)
    env.pop("CODEX_PROFILES_FLAGS", None)
    return ProfileEnvironment(tmp_path, home, codex_home, log, child_home_log, env)


@pytest.mark.parametrize("command", ("codex-profiles", "cxl", "cx", "cxr", "cxlast"))
@pytest.mark.parametrize("help_arg", ("help", "-h", "--help"))
def test_help_is_standalone_for_all_launchers(
    profile_env: ProfileEnvironment, command: str, help_arg: str
):
    env = profile_env.env | {"CODEX_PROFILES_BIN": "missing-codex-for-help"}
    result = profile_env.run(f"{command} {help_arg}", env=env)

    assert result.returncode == 0, result.stderr
    assert "cx" in result.stdout
    assert result.stderr == ""
    assert not profile_env.log.exists()


def test_listing_filters_names_and_refreshes_immediately(profile_env: ProfileEnvironment):
    for name in (
        "-leading",
        "alpha",
        "UPPER_123",
        "dash-name",
        "under_score",
        "zeta",
    ):
        profile_env.profile(name)
    for invalid in ("bad space", "bad.dot", "$(touch PWNED)", "bad\nline"):
        profile_env.profile(invalid)
    (profile_env.codex_home / "config.toml").write_text("# base\n", encoding="utf-8")
    (profile_env.codex_home / "directory.config.toml").mkdir()
    (profile_env.codex_home / "broken.config.toml").symlink_to("missing")
    (profile_env.codex_home / "linked.config.toml").symlink_to("alpha.config.toml")

    result = profile_env.run(
        'cxl; print -r -- "# next"; : > "$CODEX_HOME/new.config.toml"; codex-profiles'
    )

    assert result.returncode == 0, result.stderr
    first, second = result.stdout.split("# next\n")
    assert set(first.splitlines()) == {
        "alpha",
        "UPPER_123",
        "dash-name",
        "under_score",
        "zeta",
        "linked",
        "-leading",
    }
    assert set(second.splitlines()) == {
        "alpha",
        "UPPER_123",
        "dash-name",
        "under_score",
        "zeta",
        "linked",
        "-leading",
        "new",
    }
    assert not (profile_env.root / "PWNED").exists()


@pytest.mark.parametrize("home_kind", ("unset", "empty", "custom", "relative", "symlink"))
def test_home_fallback_custom_relative_and_symlink(
    profile_env: ProfileEnvironment, home_kind: str
):
    relative_home = profile_env.root / "relative profiles"
    relative_home.mkdir()
    profile_dir = relative_home if home_kind == "relative" else None
    profile_env.profile("selected", profile_dir)
    env = profile_env.env.copy()
    if home_kind == "unset":
        env.pop("CODEX_HOME")
        profile_dir = profile_env.home / ".codex"
        profile_dir.mkdir()
        profile_env.profile("selected", profile_dir)
    elif home_kind == "empty":
        env["CODEX_HOME"] = ""
        profile_dir = profile_env.home / ".codex"
        profile_dir.mkdir()
        profile_env.profile("selected", profile_dir)
    elif home_kind == "relative":
        env["CODEX_HOME"] = "relative profiles"
    elif home_kind == "symlink":
        link = profile_env.root / "linked profiles"
        link.symlink_to(profile_env.codex_home, target_is_directory=True)
        env["CODEX_HOME"] = str(link)
    else:
        env["CODEX_HOME"] = str(profile_env.codex_home)

    result = profile_env.run("cxl", env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "selected\n"


def test_relative_home_is_normalized_for_child_without_mutating_caller(
    profile_env: ProfileEnvironment,
):
    relative_home = profile_env.root / "relative profiles"
    relative_home.mkdir()
    profile_env.profile("selected", relative_home)
    env = profile_env.env | {"CODEX_HOME": "relative profiles"}

    result = profile_env.run(
        'caller_home="$CODEX_HOME"; cx selected; print -r -- "$CODEX_HOME:$caller_home"',
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "relative profiles:relative profiles\n"
    assert profile_env.child_home() == str(relative_home.resolve())


@pytest.mark.parametrize("bad_home", ("missing", "file"))
def test_invalid_home_does_not_launch(profile_env: ProfileEnvironment, bad_home: str):
    if bad_home == "missing":
        home = profile_env.root / "missing profiles"
    else:
        home = profile_env.root / "not-a-directory"
        home.write_text("x", encoding="utf-8")
    profile_env.profile("fallback", profile_env.home / ".codex")
    env = profile_env.env | {"CODEX_HOME": str(home)}

    result = profile_env.run("cx", env=env)

    assert result.returncode != 0
    assert result.stderr
    assert not profile_env.log.exists()


@pytest.mark.parametrize(
    ("command", "prefix"),
    (
        ("cx", ["--yolo", "--search", "-p", "pro"]),
        ("cxr", ["resume", "--yolo", "--search", "-p", "pro"]),
        ("cxlast", ["resume", "--yolo", "--search", "-p", "pro", "--last"]),
    ),
)
def test_launchers_preserve_exact_argv(
    profile_env: ProfileEnvironment,
    command: str,
    prefix: list[str],
):
    profile_env.profile("pro")
    result = profile_env.run(
        f'''{command} pro "review a file" "" '$(touch PWNED)' "*.py" --model example-model'''
    )

    assert result.returncode == 0, result.stderr
    assert profile_env.argv() == prefix + [
        "review a file",
        "",
        "$(touch PWNED)",
        "*.py",
        "--model",
        "example-model",
    ]
    assert not (profile_env.root / "PWNED").exists()


def test_child_exit_status_is_preserved(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    result = profile_env.run(
        "cx pro", env=profile_env.env | {"CODEX_TEST_EXIT": "37"}
    )

    assert result.returncode == 37, result.stderr
    assert profile_env.argv() == ["--yolo", "--search", "-p", "pro"]


@pytest.mark.parametrize(
    ("flags_source", "expected"),
    (
        ("CODEX_PROFILES_FLAGS=()", []),
        (
            "CODEX_PROFILES_FLAGS=(--search -c 'model=example model')",
            ["--search", "-c", "model=example model"],
        ),
    ),
)
def test_flags_empty_or_custom_survive_reload(
    profile_env: ProfileEnvironment, flags_source: str, expected: list[str]
):
    profile_env.profile("pro")
    result = profile_env.run(
        f"source {_shell_quote(PLUGIN_PATH)}; cx pro",
        before=f"typeset -a CODEX_PROFILES_FLAGS; {flags_source}",
    )

    assert result.returncode == 0, result.stderr
    assert profile_env.argv() == expected + ["-p", "pro"]


def test_executable_override_supports_a_path_with_spaces(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    override = profile_env.root / "override codex"
    override.write_text(
        "#!/usr/bin/env zsh\n"
        "printf '%s\\0' \"$@\" > \"$CODEX_TEST_LOG\"\n",
        encoding="utf-8",
    )
    override.chmod(0o755)
    env = profile_env.env | {"CODEX_PROFILES_BIN": str(override)}

    result = profile_env.run("cx pro", env=env)

    assert result.returncode == 0, result.stderr
    assert profile_env.argv() == ["--yolo", "--search", "-p", "pro"]


@pytest.mark.parametrize("body", ("cx", "cxr --last", "cxlast"))
def test_picker_without_tty_and_missing_binary_do_not_launch(
    profile_env: ProfileEnvironment, body: str
):
    profile_env.profile("pro")
    env = profile_env.env | {"CODEX_PROFILES_BIN": "missing-codex-for-picker"}

    result = profile_env.run(body, env=env)

    assert result.returncode != 0
    assert not profile_env.log.exists()


def test_missing_binary_for_named_profile_does_not_launch(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    env = profile_env.env | {"CODEX_PROFILES_BIN": "missing-codex-for-named"}

    result = profile_env.run("cx pro", env=env)

    assert result.returncode != 0
    assert result.stderr
    assert not profile_env.log.exists()


@pytest.mark.parametrize("selector", ("-p help", "--profile help", "--profile=help"))
def test_explicit_selector_can_launch_reserved_help_profile(
    profile_env: ProfileEnvironment, selector: str
):
    profile_env.profile("help")
    result = profile_env.run(f"cxr {selector} --last --all")

    assert result.returncode == 0, result.stderr
    assert profile_env.argv() == [
        "resume", "--yolo", "--search", "-p", "help", "--last", "--all"
    ]


@pytest.mark.parametrize("selector", ("-p", "--profile", "--profile="))
def test_missing_explicit_profile_is_a_usage_error(
    profile_env: ProfileEnvironment, selector: str
):
    profile_env.profile("pro")
    result = profile_env.run(f"cx {selector}")

    assert result.returncode == 2, result.stderr
    assert "profile" in result.stderr
    assert not profile_env.log.exists()


def test_executable_directory_is_rejected(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    result = profile_env.run(
        "cx pro", env=profile_env.env | {"CODEX_PROFILES_BIN": str(profile_env.root)}
    )

    assert result.returncode != 0
    assert "executable not found" in result.stderr
    assert not profile_env.log.exists()


def test_scalar_flags_are_rejected_with_array_guidance(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    result = profile_env.run("cx pro", before="CODEX_PROFILES_FLAGS='--search --yolo'")

    assert result.returncode == 2
    assert "Zsh array" in result.stderr
    assert not profile_env.log.exists()


def test_listing_preserves_shell_scratch_variables(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    result = profile_env.run(
        'cxl >/dev/null; [[ "$REPLY" = reply-sentinel && "$MATCH" = match-sentinel ]]',
        before="REPLY=reply-sentinel; MATCH=match-sentinel",
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("candidate", ("missing", "../pro", "pro*", "pro.config.toml"))
def test_unknown_names_fail_without_launch_or_side_effects(
    profile_env: ProfileEnvironment, candidate: str
):
    profile_env.profile("pro")

    result = profile_env.run(f"cx {_shell_quote(candidate)}")

    assert result.returncode != 0
    assert not profile_env.log.exists()
    assert not (profile_env.root / "PWNED").exists()


def test_caller_options_and_ps3_are_preserved(profile_env: ProfileEnvironment):
    profile_env.profile("pro")
    result = profile_env.run(
        """
cx pro "two words"
[[ -o ksharrays && -o shwordsplit && -o globsubst ]] || exit 90
[[ "$PS3" = sentinel ]] || exit 91
""",
        before="setopt KSH_ARRAYS SH_WORD_SPLIT GLOB_SUBST; PS3=sentinel",
    )

    assert result.returncode == 0, result.stderr
    assert profile_env.argv() == ["--yolo", "--search", "-p", "pro", "two words"]


@pytest.mark.parametrize("response", (b"q", b"Q", b"\x1b", b"\n", b"\x04"))
def test_picker_cancel_q_escape_enter_and_eof(
    profile_env: ProfileEnvironment, response: bytes
):
    profile_env.profile("pro")
    stty_before = profile_env.root / "stty-before"
    stty_after = profile_env.root / "stty-after"
    env = profile_env.env | {
        "CODEX_STTY_BEFORE": str(stty_before),
        "CODEX_STTY_AFTER": str(stty_after),
    }
    body = r'''
command -p stty -g > "$CODEX_STTY_BEFORE"
cx
picker_status=$?
command -p stty -g > "$CODEX_STTY_AFTER"
print -r -- "PICKER_STATUS=$picker_status"
print -r -- AFTER_MARKER
'''
    code, output = profile_env.run_terminal(body, response, env=env)

    assert code == 0, output
    assert "PICKER_STATUS=1" in output
    assert "AFTER_MARKER" in output
    assert _normalise_stty_snapshot(stty_before) == _normalise_stty_snapshot(
        stty_after
    )
    assert not profile_env.log.exists()


@pytest.mark.parametrize(
    ("command", "prefix", "suffix"),
    (
        ("cx", [], []),
        ("cxr", ["resume"], []),
        ("cxlast", ["resume"], ["--last"]),
    ),
)
def test_picker_single_key_launches_without_enter(
    profile_env: ProfileEnvironment,
    command: str,
    prefix: list[str],
    suffix: list[str],
):
    profile_env.profile("pro")
    code, output = profile_env.run_terminal(command, b"1")

    assert code == 0, output
    assert profile_env.argv() == prefix + ["--yolo", "--search", "-p", "pro"] + suffix


@pytest.mark.parametrize(
    ("profile_count", "selection", "target_index"),
    (
        (1, "1", -1),
        (9, "9", -1),
        (10, "10", -1),
        (12, "12", -1),
        (100, "100", -1),
        (10, "01", 0),
        (100, "001", 0),
    ),
)
def test_picker_uses_fixed_width_numbering_for_menu_size(
    profile_env: ProfileEnvironment,
    profile_count: int,
    selection: str,
    target_index: int,
):
    names = [f"profile-{index:03d}" for index in range(1, profile_count + 1)]
    for name in names:
        profile_env.profile(name)

    code, output = profile_env.run_terminal(
        "cx",
        selection.encode(),
        ready_marker=b"Select a Codex profile:",
    )

    assert code == 0, output
    assert profile_env.argv() == [
        "--yolo",
        "--search",
        "-p",
        names[target_index],
    ]
    width = len(str(profile_count))
    assert re.findall(r"(?m)^(\d+)\) ", output) == [
        f"{index:0{width}d}" for index in range(1, profile_count + 1)
    ]


def test_picker_waits_for_complete_fixed_width_code(profile_env: ProfileEnvironment):
    names = [f"profile-{index:02d}" for index in range(1, 11)]
    for name in names:
        profile_env.profile(name)

    def assert_prefix_is_pending() -> None:
        assert not profile_env.log.exists()

    code, output = profile_env.run_terminal(
        "cx",
        b"",
        ready_marker=b"Select a Codex profile:",
        response_stages=(b"1", b"0"),
        stage_checks=(assert_prefix_is_pending,),
    )

    assert code == 0, output
    assert profile_env.argv() == ["--yolo", "--search", "-p", names[-1]]


def test_picker_invalid_input_resets_and_retries_without_enter(
    profile_env: ProfileEnvironment,
):
    profile_env.profile("pro")
    code, output = profile_env.run_terminal("cxr --last", b"x1")

    assert code == 0, output
    assert profile_env.argv() == [
        "resume",
        "--yolo",
        "--search",
        "-p",
        "pro",
        "--last",
    ]


@pytest.mark.parametrize("invalid_code", ("00", "99"))
def test_picker_numeric_invalid_code_resets_and_retries(
    profile_env: ProfileEnvironment, invalid_code: str
):
    names = [f"profile-{index:02d}" for index in range(1, 11)]
    for name in names:
        profile_env.profile(name)

    code, output = profile_env.run_terminal(
        "cx",
        (invalid_code + "01").encode(),
        ready_marker=b"Select a Codex profile:",
    )

    assert code == 0, output
    assert profile_env.argv() == ["--yolo", "--search", "-p", names[0]]


def test_picker_backspace_removes_buffered_digit(profile_env: ProfileEnvironment):
    names = [f"profile-{index:02d}" for index in range(1, 11)]
    for name in names:
        profile_env.profile(name)

    code, output = profile_env.run_terminal(
        "cx",
        b"1\x7f10",
        ready_marker=b"Select a Codex profile:",
    )

    assert code == 0, output
    assert profile_env.argv() == ["--yolo", "--search", "-p", names[-1]]


def test_picker_ctrl_c_restores_tty_preserves_caller_trap_and_shell(
    profile_env: ProfileEnvironment,
):
    names = [f"profile-{index:02d}" for index in range(1, 11)]
    for name in names:
        profile_env.profile(name)
    stty_before = profile_env.root / "stty-before"
    stty_after = profile_env.root / "stty-after"
    int_trap_log = profile_env.root / "caller-int.log"
    env = profile_env.env | {
        "CODEX_STTY_BEFORE": str(stty_before),
        "CODEX_STTY_AFTER": str(stty_after),
        "CODEX_INT_TRAP_LOG": str(int_trap_log),
    }
    body = r'''
command -p stty -g > "$CODEX_STTY_BEFORE"
trap 'print -r -- caller-int > "$CODEX_INT_TRAP_LOG"' INT
cx
picker_status=$?
[[ ! -e "$CODEX_INT_TRAP_LOG" ]] || exit 90
command -p stty -g > "$CODEX_STTY_AFTER"
print -r -- "PICKER_STATUS=$picker_status"
kill -INT $$
[[ -e "$CODEX_INT_TRAP_LOG" ]] || exit 91
print -r -- AFTER_MARKER
'''

    def assert_prefix_is_pending() -> None:
        assert not profile_env.log.exists()

    code, output = profile_env.run_terminal(
        body,
        b"",
        env=env,
        ready_marker=b"Select a Codex profile:",
        response_stages=(b"1", b"\x03"),
        stage_checks=(assert_prefix_is_pending,),
    )

    assert code == 0, output
    assert "PICKER_STATUS=130" in output
    assert "AFTER_MARKER" in output
    assert _normalise_stty_snapshot(stty_before) == _normalise_stty_snapshot(
        stty_after
    )
    assert int_trap_log.read_text(encoding="utf-8") == "caller-int\n"
    assert not profile_env.log.exists()


def test_picker_external_sigint_targets_picker_process_and_restores_tty(
    profile_env: ProfileEnvironment,
):
    profile_env.profile("pro")
    stty_before = profile_env.root / "stty-before"
    stty_after = profile_env.root / "stty-after"
    env = profile_env.env | {
        "CODEX_STTY_BEFORE": str(stty_before),
        "CODEX_STTY_AFTER": str(stty_after),
    }
    body = r'''
command -p stty -g > "$CODEX_STTY_BEFORE"
zmodload zsh/system
function read() {
  builtin kill -INT "$sysparams[pid]"
  builtin read "$@"
}
cx
picker_status=$?
command -p stty -g > "$CODEX_STTY_AFTER"
print -r -- "PICKER_STATUS=$picker_status"
print -r -- AFTER_MARKER
'''

    code, output = profile_env.run_terminal(
        body,
        b"",
        env=env,
    )

    assert code == 0, output
    assert "PICKER_STATUS=130" in output
    assert "AFTER_MARKER" in output
    assert _normalise_stty_snapshot(stty_before) == _normalise_stty_snapshot(
        stty_after
    )
    assert not profile_env.log.exists()


def test_picker_restore_failure_prevents_launch(
    profile_env: ProfileEnvironment,
):
    profile_env.profile("pro")
    stty_before = profile_env.root / "stty-before"
    stty_after = profile_env.root / "stty-after"
    env = profile_env.env | {
        "CODEX_STTY_BEFORE": str(stty_before),
        "CODEX_STTY_AFTER": str(stty_after),
    }
    body = r'''
function read() {
  builtin read "$@"
  local read_result=$?
  exec 0<&-
  return $read_result
}
CODEX_TEST_SAVED_TERMINAL=$(command -p stty -g)
print -r -- "$CODEX_TEST_SAVED_TERMINAL" > "$CODEX_STTY_BEFORE"
cx
picker_status=$?
# The fault deliberately removes the picker's restoration descriptor. Recover
# this fixture terminal through the parent's still-open stdin after checking
# that the failed restore prevents the launcher from proceeding.
command -p stty "$CODEX_TEST_SAVED_TERMINAL" || exit 90
command -p stty -g > "$CODEX_STTY_AFTER"
print -r -- "PICKER_STATUS=$picker_status"
print -r -- AFTER_MARKER
'''

    code, output = profile_env.run_terminal(body, b"1", env=env)

    assert code == 0, output
    assert "PICKER_STATUS=1" in output
    assert "could not restore terminal settings." in output
    assert "AFTER_MARKER" in output
    assert _normalise_stty_snapshot(stty_before) == _normalise_stty_snapshot(
        stty_after
    )
    assert not profile_env.log.exists()


def test_leading_hyphen_profile_uses_native_equals_form(profile_env: ProfileEnvironment):
    profile_env.profile("-leading")
    code, output = profile_env.run_terminal(
        "cx --model example", b"1\n", ready_marker=b"-leading"
    )

    assert code == 0, output
    assert profile_env.argv() == [
        "--yolo",
        "--search",
        "--profile=-leading",
        "--model",
        "example",
    ]


def test_completion_registration_and_dynamic_candidates(profile_env: ProfileEnvironment):
    profile_env.profile("alpha")
    profile_env.profile("beta")
    completion_log = profile_env.root / "completion.log"
    before = f"""
autoload -Uz compinit
compinit -D -i
_codex() {{ print -r -- codex-sentinel; }}
    _describe() {{
        local -a describe_args=("$@")
        local candidate_array="${{describe_args[-1]}}"
        printf '%s\\0' _describe "$@" >> {_shell_quote(completion_log)}
        printf '%s\\0' "${{(@P)candidate_array}}" >> {_shell_quote(completion_log)}
    }}
compadd() {{ printf '%s\\0' compadd "$@" >> {_shell_quote(completion_log)}; }}
"""
    body = f"""
print -r -- "${{_comps[cx]}}|${{_comps[cxr]}}|${{_comps[cxlast]}}"
[[ -n "${{_comps[cx]}}" && -n "${{_comps[cxr]}}" && -n "${{_comps[cxlast]}}" ]] || exit 80
[[ "${{_comps[cx]}}" = "${{_comps[cxr]}}" && "${{_comps[cxr]}}" = "${{_comps[cxlast]}}" ]] || exit 81
for command in cx cxr cxlast; do
    words=($command '')
    CURRENT=2
    PREFIX=''
    IPREFIX=''
    SUFFIX=''
    function_name="${{_comps[$command]}}"
    "$function_name"
done
: > "$CODEX_HOME/gamma.config.toml"
words=(cx '')
CURRENT=2
function_name="${{_comps[cx]}}"
"$function_name"
_codex
"""
    result = profile_env.run(body, before=before)

    assert result.returncode == 0, result.stderr
    registrations, sentinel = result.stdout.splitlines()
    assert registrations.count("|") == 2
    assert sentinel == "codex-sentinel"
    completion_args = completion_log.read_bytes().decode().split("\0")[:-1]
    assert "_describe" in completion_args or "compadd" in completion_args
    assert "alpha" in completion_args
    assert "beta" in completion_args
    assert "gamma" in completion_args


@pytest.mark.parametrize("command", ("cx", "cxr", "cxlast"))
def test_real_tab_keystroke_completes_a_profile(
    profile_env: ProfileEnvironment, command: str
):
    profile_env.profile("pro-ultra")
    profile_env.profile("pro-ultra-sol")
    code, output = profile_env.run_terminal(
        "",
        f"{command} pro-ultra-s\t\nexit\n".encode(),
        ready_marker=b"CODEX_TEST_READY> ",
        interactive=True,
    )

    assert code == 0, output
    assert profile_env.log.exists(), output
    expected = ["--yolo", "--search", "-p", "pro-ultra-sol"]
    if command != "cx":
        expected.insert(0, "resume")
    if command == "cxlast":
        expected.append("--last")
    assert profile_env.argv() == expected
