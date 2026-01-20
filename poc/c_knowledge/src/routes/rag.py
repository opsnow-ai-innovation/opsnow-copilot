"""
RAG API

Context 조회 API - memory, faq, menu 통합 응답
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from src.config import REDIS_URL
from src.processors.memory_summarizer_processor import MemorySummarizer
from src.processors.memory_store_processor import RedisMemoryStore
from src.processors.context_builder_processor import build_memory_response
from src.processors.rag_agent_processor import RAGPipeline
from src.rag_assistant.rag.search import FAISSSearch

router = APIRouter(prefix="/rag", tags=["RAG"])


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────
class ContextRequest(BaseModel):
    """Context 조회 요청"""

    query: str = Field(..., description="사용자 질의")
    session: str = Field(..., description="세션 ID")
    user_id: str = Field(default="", description="유저 ID (Fallback 메뉴용)")


class MenuInfo(BaseModel):
    """메뉴 정보"""

    rank: int
    name: str
    path: str
    url: str


class ContextResponse(BaseModel):
    """
    Context API 응답 (디자인 문서 Section 13)

    memory, faq, menu 중 있는 것만 배열로 반환
    """

    memory: list[str] = Field(default_factory=list, description="대화 메모리")
    faq: list[str] = Field(default_factory=list, description="FAQ/가이드 검색 결과")
    menu: list[MenuInfo] = Field(default_factory=list, description="관련 메뉴 링크")


class RetrieveRequest(BaseModel):
    """RAG 검색 요청 (정렬된 결과만 반환)"""

    query: str = Field(..., description="사용자 질의")
    session: str = Field(..., description="세션 ID")
    user_id: str = Field(default="", description="유저 ID (Fallback 메뉴용)")
    dom_context: str = Field(default="", description="화면 domContext (JSON string)")


class RankedResult(BaseModel):
    """정렬된 검색 결과"""

    content: str
    source: str
    score: float
    doc_type: str


class RetrieveResponse(BaseModel):
    """정렬된 RAG 결과 응답"""

    ranked_results: list[RankedResult] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    answer: str = Field(default="", description="Agent 생성 답변")
    confidence: float = Field(default=0.0)
    is_sufficient: bool = Field(default=False)


# ─────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────
_redis_client: Redis | None = None
_memory_store: RedisMemoryStore | None = None
_search: FAISSSearch | None = None
_pipeline: RAGPipeline | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def get_memory_store() -> RedisMemoryStore:
    global _memory_store
    if _memory_store is None:
        redis = await get_redis()
        summarizer = MemorySummarizer()
        _memory_store = RedisMemoryStore(redis, summarizer=summarizer)
    return _memory_store


async def get_search() -> FAISSSearch:
    global _search
    if _search is None:
        _search = FAISSSearch()
    return _search


async def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        memory_store = await get_memory_store()
        search = await get_search()
        _pipeline = RAGPipeline(memory_store=memory_store, search=search)
    return _pipeline


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/context", response_model=ContextResponse)
async def get_context(
    request: ContextRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> ContextResponse:
    """
    Context 조회 API

    memory + faq + menu 통합 응답 반환
    - memory: 대화 히스토리 기반 메모리
    - faq: RAG 검색 결과
    - menu: Fallback 메뉴 링크
    """
    # RAG 파이프라인 실행
    rag_result = await pipeline.retrieve(
        query=request.query,
        session=request.session,
        user_id=request.user_id,
    )

    # Memory 응답 구성
    memory_response = build_memory_response(rag_result.memory)

    # FAQ 응답 구성 (검색 결과에서 content 추출)
    faq_response = [
        f"Q: {r.content}" for r in rag_result.ranked_results if r.metadata.doc_type == "faq"
    ]

    # Menu 응답 구성 (Fallback용, 현재는 빈 배열)
    # TODO: menu_service 연동 필요
    menu_response: list[MenuInfo] = []

    return ContextResponse(
        memory=memory_response,
        faq=faq_response,
        menu=menu_response,
    )


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_rag_results(
    request: RetrieveRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> RetrieveResponse:
    """
    RAG 검색 + 정렬 결과만 반환

    - 응답 생성은 클라이언트(예: Chat CLI)에서 처리
    """
    rag_result = await pipeline.retrieve(
        query=request.query,
        session=request.session,
        user_id=request.user_id,
        dom_context_raw=request.dom_context,
    )

    return RetrieveResponse(
        ranked_results=[
            RankedResult(
                content=r.content,
                source=r.source,
                score=r.score,
                doc_type=r.metadata.doc_type,
            )
            for r in rag_result.ranked_results
        ],
        sources=rag_result.sources,
        answer=rag_result.answer,
        confidence=rag_result.confidence,
        is_sufficient=rag_result.is_sufficient,
    )


# ─────────────────────────────────────────────────────────────
# Debug Endpoints (TODO: PoC 이후 삭제 예정)
# ─────────────────────────────────────────────────────────────
class MemoryRequest(BaseModel):
    """메모리 조회 요청"""

    session: str = Field(..., description="세션 ID")


class MemoryResponse(BaseModel):
    """메모리 조회 응답"""

    short_term: list[dict] = Field(default_factory=list, description="단기기억 (최근 5턴)")
    long_term: str = Field(default="", description="Long-term Memory")
    entities: dict[str, str] = Field(default_factory=dict, description="Entities")


class SearchRequest(BaseModel):
    """검색 요청"""

    query: str = Field(..., description="검색 쿼리")
    doc_type: str = Field(default="all", description="문서 타입 (faq, guide, all)")
    top_k: int = Field(default=5, description="검색 결과 수")


class SearchResult(BaseModel):
    """검색 결과"""

    content: str
    source: str
    score: float
    doc_type: str


class SearchResponse(BaseModel):
    """검색 응답"""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    count: int = 0


@router.post("/debug/memory", response_model=MemoryResponse)
async def debug_get_memory(
    request: MemoryRequest,
    store: RedisMemoryStore = Depends(get_memory_store),
) -> MemoryResponse:
    """
    [DEBUG] 메모리만 조회 (TODO: PoC 이후 삭제 예정)

    - short_term: 최근 5턴 원본
    - long_term: 요약된 Long-term Memory
    - entities: 추출된 엔티티
    """
    context = await store.get_context(request.session)

    return MemoryResponse(
        short_term=[
            {"turn": t.turn, "user": t.user, "assistant": t.assistant}
            for t in context.short_term
        ],
        long_term=context.memory,
        entities=context.entities,
    )


@router.post("/debug/search", response_model=SearchResponse)
async def debug_search(
    request: SearchRequest,
    search: FAISSSearch = Depends(get_search),
) -> SearchResponse:
    """
    [DEBUG] FAQ/Guide 검색만 (TODO: PoC 이후 삭제 예정)

    - doc_type: faq, guide, all
    - top_k: 검색 결과 수
    """
    results = await search.search(
        query=request.query,
        top_k=request.top_k,
    )

    # doc_type 필터링
    if request.doc_type != "all":
        results = [r for r in results if r.metadata.doc_type == request.doc_type]

    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                content=r.content,
                source=r.source,
                score=r.score,
                doc_type=r.metadata.doc_type,
            )
            for r in results
        ],
        count=len(results),
    )
