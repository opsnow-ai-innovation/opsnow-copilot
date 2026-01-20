"""RAG route tests."""

import os
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test")

from src.models import ChunkMetadata, MemoryContext, SearchResult, Turn  # noqa: E402
from src.routes.rag import (  # noqa: E402
    get_memory_store,
    get_pipeline,
    get_search,
    router,
)


def _build_app(pipeline, memory_store, search):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    app.dependency_overrides[get_search] = lambda: search
    return app


def test_context_endpoint_builds_memory_and_faq_response():
    memory = MemoryContext(
        short_term=[Turn(turn=1, user="hello", assistant="hi")],
        memory="one. two.",
        entities={"provider": "aws", "ignored": "skip"},
    )
    faq_result = SearchResult(
        content="faq content",
        source="faq.md",
        score=0.9,
        metadata=ChunkMetadata(
            doc_id="doc1",
            doc_type="faq",
            guide_type="",
            section_path="",
            has_steps=False,
        ),
    )
    guide_result = SearchResult(
        content="guide content",
        source="guide.md",
        score=0.5,
        metadata=ChunkMetadata(
            doc_id="doc2",
            doc_type="guide",
            guide_type="user",
            section_path="",
            has_steps=False,
        ),
    )
    async def fake_retrieve(**kwargs):
        return SimpleNamespace(
            memory=memory,
            ranked_results=[faq_result, guide_result],
        )

    pipeline = SimpleNamespace(retrieve=fake_retrieve)

    app = _build_app(pipeline, memory_store=None, search=None)
    client = TestClient(app)

    response = client.post(
        "/rag/context",
        json={"query": "q", "session": "s", "user_id": ""},
    )
    assert response.status_code == 200
    payload = response.json()

    assert "one." in payload["memory"][0]
    assert any("provider: aws" == item for item in payload["memory"])
    assert payload["faq"] == ["Q: faq content"]
    assert payload["menu"] == []


def test_debug_memory_endpoint_returns_short_long_entities():
    memory = MemoryContext(
        short_term=[Turn(turn=1, user="hi", assistant="ok")],
        memory="summary",
        entities={"budget": "100"},
    )
    async def fake_get_context(*args, **kwargs):
        return memory

    memory_store = SimpleNamespace(get_context=fake_get_context)

    app = _build_app(pipeline=None, memory_store=memory_store, search=None)
    client = TestClient(app)

    response = client.post("/rag/debug/memory", json={"session": "s"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["short_term"] == [{"turn": 1, "user": "hi", "assistant": "ok"}]
    assert payload["long_term"] == "summary"
    assert payload["entities"] == {"budget": "100"}


def test_debug_search_filters_doc_type():
    faq_result = SearchResult(
        content="faq",
        source="faq.md",
        score=0.9,
        metadata=ChunkMetadata(
            doc_id="doc1",
            doc_type="faq",
            guide_type="",
            section_path="",
            has_steps=False,
        ),
    )
    guide_result = SearchResult(
        content="guide",
        source="guide.md",
        score=0.5,
        metadata=ChunkMetadata(
            doc_id="doc2",
            doc_type="guide",
            guide_type="user",
            section_path="",
            has_steps=False,
        ),
    )
    async def fake_search(**kwargs):
        return [faq_result, guide_result]

    search = SimpleNamespace(search=fake_search)

    app = _build_app(pipeline=None, memory_store=None, search=search)
    client = TestClient(app)

    response = client.post(
        "/rag/debug/search",
        json={"query": "q", "doc_type": "faq", "top_k": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["doc_type"] == "faq"
