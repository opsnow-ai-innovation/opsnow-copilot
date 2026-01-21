"""auth.py 단위 테스트"""

import time
import pytest
from auth import (
    generate_token,
    validate_token,
    get_user_info,
    is_token_expiring_soon,
    JWT_EXPIRY_SECONDS
)


class TestGenerateToken:
    """generate_token 테스트"""

    def test_generate_token_default(self):
        """기본 토큰 생성"""
        token = generate_token()
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_with_custom_user(self, sample_user):
        """커스텀 사용자 정보로 토큰 생성"""
        token = generate_token(
            username=sample_user["username"],
            name=sample_user["name"]
        )
        assert token is not None

        # 검증
        payload, error, status = validate_token(token)
        assert error is None
        assert payload["preferred_username"] == sample_user["username"]
        assert payload["name"] == sample_user["name"]

    def test_generate_token_with_custom_expiry(self):
        """커스텀 만료 시간"""
        token = generate_token(expires_in=60)  # 60초
        payload, error, _ = validate_token(token)
        assert error is None
        assert payload["exp"] - payload["iat"] == 60


class TestValidateToken:
    """validate_token 테스트"""

    def test_validate_valid_token(self):
        """유효한 토큰 검증"""
        token = generate_token()
        payload, error, status = validate_token(token)

        assert error is None
        assert status == 200
        assert payload is not None
        assert "sub" in payload
        assert "exp" in payload

    def test_validate_empty_token(self):
        """빈 토큰"""
        payload, error, status = validate_token("")
        assert payload is None
        assert error == "토큰이 없습니다"
        assert status == 401

    def test_validate_none_token(self):
        """None 토큰"""
        payload, error, status = validate_token(None)
        assert payload is None
        assert error == "토큰이 없습니다"

    def test_validate_invalid_token(self):
        """유효하지 않은 토큰"""
        payload, error, status = validate_token("invalid.token.here")
        assert payload is None
        assert status == 401

    def test_validate_expired_token(self):
        """만료된 토큰"""
        token = generate_token(expires_in=-1)  # 이미 만료됨
        payload, error, status = validate_token(token)

        assert payload is None
        assert "만료" in error
        assert status == 401

    def test_validate_bearer_prefix(self):
        """Bearer 접두사 처리"""
        token = generate_token()
        bearer_token = f"Bearer {token}"

        payload, error, status = validate_token(bearer_token)
        assert error is None
        assert payload is not None


class TestGetUserInfo:
    """get_user_info 테스트"""

    def test_get_user_info(self, sample_user):
        """사용자 정보 추출"""
        token = generate_token(
            username=sample_user["username"],
            name=sample_user["name"]
        )
        payload, _, _ = validate_token(token)
        user_info = get_user_info(payload)

        assert user_info["username"] == sample_user["username"]
        assert user_info["name"] == sample_user["name"]
        assert "user_id" in user_info
        assert "roles" in user_info

    def test_get_user_info_with_roles(self):
        """역할 정보 추출"""
        token = generate_token(roles=["admin", "user"])
        payload, _, _ = validate_token(token)
        user_info = get_user_info(payload)

        assert "admin" in user_info["roles"]
        assert "user" in user_info["roles"]


class TestTokenExpiry:
    """토큰 만료 관련 테스트"""

    def test_token_not_expiring_soon(self):
        """토큰이 곧 만료되지 않음"""
        token = generate_token(expires_in=3600)  # 1시간
        payload, _, _ = validate_token(token)

        assert is_token_expiring_soon(payload, threshold_seconds=300) is False

    def test_token_expiring_soon(self):
        """토큰이 곧 만료됨"""
        token = generate_token(expires_in=60)  # 1분
        payload, _, _ = validate_token(token)

        assert is_token_expiring_soon(payload, threshold_seconds=300) is True
