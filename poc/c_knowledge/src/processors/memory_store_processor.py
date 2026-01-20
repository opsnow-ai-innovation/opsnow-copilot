"""
메모리 저장소

Redis를 통한 대화 히스토리 관리
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from src.constants.memory import (
    ENTITIES_MAX_COUNT,
    MEMORY_TTL_SECONDS,
    REDIS_KEY_ENTITIES,
    REDIS_KEY_MEMORY,
    REDIS_KEY_SHORT,
    SHORT_TERM_SIZE,
)
from src.models import Entities, MemoryContext, MemoryState, Turn
from src.utils.text import sanitize_text

if TYPE_CHECKING:
    from src.processors.memory_summarizer_processor import MemorySummarizer


class RedisMemoryStore:
    """Redis 기반 메모리 저장소"""

    def __init__(self, redis_client, summarizer: MemorySummarizer | None = None):
        self._redis = redis_client
        self._summarizer = summarizer

    def _format_key(self, pattern: str, session: str) -> str:
        return pattern.format(session=session)

    async def get_context(self, session: str) -> MemoryContext:
        """전체 메모리 컨텍스트 조회"""
        # Short-term
        short_key = self._format_key(REDIS_KEY_SHORT, session)
        short_data = await self._redis.lrange(short_key, -SHORT_TERM_SIZE, -1)
        short_term = [Turn(**json.loads(t)) for t in short_data]

        # Memory
        memory_key = self._format_key(REDIS_KEY_MEMORY, session)
        memory_data = await self._redis.get(memory_key)
        memory = ""
        if memory_data:
            state = MemoryState(**json.loads(memory_data))
            memory = state.content

        # Entities
        entities_key = self._format_key(REDIS_KEY_ENTITIES, session)
        entities_data = await self._redis.get(entities_key)
        entities = {}
        if entities_data:
            entities = json.loads(entities_data)

        # TTL 갱신 (조회 시마다 24시간 연장)
        await asyncio.gather(
            self._redis.expire(short_key, MEMORY_TTL_SECONDS),
            self._redis.expire(memory_key, MEMORY_TTL_SECONDS),
            self._redis.expire(entities_key, MEMORY_TTL_SECONDS),
        )

        return MemoryContext(
            short_term=short_term,
            memory=memory,
            entities=entities,
        )

    async def add_turn(self, session: str, turn: Turn) -> None:
        """
        턴 추가 + 필요 시 Memory Update 트리거

        단기기억이 SHORT_TERM_SIZE를 초과하면 오래된 턴들을
        Long-term Memory로 요약하여 이동
        """
        key = self._format_key(REDIS_KEY_SHORT, session)
        sanitized_turn = Turn(
            turn=turn.turn,
            user=sanitize_text(turn.user),
            assistant=sanitize_text(turn.assistant),
            ts=turn.ts,
        )
        await self._redis.rpush(key, sanitized_turn.model_dump_json())

        # 단기기억 개수 확인
        short_len = await self._redis.llen(key)

        if short_len > SHORT_TERM_SIZE and self._summarizer:
            # 오래된 턴들 추출 (앞에서 SHORT_TERM_SIZE개)
            to_process_data = await self._redis.lrange(key, 0, SHORT_TERM_SIZE - 1)
            to_process = [Turn(**json.loads(t)) for t in to_process_data]

            # 비동기로 Memory Update 실행
            asyncio.create_task(
                self._memory_update(session, to_process)
            )

            # 처리된 턴들 삭제 (앞에서 SHORT_TERM_SIZE개)
            await self._redis.ltrim(key, SHORT_TERM_SIZE, -1)

        await self._redis.expire(key, MEMORY_TTL_SECONDS)

    async def _memory_update(
        self, session: str, turns: list[Turn]
    ) -> None:
        """
        Recursive Summarization: 이전 메모리 + 새 대화 → 새 메모리

        Args:
            session: 세션 ID
            turns: 요약할 대화 턴들
        """
        if not self._summarizer:
            return

        memory_key = self._format_key(REDIS_KEY_MEMORY, session)
        entities_key = self._format_key(REDIS_KEY_ENTITIES, session)

        # 기존 메모리/엔티티 조회
        memory_data, entities_data = await asyncio.gather(
            self._redis.get(memory_key),
            self._redis.get(entities_key),
        )

        prev_memory = ""
        version = 0
        if memory_data:
            state = MemoryState(**json.loads(memory_data))
            prev_memory = state.content
            version = state.version

        prev_entities = json.loads(entities_data) if entities_data else {}

        # Recursive Summarization 실행
        result = await self._summarizer.recursive_summarize(
            prev_memory=prev_memory,
            new_turns=turns,
            prev_entities=prev_entities,
        )

        # Entities FIFO 적용 (최대 25개)
        entities_obj = Entities(data=prev_entities)
        entities_obj.update(result.entities, max_count=ENTITIES_MAX_COUNT)

        # 새 메모리 저장
        new_state = MemoryState(
            content=result.memory,
            version=version + 1,
            last_turns=f"{turns[0].turn}-{turns[-1].turn}",
        )

        await asyncio.gather(
            self._redis.set(
                memory_key,
                new_state.model_dump_json(),
                ex=MEMORY_TTL_SECONDS,
            ),
            self._redis.set(
                entities_key,
                json.dumps(entities_obj.data, ensure_ascii=False),
                ex=MEMORY_TTL_SECONDS,
            ),
        )

    async def update_memory(self, session: str, memory: str, entities: dict) -> None:
        """Long-term Memory 업데이트"""
        # Memory
        memory_key = self._format_key(REDIS_KEY_MEMORY, session)
        memory_data = await self._redis.get(memory_key)
        version = 0
        if memory_data:
            version = MemoryState(**json.loads(memory_data)).version

        new_state = MemoryState(content=memory, version=version + 1)
        await self._redis.set(
            memory_key,
            new_state.model_dump_json(),
            ex=MEMORY_TTL_SECONDS,
        )

        # Entities
        entities_key = self._format_key(REDIS_KEY_ENTITIES, session)
        await self._redis.set(
            entities_key,
            json.dumps(entities, ensure_ascii=False),
            ex=MEMORY_TTL_SECONDS,
        )

    async def clear(self, session: str) -> None:
        """세션 메모리 초기화"""
        keys = [
            self._format_key(REDIS_KEY_SHORT, session),
            self._format_key(REDIS_KEY_MEMORY, session),
            self._format_key(REDIS_KEY_ENTITIES, session),
        ]
        await self._redis.delete(*keys)

    async def get_all_turns(self, session: str) -> list[Turn]:
        """전체 대화 턴 조회"""
        key = self._format_key(REDIS_KEY_SHORT, session)
        data = await self._redis.lrange(key, 0, -1)
        return [Turn(**json.loads(t)) for t in data]
