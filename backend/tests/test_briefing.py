import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.crud.schemas.news import NewsCreate
from backend.services.news import briefing, news
from backend.services.news.briefing import BriefingExists
from backend.tests.conftest import TestSession

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def rfc(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def rss(*items) -> str:
    body = "".join(
        f"<item><title>{t}</title><link>{link}</link><description>{d}</description>"
        + (f"<pubDate>{rfc(p)}</pubDate>" if p else "")
        + "</item>"
        for t, link, d, p in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>f</title>{body}</channel></rss>'


def hours_ago(h):
    return NOW - timedelta(hours=h)


# feeds config

def test_default_feed_list_is_valid():
    feeds = news.load_feeds()
    assert feeds and all(f.startswith("http") for f in feeds)


@pytest.mark.parametrize("content", ['{"a": 1}', '[1, 2]', '[""]'])
def test_load_feeds_rejects_bad_config(tmp_path, content):
    path = tmp_path / "feeds.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        news.load_feeds(path)


# parsing

def test_parse_feed_keeps_recent_dated_titled_items_newest_first():
    content = rss(
        ("old", "https://x/old", "d", hours_ago(30)),
        ("fresh", "https://x/fresh", "d", hours_ago(2)),
        ("fresher", "https://x/fresher", "d", hours_ago(1)),
        ("undated", "https://x/undated", "d", None),
        ("", "https://x/untitled", "d", hours_ago(1)),
    )
    articles = news.parse_feed(content, "https://x/feed", NOW - timedelta(hours=24))
    assert [a.title for a in articles] == ["fresher", "fresh"]


def test_parse_feed_strips_html_and_truncates_summary():
    content = rss(("t", "https://x/1", "&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt; &amp;amp; more&lt;/p&gt;" + " z" * 400, hours_ago(1)))
    (a,) = news.parse_feed(content, "f", NOW - timedelta(hours=24))
    assert a.summary.startswith("Hello world & more")
    assert "<" not in a.summary and len(a.summary) <= news.SUMMARY_CHARS


def test_parse_feed_caps_items_per_feed():
    content = rss(*[(f"t{i}", f"https://x/{i}", "d", hours_ago(1 + i / 100)) for i in range(25)])
    assert len(news.parse_feed(content, "f", NOW - timedelta(hours=24))) == news.MAX_PER_FEED


def test_parse_feed_garbage_gives_nothing():
    assert news.parse_feed("not xml at all", "f", NOW - timedelta(hours=24)) == []
    assert news.parse_feed("", "f", NOW - timedelta(hours=24)) == []


# fetching

def transport(routes):
    def handler(request: httpx.Request) -> httpx.Response:
        result = routes[str(request.url)]
        if isinstance(result, Exception):
            raise result
        return result

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_skips_broken_feeds_and_dedupes():
    shared = ("same story", "https://x/same", "d", hours_ago(3))
    routes = {
        "https://a/feed": httpx.Response(200, text=rss(shared, ("a only", "https://a/1", "d", hours_ago(1)))),
        "https://b/feed": httpx.Response(200, text=rss(shared)),
        "https://c/feed": httpx.Response(500),
        "https://d/feed": httpx.ConnectError("down"),
    }
    articles = await news.fetch_articles(list(routes), now=NOW, transport=transport(routes))
    assert [a.title for a in articles] == ["a only", "same story"]


@pytest.mark.asyncio
async def test_fetch_with_all_feeds_failing_or_no_feeds_is_empty():
    routes = {"https://a/feed": httpx.Response(404)}
    assert await news.fetch_articles(list(routes), now=NOW, transport=transport(routes)) == []
    assert await news.fetch_articles([], now=NOW, transport=transport({})) == []


def test_format_for_agent_lists_articles_and_unique_sources():
    a = news.Article("One", "l1", "about one", NOW, "https://a.example/feed")
    b = news.Article("Two", "l2", "", NOW, "https://a.example/feed")
    text, sources = news.format_for_agent([a, b])
    assert text == "- One (a.example): about one\n- Two (a.example)"
    assert sources == ["https://a.example/feed"]


# refresh endpoint

ARTICLE = news.Article("Big story", "https://x/1", "details", NOW, "https://x/feed")


class Spy:
    def __init__(self, monkeypatch, articles=(ARTICLE,), summary=None, exc=None):
        self.fetched = self.summarized = 0
        self.summary, self.exc = summary or NewsCreate(title="Briefing", summary="Things happened."), exc

        async def fetch():
            self.fetched += 1
            return list(articles)

        async def summarize(text, sources):
            self.summarized += 1
            self.text = text
            if self.exc:
                raise self.exc
            return self.summary.model_copy(update={"sources": sources})

        monkeypatch.setattr(briefing, "fetch_articles", fetch)
        monkeypatch.setattr(briefing, "summarize_news", summarize)


def test_refresh_creates_todays_briefing(client, monkeypatch):
    spy = Spy(monkeypatch)
    r = client.post("/news/refresh")
    assert r.status_code == 201
    assert r.json()["title"] == "Briefing" and r.json()["sources"] == ["https://x/feed"]
    assert "Big story" in spy.text
    assert [n["id"] for n in client.get("/news/today").json()] == [r.json()["id"]]


def test_refresh_twice_returns_409_and_does_no_work(client, monkeypatch):
    spy = Spy(monkeypatch)
    assert client.post("/news/refresh").status_code == 201
    r = client.post("/news/refresh")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert (spy.fetched, spy.summarized) == (1, 1)
    assert len(client.get("/news/today").json()) == 1


def test_refresh_replace_swaps_todays_briefing(client, monkeypatch):
    spy = Spy(monkeypatch)
    first = client.post("/news/refresh").json()
    spy.summary = NewsCreate(title="Second", summary="More happened.")
    r = client.post("/news/refresh?replace=true")
    assert r.status_code == 201 and r.json()["title"] == "Second"
    assert [n["id"] for n in client.get("/news/today").json()] == [r.json()["id"]]
    assert client.get(f"/news/{first['id']}").status_code == 404


def test_refresh_replace_with_no_existing_briefing_just_creates(client, monkeypatch):
    Spy(monkeypatch)
    assert client.post("/news/refresh?replace=true").status_code == 201
    assert len(client.get("/news/today").json()) == 1


@pytest.mark.parametrize("exc, status", [(ConnectionError("ollama down"), 503), (ValueError("x"), 503)])
def test_failed_replace_keeps_existing_briefing(client, monkeypatch, exc, status):
    Spy(monkeypatch)
    first = client.post("/news/refresh").json()
    Spy(monkeypatch, exc=exc)
    assert client.post("/news/refresh?replace=true").status_code == status
    assert [n["id"] for n in client.get("/news/today").json()] == [first["id"]]


def test_replace_with_no_articles_keeps_existing_briefing(client, monkeypatch):
    Spy(monkeypatch)
    first = client.post("/news/refresh").json()
    Spy(monkeypatch, articles=())
    assert client.post("/news/refresh?replace=true").status_code == 502
    assert [n["id"] for n in client.get("/news/today").json()] == [first["id"]]


def test_refresh_with_no_articles_is_502_and_stores_nothing(client, monkeypatch):
    spy = Spy(monkeypatch, articles=())
    assert client.post("/news/refresh").status_code == 502
    assert spy.summarized == 0 and client.get("/news/today").json() == []


@pytest.mark.parametrize("exc, status", [(ConnectionError("ollama down"), 503), (ValueError("x"), 503)])
def test_refresh_agent_failure_stores_nothing_and_can_be_retried(client, monkeypatch, exc, status):
    Spy(monkeypatch, exc=exc)
    assert client.post("/news/refresh").status_code == status
    assert client.get("/news/today").json() == []
    Spy(monkeypatch)
    assert client.post("/news/refresh").status_code == 201


@pytest.mark.asyncio
async def test_concurrent_requests_generate_only_one_briefing(monkeypatch):
    monkeypatch.setattr(briefing, "_lock", asyncio.Lock())
    spy = Spy(monkeypatch)
    slow = briefing.summarize_news

    async def slow_summarize(text, sources):
        await asyncio.sleep(0.05)
        return await slow(text, sources)

    monkeypatch.setattr(briefing, "summarize_news", slow_summarize)

    async def attempt():
        with TestSession() as db:
            return await briefing.generate_briefing(db)

    results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)
    assert sum(isinstance(r, BriefingExists) for r in results) == 1
    assert spy.summarized == 1
