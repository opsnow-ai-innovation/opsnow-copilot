"""
DSPy Module Composition Example
PoC-3a: DSPy 프레임워크 리서치

Module 분리 및 조합 패턴:
- 작은 Module로 분리
- 상위 Module에서 조합
- forward()는 조율자 역할만
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. 작은 Module들 (각자 단일 책임)
# =============================================================================

class Router(dspy.Module):
    """질문 분류만 담당"""

    class Signature(dspy.Signature):
        """질문을 분류"""
        query: str = dspy.InputField()
        route: str = dspy.OutputField(desc="'analyze' | 'recommend' | 'both'")

    def __init__(self):
        super().__init__()
        self.classify = dspy.Predict(self.Signature)

    def forward(self, query: str):
        return self.classify(query=query)


class Analyzer(dspy.Module):
    """비용 분석만 담당"""

    class Signature(dspy.Signature):
        """비용 데이터 분석"""
        query: str = dspy.InputField()
        data: str = dspy.InputField()
        analysis: str = dspy.OutputField(desc="분석 결과 (2-3문장)")

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(self.Signature)

    def forward(self, query: str, data: str):
        return self.analyze(query=query, data=data)


class Recommender(dspy.Module):
    """최적화 추천만 담당"""

    class Signature(dspy.Signature):
        """비용 최적화 추천"""
        query: str = dspy.InputField()
        data: str = dspy.InputField()
        recommendations: str = dspy.OutputField(desc="추천 사항 (bullet points)")

    def __init__(self):
        super().__init__()
        self.recommend = dspy.Predict(self.Signature)

    def forward(self, query: str, data: str):
        return self.recommend(query=query, data=data)


# =============================================================================
# 2. 상위 Module (조합 + 조율)
# =============================================================================

class FinOpsAgent(dspy.Module):
    """하위 Module들을 조합하여 처리"""

    def __init__(self):
        super().__init__()
        self.router = Router()
        self.analyzer = Analyzer()
        self.recommender = Recommender()

    def forward(self, query: str, data: str):
        # Step 1: 라우팅
        route_result = self.router(query=query)
        route = route_result.route.lower()

        # Step 2: 라우팅 결과에 따라 하위 Module 호출
        analysis = None
        recommendations = None

        if route in ["analyze", "both"]:
            analysis = self.analyzer(query=query, data=data).analysis

        if route in ["recommend", "both"]:
            recommendations = self.recommender(query=query, data=data).recommendations

        # Step 3: 결과 조합
        return dspy.Prediction(
            route=route,
            analysis=analysis,
            recommendations=recommendations,
        )


# =============================================================================
# 3. 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    # 샘플 데이터
    cost_data = """
    EC2: $22,100 (+25%)
    RDS: $12,300 (+8%)
    S3: $5,200 (-3%)
    Lambda: $3,100 (+45%)
    """

    agent = FinOpsAgent()

    # 테스트
    test_queries = [
        "EC2 비용이 왜 올랐어?",           # → analyze
        "비용 줄이는 방법 알려줘",          # → recommend
        "Lambda 분석하고 최적화 방안도 줘",  # → both
    ]

    for query in test_queries:
        print("\n" + "=" * 60)
        print(f"Query: {query}")
        print("=" * 60)

        result = agent(query=query, data=cost_data)

        print(f"Route: {result.route}")
        if result.analysis:
            print(f"\n[Analysis]\n{result.analysis}")
        if result.recommendations:
            print(f"\n[Recommendations]\n{result.recommendations}")


if __name__ == "__main__":
    main()
