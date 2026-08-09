"""A deterministic, offline scorer.

This measures things that genuinely affect a narrated short: whether the text
is the right length to read aloud, whether it is broken into paragraphs and
sentences of a speakable size, whether it is written in a personal voice, and
whether the opening gives the listener a reason to stay.

It is a readability heuristic, not a prediction of how an audience will react.
"""

from __future__ import annotations

import re

from resumex.models import Story, StoryScore
from resumex.scoring.base import Scorer, clamp

# A comfortable narrated short lands between roughly 30 and 90 seconds.
IDEAL_MIN_WORDS = 90
IDEAL_MAX_WORDS = 260

FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|me|mine|we|our)\b", re.IGNORECASE)
HOOK_MARKERS = re.compile(
    r"\b(never|always|until|suddenly|then|finally|nobody|everyone|why|how|when)\b",
    re.IGNORECASE,
)


class HeuristicScorer(Scorer):
    name = "heuristic"

    def score(self, story: Story) -> StoryScore:
        components = {
            "length": _length_score(story.word_count),
            "structure": _structure_score(story),
            "voice": _voice_score(story.narration_text),
            "hook": _hook_score(story),
        }
        weights = {"length": 0.35, "structure": 0.25, "voice": 0.2, "hook": 0.2}
        overall = sum(components[key] * weights[key] for key in components)
        return StoryScore(overall=clamp(overall), components=components, provider=self.name)


def _length_score(words: int) -> float:
    """Full marks inside the ideal band, tapering off outside it."""
    if words <= 0:
        return 0.0
    if IDEAL_MIN_WORDS <= words <= IDEAL_MAX_WORDS:
        return 10.0
    if words < IDEAL_MIN_WORDS:
        return clamp(10.0 * words / IDEAL_MIN_WORDS)
    overshoot = (words - IDEAL_MAX_WORDS) / IDEAL_MAX_WORDS
    return clamp(10.0 - 6.0 * overshoot)


def _structure_score(story: Story) -> float:
    sentences = story.sentences()
    if not sentences:
        return 0.0

    average_words = sum(len(s.split()) for s in sentences) / len(sentences)
    # 8 to 22 words per sentence reads naturally out loud.
    if 8 <= average_words <= 22:
        sentence_score = 10.0
    elif average_words < 8:
        sentence_score = clamp(10.0 * average_words / 8)
    else:
        sentence_score = clamp(10.0 - (average_words - 22) * 0.5)

    paragraphs = [p for p in story.body.split("\n\n") if p.strip()]
    paragraph_score = 10.0 if len(paragraphs) >= 3 else clamp(4.0 + 2.0 * len(paragraphs))

    return clamp(0.6 * sentence_score + 0.4 * paragraph_score)


def _voice_score(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    density = len(FIRST_PERSON.findall(text)) / len(words)
    # ~4% first-person words is a strongly personal narration.
    return clamp(density / 0.04 * 10.0)


def _hook_score(story: Story) -> float:
    sentences = story.sentences()
    opening = " ".join(sentences[:2]) if sentences else story.title
    score = 4.0
    score += min(3.0, len(HOOK_MARKERS.findall(opening)) * 1.5)
    if 4 <= len(story.title.split()) <= 14:
        score += 2.0
    if story.title.endswith("?"):
        score += 1.0
    return clamp(score)
