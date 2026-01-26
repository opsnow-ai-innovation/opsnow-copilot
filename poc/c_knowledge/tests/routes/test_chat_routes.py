"""Chat route tests."""

import os
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.models import Turn  # noqa: E402
from src.routes.chat import get_memory_store, router  # noqa: E402


def _build_app(memory_store):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    return app


def test_chat_save_assigns_next_turn():
    async def fake_get_all_turns(session):
        return [Turn(turn=1, user="hi", assistant="ok")]

    captured = {}

    async def fake_add_turn(session, turn):
        captured["session"] = session
        captured["turn"] = turn

    async def fake_incr(key):
        return 2  # next turn id

    async def fake_expire(key, ttl):
        return True

    memory_store = SimpleNamespace(
        get_all_turns=fake_get_all_turns,
        add_turn=fake_add_turn,
        _redis=SimpleNamespace(incr=fake_incr, expire=fake_expire),
    )

    app = _build_app(memory_store)
    client = TestClient(app)

    response = client.post(
        "/chat/save",
        json={"session": "s", "user_id": "", "query": "q", "answer": "a"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["saved"] is True
    assert payload["turn"] == 2
    assert captured["turn"].turn == 2
    assert captured["turn"].user == "q"
    assert captured["turn"].assistant == "a"


def test_chat_save_uses_explicit_turn():
    async def fake_get_all_turns(session):
        return []

    captured = {}

    async def fake_add_turn(session, turn):
        captured["turn"] = turn

    memory_store = SimpleNamespace(
        get_all_turns=fake_get_all_turns,
        add_turn=fake_add_turn,
    )

    app = _build_app(memory_store)
    client = TestClient(app)

    response = client.post(
        "/chat/save",
        json={
            "session": "s",
            "user_id": "",
            "query": "q",
            "answer": "a",
            "turn": 10,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["turn"] == 10
    assert captured["turn"].turn == 10
