from pydantic import BaseModel, ConfigDict, Field

from backend.models.note import NoteBlock


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    content_blocks: list[NoteBlock] = []


class NoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_blocks: list[NoteBlock] | None = None
