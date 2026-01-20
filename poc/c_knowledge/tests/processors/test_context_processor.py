"""Context processor tests."""

from unittest.mock import AsyncMock

import pytest

from src.models import MemoryContext, Turn
from src.processors.context_builder_processor import (
    ContextBuilder,
    build_memory_response,
)


def test_build_memory_response_splits_and_filters():
    context = MemoryContext(
        short_term=[],
        memory="첫번째 문장. 두번째 문장.",
        entities={
            "budget": "100",
            "provider": "aws",
            "period": "2024-01",
            "ignored": "skip",
        },
    )

    result = build_memory_response(context)

    assert result[:2] == ["첫번째 문장.", "두번째 문장."]
    assert "budget: 100" in result
    assert "provider: aws" in result
    assert "period: 2024-01" in result
    assert all("ignored" not in item for item in result)


@pytest.mark.asyncio
async def test_context_builder_uses_memory_and_dom_context():
    memory = MemoryContext(
        short_term=[Turn(turn=1, user="hi", assistant="hello")],
        memory="summary",
        entities={"provider": "aws"},
    )
    memory_store = AsyncMock()
    memory_store.get_context = AsyncMock(return_value=memory)

    builder = ContextBuilder(memory=memory_store)
    dom_context_raw = '{"summary":{"totalCost":"$10"}}'
    page = {"url": "/budget", "title": "Budget", "vendor": "opsnow"}

    context = await builder.build_context(
        query="내 예산",
        dom_context_raw=dom_context_raw,
        page=page,
        session_id="",
    )

    memory_store.get_context.assert_awaited_once_with("")
    assert context.user_query == "내 예산"
    assert context.memory is memory
    assert context.page_info.url == "/budget"
    assert context.page_info.title == "Budget"
    assert context.page_info.vendor == "opsnow"
    assert context.dom_context.has_data is True
    assert "totalCost" in context.dom_context.summary
