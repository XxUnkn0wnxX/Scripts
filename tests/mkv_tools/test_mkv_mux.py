from __future__ import annotations

from pathlib import Path

from _mkv_helpers import (
    _command_argv,
    _command_invocations,
    _read_command_log,
    _set_fake_fzf_responses,
    run_mkv_mux_script,
)


def _run_mkv_mux(
    env: dict[str, Path],
    *args: str,
    fzf_responses: list[list[str]] | None = None,
    input_data: str = "",
    extra_env: dict[str, str] | None = None,
):
    if fzf_responses is not None:
        _set_fake_fzf_responses(env, fzf_responses)
    return run_mkv_mux_script(
        env,
        *args,
        input_data=input_data,
        extra_env=extra_env,
    )


def _mkv_file(env: dict[str, Path], name: str) -> Path:
    path = env["workdir"] / name
    path.write_text("payload", encoding="utf-8")
    return path


def test_mkv_mux_help_shows_options(env: dict[str, Path]):
    result = _run_mkv_mux(env, "--help")

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--debug" in result.stdout
    assert "1) Remux to MKV (ffmpeg)" in result.stdout
    assert "2) Remux to MKV (mkvmerge)" in result.stdout
    assert "3) Volume Boost" in result.stdout


def test_mkv_mux_unknown_argument_rejects_and_prints_usage(env: dict[str, Path]):
    result = _run_mkv_mux(env, "--does-not-exist")

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Usage: mkv_mux.zsh" in combined
    assert "Invalid" not in combined


def test_mkv_mux_guard_for_invalid_working_directory(env: dict[str, Path]):
    missing = env["workdir"] / "missing"
    result = _run_mkv_mux(env, str(missing))

    assert result.returncode == 1
    assert f"Error: Working directory not found: {missing}" in result.stderr


def test_mkv_mux_option1_copy_mode_uses_safe_output_and_copy_args(env: dict[str, Path]):
    source = _mkv_file(env, "copy_input.mp4")
    (env["workdir"] / "copy_input_remuxed (1).mkv").write_text("existing", encoding="utf-8")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="1\nN\n",
    )

    log = _read_command_log(env)
    ffmpeg_calls = _command_invocations(log, "ffmpeg")
    ffmpeg_argv = _command_argv(env, "ffmpeg")
    assert result.returncode == 0
    assert len(ffmpeg_calls) == 1
    assert not any("-encoders" in call for call in ffmpeg_argv)
    assert "-c copy" in ffmpeg_calls[0]
    assert "-map 0:v:0" in ffmpeg_calls[0]
    assert f"{source.stem}_temp.mkv" in ffmpeg_calls[0]
    assert (env["workdir"] / f"{source.stem}_remuxed (2).mkv").exists()


def test_mkv_mux_option1_nsafe_decline_preserves_existing_output(env: dict[str, Path]):
    source = _mkv_file(env, "decline_overwrite.mp4")
    output = env["workdir"] / "decline_overwrite.mkv"
    output.write_text("keep-existing", encoding="utf-8")

    result = _run_mkv_mux(
        env,
        "--nsafe",
        fzf_responses=[[source.name]],
        input_data="1\nN\nN\n",
    )

    assert result.returncode == 0
    assert "Skipped; decline_overwrite.mkv unchanged." in result.stdout
    assert output.read_text(encoding="utf-8") == "keep-existing"
    assert not _command_invocations(_read_command_log(env), "ffmpeg")


def test_mkv_mux_option1_handles_source_filename_with_spaces(env: dict[str, Path]):
    source = _mkv_file(env, "episode one.mp4")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="1\nN\n",
    )

    ffmpeg_calls = _command_argv(env, "ffmpeg")
    assert result.returncode == 0
    assert len(ffmpeg_calls) == 1
    assert source.name in ffmpeg_calls[0]
    assert "episode" not in ffmpeg_calls[0]
    assert "one.mp4" not in ffmpeg_calls[0]
    assert (env["workdir"] / "episode one_remuxed (1).mkv").exists()


def test_mkv_mux_option1_reencode_uses_fdk_aac_encoder_when_available(env: dict[str, Path]):
    source = _mkv_file(env, "option1_reencode.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source.name]],
        input_data="1\nY\n",
        extra_env={"TEST_FAKE_FFMPEG_HAS_LIBFDK": "1"},
    )

    log = _read_command_log(env)
    ffmpeg_calls = _command_invocations(log, "ffmpeg")
    assert result.returncode == 0
    reencode_calls = [call for call in ffmpeg_calls if "-c:a libfdk_aac" in call]
    assert len(reencode_calls) == 2
    assert all(call.count(" -vbr 5 ") == 1 for call in reencode_calls)
    assert all(call.count("-afterburner 1") == 1 for call in reencode_calls)
    assert all("-profile:a aac_low" in call for call in reencode_calls)
    assert all("-q:a 0" not in call for call in reencode_calls)
    assert result.stdout.count("Debug: AAC encoder selected: libfdk_aac") == 1


def test_mkv_mux_option1_reencode_uses_aac_q_a_0_and_track_maps(env: dict[str, Path]):
    source = _mkv_file(env, "option1_reencode.mkv")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="1\nY\n",
    )

    log = _read_command_log(env)
    ffmpeg_calls = _command_invocations(log, "ffmpeg")
    assert result.returncode == 0
    reencode_calls = [call for call in ffmpeg_calls if "-c:a aac" in call]
    assert len(reencode_calls) == 2
    assert all("-q:a 0" in call for call in reencode_calls)
    assert result.stdout.count("Debug: AAC encoder selected: FFmpeg native AAC") == 0
    assert "Debug: AAC encoder selected" not in result.stdout
    assert all("-c:a libfdk_aac" not in call for call in reencode_calls)
    assert all("-profile:a aac_low" not in call for call in reencode_calls)
    assert all("-afterburner 1" not in call for call in reencode_calls)
    assert all(call.count(" -map 0:a:") == 1 for call in reencode_calls)
    merge_call = ffmpeg_calls[-1]
    assert "-c:v copy" in merge_call
    assert "-c:a copy" in merge_call
    assert "-c:s copy" in merge_call
    assert "-map 0:v:0" in merge_call
    assert "-map 1:a:0" in merge_call
    assert "-map 2:a:0" in merge_call
    assert "-disposition:a:0 default" in merge_call
    assert "-metadata:s:a:1 language=jpn" in merge_call


def test_mkv_mux_option1_reencode_cache_checks_encoder_once_per_run(env: dict[str, Path]):
    source_one = _mkv_file(env, "option1_replace_cached_one.mkv")
    source_two = _mkv_file(env, "option1_replace_cached_two.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source_one.name, source_two.name]],
        input_data="1\nY\n",
        extra_env={"TEST_FAKE_FFMPEG_HAS_LIBFDK": "1"},
    )

    ffmpeg_argv = _command_argv(env, "ffmpeg")
    assert result.returncode == 0
    assert len([call for call in ffmpeg_argv if "-encoders" in call]) == 1
    assert result.stdout.count("Debug: AAC encoder selected: libfdk_aac") == 2


def test_mkv_mux_option1_no_debug_output_for_copy_only(env: dict[str, Path]):
    source = _mkv_file(env, "option1_copy_only.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source.name]],
        input_data="1\nN\n",
    )

    assert result.returncode == 0
    assert "Debug: AAC encoder selected" not in result.stdout


def test_mkv_mux_option1_reencode_uses_native_debug_text_with_debug(env: dict[str, Path]):
    source = _mkv_file(env, "option1_reencode.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source.name]],
        input_data="1\nY\n",
    )

    ffmpeg_calls = _command_invocations(_read_command_log(env), "ffmpeg")
    reencode_calls = [call for call in ffmpeg_calls if "-c:a aac" in call]
    assert result.returncode == 0
    assert len(reencode_calls) == 2
    assert result.stdout.count("Debug: AAC encoder selected: FFmpeg native AAC") == 1
    assert "Debug: AAC encoder selected: libfdk_aac" not in result.stdout


def test_mkv_mux_option1_reencode_applies_climiter_filter_in_reencode_stage(env: dict[str, Path]):
    source = _mkv_file(env, "option1_replace_limited.mkv")

    result = _run_mkv_mux(
        env,
        "--climit",
        fzf_responses=[[source.name]],
        input_data="1\nY\nalimiter=limit=0.99:attack=20:release=20\n",
    )

    log = _read_command_log(env)
    ffmpeg_calls = _command_invocations(log, "ffmpeg")
    assert result.returncode == 0
    assert any(
        "-filter:a alimiter=limit=0.99:attack=20:release=20:level=0" in call
        for call in ffmpeg_calls
    )


def test_mkv_mux_climiter_reprompts_then_uses_default(env: dict[str, Path]):
    source = _mkv_file(env, "option1_default_limiter.mkv")

    result = _run_mkv_mux(
        env,
        "--climit",
        fzf_responses=[[source.name]],
        input_data="1\nY\ninvalid\n\n",
    )

    ffmpeg_calls = _command_invocations(_read_command_log(env), "ffmpeg")
    assert result.returncode == 0
    assert "Invalid limiter." in result.stderr
    assert any(
        "-filter:a alimiter=limit=0.99:attack=20:release=20:level=0" in call
        for call in ffmpeg_calls
    )


def test_mkv_mux_option1_reencode_failure_cleans_temp_workdir(env: dict[str, Path]):
    source = _mkv_file(env, "option1_replace_fail.mkv")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="1\nY\n",
        extra_env={"TEST_FAKE_FFMPEG_FAIL_CALL": "1"},
    )

    assert result.returncode == 0
    assert "Error processing" in (result.stdout + result.stderr)
    assert not any(entry.name.startswith("option1_replace_fail_temp") for entry in env["workdir"].iterdir())
    assert not (env["workdir"] / f"{source.stem}_remuxed (1).mkv").exists()


def test_mkv_mux_option2_runs_mkvmerge_and_safe_naming(env: dict[str, Path]):
    source = _mkv_file(env, "remux_source.mkv")
    (env["workdir"] / "remux_source_remuxed (1).mkv").write_text("existing", encoding="utf-8")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="2\n",
    )

    log = _read_command_log(env)
    mkvmerge_calls = _command_invocations(log, "mkvmerge")
    assert result.returncode == 0
    assert mkvmerge_calls
    assert f"{source.stem}_temp.mkv" in mkvmerge_calls[0]
    assert (env["workdir"] / f"{source.stem}_remuxed (2).mkv").exists()


def test_mkv_mux_option2_shows_no_debug_output(env: dict[str, Path]):
    source = _mkv_file(env, "option2_source.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source.name]],
        input_data="2\n",
    )

    assert result.returncode == 0
    assert "Debug: AAC encoder selected" not in result.stdout
    ffmpeg_argv = _command_argv(env, "ffmpeg")
    assert not any("-encoders" in call for call in ffmpeg_argv)


def test_mkv_mux_option2_skips_non_video_file(env: dict[str, Path]):
    source = _mkv_file(env, "not_video.txt")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="2\n",
    )

    assert result.returncode == 0
    assert "Warning: Skipping non-video file" in result.stdout
    assert not _command_invocations(_read_command_log(env), "mkvmerge")


def test_mkv_mux_option3_creates_boosted_files_and_safe_sorting(env: dict[str, Path]):
    source = _mkv_file(env, "boost_single.mkv")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="3\n2dB,-3dB\n",
    )

    log = _read_command_log(env)
    mkvextract_calls = _command_invocations(log, "mkvextract")
    ffmpeg_calls = _command_invocations(log, "ffmpeg")
    mkvmerge_calls = _command_invocations(log, "mkvmerge")

    assert result.returncode == 0
    assert any("tracks boost_single.mkv" in call for call in mkvextract_calls)
    assert any("-filter:a volume=2dB" in call for call in ffmpeg_calls)
    assert any("-filter:a volume=-3dB" in call for call in ffmpeg_calls)
    assert any(
        "--track-name 0:-3dB" in call and "--track-name 0:2dB" in call
        for call in mkvmerge_calls
    )
    assert (env["workdir"] / f"{source.stem}_boosted (1).mkv").exists()
    assert source.exists()
    assert not (env["workdir"] / "boost_single_original.mkv").exists()


def test_mkv_mux_option3_multi_file_multi_track_processing_keeps_codec_extension_hidden(
    env: dict[str, Path],
):
    first = _mkv_file(env, "boost_multi_one.mkv")
    second = _mkv_file(env, "boost_multi_two.mkv")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[first.name, second.name]],
        input_data="3\n1\nY\n2dB,-3dB\n",
    )

    log = _read_command_log(env)
    mkvextract_calls = _command_invocations(log, "mkvextract")
    ffmpeg_calls = _command_invocations(log, "ffmpeg")
    mkvmerge_calls = _command_invocations(log, "mkvmerge")
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert any("boost_multi_one.mkv" in call for call in mkvextract_calls)
    assert any("boost_multi_two.mkv" in call for call in mkvextract_calls)
    assert any("-filter:a volume=2dB" in call for call in ffmpeg_calls)
    assert any("-filter:a volume=-3dB" in call for call in ffmpeg_calls)
    assert any("--track-name 0:-3dB" in call and "--track-name 0:2dB" in call for call in mkvmerge_calls)
    assert (env["workdir"] / f"{first.stem}_boosted (1).mkv").exists()
    assert (env["workdir"] / f"{second.stem}_boosted (1).mkv").exists()
    assert first.exists()
    assert second.exists()
    assert "codec_extension=" not in output


def test_mkv_mux_option3_uses_fdk_aac_encoder_when_available(env: dict[str, Path]):
    source = _mkv_file(env, "boost_single.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source.name]],
        input_data="3\n2dB,-3dB\n",
        extra_env={"TEST_FAKE_FFMPEG_HAS_LIBFDK": "1"},
    )

    ffmpeg_calls = _command_invocations(_read_command_log(env), "ffmpeg")
    boosted_calls = [call for call in ffmpeg_calls if "-filter:a" in call and "-encoders" not in call]
    assert result.returncode == 0
    assert len(boosted_calls) == 2
    assert all("-c:a libfdk_aac" in call for call in boosted_calls)
    assert all("-profile:a aac_low" in call for call in boosted_calls)
    assert all(call.count(" -vbr 5 ") == 1 for call in boosted_calls)
    assert all(call.count("-afterburner 1") == 1 for call in boosted_calls)
    assert all("-q:a 0" not in call for call in boosted_calls)
    assert result.stdout.count("Debug: AAC encoder selected: libfdk_aac") == 1
    assert result.stdout.count("Debug: AAC encoder selected") == 1


def test_mkv_mux_option3_uses_native_aac_when_libfdk_missing(env: dict[str, Path]):
    source = _mkv_file(env, "boost_single_climit.mkv")

    result = _run_mkv_mux(
        env,
        "--debug",
        fzf_responses=[[source.name]],
        input_data="3\n2dB\n",
    )

    ffmpeg_calls = _command_invocations(_read_command_log(env), "ffmpeg")
    assert result.returncode == 0
    assert result.stdout.count("Debug: AAC encoder selected: FFmpeg native AAC") == 1
    assert "Debug: AAC encoder selected: libfdk_aac" not in result.stdout
    assert any("-c:a aac -q:a 0" in call for call in ffmpeg_calls)
    assert not any("-c:a libfdk_aac" in call for call in ffmpeg_calls)
    assert not any("-profile:a aac_low" in call for call in ffmpeg_calls)
    assert not any("-afterburner 1" in call for call in ffmpeg_calls)


def test_mkv_mux_option3_climiter_is_added_to_boost_filters(env: dict[str, Path]):
    source = _mkv_file(env, "boost_single_climit.mkv")

    result = _run_mkv_mux(
        env,
        "--climit",
        fzf_responses=[[source.name]],
        input_data="3\n2dB\nalimiter=limit=0.8:attack=14:release=14\n",
    )

    ffmpeg_calls = _command_invocations(_read_command_log(env), "ffmpeg")
    assert result.returncode == 0
    assert "Debug: AAC encoder selected" not in result.stdout
    assert any(
        "volume=2dB,alimiter=limit=0.8:attack=14:release=14:level=0" in call
        for call in ffmpeg_calls
    )


def test_mkv_mux_option3_climiter_preserves_fdk_filter_shape(env: dict[str, Path]):
    source = _mkv_file(env, "boost_single_climit.mkv")

    result = _run_mkv_mux(
        env,
        "--climit",
        "--debug",
        fzf_responses=[[source.name]],
        input_data="3\n2dB\nalimiter=limit=0.8:attack=14:release=14\n",
        extra_env={"TEST_FAKE_FFMPEG_HAS_LIBFDK": "1"},
    )

    ffmpeg_calls = _command_invocations(_read_command_log(env), "ffmpeg")
    assert result.returncode == 0
    boosted_calls = [call for call in ffmpeg_calls if "-filter:a" in call and "-encoders" not in call]
    assert len(boosted_calls) == 1
    assert any(
        "-c:a libfdk_aac -profile:a aac_low -vbr 5 -afterburner 1" in call
        for call in boosted_calls
    )
    assert any(
        "volume=2dB,alimiter=limit=0.8:attack=14:release=14:level=0" in call
        for call in boosted_calls
    )


def test_mkv_mux_option3_failing_boost_restores_backup(env: dict[str, Path]):
    source = _mkv_file(env, "boost_fail.mkv")

    result = _run_mkv_mux(
        env,
        fzf_responses=[[source.name]],
        input_data="3\n2dB\n",
        extra_env={"TEST_FAKE_FFMPEG_FAIL_CALL": "1"},
    )

    assert result.returncode == 0
    assert "Error: Boosting volume failed" in (result.stdout + result.stderr)
    assert source.exists()
    assert not (env["workdir"] / f"{source.stem}_boosted (1).mkv").exists()
    assert not any(path.name.startswith("boost_fail_temp") for path in env["workdir"].iterdir())
