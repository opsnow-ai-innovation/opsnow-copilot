"""Integration tests for RedisMemoryStore with real Redis."""

from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis

from src.config import REDIS_URL
from src.processors.memory_store_processor import RedisMemoryStore
from src.models import Turn


async def _get_redis() -> Redis:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.ping()
    return redis


@pytest.mark.asyncio
async def test_redis_connection_available():
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis.ping()
    await redis.aclose()


@pytest.mark.asyncio
async def test_redis_memory_store_roundtrip():
    redis = await _get_redis()
    store = RedisMemoryStore(redis, summarizer=None)

    session = f"test-session-{uuid.uuid4()}"

    try:
        await store.clear(session)

        turn = Turn(turn=1, user="hello", assistant="hi")
        await store.add_turn(session, turn)

        await store.update_memory(
            session,
            memory="previous summary",
            entities={"provider": "aws"},
        )

        context = await store.get_context(session)

        assert len(context.short_term) == 1
        assert context.short_term[0].user == "hello"
        assert context.short_term[0].assistant == "hi"
        assert context.memory == "previous summary"
        assert context.entities == {"provider": "aws"}
    finally:
        await store.clear(session)
        await redis.aclose()
