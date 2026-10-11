import asyncio
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from backend.agents import runner
from backend.agents.actions import UnknownAction, get_action
from backend.agents.task_agent.agent import DayPlan, GoalCheck, PlanItem
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


def note(client, content="alpha beta gamma", title="n"):
    return client.post("/notes", json={"title": title, "content": content}).json()


def plan(items, **over):
    return DayPlan(items=items, **{"week_status": "ON_TRACK", "week_summary": "Fine.", **over})


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
    assert post(client, "task", "plan_day", {"bogus": 1}).status_code == 422
    assert post(client, "task", "plan_day", {"date": "not-a-date"}).status_code == 422
    assert post(client, "notes", "summarize_note", {}).status_code == 422
    assert post(client, "notes", "summarize_note", {"note_id": "nope"}).status_code == 422
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
        plan(
            [
                PlanItem(task_id=uuid.UUID(b["id"]), reason="first", estimate_minutes=30),
                PlanItem(task_id=uuid.uuid4(), reason="invented", estimate_minutes=10),
                PlanItem(task_id=uuid.UUID(b["id"]), reason="duplicate", estimate_minutes=10),
            ]
        ),
    )
    items = post(client, "task", "plan_day").json()["items"]
    assert [(i["task_id"], i["reason"], i["estimate_minutes"]) for i in items] == [(b["id"], "first", 30), (a["id"], "", None)]
    assert items[0]["title"] == "today"


def test_plan_day_for_a_later_date_includes_that_day(client, monkeypatch):
    t = task(client, "future", TOMORROW)
    FakeRun(monkeypatch, plan([PlanItem(task_id=uuid.UUID(t["id"]), reason="r", estimate_minutes=15)]))
    r = post(client, "task", "plan_day", {"date": TOMORROW.isoformat()})
    assert [i["task_id"] for i in r.json()["items"]] == [t["id"]]


def test_plan_day_reports_week_stats_and_status(client, monkeypatch):
    monday = TODAY - timedelta(days=TODAY.weekday())
    done = task(client, "done", monday)
    client.patch(f"/tasks/{done['id']}/complete")
    open_today = task(client, "today", TODAY)
    task(client, "last week", monday - timedelta(days=1))  # outside the week
    FakeRun(monkeypatch, plan([PlanItem(task_id=uuid.UUID(open_today["id"]), reason="r", estimate_minutes=15)], week_status="AT_RISK", week_summary="Behind."))
    body = post(client, "task", "plan_day").json()
    assert body["status"] == "AT_RISK" and body["summary"] == "Behind."
    week = body["week"]
    assert (week["start"], week["end"]) == (monday.isoformat(), (monday + timedelta(days=6)).isoformat())
    assert (week["due_so_far"], week["completed_so_far"], week["overdue_open"]) == (2, 1, 0)


def test_plan_day_week_stats_for_a_fixed_wednesday(client, monkeypatch):
    for title, due in [("a", "2026-10-12"), ("b", "2026-10-13"), ("c", "2026-10-14"), ("d", "2026-10-16"), ("e", "2026-10-19")]:
        t = client.post("/tasks", json={"title": title, "type": "WORK", "due_date": due}).json()
        if title == "b":
            client.patch(f"/tasks/{t['id']}/complete")
    FakeRun(monkeypatch, plan([]))
    week = post(client, "task", "plan_day", {"date": "2026-10-14"}).json()["week"]
    assert week == {"start": "2026-10-12", "end": "2026-10-18", "due_so_far": 3, "completed_so_far": 1, "overdue_open": 1, "due_remaining": 1}


def test_plan_day_without_due_tasks_still_returns_week_stats_and_no_status(client, monkeypatch):
    FakeRun(monkeypatch)
    r = post(client, "task", "plan_day").json()
    assert r["status"] is None and r["summary"] == "" and r["goals"] == []
    assert r["week"]["due_so_far"] == 0


def test_plan_day_sends_week_numbers_and_goals_to_the_model(client, monkeypatch):
    task(client, "today", TODAY)
    g = client.post("/goals", json={"title": "Ship report", "details": "by Friday"}).json()
    fake = FakeRun(monkeypatch, plan([]))
    post(client, "task", "plan_day")
    message = fake.calls[0][1]
    assert g["id"] in message and "Ship report" in message and "by Friday" in message
    assert "1 tasks due so far" in message


def test_plan_day_message_says_when_no_goals_are_set(client, monkeypatch):
    task(client, "today", TODAY)
    fake = FakeRun(monkeypatch, plan([]))
    post(client, "task", "plan_day")
    assert "Goals: none set." in fake.calls[0][1]


def test_plan_day_keeps_only_real_goal_checks_once_each(client, monkeypatch):
    task(client, "today", TODAY)
    g = client.post("/goals", json={"title": "Ship report"}).json()
    FakeRun(
        monkeypatch,
        plan(
            [],
            goal_checks=[
                GoalCheck(goal_id=uuid.UUID(g["id"]), on_track=True, note="first"),
                GoalCheck(goal_id=uuid.uuid4(), on_track=False, note="invented"),
                GoalCheck(goal_id=uuid.UUID(g["id"]), on_track=False, note="duplicate"),
            ],
        ),
    )
    goals = post(client, "task", "plan_day").json()["goals"]
    assert goals == [{"goal_id": g["id"], "title": "Ship report", "on_track": True, "note": "first"}]


def test_day_plan_rejects_an_unknown_week_status():
    with pytest.raises(ValueError):
        plan([], week_status="GREAT")


def test_day_plan_requires_a_summary():
    with pytest.raises(ValueError):
        plan([], week_summary="")


@pytest.mark.parametrize("minutes", [0, 4, 481, -5])
def test_plan_item_rejects_out_of_range_estimates(minutes):
    with pytest.raises(ValueError):
        PlanItem(task_id=uuid.uuid4(), reason="r", estimate_minutes=minutes)


def test_plan_item_requires_an_estimate():
    with pytest.raises(ValueError):
        PlanItem(task_id=uuid.uuid4(), reason="r")


def test_plan_day_instructions_ask_for_estimates():
    assert "minutes" in get_action("task", "plan_day").instructions


# summarize_note

def test_summarize_unknown_or_empty_note(client, monkeypatch):
    fake = FakeRun(monkeypatch)
    assert post(client, "notes", "summarize_note", {"note_id": str(uuid.uuid4())}).status_code == 404
    empty = note(client, content="", title="empty")
    assert post(client, "notes", "summarize_note", {"note_id": empty["id"]}).status_code == 400
    blank = note(client, content="  ", title="blank")
    assert post(client, "notes", "summarize_note", {"note_id": blank["id"]}).status_code == 400
    assert fake.calls == []


def append_text(note_id, content):
    def write():
        with TestSession() as db:
            n = notes_crud.get_note(db, uuid.UUID(note_id))
            notes_crud.update_note(db, n.id, content=f"{n.content}\n\n{content}")

    return write


def test_summarize_returns_note_with_summary_appended(client, monkeypatch):
    n = note(client)
    fake = FakeRun(monkeypatch, "done", side_effect=append_text(n["id"], "Summary: short"))
    r = post(client, "notes", "summarize_note", {"note_id": n["id"]})
    assert r.status_code == 200
    assert r.json()["content"] == "alpha beta gamma\n\nSummary: short"
    assert n["id"] in fake.calls[0][1] and "alpha beta gamma" in fake.calls[0][1]


def test_summarize_fails_when_agent_saved_nothing_or_the_wrong_thing(client, monkeypatch):
    n = note(client)
    FakeRun(monkeypatch, "I summarized it")
    assert post(client, "notes", "summarize_note", {"note_id": n["id"]}).status_code == 502
    FakeRun(monkeypatch, "x", side_effect=append_text(n["id"], "not a summary"))
    assert post(client, "notes", "summarize_note", {"note_id": n["id"]}).status_code == 502


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
    assert plan.tools == ("list_tasks",)  # read only: no update tool
    assert get_action("notes", "summarize_note").tools == ("append_note_content",)


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
