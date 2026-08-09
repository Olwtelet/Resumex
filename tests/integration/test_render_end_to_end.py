"""The one test that actually runs FFmpeg.

Marked ``integration`` and skipped automatically when FFmpeg is not installed,
so ``pytest`` stays fast and offline by default. Run it with:

    pytest -m integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resumex.config import BUNDLED_DEMO_STORY, Config, Paths, RenderConfig
from resumex.pipeline import Pipeline
from resumex.rendering import ffmpeg
from resumex.sources.local import load_file
from tests.conftest import requires_ffmpeg

pytestmark = [pytest.mark.integration, requires_ffmpeg]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory):
    workspace = tmp_path_factory.mktemp("render")
    config = Config(
        paths=Paths(workspace=workspace),
        render=RenderConfig(width=270, height=480, fps=12, preset="ultrafast", font_size=26),
    )
    config.paths.ensure()
    story = load_file(BUNDLED_DEMO_STORY)[0]
    with Pipeline(config, force_silent=True) as pipeline:
        return pipeline.render_story(story), config


def test_the_pipeline_produces_a_real_mp4(rendered):
    result, _ = rendered
    assert result.render.path.is_file()
    assert result.render.path.stat().st_size > 10_000


def test_the_output_has_the_requested_geometry_and_codecs(rendered):
    result, config = rendered
    info = ffmpeg.probe(result.render.path, config.tools.ffprobe)
    assert (info.width, info.height) == (270, 480)
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.duration > 1.0


def test_the_aspect_ratio_is_nine_by_sixteen(rendered):
    result, config = rendered
    info = ffmpeg.probe(result.render.path, config.tools.ffprobe)
    assert round(info.width / info.height, 4) == round(9 / 16, 4)


def test_the_video_length_matches_the_narration(rendered):
    result, config = rendered
    info = ffmpeg.probe(result.render.path, config.tools.ffprobe)
    assert info.duration == pytest.approx(result.render.duration, rel=0.05)


def test_the_metadata_sidecar_describes_the_file_that_exists(rendered):
    result, _ = rendered
    assert result.metadata_path.is_file()
    assert result.metadata.title


def test_scratch_files_do_not_survive_the_render(rendered):
    _, config = rendered
    assert list(config.paths.temp.iterdir()) == []


def test_probing_a_non_media_file_raises_a_useful_error(tmp_path: Path):
    from resumex.exceptions import RenderError

    junk = tmp_path / "not-a-video.mp4"
    junk.write_bytes(b"definitely not an mp4")
    with pytest.raises(RenderError):
        ffmpeg.probe(junk)
