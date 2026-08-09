from __future__ import annotations

from pathlib import Path

import pytest

from resumex.captions.render import CaptionTrack
from resumex.config import RenderConfig, ToolsConfig
from resumex.exceptions import MissingDependencyError, RenderError
from resumex.rendering import ffmpeg
from resumex.rendering.background import Background, choose, find_backgrounds, synthesize
from resumex.rendering.compositor import Composition, build_command


def make_composition(tmp_path: Path, **overrides) -> Composition:
    defaults = {
        "background": Background(path=tmp_path / "bg.png", kind="image"),
        "duration": 12.5,
        "output": tmp_path / "out.mp4",
        "config": RenderConfig(),
        "captions": None,
        "audio": None,
    }
    defaults.update(overrides)
    return Composition(**defaults)  # type: ignore[arg-type]


def flag_value(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


# -- command construction ------------------------------------------------


def test_command_encodes_h264_yuv420p_mp4(tmp_path: Path):
    command = build_command(make_composition(tmp_path))
    assert flag_value(command, "-c:v") == "libx264"
    assert flag_value(command, "-pix_fmt") == "yuv420p"
    assert command[-1].endswith("out.mp4")


def test_command_bounds_the_output_to_the_narration_length(tmp_path: Path):
    command = build_command(make_composition(tmp_path, duration=7.25))
    assert flag_value(command, "-t") == "7.250"


def test_video_backgrounds_are_looped_and_cover_cropped(tmp_path: Path):
    composition = make_composition(
        tmp_path, background=Background(path=tmp_path / "bg.mp4", kind="video")
    )
    command = build_command(composition)
    assert flag_value(command, "-stream_loop") == "-1"
    graph = flag_value(command, "-filter_complex")
    assert "force_original_aspect_ratio=increase" in graph
    assert "crop=1080:1920" in graph


def test_still_backgrounds_are_looped_and_drift(tmp_path: Path):
    command = build_command(make_composition(tmp_path, duration=9.0))
    assert flag_value(command, "-loop") == "1"
    graph = flag_value(command, "-filter_complex")
    assert "(ih-oh)*t/9.000" in graph


def test_no_audio_input_means_an_explicitly_silent_file(tmp_path: Path):
    command = build_command(make_composition(tmp_path))
    assert "-an" in command
    assert "-c:a" not in command


def test_audio_is_mapped_and_encoded_as_aac(tmp_path: Path):
    command = build_command(make_composition(tmp_path, audio=tmp_path / "narration.wav"))
    assert flag_value(command, "-c:a") == "aac"
    assert flag_value(command, "-map") == "[v]"
    assert "1:a" in command


def test_caption_track_becomes_a_single_concat_input_and_one_overlay(tmp_path: Path):
    track = CaptionTrack(
        concat_file=tmp_path / "captions.txt", width=1080, height=340, y_offset=700, frame_count=9
    )
    command = build_command(make_composition(tmp_path, captions=track))
    assert "concat" in command
    assert flag_value(command, "-safe") == "0"
    graph = flag_value(command, "-filter_complex")
    assert graph.count("overlay=") == 1
    assert "overlay=0:700" in graph


def test_indices_shift_when_captions_and_audio_are_both_present(tmp_path: Path):
    track = CaptionTrack(
        concat_file=tmp_path / "captions.txt", width=1080, height=340, y_offset=700, frame_count=2
    )
    command = build_command(
        make_composition(tmp_path, captions=track, audio=tmp_path / "narration.wav")
    )
    assert "2:a" in command
    assert "[1:v]format=rgba" in flag_value(command, "-filter_complex")


def test_dimming_is_skipped_when_it_is_zero(tmp_path: Path):
    lit = build_command(make_composition(tmp_path, config=RenderConfig(background_dim=0.0)))
    dimmed = build_command(make_composition(tmp_path, config=RenderConfig(background_dim=0.4)))
    assert "colorchannelmixer" not in flag_value(lit, "-filter_complex")
    assert "colorchannelmixer=rr=0.6" in flag_value(dimmed, "-filter_complex")


def test_render_settings_reach_the_command(tmp_path: Path):
    config = RenderConfig(width=720, height=1280, fps=24, crf=28, preset="ultrafast")
    command = build_command(make_composition(tmp_path, config=config))
    assert flag_value(command, "-crf") == "28"
    assert flag_value(command, "-preset") == "ultrafast"
    assert flag_value(command, "-r") == "24"
    assert "crop=720:1280" in flag_value(command, "-filter_complex")


def test_command_is_an_argument_list_so_nothing_is_shell_interpreted(tmp_path: Path):
    hostile = tmp_path / "a b; rm -rf $HOME.png"
    command = build_command(make_composition(tmp_path, background=Background(hostile, "image")))
    assert str(hostile) in command
    assert all(isinstance(part, str) for part in command)


def test_zero_duration_is_refused(tmp_path: Path):
    with pytest.raises(RenderError):
        make_composition(tmp_path, duration=0)


# -- tool discovery ------------------------------------------------------


def test_resolve_explains_how_to_install_a_missing_tool():
    with pytest.raises(MissingDependencyError) as exc:
        ffmpeg.resolve("definitely-not-a-real-binary-xyz")
    assert "install" in (exc.value.hint or "").lower()


def test_available_reports_both_tools_without_raising():
    found = ffmpeg.available(ToolsConfig(ffmpeg="nope-xyz", ffprobe="nope-xyz"))
    assert found == (False, False)


# -- backgrounds ---------------------------------------------------------


def test_find_backgrounds_ignores_unrelated_files(tmp_path: Path):
    (tmp_path / "clip.mp4").write_bytes(b"")
    (tmp_path / "still.png").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    assert [p.name for p in find_backgrounds(tmp_path)] == ["clip.mp4", "still.png"]


def test_choose_returns_none_for_an_empty_directory(tmp_path: Path):
    assert choose(tmp_path / "missing") is None
    assert choose(tmp_path) is None


def test_choose_labels_videos_and_stills(tmp_path: Path):
    (tmp_path / "clip.mp4").write_bytes(b"")
    background = choose(tmp_path)
    assert background is not None and background.is_video


def test_synthetic_background_is_deterministic_and_taller_than_the_frame(tmp_path: Path):
    from PIL import Image

    first = synthesize(tmp_path / "a.png", 270, 480, seed=7)
    second = synthesize(tmp_path / "b.png", 270, 480, seed=7)
    assert first.synthetic and not first.is_video
    assert first.path.read_bytes() == second.path.read_bytes()

    with Image.open(first.path) as image:
        assert image.width == 270
        assert image.height > 480


def test_different_seeds_give_different_backgrounds(tmp_path: Path):
    a = synthesize(tmp_path / "a.png", 120, 200, seed=1)
    b = synthesize(tmp_path / "b.png", 120, 200, seed=2)
    assert a.path.read_bytes() != b.path.read_bytes()
