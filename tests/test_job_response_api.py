import tempfile
from pathlib import Path

from api.models import JobDetailResponse, JobResponse
from src.models import RawJob
from src.store import Store


def test_job_list_response_exposes_company_quality_signals_and_fit_category():
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

        candidates = store.get_unscored()
        assert len(candidates) == 1
        db_id = candidates[0].db_id
        store.update_score(
            db_id=db_id,
            fit_score=67,
            reasoning="Strategic but below target seniority.",
            breakdown={
                "tech_stack_match": 62,
                "seniority_match": 58,
                "remote_location_fit": 90,
                "growth_potential": 79,
            },
            key_matches=["Distributed systems"],
            red_flags=["Mid-level scope"],
            fit_category="strategic_exception",
            apply_priority="low",
        )

        rows, total = store.get_jobs_filtered(status=["scored"], per_page=10)

        assert total == 1
        response = JobResponse.from_row(rows[0])

        assert response.company_quality_signals == [
            "strong product company",
            "high engineering reputation",
        ]
        assert response.score_breakdown is not None
        assert response.score_breakdown.fit_category == "strategic_exception"


def test_job_detail_response_exposes_company_quality_signals():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        inserted = store.upsert_jobs([
            RawJob(
                ats_platform="lever",
                company_slug="vercel",
                company_name="Vercel",
                job_id="role-2",
                title="Senior Platform Engineer",
                location="Berlin, Germany",
                url="https://example.com/jobs/2",
                description="Platform role description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                company_metadata={
                    "quality_signals": ["strong cv value"],
                },
            )
        ])

        candidates = store.get_unscored()
        assert len(candidates) == 1
        row = store.get_job_detail(candidates[0].db_id)
        assert row is not None

        response = JobDetailResponse.from_row(row)

        assert response.company_quality_signals == ["strong cv value"]


def test_job_response_exposes_structured_location_metadata_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="example-labs",
                company_name="Example Labs",
                job_id="role-structured-location",
                title="Staff QA Engineer",
                location="London",
                url="https://example.com/jobs/structured-location",
                description="Structured location metadata example.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
                location_metadata={
                    "raw_location": "London",
                    "workplace_type": "Remote",
                },
            )
        ])

        row = store.get_job_detail(store.get_unscored()[0].db_id)
        assert row is not None

        response = JobDetailResponse.from_row(row)

        assert response.location == "London"
        assert response.raw_location == "London"
        assert response.workplace_type == "Remote"


def test_job_response_normalizes_stale_priority_from_fit_score():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="linear",
                company_name="Linear",
                job_id="role-3",
                title="Senior Backend Engineer",
                location="Remote",
                url="https://example.com/jobs/3",
                description="Example description.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            )
        ])

        candidate = store.get_unscored()[0]
        store.update_score(
            db_id=candidate.db_id,
            fit_score=82,
            reasoning="Strong role fit.",
            breakdown={
                "tech_stack_match": 84,
                "seniority_match": 82,
                "remote_location_fit": 90,
                "growth_potential": 78,
            },
            fit_category="core_fit",
            apply_priority="medium",
        )

        row = store.get_job_detail(candidate.db_id)
        assert row is not None

        response = JobDetailResponse.from_row(row)

        assert response.fit_score == 82
        assert response.score_breakdown is not None
        assert response.score_breakdown.apply_priority == "high"


def test_job_response_marks_pipeline_jobs_as_fresh_since_previous_collection_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="ashby",
                company_slug="example-labs",
                company_name="Example Labs",
                job_id="role-old",
                title="Backend Engineer",
                location="Remote",
                url="https://example.com/jobs/old",
                description="Older pipeline job.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
            RawJob(
                ats_platform="ashby",
                company_slug="example-labs",
                company_name="Example Labs",
                job_id="role-new",
                title="Staff Backend Engineer",
                location="Remote",
                url="https://example.com/jobs/new",
                description="Fresh pipeline job.",
                posted_at="2026-04-08T00:00:00Z",
                fetched_at="2026-04-08T00:00:00Z",
            ),
        ])

        candidates = {candidate.job_id: candidate.db_id for candidate in store.get_unscored()}
        store.set_metadata("previous_collection_run_at", "2026-04-10T12:00:00")

        with store._connect() as conn:
            conn.execute(
                "UPDATE jobs SET first_seen_at = ? WHERE id = ?",
                ("2026-04-10T10:00:00", candidates["role-old"]),
            )
            conn.execute(
                "UPDATE jobs SET first_seen_at = ? WHERE id = ?",
                ("2026-04-10T14:00:00", candidates["role-new"]),
            )

        rows, total = store.get_jobs_filtered(per_page=10, sort="date", order="asc")

        assert total == 2
        responses = {row["job_id"]: JobResponse.from_row(row) for row in rows}

        assert responses["role-old"].is_fresh is False
        assert responses["role-new"].is_fresh is True

        detail_row = store.get_job_detail(candidates["role-new"])
        assert detail_row is not None

        detail_response = JobDetailResponse.from_row(detail_row)
        assert detail_response.is_fresh is True
