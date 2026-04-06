from __future__ import annotations

import re


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
