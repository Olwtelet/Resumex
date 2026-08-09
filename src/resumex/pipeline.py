"""The pipeline: story in, video out.

Every stage is a small, replaceable piece. This module only decides the order
they run in, where their intermediate files live, and that those files are
cleaned up whether the render succeeds or fails.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from resumex.captions.render import render_track
from resumex.captions.timing import cues_from_chunks
from resumex.config import Config
from resumex.exceptions import ContentError, RenderError
from resumex.logging import get_logger
from resumex.metadata import generate_metadata
from resumex.models import RenderResult, Story, StoryScore, VideoMetadata
from resumex.narration import Narrator, get_narrator
from resumex.rendering import background as background_module
from resumex.rendering.compositor import Composition, compose
from resumex.scoring import get_scorer, passes
from resumex.state import StateStore

logger = get_logger(__name__)

Progress = Callable[[str], None]

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Everything one run produced."""

    story: Story
    render: RenderResult
    metadata: VideoMetadata
    metadata_path: Path
    narration_provider: str
    score: StoryScore | None = None


class Pipeline:
    """Runs stories through narration, captions and composition."""

    def __init__(
        self,
        config: Config,
        *,
        narrator: Narrator | None = None,
        store: StateStore | None = None,
        progress: Progress | None = None,
        force_silent: bool = False,
    ) -> None:
        self.config = config
        self.progress = progress or (lambda _message: None)
        self._store = store
        self._force_silent = force_silent
        self._narrator = narrator
        self._scorer = get_scorer(config)

    @property
    def narrator(self) -> Narrator:
        """Built once and reused, so the speech model is loaded at most once."""
        if self._narrator is None:
            self._narrator = get_narrator(self.config, force_silent=self._force_silent)
        return self._narrator

    def close(self) -> None:
        if self._narrator is not None:
            self._narrator.close()

    def __enter__(self) -> Pipeline:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- main entry points ----------------------------------------------

    def render_story(
        self,
        story: Story,
        *,
        output: Path | None = None,
        background: Path | None = None,
    ) -> PipelineResult:
        """Render one story to an MP4 with a metadata sidecar."""
        score = self._score(story)
        if not passes(score, self.config.scoring.min_overall):
            raise ContentError(
                f"'{story.title[:50]}' scored {score} which is below the configured minimum "
                f"of {self.config.scoring.min_overall:g}.",
                hint="Lower scoring.min_overall in resumex.toml, or set scoring.provider = 'none'.",
            )

        destination = output or (self.config.paths.output / f"{slugify(story)}.mp4")

        with self._scratch() as scratch:
            self.progress("Narrating")
            narration = self.narrator.synthesize(story.narration_text, scratch / "narration.wav")
            if narration.duration <= 0:
                raise RenderError("Narration produced zero seconds of audio.")

            self.progress(f"Timing captions ({narration.duration:.1f}s of narration)")
            cues = cues_from_chunks(
                narration.chunks,
                max_words=self.config.render.caption_max_words,
                max_duration=self.config.render.caption_max_duration,
            )
            track = render_track(cues, self.config.render, scratch / "captions", narration.duration)

            self.progress("Preparing background")
            backdrop = self._background(background, scratch, story)

            self.progress(f"Composing {self.config.render.width}x{self.config.render.height} video")
            render = compose(
                Composition(
                    background=backdrop,
                    duration=narration.duration,
                    output=destination,
                    config=self.config.render,
                    captions=track,
                    audio=narration.audio_path,
                ),
                tools_ffmpeg=self.config.tools.ffmpeg,
                ffprobe=self.config.tools.ffprobe,
                story_id=story.id,
            )

        self.progress("Writing metadata")
        metadata = generate_metadata(story, self.config)
        metadata_path = write_metadata(destination, metadata, story, render)

        self._record(story, render)
        return PipelineResult(
            story=story,
            render=render,
            metadata=metadata,
            metadata_path=metadata_path,
            narration_provider=narration.provider,
            score=score,
        )

    def render_many(
        self,
        stories: Iterable[Story],
        *,
        limit: int | None = None,
        skip_seen: bool = True,
        on_error: Callable[[Story, Exception], None] | None = None,
    ) -> list[PipelineResult]:
        """Render a batch, keeping going when an individual story fails."""
        results: list[PipelineResult] = []
        for story in stories:
            if limit is not None and len(results) >= limit:
                break
            if skip_seen and self._store is not None and self._store.has_render_for_story(story.id):
                logger.info("skipping already-rendered story %s", story.id)
                continue
            try:
                results.append(self.render_story(story))
            # One unusable story must never abort a batch.
            except Exception as exc:
                logger.warning("failed to render '%s': %s", story.title[:60], exc)
                if on_error is not None:
                    on_error(story, exc)
        return results

    # -- stages ----------------------------------------------------------

    def _score(self, story: Story) -> StoryScore | None:
        if self._scorer is None:
            return None
        self.progress(f"Scoring with the {self._scorer.name} scorer")
        return self._scorer.score(story)

    def _background(
        self, override: Path | None, scratch: Path, story: Story
    ) -> background_module.Background:
        if override is not None:
            if not override.is_file():
                raise ContentError(f"Background file not found: {override}")
            kind = (
                "video"
                if override.suffix.lower() in background_module.VIDEO_SUFFIXES
                else "image"
            )
            return background_module.Background(path=override, kind=kind)

        chosen = background_module.choose(self.config.paths.backgrounds)
        if chosen is not None:
            logger.debug("using background %s", chosen.path.name)
            return chosen

        logger.info("no files in %s; drawing a background", self.config.paths.backgrounds)
        return background_module.synthesize(
            scratch / "background.png",
            self.config.render.width,
            self.config.render.height,
            seed=int(story.id[:8], 16),
        )

    def _record(self, story: Story, render: RenderResult) -> None:
        if self._store is None:
            return
        self._store.record_story(story)
        self._store.record_render(render)

    @contextmanager
    def _scratch(self):
        """A temp directory that is removed even when a stage raises."""
        self.config.paths.temp.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix="render-", dir=self.config.paths.temp))
        try:
            yield path
        finally:
            shutil.rmtree(path, ignore_errors=True)


def slugify(story: Story) -> str:
    """A filesystem-safe, collision-resistant name for a story."""
    base = _SLUG_STRIP.sub("-", story.title.lower()).strip("-")[:56].strip("-")
    return f"{base or 'story'}-{story.id[:8]}"


def write_metadata(
    video: Path, metadata: VideoMetadata, story: Story, render: RenderResult
) -> Path:
    """Write the sidecar JSON that ``resumex upload`` reads back."""
    path = video.with_suffix(".metadata.json")
    payload = {
        **metadata.to_dict(),
        "story": {
            "id": story.id,
            "title": story.title,
            "author": story.author,
            "source": story.source,
            "source_url": story.source_url,
        },
        "video": {
            "path": video.name,
            "width": render.width,
            "height": render.height,
            "duration": round(render.duration, 3),
            "has_audio": render.has_audio,
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_metadata(video: Path) -> dict:
    """Read the sidecar written by :func:`write_metadata`."""
    path = video.with_suffix(".metadata.json")
    if not path.is_file():
        raise ContentError(
            f"No metadata sidecar next to {video.name}.",
            hint=(
                f"Expected {path.name}. Re-render the story, "
                "or upload with --title/--description."
            ),
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContentError(f"{path.name} is not valid JSON: {exc}") from exc
