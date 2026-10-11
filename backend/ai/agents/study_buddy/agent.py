import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from backend.ai.agents.runner import stream_agent
from backend.ai.agents.study_buddy.tools import make_resolve_weak_point_tool, make_weak_point_tool

# Keeps the prompt inside a small model's context window.
MAX_NOTE_CHARS = 8000
# Each tool call takes two graph steps, so this allows a few weak points per reply.
RECURSION_LIMIT = 12
# Open weak points shown to the model.
MAX_WEAK_POINTS = 20

_PROMPTS = {
    "quiz": (Path(__file__).parent / "prompt.md").read_text().strip(),
    "review": (Path(__file__).parent / "review_prompt.md").read_text().strip(),
}


def system_prompt(title: str, text: str, weak_points: list[str] = (), mode: str = "quiz") -> str:
    prompt = f"{_PROMPTS[mode]}\n\n<note title={title!r}>\n{text[:MAX_NOTE_CHARS]}\n</note>"
    if weak_points:
        listed = "\n".join(f"- {topic}" for topic in weak_points[:MAX_WEAK_POINTS])
        prompt += f"\n\n<weak_points>\n{listed}\n</weak_points>"
    return prompt


async def study_buddy_events(
    note_id: uuid.UUID, title: str, text: str, weak_points: list[str], history: list[dict],
    mode: str = "quiz",
) -> AsyncIterator[dict]:
    """One reply in a quiz, or in a review of the note's weak points when `mode` is "review".
    `weak_points` are the topics still open on the note.
    `history` is the conversation so far as {"role", "content"} dicts.

    Yields {"type": "token", "text"} as the reply streams, {"type": "weak_point", "topic"} each time a quiz adds
    one and {"type": "weak_point_resolved", "topic"} each time a review resolves one.
    """
    tool = make_resolve_weak_point_tool(note_id) if mode == "review" else make_weak_point_tool(note_id)
    async for chunk in stream_agent(
        "study_buddy", system_prompt(title, text, weak_points, mode), [tool], history, RECURSION_LIMIT,
        metadata={"note_id": str(note_id), "mode": mode},
    ):
        if isinstance(chunk, ToolMessage):
            result = chunk.artifact
            if not isinstance(result, dict):
                continue
            if chunk.name == "add_weak_point" and result.get("added"):
                yield {"type": "weak_point", "topic": result["topic"]}
            elif chunk.name == "resolve_weak_point" and result.get("resolved"):
                yield {"type": "weak_point_resolved", "topic": result["topic"]}
        elif isinstance(chunk, AIMessage) and isinstance(chunk.content, str) and chunk.content:
            # A streamed chunk (AIMessageChunk is an AIMessage) or a whole reply from a model that does not stream.
            yield {"type": "token", "text": chunk.content}
