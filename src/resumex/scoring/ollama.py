"""Optional LLM scoring via a local Ollama model.

Falls back to :class:`~resumex.scoring.heuristic.HeuristicScorer` whenever the
model is unreachable or answers with something unusable, so enabling this can
slow a run down but can never break it.
"""

from __future__ import annotations

import json

from resumex.config import OllamaConfig
from resumex.logging import get_logger
from resumex.models import Story, StoryScore
from resumex.ollama import OllamaClient, OllamaUnavailable
from resumex.scoring.base import COMPONENTS, Scorer, clamp
from resumex.scoring.heuristic import HeuristicScorer

logger = get_logger(__name__)

PROMPT = """You are rating a written story for use as a narrated short-form video.

Reply with ONLY a JSON object with these four integer fields, each 1-10:
- "length": is this a comfortable length to read aloud in 30-90 seconds?
- "structure": are the sentences and paragraphs a natural size for speech?
- "voice": is it written in a clear personal voice rather than dry exposition?
- "hook": does the opening give a listener a reason to keep listening?

Title: {title}

Story: {body}
"""


class OllamaScorer(Scorer):
    name = "ollama"

    def __init__(self, config: OllamaConfig) -> None:
        self.client = OllamaClient(config)
        self._fallback = HeuristicScorer()

    def score(self, story: Story) -> StoryScore:
        prompt = PROMPT.format(title=story.title, body=story.body[:4000])
        try:
            raw = self.client.generate(prompt, json_mode=True)
            components = _parse(raw)
        except (OllamaUnavailable, ValueError) as exc:
            logger.warning("Ollama scoring unavailable (%s); using the heuristic scorer", exc)
            return self._fallback.score(story)

        overall = sum(components.values()) / len(components)
        return StoryScore(overall=clamp(overall), components=components, provider=self.name)


def _parse(raw: str) -> dict[str, float]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")

    components: dict[str, float] = {}
    for key in COMPONENTS:
        value = data.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"missing or non-numeric field {key!r}")
        components[key] = clamp(float(value))
    return components
