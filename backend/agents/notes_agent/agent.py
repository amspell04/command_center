from pathlib import Path

from backend.agents.types import Action, load_instructions

BASE_PROMPT = """You help the user study and review their notes.
Use only the note text you are given. Never invent note ids. Be brief."""

_DIR = Path(__file__).parent


ACTIONS = {
    "summarize_note": Action(
        "notes", "summarize_note", load_instructions(_DIR, BASE_PROMPT, "summarize_note"), ("append_note_content",)
    ),
}

ALLOWED_TOOLS = sorted({t for a in ACTIONS.values() for t in a.tools})
