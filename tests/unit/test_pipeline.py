"""Pipeline behaviour with the FFmpeg call stubbed out."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resumex.config import Config, Paths, RenderConfig, ScoringConfig
from resumex.exceptions import ContentError
from resumex.models import RenderResult, Story
from resumex.pipeline import Pipeline, read_metadata, slugify, write_metadata
from resumex.state import StateStore


@pytest.fixture
def stub_compose(monkeypatch: pytest.MonkeyPatch) -> list:
    """Replace composition with a stub that writes a placeholder file."""
    calls: list = []

    def fake_compose(composition, tools_ffmpeg="ffmpeg", ffprobe="ffprobe", story_id=""):
        calls.append(composition)
        composition.output.parent.mkdir(parents=True, exist_ok=True)
        composition.output.write_bytes(b"fake mp4")
        return RenderResult(
            path=composition.output,
            width=composition.config.width,
            height=composition.config.height,
            duration=composition.duration,
            has_audio=composition.audio is not None,
            story_id=story_id,
        )

    monkeypatch.setattr("resumex.pipeline.compose", fake_compose)
    return calls


def small(tmp_path: Path, **kwargs) -> Config:
    return Config(
        paths=Paths(workspace=tmp_path),
        render=RenderConfig(width=270, height=480, font_size=24),
        **kwargs,
    )


def test_slug_is_readable_and_unique(story: Story):
    slug = slugify(story)
    assert slug.startswith("a-note-in-a-library-book-")
    assert slug.endswith(story.id[:8])
    assert " " not in slug


def test_render_writes_a_video_and_a_metadata_sidecar(tmp_path: Path, story: Story, stub_compose):
    with Pipeline(small(tmp_path)) as pipeline:
        result = pipeline.render_story(story)

    assert result.render.path.is_file()
    assert result.metadata_path.is_file()
    assert result.metadata_path.name.endswith(".metadata.json")

    payload = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert payload["story"]["id"] == story.id
    assert payload["video"]["width"] == 270


def test_narration_and_captions_reach_the_composition(tmp_path: Path, story: Story, stub_compose):
    with Pipeline(small(tmp_path)) as pipeline:
        pipeline.render_story(story)

    composition = stub_compose[0]
    assert composition.audio is not None
    assert composition.captions is not None
    assert composition.captions.frame_count > 0
    assert composition.duration > 0


def test_a_synthetic_background_is_drawn_when_the_directory_is_empty(
    tmp_path: Path, story: Story, stub_compose
):
    with Pipeline(small(tmp_path)) as pipeline:
        pipeline.render_story(story)
    assert stub_compose[0].background.synthetic


def test_a_supplied_background_is_used_as_is(tmp_path: Path, story: Story, stub_compose):
    backdrop = tmp_path / "mine.mp4"
    backdrop.write_bytes(b"")
    with Pipeline(small(tmp_path)) as pipeline:
        pipeline.render_story(story, background=backdrop)
    assert stub_compose[0].background.path == backdrop
    assert stub_compose[0].background.is_video


def test_a_missing_background_is_reported(tmp_path: Path, story: Story, stub_compose):
    with Pipeline(small(tmp_path)) as pipeline, pytest.raises(ContentError, match="not found"):
        pipeline.render_story(story, background=tmp_path / "gone.mp4")


def test_scratch_files_are_cleaned_up(tmp_path: Path, story: Story, stub_compose):
    config = small(tmp_path)
    with Pipeline(config) as pipeline:
        pipeline.render_story(story)
    assert list(config.paths.temp.iterdir()) == []


def test_scratch_files_are_cleaned_up_after_a_failure(
    tmp_path: Path, story: Story, monkeypatch: pytest.MonkeyPatch
):
    def boom(*args, **kwargs):
        raise RuntimeError("encoder exploded")

    monkeypatch.setattr("resumex.pipeline.compose", boom)
    config = small(tmp_path)
    with Pipeline(config) as pipeline, pytest.raises(RuntimeError):
        pipeline.render_story(story)
    assert list(config.paths.temp.iterdir()) == []


def test_a_story_below_the_score_threshold_is_refused(tmp_path: Path, stub_compose):
    config = small(tmp_path, scoring=ScoringConfig(provider="heuristic", min_overall=9.9))
    with Pipeline(config) as pipeline, pytest.raises(ContentError, match="below the configured"):
        pipeline.render_story(Story(title="Hi", body="No."))


def test_the_score_is_reported_when_scoring_is_on(tmp_path: Path, story: Story, stub_compose):
    config = small(tmp_path, scoring=ScoringConfig(provider="heuristic"))
    with Pipeline(config) as pipeline:
        result = pipeline.render_story(story)
    assert result.score is not None
    assert result.score.provider == "heuristic"


def test_the_narrator_is_built_once_per_pipeline(tmp_path: Path, story: Story, stub_compose):
    with Pipeline(small(tmp_path)) as pipeline:
        first = pipeline.narrator
        pipeline.render_story(story)
        assert pipeline.narrator is first


def test_batches_record_state_and_skip_what_is_already_rendered(
    tmp_path: Path, story: Story, stub_compose
):
    config = small(tmp_path)
    with StateStore(config.paths.database) as store, Pipeline(config, store=store) as pipeline:
        assert len(pipeline.render_many([story])) == 1
        assert len(pipeline.render_many([story])) == 0
        assert len(pipeline.render_many([story], skip_seen=False)) == 1
        assert store.stats().stories == 1


def test_a_failing_story_does_not_stop_the_batch(
    tmp_path: Path, story: Story, monkeypatch: pytest.MonkeyPatch, stub_compose
):
    good = Story(title="Good one", body="This story renders without any trouble at all.")
    calls = {"n": 0}
    original = Pipeline.render_story

    def flaky(self, target, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first one failed")
        return original(self, target, **kwargs)

    monkeypatch.setattr(Pipeline, "render_story", flaky)
    failures: list = []
    with Pipeline(small(tmp_path)) as pipeline:
        results = pipeline.render_many(
            [story, good], on_error=lambda s, e: failures.append((s, e))
        )
    assert len(results) == 1
    assert len(failures) == 1


def test_metadata_sidecar_round_trips(tmp_path: Path, story: Story):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"")
    render = RenderResult(
        path=video, width=1080, height=1920, duration=12.0, has_audio=True, story_id=story.id
    )
    from resumex.metadata.fallback import generate

    write_metadata(video, generate(story), story, render)
    payload = read_metadata(video)
    assert payload["title"]
    assert payload["video"]["duration"] == 12.0


def test_reading_a_missing_sidecar_explains_the_options(tmp_path: Path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"")
    with pytest.raises(ContentError) as exc:
        read_metadata(video)
    assert "--title" in (exc.value.hint or "")
