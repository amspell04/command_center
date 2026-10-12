from datetime import date, timedelta

from backend.ai.llm import tasks as tasks_llm
from backend.ai.llm import training as training_llm
from backend.crud import agent_results as results_crud
from backend.db.models import AgentResult
from backend.tests.test_agent_actions import FakeLLM, plan, task
from backend.tests.test_balance_week import WED, MON, balance, gym_week, run
from backend.ai.llm.tasks import PlanItem

TODAY = date.today()


def fake_plan(monkeypatch, client):
    t = task(client, "Report", TODAY)
    result = plan([PlanItem(task_id=t["id"], reason="due", estimate_minutes=30)])
    return t, FakeLLM(monkeypatch, tasks_llm, "plan_day", result)


def fake_balance(monkeypatch):
    return FakeLLM(monkeypatch, training_llm, "balance_week", balance(status="TIGHT", summary="Heavy Wednesday."))


def plan_now(client, **body):
    return client.post("/agents/task/actions/plan_day", json={"date": TODAY.isoformat(), **body})


def stored(client, kind, on):
    return client.get(f"/agents/results/{kind}", params={"date": on.isoformat()})


# plan_day

def test_plan_day_is_stored_and_reused_while_inputs_are_unchanged(client, db, monkeypatch):
    _, f = fake_plan(monkeypatch, client)
    first = plan_now(client).json()
    second = plan_now(client).json()
    assert len(f.calls) == 1 and second == first
    assert results_crud.get_result(db, "plan_day", TODAY) is not None


def test_plan_day_regenerates_when_a_task_changes(client, monkeypatch):
    _, f = fake_plan(monkeypatch, client)
    plan_now(client)
    task(client, "Another", TODAY)
    plan_now(client)
    assert len(f.calls) == 2


def test_plan_day_force_regenerates_and_replaces_the_row(client, db, monkeypatch):
    _, f = fake_plan(monkeypatch, client)
    plan_now(client)
    plan_now(client, force=True)
    assert len(f.calls) == 2
    assert len(db.query(AgentResult).all()) == 1


def test_plan_day_failure_keeps_the_previous_result(client, monkeypatch):
    _, f = fake_plan(monkeypatch, client)
    first = plan_now(client).json()
    f.exc = ValueError("boom")
    assert plan_now(client, force=True).status_code >= 400
    assert stored(client, "plan_day", TODAY).json() == first


def test_plan_day_without_tasks_stores_nothing(client, db, monkeypatch):
    f = FakeLLM(monkeypatch, tasks_llm, "plan_day", plan([]))
    assert plan_now(client).status_code == 200
    assert f.calls == [] and db.query(AgentResult).count() == 0


def test_plan_day_rejects_non_boolean_force(client):
    assert plan_now(client, force="maybe").status_code == 422


# balance_week

def test_balance_week_is_stored_and_reused_while_inputs_are_unchanged(client, monkeypatch):
    gym_week(client)
    f = fake_balance(monkeypatch)
    first = run(client).json()
    assert run(client).json() == first and len(f.calls) == 1


def test_balance_week_regenerates_when_the_week_changes(client, monkeypatch):
    gym_week(client)
    f = fake_balance(monkeypatch)
    run(client)
    task(client, "New", WED)
    run(client)
    assert len(f.calls) == 2


def test_balance_week_force_regenerates(client, monkeypatch):
    gym_week(client)
    f = fake_balance(monkeypatch)
    run(client)
    run(client, force=True)
    assert len(f.calls) == 2


def test_balance_week_without_gym_days_stores_nothing(client, db, monkeypatch):
    f = fake_balance(monkeypatch)
    run(client)
    assert f.calls == [] and db.query(AgentResult).count() == 0


def test_balance_week_is_keyed_by_the_week_start(client, monkeypatch):
    gym_week(client)
    fake_balance(monkeypatch)
    body = run(client).json()
    assert stored(client, "balance_week", MON + timedelta(days=4)).json() == body


# reading stored results

def test_stored_result_is_null_before_any_run(client):
    r = stored(client, "plan_day", TODAY)
    assert r.status_code == 200 and r.json() is None
    assert stored(client, "balance_week", WED).json() is None


def test_stored_result_never_runs_the_model(client, monkeypatch):
    _, f = fake_plan(monkeypatch, client)
    stored(client, "plan_day", TODAY)
    assert f.calls == []


def test_stored_result_returns_what_was_saved(client, monkeypatch):
    fake_plan(monkeypatch, client)
    body = plan_now(client).json()
    assert stored(client, "plan_day", TODAY).json() == body
    assert stored(client, "plan_day", TODAY + timedelta(days=1)).json() is None


def test_stored_result_rejects_unknown_kind_and_bad_date(client):
    assert stored(client, "nope", TODAY).status_code == 404
    assert client.get("/agents/results/plan_day", params={"date": "soon"}).status_code == 422
    assert client.get("/agents/results/plan_day").status_code == 422
