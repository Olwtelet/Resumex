from __future__ import annotations

from pathlib import Path

from resumex.models import RenderResult, Story
from resumex.state import StateStore
from resumex.state.store import open_store


def make_render(tmp_path: Path, story: Story, name: str = "a.mp4") -> RenderResult:
    return RenderResult(
        path=tmp_path / name,
        width=1080,
        height=1920,
        duration=21.5,
        has_audio=True,
        story_id=story.id,
    )


def test_database_is_created_with_its_parent(tmp_path: Path):
    database = tmp_path / "nested" / "state.db"
    with StateStore(database):
        pass
    assert database.is_file()


def test_recording_a_story_twice_is_idempotent(tmp_path: Path, story: Story):
    with StateStore(tmp_path / "s.db") as store:
        store.record_story(story)
        store.record_story(story)
        assert store.stats().stories == 1
        assert store.has_story(story.id)


def test_source_urls_are_searchable(tmp_path: Path):
    story = Story(title="T", body="B", source_url="https://example.com/post")
    with StateStore(tmp_path / "s.db") as store:
        store.record_story(story)
        assert store.has_source_url("https://example.com/post")
        assert not store.has_source_url("https://example.com/other")


def test_renders_are_linked_to_their_story(tmp_path: Path, story: Story):
    with StateStore(tmp_path / "s.db") as store:
        store.record_story(story)
        assert not store.has_render_for_story(story.id)
        store.record_render(make_render(tmp_path, story))
        assert store.has_render_for_story(story.id)


def test_re_rendering_the_same_path_updates_rather_than_duplicates(tmp_path: Path, story: Story):
    with StateStore(tmp_path / "s.db") as store:
        store.record_story(story)
        store.record_render(make_render(tmp_path, story))
        store.record_render(make_render(tmp_path, story))
        assert store.stats().renders == 1


def test_uploads_are_tracked_per_file(tmp_path: Path, story: Story):
    video = tmp_path / "a.mp4"
    with StateStore(tmp_path / "s.db") as store:
        store.record_story(story)
        store.record_render(make_render(tmp_path, story))
        assert not store.is_uploaded(video)
        store.record_upload(video, "abc123", "https://youtu.be/abc123", "private")
        assert store.is_uploaded(video)
        assert store.stats().uploads == 1


def test_recent_renders_are_newest_first(tmp_path: Path, story: Story):
    with StateStore(tmp_path / "s.db") as store:
        store.record_story(story)
        store.record_render(make_render(tmp_path, story, "first.mp4"))
        store.record_render(make_render(tmp_path, story, "second.mp4"))
        rows = store.recent_renders(5)
    assert [Path(row["path"]).name for row in rows] == ["second.mp4", "first.mp4"]
    assert rows[0]["title"] == story.title


def test_state_survives_reopening(tmp_path: Path, story: Story):
    database = tmp_path / "s.db"
    with StateStore(database) as store:
        store.record_story(story)
    with StateStore(database) as store:
        assert store.has_story(story.id)


def test_open_store_closes_on_the_way_out(tmp_path: Path, story: Story):
    with open_store(tmp_path / "s.db") as store:
        store.record_story(story)
    assert (tmp_path / "s.db").is_file()
