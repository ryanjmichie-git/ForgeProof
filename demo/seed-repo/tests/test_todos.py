"""Tests for the Todo API."""

from fastapi.testclient import TestClient

from src.api.routes import app, service


def setup_function():
    service._todos.clear()
    service._next_id = 1


client = TestClient(app)


def test_list_empty():
    resp = client.get("/todos")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_todo():
    resp = client.post("/todos", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Buy milk"
    assert data["completed"] is False
    assert data["id"] == 1


def test_get_todo():
    client.post("/todos", json={"title": "Walk dog"})
    resp = client.get("/todos/1")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Walk dog"


def test_get_missing_todo():
    resp = client.get("/todos/999")
    assert resp.status_code == 404


def test_complete_todo():
    client.post("/todos", json={"title": "Read book"})
    resp = client.post("/todos/1/complete")
    assert resp.status_code == 200
    assert resp.json()["completed"] is True


def test_delete_todo():
    client.post("/todos", json={"title": "Clean room"})
    resp = client.delete("/todos/1")
    assert resp.status_code == 204
    assert client.get("/todos/1").status_code == 404


def test_list_multiple():
    client.post("/todos", json={"title": "A"})
    client.post("/todos", json={"title": "B"})
    resp = client.get("/todos")
    assert len(resp.json()) == 2
