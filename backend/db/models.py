import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class TaskType(str, enum.Enum):
    work = "WORK"
    personal = "PERSONAL"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))


def _date_created() -> Mapped[date]:
    return mapped_column(Date, server_default=func.current_date())


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_due_date_completed", "due_date", "completed"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[TaskType] = mapped_column(Enum(TaskType, name="task_type", values_callable=lambda e: [m.value for m in e]))
    requirement: Mapped[str] = mapped_column(Text, default="", server_default="")
    due_date: Mapped[date] = mapped_column(Date)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    date_created: Mapped[date] = _date_created()


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    # Ordered list of {"content": str}, mirrors NoteBlock in backend/models/note.py
    content_blocks: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    date_created: Mapped[date] = _date_created()


class News(Base):
    __tablename__ = "news"
    __table_args__ = (Index("ix_news_date_created", "date_created"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    # Ordered list of {"question": str, "answer": str}, mirrors NewsQuizQuestion
    quiz_section: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    sources: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"))
    date_created: Mapped[date] = _date_created()
