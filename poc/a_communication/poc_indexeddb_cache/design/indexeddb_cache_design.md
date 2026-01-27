# IndexedDB Cache 설계서

> OpsNow Copilot — 화면 데이터 캐싱 및 서버 연동 상세 설계

---

## 1. 개요

### 1.1 목적

OpsNow 프론트엔드의 API 응답을 **브라우저 IndexedDB에 자동 캐싱**하고, Copilot 서버가 **WebSocket 콜백**으로 해당 데이터를 조회/활용하는 구조 설계

### 1.2 PoC 검증 완료 항목

| Phase | 검증 항목 | 결과 |
|-------|-----------|------|
| Phase 1 | fetch/XHR 오버라이드 + IndexedDB 저장/조회 | 검증 완료 |
| Phase 2 | URL 필터링, 덮어쓰기, TTL, 중복 방지, 메뉴별 관리 | 검증 완료 |
| Phase 3 | 에러 격리 100%, 성능 영향 < 1ms, Sentry 공존 | 검증 완료 |
| Phase 4 | WebSocket 콜백 → IndexedDB 조회 End-to-End | 검증 완료 |

### 1.3 기술 스택

```
Network Intercept: fetch/XHR Override (브라우저 네이티브)
Storage: IndexedDB (브라우저 네이티브)
Communication: WebSocket (Server ↔ Client 콜백)
Server: FastAPI + uvicorn (ASGI)
Code Execution: new Function() sandbox (PoC) → Web Worker (프로덕션)
```

---

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (Client)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────────┐     ┌──────────────────┐                     │
│   │  OpsNow App      │     │  Copilot Widget   │                    │
│   │  (React + Axios)  │     │                  │                    │
│   └────────┬─────────┘     └────────┬─────────┘                    │
│            │                        │                               │
│            │ API 요청               │ WebSocket                     │
│            ▼                        ▼                               │
│   ┌──────────────────┐     ┌──────────────────┐                     │
│   │  Network Hook     │     │  WS Handler      │                    │
│   │  (fetch/XHR       │     │  (콜백 처리)      │                    │
│   │   Override)       │     │                  │                    │
│   └────────┬─────────┘     └────────┬─────────┘                    │
│            │ fire-and-forget         │ get/getAll                   │
│            ▼                        ▼                               │
│   ┌─────────────────────────────────────────┐                       │
│   │         IndexedDB (copilot-cache)       │                       │
│   │         api-responses store             │                       │
│   └─────────────────────────────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    WebSocket │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Copilot Server (Python)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   query 수신                                                        │
│     ↓                                                               │
│   request_available_data → 클라이언트 IndexedDB 키 목록 조회        │
│     ↓                                                               │
│   LLM 판단: 어떤 데이터가 필요한가?                                  │
│     ↓                                                               │
│   ┌─── 소용량 ───┐  ┌─── 대용량 ──────────┐                        │
│   │ request_api   │  │ execute_code         │                       │
│   │ (데이터 직접  │  │ (LLM이 생성한 JS    │                       │
│   │  전송 받기)   │  │  코드를 클라이언트   │                       │
│   │              │  │  에서 실행)          │                       │
│   └──────────────┘  └─────────────────────┘                        │
│     ↓                                                               │
│   LLM 응답 생성 → response 전송                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 모듈 구성

| 모듈 | 파일 | 역할 |
|------|------|------|
| **Network Hook** | `copilot-network-hook.js` | fetch/XHR 오버라이드, API 응답 감지 → IndexedDB 저장 |
| **Cache Manager** | `copilot-cache.js` | IndexedDB CRUD, TTL/용량/중복 관리 정책 |
| **WS Handler** | `copilot-ws-handler.js` | WebSocket 콜백 메시지 수신 → IndexedDB 조회 → 응답 |

### 2.3 스크립트 로드 순서

```html
<!-- index.html (OpsNow App보다 먼저 로드) -->
<script src="/copilot-cache.js"></script>
<script src="/copilot-network-hook.js"></script>
<script src="/copilot-ws-handler.js"></script>

<!-- OpsNow App -->
<script src="/app.js"></script>
```

> Network Hook은 App보다 먼저 로드해야 fetch/XHR 오버라이드가 적용됨
>
> **Axios Interceptor 전환 시**: 로드 순서 의존성 없음. Copilot 위젯 초기화 시점에 `getAxios().interceptors.response.use()`로 등록하면 됨

---

## 3. Network Hook — API 응답 캐싱

> **Axios Interceptor 전환 예정**: 현재 PoC는 fetch/XHR Override 방식이나,
> 공통 axios (`getAxios()`) 통일 후 Axios Interceptor로 전환합니다.
> 전환 시 이 모듈만 교체되며, IndexedDB 이후 흐름(Cache Manager, WS Handler, 서버)은 변경 없음.
>
> | 항목 | Override (PoC) | Interceptor (전환 후) |
> |------|---------------|----------------------|
> | 인터셉트 | fetch/XHR 래핑 | `axios.interceptors.response.use()` |
> | 로드 순서 | App보다 먼저 | 의존성 없음 |
> | response 접근 | `response.clone()` | `response.data` 직접 |
> | Sentry 충돌 | 가능 | 없음 |

### 3.1 동작 원리

```
Axios 응답 (response interceptor)
    │
    ▼
[필터링] shouldProcess() → 저장 대상 여부 판단
    │
    ├── 비대상 → 원본 응답 그대로 반환
    │
    └── 대상 →  원본 응답 반환 + fire-and-forget 저장
                 │
                 ▼
         [저장] CopilotCache.put() → IndexedDB
```

### 3.2 필터링 규칙

| 기준 | 조건 | 설명 |
|------|------|------|
| URL 패턴 | `/api/` 포함 | API 경로만 대상 |
| URL 제외 | `/auth/`, `/login/`, `/logout/` | 인증 관련 제외 |
| HTTP 메서드 | GET, POST | 조회 요청만 |
| 응답 상태 | 200~299 | 성공 응답만 |
| Content-Type | `application/json` | JSON 응답만 |
| 응답 크기 | < 10MB | 대용량 응답 스킵 |

### 3.3 메뉴 변경 감지

```
History API 래핑 (pushState, replaceState) + popstate 이벤트
    │
    ▼
현재 메뉴 감지 (URL pathname에서 추출)
    │
    ▼
이전 메뉴 데이터 삭제 (CopilotCache.deleteByMenu)
```

> 메뉴 변경 감지는 인터셉트 방식과 무관. Interceptor 전환 후에도 동일하게 동작

### 3.4 에러 격리 (PoC 검증 완료)

| 장애 상황 | 동작 | 원본 영향 |
|-----------|------|----------|
| IndexedDB 저장 실패 | 무시 (catch) | 없음 |
| IndexedDB quota 초과 | 스킵 | 없음 |
| JSON 파싱 실패 | 스킵 | 없음 |
| DB 접근 에러 | 무시 | 없음 |

> **fire-and-forget**: 비동기 저장이 완료되기 전에 원본 응답이 반환됨. 오버헤드 < 1ms

---

## 4. Cache Manager — IndexedDB 관리

### 4.1 데이터베이스 스키마

```
Database: copilot-cache
Store: api-responses

Record {
  key: string          // URL 기반 키 (예: "GET:/api/cost/summary")
  url: string          // 원본 URL
  method: string       // HTTP 메서드
  data: any            // API 응답 데이터 (JSON)
  size: number         // 데이터 크기 (bytes)
  menu: string         // 페이지 메뉴 경로 (예: "/cost/")
  timestamp: number    // 저장 시각 (ms)
}

Indexes:
  - menu     → 메뉴별 조회/삭제
  - timestamp → TTL 만료 확인, 오래된 항목 삭제
```

### 4.2 관리 정책

| 정책 | 값 | 설명 |
|------|-----|------|
| TTL | 5분 | 저장 후 5분 경과 시 자동 만료 |
| MAX_ENTRIES | 100건 | 초과 시 오래된 항목부터 삭제 |
| MAX_SIZE | 100MB | 단일 응답 크기 상한 |
| DEDUP_INTERVAL | 1초 | 동일 URL 중복 저장 방지 |
| 덮어쓰기 | 항상 | 동일 키 → 최신 데이터로 교체 |
| 메뉴 변경 삭제 | 즉시 | 이전 메뉴 데이터 전체 삭제 |

### 4.3 Public API

```typescript
interface CopilotCache {
  put(key: string, data: any, meta: object): Promise<void>
  get(key: string): Promise<Record | null>
  getAll(): Promise<Record[]>
  getByMenu(menu: string): Promise<Record[]>
  deleteByMenu(menu: string): Promise<void>
  count(): Promise<number>
  getDataSize(data: any): number
}
```

---

## 5. WebSocket Handler — 서버 콜백 처리

### 5.1 처리하는 콜백 타입

| 서버 → 클라이언트 | 클라이언트 → 서버 | 설명 |
|-------------------|------------------|------|
| `request_available_data` | `available_data` | IndexedDB 키 목록 조회 |
| `request_api` | `api_result` | 특정 키의 데이터 조회 |
| `execute_code` | `code_result` | LLM 생성 JS 코드 실행 |
| `ping` | `pong` | 하트비트 |

### 5.2 콜백 흐름 — request_available_data

```
Server                              Client
  │                                   │
  │ ─── request_available_data ─────► │
  │     { requestId }                 │
  │                                   │ CopilotCache.getAll()
  │                                   │
  │ ◄── available_data ──────────── │
  │     { requestId,                  │
  │       data: [                     │
  │         { key, description,       │
  │           size, menu, timestamp } │
  │       ]}                          │
```

### 5.3 콜백 흐름 — request_api

```
Server                              Client
  │                                   │
  │ ─── request_api ────────────────► │
  │     { requestId, dataKey }        │
  │                                   │ CopilotCache.get(dataKey)
  │                                   │
  │ ◄── api_result ─────────────── │
  │     { requestId, success,         │
  │       data (< 100KB) }           │
  │                                   │
  │ 또는                               │
  │ ◄── api_result ─────────────── │
  │     { requestId, success,         │
  │       isLargeData: true }         │ ← 100KB 이상: 스키마 방식 전환
```

### 5.4 콜백 흐름 — execute_code (대용량 데이터용)

```
Server                              Client
  │                                   │
  │ [LLM이 available_data 스키마를     │
  │  보고 자체 완결형 코드 생성]       │
  │                                   │
  │ ─── execute_code ───────────────► │
  │     { requestId,                  │
  │       code: "                     │
  │         const r = await           │
  │           CopilotCache.get(key);  │
  │         return r.data.breakdown   │
  │           .sort(...)              │
  │           .slice(0, 3);           │
  │       " }                         │
  │                                   │ new Function(code)()
  │                                   │
  │ ◄── code_result ─────────────── │
  │     { requestId, success,         │
  │       result: [...top3] }         │
```

**execute_code 핵심 특성**:
- 서버(LLM)가 available_data 스키마를 보고 **자체 완결형 코드 생성**
- 코드 안에 `CopilotCache.get(key)` 호출 포함 — 클라이언트는 코드만 실행
- 클라이언트는 어떤 키를 조회할지 **알 필요 없음**
- 에러 시 `code_result.success=false` + 에러 정보 반환 (원본 페이지 영향 없음)

### 5.5 execute_code 실행 환경

| 항목 | PoC | 프로덕션 |
|------|-----|---------|
| 실행 방식 | `new Function('CopilotCache', code)` | Web Worker / iframe sandbox |
| 접근 가능 객체 | `CopilotCache` 만 | `CopilotCache` 만 |
| 타임아웃 | 10초 | 10초 |
| 에러 격리 | try-catch | Worker 격리 |

### 5.6 약속된 클라이언트 인터페이스

서버(LLM)가 execute_code 생성 시 사용할 수 있는 인터페이스:

```javascript
// LLM 시스템 프롬프트에 포함할 API 명세
CopilotCache.get(key)       // → { key, data, url, method, size, menu, timestamp }
CopilotCache.getAll()       // → [Record, ...]
CopilotCache.getByMenu(m)   // → [Record, ...] (특정 메뉴의 데이터만)
```

---

## 6. 전체 데이터 흐름

### 6.1 시나리오 1: 정상 흐름 (소용량 데이터)

```
1. 사용자 → /cost/ 페이지 접속
2. OpsNow App → API 호출 (/api/cost/summary, /api/cost/detail)
3. Network Hook → Axios Interceptor → IndexedDB 저장 (fire-and-forget)
4. 사용자 → Copilot에 "이번달 비용이 얼마야?" 질문
5. Client → Server: query { query, domContext }
6. Server → Client: request_available_data { requestId }
7. Client → Server: available_data { requestId, data: [키 목록] }
8. Server: LLM이 키 목록 보고 필요한 데이터 선택
9. Server → Client: request_api { requestId, dataKey: "/api/cost/summary" }
10. Client: IndexedDB에서 조회 → Server: api_result { data }
11. Server: LLM 응답 생성 → Client: response { answer }
```

### 6.2 시나리오 2: 대용량 데이터 (execute_code)

```
1~7. 동일
8. Server: LLM이 available_data 보고 대용량 판단
9. Server: LLM이 JS 코드 생성 (CopilotCache.get 포함)
10. Server → Client: execute_code { requestId, code }
11. Client: 코드 실행 → 필요한 부분만 추출
12. Client → Server: code_result { result: 추출된 데이터 }
13. Server: LLM 응답 생성 → Client: response { answer }
```

### 6.3 시나리오 3: 캐시 없음 (Smart Fallback)

```
1. 사용자 → 정적 페이지 접속 (API 호출 없음)
2. 사용자 → Copilot에 질문
3. Server → Client: request_available_data
4. Client → Server: available_data { data: [] }   ← 빈 목록
5. Server: Smart Fallback → 관련 메뉴 링크 안내
```

### 6.4 시나리오 4: 메뉴 이동

```
1. /cost/ 페이지 → IndexedDB에 cost 데이터 저장
2. /asset/ 페이지로 이동
3. Network Hook: 메뉴 변경 감지 → /cost/ 데이터 삭제
4. /asset/ API 응답 → IndexedDB에 저장
5. Copilot 질문 → 현재 메뉴(/asset/) 데이터만 조회됨
```

---

## 7. 보안

### 7.1 One-Time Token (requestId)

모든 콜백은 `requestId`로 요청-응답을 매칭. 1회 사용 후 폐기.

```
{timestamp_ms}-{random_urlsafe}
예: 1705123456789-abc123def456ghi789
```

| 위협 | 대응 |
|------|------|
| Replay Attack | 사용 즉시 폐기 (1회용) |
| 토큰 예측 | `secrets.token_urlsafe` (암호학적 안전) |
| 오래된 토큰 | 타임스탬프 검증 |

### 7.2 execute_code 보안

| 위협 | 대응 |
|------|------|
| 악성 코드 실행 | `CopilotCache`만 접근 가능 (DOM, window 접근 차단) |
| 무한 루프 | 타임아웃 10초 |
| 에러 전파 | try-catch 격리 → 원본 페이지 영향 없음 |
| 프로덕션 | Web Worker 격리 (별도 스레드, DOM 접근 원천 차단) |

### 7.3 데이터 보안

| 항목 | 정책 |
|------|------|
| 저장 대상 | API 응답 데이터만 (인증 토큰 등 제외) |
| 저장 위치 | 브라우저 IndexedDB (로컬, 서버 전송 X) |
| 자동 만료 | TTL 5분 |
| 메뉴 이동 삭제 | 이전 메뉴 데이터 즉시 삭제 |

---

## 8. 성능 (PoC 검증 결과)

### 8.1 Network Hook 오버헤드

| 테스트 | 결과 |
|--------|------|
| 1KB x 100건 | < 1ms 오버헤드 |
| 100KB x 20건 | < 1ms 오버헤드 |
| 5MB x 5건 | < 1ms 오버헤드 |
| 동시 10건 | 모든 건 정상 저장 |

> fire-and-forget 패턴: 비동기 저장이 응답 반환을 블로킹하지 않음

### 8.2 메시지 크기 제한

| 메시지 | 권장 최대 |
|--------|----------|
| `available_data` | 10KB (키 목록) |
| `api_result` | 100KB (초과 시 execute_code 전환) |
| `code_result` | 1KB (추출 결과만) |

---

## 9. 구현 항목 정리

### 9.1 클라이언트 모듈 (PoC → 프로덕션 전환)

| 모듈 | PoC 완료 | 프로덕션 추가 작업 |
|------|----------|-------------------|
| `copilot-cache.js` | IndexedDB CRUD + 관리 정책 | TypeScript 전환, 설정 외부화 |
| `copilot-network-hook.js` | fetch/XHR 오버라이드 + 필터링 | **Axios Interceptor로 전환** (공통 axios 통일 후) |
| `copilot-ws-handler.js` | WebSocket 콜백 처리 | Web Worker sandbox, 재연결 로직 |

### 9.2 서버 모듈 (신규 구현)

| 모듈 | 설명 |
|------|------|
| WebSocket 엔드포인트 | FastAPI WebSocket + PendingCallbacks |
| 콜백 요청 함수 | `request_available_data()`, `request_api()`, `execute_code()` |
| LLM 코드 생성 | available_data 스키마 기반 JS 코드 생성 프롬프트 |
| Smart Fallback | IndexedDB 데이터 없을 때 관련 메뉴 안내 |

### 9.3 배포

| 항목 | 방법 |
|------|------|
| 클라이언트 스크립트 | Copilot 위젯과 함께 배포 |
| OpsNow 연동 (PoC) | `index.html`에 `<script>` 태그 추가 (프론트엔드 팀) |
| OpsNow 연동 (Interceptor 전환 후) | Copilot 위젯 초기화 시 `getAxios().interceptors.response.use()` 등록 |

### 9.4 Axios Interceptor 전환 계획

공통 axios (`getAxios()`) 통일 후 Network Hook을 Axios Interceptor로 전환 예정.

| 항목 | 변경 내용 |
|------|----------|
| 교체 대상 | `copilot-network-hook.js` **1개 모듈만** |
| 변경 없음 | `copilot-cache.js`, `copilot-ws-handler.js`, 서버 전체 |
| 로드 순서 | 의존성 없어짐 |
| Sentry 충돌 | 제거됨 |
| response 접근 | `response.data` 직접 (clone 불필요) |
