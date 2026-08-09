"""Reddit adapter tests. The HTTP layer is stubbed; nothing leaves the machine."""

from __future__ import annotations

import pytest

from resumex.config import RedditConfig
from resumex.exceptions import SourceError
from resumex.sources.reddit import RedditSource


def listing(*posts: dict) -> dict:
    return {"data": {"children": [{"data": post} for post in posts]}}


def post(**overrides) -> dict:
    base = {
        "title": "A self post",
        "selftext": "x" * 800,
        "author": "someone",
        "permalink": "/r/test/comments/abc/a_self_post/",
        "id": "abc",
        "is_self": True,
        "stickied": False,
        "over_18": False,
    }
    base.update(overrides)
    return base


def source(monkeypatch, payload, **config_overrides) -> RedditSource:
    settings = RedditConfig(enabled=True, subreddits=("test",), **config_overrides)
    adapter = RedditSource(settings)
    monkeypatch.setattr(adapter, "_fetch", lambda subreddit: payload)
    return adapter


def test_no_subreddits_configured_says_what_to_set():
    adapter = RedditSource(RedditConfig(enabled=True))
    with pytest.raises(SourceError) as exc:
        list(adapter.stories())
    assert "reddit.subreddits" in (exc.value.hint or "")


def test_self_posts_become_stories(monkeypatch):
    stories = list(source(monkeypatch, listing(post())).stories())
    assert len(stories) == 1
    assert stories[0].source == "reddit"
    assert stories[0].source_url.endswith("/r/test/comments/abc/a_self_post/")
    assert stories[0].author == "someone"


def test_link_posts_stickies_and_nsfw_are_skipped(monkeypatch):
    payload = listing(
        post(is_self=False),
        post(stickied=True),
        post(over_18=True),
        post(title="kept"),
    )
    stories = list(source(monkeypatch, payload).stories())
    assert [s.title for s in stories] == ["kept"]


def test_posts_outside_the_length_window_are_skipped(monkeypatch):
    payload = listing(post(selftext="too short"), post(selftext="x" * 9000), post(title="kept"))
    stories = list(source(monkeypatch, payload, min_chars=400, max_chars=4000).stories())
    assert [s.title for s in stories] == ["kept"]


def test_deleted_authors_become_anonymous(monkeypatch):
    stories = list(source(monkeypatch, listing(post(author="[deleted]"))).stories())
    assert stories[0].author is None


def test_a_failing_subreddit_does_not_stop_the_others(monkeypatch):
    settings = RedditConfig(enabled=True, subreddits=("broken", "working"))
    adapter = RedditSource(settings)

    def fetch(subreddit: str) -> dict:
        if subreddit == "broken":
            raise SourceError("Reddit returned HTTP 429 for r/broken.")
        return listing(post(title="from working"))

    monkeypatch.setattr(adapter, "_fetch", fetch)
    assert [s.title for s in adapter.stories()] == ["from working"]


def test_the_listing_url_carries_the_configured_options():
    adapter = RedditSource(RedditConfig(enabled=True, listing="top", time_filter="week", limit=7))
    url = adapter._url("r/test/")
    assert url.startswith("https://www.reddit.com/r/test/top.json")
    assert "limit=7" in url
    assert "t=week" in url


def test_non_top_listings_do_not_send_a_time_filter():
    adapter = RedditSource(RedditConfig(enabled=True, listing="new"))
    assert "&t=" not in adapter._url("test")


def test_the_request_limit_is_clamped_to_what_reddit_accepts():
    adapter = RedditSource(RedditConfig(enabled=True, limit=5000))
    assert "limit=100" in adapter._url("test")
