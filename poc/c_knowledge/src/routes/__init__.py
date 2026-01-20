"""API 라우터"""

from src.routes.health import router as health_router
from src.routes.rag import router as rag_router
from src.routes.chat import router as chat_router  # TODO: 삭제 예정

__all__ = ["health_router", "rag_router", "chat_router"]