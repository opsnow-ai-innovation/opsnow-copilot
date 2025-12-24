"""
DSPy MIPROv2 Example
PoC-3a: DSPy 프레임워크 리서치

MIPROv2 핵심 개념:
- Bayesian 최적화로 instruction + few-shot 동시 최적화
- BootstrapFewShot보다 더 강력한 최적화
- auto 모드: "light", "medium", "heavy"
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

class IntentClassifier(dspy.Signature):
    """사용자 질문의 의도를 분류합니다."""

    query: str = dspy.InputField(desc="사용자의 질문")
    intent: str = dspy.OutputField(
        desc="의도: 'cost_inquiry' | 'optimization' | 'billing' | 'general'"
    )


# =============================================================================
# 2. 훈련/검증 데이터
# =============================================================================

trainset = [
    # cost_inquiry - 명확한 케이스
    dspy.Example(query="EC2 비용이 얼마야?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="이번 달 AWS 청구 금액 알려줘", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="RDS 사용량 비용 조회해줘", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="Lambda 비용이 전월 대비 얼마나 올랐어?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="S3 스토리지 비용 현황", intent="cost_inquiry").with_inputs("query"),
    # cost_inquiry - 애매한 케이스 (최적화처럼 보이지만 조회)
    dspy.Example(query="EC2 비용이 왜 이렇게 많이 나왔어?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="비용 증가 원인 분석해줘", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="어떤 서비스가 제일 비싸?", intent="cost_inquiry").with_inputs("query"),

    # optimization - 명확한 케이스
    dspy.Example(query="비용 절감 방법 알려줘", intent="optimization").with_inputs("query"),
    dspy.Example(query="EC2 최적화 추천해줘", intent="optimization").with_inputs("query"),
    dspy.Example(query="RI 구매 추천", intent="optimization").with_inputs("query"),
    dspy.Example(query="비용 줄이는 방법 뭐 있어?", intent="optimization").with_inputs("query"),
    dspy.Example(query="Savings Plans 적용하면 얼마나 절약돼?", intent="optimization").with_inputs("query"),
    # optimization - 애매한 케이스 (비용 언급하지만 최적화)
    dspy.Example(query="EC2 비용 줄이려면 어떻게 해?", intent="optimization").with_inputs("query"),
    dspy.Example(query="다음 달 비용 낮추고 싶어", intent="optimization").with_inputs("query"),
    dspy.Example(query="이 비용 정상이야? 너무 비싼 것 같은데", intent="optimization").with_inputs("query"),

    # billing - 명확한 케이스
    dspy.Example(query="청구서 다운로드", intent="billing").with_inputs("query"),
    dspy.Example(query="결제 수단 변경하고 싶어", intent="billing").with_inputs("query"),
    dspy.Example(query="인보이스 번호 알려줘", intent="billing").with_inputs("query"),
    dspy.Example(query="크레딧 잔액 확인", intent="billing").with_inputs("query"),
    dspy.Example(query="납부 기한이 언제야?", intent="billing").with_inputs("query"),
    # billing - 애매한 케이스 (비용 언급하지만 청구)
    dspy.Example(query="지난달 청구 내역 보여줘", intent="billing").with_inputs("query"),
    dspy.Example(query="비용 청구서 PDF로 받고 싶어", intent="billing").with_inputs("query"),
    dspy.Example(query="이번 달 결제 금액 확정됐어?", intent="billing").with_inputs("query"),

    # general - 명확한 케이스
    dspy.Example(query="안녕하세요", intent="general").with_inputs("query"),
    dspy.Example(query="도움말", intent="general").with_inputs("query"),
    dspy.Example(query="OpsNow가 뭐야?", intent="general").with_inputs("query"),
    dspy.Example(query="사용 방법 알려줘", intent="general").with_inputs("query"),
    dspy.Example(query="오늘 날씨 어때?", intent="general").with_inputs("query"),
    # general - 애매한 케이스 (FinOps 관련 같지만 일반)
    dspy.Example(query="AWS 리전 목록 알려줘", intent="general").with_inputs("query"),
    dspy.Example(query="너 뭐 할 수 있어?", intent="general").with_inputs("query"),
]

# 검증용 데이터 - 어려운 케이스들 + 다국어
valset = [
    # === 한국어 (Korean) ===
    # 비용 조회 vs 최적화 헷갈리는 케이스
    dspy.Example(query="왜 이번 달 비용이 폭등했지?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="비용 많이 나온 원인 좀 줄여봐", intent="optimization").with_inputs("query"),
    # 비용 vs 청구 헷갈리는 케이스
    dspy.Example(query="3월 비용 명세서", intent="billing").with_inputs("query"),
    dspy.Example(query="3월에 EC2 얼마 썼어?", intent="cost_inquiry").with_inputs("query"),
    # 줄임말/비표준 표현
    dspy.Example(query="RI 사야됨?", intent="optimization").with_inputs("query"),
    dspy.Example(query="ㅎㅇ", intent="general").with_inputs("query"),

    # === 영어 (English) ===
    dspy.Example(query="How much did EC2 cost this month?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="How can I reduce my AWS bill?", intent="optimization").with_inputs("query"),
    dspy.Example(query="Download my invoice please", intent="billing").with_inputs("query"),
    dspy.Example(query="What is FinOps?", intent="general").with_inputs("query"),
    # 애매한 영어 케이스
    dspy.Example(query="Why is my bill so high?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="Should I buy Reserved Instances?", intent="optimization").with_inputs("query"),

    # === 일본어 (Japanese) ===
    dspy.Example(query="EC2のコストはいくらですか?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="コスト削減の方法を教えて", intent="optimization").with_inputs("query"),
    dspy.Example(query="請求書をダウンロードしたい", intent="billing").with_inputs("query"),
    dspy.Example(query="こんにちは", intent="general").with_inputs("query"),
    # 애매한 일본어 케이스
    dspy.Example(query="なぜ今月の費用が高いの?", intent="cost_inquiry").with_inputs("query"),
    dspy.Example(query="RIを購入すべき?", intent="optimization").with_inputs("query"),
]


# =============================================================================
# 3. Metric 함수
# =============================================================================

def validate_intent(example, pred, trace=None):
    """예측 의도가 정답과 일치하는지 검증"""
    return example.intent.lower() == pred.intent.lower()


# =============================================================================
# 4. 메인 실행
# =============================================================================

def test_classifier(classifier, valset, label=""):
    """분류기 테스트 및 정확도 반환"""
    correct = 0
    for example in valset:
        pred = classifier(query=example.query)
        is_correct = validate_intent(example, pred)
        correct += int(is_correct)
        status = "✓" if is_correct else "✗"
        print(f"  {status} {example.query[:30]}... → {pred.intent} (정답: {example.intent})")
    accuracy = correct / len(valset) * 100
    print(f"\n  {label} 정확도: {correct}/{len(valset)} ({accuracy:.0f}%)")
    return correct, accuracy


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME)
    dspy.configure(lm=lm)

    print("=" * 70)
    print("MIPROv2 Optimizer: Predict vs ChainOfThought 비교")
    print("=" * 70)

    # 저장 디렉토리 설정
    prompts_dir = Path(__file__).parent / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    results = {}

    # =========================================================================
    # PART A: Predict 모드
    # =========================================================================
    print("\n" + "=" * 70)
    print("[ PART A: Predict 모드 ]")
    print("=" * 70)

    # ----- Predict 최적화 전 -----
    print("\n[A-1] Predict 최적화 전")
    basic_predict = dspy.Predict(IntentClassifier)
    correct_predict_before, acc_predict_before = test_classifier(basic_predict, valset, "Predict")

    # ----- Predict 최적화 -----
    print("\n[A-2] Predict + MIPROv2 최적화 중...")
    try:
        optimizer = dspy.MIPROv2(metric=validate_intent, auto="light")
        optimized_predict = optimizer.compile(
            student=dspy.Predict(IntentClassifier),
            trainset=trainset,
            valset=valset,
        )
        print("\n[A-3] Predict 최적화 후")
        correct_predict_after, acc_predict_after = test_classifier(optimized_predict, valset, "Predict+MIPRO")
        results["Predict"] = {"before": acc_predict_before, "after": acc_predict_after}
    except Exception as e:
        print(f"  Predict 최적화 오류: {e}")
        results["Predict"] = {"before": acc_predict_before, "after": None}

    # =========================================================================
    # PART B: ChainOfThought 모드
    # =========================================================================
    print("\n" + "=" * 70)
    print("[ PART B: ChainOfThought 모드 ]")
    print("=" * 70)

    # ----- CoT 최적화 전 -----
    print("\n[B-1] ChainOfThought 최적화 전")
    basic_cot = dspy.ChainOfThought(IntentClassifier)
    correct_cot_before, acc_cot_before = test_classifier(basic_cot, valset, "CoT")

    # ----- CoT 최적화 -----
    print("\n[B-2] ChainOfThought + MIPROv2 최적화 중...")
    try:
        optimizer = dspy.MIPROv2(metric=validate_intent, auto="light")
        optimized_cot = optimizer.compile(
            student=dspy.ChainOfThought(IntentClassifier),
            trainset=trainset,
            valset=valset,
        )
        print("\n[B-3] ChainOfThought 최적화 후")
        correct_cot_after, acc_cot_after = test_classifier(optimized_cot, valset, "CoT+MIPRO")
        results["CoT"] = {"before": acc_cot_before, "after": acc_cot_after}

        # CoT 저장
        cot_path = prompts_dir / "optimized_intent_classifier_cot.json"
        optimized_cot.save(str(cot_path))
        print(f"\n  CoT 저장 완료: {cot_path.name}")

    except Exception as e:
        print(f"  CoT 최적화 오류: {e}")
        results["CoT"] = {"before": acc_cot_before, "after": None}

    # =========================================================================
    # 최종 비교
    # =========================================================================
    print("\n" + "=" * 70)
    print("[ 최종 결과 비교 ]")
    print("=" * 70)
    print(f"""
    | 모드            | 최적화 전 | 최적화 후 | 개선    |
    |-----------------|-----------|-----------|---------|""")

    for mode, scores in results.items():
        before = f"{scores['before']:.0f}%" if scores['before'] else "N/A"
        after = f"{scores['after']:.0f}%" if scores['after'] else "N/A"
        if scores['before'] and scores['after']:
            improvement = f"+{scores['after'] - scores['before']:.0f}%"
        else:
            improvement = "N/A"
        print(f"    | {mode:15} | {before:9} | {after:9} | {improvement:7} |")

    print("""
    [분석]
    - Predict: 빠름, 단순 분류에 적합
    - ChainOfThought: 추론 과정 거침, 애매한 케이스에 강함
    """)

    # Predict 버전도 저장
    try:
        predict_path = prompts_dir / "optimized_intent_classifier.json"
        optimized_predict.save(str(predict_path))
        print(f"  Predict 저장 완료: {predict_path.name}")
    except:
        pass

    # ----- 프로덕션 사용법 안내 -----
    print("\n" + "=" * 70)
    print("[프로덕션 사용법]")
    print("=" * 70)
    print("""
# Predict 버전 (빠름)
classifier = dspy.Predict(IntentClassifier)
classifier.load("prompts/optimized_intent_classifier.json")

# ChainOfThought 버전 (정확함)
classifier = dspy.ChainOfThought(IntentClassifier)
classifier.load("prompts/optimized_intent_classifier_cot.json")

result = classifier(query="EC2 비용 분석해줘")
""")


if __name__ == "__main__":
    main()
