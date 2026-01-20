"""RAG 관련 Pydantic 모델"""

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Chunk 메타데이터"""

    doc_id: str
    doc_type: str = Field(description="faq | guide")
    guide_type: str | None = Field(
        default=None,
        description="user | developer | tech_blog (guide일 때만)",
    )
    section_path: str = ""
    has_steps: bool = False
    parent_doc_id: str | None = None


class SearchResult(BaseModel):
    """검색 결과 아이템"""

    content: str
    source: str
    score: float
    metadata: ChunkMetadata


class RerankResult(BaseModel):
    """Rerank + 충분성 평가 통합 결과"""

    ranked_results: list[SearchResult]
    is_sufficient: bool
    missing: list[str] = Field(
        default_factory=list,
        description="steps | conditions | context",
    )
    next_action: str | None = Field(
        default=None,
        description="get_section | search_again | None",
    )
    refined_query: str | None = Field(
        default=None,
        description="충분하지 않을 때 재검색용 개선된 쿼리",
    )
    confidence: float = Field(ge=0.0, le=1.0)


class RAGResult(BaseModel):
    """최종 RAG 응답"""

    answer: str
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ContextResult(BaseModel):
    """통합 컨텍스트 검색 결과"""

    memory: list[str] = Field(
        default_factory=list,
        description="관련 대화 히스토리",
    )
    faq: list[str] = Field(
        default_factory=list,
        description="관련 FAQ/Manual",
    )
    menu: list[dict] = Field(
        default_factory=list,
        description="관련 메뉴 정보 (랭킹순)",
    )


class ParsedDomContext(BaseModel):
    """Agent가 받을 표준 포맷 (내부 구조는 유연)"""

    raw: str  # 원본 JSON string
    summary: str  # 사람이 읽을 수 있는 요약 (LLM용)
    structured: dict = Field(default_factory=dict)  # 파싱된 구조 (있으면)
    screen_type: str | None = None  # 알 수 있으면
    has_data: bool = True  # 데이터가 있는지 없는지


class PageInfo(BaseModel):
    """페이지 정보 (WebSocket에서 전달)"""

    url: str
    title: str
    vendor: str | None = None
