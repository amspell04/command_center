from datetime import date, timedelta

from backend.crud.news import create_news, list_todays_news
from backend.db.models import News
from backend.crud.schemas.news import NewsCreate

ITEM = {
    "title": "Headline",
    "summary": "Things happened.",
    "quiz_section": [{"question": "What?", "answer": "Things"}],
    "sources": ["https://example.com/a"],
}

def test_today_excludes_other_days(db):
    create_news(db, NewsCreate(title="today", summary="s"))
    db.add(News(title="old", summary="s", date_created=date.today() - timedelta(days=1)))
    db.commit()
    assert [n.title for n in list_todays_news(db)] == ["today"]
