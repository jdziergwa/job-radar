import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


def test_store_persists_location_metadata_on_raw_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        inserted_count = store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="example",
                company_name="ExampleCo",
                job_id="role-1",
                title="Platform Engineer",
                location="Remote",
                url="https://example.com/jobs/1",
                description="Remote across North America only.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                location_metadata={
                    "raw_location": "Remote",
                    "derived_geographic_signals": ["Restricted to North America"],
                },
            )
        ])

        assert inserted_count == 1

        candidates = store.get_unscored()

        assert len(candidates) == 1
        assert candidates[0].location_metadata == {
            "raw_location": "Remote",
            "derived_geographic_signals": ["Restricted to North America"],
        }
