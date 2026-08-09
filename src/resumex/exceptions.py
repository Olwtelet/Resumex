"""Error types for Resumex.

Every error carries a human-readable message and, where we can be useful, a
``hint`` telling the user what to actually do about it. The CLI prints both and
exits with the error's ``exit_code`` — anything else bubbles up as a traceback
only when ``--verbose`` is set.
"""

from __future__ import annotations


class ResumexError(Exception):
    """Base class for every error Resumex raises on purpose."""

    exit_code = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ConfigError(ResumexError):
    """The configuration file is malformed or holds an impossible value."""

    exit_code = 3


class MissingDependencyError(ResumexError):
    """Something Resumex needs is not installed — FFmpeg, or an optional extra."""

    exit_code = 4


class NotConfiguredError(ResumexError):
    """An optional integration was asked for but has not been set up."""

    exit_code = 5


class ContentError(ResumexError):
    """The input could not be turned into a usable story."""

    exit_code = 6


class NarrationError(ResumexError):
    """Speech synthesis failed."""

    exit_code = 7


class RenderError(ResumexError):
    """Video composition failed."""

    exit_code = 8


class UploadError(ResumexError):
    """Publishing failed."""

    exit_code = 9


class SourceError(ResumexError):
    """A content source was unreachable or returned nothing usable."""

    exit_code = 10
