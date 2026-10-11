import uuid

from pydantic import BaseModel
from datetime import date, datetime

class NewsQuizQuestion(BaseModel):
    question: str
    answer: str

class NewsArticleLink(BaseModel):
    title: str
    url: str

class News(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    body: str
    quiz_section: list[NewsQuizQuestion]
    sources: list[str]
    articles: list[NewsArticleLink]
    date_created: date

    