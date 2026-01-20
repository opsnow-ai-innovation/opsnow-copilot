"""Text utils tests."""

from src.utils.text import sanitize_text


def test_sanitize_text_removes_surrogates():
    raw = "ok\udce3"
    cleaned = sanitize_text(raw)
    assert cleaned == "ok"


def test_sanitize_text_handles_non_string():
    assert sanitize_text(None) == ""
