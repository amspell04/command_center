from enum import Enum
import uuid

from pydantic import BaseModel
from datetime import date, datetime

class TaskType(Enum):
    work = "WORK"
    personal = "PERSONAL"

class Task(BaseModel):
    id: uuid.UUID
    title: str
    type: TaskType
    requirement: str
    due_date: date
    completed: bool
    date_created: date