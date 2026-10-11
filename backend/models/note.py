import uuid
from datetime import date, datetime

from pydantic import BaseModel

class Note(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    date_created: date
    summary: str | None = None
    summary_generated_at: datetime | None = None
    summary_stale: bool = False  # the note changed after the summary was written
