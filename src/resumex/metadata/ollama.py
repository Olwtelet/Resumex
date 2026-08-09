"""Optional LLM-written titles and descriptions, with a deterministic fallback."""

from __future__ import annotations

import re

from resumex.config import OllamaConfig
from resumex.logging import get_logger
from resumex.metadata import fallback
from resumex.models import Story, VideoMetadata
from resumex.ollama import OllamaClient, OllamaUnavailable

logger = get_logger(__name__)

TITLE_PROMPT = """Write one short title for a vertical video of this story.

Rules:
- at most 10 words
- no quotation marks, no hashtags, no emoji
- describe what actually happens; do not invent details
- output the title only, nothing else

Title: {title}

Story: {body}
"""

DESCRIPTION_PROMPT = """Write a two-sentence description for a vertical video of this story.

Rules:
- two sentences, plain language, no emoji, no hashtags
- only state things that appear in the story
- output the description only, nothing else

Title: {title}

Story: {body}
"""


def generate(story: Story, config: OllamaConfig, max_title_length: int) -> VideoMetadata:
    """Ask the model for a title and description; fall back if it cannot answer."""
    client = OllamaClient(config)
    default = fallback.generate(story, max_title_length)

    try:
        title = _clean(
            client.generate(TITLE_PROMPT.format(title=story.title, body=story.body[:4000]))
        )
        description = _clean(
            client.generate(DESCRIPTION_PROMPT.format(title=story.title, body=story.body[:4000]))
        )
    except OllamaUnavailable as exc:
        logger.warning("Ollama metadata unavailable (%s); using deterministic metadata", exc)
        return default

    if not title or not description:
        logger.warning("Ollama returned empty metadata; using deterministic metadata")
        return default

    attribution = fallback.credit(story)
    if attribution:
        description = f"{description}\n\n{attribution}"

    return VideoMetadata(
        title=fallback.build_title(title, max_title_length),
        description=description[: fallback.MAX_DESCRIPTION],
        tags=default.tags,
        provider="ollama",
        source_url=story.source_url,
    )


def _clean(text: str) -> str:
    """Strip the label prefixes, quotes and markdown that small models like to add."""
    text = text.strip()
    text = re.sub(r"^(title|description)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = text.strip().strip('"').strip("'")
    return re.sub(r"[ \t]+", " ", text).strip()
