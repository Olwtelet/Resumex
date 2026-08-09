"""Speech synthesis providers."""

from __future__ import annotations

from resumex.config import Config
from resumex.exceptions import MissingDependencyError
from resumex.logging import get_logger
from resumex.narration import kokoro as kokoro_module
from resumex.narration.base import Narrator, split_into_chunks
from resumex.narration.kokoro import KokoroNarrator
from resumex.narration.silent import SilentNarrator

logger = get_logger(__name__)

__all__ = [
    "KokoroNarrator",
    "Narrator",
    "SilentNarrator",
    "get_narrator",
    "split_into_chunks",
]


def get_narrator(config: Config, *, force_silent: bool = False) -> Narrator:
    """Build the configured narrator.

    ``auto`` uses Kokoro when the TTS extra is installed and falls back to the
    silent narrator otherwise, so a base install still renders a video.
    """
    if force_silent:
        return SilentNarrator(config.narration.words_per_minute)

    provider = config.narration.provider
    if provider == "silent":
        return SilentNarrator(config.narration.words_per_minute)

    if provider == "kokoro":
        if not kokoro_module.is_available():
            raise MissingDependencyError(
                "narration.provider is 'kokoro' but the TTS extra is not installed.",
                hint=kokoro_module.INSTALL_HINT,
            )
        return _kokoro(config)

    if kokoro_module.is_available():
        return _kokoro(config)

    logger.info("Kokoro is not installed; narrating silently")
    return SilentNarrator(config.narration.words_per_minute)


def _kokoro(config: Config) -> KokoroNarrator:
    return KokoroNarrator(
        voice=config.narration.voice,
        lang_code=config.narration.lang_code,
        speed=config.narration.speed,
    )
