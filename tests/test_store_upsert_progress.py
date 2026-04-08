import tempfile
from pathlib import Path

from src.models import RawJob
import src.store as store_module
from src.store import Store


def test_upsert_jobs_reports_progress_phases():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))
        phases: list[tuple[str, int, int]] = []
        original_chunk_size = store_module.UPSERT_WRITE_CHUNK_SIZE
        store_module.UPSERT_WRITE_CHUNK_SIZE = 2

        try:
            jobs = [
                RawJob(
                    ats_platform="lever",
                    company_slug="example",
                    company_name="Example",
                    job_id=f"job-{idx}",
                    title=f"Role {idx}",
                    location="Remote",
                    url=f"https://example.com/{idx}",
                    description="Example description long enough to avoid sparse edge cases.",
                    posted_at="2026-04-08T00:00:00Z",
                    fetched_at="2026-04-08T00:00:00Z",
                )
                for idx in range(5)
            ]

            store.upsert_jobs(jobs, progress_callback=lambda phase, current, total: phases.append((phase, current, total)))
        finally:
            store_module.UPSERT_WRITE_CHUNK_SIZE = original_chunk_size

        insert_progress = [(phase, current, total) for phase, current, total in phases if phase == "Inserting new jobs"]

        assert insert_progress == [
            ("Inserting new jobs", 2, 5),
            ("Inserting new jobs", 4, 5),
            ("Inserting new jobs", 5, 5),
        ]
        assert "Checking existing jobs" not in [phase for phase, _, _ in phases]
        assert "Reconciling new jobs" not in [phase for phase, _, _ in phases]
