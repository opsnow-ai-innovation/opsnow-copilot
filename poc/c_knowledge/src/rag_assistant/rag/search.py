"""FAISS 기반 검색 로직"""

import pickle
from pathlib import Path

import faiss
import numpy as np
from openai import AsyncOpenAI

from src.models import ChunkMetadata, SearchResult
from src.config import EMBEDDED_VECTOR_PATH, EMBEDDING_MODEL
from src.constants import FAQ_SEARCH_K, GUIDE_SEARCH_K
from src.utils.secrets import get_open_ai_key

client = AsyncOpenAI(api_key=get_open_ai_key())


def _sanitize_text(text: str) -> str:
    """UTF-8 인코딩이 불가능한 문자 제거"""
    try:
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        return text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')


class FAISSSearch:
    """FAISS 검색 클래스"""

    def __init__(self, vector_path: str | None = None):
        self.vector_path = Path(vector_path or EMBEDDED_VECTOR_PATH)
        self.faq_index: faiss.IndexFlatIP | None = None
        self.guide_index: faiss.IndexFlatIP | None = None
        self.faq_data: list[dict] = []
        self.guide_data: list[dict] = []
        self.doc_index: dict = {}

        self._load_indices()

    def _load_indices(self):
        """임베딩 인덱스 로드 (FAQ, Guide 분리)"""
        if not self.vector_path.exists():
            return

        with open(self.vector_path, "rb") as f:
            data = pickle.load(f)

        # FAQ 인덱스
        if "faq" in data:
            self.faq_index = faiss.deserialize_index(data["faq"]["faiss_index"])
            self.faq_data = data["faq"]["data"]

        # Guide 인덱스
        if "guide" in data:
            self.guide_index = faiss.deserialize_index(data["guide"]["faiss_index"])
            self.guide_data = data["guide"]["data"]
            self.doc_index = data["guide"].get("doc_index", {})

    async def search_faq(self, query: str, k: int = FAQ_SEARCH_K) -> list[SearchResult]:
        """FAQ 검색"""
        if self.faq_index is None or not self.faq_data:
            return []

        embedding = await self._embed_query(query)
        scores, indices = self.faq_index.search(embedding, k)

        return [
            SearchResult(
                content=_sanitize_text(self.faq_data[idx]["content"]),
                source=_sanitize_text(self.faq_data[idx]["source"]),
                score=float(scores[0][i]),
                metadata=ChunkMetadata(**self.faq_data[idx]["metadata"]),
            )
            for i, idx in enumerate(indices[0])
            if idx >= 0 and idx < len(self.faq_data)
        ]

    async def search_guide(
        self, query: str, k: int = GUIDE_SEARCH_K
    ) -> list[SearchResult]:
        """Guide 검색"""
        if self.guide_index is None or not self.guide_data:
            return []

        embedding = await self._embed_query(query)
        scores, indices = self.guide_index.search(embedding, k)

        return [
            SearchResult(
                content=_sanitize_text(self.guide_data[idx]["content"]),
                source=_sanitize_text(self.guide_data[idx]["source"]),
                score=float(scores[0][i]),
                metadata=ChunkMetadata(**self.guide_data[idx]["metadata"]),
            )
            for i, idx in enumerate(indices[0])
            if idx >= 0 and idx < len(self.guide_data)
        ]

    async def search_by_metadata(
        self,
        query: str,
        doc_type: str | None = None,
        guide_type: str | None = None,
        has_steps: bool | None = None,
        section_path: str | None = None,
        k: int = 10,
    ) -> list[SearchResult]:
        """메타데이터 필터로 검색"""
        # 대상 데이터 선택
        if doc_type == "faq":
            candidates = self.faq_data
            index = self.faq_index
        elif doc_type == "guide":
            candidates = self.guide_data
            index = self.guide_index
        else:
            # 전체 검색
            faq_results = await self.search_faq(query, k=k // 2)
            guide_results = await self.search_guide(query, k=k // 2)
            return faq_results + guide_results

        if index is None or not candidates:
            return []

        # 메타데이터 필터링
        filtered_indices = []
        for i, doc in enumerate(candidates):
            meta = doc["metadata"]

            if guide_type and meta.get("guide_type") != guide_type:
                continue
            if has_steps is not None and meta.get("has_steps") != has_steps:
                continue
            if section_path and section_path not in meta.get("section_path", ""):
                continue

            filtered_indices.append(i)

        if not filtered_indices:
            return []

        # 필터링된 문서들의 벡터로 서브 인덱스 생성
        filtered_vectors = np.array(
            [candidates[i]["vector"] for i in filtered_indices],
            dtype=np.float32,
        )
        faiss.normalize_L2(filtered_vectors)

        sub_index = faiss.IndexFlatIP(filtered_vectors.shape[1])
        sub_index.add(filtered_vectors)

        # 검색
        embedding = await self._embed_query(query)
        actual_k = min(k, len(filtered_indices))
        scores, indices = sub_index.search(embedding, actual_k)

        return [
            SearchResult(
                content=_sanitize_text(candidates[filtered_indices[idx]]["content"]),
                source=_sanitize_text(candidates[filtered_indices[idx]]["source"]),
                score=float(scores[0][i]),
                metadata=ChunkMetadata(**candidates[filtered_indices[idx]]["metadata"]),
            )
            for i, idx in enumerate(indices[0])
            if idx >= 0
        ]

    async def get_section(
        self, doc_id: str, section_path: str
    ) -> list[SearchResult]:
        """특정 문서의 섹션 전체 가져오기"""
        chunk_indices = (
            self.doc_index.get(doc_id, {}).get("sections", {}).get(section_path, [])
        )

        if not chunk_indices:
            # section_path가 정확히 일치하지 않으면 부분 매칭 시도
            doc_sections = self.doc_index.get(doc_id, {}).get("sections", {})
            for path, indices in doc_sections.items():
                if section_path in path or path in section_path:
                    chunk_indices = indices
                    break

        return [
            SearchResult(
                content=_sanitize_text(self.guide_data[idx]["content"]),
                source=_sanitize_text(self.guide_data[idx]["source"]),
                score=1.0,
                metadata=ChunkMetadata(**self.guide_data[idx]["metadata"]),
            )
            for idx in chunk_indices
            if idx < len(self.guide_data)
        ]

    async def _embed_query(self, query: str) -> np.ndarray:
        """쿼리 임베딩"""
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=query,
        )

        embedding = np.array([response.data[0].embedding], dtype=np.float32)
        faiss.normalize_L2(embedding)

        return embedding