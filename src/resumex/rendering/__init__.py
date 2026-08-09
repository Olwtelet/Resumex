"""Deterministic 9:16 video composition on top of FFmpeg."""

from resumex.rendering.background import Background, choose, find_backgrounds, synthesize
from resumex.rendering.compositor import Composition, build_command, compose
from resumex.rendering.ffmpeg import MediaInfo, probe

__all__ = [
    "Background",
    "Composition",
    "MediaInfo",
    "build_command",
    "choose",
    "compose",
    "find_backgrounds",
    "probe",
    "synthesize",
]
