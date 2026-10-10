import uuid
from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.db.models import Task
from backend.models.task import TaskType
from backend.crud.schemas.task import TaskCreate


def create_task(db: Session, data: TaskCreate) -> Task:
    task = Task(**data.model_dump(mode="json"))
    db.add(task)
    db.commit()
    return task


def list_tasks(
    db: Session,
    due_date: date | None = None,
    completed: bool | None = None,
    type: TaskType | None = None,
) -> list[Task]:
    stmt = select(Task).order_by(Task.due_date, Task.date_created)
    if due_date is not None:
        stmt = stmt.where(Task.due_date == due_date)
    if completed is not None:
        stmt = stmt.where(Task.completed == completed)
    if type is not None:
        stmt = stmt.where(Task.type == type.value)
    return list(db.scalars(stmt))


def update_task(db: Session, task_id: uuid.UUID, **fields) -> Task | None:
    """Partial update. `fields` must be JSON-mode values (e.g. type as its string value)."""
    stmt = update(Task).where(Task.id == task_id).values(**fields).returning(Task)
    task = db.scalars(stmt).one_or_none()
    db.commit()
    return task


def complete_task(db: Session, task_id: uuid.UUID) -> Task | None:
    return update_task(db, task_id, completed=True)


def delete_task(db: Session, task_id: uuid.UUID) -> bool:
    deleted = db.execute(delete(Task).where(Task.id == task_id).returning(Task.id)).scalar_one_or_none()
    db.commit()
    return deleted is not None
