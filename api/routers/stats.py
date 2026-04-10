from fastapi import APIRouter, Query
from api.deps import get_store
from api.models import StatsOverview, TrendsResponse, DismissalStats, MarketIntelligenceResponse, InsightsResponse
import json
from datetime import datetime, timedelta, timezone

router = APIRouter()
INSIGHTS_CACHE_TTL = timedelta(days=3)


def _parse_metadata_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


@router.get("/stats", response_model=StatsOverview)
def get_stats(profile: str = Query("default")):
    """Get dashboard aggregates."""
    store = get_store(profile)
    # The Store method already handles all counts and JSON parsing
    raw_stats = store.get_stats()
    return StatsOverview(**raw_stats)


@router.get("/stats/trends", response_model=TrendsResponse)
def get_trends(profile: str = Query("default"), days: int = Query(30, ge=1, le=365)):
    """Get time-series and categorical data for charts."""
    store = get_store(profile)
    # The Store method already performs the SQL grouping and JSON parsing
    trends_data = store.get_trends(days=days)
    return TrendsResponse(**trends_data)


@router.get("/stats/dismissed", response_model=DismissalStats)
def get_dismissal_stats(profile: str = Query("default")):
    """Get breakdown of dismissal reasons."""
    store = get_store(profile)
    stats = store.get_dismissal_stats()
    return DismissalStats(**stats)


async def _generate_insights_report(market_data: dict, days: int, profile: str) -> str:
    """Call Claude Haiku to generate a markdown market intelligence report."""
    from anthropic import AsyncAnthropic
    from api.deps import get_profile_dir

    # 1. Load user context from disk instead of hardcoding
    profile_dir = get_profile_dir(profile)
    doc_path = profile_dir / "profile_doc.md"
    profile_summary = ""
    if doc_path.exists():
        # Just take the first few sections or the whole thing if it's small
        profile_summary = doc_path.read_text(encoding="utf-8")
    
    async with AsyncAnthropic() as client:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=(
                "You are a career market analyst. You help a candidate understand their "
                "positioning based on their profile and recent job market data. "
                "Analyze the data and produce a concise markdown report. "
                "Use exactly these 5 sections with ## headers: "
                "Market Overview, Salary Expectations, Primary Blockers, Skill Gaps to Address, Geographic Patterns. "
                "Use bullet points only — no paragraphs. Be direct and specific. Max 400 words total."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"CANDIDATE PROFILE:\n{profile_summary}\n\n"
                    f"MARKET DATA ({days} days):\n{json.dumps(market_data, indent=2)}\n\n"
                    "Generate the market intelligence report. Focus on how the market "
                    "aligns with or blocks the candidate's specific goals and background."
                )
            }]
        )
    return response.content[0].text


@router.get("/stats/market", response_model=MarketIntelligenceResponse)
def get_market_intelligence(profile: str = Query("default"), days: int = Query(30, ge=1, le=365)):
    """Get structured market intelligence data for charts."""
    store = get_store(profile)
    data = store.get_market_intelligence(days=days)
    # Convert skip_reason_distribution dict → list[SkipReasonStat]
    skip_list = [
        {"reason": reason, "count": count}
        for reason, count in data["skip_reason_distribution"].items()
    ]
    return MarketIntelligenceResponse(
        skip_reason_distribution=skip_list,
        country_distribution=data["country_distribution"],
        missing_skills=data["missing_skills"],
        total_scored=data["total_scored"],
        apply_priority_counts=data["apply_priority_counts"],
        salary_distribution=data["salary_distribution"],
    )


@router.get("/stats/insights", response_model=InsightsResponse)
async def get_insights(
    profile: str = Query("default"),
    days: int = Query(30, ge=1, le=365),
    force: bool = Query(False),
):
    """Get LLM-generated market intelligence narrative report (cached for 3 days or until a newer pipeline run)."""
    store = get_store(profile)
    cache_key = f"insights_cache_{profile}_{days}"
    last_pipeline_run = _parse_metadata_timestamp(store.get_metadata("last_pipeline_run_at"))

    if not force:
        cached_raw = store.get_metadata(cache_key)
        if cached_raw:
            try:
                cached_data = json.loads(cached_raw)
                generated_at = _parse_metadata_timestamp(cached_data["generated_at"])
                cache_is_fresh = generated_at is not None and (datetime.utcnow() - generated_at) < INSIGHTS_CACHE_TTL
                pipeline_has_not_advanced = generated_at is not None and (
                    last_pipeline_run is None or last_pipeline_run <= generated_at
                )
                if cache_is_fresh and pipeline_has_not_advanced:
                    return InsightsResponse(
                        report=cached_data["report"],
                        generated_at=cached_data["generated_at"],
                        cached=True,
                    )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                pass  # Stale or corrupt cache — regenerate

    market_data = store.get_market_intelligence(days=days)

    if market_data["total_scored"] < 5:
        return InsightsResponse(
            report="Not enough data yet — score at least 5 jobs to generate insights.",
            generated_at=datetime.utcnow().isoformat(),
            cached=False,
        )

    report_md = await _generate_insights_report(market_data, days, profile)
    now = datetime.utcnow().isoformat()
    store.set_metadata(cache_key, json.dumps({"report": report_md, "generated_at": now}))

    return InsightsResponse(report=report_md, generated_at=now, cached=False)
