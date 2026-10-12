"""Single-shot LLM actions. Routes load the data an action needs, make one model call, and check its output
against the database before returning it, so a small model's invented ids never reach the UI."""
import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal
import datetime as dt
from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from backend.ai.llm import notes as notes_llm
from backend.ai.llm import tasks as tasks_llm
from backend.ai.llm import training as training_llm
from backend.ai.llm.client import load_prompt
from backend.crud import agent_results as results_crud
from backend.crud import goals as goals_crud
from backend.crud import notes as notes_crud
from backend.crud import tasks as tasks_crud
from backend.crud import training as training_crud
from backend.db.models import note_hash
from backend.db.session import get_db
from backend.models.note import Note
from backend.models.training import GymDay
from backend.services.helpers import _found, guarded

router = APIRouter(prefix="/agents", tags=["agents"])


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanDayParams(Params):
    date: dt.date | None = None
    force: bool = False  # regenerate even when the stored plan is current


class BalanceWeekParams(Params):
    date: dt.date | None = None  # any day in the week to balance
    force: bool = False  # regenerate even when the stored result is current


class NoteParams(Params):
    note_id: uuid.UUID


class SummarizeParams(NoteParams):
    force: bool = False  # regenerate even when the stored summary is current


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
    overdue_open: int  # due before the planned date, in any week, and still open
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


class BalanceDay(BaseModel):
    date: dt.date
    weekday: str
    tasks_due: int
    tasks_done: int
    task_titles: list[str]  # the open ones
    gym: GymDay | None = None


class Meet(BaseModel):
    title: str
    date: dt.date
    days_left: int


class BalanceSuggestion(BaseModel):
    date: dt.date
    action: str


class WeekBalanceResult(BaseModel):
    start: dt.date
    end: dt.date
    days: list[BalanceDay]
    meet: Meet | None = None
    program: str | None = None  # e.g. "Meet prep, week 3 of 10"
    status: Literal["BALANCED", "TIGHT", "OVERLOADED"] | None = None  # None when the model was not run
    summary: str = ""
    suggestions: list[BalanceSuggestion] = []


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


# STORED RESULTS

def _digest(prompt_name: str, message: str) -> str:
    """Fingerprint of what the model reads, so a changed task, session or prompt regenerates the stored output."""
    return hashlib.sha256(f"{load_prompt(prompt_name)}\n{message}".encode()).hexdigest()


def _stored(db: Session, kind: str, period: date, digest: str, force: bool, model: type[BaseModel]):
    row = results_crud.get_result(db, kind, period)
    if row is None or force or row.source_hash != digest:
        return None
    return model.model_validate(row.payload)


def _store(db: Session, kind: str, period: date, digest: str, result: BaseModel):
    results_crud.save_result(db, kind, period, result.model_dump(mode="json"), digest)
    return result


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
        overdue_open=sum(not t.completed and t.due_date < day for t in tasks),
        due_remaining=sum(day < t.due_date <= end for t in tasks),
    )


def _plan_message(day: date, week: WeekStats, goals, due) -> str:
    lines = [
        f"Plan my day for {day.isoformat()}.",
        "Tasks to plan:",
        *(f"- id {t.id}: {t.title} (due {t.due_date})" + (f", requirement: {t.requirement}" if t.requirement else "") for t in due),
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
    message = _plan_message(day, week, goals, sorted(due.values(), key=lambda t: t.due_date))
    digest = _digest("plan_day", message)
    if (cached := _stored(db, "plan_day", day, digest, p.force, DayPlanResult)) is not None:
        return cached
    plan = await guarded("tasks/plan_day", tasks_llm.plan_day(message, day))
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
    result = DayPlanResult(date=day, items=items, week=week, status=plan.week_status, summary=plan.week_summary, goals=list(checked.values()))
    return _store(db, "plan_day", day, digest, result)


# TRAINING

def _balance_message(day: date, days: list[BalanceDay], meet: Meet | None, program: str | None) -> str:
    lines = [
        f"Balance my week. Today is {day.isoformat()}, only give advice for today or later.",
        f"Meet: {meet.title} on {meet.date}, {meet.days_left} days away." if meet else "Meet: no date set.",
        f"Program: {program}." if program else "Program: none active.",
        "Days:",
    ]
    for d in days:
        gym = "; ".join(d.gym.details) if d.gym else "no gym"
        tasks = f"{d.tasks_due} tasks due, {d.tasks_done} done" + (f" ({', '.join(d.task_titles)})" if d.task_titles else "")
        lines.append(f"- {d.date} {d.weekday}: gym: {gym}. Tasks: {tasks}.")
    return "\n".join(lines)


async def balance_week(db: Session, p: BalanceWeekParams) -> WeekBalanceResult:
    day = p.date or date.today()
    start = day - timedelta(days=day.weekday())
    end = start + timedelta(days=6)
    tasks = tasks_crud.list_tasks(db)
    days = []
    for d in (start + timedelta(days=i) for i in range(7)):
        due = [t for t in tasks if t.due_date == d]
        days.append(BalanceDay(
            date=d, weekday=d.strftime("%A"), tasks_due=len(due), tasks_done=sum(t.completed for t in due),
            task_titles=[t.title for t in due if not t.completed][:5], gym=training_crud.gym_day(db, d),
        ))
    upcoming = sorted((g for g in goals_crud.list_goals(db) if g.target_date and g.target_date >= day), key=lambda g: g.target_date)
    meet = Meet(title=upcoming[0].title, date=upcoming[0].target_date, days_left=(upcoming[0].target_date - day).days) if upcoming else None
    active = training_crud.get_active_program(db)
    program = None
    if active is not None and 0 <= (end - active.start_date).days and (start - active.start_date).days < active.weeks * 7:
        week_no = max(1, (start - active.start_date).days // 7 + 1)
        program = f"{active.name}, week {min(week_no, active.weeks)} of {active.weeks}"
    result = WeekBalanceResult(start=start, end=end, days=days, meet=meet, program=program)
    if not any(d.gym for d in days):  # nothing to balance tasks against
        return result
    message = _balance_message(day, days, meet, program)
    digest = _digest("balance_week", message)
    if (cached := _stored(db, "balance_week", start, digest, p.force, WeekBalanceResult)) is not None:
        return cached
    balance = await guarded("training/balance_week", training_llm.balance_week(message, day))
    result.status, result.summary = balance.status, balance.summary
    seen = set()
    for s in balance.suggestions:  # keep only real, upcoming days in this week, and each date's action once
        key = (s.date, s.action.strip().lower())
        if max(day, start) <= s.date <= end and s.action.strip() and key not in seen and len(result.suggestions) < 4:
            seen.add(key)
            result.suggestions.append(BalanceSuggestion(date=s.date, action=s.action.strip()))
    return _store(db, "balance_week", start, digest, result)


# NOTES

async def summarize_note(db: Session, p: SummarizeParams) -> Note:
    note = _note_or_404(db, p.note_id)
    text = _note_text(note)
    if note.summary and not note.summary_stale and not p.force:
        return Note.model_validate(note, from_attributes=True)
    summary = (await guarded("notes/summarize_note", notes_llm.summarize_note(note.title, text))).strip()
    summary = summary.removeprefix("Summary:").strip()
    if not summary:
        raise HTTPException(502, "The agent returned an unusable response, try again")
    saved = notes_crud.update_note(
        db,
        note.id,
        summary=summary,
        summary_generated_at=dt.datetime.now(dt.timezone.utc),
        summary_source_hash=note_hash(note.title, note.content),
    )
    return Note.model_validate(_found(saved, "Note"), from_attributes=True)


HANDLERS: dict[tuple[str, str], tuple[type[Params], Callable[[Session, Params], Awaitable[BaseModel]]]] = {
    ("task", "plan_day"): (PlanDayParams, plan_day),
    ("training", "balance_week"): (BalanceWeekParams, balance_week),
    ("notes", "summarize_note"): (SummarizeParams, summarize_note),
}


RESULT_KINDS: dict[str, type[BaseModel]] = {"plan_day": DayPlanResult, "balance_week": WeekBalanceResult}


@router.get("/results/{kind}")
def stored_result(kind: str, date: dt.date, db: Session = Depends(get_db)):
    """The last stored output for the day (plan_day) or the week containing it (balance_week), or null. Never runs the model."""
    model = RESULT_KINDS.get(kind)
    if model is None:
        raise HTTPException(404, f"Unknown result '{kind}'")
    period = date - timedelta(days=date.weekday()) if kind == "balance_week" else date
    row = results_crud.get_result(db, kind, period)
    return model.model_validate(row.payload) if row else None


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
