"""WebSocket 메시지 관련 Pydantic 모델"""

from pydantic import BaseModel


class QueryMessage(BaseModel):
    """WebSocket query 메시지"""

    type: str = "query"
    query: str
    domContext: str  # JSON string
    page: dict