import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.models import RawJob
from src.store import Store


def _job(job_id: str, title: str) -> RawJob:
    return RawJob(
        ats_platform="lever",
        company_slug="example",
        company_name="Example",
        job_id=job_id,
        title=title,
        location="Remote",
        url=f"https://example.com/{job_id}",
        description="A full description.",
        posted_at="2026-04-08T00:00:00Z",
        fetched_at="2026-04-08T00:00:00Z",
    )


def test_archive_stale_jobs_archives_only_untracked_pipeline_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(str(Path(tmpdir) / "jobs.db"))
        store.upsert_jobs([
            _job("old-active", "Old Active"),
            _job("old-tracked", "Old Tracked"),
            _job("old-manual", "Old Manual"),
            _job("recent-active", "Recent Active"),
        ])

        candidates = {job.job_id: job for job in store.get_unscored()}
        assert store.update_application_status(candidates["old-tracked"].db_id, "applied")

        old_seen_at = (datetime.utcnow() - timedelta(days=45)).isoformat()
        recent_seen_at = (datetime.utcnow() - timedelta(days=5)).isoformat()
        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET last_seen_at = ? WHERE job_id IN ('old-active', 'old-tracked', 'old-manual')",
                (old_seen_at,),
            )
            conn.execute(
                "UPDATE jobs SET source = 'manual' WHERE job_id = 'old-manual'",
            )
            conn.execute(
                "UPDATE jobs SET last_seen_at = ? WHERE job_id = 'recent-active'",
                (recent_seen_at,),
            )

        assert store.archive_stale_jobs(stale_days=30) == 1

        rows = {
            row["job_id"]: row["status"]
            for row in store.get_jobs_filtered(status=None, per_page=20)[0]
        }
        assert rows["old-active"] == "archived"
        assert rows["old-tracked"] == "new"
        assert rows["old-manual"] == "new"
        assert rows["recent-active"] == "new"


def test_upsert_restores_archived_job_when_seen_again():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(str(Path(tmpdir) / "jobs.db"))
        store.upsert_jobs([_job("returns", "Returning Role")])

        candidate = store.get_unscored()[0]
        store.update_score(
            db_id=candidate.db_id,
            fit_score=72,
            reasoning="Good fit",
            breakdown={},
        )
        store.update_status(candidate.db_id, "archived")

        store.upsert_jobs([_job("returns", "Returning Role")])

        row = store.get_job_detail(candidate.db_id)
        assert row["status"] == "scored"
