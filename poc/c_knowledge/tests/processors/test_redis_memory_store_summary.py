"""Unit tests for RedisMemoryStore summarization trigger."""

import asyncio
import json

import pytest

from src.constants.memory import REDIS_KEY_ENTITIES, REDIS_KEY_MEMORY, REDIS_KEY_SHORT
from src.processors.memory_store_processor import RedisMemoryStore
from src.models import SummarizerResult, Turn


class FakeRedis:
    def __init__(self):
        self._store = {}
        self._lists = {}

    async def rpush(self, key, value):
        self._lists.setdefault(key, []).append(value)

    async def llen(self, key):
        return len(self._lists.get(key, []))

    async def lrange(self, key, start, end):
        data = self._lists.get(key, [])
        if end == -1:
            end = len(data) - 1
        return data[start : end + 1]

    async def ltrim(self, key, start, end):
        data = self._lists.get(key, [])
        if end == -1:
            end = len(data) - 1
        self._lists[key] = data[start : end + 1]

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value


class FakeSummarizer:
    async def recursive_summarize(self, prev_memory, new_turns, prev_entities):
        return SummarizerResult(
            memory="summary",
            entities={"provider": "aws"},
        )


@pytest.mark.asyncio
async def test_add_turn_triggers_summary_after_short_term_limit(monkeypatch):
    redis = FakeRedis()
    summarizer = FakeSummarizer()
    store = RedisMemoryStore(redis, summarizer=summarizer)
    session = "session-1"

    created_tasks = []

    original_create_task = asyncio.create_task

    def fake_create_task(coro):
        task = original_create_task(coro)
        created_tasks.append(task)
        return task

    monkeypatch.setattr("src.processors.memory_store_processor.asyncio.create_task", fake_create_task)

    for i in range(6):
        await store.add_turn(
            session,
            Turn(turn=i + 1, user=f"user-{i+1}", assistant="ok"),
        )

    if created_tasks:
        await asyncio.gather(*created_tasks)

    short_key = REDIS_KEY_SHORT.format(session=session)
    assert len(redis._lists.get(short_key, [])) == 1

    memory_key = REDIS_KEY_MEMORY.format(session=session)
    entities_key = REDIS_KEY_ENTITIES.format(session=session)

    memory_state = json.loads(redis._store[memory_key])
    assert memory_state["content"] == "summary"
    assert json.loads(redis._store[entities_key]) == {"provider": "aws"}
