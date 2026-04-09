import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


def test_get_jobs_for_rescore_includes_scored_and_new_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="job-scored",
                title="Scored Role",
                location="Remote",
                url="https://example.com/scored",
                description="A full description that is long enough to behave like a real persisted job.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="job-new",
                title="New Role",
                location="Remote",
                url="https://example.com/new",
                description="Another persisted job description that has not been scored yet.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="job-dismissed",
                title="Dismissed Role",
                location="Remote",
                url="https://example.com/dismissed",
                description="A dismissed job that should not become eligible just because it is unscored.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                status="dismissed",
                dismissal_reason="Not relevant",
            ),
        ])

        unscored = {job.job_id: job for job in store.get_unscored()}
        store.update_score(
            db_id=unscored["job-scored"].db_id,
            fit_score=81,
            reasoning="Strong match",
            breakdown={
                "tech_stack_match": 80,
                "seniority_match": 82,
                "remote_location_fit": 85,
                "growth_potential": 78,
            },
            fit_category="core_fit",
            apply_priority="high",
        )

        selected_job_ids = [job.job_id for job in store.get_jobs_for_rescore()]

        assert "job-scored" in selected_job_ids
        assert "job-new" in selected_job_ids
        assert "job-dismissed" not in selected_job_ids
