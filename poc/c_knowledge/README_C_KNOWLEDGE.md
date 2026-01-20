## 시작하기

### 1. 가상환경 설정
```bash
# 프로젝트 디렉토리로 이동
cd poc/c_knowledge

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements_c_knowledge.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env.local

# 필수 환경변수
export OPENAI_API_KEY=sk-your-api-key
export REDIS_URL=redis://localhost:6379
export LOCAL_DEV=true
```

### 3. 가이드 배치 실행
```bash
bash poc/c_knowledge/scripts/run_guide_batch.sh
```

### 4. 서버 실행
```bash
bash poc/c_knowledge/scripts/run_local.sh
```

### 5. chat cli 실행
```bash
python poc/c_knowledge/scripts/chat_cli.py
```

### 6. unittest 실행
```bash
pytest poc/c_knowledge/tests
```
