import asyncio
from datetime import date, timedelta

import pytest
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from backend.ai.llm import training as training_llm
from backend.ai.llm.client import load_prompt
from backend.ai.llm.training import Suggestion, WeekBalance
from backend.tests.test_agent_actions import FakeLLM

MON = date(2026, 10, 12)
WED = MON + timedelta(days=2)


def d(offset):
    return MON + timedelta(days=offset)


def balance(items=(), **over):
    return WeekBalance(**{"status": "TIGHT", "summary": "Wednesday is heavy.", "suggestions": list(items), **over})


def fake(monkeypatch, result=None, exc=None):
    return FakeLLM(monkeypatch, training_llm, "balance_week", result if result is not None else balance(), exc)


def run(client, on=WED, **body):
    return client.post("/agents/training/actions/balance_week", json={"date": on.isoformat(), **body})


def task(client, title, due, **over):
    return client.post("/tasks", json={"title": title, "type": "WORK", "due_date": due.isoformat(), **over}).json()


def program(client, **over):
    return client.post("/training/programs", json={"name": "Meet prep", "start_date": MON.isoformat(), "weeks": 10, "active": True, **over}).json()


def exercise(client, program_id, **over):
    body = {"week": 1, "day": 1, "lift": "SQUAT", "sets": 3, "reps": 5, "percent": 80, **over}
    return client.post(f"/training/programs/{program_id}/sets", json=body).json()


def log(client, on, sets=None):
    sets = sets or [{"lift": "BENCH", "weight": 225, "reps": 5}] * 2
    return client.put("/training/sessions", json={"date": on.isoformat(), "sets": sets})


def goal(client, title, target_date):
    return client.post("/goals", json={"title": title, "target_date": target_date.isoformat() if target_date else None}).json()


def gym_week(client):
    p = program(client)
    exercise(client, p["id"], day=1)  # Monday
    exercise(client, p["id"], day=3, lift="DEADLIFT", sets=2, reps=3, percent=85)  # Wednesday
    return p


# request handling

def test_bad_params_are_rejected_before_the_model_runs(client, monkeypatch):
    f = fake(monkeypatch)
    assert client.post("/agents/training/actions/balance_week", json={"bogus": 1}).status_code == 422
    assert client.post("/agents/training/actions/balance_week", json={"date": "someday"}).status_code == 422
    assert f.calls == []


def test_defaults_to_this_week(client, monkeypatch):
    fake(monkeypatch)
    body = client.post("/agents/training/actions/balance_week", json={}).json()
    today = date.today()
    assert body["start"] == (today - timedelta(days=today.weekday())).isoformat()


# the week it computes

def test_returns_seven_days_monday_to_sunday_with_task_counts(client, monkeypatch):
    f = fake(monkeypatch)
    task(client, "Report", d(2))
    task(client, "Email", d(2))
    done = task(client, "Filed", d(2))
    client.patch(f"/tasks/{done['id']}/complete")
    task(client, "Next week", d(7))
    body = run(client).json()
    assert (body["start"], body["end"]) == (d(0).isoformat(), d(6).isoformat())
    assert [x["weekday"] for x in body["days"]] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    wed = body["days"][2]
    assert (wed["tasks_due"], wed["tasks_done"], sorted(wed["task_titles"])) == (3, 1, ["Email", "Report"])
    assert all(x["tasks_due"] == 0 for i, x in enumerate(body["days"]) if i != 2)
    assert f.calls == []  # no gym days, nothing to balance


def test_a_mid_week_date_gives_the_same_week_as_monday_and_sunday(client, monkeypatch):
    fake(monkeypatch)
    weeks = {run(client, on=d(i)).json()["start"] for i in (0, 3, 6)}
    assert weeks == {d(0).isoformat()}
    assert run(client, on=d(7)).json()["start"] == d(7).isoformat()


def test_planned_gym_days_come_from_the_active_program(client, monkeypatch):
    fake(monkeypatch)
    gym_week(client)
    days = run(client).json()["days"]
    assert days[0]["gym"] == {"date": d(0).isoformat(), "logged": False, "lifts": ["Squat"], "sets": 3, "details": ["Squat 3x5 at 80%"]}
    assert days[2]["gym"]["lifts"] == ["Deadlift"] and days[2]["gym"]["sets"] == 2
    assert days[1]["gym"] is None


def test_a_logged_session_replaces_the_plan_for_that_day(client, monkeypatch):
    fake(monkeypatch)
    gym_week(client)
    log(client, d(0))
    gym = run(client).json()["days"][0]["gym"]
    assert (gym["logged"], gym["lifts"], gym["sets"]) == (True, ["Bench"], 2)


def test_a_logged_session_counts_without_any_program(client, monkeypatch):
    f = fake(monkeypatch)
    log(client, d(4))
    assert run(client).json()["days"][4]["gym"]["logged"] is True
    assert len(f.calls) == 1


def test_inactive_program_adds_no_gym_days(client, monkeypatch):
    f = fake(monkeypatch)
    p = program(client, active=False)
    exercise(client, p["id"])
    assert all(x["gym"] is None for x in run(client).json()["days"])
    assert f.calls == []


def test_program_label_shows_the_week_and_is_absent_outside_the_program(client, monkeypatch):
    fake(monkeypatch)
    gym_week(client)
    assert run(client).json()["program"] == "Meet prep, week 1 of 10"
    assert run(client, on=d(14)).json()["program"] == "Meet prep, week 3 of 10"
    assert run(client, on=d(-7)).json()["program"] is None
    assert run(client, on=d(70)).json()["program"] is None


# the meet

def test_meet_is_the_soonest_upcoming_goal_date(client, monkeypatch):
    fake(monkeypatch)
    goal(client, "Later", d(100))
    goal(client, "Meet", d(40))
    goal(client, "Past", d(-3))
    goal(client, "No date", None)
    assert run(client).json()["meet"] == {"title": "Meet", "date": d(40).isoformat(), "days_left": 38}


def test_no_upcoming_goal_means_no_meet(client, monkeypatch):
    fake(monkeypatch)
    goal(client, "Past", d(-3))
    assert run(client).json()["meet"] is None


# what the model is told

def test_message_lists_each_day_with_gym_tasks_and_meet(client, monkeypatch):
    f = fake(monkeypatch)
    gym_week(client)
    goal(client, "State meet", d(40))
    task(client, "Quarterly report", d(2))
    run(client)
    message = f.calls[0][0]
    assert f"Today is {WED}" in message
    assert "Meet: State meet on" in message and "38 days away" in message
    assert "Program: Meet prep, week 1 of 10." in message
    assert f"- {d(0)} Monday: gym: Squat 3x5 at 80%." in message
    assert f"- {d(2)} Wednesday: gym: Deadlift 2x3 at 85%. Tasks: 1 tasks due, 0 done (Quarterly report)." in message
    assert f"- {d(1)} Tuesday: gym: no gym. Tasks: 0 tasks due, 0 done." in message


def test_message_says_when_there_is_no_meet_or_program(client, monkeypatch):
    f = fake(monkeypatch)
    log(client, d(1))
    run(client)
    assert "Meet: no date set." in f.calls[0][0]
    assert "Program: none active." in f.calls[0][0]
    assert "already logged" in f.calls[0][0]


# what comes back from the model

def test_model_status_summary_and_suggestions_are_returned(client, monkeypatch):
    gym_week(client)
    fake(monkeypatch, balance([Suggestion(date=d(3), action="Move the report to Thursday")], status="OVERLOADED", summary="Crowded."))
    body = run(client).json()
    assert (body["status"], body["summary"]) == ("OVERLOADED", "Crowded.")
    assert body["suggestions"] == [{"date": d(3).isoformat(), "action": "Move the report to Thursday"}]


def test_suggestions_for_other_weeks_or_past_days_are_dropped(client, monkeypatch):
    gym_week(client)
    fake(monkeypatch, balance([
        Suggestion(date=d(1), action="past day"),       # before Wednesday
        Suggestion(date=d(7), action="next week"),
        Suggestion(date=d(-3), action="last week"),
        Suggestion(date=d(2), action="today counts"),
        Suggestion(date=d(6), action="sunday counts"),
    ]))
    assert [s["action"] for s in run(client).json()["suggestions"]] == ["today counts", "sunday counts"]


def test_suggestions_are_trimmed_deduplicated_and_capped_at_four(client, monkeypatch):
    gym_week(client)
    fake(monkeypatch, balance([
        Suggestion(date=d(3), action="  Rest  "),
        Suggestion(date=d(3), action="rest"),          # same date and text
        Suggestion(date=d(3), action="   "),           # blank after trimming
        Suggestion(date=d(4), action="a"),
        Suggestion(date=d(5), action="b"),
        Suggestion(date=d(6), action="c"),
        Suggestion(date=d(6), action="d"),
    ]))
    assert [s["action"] for s in run(client).json()["suggestions"]] == ["Rest", "a", "b", "c"]


def test_no_suggestions_is_fine(client, monkeypatch):
    gym_week(client)
    fake(monkeypatch, balance(status="BALANCED", summary="All good."))
    body = run(client).json()
    assert body["status"] == "BALANCED" and body["suggestions"] == []


@pytest.mark.parametrize("exc,status", [(OutputParserException("bad"), 502), (asyncio.TimeoutError(), 504), (RuntimeError("down"), 503)])
def test_model_failures_map_to_http_errors(client, monkeypatch, exc, status):
    gym_week(client)
    fake(monkeypatch, exc=exc)
    assert run(client).status_code == status


# model output shape and prompt

def test_week_balance_rejects_bad_output():
    with pytest.raises(ValidationError):
        WeekBalance(status="FINE", summary="x")
    with pytest.raises(ValidationError):
        WeekBalance(status="BALANCED", summary="")
    with pytest.raises(ValidationError):
        Suggestion(date=MON, action="")
    with pytest.raises(ValidationError):
        Suggestion(date="not a date", action="x")


def test_prompt_keeps_the_program_fixed_and_has_its_date_placeholder():
    prompt = load_prompt("balance_week")
    assert "{today}" in prompt
    assert "Never suggest skipping or moving a gym session" in prompt


def test_prompt_asks_for_food_water_and_caffeine_guidance_with_a_caffeine_cap():
    prompt = load_prompt("balance_week")
    for word in ("food", "water", "caffeine", "sleep"):
        assert word in prompt.lower()
    assert "400 mg" in prompt
