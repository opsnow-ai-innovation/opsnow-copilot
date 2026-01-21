"""
RateLimiter - 요청 제한

기능:
- 사용자/연결 기준 Rate Limit
- Sliding Window 방식
"""

import time
from collections import defaultdict


class RateLimiter:
    """Rate Limiter (사용자 기준 또는 연결 기준)"""

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        share_limit: bool = True
    ):
        """
        Args:
            max_requests: 윈도우 내 최대 요청 수
            window_seconds: 시간 윈도우 (초)
            share_limit: True면 사용자 기준, False면 연결 기준
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._share_limit = share_limit
        self._requests: dict[str, list[float]] = defaultdict(list)

    @property
    def share_limit(self) -> bool:
        return self._share_limit

    def _get_key(self, username: str, connection_id: str) -> str:
        """Rate Limit 키 결정"""
        if self._share_limit:
            return username
        else:
            return connection_id

    def is_allowed(self, username: str, connection_id: str) -> tuple[bool, dict]:
        """
        요청 허용 여부 확인

        Returns:
            (allowed, info)
        """
        key = self._get_key(username, connection_id)
        now = time.time()
        window_start = now - self.window_seconds

        # 윈도우 밖의 오래된 요청 제거
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        current_count = len(self._requests[key])
        remaining = max(0, self.max_requests - current_count)

        info = {
            "limit": self.max_requests,
            "remaining": remaining,
            "reset": int(window_start + self.window_seconds),
            "window": self.window_seconds,
            "limitKey": "user" if self._share_limit else "connection"
        }

        if current_count >= self.max_requests:
            if self._requests[key]:
                oldest = min(self._requests[key])
                info["retry_after"] = int(oldest + self.window_seconds - now) + 1
            return False, info

        # 요청 기록
        self._requests[key].append(now)
        info["remaining"] = remaining - 1

        return True, info

    def get_status(self, username: str, connection_id: str) -> dict:
        """현재 Rate Limit 상태 조회"""
        key = self._get_key(username, connection_id)
        now = time.time()
        window_start = now - self.window_seconds

        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        current_count = len(self._requests[key])
        return {
            "limit": self.max_requests,
            "used": current_count,
            "remaining": max(0, self.max_requests - current_count),
            "window": self.window_seconds,
            "limitKey": "user" if self._share_limit else "connection"
        }

    def reset(self, username: str, connection_id: str = ""):
        """Rate Limit 초기화"""
        key = self._get_key(username, connection_id)
        self._requests[key] = []

    def reset_all(self):
        """모든 Rate Limit 초기화"""
        self._requests.clear()
