import uuid
from datetime import date, timedelta

START = date(2026, 10, 12)  # a Monday


def iso(offset=0):
    return (START + timedelta(days=offset)).isoformat()


def make_program(client, **over):
    return client.post("/training/programs", json={"name": "Peak", "start_date": iso(), "weeks": 10, "active": True, **over}).json()


def make_exercise(client, program_id, **over):
    body = {"week": 1, "day": 1, "lift": "SQUAT", "sets": 3, "reps": 5, "percent": 80, **over}
    return client.post(f"/training/programs/{program_id}/sets", json=body)


def put_max(client, lift="SQUAT", weight=400, on=None):
    return client.put("/training/maxes", json={"lift": lift, "weight": weight, "effective_date": on or iso(-30)})


def log(client, on=None, sets=None, **over):
    sets = sets if sets is not None else [{"lift": "SQUAT", "weight": 315, "reps": 5}]
    return client.put("/training/sessions", json={"date": on or iso(), "sets": sets, **over})


# maxes

def test_set_max_returns_lb_and_kg(client):
    r = put_max(client, weight=405)
    assert r.status_code == 200
    assert r.json()["weight_lb"] == 405 and r.json()["weight_kg"] == 183.7
    assert client.get("/training/maxes").json()[0]["lift"] == "SQUAT"


def test_set_max_rejects_bad_input(client):
    assert put_max(client, weight=0).status_code == 422
    assert put_max(client, lift="OHP").status_code == 422
    assert client.put("/training/maxes", json={"lift": "SQUAT", "weight": 300}).status_code == 422
    assert client.put("/training/maxes", json={"lift": "SQUAT", "weight": 300, "effective_date": iso(), "x": 1}).status_code == 422
    assert client.get("/training/maxes").json() == []


def test_delete_max(client):
    m = put_max(client).json()
    assert client.delete(f"/training/maxes/{m['id']}").status_code == 204
    assert client.delete(f"/training/maxes/{m['id']}").status_code == 404


# programs

def test_create_and_get_program(client):
    p = make_program(client)
    assert p["weeks"] == 10 and p["active"] is True
    assert client.get(f"/training/programs/{p['id']}").json() == p
    assert [x["id"] for x in client.get("/training/programs").json()] == [p["id"]]


def test_create_program_rejects_bad_input(client):
    assert client.post("/training/programs", json={"name": "", "start_date": iso(), "weeks": 10}).status_code == 422
    assert client.post("/training/programs", json={"name": "x", "start_date": iso(), "weeks": 0}).status_code == 422
    assert client.post("/training/programs", json={"name": "x", "start_date": "soon", "weeks": 4}).status_code == 422
    assert client.get("/training/programs").json() == []


def test_new_active_program_replaces_the_old_one(client):
    first = make_program(client, name="One")
    make_program(client, name="Two")
    assert client.get(f"/training/programs/{first['id']}").json()["active"] is False


def test_update_program(client):
    p = make_program(client)
    r = client.patch(f"/training/programs/{p['id']}", json={"name": "Renamed", "start_date": iso(7)})
    assert r.status_code == 200 and r.json()["name"] == "Renamed" and r.json()["start_date"] == iso(7)


def test_update_program_rejects_bad_input(client):
    p = make_program(client)
    url = f"/training/programs/{p['id']}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"name": None}).status_code == 422
    assert client.patch(url, json={"weeks": 0}).status_code == 422
    assert client.patch(f"/training/programs/{uuid.uuid4()}", json={"name": "x"}).status_code == 404
    make_exercise(client, p["id"], week=8)
    r = client.patch(url, json={"weeks": 6})
    assert r.status_code == 422 and "Week 8" in r.json()["detail"]


def test_delete_program(client):
    p = make_program(client)
    assert client.delete(f"/training/programs/{p['id']}").status_code == 204
    assert client.get(f"/training/programs/{p['id']}").status_code == 404
    assert client.delete(f"/training/programs/{p['id']}").status_code == 404


# exercises

def test_add_exercise_shows_weight_from_the_max(client):
    put_max(client, weight=400)
    p = make_program(client)
    r = make_exercise(client, p["id"], percent=80)
    assert r.status_code == 201
    body = r.json()
    assert body["weight_lb"] == 320 and body["weight_kg"] == 145.1 and body["date"] == iso()


def test_exercise_weight_is_null_until_a_max_exists(client):
    p = make_program(client)
    body = make_exercise(client, p["id"]).json()
    assert body["weight_lb"] is None and body["weight_kg"] is None


def test_add_exercise_rejects_bad_input(client):
    p = make_program(client, weeks=4)
    for bad in ({"day": 8}, {"percent": 0}, {"percent": 200}, {"reps": 0}, {"sets": 0}, {"lift": "OHP"}, {"extra": 1}):
        assert make_exercise(client, p["id"], **bad).status_code == 422
    r = make_exercise(client, p["id"], week=5)
    assert r.status_code == 422 and "past the end" in r.json()["detail"]
    assert make_exercise(client, uuid.uuid4()).status_code == 404
    assert client.get(f"/training/programs/{p['id']}/sets").json() == []


def test_list_exercises_filters_by_week(client):
    p = make_program(client)
    make_exercise(client, p["id"], week=1)
    make_exercise(client, p["id"], week=2)
    assert len(client.get(f"/training/programs/{p['id']}/sets").json()) == 2
    assert [e["week"] for e in client.get(f"/training/programs/{p['id']}/sets?week=2").json()] == [2]
    assert client.get(f"/training/programs/{uuid.uuid4()}/sets").status_code == 404


def test_update_and_delete_exercise(client):
    put_max(client, weight=400)
    p = make_program(client)
    e = make_exercise(client, p["id"]).json()
    r = client.patch(f"/training/sets/{e['id']}", json={"percent": 85, "lift": "BENCH"})
    assert r.status_code == 200 and r.json()["percent"] == 85 and r.json()["lift"] == "BENCH"
    assert r.json()["weight_lb"] is None  # no bench max yet
    assert client.delete(f"/training/sets/{e['id']}").status_code == 204
    assert client.delete(f"/training/sets/{e['id']}").status_code == 404


def test_update_exercise_rejects_bad_input(client):
    p = make_program(client, weeks=4)
    e = make_exercise(client, p["id"]).json()
    url = f"/training/sets/{e['id']}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"percent": None}).status_code == 422
    assert client.patch(url, json={"day": 9}).status_code == 422
    assert client.patch(url, json={"week": 5}).status_code == 422
    assert client.patch(f"/training/sets/{uuid.uuid4()}", json={"reps": 3}).status_code == 404


def test_copy_week(client):
    p = make_program(client)
    make_exercise(client, p["id"], day=1)
    make_exercise(client, p["id"], day=3, lift="BENCH")
    r = client.post(f"/training/programs/{p['id']}/copy_week", json={"from_week": 1, "to_week": 2})
    assert r.status_code == 201 and [(e["week"], e["day"]) for e in r.json()] == [(2, 1), (2, 3)]
    assert r.json()[0]["date"] == iso(7)


def test_copy_week_rejects_bad_requests(client):
    p = make_program(client, weeks=3)
    make_exercise(client, p["id"], week=1)
    url = f"/training/programs/{p['id']}/copy_week"
    assert client.post(url, json={"from_week": 1, "to_week": 1}).status_code == 422
    assert client.post(url, json={"from_week": 2, "to_week": 3}).status_code == 422  # nothing to copy
    assert client.post(url, json={"from_week": 1, "to_week": 4}).status_code == 422  # past the end
    assert client.post(url, json={"from_week": 1}).status_code == 422
    assert client.post(f"/training/programs/{uuid.uuid4()}/copy_week", json={"from_week": 1, "to_week": 2}).status_code == 404
    client.post(url, json={"from_week": 1, "to_week": 2})
    assert client.post(url, json={"from_week": 1, "to_week": 2}).status_code == 422  # already filled


# planned

def test_planned_for_a_date(client):
    put_max(client, weight=400)
    p = make_program(client)
    make_exercise(client, p["id"], week=1, day=3, percent=75)
    r = client.get(f"/training/planned?date={iso(2)}")
    assert r.status_code == 200 and [(e["weight_lb"], e["weight_kg"]) for e in r.json()] == [(300, 136.1)]
    assert client.get(f"/training/planned?date={iso(1)}").json() == []


def test_planned_rejects_a_bad_date_and_defaults_to_today(client):
    assert client.get("/training/planned?date=tomorrow").status_code == 422
    assert client.get("/training/planned").json() == []


# sessions

def test_log_session_returns_both_units_and_e1rm(client):
    r = log(client, bodyweight=200, notes="felt good")
    assert r.status_code == 200
    body = r.json()
    assert body["bodyweight_kg"] == 90.7 and body["notes"] == "felt good"
    s = body["sets"][0]
    assert (s["weight_lb"], s["weight_kg"], s["estimated_1rm_lb"], s["set_order"]) == (315, 142.9, 367.5, 1)


def test_logging_a_date_again_replaces_the_session(client):
    first = log(client).json()
    second = log(client, sets=[{"lift": "BENCH", "weight": 225, "reps": 5}]).json()
    assert second["id"] == first["id"] and [s["lift"] for s in second["sets"]] == ["BENCH"]
    assert len(client.get("/training/sessions").json()) == 1


def test_log_session_rejects_bad_input(client):
    assert log(client, sets=[]).status_code == 422
    assert log(client, sets=[{"lift": "SQUAT", "weight": 0, "reps": 5}]).status_code == 422
    assert log(client, sets=[{"lift": "SQUAT", "weight": 300, "reps": 0}]).status_code == 422
    assert log(client, sets=[{"lift": "OHP", "weight": 300, "reps": 5}]).status_code == 422
    assert log(client, on="today").status_code == 422
    assert log(client, bodyweight=0).status_code == 422
    r = log(client, sets=[{"lift": "SQUAT", "weight": 300, "reps": 5, "program_set_id": str(uuid.uuid4())}])
    assert r.status_code == 422 and "Unknown program set" in r.json()["detail"]
    assert client.get("/training/sessions").json() == []


def test_log_session_against_a_planned_exercise(client):
    p = make_program(client)
    e = make_exercise(client, p["id"]).json()
    r = log(client, sets=[{"lift": "SQUAT", "weight": 320, "reps": 5, "program_set_id": e["id"]}])
    assert r.status_code == 200 and r.json()["sets"][0]["program_set_id"] == e["id"]


def test_list_get_and_delete_sessions(client):
    a = log(client, on=iso(0)).json()
    log(client, on=iso(3))
    assert [s["date"] for s in client.get("/training/sessions").json()] == [iso(3), iso(0)]
    assert [s["date"] for s in client.get(f"/training/sessions?start={iso(1)}&end={iso(5)}").json()] == [iso(3)]
    assert client.get(f"/training/sessions/{a['id']}").json()["id"] == a["id"]
    assert client.delete(f"/training/sessions/{a['id']}").status_code == 204
    assert client.get(f"/training/sessions/{a['id']}").status_code == 404
    assert client.delete(f"/training/sessions/{a['id']}").status_code == 404
    assert client.get("/training/sessions?start=oops").status_code == 422


# progress

def test_progress_is_best_e1rm_per_date(client):
    log(client, on=iso(0), sets=[{"lift": "SQUAT", "weight": 300, "reps": 5}, {"lift": "BENCH", "weight": 200, "reps": 5}])
    log(client, on=iso(7), sets=[{"lift": "SQUAT", "weight": 320, "reps": 5}])
    r = client.get("/training/progress/SQUAT")
    assert r.status_code == 200
    assert [(p["date"], p["estimated_1rm_lb"], p["estimated_1rm_kg"]) for p in r.json()] == [(iso(0), 350, 158.8), (iso(7), 373.3, 169.3)]
    assert client.get("/training/progress/DEADLIFT").json() == []
    assert client.get("/training/progress/OHP").status_code == 422


# gym week

def test_gym_week_lists_planned_and_logged_days_only(client):
    p = make_program(client)
    make_exercise(client, p["id"], day=1)
    make_exercise(client, p["id"], day=3, lift="BENCH", sets=5, reps=3)
    make_exercise(client, p["id"], day=3, lift="DEADLIFT", sets=1, reps=3)
    log(client, on=iso(1), sets=[{"lift": "SQUAT", "weight": 200, "reps": 5}])
    r = client.get(f"/training/week?date={iso(4)}")  # a Friday
    assert r.status_code == 200
    days = r.json()
    assert [(x["date"], x["logged"]) for x in days] == [(iso(0), False), (iso(1), True), (iso(2), False)]
    assert days[2]["lifts"] == ["Bench", "Deadlift"] and days[2]["sets"] == 6
    assert days[0]["details"] == ["Squat 3x5 at 80%"]


def test_gym_week_is_empty_without_a_program_or_sessions_and_rejects_a_bad_date(client):
    assert client.get("/training/week").json() == []
    assert client.get(f"/training/week?date={iso(10)}").json() == []
    assert client.get("/training/week?date=soon").status_code == 422


def test_gym_week_only_includes_that_weeks_days(client):
    p = make_program(client)
    make_exercise(client, p["id"], week=1, day=1)
    make_exercise(client, p["id"], week=2, day=1)
    assert [x["date"] for x in client.get(f"/training/week?date={iso(8)}").json()] == [iso(7)]
