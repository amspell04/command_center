import uuid
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from backend.agents.actions import Action, load_instructions

BASE_PROMPT = """You manage the user's tasks using the provided tools.
Today is {today}. Dates are YYYY-MM-DD. Task type is WORK or PERSONAL.
Never invent task ids; get them from list_tasks. Be brief."""

_DIR = Path(__file__).parent


class PlanItem(BaseModel):
    task_id: uuid.UUID
    reason: str = Field(min_length=1)


class DayPlan(BaseModel):
    """Tasks in the order to do them."""

    items: list[PlanItem]


class RescheduleProposal(BaseModel):
    task_id: uuid.UUID
    new_due_date: date
    reason: str = Field(min_length=1)


class OverdueSweep(BaseModel):
    proposals: list[RescheduleProposal]


ACTIONS = {
    "plan_day": Action("task", "plan_day", load_instructions(_DIR, BASE_PROMPT, "plan_day"), ("list_tasks",), DayPlan),
    "overdue_sweep": Action(
        "task", "overdue_sweep", load_instructions(_DIR, BASE_PROMPT, "overdue_sweep"), ("list_tasks",), OverdueSweep
    ),
}

ALLOWED_TOOLS = sorted({t for a in ACTIONS.values() for t in a.tools})
