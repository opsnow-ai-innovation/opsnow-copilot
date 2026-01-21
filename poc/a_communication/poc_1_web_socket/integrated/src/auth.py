"""
JWT 인증 유틸리티 (Mock)

실제 환경: Keycloak JWKS로 RS256 검증
PoC Mock: 로컬 secret key로 HS256 검증
"""

import time
import uuid
import jwt
from typing import Optional

# Mock 설정 (실제 환경에서는 환경변수로 관리)
JWT_SECRET_KEY = "opsnow-copilot-poc-secret-key-for-testing"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "https://sso.opsnow360.io/realms/OPSNOW"
JWT_AUDIENCE = "platform_api"
JWT_EXPIRY_SECONDS = 3600  # 1시간


def generate_token(
    user_id: str = None,
    username: str = "test@example.com",
    name: str = "테스트 사용자",
    company_id: str = None,
    roles: list[str] = None,
    expires_in: int = JWT_EXPIRY_SECONDS
) -> str:
    """JWT 토큰 생성 (Mock)"""
    now = int(time.time())

    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "exp": now + expires_in,
        "iat": now,
        "iss": JWT_ISSUER,
        "aud": [JWT_AUDIENCE, "account"],
        "preferred_username": username,
        "name": name,
        "email": username,
        "email_verified": True,
        "currentCompanyId": company_id or str(uuid.uuid4()),
        "realm_access": {
            "roles": roles or ["default-roles-opsnow", "platform_admin"]
        },
        "typ": "Bearer",
        "azp": "platform_web",
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def validate_token(token: str) -> tuple[Optional[dict], Optional[str], int]:
    """
    JWT 토큰 검증

    Returns:
        (payload, error, status_code)
    """
    if not token:
        return None, "토큰이 없습니다", 401

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
    """JWT payload에서 사용자 정보 추출"""
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("preferred_username"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "company_id": payload.get("currentCompanyId"),
        "roles": payload.get("realm_access", {}).get("roles", [])
    }


def is_token_expiring_soon(payload: dict, threshold_seconds: int = 300) -> bool:
    """토큰이 곧 만료되는지 확인 (기본 5분 이내)"""
    exp = payload.get("exp", 0)
    return (exp - time.time()) < threshold_seconds