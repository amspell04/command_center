import uuid

from pydantic import BaseModel
from datetime import date

class Note(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    date_created: date

