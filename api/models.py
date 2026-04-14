from pydantic import BaseModel
from typing import Optional, Literal
import json

from src.score_normalization import normalize_persisted_priority


class ScoreBreakdownDimensions(BaseModel):
    tech_stack_match: int = 0
    seniority_match: int = 0
    remote_location_fit: int = 0
    growth_potential: int = 0


class ScoreBreakdown(BaseModel):
    dimensions: ScoreBreakdownDimensions = ScoreBreakdownDimensions()
    key_matches: list[str] = []
    red_flags: list[str] = []
    fit_category: Optional[str] = None
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
    company_quality_signals: list[str] = []

    @classmethod
    def from_row(cls, row: dict) -> "JobResponse":
        """Parse a SQLite row dict into a JobResponse."""
        breakdown = None
        company_quality_signals: list[str] = []
        if row.get("score_breakdown"):
            try:
                raw = json.loads(row["score_breakdown"])
                dimensions = raw.get("dimensions", {}) if isinstance(raw, dict) else {}
                apply_priority, _ = normalize_persisted_priority(
                    row.get("fit_score", 0),
                    dimensions if isinstance(dimensions, dict) else {},
                    raw.get("apply_priority", "skip") if isinstance(raw, dict) else "skip",
                    raw.get("skip_reason", "none") if isinstance(raw, dict) else "none",
                )
                if isinstance(raw, dict):
                    raw["apply_priority"] = apply_priority
                breakdown = ScoreBreakdown(**raw)
            except (json.JSONDecodeError, Exception):
                pass
        if row.get("company_metadata"):
            try:
                company_metadata = json.loads(row["company_metadata"])
                raw_signals = company_metadata.get("quality_signals", []) if isinstance(company_metadata, dict) else []
                if isinstance(raw_signals, list):
                    company_quality_signals = [
                        str(signal).strip()
                        for signal in raw_signals
                        if str(signal).strip()
                    ]
            except (json.JSONDecodeError, Exception):
                pass
        return cls(**{**row, "score_breakdown": breakdown, "company_quality_signals": company_quality_signals})


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
    high_priority_today: int = 0
    new_this_week: int = 0
    last_pipeline_run_at: Optional[str] = None
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
    in_funnel: int = 0
    scored: int


class PipelineFunnelStats(BaseModel):
    collected: int = 0
    passed_prefilter: int = 0
    high_priority: int = 0
    applied: int = 0


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
    currency: Optional[str] = None
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
    pipeline_funnel: PipelineFunnelStats = PipelineFunnelStats()
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
    platform: Literal["greenhouse", "lever", "ashby", "workable", "bamboohr", "smartrecruiters"]
    slug: str
    name: str
    company_quality_signals: list[str] = []


class TrackedCompanyEntry(BaseModel):
    slug: str
    name: str
    company_quality_signals: list[str] = []


class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = None
    company_quality_signals: list[str] = []


class CompaniesResponse(BaseModel):
    greenhouse: list[TrackedCompanyEntry] = []
    lever: list[TrackedCompanyEntry] = []
    ashby: list[TrackedCompanyEntry] = []
    workable: list[TrackedCompanyEntry] = []
    bamboohr: list[TrackedCompanyEntry] = []
    smartrecruiters: list[TrackedCompanyEntry] = []


# Wizard Models

class UserPreferences(BaseModel):
    targetRoles: list[str] = []
    seniority: list[str] = []
    location: str
    baseCity: Optional[str] = None
    baseCountry: str = ""
    workAuth: str
    remotePref: list[str] = []
    primaryRemotePref: Optional[str] = None
    timezonePref: Optional[str] = None
    targetRegions: list[str] = []
    excludedRegions: list[str] = []
    industries: list[str] = []
    careerDirection: str
    careerGoal: Optional[Literal['stay', 'pivot', 'step_up', 'broaden']] = "stay"
    careerDirectionEdited: bool = False
    goodMatchSignals: list[str] = []
    goodMatchSignalsConfirmed: bool = False
    companyQualitySignals: list[str] = []
    allowLowerSeniorityAtStrategicCompanies: bool = False
    dealBreakers: list[str] = []
    dealBreakersConfirmed: bool = False
    enableStandardExclusions: bool = True
    additionalContext: Optional[str] = None


class ExperienceEntry(BaseModel):
    company: str
    role: str
    dates: str
    industry: Optional[str] = None
    highlights: list[str] = []


class EducationEntry(BaseModel):
    school: str
    degree: str
    start_year: Optional[str] = None
    end_year: Optional[str] = None


class PortfolioEntry(BaseModel):
    name: str
    url: str
    technologies: list[str] = []
    description: Optional[str] = None


class CVAnalysisResponse(BaseModel):
    page_count: int
    current_role: str
    experience_years: Optional[int] = None
    experience_summary: str
    experience: list[ExperienceEntry] = []
    skills: dict[str, list[str]] = {}
    education: list[EducationEntry] = []
    portfolio: list[PortfolioEntry] = []
    spoken_languages: list[str] = []
    inferred_seniority: str
    suggested_target_roles: list[str] = []
    suggested_title_patterns: dict[str, list[str]] = {}
    suggested_description_signals: list[str] = []
    suggested_exclusions: list[str] = []
    suggested_skill_gaps: list[str] = []
    suggested_career_direction: str = ""
    suggested_narratives: dict[str, str] = {}  # Keys: stay, pivot, step_up, broaden
    suggested_good_match_signals: list[str] = []
    suggested_lower_fit_signals: list[str] = []
    extraction_method: Literal["text", "vision"] = "text"


class ProfileGenerateRequest(BaseModel):
    cv_analysis: CVAnalysisResponse
    user_preferences: UserPreferences
    profile_name: str = "default"


class ProfileGenerateResponse(BaseModel):
    profile_yaml: str
    profile_doc: str


class ProfileSaveRequest(BaseModel):
    profile_name: str
    profile_yaml: str
    profile_doc: str
    cv_analysis: Optional[CVAnalysisResponse] = None
    user_preferences: Optional[UserPreferences] = None


class ProfileTemplateResponse(BaseModel):
    profile_yaml: str
    profile_doc: str


class ProfileRefinementContext(BaseModel):
    mode: Literal["fresh_start", "preferences_edit"] = "fresh_start"
    changed_fields: list[str] = []
    change_summary: list[str] = []
    preserve_existing_shape: bool = True


class ProfileRefineRequest(BaseModel):
    cv_analysis: CVAnalysisResponse
    user_preferences: UserPreferences
    draft_doc: str
    draft_yaml: str
    refinement_context: Optional[ProfileRefinementContext] = None


class ProfileRefineResponse(BaseModel):
    profile_doc: str
    profile_yaml: str
    changes_made: list[str] = []


class WizardStateResponse(BaseModel):
    profile_name: str
    cv_analysis: Optional[CVAnalysisResponse] = None
    user_preferences: Optional[UserPreferences] = None
