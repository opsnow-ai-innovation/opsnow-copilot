"""모델 모듈 - 기능별 분리"""

# RAG 관련
from src.models.rag import (
    ChunkMetadata,
    ContextResult,
    PageInfo,
    ParsedDomContext,
    RAGResult,
    RerankResult,
    SearchResult,
)

# Memory 관련
from src.models.memory import (
    Entities,
    IntegratedContext,
    MemoryContext,
    MemoryState,
    SummarizerResult,
    Turn,
)

# WebSocket 관련
from src.models.websocket import QueryMessage

# Forward reference 해결
IntegratedContext.model_rebuild()

__all__ = [
    # RAG
    "ChunkMetadata",
    "SearchResult",
    "RerankResult",
    "RAGResult",
    "ContextResult",
    "ParsedDomContext",
    "PageInfo",
    # Memory
    "Turn",
    "MemoryState",
    "Entities",
    "MemoryContext",
    "SummarizerResult",
    "IntegratedContext",
    # WebSocket
    "QueryMessage",
]