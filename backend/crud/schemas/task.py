from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from backend.models.task import TaskType


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    type: TaskType
    due_date: date
    requirement: str = ""


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    type: TaskType | None = None
    requirement: str | None = None
    due_date: date | None = None
    completed: bool | None = None
