from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


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
