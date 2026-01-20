"""Guide batch output metadata 검증 테스트"""

import os
import pickle
import random

import numpy as np
import pytest

from src.constants import EMBEDDED_VECTOR_PATH

REQUIRED_METADATA_KEYS = {
    "doc_id",
    "doc_type",
    "guide_type",
    "section_path",
    "has_steps",
}


def _validate_entry(entry: dict, expected_doc_type: str) -> None:
    assert isinstance(entry, dict)
    assert isinstance(entry.get("content"), str)
    assert isinstance(entry.get("source"), str)
    assert "vector" in entry

    metadata = entry.get("metadata")
    assert isinstance(metadata, dict)
    assert REQUIRED_METADATA_KEYS.issubset(metadata.keys())
    assert isinstance(metadata["doc_id"], str)
    assert len(metadata["doc_id"]) == 16
    assert metadata["doc_type"] == expected_doc_type
    assert isinstance(metadata["guide_type"], str)
    assert isinstance(metadata["section_path"], str)
    assert isinstance(metadata["has_steps"], bool)


def test_embedded_vector_metadata_schema():
    """run_guide_batch.sh 결과물의 metadata 스키마 검증"""
    if not os.path.exists(EMBEDDED_VECTOR_PATH):
        pytest.skip(
            f"결과 파일이 없습니다. scripts/run_guide_batch.sh 실행 필요: {EMBEDDED_VECTOR_PATH}"
        )

    with open(EMBEDDED_VECTOR_PATH, "rb") as f:
        result = pickle.load(f)

    assert isinstance(result, dict)
    assert result, "임베딩 결과가 비어있습니다."

    for doc_type in ("guide", "faq"):
        payload = result.get(doc_type)
        if payload is None:
            continue

        assert isinstance(payload, dict)
        if "faiss_index" in payload:
            assert isinstance(payload["faiss_index"], (bytes, bytearray, np.ndarray))

        entries = payload.get("data")
        assert isinstance(entries, list)
        assert entries, f"{doc_type} 데이터가 비어있습니다."

        for entry in entries:
            _validate_entry(entry, doc_type)


def test_show_random_metadata_values():
    """임의의 엔트리를 선택하여 metadata 내용을 확인합니다. (항상 통과)"""
    if not os.path.exists(EMBEDDED_VECTOR_PATH):
        pytest.skip(
            f"결과 파일이 없습니다. scripts/run_guide_batch.sh 실행 필요: {EMBEDDED_VECTOR_PATH}"
        )

    with open(EMBEDDED_VECTOR_PATH, "rb") as f:
        result = pickle.load(f)

    print()  # for better formatting in pytest output
    for doc_type in ("guide", "faq"):
        payload = result.get(doc_type)
        if not payload:
            continue

        entries = payload.get("data")
        if not entries:
            continue

        random_entry = random.choice(entries)
        metadata = random_entry.get("metadata", {})
        print(f"\n--- Random metadata for doc_type: {doc_type} ---")
        for key in REQUIRED_METADATA_KEYS:
            if key in metadata:
                print(f"  {key}: {metadata[key]}")
        print("--------------------------------------------------")

    # This test is for inspection, so it always passes.
    assert True
