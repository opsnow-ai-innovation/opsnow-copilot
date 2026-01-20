"""배치 처리 관련 상수 (문서 임베딩, 청킹, 크롤링)"""

# 임베딩 차원
EMBEDDING_DIMENSION = 1536

# 토큰 제한
MAX_EMBEDDING_TOKEN_LIMIT = 8191

# 문장 단위 청킹
CHUNK_MAX_CHAR_SIZE = 40
CHUNK_OVERLAP_SIZE = 10

# 단어 단위 청킹
CHUNK_WORD_SIZE = 150
CHUNK_WORD_OVERLAP = 50

# 크롤링 설정
RETRY_COUNT = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"