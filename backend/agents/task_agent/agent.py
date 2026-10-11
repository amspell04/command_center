import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from backend.agents.types import Action, load_instructions

BASE_PROMPT = """You manage the user's tasks using the provided tools.
Today is {today}. Dates are YYYY-MM-DD. Task type is WORK or PERSONAL.
Never invent task ids; get them from list_tasks. Be brief."""

_DIR = Path(__file__).parent


class PlanItem(BaseModel):
    task_id: uuid.UUID
    reason: str = Field(min_length=1)
    estimate_minutes: int = Field(ge=5, le=480)


class DayPlan(BaseModel):
    """Tasks in the order to do them, each with a time estimate."""

    items: list[PlanItem]


ACTIONS = {
    "plan_day": Action("task", "plan_day", load_instructions(_DIR, BASE_PROMPT, "plan_day"), ("list_tasks",), DayPlan),
}

ALLOWED_TOOLS = sorted({t for a in ACTIONS.values() for t in a.tools})
