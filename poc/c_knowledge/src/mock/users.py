"""
Mock 유저 데이터

TODO: 합칠 때 제거 - 실제 서비스에서는 인증 시스템으로 대체
"""

import random
import uuid
from dataclasses import dataclass


@dataclass
class MockUser:
    """Mock 유저 정보"""

    user_id: str
    name: str
    color: str  # 터미널 출력용 색상 코드


# 3명의 Mock 유저
MOCK_USERS = [
    MockUser(
        user_id="user_001",
        name="김철수",
        color="\033[94m",  # 파랑
    ),
    MockUser(
        user_id="user_002",
        name="이영희",
        color="\033[92m",  # 초록
    ),
    MockUser(
        user_id="user_003",
        name="박민수",
        color="\033[93m",  # 노랑
    ),
]

RESET_COLOR = "\033[0m"


def get_random_user() -> MockUser:
    """랜덤 유저 선택"""
    return random.choice(MOCK_USERS)


def generate_session_id() -> str:
    """새 세션 ID 생성 (UUID)"""
    return str(uuid.uuid4())[:8]  # 짧게 8자리만


def print_user_banner(user: MockUser, session_id: str):
    """유저 정보 배너 출력"""
    print(f"\n{user.color}{'=' * 50}")
    print(f"  유저: {user.name} ({user.user_id})")
    print(f"  세션: {session_id}")
    print(f"{'=' * 50}{RESET_COLOR}\n")
