"""Rerank + 충분성 평가 통합"""

import json

from openai import AsyncOpenAI

from src.models import RerankResult, SearchResult
from src.config import OPENAI_MODEL
from src.constants.rag import RERANK_TOP_K
from src.utils.secrets import get_open_ai_key

client = AsyncOpenAI(api_key=get_open_ai_key())


def _sanitize_text(text: str) -> str:
    """UTF-8 인코딩이 불가능한 문자 제거"""
    try:
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        return text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')


class Reranker:
    """Rerank + 충분성 평가 통합 클래스"""

    async def rerank_and_evaluate(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = RERANK_TOP_K,
    ) -> RerankResult:
        """
        Rerank + 충분성 평가를 한 번의 LLM 호출로 처리.

        Args:
            query: 사용자 쿼리
            candidates: 검색된 후보 문서들
            top_k: 상위 몇 개 반환할지

        Returns:
            RerankResult (ranked_results, is_sufficient, missing, next_action)
        """
        if not candidates:
            return RerankResult(
                ranked_results=[],
                is_sufficient=False,
                missing=["no_results"],
                next_action=None,
                confidence=0.0,
            )

        # query 정리
        clean_query = _sanitize_text(query)

        # 후보 텍스트 구성
        candidate_texts = []
        for i, c in enumerate(candidates):
            candidate_texts.append(
                f"[{i}] (type: {c.metadata.doc_type}) {c.content[:500]}"
            )

        prompt = f"""You are evaluating search results for a user query.

Query: {clean_query}

Candidates:
{chr(10).join(candidate_texts)}

Tasks:
1. Rank candidates by relevance (return indices)
2. Evaluate if top results are SUFFICIENT to answer the query
3. If insufficient, identify what's missing

Evaluation criteria:
- For "how to" questions: Are ALL steps included?
- For concept questions: Is the definition clear?
- For troubleshooting: Is cause AND solution included?

Return JSON:
{{
    "ranked_indices": [3, 1, 5, ...],
    "relevance_scores": [0.95, 0.87, ...],
    "is_sufficient": true/false,
    "missing": ["steps", "conditions", "context"],
    "next_action": "get_section" | "search_again" | null,
    "refined_query": "improved query if search_again",
    "confidence": 0.0 to 1.0,
    "reason": "evaluation reason"
}}"""

        try:
            response = await client.responses.create(
                model=OPENAI_MODEL,
                input=prompt,
                response_format={"type": "json_object"},
                max_output_tokens=500,
            )

            result = json.loads(_extract_response_text(response))

            # 재정렬된 결과 구성
            ranked_results = []
            ranked_indices = result.get("ranked_indices", [])
            relevance_scores = result.get("relevance_scores", [])

            for i, idx in enumerate(ranked_indices[:top_k]):
                if idx < len(candidates):
                    item = candidates[idx]
                    # score 업데이트
                    if i < len(relevance_scores):
                        item = SearchResult(
                            content=item.content,
                            source=item.source,
                            score=relevance_scores[i],
                            metadata=item.metadata,
                        )
                    ranked_results.append(item)

            return RerankResult(
                ranked_results=ranked_results,
                is_sufficient=result.get("is_sufficient", False),
                missing=result.get("missing", []),
                next_action=result.get("next_action"),
                refined_query=result.get("refined_query"),
                confidence=result.get("confidence", 0.5),
            )

        except Exception as e:
            # 실패 시 기본 정렬 (스코어 기준)
            sorted_candidates = sorted(
                candidates, key=lambda x: x.score, reverse=True
            )
            return RerankResult(
                ranked_results=sorted_candidates[:top_k],
                is_sufficient=False,
                missing=["evaluation_failed"],
                next_action=None,
                confidence=0.3,
            )


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
