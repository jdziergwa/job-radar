from __future__ import annotations

from html.parser import HTMLParser
import re
from src.salary import parse_salary_string


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

        if tag in ["p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6"]:
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


def strip_html(html: str) -> str:
    """Remove HTML tags and return plain text."""
    if not html:
        return ""
    stripper = HTMLStripper()
    try:
        stripper.feed(html)
        return stripper.get_text().strip()
    except Exception:
        return html




def slugify(text: str) -> str:
    """Standardize string to URL-safe slug: lowercase, hyphens, alphanumeric only."""
    if not text:
        return "unknown"
    # Lowercase, replace non-alphanumeric with hyphens
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    # Remove leading/trailing hyphens
    return s.strip("-") or "unknown"

