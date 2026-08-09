"""The contract every scorer implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from resumex.models import Story, StoryScore

COMPONENTS = ("length", "structure", "voice", "hook")


class Scorer(ABC):
    """Rates how well a story suits short-form narration."""

    name: str = "scorer"

    @abstractmethod
    def score(self, story: Story) -> StoryScore:
        """Return a 0 to 10 score. Must not raise for ordinary input."""


def clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return round(max(low, min(high, value)), 2)
