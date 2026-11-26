"""Data models for Job Radar — dataclasses for the pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringProvenance:
    """Which LLM Provider and Model produced a score."""

    llm_provider: str
    model: str

    @classmethod
    def from_breakdown(cls, data: dict) -> "ScoringProvenance | None":
        """Rebuild from a persisted `score_breakdown` dict; None for rows scored before provenance."""
        if data.get("llm_provider") and data.get("llm_model"):
            return cls(data["llm_provider"], data["llm_model"])
        return None


@dataclass
class RawJob:
    """Job straight from an ATS API, before dedup or filtering."""

    ats_platform: str       # "greenhouse" | "lever" | "ashby" | "workable"
    company_slug: str       # e.g. "crowdstrike", "kraken"
    company_name: str       # Display name from config
    job_id: str             # ATS-specific job ID
    title: str
    location: str           # Raw location string
    url: str                # Direct application URL
    description: str        # Full job description (plain text, HTML stripped)
    posted_at: str | None   # ISO date if available
    fetched_at: str         # ISO timestamp of fetch
    company_metadata: dict[str, object] = field(default_factory=dict)
    location_metadata: dict[str, object] = field(default_factory=dict)
    status: str = "new"     # "new" | "dismissed" | "archived"
    dismissal_reason: str | None = None
    match_tier: str | None = None
    salary: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    collection_provider: str | None = None


@dataclass
class CandidateJob:
    """Job that passed pre-filter — ready for LLM scoring."""

    db_id: int              # Internal database row id
    ats_platform: str
    company_slug: str
    company_name: str
    job_id: str
    title: str
    location: str
    url: str
    description: str
    posted_at: str | None
    first_seen_at: str
    company_metadata: dict[str, object] = field(default_factory=dict)
    location_metadata: dict[str, object] = field(default_factory=dict)
    match_tier: str | None = None
    salary: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None


@dataclass
class ScoredJob:
    """Job after LLM scoring — has fit assessment."""

    db_id: int
    ats_platform: str
    company_slug: str
    company_name: str
    job_id: str
    title: str
    location: str
    url: str
    description: str
    posted_at: str | None
    first_seen_at: str
    company_metadata: dict[str, object] = field(default_factory=dict)
    location_metadata: dict[str, object] = field(default_factory=dict)
    match_tier: str | None = None
    salary: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None

    # Scoring results
    fit_score: int = 0                          # 0-100
    reasoning: str = ""
    breakdown: dict[str, int] = field(default_factory=dict)
    key_matches: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    fit_category: str = ""
    apply_priority: str = "skip"                # high | medium | low | skip
    skip_reason: str = "none"               # location_onsite | location_timezone | tech_gap | seniority_mismatch | growth_mismatch | none
    missing_skills: list[str] = field(default_factory=list)
    normalization_audit: dict[str, object] = field(default_factory=dict)
    provenance: ScoringProvenance | None = None
    scored_at: str | None = None
    is_sparse: bool = False
    scoring_error: str | None = None

    # Status
    status: str = "new"
