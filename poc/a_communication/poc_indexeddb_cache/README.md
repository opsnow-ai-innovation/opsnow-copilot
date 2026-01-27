# IndexedDB Cache PoC

> 방식 5 (Global Network Override) — fetch/XHR 오버라이드로 API 응답을 IndexedDB에 저장하고, Copilot 서버가 WebSocket 콜백으로 조회하는 구조 검증

---

## 실행 방법

### Phase 1: Network Override + IndexedDB 기본

```bash
# 프로젝트 루트(opsnow-copilot/)에서 이 폴더로 이동
cd poc/a_communication/poc_indexeddb_cache

# 1. Mock API 서버 실행
node phase1_basic/mock-api-server.js

# 2. 브라우저에서 테스트 페이지 열기
open http://localhost:3456/test.html
```

브라우저에서 `http://localhost:3456/test.html`을 열어 테스트합니다.
> `file://`로 직접 열면 History API(`pushState`) 등이 동작하지 않습니다.

#### 테스트 항목

| 구분 | 테스트 | 확인 사항 |
|------|--------|----------|
| fetch Override | GET/POST 요청 | IndexedDB 저장 + 원본 응답 무결성 |
| XHR Override | GET/POST 요청 | IndexedDB 저장 + 원본 응답 무결성 |
| 비대상 URL | `/auth/token` 요청 | IndexedDB에 저장되지 않음 |
| Axios adapter | 기본/xhr/fetch | 어느 override가 트리거되는지 확인 |
| 캐시 확인 | 조회/삭제 | IndexedDB CRUD 동작 확인 |

---

### Phase 2: 선별 저장 및 데이터 관리

```bash
# 프로젝트 루트(opsnow-copilot/)에서 이 폴더로 이동
cd poc/a_communication/poc_indexeddb_cache

# 1. Mock API 서버 실행
node phase2_management/mock-api-server.js

# 2. 브라우저에서 테스트 페이지 열기
open http://localhost:3456/test.html
```

#### 테스트 항목

| 구분 | 테스트 | 확인 사항 |
|------|--------|----------|
| 필터링 | 대상/비대상 URL, DELETE 메서드, 500 에러, text/html, 대용량(~6MB) | 조건에 맞는 응답만 저장 |
| 데이터 관리 | 덮어쓰기, 중복 방지(1초 내), TTL 만료 | 정책대로 동작 |
| 메뉴 변경 삭제 | /cost/ → /asset/ → /billing/ 이동 | 이전 메뉴 데이터 삭제, 현재 메뉴 유지 |

---

### Phase 3: 안정성 및 충돌 검증

```bash
# 프로젝트 루트(opsnow-copilot/)에서 이 폴더로 이동
cd poc/a_communication/poc_indexeddb_cache

# 1. Mock API 서버 실행
node phase3_stability/mock-api-server.js

# 2. 브라우저에서 테스트 페이지 열기
open http://localhost:3456/test.html
```

#### 테스트 항목

| 구분 | 테스트 | 확인 사항 |
|------|--------|----------|
| 충돌 테스트 | Sentry Mock 래핑 순서 3종 | fetch/XHR 이중 래핑 공존 확인 |
| 에러 격리 | IndexedDB 강제 에러, JSON 파싱 실패, Quota 초과 | 원본 응답에 영향 없음 (에러 격리 100%) |
| 성능 | 1KB×100, 100KB×20, 5MB×5, 동시 10건 | 오버라이드 오버헤드 측정 |

---

### Phase 4: WebSocket 콜백 연동

```bash
# 프로젝트 루트(opsnow-copilot/)에서 이 폴더로 이동
cd poc/a_communication/poc_indexeddb_cache

# 1. Mock API 서버 실행 (터미널 1)
node phase4_integration/mock-api-server.js

# 2. WebSocket 서버 실행 (터미널 2)
pip install websockets   # 최초 1회
python phase4_integration/ws-server.py

# 3. 브라우저에서 테스트 페이지 열기
open http://localhost:3456/test.html
```

> **두 서버 모두 실행 필요**: Mock API (포트 3456) + WebSocket (포트 8765)

#### 테스트 항목

| 구분 | 테스트 | 확인 사항 |
|------|--------|----------|
| 정상 흐름 | query → request_available_data → request_api → response | End-to-End 콜백 흐름 성공 |
| 캐시 없음 | IndexedDB 비어 있을 때 query | 빈 목록 응답 + Smart Fallback |
| execute_code | 서버가 JS 코드 전송 → 클라이언트 실행 | IndexedDB 데이터에서 결과 추출 |
| execute_code 에러 | 잘못된 코드 실행 | 에러 격리, 페이지 영향 없음 |
| 메뉴 이동 | /cost/ → /asset/ 이동 후 query | 현재 메뉴 데이터만 반환 |

---

## 폴더 구조

```
poc_indexeddb_cache/
├── README.md                 # 이 문서
├── poc_plan.md               # 전체 PoC 실행 계획 (Phase 1~4)
├── analysis/                 # 사전 분석 문서
│   ├── indexeddb_caching_approaches.md
│   └── axios_direct_create_files.md
├── design/                   # 설계 문서
│   ├── indexeddb_cache_design.md    # 설계서 (Markdown)
│   └── indexeddb_cache_design.html  # 설계서 (HTML, Mermaid 다이어그램)
├── phase1_basic/             # Phase 1: Network Override + IndexedDB 기본
│   ├── copilot-cache.js
│   ├── copilot-network-hook.js
│   ├── mock-api-server.js
│   └── test.html
├── phase2_management/        # Phase 2: 선별 저장 및 데이터 관리
│   ├── copilot-cache.js
│   ├── copilot-network-hook.js
│   ├── mock-api-server.js
│   └── test.html
├── phase3_stability/         # Phase 3: 안정성 및 충돌 검증
│   ├── copilot-cache.js
│   ├── copilot-network-hook.js
│   ├── mock-api-server.js
│   └── test.html
└── phase4_integration/       # Phase 4: WebSocket 콜백 연동
    ├── copilot-cache.js          # Phase 3 최종 버전
    ├── copilot-network-hook.js   # Phase 3 최종 버전
    ├── copilot-ws-handler.js     # WebSocket 콜백 → IndexedDB 핸들러
    ├── mock-api-server.js        # API 서버 (포트 3456)
    ├── ws-server.py              # WebSocket 서버 (포트 8765)
    └── test.html                 # 통합 테스트 페이지
```
