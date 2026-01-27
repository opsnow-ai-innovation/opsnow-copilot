# IndexedDB Cache PoC 실행 계획

> `analysis/indexeddb_caching_approaches.md` 분석 문서 기반 단계별 검증 계획

---

## 1. PoC 목표

방식 5 (Global Network Override)가 OpsNow 프론트엔드 환경에서 실제로 동작하는지 검증:

| Phase | 검증 항목 | 설명 | 상태 |
|-------|-----------|------|------|
| 1 | Network Override + IndexedDB 기본 | fetch/XHR 오버라이드 → IndexedDB 저장/조회 | ✅ 완료 |
| 2 | 선별 저장 및 데이터 관리 | URL 필터링, 덮어쓰기, TTL, 용량 관리, 중복 방지 | ✅ 완료 |
| 3 | 안정성 및 충돌 검증 | Sentry 충돌, 에러 격리, 성능, 대용량 응답 | ✅ 완료 |
| 4 | WebSocket 콜백 연동 | request_available_data → IndexedDB 조회 → available_data 응답 | ✅ 완료 |

---

## 2. 단계별 실행 계획

### Phase 1: Network Override + IndexedDB 기본

**목표**: fetch/XHR 오버라이드로 API 응답을 가로채고 IndexedDB에 저장/조회하는 기본 흐름 검증

```
phase1_basic/
├── copilot-network-hook.js    # fetch + XHR 오버라이드
├── copilot-cache.js           # IndexedDB CRUD 모듈
├── mock-api-server.js         # 테스트용 API 서버 (Express 또는 간단한 서버)
└── test.html                  # 브라우저 테스트 페이지
```

**검증 항목**:
- [ ] IndexedDB 데이터베이스 생성 (`copilot-cache` DB, `api-responses` store)
- [ ] ⛔ `window.fetch` 오버라이드 → 응답 가로채기 → IndexedDB 저장 — *Interceptor 전환 시 불필요*
- [ ] ⛔ `XMLHttpRequest.prototype` 오버라이드 → 응답 가로채기 → IndexedDB 저장 — *Interceptor 전환 시 불필요*
- [ ] ⛔ Axios adapter 런타임 확인 (실제로 xhr/fetch 중 어느 것이 사용되는지) — *Interceptor 전환 시 불필요*
- [ ] ⛔ 스크립트 로드 순서 검증 (network hook이 Axios보다 먼저 로드되어야 fetch adapter override 적용) — *Interceptor 전환 시 불필요 (로드 순서 의존 없음)*
- [ ] 저장된 데이터 조회 (key로 읽기)
- [ ] 원본 응답이 변경 없이 반환되는지 확인

**테스트 구성**:

#### 1-1. fetch Override 테스트 — ⛔ Interceptor 전환 시 전체 불필요

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| ⛔ fetch GET 요청 | `fetch('/api/cost/summary')` | 응답 반환 + IndexedDB 저장 |
| ⛔ fetch POST 요청 | `fetch('/api/cost/detail', {method: 'POST'})` | 응답 반환 + IndexedDB 저장 |
| ⛔ 원본 응답 무결성 | 오버라이드 전후 response 비교 | 동일 |
| ⛔ 비대상 URL | `fetch('/auth/token')` | 응답 반환, IndexedDB 저장 안 됨 |

#### 1-2. XHR Override 테스트 — ⛔ Interceptor 전환 시 전체 불필요

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| ⛔ XHR GET 요청 | `xhr.open('GET', '/api/asset/list')` | 응답 반환 + IndexedDB 저장 |
| ⛔ XHR POST 요청 | `xhr.open('POST', '/api/asset/detail')` | 응답 반환 + IndexedDB 저장 |
| ⛔ 원본 응답 무결성 | `xhr.responseText` 변경 없음 | 동일 |
| ⛔ 비대상 URL | `xhr.open('GET', '/auth/token')` | 응답 반환, IndexedDB 저장 안 됨 |

#### 1-3. Axios adapter 확인 테스트 — ⛔ Interceptor 전환 시 전체 불필요

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| ⛔ Axios 기본 요청 | `axios.get('/api/cost/summary')` | fetch/XHR 중 어느 것이 트리거되는지 확인 |
| ⛔ adapter 명시 `xhr` | `axios.get(url, {adapter: 'xhr'})` | XHR override가 트리거됨 |
| ⛔ adapter 명시 `fetch` | `axios.get(url, {adapter: 'fetch'})` | fetch override가 트리거됨 |
| ⛔ 동시 트리거 확인 | 하나의 요청에 fetch + XHR 모두 트리거 여부 | **하나만** 트리거되어야 함 |
| ⛔ 로드 순서: hook 먼저 | network hook → Axios 순서 로드 후 `adapter: 'fetch'` | fetch override 트리거됨 |
| ⛔ 로드 순서: Axios 먼저 | Axios → network hook 순서 로드 후 `adapter: 'fetch'` | fetch override **트리거 안 됨** (Axios가 원본 fetch 캡처) |

---

### Phase 2: 선별 저장 및 데이터 관리

**목표**: 원하는 데이터만 선별 저장하고, TTL/용량/중복 관리 정책 검증

```
phase2_management/
├── copilot-network-hook.js    # Phase 1에서 필터링 로직 추가
├── copilot-cache.js           # 관리 정책 포함 IndexedDB 모듈
├── mock-api-server.js         # 테스트용 API 서버
└── test.html                  # 브라우저 테스트 페이지
```

**검증 항목**:
- [ ] URL 패턴 필터링 (`/cost/`, `/asset/`, `/billing/` 등)
- [ ] HTTP 메서드 필터링 (GET만 저장 등)
- [ ] 응답 상태 필터링 (200~299만 저장)
- [ ] Content-Type 필터링 (`application/json`만 저장)
- [ ] 대용량 응답 스킵 (크기 상한)
- [ ] 동일 URL 덮어쓰기 (최신 데이터 유지)
- [ ] TTL 기반 자동 만료
- [ ] 저장 건수/용량 상한 관리
- [ ] 리트라이 중복 저장 방지 (짧은 시간 내 동일 URL 무시)
- [ ] 메뉴별 데이터 분리 (`location.pathname` 키 포함)
- [ ] 메뉴 변경 감지 (`popstate`, `pushState/replaceState` 래핑)
- [ ] 메뉴 변경 시 이전 메뉴 데이터 삭제 정책 (즉시 삭제 / TTL 유지 / 선택적 보존)
- [ ] IndexedDB 저장 키 설계 검증 (URL + params 조합)

**테스트 구성**:

#### 2-1. 필터링 테스트

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 대상 URL | `/cost/summary` 요청 | IndexedDB 저장 |
| 비대상 URL | `/auth/token` 요청 | IndexedDB 저장 안 됨 |
| GET 메서드 | `GET /cost/summary` | 저장 |
| DELETE 메서드 | `DELETE /cost/item/123` | 저장 안 됨 (정책에 따라) |
| 에러 응답 | `500 Internal Server Error` | 저장 안 됨 |
| 비 JSON 응답 | `Content-Type: text/html` | 저장 안 됨 |
| 대용량 응답 | 10MB 초과 JSON | 저장 안 됨 (스킵) |

#### 2-2. 데이터 관리 테스트

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 덮어쓰기 | 같은 URL 2회 요청 | 최신 데이터만 존재 |
| TTL 만료 | 저장 후 TTL 경과 | 조회 시 만료 데이터 제거 |
| 용량 초과 | 상한 초과 저장 시도 | 오래된 항목부터 제거 |
| 리트라이 중복 | 1초 내 동일 URL 3회 요청 | 1건만 저장 |
| 메뉴별 분리 | `/cost/` 페이지와 `/asset/` 페이지 | 각각 독립 저장 |
| 단일 메뉴 다수 API | 하나의 메뉴에서 5~10건 API 호출 | 전부 저장, 메뉴별 키 목록 정확 |

#### 2-3. 메뉴 변경 시 삭제 정책 테스트

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| 메뉴 변경 감지 | `/cost/` → `/asset/` 이동 | `popstate` 또는 `pushState` 래핑으로 변경 감지 |
| 즉시 삭제 | 메뉴 이동 시 이전 메뉴 데이터 삭제 | `/cost/` 관련 데이터 전부 삭제, `/asset/` 데이터만 존재 |
| 이전 메뉴 데이터 조회 | 삭제 전 이전 메뉴의 저장 키 목록 확인 | `menu` 인덱스로 해당 메뉴 데이터만 정확히 조회 |
| 현재 메뉴 데이터 유지 | 이전 메뉴 삭제 후 현재 메뉴 데이터 확인 | 현재 메뉴 데이터 영향 없음 |
| SPA 라우팅 호환 | React Router의 `pushState`/`replaceState` 감지 | History API 래핑으로 정상 감지 |
| 빠른 연속 이동 | `/cost/` → `/asset/` → `/billing/` 빠르게 이동 | 각 단계마다 이전 데이터 정상 삭제 |

---

### Phase 3: 안정성 및 충돌 검증

**목표**: 실제 운영 환경에서 발생할 수 있는 충돌, 성능 문제, 에러 격리 검증

```
phase3_stability/
├── copilot-network-hook.js    # Phase 2에서 에러 격리 강화
├── copilot-cache.js           # 안정성 강화 IndexedDB 모듈
├── mock-api-server.js         # 다양한 응답 시뮬레이션
└── test.html                  # 브라우저 테스트 페이지
```

**검증 항목**:
- [ ] ⛔ Sentry SDK와 fetch/XHR 오버라이드 충돌 여부 — *Interceptor 전환 시 불필요 (fetch/XHR 래핑 안 함)*
- [ ] ⛔ 다른 모니터링 라이브러리 공존 여부 — *Interceptor 전환 시 불필요 (동일 이유)*
- [ ] IndexedDB 저장 실패 시 원본 응답에 영향 없음 (에러 격리)
- [ ] IndexedDB quota 초과 시 graceful 처리
- [ ] 대용량 응답 (1MB, 5MB, 10MB) 파싱 성능
- [ ] 동시 다발 요청 (10건+) 시 성능 영향
- [ ] fire-and-forget 패턴 확인 (비동기 저장이 응답 지연을 유발하지 않음)
- [ ] ⛔ `response.clone()` (fetch) / `responseText` 복사 (XHR) 메모리 영향 — *Interceptor 전환 시 불필요 (response.data 직접 접근)*

**테스트 구성**:

#### 3-1. 충돌 테스트 — ⛔ Interceptor 전환 시 전체 불필요

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| ⛔ Sentry 초기화 후 override | Sentry SDK 로드 → copilot hook 로드 | 양쪽 모두 정상 동작 |
| ⛔ override 후 Sentry 초기화 | copilot hook 로드 → Sentry SDK 로드 | 양쪽 모두 정상 동작 |
| ⛔ 이중 override 순서 무관 | 로드 순서 변경 | 양쪽 모두 정상 동작 |

#### 3-2. 에러 격리 테스트

| 테스트 | 설명 | 예상 결과 |
|-------|------|----------|
| IndexedDB 저장 실패 | DB 접근 에러 강제 발생 | 원본 응답 정상 반환 |
| JSON 파싱 실패 | 비정상 JSON 응답 | 원본 응답 정상 반환, 저장 스킵 |
| IndexedDB quota 초과 | 대량 데이터로 quota 도달 | 원본 응답 정상 반환, 저장 스킵 |

#### 3-3. 성능 테스트

| 테스트 | 설명 | 측정 항목 |
|-------|------|----------|
| 소형 응답 (1KB) | 100건 연속 요청 | 오버라이드 유/무 응답 시간 차이 |
| 중형 응답 (100KB) | 20건 연속 요청 | 오버라이드 유/무 응답 시간 차이 |
| 대형 응답 (5MB) | 5건 연속 요청 | 메모리 사용량, 응답 시간 차이 |
| 동시 요청 (10건) | Promise.all 10건 | 응답 시간 차이, 모든 건 저장 확인 |

**성능 기준**: 오버라이드로 인한 응답 지연 **1ms 미만** (fire-and-forget이므로)

---

### Phase 4: WebSocket 콜백 연동

**목표**: Copilot 서버의 WebSocket 콜백으로 IndexedDB 데이터를 조회하여 응답하는 End-to-End 흐름 검증

```
phase4_integration/
├── copilot-network-hook.js    # Phase 3 최종 버전
├── copilot-cache.js           # Phase 3 최종 버전
├── copilot-ws-handler.js      # WebSocket 콜백 → IndexedDB 조회 핸들러
├── mock-api-server.js         # 테스트용 API 서버
├── ws-server.py               # WebSocket 서버 (poc_1_web_socket 기반)
└── test.html                  # 통합 테스트 페이지
```

**검증 항목**:
- [ ] `request_available_data` 수신 → IndexedDB 키 목록 조회 → `available_data` 응답
- [ ] `request_api` 수신 → IndexedDB에서 해당 데이터 조회 → `api_result` 응답
- [ ] `execute_code` 수신 → 클라이언트에서 코드 실행 → `execute_result` 응답
- [ ] `execute_code` 실행 에러 시 → 에러 메시지 응답 (원본 페이지 영향 없음)
- [ ] IndexedDB에 데이터 없을 때 → 빈 목록/null 응답
- [ ] 전체 흐름: 페이지 렌더링 → API 응답 저장 → Copilot 질문 → 서버 콜백 → IndexedDB 조회 → 응답

**테스트 시나리오**:

```
시나리오 1: 정상 흐름
  1. 페이지 로드 → API 호출 (/cost/summary, /cost/trend)
  2. Network Override → IndexedDB에 2건 저장
  3. 사용자: "이번달 비용이 얼마야?" (WebSocket query)
  4. 서버: request_available_data 전송
  5. 클라이언트: IndexedDB 키 목록 조회 → available_data 응답
     { keys: ["/cost/summary", "/cost/trend"] }
  6. 서버: request_api 전송 (query: "/cost/summary")
  7. 클라이언트: IndexedDB에서 /cost/summary 데이터 조회 → api_result 응답
  8. 서버: LLM으로 응답 생성 → response 전송

시나리오 2: 캐시 없음
  1. 페이지 로드 (API 호출 없는 정적 페이지)
  2. 사용자: "비용 데이터 보여줘" (WebSocket query)
  3. 서버: request_available_data 전송
  4. 클라이언트: IndexedDB 비어 있음 → available_data 응답
     { keys: [] }
  5. 서버: Smart Fallback → 관련 메뉴 안내

시나리오 3: 메뉴 이동 후 데이터 갱신
  1. /cost/ 페이지 → API 응답 저장
  2. /asset/ 페이지로 이동 → 새 API 응답 저장
  3. Copilot 질문 → 현재 페이지(/asset/) 관련 데이터만 조회

시나리오 4: execute_code — 서버가 클라이언트에 코드 실행 요청
  1. 페이지 로드 → API 호출 → IndexedDB 저장
  2. 사용자: "비용 상위 3개 서비스 알려줘" (WebSocket query)
  3. 서버: execute_code 전송
     { code: "return await CopilotCache.get('/api/cost/summary')" }
  4. 클라이언트: 코드 실행 → execute_result 응답
     { result: { totalCost: 125340.5, breakdown: [...] } }
  5. 서버: LLM으로 응답 생성

시나리오 5: execute_code — 에러 격리
  1. 서버: execute_code 전송 (잘못된 코드)
     { code: "undefinedFunction()" }
  2. 클라이언트: 실행 에러 → execute_result 응답
     { error: "undefinedFunction is not defined" }
  3. 원본 페이지 동작에 영향 없음
```

---

## 3. 기술 스택

| 구분 | 기술 |
|------|------|
| Network Override | 브라우저 네이티브 fetch/XMLHttpRequest |
| Storage | IndexedDB (브라우저 네이티브) |
| Mock API Server | Express.js 또는 Python http.server |
| WebSocket 연동 | poc_1_web_socket 통합 버전 활용 |
| 테스트 | 브라우저 콘솔 + 테스트 페이지 |

---

## 4. 실행 방법

```bash
# 프로젝트 루트(opsnow-copilot/)에서 이 폴더로 이동
cd poc/a_communication/poc_indexeddb_cache

# Phase 1~3: Mock API 서버 실행 후 브라우저 테스트
node phase1_basic/mock-api-server.js       # Phase 1
node phase2_management/mock-api-server.js  # Phase 2
node phase3_stability/mock-api-server.js   # Phase 3
open http://localhost:3456/test.html

# Phase 4: 두 서버 모두 실행 필요
node phase4_integration/mock-api-server.js   # 터미널 1 — API 서버 (포트 3456)
python phase4_integration/ws-server.py       # 터미널 2 — WebSocket 서버 (포트 8765)
open http://localhost:3456/test.html
```

---

## 5. 성공 기준

| Phase | 성공 기준 | Interceptor 전환 시 | 상태 |
|-------|-----------|---------------------|------|
| Phase 1 | fetch/XHR 오버라이드로 IndexedDB 저장/조회 성공, 원본 응답 무결성 확인 | ⛔ Override 테스트 ~80% 불필요, IndexedDB 기본만 유효 | ✅ 완료 |
| Phase 2 | URL 필터링, 덮어쓰기, TTL, 중복 방지 정책 동작 확인 | ✅ 전부 유효 | ✅ 완료 |
| Phase 3 | Sentry 공존 확인, 에러 격리 100%, 응답 지연 1ms 미만 | ⛔ Sentry 충돌 테스트 불필요 (~30% 감소) | ✅ 완료 |
| Phase 4 | WebSocket 콜백으로 IndexedDB 데이터 조회 → 서버 응답 End-to-End 성공 | ✅ 전부 유효 | ✅ 완료 |

---

## 6. 폴더 구조 (최종)

```
poc/a_communication/poc_indexeddb_cache/
├── README.md                             # 실행 방법 및 테스트 항목 안내
├── poc_plan.md                           # 이 문서
├── analysis/                             # 사전 분석 문서
│   ├── indexeddb_caching_approaches.md   # 방식 분석 문서
│   └── axios_direct_create_files.md      # axios.create() 직접 사용 파일 목록
├── design/                               # 설계 문서
│   ├── indexeddb_cache_design.md         # 설계서 (Markdown)
│   └── indexeddb_cache_design.html       # 설계서 (HTML, Mermaid 다이어그램)
├── phase1_basic/                         # Network Override + IndexedDB 기본
│   ├── copilot-network-hook.js
│   ├── copilot-cache.js
│   ├── mock-api-server.js
│   └── test.html
├── phase2_management/                    # 선별 저장 및 데이터 관리
│   ├── copilot-network-hook.js
│   ├── copilot-cache.js
│   ├── mock-api-server.js
│   └── test.html
├── phase3_stability/                     # 안정성 및 충돌 검증
│   ├── copilot-network-hook.js
│   ├── copilot-cache.js
│   ├── mock-api-server.js
│   └── test.html
└── phase4_integration/                   # WebSocket 콜백 연동
    ├── copilot-network-hook.js
    ├── copilot-cache.js
    ├── copilot-ws-handler.js
    ├── mock-api-server.js
    ├── ws-server.py
    └── test.html
```

---

## 7. 현재 진행 상황

- [x] Phase 1: Network Override + IndexedDB 기본
- [x] Phase 2: 선별 저장 및 데이터 관리
- [x] Phase 3: 안정성 및 충돌 검증
- [x] Phase 4: WebSocket 콜백 연동

---

## 8. PoC에서 확인된 사항

### 스크립트 로드 순서 제약 — ⛔ Interceptor 전환 시 해당 없음

- `copilot-network-hook.js`는 Axios보다 **먼저** 로드해야 함
- Axios가 먼저 로드되면 원본 `fetch` 참조를 캡처하여 fetch adapter override가 적용되지 않음
- XHR adapter는 prototype 오버라이드이므로 로드 순서 무관
- **→ Interceptor 방식은 로드 순서 의존성 자체가 없음**

### 공통 Axios 통일 시 인터셉터 전환 권장

현재 PoC는 Network Override (fetch/XHR 래핑) 방식이나, 공통 axios(`getAxios()`) 통일이 완료되면 **Axios Interceptor 방식으로 전환**이 더 안정적:

| 비교 | Network Override (현재 PoC) | Axios Interceptor (전환 대상) |
|------|---------------------------|------------------------------|
| 로드 순서 의존 | Axios보다 먼저 로드 필수 | 없음 |
| Sentry 등 충돌 위험 | fetch/XHR 래핑 충돌 가능 | 없음 |
| response.clone() 필요 | O | X (interceptor가 직접 data 접근) |
| 커버리지 | 모든 HTTP 요청 | getAxios() 경유만 |
| 코드 변경 필요 | 없음 | 공통 axios 통일 필요 |

> 결론: PoC는 코드 변경 없이 동작하는 Network Override로 검증하고, 공통 axios 통일 후 `getAxios().interceptors.response.use()` 방식으로 전환

### Interceptor 전환 시 불필요해지는 PoC 항목 요약

| Phase | 불필요 항목 | 이유 |
|-------|-----------|------|
| Phase 1 | fetch Override 테스트 (1-1 전체) | fetch 래핑 안 함 |
| Phase 1 | XHR Override 테스트 (1-2 전체) | XHR 래핑 안 함 |
| Phase 1 | Axios adapter 확인 테스트 (1-3 전체) | adapter 무관하게 interceptor에서 처리 |
| Phase 1 | 스크립트 로드 순서 검증 | 로드 순서 의존성 없음 |
| Phase 3 | Sentry/모니터링 충돌 테스트 (3-1 전체) | fetch/XHR 래핑 안 하므로 충돌 원인 없음 |
| Phase 3 | `response.clone()` 메모리 영향 | `response.data` 직접 접근, clone 불필요 |
| Phase 2 | — | 전부 유효 (데이터 관리 정책은 방식 무관) |
| Phase 4 | — | 전부 유효 (WebSocket 연동은 방식 무관) |

> Phase 1 ~80%, Phase 3 ~30% 항목이 불필요해짐. Phase 2, Phase 4는 전부 유효.

---

## 9. PoC 완료 후 다음 단계

1. 검증된 `copilot-network-hook.js`를 Copilot 위젯 배포 패키지에 포함
2. OpsNow `index.html`에 `<script>` 태그 1줄 추가 요청 (프론트엔드 팀) — **Axios보다 먼저 로드**
3. poc_1_web_socket의 콜백 패턴과 통합하여 실제 데이터 흐름 구성
4. `copilot-cache.js`를 Copilot 위젯 내 WebSocket 핸들러와 연동
5. 공통 axios 통일 완료 시 Axios Interceptor 방식으로 전환 검토
