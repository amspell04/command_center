"""Single-shot agent actions. Routes load the data an action needs, run the agent, and check its output
against the database before returning it, so a small model's invented ids or quotes never reach the UI."""
import uuid
from collections.abc import Awaitable, Callable
import datetime as dt
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from backend.agents.actions import get_action, run_action
from backend.crud import notes as notes_crud
from backend.crud import tasks as tasks_crud
from backend.db.session import get_db
from backend.models.note import Note
from backend.services.helpers import guarded

router = APIRouter(prefix="/agents", tags=["agents"])


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanDayParams(Params):
    date: dt.date | None = None


class NoteParams(Params):
    note_id: uuid.UUID


class PlannedTask(BaseModel):
    task_id: uuid.UUID
    title: str
    due_date: date
    reason: str
    estimate_minutes: int | None = None  # None when the model did not rank the task


class DayPlanResult(BaseModel):
    date: dt.date
    items: list[PlannedTask]


async def _run(agent: str, name: str, message: str):
    return await guarded(f"{agent}/{name}", run_action(get_action(agent, name), message))


def _note_or_404(db: Session, note_id: uuid.UUID):
    note = notes_crud.get_note(db, note_id)
    if note is None:
        raise HTTPException(404, "Note not found")
    return note


def _note_text(note) -> str:
    text = note.content.strip()
    if not text:
        raise HTTPException(400, "Note has no content")
    return text


# TASKS

async def plan_day(db: Session, p: PlanDayParams) -> DayPlanResult:
    day = p.date or date.today()
    due = {t.id: t for t in tasks_crud.list_tasks(db, completed=False) if t.due_date <= day}
    if not due:
        return DayPlanResult(date=day, items=[])
    plan = await _run("task", "plan_day", f"Plan my day for {day.isoformat()}.")
    items, seen = [], set()
    for item in plan.items:
        task = due.get(item.task_id)
        if task is not None and task.id not in seen:
            seen.add(task.id)
            items.append(PlannedTask(task_id=task.id, title=task.title, due_date=task.due_date, reason=item.reason, estimate_minutes=item.estimate_minutes))
    # Never silently drop a task the model forgot to rank.
    items += [PlannedTask(task_id=t.id, title=t.title, due_date=t.due_date, reason="") for t in due.values() if t.id not in seen]
    return DayPlanResult(date=day, items=items)


# NOTES

async def summarize_note(db: Session, p: NoteParams) -> Note:
    note = _note_or_404(db, p.note_id)
    text = _note_text(note)
    before = note.content
    await _run("notes", "summarize_note", f"note_id: {note.id}\ntitle: {note.title}\n\n{text}")
    db.refresh(note)  # the MCP server wrote in its own session
    added = note.content[len(before):].strip() if note.content.startswith(before) else ""
    if not added.startswith("Summary:"):
        raise HTTPException(502, "The agent did not save a summary, try again")
    return Note.model_validate(note, from_attributes=True)


HANDLERS: dict[tuple[str, str], tuple[type[Params], Callable[[Session, Params], Awaitable[BaseModel]]]] = {
    ("task", "plan_day"): (PlanDayParams, plan_day),
    ("notes", "summarize_note"): (NoteParams, summarize_note),
}


@router.post("/{agent}/actions/{name}")
async def run_agent_action(agent: str, name: str, body: dict = Body(default_factory=dict), db: Session = Depends(get_db)):
    handler = HANDLERS.get((agent, name))
    if handler is None:
        raise HTTPException(404, f"Unknown action '{name}' for agent '{agent}'")
    params_model, fn = handler
    try:
        params = params_model.model_validate(body)
    except ValidationError as e:
        raise HTTPException(422, "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()))
    return await fn(db, params)
