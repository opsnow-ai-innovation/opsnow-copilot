"""
Health API

헬스체크 엔드포인트
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """헬스체크 응답"""

    status: str = "ok"
    service: str = "c_knowledge"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """헬스체크"""
    return HealthResponse()


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """루트 엔드포인트"""
    return HealthResponse()
