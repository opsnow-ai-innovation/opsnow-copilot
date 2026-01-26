"""상수 모듈 - 기능별 분리"""

# ============================================
# 1. 배치 처리 (문서 임베딩, 청킹, 크롤링)
# ============================================
from src.constants.batch import (
    CHUNK_MAX_CHAR_SIZE,
    CHUNK_OVERLAP_SIZE,
    CHUNK_WORD_OVERLAP,
    CHUNK_WORD_SIZE,
    EMBEDDING_DIMENSION,
    MAX_EMBEDDING_TOKEN_LIMIT,
    RETRY_COUNT,
    USER_AGENT,
)

# ============================================
# 2. 히스토리 RAG (대화 메모리)
# ============================================
from src.constants.memory import (
    ENTITIES_MAX_COUNT,
    MEMORY_MAX_SENTENCES,
    MEMORY_SUMMARIZE_RETRY_COUNT,
    MEMORY_TTL_SECONDS,
    REDIS_KEY_ENTITIES,
    REDIS_KEY_MEMORY,
    REDIS_KEY_SHORT,
    SHORT_TERM_SIZE,
)

# ============================================
# 3. 가이드 FAQ/MENU RAG (문서 검색)
# ============================================
from src.constants.rag import (
    FAQ_SEARCH_K,
    GUIDE_SEARCH_K,
    MAX_TOOL_CALLS,
    RERANK_TOP_K,
)

# ============================================
# 공통: 파일 경로
# ============================================
from src.constants.paths import (
    BASE_PATH,
    EMBEDDED_VECTOR_PATH,
    FAQ_DATA_PATH,
    MENU_DATA_PATH,
)

__all__ = [
    # 배치 처리
    "EMBEDDING_DIMENSION",
    "MAX_EMBEDDING_TOKEN_LIMIT",
    "CHUNK_MAX_CHAR_SIZE",
    "CHUNK_OVERLAP_SIZE",
    "CHUNK_WORD_SIZE",
    "CHUNK_WORD_OVERLAP",
    "RETRY_COUNT",
    "USER_AGENT",
    # 히스토리 RAG
    "SHORT_TERM_SIZE",
    "MEMORY_MAX_SENTENCES",
    "ENTITIES_MAX_COUNT",
    "MEMORY_SUMMARIZE_RETRY_COUNT",
    "MEMORY_TTL_SECONDS",
    "REDIS_KEY_SHORT",
    "REDIS_KEY_MEMORY",
    "REDIS_KEY_ENTITIES",
    # 가이드 FAQ/MENU RAG
    "FAQ_SEARCH_K",
    "GUIDE_SEARCH_K",
    "RERANK_TOP_K",
    "MAX_TOOL_CALLS",
    # 공통: 파일 경로
    "BASE_PATH",
    "FAQ_DATA_PATH",
    "MENU_DATA_PATH",
    "EMBEDDED_VECTOR_PATH",
]
