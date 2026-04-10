import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


def test_company_stats_only_include_recent_in_funnel_jobs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="in-funnel-scored",
                title="QA Engineer",
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
                job_id="in-funnel-new",
                title="SDET",
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
                job_id="dismissed-role",
                title="Rejected role",
                location="Remote",
                url="https://example.com/3",
                description="Role three",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                status="dismissed",
                dismissal_reason="Title mismatch",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="globex",
                company_name="Globex",
                job_id="closed-role",
                title="Closed role",
                location="Remote",
                url="https://example.com/4",
                description="Role four",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="initech",
                company_name="Initech",
                job_id="old-role",
                title="Old role",
                location="Remote",
                url="https://example.com/5",
                description="Role five",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
        ])

        candidates = {candidate.job_id: candidate for candidate in store.get_unscored()}
        store.update_score(
            db_id=candidates["in-funnel-scored"].db_id,
            fit_score=82,
            reasoning="Strong fit",
            breakdown={"tech_stack_match": 4},
        )

        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'closed', last_seen_at = ? WHERE job_id = ?",
                ("2026-04-10T00:00:00", "closed-role"),
            )
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?, last_seen_at = ? WHERE job_id = ?",
                ("2026-02-01T00:00:00", "2026-02-05T00:00:00", "old-role"),
            )

        trends = store.get_trends(days=30)
        company_stats = {item["company_name"]: item for item in trends["company_stats"]}

        assert company_stats["Acme"]["job_count"] == 2
        assert company_stats["Acme"]["avg_score"] == 82.0
        assert "Globex" not in company_stats
        assert "Initech" not in company_stats
