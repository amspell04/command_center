import uuid

TASK = {"title": "write report", "type": "WORK", "due_date": "2026-10-12"}


def make(client, **over):
    return client.post("/tasks", json={**TASK, **over}).json()


def test_create_task_defaults(client):
    r = client.post("/tasks", json=TASK)
    assert r.status_code == 201
    body = r.json()
    assert body["completed"] is False and body["requirement"] == "" and body["type"] == "WORK"
    assert uuid.UUID(body["id"])


def test_create_task_rejects_bad_input(client):
    assert client.post("/tasks", json={**TASK, "type": "OTHER"}).status_code == 422
    assert client.post("/tasks", json={**TASK, "title": ""}).status_code == 422
    assert client.post("/tasks", json={"title": "x"}).status_code == 422
    assert client.post("/tasks", json={**TASK, "due_date": "nope"}).status_code == 422
    assert client.post("/tasks", json={**TASK, "extra": 1}).status_code == 422
    assert client.get("/tasks").json() == []


def test_list_filters(client):
    a = make(client, title="a", due_date="2026-10-12")
    make(client, title="b", type="PERSONAL", due_date="2026-10-13")
    client.patch(f"/tasks/{a['id']}/complete")
    assert [t["title"] for t in client.get("/tasks").json()] == ["a", "b"]
    assert [t["title"] for t in client.get("/tasks?completed=false").json()] == ["b"]
    assert [t["title"] for t in client.get("/tasks?type=PERSONAL").json()] == ["b"]
    assert [t["title"] for t in client.get("/tasks?due_date=2026-10-12").json()] == ["a"]
    assert client.get("/tasks?type=BAD").status_code == 422


def test_complete_and_update(client):
    t = make(client)
    assert client.patch(f"/tasks/{t['id']}/complete").json()["completed"] is True
    r = client.patch(f"/tasks/{t['id']}", json={"title": "new", "type": "PERSONAL"})
    assert r.status_code == 200
    assert (r.json()["title"], r.json()["type"], r.json()["due_date"]) == ("new", "PERSONAL", "2026-10-12")


def test_update_rejects_bad_body(client):
    t = make(client)
    url = f"/tasks/{t['id']}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"title": None}).status_code == 422
    assert client.patch(url, json={"bogus": 1}).status_code == 422
    assert client.patch(url, json={"type": "X"}).status_code == 422


def test_missing_and_malformed_ids(client):
    missing = uuid.uuid4()
    assert client.patch(f"/tasks/{missing}/complete").status_code == 404
    assert client.patch(f"/tasks/{missing}", json={"title": "x"}).status_code == 404
    assert client.delete(f"/tasks/{missing}").status_code == 404
    assert client.patch("/tasks/nope/complete").status_code == 422


def test_delete(client):
    t = make(client)
    assert client.delete(f"/tasks/{t['id']}").status_code == 204
    assert client.delete(f"/tasks/{t['id']}").status_code == 404
    assert client.get("/tasks").json() == []
