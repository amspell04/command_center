import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from backend.ai.agents.runner import stream_agent
from backend.ai.agents.study_buddy.tools import make_weak_point_tool

# Keeps the prompt inside a small model's context window.
MAX_NOTE_CHARS = 8000
# Each tool call takes two graph steps, so this allows a few weak points per reply.
RECURSION_LIMIT = 12
# Open weak points shown to the model.
MAX_WEAK_POINTS = 20

_PROMPT = (Path(__file__).parent / "prompt.md").read_text().strip()


def system_prompt(title: str, text: str, weak_points: list[str] = ()) -> str:
    prompt = f"{_PROMPT}\n\n<note title={title!r}>\n{text[:MAX_NOTE_CHARS]}\n</note>"
    if weak_points:
        listed = "\n".join(f"- {topic}" for topic in weak_points[:MAX_WEAK_POINTS])
        prompt += f"\n\n<weak_points>\n{listed}\n</weak_points>"
    return prompt


async def study_buddy_events(
    note_id: uuid.UUID, title: str, text: str, weak_points: list[str], history: list[dict]
) -> AsyncIterator[dict]:
    """One reply in a quiz. `weak_points` are the topics still open on the note.
    `history` is the conversation so far as {"role", "content"} dicts.

    Yields {"type": "token", "text"} as the reply streams and {"type": "weak_point", "topic"} each time the
    agent adds one.
    """
    async for chunk in stream_agent(
        "study_buddy", system_prompt(title, text, weak_points), [make_weak_point_tool(note_id)], history, RECURSION_LIMIT
    ):
        if isinstance(chunk, ToolMessage):
            result = chunk.artifact
            if chunk.name == "add_weak_point" and isinstance(result, dict) and result.get("added"):
                yield {"type": "weak_point", "topic": result["topic"]}
        elif isinstance(chunk, AIMessage) and isinstance(chunk.content, str) and chunk.content:
            # A streamed chunk (AIMessageChunk is an AIMessage) or a whole reply from a model that does not stream.
            yield {"type": "token", "text": chunk.content}
