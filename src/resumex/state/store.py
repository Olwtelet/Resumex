"""SQLite-backed state.

Replaces the append-only ``.txt`` history files the project used to keep. One
file, three tables, transactional, and safe to delete if you want a clean slate.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from resumex.models import RenderResult, Story

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL,
    source_url  TEXT,
    word_count  INTEGER NOT NULL DEFAULT 0,
    seen_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS renders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id    TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    path        TEXT NOT NULL UNIQUE,
    duration    REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uploads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    render_path TEXT NOT NULL,
    video_id    TEXT NOT NULL,
    url         TEXT NOT NULL,
    privacy     TEXT NOT NULL,
    uploaded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_renders_story ON renders(story_id);
CREATE INDEX IF NOT EXISTS idx_stories_url ON stories(source_url);
"""


@dataclass(frozen=True, slots=True)
class Stats:
    stories: int
    renders: int
    uploads: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StateStore:
    """Small wrapper over a SQLite file. Use as a context manager."""

    def __init__(self, database: Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        with self._connection:
            self._connection.executescript(_SCHEMA)
            self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> StateStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- stories ---------------------------------------------------------

    def record_story(self, story: Story) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO stories (id, title, source, source_url, word_count, seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                (
                    story.id,
                    story.title,
                    story.source,
                    story.source_url,
                    story.word_count,
                    _now(),
                ),
            )

    def has_story(self, story_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM stories WHERE id = ? LIMIT 1", (story_id,)
        ).fetchone()
        return row is not None

    def has_source_url(self, url: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM stories WHERE source_url = ? LIMIT 1", (url,)
        ).fetchone()
        return row is not None

    # -- renders ---------------------------------------------------------

    def record_render(self, result: RenderResult) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO renders (story_id, path, duration, created_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET duration = excluded.duration",
                (result.story_id, str(result.path), result.duration, _now()),
            )

    def has_render_for_story(self, story_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM renders WHERE story_id = ? LIMIT 1", (story_id,)
        ).fetchone()
        return row is not None

    def recent_renders(self, limit: int = 10) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                "SELECT r.path, r.duration, r.created_at, s.title "
                "FROM renders r LEFT JOIN stories s ON s.id = r.story_id "
                "ORDER BY r.id DESC LIMIT ?",
                (limit,),
            )
        )

    # -- uploads ---------------------------------------------------------

    def record_upload(self, render_path: Path, video_id: str, url: str, privacy: str) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO uploads (render_path, video_id, url, privacy, uploaded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(render_path), video_id, url, privacy, _now()),
            )

    def is_uploaded(self, render_path: Path) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM uploads WHERE render_path = ? LIMIT 1", (str(render_path),)
        ).fetchone()
        return row is not None

    # -- reporting -------------------------------------------------------

    def stats(self) -> Stats:
        def count(table: str) -> int:
            return int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

        return Stats(stories=count("stories"), renders=count("renders"), uploads=count("uploads"))


@contextmanager
def open_store(database: Path) -> Iterator[StateStore]:
    store = StateStore(database)
    try:
        yield store
    finally:
        store.close()
