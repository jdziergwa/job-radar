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


def test_get_jobs_for_rescore_failed_recent_selects_recent_api_errors_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="recent-error",
                title="Recent Error Role",
                location="Remote",
                url="https://example.com/recent-error",
                description="A full description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="real-zero",
                title="Real Zero Role",
                location="Remote",
                url="https://example.com/real-zero",
                description="A full description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="old-error",
                title="Old Error Role",
                location="Remote",
                url="https://example.com/old-error",
                description="A full description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
        ])

        unscored = {job.job_id: job for job in store.get_unscored()}
        store.update_score(
            db_id=unscored["recent-error"].db_id,
            fit_score=0,
            reasoning="API_ERROR: credit balance is too low",
            breakdown={},
        )
        store.update_score(
            db_id=unscored["real-zero"].db_id,
            fit_score=0,
            reasoning="The role is not a fit.",
            breakdown={},
        )
        store.update_score(
            db_id=unscored["old-error"].db_id,
            fit_score=0,
            reasoning="API_ERROR: older failure",
            breakdown={},
        )
        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET first_seen_at = datetime('now', '-30 days') WHERE job_id = ?",
                ("old-error",),
            )

        selected_job_ids = [
            job.job_id
            for job in store.get_jobs_for_rescore(scope="failed_recent", days=7)
        ]

        assert selected_job_ids == ["recent-error"]


def test_get_jobs_for_rescore_unscored_new_scope_excludes_scored_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="scored",
                title="Scored Role",
                location="Remote",
                url="https://example.com/scored",
                description="A full description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="new",
                title="New Role",
                location="Remote",
                url="https://example.com/new",
                description="A full description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
        ])

        unscored = {job.job_id: job for job in store.get_unscored()}
        store.update_score(
            db_id=unscored["scored"].db_id,
            fit_score=75,
            reasoning="Good fit",
            breakdown={},
        )

        selected_job_ids = [
            job.job_id
            for job in store.get_jobs_for_rescore(scope="unscored_new")
        ]

        assert selected_job_ids == ["new"]
