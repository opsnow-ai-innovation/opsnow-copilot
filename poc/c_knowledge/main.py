"""OpsNow Copilot - Knowledge PoC FastAPI 진입점"""

import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import (
    REDIS_SOCKET_CONNECT_TIMEOUT,
    REDIS_SOCKET_TIMEOUT,
    REDIS_URL,
)
from src.utils.logger import Logger

Logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 관리"""
    # Startup
    logger.info("Redis 연결 시도: %s", REDIS_URL)
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)

    # 연결 검증
    try:
        await app.state.redis.ping()
        logger.info("Redis 연결 성공")
    except Exception as e:
        logger.error("Redis 연결 실패: %s", e)
        raise RuntimeError(f"Redis 연결 실패: {e}") from e

    yield

    # Shutdown
    logger.info("Redis 연결 종료")
    await app.state.redis.aclose()


app = FastAPI(
    title="OpsNow Copilot - Knowledge PoC",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {"status": "ok"}


@app.get("/health/redis")
async def redis_health_check():
    """Redis 연결 상태 확인"""
    try:
        await app.state.redis.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return {"status": "error", "redis": str(e)}


# 라우터 등록
from src.routes.rag import router as rag_router
from src.routes.chat import router as chat_router  # TODO: 삭제 예정

app.include_router(rag_router)
app.include_router(chat_router)  # TODO: 삭제 예정

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
