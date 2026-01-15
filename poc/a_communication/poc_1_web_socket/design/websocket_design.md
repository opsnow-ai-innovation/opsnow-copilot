# WebSocket 통신 설계서

> OpsNow Copilot 클라이언트-서버 실시간 통신 상세 설계

---

## 1. 개요

### 1.1 목적

OpsNow Copilot의 클라이언트(브라우저)와 서버 간 **실시간 양방향 통신**을 위한 WebSocket 프로토콜 설계

### 1.2 요구사항

| 요구사항 | 설명 |
|----------|------|
| 실시간 통신 | 양방향 메시지 즉시 송수신 |
| 양방향 통신 | 서버가 클라이언트에 데이터 요청 가능 (콜백 패턴) |
| 연결 안정성 | 연결 끊김 감지, 자동 재연결 |
| 보안 | One-Time Token으로 콜백 응답 검증 |

### 1.3 기술 스택

```
Server: FastAPI + uvicorn (ASGI)
Client: 브라우저 네이티브 WebSocket API
Protocol: RFC 6455 (WebSocket)
Message Format: JSON
```

---

## 2. 연결 관리

### 2.1 연결 수립 (Handshake)

#### 엔드포인트

```
wss://{host}/ws/copilot?token={auth_token}
```

| 항목 | 값 |
|------|-----|
| Protocol | `wss://` (TLS) |
| Path | `/ws/copilot` |
| Auth | Query parameter `token` |

#### 연결 흐름

```
Client                                          Server
  │                                               │
  │ ─── GET /ws/copilot?token=xxx ──────────────► │
  │     Upgrade: websocket                        │
  │     Connection: Upgrade                       │
  │                                               │
  │                                    [토큰 검증] │
  │                                               │
  │ ◄─── 101 Switching Protocols ──────────────── │  (성공)
  │      Upgrade: websocket                       │
  │                                               │
  │ ═══════════ WebSocket 연결 수립 ═══════════════ │
  │                                               │
  │ ◄─── connected {serverTime} ────────────────── │
  │                                               │
```

#### 연결 실패 시

| HTTP 상태 | 원인 | 클라이언트 동작 |
|-----------|------|----------------|
| `401 Unauthorized` | 토큰 없음 | 로그인 페이지 이동 |
| `403 Forbidden` | 토큰 만료/무효 | 토큰 갱신 후 재시도 |
| `429 Too Many Requests` | Rate Limit 초과 | 대기 후 재시도 |
| `4001` (WebSocket) | 토큰 검증 실패 | 연결 종료 |

#### Rate Limiting

| 항목 | 값 |
|------|-----|
| 최대 요청 | 10 requests |
| 윈도우 | 60초 |

### 2.2 연결 수명주기

```
┌─────────────────────────────────────────────────────────────┐
│                      연결 수명주기                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   [DISCONNECTED] ──connect──> [CONNECTING]                  │
│         ▲                          │                        │
│         │                     connected                     │
│         │                          ▼                        │
│     disconnect              [CONNECTED]                     │
│         │                          │                        │
│         │                     error/close                   │
│         │                          ▼                        │
│         └──────────────── [RECONNECTING]                    │
│                                    │                        │
│                               retry/fail                    │
│                                    ▼                        │
│                            [DISCONNECTED]                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 연결 상태

| 상태 | 설명 | 클라이언트 동작 |
|------|------|-----------------|
| `DISCONNECTED` | 연결 없음 | 연결 시도 가능 |
| `CONNECTING` | 연결 중 | 대기 |
| `CONNECTED` | 연결됨 | 메시지 송수신 가능 |
| `RECONNECTING` | 재연결 중 | 메시지 큐잉 |

---

## 3. 메시지 프로토콜

### 3.1 메시지 구조

모든 메시지는 JSON 형식이며, `type` 필드로 메시지 종류 구분

```typescript
interface BaseMessage {
  type: string;           // 메시지 타입 (필수)
  requestId?: string;     // 요청 식별자 (콜백용)
  timestamp?: number;     // 타임스탬프 (ms)
}
```

### 3.2 Client → Server 메시지

#### 3.2.1 query (질의)

사용자가 질문을 입력할 때 전송. **사용자 질문과 화면 DOM 컨텍스트가 함께 전달됨.**

```typescript
interface QueryMessage {
  type: "query";
  query: string;                      // 사용자 질문
  domContext: string;                 // 화면 DOM 컨텍스트 (~2000 토큰)
  page: {
    url: string;                      // 현재 페이지 URL
    title: string;                    // 페이지 타이틀
    vendor?: string;                  // 선택된 벤더
  };
}
```

> **참고**: `availableData`(IndexedDB 데이터 목록)는 서버가 `request_available_data`로 별도 요청합니다.

**domContext 포함 내용:**
- 현재 화면의 비용/자산 데이터 요약
- 테이블 데이터 (상위 N개 행)
- 차트 데이터 포인트
- 필터 상태 (기간, 벤더 등)

```typescript
// domContext 예시 (~2000 토큰)
{
  "summary": {
    "totalCost": "$45,678",
    "change": "+15%",
    "period": "2024-01"
  },
  "table": {
    "headers": ["Service", "Cost", "Change"],
    "rows": [
      ["EC2", "$15,000", "+25%"],
      ["Lambda", "$3,000", "-5%"],
      // ... 상위 10개
    ]
  },
  "filters": {
    "period": "2024-01",
    "vendor": "aws"
  }
}
```

#### 3.2.2 human_response (사용자 응답)

서버의 `clarification_request`에 대한 응답

```typescript
interface HumanResponseMessage {
  type: "human_response";
  requestId: string;
  response: string;                   // 사용자 입력
  selectedOption?: string;            // 선택한 옵션 (있는 경우)
}
```

#### 3.2.3 available_data (IndexedDB 데이터 목록)

서버의 `request_available_data` 요청에 대한 응답 (현재 IndexedDB에 저장된 데이터 목록)

```typescript
interface AvailableDataMessage {
  type: "available_data";
  requestId: string;
  data: AvailableDataItem[];
}

interface AvailableDataItem {
  key: string;                        // IndexedDB 키 (예: "costSummary")
  description?: string;               // 데이터 설명 (예: "월별 비용 요약")
  size?: number;                      // 대략적인 크기 (bytes)
}
```

> **참고**: 클라이언트는 페이지 로드 시 API 호출 결과를 IndexedDB에 저장합니다.
> 서버는 필요 시 이 목록을 요청하여 어떤 데이터가 사용 가능한지 확인합니다.

#### 3.2.4 api_result (IndexedDB 데이터 결과)

서버의 `request_api` 요청에 대한 응답 (IndexedDB에서 조회한 데이터)

```typescript
interface ApiResultMessage {
  type: "api_result";
  requestId: string;
  success: boolean;
  data?: any;                         // 성공 시 데이터
  error?: {
    code: string;
    message: string;
  };
  isLargeData?: boolean;              // 대용량 데이터 여부
  cacheKey?: string;                  // IndexedDB 캐시 키
}
```

#### 3.2.5 schema_response (IndexedDB 스키마 응답) - 대용량 데이터용

서버의 `request_schema` 요청에 대한 응답 (IndexedDB 데이터의 스키마)

```typescript
interface SchemaResponseMessage {
  type: "schema_response";
  requestId: string;
  schema: {
    fields: string[];
    types: Record<string, string>;
    totalRecords: number;
    estimatedSize: number;
    sampleData?: any[];
  };
  cacheKey: string;
}
```

#### 3.2.6 code_result (IndexedDB 코드 실행 결과) - 대용량 데이터용

서버의 `execute_code` 요청에 대한 응답 (IndexedDB 데이터에 대해 JavaScript 코드 실행 결과)

```typescript
interface CodeResultMessage {
  type: "code_result";
  requestId: string;
  success: boolean;
  result?: any;
  error?: {
    type: string;
    message: string;
  };
}
```

#### 3.2.7 pong (하트비트 응답)

서버의 `ping`에 대한 응답

```typescript
interface PongMessage {
  type: "pong";
}
```

### 3.3 Server → Client 메시지

#### 3.3.1 connected (연결 확인)

```typescript
interface ConnectedMessage {
  type: "connected";
  serverTime: string;                 // ISO 8601
}
```

#### 3.3.2 clarification_request (추가 질문)

사용자에게 추가 정보 요청 (ask_human 도구)

```typescript
interface ClarificationRequestMessage {
  type: "clarification_request";
  requestId: string;
  question: string;                   // 질문 텍스트
  options?: string[];                 // 선택지 (있는 경우)
  defaultValue?: string;              // 기본값
  inputType?: "text" | "select" | "confirm";
  timeout?: number;                   // 응답 대기 시간 (ms)
}
```

#### 3.3.3 request_available_data (IndexedDB 목록 요청)

클라이언트의 IndexedDB에 저장된 데이터 목록 요청

```typescript
interface RequestAvailableDataMessage {
  type: "request_available_data";
  requestId: string;
  timeout?: number;                   // 기본 10초
}
```

> **참고**: 서버는 query 수신 후 IndexedDB에서 사용 가능한 데이터를 확인하기 위해 이 메시지를 보냅니다.

#### 3.3.4 request_api (IndexedDB 데이터 요청)

클라이언트의 IndexedDB에서 데이터 조회 요청 (request_api 도구)

```typescript
interface RequestApiMessage {
  type: "request_api";
  requestId: string;
  dataKey: string;                    // IndexedDB 키 (available_data에서 선택)
  timeout?: number;                   // 기본 60초
}
```

> **참고**: 서버는 `available_data`에서 필요한 데이터를 선택하여 `dataKey`로 요청합니다.

#### 3.3.5 request_schema (IndexedDB 스키마 요청) - 대용량 데이터용

IndexedDB 대용량 데이터의 스키마만 요청

```typescript
interface RequestSchemaMessage {
  type: "request_schema";
  requestId: string;
  cacheKey: string;                   // IndexedDB 캐시 키
  timeout?: number;                   // 기본 10초
}
```

#### 3.3.6 execute_code (IndexedDB 코드 실행 요청) - 대용량 데이터용

LLM이 생성한 JavaScript 코드를 IndexedDB 데이터에 대해 클라이언트에서 실행

```typescript
interface ExecuteCodeMessage {
  type: "execute_code";
  requestId: string;
  code: string;                       // JavaScript 코드
  cacheKey: string;                   // IndexedDB 키
  timeout?: number;                   // 기본 10초
}
```

#### 3.3.7 response (최종 응답)

질의에 대한 최종 응답

```typescript
interface ResponseMessage {
  type: "response";
  answer: string;                     // 답변 (Markdown)
  suggestions?: Suggestion[];         // 후속 제안
  sources?: string[];                 // 참조 소스
  actions?: Action[];                 // 실행 가능한 액션
}

interface Suggestion {
  type: "follow_up" | "related" | "menu";
  text: string;
  query?: string;                     // follow_up: 후속 질문
  url?: string;                       // menu: 이동 URL
}

interface Action {
  type: "link" | "copy" | "download";
  label: string;
  value: string;
}
```

#### 3.3.8 error (에러)

```typescript
interface ErrorMessage {
  type: "error";
  code: ErrorCode;
  message: string;
  requestId?: string;                 // 관련 요청 ID
  retryable?: boolean;                // 재시도 가능 여부
}

type ErrorCode =
  | "CONNECTION_CLOSED"
  | "INVALID_MESSAGE"
  | "INVALID_TOKEN"
  | "TIMEOUT"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR";
```

#### 3.3.9 ping (하트비트)

연결 유지 확인을 위한 주기적 핑

```typescript
interface PingMessage {
  type: "ping";
}
```

**주기**: 30초

---

## 4. 콜백 패턴 상세

### 4.1 동기화 메커니즘

서버가 클라이언트의 IndexedDB 데이터를 필요로 할 때 사용하는 **비동기 콜백 패턴**

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Server (Python/asyncio)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   async def process_query(websocket, query):                        │
│       # 1. 클라이언트의 IndexedDB 목록 요청 (콜백)                   │
│       available = await request_available_data(websocket)           │
│                                                                     │
│       # 2. 필요한 데이터 결정 후 IndexedDB에서 데이터 요청 (콜백)    │
│       needed_keys = analyze_available_data(available)               │
│       data = await request_indexed_db_data(websocket, needed_keys)  │
│                         ▲                                           │
│                         │ await (대기)                               │
│                         │                                           │
│       # 3. 데이터로 ReAct 처리                                       │
│       response = await generate_response(query, data)               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                   WebSocket  │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Client (JavaScript)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ws.onmessage = async (event) => {                                 │
│       const msg = JSON.parse(event.data);                           │
│                                                                     │
│       if (msg.type === "request_api") {                             │
│           // 1. IndexedDB에서 데이터 조회                            │
│           const result = await getFromIndexedDB(msg.dataKey);       │
│                                                                     │
│           // 2. 응답 전송 (requestId 포함)                           │
│           ws.send(JSON.stringify({                                  │
│               type: "api_result",                                   │
│               requestId: msg.requestId,  // 필수!                   │
│               success: true,                                        │
│               data: result                                          │
│           }));                                                      │
│       }                                                             │
│   };                                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 PendingCallbacks 구현

```python
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class PendingCallback:
    future: asyncio.Future
    created_at: datetime
    timeout: float
    callback_type: str  # "data", "human", "api"

class PendingCallbacks:
    """콜백 요청 관리자"""

    def __init__(self, default_timeout: float = 30.0):
        self._pending: Dict[str, PendingCallback] = {}
        self._default_timeout = default_timeout

    def create(
        self,
        request_id: str,
        callback_type: str = "data",
        timeout: Optional[float] = None
    ) -> asyncio.Future:
        """새 콜백 Future 생성"""
        if request_id in self._pending:
            raise ValueError(f"Duplicate request_id: {request_id}")

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        self._pending[request_id] = PendingCallback(
            future=future,
            created_at=datetime.now(),
            timeout=timeout or self._default_timeout,
            callback_type=callback_type
        )

        return future

    def resolve(self, request_id: str, data: Any) -> bool:
        """콜백 완료 (1회용 - 즉시 제거)"""
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.set_result(data)

        return True

    def reject(self, request_id: str, error: Exception) -> bool:
        """콜백 실패"""
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.set_exception(error)

        return True

    def cancel(self, request_id: str) -> bool:
        """콜백 취소"""
        if request_id not in self._pending:
            return False

        callback = self._pending.pop(request_id)

        if not callback.future.done():
            callback.future.cancel()

        return True

    def cleanup_expired(self) -> int:
        """만료된 콜백 정리"""
        now = datetime.now()
        expired = []

        for request_id, callback in self._pending.items():
            if now - callback.created_at > timedelta(seconds=callback.timeout):
                expired.append(request_id)

        for request_id in expired:
            self.reject(request_id, TimeoutError(f"Callback timeout: {request_id}"))

        return len(expired)
```

### 4.3 타임아웃 처리

```python
async def request_api(
    websocket: WebSocket,
    data_key: str,
    callbacks: PendingCallbacks,
    timeout: float = 60.0
) -> dict:
    """클라이언트의 IndexedDB에서 데이터 조회 요청"""
    request_id = generate_one_time_token()

    # Future 생성
    future = callbacks.create(request_id, "api", timeout)

    # 요청 전송
    await websocket.send_json({
        "type": "request_api",
        "requestId": request_id,
        "dataKey": data_key,  # IndexedDB 키 (available_data에서 선택)
        "timeout": int(timeout * 1000)  # 클라이언트에게도 알림
    })

    try:
        # 타임아웃과 함께 대기
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        callbacks.remove(request_id)
        raise ApiRequestTimeout(data_key)
```

---

## 5. One-Time Token 상세

### 5.1 토큰 구조

```
{timestamp}-{random}

예: 1705123456789-abc123def456ghi789
    │              │
    │              └── 랜덤 문자열 (16+ chars, URL-safe)
    └── Unix timestamp (ms)
```

### 5.2 생성 및 검증

```python
import secrets
import time

class TokenManager:
    """One-Time Token 관리"""

    def __init__(self, max_age_seconds: float = 60.0):
        self._max_age = max_age_seconds

    def generate(self) -> str:
        """새 토큰 생성"""
        timestamp = int(time.time() * 1000)
        random_part = secrets.token_urlsafe(16)
        return f"{timestamp}-{random_part}"

    def validate_timestamp(self, token: str) -> bool:
        """토큰 타임스탬프 검증 (만료 여부)"""
        try:
            timestamp_str = token.split("-")[0]
            timestamp = int(timestamp_str)
            age = (time.time() * 1000 - timestamp) / 1000
            return age <= self._max_age
        except (ValueError, IndexError):
            return False
```

### 5.3 보안 고려사항

| 위협 | 대응 |
|------|------|
| 토큰 재사용 | 사용 즉시 폐기 (1회용) |
| 토큰 예측 | `secrets.token_urlsafe` 사용 (암호학적 안전) |
| 오래된 토큰 | 타임스탬프 검증 (max_age) |
| 타 세션 토큰 | 세션별 PendingCallbacks 분리 |

---

## 6. 에러 처리

### 6.1 에러 코드 상세

| 코드 | HTTP 유사 | 설명 | 클라이언트 액션 |
|------|-----------|------|-----------------|
| `CONNECTION_CLOSED` | - | WebSocket 연결 종료 | 재연결 |
| `INVALID_MESSAGE` | 400 | 잘못된 메시지 형식 | 메시지 수정 후 재전송 |
| `INVALID_TOKEN` | 401 | 유효하지 않은 requestId | 무시 (이미 처리됨) |
| `TIMEOUT` | 408 | 응답 시간 초과 | 재시도 또는 취소 |
| `RATE_LIMITED` | 429 | 요청 제한 초과 | 대기 후 재시도 |
| `INTERNAL_ERROR` | 500 | 서버 내부 에러 | 재시도 |

### 6.2 에러 응답 예시

```json
{
  "type": "error",
  "code": "TIMEOUT",
  "message": "데이터 요청 시간이 초과되었습니다",
  "requestId": "1705123456789-abc123",
  "retryable": true
}
```

### 6.3 서버 에러 핸들링

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def websocket_error_handler(websocket: WebSocket):
    """WebSocket 에러 핸들링 컨텍스트"""
    try:
        yield
    except WebSocketDisconnect:
        # 정상 종료 - 로깅만
        logger.info("Client disconnected")
    except asyncio.TimeoutError as e:
        await send_error(websocket, "TIMEOUT", str(e), retryable=True)
    except ValidationError as e:
        await send_error(websocket, "INVALID_MESSAGE", str(e), retryable=False)
    except Exception as e:
        logger.exception("Unexpected error")
        await send_error(websocket, "INTERNAL_ERROR", "서버 오류가 발생했습니다", retryable=True)

async def send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    request_id: str = None,
    retryable: bool = False
):
    """에러 메시지 전송"""
    await websocket.send_json({
        "type": "error",
        "code": code,
        "message": message,
        "requestId": request_id,
        "retryable": retryable
    })
```

---

## 7. 재연결 전략

### 7.1 Exponential Backoff

```javascript
class ReconnectManager {
    constructor(options = {}) {
        this.baseDelay = options.baseDelay || 1000;    // 1초
        this.maxDelay = options.maxDelay || 30000;     // 30초
        this.maxAttempts = options.maxAttempts || 10;
        this.jitterFactor = options.jitterFactor || 0.3;

        this.attempts = 0;
    }

    getNextDelay() {
        if (this.attempts >= this.maxAttempts) {
            return null;  // 재연결 포기
        }

        // Exponential backoff with jitter
        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.attempts),
            this.maxDelay
        );

        // Jitter 추가 (동시 재연결 방지)
        const jitter = delay * this.jitterFactor * Math.random();

        this.attempts++;
        return delay + jitter;
    }

    reset() {
        this.attempts = 0;
    }
}
```

### 7.2 재연결 흐름

```javascript
class CopilotWebSocket {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectManager = new ReconnectManager();
        this.messageQueue = [];  // 재연결 중 메시지 큐
    }

    connect() {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            this.reconnectManager.reset();
            this.flushMessageQueue();
        };

        this.ws.onclose = (event) => {
            if (!event.wasClean) {
                this.scheduleReconnect();
            }
        };

        this.ws.onerror = () => {
            // onclose가 호출됨
        };
    }

    scheduleReconnect() {
        const delay = this.reconnectManager.getNextDelay();

        if (delay === null) {
            this.onReconnectFailed();
            return;
        }

        setTimeout(() => this.connect(), delay);
    }

    send(message) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            this.messageQueue.push(message);
        }
    }

    flushMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
    }
}
```

---

## 8. 성능 고려사항

### 8.1 메시지 크기 제한

| 메시지 | 권장 최대 크기 | 비고 |
|--------|---------------|------|
| query | 50KB | domContext (~2000 토큰) 포함 |
| api_result | 100KB | 초과 시 isLargeData: true |
| schema_response | 2KB | 스키마만 |
| code_result | 1KB | 추출 결과만 |
| response | 50KB | answer + suggestions |

### 8.2 하트비트 (Keep-Alive)

```python
HEARTBEAT_INTERVAL = 30  # 초

async def heartbeat_loop(websocket: WebSocket):
    """연결 유지를 위한 주기적 핑"""
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "ping"})
        except Exception:
            break
```

---

## 9. 보안

### 9.1 인증

WebSocket 연결 시 인증 토큰 검증

```python
@app.websocket("/ws/copilot")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)  # 쿼리 파라미터로 토큰 전달
):
    # 토큰 검증
    try:
        user = verify_token(token)
    except InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket, user.id)
    # ...
```

### 9.2 Rate Limiting

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = datetime.now()
        window_start = now - self.window

        # 윈도우 내 요청만 유지
        self.requests[user_id] = [
            t for t in self.requests[user_id]
            if t > window_start
        ]

        if len(self.requests[user_id]) >= self.max_requests:
            return False

        self.requests[user_id].append(now)
        return True
```

---

## 부록: 타입 정의 전체

```typescript
// ============================================
// Common Types
// ============================================

type MessageType =
  // Client → Server
  | "query"
  | "human_response"
  | "available_data"
  | "api_result"
  | "schema_response"
  | "code_result"
  // Server → Client
  | "connected"
  | "clarification_request"
  | "request_available_data"
  | "request_api"
  | "request_schema"
  | "execute_code"
  | "response"
  | "error"
  | "ping"
  | "pong";

type ErrorCode = "CONNECTION_CLOSED" | "INVALID_MESSAGE" | "INVALID_TOKEN" | "TIMEOUT" | "RATE_LIMITED" | "INTERNAL_ERROR";

// ============================================
// Query Types
// ============================================

interface QueryMessage {
  type: "query";
  query: string;                      // 사용자 질문
  domContext: string;                 // 화면 DOM 컨텍스트 (~2000 토큰)
  page: {
    url: string;
    title: string;
    vendor?: string;
  };
}

// 서버가 IndexedDB 목록 요청
interface RequestAvailableDataMessage {
  type: "request_available_data";
  requestId: string;
  timeout?: number;
}

// 클라이언트가 IndexedDB 목록 응답
interface AvailableDataMessage {
  type: "available_data";
  requestId: string;
  data: AvailableDataItem[];
}

interface AvailableDataItem {
  key: string;                        // IndexedDB 키
  description?: string;               // 데이터 설명
  size?: number;                      // 크기 (bytes)
}

interface DomContext {
  summary?: {
    totalCost: string;
    change: string;
    period: string;
  };
  table?: {
    headers: string[];
    rows: string[][];
  };
  filters?: Record<string, string>;
}

// ============================================
// Response Types
// ============================================

interface Suggestion {
  type: "follow_up" | "related" | "menu";
  text: string;
  query?: string;
  url?: string;
}

interface Action {
  type: "link" | "copy" | "download";
  label: string;
  value: string;
}
```
