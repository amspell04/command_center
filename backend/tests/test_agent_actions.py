import asyncio
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from langchain_core.exceptions import OutputParserException

from backend.ai.agents import runner
from backend.ai.llm import notes as notes_llm
from backend.ai.llm import tasks as tasks_llm
from backend.ai.llm.client import load_prompt
from backend.ai.llm.tasks import DayPlan, GoalCheck, PlanItem
from backend.config import settings

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def task(client, title, due, **over):
    r = client.post("/tasks", json={"title": title, "type": "WORK", "due_date": due.isoformat(), **over})
    return r.json()


def note(client, content="alpha beta gamma", title="n"):
    return client.post("/notes", json={"title": title, "content": content}).json()


def saved_content(client, note_id):
    return next(n["content"] for n in client.get("/notes").json() if n["id"] == note_id)


def plan(items, **over):
    return DayPlan(items=items, **{"week_status": "ON_TRACK", "week_summary": "Fine.", **over})


class FakeLLM:
    """Stands in for one llm function; records its args and returns or raises what the test set."""

    def __init__(self, monkeypatch, module, name, result=None, exc=None):
        self.calls = []
        self.result, self.exc = result, exc
        monkeypatch.setattr(module, name, self)

    async def __call__(self, *args):
        self.calls.append(args)
        if self.exc:
            raise self.exc
        return self.result


def FakeRun(monkeypatch, result=None, exc=None):
    return FakeLLM(monkeypatch, tasks_llm, "plan_day", result, exc)


def FakeSummary(monkeypatch, result="A short summary.", exc=None):
    return FakeLLM(monkeypatch, notes_llm, "summarize_note", result, exc)


def post(client, agent, name, body=None):
    return client.post(f"/agents/{agent}/actions/{name}", json=body or {})


# routing

def test_unknown_agent_or_action_is_404(client):
    assert post(client, "nope", "plan_day").status_code == 404
    assert post(client, "task", "nope").status_code == 404
    assert post(client, "notes", "plan_day").status_code == 404


def test_bad_params_are_rejected_before_the_model_runs(client, monkeypatch):
    fake, summary = FakeRun(monkeypatch), FakeSummary(monkeypatch)
    assert post(client, "task", "plan_day", {"bogus": 1}).status_code == 422
    assert post(client, "task", "plan_day", {"date": "not-a-date"}).status_code == 422
    assert post(client, "notes", "summarize_note", {}).status_code == 422
    assert post(client, "notes", "summarize_note", {"note_id": "nope"}).status_code == 422
    assert fake.calls == [] and summary.calls == []


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
    task(client, "last week", monday - timedelta(days=1))  # outside the week, but still overdue
    FakeRun(monkeypatch, plan([PlanItem(task_id=uuid.UUID(open_today["id"]), reason="r", estimate_minutes=15)], week_status="AT_RISK", week_summary="Behind."))
    body = post(client, "task", "plan_day").json()
    assert body["status"] == "AT_RISK" and body["summary"] == "Behind."
    week = body["week"]
    assert (week["start"], week["end"]) == (monday.isoformat(), (monday + timedelta(days=6)).isoformat())
    assert (week["due_so_far"], week["completed_so_far"], week["overdue_open"]) == (2, 1, 1)


def test_plan_day_week_stats_for_a_fixed_wednesday(client, monkeypatch):
    for title, due in [("a", "2026-10-12"), ("b", "2026-10-13"), ("c", "2026-10-14"), ("d", "2026-10-16"), ("e", "2026-10-19")]:
        t = client.post("/tasks", json={"title": title, "type": "WORK", "due_date": due}).json()
        if title == "b":
            client.patch(f"/tasks/{t['id']}/complete")
    FakeRun(monkeypatch, plan([]))
    week = post(client, "task", "plan_day", {"date": "2026-10-14"}).json()["week"]
    assert week == {"start": "2026-10-12", "end": "2026-10-18", "due_so_far": 3, "completed_so_far": 1, "overdue_open": 1, "due_remaining": 1}


def test_plan_day_counts_overdue_tasks_from_earlier_weeks(client, monkeypatch):
    task(client, "last week", date(2026, 10, 7))
    task(client, "this week", date(2026, 10, 13))
    FakeRun(monkeypatch, plan([]))
    week = post(client, "task", "plan_day", {"date": "2026-10-14"}).json()["week"]
    assert week["overdue_open"] == 2 and week["due_so_far"] == 1


def test_plan_day_passes_the_requested_day_to_the_model(client, monkeypatch):
    task(client, "t", date(2026, 10, 13))
    fake = FakeRun(monkeypatch, plan([]))
    post(client, "task", "plan_day", {"date": "2026-10-14"})
    assert fake.calls[0][1] == date(2026, 10, 14)


@pytest.mark.asyncio
async def test_guarded_lets_http_errors_through():
    from fastapi import HTTPException

    from backend.services.helpers import guarded

    async def work():
        raise HTTPException(404, "nope")

    with pytest.raises(HTTPException) as e:
        await guarded("x", work())
    assert e.value.status_code == 404


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
    message = fake.calls[0][0]
    assert g["id"] in message and "Ship report" in message and "by Friday" in message
    assert "1 tasks due so far" in message


def test_plan_day_sends_the_due_tasks_with_ids_and_requirements(client, monkeypatch):
    a = task(client, "overdue", YESTERDAY, requirement="needs the report")
    b = task(client, "today", TODAY)
    task(client, "future", TOMORROW)
    done = task(client, "done", TODAY)
    client.patch(f"/tasks/{done['id']}/complete")
    fake = FakeRun(monkeypatch, plan([]))
    post(client, "task", "plan_day")
    message = fake.calls[0][0]
    assert f"id {a['id']}: overdue" in message and "requirement: needs the report" in message
    assert f"id {b['id']}: today" in message
    assert "future" not in message and "done" not in message
    assert message.index("overdue") < message.index("today")  # earliest due first


def test_plan_day_message_says_when_no_goals_are_set(client, monkeypatch):
    task(client, "today", TODAY)
    fake = FakeRun(monkeypatch, plan([]))
    post(client, "task", "plan_day")
    assert "Goals: none set." in fake.calls[0][0]


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


def test_plan_day_prompt_asks_for_estimates_and_needs_no_tools():
    prompt = load_prompt("plan_day")
    assert "minutes" in prompt and "list_tasks" not in prompt and "{today}" in prompt


# summarize_note

def test_summarize_unknown_or_empty_note(client, monkeypatch):
    fake = FakeSummary(monkeypatch)
    assert post(client, "notes", "summarize_note", {"note_id": str(uuid.uuid4())}).status_code == 404
    empty = note(client, content="", title="empty")
    assert post(client, "notes", "summarize_note", {"note_id": empty["id"]}).status_code == 400
    blank = note(client, content="  ", title="blank")
    assert post(client, "notes", "summarize_note", {"note_id": blank["id"]}).status_code == 400
    assert fake.calls == []


def summarize(client, n, **extra):
    return post(client, "notes", "summarize_note", {"note_id": n["id"], **extra})


def test_summarize_stores_the_summary_and_leaves_content_alone(client, monkeypatch):
    n = note(client, title="Cells")
    fake = FakeSummary(monkeypatch, "Short.")
    r = summarize(client, n)
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "Short." and body["summary_stale"] is False and body["summary_generated_at"]
    assert body["content"] == "alpha beta gamma"
    assert fake.calls == [("Cells", "alpha beta gamma")]
    assert saved_content(client, n["id"]) == "alpha beta gamma"
    stored = next(x for x in client.get("/notes").json() if x["id"] == n["id"])
    assert stored["summary"] == "Short."


def test_summarize_reuses_a_current_summary_without_calling_the_model(client, monkeypatch):
    n = note(client)
    fake = FakeSummary(monkeypatch, "First.")
    first = summarize(client, n).json()
    second = summarize(client, n).json()
    assert len(fake.calls) == 1
    assert second["summary"] == "First." and second["summary_generated_at"] == first["summary_generated_at"]


def test_summarize_force_regenerates(client, monkeypatch):
    n = note(client)
    fake = FakeSummary(monkeypatch, "First.")
    summarize(client, n)
    fake.result = "Second."
    r = summarize(client, n, force=True)
    assert len(fake.calls) == 2 and r.json()["summary"] == "Second."


@pytest.mark.parametrize("change", [{"content": "changed text"}, {"title": "new title"}])
def test_an_edit_marks_the_summary_stale_and_summarize_regenerates(client, monkeypatch, change):
    n = note(client)
    fake = FakeSummary(monkeypatch, "First.")
    summarize(client, n)
    stale = client.patch(f"/notes/{n['id']}", json=change).json()
    assert stale["summary"] == "First." and stale["summary_stale"] is True
    fake.result = "Fresh."
    r = summarize(client, n).json()
    assert len(fake.calls) == 2 and r["summary"] == "Fresh." and r["summary_stale"] is False


def test_whitespace_only_edits_do_not_make_the_summary_stale(client, monkeypatch):
    n = note(client)
    FakeSummary(monkeypatch)
    summarize(client, n)
    assert client.patch(f"/notes/{n['id']}", json={"content": "alpha beta gamma\n\n"}).json()["summary_stale"] is False


def test_notes_without_a_summary_are_not_stale(client):
    n = note(client)
    assert n["summary"] is None and n["summary_stale"] is False


def test_summary_cannot_be_set_through_the_notes_api(client):
    n = note(client)
    assert client.patch(f"/notes/{n['id']}", json={"summary": "forged"}).status_code == 422
    assert client.post("/notes", json={"title": "t", "summary": "forged"}).status_code == 422


def test_summarize_rejects_a_non_boolean_force(client, monkeypatch):
    fake = FakeSummary(monkeypatch)
    assert summarize(client, note(client), force="maybe").status_code == 422
    assert fake.calls == []


def test_summarize_does_not_double_the_label(client, monkeypatch):
    n = note(client)
    FakeSummary(monkeypatch, "Summary: Short.")
    assert summarize(client, n).json()["summary"] == "Short."


@pytest.mark.parametrize("reply", ["", "   ", "Summary:"])
def test_summarize_with_an_empty_reply_is_502_and_saves_nothing(client, monkeypatch, reply):
    n = note(client)
    FakeSummary(monkeypatch, reply)
    assert summarize(client, n).status_code == 502
    assert next(x for x in client.get("/notes").json() if x["id"] == n["id"])["summary"] is None


def test_summarize_failure_keeps_the_previous_summary(client, monkeypatch):
    n = note(client)
    fake = FakeSummary(monkeypatch, "Kept.")
    summarize(client, n)
    fake.exc = ConnectionError("down")
    assert summarize(client, n, force=True).status_code == 503
    assert next(x for x in client.get("/notes").json() if x["id"] == n["id"])["summary"] == "Kept."


# failure mapping

@pytest.mark.parametrize(
    "exc, status",
    [
        (ConnectionError("down"), 503),
        (runner.AgentOutputError("no structure"), 502),
        (OutputParserException("bad json"), 502),
    ],
)
def test_llm_failures_map_to_http_errors(client, monkeypatch, exc, status):
    task(client, "overdue", YESTERDAY)
    FakeRun(monkeypatch, exc=exc)
    assert post(client, "task", "plan_day").status_code == status


def test_timeout_is_504(client, monkeypatch):
    task(client, "overdue", YESTERDAY)

    async def slow(message, day=None):
        await asyncio.sleep(1)

    monkeypatch.setattr(tasks_llm, "plan_day", slow)
    monkeypatch.setattr(settings, "agent_timeout_seconds", 0.01)
    assert post(client, "task", "plan_day").status_code == 504


# runner (tool-calling loop, used by agents)

class FakeAgent:
    def __init__(self, result):
        self.result = result

    async def ainvoke(self, payload, config=None):
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
