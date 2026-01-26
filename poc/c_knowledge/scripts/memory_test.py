"""
장기 기억 정확도 테스트 러너

사용법:
    python scripts/memory_test.py --turns 20 --checkpoints 5,10,15,20

테스트 절차:
    1. 랜덤 필터로 다양한 화면 데이터 생성
    2. 자동으로 대화 진행 (10-20턴)
    3. 체크포인트에서 메모리 평가 (LLM-as-Judge)
    4. 오류 유형별 분석 결과 출력
"""

import asyncio
import argparse
import json
import os
import sys
import random
import logging
from datetime import datetime

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OPENAI_MODEL
from src.mock.users import get_random_user, generate_session_id
from src.mock.dom_context import generate_random_dom_context
from src.utils.secrets import get_open_ai_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 테스트 질문 템플릿 (화면 유형별)
QUESTION_TEMPLATES = {
    "cost_overview": [
        "현재 비용 추세가 어때?",
        "어떤 클라우드가 가장 비용이 많이 나와?",
        "비용 절감할 수 있는 방법 있어?",
        "지난 기간 대비 비용 변화는?",
        "가장 비용 증가가 큰 항목이 뭐야?",
        "이번 달 예상 비용은 얼마야?",
        "비용 트렌드 분석해줘",
        "AWS 비용이 왜 이렇게 높아?",
    ],
    "govern_kpi": [
        "현재 KPI 달성률은?",
        "어떤 KPI가 가장 저조해?",
        "거버넌스 개선 방향 제안해줘",
        "규정 준수 현황 알려줘",
        "리스크가 높은 영역이 어디야?",
        "KPI 트렌드가 어떻게 변하고 있어?",
        "개선이 필요한 항목 우선순위 알려줘",
    ],
    "optimize_commitments": [
        "현재 커밋먼트 활용률은?",
        "어떤 커밋먼트를 추가해야 할까?",
        "최적화 기회가 있는 곳이 어디야?",
        "RI 커버리지는 어때?",
        "Savings Plans 추천해줘",
        "낭비되는 리소스가 있어?",
        "커밋먼트 만료 예정인 거 있어?",
    ],
}

# 회상 테스트용 질문 (이전 대화 내용 기억 확인)
RECALL_QUESTIONS = [
    "아까 내가 물어본 첫 번째 질문이 뭐였어?",
    "우리가 처음에 어떤 화면 보고 있었어?",
    "비용 관련해서 내가 뭘 물어봤었지?",
    "이전에 내가 관심 가졌던 클라우드가 뭐였어?",
    "지금까지 대화 요약해줘",
]


class MemoryTestRunner:
    """장기 기억 테스트 러너"""

    def __init__(self, max_turns: int = 20, checkpoints: list[int] = None):
        self.max_turns = max_turns
        self.checkpoints = checkpoints or [5, 10, 15, 20]
        self.server_url = os.getenv("RAG_SERVER_URL", "http://localhost:8000")
        self.http_client = None
        self.llm_client = None
        self.user = get_random_user()
        self.session = f"{self.user.user_id}:{generate_session_id()}"

        # 대화 기록 (평가용)
        self.conversation_log: list[dict] = []
        self.dom_contexts: list[dict] = []
        self.evaluation_results: list[dict] = []

    async def initialize(self):
        """초기화"""
        self.http_client = httpx.AsyncClient(base_url=self.server_url, timeout=120.0)
        self.llm_client = AsyncOpenAI(api_key=get_open_ai_key())
        logger.info(f"테스트 세션: {self.session}")
        logger.info(f"최대 턴: {self.max_turns}, 체크포인트: {self.checkpoints}")

    async def close(self):
        """종료"""
        if self.http_client:
            await self.http_client.aclose()

    def _generate_question(self, screen_type: str, turn: int) -> str:
        """화면 유형에 맞는 질문 생성"""
        # 가끔 회상 테스트 질문 삽입 (5턴 이후, 20% 확률)
        if turn > 5 and random.random() < 0.2:
            return random.choice(RECALL_QUESTIONS)

        templates = QUESTION_TEMPLATES.get(screen_type, QUESTION_TEMPLATES["cost_overview"])
        return random.choice(templates)

    async def send_chat(self, query: str, dom_context: str) -> dict:
        """서버에 대화 요청"""
        # 1. RAG 조회
        rag_payload = {
            "query": query,
            "session": self.session,
            "user_id": self.user.user_id,
            "dom_context": dom_context,
        }
        try:
            response = await self.http_client.post("/rag/retrieve", json=rag_payload)
            response.raise_for_status()
            rag_data = response.json()
        except httpx.HTTPError as exc:
            logger.error(f"RAG 조회 실패: {exc}")
            return {"answer": "[RAG 실패]", "rag": {}}

        # 2. LLM 답변 생성 (간단히 직접 호출)
        ranked_results = rag_data.get("ranked_results", [])
        faq_context = "\n".join([r["content"] for r in ranked_results[:3]])

        prompt = f"""대화 맥락:
{faq_context}

화면 정보:
{dom_context[:500]}

사용자 질문: {query}

간결하게 답변해주세요."""

        try:
            response = await self.llm_client.responses.create(
                model=OPENAI_MODEL,
                input=prompt,
            )
            answer = response.output_text or "[응답 없음]"
        except Exception as exc:
            logger.error(f"LLM 생성 실패: {exc}")
            answer = "[LLM 실패]"

        # 3. 대화 저장
        save_payload = {
            "session": self.session,
            "user_id": self.user.user_id,
            "query": query,
            "answer": answer,
        }
        try:
            await self.http_client.post("/chat/save", json=save_payload)
        except httpx.HTTPError as exc:
            logger.error(f"대화 저장 실패: {exc}")

        return {"answer": answer, "rag": rag_data}

    async def fetch_memory(self) -> dict:
        """현재 메모리 상태 조회"""
        payload = {"session": self.session}
        try:
            response = await self.http_client.post("/rag/debug/memory", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.error(f"메모리 조회 실패: {exc}")
            return {}

    async def evaluate_memory(self, turn: int) -> dict:
        """LLM-as-Judge로 메모리 정확도 평가"""
        memory = await self.fetch_memory()

        # 대화 로그를 텍스트로 변환
        conversation_text = "\n".join([
            f"[Turn {i+1}] User: {log['query']}\nAssistant: {log['answer'][:200]}..."
            for i, log in enumerate(self.conversation_log)
        ])

        long_term_memory = memory.get("long_term", "") or "(없음)"
        entities = memory.get("entities", {}) or {}

        eval_prompt = f"""당신은 AI 메모리 시스템 평가자입니다.
아래 대화 기록과 저장된 장기 기억을 비교하여 정확도를 평가해주세요.

## 실제 대화 기록 (Turn 1 ~ {turn})
{conversation_text}

## 저장된 장기 기억
{long_term_memory}

## 저장된 엔티티
{json.dumps(entities, ensure_ascii=False)}

## 평가 기준
다음 오류 유형을 체크하고 각각 점수(0-10)를 매겨주세요:
1. over_inference (과잉 추론): 대화에 없는 내용을 추가했는가?
2. omission (누락): 중요한 정보가 빠졌는가?
3. distortion (왜곡): 정보가 잘못 저장되었는가?
4. update_failure (업데이트 실패): 새 정보로 갱신이 안 되었는가?
5. irrelevance (무관함): 관련 없는 정보가 저장되었는가?

## 응답 형식 (JSON만)
{{
    "overall_score": 0-100,
    "errors": {{
        "over_inference": {{"score": 0-10, "examples": ["..."]}},
        "omission": {{"score": 0-10, "examples": ["..."]}},
        "distortion": {{"score": 0-10, "examples": ["..."]}},
        "update_failure": {{"score": 0-10, "examples": ["..."]}},
        "irrelevance": {{"score": 0-10, "examples": ["..."]}}
    }},
    "summary": "한 줄 평가",
    "improvement_suggestions": ["개선 제안 1", "개선 제안 2"]
}}"""

        try:
            response = await self.llm_client.responses.create(
                model=OPENAI_MODEL,
                input=eval_prompt,
            )
            result_text = response.output_text or "{}"
            # JSON 파싱 시도
            try:
                # JSON 블록 추출
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]
                result = json.loads(result_text.strip())
            except json.JSONDecodeError:
                result = {"raw": result_text, "parse_error": True}
        except Exception as exc:
            logger.error(f"평가 실패: {exc}")
            result = {"error": str(exc)}

        result["turn"] = turn
        result["memory_snapshot"] = {
            "long_term": long_term_memory[:500],
            "entities": entities,
        }
        return result

    async def run(self):
        """테스트 실행"""
        await self.initialize()

        print("\n" + "=" * 60)
        print("장기 기억 정확도 테스트")
        print("=" * 60)
        print(f"세션: {self.session}")
        print(f"최대 턴: {self.max_turns}")
        print(f"체크포인트: {self.checkpoints}")
        print("=" * 60 + "\n")

        try:
            for turn in range(1, self.max_turns + 1):
                # 랜덤 화면 데이터 생성 (가끔 화면 전환)
                if turn == 1 or random.random() < 0.3:
                    dom_context_raw = generate_random_dom_context()
                    dom_data = json.loads(dom_context_raw)
                    screen_type = dom_data.get("generated", {}).get("screen_type", "cost_overview")
                    self.dom_contexts.append({
                        "turn": turn,
                        "screen_type": screen_type,
                        "data": dom_data,
                    })
                    print(f"[화면 변경] → {screen_type}")
                else:
                    # 이전 화면 유지
                    dom_context_raw = json.dumps(self.dom_contexts[-1]["data"], ensure_ascii=False)
                    screen_type = self.dom_contexts[-1]["screen_type"]

                # 질문 생성
                question = self._generate_question(screen_type, turn)

                # 대화 실행
                print(f"\n[Turn {turn}] User: {question}")
                result = await self.send_chat(question, dom_context_raw)
                answer = result["answer"]
                print(f"[Turn {turn}] Assistant: {answer[:100]}...")

                # 로그 저장
                self.conversation_log.append({
                    "turn": turn,
                    "query": question,
                    "answer": answer,
                    "screen_type": screen_type,
                })

                # 체크포인트에서 평가
                if turn in self.checkpoints:
                    print(f"\n{'=' * 40}")
                    print(f"[체크포인트 {turn}턴] 메모리 평가 중...")
                    print("=" * 40)

                    eval_result = await self.evaluate_memory(turn)
                    self.evaluation_results.append(eval_result)

                    if "overall_score" in eval_result:
                        print(f"전체 점수: {eval_result['overall_score']}/100")
                        print(f"요약: {eval_result.get('summary', 'N/A')}")
                        if "errors" in eval_result:
                            for err_type, err_data in eval_result["errors"].items():
                                print(f"  - {err_type}: {err_data.get('score', 'N/A')}/10")
                    else:
                        print(f"평가 결과: {json.dumps(eval_result, ensure_ascii=False, indent=2)[:500]}")

            # 최종 리포트
            self._print_final_report()

        finally:
            await self.close()

    def _print_final_report(self):
        """최종 리포트 출력"""
        print("\n" + "=" * 60)
        print("최종 테스트 리포트")
        print("=" * 60)
        print(f"총 대화 턴: {len(self.conversation_log)}")
        print(f"화면 전환 횟수: {len(self.dom_contexts)}")
        print(f"평가 횟수: {len(self.evaluation_results)}")

        if self.evaluation_results:
            print("\n[체크포인트별 점수]")
            for result in self.evaluation_results:
                turn = result.get("turn", "?")
                score = result.get("overall_score", "N/A")
                summary = result.get("summary", "")
                print(f"  Turn {turn}: {score}/100 - {summary[:50]}")

            # 오류 유형별 평균 점수
            error_types = ["over_inference", "omission", "distortion", "update_failure", "irrelevance"]
            print("\n[오류 유형별 평균 점수 (낮을수록 좋음)]")
            for err_type in error_types:
                scores = []
                for result in self.evaluation_results:
                    if "errors" in result and err_type in result["errors"]:
                        score = result["errors"][err_type].get("score")
                        if isinstance(score, (int, float)):
                            scores.append(score)
                if scores:
                    avg = sum(scores) / len(scores)
                    print(f"  {err_type}: {avg:.1f}/10")

            # 개선 제안 수집
            suggestions = set()
            for result in self.evaluation_results:
                for s in result.get("improvement_suggestions", []):
                    suggestions.add(s)

            if suggestions:
                print("\n[개선 제안]")
                for i, s in enumerate(list(suggestions)[:5], 1):
                    print(f"  {i}. {s}")

        # JSON 파일로 저장
        report_path = f"memory_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report = {
            "session": self.session,
            "max_turns": self.max_turns,
            "checkpoints": self.checkpoints,
            "conversation_log": self.conversation_log,
            "dom_contexts": [{"turn": d["turn"], "screen_type": d["screen_type"]} for d in self.dom_contexts],
            "evaluation_results": self.evaluation_results,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[리포트 저장됨] {report_path}")
        print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="장기 기억 정확도 테스트")
    parser.add_argument("--turns", type=int, default=20, help="최대 대화 턴 수 (기본: 20)")
    parser.add_argument(
        "--checkpoints",
        type=str,
        default="5,10,15,20",
        help="평가 체크포인트 (콤마 구분, 기본: 5,10,15,20)",
    )
    args = parser.parse_args()

    checkpoints = [int(x.strip()) for x in args.checkpoints.split(",")]

    runner = MemoryTestRunner(max_turns=args.turns, checkpoints=checkpoints)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())