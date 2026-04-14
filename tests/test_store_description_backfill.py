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
            "service reliability, and internal tooling across distributed systems. "
            "We are looking for someone with deep experience in Kubernetes, Terraform, "
            "and cloud-native architectures. You will be responsible for scaling our "
            "data processing pipelines and ensuring 99.99% availability for our customers. "
            "The ideal candidate has a strong background in Go or Python and has worked "
            "on large-scale infrastructure projects. "
        ) * 4  # Ensure it's well over the 500-char backfill threshold (approx 1200 chars)

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
