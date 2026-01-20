"""파일 경로 관련 상수"""

import os

# 프로젝트 루트 경로
BASE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 데이터 경로
DATA_BASE_PATH = os.path.join(BASE_PATH, "src", "data")
FAQ_DATA_PATH = os.path.join(DATA_BASE_PATH, "origin", "io_faq")
MENU_DATA_PATH = os.path.join(DATA_BASE_PATH, "origin", "io_menu")

# 출력 경로
_EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDED_VECTOR_PATH = os.environ.get(
    "EMBEDDED_VECTOR_PATH",
    os.path.join(DATA_BASE_PATH, "output", _EMBEDDING_MODEL, "embedded_vector.pkl"),
)
