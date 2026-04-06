from __future__ import annotations

from html.parser import HTMLParser
import re


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


def parse_salary_string(salary_str: str | None) -> tuple[int | None, int | None, str | None]:
    """Try to extract min/max numeric values and currency from strings like '$100k - $120k' or '50000 EUR'.
    
    Returns:
        (min_val, max_val, currency_code)
    """
    if not salary_str or not isinstance(salary_str, str):
        return None, None, None
        
    # Clean string: remove commas, lowercase
    s = salary_str.lower().replace(",", "")
    
    # Currency detection (basic)
    cur = None
    if "$" in s: cur = "USD"
    elif "€" in s or "eur" in s: cur = "EUR"
    elif "£" in s or "gbp" in s: cur = "GBP"
    
    # Regex for numbers with optional 'k'
    # Matches: 100,000, 100k, 120000, etc.
    patterns = re.findall(r"(\d+)(k?)", s)
    nums = []
    for val, k in patterns:
        try:
            n = int(val)
            if k == "k": n *= 1000
            nums.append(n)
        except ValueError:
            continue
    
    if not nums:
        return None, None, cur
        
    s_min = min(nums)
    s_max = max(nums)
    return s_min, s_max, cur
