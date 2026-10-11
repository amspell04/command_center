import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import News
from backend.crud.schemas.news import NewsCreate


def create_news(db: Session, data: NewsCreate) -> News:
    news = News(**data.model_dump(mode="json"))
    db.add(news)
    db.commit()
    return news


def get_news(db: Session, news_id: uuid.UUID) -> News | None:
    return db.get(News, news_id)


def get_latest_news(db: Session) -> News | None:
    stmt = select(News).order_by(News.date_created.desc(), News.title).limit(1)
    return db.scalars(stmt).first()


def list_todays_news(db: Session) -> list[News]:
    stmt = select(News).where(News.date_created == func.current_date()).order_by(News.title)
    return list(db.scalars(stmt))
