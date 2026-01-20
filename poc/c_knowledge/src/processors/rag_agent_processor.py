"""
RAG 파이프라인

메모리 컨텍스트 + pydantic-ai Agentic RAG 검색 결과를 반환
"""

from dataclasses import dataclass
import logging

from src.models import SearchResult, IntegratedContext, PageInfo, ParsedDomContext
from src.rag_assistant.agents.rag_agent import AgentResult, run_rag_agent
from src.models import MemoryContext
from src.processors.memory_store_processor import RedisMemoryStore
from src.rag_assistant.dom_parser import DomContextParser
from src.rag_assistant.rag.reranker import Reranker
from src.rag_assistant.rag.search import FAISSSearch

logger = logging.getLogger(__name__)

@dataclass
class RAGContext:
    """RAG 파이프라인 결과"""

    query: str
    memory: MemoryContext
    ranked_results: list[SearchResult]
    answer: str
    sources: list[str]
    confidence: float
    is_sufficient: bool

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "memory": {
                "short_term": [
                    {"user": t.user, "assistant": t.assistant}
                    for t in self.memory.short_term
                ],
                "long_term": self.memory.memory,
                "entities": self.memory.entities,
            },
            "ranked_results": [
                {
                    "content": r.content,
                    "source": r.source,
                    "score": r.score,
                    "doc_type": r.metadata.doc_type,
                }
                for r in self.ranked_results
            ],
            "answer": self.answer,
            "sources": self.sources,
            "confidence": self.confidence,
            "is_sufficient": self.is_sufficient,
        }


class RAGPipeline:
    """
    pydantic-ai Agentic RAG 파이프라인

    1. 메모리에서 컨텍스트 조회
    2. pydantic-ai Agent 실행 (검색 → Rerank → 충분성 평가 → 응답 생성)
    3. 결과 반환
    """

    def __init__(self, memory_store: RedisMemoryStore, search: FAISSSearch):
        self._memory = memory_store
        self._search = search
        self._reranker = Reranker()
        self._dom_parser = DomContextParser()

    async def retrieve(
        self,
        query: str,
        session: str,
        user_id: str = "",
        dom_context_raw: str | None = None,
    ) -> RAGContext:
        """
        Agentic RAG 검색 + 응답 생성

        Args:
            query: 사용자 질의
            session: 세션 ID
            user_id: 유저 ID (Fallback 메뉴 검색용)

        Returns:
            RAGContext: 메모리 + Agentic RAG 결과 + 응답
        """
        # 1. 메모리 컨텍스트 조회
        memory = await self._memory.get_context(session)
        logger.debug(
            "Memory context: session=%s short_term=%s long_term_len=%s entities=%s",
            session,
            len(memory.short_term),
            len(memory.memory or ""),
            list((memory.entities or {}).keys()),
        )

        # 2. IntegratedContext 생성
        if dom_context_raw is None:
            dom_context = ParsedDomContext(
                raw="",
                summary="",
                has_data=False,
            )
        else:
            dom_context = self._dom_parser.parse(dom_context_raw)

        integrated_context = IntegratedContext(
            user_query=query,
            dom_context=dom_context,
            page_info=PageInfo(url="", title=""),
            memory=memory,
        )

        # 3. pydantic-ai Agent 실행
        agent_result: AgentResult = await run_rag_agent(
            integrated_context=integrated_context,
            search=self._search,
            reranker=self._reranker,
            user_id=user_id,
        )
        logger.debug(
            "Agent result: results=%s sources=%s confidence=%.2f sufficient=%s",
            len(agent_result.ranked_results),
            agent_result.sources,
            agent_result.confidence,
            agent_result.is_sufficient,
        )

        return RAGContext(
            query=query,
            memory=memory,
            ranked_results=agent_result.ranked_results,
            answer=agent_result.answer,
            sources=agent_result.sources,
            confidence=agent_result.confidence,
            is_sufficient=agent_result.is_sufficient,
        )
