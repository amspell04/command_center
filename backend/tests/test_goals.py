import uuid

GOAL = {"title": "Ship the report", "details": "Done by Friday"}


def make(client, **over):
    return client.post("/goals", json={**GOAL, **over}).json()


def test_create_goal_defaults_details(client):
    r = client.post("/goals", json={"title": "Read more"})
    assert r.status_code == 201
    assert r.json()["details"] == "" and uuid.UUID(r.json()["id"])


def test_create_goal_rejects_bad_input(client):
    assert client.post("/goals", json={"title": ""}).status_code == 422
    assert client.post("/goals", json={"details": "x"}).status_code == 422
    assert client.post("/goals", json={**GOAL, "extra": 1}).status_code == 422
    assert client.get("/goals").json() == []


def test_list_goals(client):
    make(client, title="a")
    make(client, title="b")
    assert [g["title"] for g in client.get("/goals").json()] == ["a", "b"]


def test_update_goal(client):
    g = make(client)
    r = client.patch(f"/goals/{g['id']}", json={"title": "New"})
    assert r.status_code == 200 and r.json()["title"] == "New" and r.json()["details"] == GOAL["details"]


def test_update_goal_rejects_bad_input(client):
    g = make(client)
    assert client.patch(f"/goals/{g['id']}", json={}).status_code == 422
    assert client.patch(f"/goals/{g['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/goals/{g['id']}", json={"title": ""}).status_code == 422
    assert client.patch(f"/goals/{uuid.uuid4()}", json={"title": "x"}).status_code == 404


def test_delete_goal(client):
    g = make(client)
    assert client.delete(f"/goals/{g['id']}").status_code == 204
    assert client.get("/goals").json() == []
    assert client.delete(f"/goals/{g['id']}").status_code == 404


def test_goal_target_date_is_optional_and_round_trips(client):
    assert make(client)["target_date"] is None
    g = make(client, title="Meet", target_date="2027-02-13")
    assert g["target_date"] == "2027-02-13"
    r = client.patch(f"/goals/{g['id']}", json={"target_date": "2027-02-20"})
    assert r.status_code == 200 and r.json()["target_date"] == "2027-02-20"


def test_goal_rejects_a_bad_target_date(client):
    assert client.post("/goals", json={**GOAL, "target_date": "next feb"}).status_code == 422
    g = make(client)
    assert client.patch(f"/goals/{g['id']}", json={"target_date": "2027-13-40"}).status_code == 422


def test_goal_target_date_can_be_cleared_but_other_fields_cannot_be_null(client):
    g = make(client, target_date="2027-02-13")
    r = client.patch(f"/goals/{g['id']}", json={"target_date": None})
    assert r.status_code == 200 and r.json()["target_date"] is None
    assert client.patch(f"/goals/{g['id']}", json={"title": "x", "details": None}).status_code == 422
    assert client.patch(f"/goals/{g['id']}", json={"title": None, "target_date": None}).status_code == 422
