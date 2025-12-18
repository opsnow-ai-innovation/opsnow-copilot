# OpsNow Copilot

> FinOps AI 어시스턴트 - 화면 맥락 기반 지능형 도우미
> Python FastAPI 기반 WebSocket API 서버 + DSPy Agentic AI

## 프로젝트 개요

- **프레임워크**: FastAPI (Python 3.11+)
- **AI 프레임워크**: DSPy (No Framework 철학)
- **통신**: WebSocket (실시간 양방향)
- **벡터 저장소**: In-Memory Vector Store
- **캐시**: Redis (대화 히스토리, 메뉴 캐시 - 선택적)

## 주요 기능

- ✅ 현재 화면 DOM 기반 맥락 인식
- ✅ FAQ/User Manual 벡터 RAG
- ✅ ReAct Loop 다단계 추론
- ✅ Human Feedback (사용자 되물음)
- ✅ FinOps API 요청 (클라이언트 위임)
- ✅ Smart Fallback (관련 메뉴 안내)

## Python 개발환경 설정

### 1. Python 설치
``` bash
# Python 3.11+ 설치 (설치 후 터미널 재시작)
brew install python@3.11

# Python 버전 확인
python3.11 -V
```

### 2. 가상환경 설정
``` bash
# home 이동
cd

# venv 저장 디렉토리 생성 (최초 1회)
mkdir -p venvs

# venvs 디렉토리 이동
cd venvs

# 가상환경 생성
python3.11 -m venv opsnow-copilot

# 가상환경 활성화
source ~/venvs/opsnow-copilot/bin/activate
```

### 3. 소스코드 받기
``` bash
# 프로젝트 저장 위치로 이동
cd ~/IdeaProjects

# 소스코드 받기
git clone https://github.com/opsnow-ai-innovation/opsnow-copilot.git

# 프로젝트 위치로 이동
cd opsnow-copilot
```

### 4. IntelliJ 설정 (선택사항)
1. IntelliJ Python plugin 설치
2. File > Project Structure... > Project > SDK
3. Python 가상환경 지정: `~/venvs/opsnow-copilot/bin/python3`

### 5. Zscaler 인증서 오류 해결 (필요시)
``` bash
# Zscaler 문제해결 가이드 12p 4번 참고
# 인증서를 ~/Downloads 에 다운로드 완료 후

# certifi 패키지 설치/업그레이드
pip install --upgrade certifi

# 인증서 경로 확인
python -m certifi

# 인증서 업데이트
cat ~/Downloads/ZscalerRootCA.pem >> $(python -m certifi)
```

## 의존성 관리

``` bash
# 가상환경 활성화 확인
source ~/venvs/opsnow-copilot/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 의존성 제거
pip uninstall -r requirements.txt -y

# 가상환경 내 모든 패키지 clean uninstall
pip freeze > installed_packages.txt && pip uninstall -y -r installed_packages.txt && rm installed_packages.txt

# (선택) 캐시 제거 후 재설치
pip cache purge
pip install --no-cache-dir -r requirements.txt
```

## 환경 설정

### 환경변수 설정 (로컬 개발)
``` bash
# 필수 환경변수
export PROFILE=dev                    # 환경: dev, prod
export OPENAI_API_KEY=your_api_key    # OpenAI API 키
export ANTHROPIC_API_KEY=your_key     # Anthropic API 키 (선택)

# 선택 환경변수
export REDIS_HOST=localhost           # Redis 호스트 (세션 공유 시)
export LOG_LEVEL=DEBUG                # 로그 레벨
```

### 환경별 프로파일
- `dev`: 개발 환경 (상세 로깅, Hot-Reload)
- `prod`: 운영 환경 (최적화, 멀티 워커)

## 실행 방법

### 방법 1: 로컬 개발 (Hot-Reload)
``` bash
# 가상환경 활성화
source ~/venvs/opsnow-copilot/bin/activate

# Hot-Reload 모드 실행
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 방법 2: 프로덕션 실행
``` bash
# 가상환경 활성화
source ~/venvs/opsnow-copilot/bin/activate

# 멀티 워커 실행
python main.py
```

### Docker 실행
``` bash
# 이미지 빌드
docker build -t opsnow-copilot:latest .

# 컨테이너 실행
docker run -d \
  -p 8000:8000 \
  -e PROFILE=dev \
  -e OPENAI_API_KEY=your_api_key \
  --name opsnow-copilot \
  opsnow-copilot:latest

# 로그 확인
docker logs -f opsnow-copilot
```

## API 엔드포인트

### Health Check
```
GET /health
```

### WebSocket
```
WS /ws/chat
```

### Swagger UI
- 로컬: http://localhost:8000/docs

## 프로젝트 구조

```
opsnow-copilot/
├── main.py                      # FastAPI 진입점
├── Dockerfile                   # 컨테이너 빌드
├── requirements.txt             # Python 의존성
├── src/
│   ├── config.py                # 환경변수, 설정
│   ├── routes/                  # API 라우터 (WebSocket 포함)
│   ├── agents/                  # ReAct Loop, Agentic 로직
│   ├── rag/                     # In-Memory 벡터 저장소, Adaptive RAG
│   ├── tools/                   # FinOps API 도구, Human Feedback
│   ├── processors/              # DOM 전처리, 응답 생성
│   ├── prompts/                 # 프롬프트 정의
│   └── utils/                   # 로거, 유틸리티
├── data/                        # FAQ, Manual 정적 데이터
├── tests/                       # 테스트
├── design/                      # 외부 공유용 문서 (Git 포함)
└── docs/                        # 개발 문서 (로컬 전용)
```

## 핵심 패턴

| 패턴 | 효과 | 설명 |
|------|------|------|
| **JIT Instructions** | 토큰 90%↓ | 도구 호출 시 관련 지시사항만 제공 |
| **Adaptive RAG** | RAG 호출 50-70%↓ | 필요한 경우에만 벡터 검색 |
| **ReAct Loop** | 다단계 추론 | Reason → Act → Observe → Reflect |
| **Memory as RAG** | 토큰 91%↓ | 대화 히스토리 벡터 검색 |
| **Smart Fallback** | UX 향상 | 처리 불가 시 관련 메뉴 안내 |

## 정보 소스 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    OpsNow Copilot                           │
├─────────────────────────────────────────────────────────────┤
│  1. DOM (화면 컨텍스트)  │  항상 포함 (~2000 토큰)          │
│  2. FAQ + User Manual   │  Adaptive RAG로 필요시 조회      │
│  3. 사이트 메뉴 정보     │  Platform API, Fallback용       │
└─────────────────────────────────────────────────────────────┘
```

## 테스트

``` bash
# 전체 테스트 실행
pytest tests/ -v

# 특정 테스트만 실행
pytest tests/test_agents.py -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html
```

## 트러블슈팅

### 의존성 문제
``` bash
# 가상환경 전체 초기화
pip freeze > installed_packages.txt
pip uninstall -y -r installed_packages.txt
rm installed_packages.txt
pip install -r requirements.txt
```

### WebSocket 연결 오류
- CORS 설정 확인
- Nginx 프록시 사용 시 `websocket_nginx_fastapi_setup.md` 참고

### LLM API 오류
- API 키 환경변수 확인
- Rate Limit 확인 (토큰 사용량 모니터링)

## 참고 문서

- 프로젝트 프리뷰: [design/opsnow_copilot_preview.html](design/opsnow_copilot_preview.html)
- 코딩 가이드: [CLAUDE.md](CLAUDE.md)
- FastAPI 문서: https://fastapi.tiangolo.com/
- DSPy 문서: https://dspy-docs.vercel.app/

## 라이센스

Copyright © 2024 OpsNow
