from __future__ import annotations

import wave
from pathlib import Path

import pytest

from resumex.config import Config, NarrationConfig, Paths
from resumex.exceptions import MissingDependencyError
from resumex.narration import get_narrator
from resumex.narration.base import split_into_chunks
from resumex.narration.silent import SilentNarrator


def test_short_sentences_stay_whole():
    chunks = split_into_chunks("One short line. Another short line.")
    assert chunks == ["One short line.", "Another short line."]


def test_long_sentences_are_split_on_clauses():
    text = " ".join(["word"] * 12) + ", " + " ".join(["other"] * 12) + "."
    chunks = split_into_chunks(text, max_words=18)
    assert len(chunks) == 2
    assert chunks[0].endswith(",")


def test_clauses_that_are_still_too_long_are_split_on_word_count():
    chunks = split_into_chunks(" ".join(["word"] * 40), max_words=10)
    assert all(len(chunk.split()) <= 10 for chunk in chunks)


def test_empty_text_yields_no_chunks():
    assert split_into_chunks("   \n  ") == []


def test_silent_narrator_writes_a_playable_wav(tmp_path: Path):
    result = SilentNarrator(words_per_minute=180).synthesize(
        "One two three. Four five six.", tmp_path / "n.wav"
    )
    assert result.audio_path.is_file()
    assert result.is_silent
    assert result.provider == "silent"

    with wave.open(str(result.audio_path), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == result.sample_rate
        seconds = handle.getnframes() / handle.getframerate()
    assert seconds == pytest.approx(result.duration, abs=0.05)


def test_silent_narration_timing_is_monotonic_and_paced(tmp_path: Path):
    result = SilentNarrator(words_per_minute=150).synthesize(
        "Alpha beta gamma delta. Epsilon zeta eta theta.", tmp_path / "n.wav"
    )
    assert len(result.chunks) == 2
    assert result.chunks[0].end <= result.chunks[1].start
    assert result.duration == result.chunks[-1].end


def test_slower_speech_makes_a_longer_file(tmp_path: Path):
    text = "One two three four five six seven eight."
    fast = SilentNarrator(words_per_minute=240).synthesize(text, tmp_path / "fast.wav")
    slow = SilentNarrator(words_per_minute=90).synthesize(text, tmp_path / "slow.wav")
    assert slow.duration > fast.duration


def test_auto_falls_back_to_silence_when_kokoro_is_absent(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("resumex.narration.kokoro_module.is_available", lambda: False)
    config = Config(paths=Paths(workspace=tmp_path))
    assert isinstance(get_narrator(config), SilentNarrator)


def test_requesting_kokoro_without_it_installed_says_how_to_install(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("resumex.narration.kokoro_module.is_available", lambda: False)
    config = Config(paths=Paths(workspace=tmp_path), narration=NarrationConfig(provider="kokoro"))
    with pytest.raises(MissingDependencyError) as exc:
        get_narrator(config)
    assert "resumex[tts]" in (exc.value.hint or "")


def test_force_silent_wins_over_the_configured_provider(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("resumex.narration.kokoro_module.is_available", lambda: True)
    config = Config(paths=Paths(workspace=tmp_path), narration=NarrationConfig(provider="kokoro"))
    assert isinstance(get_narrator(config, force_silent=True), SilentNarrator)
