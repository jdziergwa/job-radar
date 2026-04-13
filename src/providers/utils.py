from __future__ import annotations

import html as html_lib
from html.parser import HTMLParser
import re
from src.salary import parse_salary_string


_BLOCK_TAG_PATTERN = re.compile(
    r"</?(?:p|br|div|h[1-6]|li|ul|ol|section|article|header|footer|main|aside|tr|td|th|table)\b[^>]*>",
    re.IGNORECASE,
)
_LIST_ITEM_PATTERN = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_IGNORED_BLOCK_PATTERN = re.compile(
    r"<(?:script|style|noscript|head)\b[^>]*>.*?</(?:script|style|noscript|head)>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
_GENERIC_TAG_PATTERN = re.compile(r"<[^>]+>")


class HTMLStripper(HTMLParser):
    """Strip HTML tags from a string, keeping only text content."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._ignore_tags = {"script", "style", "noscript", "head"}
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignore_tags:
            self._ignore_depth += 1
            return
        
        if self._ignore_depth > 0:
            return

        if tag in ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "section", "article", "header", "footer"]:
            self._parts.append("\n\n")
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n• ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignore_tags:
            self._ignore_depth = max(0, self._ignore_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignore_depth > 0:
            return
        # Clean up excessive whitespace in data block but keep newlines we added
        cleaned = " ".join(data.split())
        if cleaned:
            self._parts.append(cleaned)

    def get_text(self) -> str:
        # Avoid multiple consecutive newlines and leading/trailing whitespace
        text = "".join(self._parts).strip()
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text


def _normalize_plain_text(text: str) -> str:
    """Collapse whitespace while preserving paragraph breaks and bullets."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n[ \t]+", "\n", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _strip_html_fallback(html: str) -> str:
    """Best-effort HTML cleanup for malformed markup."""
    # Unescape early for legacy reasons
    cleaned = html_lib.unescape(html or "")
    cleaned = _HTML_COMMENT_PATTERN.sub(" ", cleaned)
    cleaned = _IGNORED_BLOCK_PATTERN.sub(" ", cleaned)
    cleaned = _LIST_ITEM_PATTERN.sub("\n• ", cleaned)
    cleaned = _BLOCK_TAG_PATTERN.sub("\n\n", cleaned)
    cleaned = _GENERIC_TAG_PATTERN.sub(" ", cleaned)
    return _normalize_plain_text(cleaned)


def strip_html(html: str) -> str:
    """Remove HTML tags and return plain text."""
    if not html:
        return ""
    
    # Handle Greenhouse/Ats escaped HTML by unescaping once before parsing
    html = html_lib.unescape(html)
    
    stripper = HTMLStripper()
    try:
        stripper.feed(html)
        stripper.close()
        text = stripper.get_text().strip()
        return _normalize_plain_text(text)
    except Exception:
        return _strip_html_fallback(html)




def slugify(text: str) -> str:
    """Standardize string to URL-safe slug: lowercase, hyphens, alphanumeric only."""
    if not text:
        return "unknown"
    # Lowercase, replace non-alphanumeric with hyphens
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    # Remove leading/trailing hyphens
    return s.strip("-") or "unknown"
