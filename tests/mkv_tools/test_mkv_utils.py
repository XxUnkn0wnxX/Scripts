from __future__ import annotations

from pathlib import Path

import pytest

from _mkv_helpers import (
    _command_argv,
    _command_invocations,
    _read_command_log,
    _set_fake_fzf_responses,
    run_mkv_utils_script,
)


def _run_mkv_utils(
    env: dict[str, Path],
    *args: str,
    fzf_responses: list[list[str]] | None = None,
    input_data: str = "",
    extra_env: dict[str, str] | None = None,
):
    if fzf_responses is not None:
        _set_fake_fzf_responses(env, fzf_responses)
    return run_mkv_utils_script(
        env,
        *args,
        input_data=input_data,
        extra_env=extra_env,
    )


def _mkv_file(env: dict[str, Path], name: str) -> Path:
    path = env["workdir"] / name
    path.write_text("payload", encoding="utf-8")
    return path


def test_mkv_utils_help_shows_menu(env: dict[str, Path]):
    result = _run_mkv_utils(env, "--help")

    assert result.returncode == 0
    assert "Usage: mkv_utils.zsh" in result.stdout
    assert "1) Set flag-forced for tracks" in result.stdout
    assert "9) Extract Tracks for multi-MK files" in result.stdout


def test_mkv_utils_invalid_argument_rejects(env: dict[str, Path]):
    result = _run_mkv_utils(env, "--bad-choice")

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Usage: mkv_utils.zsh" in combined


def test_mkv_utils_nonexistent_working_dir_guard(env: dict[str, Path]):
    missing = env["workdir"] / "missing-dir"
    result = _run_mkv_utils(env, str(missing))
    assert result.returncode == 1
    assert f"Error: Working directory not found: {missing}" in result.stderr


def test_mkv_utils_no_mkv_files_displays_guard(env: dict[str, Path]):
    (env["workdir"] / "notes.txt").write_text("plain", encoding="utf-8")
    result = _run_mkv_utils(env)
    assert result.returncode == 1
    assert "Please check if there are Matroska files" in result.stdout


def test_mkv_utils_option1_forced_flag_uses_one_based_track_selector(env: dict[str, Path]):
    mkv = _mkv_file(env, "forced.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="1\n\n0\n\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"track:1" in calls[0]
    assert f"{mkv.name} --edit track:1 --set flag-forced=0" in calls[0]
    assert f"Edited File: {mkv.name}" in result.stdout


def test_mkv_utils_option2_default_flag_defaults_to_one(env: dict[str, Path]):
    mkv = _mkv_file(env, "default.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="2\n\n0\n\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --edit track:1 --set flag-default=1" in calls[0]


def test_mkv_utils_option3_language_updates_track_language(env: dict[str, Path]):
    mkv = _mkv_file(env, "language.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="3\n\n0\neng\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --edit track:1 --set language=eng" in calls[0]


def test_mkv_utils_option4_name_updates_track_name(env: dict[str, Path]):
    mkv = _mkv_file(env, "rename.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="4\n\n0\nDialogue\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --edit track:1 --set name=Dialogue" in calls[0]


def test_mkv_utils_option4_handles_spaces_in_file_and_track_name(env: dict[str, Path]):
    mkv = _mkv_file(env, "Episode One.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="4\n\n0\nEnglish Stereo\n",
    )

    calls = _command_argv(env, "mkvpropedit")
    assert result.returncode == 0
    assert len(calls) == 1
    assert mkv.name in calls[0]
    assert "name=English Stereo" in calls[0]
    assert "English" not in calls[0]
    assert "Stereo" not in calls[0]


def test_mkv_utils_option5_title_empty_input_deletes_title(env: dict[str, Path]):
    mkv = _mkv_file(env, "title.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="5\n\n\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvpropedit")
    assert result.returncode == 0
    assert f"{mkv.name} --delete title" in calls[0]


def test_mkv_utils_option1_multi_file_partial_failure_summary(env: dict[str, Path]):
    target_a = _mkv_file(env, "multi_fail_a.mkv")
    target_b = _mkv_file(env, "multi_fail_b.mkv")

    result = _run_mkv_utils(
        env,
        fzf_responses=[[target_a.name, target_b.name]],
        input_data="1\nY\n0\n0\n0\n",
        extra_env={"TEST_FAKE_MKVPROPEDIT_FAIL_CALL": "2"},
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "Total Files To Edit: 2" in output
    assert "Total Files Edited: 1" in output
    assert "Failed Files: 01" in output
    assert "multi_fail_b.mkv" in output


def test_mkv_utils_option6_extracts_all_attachments(env: dict[str, Path]):
    mkv = _mkv_file(env, "with_attachments2.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="6\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvextract")
    assert result.returncode == 0
    assert f"attachments {mkv}" in calls[0]
    assert "1" in calls[0]
    assert "2" in calls[0]
    assert (env["workdir"] / "Attachments").exists()
    assert (env["workdir"] / "Attachments" / "attachment_1.bin").exists()
    assert (env["workdir"] / "Attachments" / "attachment_2.bin").exists()


def test_mkv_utils_option7_video_removal_converts_to_mka_and_keeps_other_tracks(
    env: dict[str, Path],
):
    mkv = _mkv_file(env, "remove_video.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    remux_calls = [call for call in calls if " -o " in f" {call} "]
    assert len(remux_calls) == 1
    assert "--no-video" in remux_calls[0]
    assert "--audio-tracks 1,2" in remux_calls[0]
    assert "--subtitle-tracks 3" in remux_calls[0]
    assert not mkv.exists()
    assert (env["workdir"] / "remove_video.mka").exists()


def test_mkv_utils_option7_failure_cleans_temporary_file(env: dict[str, Path]):
    mkv = _mkv_file(env, "remove_fail.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
        extra_env={"TEST_FAKE_MKVMERGE_FAIL_CALL": "1"},
    )

    assert result.returncode == 0
    assert "Error on" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert not (env["workdir"] / f"{mkv.stem}_temp.mka").exists()
    assert not (env["workdir"] / f"{mkv.stem}.mka").exists()
    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 1


@pytest.mark.parametrize(
    "extra_env",
    [
        {"TEST_FAKE_MKVMERGE_JSON_FAIL_CALL": "1"},
        {"TEST_FAKE_JQ_FAIL_CALL": "1"},
        {"TEST_FAKE_JQ_FAIL_CALL": "2"},
    ],
    ids=("mkvmerge-json", "jq-validation", "jq-display"),
)
def test_mkv_utils_option7_inspection_failure_skips_remux(
    env: dict[str, Path], extra_env: dict[str, str]
):
    mkv = _mkv_file(env, "remove_fail_inspect.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
        extra_env=extra_env,
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 1
    assert "track inspection failed; file unchanged" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


@pytest.mark.parametrize(
    "row_mode",
    ("empty", "non-numeric", "duplicate", "unsupported"),
)
def test_mkv_utils_option7_invalid_discovery_rows_skip_remux(
    env: dict[str, Path], row_mode: str
):
    mkv = _mkv_file(env, "remove_invalid_rows.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0\n",
        extra_env={"TEST_FAKE_JQ_TRACK_ROW_MODE": row_mode},
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode in (0, 1)
    assert "file unchanged" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


def test_mkv_utils_option7_nonexistent_track_id_skips_remux(env: dict[str, Path]):
    mkv = _mkv_file(env, "remove_missing_id.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n99\n",
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    assert "requested Track ID not found; file unchanged" in (
        result.stdout + result.stderr
    )
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


def test_mkv_utils_option7_refuses_to_remove_every_track(env: dict[str, Path]):
    mkv = _mkv_file(env, "remove_all.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="7\n\n0-3\n",
    )

    mkvmerge_calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    assert "no tracks to keep after removal; file unchanged" in (
        result.stdout + result.stderr
    )
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert len([call for call in mkvmerge_calls if " -o " in f" {call} "]) == 0


def test_mkv_utils_option7_multi_file_uses_per_file_track_layout(env: dict[str, Path]):
    first = _mkv_file(env, "option7_default.mkv")
    second = _mkv_file(env, "option7_alt.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[first.name, second.name]],
        input_data="7\nY\n0\n",
    )

    assert result.returncode == 0
    calls = _command_invocations(_read_command_log(env), "mkvmerge")
    remux_calls = [call for call in calls if " -o " in f" {call} "]
    assert len(remux_calls) == 2

    first_call, second_call = remux_calls
    assert "--no-video" in first_call
    assert "--audio-tracks 1,2" in first_call
    assert "--subtitle-tracks 3" in first_call
    assert "--no-video" in second_call
    assert "--audio-tracks 11" in second_call
    assert "--subtitle-tracks 12" in second_call
    assert "--audio-tracks 1,2" not in second_call


def test_mkv_utils_option8_reorder_tracks_replaces_original(env: dict[str, Path]):
    mkv = _mkv_file(env, "reorder.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="8\n\n0:1,1:0\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvmerge")
    assert result.returncode == 0
    remux_calls = [call for call in calls if " -o " in f" {call} "]
    assert len(remux_calls) == 1
    assert "--track-order 0:1,1:0" in remux_calls[0]
    assert (env["workdir"] / mkv.name).exists()


def test_mkv_utils_option8_reorder_failure_cleans_temp_file(env: dict[str, Path]):
    mkv = _mkv_file(env, "reorder_fail.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="8\n\n0:1\n",
        extra_env={"TEST_FAKE_MKVMERGE_FAIL_CALL": "1"},
    )

    assert result.returncode == 0
    assert "Error on" in (result.stdout + result.stderr)
    assert mkv.read_text(encoding="utf-8") == "payload"
    assert not (env["workdir"] / "reorder_fail_temp.mkv").exists()


def test_mkv_utils_option9_extract_track_extension_from_override(env: dict[str, Path]):
    mkv = _mkv_file(env, "extract_codec.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="9\n\n1\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvextract")
    assert result.returncode == 0
    assert 'extract_codec - Track [1].opus' in calls[0]


def test_mkv_utils_option9_extract_track_extension_from_python_map(env: dict[str, Path]):
    mkv = _mkv_file(env, "extract_unknown.mkv")
    result = _run_mkv_utils(
        env,
        fzf_responses=[[mkv.name]],
        input_data="9\n\n0\n",
    )

    calls = _command_invocations(_read_command_log(env), "mkvextract")
    assert result.returncode == 0
    assert 'extract_unknown - Track [0].thd' in calls[0]
