from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from backend.agents.runner import run_agent


class UnknownAction(LookupError):
    """No such agent, or the agent has no such action."""


@dataclass(frozen=True)
class Action:
    """One single-shot job for an agent: instructions, a tool allow-list and an optional output schema."""

    agent: str
    name: str
    instructions: str
    tools: tuple[str, ...] = ()
    output: type[BaseModel] | None = None


def load_instructions(agent_dir: Path, base: str, name: str) -> str:
    """Agent-wide rules followed by the action's own prompt file (`<agent_dir>/actions/<name>.md`)."""
    return f"{base}\n\n{(agent_dir / 'actions' / f'{name}.md').read_text().strip()}"


def get_action(agent: str, name: str) -> Action:
    # Imported here because the agent modules import `Action` from this file.
    from backend.agents.notes_agent.agent import ACTIONS as notes_actions
    from backend.agents.task_agent.agent import ACTIONS as task_actions

    registry = {"task": task_actions, "notes": notes_actions}
    try:
        return registry[agent][name]
    except KeyError:
        raise UnknownAction(f"Unknown action '{name}' for agent '{agent}'") from None


async def run_action(action: Action, message: str) -> str | BaseModel:
    """Run an action. Returns the reply text, or an `action.output` instance when a schema is set."""
    prompt = action.instructions.replace("{today}", date.today().isoformat())
    result = await run_agent(f"{action.agent}_agent", prompt, action.tools, message, action.output)
    return result["output"]
