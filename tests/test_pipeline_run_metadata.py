import asyncio
import sys
import tempfile
from pathlib import Path

from src.models import RawJob, ScoredJob
from src.store import Store
import src.main as main_module


class _StubProvider:
    name = "stub"
    display_name = "Stub"
    description = "Stub provider for tests"
    shows_aggregator_badge = False

    def __init__(self, jobs):
        self._jobs = jobs

    async def fetch_jobs(self, ctx, progress_callback=None):
        if progress_callback is not None:
            progress_callback(len(self._jobs), len(self._jobs))
        return list(self._jobs)


def test_store_stats_include_last_pipeline_run_at_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))
        last_run = "2026-04-10T08:15:00"

        store.set_metadata("last_pipeline_run_at", last_run)
        stats = store.get_stats()

        assert stats["last_pipeline_run_at"] == last_run


def test_run_persists_last_pipeline_run_at_on_dry_run(monkeypatch, tmp_path):
    _prepare_workspace(tmp_path, monkeypatch)
    jobs = [_make_raw_job()]

    monkeypatch.setitem(main_module.PROVIDER_REGISTRY, "stub", _StubProvider(jobs))
    monkeypatch.setattr(main_module, "load_config", lambda profile_dir: {"keywords": {"title_patterns": ["Engineer"]}})
    monkeypatch.setattr(main_module, "load_companies", lambda profile_dir: {})
    monkeypatch.setattr(main_module, "load_profile_doc", lambda profile_dir: "Profile doc")
    monkeypatch.setattr(main_module, "print_scan_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_candidates", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["main.py", "--profile", "default", "--source", "stub", "--dry-run"])

    asyncio.run(main_module.run())

    last_run = Store("data/default.db").get_metadata("last_pipeline_run_at")
    assert last_run is not None


def test_run_persists_last_pipeline_run_at_after_scoring(monkeypatch, tmp_path):
    _prepare_workspace(tmp_path, monkeypatch)
    jobs = [_make_raw_job()]

    async def fake_score_jobs(candidates, *args, **kwargs):
        candidate = candidates[0]
        return [
            ScoredJob(
                db_id=candidate.db_id,
                ats_platform=candidate.ats_platform,
                company_slug=candidate.company_slug,
                company_name=candidate.company_name,
                job_id=candidate.job_id,
                title=candidate.title,
                location=candidate.location,
                url=candidate.url,
                description=candidate.description,
                posted_at=candidate.posted_at,
                first_seen_at=candidate.first_seen_at,
                company_metadata=candidate.company_metadata,
                location_metadata=candidate.location_metadata,
                match_tier=candidate.match_tier,
                salary=candidate.salary,
                salary_min=candidate.salary_min,
                salary_max=candidate.salary_max,
                salary_currency=candidate.salary_currency,
                fit_score=91,
                reasoning="Strong fit",
                breakdown={"tech_stack_match": 5},
                key_matches=["Python"],
                red_flags=[],
                fit_category="strong",
                apply_priority="high",
                skip_reason="none",
                scored_at="2026-04-10T08:15:00",
                status="new",
            )
        ]

    monkeypatch.setitem(main_module.PROVIDER_REGISTRY, "stub", _StubProvider(jobs))
    monkeypatch.setattr(main_module, "load_config", lambda profile_dir: {"keywords": {"title_patterns": ["Engineer"]}, "output": {"markdown_report": False}})
    monkeypatch.setattr(main_module, "load_companies", lambda profile_dir: {})
    monkeypatch.setattr(main_module, "load_profile_doc", lambda profile_dir: "Profile doc")
    monkeypatch.setattr(main_module, "score_jobs", fake_score_jobs)
    monkeypatch.setattr(main_module, "print_scan_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "print_results", lambda *args, **kwargs: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["main.py", "--profile", "default", "--source", "stub"])

    asyncio.run(main_module.run())

    last_run = Store("data/default.db").get_metadata("last_pipeline_run_at")
    assert last_run is not None


def _prepare_workspace(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "profiles" / "default").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)


def _make_raw_job() -> RawJob:
    return RawJob(
        ats_platform="greenhouse",
        company_slug="acme",
        company_name="Acme",
        job_id="job-1",
        title="Platform Engineer",
        location="Remote",
        url="https://example.com/jobs/1",
        description="Python platform engineering role with backend systems work.",
        posted_at="2026-04-10T08:00:00",
        fetched_at="2026-04-10T08:05:00",
    )
