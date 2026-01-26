"""memory/models.py 테스트"""

import pytest
from datetime import datetime

from src.models import Entities, MemoryContext, MemoryState, SummarizerResult, Turn


class TestTurn:
    """Turn 모델 테스트"""

    def test_turn_creation(self):
        """Turn 생성 확인"""
        turn = Turn(turn=1, user="안녕", assistant="안녕하세요!")
        assert turn.turn == 1
        assert turn.user == "안녕"
        assert turn.assistant == "안녕하세요!"
        assert isinstance(turn.ts, datetime)


class TestEntities:
    """Entities 모델 테스트"""

    def test_entities_update(self):
        """엔티티 업데이트 확인"""
        entities = Entities(data={"provider": "AWS"})
        entities.update({"service": "EC2"})
        assert entities.data == {"provider": "AWS", "service": "EC2"}

    def test_entities_fifo_limit(self):
        """FIFO 제한 확인"""
        entities = Entities(data={f"key{i}": f"val{i}" for i in range(3)})
        entities.update({"new": "value"}, max_count=3)
        assert len(entities.data) == 3
        assert "new" in entities.data
        assert "key0" not in entities.data  # FIFO로 삭제됨

    def test_entities_overwrite(self):
        """같은 키 덮어쓰기 확인"""
        entities = Entities(data={"provider": "AWS"})
        entities.update({"provider": "GCP"})
        assert entities.data["provider"] == "GCP"


class TestMemoryContext:
    """MemoryContext 모델 테스트"""

    def test_empty_context(self):
        """빈 컨텍스트 생성"""
        ctx = MemoryContext()
        assert ctx.short_term == []
        assert ctx.memory == ""
        assert ctx.entities == {}

    def test_context_with_data(self):
        """데이터가 있는 컨텍스트"""
        turn = Turn(turn=1, user="질문", assistant="답변")
        ctx = MemoryContext(
            short_term=[turn],
            memory="사용자가 AWS 비용을 확인함",
            entities={"provider": "AWS"},
        )
        assert len(ctx.short_term) == 1
        assert "AWS" in ctx.memory


class TestSummarizerResult:
    """SummarizerResult 모델 테스트"""

    def test_result_creation(self):
        """결과 생성 확인"""
        result = SummarizerResult(
            memory="요약된 메모리",
            entities={"key": "value"},
        )
        assert result.memory == "요약된 메모리"
        assert result.entities == {"key": "value"}
