"""
DSPy Multi-Agent Example
PoC-3a: DSPy 프레임워크 리서치

Multi-Agent 패턴:
- Router가 질문 분류
- 도메인별 Agent 분리 (각 3-4개 도구)
- 상위 Module에서 조합
"""

import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. 공통 데이터
# =============================================================================

COSTS = {
    "ec2": {"11": 17680, "12": 22100},
    "rds": {"11": 11389, "12": 12300},
    "s3": {"11": 5361, "12": 5200},
    "lambda": {"11": 2138, "12": 3100},
}

RI_COVERAGE = {
    "ec2": {"current": 45, "recommended": 70},
    "rds": {"current": 60, "recommended": 80},
}

BILLING = {
    "invoice": {"12": "INV-2024-1201", "due_date": "2025-01-15"},
    "payment_method": "Credit Card (****1234)",
    "credits": 500,
}


# =============================================================================
# 2. Cost Agent 도구 (비용 조회/분석)
# =============================================================================

def get_service_cost(service_name: str) -> str:
    """특정 서비스의 월별 비용 조회"""
    service = service_name.lower()
    if service in COSTS:
        return str(COSTS[service])
    return f"{service_name}: 데이터 없음"


def get_total_cost() -> str:
    """전체 월별 비용 조회"""
    total = {"11": 0, "12": 0}
    for cost in COSTS.values():
        total["11"] += cost["11"]
        total["12"] += cost["12"]
    return str(total)


def get_cost_change(service_name: str) -> str:
    """특정 서비스의 전월 대비 비용 변화율 계산"""
    service = service_name.lower()
    if service in COSTS:
        nov = COSTS[service]["11"]
        dec = COSTS[service]["12"]
        change = round((dec - nov) / nov * 100, 1)
        return f"{change}%"
    return f"{service_name}: 데이터 없음"


# =============================================================================
# 3. Optimization Agent 도구 (최적화 추천)
# =============================================================================

def get_ri_coverage(service_name: str) -> str:
    """RI 커버리지 현황 조회"""
    service = service_name.lower()
    if service in RI_COVERAGE:
        return str(RI_COVERAGE[service])
    return f"{service_name}: RI 데이터 없음"


def get_optimization_tip(service_name: str) -> str:
    """서비스별 최적화 팁"""
    tips = {
        "ec2": "미사용 인스턴스 중지, Right-sizing 검토",
        "rds": "Aurora Serverless 전환, 스토리지 최적화",
        "s3": "Intelligent-Tiering, 수명주기 정책",
        "lambda": "메모리 최적화, 콜드스타트 개선",
    }
    service = service_name.lower()
    return tips.get(service, f"{service_name}: 팁 없음")


def get_savings_estimate(service_name: str) -> str:
    """예상 절감액 계산"""
    service = service_name.lower()
    if service in COSTS and service in RI_COVERAGE:
        current_cost = COSTS[service]["12"]
        ri_gap = RI_COVERAGE[service]["recommended"] - RI_COVERAGE[service]["current"]
        savings = int(current_cost * ri_gap / 100 * 0.3)  # RI 30% 할인 가정
        return f"${savings}/월 절감 가능 (RI 커버리지 {ri_gap}% 증가 시)"
    return f"{service_name}: 절감 추정 불가"


# =============================================================================
# 4. Billing Agent 도구 (청구/결제)
# =============================================================================

def get_invoice_info() -> str:
    """청구서 정보 조회"""
    return str(BILLING["invoice"])


def get_payment_method() -> str:
    """결제 수단 조회"""
    return BILLING["payment_method"]


def get_credits() -> str:
    """크레딧 잔액 조회"""
    return f"${BILLING['credits']}"


# =============================================================================
# 5. Signatures
# =============================================================================

class RouterSignature(dspy.Signature):
    """질문을 분석하여 담당 Agent 결정"""
    query: str = dspy.InputField()
    agent: str = dspy.OutputField(desc="'cost' | 'optimization' | 'billing'")


class CostSignature(dspy.Signature):
    """비용 관련 질문에 답변"""
    query: str = dspy.InputField()
    answer: str = dspy.OutputField()


class OptimizationSignature(dspy.Signature):
    """최적화 관련 질문에 답변"""
    query: str = dspy.InputField()
    answer: str = dspy.OutputField()


class BillingSignature(dspy.Signature):
    """청구/결제 관련 질문에 답변"""
    query: str = dspy.InputField()
    answer: str = dspy.OutputField()


# =============================================================================
# 6. Multi-Agent System
# =============================================================================

class FinOpsMultiAgent(dspy.Module):
    """도메인별 Agent를 조합한 Multi-Agent 시스템"""

    def __init__(self):
        super().__init__()

        # Router (어떤 Agent가 처리할지 결정)
        self.router = dspy.Predict(RouterSignature)

        # 도메인별 Agent (각자 3-4개 도구)
        self.cost_agent = dspy.ReAct(
            CostSignature,
            tools=[get_service_cost, get_total_cost, get_cost_change],
            max_iters=3,
        )

        self.opt_agent = dspy.ReAct(
            OptimizationSignature,
            tools=[get_ri_coverage, get_optimization_tip, get_savings_estimate],
            max_iters=3,
        )

        self.billing_agent = dspy.ReAct(
            BillingSignature,
            tools=[get_invoice_info, get_payment_method, get_credits],
            max_iters=3,
        )

    def forward(self, query: str):
        # Step 1: 라우팅
        print("\n  [1] Router 판단 중...")
        route_result = self.router(query=query)
        agent_type = route_result.agent.lower()
        print(f"      → 선택된 Agent: {agent_type}")

        # Step 2: 해당 Agent에 위임
        print(f"\n  [2] {agent_type.upper()} Agent 실행 중...")
        if agent_type == "cost":
            result = self.cost_agent(query=query)
            tools_used = ["get_service_cost", "get_total_cost", "get_cost_change"]
        elif agent_type == "optimization":
            result = self.opt_agent(query=query)
            tools_used = ["get_ri_coverage", "get_optimization_tip", "get_savings_estimate"]
        elif agent_type == "billing":
            result = self.billing_agent(query=query)
            tools_used = ["get_invoice_info", "get_payment_method", "get_credits"]
        else:
            result = dspy.Prediction(answer="질문을 이해하지 못했습니다.")
            tools_used = []

        print(f"      사용 가능 도구: {tools_used}")

        # Step 3: ReAct trajectory 출력 (도구 호출 기록)
        if hasattr(result, 'trajectory'):
            print(f"\n  [3] ReAct Trajectory:")
            for i, step in enumerate(result.trajectory):
                print(f"      Step {i+1}: {step}")

        # observations 확인 (도구 호출 결과)
        if hasattr(result, 'observations'):
            print(f"\n  [3] Tool 호출 결과:")
            for obs in result.observations:
                print(f"      → {obs[:100]}..." if len(str(obs)) > 100 else f"      → {obs}")

        print(f"\n  [4] 최종 답변 생성 완료")

        return dspy.Prediction(
            agent=agent_type,
            answer=result.answer,
        )


# =============================================================================
# 7. 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    system = FinOpsMultiAgent()

    test_queries = [
        # Cost Agent
        "EC2 비용이 전월 대비 얼마나 올랐어?",
        # Optimization Agent
        "EC2 비용 줄이려면 어떻게 해야해?",
        # Billing Agent
        "이번 달 청구서 번호가 뭐야?",
    ]

    for query in test_queries:
        print("\n" + "=" * 60)
        print(f"Query: {query}")
        print("=" * 60)

        result = system(query=query)

        print(f"Agent: {result.agent}")
        print(f"Answer: {result.answer}")


if __name__ == "__main__":
    main()
