# WebSocket PoC 실행 계획

> `websocket_design.md` 설계 문서 기반 단계별 검증 계획

---

## 1. PoC 목표

설계 문서의 핵심 기능들이 실제로 동작하는지 검증:

| Phase | 검증 항목 | 설명 | 상태 |
|-------|-----------|------|------|
| 1 | 양방향 통신 | 클라이언트 ↔ 서버 실시간 메시지 송수신 | ✅ 완료 |
| 2 | 토큰 인증 | `ws://{host}/ws/copilot?token={auth_token}` 연결 | ✅ 완료 |
| 3 | 콜백 패턴 | 서버가 클라이언트에 데이터 요청 후 응답 대기 (One-Time Token) | ✅ 완료 |
| 4 | 안정성 | 재연결, Rate Limiting, 에러 처리 | ✅ 완료 |
| 5 | 멀티 유저 | 다중 클라이언트 동시 연결 및 세션 독립성 (통합 테스트) | ✅ 완료 |

> **참고**: 기존 Phase 4 (대용량 데이터)는 WebSocket 통신 검증이 아닌 비즈니스 로직이므로 PoC 범위에서 제외

---

## 2. 단계별 실행 계획

### Phase 1: 기본 연결 ✅ 완료

**목표**: WebSocket 연결 수립 및 기본 메시지 송수신 (싱글 유저, 인증 없음)

```
phase1_basic/
├── server.py          # FastAPI WebSocket 서버
└── client.html        # 브라우저 테스트 클라이언트
```

**검증 항목**:
- [x] WebSocket 연결 핸드셰이크
- [x] `connected` 메시지 수신
- [x] `query` → `response` 기본 흐름
- [x] `ping` / `pong` 하트비트

---

### Phase 2: JWT 토큰 인증 ✅ 완료

**목표**: OpsNow 실제 환경과 동일한 Keycloak JWT 인증 방식 검증 (Mock)

```
phase2_auth/
├── server.py          # JWT 검증 로직 (Mock)
├── client.html        # JWT 토큰 포함 연결
└── auth.py            # JWT 유틸리티 (생성/검증)
```

**실제 환경 (OpsNow)**:
```
사용자 로그인 → Keycloak → JWT 발급 (RS256)
                              ↓
              Authorization: Bearer {JWT} 헤더로 전달
                              ↓
              서버가 Keycloak JWKS로 토큰 검증
```

**PoC Mock 구현**:
```
로컬 JWT 발급 (HS256, secret key)
                ↓
        ?token={JWT} 쿼리 파라미터로 전달
                ↓
        서버가 로컬 secret key로 토큰 검증
```

**검증 항목**:
- [x] `ws://{host}/ws/copilot?token={JWT}` 연결
- [x] JWT 검증 성공 → 연결 허용, payload에서 user_id 추출
- [x] 토큰 없음 → `1008` (Policy Violation) 연결 거부
- [x] 토큰 만료 → `4001` WebSocket close code
- [x] 토큰 서명 무효 → `4001` WebSocket close code
- [x] 토큰 갱신 후 재연결

**JWT Payload 구조** (실제 Keycloak 토큰 기반):
```json
{
  "sub": "997726f9-ce0f-470d-af5c-1ebe858e5bf3",
  "exp": 1768885200,
  "iat": 1768872107,
  "iss": "https://sso.opsnow360.io/realms/OPSNOW",
  "aud": ["platform_api", "account"],
  "preferred_username": "user@example.com",
  "name": "홍길동",
  "email": "user@example.com",
  "currentCompanyId": "ae06161e-8d5b-4c34-80c1-26f2cf00fff5",
  "realm_access": {
    "roles": ["platform_admin", "default-roles-opsnow"]
  }
}
```

**에러 코드**:
| HTTP/WS 코드 | 원인 | 클라이언트 동작 |
|--------------|------|----------------|
| `1008` | 토큰 없음 | 로그인 페이지 이동 |
| `4001` | 토큰 만료/서명 무효 | 토큰 갱신 후 재시도 |

---

### Phase 3: 콜백 패턴 ✅ 완료

**목표**: 서버 → 클라이언트 요청 (역방향 통신) 검증

```
phase3_callback/
├── server.py          # PendingCallbacks 구현
├── client.html        # 콜백 응답 처리
└── pending_callbacks.py # 콜백 관리 모듈
```

**검증 항목**:
- [x] `request_available_data` → `available_data` 흐름
- [x] `request_api` → `api_result` 흐름
- [x] `clarification_request` → `human_response` 흐름
- [ ] One-Time Token (requestId) 발급/매칭
- [x] 타임아웃 처리 (asyncio.wait_for)

**테스트 구성** (2개 영역):

#### 3-1. One-Time Token 테스트
서버가 발급한 requestId의 발급/매칭 검증

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 토큰 발급 확인 | 서버 요청 시 requestId 생성 | 로그에 토큰 표시 |
| 정상 매칭 | 동일한 requestId로 응답 | 매칭 성공 |
| 잘못된 토큰 | 존재하지 않는 requestId로 응답 | 매칭 실패 |
| 중복 사용 | 같은 requestId로 두 번 응답 | 두 번째 매칭 실패 |

#### 3-2. 콜백 패턴 시나리오 테스트
콜백 흐름별 동작 검증

| 시나리오 | 흐름 | 검증 내용 |
|---------|------|----------|
| 1: 기본 콜백 | query(C→S) → request_available_data(S→C) → available_data(C→S) → request_api(S→C) → api_result(C→S) → response(S→C) | 정상 흐름 |
| 2: Clarification | query(C→S) → clarification_request(S→C) → human_response(C→S) → response(S→C) | 사용자 입력 요청 |
| 3: 타임아웃 | 응답 지연 15초 (서버 타임아웃 10초) | 타임아웃 감지 |
| 4-A: 응답 없음 | 클라이언트가 서버 요청에 응답하지 않음 | 클라이언트 오류 상황 |
| 4-B: 빈 데이터 | 클라이언트가 빈 목록 응답 | 캐시 없음 상황 |

**콜백 흐름 시나리오**:
```
1. 클라이언트: query 전송
2. 서버: request_available_data 전송 (requestId 생성)
3. 서버: Future 생성 및 대기 (await)
4. 클라이언트: IndexedDB 목록 조회
5. 클라이언트: available_data 응답 (requestId 포함)
6. 서버: Future resolve, 처리 계속
7. 서버: response 전송
```

**PendingCallbacks 핵심 코드**:
```python
class PendingCallbacks:
    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}

    def create(self, request_id: str, timeout: float = 30.0) -> asyncio.Future:
        future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future
        return future

    def resolve(self, request_id: str, data: Any) -> bool:
        if request_id in self._pending:
            self._pending.pop(request_id).set_result(data)
            return True
        return False
```

---

### Phase 4: 안정성 (Rate Limiting, Ping/Pong, 재연결)

**목표**: Rate Limiting, Ping/Pong 타임아웃, 재연결, 에러 처리 검증

```
phase4_stability/
├── server.py          # RateLimiter, HeartbeatManager 구현
└── client.html        # 재연결 로직, Pong 테스트
```

**테스트 구성** (3개 영역):

#### 4-1. Rate Limiting 테스트
사용자별 요청 제한 검증

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 단일 요청 | 요청 1회 전송 | 정상 응답 |
| 연속 요청 (5회) | 요청 5회 연속 전송 | 정상 응답, remaining 감소 |
| 초과 요청 (12회) | 10회 초과 요청 | 11번째부터 RATE_LIMITED 에러 |
| 초기화 후 재시도 | Rate Limit 초기화 후 요청 | 정상 응답 |

#### 4-2. Ping/Pong 타임아웃 테스트
서버 ping에 클라이언트 pong 응답 검증

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 정상 응답 | ping 수신 시 pong 응답 | 연결 유지 |
| 응답 중지 | pong 응답 비활성화 | 3회 무응답 후 연결 종료 (code: 4003) |
| 빠른 테스트 | 5초 간격 ping 테스트 | ~25초 후 연결 종료 |

**HeartbeatManager 설정**:
```python
HEARTBEAT_INTERVAL = 30  # ping 전송 간격 (초)
PONG_TIMEOUT = 10        # pong 응답 대기 시간 (초)
MAX_MISSED_PONGS = 3     # 최대 허용 무응답 횟수

# 빠른 테스트 모드
QUICK_TEST_INTERVAL = 5      # 5초 간격
QUICK_TEST_PONG_TIMEOUT = 3  # 3초 대기
```

#### 4-3. 재연결 테스트 (Exponential Backoff)
연결 끊김 시 자동 재연결 검증

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 강제 연결 해제 | 수동 연결 끊기 | 자동 재연결 시도 |
| Backoff 증가 | 연속 재연결 실패 | 1초 → 2초 → 4초 → 8초 → 최대 30초 |
| 최대 시도 초과 | 10회 재연결 실패 | 재연결 중단 |

**검증 항목**:
- [x] Rate Limiting (10 req/60s)
- [x] `429 Too Many Requests` (RATE_LIMITED) 처리
- [x] Ping/Pong 타임아웃 → 연결 끊기 (3회 무응답)
- [x] Exponential Backoff 재연결
- [x] 에러 메시지 (`RATE_LIMITED`, `INVALID_MESSAGE` 등)

---

### Phase 5: 멀티 유저

**목표**: 다중 사용자 동시 연결 및 옵션별 동작 검증

```
phase5_multi_user/
├── server.py          # ConnectionManager, 옵션 설정
└── client.html        # 다중 사용자 테스트
```

**테스트 구성** (3개 영역):

#### 5-1. 동일 사용자 다중 연결 정책
같은 사용자가 여러 탭/브라우저에서 연결 시 동작

| 옵션 | 설명 | 동작 |
|------|------|------|
| `SINGLE_SESSION_PER_USER=False` | 다중 연결 허용 | 모든 연결 유지 |
| `SINGLE_SESSION_PER_USER=True` | 단일 연결만 허용 | 기존 연결 끊고 새 연결 |

#### 5-2. Rate Limit 공유 정책
동일 사용자의 다중 연결 시 Rate Limit 적용 방식

| 옵션 | 설명 | 동작 |
|------|------|------|
| `SHARE_RATE_LIMIT=True` | 사용자 기준 (공유) | 탭1 + 탭2 합쳐서 10회 |
| `SHARE_RATE_LIMIT=False` | 연결 기준 (별도) | 탭1: 10회, 탭2: 10회 |

#### 5-3. 동시 요청 처리
여러 사용자가 동시에 요청 시 독립 처리 검증

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| User A, B 동시 query | 두 사용자 동시 요청 | 각자 독립 응답 |
| User A 끊김 | A 연결 종료 | B 영향 없음 |
| 연결 현황 조회 | 현재 접속자 목록 | 실시간 표시 |

**서버 설정**:
```python
# 옵션 설정
SINGLE_SESSION_PER_USER = False     # True: 단일 연결만, False: 다중 연결 허용
SHARE_RATE_LIMIT = True             # True: 사용자 공유, False: 연결별 별도
```

**검증 항목**:
- [x] 동일 사용자 다중 연결 정책 (옵션별 동작)
- [x] Rate Limit 공유 정책 (옵션별 동작)
- [x] 동시 요청 독립 처리
- [x] 연결 현황 실시간 추적

---

## 3. 기술 스택

| 구분 | 기술 |
|------|------|
| Server | FastAPI + uvicorn |
| Client | 브라우저 네이티브 WebSocket API |
| 테스트 | pytest-asyncio (서버), 브라우저 콘솔 (클라이언트) |

---

## 4. 실행 방법

```bash
# 1. 가상환경 설정
cd poc/a_communication/poc_1_web_socket
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 서버 실행 (각 Phase별)
cd phase2_auth
uvicorn server:app --reload --port 8000

# 4. 클라이언트 테스트
# 브라우저에서 client.html 열기
```

---

## 5. 성공 기준

| Phase | 성공 기준 | 상태 |
|-------|-----------|------|
| Phase 1 | query → response 왕복 성공 | ✅ |
| Phase 2 | 유효 토큰 연결 성공, 무효 토큰 연결 거부 | ✅ |
| Phase 3 | 콜백 요청/응답 requestId 매칭 100% | ✅ |
| Phase 4 | 연결 끊김 후 자동 재연결, Rate Limit 동작 | |
| Phase 5 | 3+ 클라이언트 동시 연결, 메시지 격리 확인 | |

---

## 6. 폴더 구조 (최종)

```
poc/a_communication/poc_1_web_socket/
├── design/
│   ├── websocket_design.md      # 설계 문서
│   └── websocket_interface.md   # 인터페이스 정의
├── poc_plan.md                  # 이 문서
├── requirements.txt
├── phase1_basic/                # ✅ 완료
│   ├── server.py
│   └── client.html
├── phase2_auth/                 # ✅ 완료
│   ├── server.py
│   ├── client.html
│   └── auth.py                  # JWT 유틸리티 (Mock)
├── phase3_callback/             # ✅ 완료
│   ├── server.py
│   ├── client.html
│   └── pending_callbacks.py
├── phase4_stability/
│   ├── server.py
│   └── client.html
└── phase5_multi_user/
    ├── server.py
    └── client.html
```

---

## 7. 현재 진행 상황

- [x] Phase 1: 기본 연결 ✅
- [x] Phase 2: JWT 토큰 인증 ✅
- [x] Phase 3: 콜백 패턴 ✅
- [x] Phase 4: 안정성 (재연결, Rate Limiting) ✅
- [x] Phase 5: 멀티 유저 (통합 테스트) ✅

**PoC 완료!**

---

## 8. PoC 완료 후 다음 단계

1. 검증된 패턴을 `src/routes/websocket.py`로 이동
2. ReAct Loop (poc_b_ai_engine)과 통합
3. 실제 IndexedDB 연동 테스트