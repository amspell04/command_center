"""Generate today's news briefing on request: fetch feeds, summarize with the news agent, store."""
import asyncio

from sqlalchemy.orm import Session

from backend.agents.news_agent.agent import summarize_news
from backend.crud import news as news_crud
from backend.db.models import News
from backend.services.news.news import fetch_articles, format_for_agent


class BriefingExists(Exception):
    """Today already has a briefing; it is generated at most once per day."""


class NoArticles(Exception):
    """No feed returned a recent article, so there is nothing to summarize."""


# Serializes requests so a double click cannot generate two briefings.
_lock = asyncio.Lock()


async def generate_briefing(db: Session) -> News:
    async with _lock:
        if news_crud.list_todays_news(db):
            raise BriefingExists("Today's briefing already exists")
        articles = await fetch_articles()
        if not articles:
            raise NoArticles("No recent articles could be fetched")
        text, sources = format_for_agent(articles)
        return news_crud.create_news(db, await summarize_news(text, sources))
