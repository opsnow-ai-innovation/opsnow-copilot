"""
RAG Pipeline

사용자 질문 처리 진입점 (WebSocket → Context Builder → RAG Agent)
"""

import logging

from src.rag_assistant.agents.rag_agent import AgentResult, run_rag_agent
from src.processors.memory_store_processor import RedisMemoryStore
from src.processors.context_builder_processor import ContextBuilder
from src.rag_assistant.rag.reranker import Reranker
from src.rag_assistant.rag.search import FAISSSearch

logger = logging.getLogger(__name__)


class RagPipeline:
    """
    RAG 질문 처리 메인 클래스.

    WebSocket → ContextBuilder → RAG Agent 흐름 관리.
    """

    def __init__(
        self,
        search: FAISSSearch,
        reranker: Reranker,
        memory: RedisMemoryStore,
    ):
        """
        Args:
            search: FAISS 검색 인스턴스
            reranker: Reranker 인스턴스
            memory: RedisMemoryStore 인스턴스
        """
        self.search = search
        self.reranker = reranker
        self.memory = memory
        self.context_builder = ContextBuilder(memory=memory)

    async def process(
        self,
        query: str,
        dom_context_raw: str,
        page: dict,
        session_id: str,
        user_id: str = "",
    ) -> AgentResult:
        """
        사용자 질문 처리.

        Args:
            query: 사용자 질문
            dom_context_raw: WebSocket에서 받은 domContext (JSON string)
            page: 페이지 정보 dict
                - url: str
                - title: str
                - vendor: str | None
            session_id: 세션 ID
            user_id: 유저 ID (Fallback 메뉴 검색용)

        Returns:
            AgentResult (answer, sources, confidence 등)

        Raises:
            Exception: 처리 중 오류 발생 시
        """
        try:
            # 1. Context Builder로 통합 컨텍스트 생성
            integrated_context = await self.context_builder.build_context(
                query=query,
                dom_context_raw=dom_context_raw,
                page=page,
                session_id=session_id,
            )

            logger.info(
                f"Context built - Query: {query[:50]}, "
                f"Page: {page.get('url')}, "
                f"DomContext has_data: {integrated_context.dom_context.has_data}, "
                f"Memory length: {len(integrated_context.memory.memory)}"
            )

            # 2. RAG Agent 실행
            result = await run_rag_agent(
                integrated_context=integrated_context,
                search=self.search,
                reranker=self.reranker,
                user_id=user_id,
            )

            logger.info(
                f"RAG Agent completed - Confidence: {result.confidence:.2f}, "
                f"Sources: {len(result.sources)}, "
                f"Sufficient: {result.is_sufficient}"
            )

            # 3. Memory 업데이트 (비동기, 응답 후)
            # Note: add_turn은 LongtermMemory에서 비동기로 처리됨
            await self.memory.add_turn(
                session_id=session_id,
                user=query,
                assistant=result.answer,
            )

            return result

        except Exception as e:
            logger.error(f"Guide processing failed: {e}", exc_info=True)
            raise

    async def process_simple(
        self,
        query: str,
        session_id: str,
        user_id: str = "",
    ) -> AgentResult:
        """
        간단한 처리 (domContext 없이).

        테스트나 단순 질문 처리용.

        Args:
            query: 사용자 질문
            session_id: 세션 ID
            user_id: 유저 ID

        Returns:
            AgentResult
        """
        return await self.process(
            query=query,
            dom_context_raw="{}",
            page={"url": "", "title": ""},
            session_id=session_id,
            user_id=user_id,
        )
