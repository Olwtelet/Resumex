"""Optional story scoring. The pipeline works fine with scoring switched off."""

from __future__ import annotations

from resumex.config import Config
from resumex.models import Story, StoryScore
from resumex.scoring.base import Scorer
from resumex.scoring.heuristic import HeuristicScorer
from resumex.scoring.ollama import OllamaScorer

__all__ = ["HeuristicScorer", "OllamaScorer", "Scorer", "get_scorer"]


def get_scorer(config: Config) -> Scorer | None:
    """Return the configured scorer, or ``None`` when scoring is disabled."""
    provider = config.scoring.provider
    if provider == "none":
        return None
    if provider == "ollama":
        return OllamaScorer(config.ollama)
    return HeuristicScorer()


def passes(score: StoryScore | None, minimum: float) -> bool:
    """Whether a story clears the configured threshold. No score means no filter."""
    return score is None or score.overall >= minimum


def describe(story: Story, score: StoryScore | None) -> str:
    return f"{story.title[:60]} — {score}" if score else story.title[:60]
