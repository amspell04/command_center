from datetime import date
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from backend.ai.llm.client import get_llm, load_prompt


class Suggestion(BaseModel):
    date: date
    action: str = Field(min_length=1)


class WeekBalance(BaseModel):
    """How the week's tasks line up with the gym sessions, with a few concrete changes."""

    status: Literal["BALANCED", "TIGHT", "OVERLOADED"]
    summary: str = Field(min_length=1)
    suggestions: list[Suggestion] = []


@traceable(run_type="chain")
async def balance_week(message: str, day: date | None = None) -> WeekBalance:
    """One structured model call: no tools, no DB access. The message carries the week's days, tasks and sessions."""
    prompt = load_prompt("balance_week").replace("{today}", (day or date.today()).isoformat())
    llm = get_llm("training").with_structured_output(WeekBalance, method="json_schema")
    return await llm.ainvoke([SystemMessage(prompt), HumanMessage(message)])
