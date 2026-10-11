import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.db.models import WeakPoint


def record_miss(db: Session, note_id: uuid.UUID, topic: str) -> tuple[WeakPoint, bool]:
    """Record that the user missed `topic` on a note. Topics match case-insensitively.

    Returns (weak point, changed). `changed` is True when the topic is new or was resolved and is now open
    again; a miss on a topic that is already open changes nothing.
    """
    existing = db.scalars(
        select(WeakPoint).where(WeakPoint.note_id == note_id, func.lower(WeakPoint.topic) == topic.lower())
    ).one_or_none()
    if existing is None:
        weak_point = WeakPoint(note_id=note_id, topic=topic)
        db.add(weak_point)
        db.commit()
        db.refresh(weak_point)  # date_created is a server default
        return weak_point, True
    if not existing.resolved:
        return existing, False
    existing.resolved = False
    db.commit()
    return existing, True


def list_weak_points(db: Session, note_id: uuid.UUID, resolved: bool | None = None) -> list[WeakPoint]:
    stmt = select(WeakPoint).where(WeakPoint.note_id == note_id).order_by(WeakPoint.date_created.desc(), WeakPoint.topic)
    if resolved is not None:
        stmt = stmt.where(WeakPoint.resolved == resolved)
    return list(db.scalars(stmt))


def list_all_weak_points(db: Session, resolved: bool | None = None) -> list[WeakPoint]:
    stmt = select(WeakPoint).order_by(WeakPoint.date_created.desc(), WeakPoint.topic)
    if resolved is not None:
        stmt = stmt.where(WeakPoint.resolved == resolved)
    return list(db.scalars(stmt))


def update_weak_point(db: Session, weak_point_id: uuid.UUID, **fields) -> WeakPoint | None:
    """Partial update. `fields` must be JSON-mode values."""
    stmt = update(WeakPoint).where(WeakPoint.id == weak_point_id).values(**fields).returning(WeakPoint)
    weak_point = db.scalars(stmt).one_or_none()
    db.commit()
    return weak_point


def delete_weak_point(db: Session, weak_point_id: uuid.UUID) -> bool:
    stmt = delete(WeakPoint).where(WeakPoint.id == weak_point_id).returning(WeakPoint.id)
    deleted = db.execute(stmt).scalar_one_or_none()
    db.commit()
    return deleted is not None
