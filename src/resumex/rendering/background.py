"""Choosing or generating the video background.

Resumex never downloads anyone else's video. You either put your own footage in
``backgrounds/``, or Resumex draws a gradient locally — which is what makes the
demo work on a machine with no media on it at all.
"""

from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass
from pathlib import Path

VIDEO_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")

# The synthetic background is drawn taller than the frame so it can drift.
DRIFT_RATIO = 1.18


@dataclass(frozen=True, slots=True)
class Background:
    """Where the backdrop comes from and how FFmpeg should treat it."""

    path: Path
    kind: str  # "video" or "image"
    synthetic: bool = False

    @property
    def is_video(self) -> bool:
        return self.kind == "video"


def find_backgrounds(directory: Path) -> list[Path]:
    """Every usable background file in ``directory``, sorted for determinism."""
    if not directory.is_dir():
        return []
    suffixes = VIDEO_SUFFIXES + IMAGE_SUFFIXES
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in suffixes)


def choose(directory: Path, rng: random.Random | None = None) -> Background | None:
    """Pick one background from the directory, or ``None`` if there are none."""
    candidates = find_backgrounds(directory)
    if not candidates:
        return None
    chosen = (rng or random).choice(candidates)
    kind = "video" if chosen.suffix.lower() in VIDEO_SUFFIXES else "image"
    return Background(path=chosen, kind=kind)


def synthesize(destination: Path, width: int, height: int, seed: int = 0) -> Background:
    """Draw a vertical gradient with a soft vignette, deterministically from ``seed``."""
    from PIL import Image, ImageDraw, ImageFilter

    tall = int(height * DRIFT_RATIO)
    rng = random.Random(seed)
    hue = rng.random()
    top = _rgb(hue, 0.55, 0.32)
    bottom = _rgb((hue + 0.12) % 1.0, 0.65, 0.08)

    image = Image.new("RGB", (1, tall))
    pixels = image.load()
    for y in range(tall):
        ratio = y / max(1, tall - 1)
        pixels[0, y] = tuple(  # type: ignore[assignment]
            int(top[c] + (bottom[c] - top[c]) * ratio) for c in range(3)
        )
    image = image.resize((width, tall), Image.Resampling.BILINEAR)

    vignette = Image.new("L", (width, tall), 0)
    draw = ImageDraw.Draw(vignette)
    inset = int(min(width, tall) * 0.12)
    draw.ellipse((-inset, -inset, width + inset, tall + inset), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=max(8, width // 12)))

    darkened = Image.new("RGB", (width, tall), (0, 0, 0))
    image = Image.composite(image, darkened, vignette)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return Background(path=destination, kind="image", synthetic=True)


def _rgb(hue: float, saturation: float, value: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return (int(r * 255), int(g * 255), int(b * 255))
