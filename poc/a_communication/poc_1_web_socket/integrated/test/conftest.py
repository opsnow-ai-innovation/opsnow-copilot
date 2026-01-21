"""Pytest fixtures"""

import sys
from pathlib import Path

# src 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


@pytest.fixture
def sample_user():
    """샘플 사용자 정보"""
    return {
        "username": "test@example.com",
        "name": "테스트 사용자",
        "user_id": "test-user-id-123"
    }


@pytest.fixture
def sample_users():
    """여러 사용자 정보"""
    return [
        {"username": "user_a@example.com", "name": "사용자 A"},
        {"username": "user_b@example.com", "name": "사용자 B"},
        {"username": "user_c@example.com", "name": "사용자 C"},
    ]
