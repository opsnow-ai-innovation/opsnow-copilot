"""
DSPy Typed Output Example
PoC-3a: DSPy 프레임워크 리서치

Typed Output 핵심 개념:
- Pydantic BaseModel로 출력 타입 강제
- 구조화된 JSON 응답 보장
- DSPy 3.0+: Predict/ChainOfThought가 Pydantic 직접 지원
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Pydantic 모델 정의 (출력 구조)
# =============================================================================

class CostAnalysisResult(BaseModel):
    """비용 분석 결과 구조"""
    service: str = Field(description="분석 대상 서비스명")
    nov_cost: int = Field(description="11월 비용 (USD)")
    dec_cost: int = Field(description="12월 비용 (USD)")
    change_percent: float = Field(description="전월 대비 변화율 (%)")
    trend: str = Field(description="추세: 'increase' | 'decrease' | 'stable'")
    recommendation: str = Field(description="비용 최적화 권장사항")


# =============================================================================
# 2. Typed Signature 정의
# =============================================================================

class AnalyzeCost(dspy.Signature):
    """AWS 서비스 비용을 분석하여 구조화된 결과를 반환합니다."""

    service_name: str = dspy.InputField(desc="분석할 AWS 서비스명")
    cost_data: str = dspy.InputField(desc="비용 데이터 (JSON)")

    analysis: CostAnalysisResult = dspy.OutputField(desc="구조화된 분석 결과")


# =============================================================================
# 3. 데이터
# =============================================================================

COSTS = {
    "ec2": {"11": 17680, "12": 22100},
    "rds": {"11": 11389, "12": 12300},
    "s3": {"11": 5361, "12": 5200},
    "lambda": {"11": 2138, "12": 3100},
}


# =============================================================================
# 4. 메인 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    # DSPy 3.0+: Predict가 Pydantic 직접 지원
    analyzer = dspy.Predict(AnalyzeCost)

    print("=" * 60)
    print("Typed Output Example - 구조화된 비용 분석")
    print("=" * 60)

    for service, costs in COSTS.items():
        print(f"\n[{service.upper()}]")

        result = analyzer(
            service_name=service,
            cost_data=str(costs)
        )

        # 결과는 Pydantic 모델로 반환됨
        analysis = result.analysis
        print(f"  서비스: {analysis.service}")
        print(f"  11월: ${analysis.nov_cost:,}")
        print(f"  12월: ${analysis.dec_cost:,}")
        print(f"  변화율: {analysis.change_percent:+.1f}%")
        print(f"  추세: {analysis.trend}")
        print(f"  권장: {analysis.recommendation}")


if __name__ == "__main__":
    main()
