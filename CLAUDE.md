# OpsNow Copilot

FinOps AI 어시스턴트 - 화면 맥락 기반 지능형 도우미

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **LLM**: DSPy (No Framework 철학)
- **Communication**: WebSocket
- **Vector Store**: In-Memory (ChromaDB 불필요)
- **Cache**: Redis (대화 히스토리, 메뉴 캐시)

## Architecture

```
main.py              # FastAPI 진입점
src/
├── config.py        # 환경변수, 설정
├── routes/          # API 라우터 (WebSocket 포함)
├── agents/          # ReAct Loop, Agentic 로직
├── rag/             # In-Memory 벡터 저장소, Adaptive RAG
├── tools/           # FinOps API 도구, Human Feedback
├── processors/      # DOM 전처리, 응답 생성
├── prompts/         # 프롬프트 정의
└── utils/           # 로거, 유틸리티
```

## 핵심 코딩 규칙

### 1. 코드 작성 전 필수 확인

- **기존 코드 확인 후 작성** - 중복 코드 생성 절대 금지
- **config.py 상수 사용** - 하드코딩 금지
- **기존 파일 수정 우선** - 새 파일 생성 최소화

### 2. 파일 생성 규칙

- 목표 달성에 절대적으로 필요한 경우에만 새 파일 생성
- 문서 파일(*.md, README) 자동 생성 금지 - 명시적 요청 시에만
- 에이전트 추가 시 `src/agents/` 하위에 배치
- 도구 추가 시 `src/tools/` 하위에 배치

### 3. 로깅

- 프로젝트 공통 로거만 사용
- 별도 로거 생성 금지

### 4. 보안

- 커밋 시 API key, Password 등 민감정보 포함 금지
- .env 파일 커밋 금지

## 핵심 패턴

### ReAct Loop
- Reason → Act → Observe → Reflect 사이클
- MAX_ITERATIONS로 무한 루프 방지
- 상세: `docs/react_loop_guide.md`

### 정보 소스
1. **화면 DOM** (항상 포함, ~2000 토큰)
2. **FAQ/Manual** (벡터 RAG, ~800 토큰)
3. **메뉴 정보** (Fallback용)

### Fallback 전략
- 처리 불가 시 관련 메뉴 링크 제공
- 상세: `docs/info_source_architecture.md`

## 흔한 실수

- 기존 코드 확인 없이 새로운 유틸리티 생성
- config.py 상수 대신 하드코딩
- 시스템 프롬프트에 모든 도구 지시사항 포함 (JIT Instructions 사용할 것)
- 모든 질의에 RAG 호출 (Adaptive RAG Gate 사용할 것)
