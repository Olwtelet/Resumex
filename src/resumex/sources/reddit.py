"""Reddit as an optional content adapter.

This uses Reddit's public JSON listings over plain HTTP with an honest
User-Agent. There is no browser automation and no attempt to look like one:
if Reddit declines the request, Resumex says so and everything else keeps
working.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

from resumex.config import RedditConfig
from resumex.exceptions import SourceError
from resumex.logging import get_logger
from resumex.models import Story
from resumex.sources.base import Source

logger = get_logger(__name__)

BASE_URL = "https://www.reddit.com"


class RedditSource(Source):
    """Reads self-post text from public subreddit listings."""

    name = "reddit"

    def __init__(self, config: RedditConfig) -> None:
        self.config = config

    def stories(self) -> Iterator[Story]:
        if not self.config.subreddits:
            raise SourceError(
                "No subreddits configured.",
                hint="Set reddit.subreddits in resumex.toml, e.g. subreddits = [\"nosleep\"].",
            )

        for subreddit in self.config.subreddits:
            try:
                payload = self._fetch(subreddit)
            except SourceError as exc:
                logger.warning("skipping r/%s: %s", subreddit, exc.message)
                continue
            yield from self._parse(payload, subreddit)

    def _url(self, subreddit: str) -> str:
        name = subreddit.strip().removeprefix("r/").strip("/")
        query = f"limit={max(1, min(100, self.config.limit))}"
        if self.config.listing == "top":
            query += f"&t={self.config.time_filter}"
        return f"{BASE_URL}/r/{name}/{self.config.listing}.json?{query}"

    def _fetch(self, subreddit: str) -> dict:
        url = self._url(subreddit)
        request = urllib.request.Request(url, headers={"User-Agent": self.config.user_agent})
        logger.debug("GET %s", url)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise SourceError(
                f"Reddit returned HTTP {exc.code} for r/{subreddit}.",
                hint=(
                    "Reddit rate-limits and blocks anonymous traffic. Wait and retry, or "
                    "use local files instead: resumex render my-story.txt"
                ),
            ) from exc
        except urllib.error.URLError as exc:
            raise SourceError(f"Could not reach Reddit: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SourceError(f"Reddit returned something that is not JSON: {exc}") from exc

    def _parse(self, payload: dict, subreddit: str) -> Iterator[Story]:
        children = payload.get("data", {}).get("children", [])
        for child in children:
            data = child.get("data", {})
            if data.get("stickied") or data.get("over_18") or not data.get("is_self"):
                continue

            body = str(data.get("selftext") or "").strip()
            title = str(data.get("title") or "").strip()
            if not body or not title:
                continue
            if not self.config.min_chars <= len(body) <= self.config.max_chars:
                continue

            permalink = data.get("permalink")
            yield Story(
                title=title,
                body=body,
                author=_author(data),
                source="reddit",
                source_url=f"{BASE_URL}{permalink}" if permalink else None,
                source_id=str(data.get("id") or "") or None,
            )
        logger.debug("r/%s yielded %d candidate posts", subreddit, len(children))


def _author(data: dict) -> str | None:
    author = str(data.get("author") or "").strip()
    return author if author and author != "[deleted]" else None
