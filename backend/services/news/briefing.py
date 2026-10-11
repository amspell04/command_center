"""Generate today's news briefing on request: fetch feeds, summarize with the news agent, store."""
import asyncio

from sqlalchemy.orm import Session

from backend.ai.llm.news import summarize_news
from backend.crud import news as news_crud
from backend.db.models import News
from backend.services.news.news import fetch_articles, format_for_agent


class BriefingExists(Exception):
    """Today already has a briefing; it is generated at most once per day."""


class NoArticles(Exception):
    """No feed returned a recent article, so there is nothing to summarize."""


# Serializes requests so a double click cannot generate two briefings.
_lock = asyncio.Lock()


async def generate_briefing(db: Session, replace: bool = False) -> News:
    """Create today's briefing. With replace, the existing one is deleted only after the new one is stored."""
    async with _lock:
        existing = news_crud.list_todays_news(db)
        if existing and not replace:
            raise BriefingExists("Today's briefing already exists")
        old_ids = [n.id for n in existing]
        articles = await fetch_articles()
        if not articles:
            raise NoArticles("No recent articles could be fetched")
        text, sources = format_for_agent(articles)
        created = news_crud.create_news(db, await summarize_news(text, sources))
        for old_id in old_ids:
            news_crud.delete_news(db, old_id)
        return created
