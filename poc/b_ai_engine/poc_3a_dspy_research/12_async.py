"""
DSPy Async Example
PoC-3a: DSPy 프레임워크 리서치

Async 핵심 개념:
- asyncify: 동기 모듈 → 비동기 변환
- aforward(): 비동기 forward 메서드 직접 구현
- asyncio.gather(): 여러 요청 동시 처리
"""

import asyncio
import os
import time
from pathlib import Path

import dspy
from dotenv import load_dotenv

from config import MODEL_NAME

env_path = Path(__file__).parent / ".env.local"
load_dotenv(dotenv_path=env_path)


# =============================================================================
# 1. Signature 정의
# =============================================================================

class CostSummary(dspy.Signature):
    """AWS 서비스 비용을 한 문장으로 요약합니다."""

    service: str = dspy.InputField(desc="AWS 서비스명")
    cost: int = dspy.InputField(desc="월간 비용 (USD)")
    summary: str = dspy.OutputField(desc="비용 요약 (한 문장)")


# =============================================================================
# 2. 비동기 모듈 (aforward 직접 구현)
# =============================================================================

class AsyncCostAnalyzer(dspy.Module):
    """비동기 비용 분석 모듈 (aforward 구현)"""

    def __init__(self):
        super().__init__()
        self.summarizer = dspy.Predict(CostSummary)  # Predict 사용 (더 빠름)

    def forward(self, service: str, cost: int):
        """동기 버전"""
        return self.summarizer(service=service, cost=cost)

    async def aforward(self, service: str, cost: int):
        """비동기 버전 - asyncio와 함께 사용"""
        # DSPy 내부적으로 비동기 처리
        # 실제로는 asyncify를 사용하는 것이 더 간단
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.summarizer(service=service, cost=cost)
        )
        return result


# =============================================================================
# 3. 테스트 데이터 (3개로 축소 - 빠른 테스트)
# =============================================================================

SERVICES = [
    ("EC2", 22100),
    ("RDS", 12300),
    ("S3", 5200),
]


# =============================================================================
# 4. 동기 실행 (순차)
# =============================================================================

def run_sync(analyzer):
    """동기 방식으로 순차 실행"""
    results = []
    for service, cost in SERVICES:
        result = analyzer(service=service, cost=cost)
        results.append((service, result.summary))
    return results


# =============================================================================
# 5. 비동기 실행 (병렬)
# =============================================================================

async def run_async_with_gather(analyzer):
    """asyncio.gather를 사용한 비동기 실행 (ThreadPoolExecutor)"""
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=len(SERVICES)) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                lambda s=service, c=cost: analyzer(service=s, cost=c)
            )
            for service, cost in SERVICES
        ]
        results = await asyncio.gather(*tasks)

    return [(SERVICES[i][0], r.summary) for i, r in enumerate(results)]


async def run_async_with_aforward(analyzer):
    """aforward를 사용한 비동기 실행"""
    tasks = [
        analyzer.aforward(service=service, cost=cost)
        for service, cost in SERVICES
    ]

    results = await asyncio.gather(*tasks)
    return [(SERVICES[i][0], r.summary) for i, r in enumerate(results)]


# =============================================================================
# 6. 메인 실행
# =============================================================================

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    os.environ["OPENAI_API_KEY"] = api_key
    lm = dspy.LM(model=MODEL_NAME, cache=False)  # 캐시 비활성화 - 공정한 성능 비교
    dspy.configure(lm=lm)

    print("=" * 60)
    print("Async Example - 동기 vs 비동기 성능 비교")
    print("=" * 60)

    analyzer = AsyncCostAnalyzer()

    # ----- 동기 실행 -----
    print("\n[1] 동기 실행 (순차)")
    print("-" * 40)

    start = time.time()
    sync_results = run_sync(analyzer)
    sync_time = time.time() - start

    for service, summary in sync_results:
        print(f"  {service}: {summary[:50]}...")

    print(f"\n  소요 시간: {sync_time:.2f}초")

    # ----- 비동기 실행 (ThreadPoolExecutor) -----
    print("\n[2] 비동기 실행 (ThreadPoolExecutor)")
    print("-" * 40)

    start = time.time()
    async_results = asyncio.run(run_async_with_gather(analyzer))
    async_time = time.time() - start

    for service, summary in async_results:
        print(f"  {service}: {summary[:50]}...")

    print(f"\n  소요 시간: {async_time:.2f}초")

    # ----- 비동기 실행 (aforward) -----
    print("\n[3] 비동기 실행 (aforward)")
    print("-" * 40)

    start = time.time()
    aforward_results = asyncio.run(run_async_with_aforward(analyzer))
    aforward_time = time.time() - start

    for service, summary in aforward_results:
        print(f"  {service}: {summary[:50]}...")

    print(f"\n  소요 시간: {aforward_time:.2f}초")

    # ----- 성능 비교 -----
    print("\n" + "=" * 60)
    print("[결과 비교]")
    print("=" * 60)
    print(f"  동기 (순차):       {sync_time:.2f}초")
    print(f"  비동기 (gather):   {async_time:.2f}초")
    print(f"  비동기 (aforward): {aforward_time:.2f}초")

    if sync_time > 0:
        speedup_gather = sync_time / async_time if async_time > 0 else 0
        speedup_aforward = sync_time / aforward_time if aforward_time > 0 else 0
        print(f"\n  gather 속도 향상:  {speedup_gather:.1f}x")
        print(f"  aforward 속도 향상: {speedup_aforward:.1f}x")

    print("""
[참고]
- 캐시 히트 시 속도 차이가 작을 수 있음
- 첫 실행 시 캐시 없이 테스트하려면:
  rm -rf ~/.dspy_cache
""")


if __name__ == "__main__":
    main()
