import uuid
from datetime import date

from pydantic import BaseModel


class WeakPoint(BaseModel):
    id: uuid.UUID
    note_id: uuid.UUID
    topic: str
    resolved: bool
    date_created: date
