import sqlite3
import tempfile
from pathlib import Path

from src.store import Store


class _ConnectionProxy:
    def __init__(self, conn: sqlite3.Connection, pragma_calls: list[str]) -> None:
        self._conn = conn
        self._pragma_calls = pragma_calls

    def execute(self, sql, *args, **kwargs):
        if sql == "PRAGMA journal_mode=WAL":
            self._pragma_calls.append(sql)
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_store_only_enables_wal_once_per_database_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        pragma_calls: list[str] = []
        real_connect = sqlite3.connect

        def connect_proxy(*args, **kwargs):
            return _ConnectionProxy(real_connect(*args, **kwargs), pragma_calls)

        original_connect = sqlite3.connect
        sqlite3.connect = connect_proxy
        try:
            first_store = Store(str(db_path))
            second_store = Store(str(db_path))

            with first_store._connect() as conn:
                conn.execute("SELECT 1")

            with second_store._connect() as conn:
                conn.execute("SELECT 1")
        finally:
            sqlite3.connect = original_connect

        assert pragma_calls == ["PRAGMA journal_mode=WAL"]


def test_store_connections_set_busy_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        store = Store(str(db_path))

        with store._connect() as conn:
            busy_timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]

        assert busy_timeout_ms == 30000


def test_store_migrates_legacy_applied_status_into_application_tracking():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ats_platform TEXT NOT NULL,
                    company_slug TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    company_name TEXT,
                    title TEXT NOT NULL,
                    location TEXT,
                    url TEXT NOT NULL,
                    description TEXT,
                    posted_at TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    fit_score INTEGER,
                    score_reasoning TEXT,
                    score_breakdown TEXT,
                    scored_at TEXT,
                    status TEXT DEFAULT 'new',
                    dismissal_reason TEXT,
                    match_tier TEXT,
                    salary TEXT,
                    salary_min INTEGER,
                    salary_max INTEGER,
                    salary_currency TEXT,
                    is_sparse INTEGER DEFAULT 0,
                    UNIQUE(ats_platform, company_slug, job_id)
                );
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            conn.execute(
                """INSERT INTO jobs (
                       ats_platform, company_slug, job_id, company_name, title, location, url,
                       description, posted_at, first_seen_at, last_seen_at, scored_at, status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "ashby",
                    "acme",
                    "legacy-job",
                    "Acme",
                    "QA Engineer",
                    "Remote",
                    "https://example.com/jobs/legacy",
                    "Legacy role",
                    "2026-04-08T00:00:00Z",
                    "2026-04-08T10:00:00",
                    "2026-04-09T10:00:00",
                    "2026-04-10T12:00:00",
                    "applied",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        store = Store(str(db_path))

        with store._connect() as migrated_conn:
            row = migrated_conn.execute(
                """SELECT status, application_status, applied_at, source
                   FROM jobs WHERE job_id = 'legacy-job'"""
            ).fetchone()
            events = migrated_conn.execute(
                """SELECT status, note FROM application_events
                   WHERE job_id = (SELECT id FROM jobs WHERE job_id = 'legacy-job')"""
            ).fetchall()

        assert row is not None
        assert row["status"] == "scored"
        assert row["application_status"] == "applied"
        assert row["applied_at"] == "2026-04-09T10:00:00"
        assert row["source"] == "pipeline"
        assert len(events) == 1
        assert events[0]["status"] == "applied"
        assert events[0]["note"] == "Migrated from existing application status"


def test_store_repairs_mismatched_legacy_applied_event_date():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ats_platform TEXT NOT NULL,
                    company_slug TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    company_name TEXT,
                    title TEXT NOT NULL,
                    location TEXT,
                    url TEXT NOT NULL,
                    description TEXT,
                    posted_at TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    fit_score INTEGER,
                    score_reasoning TEXT,
                    score_breakdown TEXT,
                    scored_at TEXT,
                    status TEXT DEFAULT 'new',
                    application_status TEXT,
                    applied_at TEXT,
                    dismissal_reason TEXT,
                    match_tier TEXT,
                    salary TEXT,
                    salary_min INTEGER,
                    salary_max INTEGER,
                    salary_currency TEXT,
                    is_sparse INTEGER DEFAULT 0,
                    source TEXT DEFAULT 'pipeline',
                    UNIQUE(ats_platform, company_slug, job_id)
                );
                CREATE TABLE application_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            conn.execute(
                """INSERT INTO jobs (
                       ats_platform, company_slug, job_id, company_name, title, location, url,
                       description, posted_at, first_seen_at, last_seen_at, status, application_status, applied_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "ashby",
                    "example-co",
                    "legacy-tracked-job",
                    "Example Co",
                    "QA Engineer",
                    "Remote",
                    "https://example.com/jobs/legacy-tracked-job",
                    "Legacy tracked role",
                    "2026-04-08T00:00:00Z",
                    "2026-04-08T10:00:00",
                    "2026-04-09T10:00:00",
                    "scored",
                    "applied",
                    "2026-04-15",
                ),
            )
            conn.execute(
                """INSERT INTO application_events (job_id, status, note, created_at)
                   VALUES (
                     (SELECT id FROM jobs WHERE job_id = 'legacy-tracked-job'),
                     'applied',
                     'Migrated from existing application status',
                     '2026-04-17'
                   )"""
            )
            conn.commit()
        finally:
            conn.close()

        store = Store(str(db_path))

        with store._connect() as migrated_conn:
            event = migrated_conn.execute(
                """SELECT created_at FROM application_events
                   WHERE job_id = (SELECT id FROM jobs WHERE job_id = 'legacy-tracked-job')
                     AND status = 'applied'"""
            ).fetchone()

        assert event is not None
        assert event["created_at"] == "2026-04-15"
