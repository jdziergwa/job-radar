from __future__ import annotations

import re

PAY_PERIOD_MULTIPLIERS = {
    "hour": 2080,
    "day": 260,
    "week": 52,
    "month": 12,
    "year": 1,
}

CURRENCY_PATTERNS = (
    ("USD", (r"\$", r"\busd\b")),
    ("EUR", (r"€", r"\beur\b")),
    ("GBP", (r"£", r"\bgbp\b")),
    ("PLN", (r"\bpln\b", r"\bzl\b", r"\bzł\b")),
    ("CHF", (r"\bchf\b",)),
    ("CAD", (r"\bcad\b",)),
)

PAY_PERIOD_PATTERNS = {
    "hour": [
        r"/h\b",
        r"/hr\b",
        r"/hour\b",
        r"\bper hr\b",
        r"\bper hour\b",
        r"\bhourly\b",
    ],
    "day": [
        r"/day\b",
        r"\bper day\b",
        r"\bdaily\b",
    ],
    "week": [
        r"/week\b",
        r"/wk\b",
        r"\bper week\b",
        r"\bweekly\b",
    ],
    "month": [
        r"/month\b",
        r"/mo\b",
        r"\bper month\b",
        r"\bmonthly\b",
    ],
    "year": [
        r"/year\b",
        r"/yr\b",
        r"\bper year\b",
        r"\byearly\b",
        r"\bannual(?:ly)?\b",
        r"\bannum\b",
        r"\bp\.?a\.?\b",
    ],
}

_DASH_PATTERN = re.compile(r"[–—−]")
_THOUSANDS_SPACE_PATTERN = re.compile(r"(?<=\d)[\s\u00a0](?=\d{3}(?:\D|$))")


def _detect_pay_period(text: str) -> str | None:
    for period, patterns in PAY_PERIOD_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            return period
    return None


def _detect_currency(text: str) -> str | None:
    for currency, patterns in CURRENCY_PATTERNS:
        if any(re.search(pattern, text) for pattern in patterns):
            return currency
    return None


def _normalize_salary_text(text: str) -> str:
    normalized = _DASH_PATTERN.sub("-", text.lower().replace("\xa0", " "))
    while True:
        collapsed = _THOUSANDS_SPACE_PATTERN.sub("", normalized)
        if collapsed == normalized:
            break
        normalized = collapsed
    normalized = normalized.replace(",", "")
    normalized = re.sub(r"\b\d+(?:\.\d+)?\s*%", "", normalized)
    return normalized


def parse_salary_string(salary_str: str | None) -> tuple[int | None, int | None, str | None]:
    """Extract annualized min/max salary values and a best-effort currency code."""
    if not salary_str or not isinstance(salary_str, str):
        return None, None, None

    s = _normalize_salary_text(salary_str)
    primary_segment = s.split("(", 1)[0].strip() or s

    pay_period = _detect_pay_period(primary_segment) or _detect_pay_period(s)
    cur = _detect_currency(primary_segment) or _detect_currency(s)

    patterns = re.findall(r"(\d+(?:\.\d+)?)(k?)", primary_segment)
    if not patterns:
        patterns = re.findall(r"(\d+(?:\.\d+)?)(k?)", s)
    nums: list[float] = []
    for val, k in patterns:
        try:
            n = float(val)
            if k == "k":
                n *= 1000
            nums.append(n)
        except ValueError:
            continue

    if not nums:
        return None, None, None

    if any(k == "k" for _, k in patterns):
        nums = [n * 1000 if n < 1000 else n for n in nums]

    multiplier = PAY_PERIOD_MULTIPLIERS.get(pay_period or "year", 1)
    annualized = [n * multiplier for n in nums]

    return int(round(min(annualized))), int(round(max(annualized))), cur
