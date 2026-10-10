"""Fetch recent articles from the RSS feeds listed in `feeds.json`."""
import asyncio
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import httpx

logger = logging.getLogger(__name__)

FEEDS_FILE = Path(__file__).with_name("feeds.json")
MAX_PER_FEED = 10  # newest first, so one busy feed cannot crowd out the rest of the small context window
SUMMARY_CHARS = 200
FETCH_TIMEOUT = 15.0


@dataclass(frozen=True)
class Article:
    title: str
    link: str
    summary: str
    published: datetime
    feed: str


def load_feeds(path: Path = FEEDS_FILE) -> list[str]:
    feeds = json.loads(path.read_text())
    if not isinstance(feeds, list) or not all(isinstance(f, str) and f for f in feeds):
        raise ValueError(f"{path.name} must be a JSON list of feed URLs")
    return feeds


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def parse_feed(content: str, feed: str, since: datetime) -> list[Article]:
    """Articles newer than `since`. Entries with no title or no date are skipped."""
    articles = []
    for entry in feedparser.parse(content).entries:
        title = _clean(entry.get("title", ""))
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not title or not stamp:
            continue
        published = datetime(*stamp[:6], tzinfo=timezone.utc)  # feedparser normalizes these to UTC
        if published < since:
            continue
        articles.append(
            Article(title, entry.get("link", ""), _clean(entry.get("summary", ""))[:SUMMARY_CHARS], published, feed)
        )
    return sorted(articles, key=lambda a: a.published, reverse=True)[:MAX_PER_FEED]


async def _fetch_one(client: httpx.AsyncClient, feed: str, since: datetime) -> list[Article]:
    try:
        response = await client.get(feed)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("skipping feed %s: %s", feed, e)
        return []
    return parse_feed(response.text, feed, since)


async def fetch_articles(
    feeds: list[str] | None = None,
    hours: int = 24,
    now: datetime | None = None,
    transport: httpx.AsyncBaseTransport | None = None,  # test seam
) -> list[Article]:
    """Recent, de-duplicated articles from all feeds, newest first. Unreachable feeds are skipped."""
    feeds = load_feeds() if feeds is None else feeds
    since = (now or datetime.now(timezone.utc)) - timedelta(hours=hours)
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True, transport=transport) as client:
        per_feed = await asyncio.gather(*(_fetch_one(client, f, since) for f in feeds))
    seen, unique = set(), []
    for article in sorted((a for group in per_feed for a in group), key=lambda a: a.published, reverse=True):
        key = article.link or article.title.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(article)
    return unique


def format_for_agent(articles: list[Article]) -> tuple[str, list[str]]:
    """Plain-text article list for the news agent, plus the feeds that contributed (the briefing's sources)."""
    lines = [
        f"- {a.title} ({urlparse(a.feed).netloc})" + (f": {a.summary}" if a.summary else "") for a in articles
    ]
    sources = list(dict.fromkeys(a.feed for a in articles))
    return "\n".join(lines), sources
