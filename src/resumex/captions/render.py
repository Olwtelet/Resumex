"""Drawing caption cues into a transparent overlay track.

Each cue becomes one RGBA frame the width of the video and a few hundred pixels
tall. The frames are listed in an FFmpeg concat file with explicit durations,
so the whole caption track enters the render as a single input and a single
overlay — no per-cue filter chains, no frame-by-frame compositing in Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resumex.config import RenderConfig
from resumex.exceptions import RenderError
from resumex.models import CaptionCue

MARGIN = 64
LINE_SPACING = 1.2
MAX_LINES = 3


@dataclass(frozen=True, slots=True)
class CaptionTrack:
    """A rendered caption overlay, ready to hand to FFmpeg."""

    concat_file: Path
    width: int
    height: int
    y_offset: int
    frame_count: int


def band_height(config: RenderConfig) -> int:
    line = int(config.font_size * LINE_SPACING)
    return min(config.height, line * MAX_LINES + config.caption_stroke_width * 2 + MARGIN)


def y_offset(config: RenderConfig) -> int:
    return max(0, int((config.height - band_height(config)) * config.caption_position))


def render_track(
    cues: list[CaptionCue],
    config: RenderConfig,
    directory: Path,
    total_duration: float,
) -> CaptionTrack | None:
    """Render every cue to disk and write the concat file. ``None`` if no cues."""
    if not cues:
        return None

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - Pillow is a hard dependency
        raise RenderError("Pillow is required to draw captions.") from exc

    if not config.font.is_file():
        raise RenderError(
            f"Caption font not found: {config.font}",
            hint="Point render.font_path at a .ttf file, or unset it to use the bundled font.",
        )

    directory.mkdir(parents=True, exist_ok=True)
    width, height = config.width, band_height(config)
    font = ImageFont.truetype(str(config.font), config.font_size)

    blank = directory / "caption-blank.png"
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(blank)

    entries: list[tuple[Path, float]] = []
    cursor = 0.0
    for index, cue in enumerate(cues):
        if cue.start > cursor + 0.01:
            entries.append((blank, cue.start - cursor))
            cursor = cue.start

        frame = directory / f"caption-{index:05d}.png"
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        _draw_cue(ImageDraw.Draw(image), cue, font, config, width, height)
        image.save(frame)
        entries.append((frame, max(0.04, cue.end - cue.start)))
        cursor = cue.end

    if total_duration > cursor + 0.01:
        entries.append((blank, total_duration - cursor))

    concat_file = directory / "captions.txt"
    _write_concat(concat_file, entries)
    return CaptionTrack(
        concat_file=concat_file,
        width=width,
        height=height,
        y_offset=y_offset(config),
        frame_count=len(entries),
    )


def _draw_cue(draw, cue: CaptionCue, font, config: RenderConfig, width: int, height: int) -> None:
    lines = _wrap(cue.words, draw, font, width - MARGIN * 2)
    line_height = int(config.font_size * LINE_SPACING)
    total_height = line_height * len(lines)
    y = max(0, (height - total_height) // 2)

    space = draw.textlength(" ", font=font)
    fill = config.caption_text_color
    highlight = config.caption_highlight_color
    stroke = config.caption_stroke_color
    stroke_width = config.caption_stroke_width

    index = 0
    for line in lines:
        line_width = sum(draw.textlength(word, font=font) for word in line)
        line_width += space * max(0, len(line) - 1)
        x = max(0.0, (width - line_width) / 2)

        for word in line:
            draw.text(
                (x, y),
                word,
                font=font,
                fill=highlight if index == cue.highlight_index else fill,
                stroke_width=stroke_width,
                stroke_fill=stroke,
            )
            x += draw.textlength(word, font=font) + space
            index += 1
        y += line_height


def _wrap(words: tuple[str, ...], draw, font, max_width: float) -> list[list[str]]:
    """Greedy word wrap, capped at MAX_LINES so text never leaves the band."""
    lines: list[list[str]] = []
    current: list[str] = []
    space = draw.textlength(" ", font=font)

    for word in words:
        candidate = [*current, word]
        candidate_width = sum(draw.textlength(w, font=font) for w in candidate)
        candidate_width += space * (len(candidate) - 1)
        if current and candidate_width > max_width:
            lines.append(current)
            current = [word]
        else:
            current = candidate

    if current:
        lines.append(current)

    if len(lines) > MAX_LINES:
        head = lines[: MAX_LINES - 1]
        head.append([word for line in lines[MAX_LINES - 1 :] for word in line])
        lines = head
    return lines


def _write_concat(path: Path, entries: list[tuple[Path, float]]) -> None:
    """Write an FFmpeg concat demuxer script.

    The final entry is repeated without a duration: the concat demuxer ignores
    the duration of the last file, so the repeat is what makes the real last
    duration take effect.
    """
    lines: list[str] = []
    for file, duration in entries:
        lines.append(f"file '{_escape(file)}'")
        lines.append(f"duration {duration:.3f}")
    if entries:
        lines.append(f"file '{_escape(entries[-1][0])}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _escape(path: Path) -> str:
    """Absolute POSIX-style path, with single quotes escaped for the concat parser."""
    return path.resolve().as_posix().replace("'", r"'\''")
