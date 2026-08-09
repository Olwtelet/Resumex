"""Turning narration timing into caption cues.

The narrator tells us when each chunk of text starts and ends. Within a chunk
we distribute time across words in proportion to their length, which tracks
speech closely enough for word-level highlighting and costs nothing.
"""

from __future__ import annotations

from resumex.models import CaptionCue, NarrationChunk

# Below this, a highlight flickers rather than reads.
MIN_WORD_SECONDS = 0.08


def word_timings(text: str, start: float, end: float) -> list[tuple[str, float, float]]:
    """Spread the span ``start``..``end`` across the words of ``text`` by length."""
    words = text.split()
    if not words:
        return []

    span = max(0.0, end - start)
    total_chars = sum(len(word) for word in words) + max(0, len(words) - 1)
    if total_chars <= 0 or span <= 0:
        step = span / len(words) if words else 0.0
        return [(w, start + i * step, start + (i + 1) * step) for i, w in enumerate(words)]

    per_char = span / total_chars
    timings: list[tuple[str, float, float]] = []
    cursor = start
    for index, word in enumerate(words):
        chars = len(word) + (1 if index < len(words) - 1 else 0)
        word_end = cursor + chars * per_char
        timings.append((word, round(cursor, 3), round(word_end, 3)))
        cursor = word_end
    return timings


def cues_from_chunks(
    chunks: tuple[NarrationChunk, ...] | list[NarrationChunk],
    *,
    max_words: int = 4,
    max_duration: float = 2.2,
) -> list[CaptionCue]:
    """Build one cue per word, each carrying the group it is shown with.

    Words are grouped so that a group never exceeds ``max_words`` or
    ``max_duration``. Groups never span two narration chunks, which keeps
    captions aligned with the pauses in the audio.
    """
    cues: list[CaptionCue] = []
    for chunk in chunks:
        timings = word_timings(chunk.text, chunk.start, chunk.end)
        for group in _group(timings, max_words, max_duration):
            words = tuple(word for word, _, _ in group)
            for index, (_, start, end) in enumerate(group):
                cues.append(
                    CaptionCue(
                        words=words,
                        highlight_index=index,
                        start=start,
                        end=max(end, start + MIN_WORD_SECONDS),
                    )
                )
    return _remove_overlaps(cues)


def _group(
    timings: list[tuple[str, float, float]], max_words: int, max_duration: float
) -> list[list[tuple[str, float, float]]]:
    groups: list[list[tuple[str, float, float]]] = []
    current: list[tuple[str, float, float]] = []

    for timing in timings:
        candidate = [*current, timing]
        too_long = candidate[-1][2] - candidate[0][1] > max_duration
        too_many = len(candidate) > max_words
        if current and (too_long or too_many):
            groups.append(current)
            current = [timing]
        else:
            current = candidate

    if current:
        groups.append(current)
    return groups


def _remove_overlaps(cues: list[CaptionCue]) -> list[CaptionCue]:
    """Make each cue end exactly where the next begins, so nothing flickers."""
    adjusted: list[CaptionCue] = []
    for index, cue in enumerate(cues):
        end = cue.end
        if index + 1 < len(cues):
            end = min(end, cues[index + 1].start)
        if end <= cue.start:
            end = cue.start + MIN_WORD_SECONDS
        adjusted.append(
            CaptionCue(
                words=cue.words,
                highlight_index=cue.highlight_index,
                start=round(cue.start, 3),
                end=round(end, 3),
            )
        )
    return adjusted
