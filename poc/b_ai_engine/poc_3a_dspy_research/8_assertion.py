"""
DSPy Validation Example
PoC-3a: DSPy 프레임워크 리서치

Validation 핵심 개념 (DSPy 3.0+):
- Pydantic validator로 출력 검증
- 조건 불만족 시 ValidationError
- 출력 품질 보장, 환각 방지
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Pydantic 모델 (검증 로직 포함)
# =============================================================================

class CostEstimateResult(BaseModel):
    """비용 추정 결과 - 검증 규칙 포함"""

    estimated_cost: float = Field(description="예상 월 비용 (USD)")
    confidence: float = Field(description="신뢰도 0.0-1.0")
    reasoning: str = Field(description="추정 근거 (최소 20자)")

    @field_validator("estimated_cost")
    @classmethod
    def cost_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("비용은 음수일 수 없습니다")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("신뢰도는 0.0에서 1.0 사이여야 합니다")
        return v

    @field_validator("reasoning")
    @classmethod
    def reasoning_must_be_detailed(cls, v):
        if len(v) < 20:
            raise ValueError("추정 근거를 더 상세히 설명해주세요 (최소 20자)")
        return v


# =============================================================================
# 2. Signature 정의
# =============================================================================

class CostEstimate(dspy.Signature):
    """AWS 서비스 비용을 추정합니다."""

    service: str = dspy.InputField(desc="AWS 서비스명")
    usage_description: str = dspy.InputField(desc="사용량 설명")

    result: CostEstimateResult = dspy.OutputField(desc="검증된 비용 추정 결과")


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

    # Pydantic validation이 자동으로 적용됨
    estimator = dspy.ChainOfThought(CostEstimate)

    test_cases = [
        ("ec2", "m5.large 인스턴스 2대, 24시간 운영"),
        ("s3", "월 500GB 저장, 10만 건 요청"),
        ("lambda", "월 100만 호출, 평균 실행시간 200ms, 메모리 256MB"),
    ]

    print("=" * 60)
    print("Validation Example - Pydantic 검증")
    print("=" * 60)

    for service, usage in test_cases:
        print(f"\n[{service.upper()}] {usage}")

        try:
            output = estimator(service=service, usage_description=usage)
            result = output.result
            print(f"  예상 비용: ${result.estimated_cost:,.2f}/월")
            print(f"  신뢰도: {result.confidence*100:.0f}%")
            print(f"  근거: {result.reasoning[:100]}...")
        except Exception as e:
            print(f"  검증 실패: {e}")


if __name__ == "__main__":
    main()
