import uuid
from datetime import date

from pydantic import BaseModel


class Goal(BaseModel):
    id: uuid.UUID
    title: str
    details: str
    target_date: date | None = None
    date_created: date
