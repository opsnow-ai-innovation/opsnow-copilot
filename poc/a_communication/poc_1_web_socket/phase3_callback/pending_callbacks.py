"""
PendingCallbacks - 콜백 요청 관리자

서버가 클라이언트에 데이터를 요청하고 응답을 기다리는 패턴 구현.
One-Time Token (requestId) 기반으로 요청/응답 매칭.

사용 예시:
    callbacks = PendingCallbacks()

    # 1. 콜백 요청 생성
    future = callbacks.create(request_id)

    # 2. 클라이언트에 요청 전송
    await websocket.send_json({"type": "request_api", "requestId": request_id, ...})

    # 3. 응답 대기 (타임아웃 포함)
    try:
        result = await asyncio.wait_for(future, timeout=30.0)
    except asyncio.TimeoutError:
        callbacks.cancel(request_id)
        raise

    # 4. 클라이언트 응답 수신 시 (다른 태스크에서)
    callbacks.resolve(request_id, data)  # -> future가 완료됨
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
    예: 1705123456789-abc123def456ghi7
    """
    timestamp = int(time.time() * 1000)
    random_part = secrets.token_urlsafe(12)  # 16자 URL-safe 문자열
    return f"{timestamp}-{random_part}"


@dataclass
class PendingCallback:
    """개별 콜백 요청 정보"""
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.now)
    timeout: float = 30.0
    callback_type: str = "data"  # "data", "human", "api", "schema", "code"
    metadata: dict = field(default_factory=dict)


class PendingCallbacks:
    """
    콜백 요청 관리자

    서버 → 클라이언트 요청 후 응답 대기를 위한 Future 관리
    """

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

        Args:
            request_id: 요청 ID (없으면 자동 생성)
            callback_type: 콜백 타입 (data, human, api, schema, code)
            timeout: 타임아웃 (초)
            metadata: 추가 메타데이터

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
        """
        콜백 완료 (성공)

        클라이언트로부터 응답 수신 시 호출.
        Future를 완료 상태로 만들고 대기 중인 코드가 진행됨.

        Args:
            request_id: 요청 ID
            data: 응답 데이터

        Returns:
            성공 여부 (해당 request_id가 존재했는지)
        """
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.set_result(data)

        return True

    def reject(self, request_id: str, error: Exception) -> bool:
        """
        콜백 실패

        클라이언트 에러 응답 시 호출.

        Args:
            request_id: 요청 ID
            error: 에러 객체

        Returns:
            성공 여부
        """
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.set_exception(error)

        return True

    def cancel(self, request_id: str) -> bool:
        """
        콜백 취소

        타임아웃이나 연결 종료 시 호출.

        Args:
            request_id: 요청 ID

        Returns:
            성공 여부
        """
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
        """
        모든 콜백 취소

        연결 종료 시 호출.

        Returns:
            취소된 콜백 수
        """
        count = 0
        for request_id in list(self._pending.keys()):
            if self.cancel(request_id):
                count += 1
        return count


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


# 테스트용
if __name__ == "__main__":
    async def test():
        callbacks = PendingCallbacks()

        # 1. 콜백 생성
        request_id, future = callbacks.create(callback_type="api")
        print(f"Created: {request_id}")
        print(f"Pending: {callbacks.get_pending_count()}")

        # 2. 다른 태스크에서 resolve (시뮬레이션)
        async def simulate_response():
            await asyncio.sleep(0.5)
            callbacks.resolve(request_id, {"success": True, "data": "test"})

        asyncio.create_task(simulate_response())

        # 3. 응답 대기
        try:
            result = await asyncio.wait_for(future, timeout=5.0)
            print(f"Result: {result}")
        except asyncio.TimeoutError:
            print("Timeout!")
            callbacks.cancel(request_id)

        print(f"Pending after: {callbacks.get_pending_count()}")

    asyncio.run(test())
