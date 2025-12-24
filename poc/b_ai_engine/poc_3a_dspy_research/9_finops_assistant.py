"""
DSPy FinOps Assistant Example
PoC-3a: DSPy 프레임워크 리서치

실용적 DSPy 패턴 검증:
- 복합 Signature (다중 출력)
- Query Router (질문 분류)
- ChainOfThought (추론 기반 분석)
- 컨텍스트 기반 응답 생성
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

# 환경 설정
env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Signature 정의
# =============================================================================

class QueryRouter(dspy.Signature):
    """사용자 질문을 분석하여 적절한 처리 경로 결정"""

    query: str = dspy.InputField(desc="사용자의 질문")
    context: str = dspy.InputField(desc="현재 화면 컨텍스트 (비용 데이터 등)")

    route: str = dspy.OutputField(desc="처리 경로: 'cost_analysis' | 'optimization' | 'faq' | 'clarification'")
    confidence: float = dspy.OutputField(desc="분류 신뢰도 0.0-1.0")
    reasoning: str = dspy.OutputField(desc="분류 이유")


class CostAnalysis(dspy.Signature):
    """비용 데이터 분석 및 인사이트 도출"""

    query: str = dspy.InputField(desc="사용자의 질문")
    cost_data: str = dspy.InputField(desc="비용 데이터 (JSON 또는 텍스트)")

    analysis: str = dspy.OutputField(desc="비용 분석 결과")
    key_findings: str = dspy.OutputField(desc="핵심 발견사항 (bullet points)")
    recommendations: str = dspy.OutputField(desc="비용 최적화 권장사항")


class Clarification(dspy.Signature):
    """모호한 질문에 대해 명확화 질문 생성"""

    query: str = dspy.InputField(desc="모호한 사용자 질문")
    context: str = dspy.InputField(desc="현재 컨텍스트")

    clarification_question: str = dspy.OutputField(desc="사용자에게 할 명확화 질문")
    options: str = dspy.OutputField(desc="선택지 (쉼표로 구분)")


# =============================================================================
# 2. FinOps Assistant Module
# =============================================================================

class FinOpsAssistant(dspy.Module):
    """FinOps 질의응답을 위한 DSPy 모듈"""

    def __init__(self):
        super().__init__()
        self.router = dspy.ChainOfThought(QueryRouter)
        self.analyzer = dspy.ChainOfThought(CostAnalysis)
        self.clarifier = dspy.Predict(Clarification)

    def forward(self, query: str, context: str):
        # Step 1: 질문 분류
        route_result = self.router(query=query, context=context)

        # Step 2: 경로에 따른 처리
        if route_result.route == "cost_analysis":
            analysis = self.analyzer(query=query, cost_data=context)
            return dspy.Prediction(
                route=route_result.route,
                confidence=route_result.confidence,
                response=analysis.analysis,
                details={
                    "key_findings": analysis.key_findings,
                    "recommendations": analysis.recommendations,
                },
            )

        elif route_result.route == "clarification":
            clarify = self.clarifier(query=query, context=context)
            return dspy.Prediction(
                route=route_result.route,
                confidence=route_result.confidence,
                response=clarify.clarification_question,
                details={"options": clarify.options},
            )

        else:
            # FAQ 또는 optimization은 간단히 처리
            return dspy.Prediction(
                route=route_result.route,
                confidence=route_result.confidence,
                response=route_result.reasoning,
                details={},
            )


# =============================================================================
# 3. 테스트 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    # 샘플 비용 데이터
    sample_context = """
    [Current Screen: AWS Cost Dashboard]
    - Total Cost (This Month): $45,230
    - Previous Month: $38,500
    - Change: +17.5%

    Top Services:
    1. EC2: $22,100 (+25%)
    2. RDS: $12,300 (+8%)
    3. S3: $5,200 (-3%)
    4. Lambda: $3,100 (+45%)

    Anomaly Detected: EC2 cost spike on Dec 15-18
    """

    assistant = FinOpsAssistant()

    # 테스트 케이스들
    test_queries = [
        "왜 이번 달 비용이 증가했나요?",
        "비용 줄이는 방법 알려줘",
        "저번에 그거",  # 모호한 질문
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("=" * 60)

        result = assistant(query=query, context=sample_context)

        print(f"Route: {result.route} (confidence: {result.confidence})")
        print(f"Response: {result.response}")
        if result.details:
            print(f"Details: {result.details}")


if __name__ == "__main__":
    main()
