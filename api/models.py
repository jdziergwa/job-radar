from pydantic import BaseModel
from typing import Optional, Literal
import json


class ScoreBreakdownDimensions(BaseModel):
    tech_stack_match: int = 0
    seniority_match: int = 0
    remote_location_fit: int = 0
    growth_potential: int = 0


class ScoreBreakdown(BaseModel):
    dimensions: ScoreBreakdownDimensions = ScoreBreakdownDimensions()
    key_matches: list[str] = []
    red_flags: list[str] = []
    apply_priority: Literal["high", "medium", "low", "skip"] = "skip"


class JobResponse(BaseModel):
    id: int
    ats_platform: str
    company_slug: str
    company_name: str
    title: str
    location: str
    url: str
    posted_at: Optional[str] = None
    first_seen_at: str
    last_seen_at: Optional[str] = None
    fit_score: Optional[int] = None
    score_reasoning: Optional[str] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    scored_at: Optional[str] = None
    status: str = "new"
    dismissal_reason: Optional[str] = None
    match_tier: Optional[str] = None
    salary: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    is_sparse: bool = False

    @classmethod
    def from_row(cls, row: dict) -> "JobResponse":
        """Parse a SQLite row dict into a JobResponse."""
        breakdown = None
        if row.get("score_breakdown"):
            try:
                raw = json.loads(row["score_breakdown"])
                breakdown = ScoreBreakdown(**raw)
            except (json.JSONDecodeError, Exception):
                pass
        return cls(**{**row, "score_breakdown": breakdown})


class JobDetailResponse(JobResponse):
    description: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    pages: int
    per_page: int


class StatusUpdate(BaseModel):
    status: Literal["new", "scored", "applied", "dismissed"]


class StatsOverview(BaseModel):
    total_jobs: int = 0
    new_today: int = 0
    total_new_today: int = 0
    new_this_week: int = 0
    scored: int = 0
    pending: int = 0
    applied: int = 0
    dismissed: int = 0
    closed: int = 0
    score_distribution: dict[str, int] = {}
    apply_priority_counts: dict[str, int] = {}


class DismissalStats(BaseModel):
    reasons: dict[str, int] = {}
    total: int = 0


class DailyCount(BaseModel):
    date: str
    new_jobs: int
    scored: int


class SkillCount(BaseModel):
    skill: str
    count: int


class CompanyStat(BaseModel):
    company_name: str
    job_count: int
    avg_score: Optional[float] = None
    last_seen: Optional[str] = None


class CountryStat(BaseModel):
    country: str
    count: int


class SkipReasonStat(BaseModel):
    reason: str
    count: int


class SalaryStat(BaseModel):
    range: str
    count: int


class MarketIntelligenceResponse(BaseModel):
    skip_reason_distribution: list[SkipReasonStat] = []
    country_distribution: list[CountryStat] = []
    missing_skills: list[SkillCount] = []
    total_scored: int = 0
    apply_priority_counts: dict[str, int] = {}
    salary_distribution: list[SalaryStat] = []


class InsightsResponse(BaseModel):
    report: str
    generated_at: str
    cached: bool


class TrendsResponse(BaseModel):
    daily_counts: list[DailyCount] = []
    top_skills: list[SkillCount] = []
    company_stats: list[CompanyStat] = []
    score_trend: list[dict] = []


class ProviderInfo(BaseModel):
    name: str
    display_name: str
    description: str
    shows_aggregator_badge: bool


class PipelineRunRequest(BaseModel):
    profile: str = "default"
    sources: list[str] = ["aggregator", "local"]
    dry_run: bool = False


class PipelineRunResponse(BaseModel):
    run_id: str


class PipelineStatusResponse(BaseModel):
    status: Literal["running", "done", "error", "cancelled", "not_found"]
    step: int = 0
    step_name: str = ""
    detail: Optional[str] = None
    duration: Optional[float] = None
    stats: Optional[dict] = None
    skipped_steps: list[int] = []
    error: Optional[str] = None


class ProfileContent(BaseModel):
    content: str


class CompanyEntry(BaseModel):
    platform: Literal["greenhouse", "lever", "ashby", "workable"]
    slug: str
    name: str


class CompaniesResponse(BaseModel):
    greenhouse: list[dict] = []
    lever: list[dict] = []
    ashby: list[dict] = []
    workable: list[dict] = []
