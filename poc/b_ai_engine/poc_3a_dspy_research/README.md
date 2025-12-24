# PoC-3a: DSPy 프레임워크 리서치

DSPy(Declarative Self-improving Python) 프레임워크 학습 및 검증을 위한 예제 모음.

> **DSPy 철학**: "Programming, not prompting" - 프롬프트 엔지니어링 대신 프로그래밍으로 LLM 제어

---

## 목차

- [환경 설정](#환경-설정)
- [기본 예제](#기본-예제)
  - [1. Hello World - 기본 개념](#1-hello-world---기본-개념)
  - [2. Optimizer - 자동 프롬프트 최적화](#2-optimizer---자동-프롬프트-최적화)
  - [3. ReAct - 도구 사용 에이전트](#3-react---도구-사용-에이전트)
  - [4. Multi-Agent - 라우팅 기반 멀티 에이전트](#4-multi-agent---라우팅-기반-멀티-에이전트)
  - [5. Module Composition - 모듈 분리 패턴](#5-module-composition---모듈-분리-패턴)
  - [6. Program of Thought - 코드 생성 및 실행](#6-program-of-thought---코드-생성-및-실행)
  - [7. Typed Predictor - 구조화된 출력](#7-typed-predictor---구조화된-출력)
  - [8. Assertion - 출력 검증](#8-assertion---출력-검증)
  - [9. FinOps Assistant - 복합 예제](#9-finops-assistant---복합-예제)
- [심화 예제](#심화-예제)
  - [10. MIPROv2 - 고급 최적화](#10-miprov2---고급-최적화)
  - [11. BootstrapFinetune - 모델 파인튜닝](#11-bootstrapfinetune---모델-파인튜닝)
  - [12. Async - 비동기 실행](#12-async---비동기-실행)
  - [13. Parallel - 병렬 실행](#13-parallel---병렬-실행)
  - [14. Observability - 모니터링](#14-observability---모니터링)
- [DSPy 핵심 개념 요약](#dspy-핵심-개념-요약)
- [DSPy 3.0 주요 변경사항](#dspy-30-주요-변경사항)
- [참고 자료](#참고-자료)

---

## 환경 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env.local
# .env.local 파일에 OPENAI_API_KEY 설정
```

### 3. 모델 설정

`config.py`에서 모델 변경 가능:

```python
MODEL_NAME = "openai/gpt-5-nano"
```

---

## 기본 예제

### 1. Hello World - 기본 개념

**파일**: `1_hello_world.py`

DSPy 핵심 개념 검증:
- LM 설정
- Signature 정의 (입출력 선언)
- Predict vs ChainOfThought

```bash
python 1_hello_world.py
```

```python
# Signature 정의
class Greeting(dspy.Signature):
    name: str = dspy.InputField(desc="Name of the person")
    greeting: str = dspy.OutputField(desc="A friendly greeting")

# 사용
predictor = dspy.Predict(Greeting)
result = predictor(name="World")
```

---

### 2. Optimizer - 자동 프롬프트 최적화

**파일**: `2_optimizer.py`

BootstrapFewShot으로 Few-shot 예제 자동 선택:

```bash
python 2_optimizer.py
```

```python
# 훈련 데이터
trainset = [
    dspy.Example(query="EC2 비용 분석해줘", category="cost_analysis").with_inputs("query"),
    ...
]

# 최적화
optimizer = BootstrapFewShot(metric=validate_category, max_bootstrapped_demos=4)
optimized = optimizer.compile(student=dspy.Predict(Signature), trainset=trainset)
```

---

### 3. ReAct - 도구 사용 에이전트

**파일**: `3_react.py`

Reason → Act → Observe 루프로 도구 호출:

```bash
python 3_react.py
```

```python
# 도구 정의
def get_service_cost(service_name: str) -> str:
    """특정 서비스의 비용 조회"""
    return str(COSTS.get(service_name.lower(), "데이터 없음"))

# ReAct 에이전트
agent = dspy.ReAct(
    FinOpsQuestion,
    tools=[get_service_cost, get_optimization_tip, get_total_cost],
    max_iters=5,
)

# 대화형 실행
result = agent(question="EC2 비용이 얼마야?")
```

---

### 4. Multi-Agent - 라우팅 기반 멀티 에이전트

**파일**: `4_multi_agent.py`

Router가 질문 분류 → 도메인별 Agent 위임:

```bash
python 4_multi_agent.py
```

```python
class FinOpsMultiAgent(dspy.Module):
    def __init__(self):
        self.router = dspy.Predict(RouterSignature)
        self.cost_agent = dspy.ReAct(CostSignature, tools=[...])
        self.opt_agent = dspy.ReAct(OptSignature, tools=[...])
        self.billing_agent = dspy.ReAct(BillingSignature, tools=[...])

    def forward(self, query: str):
        route = self.router(query=query)
        if route.agent == "cost":
            return self.cost_agent(query=query)
        ...
```

---

### 5. Module Composition - 모듈 분리 패턴

**파일**: `5_module_composition.py`

작은 모듈로 분리하여 조합 (도구 없이 LLM만 사용):

```bash
python 5_module_composition.py
```

```python
class Router(dspy.Module):
    def forward(self, query): ...

class Analyzer(dspy.Module):
    def forward(self, query, data): ...

class FinOpsAgent(dspy.Module):
    def __init__(self):
        self.router = Router()
        self.analyzer = Analyzer()

    def forward(self, query, data):
        route = self.router(query=query)
        if route.route == "analyze":
            return self.analyzer(query=query, data=data)
```

---

### 6. Program of Thought - 코드 생성 및 실행

**파일**: `6_program_of_thought.py`

LLM이 Python 코드 생성 → Deno(Pyodide)에서 실행:

```bash
# Deno 설치 필요 (macOS)
brew install deno

python 6_program_of_thought.py
```

```python
# 3가지 Solver 비교
basic_solver = dspy.Predict(CostCalculation)        # 바로 답변
cot_solver = dspy.ChainOfThought(CostCalculation)   # 추론 후 답변
pot_solver = dspy.ProgramOfThought(CostCalculation) # 코드 실행 후 답변

# 복잡한 계산
result = pot_solver(question="987654321 * 123456789 / 7654321 + 999999.99 = ?")
```

---

### 7. Typed Predictor - 구조화된 출력

**파일**: `7_typed_predictor.py`

Pydantic BaseModel로 출력 타입 강제:

```bash
python 7_typed_predictor.py
```

```python
from pydantic import BaseModel, Field

class CostAnalysisResult(BaseModel):
    service: str = Field(description="서비스명")
    nov_cost: int = Field(description="11월 비용")
    dec_cost: int = Field(description="12월 비용")
    change_percent: float = Field(description="변화율 (%)")
    trend: str = Field(description="'increase' | 'decrease' | 'stable'")

class AnalyzeCost(dspy.Signature):
    service_name: str = dspy.InputField()
    cost_data: str = dspy.InputField()
    analysis: CostAnalysisResult = dspy.OutputField()

# DSPy 3.0+: Predict가 Pydantic 직접 지원
analyzer = dspy.Predict(AnalyzeCost)
result = analyzer(service_name="ec2", cost_data=str(data))
# result.analysis.service, result.analysis.nov_cost 등으로 접근
```

---

### 8. Assertion - 출력 검증

**파일**: `8_assertion.py`

Pydantic validator로 출력 품질 보장:

```bash
python 8_assertion.py
```

```python
from pydantic import BaseModel, field_validator

class CostEstimateResult(BaseModel):
    estimated_cost: float
    confidence: float
    reasoning: str

    @field_validator("estimated_cost")
    @classmethod
    def cost_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("비용은 음수일 수 없습니다")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("신뢰도는 0.0-1.0 사이")
        return v
```

> **Note**: DSPy 3.0에서 `dspy.Suggest`/`dspy.Assert` 제거됨. Pydantic validator로 대체.

---

### 9. FinOps Assistant - 복합 예제

**파일**: `9_finops_assistant.py`

Query Router + ChainOfThought + Clarification 조합:

```bash
python 9_finops_assistant.py
```

---

## DSPy 핵심 개념 요약

| 개념 | 설명 |
|------|------|
| **Signature** | 입출력 선언 (시스템 프롬프트 역할) |
| **Module** | Signature를 실행하는 단위 |
| **Predict** | 기본 실행 (추론 없음) |
| **ChainOfThought** | 단계별 추론 후 답변 |
| **ReAct** | 도구 사용 에이전트 (Reason → Act → Observe) |
| **ProgramOfThought** | 코드 생성 후 실행 |
| **Optimizer** | 프롬프트 자동 최적화 |

---

## DSPy Optimizer 비교

DSPy는 세 가지 주요 Optimizer를 제공합니다:

| Optimizer | 최적화 대상 | 결과물 | 속도 | 비용 | 성능 |
|-----------|-------------|--------|------|------|------|
| **BootstrapFewShot** | Few-shot 예제만 | JSON (프롬프트) | 빠름 | 낮음 | 보통 |
| **MIPROv2** | Instruction + Few-shot | JSON (프롬프트) | 중간 | 중간 | 높음 |
| **BootstrapFinetune** | 모델 가중치 | 새 모델 (ft:xxx) | 느림 | 높음 | 최고 |

### 언제 무엇을 사용하나?

```
빠른 프로토타이핑        → BootstrapFewShot (2_optimizer.py)
프롬프트 최적화          → MIPROv2 (10_mipro.py)
최대 성능 / 토큰 절약    → BootstrapFinetune (11_finetune.py)
```

### 동작 방식 비교

```
BootstrapFewShot:
  trainset → 예제 선택 → few-shot 프롬프트 생성

MIPROv2:
  trainset + valset → Bayesian 최적화 → instruction + few-shot 최적화

BootstrapFinetune:
  Teacher 모델 → 트레이스 수집 → Student 모델 파인튜닝 → 새 모델
```

---

## DSPy 3.0 주요 변경사항

| 기존 (2.x) | 현재 (3.0) |
|------------|------------|
| `dspy.TypedPredictor` | `dspy.Predict` (Pydantic 직접 지원) |
| `dspy.Suggest` / `dspy.Assert` | Pydantic `@field_validator` |
| 별도 캐시 설정 | 자동 캐시 (`~/.dspy_cache`) |

---

## 심화 예제

### 10. MIPROv2 - 고급 최적화

**파일**: `10_mipro.py`

Bayesian 최적화로 instruction + few-shot 동시 최적화:

```bash
python 10_mipro.py
```

```python
optimizer = dspy.MIPROv2(
    metric=validate_intent,
    auto="light",  # "light", "medium", "heavy"
)

optimized = optimizer.compile(
    student=dspy.Predict(IntentClassifier),
    trainset=trainset,
    valset=valset,
)
```

---

### 11. BootstrapFinetune - 모델 파인튜닝

**파일**: `11_finetune.py`

Teacher 모델의 지식을 Student 모델로 증류 (Knowledge Distillation):

```bash
python 11_finetune.py
```

**다른 Optimizer와의 차이:**
```
BootstrapFewShot  → 프롬프트만 변경 (모델 그대로)
MIPROv2           → 프롬프트만 변경 (모델 그대로)
BootstrapFinetune → 모델 가중치 변경 (새 모델 생성)
```

**파인튜닝 코드 (참고용 - 비용 발생!):**
```python
from dspy.teleprompt import BootstrapFinetune

# Teacher (큰 모델) → Student (작은 모델) 증류
teacher_lm = dspy.LM("openai/gpt-4o")
student_lm = dspy.LM("openai/gpt-5-nano")

optimizer = BootstrapFinetune(
    metric=validate_analysis,
    teacher_settings={"lm": teacher_lm},
)

finetuned = optimizer.compile(
    student=dspy.ChainOfThought(Signature),
    trainset=trainset,
    target=student_lm,  # 이 모델이 파인튜닝됨
)
# 결과: ft:gpt-5-nano:my-org::abc123
```

> **Note**: 실제 파인튜닝은 비용 발생! OpenAI Fine-tuning API 또는 로컬 GPU 필요

---

### 12. Async - 비동기 실행

**파일**: `12_async.py`

동기 vs 비동기 성능 비교:

```bash
python 12_async.py
```

```python
from dspy.utils import asyncify

# 방법 1: asyncify로 변환
async_module = asyncify(my_module)
results = await asyncio.gather(*[async_module(q) for q in queries])

# 방법 2: aforward() 직접 구현
class AsyncModule(dspy.Module):
    async def aforward(self, query: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.predictor(query=query))
```

---

### 13. Parallel - 병렬 실행

**파일**: `13_parallel.py`

dspy.Parallel로 여러 분석 동시 실행:

```bash
python 13_parallel.py
```

```python
class ParallelAnalyzer(dspy.Module):
    def __init__(self):
        self.trend = dspy.ChainOfThought(TrendSignature)
        self.anomaly = dspy.ChainOfThought(AnomalySignature)
        self.optimization = dspy.ChainOfThought(OptSignature)

        # Parallel로 묶기
        self.parallel = dspy.Parallel(
            trend=self.trend,
            anomaly=self.anomaly,
            optimization=self.optimization,
        )

    def forward(self, data: str):
        results = self.parallel(
            trend={"cost_data": data},
            anomaly={"cost_data": data},
            optimization={"cost_data": data},
        )
        return results
```

---

### 14. Observability - 모니터링

**파일**: `14_observability.py`

MLflow/Langfuse 트레이싱:

```bash
# MLflow 설치
pip install mlflow

python 14_observability.py
```

```python
import mlflow

# 자동 트레이싱 활성화
mlflow.dspy.autolog()
mlflow.set_experiment("dspy-finops-poc")

with mlflow.start_run(run_name="cost-qa-test"):
    result = qa(question="EC2 비용 분석해줘")
    mlflow.log_metric("answer_length", len(result.answer))

# MLflow UI 실행
# mlflow ui → http://localhost:5000
```

---

## 참고 자료

- [DSPy 공식 문서](https://dspy.ai/)
- [DSPy GitHub](https://github.com/stanfordnlp/dspy)
- [DSPy Cheatsheet](https://dspy.ai/cheatsheet/)
- [MIPROv2 API](https://dspy.ai/api/optimizers/MIPROv2/)
