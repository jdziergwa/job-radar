import tempfile
from pathlib import Path

from src.store import Store
from src.models import RawJob


def test_store_persists_normalization_audit_in_score_breakdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        with store._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO jobs (
                    ats_platform, company_slug, job_id, company_name, title, location, url, description, first_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "test",
                    "example",
                    "1",
                    "ExampleCo",
                    "Example Role",
                    "Remote",
                    "https://example.com/jobs/1",
                    "Example description",
                    "2026-04-08T00:00:00",
                ),
            )
            db_id = cursor.lastrowid

        audit = {
            "raw_fit_score": 90,
            "weighted_fit_score": 74,
            "normalized_fit_score": 39,
            "raw_apply_priority": "high",
            "normalized_apply_priority": "skip",
            "raw_skip_reason": "none",
            "normalized_skip_reason": "location_timezone",
            "changed_fields": ["fit_score", "apply_priority", "skip_reason"],
            "reason_codes": ["weighted_fit_cap", "remote_hard_stop"],
        }

        store.update_score(
            db_id=db_id,
            fit_score=39,
            reasoning="Example reasoning",
            breakdown={
                "tech_stack_match": 95,
                "seniority_match": 90,
                "remote_location_fit": 20,
                "growth_potential": 90,
            },
            fit_category="conditional_fit",
            apply_priority="skip",
            skip_reason="location_timezone",
            normalization_audit=audit,
        )

        stored = store.get_job_by_id(db_id)

        assert stored is not None
        assert stored.fit_category == "conditional_fit"
        assert stored.normalization_audit == audit


def test_store_priority_filter_uses_normalized_fit_score_not_stale_breakdown_priority():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        store.upsert_jobs([
            RawJob(
                ats_platform="test",
                company_slug="example",
                company_name="ExampleCo",
                job_id="2",
                title="Senior Backend Engineer",
                location="Remote",
                url="https://example.com/jobs/2",
                description="Example description",
                posted_at="2026-04-08T00:00:00",
                fetched_at="2026-04-08T00:00:00",
            ),
        ])

        candidate = store.get_unscored()[0]
        store.update_score(
            db_id=candidate.db_id,
            fit_score=82,
            reasoning="Example reasoning",
            breakdown={
                "tech_stack_match": 84,
                "seniority_match": 82,
                "remote_location_fit": 90,
                "growth_potential": 78,
            },
            fit_category="core_fit",
            apply_priority="medium",
        )

        high_rows, high_total = store.get_jobs_filtered(status=["scored"], priority="high", per_page=10)
        medium_rows, medium_total = store.get_jobs_filtered(status=["scored"], priority="medium", per_page=10)

        assert high_total == 1
        assert len(high_rows) == 1
        assert medium_total == 0
        assert medium_rows == []


def _insert_job(store, job_id):
    with store._connect() as conn:
        return conn.execute(
            """INSERT INTO jobs (
                ats_platform, company_slug, job_id, company_name, title, location, url, description, first_seen_at
            ) VALUES ('test', 'example', ?, 'ExampleCo', 'Role', 'Remote', 'https://example.com/x', 'd', '2026-04-08T00:00:00')""",
            (job_id,),
        ).lastrowid


def test_store_persists_llm_provider_and_model_in_score_breakdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(str(Path(tmpdir) / "jobs.db"))
        db_id = _insert_job(store, "3")

        store.update_score(
            db_id=db_id,
            fit_score=70,
            reasoning="r",
            breakdown={"tech_stack_match": 70},
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
        )

        stored = store.get_job_by_id(db_id)
        assert stored.llm_provider == "gemini"
        assert stored.llm_model == "gemini-2.5-flash"


def test_rows_scored_without_provenance_load_without_the_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(str(Path(tmpdir) / "jobs.db"))
        db_id = _insert_job(store, "4")

        store.update_score(db_id=db_id, fit_score=70, reasoning="r", breakdown={"tech_stack_match": 70})

        stored = store.get_job_by_id(db_id)
        assert stored.llm_provider is None
        assert stored.llm_model is None
