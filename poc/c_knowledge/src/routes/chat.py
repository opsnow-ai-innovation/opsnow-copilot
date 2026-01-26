"""
Chat API

# TODO: 이 파일은 삭제 예정
# RAG API 응답을 받아서 LLM을 한 번 더 타서 최종 응답을 생성하는 API
# 실제 운영에서는 프론트엔드에서 직접 LLM 호출하거나 별도 서비스로 분리될 예정
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.routes.rag import ContextResponse, get_pipeline, get_memory_store
from src.processors.rag_agent_processor import RAGPipeline
from src.processors.context_builder_processor import build_llm_context
from src.processors.memory_store_processor import RedisMemoryStore
from src.models import Turn

router = APIRouter(prefix="/chat", tags=["Chat"])


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    """Chat 요청"""

    query: str = Field(..., description="사용자 질의")
    session: str = Field(..., description="세션 ID")
    user_id: str = Field(default="", description="유저 ID")


class ChatResponse(BaseModel):
    """Chat 응답"""

    answer: str = Field(..., description="LLM 생성 응답")
    context: ContextResponse = Field(..., description="RAG Context")
    confidence: float = Field(default=0.0, description="응답 신뢰도")


class SaveChatRequest(BaseModel):
    """Chat 저장 요청"""

    session: str = Field(..., description="세션 ID")
    user_id: str = Field(default="", description="유저 ID")
    query: str = Field(..., description="사용자 질의")
    answer: str = Field(..., description="응답 내용")
    turn: int | None = Field(default=None, description="턴 번호(없으면 자동 증가)")


class SaveChatResponse(BaseModel):
    """Chat 저장 응답"""

    saved: bool = Field(default=True)
    turn: int = Field(..., description="저장된 턴 번호")


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> ChatResponse:
    """
    # TODO: 삭제 예정

    Chat API - RAG Context + LLM 응답 생성

    1. RAG 파이프라인으로 Context 조회
    2. Context를 LLM에 전달하여 최종 응답 생성
    3. 응답 + Context 반환
    """
    # 1. RAG 파이프라인 실행
    rag_result = await pipeline.retrieve(
        query=request.query,
        session=request.session,
        user_id=request.user_id,
    )

    # 2. LLM Context 구성
    faq_results = [r.content for r in rag_result.ranked_results]
    llm_ctx = build_llm_context(rag_result.memory, faq_results=faq_results)

    # 3. Context 응답 구성
    from src.processors.context_builder_processor import build_memory_response

    context_response = ContextResponse(
        memory=build_memory_response(rag_result.memory),
        faq=[f"Q: {r.content}" for r in rag_result.ranked_results if r.metadata.doc_type == "faq"],
        menu=[],
    )

    # TODO: 실제 LLM 호출하여 응답 생성
    # 현재는 rag_result.answer 사용 (Agent가 생성한 응답)
    return ChatResponse(
        answer=rag_result.answer,
        context=context_response,
        confidence=rag_result.confidence,
    )


@router.post("/save", response_model=SaveChatResponse)
async def save_chat(
    request: SaveChatRequest,
    store: RedisMemoryStore = Depends(get_memory_store),
) -> SaveChatResponse:
    """
    Chat 저장 API

    - query/answer를 Turn으로 저장
    - 단기기억이 5턴을 초과하면 Long-term 요약 트리거
    """
    if request.turn is None:
        # 자동 증가 counter 사용 (요약 후 턴 삭제되어도 번호 유지)
        # counter를 먼저 증가시켜서 turn_id를 가져옴
        turn_key = f"chat:{request.session}:turn"
        turn_id = await store._redis.incr(turn_key)
        await store._redis.expire(turn_key, 86400)  # TTL 24시간
    else:
        turn_id = request.turn

    turn = Turn(
        turn=turn_id,
        user=request.query,
        assistant=request.answer,
    )
    await store.add_turn(request.session, turn)

    return SaveChatResponse(saved=True, turn=turn_id)
