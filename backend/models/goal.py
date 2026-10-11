import uuid
from datetime import date

from pydantic import BaseModel


class Goal(BaseModel):
    id: uuid.UUID
    title: str
    details: str
    date_created: date
