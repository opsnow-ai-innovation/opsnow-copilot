"""
터미널 챗 인터페이스

TODO: 합칠 때 제거 - API로 대체
- 이 파일은 테스트/개발용 CLI입니다
- 실제 서비스에서는 WebSocket API로 대체됩니다
"""

import asyncio
import json
import os
import sys
import logging
import re
import httpx

from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OPENAI_MODEL
from src.models import MemoryContext, Turn
from src.processors.context_builder_processor import build_llm_context
from src.rag_assistant.dom_parser import DomContextParser
from src.mock.users import (
    MockUser,
    RESET_COLOR,
    get_random_user,
    generate_session_id,
    print_user_banner,
)
from src.mock.dom_context import (
    get_cost_overview_dom_context,
    get_govern_kpi_dom_context,
    get_optimize_my_commitments_dom_context,
    get_random_dom_context,
    # TODO: remove before production - filter-based random generation
    generate_random_dom_context,
    get_filter_options,
    SCREEN_OPTIONS,
    PERIOD_OPTIONS,
    TREND_OPTIONS,
    PROVIDER_OPTIONS,
)
from src.utils.text import sanitize_text
from src.utils.secrets import get_open_ai_key

logger = logging.getLogger(__name__)

class ChatCLI:
    """
    TODO: 합칠 때 제거 - 터미널 챗 인터페이스

    사용법:
        python scripts/chat_cli.py

    명령어:
        /clear - 세션 초기화
        /memory - 현재 메모리 상태 확인
        /history - 대화 히스토리 확인
        /context - RAG 검색 결과만 확인
        /user - 현재 유저 정보 확인
        /switch [화면] - 화면 전환 (cost, govern, optimize)
        /filter [key] [value] - 필터 설정/확인 (screen, period, trend, providers)
        /random - 현재 필터로 랜덤 데이터 생성
        /eval [쿼리] - 쿼리에 대한 메모리 유용성 평가 (LLM-as-Judge)
        /quit - 종료
    """

    def __init__(self, user: MockUser, session_id: str):
        self.user = user
        self.session = f"{user.user_id}:{session_id}"
        self.turn_count = 0
        self.server_url = os.getenv("RAG_SERVER_URL", "http://localhost:8000")
        self.http_client = None
        self.llm_client = None
        self.dom_parser = DomContextParser()
        self.dom_context_raw = get_random_dom_context()
        # 필터 상태 (None = 랜덤)
        self.filter_screen: str | None = None
        self.filter_period: str | None = None
        self.filter_trend: str | None = None
        self.filter_providers: list[str] | None = None

    def _get_dom_context_page(self) -> str:
        """Return page path from domContext if available."""
        try:
            data = json.loads(self.dom_context_raw)
        except json.JSONDecodeError:
            return "unknown"
        return data.get("page") or data.get("current_page") or "unknown"

    @staticmethod
    def _sanitize_command_input(text: str) -> str:
        """Strip invisible/bom characters from command input."""
        cleaned = sanitize_text(text)
        return re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", cleaned)

    async def initialize(self):
        """초기화"""
        self.http_client = httpx.AsyncClient(base_url=self.server_url, timeout=120.0)
        self.llm_client = AsyncOpenAI(api_key=get_open_ai_key())

        self.turn_count = 0

    async def close(self):
        """종료"""
        if self.http_client:
            await self.http_client.aclose()

    async def fetch_ranked_results(self, query: str) -> dict:
        """서버에서 정렬된 RAG 결과 조회"""
        payload = {
            "query": query.encode("utf-8", errors="ignore").decode("utf-8"),
            "session": self.session,
            "user_id": self.user.user_id,
            "dom_context": self.dom_context_raw.encode("utf-8", errors="ignore").decode("utf-8"),
        }
        logger.debug("RAG request: %s", payload)
        try:
            response = await self.http_client.post("/rag/retrieve", json=payload)
            response.raise_for_status()
            data = response.json()
            logger.debug("RAG response: results=%s", len(data.get("ranked_results", [])))
            return data
        except httpx.ReadTimeout:
            logger.error("RAG 서버 응답 시간 초과: %s", self.server_url)
            return {"ranked_results": [], "sources": [], "confidence": 0.0, "is_sufficient": False}
        except httpx.HTTPError as exc:
            logger.error("RAG 서버 호출 실패: %s", exc)
            return {"ranked_results": [], "sources": [], "confidence": 0.0, "is_sufficient": False}

    async def fetch_memory_context(self) -> MemoryContext:
        """서버에서 메모리 컨텍스트 조회"""
        payload = {"session": self.session}
        try:
            response = await self.http_client.post("/rag/debug/memory", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.error("메모리 조회 실패: %s", exc)
            return MemoryContext()

        short_term = [
            Turn(turn=item.get("turn", 0), user=item.get("user", ""), assistant=item.get("assistant", ""))
            for item in data.get("short_term", [])
        ]
        return MemoryContext(
            short_term=short_term,
            memory=data.get("long_term", "") or "",
            entities=data.get("entities", {}) or {},
        )

    async def generate_answer(self, query: str, ranked_results: list[dict]) -> str:
        """정렬된 RAG 결과로 LLM 답변 생성"""
        memory = await self.fetch_memory_context()
        dom_context = self.dom_parser.parse(self.dom_context_raw)
        dom_summary = dom_context.summary
        faq_results = [r["content"] for r in ranked_results]
        llm_ctx = build_llm_context(memory, faq_results=faq_results)

        prompt = (
            f"{llm_ctx.build_prompt_sections()}\n\n"
            f"## 화면 정보 요약\n{dom_summary}\n\n"
            f"## 화면 domContext\n{self.dom_context_raw}\n\n"
            f"## 사용자 질문\n{query}\n\n"
            "규칙:\n"
            "- 질문 언어로 답변\n"
            "- 필요한 경우 단계별로 설명\n"
            "- 근거가 있는 경우 출처를 간단히 언급\n"
        )
        prompt = prompt.encode("utf-8", errors="ignore").decode("utf-8")
        print(repr(prompt))

        try:
            response = await self.llm_client.responses.create(
                model=OPENAI_MODEL,
                input=prompt,
            )
            print(response)
            content = self._extract_response_text(response)
            if not content:
                logger.error("LLM returned empty content")
                return await self._retry_generate_answer(query, llm_ctx, dom_summary)
            return content.strip()
        except Exception as exc:
            logger.error("LLM generate failed: %s", exc)
            return await self._retry_generate_answer(query, llm_ctx, dom_summary)

    async def _retry_generate_answer(self, query: str, llm_ctx, dom_summary: str) -> str:
        """LLM 응답이 비거나 실패했을 때 1회 재시도"""
        retry_prompt = (
            f"{llm_ctx.build_prompt_sections()}\n\n"
            f"## 화면 정보 요약\n{dom_summary}\n\n"
            f"## 화면 domContext\n{self.dom_context_raw}\n\n"
            f"## 사용자 질문\n{query}\n\n"
            "규칙:\n"
            "- 질문 언어로 답변\n"
            "- 필요한 경우 단계별로 설명\n"
        )
        retry_prompt = retry_prompt.encode("utf-8", errors="ignore").decode("utf-8")
        logger.debug(
            "LLM retry prompt sanitized: len=%s head=%s",
            len(retry_prompt),
            retry_prompt[:200],
        )
        try:
            response = await self.llm_client.responses.create(
                model=OPENAI_MODEL,
                input=retry_prompt,
            )
            content = self._extract_response_text(response)
            if content:
                return content.strip()
        except Exception as exc:
            logger.error("LLM retry failed: %s", exc)
        return "답변을 생성하지 못했습니다. 다시 시도해 주세요."

    @staticmethod
    def _extract_response_text(response) -> str:
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text
        text_outputs: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "message" and hasattr(item, "content"):
                for content_item in item.content:
                    if getattr(content_item, "type", None) == "output_text":
                        text_outputs.append(content_item.text)
        return "\n".join(text_outputs) if text_outputs else ""

    async def _evaluate_memory(self, query: str):
        """쿼리에 대한 메모리 유용성을 LLM-as-Judge로 평가"""
        # 1. 메모리 상태 조회
        memory = await self.fetch_memory_context()

        if not memory.memory and not memory.entities:
            print("\n[평가 불가] 저장된 메모리가 없습니다.\n")
            return

        # 2. LLM 평가 프롬프트
        eval_prompt = f"""당신은 AI 메모리 시스템 평가자입니다.
아래 쿼리를 처리하는 데 저장된 메모리가 유용한지 평가해주세요.

## 사용자 쿼리
{query}

## 저장된 장기 기억
{memory.memory or "(없음)"}

## 저장된 엔티티
{json.dumps(memory.entities, ensure_ascii=False) if memory.entities else "(없음)"}

## 평가 기준 (각 0-10점)
1. relevance (관련성): 쿼리와 관련된 정보가 메모리에 있는가? (높을수록 좋음)
2. completeness (완전성): 쿼리 응답에 필요한 맥락이 충분한가? (높을수록 좋음)
3. accuracy (정확성): 메모리 정보가 정확한가? (높을수록 좋음)
4. noise (노이즈): 무관한 정보가 방해되는가? (낮을수록 좋음)

## 응답 형식 (JSON만)
{{
    "overall_score": 0-100,
    "scores": {{
        "relevance": {{"score": 0-10, "reason": "..."}},
        "completeness": {{"score": 0-10, "reason": "..."}},
        "accuracy": {{"score": 0-10, "reason": "..."}},
        "noise": {{"score": 0-10, "reason": "..."}}
    }},
    "helpful_info": ["쿼리 처리에 도움되는 정보"],
    "missing_info": ["있었으면 좋았을 정보"],
    "summary": "한 줄 평가"
}}"""

        try:
            response = await self.llm_client.responses.create(
                model=OPENAI_MODEL,
                input=eval_prompt,
            )
            result_text = self._extract_response_text(response)

            # JSON 파싱
            try:
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]
                result = json.loads(result_text.strip())

                # 결과 출력
                print("\n" + "=" * 50)
                print("[메모리 유용성 평가]")
                print("=" * 50)
                print(f"쿼리: {query}")
                print(f"전체 점수: {result.get('overall_score', 'N/A')}/100")
                print(f"요약: {result.get('summary', 'N/A')}")

                if "scores" in result:
                    print("\n[항목별 점수]")
                    for key, data in result["scores"].items():
                        score = data.get("score", "N/A")
                        reason = data.get("reason", "")
                        direction = "(높을수록 좋음)" if key != "noise" else "(낮을수록 좋음)"
                        print(f"  {key}: {score}/10 {direction}")
                        if reason:
                            print(f"    → {reason[:60]}...")

                if result.get("helpful_info"):
                    print("\n[도움되는 정보]")
                    for info in result["helpful_info"][:3]:
                        print(f"  + {info[:60]}...")

                if result.get("missing_info"):
                    print("\n[누락된 정보]")
                    for info in result["missing_info"][:3]:
                        print(f"  - {info[:60]}...")

                print("=" * 50 + "\n")

            except json.JSONDecodeError:
                print(f"\n[평가 결과 (원문)]\n{result_text[:500]}...\n")

        except Exception as exc:
            print(f"\n[평가 실패] LLM 오류: {exc}\n")

    async def handle_command(self, cmd: str) -> bool:
        """명령어 처리. True면 계속, False면 종료"""
        if cmd == "/quit":
            return False

        elif cmd == "/clear":
            payload = {"session": self.session}
            try:
                response = await self.http_client.post("/rag/debug/clear", json=payload)
                response.raise_for_status()
                self.turn_count = 0
                print("\n[세션 초기화됨]\n")
            except httpx.HTTPError as exc:
                logger.error("세션 초기화 실패: %s", exc)
                print("\n[세션 초기화 실패]\n")

        elif cmd == "/memory":
            ctx = await self.fetch_memory_context()
            print("\n" + "=" * 50)
            print("[메모리 상태]")
            print("=" * 50)
            print(f"Short-term ({len(ctx.short_term)}턴):")
            for t in ctx.short_term:
                print(f"  U: {t.user[:50]}...")
                print(f"  A: {t.assistant[:50]}...")
            print(f"\nLong-term Memory:\n  {ctx.memory or '(없음)'}")
            print(f"\nEntities:\n  {ctx.entities or '(없음)'}")
            print("=" * 50 + "\n")

        elif cmd == "/history":
            payload = {"session": self.session}
            try:
                response = await self.http_client.post("/rag/debug/history", json=payload)
                response.raise_for_status()
                data = response.json()
                turns = data.get("turns", [])
                print("\n" + "=" * 50)
                print(f"[대화 히스토리] ({len(turns)}턴)")
                print("=" * 50)
                for t in turns:
                    print(f"[Turn {t.get('turn')}]")
                    print(f"  User: {t.get('user')}")
                    print(f"  Assistant: {str(t.get('assistant', ''))[:100]}...")
                    print()
                print("=" * 50 + "\n")
            except httpx.HTTPError as exc:
                logger.error("대화 히스토리 조회 실패: %s", exc)
                print("\n[대화 히스토리 조회 실패]\n")

        elif cmd.startswith("/context"):
            # /context 뒤에 질문이 있으면 그걸로 검색
            query = cmd[8:].strip() or "테스트 질문"
            ctx = await self.fetch_ranked_results(query)
            print("\n" + "=" * 50)
            print("[RAG 검색 결과]")
            print("=" * 50)
            print(json.dumps(ctx, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")

        elif cmd == "/user":
            print_user_banner(self.user, self.session.split(":")[1])

        elif cmd.startswith("/switch"):
            # 화면 전환
            parts = cmd.split()
            if len(parts) < 2:
                print("\n사용법: /switch [cost|govern|optimize]")
                print("  cost     - 비용 개요 화면")
                print("  govern   - 거버넌스 KPI 화면")
                print("  optimize - 커밋먼트 최적화 화면\n")
                return True

            screen = parts[1].lower()
            if screen == "cost":
                self.dom_context_raw = get_cost_overview_dom_context()
                print("\n[화면 전환] → 비용 개요 (Cost Overview)\n")
            elif screen == "govern":
                self.dom_context_raw = get_govern_kpi_dom_context()
                print("\n[화면 전환] → 거버넌스 KPI (Governance KPI)\n")
            elif screen == "optimize":
                self.dom_context_raw = get_optimize_my_commitments_dom_context()
                print("\n[화면 전환] → 커밋먼트 최적화 (Optimize Commitments)\n")
            else:
                print(f"\n알 수 없는 화면: {screen}")
                print("사용 가능: cost, govern, optimize\n")

        elif cmd.startswith("/filter"):
            # 필터 설정/확인
            parts = cmd.split()
            if len(parts) == 1:
                # 현재 필터 상태 및 옵션 출력
                print("\n" + "=" * 50)
                print("[필터 설정]")
                print("=" * 50)
                print(f"  screen:    {self.filter_screen or '(랜덤)'}")
                print(f"  period:    {self.filter_period or '(랜덤)'}")
                print(f"  trend:     {self.filter_trend or '(랜덤)'}")
                print(f"  providers: {self.filter_providers or '(랜덤)'}")
                print("\n사용 가능한 옵션:")
                print(f"  screen:    {', '.join(SCREEN_OPTIONS)}")
                print(f"  period:    {', '.join(PERIOD_OPTIONS)}")
                print(f"  trend:     {', '.join(TREND_OPTIONS)}")
                print(f"  providers: {', '.join(PROVIDER_OPTIONS)}")
                print("\n사용법:")
                print("  /filter screen cost_overview")
                print("  /filter period last_30_days")
                print("  /filter trend increasing")
                print("  /filter providers AWS,GCP")
                print("  /filter reset")
                print("=" * 50 + "\n")
            elif len(parts) == 2 and parts[1] == "reset":
                self.filter_screen = None
                self.filter_period = None
                self.filter_trend = None
                self.filter_providers = None
                print("\n[필터 초기화됨] 모든 필터가 랜덤으로 설정됨\n")
            elif len(parts) >= 3:
                key = parts[1].lower()
                value = parts[2]
                if key == "screen":
                    if value in SCREEN_OPTIONS:
                        self.filter_screen = value
                        print(f"\n[필터 설정] screen = {value}\n")
                    else:
                        print(f"\n잘못된 값: {value}")
                        print(f"사용 가능: {', '.join(SCREEN_OPTIONS)}\n")
                elif key == "period":
                    if value in PERIOD_OPTIONS:
                        self.filter_period = value
                        print(f"\n[필터 설정] period = {value}\n")
                    else:
                        print(f"\n잘못된 값: {value}")
                        print(f"사용 가능: {', '.join(PERIOD_OPTIONS)}\n")
                elif key == "trend":
                    if value in TREND_OPTIONS:
                        self.filter_trend = value
                        print(f"\n[필터 설정] trend = {value}\n")
                    else:
                        print(f"\n잘못된 값: {value}")
                        print(f"사용 가능: {', '.join(TREND_OPTIONS)}\n")
                elif key == "providers":
                    provider_list = [p.strip() for p in value.split(",")]
                    valid = all(p in PROVIDER_OPTIONS for p in provider_list)
                    if valid:
                        self.filter_providers = provider_list
                        print(f"\n[필터 설정] providers = {provider_list}\n")
                    else:
                        print(f"\n잘못된 값: {value}")
                        print(f"사용 가능: {', '.join(PROVIDER_OPTIONS)}\n")
                else:
                    print(f"\n알 수 없는 필터 키: {key}")
                    print("사용 가능: screen, period, trend, providers\n")
            else:
                print("\n사용법: /filter [key] [value] 또는 /filter reset\n")

        elif cmd == "/random":
            # 현재 필터로 랜덤 데이터 생성
            self.dom_context_raw = generate_random_dom_context(
                screen_type=self.filter_screen,
                period=self.filter_period,
                trend=self.filter_trend,
                providers=self.filter_providers,
            )
            data = json.loads(self.dom_context_raw)
            generated = data.get("generated", {})
            print("\n" + "=" * 50)
            print("[랜덤 데이터 생성됨]")
            print("=" * 50)
            print(f"  screen:    {generated.get('screen_type', 'unknown')}")
            print(f"  period:    {generated.get('period', 'unknown')}")
            print(f"  trend:     {generated.get('trend', 'unknown')}")
            print(f"  providers: {generated.get('providers', [])}")
            print("=" * 50 + "\n")

        elif cmd.startswith("/eval"):
            # 쿼리에 대한 메모리 유용성 평가 (LLM-as-Judge)
            query = cmd[5:].strip()
            if not query:
                print("\n사용법: /eval [평가할 쿼리]")
                print("예시: /eval 아까 말한 예산 초과 상황 다시 설명해줘\n")
                return True
            print("\n[메모리 유용성 평가 중...]")
            await self._evaluate_memory(query)

        else:
            print(f"알 수 없는 명령어: {cmd}")
            print("사용 가능: /clear, /memory, /history, /context, /user, /switch, /filter, /random, /eval, /quit")

        return True

    async def chat(self, user_input: str):
        """대화 처리"""
        # 1. pydantic-ai Agent 실행 (검색 + 응답 생성)
        print("\n[RAG 서버 호출 중...]")
        logger.debug("RAG retrieve start: session=%s", self.session)
        rag_payload = await self.fetch_ranked_results(user_input)
        print(
            f"  → confidence: {rag_payload.get('confidence', 0.0):.2f}, "
            f"sufficient: {rag_payload.get('is_sufficient')}"
        )
        print(f"  → results: {len(rag_payload.get('ranked_results', []))}개")

        ranked_results = rag_payload.get("ranked_results", [])
        print("[LLM 답변 생성 중...]")
        answer = await self.generate_answer(user_input, ranked_results)

        # 2. 서버에 대화 저장 요청
        save_payload = {
            "session": self.session,
            "user_id": self.user.user_id,
            "query": user_input,
            "answer": answer,
        }
        try:
            response = await self.http_client.post("/chat/save", json=save_payload)
            response.raise_for_status()
            data = response.json()
            self.turn_count = data.get("turn", self.turn_count)
            logger.debug("Turn saved by server: session=%s turn=%s", self.session, self.turn_count)
        except httpx.HTTPError as exc:
            logger.error("대화 저장 실패: %s", exc)

        # 3. 응답 출력
        print("\n" + "-" * 50)
        print(f"Assistant: {answer}")
        print("-" * 50 + "\n")

        # 4. 메모리 유용성 자동 평가
        await self._evaluate_memory(user_input)

    async def run(self):
        """메인 루프"""
        await self.initialize()

        # 유저 배너 출력
        session_id = self.session.split(":")[1]
        print_user_banner(self.user, session_id)
        print(f"Selected page: {self._get_dom_context_page()}")

        print("=" * 50)
        print("OpsNow Copilot - Chat CLI (pydantic-ai)")
        print("=" * 50)
        print("명령어:")
        print("  /clear    - 세션 초기화")
        print("  /memory   - 메모리 상태 확인")
        print("  /history  - 대화 히스토리")
        print("  /context  - RAG 검색 결과")
        print("  /user     - 유저 정보")
        print("  /switch   - 화면 전환")
        print("  /filter   - 필터 설정/확인")
        print("  /random   - 랜덤 데이터 생성")
        print("  /eval     - 메모리 유용성 평가 (/eval 쿼리)")
        print("  /quit     - 종료")
        print("=" * 50 + "\n")

        try:
            while True:
                try:
                    prompt = f"{self.user.color}[{self.user.name}]{RESET_COLOR} You: "
                    user_input = self._sanitize_command_input(input(prompt)).strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if not await self.handle_command(user_input):
                        break
                else:
                    await self.chat(user_input)

        finally:
            await self.close()
            print("\n종료됨.")


async def main():
    # TODO: 합칠 때 제거 - 랜덤 유저 선택
    user = get_random_user()
    session_id = generate_session_id()

    cli = ChatCLI(user, session_id)
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
