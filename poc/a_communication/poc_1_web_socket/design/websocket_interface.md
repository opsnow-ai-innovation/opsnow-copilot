# WebSocket 인터페이스 정의서

> OpsNow Copilot 클라이언트-서버 간 모든 WebSocket 메시지 타입 정리

---

## 1. 개요

### 1.1 통신 방향

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Client (Browser)          WebSocket           Server          │
│                                                                 │
│   ┌─────────────┐                            ┌─────────────┐   │
│   │ Copilot     │ ─────── C→S 메시지 ──────► │ Backend     │   │
│   │ Widget      │ ◄────── S→C 메시지 ─────── │ (FastAPI)   │   │
│   └─────────────┘                            └─────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 메시지 기본 구조

```typescript
interface BaseMessage {
  type: string;           // 메시지 타입 (필수)
  requestId?: string;     // 요청 식별자 (콜백용, One-Time Token)
  timestamp?: number;     // 타임스탬프 (ms)
}
```

---

## 2. Client → Server 메시지

### 2.1 메시지 타입 요약

| 타입 | 설명 | 트리거 | 응답 메시지 |
|------|------|--------|-------------|
| `query` | 사용자 질의 + DOM 컨텍스트 | 사용자가 질문 입력 | `response` |
| `human_response` | 사용자 추가 입력 | 서버 `clarification_request` | - |
| `available_data` | IndexedDB 데이터 목록 | 서버 `request_available_data` 요청 | - |
| `api_result` | IndexedDB 데이터 조회 결과 | 서버 `request_api` 요청 | - |
| `schema_response` | 데이터 스키마 응답 | 서버 `request_schema` 요청 | - |
| `code_result` | 코드 실행 결과 | 서버 `execute_code` 요청 | - |
| `pong` | 하트비트 응답 | 서버 `ping` | - |

---

### 2.2 query (사용자 질의)

**용도**: 사용자가 채팅창에 질문 입력 시 전송

```typescript
interface QueryMessage {
  type: "query";
  query: string;                      // 사용자 질문
  domContext: string;                 // 화면 DOM 컨텍스트 (~2000 토큰)
  page: {
    url: string;                      // 현재 페이지 URL
    title: string;                    // 페이지 타이틀
    vendor?: string;                  // 선택된 벤더 (aws, azure, gcp)
  };
}
```

**크기 제한**: ~50KB (domContext 포함)

> **참고**: `availableData`(IndexedDB 데이터 목록)는 서버가 `request_available_data`로 별도 요청합니다.

---

### 2.3 human_response (사용자 추가 입력)

**용도**: 서버의 `clarification_request` (ask_human 도구)에 대한 응답

```typescript
interface HumanResponseMessage {
  type: "human_response";
  requestId: string;
  response: string;                   // 사용자 입력
  selectedOption?: string;            // 선택한 옵션 (있는 경우)
}
```

**트리거**: 서버가 모호한 질문에 대해 되물음 시

---

### 2.4 available_data (IndexedDB 데이터 목록)

**용도**: 서버의 `request_available_data` 요청에 대한 응답 (현재 IndexedDB에 저장된 데이터 목록)

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

**예시**:
```json
{
  "type": "available_data",
  "requestId": "1736849123456-abc123",
  "data": [
    { "key": "costSummary", "description": "비용 요약", "size": 1024 },
    { "key": "costTrend", "description": "월별 비용 추세", "size": 52000 },
    { "key": "resourceList", "description": "리소스 목록", "size": 2048000 }
  ]
}
```

> **참고**: 클라이언트는 페이지 로드 시 API 호출 결과를 IndexedDB에 저장합니다.
> 서버는 필요 시 이 목록을 요청하여 어떤 데이터가 사용 가능한지 확인합니다.

---

### 2.6 api_result (IndexedDB 데이터 조회 결과)

**용도**: 서버의 `request_api` 요청에 대한 응답 (IndexedDB에서 조회한 데이터)

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
  // 대용량 데이터인 경우
  isLargeData?: boolean;              // true면 스키마 방식으로 처리
  cacheKey?: string;                  // IndexedDB 키
}
```

**크기 정책**:
- 데이터 < 100KB: 그대로 전송
- 데이터 >= 100KB: `isLargeData: true`로 표시, 스키마 방식으로 전환

> **참고**: 클라이언트는 IndexedDB에서 데이터를 조회하여 응답합니다.

---

### 2.7 schema_response (IndexedDB 스키마 응답) - 대용량 데이터용

**용도**: 서버의 `request_schema` 요청에 대한 응답 (IndexedDB 데이터의 스키마)

```typescript
interface SchemaResponseMessage {
  type: "schema_response";
  requestId: string;
  schema: {
    fields: string[];                 // 필드 목록
    types: Record<string, string>;    // 필드별 타입
    totalRecords: number;             // 총 레코드 수
    estimatedSize: number;            // 추정 크기 (bytes)
    sampleData?: any[];               // 샘플 데이터 (1-2건)
  };
  cacheKey: string;                   // IndexedDB 키
}
```

**크기 제한**: ~2KB

> **참고**: 클라이언트는 IndexedDB의 데이터 구조를 분석하여 스키마를 생성합니다.

---

### 2.8 code_result (IndexedDB 코드 실행 결과) - 대용량 데이터용

**용도**: 서버의 `execute_code` 요청에 대한 응답 (IndexedDB에서 JavaScript 코드 실행 결과)

```typescript
interface CodeResultMessage {
  type: "code_result";
  requestId: string;
  success: boolean;
  result?: any;                       // 실행 결과 (추출된 데이터)
  error?: {
    type: string;                     // 에러 타입 (SyntaxError, TypeError, ...)
    message: string;
    stack?: string;
  };
}
```

**크기 제한**: ~1KB (추출된 핵심 데이터만)

> **참고**: 서버(LLM)가 생성한 JavaScript 코드를 IndexedDB 데이터에 대해 실행하고 결과를 반환합니다.

---

## 3. Server → Client 메시지

### 3.1 메시지 타입 요약

| 타입 | 설명 | 트리거 | 클라이언트 응답 |
|------|------|--------|-----------------|
| `connected` | 연결 확인 | WebSocket 연결 성공 | - |
| `clarification_request` | 사용자 추가 질문 | ask_human 도구 호출 | `human_response` |
| `request_available_data` | IndexedDB 데이터 목록 요청 | 데이터 확인 필요 시 | `available_data` |
| `request_api` | API 호출 요청 | request_api 도구 호출 | `api_result` |
| `request_schema` | 스키마 요청 | 대용량 API 응답 처리 | `schema_response` |
| `execute_code` | 코드 실행 요청 | ProgramOfThought 처리 | `code_result` |
| `response` | 최종 응답 | 질의 처리 완료 | - |
| `error` | 에러 | 에러 발생 | - |
| `ping` | 하트비트 요청 | 30초 주기 | `pong` |

---

### 3.2 connected (연결 확인)

**용도**: WebSocket 연결 성공 알림

```typescript
interface ConnectedMessage {
  type: "connected";
  serverTime: string;                 // 서버 시간 (ISO 8601)
}
```

---

### 3.3 clarification_request (추가 질문 - ask_human)

**용도**: 사용자에게 추가 정보 요청 (모호한 질문, 위험 액션 확인)

```typescript
interface ClarificationRequestMessage {
  type: "clarification_request";
  requestId: string;
  question: string;                   // 질문 텍스트
  options?: string[];                 // 선택지 (있는 경우)
  defaultValue?: string;              // 기본값
  inputType?: "text" | "select" | "confirm";
  timeout?: number;                   // 타임아웃 (ms), 기본 2분
}
```

**타임아웃**: 2분 (120초)

---

### 3.4 request_available_data (IndexedDB 데이터 목록 요청)

**용도**: 클라이언트의 IndexedDB에 저장된 데이터 목록 요청

```typescript
interface RequestAvailableDataMessage {
  type: "request_available_data";
  requestId: string;
  timeout?: number;                   // 타임아웃 (ms), 기본 10초
}
```

**타임아웃**: 10초

> **참고**: 서버는 query 수신 후 IndexedDB에서 사용 가능한 데이터를 확인하기 위해 이 메시지를 보냅니다.

---

### 3.5 request_api (IndexedDB 데이터 요청)

**용도**: IndexedDB에서 데이터 조회 요청

```typescript
interface RequestApiMessage {
  type: "request_api";
  requestId: string;
  dataKey: string;                    // IndexedDB 키 (available_data에서 선택)
  timeout?: number;                   // 타임아웃 (ms), 기본 60초
}
```

**타임아웃**: 60초

> **참고**: 서버는 `available_data`에서 필요한 데이터를 선택하여 `dataKey`로 요청합니다.

---

### 3.6 request_schema (IndexedDB 스키마 요청) - 대용량 데이터용

**용도**: IndexedDB 데이터의 스키마만 요청 (대용량 데이터 처리)

```typescript
interface RequestSchemaMessage {
  type: "request_schema";
  requestId: string;
  cacheKey: string;                   // IndexedDB 키
  timeout?: number;                   // 타임아웃 (ms), 기본 10초
}
```

**사용 시점**: `api_result.isLargeData === true`인 경우

> **참고**: 대용량 데이터의 경우 전체 데이터 대신 스키마(필드, 타입, 레코드 수)만 요청하여 LLM이 추출 코드를 생성할 수 있게 합니다.

---

### 3.7 execute_code (IndexedDB 코드 실행 요청) - 대용량 데이터용

**용도**: LLM이 생성한 JavaScript 코드를 IndexedDB 데이터에 대해 실행

```typescript
interface ExecuteCodeMessage {
  type: "execute_code";
  requestId: string;
  code: string;                       // JavaScript 코드
  cacheKey: string;                   // IndexedDB 키
  timeout?: number;                   // 타임아웃 (ms), 기본 10초
}
```

**보안**: 샌드박스 환경에서 실행, 허용된 API만 사용 가능

> **참고**: LLM이 스키마를 기반으로 생성한 JavaScript 코드를 클라이언트에서 실행하여 필요한 데이터만 추출합니다.

---

### 3.8 response (최종 응답)

**용도**: 질의에 대한 최종 응답

```typescript
interface ResponseMessage {
  type: "response";
  answer: string;                     // 답변 (Markdown)
  suggestions?: Suggestion[];         // 후속 제안
  sources?: string[];                 // 참조 소스 (FAQ, Manual)
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

---

### 3.9 error (에러)

**용도**: 에러 발생 알림

```typescript
interface ErrorMessage {
  type: "error";
  code: ErrorCode;
  message: string;
  requestId?: string;                 // 특정 요청 관련 에러
  retryable: boolean;                 // 재시도 가능 여부
}

type ErrorCode =
  | "CONNECTION_CLOSED"
  | "INVALID_MESSAGE"
  | "INVALID_TOKEN"
  | "TIMEOUT"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR";
```

---

### 3.10 ping/pong (하트비트)

**용도**: 연결 유지 및 끊김 감지

```typescript
// Server → Client
interface PingMessage {
  type: "ping";
}

// Client → Server
interface PongMessage {
  type: "pong";
}
```

**주기**: 30초

---

## 4. 메시지 흐름도

### 4.1 기본 질의 흐름

```
Client                              Server
  │                                    │
  │ ──────── query ──────────────────► │
  │          {query, domContext}       │
  │                                    │
  │ ◄─────── response ─────────────── │
  │          {answer, suggestions}     │
```

### 4.2 콜백 흐름 (ask_human)

```
Client                              Server
  │                                    │
  │ ──────── query ──────────────────► │
  │                                    │
  │                                    │ ReAct: ask_human 호출
  │                                    │
  │ ◄─────── clarification_request ─── │
  │          {question, options}       │
  │                                    │
  │          [사용자 입력 대기]          │
  │                                    │
  │ ──────── human_response ─────────► │
  │          {response}                │
  │                                    │
  │ ◄─────── response ─────────────── │
```

### 4.3 콜백 흐름 (request_api - IndexedDB 조회)

```
Client                              Server
  │                                    │
  │ ──────── query ──────────────────► │
  │          {query, domContext}       │
  │                                    │
  │                                    │ 데이터 필요 여부 판단
  │                                    │
  │ ◄── request_available_data ─────── │
  │                                    │
  │          [IndexedDB 목록 조회]       │
  │                                    │
  │ ──────── available_data ─────────► │
  │          {data: [...]}             │
  │                                    │
  │                                    │ 필요한 데이터 선택
  │                                    │
  │ ◄─────── request_api ────────────── │
  │          {dataKey}                 │
  │                                    │
  │          [IndexedDB 조회]           │
  │                                    │
  │ ──────── api_result ──────────────► │
  │          {success, data}           │
  │                                    │
  │ ◄─────── response ─────────────── │
```

### 4.4 대용량 데이터 처리 흐름 (ProgramOfThought)

```
Client                              Server
  │                                    │
  │ ──────── api_result ─────────────► │
  │          {isLargeData: true,       │
  │           cacheKey: "..."}         │
  │                                    │
  │ ◄─────── request_schema ────────── │
  │          {cacheKey}                │
  │                                    │
  │          [IndexedDB에서 스키마 추출] │
  │                                    │
  │ ──────── schema_response ────────► │
  │          {schema, cacheKey}        │
  │                                    │
  │                                    │ LLM: 추출 코드 생성
  │                                    │
  │ ◄─────── execute_code ──────────── │
  │          {code, cacheKey}          │
  │                                    │
  │          [코드 실행 (샌드박스)]       │
  │                                    │
  │ ──────── code_result ────────────► │
  │          {result}                  │
  │                                    │
  │ ◄─────── response ─────────────── │
```

---

## 5. 크기 제한 정책

| 메시지 | 방향 | 최대 크기 | 비고 |
|--------|------|----------|------|
| `query` | C→S | 50KB | domContext ~2000 토큰 포함 |
| `api_result` | C→S | 100KB | 초과 시 스키마 방식 |
| `schema_response` | C→S | 2KB | 스키마만 |
| `code_result` | C→S | 1KB | 추출 결과만 |
| `response` | S→C | 50KB | 최종 응답 |

---

## 6. 타임아웃 정책

| 콜백 도구 | 타임아웃 | 설명 |
|-----------|----------|------|
| `clarification_request` (ask_human) | 2분 | 사용자 입력 대기 |
| `request_available_data` | 10초 | IndexedDB 목록 조회 |
| `request_api` | 60초 | API 호출 |
| `request_schema` | 10초 | 스키마 추출 |
| `execute_code` | 10초 | 코드 실행 |

---

## 7. 참고 문서

- `ai_engine_design.html` - ReAct Loop, 도구 설계
- `api_response_postprocessing.html` - 대용량 데이터 처리 (ProgramOfThought)
- `websocket_design.md` - WebSocket 프로토콜 상세
