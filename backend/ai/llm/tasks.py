import uuid
from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from backend.ai.llm.client import get_llm, load_prompt


class PlanItem(BaseModel):
    task_id: uuid.UUID
    reason: str = Field(min_length=1)
    estimate_minutes: int = Field(ge=5, le=480)


class GoalCheck(BaseModel):
    goal_id: uuid.UUID
    on_track: bool
    note: str = Field(min_length=1)


class DayPlan(BaseModel):
    """Tasks in the order to do them with time estimates, plus a status update on the week so far."""

    items: list[PlanItem]
    week_status: Literal["ON_TRACK", "AT_RISK", "OFF_TRACK"]
    week_summary: str = Field(min_length=1)
    goal_checks: list[GoalCheck] = []


@traceable(run_type="chain")
async def plan_day(message: str, day: date | None = None) -> DayPlan:
    """One structured model call: no tools, no DB access. The message carries the tasks, week numbers and goals."""
    prompt = load_prompt("plan_day").replace("{today}", (day or date.today()).isoformat())
    llm = get_llm("tasks").with_structured_output(DayPlan, method="json_schema")
    return await llm.ainvoke([SystemMessage(prompt), HumanMessage(message)])
