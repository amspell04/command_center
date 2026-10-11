import uuid

from langchain_core.tools import BaseTool, tool

from backend.crud import notes as notes_crud
from backend.crud import weak_points as weak_points_crud
from backend.db.session import get_session

MAX_TOPIC_CHARS = 120


def make_weak_point_tool(note_id: uuid.UUID) -> BaseTool:
    """The tool is bound to one note, so the model never supplies (or invents) an id.

    It returns (message for the model, result for the caller); `result["added"]` says whether the list changed.
    """

    @tool("add_weak_point", response_format="content_and_artifact")
    def add_weak_point_tool(topic: str) -> tuple[str, dict]:
        """Record a topic the user is weak on for this note.
        Call it once per topic, with a short topic (under 10 words) taken from the note.
        Never call it for a question the user answered correctly."""
        topic = " ".join(topic.split())
        result = {"topic": topic, "added": False}
        if not topic or len(topic) > MAX_TOPIC_CHARS:
            return f"Not added: the topic must be 1 to {MAX_TOPIC_CHARS} characters.", result
        with get_session() as db:
            if notes_crud.get_note(db, note_id) is None:
                return "Not added: the note no longer exists.", result
            _, changed = weak_points_crud.record_miss(db, note_id, topic)
        if not changed:
            return f"'{topic}' is already on the list.", result
        return f"Added '{topic}' to the weak points.", {**result, "added": True}

    return add_weak_point_tool


def make_resolve_weak_point_tool(note_id: uuid.UUID) -> BaseTool:
    """Bound to one note like the add tool. It can only resolve a topic that is already open on that note.

    It returns (message for the model, result for the caller); `result["resolved"]` says whether the list changed.
    """

    @tool("resolve_weak_point", response_format="content_and_artifact")
    def resolve_weak_point_tool(topic: str) -> tuple[str, dict]:
        """Mark a weak point as resolved once the user has explained it correctly.
        Pass the topic exactly as listed in <weak_points>. Call it once per topic."""
        topic = " ".join(topic.split())
        result = {"topic": topic, "resolved": False}
        with get_session() as db:
            weak_point = weak_points_crud.resolve_topic(db, note_id, topic) if topic else None
            if weak_point is None:
                return f"Not resolved: '{topic}' is not an open weak point.", result
            topic = weak_point.topic
        return f"Resolved '{topic}'.", {"topic": topic, "resolved": True}

    return resolve_weak_point_tool
