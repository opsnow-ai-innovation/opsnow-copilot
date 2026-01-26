"""Memory 관련 상수"""

# 단기기억 설정
SHORT_TERM_SIZE = 5

# Long-term Memory 설정
MEMORY_MAX_SENTENCES = 20

# Entities 설정
ENTITIES_MAX_COUNT = 25

# 요약 재시도 횟수
MEMORY_SUMMARIZE_RETRY_COUNT = 2

# TTL (24시간)
MEMORY_TTL_SECONDS = 86400

# Redis 키 패턴 (session 단위)
REDIS_KEY_SHORT = "chat:{session}:short"
REDIS_KEY_MEMORY = "chat:{session}:memory"
REDIS_KEY_ENTITIES = "chat:{session}:entities"
REDIS_KEY_TURN = "chat:{session}:turn"
