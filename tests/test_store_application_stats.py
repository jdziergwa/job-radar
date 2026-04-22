import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.models import RawJob
from src.store import Store


def _build_store() -> Store:
    tmpdir = tempfile.TemporaryDirectory()
    db_path = Path(tmpdir.name) / "jobs.db"
    store = Store(str(db_path))
    store._tmpdir = tmpdir  # keep temp dir alive for the test lifetime
    return store


def _seed_jobs(store: Store) -> dict[str, int]:
    jobs = [
        RawJob(
            ats_platform="ashby",
            company_slug="acme",
            company_name="Acme",
            job_id="critical-applied",
            title="Critical Applied",
            location="Remote",
            url="https://example.com/jobs/critical-applied",
            description="Critical applied role",
            posted_at="2026-04-01T00:00:00Z",
            fetched_at="2026-04-01T00:00:00Z",
        ),
        RawJob(
            ats_platform="ashby",
            company_slug="acme",
            company_name="Acme",
            job_id="warning-applied",
            title="Warning Applied",
            location="Remote",
            url="https://example.com/jobs/warning-applied",
            description="Warning applied role",
            posted_at="2026-04-01T00:00:00Z",
            fetched_at="2026-04-01T00:00:00Z",
        ),
        RawJob(
            ats_platform="ashby",
            company_slug="acme",
            company_name="Acme",
            job_id="warning-screening",
            title="Warning Screening",
            location="Remote",
            url="https://example.com/jobs/warning-screening",
            description="Warning screening role",
            posted_at="2026-04-01T00:00:00Z",
            fetched_at="2026-04-01T00:00:00Z",
        ),
        RawJob(
            ats_platform="ashby",
            company_slug="acme",
            company_name="Acme",
            job_id="ghosted",
            title="Ghosted",
            location="Remote",
            url="https://example.com/jobs/ghosted",
            description="Ghosted role",
            posted_at="2026-04-01T00:00:00Z",
            fetched_at="2026-04-01T00:00:00Z",
        ),
    ]
    store.upsert_jobs(jobs)

    with store._connect() as conn:
        rows = conn.execute("SELECT id, job_id FROM jobs").fetchall()

    return {str(row["job_id"]): int(row["id"]) for row in rows}


def _days_ago(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).replace(microsecond=0).isoformat()


def test_application_stats_stalled_count_matches_badge_logic():
    store = _build_store()
    ids = _seed_jobs(store)

    store.update_application_status(
        ids["critical-applied"],
        "applied",
        occurred_at_override=_days_ago(31),
    )

    store.update_application_status(
        ids["warning-applied"],
        "applied",
        occurred_at_override=_days_ago(8),
    )

    store.update_application_status(
        ids["warning-screening"],
        "applied",
        occurred_at_override=_days_ago(14),
    )
    store.update_application_status(
        ids["warning-screening"],
        "screening",
        occurred_at_override=_days_ago(8),
    )

    store.update_application_status(
        ids["ghosted"],
        "applied",
        occurred_at_override=_days_ago(40),
    )
    store.update_application_status(
        ids["ghosted"],
        "ghosted",
        occurred_at_override=_days_ago(35),
    )

    stats = store.get_application_stats()

    assert stats["total"] == 4
    assert stats["status_counts"]["ghosted"] == 1
    assert stats["needs_attention_count"] == 1
