"""rate_limiter.py 단위 테스트"""

import time
import pytest
from rate_limiter import RateLimiter


class TestRateLimiterBasic:
    """RateLimiter 기본 테스트"""

    def test_allow_within_limit(self):
        """한도 내 요청 허용"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for i in range(5):
            allowed, info = limiter.is_allowed("user", "conn")
            assert allowed is True
            assert info["remaining"] == 4 - i

    def test_block_over_limit(self):
        """한도 초과 요청 차단"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # 3회 요청
        for _ in range(3):
            limiter.is_allowed("user", "conn")

        # 4번째 요청 차단
        allowed, info = limiter.is_allowed("user", "conn")
        assert allowed is False
        assert info["remaining"] == 0
        assert "retry_after" in info

    def test_get_status(self):
        """현재 상태 조회"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        # 3회 요청
        for _ in range(3):
            limiter.is_allowed("user", "conn")

        status = limiter.get_status("user", "conn")
        assert status["limit"] == 10
        assert status["used"] == 3
        assert status["remaining"] == 7


class TestShareLimitMode:
    """Rate Limit 공유 모드 테스트"""

    def test_share_limit_true(self):
        """사용자 기준 공유 (share_limit=True)"""
        limiter = RateLimiter(max_requests=5, window_seconds=60, share_limit=True)

        # conn-1에서 3회
        for _ in range(3):
            limiter.is_allowed("user", "conn-1")

        # conn-2에서 상태 확인 - 공유되어야 함
        status = limiter.get_status("user", "conn-2")
        assert status["used"] == 3
        assert status["remaining"] == 2
        assert status["limitKey"] == "user"

    def test_share_limit_false(self):
        """연결 기준 별도 (share_limit=False)"""
        limiter = RateLimiter(max_requests=5, window_seconds=60, share_limit=False)

        # conn-1에서 3회
        for _ in range(3):
            limiter.is_allowed("user", "conn-1")

        # conn-2에서 상태 확인 - 별도여야 함
        status = limiter.get_status("user", "conn-2")
        assert status["used"] == 0
        assert status["remaining"] == 5
        assert status["limitKey"] == "connection"

    def test_share_limit_property(self):
        """share_limit 속성"""
        limiter1 = RateLimiter(share_limit=True)
        limiter2 = RateLimiter(share_limit=False)

        assert limiter1.share_limit is True
        assert limiter2.share_limit is False


class TestReset:
    """Reset 테스트"""

    def test_reset_user(self):
        """사용자 Rate Limit 초기화"""
        limiter = RateLimiter(max_requests=5, window_seconds=60, share_limit=True)

        # 5회 요청으로 한도 소진
        for _ in range(5):
            limiter.is_allowed("user", "conn")

        status = limiter.get_status("user", "conn")
        assert status["remaining"] == 0

        # 초기화
        limiter.reset("user", "conn")

        status = limiter.get_status("user", "conn")
        assert status["remaining"] == 5

    def test_reset_all(self):
        """전체 Rate Limit 초기화"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        limiter.is_allowed("user1", "conn1")
        limiter.is_allowed("user2", "conn2")

        limiter.reset_all()

        assert limiter.get_status("user1", "conn1")["used"] == 0
        assert limiter.get_status("user2", "conn2")["used"] == 0


class TestSlidingWindow:
    """Sliding Window 테스트"""

    def test_window_expiry(self):
        """윈도우 만료 후 요청 허용"""
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)  # 0.1초 윈도우

        # 2회 요청으로 한도 소진
        limiter.is_allowed("user", "conn")
        limiter.is_allowed("user", "conn")

        allowed, _ = limiter.is_allowed("user", "conn")
        assert allowed is False

        # 윈도우 만료 대기
        time.sleep(0.15)

        # 다시 허용
        allowed, info = limiter.is_allowed("user", "conn")
        assert allowed is True


class TestMultipleUsers:
    """다중 사용자 테스트"""

    def test_independent_limits(self):
        """사용자별 독립적 한도"""
        limiter = RateLimiter(max_requests=3, window_seconds=60, share_limit=True)

        # user1: 3회 소진
        for _ in range(3):
            limiter.is_allowed("user1", "conn1")

        # user1 차단
        allowed, _ = limiter.is_allowed("user1", "conn1")
        assert allowed is False

        # user2는 여전히 허용
        allowed, _ = limiter.is_allowed("user2", "conn2")
        assert allowed is True


class TestRetryAfter:
    """retry_after 테스트"""

    def test_retry_after_calculated(self):
        """retry_after 계산"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        limiter.is_allowed("user", "conn")
        allowed, info = limiter.is_allowed("user", "conn")

        assert allowed is False
        assert "retry_after" in info
        assert 0 < info["retry_after"] <= 61  # 약 60초 이내
