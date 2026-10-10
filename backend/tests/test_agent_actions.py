import asyncio
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from backend.agents import runner
from backend.agents.actions import UnknownAction, get_action
from backend.agents.notes_agent.agent import CritiquePoint, NoteCritique
from backend.agents.task_agent.agent import DayPlan, OverdueSweep, PlanItem, RescheduleProposal
from backend.config import settings
from backend.crud import notes as notes_crud
from backend.services.api import agent_routes
from backend.tests.conftest import TestSession

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def task(client, title, due, **over):
    r = client.post("/tasks", json={"title": title, "type": "WORK", "due_date": due.isoformat(), **over})
    return r.json()


def note(client, blocks=("alpha beta gamma",), title="n"):
    return client.post("/notes", json={"title": title, "content_blocks": [{"content": b} for b in blocks]}).json()


class FakeRun:
    """Stands in for run_action; records calls and returns or raises what the test set."""

    def __init__(self, monkeypatch, result=None, exc=None, side_effect=None):
        self.calls = []
        self.result, self.exc, self.side_effect = result, exc, side_effect
        monkeypatch.setattr(agent_routes, "run_action", self)

    async def __call__(self, action, message):
        self.calls.append((action.name, message))
        if self.side_effect:
            self.side_effect()
        if self.exc:
            raise self.exc
        return self.result


def post(client, agent, name, body=None):
    return client.post(f"/agents/{agent}/actions/{name}", json=body or {})


# routing

def test_unknown_agent_or_action_is_404(client):
    assert post(client, "nope", "plan_day").status_code == 404
    assert post(client, "task", "nope").status_code == 404
    assert post(client, "notes", "plan_day").status_code == 404


def test_bad_params_are_rejected_before_the_model_runs(client, monkeypatch):
    fake = FakeRun(monkeypatch)
    assert post(client, "task", "overdue_sweep", {"bogus": 1}).status_code == 422
    assert post(client, "task", "plan_day", {"date": "not-a-date"}).status_code == 422
    assert post(client, "notes", "critique_note", {}).status_code == 422
    assert post(client, "notes", "critique_note", {"note_id": "nope"}).status_code == 422
    assert fake.calls == []


# plan_day

def test_plan_day_without_tasks_skips_the_model(client, monkeypatch):
    fake = FakeRun(monkeypatch)
    task(client, "later", TOMORROW)
    done = task(client, "done", YESTERDAY)
    client.patch(f"/tasks/{done['id']}/complete")
    r = post(client, "task", "plan_day")
    assert r.status_code == 200 and r.json()["items"] == []
    assert fake.calls == []


def test_plan_day_keeps_only_real_due_tasks_and_never_drops_one(client, monkeypatch):
    a = task(client, "overdue", YESTERDAY)
    b = task(client, "today", TODAY)
    task(client, "future", TOMORROW)
    FakeRun(
        monkeypatch,
        DayPlan(
            items=[
                PlanItem(task_id=uuid.UUID(b["id"]), reason="first"),
                PlanItem(task_id=uuid.uuid4(), reason="invented"),
                PlanItem(task_id=uuid.UUID(b["id"]), reason="duplicate"),
            ]
        ),
    )
    items = post(client, "task", "plan_day").json()["items"]
    assert [(i["task_id"], i["reason"]) for i in items] == [(b["id"], "first"), (a["id"], "")]
    assert items[0]["title"] == "today"


def test_plan_day_for_a_later_date_includes_that_day(client, monkeypatch):
    t = task(client, "future", TOMORROW)
    FakeRun(monkeypatch, DayPlan(items=[PlanItem(task_id=uuid.UUID(t["id"]), reason="r")]))
    r = post(client, "task", "plan_day", {"date": TOMORROW.isoformat()})
    assert [i["task_id"] for i in r.json()["items"]] == [t["id"]]


# overdue_sweep

def test_sweep_with_nothing_overdue_skips_the_model(client, monkeypatch):
    fake = FakeRun(monkeypatch)
    task(client, "today", TODAY)
    assert post(client, "task", "overdue_sweep").json() == {"proposals": []}
    assert fake.calls == []


def test_sweep_drops_invalid_proposals_and_changes_nothing(client, monkeypatch):
    a = task(client, "a", YESTERDAY)
    b = task(client, "b", YESTERDAY)
    ok = RescheduleProposal(task_id=uuid.UUID(a["id"]), new_due_date=TOMORROW, reason="r")
    FakeRun(
        monkeypatch,
        OverdueSweep(
            proposals=[
                ok,
                ok,  # duplicate
                RescheduleProposal(task_id=uuid.UUID(b["id"]), new_due_date=YESTERDAY, reason="still overdue"),
                RescheduleProposal(task_id=uuid.uuid4(), new_due_date=TOMORROW, reason="invented"),
            ]
        ),
    )
    proposals = post(client, "task", "overdue_sweep").json()["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["task_id"] == a["id"] and proposals[0]["current_due_date"] == YESTERDAY.isoformat()
    assert proposals[0]["new_due_date"] == TOMORROW.isoformat()
    assert {t["due_date"] for t in client.get("/tasks").json()} == {YESTERDAY.isoformat()}


def test_sweep_ignores_completed_tasks(client, monkeypatch):
    done = task(client, "done", YESTERDAY)
    client.patch(f"/tasks/{done['id']}/complete")
    fake = FakeRun(monkeypatch)
    assert post(client, "task", "overdue_sweep").json() == {"proposals": []}
    assert fake.calls == []


# summarize_note

def test_summarize_unknown_or_empty_note(client, monkeypatch):
    fake = FakeRun(monkeypatch)
    assert post(client, "notes", "summarize_note", {"note_id": str(uuid.uuid4())}).status_code == 404
    empty = note(client, blocks=(), title="empty")
    assert post(client, "notes", "summarize_note", {"note_id": empty["id"]}).status_code == 400
    blank = note(client, blocks=("  ",), title="blank")
    assert post(client, "notes", "summarize_note", {"note_id": blank["id"]}).status_code == 400
    assert fake.calls == []


def append_block(note_id, content):
    def write():
        with TestSession() as db:
            n = notes_crud.get_note(db, uuid.UUID(note_id))
            notes_crud.update_note(db, n.id, content_blocks=[*n.content_blocks, {"content": content}])

    return write


def test_summarize_returns_note_with_summary_block(client, monkeypatch):
    n = note(client)
    fake = FakeRun(monkeypatch, "done", side_effect=append_block(n["id"], "Summary: short"))
    r = post(client, "notes", "summarize_note", {"note_id": n["id"]})
    assert r.status_code == 200
    assert r.json()["content_blocks"][-1] == {"content": "Summary: short"}
    assert len(r.json()["content_blocks"]) == 2
    assert n["id"] in fake.calls[0][1] and "alpha beta gamma" in fake.calls[0][1]


def test_summarize_fails_when_agent_saved_nothing_or_the_wrong_thing(client, monkeypatch):
    n = note(client)
    FakeRun(monkeypatch, "I summarized it")
    assert post(client, "notes", "summarize_note", {"note_id": n["id"]}).status_code == 502
    FakeRun(monkeypatch, "x", side_effect=append_block(n["id"], "not a summary"))
    assert post(client, "notes", "summarize_note", {"note_id": n["id"]}).status_code == 502


# critique_note

def test_critique_unknown_or_empty_note(client, monkeypatch):
    fake = FakeRun(monkeypatch)
    assert post(client, "notes", "critique_note", {"note_id": str(uuid.uuid4())}).status_code == 404
    empty = note(client, blocks=())
    assert post(client, "notes", "critique_note", {"note_id": empty["id"]}).status_code == 400
    assert fake.calls == []


def test_critique_drops_points_with_made_up_quotes(client, monkeypatch):
    n = note(client, blocks=("Water boils at 100C.", "Salt  raises\nthe boiling point."))
    FakeRun(
        monkeypatch,
        NoteCritique(
            gaps=[
                CritiquePoint(point="no pressure", quote="water boils at 100c."),
                CritiquePoint(point="x", quote="never written"),
            ],
            unclear_claims=[CritiquePoint(point="vague", quote="Salt raises the boiling point.")],
            questions=["Why?"],
        ),
    )
    r = post(client, "notes", "critique_note", {"note_id": n["id"]})
    assert r.status_code == 200
    body = r.json()
    assert [g["point"] for g in body["gaps"]] == ["no pressure"]
    assert [c["point"] for c in body["unclear_claims"]] == ["vague"]
    assert body["questions"] == ["Why?"]


def test_critique_does_not_modify_the_note(client, monkeypatch):
    n = note(client)
    FakeRun(monkeypatch, NoteCritique(gaps=[], unclear_claims=[], questions=[]))
    post(client, "notes", "critique_note", {"note_id": n["id"]})
    assert client.get("/notes").json()[0]["content_blocks"] == n["content_blocks"]


# failure mapping

@pytest.mark.parametrize(
    "exc, status",
    [
        (ConnectionError("down"), 503),
        (RuntimeError("MCP server is missing tools"), 503),
        (runner.AgentOutputError("no structure"), 502),
    ],
)
def test_agent_failures_map_to_http_errors(client, monkeypatch, exc, status):
    task(client, "overdue", YESTERDAY)
    FakeRun(monkeypatch, exc=exc)
    assert post(client, "task", "plan_day").status_code == status


def test_timeout_is_504(client, monkeypatch):
    task(client, "overdue", YESTERDAY)

    async def slow(action, message):
        await asyncio.sleep(1)

    monkeypatch.setattr(agent_routes, "run_action", slow)
    monkeypatch.setattr(settings, "agent_timeout_seconds", 0.01)
    assert post(client, "task", "plan_day").status_code == 504


# framework

def test_get_action_unknown_raises():
    with pytest.raises(UnknownAction):
        get_action("task", "nope")
    with pytest.raises(UnknownAction):
        get_action("nope", "plan_day")


def test_actions_carry_base_and_action_prompt_and_read_only_tools():
    plan = get_action("task", "plan_day")
    assert "manage the user's tasks" in plan.instructions and "plan the user's day" in plan.instructions
    assert get_action("task", "overdue_sweep").tools == ("list_tasks",)  # proposals only: no update tool
    assert get_action("notes", "critique_note").tools == ()


class FakeAgent:
    def __init__(self, result):
        self.result = result

    async def ainvoke(self, payload):
        return self.result


def patch_agent(monkeypatch, result):
    seen = {}

    def fake_create_agent(llm, tools, **kw):
        seen.update(tools=tools, **kw)
        return FakeAgent(result)

    async def fake_load(allowed):
        seen["loaded"] = list(allowed)
        return ["tool"]

    monkeypatch.setattr(runner, "create_agent", fake_create_agent)
    monkeypatch.setattr(runner, "load_tools", fake_load)
    monkeypatch.setattr(runner, "get_llm", lambda name: None)
    return seen


@pytest.mark.asyncio
async def test_run_agent_returns_structured_output(monkeypatch):
    seen = patch_agent(monkeypatch, {"messages": [SimpleNamespace(content="text")], "structured_response": "obj"})
    out = await runner.run_agent("a", "p", ["list_tasks"], "hi", response_format=dict)
    assert out["output"] == "obj" and seen["loaded"] == ["list_tasks"] and seen["response_format"] is dict


@pytest.mark.asyncio
async def test_run_agent_without_tools_skips_the_mcp_server(monkeypatch):
    seen = patch_agent(monkeypatch, {"messages": [SimpleNamespace(content="text")]})
    out = await runner.run_agent("a", "p", [], "hi")
    assert out["output"] == "text" and "loaded" not in seen and seen["tools"] == []


@pytest.mark.asyncio
async def test_run_agent_missing_structure_raises(monkeypatch):
    patch_agent(monkeypatch, {"messages": [SimpleNamespace(content="just prose")]})
    with pytest.raises(runner.AgentOutputError):
        await runner.run_agent("a", "p", [], "hi", response_format=dict)
