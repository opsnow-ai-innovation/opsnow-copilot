# OpsNow Copilot PoC 프로젝트 계획

> 기술 검증 및 프로토타입 개발을 위한 파트별 PoC 프로젝트 정의

## 개요

전체 시스템을 한 번에 구현하지 않고, **핵심 기술 영역별로 분리하여 독립적으로 검증**합니다.
각 PoC는 독립 실행 가능하며, 검증 완료 후 통합합니다.

| OpsNow Copilot 전체 | | |
|---------------------|---------------------|---------------------|
| PoC-1: WebSocket | PoC-2: Memory RAG | PoC-3: ReAct |
| PoC-4: DOM 전처리 | PoC-5: ask_human | PoC-6: request_api |
| PoC-7: FAQ/Manual RAG | PoC-8: Platform Menu API | |

---

## PoC 프로젝트 구조

```
OpsNow Copilot PoC
│
├─ A. 클라이언트-서버 통신 계층
│   ├─ PoC-1: WebSocket 스트리밍 (기반)
│   │   ├─ Server→Client→Server 콜백 패턴 (asyncio.Future)
│   │   └─ One-Time Token 보안 (콜백 응답 검증)
│   └─ PoC-4: DOM 전처리 (Client → Server)
│
├─ B. AI 추론 엔진 & 도구
│   ├─ PoC-3a: DSPy 프레임워크 리서치 (기반)
│   ├─ PoC-3b: ReAct Loop 구현
│   ├─ PoC-5: Human Feedback Tool (ask_human)
│   └─ PoC-6: API Request Tool (request_api)
│
└─ C. 지식 & 메모리 관리
    ├─ PoC-2: Memory as RAG (대화 히스토리)
    ├─ PoC-7: FAQ/Manual RAG (정적 지식)
    └─ PoC-8: Platform Menu API (메뉴 정보 → Smart Fallback)
```

---

## PoC 프로젝트 목록

### A. 클라이언트-서버 통신 계층

| PoC | 이름 | 핵심 검증 항목 | 의존성 |
|-----|------|---------------|--------|
| 1 | WebSocket 스트리밍 | 양방향 통신, LLM 스트리밍 | 없음 (기반) |
| 4 | DOM 전처리 | HTML 파싱, 비용 메트릭 추출 | PoC-1 |

### B. AI 추론 엔진 & 도구

| PoC | 이름 | 핵심 검증 항목 | 의존성 |
|-----|------|---------------|--------|
| 3a | DSPy 프레임워크 리서치 | Signature, Module, Optimizer | 없음 (기반) |
| 3b | ReAct Loop 구현 | 다단계 추론, 도구 호출 | PoC-3a |
| 5 | Human Feedback Tool | ask_human 도구, 타임아웃 | PoC-3b |
| 6 | API Request Tool | request_api 도구, 추가 데이터 요청 | PoC-3b, PoC-1 |

### C. 지식 & 메모리 관리

| PoC | 이름 | 핵심 검증 항목 | 의존성 |
|-----|------|---------------|--------|
| 2 | Memory as RAG | 대화 히스토리 관리, 토큰 절감 | 없음 |
| 7 | FAQ/Manual RAG | 정적 지식 검색, Agentic RAG | 없음 |
| 8 | Platform Menu API | 메뉴 정보 조회, Smart Fallback | 없음 |

---

## PoC-1: WebSocket 스트리밍

### 목적
FastAPI WebSocket + LLM 스트리밍 응답 검증

### 검증 항목
- [ ] WebSocket 연결/해제 처리
- [ ] LLM 스트리밍 응답 청크 전송
- [ ] 연결 상태 관리 (ConnectionManager)
- [ ] 에러 핸들링 및 재연결
- [ ] Server→Client→Server 콜백 패턴 (asyncio.Future 기반)
- [ ] One-Time Token 발급/검증/폐기

### 기술 스택
```
FastAPI + uvicorn
OpenAI API (streaming=True)
websockets
```

### 콜백 패턴: Server→Client→Server

서버 함수가 클라이언트 데이터를 요청하고, 응답을 받아 리턴하는 패턴 (asyncio.Future 기반)

**흐름:**
1. 서버: Future 생성 + 요청 전송
2. 서버: await future (클라이언트 응답 대기)
3. 클라이언트: 데이터 수집 → 응답 전송
4. 서버: future.set_result() → 리턴

**활용처:**
- PoC-5 (ask_human): 사용자 입력 대기
- PoC-6 (request_api): API 데이터 대기

### 보안: One-Time Token 패턴

서버 → 클라이언트 콜백 요청 시 일회용 토큰으로 응답 검증

**흐름:**
1. 서버 → 클라: 요청 + 일회용 토큰 발급
2. 클라 → 서버: 응답 + 토큰 첨부
3. 서버: 토큰 검증 후 즉시 폐기 (1회용)

**보안 효과:**

| 공격 유형 | 방어 |
|----------|------|
| Replay Attack | ✅ 완전 차단 (1회용) |
| 토큰 탈취 후 사용 | ✅ 즉시 만료로 무의미 |
| 위조 응답 주입 | ✅ 토큰 없으면 거부 |

---

## PoC-2: In-Memory Vector RAG (대화 히스토리 관리)

### 목적
대화 히스토리를 벡터 검색으로 관리하여 토큰 사용량 91% 절감 검증

### 배경: Memory as RAG

| 기존 방식 | Memory as RAG |
|----------|---------------|
| 전체 히스토리 전송 | 3-Layer 구조 |
| Turn 50 시 ~15,000 토큰 | Short-term (최근 3턴): ~600 토큰 |
| | Long-term (관련 3턴 벡터 검색): ~600 토큰 |
| | Entity Memory: ~50 토큰 |
| **비용 높음** | **총 ~1,350 토큰 (91%↓)**

### 검증 항목
- [ ] 3-Layer Memory 구조 (Short-term / Long-term / Entity)
- [ ] 대화 턴 임베딩 및 벡터 검색
- [ ] 시간 참조 키워드 감지 ("이전", "아까", "그거")
- [ ] Hybrid Retrieval (시간 + 유사도)
- [ ] 토큰 절감률 측정
- [ ] Redis 저장/조회
  - [ ] gzip 압축 적용 (저장 시 압축, 조회 시 해제)
  - [ ] 세션별 키 관리

### 기술 스택
```
sentence-transformers
numpy
redis
```

---

## PoC-3a: DSPy 프레임워크 리서치

### 목적
DSPy 프레임워크 핵심 개념 학습 및 기본 패턴 검증

### 배경: DSPy "No Framework" 철학

| 기존 방식 (LangChain 등) | DSPy 방식 |
|-------------------------|-----------|
| 프롬프트 수동 작성 | Signature: 입출력 선언만 정의 |
| 프롬프트 엔지니어링 반복 | Module: 로직 구조화 |
| 체인 구조 하드코딩 | Optimizer: 프롬프트 자동 최적화 |

**핵심:** "프롬프트 작성" 대신 "동작 정의"

### 검증 항목
- [ ] DSPy 설치 및 LLM 연동 (OpenAI, Anthropic)
- [ ] Signature 정의 패턴 이해
- [ ] Module 구현 패턴 (dspy.Module, forward)
- [ ] ChainOfThought, ReAct 내장 모듈 테스트
- [ ] Optimizer 기본 사용법 (BootstrapFewShot)
- [ ] 로컬 LLM 연동 테스트 (LM Studio)

### 기술 스택
```
dspy-ai
openai / anthropic
```

---

## PoC-3b: ReAct Loop 구현

### 목적
다단계 추론 (Reason → Act → Observe → Reflect) 구현

### 검증 항목
- [ ] ReAct Signature 정의
- [ ] ReAct Agent Module 구현
- [ ] 도구 호출 파싱 및 실행
- [ ] 반복 종료 조건 (MAX_ITERATIONS, confidence)
- [ ] 무한 루프 방지

### 기술 스택
```
openai / anthropic
```

---

## PoC-4: DOM 전처리

### 목적
OpsNow 화면 HTML에서 비용/자산 정보 추출 검증

### 검증 항목
- [ ] BeautifulSoup HTML 파싱
- [ ] 비용 메트릭 추출 ($숫자 패턴)
- [ ] 테이블 데이터 구조화
- [ ] 불필요한 요소 제거 (스크립트, 스타일)
- [ ] 토큰 압축률

### 기술 스택
```
beautifulsoup4
lxml
```

---

## PoC-5: Human Feedback Tool

### 목적
WebSocket 기반 사용자 되물음 및 응답 대기 검증

### 검증 항목
- [ ] clarification_request 메시지 전송
- [ ] 사용자 응답 대기 (asyncio.Future)
- [ ] 타임아웃 처리 (30초)
- [ ] 기본값 폴백
- [ ] 위험도 기반 자동 트리거
  - [ ] 위험도 레벨 정의 (critical, high, medium, low)
  - [ ] 위험도별 확인 조건 (critical: 항상, high: 신뢰도<80%, 등)

### 기술 스택
```
FastAPI + WebSocket
asyncio
```

---

## PoC-6: API Request Tool (request_api)

### 목적
AI가 추가 데이터가 필요할 때 클라이언트에 요청하는 **통합 도구** 검증

### 배경: 도구 기반 데이터 요청

**흐름:**

| 단계 | 주체 | 동작 |
|------|------|------|
| 1 | LLM | "사용자의 이번달 비용 데이터가 필요합니다" |
| 2 | LLM | `request_api(query="이번달 비용 데이터")` 호출 |
| 3 | Client | 적절한 API 호출 → 결과 반환 |

**특징:**

| 항목 | 설명 |
|------|------|
| API 종류 | 사전 공유 불필요 (보안 우려 해소) |
| LLM 역할 | "무엇이 필요한지"만 자연어로 표현 |
| Client 역할 | 적절한 API 매핑 담당 |
| 고도화 | 구체적 API 최적화는 추후 진행

### 검증 항목
- [ ] request_api 도구 정의 (DSPy Tool)
- [ ] 자연어 기반 데이터 요청
- [ ] WebSocket 메시지 전송/수신
- [ ] 타임아웃 처리 (10초)
- [ ] 에러 핸들링
- [ ] ReAct Loop 내 도구 호출 연동

### 기술 스택
```
dspy-ai (Tool 정의)
FastAPI + WebSocket
JavaScript fetch API
```

---

## PoC-7: FAQ/Manual RAG (정적 지식)

### 목적
FAQ, User Manual 정적 지식을 In-Memory 벡터 검색으로 제공 + Agentic RAG 패턴 검증

### 배경: 정적 지식 vs 동적 메모리

| 구분 | PoC-2: Memory as RAG | PoC-7: FAQ/Manual RAG |
|------|---------------------|----------------------|
| 데이터 | 대화 히스토리 (동적) | FAQ/Manual (정적) |
| 생명주기 | 세션별 생성/소멸 | 서버 시작 시 로드 |
| 특징 | 시간 참조 감지 | Agentic RAG 패턴 |

### 검증 항목
- [ ] In-Memory Vector Store (서버 시작 시 로드)
- [ ] 임베딩 캐싱 (pickle)
- [ ] Hybrid Search (Semantic + Keyword)
- [ ] Agentic RAG 패턴
  - [ ] Document Grader (관련성 평가)
  - [ ] Query Refiner (쿼리 재구성)
  - [ ] Hallucination Checker (환각 검증)
- [ ] Adaptive RAG Gate (RAG 필요 여부 판단)

### 기술 스택
```
sentence-transformers
numpy
pickle
```

---

## PoC-8: Platform Menu API (메뉴 정보)

### 목적
OpsNow 플랫폼 Internal API로 메뉴 정보 조회 + Smart Fallback 활용 검증

### 배경: 메뉴 정보 활용

| 활용처 | 설명 | 예시 |
|--------|------|------|
| Smart Fallback | 처리 불가 질문 → 관련 메뉴 링크 제공 | "비용 분석은 [Cost Explorer] 메뉴에서 확인하세요" |
| 네비게이션 안내 | 메뉴 경로 안내, 권한별 필터링 | "EC2 비용은 어디서 봐?" → 메뉴 경로 제공 |
| 컨텍스트 이해 | 현재 화면 메뉴 파악, 관련 기능 인지 | 하위 메뉴 및 관련 기능 연결 |

### 검증 항목
- [ ] Platform Internal API 연동 (메뉴 목록 조회)
- [ ] 메뉴 정보 캐싱 (Redis 또는 In-Memory)
- [ ] 메뉴 검색 (키워드 → 관련 메뉴)
- [ ] Smart Fallback 응답 생성
- [ ] 메뉴 경로/URL 매핑

### 기술 스택
```
httpx (Internal API 호출)
redis (캐싱, 선택)
```
