from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import News
from backend.crud.schemas.news import NewsCreate


def create_news(db: Session, data: NewsCreate) -> News:
    news = News(**data.model_dump(mode="json"))
    db.add(news)
    db.commit()
    return news


def list_todays_news(db: Session) -> list[News]:
    stmt = select(News).where(News.date_created == func.current_date()).order_by(News.title)
    return list(db.scalars(stmt))
