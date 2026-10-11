import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.crud.schemas.goal import GoalCreate
from backend.db.models import Goal


def create_goal(db: Session, data: GoalCreate) -> Goal:
    goal = Goal(**data.model_dump(mode="json"))
    db.add(goal)
    db.commit()
    return goal


def list_goals(db: Session) -> list[Goal]:
    return list(db.scalars(select(Goal).order_by(Goal.date_created, Goal.title)))


def update_goal(db: Session, goal_id: uuid.UUID, **fields) -> Goal | None:
    """Partial update. `fields` must be JSON-mode values."""
    goal = db.scalars(update(Goal).where(Goal.id == goal_id).values(**fields).returning(Goal)).one_or_none()
    db.commit()
    return goal


def delete_goal(db: Session, goal_id: uuid.UUID) -> bool:
    deleted = db.execute(delete(Goal).where(Goal.id == goal_id).returning(Goal.id)).scalar_one_or_none()
    db.commit()
    return deleted is not None
