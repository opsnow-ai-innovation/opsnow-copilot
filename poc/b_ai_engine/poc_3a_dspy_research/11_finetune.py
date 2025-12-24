"""
DSPy BootstrapFinetune Example
PoC-3a: DSPy 프레임워크 리서치

BootstrapFinetune 핵심 개념:
- 프롬프트 기반 프로그램 → 모델 가중치로 증류 (Distillation)
- Teacher 모델 (큰 모델)의 지식을 Student 모델 (작은 모델)로 전이
- 런타임 효율성 향상 (few-shot 프롬프트 불필요)

⚠️ 주의: 파인튜닝은 비용이 발생할 수 있습니다!
"""

import json
import os
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)

# 파인튜닝용 모델 (파인튜닝 지원하는 최저가 모델)
FINETUNE_MODEL = "openai/gpt-4.1-nano-2025-04-14"

# Teacher 모델 (더 큰 모델 → 더 좋은 품질의 학습 데이터 생성)
TEACHER_MODEL = "openai/gpt-5.2"

# 파인튜닝 모델 정보 저장 경로
FINETUNE_INFO_PATH = Path(__file__).parent / "prompts" / "finetuned_model_info.json"


# =============================================================================
# 1. Signature 정의
# =============================================================================

class CostAnalyzer(dspy.Signature):
    """비용 데이터를 분석하여 인사이트를 제공합니다."""

    cost_data: str = dspy.InputField(desc="비용 데이터 (JSON)")
    analysis: str = dspy.OutputField(desc="비용 분석 결과 (2-3문장)")


# =============================================================================
# 2. 훈련 데이터 (30개 - OpenAI 최소 10개 요구)
# =============================================================================

trainset = [
    # === 기본 증가 케이스 (5개) ===
    dspy.Example(
        cost_data='{"service": "EC2", "nov": 17680, "dec": 22100}',
        analysis="EC2 비용이 25% 증가했습니다. Reserved Instance 적용을 검토하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "RDS", "nov": 11389, "dec": 12300}',
        analysis="RDS 비용이 8% 증가했습니다. 데이터베이스 사용량 증가에 따른 변동입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "ECS", "nov": 3200, "dec": 4100}',
        analysis="ECS 비용이 28% 증가했습니다. 컨테이너 수 증가를 확인하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "EKS", "nov": 5000, "dec": 6500}',
        analysis="EKS 비용이 30% 증가했습니다. 노드 그룹 확장을 검토하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Fargate", "nov": 2800, "dec": 3500}',
        analysis="Fargate 비용이 25% 증가했습니다. 태스크 수 최적화를 검토하세요."
    ).with_inputs("cost_data"),

    # === 기본 감소 케이스 (5개) ===
    dspy.Example(
        cost_data='{"service": "S3", "nov": 5361, "dec": 5200}',
        analysis="S3 비용이 3% 감소했습니다. 수명주기 정책이 효과적입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "CloudFront", "nov": 1200, "dec": 1000}',
        analysis="CloudFront 비용이 17% 감소했습니다. 캐시 적중률이 개선되었습니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "NAT Gateway", "nov": 800, "dec": 650}',
        analysis="NAT Gateway 비용이 19% 감소했습니다. 트래픽 최적화가 효과적입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "EBS", "nov": 2500, "dec": 2200}',
        analysis="EBS 비용이 12% 감소했습니다. 볼륨 정리가 잘 되고 있습니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Glacier", "nov": 400, "dec": 350}',
        analysis="Glacier 비용이 13% 감소했습니다. 아카이빙 정책이 효과적입니다."
    ).with_inputs("cost_data"),

    # === 급격한 변화 (5개) ===
    dspy.Example(
        cost_data='{"service": "Lambda", "nov": 2138, "dec": 5345}',
        analysis="Lambda 비용이 150% 급증했습니다. 호출 횟수와 메모리 설정을 확인하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "SageMaker", "nov": 8000, "dec": 24000}',
        analysis="SageMaker 비용이 200% 급증했습니다. 학습 인스턴스 종료 여부를 확인하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Glue", "nov": 1500, "dec": 6000}',
        analysis="Glue 비용이 300% 급증했습니다. ETL 작업 설정을 점검하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Kinesis", "nov": 600, "dec": 2400}',
        analysis="Kinesis 비용이 300% 급증했습니다. 샤드 수를 확인하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Athena", "nov": 200, "dec": 1000}',
        analysis="Athena 비용이 400% 급증했습니다. 쿼리 최적화를 검토하세요."
    ).with_inputs("cost_data"),

    # === 미세 변화 (5개) ===
    dspy.Example(
        cost_data='{"service": "Route53", "nov": 150, "dec": 147}',
        analysis="Route53 비용이 2% 감소했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "SNS", "nov": 320, "dec": 325}',
        analysis="SNS 비용이 2% 증가했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "SQS", "nov": 180, "dec": 175}',
        analysis="SQS 비용이 3% 감소했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "EventBridge", "nov": 100, "dec": 102}',
        analysis="EventBridge 비용이 2% 증가했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Secrets Manager", "nov": 50, "dec": 48}',
        analysis="Secrets Manager 비용이 4% 감소했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),

    # === 신규/중단 케이스 (5개) ===
    dspy.Example(
        cost_data='{"service": "Bedrock", "nov": 0, "dec": 3500}',
        analysis="Bedrock이 신규 도입되어 $3,500 비용이 발생했습니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "CodePipeline", "nov": 450, "dec": 0}',
        analysis="CodePipeline 비용이 0원이 되었습니다. 서비스 중단을 확인하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "AppSync", "nov": 0, "dec": 800}',
        analysis="AppSync이 신규 도입되어 $800 비용이 발생했습니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "CodeBuild", "nov": 300, "dec": 0}',
        analysis="CodeBuild 비용이 0원이 되었습니다. 빌드 중단을 확인하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Step Functions", "nov": 0, "dec": 250}',
        analysis="Step Functions이 신규 도입되어 $250 비용이 발생했습니다."
    ).with_inputs("cost_data"),

    # === 추천 포함 케이스 (5개) ===
    dspy.Example(
        cost_data='{"service": "DynamoDB", "nov": 1500, "dec": 2200}',
        analysis="DynamoDB 비용이 47% 증가했습니다. DAX 캐시 도입을 검토하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "ElastiCache", "nov": 3000, "dec": 4200}',
        analysis="ElastiCache 비용이 40% 증가했습니다. 노드 타입 최적화를 검토하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "OpenSearch", "nov": 5000, "dec": 7000}',
        analysis="OpenSearch 비용이 40% 증가했습니다. 인스턴스 타입 검토가 필요합니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Redshift", "nov": 8000, "dec": 10000}',
        analysis="Redshift 비용이 25% 증가했습니다. RA3 인스턴스 전환을 검토하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Neptune", "nov": 2000, "dec": 2800}',
        analysis="Neptune 비용이 40% 증가했습니다. 쿼리 최적화를 검토하세요."
    ).with_inputs("cost_data"),
]


# =============================================================================
# 3. 테스트 데이터 (평가용 - 어려운 케이스)
# =============================================================================

testset = [
    # === 기본 케이스 (쉬움) ===
    dspy.Example(
        cost_data='{"service": "EC2", "nov": 10000, "dec": 15000}',
        analysis="EC2 비용이 50% 증가했습니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "S3", "nov": 2000, "dec": 1800}',
        analysis="S3 비용이 10% 감소했습니다."
    ).with_inputs("cost_data"),

    # === 급격한 변화 (이상 탐지 필요) ===
    dspy.Example(
        cost_data='{"service": "Glue", "nov": 1200, "dec": 4800}',
        analysis="Glue 비용이 300% 급증했습니다. 비정상적 증가로 ETL 작업 설정을 점검하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Kinesis", "nov": 500, "dec": 2500}',
        analysis="Kinesis 비용이 400% 급증했습니다. 스트림 샤드 수와 데이터 처리량을 확인하세요."
    ).with_inputs("cost_data"),

    # === 미세 변화 (판단 어려움) ===
    dspy.Example(
        cost_data='{"service": "SNS", "nov": 320, "dec": 325}',
        analysis="SNS 비용이 1.6% 미세 증가했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "SQS", "nov": 180, "dec": 177}',
        analysis="SQS 비용이 1.7% 미세 감소했습니다. 정상 범위입니다."
    ).with_inputs("cost_data"),

    # === 3개월 추세 분석 ===
    dspy.Example(
        cost_data='{"service": "Neptune", "oct": 2000, "nov": 2500, "dec": 3200}',
        analysis="Neptune 비용이 3개월간 지속 증가 추세입니다. 그래프 데이터베이스 쿼리 최적화를 검토하세요."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "DocumentDB", "oct": 4000, "nov": 3500, "dec": 3000}',
        analysis="DocumentDB 비용이 3개월간 꾸준히 감소 중입니다. 최적화 노력이 효과를 보고 있습니다."
    ).with_inputs("cost_data"),

    # === 특수 케이스 (0원 관련) ===
    dspy.Example(
        cost_data='{"service": "AppSync", "nov": 0, "dec": 850}',
        analysis="AppSync이 12월에 신규 도입되어 비용이 발생했습니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "Step Functions", "nov": 320, "dec": 0}',
        analysis="Step Functions 비용이 0원이 되었습니다. 서비스 사용 중단을 확인하세요."
    ).with_inputs("cost_data"),

    # === 컨텍스트 포함 케이스 ===
    dspy.Example(
        cost_data='{"service": "API Gateway", "nov": 600, "dec": 1500, "event": "product_launch"}',
        analysis="API Gateway 비용이 150% 증가했습니다. 신제품 출시 이벤트로 인한 일시적 증가입니다."
    ).with_inputs("cost_data"),
    dspy.Example(
        cost_data='{"service": "OpenSearch", "nov": 5000, "dec": 7000, "cluster_count": 3}',
        analysis="OpenSearch 비용이 40% 증가했습니다. 3개 클러스터 통합 검토와 인스턴스 타입 최적화를 권장합니다."
    ).with_inputs("cost_data"),
]


# =============================================================================
# 4. Metric 함수 (강화된 검증)
# =============================================================================

def validate_analysis_strict(example, pred, trace=None):
    """분석 결과가 적절한지 검증 (엄격한 버전 - 평가용)"""
    # 최소 길이
    if len(pred.analysis) < 20:
        return False

    data = json.loads(example.cost_data)
    service = data.get("service", "").lower()
    analysis_lower = pred.analysis.lower()

    # 서비스명 포함 여부 (대소문자 무시, 공백 처리)
    service_normalized = service.replace(" ", "").replace("-", "")
    analysis_normalized = analysis_lower.replace(" ", "").replace("-", "")
    if service_normalized not in analysis_normalized:
        return False

    # 기간 데이터 추출 (oct, nov, dec 등)
    months = ["oct", "nov", "dec", "jan", "feb", "mar"]
    values = [(m, data.get(m, None)) for m in months if data.get(m) is not None]

    if len(values) < 2:
        return True  # 단일 값이면 방향 검증 불가

    # 마지막 두 달 비교
    prev_month, prev_val = values[-2]
    curr_month, curr_val = values[-1]

    # 특수 케이스: 0원에서 증가 (신규 도입)
    if prev_val == 0 and curr_val > 0:
        return "신규" in pred.analysis or "도입" in pred.analysis or "발생" in pred.analysis or "new" in analysis_lower

    # 특수 케이스: 0원으로 감소 (서비스 중단)
    if prev_val > 0 and curr_val == 0:
        return "0원" in pred.analysis or "중단" in pred.analysis or "종료" in pred.analysis or "stopped" in analysis_lower

    # 변화율 계산
    if prev_val > 0:
        change_rate = ((curr_val - prev_val) / prev_val) * 100
    else:
        change_rate = 0

    # 미세 변화 (5% 이하)
    if abs(change_rate) <= 5:
        return "미세" in pred.analysis or "정상" in pred.analysis or "자연" in pred.analysis or "slight" in analysis_lower

    # 급격한 변화 (100% 이상)
    if abs(change_rate) >= 100:
        has_urgency = "급증" in pred.analysis or "급감" in pred.analysis or "비정상" in pred.analysis or "즉시" in pred.analysis or "surge" in analysis_lower
        # 급격한 변화에 대해 경고/권장 언급 확인
        has_action = "확인" in pred.analysis or "검토" in pred.analysis or "점검" in pred.analysis or "check" in analysis_lower
        if has_urgency or has_action:
            return True

    # 일반적인 증가/감소 방향 확인
    if curr_val > prev_val:
        return "증가" in pred.analysis or "increase" in analysis_lower
    elif curr_val < prev_val:
        return "감소" in pred.analysis or "decrease" in analysis_lower

    return True


def validate_analysis(example, pred, trace=None):
    """분석 결과가 적절한지 검증 (매우 관대한 버전 - 파인튜닝 Bootstrap용)"""
    # 최소 길이만 확인 (10자 이상이면 OK)
    if len(pred.analysis) < 10:
        return False

    # 응답이 있으면 거의 다 통과
    return True


def validate_analysis_strict_debug(example, pred, trace=None):
    """분석 결과가 적절한지 검증 (엄격한 버전 - 평가용) + 실패 이유 반환"""
    # 최소 길이
    if len(pred.analysis) < 20:
        return False, "길이 부족 (<20)"

    data = json.loads(example.cost_data)
    service = data.get("service", "").lower()
    analysis_lower = pred.analysis.lower()

    # 서비스명 포함 여부 (대소문자 무시, 공백 처리)
    service_normalized = service.replace(" ", "").replace("-", "")
    analysis_normalized = analysis_lower.replace(" ", "").replace("-", "")
    if service_normalized not in analysis_normalized:
        return False, f"서비스명 미포함 ({service})"

    # 기간 데이터 추출 (oct, nov, dec 등)
    months = ["oct", "nov", "dec", "jan", "feb", "mar"]
    values = [(m, data.get(m, None)) for m in months if data.get(m) is not None]

    if len(values) < 2:
        return True, "OK (단일값)"

    # 마지막 두 달 비교
    prev_month, prev_val = values[-2]
    curr_month, curr_val = values[-1]

    # 특수 케이스: 0원에서 증가 (신규 도입)
    if prev_val == 0 and curr_val > 0:
        if "신규" in pred.analysis or "도입" in pred.analysis or "발생" in pred.analysis or "new" in analysis_lower:
            return True, "OK (신규도입)"
        return False, "신규도입 키워드 없음"

    # 특수 케이스: 0원으로 감소 (서비스 중단)
    if prev_val > 0 and curr_val == 0:
        if "0원" in pred.analysis or "중단" in pred.analysis or "종료" in pred.analysis or "stopped" in analysis_lower:
            return True, "OK (서비스중단)"
        return False, "서비스중단 키워드 없음"

    # 변화율 계산
    if prev_val > 0:
        change_rate = ((curr_val - prev_val) / prev_val) * 100
    else:
        change_rate = 0

    # 미세 변화 (5% 이하)
    if abs(change_rate) <= 5:
        if "미세" in pred.analysis or "정상" in pred.analysis or "자연" in pred.analysis or "slight" in analysis_lower:
            return True, "OK (미세변화)"
        return False, f"미세변화({change_rate:.1f}%) 키워드 없음"

    # 급격한 변화 (100% 이상)
    if abs(change_rate) >= 100:
        has_urgency = "급증" in pred.analysis or "급감" in pred.analysis or "비정상" in pred.analysis or "즉시" in pred.analysis or "surge" in analysis_lower
        has_action = "확인" in pred.analysis or "검토" in pred.analysis or "점검" in pred.analysis or "check" in analysis_lower
        if has_urgency or has_action:
            return True, "OK (급격한변화)"
        return False, f"급격한변화({change_rate:.1f}%) 키워드 없음"

    # 일반적인 증가/감소 방향 확인
    if curr_val > prev_val:
        if "증가" in pred.analysis or "increase" in analysis_lower:
            return True, "OK (증가)"
        return False, "증가 키워드 없음"
    elif curr_val < prev_val:
        if "감소" in pred.analysis or "decrease" in analysis_lower:
            return True, "OK (감소)"
        return False, "감소 키워드 없음"

    return True, "OK"


def evaluate_model(model, testset, label="", verbose=False):
    """모델 평가 (상세 결과 포함) - 엄격한 검증 사용"""
    correct = 0
    results_by_category = {
        "basic": {"total": 0, "correct": 0, "name": "기본 증감"},
        "surge": {"total": 0, "correct": 0, "name": "급격한 변화"},
        "micro": {"total": 0, "correct": 0, "name": "미세 변화"},
        "trend": {"total": 0, "correct": 0, "name": "3개월 추세"},
        "zero": {"total": 0, "correct": 0, "name": "0원 케이스"},
        "context": {"total": 0, "correct": 0, "name": "컨텍스트 포함"},
    }

    print(f"\n  [{label}]")
    for i, example in enumerate(testset):
        pred = model(cost_data=example.cost_data)
        is_correct, fail_reason = validate_analysis_strict_debug(example, pred)  # 디버그 버전
        correct += int(is_correct)
        status = "✓" if is_correct else "✗"
        data = json.loads(example.cost_data)

        # 카테고리 분류
        if i < 2:
            cat = "basic"
        elif i < 4:
            cat = "surge"
        elif i < 6:
            cat = "micro"
        elif i < 8:
            cat = "trend"
        elif i < 10:
            cat = "zero"
        else:
            cat = "context"

        results_by_category[cat]["total"] += 1
        results_by_category[cat]["correct"] += int(is_correct)

        # 실패 이유 출력
        reason_str = f" ({fail_reason})" if not is_correct else ""
        print(f"  {status} [{results_by_category[cat]['name']}] {data['service']}: {pred.analysis[:40]}...{reason_str}")

    accuracy = correct / len(testset) * 100
    print(f"\n  전체 정확도: {correct}/{len(testset)} ({accuracy:.0f}%)")

    # 카테고리별 결과 요약
    print("\n  [카테고리별 정확도]")
    for cat, info in results_by_category.items():
        if info["total"] > 0:
            cat_acc = info["correct"] / info["total"] * 100
            print(f"    - {info['name']}: {info['correct']}/{info['total']} ({cat_acc:.0f}%)")

    return correct, accuracy


# =============================================================================
# 5. 파인튜닝 모델 관리
# =============================================================================

def load_finetuned_model_info():
    """저장된 파인튜닝 모델 정보 로드"""
    if FINETUNE_INFO_PATH.exists():
        with open(FINETUNE_INFO_PATH, "r") as f:
            return json.load(f)
    return None


def save_finetuned_model_info(model_id, base_model):
    """파인튜닝 모델 정보 저장"""
    FINETUNE_INFO_PATH.parent.mkdir(exist_ok=True)
    info = {
        "finetuned_model_id": model_id,
        "base_model": base_model,
        "trainset_size": len(trainset),
    }
    with open(FINETUNE_INFO_PATH, "w") as f:
        json.dump(info, f, indent=2)
    return info


# =============================================================================
# 6. 메인 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key

    print("=" * 70)
    print("BootstrapFinetune - 실제 파인튜닝 테스트")
    print("=" * 70)

    # 데이터셋 통계 출력
    print(f"""
    [데이터셋 정보]
    - 훈련 데이터: {len(trainset)}개 예제
    - 테스트 데이터: {len(testset)}개 예제

    [훈련 데이터 구성]
    - 기본 증가: 5개
    - 기본 감소: 5개
    - 급격한 변화: 5개
    - 미세 변화: 5개
    - 신규/중단: 5개
    - 추천 포함: 5개
    """)

    # 기본 모델 설정 (파인튜닝과 동일한 베이스 모델 사용)
    base_lm = dspy.LM(model=FINETUNE_MODEL)
    dspy.configure(lm=base_lm)

    # =========================================================================
    # STEP 1: 기본 모델 평가 (파인튜닝 전)
    # =========================================================================
    print("[STEP 1] 기본 모델 평가 (파인튜닝 전)")
    print("-" * 50)

    basic_model = dspy.ChainOfThought(CostAnalyzer)
    _, acc_before = evaluate_model(basic_model, testset, f"기본 모델 ({FINETUNE_MODEL})")

    # =========================================================================
    # STEP 2: 파인튜닝 실행 또는 기존 모델 로드
    # =========================================================================
    print("\n[STEP 2] 파인튜닝 확인")
    print("-" * 50)

    finetuned_info = load_finetuned_model_info()

    if finetuned_info:
        print(f"\n  기존 파인튜닝 모델 발견!")
        print(f"  - Model ID: {finetuned_info['finetuned_model_id']}")
        print(f"  - Base Model: {finetuned_info['base_model']}")
        print(f"  - Trainset Size: {finetuned_info['trainset_size']}")

        # 파인튜닝된 모델로 LM 설정
        finetuned_model_id = finetuned_info['finetuned_model_id']

    else:
        print("\n  파인튜닝된 모델이 없습니다. 새로 파인튜닝을 실행합니다.")
        print("  ⚠️  비용이 발생할 수 있습니다!")

        # 실제 파인튜닝 실행
        try:
            from dspy.teleprompt import BootstrapFinetune

            print("\n  [파인튜닝 시작]")
            print(f"  - Teacher: {TEACHER_MODEL} (큰 모델)")
            print(f"  - Student: {FINETUNE_MODEL} (파인튜닝 대상)")
            print(f"  - Trainset: {len(trainset)}개")

            # 파인튜닝용 LM 설정
            finetune_lm = dspy.LM(model=FINETUNE_MODEL)
            teacher_lm = dspy.LM(model=TEACHER_MODEL)

            # DSPy 3.0 API: teacher는 compile()에서 전달
            optimizer = BootstrapFinetune(
                metric=validate_analysis,
            )

            # Student: 파인튜닝 대상 (작은 모델), Teacher: 큰 모델
            student_program = dspy.ChainOfThought(CostAnalyzer)
            student_program.set_lm(finetune_lm)

            teacher_program = dspy.ChainOfThought(CostAnalyzer)
            teacher_program.set_lm(teacher_lm)  # 큰 모델이 Teacher

            print("\n  파인튜닝 중... (몇 분 소요될 수 있습니다)")

            finetuned_program = optimizer.compile(
                student=student_program,
                trainset=trainset,
                teacher=teacher_program,
            )

            # 파인튜닝된 모델 ID 추출
            # DSPy 3.0에서는 finetuned_program의 predictor에서 LM 확인
            finetuned_model_id = None
            try:
                # 방법 1: predictors에서 LM 모델 ID 추출
                for predictor in finetuned_program.predictors():
                    if hasattr(predictor, 'lm') and predictor.lm:
                        model_id = getattr(predictor.lm, 'model', None)
                        if model_id and model_id.startswith('ft:'):
                            finetuned_model_id = model_id
                            break

                # 방법 2: 모듈 자체의 lm 확인
                if not finetuned_model_id and hasattr(finetuned_program, 'lm'):
                    model_id = getattr(finetuned_program.lm, 'model', None)
                    if model_id and model_id.startswith('ft:'):
                        finetuned_model_id = model_id
            except Exception as e:
                print(f"  모델 ID 추출 중 오류: {e}")

            if not finetuned_model_id:
                print("\n  ⚠️  파인튜닝 모델 ID를 자동 추출하지 못했습니다.")
                print("  OpenAI 콘솔에서 모델 ID를 확인하고 prompts/finetuned_model_info.json에 수동 입력하세요.")
                print("  예: ft:gpt-4.1-nano-2025-04-14:opsnow::xxxxx")
                return

            # 모델 정보 저장
            save_finetuned_model_info(finetuned_model_id, FINETUNE_MODEL)
            print(f"\n  ✓ 파인튜닝 완료!")
            print(f"  - Model ID: {finetuned_model_id}")

        except ImportError as e:
            print(f"\n  BootstrapFinetune import 오류: {e}")
            print("  DSPy 버전을 확인하세요.")
            return
        except Exception as e:
            print(f"\n  파인튜닝 오류: {e}")
            import traceback
            traceback.print_exc()
            print("  파인튜닝을 건너뛰고 기본 모델로 계속합니다.")
            finetuned_model_id = None

    # =========================================================================
    # STEP 3: 파인튜닝 모델 평가
    # =========================================================================
    if finetuned_info or finetuned_model_id:
        print("\n[STEP 3] 파인튜닝 모델 평가")
        print("-" * 50)

        try:
            # 파인튜닝된 모델로 설정
            model_id = finetuned_info['finetuned_model_id'] if finetuned_info else finetuned_model_id
            finetuned_lm = dspy.LM(model=model_id)
            dspy.configure(lm=finetuned_lm)

            finetuned_model = dspy.ChainOfThought(CostAnalyzer)
            _, acc_after = evaluate_model(finetuned_model, testset, f"파인튜닝 모델 ({model_id})")

            # =========================================================================
            # STEP 4: 결과 비교
            # =========================================================================
            print("\n[STEP 4] 결과 비교")
            print("=" * 70)
            print(f"""
    | 모델                | 정확도    |
    |---------------------|-----------|
    | 기본 ({FINETUNE_MODEL}) | {acc_before:.0f}%      |
    | 파인튜닝            | {acc_after:.0f}%      |
    | 개선                | {acc_after - acc_before:+.0f}%      |
""")

        except Exception as e:
            print(f"\n  파인튜닝 모델 로드 오류: {e}")
            print("  모델 ID가 유효하지 않을 수 있습니다.")

    # =========================================================================
    # 참고 정보
    # =========================================================================
    print("\n" + "=" * 70)
    print("[참고] 파인튜닝 모델 관리")
    print("=" * 70)
    print(f"""
  - 모델 정보 저장 위치: {FINETUNE_INFO_PATH}
  - 재실행 시 기존 모델 재사용
  - 새로 파인튜닝하려면: rm {FINETUNE_INFO_PATH}
""")


if __name__ == "__main__":
    main()
