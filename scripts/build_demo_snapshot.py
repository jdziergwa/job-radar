"""Export a profile snapshot into static files for the GitHub Pages demo."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.deps import get_profile_dir, get_store
from api.models import (
    CompaniesResponse,
    DismissalStats,
    InsightsResponse,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
    MarketIntelligenceResponse,
    StatsOverview,
    TrendsResponse,
)
from src.providers import get_all_info


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_model(path: Path, model: Any) -> None:
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _load_companies(profile: str) -> CompaniesResponse:
    companies_path = get_profile_dir(profile) / "companies.yaml"
    data = yaml.safe_load(companies_path.read_text(encoding="utf-8")) or {}
    return CompaniesResponse(
        greenhouse=data.get("greenhouse", []),
        lever=data.get("lever", []),
        ashby=data.get("ashby", []),
        workable=data.get("workable", []),
    )


def _build_insights_response(store: Any, profile: str, days: int) -> InsightsResponse:
    cache_keys = [
        f"insights_cache_{profile}_{days}",
        f"insights_cache_default_{days}",
    ]

    for cache_key in cache_keys:
        cached_raw = store.get_metadata(cache_key)
        if not cached_raw:
            continue
        try:
            cached_data = json.loads(cached_raw)
            return InsightsResponse(
                report=cached_data["report"],
                generated_at=cached_data["generated_at"],
                cached=True,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue

    return InsightsResponse(
        report=(
            "## Demo Snapshot Notice\n\n"
            "- This hosted demo uses a static data snapshot.\n"
            "- Narrative market insights were not baked into this export yet.\n"
            "- Rebuild after calling `/api/stats/insights?profile=demo&days=30` to include the cached report."
        ),
        generated_at=_now_iso(),
        cached=True,
    )


def _load_json_or_none(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_snapshot(profile: str, out_dir: Path, max_jobs: int, days: int) -> None:
    profile_dir = get_profile_dir(profile)
    example_dir = get_profile_dir("example")
    db_path = Path("data") / f"{profile}.db"

    if not profile_dir.exists():
        raise FileNotFoundError(f"Profile directory not found: {profile_dir}")
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    store = get_store(profile)

    out_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir = out_dir / "jobs"
    shutil.rmtree(jobs_dir, ignore_errors=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    rows, total = store.get_jobs_filtered(page=1, per_page=max_jobs)
    jobs = [JobResponse.from_row(row) for row in rows]
    job_list = JobListResponse(
        jobs=jobs,
        total=total,
        page=1,
        pages=max(1, -(-total // max_jobs)),
        per_page=max_jobs,
    )
    _write_model(out_dir / "jobs.json", job_list)

    for row in rows:
        detail_row = store.get_job_detail(row["id"])
        if detail_row is None:
            continue
        _write_model(
            jobs_dir / f"{row['id']}.json",
            JobDetailResponse.from_row(detail_row),
        )

    _write_model(out_dir / "stats.json", StatsOverview(**store.get_stats()))
    _write_model(out_dir / "stats-trends.json", TrendsResponse(**store.get_trends(days=days)))

    market_data = store.get_market_intelligence(days=days)
    _write_model(
        out_dir / "stats-market.json",
        MarketIntelligenceResponse(
            skip_reason_distribution=[
                {"reason": reason, "count": count}
                for reason, count in market_data["skip_reason_distribution"].items()
            ],
            country_distribution=market_data["country_distribution"],
            missing_skills=market_data["missing_skills"],
            total_scored=market_data["total_scored"],
            apply_priority_counts=market_data["apply_priority_counts"],
            salary_distribution=market_data["salary_distribution"],
        ),
    )
    _write_model(out_dir / "stats-dismissed.json", DismissalStats(**store.get_dismissal_stats()))
    _write_model(out_dir / "stats-insights.json", _build_insights_response(store, profile, days))

    _write_json(out_dir / "providers.json", [info.__dict__ for info in get_all_info()])
    _write_model(out_dir / "companies.json", _load_companies(profile))

    (out_dir / "profile-yaml.txt").write_text(
        (profile_dir / "search_config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out_dir / "profile-doc.txt").write_text(
        (profile_dir / "profile_doc.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out_dir / "scoring-philosophy.txt").write_text(
        (profile_dir / "scoring_philosophy.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    _write_json(
        out_dir / "wizard-state.json",
        {
            "profile_name": profile,
            "cv_analysis": _load_json_or_none(profile_dir / "cv_analysis.json"),
            "user_preferences": _load_json_or_none(profile_dir / "preferences.json"),
        },
    )
    _write_json(
        out_dir / "wizard-template.json",
        {
            "profile_yaml": (example_dir / "search_config.yaml").read_text(encoding="utf-8"),
            "profile_doc": (example_dir / "profile_doc.md").read_text(encoding="utf-8"),
        },
    )

    _write_json(out_dir / "profiles.json", [{"name": profile, "has_data": True}])
    _write_json(out_dir / "health.json", {"status": "ok", "version": "1.0.0", "demo": True})
    _write_json(
        out_dir / "snapshot.json",
        {
            "generated_at": _now_iso(),
            "job_count": total,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="demo")
    parser.add_argument("--out", default="web/public/demo-data")
    parser.add_argument("--max-jobs", type=int, default=80)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    build_snapshot(
        profile=args.profile,
        out_dir=Path(args.out),
        max_jobs=args.max_jobs,
        days=args.days,
    )


if __name__ == "__main__":
    main()
