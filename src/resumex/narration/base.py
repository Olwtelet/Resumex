"""The contract every narrator implements, plus the text chunking they share."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from resumex.models import NarrationResult

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")
_WHITESPACE = re.compile(r"\s+")

# Long enough to sound natural, short enough that caption timing stays accurate.
MAX_CHUNK_WORDS = 18


class Narrator(ABC):
    """Turns text into an audio file plus the timing of each spoken chunk."""

    name: str = "narrator"

    @abstractmethod
    def synthesize(self, text: str, destination: Path) -> NarrationResult:
        """Write audio to ``destination`` and describe its timing."""

    # Not abstract: most narrators hold nothing that needs releasing.
    def close(self) -> None:  # noqa: B027
        """Release any model held open. Safe to call more than once."""


def split_into_chunks(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    """Split narration text into speakable chunks, on sentences then clauses."""
    normalized = _WHITESPACE.sub(" ", text).strip()
    if not normalized:
        return []

    chunks: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(normalized):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence.split()) <= max_words:
            chunks.append(sentence)
            continue
        chunks.extend(_split_long(sentence, max_words))
    return chunks


def _split_long(sentence: str, max_words: int) -> list[str]:
    """Break an over-long sentence on clause boundaries, then on word count."""
    pieces: list[str] = []
    for clause in _CLAUSE_SPLIT.split(sentence):
        clause = clause.strip()
        if not clause:
            continue
        words = clause.split()
        if len(words) <= max_words:
            pieces.append(clause)
            continue
        for start in range(0, len(words), max_words):
            pieces.append(" ".join(words[start : start + max_words]))
    return pieces
