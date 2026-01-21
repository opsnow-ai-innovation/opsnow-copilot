"""callbacks.py 단위 테스트"""

import asyncio
import pytest
from callbacks import (
    PendingCallbacks,
    generate_request_id,
    CallbackTimeoutError,
    CallbackError
)


class TestGenerateRequestId:
    """generate_request_id 테스트"""

    def test_generate_unique_ids(self):
        """고유한 ID 생성"""
        ids = [generate_request_id() for _ in range(100)]
        assert len(set(ids)) == 100  # 모두 고유

    def test_id_format(self):
        """ID 형식 확인"""
        request_id = generate_request_id()
        parts = request_id.split("-")
        assert len(parts) >= 2
        # 첫 부분은 타임스탬프 (숫자)
        assert parts[0].isdigit()


class TestPendingCallbacks:
    """PendingCallbacks 테스트"""

    def test_create_callback(self):
        """콜백 생성"""
        callbacks = PendingCallbacks()
        request_id, future = callbacks.create()

        assert request_id is not None
        assert future is not None
        assert callbacks.get_pending_count() == 1
        assert callbacks.is_pending(request_id)

    def test_create_with_custom_id(self):
        """커스텀 ID로 콜백 생성"""
        callbacks = PendingCallbacks()
        request_id, future = callbacks.create(request_id="custom-id-123")

        assert request_id == "custom-id-123"
        assert callbacks.is_pending("custom-id-123")

    def test_create_duplicate_id_raises(self):
        """중복 ID 생성 시 에러"""
        callbacks = PendingCallbacks()
        callbacks.create(request_id="dup-id")

        with pytest.raises(ValueError, match="Duplicate"):
            callbacks.create(request_id="dup-id")

    @pytest.mark.asyncio
    async def test_resolve_callback(self):
        """콜백 resolve"""
        callbacks = PendingCallbacks()
        request_id, future = callbacks.create()

        # resolve
        result = callbacks.resolve(request_id, {"data": "test"})
        assert result is True
        assert callbacks.get_pending_count() == 0

        # future 결과 확인
        data = await future
        assert data == {"data": "test"}

    def test_resolve_nonexistent(self):
        """존재하지 않는 콜백 resolve"""
        callbacks = PendingCallbacks()
        result = callbacks.resolve("nonexistent-id", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_reject_callback(self):
        """콜백 reject"""
        callbacks = PendingCallbacks()
        request_id, future = callbacks.create()

        # reject
        error = CallbackError(request_id, "TEST_ERROR", "Test error message")
        result = callbacks.reject(request_id, error)
        assert result is True

        # future 에러 확인
        with pytest.raises(CallbackError):
            await future

    def test_cancel_callback(self):
        """콜백 취소"""
        callbacks = PendingCallbacks()
        request_id, future = callbacks.create()

        result = callbacks.cancel(request_id)
        assert result is True
        assert callbacks.get_pending_count() == 0
        assert future.cancelled()

    def test_cancel_all(self):
        """모든 콜백 취소"""
        callbacks = PendingCallbacks()
        for _ in range(5):
            callbacks.create()

        assert callbacks.get_pending_count() == 5

        count = callbacks.cancel_all()
        assert count == 5
        assert callbacks.get_pending_count() == 0

    def test_get_pending_ids(self):
        """대기 중인 ID 목록"""
        callbacks = PendingCallbacks()
        callbacks.create(request_id="id-1")
        callbacks.create(request_id="id-2")
        callbacks.create(request_id="id-3")

        ids = callbacks.get_pending_ids()
        assert "id-1" in ids
        assert "id-2" in ids
        assert "id-3" in ids

    def test_get_callback_info(self):
        """콜백 정보 조회"""
        callbacks = PendingCallbacks()
        request_id, _ = callbacks.create(
            callback_type="api",
            metadata={"endpoint": "/api/test"}
        )

        info = callbacks.get_callback_info(request_id)
        assert info is not None
        assert info["callback_type"] == "api"
        assert info["metadata"]["endpoint"] == "/api/test"

    def test_get_callback_info_nonexistent(self):
        """존재하지 않는 콜백 정보 조회"""
        callbacks = PendingCallbacks()
        info = callbacks.get_callback_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_timeout_scenario(self):
        """타임아웃 시나리오"""
        callbacks = PendingCallbacks(default_timeout=0.1)
        request_id, future = callbacks.create()

        # 타임아웃 대기
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(future, timeout=0.1)

        # 취소
        callbacks.cancel(request_id)
        assert callbacks.get_pending_count() == 0


class TestCallbackErrors:
    """콜백 에러 클래스 테스트"""

    def test_callback_timeout_error(self):
        """CallbackTimeoutError"""
        error = CallbackTimeoutError("req-123", 30.0)
        assert error.request_id == "req-123"
        assert error.timeout == 30.0
        assert "req-123" in str(error)

    def test_callback_error(self):
        """CallbackError"""
        error = CallbackError("req-456", "API_ERROR", "API 호출 실패")
        assert error.request_id == "req-456"
        assert error.code == "API_ERROR"
        assert error.message == "API 호출 실패"
        assert "API_ERROR" in str(error)
