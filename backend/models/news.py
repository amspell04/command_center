import uuid

from pydantic import BaseModel
from datetime import date, datetime

class NewsQuizQuestion(BaseModel):
    question: str
    answer: str

class News(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    quiz_section: list[NewsQuizQuestion]
    sources: list[str]
    date_created: date

    