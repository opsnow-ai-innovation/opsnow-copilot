"""
DomContext Parser

WebSocket에서 받은 domContext JSON을 파싱하여 표준 포맷으로 변환.
구조가 불명확한 상태에서 유연하게 처리.
"""

import json

from src.models import ParsedDomContext


class DomContextParser:
    """domContext 파싱 (나중에 개선 가능)"""

    def parse(self, dom_context_raw: str) -> ParsedDomContext:
        """
        domContext JSON string을 파싱하여 표준 포맷으로 변환.

        현재는 단순하게 처리하고, 나중에 화면 타입별로 고도화 가능.

        Args:
            dom_context_raw: WebSocket에서 받은 JSON string

        Returns:
            ParsedDomContext: Agent가 사용할 표준 포맷
        """
        # 빈 문자열 처리
        if not dom_context_raw or not dom_context_raw.strip():
            return ParsedDomContext(
                raw="",
                summary="화면 정보 없음",
                structured={},
                has_data=False,
            )

        # JSON 파싱 시도
        try:
            data = json.loads(dom_context_raw)
        except json.JSONDecodeError:
            # JSON 아니면 그냥 텍스트로 처리
            return ParsedDomContext(
                raw=dom_context_raw,
                summary=dom_context_raw[:500],  # 텍스트 일부만
                structured={},
                has_data=bool(dom_context_raw),
            )

        # 빈 객체 처리
        if not data:
            return ParsedDomContext(
                raw=dom_context_raw,
                summary="화면 정보 없음",
                structured={},
                has_data=False,
            )

        # 단순 요약 생성
        summary = self._create_simple_summary(data)

        return ParsedDomContext(
            raw=dom_context_raw,
            summary=summary,
            structured=data,
            screen_type=self._detect_screen_type(data),
            has_data=True,
        )

    def _create_simple_summary(self, data: dict) -> str:
        """
        domContext에서 단순 요약 생성.

        나중에 화면 타입별로 분기 가능.
        지금은 일반적인 필드들만 추출.

        Args:
            data: 파싱된 JSON 객체

        Returns:
            사람이 읽을 수 있는 요약 텍스트
        """
        parts = []

        # summary 필드 (Dashboard 등에서 사용)
        if "summary" in data:
            summary = data["summary"]
            if isinstance(summary, dict):
                summary_parts = []
                for key, value in summary.items():
                    summary_parts.append(f"{key}: {value}")
                parts.append(f"요약 정보:\n- " + "\n- ".join(summary_parts))
            else:
                parts.append(f"요약: {summary}")

        # table 필드 (테이블 화면에서 사용)
        if "table" in data:
            table = data["table"]
            if isinstance(table, dict):
                rows_count = len(table.get("rows", []))
                headers = table.get("headers", [])
                parts.append(
                    f"테이블: {rows_count}개 행"
                    + (f" (컬럼: {', '.join(headers)})" if headers else "")
                )

        # filters 필드 (필터 정보)
        if "filters" in data:
            filters = data["filters"]
            if isinstance(filters, dict):
                filter_parts = []
                for key, value in filters.items():
                    filter_parts.append(f"{key}={value}")
                parts.append(f"필터: {', '.join(filter_parts)}")

        # current_page 또는 page 필드
        if "current_page" in data:
            parts.append(f"현재 페이지: {data['current_page']}")
        elif "page" in data:
            parts.append(f"페이지: {data['page']}")

        # screen_type 명시적으로 있으면
        if "screen_type" in data:
            parts.append(f"화면 유형: {data['screen_type']}")

        # 아무것도 없으면 JSON 일부 보여주기
        if not parts:
            # 최대 5개 키만 보여주기
            keys = list(data.keys())[:5]
            parts.append(f"화면 데이터 (키: {', '.join(keys)})")

        return "\n".join(parts)

    def _detect_screen_type(self, data: dict) -> str | None:
        """
        domContext에서 화면 타입 추론 (best effort).

        나중에 클라이언트에서 screen_type을 명시적으로 보내주면
        이 로직은 필요 없어짐.

        Args:
            data: 파싱된 JSON 객체

        Returns:
            추론된 화면 타입 (또는 None)
        """
        # 명시적으로 screen_type이 있으면 그대로 사용
        if "screen_type" in data:
            return data["screen_type"]

        # 휴리스틱으로 추론
        if "summary" in data and "charts" in data:
            return "dashboard"

        if "table" in data:
            return "table"

        if "resource" in data:
            return "detail"

        # 추론 불가
        return None