import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


def test_upsert_jobs_backfills_short_existing_description():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        inserted_count = store.upsert_jobs([
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="job-1",
                title="Platform Engineer",
                location="Remote",
                url="https://example.com/job-1",
                description="Short stub",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            )
        ])

        assert inserted_count == 1

        richer_description = (
            "This platform engineering role owns developer infrastructure, CI pipelines, "
            "service reliability, and internal tooling across distributed systems."
        )

        inserted_count = store.upsert_jobs([
            RawJob(
                ats_platform="lever",
                company_slug="example",
                company_name="Example",
                job_id="job-1",
                title="Platform Engineer",
                location="Remote",
                url="https://example.com/job-1",
                description=richer_description,
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T01:00:00Z",
            )
        ])

        assert inserted_count == 0

        stored = store.get_unscored()
        assert len(stored) == 1
        assert stored[0].description == richer_description
