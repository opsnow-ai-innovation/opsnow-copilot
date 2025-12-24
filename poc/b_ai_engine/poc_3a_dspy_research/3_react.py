"""
DSPy ReAct Example
PoC-3a: DSPy 프레임워크 리서치

ReAct 핵심 개념 검증:
- Tool 정의 (함수 기반)
- dspy.ReAct 모듈 사용
- Reason → Act → Observe 자동 루프
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
# 1. 도구 (Tools) 정의
# =============================================================================

# 서비스별 월간 비용 데이터 (단위: USD)
COSTS = {
    "ec2": {"11": 17680, "12": 22100},
    "rds": {"11": 11389, "12": 12300},
    "s3": {"11": 5361, "12": 5200},
    "lambda": {"11": 2138, "12": 3100},
}


def get_service_cost(service_name: str) -> str:
    """특정 AWS 서비스의 11월, 12월 비용을 조회합니다."""
    service = service_name.lower()
    if service in COSTS:
        return str(COSTS[service])
    return f"{service_name}: 데이터 없음"


def get_optimization_tip(service_name: str) -> str:
    """특정 AWS 서비스의 비용 최적화 팁을 제공합니다."""
    tips = {
        "ec2": "Reserved Instance 또는 Savings Plans 적용 검토. 미사용 인스턴스 중지.",
        "rds": "인스턴스 Right-sizing 검토. Aurora Serverless 전환 고려.",
        "s3": "S3 Intelligent-Tiering 적용. 수명주기 정책 설정.",
        "lambda": "메모리 최적화로 실행 시간 단축. Provisioned Concurrency 검토.",
    }
    service = service_name.lower()
    return tips.get(service, f"{service_name} 최적화 팁 없음")


def get_total_cost() -> str:
    """11월, 12월 전체 비용을 조회합니다."""
    total = {"11": 0, "12": 0}
    for service_cost in COSTS.values():
        total["11"] += service_cost["11"]
        total["12"] += service_cost["12"]
    return str(total)


# =============================================================================
# 2. Signature 정의
# =============================================================================

class FinOpsQuestion(dspy.Signature):
    """AWS 비용 관련 질문에만 답변합니다. 비용과 무관한 질문은 정중히 거절하세요."""

    question: str = dspy.InputField(desc="사용자의 AWS 비용 관련 질문")
    answer: str = dspy.OutputField(desc="비용 관련 답변. 범위 외 질문은 '비용 관련 질문만 답변 가능합니다'로 응답")


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

    # ReAct 에이전트 생성 (Signature + Tools)
    react_agent = dspy.ReAct(
        FinOpsQuestion,
        tools=[get_service_cost, get_optimization_tip, get_total_cost],
        max_iters=5,
    )

    print("=" * 60)
    print("FinOps ReAct Agent (대화형)")
    print("종료: 'quit' 또는 'exit' 입력")
    print("=" * 60)

    while True:
        try:
            question = input("\n[질문] > ").strip()

            if not question:
                continue

            if question.lower() in ["quit", "exit", "q"]:
                print("종료합니다.")
                break

            result = react_agent(question=question)
            print(f"\n[답변] {result.answer}")

        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            print(f"\n[오류] {e}")


if __name__ == "__main__":
    main()
