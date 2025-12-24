"""
DSPy Solver 비교 Example
PoC-3a: DSPy 프레임워크 리서치

3가지 Solver 비교:
- Predict: 추론 없이 바로 답변
- ChainOfThought: 단계별 추론 후 답변
- ProgramOfThought: 코드 생성 후 실행 (Deno 필요)
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)

# Zscaler SSL 인증서 문제 해결 (Deno용)
os.environ["DENO_TLS_CA_STORE"] = "system"


# =============================================================================
# 1. Signature 정의
# =============================================================================

class CostCalculation(dspy.Signature):
    """비용 관련 계산 문제를 Python 코드로 해결합니다."""

    question: str = dspy.InputField(desc="비용 계산 관련 질문")
    answer: float = dspy.OutputField(desc="계산 결과 (숫자)")


# =============================================================================
# 2. 메인 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    # Predict vs ChainOfThought vs ProgramOfThought 비교
    basic_solver = dspy.Predict(CostCalculation)
    cot_solver = dspy.ChainOfThought(CostCalculation)
    pot_solver = dspy.ProgramOfThought(CostCalculation)

    # 복잡한 계산 문제들
    questions = [
        "EC2 비용이 11월 17680달러, 12월 22100달러일 때, 전월 대비 증가율(%)은?",
        "4개 서비스 비용이 EC2: 22100, RDS: 12300, S3: 5200, Lambda: 3100일 때, 평균 비용은?",
        "월 비용이 42700달러이고, Reserved Instance 적용 시 30% 절감된다면, 연간 절감액은?",
        # 복합 연산 (LLM이 틀리기 쉬운 문제)
        "987654321 * 123456789 / 7654321 + 999999.99 = ?",
    ]

    print("=" * 60)
    print("Predict vs ChainOfThought vs ProgramOfThought 비교")
    print("=" * 60)

    for q in questions:
        print(f"\n{'='*60}")
        print(f"[질문] {q}")
        print("=" * 60)

        # Basic Predict (추론 없이 바로 답변)
        print("\n--- [Basic Predict] ---")
        try:
            basic_result = basic_solver(question=q)
            print(f"  답변: {basic_result.answer}")
            # 내부 필드 확인
            print(f"  (필드: {list(basic_result.keys())})")
        except Exception as e:
            print(f"  오류: {e}")

        # ChainOfThought (추론 후 답변)
        print("\n--- [ChainOfThought] ---")
        try:
            cot_result = cot_solver(question=q)
            print(f"  추론: {cot_result.reasoning[:200]}..." if len(str(cot_result.reasoning)) > 200 else f"  추론: {cot_result.reasoning}")
            print(f"  답변: {cot_result.answer}")
        except Exception as e:
            print(f"  오류: {e}")

        # ProgramOfThought (코드 생성 후 실행)
        print("\n--- [ProgramOfThought] ---")
        try:
            pot_result = pot_solver(question=q)
            # 생성된 코드 확인
            if hasattr(pot_result, 'code'):
                print(f"  코드:\n{pot_result.code}")
            if hasattr(pot_result, 'generated_code'):
                print(f"  코드:\n{pot_result.generated_code}")
            # 모든 필드 출력
            print(f"  (필드: {list(pot_result.keys())})")
            for key in pot_result.keys():
                if key != 'answer':
                    val = str(getattr(pot_result, key))
                    if len(val) > 300:
                        val = val[:300] + "..."
                    print(f"  {key}: {val}")
            print(f"  답변: {pot_result.answer}")

            # LLM 호출 기록 확인
            print("\n  [LLM History - PoT]")
            dspy.inspect_history(n=1)
        except Exception as e:
            print(f"  오류: {e}")


if __name__ == "__main__":
    main()
