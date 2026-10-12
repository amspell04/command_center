from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.db.models import AgentResult


def get_result(db: Session, kind: str, period_start: date) -> AgentResult | None:
    return db.scalar(select(AgentResult).where(AgentResult.kind == kind, AgentResult.period_start == period_start))


def save_result(db: Session, kind: str, period_start: date, payload: dict, source_hash: str) -> AgentResult:
    """Insert or replace the one row for this action and period."""
    stmt = insert(AgentResult).values(kind=kind, period_start=period_start, payload=payload, source_hash=source_hash)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_agent_results_kind",
        set_={"payload": payload, "source_hash": source_hash, "generated_at": func.now()},
    ).returning(AgentResult)
    row = db.scalars(stmt).one()
    db.commit()
    return row

