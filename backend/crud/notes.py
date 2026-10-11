import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from backend.db.models import Note
from backend.crud.schemas.note import NoteCreate


def create_note(db: Session, data: NoteCreate) -> Note:
    note = Note(**data.model_dump(mode="json"))
    db.add(note)
    db.commit()
    return note


def get_note(db: Session, note_id: uuid.UUID) -> Note | None:
    return db.get(Note, note_id)


def list_notes(db: Session, q: str | None = None) -> list[Note]:
    """`q` matches case-insensitively against the title and the content."""
    stmt = select(Note).order_by(Note.date_created.desc(), Note.title)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Note.title.ilike(pattern), Note.content.ilike(pattern)))
    return list(db.scalars(stmt))


def update_note(db: Session, note_id: uuid.UUID, **fields) -> Note | None:
    """Partial update. `fields` must be JSON-mode values ."""
    stmt = update(Note).where(Note.id == note_id).values(**fields).returning(Note)
    note = db.scalars(stmt).one_or_none()
    db.commit()
    return note


def delete_note(db: Session, note_id: uuid.UUID) -> bool:
    deleted = db.execute(delete(Note).where(Note.id == note_id).returning(Note.id)).scalar_one_or_none()
    db.commit()
    return deleted is not None
