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
import httpx

import redis.asyncio as redis
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import REDIS_URL, OPENAI_MODEL
from src.constants.memory import SHORT_TERM_SIZE
from src.models import Turn
from src.processors.memory_store_processor import RedisMemoryStore
from src.processors.memory_summarizer_processor import MemorySummarizer
from src.processors.context_builder_processor import build_llm_context
from src.rag_assistant.dom_parser import DomContextParser
from src.mock.users import (
    MockUser,
    RESET_COLOR,
    get_random_user,
    generate_session_id,
    print_user_banner,
)
from src.mock.dom_context import get_cost_overview_dom_context
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
        /quit - 종료
    """

    def __init__(self, user: MockUser, session_id: str):
        self.user = user
        self.session = f"{user.user_id}:{session_id}"
        self.turn_count = 0
        self.server_url = os.getenv("RAG_SERVER_URL", "http://localhost:8000")
        self.redis_client = None
        self.memory_store = None
        self.summarizer = None
        self.http_client = None
        self.llm_client = None
        self.dom_parser = DomContextParser()
        self.dom_context_raw = get_cost_overview_dom_context()

    async def initialize(self):
        """초기화"""
        print("Redis 연결 중...")
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await self.redis_client.ping()
        print("Redis 연결 완료")

        self.memory_store = RedisMemoryStore(self.redis_client)
        self.summarizer = MemorySummarizer()
        self.http_client = httpx.AsyncClient(base_url=self.server_url, timeout=120.0)
        self.llm_client = AsyncOpenAI(api_key=get_open_ai_key())

        # 기존 턴 수 확인
        turns = await self.memory_store.get_all_turns(self.session)
        self.turn_count = len(turns)

    async def close(self):
        """종료"""
        if self.http_client:
            await self.http_client.aclose()
        if self.redis_client:
            await self.redis_client.aclose()

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

    async def generate_answer(self, query: str, ranked_results: list[dict]) -> str:
        """정렬된 RAG 결과로 LLM 답변 생성"""
        memory = await self.memory_store.get_context(self.session)
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

    async def handle_command(self, cmd: str) -> bool:
        """명령어 처리. True면 계속, False면 종료"""
        if cmd == "/quit":
            return False

        elif cmd == "/clear":
            await self.memory_store.clear(self.session)
            self.turn_count = 0
            print("\n[세션 초기화됨]\n")

        elif cmd == "/memory":
            ctx = await self.memory_store.get_context(self.session)
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
            turns = await self.memory_store.get_all_turns(self.session)
            print("\n" + "=" * 50)
            print(f"[대화 히스토리] ({len(turns)}턴)")
            print("=" * 50)
            for t in turns:
                print(f"[Turn {t.turn}]")
                print(f"  User: {t.user}")
                print(f"  Assistant: {t.assistant[:100]}...")
                print()
            print("=" * 50 + "\n")

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

        else:
            print(f"알 수 없는 명령어: {cmd}")
            print("사용 가능: /clear, /memory, /history, /context, /user, /quit")

        return True

    async def chat(self, user_input: str):
        """대화 처리"""
        self.turn_count += 1

        # 1. pydantic-ai Agent 실행 (검색 + 응답 생성)
        print("\n[RAG 서버 호출 중...]")
        logger.debug("RAG retrieve start: session=%s turn=%s", self.session, self.turn_count)
        rag_payload = await self.fetch_ranked_results(user_input)
        print(
            f"  → confidence: {rag_payload.get('confidence', 0.0):.2f}, "
            f"sufficient: {rag_payload.get('is_sufficient')}"
        )
        print(f"  → results: {len(rag_payload.get('ranked_results', []))}개")

        ranked_results = rag_payload.get("ranked_results", [])
        print("[LLM 답변 생성 중...]")
        answer = await self.generate_answer(user_input, ranked_results)

        # 2. 대화 턴 저장
        turn = Turn(
            turn=self.turn_count,
            user=user_input,
            assistant=answer,
        )
        await self.memory_store.add_turn(self.session, turn)
        logger.debug("Turn saved: session=%s turn=%s", self.session, self.turn_count)

        # 3. 메모리 요약 (SHORT_TERM_SIZE마다)
        if self.turn_count % SHORT_TERM_SIZE == 0:
            print("[메모리 요약 중...]")
            ctx = await self.memory_store.get_context(self.session)
            logger.debug(
                "Memory summarize trigger: short_term=%s long_term_len=%s entities=%s",
                len(ctx.short_term),
                len(ctx.memory or ""),
                list((ctx.entities or {}).keys()),
            )
            result = await self.summarizer.recursive_summarize(
                prev_memory=ctx.memory,
                new_turns=ctx.short_term,
                prev_entities=ctx.entities,
            )
            await self.memory_store.update_memory(
                self.session, result.memory, result.entities
            )
            logger.debug("Memory updated: long_term_len=%s", len(result.memory or ""))

        # 4. 응답 출력
        print("\n" + "-" * 50)
        print(f"Assistant: {answer}")
        print("-" * 50 + "\n")

    async def run(self):
        """메인 루프"""
        await self.initialize()

        # 유저 배너 출력
        session_id = self.session.split(":")[1]
        print_user_banner(self.user, session_id)

        print("=" * 50)
        print("OpsNow Copilot - Chat CLI (pydantic-ai)")
        print("=" * 50)
        print("명령어: /clear, /memory, /history, /context [질문], /user, /quit")
        print("=" * 50 + "\n")

        try:
            while True:
                try:
                    prompt = f"{self.user.color}[{self.user.name}]{RESET_COLOR} You: "
                    user_input = input(prompt).strip()
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
