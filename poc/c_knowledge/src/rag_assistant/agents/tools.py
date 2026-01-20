"""pydantic-ai Agent용 검색 도구"""

import logging
from dataclasses import dataclass, field

from pydantic_ai import RunContext

from src.models import IntegratedContext, RerankResult, SearchResult
from src.rag_assistant.rag.reranker import Reranker
from src.rag_assistant.rag.search import FAISSSearch

logger = logging.getLogger(__name__)


@dataclass
class RAGDependencies:
    """의존성 주입용 컨텍스트"""

    search: FAISSSearch
    reranker: Reranker
    integrated_context: IntegratedContext  # 🆕 추가
    context_pool: list[SearchResult] = field(default_factory=list)
    current_query: str = ""


# ─────────────────────────────────────────────────────────────
# Tool 1: 통합 검색 (FAQ 3 : Guide 7)
# ─────────────────────────────────────────────────────────────
async def search_all(
    ctx: RunContext[RAGDependencies],
    query: str,
) -> RerankResult:
    """
    FAQ + Guide 통합 검색 후 Rerank + 충분성 평가.

    - FAQ에서 3개, Guide에서 7개 검색
    - 합쳐서 Rerank
    - 충분성 평가까지 한 번에

    Args:
        query: 검색 쿼리

    Returns:
        RerankResult (ranked_results, is_sufficient, missing, next_action)
    """
    logger.info(f"[Tool:search_all] 호출됨 - query: {query}")

    # 1. FAQ 검색 (k=3)
    faq_results = await ctx.deps.search.search_faq(query, k=3)
    logger.debug(f"  FAQ 검색 결과: {len(faq_results)}개")

    # 2. Guide 검색 (k=7)
    guide_results = await ctx.deps.search.search_guide(query, k=7)
    logger.debug(f"  Guide 검색 결과: {len(guide_results)}개")

    # 3. 합치기
    all_results = faq_results + guide_results
    logger.debug(f"  전체 검색 결과: {len(all_results)}개")

    # 4. Rerank + 충분성 평가 (LLM 1회)
    rerank_result = await ctx.deps.reranker.rerank_and_evaluate(
        query=query,
        candidates=all_results,
    )
    logger.info(f"  Rerank 완료 - is_sufficient: {rerank_result.is_sufficient}, confidence: {rerank_result.confidence}, top_k: {len(rerank_result.ranked_results)}")

    # 5. 컨텍스트 풀 업데이트
    ctx.deps.context_pool = rerank_result.ranked_results
    ctx.deps.current_query = query

    return rerank_result


# ─────────────────────────────────────────────────────────────
# Tool 2: 메타데이터 기반 필터 검색
# ─────────────────────────────────────────────────────────────
async def search_by_metadata(
    ctx: RunContext[RAGDependencies],
    query: str,
    doc_type: str | None = None,
    guide_type: str | None = None,
    has_steps: bool | None = None,
    section_path: str | None = None,
) -> RerankResult:
    """
    메타데이터 필터로 검색. 특정 조건의 문서만 검색할 때 사용.

    Args:
        query: 검색 쿼리
        doc_type: "faq" | "guide" | None (None이면 전체)
        guide_type: "user" | "developer" | "tech_blog" | None
        has_steps: True면 단계별 설명 있는 문서만
        section_path: 특정 섹션 경로로 필터 (예: "Menu > Budget")

    Returns:
        RerankResult (필터링된 검색 결과)
    """
    logger.info(f"[Tool:search_by_metadata] 호출됨 - query: {query}, doc_type: {doc_type}, has_steps: {has_steps}")

    # 1. 메타데이터 필터 검색
    results = await ctx.deps.search.search_by_metadata(
        query=query,
        doc_type=doc_type,
        guide_type=guide_type,
        has_steps=has_steps,
        section_path=section_path,
        k=10,
    )
    logger.debug(f"  메타데이터 검색 결과: {len(results)}개")

    # 2. Rerank + 충분성 평가
    rerank_result = await ctx.deps.reranker.rerank_and_evaluate(
        query=query,
        candidates=results,
    )
    logger.info(f"  Rerank 완료 - is_sufficient: {rerank_result.is_sufficient}, confidence: {rerank_result.confidence}")

    # 3. 컨텍스트 풀 업데이트
    ctx.deps.context_pool = rerank_result.ranked_results
    ctx.deps.current_query = query

    return rerank_result


# ─────────────────────────────────────────────────────────────
# Tool 3: 섹션 확장
# ─────────────────────────────────────────────────────────────
async def get_section(
    ctx: RunContext[RAGDependencies],
    doc_id: str,
    section_path: str,
) -> RerankResult:
    """
    특정 문서의 섹션 전체를 가져와서 Rerank.

    Args:
        doc_id: 문서 ID
        section_path: 섹션 경로 (예: "Menu > Budget > Alerts")

    Returns:
        RerankResult (확장된 결과 포함)
    """
    logger.info(f"[Tool:get_section] 호출됨 - doc_id: {doc_id}, section_path: {section_path}")

    # 1. 섹션 chunk 가져오기
    section_results = await ctx.deps.search.get_section(doc_id, section_path)
    logger.debug(f"  섹션 검색 결과: {len(section_results)}개")

    # 2. 기존 컨텍스트와 합치기
    existing_contents = {r.content for r in ctx.deps.context_pool}
    for r in section_results:
        if r.content not in existing_contents:
            ctx.deps.context_pool.append(r)
    logger.debug(f"  컨텍스트 풀 업데이트: {len(ctx.deps.context_pool)}개")

    # 3. 다시 Rerank + 충분성 평가
    rerank_result = await ctx.deps.reranker.rerank_and_evaluate(
        query=ctx.deps.current_query,
        candidates=ctx.deps.context_pool,
    )
    logger.info(f"  Rerank 완료 - is_sufficient: {rerank_result.is_sufficient}, confidence: {rerank_result.confidence}")

    # 4. 컨텍스트 풀 업데이트
    ctx.deps.context_pool = rerank_result.ranked_results

    return rerank_result
