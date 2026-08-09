"""Local text-to-speech through the official Kokoro package.

Kokoro already hands back one audio segment per chunk of text it speaks, so we
take the timing straight from those segment lengths. There is no transcription
step: the pipeline never has to listen to its own speech to find out when a
word was said.

Model weights are downloaded by Kokoro itself on first use and cached under the
usual Hugging Face cache directory. Nothing is stored in this repository.
"""

from __future__ import annotations

from pathlib import Path

from resumex.exceptions import MissingDependencyError, NarrationError
from resumex.logging import get_logger
from resumex.models import NarrationChunk, NarrationResult
from resumex.narration.base import Narrator

logger = get_logger(__name__)

SAMPLE_RATE = 24_000
REPO_ID = "hexgrad/Kokoro-82M"

INSTALL_HINT = 'Install the speech extra:  pip install "resumex[tts]"'


def is_available() -> bool:
    """True if the optional TTS extra is importable. Never raises."""
    from importlib.util import find_spec

    try:
        return all(find_spec(name) is not None for name in ("kokoro", "soundfile", "numpy"))
    except (ImportError, ValueError):
        return False


class KokoroNarrator(Narrator):
    """Wraps ``kokoro.KPipeline``. The model is loaded once and reused."""

    name = "kokoro"

    def __init__(self, voice: str = "af_heart", lang_code: str = "a", speed: float = 1.0) -> None:
        self.voice = voice
        self.lang_code = lang_code
        self.speed = speed
        self._pipeline = None

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise MissingDependencyError(
                "Kokoro text-to-speech is not installed.", hint=INSTALL_HINT
            ) from exc

        logger.debug("loading Kokoro pipeline (lang_code=%s)", self.lang_code)
        self._pipeline = KPipeline(lang_code=self.lang_code, repo_id=REPO_ID)
        return self._pipeline

    def synthesize(self, text: str, destination: Path) -> NarrationResult:
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise MissingDependencyError(
                "Kokoro text-to-speech is not installed.", hint=INSTALL_HINT
            ) from exc

        pipeline = self._load()
        segments: list = []
        chunks: list[NarrationChunk] = []
        cursor = 0.0

        try:
            for graphemes, _phonemes, audio in pipeline(text, voice=self.voice, speed=self.speed):
                samples = np.asarray(audio, dtype="float32").reshape(-1)
                if samples.size == 0:
                    continue
                seconds = samples.size / SAMPLE_RATE
                segments.append(samples)
                chunks.append(
                    NarrationChunk(text=str(graphemes).strip(), start=cursor, end=cursor + seconds)
                )
                cursor += seconds
        except Exception as exc:  # noqa: BLE001 — third-party failures vary too much to enumerate
            raise NarrationError(
                f"Kokoro failed to synthesize speech: {exc}",
                hint=(
                    "The first run downloads the model, which needs network access. "
                    "Run `resumex demo` to check the rest of the pipeline without TTS."
                ),
            ) from exc

        if not segments:
            raise NarrationError("Kokoro produced no audio for this text.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(destination), np.concatenate(segments), SAMPLE_RATE)

        return NarrationResult(
            audio_path=destination,
            duration=cursor,
            chunks=tuple(chunks),
            provider=self.name,
            voice=self.voice,
            sample_rate=SAMPLE_RATE,
        )

    def close(self) -> None:
        self._pipeline = None
