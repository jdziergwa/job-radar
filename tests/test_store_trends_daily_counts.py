import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


def test_daily_counts_use_scored_at_instead_of_first_seen_date():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="job-1",
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
                job_id="job-2",
                title="SDET",
                location="Remote",
                url="https://example.com/2",
                description="Role two",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
        ])

        candidates = {candidate.job_id: candidate for candidate in store.get_unscored()}
        store.update_score(
            db_id=candidates["job-1"].db_id,
            fit_score=81,
            reasoning="Strong fit",
            breakdown={"tech_stack_match": 4},
        )
        store.update_score(
            db_id=candidates["job-2"].db_id,
            fit_score=74,
            reasoning="Good fit",
            breakdown={"tech_stack_match": 4},
        )

        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?, scored_at = ? WHERE job_id = ?",
                ("2026-04-09T08:00:00", "2026-04-10T09:30:00", "job-1"),
            )
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?, scored_at = ? WHERE job_id = ?",
                ("2026-04-09T12:00:00", "2026-04-10T11:45:00", "job-2"),
            )

        trends = store.get_trends(days=30)
        daily_counts = {item["date"]: item for item in trends["daily_counts"]}

        assert daily_counts["2026-04-09"]["new_jobs"] == 2
        assert daily_counts["2026-04-09"]["in_funnel"] == 2
        assert daily_counts["2026-04-09"]["scored"] == 0
        assert daily_counts["2026-04-10"]["new_jobs"] == 0
        assert daily_counts["2026-04-10"]["in_funnel"] == 0
        assert daily_counts["2026-04-10"]["scored"] == 2


def test_daily_counts_only_count_prefilter_survivors_as_in_funnel():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="survivor",
                title="QA Engineer",
                location="Remote",
                url="https://example.com/1",
                description="Role one",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                match_tier="high_confidence",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="rejected",
                title="Irrelevant role",
                location="Remote",
                url="https://example.com/2",
                description="Role two",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                status="dismissed",
                dismissal_reason="Failed Title Filter",
            ),
        ])

        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET first_seen_at = ?",
                ("2026-04-09T10:00:00",),
            )

        trends = store.get_trends(days=30)
        daily_counts = {item["date"]: item for item in trends["daily_counts"]}

        assert daily_counts["2026-04-09"]["new_jobs"] == 2
        assert daily_counts["2026-04-09"]["in_funnel"] == 1


def test_pipeline_funnel_counts_collected_prefilter_high_priority_and_applied():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="high-priority",
                title="QA Engineer",
                location="Remote",
                url="https://example.com/1",
                description="Role one",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                match_tier="high_confidence",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="applied-role",
                title="SDET",
                location="Remote",
                url="https://example.com/2",
                description="Role two",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                match_tier="broad_match",
                status="applied",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="acme",
                company_name="Acme",
                job_id="rejected-role",
                title="Irrelevant role",
                location="Remote",
                url="https://example.com/3",
                description="Role three",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                status="dismissed",
                dismissal_reason="Failed Title Filter",
            ),
        ])

        candidates = {candidate.job_id: candidate for candidate in store.get_unscored()}
        store.update_score(
            db_id=candidates["high-priority"].db_id,
            fit_score=82,
            reasoning="Strong fit",
            breakdown={"tech_stack_match": 84, "remote_location_fit": 90},
            apply_priority="medium",
        )

        trends = store.get_trends(days=30)
        funnel = trends["pipeline_funnel"]

        assert funnel["collected"] == 3
        assert funnel["passed_prefilter"] == 2
        assert funnel["high_priority"] == 1
        assert funnel["applied"] == 1
