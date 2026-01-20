"""
Context Processor

WebSocket → Memory + DomContext → LLM 컨텍스트 구성
"""

from dataclasses import dataclass, field

from src.processors.memory_store_processor import RedisMemoryStore
from src.models import (
    IntegratedContext,
    MemoryContext,
    PageInfo,
    ParsedDomContext,
    Turn,
)
from src.rag_assistant.dom_parser import DomContextParser


@dataclass
class LLMContext:
    """LLM에 전달할 컨텍스트 (디자인 문서 Section 6)"""

    long_term_memory: str = ""
    entities: dict[str, str] = field(default_factory=dict)
    short_term: list[Turn] = field(default_factory=list)
    faq_results: list[str] = field(default_factory=list)

    def build_prompt_sections(self) -> str:
        """
        LLM 프롬프트용 컨텍스트 섹션 생성

        Returns:
            포맷팅된 컨텍스트 문자열
        """
        sections = []

        # Long-term Memory (~500 토큰)
        if self.long_term_memory:
            sections.append(f"## 대화 맥락\n{self.long_term_memory}")

        # Entities (~200 토큰)
        if self.entities:
            entities_text = "\n".join(
                f"- {k}: {v}" for k, v in self.entities.items()
            )
            sections.append(f"## 참고 정보\n{entities_text}")

        # 단기기억 - 최근 대화 (~1500 토큰)
        if self.short_term:
            turns_text = "\n".join(
                f"User: {t.user}\nAssistant: {t.assistant}"
                for t in self.short_term
            )
            sections.append(f"## 최근 대화\n{turns_text}")

        # FAQ/Guide 결과
        if self.faq_results:
            faq_text = "\n".join(self.faq_results)
            sections.append(f"## 관련 FAQ/가이드\n{faq_text}")

        return "\n\n".join(sections)


def build_memory_response(context: MemoryContext) -> list[str]:
    """
    Long-term Memory + Entities를 API 응답 형식으로 변환
    (디자인 문서 Section 13.3)

    Args:
        context: 메모리 컨텍스트

    Returns:
        문자열 리스트 형태의 메모리 응답
    """
    result = []

    # Long-term Memory → 문장 단위로 분리
    if context.memory:
        sentences = context.memory.split(". ")
        for sentence in sentences:
            cleaned = sentence.strip()
            if not cleaned:
                continue
            cleaned = cleaned.rstrip(".")
            result.append(f"{cleaned}.")

    # Entities → 핵심 정보만 추가
    if context.entities:
        key_fields = ["budget", "total_cost", "provider", "period"]
        for key, value in context.entities.items():
            if key in key_fields:
                result.append(f"{key}: {value}")

    return result


def build_llm_context(
    memory: MemoryContext,
    faq_results: list[str] | None = None,
) -> LLMContext:
    """
    메모리 + RAG 결과 → LLM 컨텍스트 구성

    Args:
        memory: 메모리 컨텍스트
        faq_results: FAQ/Guide 검색 결과

    Returns:
        LLMContext: LLM 프롬프트에 사용할 컨텍스트
    """
    return LLMContext(
        long_term_memory=memory.memory,
        entities=memory.entities,
        short_term=memory.short_term,
        faq_results=faq_results or [],
    )


# ============================================
# Context Builder (통합 진입점)
# ============================================


class ContextBuilder:
    """
    WebSocket → Memory + DomContext 통합 처리.

    domContext 구조가 불명확한 상태에서 유연하게 처리.
    나중에 Parser만 교체하면 Agent 코드는 변경 없음.
    """

    def __init__(self, memory: RedisMemoryStore):
        """
        Args:
            memory: RedisMemoryStore 인스턴스
        """
        self.memory = memory
        self.dom_parser = DomContextParser()

    async def build_context(
        self,
        query: str,
        dom_context_raw: str,
        page: dict,
        session_id: str,
    ) -> IntegratedContext:
        """
        WebSocket 메시지 → 통합 컨텍스트 생성.

        Args:
            query: 사용자 질문
            dom_context_raw: WebSocket domContext (JSON string)
            page: 페이지 정보 dict
            session_id: 세션 ID

        Returns:
            IntegratedContext: Agent에 전달할 통합 컨텍스트
        """
        # 1. DOM 파싱 (유연하게)
        dom_context = self.dom_parser.parse(dom_context_raw)

        # 2. Memory 조회
        memory_context = await self.memory.get_context(session_id)

        # 3. 페이지 정보 파싱
        page_info = PageInfo(
            url=page.get("url", ""),
            title=page.get("title", ""),
            vendor=page.get("vendor"),
        )

        # 4. 통합
        return IntegratedContext(
            user_query=query,
            dom_context=dom_context,
            page_info=page_info,
            memory=memory_context,
        )
