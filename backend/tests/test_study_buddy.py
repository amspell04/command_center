import asyncio
import json
import uuid
from contextlib import contextmanager

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from backend.ai.agents.study_buddy import agent as sb_agent
from backend.ai.agents.study_buddy import tools as sb_tools
from backend.config import settings
from backend.crud import notes as notes_crud
from backend.crud import weak_points as weak_points_crud
from backend.crud.schemas.note import NoteCreate
from backend.services.api import study_buddy_routes
from backend.tests.conftest import TestSession

# tool: bound to one note, writes weak points through crud

@pytest.fixture
def tool_session(monkeypatch):
    @contextmanager
    def session():
        with TestSession() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    monkeypatch.setattr(sb_tools, "get_session", session)


def make_note(db, content="alpha", title="n"):
    return notes_crud.create_note(db, NoteCreate(title=title, content=content))


def call_tool(note_id, topic):
    tool = sb_tools.make_weak_point_tool(note_id)
    message = tool.invoke({"name": "add_weak_point", "args": {"topic": topic}, "id": "1", "type": "tool_call"})
    return message.content, message.artifact


def topics(db, note_id, resolved=None):
    db.expire_all()
    return [w.topic for w in weak_points_crud.list_weak_points(db, note_id, resolved)]


def test_tool_takes_only_a_topic_so_the_model_cannot_pick_a_note():
    tool = sb_tools.make_weak_point_tool(uuid.uuid4())
    assert tool.name == "add_weak_point" and list(tool.args) == ["topic"]


def test_tool_adds_the_topic_to_its_own_note_only(db, tool_session):
    mine, other = make_note(db, "mine", "a"), make_note(db, "other", "b")
    message, result = call_tool(mine.id, "  Cell   division ")
    assert result == {"topic": "Cell division", "added": True} and "Added" in message
    assert topics(db, mine.id) == ["Cell division"]
    assert topics(db, other.id) == []
    assert notes_crud.get_note(db, mine.id).content == "mine"


def test_tool_does_not_add_a_duplicate(db, tool_session):
    note = make_note(db)
    call_tool(note.id, "Mitosis")
    message, result = call_tool(note.id, "mitosis")
    assert result["added"] is False and "already" in message
    assert topics(db, note.id) == ["Mitosis"]


def test_tool_reopens_a_resolved_topic(db, tool_session):
    note = make_note(db)
    call_tool(note.id, "Mitosis")
    weak_points_crud.update_weak_point(db, weak_points_crud.list_weak_points(db, note.id)[0].id, resolved=True)
    _, result = call_tool(note.id, "Mitosis")
    assert result["added"] is True
    assert topics(db, note.id, resolved=False) == ["Mitosis"]


@pytest.mark.parametrize("topic", ["", "   ", "x" * (sb_tools.MAX_TOPIC_CHARS + 1)])
def test_tool_rejects_empty_and_oversized_topics(db, tool_session, topic):
    note = make_note(db)
    message, result = call_tool(note.id, topic)
    assert result["added"] is False and message.startswith("Not added")
    assert topics(db, note.id) == []


def test_tool_reports_a_deleted_note(db, tool_session):
    note = make_note(db)
    notes_crud.delete_note(db, note.id)
    message, result = call_tool(note.id, "Mitosis")
    assert result["added"] is False and "no longer exists" in message


# agent: translating the model stream into events

def patch_stream(monkeypatch, chunks):
    seen = {}

    async def fake_stream(name, prompt, tools, messages, recursion_limit):
        seen.update(name=name, prompt=prompt, tools=tools, messages=messages, limit=recursion_limit)
        for chunk in chunks:
            yield chunk

    monkeypatch.setattr(sb_agent, "stream_agent", fake_stream)
    return seen


async def events(note_id=None, history=None, weak_points=()):
    gen = sb_agent.study_buddy_events(note_id or uuid.uuid4(), "Cells", "body", list(weak_points), history or [])
    return [e async for e in gen]


def tool_message(result, name="add_weak_point"):
    return ToolMessage(content="ok", tool_call_id="1", name=name, artifact=result)


@pytest.mark.asyncio
async def test_events_stream_tokens_and_report_added_weak_points(monkeypatch):
    patch_stream(
        monkeypatch,
        [
            AIMessageChunk(content="Q1?"),
            tool_message({"topic": "Mitosis", "added": True}),
            AIMessageChunk(content=" Next."),
        ],
    )
    assert await events() == [
        {"type": "token", "text": "Q1?"},
        {"type": "weak_point", "topic": "Mitosis"},
        {"type": "token", "text": " Next."},
    ]


@pytest.mark.asyncio
async def test_events_skip_empty_chunks_unadded_topics_and_other_tools(monkeypatch):
    patch_stream(
        monkeypatch,
        [
            AIMessageChunk(content=""),
            AIMessageChunk(content=[{"type": "text", "text": "x"}]),
            tool_message({"topic": "Mitosis", "added": False}),
            tool_message({"topic": "Mitosis", "added": True}, name="other_tool"),
            tool_message(None),
        ],
    )
    assert await events() == []


@pytest.mark.asyncio
async def test_events_run_the_agent_with_the_note_and_history(monkeypatch):
    seen = patch_stream(monkeypatch, [])
    note_id = uuid.uuid4()
    history = [{"role": "user", "content": "Start"}]
    await events(note_id, history)
    assert seen["name"] == "study_buddy" and seen["messages"] == history and seen["limit"] == sb_agent.RECURSION_LIMIT
    assert [t.name for t in seen["tools"]] == ["add_weak_point"]
    assert "Cells" in seen["prompt"] and "body" in seen["prompt"] and "add_weak_point" in seen["prompt"]


@pytest.mark.asyncio
async def test_events_pass_open_weak_points_to_the_prompt(monkeypatch):
    seen = patch_stream(monkeypatch, [])
    await events(weak_points=["Mitosis", "Meiosis"])
    assert "<weak_points>\n- Mitosis\n- Meiosis\n</weak_points>" in seen["prompt"]


def test_system_prompt_omits_the_weak_points_block_when_there_are_none():
    assert "</weak_points>" not in sb_agent.system_prompt("t", "body")
    assert "</weak_points>" not in sb_agent.system_prompt("t", "body", [])


def test_system_prompt_caps_the_weak_points():
    topics = [f"topic{i:03}" for i in range(sb_agent.MAX_WEAK_POINTS + 5)]
    prompt = sb_agent.system_prompt("t", "body", topics)
    assert prompt.count("- topic") == sb_agent.MAX_WEAK_POINTS and f"topic{sb_agent.MAX_WEAK_POINTS:03}" not in prompt


def test_system_prompt_caps_the_note_text():
    prompt = sb_agent.system_prompt("t", "§" * (sb_agent.MAX_NOTE_CHARS + 500))
    assert prompt.count("§") == sb_agent.MAX_NOTE_CHARS


# route

def make_note_via_api(client, content="alpha beta", title="Cells"):
    return client.post("/notes", json={"title": title, "content": content}).json()


def fake_events(monkeypatch, items=(), exc=None, delay=0):
    calls = []

    async def gen(note_id, title, text, weak_points, history):
        calls.append((note_id, title, text, weak_points, history))
        for item in items:
            yield item
        if delay:
            await asyncio.sleep(delay)
        if exc:
            raise exc

    monkeypatch.setattr(study_buddy_routes, "study_buddy_events", gen)
    return calls


def stream(client, note_id, messages=None, **over):
    body = {"note_id": note_id, "messages": messages or [{"role": "user", "content": "Start"}], **over}
    return client.post("/agents/notes/study_buddy/stream", json=body)


def parse(response):
    return [json.loads(line[6:]) for line in response.text.split("\n\n") if line.startswith("data: ")]


def test_stream_sends_events_then_done(client, monkeypatch):
    note = make_note_via_api(client)
    calls = fake_events(monkeypatch, [{"type": "token", "text": "Hi"}, {"type": "weak_point", "topic": "T"}])
    r = stream(client, note["id"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert parse(r) == [{"type": "token", "text": "Hi"}, {"type": "weak_point", "topic": "T"}, {"type": "done"}]
    assert calls[0][1:] == ("Cells", "alpha beta", [], [{"role": "user", "content": "Start"}])


def test_stream_gives_the_agent_only_this_notes_open_weak_points(client, monkeypatch):
    note, other = make_note_via_api(client), make_note_via_api(client, title="Other")
    with TestSession() as db:
        for n, topic in [(note, "Open"), (note, "Done"), (other, "Elsewhere")]:
            wp, _ = weak_points_crud.record_miss(db, uuid.UUID(n["id"]), topic)
            if topic == "Done":
                weak_points_crud.update_weak_point(db, wp.id, resolved=True)
    calls = fake_events(monkeypatch)
    stream(client, note["id"])
    assert calls[0][3] == ["Open"]


def test_stream_sends_only_the_latest_turns(client, monkeypatch):
    note = make_note_via_api(client)
    calls = fake_events(monkeypatch)
    turns = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(31)]
    stream(client, note["id"], turns)
    sent = calls[0][4]
    assert len(sent) == study_buddy_routes.MAX_HISTORY and sent[-1]["content"] == "m30"


def test_unknown_note_is_404_and_an_empty_note_is_400(client, monkeypatch):
    calls = fake_events(monkeypatch)
    assert stream(client, str(uuid.uuid4())).status_code == 404
    assert stream(client, make_note_via_api(client, content="  ")["id"]).status_code == 400
    assert calls == []


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
        [{"role": "system", "content": "x"}],
        [{"role": "user", "content": ""}],
        [{"role": "user", "content": "x" * 4001}],
        [{"role": "user", "content": "q", "extra": 1}],
        [{"role": "user", "content": "q"}] * 101,
    ],
)
def test_bad_messages_are_422_before_the_model_runs(client, monkeypatch, messages):
    note = make_note_via_api(client)
    calls = fake_events(monkeypatch)
    r = client.post("/agents/notes/study_buddy/stream", json={"note_id": note["id"], "messages": messages})
    assert r.status_code == 422 and calls == []


def test_bad_note_id_or_extra_fields_are_422(client, monkeypatch):
    note = make_note_via_api(client)
    fake_events(monkeypatch)
    assert stream(client, "nope").status_code == 422
    assert stream(client, note["id"], bogus=1).status_code == 422
    assert client.post("/agents/notes/study_buddy/stream", json={"note_id": note["id"]}).status_code == 422


def test_a_failure_mid_stream_keeps_the_partial_reply_and_ends_with_an_error(client, monkeypatch):
    note = make_note_via_api(client)
    fake_events(monkeypatch, [{"type": "token", "text": "Part"}], exc=ConnectionError("down"))
    frames = parse(stream(client, note["id"]))
    assert frames[0] == {"type": "token", "text": "Part"}
    assert frames[-1]["type"] == "error" and "Ollama" in frames[-1]["message"]
    assert not any(f["type"] == "done" for f in frames)


def test_a_slow_stream_times_out_with_an_error_event(client, monkeypatch):
    note = make_note_via_api(client)
    fake_events(monkeypatch, delay=1)
    monkeypatch.setattr(settings, "agent_timeout_seconds", 0.01)
    assert parse(stream(client, note["id"])) == [{"type": "error", "message": "The agent timed out"}]
