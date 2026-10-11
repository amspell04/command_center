"""Single-shot agent actions. Routes load the data an action needs, run the agent, and check its output
against the database before returning it, so a small model's invented ids or quotes never reach the UI."""
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal
import datetime as dt
from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from backend.agents.actions import get_action, run_action
from backend.crud import goals as goals_crud
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


class WeekStats(BaseModel):
    """Computed from the database, never by the model. The week runs Monday to Sunday."""

    start: dt.date
    end: dt.date
    due_so_far: int  # due Monday through the planned date
    completed_so_far: int
    overdue_open: int  # due before the planned date and still open
    due_remaining: int  # due after the planned date, within the week


class GoalStatus(BaseModel):
    goal_id: uuid.UUID
    title: str
    on_track: bool
    note: str


class DayPlanResult(BaseModel):
    date: dt.date
    items: list[PlannedTask]
    week: WeekStats
    status: Literal["ON_TRACK", "AT_RISK", "OFF_TRACK"] | None = None  # None when the model was not run
    summary: str = ""
    goals: list[GoalStatus] = []


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

def _week_stats(tasks, day: date) -> WeekStats:
    start = day - timedelta(days=day.weekday())
    end = start + timedelta(days=6)
    so_far = [t for t in tasks if start <= t.due_date <= day]
    return WeekStats(
        start=start,
        end=end,
        due_so_far=len(so_far),
        completed_so_far=sum(t.completed for t in so_far),
        overdue_open=sum(not t.completed and t.due_date < day for t in so_far),
        due_remaining=sum(day < t.due_date <= end for t in tasks),
    )


def _plan_message(day: date, week: WeekStats, goals) -> str:
    lines = [
        f"Plan my day for {day.isoformat()}.",
        f"Week {week.start} to {week.end}: {week.due_so_far} tasks due so far, {week.completed_so_far} completed, "
        f"{week.overdue_open} overdue and open, {week.due_remaining} due later this week.",
        "Goals:" if goals else "Goals: none set.",
        *(f"- id {g.id}: {g.title}" + (f" ({g.details})" if g.details else "") for g in goals),
    ]
    return "\n".join(lines)


async def plan_day(db: Session, p: PlanDayParams) -> DayPlanResult:
    day = p.date or date.today()
    all_tasks = tasks_crud.list_tasks(db)
    week = _week_stats(all_tasks, day)
    due = {t.id: t for t in all_tasks if not t.completed and t.due_date <= day}
    if not due:
        return DayPlanResult(date=day, items=[], week=week)
    goals = goals_crud.list_goals(db)
    plan = await _run("task", "plan_day", _plan_message(day, week, goals))
    items, seen = [], set()
    for item in plan.items:
        task = due.get(item.task_id)
        if task is not None and task.id not in seen:
            seen.add(task.id)
            items.append(PlannedTask(task_id=task.id, title=task.title, due_date=task.due_date, reason=item.reason, estimate_minutes=item.estimate_minutes))
    # Never silently drop a task the model forgot to rank.
    items += [PlannedTask(task_id=t.id, title=t.title, due_date=t.due_date, reason="") for t in due.values() if t.id not in seen]
    by_id, checked = {g.id: g for g in goals}, {}
    for check in plan.goal_checks:  # drop invented goal ids and repeats
        if check.goal_id in by_id:
            checked.setdefault(check.goal_id, GoalStatus(goal_id=check.goal_id, title=by_id[check.goal_id].title, on_track=check.on_track, note=check.note))
    return DayPlanResult(date=day, items=items, week=week, status=plan.week_status, summary=plan.week_summary, goals=list(checked.values()))


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
