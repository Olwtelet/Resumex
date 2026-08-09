"""Deterministic metadata generation.

No model, no network. Given the same story this always produces the same title,
description and tags — which is what makes it a dependable default and what
makes it testable.
"""

from __future__ import annotations

import re

from resumex.models import Story, VideoMetadata

MAX_TITLE = 100
MAX_DESCRIPTION = 4900
MAX_TAGS = 6

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")

STOPWORDS = frozenset(
    """
    a about after all also am an and any are as at be because been before being but by can could
    did do does doing done down each even every for from further had has have having he her here
    hers him his how i if in into is it its just me more most my no nor not now of off on once only
    or other our out over own same she should so some such than that the their them then there
    these they this those through to too under until up very was we were what when where which
    while who whom why will with would you your yours
    """.split()
)


def generate(story: Story, max_title_length: int = MAX_TITLE) -> VideoMetadata:
    """Build publishing metadata straight from the story text."""
    return VideoMetadata(
        title=build_title(story.title, max_title_length),
        description=build_description(story),
        tags=extract_tags(story),
        provider="fallback",
        source_url=story.source_url,
    )


def build_title(raw: str, limit: int = MAX_TITLE) -> str:
    """Collapse whitespace and truncate on a word boundary."""
    title = re.sub(r"\s+", " ", raw).strip(" -–—:;,.")
    if len(title) <= limit:
        return title
    clipped = title[: limit - 1].rsplit(" ", 1)[0].rstrip(" -–—:;,.")
    return f"{clipped or title[: limit - 1]}…"


def build_description(story: Story) -> str:
    """Two sentences of teaser, then attribution when we have any."""
    sentences = [s for s in story.sentences()[1:] if s]
    teaser = " ".join(sentences[:2]) if sentences else story.body[:280]

    parts = [teaser.strip()]
    attribution = credit(story)
    if attribution:
        parts.append(attribution)

    tags = extract_tags(story)
    if tags:
        parts.append(" ".join(f"#{tag}" for tag in tags))

    return "\n\n".join(part for part in parts if part)[:MAX_DESCRIPTION]


def credit(story: Story) -> str:
    if story.author and story.source_url:
        return f"Original story by {story.author} — {story.source_url}"
    if story.source_url:
        return f"Original story: {story.source_url}"
    if story.author:
        return f"Original story by {story.author}"
    return ""


def extract_tags(story: Story, limit: int = MAX_TAGS) -> tuple[str, ...]:
    """The most frequent meaningful words in the story, longest ties first."""
    counts: dict[str, int] = {}
    for match in _WORD.finditer(f"{story.title} {story.body}"):
        word = match.group(0).lower().strip("'-")
        if len(word) < 4 or word in STOPWORDS:
            continue
        counts[word] = counts.get(word, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return tuple(word for word, _ in ranked[:limit])
