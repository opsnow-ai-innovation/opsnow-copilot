"""Unit tests for RedisMemoryStore summarization trigger."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.constants.memory import REDIS_KEY_ENTITIES, REDIS_KEY_MEMORY, REDIS_KEY_SHORT
from src.processors.memory_store_processor import RedisMemoryStore
from src.processors.memory_summarizer_processor import MemorySummarizer, _fallback_summarize
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

    for i in range(5):
        await store.add_turn(
            session,
            Turn(turn=i + 1, user=f"user-{i+1}", assistant="ok"),
        )

    if created_tasks:
        await asyncio.gather(*created_tasks)

    short_key = REDIS_KEY_SHORT.format(session=session)
    assert len(redis._lists.get(short_key, [])) == 0

    memory_key = REDIS_KEY_MEMORY.format(session=session)
    entities_key = REDIS_KEY_ENTITIES.format(session=session)

    memory_state = json.loads(redis._store[memory_key])
    assert memory_state["content"] == "summary"
    assert json.loads(redis._store[entities_key]) == {"provider": "aws"}


def test_fallback_summarize():
    """LLM 실패 시 fallback 요약이 정상 동작하는지 확인"""
    prev_memory = "사용자는 AWS 비용에 관심"
    new_turns = [
        Turn(turn=1, user="예산 얼마야?", assistant="1억입니다"),
        Turn(turn=2, user="초과했어?", assistant="1.2억으로 초과"),
    ]
    prev_entities = {"provider": "AWS"}

    result = _fallback_summarize(prev_memory, new_turns, prev_entities)

    assert prev_memory in result.memory
    assert "최근 질문" in result.memory
    assert result.entities == prev_entities


@pytest.mark.asyncio
async def test_entities_string_parsing():
    """entities가 문자열로 반환될 때 파싱되는지 확인"""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({
                    "memory": "테스트 메모리",
                    "entities": '{"provider": "GCP"}'  # 문자열로 반환
                })
            )
        )
    ]

    with patch(
        "src.processors.memory_summarizer_processor.client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        summarizer = MemorySummarizer()
        result = await summarizer.recursive_summarize(
            prev_memory="",
            new_turns=[Turn(turn=1, user="질문", assistant="답변")],
            prev_entities={},
        )

        assert result.memory == "테스트 메모리"
        assert result.entities == {"provider": "GCP"}
