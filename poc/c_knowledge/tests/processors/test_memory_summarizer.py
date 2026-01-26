"""memory/memory_summarizer.py 테스트"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models import SummarizerResult, Turn
from src.processors.memory_summarizer_processor import MemorySummarizer, _fallback_summarize


def _mock_chat_response(content: dict) -> MagicMock:
    """chat.completions.create 응답 mock 생성"""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(content)))
    ]
    mock_response.usage = MagicMock(
        prompt_tokens=100, completion_tokens=50, total_tokens=150
    )
    return mock_response


class TestMemorySummarizer:
    """MemorySummarizer 테스트"""

    @pytest.fixture
    def summarizer(self):
        return MemorySummarizer()

    @pytest.fixture
    def sample_turns(self):
        return [
            Turn(turn=1, user="AWS 비용 알려줘", assistant="현재 AWS 비용은 $1,000입니다."),
            Turn(turn=2, user="GCP는?", assistant="GCP 비용은 $500입니다."),
        ]

    @pytest.mark.asyncio
    async def test_recursive_summarize_success(self, summarizer, sample_turns):
        """정상적인 요약 처리"""
        mock_response = _mock_chat_response({
            "memory": "사용자가 클라우드 비용을 확인함",
            "entities": {"provider": "AWS"}
        })

        with patch("src.processors.memory_summarizer_processor.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await summarizer.recursive_summarize(
                prev_memory="",
                new_turns=sample_turns,
                prev_entities={},
            )

            assert isinstance(result, SummarizerResult)
            assert "비용" in result.memory
            assert result.entities.get("provider") == "AWS"

    @pytest.mark.asyncio
    async def test_recursive_summarize_with_prev_memory(self, summarizer, sample_turns):
        """이전 메모리가 있는 경우"""
        mock_response = _mock_chat_response({
            "memory": "사용자가 AWS, GCP 비용 비교 중",
            "entities": {"provider": "GCP", "aws_cost": "$1000"}
        })

        with patch("src.processors.memory_summarizer_processor.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await summarizer.recursive_summarize(
                prev_memory="사용자가 AWS 비용을 확인함",
                new_turns=sample_turns,
                prev_entities={"provider": "AWS"},
            )

            assert "비교" in result.memory
            assert result.entities.get("provider") == "GCP"  # 덮어쓰기

    @pytest.mark.asyncio
    async def test_recursive_summarize_error_fallback(self, summarizer, sample_turns):
        """API 에러 시 fallback 요약 사용"""
        with patch("src.processors.memory_summarizer_processor.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API Error")
            )

            prev_memory = "이전 메모리"
            prev_entities = {"key": "value"}

            result = await summarizer.recursive_summarize(
                prev_memory=prev_memory,
                new_turns=sample_turns,
                prev_entities=prev_entities,
            )

            # fallback: 이전 메모리 포함, entities 유지
            assert prev_memory in result.memory
            assert result.entities == prev_entities


class TestFallbackSummarize:
    """_fallback_summarize 함수 테스트"""

    def test_fallback_preserves_prev_memory(self):
        """이전 메모리가 포함되는지 확인"""
        prev_memory = "사용자는 AWS 비용에 관심"
        new_turns = [Turn(turn=1, user="질문", assistant="답변")]
        prev_entities = {"provider": "AWS"}

        result = _fallback_summarize(prev_memory, new_turns, prev_entities)

        assert prev_memory in result.memory
        assert result.entities == prev_entities
