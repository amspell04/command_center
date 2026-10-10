"""MCP server exposing narrow task and note tools to the agents.

Tools call `crud/` directly with a per-call session. There are deliberately no
delete tools. Run with `python -m backend.services.mcp.server`.
"""
import uuid
from datetime import date

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from backend.config import settings
from backend.crud import notes as notes_crud
from backend.crud import tasks as tasks_crud
from backend.crud.schemas.note import NoteCreate
from backend.crud.schemas.task import TaskCreate
from backend.db.models import Note as NoteRow
from backend.db.session import get_session
from backend.models.note import Note
from backend.models.task import Task, TaskType

mcp = FastMCP("command-center")


def _dump(model, item) -> dict:
    return model.model_validate(item, from_attributes=True).model_dump(mode="json")


def _require(item, name: str):
    if item is None:
        raise ToolError(f"{name} not found")
    return item


def _uuid(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ToolError(f"{name} must be a UUID, got '{value}'")


# TASKS

@mcp.tool
def create_task(title: str, type: TaskType, due_date: date, requirement: str = "") -> dict:
    """Create a task. `type` is WORK or PERSONAL; `due_date` is YYYY-MM-DD."""
    data = TaskCreate(title=title, type=type, due_date=due_date, requirement=requirement)
    with get_session() as db:
        return _dump(Task, tasks_crud.create_task(db, data))


@mcp.tool
def list_tasks(due_date: date | None = None, completed: bool | None = None, type: TaskType | None = None) -> list[dict]:
    """List tasks, optionally filtered by due date (YYYY-MM-DD), completion, or type."""
    with get_session() as db:
        return [_dump(Task, t) for t in tasks_crud.list_tasks(db, due_date, completed, type)]


@mcp.tool
def update_task(
    task_id: str,
    title: str | None = None,
    type: TaskType | None = None,
    requirement: str | None = None,
    due_date: date | None = None,
) -> dict:
    """Change fields on a task. Only the fields you pass are changed."""
    fields = {
        k: v
        for k, v in {
            "title": title,
            "type": type.value if type else None,
            "requirement": requirement,
            "due_date": due_date.isoformat() if due_date else None,
        }.items()
        if v is not None
    }
    if not fields:
        raise ToolError("Pass at least one field to change")
    with get_session() as db:
        return _dump(Task, _require(tasks_crud.update_task(db, _uuid(task_id, "task_id"), **fields), "Task"))


@mcp.tool
def complete_task(task_id: str) -> dict:
    """Mark a task as completed."""
    with get_session() as db:
        return _dump(Task, _require(tasks_crud.complete_task(db, _uuid(task_id, "task_id")), "Task"))


# NOTES

@mcp.tool
def create_note(title: str, content: str = "") -> dict:
    """Create a note with one block of content."""
    blocks = [{"content": content}] if content else []
    data = NoteCreate(title=title, content_blocks=blocks)
    with get_session() as db:
        return _dump(Note, notes_crud.create_note(db, data))


@mcp.tool
def search_notes(query: str | None = None) -> list[dict]:
    """Search notes by title or content (case-insensitive). No query lists all notes."""
    with get_session() as db:
        return [_dump(Note, n) for n in notes_crud.list_notes(db, query)]


@mcp.tool
def add_note_block(note_id: str, content: str) -> dict:
    """Append a block of content to an existing note. Existing content is kept."""
    if not content.strip():
        raise ToolError("content must not be empty")
    nid = _uuid(note_id, "note_id")
    with get_session() as db:
        note = _require(db.get(NoteRow, nid), "Note")
        blocks = [*note.content_blocks, {"content": content}]
        return _dump(Note, _require(notes_crud.update_note(db, nid, content_blocks=blocks), "Note"))


def main() -> None:
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
