import uuid

from pydantic import BaseModel
from datetime import date

class NoteBlock(BaseModel):
    content: str

class Note(BaseModel):
    id: uuid.UUID
    title: str
    content_blocks: list[NoteBlock]
    date_created: date

