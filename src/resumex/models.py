"""The domain model.

These are the only shapes that travel between pipeline stages. No stage passes
an untyped dict to another stage.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_WHITESPACE = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class Story:
    """A piece of text to turn into a video."""

    title: str
    body: str
    author: str | None = None
    source: str = "local"
    source_url: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _WHITESPACE.sub(" ", self.title).strip())
        object.__setattr__(self, "body", self.body.strip())
        if not self.title:
            raise ValueError("Story.title must not be empty")
        if not self.body:
            raise ValueError("Story.body must not be empty")

    @property
    def id(self) -> str:
        """A stable identifier, derived from the source or from the text itself."""
        seed = self.source_url or self.source_id or f"{self.title}\n{self.body}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    @property
    def narration_text(self) -> str:
        """What actually gets spoken: the title, then the body."""
        title = self.title if self.title.endswith((".", "!", "?")) else f"{self.title}."
        return f"{title} {self.body}"

    @property
    def word_count(self) -> int:
        return len(self.narration_text.split())

    def sentences(self) -> list[str]:
        parts = (p.strip() for p in _SENTENCE_END.split(_WHITESPACE.sub(" ", self.narration_text)))
        return [p for p in parts if p]


@dataclass(frozen=True, slots=True)
class StoryScore:
    """How well a story suits short-form narration, on a 0–10 scale."""

    overall: float
    components: dict[str, float] = field(default_factory=dict)
    provider: str = "heuristic"

    def __post_init__(self) -> None:
        object.__setattr__(self, "overall", round(max(0.0, min(10.0, self.overall)), 2))

    def __str__(self) -> str:
        parts = ", ".join(f"{k}={v:g}" for k, v in sorted(self.components.items()))
        return f"{self.overall:g}/10 ({parts})" if parts else f"{self.overall:g}/10"


@dataclass(frozen=True, slots=True)
class NarrationChunk:
    """A span of narrated text with the audio timing that belongs to it."""

    text: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True, slots=True)
class NarrationResult:
    """The output of a narrator: one audio file plus the timing of its parts."""

    audio_path: Path
    duration: float
    chunks: tuple[NarrationChunk, ...]
    provider: str
    voice: str
    sample_rate: int = 24_000
    is_silent: bool = False


@dataclass(frozen=True, slots=True)
class CaptionCue:
    """One on-screen caption: a group of words with one of them highlighted."""

    words: tuple[str, ...]
    highlight_index: int
    start: float
    end: float

    def __post_init__(self) -> None:
        if not self.words:
            raise ValueError("CaptionCue.words must not be empty")
        if not 0 <= self.highlight_index < len(self.words):
            raise ValueError(
                f"highlight_index {self.highlight_index} out of range for {len(self.words)} words"
            )
        if self.end < self.start:
            raise ValueError("CaptionCue.end must not precede .start")

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def text(self) -> str:
        return " ".join(self.words)


@dataclass(frozen=True, slots=True)
class RenderResult:
    """A finished video on disk."""

    path: Path
    width: int
    height: int
    duration: float
    has_audio: bool
    story_id: str


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Publishing metadata for a rendered video."""

    title: str
    description: str
    tags: tuple[str, ...] = ()
    provider: str = "fallback"
    source_url: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "provider": self.provider,
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> VideoMetadata:
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return cls(
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            tags=tuple(str(t) for t in tags),
            provider=str(data.get("provider", "fallback")),
            source_url=data.get("source_url") or None,  # type: ignore[arg-type]
        )
