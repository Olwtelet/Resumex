"""Shared fixtures, plus a hard guarantee that the default suite is offline."""

from __future__ import annotations

import shutil
import socket
from pathlib import Path

import pytest

from resumex.config import Config, Paths, RenderConfig
from resumex.models import NarrationChunk, Story


class NetworkBlocked(RuntimeError):
    """Raised if a test tries to open a socket."""


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly rather than silently reaching the internet during tests."""

    def blocked(*args: object, **kwargs: object):
        raise NetworkBlocked("tests must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    paths = Paths(workspace=tmp_path)
    paths.ensure()
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> Config:
    return Config(paths=Paths(workspace=workspace))


@pytest.fixture
def fast_config(workspace: Path) -> Config:
    """A small, quick render profile for tests that actually invoke FFmpeg."""
    return Config(
        paths=Paths(workspace=workspace),
        render=RenderConfig(width=270, height=480, fps=12, preset="ultrafast", font_size=28),
    )


@pytest.fixture
def story() -> Story:
    return Story(
        title="A note in a library book",
        body=(
            "I found a folded note tucked into a book about tide tables.\n\n"
            "It said the pier is still there, and it was dated eleven years ago.\n\n"
            "I went to look. Someone had left a fresh note under the same bench."
        ),
        author="anon",
    )


@pytest.fixture
def chunks() -> tuple[NarrationChunk, ...]:
    return (
        NarrationChunk(text="The pier is still there.", start=0.0, end=2.0),
        NarrationChunk(text="Someone left a fresh note.", start=2.2, end=4.4),
    )


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


requires_ffmpeg = pytest.mark.skipif(
    not ffmpeg_available(), reason="FFmpeg and ffprobe are not on PATH"
)
