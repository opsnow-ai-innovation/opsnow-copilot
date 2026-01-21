# WebSocket PoC - Integrated

Phase 1-5 검증 완료된 모든 기능 통합

## 구조

```
integrated/
├── src/
│   ├── __init__.py
│   ├── auth.py              # JWT 인증
│   ├── callbacks.py         # 콜백 관리 (One-Time Token)
│   ├── connection_manager.py # 다중 사용자 연결 관리
│   ├── rate_limiter.py      # Rate Limiting
│   ├── heartbeat.py         # Ping/Pong
│   └── server.py            # FastAPI 서버 (진입점)
├── test/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_callbacks.py
│   ├── test_connection_manager.py
│   └── test_rate_limiter.py
├── client.html              # 테스트 클라이언트
├── pytest.ini
├── requirements.txt
└── README.md
```

## 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 서버 실행
cd src
uvicorn server:app --reload --port 8000

# 3. 테스트 클라이언트
# 브라우저에서 client.html 열기
```

## 유닛 테스트

```bash
# 테스트 실행
pytest

# 상세 출력
pytest -v

# 특정 파일만
pytest test/test_auth.py
```

## 서버 설정

`src/server.py`의 `Config` 클래스에서 설정 변경:

```python
class Config:
    SINGLE_SESSION_PER_USER = False  # True: 단일 연결만
    SHARE_RATE_LIMIT = True          # True: 사용자 공유
    RATE_LIMIT_MAX_REQUESTS = 10
    RATE_LIMIT_WINDOW_SECONDS = 60
    HEARTBEAT_INTERVAL = 30
    PONG_TIMEOUT = 10
    MAX_MISSED_PONGS = 3
```

## 통합된 기능

| Phase | 기능 | 모듈 |
|-------|------|------|
| 1 | 양방향 통신 | server.py |
| 2 | JWT 인증 | auth.py |
| 3 | 콜백 패턴 | callbacks.py |
| 4 | Rate Limiting | rate_limiter.py |
| 4 | Ping/Pong | heartbeat.py |
| 5 | 다중 사용자 | connection_manager.py |

## PoC 하드코딩 값 (실제 환경 전환 시 수정 필요)

| 파일 | 값 | 실제 환경 |
|------|-----|----------|
| `auth.py` | `JWT_SECRET_KEY = "opsnow-copilot-poc-secret-key-for-testing"` | 환경변수 `JWT_SECRET_KEY` |
| `auth.py` | `JWT_ALGORITHM = "HS256"` | RS256 (Keycloak JWKS) |
| `auth.py` | `JWT_ISSUER`, `JWT_AUDIENCE` | 실제 Keycloak 설정값 |

```python
# 실제 환경 전환 예시
import os

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
# 또는 Keycloak JWKS 사용
# from jwt import PyJWKClient
# jwks_client = PyJWKClient(os.getenv("KEYCLOAK_JWKS_URL"))
```
