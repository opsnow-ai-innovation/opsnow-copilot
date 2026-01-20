"""Text utilities."""


def sanitize_text(text: str) -> str:
    """Remove characters that cannot be UTF-8 encoded."""
    if not isinstance(text, str):
        return ""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
