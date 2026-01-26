"""pydantic-ai 기반 RAG Agent"""

import json
import logging
from dataclasses import dataclass

from pydantic_ai import Agent
from openai import AsyncOpenAI

from src.rag_assistant.agents.tools import (
    RAGDependencies,
    get_section,
    search_all,
    search_by_metadata,
)
from src.config import OPENAI_MODEL
from src.mock.menu_service import MenuService
from src.models import IntegratedContext, RAGResult, SearchResult
from src.rag_assistant.rag.reranker import Reranker
from src.rag_assistant.rag.search import FAISSSearch
from src.utils.secrets import get_open_ai_key
from src.utils.token_logger import (
    TokenTimer,
    extract_usage_from_response,
    log_token_usage,
)

logger = logging.getLogger(__name__)
_format_client = AsyncOpenAI(api_key=get_open_ai_key())

# ─────────────────────────────────────────────────────────────
# Agent 정의
# ─────────────────────────────────────────────────────────────
from pydantic_ai.models.openai import OpenAIModelSettings

rag_agent = Agent[RAGDependencies, RAGResult](
    f"openai:{OPENAI_MODEL}",
    model_settings=OpenAIModelSettings(
        response_format={"type": "json_object"}
    ),
    system_prompt="""You are an OpsNow Guide Agent that answers user questions.

## Available Context (provided in user message):
- **Screen Context (domContext)**: Current page information visible to the user
- **Conversation Memory**: Previous conversation history
- **Entities**: Key facts from past conversations (costs, periods, providers, etc.)

## Decision Strategy:

### 1. Check if question references previous conversation
- Keywords: "아까", "그거", "이전", "방금", etc.
- If YES → Answer from Memory/Entities (no search needed)
- If NO → Proceed to next step

### 2. Check if question is about visible screen data
- If screen context has relevant data → Answer directly (no search needed)
- Example: "총 비용?" and screen shows totalCost → Use screen data
- If NO or screen context empty → Proceed to search

### 3. Search for guides/FAQs
- Call search_all with the user's query
- Check the result:
  - If is_sufficient=true → Generate answer using ranked_results
  - If is_sufficient=false → Check next_action:
    - If next_action="search_again" → Call search_all(refined_query)
    - If next_action="get_section" → Call get_section with doc_id and section_path from top result
  - Then check sufficiency again
- Maximum 3 tool calls total

## Fallback Rules:
- 3회 호출 후에도 is_sufficient=false → 있는 컨텍스트로 최선의 답변 생성
- confidence < 0.5 → "관련 문서를 찾지 못했습니다" + 가장 가까운 메뉴 링크 제안
- ranked_results가 비어있음 → "해당 내용은 준비 중입니다" 응답

## Rules:
- Always cite sources in your answer
- If steps are mentioned, include ALL steps
- Answer in the same language as the query
- Prioritize: Memory > Screen Context > Search Results
- Return RAGResult with answer, sources list, and confidence score

## Output Format (STRICT):
Return ONLY valid JSON matching this schema:
{"answer": "string", "sources": ["string"], "confidence": 0.0}
No extra text, no markdown, no commentary.
""",
)

# 도구 등록
rag_agent.tool(search_all)
rag_agent.tool(search_by_metadata)
rag_agent.tool(get_section)


# ─────────────────────────────────────────────────────────────
# Agent 결과
# ─────────────────────────────────────────────────────────────
@dataclass
class AgentResult:
    """Agent 최종 결과"""

    ranked_results: list[SearchResult]
    answer: str
    sources: list[str]
    confidence: float
    is_sufficient: bool


# ─────────────────────────────────────────────────────────────
# Context 포맷팅 헬퍼
# ─────────────────────────────────────────────────────────────
def _format_context_for_agent(context: IntegratedContext) -> str:
    """
    IntegratedContext를 Agent가 이해할 수 있는 텍스트로 변환.

    Args:
        context: 통합 컨텍스트

    Returns:
        포맷팅된 컨텍스트 문자열
    """
    sections = []

    # 1. Screen Context (domContext)
    if context.dom_context.has_data:
        sections.append(
            f"## Screen Context\n"
            f"Page: {context.page_info.url} ({context.page_info.title})\n"
            f"{context.dom_context.summary}"
        )
    else:
        sections.append("## Screen Context\n(No screen data available)")

    # 2. Conversation Memory
    if context.memory.memory:
        sections.append(f"## Conversation Memory\n{context.memory.memory}")

    # 3. Entities
    if context.memory.entities:
        entities_str = json.dumps(context.memory.entities, ensure_ascii=False, indent=2)
        sections.append(f"## Key Facts (Entities)\n{entities_str}")

    # 4. Recent Conversation (Short-term)
    if context.memory.short_term:
        recent_turns = "\n".join(
            f"Turn {turn.turn}:\nUser: {turn.user}\nAssistant: {turn.assistant}"
            for turn in context.memory.short_term[-3:]  # 최근 3턴만
        )
        sections.append(f"## Recent Conversation\n{recent_turns}")

    return "\n\n".join(sections)


async def _coerce_rag_result(text: str) -> RAGResult:
    """
    문자열 응답을 JSON으로 강제 변환.
    모델이 JSON을 지키지 않을 때 1회 보정 호출.
    """
    prompt = (
        "Convert the following text into a JSON object with keys: "
        "answer (string), sources (array of strings), confidence (0.0 to 1.0).\n"
        "If sources are missing, use an empty array. If confidence is missing, use 0.3.\n"
        "Return ONLY JSON.\n\n"
        f"TEXT:\n{text}"
    )
    try:
        with TokenTimer() as timer:
            response = await _format_client.responses.create(
                model=OPENAI_MODEL,
                input=prompt,
                response_format={"type": "json_object"},
                max_output_tokens=300,
            )

        # 토큰 사용량 로깅
        usage = extract_usage_from_response(response)
        log_token_usage(
            model=OPENAI_MODEL,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            duration_ms=timer.duration_ms,
            caller="_coerce_rag_result",
        )

        parsed = json.loads(_extract_response_text(response))
        return RAGResult(**parsed)
    except Exception as exc:
        logger.error("RAGResult 강제 변환 실패: %s", exc)
        return RAGResult(answer=text, sources=[], confidence=0.3)


def _extract_response_text(response) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text
    text_outputs: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) == "message" and hasattr(item, "content"):
            for content_item in item.content:
                if getattr(content_item, "type", None) == "output_text":
                    text_outputs.append(content_item.text)
    return "\n".join(text_outputs) if text_outputs else ""


# ─────────────────────────────────────────────────────────────
# 메인 실행 함수
# ─────────────────────────────────────────────────────────────
async def run_rag_agent(
    integrated_context: IntegratedContext,
    search: FAISSSearch,
    reranker: Reranker,
    user_id: str = "",
) -> AgentResult:
    """
    Agentic RAG 실행.

    Args:
        integrated_context: 통합 컨텍스트 (query, domContext, memory 포함)
        search: FAISSSearch 인스턴스
        reranker: Reranker 인스턴스
        user_id: 유저 ID (Fallback 메뉴 검색용)

    Returns:
        AgentResult (ranked_results, answer, sources, confidence, is_sufficient)
    """
    query = integrated_context.user_query

    # 의존성 설정
    deps = RAGDependencies(
        search=search,
        reranker=reranker,
        integrated_context=integrated_context,
        current_query=query,
    )

    # TODO: 합칠 때 제거 - Mock 메뉴 서비스
    menu_service = MenuService()

    try:
        # Context를 포함한 user message 생성
        context_str = _format_context_for_agent(integrated_context)
        user_message = f"{context_str}\n\n## User Question\n{query}"

        # UTF-8 문제 방지: user_message sanitize
        user_message = _sanitize_text(user_message)

        logger.info(f"[Agent 시작] query: {query}")
        logger.debug(f"  Context 길이: {len(context_str)} chars")

        # Agent 실행
        with TokenTimer() as timer:
            result = await rag_agent.run(user_message, deps=deps)

        # TODO: 프로덕션 배포 전 삭제 - 토큰 사용량 로깅
        usage = extract_usage_from_response(result)
        log_token_usage(
            model=OPENAI_MODEL,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            duration_ms=timer.duration_ms,
            caller="run_rag_agent",
        )

        # pydantic-ai 최신 버전에서는 result.output 또는 result.all_messages() 사용
        logger.debug(f"  Agent result 타입: {type(result)}")
        logger.debug(f"  Agent result 속성: {dir(result)}")

        # result에서 RAGResult 추출
        if hasattr(result, 'data'):
            rag_result_raw = result.data
        elif hasattr(result, 'output'):
            rag_result_raw = result.output
        else:
            raise AttributeError(f"Agent result has no 'data' or 'output' attribute. Type: {type(result)}, Attributes: {dir(result)}")

        # RAGResult 파싱 (문자열이면 JSON 파싱 시도)
        if isinstance(rag_result_raw, str):
            logger.warning(f"Agent가 문자열 반환: {rag_result_raw[:200]}")
            try:
                parsed_json = json.loads(rag_result_raw)
                rag_result = RAGResult(**parsed_json)
            except (json.JSONDecodeError, TypeError, ValueError):
                rag_result = await _coerce_rag_result(rag_result_raw)
        elif isinstance(rag_result_raw, RAGResult):
            rag_result = rag_result_raw
        else:
            logger.error(f"예상치 못한 타입: {type(rag_result_raw)}")
            rag_result = RAGResult(
                answer=str(rag_result_raw),
                sources=[],
                confidence=0.3,
            )

        logger.info(f"[Agent 완료] confidence: {rag_result.confidence}, sources: {len(rag_result.sources)}, context_pool: {len(deps.context_pool)}")

        # Fallback: confidence < 0.5면 메뉴 추천 추가
        answer = _sanitize_text(rag_result.answer)
        if rag_result.confidence < 0.5 and user_id:
            menus = await menu_service.search_menus(query, user_id)
            if menus:
                menu_links = _sanitize_text(menu_service.format_menu_links(menus))
                answer = f"{answer}\n\n{menu_links}"

        return AgentResult(
            ranked_results=deps.context_pool,
            answer=answer,
            sources=rag_result.sources,
            confidence=rag_result.confidence,
            is_sufficient=rag_result.confidence >= 0.5,
        )

    except Exception as e:
        import traceback
        logger.error(f"RAG Agent 실행 오류: {e}")
        logger.error(f"상세 오류:\n{traceback.format_exc()}")

        # Fallback: 기본 검색 + 메뉴 추천
        faq_results = await search.search_faq(query)
        guide_results = await search.search_guide(query)
        all_results = faq_results + guide_results

        fallback_answer = "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."

        # 메뉴 추천 추가
        if user_id:
            try:
                menus = await menu_service.search_menus(query, user_id)
                if menus:
                    menu_links = _sanitize_text(menu_service.format_menu_links(menus))
                    fallback_answer = f"{fallback_answer}\n\n{menu_links}"
            except Exception as menu_error:
                logger.error(f"메뉴 검색 오류: {menu_error}")

        return AgentResult(
            ranked_results=all_results[:5],
            answer=_sanitize_text(fallback_answer),
            sources=[],
            confidence=0.0,
            is_sufficient=False,
        )
