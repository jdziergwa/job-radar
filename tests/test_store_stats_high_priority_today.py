import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.models import RawJob
from src.store import Store


def _score_payload(priority: str) -> str:
    return json.dumps({
        "dimensions": {"remote_location_fit": 90},
        "apply_priority": priority,
        "skip_reason": "none",
    })


def test_get_stats_includes_high_priority_today():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="today-high",
                title="Senior QA Engineer",
                location="Remote",
                url="https://example.com/1",
                description="Role one",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="today-low",
                title="Junior QA Engineer",
                location="Remote",
                url="https://example.com/2",
                description="Role two",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="week-high",
                title="Automation QA Engineer",
                location="Remote",
                url="https://example.com/3",
                description="Role three",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
        ])

        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)

        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?, fit_score = ?, score_breakdown = ?, scored_at = ?, status = 'scored' WHERE job_id = ?",
                (now.isoformat(), 91, _score_payload("high"), now.isoformat(), "today-high"),
            )
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?, fit_score = ?, score_breakdown = ?, scored_at = ?, status = 'scored' WHERE job_id = ?",
                (now.isoformat(), 52, _score_payload("low"), now.isoformat(), "today-low"),
            )
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?, fit_score = ?, score_breakdown = ?, scored_at = ?, status = 'scored' WHERE job_id = ?",
                (yesterday.isoformat(), 88, _score_payload("high"), yesterday.isoformat(), "week-high"),
            )

        stats = store.get_stats()

        assert stats["high_priority_today"] == 1
