from pathlib import Path

from pydantic import BaseModel, Field

from backend.agents.actions import Action, load_instructions

BASE_PROMPT = """You help the user study and review their notes.
Use only the note text you are given. Never invent note ids. Be brief."""

_DIR = Path(__file__).parent


class CritiquePoint(BaseModel):
    point: str = Field(min_length=1)
    quote: str = Field(min_length=1, description="Exact passage from the note this refers to")


class NoteCritique(BaseModel):
    gaps: list[CritiquePoint]
    unclear_claims: list[CritiquePoint]
    questions: list[str]


ACTIONS = {
    "summarize_note": Action(
        "notes", "summarize_note", load_instructions(_DIR, BASE_PROMPT, "summarize_note"), ("add_note_block",)
    ),
    "critique_note": Action(
        "notes", "critique_note", load_instructions(_DIR, BASE_PROMPT, "critique_note"), (), NoteCritique
    ),
}

ALLOWED_TOOLS = sorted({t for a in ACTIONS.values() for t in a.tools})
