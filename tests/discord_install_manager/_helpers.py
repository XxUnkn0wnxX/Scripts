from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

SCRIPT_SOURCE = Path(__file__).resolve().parents[2] / "shell" / "discord_install_manager.zsh"

APP_NAMES = {
    "stable": "Discord",
    "ptb": "Discord PTB",
    "canary": "Discord Canary",
}

DATA_DIRS = {
    "stable": "discord",
    "ptb": "discordptb",
    "canary": "discordcanary",
}

TEST_TOOLS = (
    "aria2c",
    "curl",
    "hdiutil",
    "ditto",
    "sleep",
    "open",
    "osascript",
    "rm",
    "cp",
    "mv",
    "cmp",
)


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | 0o111)


def _prepare_fake_commands(fake_bin: Path, *, include_aria2: bool = True) -> None:
    if include_aria2:
        _write_executable(
            fake_bin / "aria2c",
            """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
attempt_file="${state_dir}/fake_aria2c_attempts"
attempt=1
if [ -f "$attempt_file" ]; then
  parsed_attempt="$(cat "$attempt_file" 2>/dev/null || echo 0)"
  attempt=$((parsed_attempt + 1))
fi
printf '%s\n' "$attempt" > "$attempt_file"

mode="${TEST_FAKE_ARIA2_MODE:-}"
fail_attempts="${TEST_FAKE_ARIA2_FAIL_ATTEMPTS:-0}"
empty_attempts="${TEST_FAKE_ARIA2_EMPTY_ATTEMPTS:-0}"
if [ -n "$log_file" ]; then
  printf 'aria2c\tattempt=%s\targs=%s\n' "$attempt" "$*" >> "$log_file"
fi

if [ "$mode" = "absent" ]; then
  exit 1
fi

if [ "${TEST_FAKE_ARIA2_ALWAYS_FAIL:-0}" = "1" ]; then
  exit 1
fi

if [ "$attempt" -le "$fail_attempts" ]; then
  exit 1
fi

out_dir=""
out_name=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir=*)
      out_dir="${1#--dir=}"
      ;;
    --out=*)
      out_name="${1#--out=}"
      ;;
    --dir)
      shift
      out_dir="$1"
      ;;
    --out)
      shift
      out_name="$1"
      ;;
  esac
  shift || break

done

mkdir -p "${out_dir:-/tmp}"
if [ -n "$out_name" ]; then
  if [ "$attempt" -le "$empty_attempts" ]; then
    : > "${out_dir}/${out_name}"
  else
    printf 'aria2-dmg' > "${out_dir}/${out_name}"
  fi
fi
""",
        )

    _write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'curl\targs=%s\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
output=""
url=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output)
      shift
      output="$1"
      ;;
    *)
      url="$1"
      ;;
  esac
  shift || break
done

if printf '%s' "$url" | /usr/bin/grep -q '^https://discord.com/api/updates/'; then
  manifest="${TEST_FAKE_CURL_UPDATE_MANIFEST:-}"
  if [ -z "$manifest" ]; then
    manifest='{"name":"0.0.401"}'
  fi
  if [ -n "$output" ]; then
    mkdir -p "$(dirname \"$output\")"
    printf '%s\n' "$manifest" > "$output"
  else
    printf '%s\n' "$manifest"
  fi
  exit 0
fi

if [ -z "$output" ]; then
  default_code="${TEST_FAKE_CURL_DEFAULT_HEADER_CODE:-404}"
  header_code=""
  if [ -n "${TEST_FAKE_CURL_HEADER_MAP_FILE:-}" ] && [ -f "${TEST_FAKE_CURL_HEADER_MAP_FILE}" ]; then
    while IFS='|' read -r pattern code || [ -n "$pattern" ]; do
      if [ -z "$pattern" ]; then
        continue
      fi
      case "$pattern" in
        '#'*)
          continue
          ;;
      esac
      case "$url" in
        $pattern)
          header_code="$code"
          ;;
      esac
      [ -n "$header_code" ] && break
    done < "${TEST_FAKE_CURL_HEADER_MAP_FILE}"
  fi

  if [ -z "$header_code" ]; then
    header_code="$default_code"
  fi

  if [ "$header_code" = "200" ]; then
    printf 'HTTP/1.1 200 OK\r\n'
    printf "Last-Modified: ${TEST_FAKE_CURL_LAST_MODIFIED:-Mon, 01 Jan 2024 00:00:00 GMT}\r\n"
  else
    printf 'HTTP/1.1 %s Not Found\r\n' "$header_code"
  fi
  exit 0
fi

attempt_file="${state_dir}/fake_curl_download_attempts"
attempt=1
if [ -f "$attempt_file" ]; then
  parsed_attempt="$(cat "$attempt_file" 2>/dev/null || echo 0)"
  attempt=$((parsed_attempt + 1))
fi
printf '%s\n' "$attempt" > "$attempt_file"

if [ "${TEST_FAKE_CURL_ALWAYS_FAIL:-0}" = "1" ] ||
   [ "$attempt" -le "${TEST_FAKE_CURL_FAIL_ATTEMPTS:-0}" ]; then
  exit 1
fi

mkdir -p "$(dirname \"$output\")"
if [ "$attempt" -le "${TEST_FAKE_CURL_EMPTY_ATTEMPTS:-0}" ]; then
  : > "$output"
else
  printf 'dummy-curl' > "$output"
fi
""",
        )

    _write_executable(
        fake_bin / "hdiutil",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'hdiutil\targs=%s\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
mode="${TEST_FAKE_HDIUTIL_MODE:-}"
attach_fail_attempts="${TEST_FAKE_HDIUTIL_ATTACH_FAIL_ATTEMPTS:-0}"
attempt_file="${state_dir}/fake_hdiutil_attach_attempts"
attach_attempt=1
if [ "$1" = "attach" ]; then
  if [ -f "$attempt_file" ]; then
    parsed_attempt="$(cat "$attempt_file" 2>/dev/null || echo 0)"
    attach_attempt=$((parsed_attempt + 1))
  fi
  printf '%s\n' "$attach_attempt" > "$attempt_file"
fi

if [ "$1" = "attach" ]; then
  mountpoint=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -mountpoint)
        shift
        mountpoint="$1"
        ;;
    esac
    shift || break
  done

  if [ "$attach_attempt" -le "$attach_fail_attempts" ] && [ -n "$attach_fail_attempts" ]; then
    exit 1
  fi

  if [ -z "$mountpoint" ]; then
    exit 1
  fi

  if [ "$mode" = "attach-fail" ]; then
    exit 1
  fi

  app_name="Discord.app"
  executable="Discord"
  case "$mountpoint" in
    *mount-ptb*) app_name="Discord PTB.app"; executable="Discord PTB" ;;
    *mount-canary*) app_name="Discord Canary.app"; executable="Discord Canary" ;;
  esac

  if [ "$mode" != "no-app" ]; then
    app_path="$mountpoint/$app_name"
    mkdir -p "$app_path/Contents/Resources" "$app_path/Contents/MacOS"
    printf 'plist' > "$app_path/Contents/Info.plist"
    printf 'bin' > "$app_path/Contents/MacOS/$executable"
    chmod +x "$app_path/Contents/MacOS/$executable"
    : > "$app_path/Contents/Resources/app.asar"
  else
    mkdir -p "$mountpoint/not-an-app"
  fi
elif [ "$1" = "detach" ]; then
  exit 0
else
  exit 0
fi
""",
        )

    _write_executable(
        fake_bin / "ditto",
        """#!/usr/bin/env sh
set -e

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'ditto\targs=%s\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
attempt_file="${state_dir}/fake_ditto_attempts"
fail_attempts="${TEST_FAKE_DITTO_FAIL_ATTEMPTS:-0}"
attempt=1
if [ -f "$attempt_file" ]; then
  parsed_attempt="$(cat "$attempt_file" 2>/dev/null || echo 0)"
  attempt=$((parsed_attempt + 1))
fi
printf '%s\n' "$attempt" > "$attempt_file"

if [ "$attempt" -le "$fail_attempts" ]; then
  exit 1
fi

cp -R "$1/." "$2"
""",
        )

    _write_executable(
        fake_bin / "sleep",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'sleep\targs=%s\n' "$*" >> "$log_file"
fi
exit 0
""",
        )

    _write_executable(
        fake_bin / "open",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'open\targs=%s\n' "$*" >> "$log_file"
fi
exit 0
""",
        )

    _write_executable(
        fake_bin / "osascript",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'osascript\targs=%s\n' "$*" >> "$log_file"
fi
exit 0
""",
        )

    _write_executable(
        fake_bin / "rm",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'rm\targs=%s\n' "$*" >> "$log_file"
fi

fail_path="${TEST_FAKE_RM_FAIL_PATH:-}"
if [ -n "$fail_path" ]; then
  for argument in "$@"; do
    if [ "$argument" = "$fail_path" ]; then
      exit 1
    fi
  done
fi

exec /bin/rm "$@"
""",
    )

    _write_executable(
        fake_bin / "cp",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'cp\targs=%s\n' "$*" >> "$log_file"
fi

destination=""
for argument in "$@"; do
  destination="$argument"
done

case "$destination" in
  */.openasar-app-*.asar)
    if [ "${TEST_FAKE_CP_FAIL_OPENASAR:-0}" = "1" ]; then
      printf 'partial-stage' > "$destination"
      exit 1
    fi
    ;;
esac

exec /bin/cp "$@"
""",
    )

    _write_executable(
        fake_bin / "mv",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'mv\targs=%s\n' "$*" >> "$log_file"
fi

source_path=""
for argument in "$@"; do
  case "$argument" in
    -*) ;;
    *)
      source_path="$argument"
      break
      ;;
  esac
done

case "$source_path" in
  */.openasar-app-*.asar)
    if [ "${TEST_FAKE_MV_FAIL_OPENASAR:-0}" = "1" ]; then
      exit 1
    fi
    ;;
esac

exec /bin/mv "$@"
""",
    )

    _write_executable(
        fake_bin / "cmp",
        """#!/usr/bin/env sh

log_file="${TEST_COMMAND_LOG:-}"
if [ -n "$log_file" ]; then
  printf 'cmp\targs=%s\n' "$*" >> "$log_file"
fi

state_dir="${TEST_FAKE_STATE_DIR:-/tmp}"
attempt_file="${state_dir}/fake_cmp_attempts"
attempt=1
if [ -f "$attempt_file" ]; then
  parsed_attempt="$(cat "$attempt_file" 2>/dev/null || echo 0)"
  attempt=$((parsed_attempt + 1))
fi
printf '%s\n' "$attempt" > "$attempt_file"

if [ -n "${TEST_FAKE_CMP_FAIL_ATTEMPT:-}" ] &&
   [ "$attempt" -eq "${TEST_FAKE_CMP_FAIL_ATTEMPT}" ]; then
  exit 1
fi

exec /usr/bin/cmp "$@"
""",
    )


def _create_manager_environment(tmp_path: Path, *, include_aria2: bool = True):
    home = tmp_path / "home"
    applications_root = tmp_path / "Applications"
    fake_bin = tmp_path / "fake_bin"
    fake_bin_without_aria2 = tmp_path / "fake_bin_without_aria2"
    command_log = tmp_path / "commands.log"
    fake_state = tmp_path / "fake_state"

    home.mkdir()
    applications_root.mkdir()
    fake_bin.mkdir()
    fake_bin_without_aria2.mkdir()
    fake_state.mkdir()

    _prepare_fake_commands(fake_bin, include_aria2=True)
    _prepare_fake_commands(fake_bin_without_aria2, include_aria2=False)

    script_path = tmp_path / "discord_install_manager.zsh"
    script_source = SCRIPT_SOURCE.read_text(encoding="utf-8")
    applications_marker = 'DEFAULT_APPLICATIONS_ROOT="/Applications"'
    assert script_source.count(applications_marker) == 1
    script_source = script_source.replace(
        applications_marker,
        f"DEFAULT_APPLICATIONS_ROOT={shlex.quote(str(applications_root))}",
    )
    script_path.write_text(script_source, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | 0o111)

    openasar_source = tmp_path / "openasar.app.asar"
    openasar_source.write_bytes(b"openasar")

    discord_pid_tracker = tmp_path / "relaunch-processes.log"

    return {
        "script": script_path,
        "home": home,
        "applications_root": applications_root,
        "fake_bin": fake_bin,
        "fake_bin_without_aria2": fake_bin_without_aria2,
        "openasar_source": openasar_source,
        "command_log": command_log,
        "fake_state": fake_state,
        "include_aria2": include_aria2,
        "discord_pid_tracker": discord_pid_tracker,
    }


def _run_manager(
    env: dict[str, Path],
    *args: str,
    extra_env: dict[str, str] | None = None,
    path_override: Path | None = None,
    required_tools: tuple[str, ...] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    process_env["HOME"] = str(env["home"])
    tool_path = path_override or env["fake_bin"]
    process_env["PATH"] = f"{tool_path}:/usr/bin:/bin:/usr/sbin:/sbin"
    process_env["TEST_COMMAND_LOG"] = str(env["command_log"])
    process_env["TEST_FAKE_STATE_DIR"] = str(env["fake_state"])
    if "discord_pid_tracker" in env:
        process_env["TEST_FAKE_DISCORD_PID_TRACKER"] = str(env["discord_pid_tracker"])

    env["command_log"].write_text("")
    if env["fake_state"].exists():
        for path in env["fake_state"].iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    if required_tools is None:
        required_tools = TEST_TOOLS if env["include_aria2"] else tuple(tool for tool in TEST_TOOLS if tool != "aria2c")

    for tool in required_tools:
        resolved_tool = shutil.which(tool, path=process_env["PATH"])
        assert (
            resolved_tool is not None
            and Path(resolved_tool).resolve() == (tool_path / tool).resolve()
        ), (
            f"{tool} is not resolved from test PATH for execution."
            f" expected={tool_path / tool}, got={resolved_tool}"
        )

    assert Path(process_env["HOME"]) == env["home"]
    assert env["applications_root"].is_relative_to(env["script"].parent)
    if extra_env:
        process_env.update(extra_env)

    return subprocess.run(
        [str(env["script"]), *args],
        cwd=str(env["home"]),
        env=process_env,
        text=True,
        capture_output=True,
    )


def _settings_path(home: Path, channel: str) -> Path:
    return home / "Library" / "Application Support" / DATA_DIRS[channel] / "settings.json"


def _application_path(applications_root: Path, channel: str) -> Path:
    return applications_root / f"{APP_NAMES[channel]}.app"


def _dmg_path(script_path: Path, channel: str, version: str) -> Path:
    normalized = version if version.startswith("0.0.") else f"0.0.{version}"
    return script_path.parent / f"Discord-{channel}-installer ({normalized}).dmg"


def _read_settings(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_command_log(env: dict[str, Path]) -> list[str]:
    return env["command_log"].read_text(encoding="utf-8").splitlines()


def _assert_no_update_artifacts(env: dict[str, Path], channel: str = "stable") -> None:
    assert not _application_path(env["applications_root"], channel).exists()
    assert not list(env["script"].parent.glob("Discord-*-installer*.dmg*"))
    assert not list(env["script"].parent.glob("mount-*"))


def _assert_no_download_artifacts(env: dict[str, Path]) -> None:
    assert not list(env["script"].parent.glob("Discord-*-installer*.dmg*"))
    assert not list(env["script"].parent.glob("mount-*"))


def _write_fake_curl_header_map(env: dict[str, Path], entries: list[tuple[str, str]]) -> Path:
    map_path = env["script"].parent / "curl_headers.map"
    map_path.write_text("\n".join(f"{pattern}|{code}" for pattern, code in entries), encoding="utf-8")
    return map_path
