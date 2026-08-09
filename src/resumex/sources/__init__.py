"""Where stories come from. Local files are the default; everything else is opt-in."""

from __future__ import annotations

from pathlib import Path

from resumex.config import Config
from resumex.exceptions import NotConfiguredError
from resumex.sources.base import Source
from resumex.sources.local import LocalSource, load_file
from resumex.sources.reddit import RedditSource

__all__ = ["LocalSource", "RedditSource", "Source", "load_file", "get_source"]


def get_source(name: str, config: Config, path: Path | None = None) -> Source:
    """Build a source by name. ``local`` needs a path; ``reddit`` needs config."""
    if name == "local":
        target = path or config.paths.stories
        return LocalSource(target)
    if name == "reddit":
        if not config.reddit.enabled:
            raise NotConfiguredError(
                "The Reddit source is disabled.",
                hint="Set enabled = true and a subreddits list under [reddit] in resumex.toml.",
            )
        return RedditSource(config.reddit)
    raise NotConfiguredError(f"Unknown source: {name!r}", hint="Available sources: local, reddit.")
