"""
DSPy Parallel Example
PoC-3a: DSPy 프레임워크 리서치

Parallel 핵심 개념:
- dspy.Parallel: 여러 predictor를 병렬 실행
- 독립적인 분석을 동시에 처리
- 결과를 하나로 합성
"""

import os
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Signatures 정의 (각각 독립적인 분석)
# =============================================================================

class CostTrendAnalysis(dspy.Signature):
    """비용 추세를 분석합니다."""
    cost_data: str = dspy.InputField(desc="월별 비용 데이터")
    trend: str = dspy.OutputField(desc="추세 분석 (2문장)")


class AnomalyDetection(dspy.Signature):
    """비용 이상치를 탐지합니다."""
    cost_data: str = dspy.InputField(desc="월별 비용 데이터")
    anomalies: str = dspy.OutputField(desc="이상치 탐지 결과")


class OptimizationSuggestion(dspy.Signature):
    """비용 최적화를 제안합니다."""
    cost_data: str = dspy.InputField(desc="월별 비용 데이터")
    suggestions: str = dspy.OutputField(desc="최적화 제안 (bullet points)")


# =============================================================================
# 2. 순차 실행 모듈
# =============================================================================

class SequentialAnalyzer(dspy.Module):
    """순차적으로 분석 실행"""

    def __init__(self):
        super().__init__()
        self.trend_analyzer = dspy.ChainOfThought(CostTrendAnalysis)
        self.anomaly_detector = dspy.ChainOfThought(AnomalyDetection)
        self.optimizer = dspy.ChainOfThought(OptimizationSuggestion)

    def forward(self, cost_data: str):
        # 순차 실행
        trend = self.trend_analyzer(cost_data=cost_data)
        anomaly = self.anomaly_detector(cost_data=cost_data)
        optimization = self.optimizer(cost_data=cost_data)

        return dspy.Prediction(
            trend=trend.trend,
            anomalies=anomaly.anomalies,
            suggestions=optimization.suggestions,
        )


# =============================================================================
# 3. 병렬 실행 모듈
# =============================================================================

class ParallelAnalyzer(dspy.Module):
    """dspy.Parallel로 병렬 분석 실행"""

    def __init__(self):
        super().__init__()
        # 개별 분석기
        self.trend_analyzer = dspy.ChainOfThought(CostTrendAnalysis)
        self.anomaly_detector = dspy.ChainOfThought(AnomalyDetection)
        self.optimizer = dspy.ChainOfThought(OptimizationSuggestion)

        # Parallel 실행기 (새 API: exec_pairs 방식)
        self.parallel = dspy.Parallel()

    def forward(self, cost_data: str):
        # 병렬 실행 - (module, Example) 튜플 리스트
        # Example에 with_inputs()로 입력 필드 명시 필요
        example = dspy.Example(cost_data=cost_data).with_inputs("cost_data")
        exec_pairs = [
            (self.trend_analyzer, example),
            (self.anomaly_detector, example),
            (self.optimizer, example),
        ]

        results = self.parallel(exec_pairs)

        return dspy.Prediction(
            trend=results[0].trend,
            anomalies=results[1].anomalies,
            suggestions=results[2].suggestions,
        )


# =============================================================================
# 4. 테스트 데이터
# =============================================================================

COST_DATA = """
서비스별 월간 비용 (USD):
- EC2: 11월 $17,680 → 12월 $22,100 (+25%)
- RDS: 11월 $11,389 → 12월 $12,300 (+8%)
- S3: 11월 $5,361 → 12월 $5,200 (-3%)
- Lambda: 11월 $2,138 → 12월 $3,100 (+45%)

총 비용: 11월 $36,568 → 12월 $42,700 (+17%)

특이사항:
- EC2: 12월 15-18일 스파이크 발생
- Lambda: 새 기능 배포 후 호출량 급증
"""


# =============================================================================
# 5. 메인 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME, cache=False)  # 캐시 비활성화 - 공정한 성능 비교
    dspy.configure(lm=lm)

    print("=" * 60)
    print("Parallel Example - 순차 vs 병렬 실행 비교")
    print("=" * 60)

    # ----- 순차 실행 -----
    print("\n[1] 순차 실행 (Sequential)")
    print("-" * 40)

    sequential = SequentialAnalyzer()

    start = time.time()
    seq_result = sequential(cost_data=COST_DATA)
    seq_time = time.time() - start

    print(f"\n  [추세 분석]")
    print(f"  {seq_result.trend[:100]}...")
    print(f"\n  [이상치 탐지]")
    print(f"  {seq_result.anomalies[:100]}...")
    print(f"\n  [최적화 제안]")
    print(f"  {seq_result.suggestions[:100]}...")
    print(f"\n  소요 시간: {seq_time:.2f}초")

    # ----- 병렬 실행 -----
    print("\n[2] 병렬 실행 (dspy.Parallel)")
    print("-" * 40)

    parallel = ParallelAnalyzer()

    start = time.time()
    par_result = parallel(cost_data=COST_DATA)
    par_time = time.time() - start

    print(f"\n  [추세 분석]")
    print(f"  {par_result.trend[:100]}...")
    print(f"\n  [이상치 탐지]")
    print(f"  {par_result.anomalies[:100]}...")
    print(f"\n  [최적화 제안]")
    print(f"  {par_result.suggestions[:100]}...")
    print(f"\n  소요 시간: {par_time:.2f}초")

    # ----- 성능 비교 -----
    print("\n" + "=" * 60)
    print("[결과 비교]")
    print("=" * 60)
    print(f"  순차 실행: {seq_time:.2f}초")
    print(f"  병렬 실행: {par_time:.2f}초")

    if seq_time > 0 and par_time > 0:
        speedup = seq_time / par_time
        print(f"\n  속도 향상: {speedup:.1f}x")

    print("""
[참고]
- 캐시 히트 시 속도 차이가 작을 수 있음
- 캐시 없이 테스트: rm -rf ~/.dspy_cache
- dspy.Parallel은 ThreadPoolExecutor 사용
""")


if __name__ == "__main__":
    main()
