import uuid


def make(client, **over):
    return client.post("/notes", json={"title": "idea", "content": "buy milk", **over}).json()


def test_create_note(client):
    r = client.post("/notes", json={"title": "idea", "content": "# a\n\nb"})
    assert r.status_code == 201
    assert r.json()["content"] == "# a\n\nb"
    assert client.post("/notes", json={"title": "empty"}).json()["content"] == ""


def test_create_note_rejects_bad_input(client):
    assert client.post("/notes", json={}).status_code == 422
    assert client.post("/notes", json={"title": ""}).status_code == 422
    assert client.post("/notes", json={"title": "x", "content": ["a"]}).status_code == 422
    assert client.post("/notes", json={"title": "x", "content_blocks": "text"}).status_code == 422
    assert client.get("/notes").json() == []


def test_search(client):
    make(client, title="Groceries", content="Oat MILK")
    make(client, title="Work", content="standup")
    assert [n["title"] for n in client.get("/notes?q=milk").json()] == ["Groceries"]
    assert [n["title"] for n in client.get("/notes?q=WORK").json()] == ["Work"]
    assert client.get("/notes?q=zzz").json() == []
    assert len(client.get("/notes").json()) == 2


def test_search_treats_wildcards_literally(client):
    make(client, title="Discount", content="save 100% today")
    make(client, title="Plain", content="nothing here")
    make(client, title="snake_case", content="x")
    assert [n["title"] for n in client.get("/notes?q=100%25").json()] == ["Discount"]
    assert [n["title"] for n in client.get("/notes?q=_").json()] == ["snake_case"]
    assert client.get("/notes?q=%25").json() == [n for n in client.get("/notes?q=%25").json() if "%" in n["content"]]


def test_get_note(client):
    note = make(client)
    assert client.get(f"/notes/{note['id']}").json()["title"] == "idea"
    assert client.get(f"/notes/{uuid.uuid4()}").status_code == 404
    assert client.get("/notes/not-a-uuid").status_code == 422


def test_update_note(client):
    n = make(client)
    r = client.patch(f"/notes/{n['id']}", json={"content": "new"})
    assert r.json()["content"] == "new" and r.json()["title"] == "idea"
    assert client.patch(f"/notes/{n['id']}", json={"content": ""}).json()["content"] == ""
    assert client.patch(f"/notes/{n['id']}", json={"content": None}).status_code == 422


def test_update_rejects_bad_body(client):
    n = make(client)
    url = f"/notes/{n['id']}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"title": None}).status_code == 422
    assert client.patch(url, json={"bogus": 1}).status_code == 422
    assert client.patch(f"/notes/{uuid.uuid4()}", json={"title": "x"}).status_code == 404


def test_delete(client):
    n = make(client)
    assert client.delete(f"/notes/{n['id']}").status_code == 204
    assert client.delete(f"/notes/{n['id']}").status_code == 404
    assert client.delete("/notes/nope").status_code == 422
