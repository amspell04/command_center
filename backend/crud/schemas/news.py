from pydantic import BaseModel, ConfigDict, Field

from backend.models.news import NewsQuizQuestion


class NewsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    quiz_section: list[NewsQuizQuestion] = []
    sources: list[str] = []
