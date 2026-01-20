"""DomContextParser 유닛 테스트"""

import json

import pytest

from src.rag_assistant.dom_parser import DomContextParser


@pytest.fixture
def parser():
    """DomContextParser 인스턴스"""
    return DomContextParser()


def test_parse_empty_string(parser):
    """빈 문자열 처리"""
    result = parser.parse("")

    assert result.has_data is False
    assert result.summary == "화면 정보 없음"
    assert result.structured == {}
    assert result.screen_type is None


def test_parse_empty_json(parser):
    """빈 JSON 객체 처리"""
    result = parser.parse("{}")

    assert result.has_data is False
    assert result.summary == "화면 정보 없음"
    assert result.structured == {}


def test_parse_invalid_json(parser):
    """깨진 JSON 처리"""
    result = parser.parse("{broken json")

    assert result.has_data is True
    assert "{broken json" in result.summary
    assert result.structured == {}


def test_parse_text_only(parser):
    """JSON 아닌 텍스트 처리"""
    text = "현재 화면: 비용 분석 대시보드"
    result = parser.parse(text)

    assert result.has_data is True
    assert text in result.summary
    assert result.structured == {}


def test_parse_dashboard(parser):
    """Dashboard 화면 파싱"""
    dom = {
        "summary": {"totalCost": "$45,678", "change": "+15%"},
        "charts": [{"type": "trend"}],
    }
    result = parser.parse(json.dumps(dom))

    assert result.has_data is True
    assert result.screen_type == "dashboard"
    assert "요약 정보" in result.summary
    assert "totalCost" in result.summary


def test_parse_table(parser):
    """테이블 화면 파싱"""
    dom = {
        "table": {
            "headers": ["Service", "Cost"],
            "rows": [["EC2", "$15,000"], ["Lambda", "$3,000"]],
        }
    }
    result = parser.parse(json.dumps(dom))

    assert result.has_data is True
    assert result.screen_type == "table"
    assert "테이블" in result.summary
    assert "2개 행" in result.summary


def test_parse_explicit_screen_type(parser):
    """명시적 screen_type 처리"""
    dom = {"screen_type": "custom", "data": "..."}
    result = parser.parse(json.dumps(dom))

    assert result.screen_type == "custom"


def test_parse_filters(parser):
    """필터 정보 파싱"""
    dom = {"filters": {"vendor": "aws", "period": "2024-11"}}
    result = parser.parse(json.dumps(dom))

    assert "필터" in result.summary
    assert "vendor=aws" in result.summary


def test_parse_complex_dashboard(parser):
    """복잡한 Dashboard 파싱"""
    dom = {
        "screen_type": "dashboard",
        "summary": {"totalCost": "$125,430", "change": "+8.5%"},
        "charts": [{"type": "cost_breakdown"}],
        "filters": {"vendor": "aws", "account": "prod"},
    }
    result = parser.parse(json.dumps(dom))

    assert result.has_data is True
    assert result.screen_type == "dashboard"
    assert "요약 정보" in result.summary
    assert "필터" in result.summary