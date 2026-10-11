import uuid
from contextlib import contextmanager

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

from backend.services.mcp import server
from backend.tests.conftest import TestSession

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _test_session(monkeypatch):
    @contextmanager
    def session():
        with TestSession() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    monkeypatch.setattr(server, "get_session", session)


@pytest_asyncio.fixture
async def client():
    async with Client(server.mcp) as c:
        yield c


async def call(client, name, **args):
    return (await client.call_tool(name, args)).data


async def test_exposes_no_delete_tools(client):
    names = {t.name for t in await client.list_tools()}
    assert names == {"create_task", "list_tasks", "update_task", "complete_task", "create_note", "search_notes", "append_note_content"}
    assert not any("delete" in n for n in names)


# tasks: likely path

async def test_task_create_list_update_complete(client):
    created = await call(client, "create_task", title="Call dentist", type="PERSONAL", due_date="2026-10-16")
    assert created["title"] == "Call dentist" and created["completed"] is False

    listed = await call(client, "list_tasks", due_date="2026-10-16")
    assert [t["id"] for t in listed] == [created["id"]]

    updated = await call(client, "update_task", task_id=created["id"], title="Call the dentist")
    assert updated["title"] == "Call the dentist" and updated["type"] == "PERSONAL"

    done = await call(client, "complete_task", task_id=created["id"])
    assert done["completed"] is True
    assert await call(client, "list_tasks", completed=False) == []


# tasks: negative

async def test_task_invalid_type_rejected(client):
    with pytest.raises(ToolError):
        await call(client, "create_task", title="x", type="HOBBY", due_date="2026-10-16")


async def test_task_empty_title_rejected(client):
    with pytest.raises(Exception):
        await call(client, "create_task", title="", type="WORK", due_date="2026-10-16")


async def test_task_bad_date_rejected(client):
    with pytest.raises(ToolError):
        await call(client, "create_task", title="x", type="WORK", due_date="next friday")


async def test_update_task_without_fields_rejected(client):
    task = await call(client, "create_task", title="x", type="WORK", due_date="2026-10-16")
    with pytest.raises(ToolError, match="at least one field"):
        await call(client, "update_task", task_id=task["id"])


@pytest.mark.parametrize("tool", ["complete_task", "update_task"])
async def test_task_unknown_id(client, tool):
    args = {"task_id": str(uuid.uuid4())} | ({"title": "x"} if tool == "update_task" else {})
    with pytest.raises(ToolError, match="Task not found"):
        await call(client, tool, **args)


async def test_task_non_uuid_id(client):
    with pytest.raises(ToolError, match="must be a UUID"):
        await call(client, "complete_task", task_id="abc")


# notes: likely path

async def test_note_create_search_append(client):
    note = await call(client, "create_note", title="Trip ideas", content="Lisbon")
    assert note["content"] == "Lisbon"

    found = await call(client, "search_notes", query="lisbon")
    assert [n["id"] for n in found] == [note["id"]]

    appended = await call(client, "append_note_content", note_id=note["id"], content="Porto")
    assert appended["content"] == "Lisbon\n\nPorto"

    empty = await call(client, "create_note", title="Blank")
    assert (await call(client, "append_note_content", note_id=empty["id"], content="First"))["content"] == "First"


async def test_search_notes_no_query_lists_all(client):
    await call(client, "create_note", title="a")
    await call(client, "create_note", title="b")
    assert len(await call(client, "search_notes")) == 2


# notes: negative

async def test_search_notes_no_match(client):
    await call(client, "create_note", title="a", content="b")
    assert await call(client, "search_notes", query="zzz") == []


async def test_note_empty_title_rejected(client):
    with pytest.raises(Exception):
        await call(client, "create_note", title="")


async def test_append_content_empty_content_rejected(client):
    note = await call(client, "create_note", title="a")
    with pytest.raises(ToolError, match="must not be empty"):
        await call(client, "append_note_content", note_id=note["id"], content="  ")


async def test_append_content_unknown_note(client):
    with pytest.raises(ToolError, match="Note not found"):
        await call(client, "append_note_content", note_id=str(uuid.uuid4()), content="x")


async def test_append_content_non_uuid_id(client):
    with pytest.raises(ToolError, match="must be a UUID"):
        await call(client, "append_note_content", note_id="abc", content="x")
