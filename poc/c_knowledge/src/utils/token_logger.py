"""
LLM API 토큰 사용량 및 호출 시간 로깅

TODO: 프로덕션 배포 전 삭제 예정 - 개발/디버깅용
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def log_token_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    duration_ms: float,
    caller: str = "",
) -> None:
    """토큰 사용량 로깅 (DEBUG 레벨)

    TODO: 프로덕션 배포 전 삭제 예정

    Args:
        model: 모델명
        prompt_tokens: 입력 토큰 수
        completion_tokens: 출력 토큰 수
        total_tokens: 총 토큰 수
        duration_ms: API 호출 시간 (밀리초)
        caller: 호출자 정보 (함수명 등)
    """
    timestamp = datetime.now().isoformat()
    log_msg = (
        f"[TOKEN] {timestamp} | "
        f"caller={caller} | "
        f"model={model} | "
        f"prompt={prompt_tokens} | "
        f"completion={completion_tokens} | "
        f"total={total_tokens} | "
        f"duration={duration_ms:.0f}ms"
    )
    logger.debug(log_msg)


def extract_usage_from_response(response: Any) -> dict:
    """OpenAI/pydantic-ai 응답에서 토큰 사용량 추출

    TODO: 프로덕션 배포 전 삭제 예정

    Args:
        response: OpenAI API 응답 또는 pydantic-ai RunResult

    Returns:
        {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    """
    # pydantic-ai RunResult: result.usage() 메서드
    if hasattr(response, "usage") and callable(getattr(response, "usage")):
        try:
            usage = response.usage()
            return {
                "prompt_tokens": getattr(usage, "request_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "response_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            }
        except Exception:
            pass

    # OpenAI response.usage 속성
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


class TokenTimer:
    """
    API 호출 시간 측정 컨텍스트 매니저

    TODO: 프로덕션 배포 전 삭제 예정
    """

    def __init__(self):
        self.start_time = 0.0
        self.end_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()

    @property
    def duration_ms(self) -> float:
        """밀리초 단위 소요 시간"""
        return (self.end_time - self.start_time) * 1000