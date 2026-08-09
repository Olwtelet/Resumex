from __future__ import annotations

import json
from pathlib import Path

import pytest

from resumex.exceptions import ContentError
from resumex.sources.local import LocalSource, load_file


def test_markdown_heading_becomes_the_title(tmp_path: Path):
    path = tmp_path / "s.md"
    path.write_text("# The Keeper\n\nBody line one.\n\nBody line two.\n", encoding="utf-8")
    story = load_file(path)[0]
    assert story.title == "The Keeper"
    assert story.body.startswith("Body line one.")
    assert story.source == "local"


def test_markdown_without_a_heading_uses_the_first_line(tmp_path: Path):
    path = tmp_path / "s.md"
    path.write_text("\n\nJust a first line\nand the rest.\n", encoding="utf-8")
    story = load_file(path)[0]
    assert story.title == "Just a first line"
    assert story.body == "and the rest."


def test_plain_text_uses_the_first_non_empty_line(tmp_path: Path):
    path = tmp_path / "s.txt"
    path.write_text("\nMy title\n\nThe body.\n", encoding="utf-8")
    story = load_file(path)[0]
    assert story.title == "My title"
    assert story.body == "The body."


def test_json_object_maps_onto_the_documented_schema(tmp_path: Path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "title": "My story",
                "body": "Story content...",
                "author": "someone",
                "source_url": "https://example.com/post",
            }
        ),
        encoding="utf-8",
    )
    story = load_file(path)[0]
    assert (story.title, story.author) == ("My story", "someone")
    assert story.source_url == "https://example.com/post"


def test_json_only_requires_title_and_body(tmp_path: Path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"title": "T", "body": "B"}), encoding="utf-8")
    story = load_file(path)[0]
    assert story.author is None
    assert story.source_url is None


def test_json_array_yields_every_story(tmp_path: Path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps([{"title": "One", "body": "A"}, {"title": "Two", "body": "B"}]),
        encoding="utf-8",
    )
    assert [s.title for s in load_file(path)] == ["One", "Two"]


def test_json_missing_a_required_field_names_it(tmp_path: Path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"title": "Only a title"}), encoding="utf-8")
    with pytest.raises(ContentError, match="body"):
        load_file(path)


def test_invalid_json_is_reported_as_such(tmp_path: Path):
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContentError, match="not valid JSON"):
        load_file(path)


def test_unsupported_extension_lists_what_is_supported(tmp_path: Path):
    path = tmp_path / "s.docx"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ContentError) as exc:
        load_file(path)
    assert ".txt" in (exc.value.hint or "")


def test_missing_file_is_reported(tmp_path: Path):
    with pytest.raises(ContentError, match="not found"):
        load_file(tmp_path / "absent.md")


def test_directory_source_reads_every_supported_file(tmp_path: Path):
    (tmp_path / "a.md").write_text("# A\n\nbody a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("B\n\nbody b\n", encoding="utf-8")
    (tmp_path / "ignore.png").write_bytes(b"\x89PNG")
    titles = sorted(story.title for story in LocalSource(tmp_path).stories())
    assert titles == ["A", "B"]


def test_empty_directory_explains_what_to_add(tmp_path: Path):
    with pytest.raises(ContentError, match="No story files"):
        list(LocalSource(tmp_path).stories())
