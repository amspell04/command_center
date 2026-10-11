import enum
import hashlib
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
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


def note_hash(title: str, content: str) -> str:
    """Fingerprint of what the summary agent reads, so an edit marks a stored summary as stale."""
    return hashlib.sha256(f"{title}\n{content.strip()}".encode()).hexdigest()


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    # One markdown document
    content: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    date_created: Mapped[date] = _date_created()
    # Latest AI summary, kept apart from `content`. The hash is of the title and content it was written from
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    summary_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    summary_source_hash: Mapped[str | None] = mapped_column(String(64), default=None)

    @property
    def summary_stale(self) -> bool:
        return self.summary is not None and self.summary_source_hash != note_hash(self.title, self.content)


class WeakPoint(Base):
    __tablename__ = "weak_points"
    # One row per topic per note, compared case-insensitively
    __table_args__ = (Index("uq_weak_points_note_topic", "note_id", func.lower(text("topic")), unique=True),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(120))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    date_created: Mapped[date] = _date_created()


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    # Optional deadline, e.g. the meet date
    target_date: Mapped[date | None] = mapped_column(Date, default=None)
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


class Lift(str, enum.Enum):
    squat = "SQUAT"
    bench = "BENCH"
    deadlift = "DEADLIFT"


def _lift_column() -> Mapped[Lift]:
    return mapped_column(Enum(Lift, name="lift", values_callable=lambda e: [m.value for m in e]))


# All weights are stored in lb. kg is derived for display
class TrainingMax(Base):
    """The max a program's percentages are taken from. History is kept; the latest row per lift applies."""

    __tablename__ = "training_maxes"
    __table_args__ = (
        UniqueConstraint("lift", "effective_date", name="uq_training_maxes_lift_date"),
        CheckConstraint("weight > 0", name="ck_training_maxes_weight"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    lift: Mapped[Lift] = _lift_column()
    weight: Mapped[float] = mapped_column(Numeric(6, 1))
    effective_date: Mapped[date] = mapped_column(Date)


class Program(Base):
    __tablename__ = "programs"
    # At most one active program
    __table_args__ = (
        Index("uq_programs_one_active", "active", unique=True, postgresql_where=text("active")),
        CheckConstraint("weeks BETWEEN 1 AND 52", name="ck_programs_weeks"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    # Week 1 day 1 falls on this date
    start_date: Mapped[date] = mapped_column(Date)
    weeks: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class ProgramSet(Base):
    """One prescribed exercise, e.g. 3 sets of 5 at 80% of the training max."""

    __tablename__ = "program_sets"
    __table_args__ = (
        CheckConstraint("week >= 1", name="ck_program_sets_week"),
        CheckConstraint("day BETWEEN 1 AND 7", name="ck_program_sets_day"),
        CheckConstraint("sets BETWEEN 1 AND 20", name="ck_program_sets_sets"),
        CheckConstraint("reps BETWEEN 1 AND 30", name="ck_program_sets_reps"),
        CheckConstraint("percent > 0 AND percent <= 150", name="ck_program_sets_percent"),
        Index("ix_program_sets_program_week_day", "program_id", "week", "day"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("programs.id", ondelete="CASCADE"))
    week: Mapped[int] = mapped_column(Integer)
    day: Mapped[int] = mapped_column(Integer)
    lift: Mapped[Lift] = _lift_column()
    sets: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)
    percent: Mapped[float] = mapped_column(Numeric(4, 1))


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    date: Mapped[date] = mapped_column(Date, unique=True)
    notes: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    bodyweight: Mapped[float | None] = mapped_column(Numeric(5, 1), default=None)


class LiftSet(Base):
    __tablename__ = "lift_sets"
    __table_args__ = (
        CheckConstraint("weight > 0", name="ck_lift_sets_weight"),
        CheckConstraint("reps BETWEEN 1 AND 30", name="ck_lift_sets_reps"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    lift: Mapped[Lift] = _lift_column()
    weight: Mapped[float] = mapped_column(Numeric(6, 1))
    reps: Mapped[int] = mapped_column(Integer)
    set_order: Mapped[int] = mapped_column(Integer)
    # The prescription this set was done for, if any. Cleared if that program row is deleted
    program_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("program_sets.id", ondelete="SET NULL"), default=None
    )
