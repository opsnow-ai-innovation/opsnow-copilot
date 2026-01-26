"""RAG context serialization tests."""

from src.models import ChunkMetadata, MemoryContext, SearchResult, Turn
from src.processors.rag_agent_processor import RAGContext


def test_rag_context_to_dict_serializes_memory_and_results():
    memory = MemoryContext(
        short_term=[Turn(turn=1, user="hello", assistant="hi")],
        memory="summary",
        entities={"provider": "aws"},
    )
    result = SearchResult(
        content="content",
        source="doc.md",
        score=0.9,
        metadata=ChunkMetadata(
            doc_id="doc1",
            doc_type="faq",
            guide_type="",
            section_path="",
            has_steps=False,
        ),
    )
    context = RAGContext(
        query="q",
        memory=memory,
        ranked_results=[result],
        answer="answer",
        sources=["doc.md"],
        confidence=0.8,
        is_sufficient=True,
    )

    payload = context.to_dict()

    assert payload["query"] == "q"
    assert payload["memory"]["short_term"] == [{"user": "hello", "assistant": "hi"}]
    assert payload["memory"]["long_term"] == "summary"
    assert payload["memory"]["entities"] == {"provider": "aws"}
    assert payload["ranked_results"][0]["doc_type"] == "faq"
