from datetime import date

from pydantic import BaseModel

from backend.agents.notes_agent.agent import ACTIONS as NOTES_ACTIONS
from backend.agents.runner import run_agent
from backend.agents.task_agent.agent import ACTIONS as TASK_ACTIONS
from backend.agents.types import Action

REGISTRY = {"task": TASK_ACTIONS, "notes": NOTES_ACTIONS}


class UnknownAction(LookupError):
    """No such agent, or the agent has no such action."""


def get_action(agent: str, name: str) -> Action:
    try:
        return REGISTRY[agent][name]
    except KeyError:
        raise UnknownAction(f"Unknown action '{name}' for agent '{agent}'") from None


async def run_action(action: Action, message: str) -> str | BaseModel:
    """Run an action. Returns the reply text, or an `action.output` instance when a schema is set."""
    prompt = action.instructions.replace("{today}", date.today().isoformat())
    result = await run_agent(f"{action.agent}_agent", prompt, action.tools, message, action.output)
    return result["output"]
