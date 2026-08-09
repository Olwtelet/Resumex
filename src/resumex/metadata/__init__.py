"""Publishing metadata. Deterministic by default, LLM-assisted if you ask for it."""

from __future__ import annotations

from resumex.config import Config
from resumex.metadata import fallback, ollama
from resumex.models import Story, VideoMetadata

__all__ = ["fallback", "ollama", "generate_metadata"]


def generate_metadata(story: Story, config: Config) -> VideoMetadata:
    """Generate metadata using the configured provider."""
    limit = config.metadata.max_title_length
    if config.metadata.provider == "ollama":
        return ollama.generate(story, config.ollama, limit)
    return fallback.generate(story, limit)
