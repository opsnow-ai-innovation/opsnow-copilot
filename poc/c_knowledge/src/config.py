"""환경변수 기반 설정"""

import logging
import os

from dotenv import load_dotenv

from src.constants.paths import BASE_PATH

# .env.local 파일이 있으면 로드 (로컬 개발용, git에 커밋 안됨)
# 배포 환경에서는 이 파일이 없으므로 환경변수 또는 기본값 사용
# override=True로 설정하여 .env.local 값이 우선 적용되도록 함
load_dotenv(os.path.join(BASE_PATH, ".env.local"), override=True)

# ─────────────────────────────────────────────────────────────
# 환경 설정
# ─────────────────────────────────────────────────────────────
IS_LOCAL_DEV = os.environ.get("LOCAL_DEV", "false").lower() == "true"

# ─────────────────────────────────────────────────────────────
# 로깅
# ─────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOGGING_LEVEL = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

# ─────────────────────────────────────────────────────────────
# LLM 모델
# ─────────────────────────────────────────────────────────────
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-nano")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

# ─────────────────────────────────────────────────────────────
# 외부 서비스 연결
# ─────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# Redis 타임아웃 (초)
REDIS_SOCKET_CONNECT_TIMEOUT = int(os.environ.get("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))
REDIS_SOCKET_TIMEOUT = int(os.environ.get("REDIS_SOCKET_TIMEOUT", "5"))

# ─────────────────────────────────────────────────────────────
# 파일 경로 (환경별로 다를 수 있음)
# ─────────────────────────────────────────────────────────────
EMBEDDED_VECTOR_PATH = os.environ.get(
    "EMBEDDED_VECTOR_PATH",
    os.path.join(BASE_PATH, "src", "data", "output", EMBEDDING_MODEL, "embedded_vector.pkl"),
)
