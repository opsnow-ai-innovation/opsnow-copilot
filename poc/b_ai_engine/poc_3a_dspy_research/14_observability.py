"""
DSPy Observability Example
PoC-3a: DSPy 프레임워크 리서치

Observability 핵심 개념:
- MLflow: 트레이싱, 실험 관리
- dspy.inspect_history(): 호출 기록 확인
- 프로덕션 모니터링 기반

Note: MLflow 설치 필요
  pip install mlflow
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Signature 정의
# =============================================================================

class CostQuery(dspy.Signature):
    """비용 관련 질문에 답변합니다."""

    question: str = dspy.InputField(desc="비용 관련 질문")
    answer: str = dspy.OutputField(desc="답변")


# =============================================================================
# 2. 간단한 모듈
# =============================================================================

class CostQA(dspy.Module):
    """비용 Q&A 모듈"""

    def __init__(self):
        super().__init__()
        self.qa = dspy.ChainOfThought(CostQuery)

    def forward(self, question: str):
        return self.qa(question=question)


# =============================================================================
# 3. 메인 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    print("=" * 60)
    print("Observability Example")
    print("=" * 60)

    # ----- MLflow 트레이싱 시도 -----
    mlflow_available = False
    try:
        import mlflow
        mlflow_available = True
        print("\n[MLflow 트레이싱 활성화]")

        # MLflow autolog 활성화
        mlflow.dspy.autolog()

        # 실험 설정
        mlflow.set_experiment("dspy-finops-poc")

        print("  - mlflow.dspy.autolog() 활성화됨")
        print("  - 실험: dspy-finops-poc")

    except ImportError:
        print("\n[MLflow 미설치]")
        print("  pip install mlflow")
        print("  설치 후 트레이싱 사용 가능")

    except Exception as e:
        print(f"\n[MLflow 오류]: {e}")

    # ----- 질의 실행 -----
    print("\n" + "-" * 40)
    print("[질의 실행]")
    print("-" * 40)

    qa = CostQA()

    questions = [
        "EC2 비용이 전월 대비 25% 증가한 원인은?",
        "Lambda 비용 최적화 방법 3가지 알려줘",
    ]

    if mlflow_available:
        with mlflow.start_run(run_name="cost-qa-test"):
            for i, q in enumerate(questions):
                # 각 질문별로 nested run 생성
                with mlflow.start_run(run_name=f"question-{i+1}", nested=True):
                    print(f"\n[Q] {q}")
                    result = qa(question=q)
                    print(f"[A] {result.answer[:100]}...")

                    # 커스텀 메트릭 로깅
                    mlflow.log_param("question", q[:50])
                    mlflow.log_metric("answer_length", len(result.answer))
    else:
        for q in questions:
            print(f"\n[Q] {q}")
            result = qa(question=q)
            print(f"[A] {result.answer[:100]}...")

    # ----- dspy.inspect_history() -----
    print("\n" + "-" * 40)
    print("[DSPy History - 마지막 호출]")
    print("-" * 40)

    dspy.inspect_history(n=1)

    # ----- DSPy 내장 디버깅 -----
    print("\n" + "=" * 60)
    print("[DSPy 디버깅 도구]")
    print("=" * 60)
    print("""
1. dspy.inspect_history(n=N)
   - 마지막 N개 LLM 호출 확인
   - 프롬프트, 응답 전문 출력

2. dspy.settings.trace
   - 상세 트레이스 활성화
   - dspy.configure(trace=[])

3. 결과 객체 검사
   - result.keys()  # 필드 목록
   - result.reasoning  # CoT 추론 과정
""")

    # ----- MLflow UI 안내 -----
    if mlflow_available:
        print("\n" + "=" * 60)
        print("[MLflow UI 실행]")
        print("=" * 60)

        # 현재 디렉토리 경로
        current_dir = Path(__file__).parent
        db_path = current_dir / "mlflow.db"

        print(f"""
MLflow UI로 트레이스 시각화:

1. 이 디렉토리로 이동:
   cd {current_dir}

2. MLflow UI 실행 (SQLite DB 지정):
   mlflow ui --backend-store-uri sqlite:///mlflow.db

3. 브라우저에서 열기:
   http://localhost:5000

4. 확인 가능한 정보:
   - Experiments 탭 → dspy-finops-poc 클릭
   - 각 Run 클릭 → Traces 탭에서 LLM 호출 확인
   - 입출력 데이터, 실행 시간, 토큰 사용량

[참고] DB 파일 위치: {db_path}
""")

    # ----- Langfuse 연동 안내 -----
    print("\n" + "=" * 60)
    print("[Langfuse 연동 (옵션)]")
    print("=" * 60)
    print("""
Langfuse로 트레이스 전송:

1. 설치:
   pip install langfuse opentelemetry-exporter-otlp-proto-http

2. 환경 변수:
   export LANGFUSE_PUBLIC_KEY="pk-..."
   export LANGFUSE_SECRET_KEY="sk-..."
   export LANGFUSE_HOST="https://cloud.langfuse.com"

3. 코드:
   import mlflow
   mlflow.dspy.autolog()

   # OpenTelemetry 설정으로 Langfuse에 트레이스 전송

참고: https://langfuse.com/guides/cookbook/integration_dspy
""")


if __name__ == "__main__":
    main()
