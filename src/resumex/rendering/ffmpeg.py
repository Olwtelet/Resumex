"""The only place in Resumex that talks to FFmpeg.

Commands are always built as argument lists and run without a shell, so nothing
in a story title or file path can ever be interpreted as a command.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from resumex.config import ToolsConfig
from resumex.exceptions import MissingDependencyError, RenderError
from resumex.logging import get_logger

logger = get_logger(__name__)

INSTALL_HINT = (
    "Install FFmpeg, then run `resumex doctor`.\n"
    "  macOS    brew install ffmpeg\n"
    "  Debian   sudo apt install ffmpeg\n"
    "  Windows  winget install Gyan.FFmpeg\n"
    "Or set the path explicitly with RESUMEX_FFMPEG / RESUMEX_FFPROBE."
)


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """What ffprobe tells us about a media file."""

    width: int
    height: int
    duration: float
    video_codec: str | None
    audio_codec: str | None

    @property
    def has_video(self) -> bool:
        return self.video_codec is not None

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None


def resolve(executable: str, *, label: str = "FFmpeg") -> str:
    """Find an executable, or explain how to install it."""
    found = shutil.which(executable)
    if found:
        return found
    if Path(executable).is_file():
        return executable
    raise MissingDependencyError(f"{label} was not found on PATH.", hint=INSTALL_HINT)


def available(tools: ToolsConfig) -> tuple[bool, bool]:
    """``(ffmpeg_found, ffprobe_found)`` — for `resumex doctor`. Never raises."""

    def check(name: str) -> bool:
        return shutil.which(name) is not None or Path(name).is_file()

    return check(tools.ffmpeg), check(tools.ffprobe)


def version(executable: str) -> str | None:
    """The first line of ``-version``, or ``None`` if it cannot be run."""
    try:
        completed = subprocess.run(
            [executable, "-version"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    first = completed.stdout.splitlines()[0] if completed.stdout else ""
    return first.strip() or None


def run(command: list[str], *, description: str, timeout: float | None = None) -> str:
    """Run an FFmpeg command, raising :class:`RenderError` with useful stderr."""
    logger.debug("running: %s", " ".join(command))
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"{command[0]} could not be executed.", hint=INSTALL_HINT) from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"{description} timed out after {timeout:.0f}s.") from exc

    if completed.returncode != 0:
        raise RenderError(
            f"{description} failed (exit {completed.returncode}).",
            hint=_tail(completed.stderr),
        )
    return completed.stderr


def probe(path: Path, ffprobe: str = "ffprobe") -> MediaInfo:
    """Read stream metadata from a media file."""
    executable = resolve(ffprobe, label="ffprobe")
    command = [
        executable,
        "-v", "error",
        "-show_entries", "stream=width,height,codec_type,codec_name:format=duration",
        "-of", "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError(f"Could not probe {path}: {exc}") from exc

    if completed.returncode != 0:
        raise RenderError(
            f"ffprobe could not read {path.name}.", hint=_tail(completed.stderr)
        )

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RenderError(f"ffprobe returned unreadable output for {path.name}: {exc}") from exc

    width = height = 0
    video_codec = audio_codec = None
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video" and video_codec is None:
            video_codec = stream.get("codec_name")
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        elif stream.get("codec_type") == "audio" and audio_codec is None:
            audio_codec = stream.get("codec_name")

    try:
        duration = float(payload.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


def _tail(stderr: str, lines: int = 8) -> str:
    text = (stderr or "").strip()
    if not text:
        return "FFmpeg produced no error output."
    return "\n".join(text.splitlines()[-lines:])
