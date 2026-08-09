"""A narrator that produces silence with realistic timing.

This is what makes ``resumex demo`` work on a fresh clone: it exercises the
entire pipeline — chunking, caption timing, composition, encoding — without
downloading a speech model. Timing is estimated from a words-per-minute rate,
so the captions still march across the screen at a believable pace.
"""

from __future__ import annotations

import wave
from pathlib import Path

from resumex.models import NarrationChunk, NarrationResult
from resumex.narration.base import Narrator, split_into_chunks

SAMPLE_RATE = 24_000
SAMPLE_WIDTH = 2
# A short breath between chunks, so captions do not run into each other.
PAUSE_SECONDS = 0.18
MIN_CHUNK_SECONDS = 0.45


class SilentNarrator(Narrator):
    name = "silent"

    def __init__(self, words_per_minute: int = 165) -> None:
        self.words_per_minute = max(40, words_per_minute)

    def synthesize(self, text: str, destination: Path) -> NarrationResult:
        chunks = self._timed_chunks(text)
        duration = chunks[-1].end if chunks else 1.0
        _write_silence(destination, duration)
        return NarrationResult(
            audio_path=destination,
            duration=duration,
            chunks=tuple(chunks),
            provider=self.name,
            voice="silent",
            sample_rate=SAMPLE_RATE,
            is_silent=True,
        )

    def _timed_chunks(self, text: str) -> list[NarrationChunk]:
        cursor = 0.0
        timed: list[NarrationChunk] = []
        for chunk in split_into_chunks(text):
            seconds = max(MIN_CHUNK_SECONDS, len(chunk.split()) / self.words_per_minute * 60.0)
            timed.append(NarrationChunk(text=chunk, start=cursor, end=cursor + seconds))
            cursor += seconds + PAUSE_SECONDS
        return timed


def _write_silence(destination: Path, duration: float) -> None:
    """Write a mono 16-bit WAV of the given length."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, round(duration * SAMPLE_RATE))
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(SAMPLE_WIDTH)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(b"\x00" * (frames * SAMPLE_WIDTH))
