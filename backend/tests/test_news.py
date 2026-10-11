import uuid
from datetime import date, timedelta

from backend.crud.news import create_news, get_latest_news, get_news, list_todays_news
from backend.db.models import News
from backend.crud.schemas.news import NewsCreate

ITEM = {
    "title": "Headline",
    "summary": "Things happened.",
    "body": "Details of what happened.",
    "quiz_section": [{"question": "What?", "answer": "Things"}],
    "sources": ["https://example.com/a"],
}

def test_today_excludes_other_days(db):
    create_news(db, NewsCreate(title="today", summary="s", body="b"))
    db.add(News(title="old", summary="s", date_created=date.today() - timedelta(days=1)))
    db.commit()
    assert [n.title for n in list_todays_news(db)] == ["today"]


def test_latest_is_the_newest_day_not_only_today(db):
    db.add(News(title="old", summary="s", date_created=date.today() - timedelta(days=3)))
    db.add(News(title="newer", summary="s", date_created=date.today() - timedelta(days=1)))
    db.commit()
    assert get_latest_news(db).title == "newer"


def test_latest_and_get_are_none_when_missing(db):
    assert get_latest_news(db) is None
    assert get_news(db, uuid.uuid4()) is None


def test_latest_endpoint(client):
    assert client.get("/news/latest").status_code == 404


def test_latest_and_by_id_endpoints(client, db):
    n = create_news(db, NewsCreate(title="today", summary="s", body="b"))
    assert client.get("/news/latest").json()["title"] == "today"
    assert client.get(f"/news/{n.id}").json()["id"] == str(n.id)


def test_get_news_unknown_or_malformed_id(client):
    assert client.get(f"/news/{uuid.uuid4()}").status_code == 404
    assert client.get("/news/not-a-uuid").status_code == 422


def test_create_news_requires_summary_and_body(db):
    import pytest
    from pydantic import ValidationError

    for missing in ("summary", "body"):
        data = {k: v for k, v in ITEM.items() if k != missing}
        with pytest.raises(ValidationError):
            NewsCreate(**data)
    with pytest.raises(ValidationError):
        NewsCreate(**{**ITEM, "body": ""})


def test_news_stores_summary_and_body_separately(db):
    n = create_news(db, NewsCreate(**ITEM))
    stored = get_news(db, n.id)
    assert (stored.summary, stored.body) == ("Things happened.", "Details of what happened.")
