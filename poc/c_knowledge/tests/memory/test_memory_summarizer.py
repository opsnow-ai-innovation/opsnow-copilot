"""memory/memory_summarizer.py 테스트"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models import SummarizerResult, Turn
from src.processors.memory_summarizer_processor import MemorySummarizer


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
        mock_response = MagicMock(
            output_text='{"memory": "사용자가 클라우드 비용을 확인함", "entities": {"provider": "AWS"}}'
        )
        with patch("src.processors.memory_summarizer_processor.client") as mock_client:
            mock_client.responses.create = AsyncMock(return_value=mock_response)

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
        mock_response = MagicMock(
            output_text=(
                '{"memory": "사용자가 AWS, GCP 비용 비교 중", '
                '"entities": {"provider": "GCP", "aws_cost": "$1000"}}'
            )
        )

        with patch("src.processors.memory_summarizer_processor.client") as mock_client:
            mock_client.responses.create = AsyncMock(return_value=mock_response)

            result = await summarizer.recursive_summarize(
                prev_memory="사용자가 AWS 비용을 확인함",
                new_turns=sample_turns,
                prev_entities={"provider": "AWS"},
            )

            assert "비교" in result.memory
            assert result.entities.get("provider") == "GCP"  # 덮어쓰기

    @pytest.mark.asyncio
    async def test_recursive_summarize_error_fallback(self, summarizer, sample_turns):
        """API 에러 시 이전 메모리 유지"""
        with patch("src.processors.memory_summarizer_processor.client") as mock_client:
            mock_client.responses.create = AsyncMock(
                side_effect=Exception("API Error")
            )

            prev_memory = "이전 메모리"
            prev_entities = {"key": "value"}

            result = await summarizer.recursive_summarize(
                prev_memory=prev_memory,
                new_turns=sample_turns,
                prev_entities=prev_entities,
            )

            # 에러 시 이전 값 유지
            assert result.memory == prev_memory
            assert result.entities == prev_entities
