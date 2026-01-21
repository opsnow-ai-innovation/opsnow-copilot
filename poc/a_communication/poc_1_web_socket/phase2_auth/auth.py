"""
JWT 인증 유틸리티 (Mock)

실제 환경: Keycloak JWKS로 RS256 검증
PoC Mock: 로컬 secret key로 HS256 검증

실제 환경으로 전환 시:
1. JWKS_URL 설정
2. get_signing_key() 함수에서 PyJWKClient 사용
3. jwt.decode()에서 RS256 알고리즘 사용
"""

import time
import uuid
import jwt
from dataclasses import dataclass
from typing import Optional

# Mock 설정 (실제 환경에서는 환경변수로 관리)
JWT_SECRET_KEY = "opsnow-copilot-poc-secret-key-for-testing"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "https://sso.opsnow360.io/realms/OPSNOW"  # 실제 Keycloak issuer
JWT_AUDIENCE = "platform_api"
JWT_EXPIRY_SECONDS = 3600  # 1시간


@dataclass
class TokenPayload:
    """JWT Payload (실제 Keycloak 토큰 구조 기반)"""
    sub: str                      # 사용자 UUID
    preferred_username: str       # 이메일
    name: str                     # 이름
    email: str                    # 이메일
    current_company_id: str       # 현재 회사 ID
    roles: list[str]              # 역할 목록
    exp: int                      # 만료 시간
    iat: int                      # 발급 시간


def generate_token(
    user_id: str = None,
    username: str = "test@example.com",
    name: str = "테스트 사용자",
    company_id: str = None,
    roles: list[str] = None,
    expires_in: int = JWT_EXPIRY_SECONDS
) -> str:
    """
    JWT 토큰 생성 (Mock)

    실제 환경에서는 Keycloak이 토큰을 발급하므로 이 함수는 테스트용
    """
    now = int(time.time())

    payload = {
        # 필수 클레임
        "sub": user_id or str(uuid.uuid4()),
        "exp": now + expires_in,
        "iat": now,
        "iss": JWT_ISSUER,
        "aud": [JWT_AUDIENCE, "account"],

        # Keycloak 사용자 정보
        "preferred_username": username,
        "name": name,
        "email": username,
        "email_verified": True,

        # OpsNow 커스텀 클레임
        "currentCompanyId": company_id or str(uuid.uuid4()),
        "masterCompanyId": str(uuid.uuid4()),
        "siteCd": "OPSNOW",
        "tokenType": "login",
        "locale": "ko",

        # 역할 정보
        "realm_access": {
            "roles": roles or ["default-roles-opsnow", "platform_admin"]
        },

        # 기타
        "typ": "Bearer",
        "azp": "platform_web",
        "session_state": str(uuid.uuid4()),
        "acr": "0",
        "allowed-origins": ["*"],
        "scope": "openid email profile"
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def validate_token(token: str) -> tuple[Optional[dict], Optional[str], int]:
    """
    JWT 토큰 검증

    Returns:
        (payload, error, status_code)
        - 성공: (payload_dict, None, 200)
        - 실패: (None, error_message, status_code)

    실제 환경에서는:
        1. Keycloak JWKS에서 공개키 가져오기
        2. RS256으로 서명 검증
    """
    if not token:
        return None, "토큰이 없습니다", 401

    # Bearer 접두사 제거 (있는 경우)
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER
        )
        return payload, None, 200

    except jwt.ExpiredSignatureError:
        return None, "토큰이 만료되었습니다", 401

    except jwt.InvalidAudienceError:
        return None, "잘못된 audience입니다", 401

    except jwt.InvalidIssuerError:
        return None, "잘못된 issuer입니다", 401

    except jwt.DecodeError:
        return None, "토큰 디코딩 실패", 401

    except jwt.InvalidTokenError as e:
        return None, f"유효하지 않은 토큰: {str(e)}", 401


def get_user_info(payload: dict) -> dict:
    """
    JWT payload에서 사용자 정보 추출
    """
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("preferred_username"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "company_id": payload.get("currentCompanyId"),
        "roles": payload.get("realm_access", {}).get("roles", [])
    }


def is_token_expiring_soon(payload: dict, threshold_seconds: int = 300) -> bool:
    """
    토큰이 곧 만료되는지 확인 (기본 5분 이내)
    """
    exp = payload.get("exp", 0)
    return (exp - time.time()) < threshold_seconds


# 테스트용
if __name__ == "__main__":
    # 토큰 생성
    token = generate_token(
        username="hwajeong.kang@bespinglobal.com",
        name="강화정"
    )
    print(f"Generated Token:\n{token}\n")

    # 토큰 검증
    payload, error, status = validate_token(token)
    if error:
        print(f"Error: {error}")
    else:
        print(f"Payload: {payload}\n")
        print(f"User Info: {get_user_info(payload)}")
