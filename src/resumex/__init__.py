"""Resumex — a local-first pipeline for turning text stories into short-form videos."""

from resumex.models import (
    CaptionCue,
    NarrationChunk,
    NarrationResult,
    RenderResult,
    Story,
    StoryScore,
    VideoMetadata,
)

__version__ = "0.1.0"

__all__ = [
    "CaptionCue",
    "NarrationChunk",
    "NarrationResult",
    "RenderResult",
    "Story",
    "StoryScore",
    "VideoMetadata",
    "__version__",
]
