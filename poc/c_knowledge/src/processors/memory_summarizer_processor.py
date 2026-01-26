"""Recursive Summarization 모듈"""

import logging
import json

from openai import AsyncOpenAI

from src.config import OPENAI_MODEL
from src.constants.memory import (
    ENTITIES_MAX_COUNT,
    MEMORY_MAX_SENTENCES,
    MEMORY_SUMMARIZE_RETRY_COUNT,
)
from src.models import SummarizerResult, Turn
from src.utils.text import sanitize_text
from src.utils.secrets import get_open_ai_key
from src.utils.token_logger import (
    TokenTimer,
    extract_usage_from_response,
    log_token_usage,
)

client = AsyncOpenAI(api_key=get_open_ai_key())
logger = logging.getLogger(__name__)


class MemorySummarizer:
    """Recursive Summarization 구현: Mi = LLM(Mi-1, Si)"""

    async def recursive_summarize(
        self,
        prev_memory: str,
        new_turns: list[Turn],
        prev_entities: dict[str, str],
    ) -> SummarizerResult:
        """
        이전 메모리 + 새 대화 → 새 메모리 + 엔티티

        Args:
            prev_memory: 이전 Long-term Memory 내용
            new_turns: 새로 추가된 대화 턴들
            prev_entities: 기존 엔티티

        Returns:
            SummarizerResult (memory, entities)
        """
        # 텍스트 정리
        turns_text = "\n".join(
            [
                f"User: {sanitize_text(t.user)}\nAssistant: {sanitize_text(t.assistant)}"
                for t in new_turns
            ]
        )
        clean_prev_memory = sanitize_text(prev_memory) if prev_memory else "(없음)"
        entities_json = json.dumps(prev_entities, ensure_ascii=False) if prev_entities else "(없음)"
        clean_entities = sanitize_text(entities_json)

        prompt = f"""당신은 대화 메모리 관리자입니다.

## 이전 메모리
{clean_prev_memory}

## 새 대화
{turns_text}

## 기존 엔티티
{clean_entities}

## 작업
위 정보를 바탕으로 메모리를 업데이트하세요.

## Long-term Memory 규칙
1. 메모리는 {MEMORY_MAX_SENTENCES}문장 이내로 작성
2. 사용자의 의도, 관심사, 진행 상황 중심으로 작성
3. 최근 대화 우선: 새 대화 내용이 더 중요
4. 주제 전환 감지: 주제가 바뀌면 이전 주제는 한 줄로 압축
5. 오래된 정보 정리: 더 이상 관련 없는 내용은 과감히 삭제

## Entities 규칙
1. 같은 키는 덮어쓰기: 값이 바뀌면 최신 값으로
2. 최대 {ENTITIES_MAX_COUNT}개 제한 (FIFO): 초과 시 오래된 것부터 삭제
3. 주제 바뀌어도 유지: 자연스럽게 밀려날 때까지 보존

## JSON 응답
{{
  "memory": "업데이트된 메모리 내용",
  "entities": {{
    "key": "value",
    ...
  }}
}}

entities에서 추출할 정보:
- provider: 클라우드 제공자
- service: 서비스명
- period: 기간
- amount/cost: 금액
- budget: 예산
- threshold: 임계값
- 기타 중요 설정값

※ 주제가 바뀌어도 Entities 유지 ({ENTITIES_MAX_COUNT}개 초과 시 FIFO로 오래된 것부터 삭제)"""

        last_exc: Exception | None = None
        for attempt in range(MEMORY_SUMMARIZE_RETRY_COUNT):
            try:
                with TokenTimer() as timer:
                    response = await client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                    )

                # 토큰 사용량 로깅
                usage = extract_usage_from_response(response)
                log_token_usage(
                    model=OPENAI_MODEL,
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                    total_tokens=usage["total_tokens"],
                    duration_ms=timer.duration_ms,
                    caller="MemorySummarizer.recursive_summarize",
                )

                result = json.loads(response.choices[0].message.content)

                # entities가 문자열로 반환되면 파싱
                entities = result.get("entities", {})
                if isinstance(entities, str):
                    try:
                        entities = json.loads(entities)
                    except json.JSONDecodeError:
                        entities = prev_entities

                return SummarizerResult(
                    memory=result.get("memory", "") or prev_memory,
                    entities=entities or prev_entities,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Memory summarize attempt %s failed: %s", attempt + 1, exc
                )

        logger.warning("Memory summarize failed, fallback used: %s", last_exc)
        return _fallback_summarize(prev_memory, new_turns, prev_entities)


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


def _fallback_summarize(
    prev_memory: str,
    new_turns: list[Turn],
    prev_entities: dict[str, str],
) -> SummarizerResult:
    """Fallback summary/entities when LLM summarization fails."""
    recent_user = [t.user for t in new_turns][-3:]
    recent_assistant = [t.assistant for t in new_turns][-3:]
    summary_parts = []
    if prev_memory:
        summary_parts.append(prev_memory.strip())
    if recent_user:
        summary_parts.append("최근 질문: " + " / ".join(recent_user))
    if recent_assistant:
        summary_parts.append("최근 답변: " + " / ".join(recent_assistant))
    summary = ". ".join(p for p in summary_parts if p)

    return SummarizerResult(
        memory=summary[:2000],
        entities=prev_entities,
    )
