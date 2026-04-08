import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


def test_store_persists_company_metadata_on_raw_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        inserted = store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="linear",
                company_name="Linear",
                job_id="role-1",
                title="Mid Backend Engineer",
                location="Remote",
                url="https://example.com/jobs/1",
                description="Example description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                company_metadata={
                    "quality_signals": ["strong product company", "high engineering reputation"],
                    "source": "companies_yaml",
                },
            )
        ])

        assert len(inserted) == 1

        candidates = store.get_unscored()

        assert len(candidates) == 1
        assert candidates[0].company_metadata == {
            "quality_signals": ["strong product company", "high engineering reputation"],
            "source": "companies_yaml",
        }
