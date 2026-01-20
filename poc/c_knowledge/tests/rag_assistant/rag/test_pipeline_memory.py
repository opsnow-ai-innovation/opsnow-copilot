"""RAG pipeline memory retrieval tests."""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.models import MemoryContext, Turn


@pytest.mark.asyncio
async def test_rag_pipeline_uses_redis_memory(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    import src.config as config
    import src.rag_assistant.agents.rag_agent as rag_agent

    importlib.reload(config)
    importlib.reload(rag_agent)

    from src.processors.rag_agent_processor import RAGPipeline

    memory_context = MemoryContext(
        short_term=[Turn(turn=1, user="hi", assistant="hello")],
        memory="previous summary",
        entities={"provider": "aws"},
    )

    memory_store = SimpleNamespace(get_context=AsyncMock(return_value=memory_context))
    search = object()

    async def fake_run_rag_agent(*, integrated_context, search, reranker, user_id=""):
        assert integrated_context.user_query == "hello"
        assert integrated_context.memory is memory_context
        return SimpleNamespace(
            ranked_results=[],
            answer="ok",
            sources=["src"],
            confidence=0.9,
            is_sufficient=True,
        )

    with patch("src.processors.rag_agent_processor.run_rag_agent", new=fake_run_rag_agent):
        pipeline = RAGPipeline(memory_store=memory_store, search=search)
        context = await pipeline.retrieve(
            query="hello",
            session="s1",
            user_id="user1",
        )

    memory_store.get_context.assert_awaited_once_with("s1")
    assert context.memory is memory_context
    assert context.answer == "ok"

    context_dict = context.to_dict()
    assert context_dict["memory"]["short_term"] == [
        {"user": "hi", "assistant": "hello"}
    ]
    assert context_dict["memory"]["long_term"] == "previous summary"
    assert context_dict["memory"]["entities"] == {"provider": "aws"}
