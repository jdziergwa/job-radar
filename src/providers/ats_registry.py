from __future__ import annotations

from typing import Any

BULK_FETCH_ATS_PLATFORMS = (
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "bamboohr",
    "smartrecruiters",
)

IMPORT_ONLY_ATS_PLATFORMS = (
    "workday",
)

SINGLE_JOB_IMPORT_ATS_PLATFORMS = (
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "bamboohr",
    "smartrecruiters",
    "workday",
)

BULK_FETCHERS: dict[str, Any] = {}


def register_bulk_fetchers(fetchers: dict[str, Any]) -> dict[str, Any]:
    expected = set(BULK_FETCH_ATS_PLATFORMS)
    actual = set(fetchers)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        problems: list[str] = []
        if missing:
            problems.append(f"missing={missing}")
        if extra:
            problems.append(f"extra={extra}")
        raise ValueError(f"Bulk fetcher registry mismatch: {', '.join(problems)}")

    BULK_FETCHERS.clear()
    BULK_FETCHERS.update(fetchers)
    return BULK_FETCHERS
