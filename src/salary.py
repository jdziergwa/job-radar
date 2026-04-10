from __future__ import annotations

import re

PAY_PERIOD_MULTIPLIERS = {
    "hour": 2080,
    "day": 260,
    "week": 52,
    "month": 12,
    "year": 1,
}

PAY_PERIOD_PATTERNS = {
    "hour": [
        r"/hr\b",
        r"/hour\b",
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


def _detect_pay_period(text: str) -> str | None:
    for period, patterns in PAY_PERIOD_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            return period
    return None


def parse_salary_string(salary_str: str | None) -> tuple[int | None, int | None, str | None]:
    """Extract annualized min/max salary values and a best-effort currency code."""
    if not salary_str or not isinstance(salary_str, str):
        return None, None, None

    s = salary_str.lower().replace(",", "")
    s = re.sub(r"\b\d+(?:\.\d+)?\s*%", "", s)
    pay_period = _detect_pay_period(s)

    cur = None
    if "$" in s:
        cur = "USD"
    elif "€" in s or "eur" in s:
        cur = "EUR"
    elif "£" in s or "gbp" in s:
        cur = "GBP"

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
