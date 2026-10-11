import uuid
from datetime import date

from backend.crud import weak_points as crud


def make_note(client, **over):
    return client.post("/notes", json={"title": "Cells", "content": "body", **over}).json()


def add(db, note_id, topic):
    return crud.record_miss(db, uuid.UUID(note_id), topic)


# crud

def test_record_miss_creates_an_open_weak_point(client, db):
    note = make_note(client)
    wp, changed = add(db, note["id"], "Mitosis")
    assert changed is True and wp.topic == "Mitosis" and wp.resolved is False
    assert wp.date_created == date.today()


def test_repeat_miss_on_an_open_topic_changes_nothing(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    again, changed = add(db, note["id"], "MITOSIS")
    assert changed is False and again.id == wp.id and again.topic == "Mitosis"
    assert len(crud.list_weak_points(db, uuid.UUID(note["id"]))) == 1


def test_miss_on_a_resolved_topic_reopens_it(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    crud.update_weak_point(db, wp.id, resolved=True)
    again, changed = add(db, note["id"], "Mitosis")
    assert changed is True and again.resolved is False


def test_same_topic_on_two_notes_is_two_rows(client, db):
    a, b = make_note(client), make_note(client, title="Other")
    add(db, a["id"], "Mitosis")
    add(db, b["id"], "Mitosis")
    assert len(crud.list_weak_points(db, uuid.UUID(a["id"]))) == 1
    assert len(crud.list_weak_points(db, uuid.UUID(b["id"]))) == 1


# REST

def listing(client, note_id, query=""):
    return client.get(f"/notes/{note_id}/weak_points{query}")


def test_list_returns_the_notes_weak_points(client, db):
    note, other = make_note(client), make_note(client, title="Other")
    add(db, note["id"], "Mitosis")
    add(db, other["id"], "Meiosis")
    r = listing(client, note["id"])
    assert r.status_code == 200 and [w["topic"] for w in r.json()] == ["Mitosis"]
    assert set(r.json()[0]) == {"id", "note_id", "topic", "resolved", "date_created"}
    assert listing(client, make_note(client, title="Empty")["id"]).json() == []


def test_list_filters_by_resolved(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "A")
    add(db, note["id"], "B")
    client.patch(f"/weak_points/{wp.id}", json={"resolved": True})
    assert [w["topic"] for w in listing(client, note["id"], "?resolved=true").json()] == ["A"]
    assert [w["topic"] for w in listing(client, note["id"], "?resolved=false").json()] == ["B"]
    assert len(listing(client, note["id"]).json()) == 2


def test_list_rejects_unknown_note_and_bad_input(client):
    assert listing(client, uuid.uuid4()).status_code == 404
    assert listing(client, "nope").status_code == 422
    note = make_note(client)
    assert listing(client, note["id"], "?resolved=maybe").status_code == 422


def test_resolve_and_reopen(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    r = client.patch(f"/weak_points/{wp.id}", json={"resolved": True})
    assert r.status_code == 200 and r.json()["resolved"] is True and r.json()["topic"] == "Mitosis"
    assert client.patch(f"/weak_points/{wp.id}", json={"resolved": False}).json()["resolved"] is False


def test_update_rejects_bad_bodies_and_unknown_ids(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    url = f"/weak_points/{wp.id}"
    assert client.patch(url, json={}).status_code == 422
    assert client.patch(url, json={"resolved": None}).status_code == 422
    assert client.patch(url, json={"resolved": "maybe"}).status_code == 422
    assert client.patch(url, json={"topic": "x"}).status_code == 422
    assert client.patch(f"/weak_points/{uuid.uuid4()}", json={"resolved": True}).status_code == 404
    assert client.patch("/weak_points/nope", json={"resolved": True}).status_code == 422


def test_delete_weak_point(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    assert client.delete(f"/weak_points/{wp.id}").status_code == 204
    assert listing(client, note["id"]).json() == []
    assert client.delete(f"/weak_points/{wp.id}").status_code == 404
    assert client.delete("/weak_points/nope").status_code == 422


def test_deleting_a_note_deletes_its_weak_points(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    wp_id = wp.id
    assert client.delete(f"/notes/{note['id']}").status_code == 204
    db.expire_all()
    assert db.get(type(wp), wp_id) is None


# list all

def test_list_all_spans_notes(client, db):
    a, b = make_note(client), make_note(client, title="Other")
    add(db, a["id"], "Mitosis")
    add(db, b["id"], "Meiosis")
    r = client.get("/weak_points")
    assert r.status_code == 200 and {w["topic"] for w in r.json()} == {"Mitosis", "Meiosis"}


def test_list_all_is_empty_with_no_weak_points(client):
    r = client.get("/weak_points")
    assert r.status_code == 200 and r.json() == []


def test_list_all_filters_by_resolved(client, db):
    note = make_note(client)
    wp, _ = add(db, note["id"], "Mitosis")
    add(db, note["id"], "Meiosis")
    client.patch(f"/weak_points/{wp.id}", json={"resolved": True})
    assert [w["topic"] for w in client.get("/weak_points?resolved=true").json()] == ["Mitosis"]
    assert [w["topic"] for w in client.get("/weak_points?resolved=false").json()] == ["Meiosis"]


def test_list_all_rejects_a_bad_resolved_value(client):
    assert client.get("/weak_points?resolved=maybe").status_code == 422
