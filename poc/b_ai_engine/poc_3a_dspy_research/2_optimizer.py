"""
DSPy Optimizer Example
PoC-3a: DSPy 프레임워크 리서치

Optimizer 핵심 개념 검증:
- 훈련 데이터 (Examples) 준비
- Metric 함수 정의
- BootstrapFewShot으로 프롬프트 자동 최적화
- 최적화 전/후 비교
"""

import os
from pathlib import Path

import dspy
from dspy.teleprompt import BootstrapFewShot
from dotenv import load_dotenv

from config import MODEL_NAME

# 환경 설정
env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Signature 정의
# =============================================================================

class QueryClassifier(dspy.Signature):
    """FinOps 관련 질문을 카테고리로 분류"""

    query: str = dspy.InputField(desc="사용자의 질문")
    category: str = dspy.OutputField(
        desc="카테고리: 'cost_analysis' | 'optimization' | 'billing' | 'general'"
    )


# =============================================================================
# 2. 훈련 데이터 (Examples)
# =============================================================================

# DSPy는 이 예제들을 분석하여 Few-shot 프롬프트를 자동 생성
trainset = [
    dspy.Example(
        query="이번 달 EC2 비용이 왜 이렇게 높아?",
        category="cost_analysis"
    ).with_inputs("query"),
    dspy.Example(
        query="지난 달 대비 비용 변화 분석해줘",
        category="cost_analysis"
    ).with_inputs("query"),
    dspy.Example(
        query="S3 비용 줄이는 방법 알려줘",
        category="optimization"
    ).with_inputs("query"),
    dspy.Example(
        query="Reserved Instance 추천해줘",
        category="optimization"
    ).with_inputs("query"),
    dspy.Example(
        query="이번 달 청구서 언제 나와?",
        category="billing"
    ).with_inputs("query"),
    dspy.Example(
        query="결제 방법 변경하고 싶어",
        category="billing"
    ).with_inputs("query"),
    dspy.Example(
        query="OpsNow가 뭐야?",
        category="general"
    ).with_inputs("query"),
    dspy.Example(
        query="안녕하세요",
        category="general"
    ).with_inputs("query"),
]

# 테스트용 데이터
testset = [
    dspy.Example(query="RDS 비용 분석", category="cost_analysis").with_inputs("query"),
    dspy.Example(query="Lambda 최적화 방법", category="optimization").with_inputs("query"),
    dspy.Example(query="인보이스 다운로드", category="billing").with_inputs("query"),
    dspy.Example(query="도움말", category="general").with_inputs("query"),
]


# =============================================================================
# 3. Metric 함수 (평가 기준)
# =============================================================================

def validate_category(example, pred, trace=None):
    """예측 카테고리가 정답과 일치하는지 검증"""
    return example.category.lower() == pred.category.lower()


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

    # ----- 최적화 전 (기본 Predict) -----
    print("=" * 60)
    print("1. 최적화 전 (기본 Predict)")
    print("=" * 60)

    basic_classifier = dspy.Predict(QueryClassifier)

    correct_before = 0
    for example in testset:
        pred = basic_classifier(query=example.query)
        is_correct = validate_category(example, pred)
        correct_before += int(is_correct)
        print(f"  Query: {example.query}")
        print(f"  Expected: {example.category}, Got: {pred.category} {'✓' if is_correct else '✗'}")
        print()

    print(f"정확도 (최적화 전): {correct_before}/{len(testset)}")

    # ----- Optimizer로 최적화 -----
    print("\n" + "=" * 60)
    print("2. BootstrapFewShot 최적화 중...")
    print("=" * 60)

    optimizer = BootstrapFewShot(
        metric=validate_category,
        max_bootstrapped_demos=4,  # 최대 4개의 예제를 Few-shot으로 사용
        max_labeled_demos=4,
    )

    optimized_classifier = optimizer.compile(
        student=dspy.Predict(QueryClassifier),
        trainset=trainset,
    )

    # ----- 최적화 후 테스트 -----
    print("\n" + "=" * 60)
    print("3. 최적화 후 테스트")
    print("=" * 60)

    correct_after = 0
    for example in testset:
        pred = optimized_classifier(query=example.query)
        is_correct = validate_category(example, pred)
        correct_after += int(is_correct)
        print(f"  Query: {example.query}")
        print(f"  Expected: {example.category}, Got: {pred.category} {'✓' if is_correct else '✗'}")
        print()

    print(f"정확도 (최적화 후): {correct_after}/{len(testset)}")

    # ----- 결과 비교 -----
    print("\n" + "=" * 60)
    print("4. 결과 비교")
    print("=" * 60)
    print(f"  최적화 전: {correct_before}/{len(testset)} ({correct_before/len(testset)*100:.0f}%)")
    print(f"  최적화 후: {correct_after}/{len(testset)} ({correct_after/len(testset)*100:.0f}%)")

    # ----- 최적화된 프롬프트 확인 -----
    print("\n" + "=" * 60)
    print("5. 최적화된 모듈 정보")
    print("=" * 60)
    print(f"  Demos (Few-shot 예제 수): {len(optimized_classifier.demos)}")
    for i, demo in enumerate(optimized_classifier.demos):
        print(f"    {i+1}. {demo.query} → {demo.category}")


if __name__ == "__main__":
    main()
