"""
PendingCallbacks - 콜백 요청 관리자

서버가 클라이언트에 데이터를 요청하고 응답을 기다리는 패턴 구현.
One-Time Token (requestId) 기반으로 요청/응답 매칭.
"""

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def generate_request_id() -> str:
    """
    One-Time Token 생성

    형식: {timestamp_ms}-{random_16chars}
    """
    timestamp = int(time.time() * 1000)
    random_part = secrets.token_urlsafe(12)
    return f"{timestamp}-{random_part}"


@dataclass
class PendingCallback:
    """개별 콜백 요청 정보"""
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.now)
    timeout: float = 30.0
    callback_type: str = "data"
    metadata: dict = field(default_factory=dict)


class PendingCallbacks:
    """콜백 요청 관리자"""

    def __init__(self, default_timeout: float = 30.0):
        self._pending: dict[str, PendingCallback] = {}
        self._default_timeout = default_timeout

    def create(
        self,
        request_id: str = None,
        callback_type: str = "data",
        timeout: float = None,
        metadata: dict = None
    ) -> tuple[str, asyncio.Future]:
        """
        새 콜백 Future 생성

        Returns:
            (request_id, future) 튜플
        """
        if request_id is None:
            request_id = generate_request_id()

        if request_id in self._pending:
            raise ValueError(f"Duplicate request_id: {request_id}")

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        self._pending[request_id] = PendingCallback(
            future=future,
            timeout=timeout or self._default_timeout,
            callback_type=callback_type,
            metadata=metadata or {}
        )

        return request_id, future

    def resolve(self, request_id: str, data: Any) -> bool:
        """콜백 완료 (성공)"""
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.set_result(data)

        return True

    def reject(self, request_id: str, error: Exception) -> bool:
        """콜백 실패"""
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.set_exception(error)

        return True

    def cancel(self, request_id: str) -> bool:
        """콜백 취소"""
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.cancel()

        return True

    def get_pending_count(self) -> int:
        """대기 중인 콜백 수"""
        return len(self._pending)

    def get_pending_ids(self) -> list[str]:
        """대기 중인 콜백 ID 목록"""
        return list(self._pending.keys())

    def cancel_all(self) -> int:
        """모든 콜백 취소"""
        count = 0
        for request_id in list(self._pending.keys()):
            if self.cancel(request_id):
                count += 1
        return count

    def is_pending(self, request_id: str) -> bool:
        """해당 request_id가 대기 중인지 확인"""
        return request_id in self._pending

    def get_callback_info(self, request_id: str) -> Optional[dict]:
        """콜백 정보 조회"""
        if request_id not in self._pending:
            return None
        cb = self._pending[request_id]
        return {
            "request_id": request_id,
            "callback_type": cb.callback_type,
            "created_at": cb.created_at.isoformat(),
            "timeout": cb.timeout,
            "metadata": cb.metadata
        }


class CallbackTimeoutError(Exception):
    """콜백 타임아웃 에러"""
    def __init__(self, request_id: str, timeout: float):
        self.request_id = request_id
        self.timeout = timeout
        super().__init__(f"Callback timeout: {request_id} ({timeout}s)")


class CallbackError(Exception):
    """콜백 에러"""
    def __init__(self, request_id: str, code: str, message: str):
        self.request_id = request_id
        self.code = code
        self.message = message
        super().__init__(f"Callback error [{code}]: {message}")