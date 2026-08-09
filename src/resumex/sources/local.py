"""Local files as a first-class content source.

Supported inputs:

``.txt``   first non-empty line is the title, the rest is the body
``.md``    the first ``# Heading`` is the title, the rest is the body
``.json``  ``{"title": ..., "body": ..., "author": ?, "source_url": ?}``
           or a list of such objects
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from resumex.exceptions import ContentError
from resumex.models import Story
from resumex.sources.base import Source

SUPPORTED_SUFFIXES = (".txt", ".md", ".markdown", ".json")


class LocalSource(Source):
    """Reads stories from a file or a directory of files."""

    name = "local"

    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()

    def stories(self) -> Iterator[Story]:
        if self.path.is_dir():
            files = sorted(
                p for p in self.path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            )
            if not files:
                raise ContentError(
                    f"No story files found in {self.path}",
                    hint=f"Add a .txt, .md or .json file. Supported: {', '.join(SUPPORTED_SUFFIXES)}",
                )
            for file in files:
                yield from load_file(file)
            return

        yield from load_file(self.path)


def load_file(path: Path) -> list[Story]:
    """Parse one file into one or more stories."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ContentError(
            f"Story file not found: {path}",
            hint="Pass a path to a .txt, .md or .json file, or a directory of them.",
        )

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ContentError(
            f"Unsupported story format: {path.suffix or '(no extension)'}",
            hint=f"Supported formats are {', '.join(SUPPORTED_SUFFIXES)}.",
        )

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ContentError(f"{path} is not valid UTF-8 text: {exc}") from exc
    except OSError as exc:
        raise ContentError(f"Could not read {path}: {exc}") from exc

    if suffix == ".json":
        return _parse_json(text, path)
    if suffix in (".md", ".markdown"):
        return [_parse_markdown(text, path)]
    return [_parse_plain_text(text, path)]


def _story(
    title: str,
    body: str,
    path: Path,
    author: str | None = None,
    source_url: str | None = None,
) -> Story:
    try:
        return Story(
            title=title,
            body=body,
            author=author,
            source="local",
            source_url=source_url,
            source_id=str(path),
        )
    except ValueError as exc:
        raise ContentError(
            f"{path} does not contain a usable story: {exc}",
            hint="A story needs a title line and at least one line of body text.",
        ) from exc


def _parse_json(text: str, path: Path) -> list[Story]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContentError(f"{path} is not valid JSON: {exc}") from exc

    entries = data if isinstance(data, list) else [data]
    stories: list[Story] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ContentError(
                f"{path}: entry {index} is a {type(entry).__name__}, expected an object",
                hint='Each entry needs at least {"title": "...", "body": "..."}.',
            )
        missing = [key for key in ("title", "body") if not str(entry.get(key, "")).strip()]
        if missing:
            raise ContentError(
                f"{path}: entry {index} is missing required field(s): {', '.join(missing)}",
                hint='Minimum schema: {"title": "My story", "body": "Story content..."}',
            )
        stories.append(
            _story(
                title=str(entry["title"]),
                body=str(entry["body"]),
                path=path,
                author=_optional_str(entry.get("author")),
                source_url=_optional_str(entry.get("source_url")),
            )
        )
    return stories


def _optional_str(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _parse_markdown(text: str, path: Path) -> Story:
    lines = text.splitlines()
    title = ""
    body_start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            body_start = index + 1
        else:
            title = stripped
            body_start = index + 1
        break

    body = "\n".join(lines[body_start:]).strip()
    return _story(title=title, body=body, path=path)


def _parse_plain_text(text: str, path: Path) -> Story:
    lines = text.splitlines()
    title = ""
    body_start = 0
    for index, line in enumerate(lines):
        if line.strip():
            title = line.strip()
            body_start = index + 1
            break

    body = "\n".join(lines[body_start:]).strip()
    return _story(title=title, body=body, path=path)
