"""Composing the final 9:16 video.

One FFmpeg invocation does the whole job: scale and crop the backdrop, overlay
the caption track, attach the narration, encode. :func:`build_command` is a
pure function so the command can be unit-tested without running anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resumex.captions.render import CaptionTrack
from resumex.config import RenderConfig
from resumex.exceptions import RenderError
from resumex.logging import get_logger
from resumex.models import RenderResult
from resumex.rendering import ffmpeg
from resumex.rendering.background import DRIFT_RATIO, Background

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Composition:
    """Everything needed to render one video."""

    background: Background
    duration: float
    output: Path
    config: RenderConfig
    captions: CaptionTrack | None = None
    audio: Path | None = None

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise RenderError("Cannot render a video with a duration of zero.")


def build_command(composition: Composition, executable: str = "ffmpeg") -> list[str]:
    """Build the full FFmpeg argument list for a composition."""
    config = composition.config
    duration = composition.duration

    command = [executable, "-y", "-hide_banner", "-loglevel", "error"]

    if composition.background.is_video:
        command += ["-stream_loop", "-1", "-i", str(composition.background.path)]
    else:
        command += ["-loop", "1", "-i", str(composition.background.path)]

    caption_index: int | None = None
    audio_index: int | None = None
    next_index = 1

    if composition.captions is not None:
        command += ["-f", "concat", "-safe", "0", "-i", str(composition.captions.concat_file)]
        caption_index = next_index
        next_index += 1

    if composition.audio is not None:
        command += ["-i", str(composition.audio)]
        audio_index = next_index
        next_index += 1

    command += ["-filter_complex", _filter_graph(composition, caption_index), "-map", "[v]"]

    if audio_index is not None:
        command += [
            "-map", f"{audio_index}:a",
            "-c:a", "aac",
            "-b:a", config.audio_bitrate,
            "-ar", "48000",
        ]
    else:
        command += ["-an"]

    command += [
        "-c:v", "libx264",
        "-preset", config.preset,
        "-crf", str(config.crf),
        "-pix_fmt", "yuv420p",
        "-r", str(config.fps),
        "-movflags", "+faststart",
        "-t", f"{duration:.3f}",
        str(composition.output),
    ]
    return command


def _filter_graph(composition: Composition, caption_index: int | None) -> str:
    config = composition.config
    width, height = config.width, config.height

    if composition.background.is_video:
        chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={config.fps}"
        )
    else:
        # Stills drift slowly upward so a static backdrop does not look frozen.
        tall = int(height * DRIFT_RATIO)
        chain = (
            f"[0:v]scale={width}:{tall}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:'(iw-ow)/2':'(ih-oh)*t/{composition.duration:.3f}',"
            f"setsar=1,fps={config.fps}"
        )

    if config.background_dim > 0:
        keep = round(1.0 - config.background_dim, 3)
        chain += f",colorchannelmixer=rr={keep}:gg={keep}:bb={keep}"

    if caption_index is None:
        return f"{chain},format=yuv420p[v]"

    track = composition.captions
    assert track is not None  # guarded by caption_index
    return (
        f"{chain}[bg];"
        f"[{caption_index}:v]format=rgba,fps={config.fps}[cap];"
        f"[bg][cap]overlay=0:{track.y_offset}:format=auto,format=yuv420p[v]"
    )


def compose(composition: Composition, tools_ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
            story_id: str = "") -> RenderResult:
    """Render the composition and report what actually landed on disk."""
    executable = ffmpeg.resolve(tools_ffmpeg)
    composition.output.parent.mkdir(parents=True, exist_ok=True)

    command = build_command(composition, executable)
    logger.debug("composing %s (%.2fs)", composition.output.name, composition.duration)
    ffmpeg.run(command, description="Video composition")

    if not composition.output.is_file() or composition.output.stat().st_size == 0:
        raise RenderError(f"FFmpeg reported success but produced no file at {composition.output}")

    info = ffmpeg.probe(composition.output, ffprobe)
    return RenderResult(
        path=composition.output,
        width=info.width or composition.config.width,
        height=info.height or composition.config.height,
        duration=info.duration or composition.duration,
        has_audio=info.has_audio,
        story_id=story_id,
    )
