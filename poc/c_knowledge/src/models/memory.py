"""Memory 관련 Pydantic 모델"""

from datetime import datetime

from pydantic import BaseModel, Field


class Turn(BaseModel):
    """단일 대화 턴"""

    turn: int
    user: str
    assistant: str
    ts: datetime = Field(default_factory=datetime.now)


class MemoryState(BaseModel):
    """Long-term Memory 상태 (Redis 저장 구조)"""

    content: str = ""
    version: int = 0
    last_turns: str = ""  # "11-15" 형태
    ts: datetime = Field(default_factory=datetime.now)


class Entities(BaseModel):
    """구조화된 엔티티 (key-value, 최대 25개)"""

    data: dict[str, str] = Field(default_factory=dict)

    def update(self, new_entities: dict[str, str], max_count: int = 25):
        """엔티티 업데이트 (FIFO 방식)"""
        merged = {**self.data, **new_entities}

        # 초과 시 오래된 것부터 삭제
        if len(merged) > max_count:
            keys = list(merged.keys())
            for key in keys[: len(merged) - max_count]:
                del merged[key]

        self.data = merged


class MemoryContext(BaseModel):
    """컨텍스트 조회 결과 (LLM에 전달할 전체 메모리)"""

    short_term: list[Turn] = Field(default_factory=list)
    memory: str = ""  # Long-term Memory content
    entities: dict[str, str] = Field(default_factory=dict)


class SummarizerResult(BaseModel):
    """Recursive Summarization 결과"""

    memory: str
    entities: dict[str, str] = Field(default_factory=dict)


class IntegratedContext(BaseModel):
    """통합 컨텍스트 (Agent에 전달할 전체 정보)"""

    user_query: str
    dom_context: "ParsedDomContext"  # Forward reference
    page_info: "PageInfo"  # Forward reference
    memory: MemoryContext