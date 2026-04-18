"""SQLite storage layer for Job Radar.

Handles dedup, persistence, scoring results, and status tracking.
Database path is passed in to support multi-profile operation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable, Generator, Literal

from src.models import CandidateJob, RawJob, ScoredJob
from src.salary import parse_salary_string
from src.score_normalization import normalize_persisted_priority

logger = logging.getLogger(__name__)
UpsertProgressCallback = Callable[[str, int, int], None]
UPSERT_WRITE_CHUNK_SIZE = 5000
SALARY_BUCKET_ORDER = [
    "Undisclosed",
    "< 60k",
    *[
        f"{min_salary}k-{min_salary + 10}k"
        for min_salary in range(60, 200, 10)
    ],
    "200k+",
]


def _representative_annual_salary(
    salary_text: str | None,
    salary_min: int | None,
    salary_max: int | None,
) -> int | None:
    """Return an annualized representative salary for bucketing market data."""
    parsed_min, parsed_max, _ = parse_salary_string(salary_text)

    normalized_min = parsed_min if parsed_min is not None else salary_min
    normalized_max = parsed_max if parsed_max is not None else salary_max

    if normalized_min is None and normalized_max is None:
        return None
    if normalized_min is None:
        return int(normalized_max)
    if normalized_max is None or normalized_max < normalized_min:
        return int(normalized_min)

    return int(round((normalized_min + normalized_max) / 2))


def _salary_bucket_sort_key(currency: str | None, salary_range: str) -> tuple[int, str, int]:
    if salary_range == "Undisclosed":
        return (0, "", 0)

    try:
        bucket_index = SALARY_BUCKET_ORDER.index(salary_range)
    except ValueError:
        bucket_index = len(SALARY_BUCKET_ORDER)

    return (1, currency or "Unknown", bucket_index)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ats_platform TEXT NOT NULL,
    company_slug TEXT NOT NULL,
    job_id TEXT NOT NULL,
    company_name TEXT,
    company_metadata TEXT,
    title TEXT NOT NULL,
    location TEXT,
    location_metadata TEXT,
    url TEXT NOT NULL,
    description TEXT,
    posted_at TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT,

    -- Scoring results (filled after LLM scoring)
    fit_score INTEGER,
    score_reasoning TEXT,
    score_breakdown TEXT,
    scored_at TEXT,

    -- Status tracking
    status TEXT DEFAULT 'new',
    application_status TEXT,
    applied_at TEXT,
    notes TEXT,
    next_step TEXT,
    next_step_date TEXT,
    source TEXT DEFAULT 'pipeline',
    dismissal_reason TEXT,
    match_tier TEXT,
    salary TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT,
    is_sparse INTEGER DEFAULT 0,

    UNIQUE(ats_platform, company_slug, job_id)
);

CREATE INDEX IF NOT EXISTS idx_first_seen ON jobs(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_score ON jobs(fit_score);
CREATE INDEX IF NOT EXISTS idx_last_seen ON jobs(last_seen_at);
CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_app_events_job ON application_events(job_id);
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Store:
    """SQLite-backed job storage with context-managed connections."""

    _initialized_paths: set[str] = set()
    _init_lock = threading.Lock()
    _busy_timeout_ms = 30_000

    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.abspath(db_path)
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Initialize schema and WAL mode once per database path in this process."""
        if self.db_path in self._initialized_paths and os.path.exists(self.db_path):
            return

        with self._init_lock:
            if self.db_path in self._initialized_paths and os.path.exists(self.db_path):
                return
            self._init_db()
            self._initialized_paths.add(self.db_path)

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

            existing_columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
            }

            for col, col_type in [
                ("dismissal_reason", "TEXT"),
                ("match_tier", "TEXT"),
                ("salary", "TEXT"),
                ("salary_min", "INTEGER"),
                ("salary_max", "INTEGER"),
                ("salary_currency", "TEXT"),
                ("is_sparse", "INTEGER DEFAULT 0"),
                ("location_metadata", "TEXT"),
                ("company_metadata", "TEXT"),
                ("application_status", "TEXT"),
                ("applied_at", "TEXT"),
                ("notes", "TEXT"),
                ("next_step", "TEXT"),
                ("next_step_date", "TEXT"),
                ("source", "TEXT DEFAULT 'pipeline'"),
            ]:
                if col in existing_columns:
                    continue
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
                logger.debug("Migrated DB: Added '%s' column", col)

            # Migrate legacy status='applied' rows to the tracker-specific application_status field.
            conn.execute(
                """UPDATE jobs
                   SET application_status = 'applied'
                   WHERE status = 'applied' AND application_status IS NULL"""
            )
            conn.execute(
                """UPDATE jobs
                   SET applied_at = COALESCE(last_seen_at, first_seen_at)
                   WHERE status = 'applied' AND applied_at IS NULL"""
            )
            conn.execute("UPDATE jobs SET source = 'pipeline' WHERE source IS NULL")
            conn.execute(
                """INSERT INTO application_events (job_id, status, note, created_at)
                   SELECT jobs.id,
                          'applied',
                          'Migrated from existing application status',
                          COALESCE(jobs.applied_at, jobs.first_seen_at)
                   FROM jobs
                   WHERE jobs.application_status = 'applied'
                     AND NOT EXISTS (
                         SELECT 1 FROM application_events ev WHERE ev.job_id = jobs.id
                     )"""
            )
            conn.execute(
                """UPDATE jobs
                   SET status = CASE
                       WHEN scored_at IS NOT NULL THEN 'scored'
                       ELSE 'new'
                   END
                   WHERE status = 'applied'"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_application_status ON jobs(application_status)")

            logger.debug("Database initialized at %s", self.db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context-managed database connection."""
        conn = sqlite3.connect(self.db_path, timeout=self._busy_timeout_ms / 1000)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Upsert ──────────────────────────────────────────────────────

    @staticmethod
    def _job_insert_row(job: RawJob, now: str) -> tuple:
        company_metadata = Store._serialize_metadata(job.company_metadata) if job.company_metadata else None
        location_metadata = Store._serialize_metadata(job.location_metadata) if job.location_metadata else None
        return (
            job.ats_platform,
            job.company_slug,
            job.job_id,
            job.company_name,
            company_metadata,
            job.title,
            job.location,
            location_metadata,
            job.url,
            job.description,
            job.posted_at,
            now,
            now,
            job.status,
            job.dismissal_reason,
            job.match_tier,
            job.salary,
            job.salary_min,
            job.salary_max,
            job.salary_currency,
        )

    def upsert_jobs(
        self,
        jobs: list[RawJob],
        progress_callback: UpsertProgressCallback | None = None,
    ) -> int:
        """Insert jobs, ignore duplicates, and return the count of newly inserted rows."""
        if not jobs:
            return 0
            
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            db_has_rows = conn.execute("SELECT 1 FROM jobs LIMIT 1").fetchone() is not None
            new_jobs_count = 0
            to_backfill_descriptions = [
                (job.description, job.ats_platform, job.company_slug, job.job_id)
                for job in jobs
                if job.description and len(job.description) > 500
            ]

            if db_has_rows:
                total_jobs = len(jobs)
                for start in range(0, total_jobs, UPSERT_WRITE_CHUNK_SIZE):
                    batch = jobs[start:start + UPSERT_WRITE_CHUNK_SIZE]
                    conn.executemany(
                        "UPDATE jobs SET last_seen_at = ? WHERE ats_platform = ? AND company_slug = ? AND job_id = ?",
                        [
                            (now, job.ats_platform, job.company_slug, job.job_id)
                            for job in batch
                        ],
                    )
                    if progress_callback:
                        progress_callback("Refreshing existing jobs", min(start + len(batch), total_jobs), total_jobs)

            total_jobs = len(jobs)
            for start in range(0, total_jobs, UPSERT_WRITE_CHUNK_SIZE):
                batch = jobs[start:start + UPSERT_WRITE_CHUNK_SIZE]
                before_changes = conn.total_changes
                conn.executemany(
                    "INSERT OR IGNORE INTO jobs (ats_platform, company_slug, job_id, company_name, company_metadata, title, location, location_metadata, url, description, posted_at, first_seen_at, last_seen_at, status, dismissal_reason, match_tier, salary, salary_min, salary_max, salary_currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [self._job_insert_row(job, now) for job in batch],
                )
                new_jobs_count += conn.total_changes - before_changes
                if progress_callback:
                    progress_callback("Inserting new jobs", min(start + len(batch), total_jobs), total_jobs)

            if db_has_rows and to_backfill_descriptions:
                total_backfills = len(to_backfill_descriptions)
                for start in range(0, total_backfills, UPSERT_WRITE_CHUNK_SIZE):
                    batch = to_backfill_descriptions[start:start + UPSERT_WRITE_CHUNK_SIZE]
                    conn.executemany(
                        "UPDATE jobs SET description = ? WHERE ats_platform = ? AND company_slug = ? AND job_id = ? AND (description IS NULL OR length(description) < 500)",
                        batch,
                    )
                    if progress_callback:
                        progress_callback("Backfilling descriptions", min(start + len(batch), total_backfills), total_backfills)

        logger.info("Upserted %d jobs, %d new", len(jobs), new_jobs_count)
        return new_jobs_count

    # ── Scoring ─────────────────────────────────────────────────────

    def update_score(
        self,
        db_id: int,
        fit_score: int,
        reasoning: str,
        breakdown: dict[str, int],
        key_matches: list[str] | None = None,
        red_flags: list[str] | None = None,
        fit_category: str = "",
        apply_priority: str = "skip",
        skip_reason: str = "none",
        missing_skills: list[str] | None = None,
        normalization_audit: dict[str, object] | None = None,
        salary: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        salary_currency: str | None = None,
        is_sparse: bool = False,
    ) -> None:
        """Store LLM scoring results for a job."""
        now = datetime.utcnow().isoformat()
        is_sparse_int = 1 if is_sparse else 0
        breakdown_json = json.dumps({
            "dimensions": breakdown,
            "key_matches": key_matches or [],
            "red_flags": red_flags or [],
            "fit_category": fit_category or "",
            "apply_priority": apply_priority,
            "skip_reason": skip_reason or "none",
            "missing_skills": missing_skills or [],
            "normalization_audit": normalization_audit or {},
        })

        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs
                   SET fit_score = ?, score_reasoning = ?, score_breakdown = ?,
                       scored_at = ?, status = 'scored',
                       salary = ?,
                       salary_min = ?,
                       salary_max = ?,
                       salary_currency = ?,
                       is_sparse = ?
                   WHERE id = ?""",
                (fit_score, reasoning, breakdown_json, now, salary, salary_min, salary_max, salary_currency, is_sparse_int, db_id),
            )
        logger.debug("Scored job %d: %d%%", db_id, fit_score)

    @staticmethod
    def _parse_score_breakdown_payload(
        breakdown_raw: str | None,
    ) -> tuple[dict[str, int], str, str, dict[str, object]]:
        """Extract dimensions and metadata from stored score_breakdown JSON."""
        breakdown: dict[str, int] = {}
        apply_priority = "skip"
        skip_reason = "none"
        payload: dict[str, object] = {}

        if not breakdown_raw:
            return breakdown, apply_priority, skip_reason, payload

        try:
            data = json.loads(breakdown_raw)
            if isinstance(data, dict):
                payload = data
                raw_breakdown = data.get("dimensions", {})
                if isinstance(raw_breakdown, dict):
                    breakdown = raw_breakdown
                apply_priority = str(data.get("apply_priority", "skip") or "skip")
                skip_reason = str(data.get("skip_reason", "none") or "none")
        except (json.JSONDecodeError, Exception):
            pass

        return breakdown, apply_priority, skip_reason, payload

    # ── Queries ─────────────────────────────────────────────────────

    def get_unscored(self) -> list[CandidateJob]:
        """Get all jobs that haven't been scored yet (status='new')."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'new' ORDER BY first_seen_at DESC"
            ).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    def get_all_new_jobs(self) -> list[CandidateJob]:
        """Get all jobs with status 'new' for pre-filtering."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'new' ORDER BY first_seen_at DESC"
            ).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    def get_recent_scored(
        self, days: int = 7, min_score: int = 50
    ) -> list[ScoredJob]:
        """Get scored jobs from last N days with score >= min_score."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM jobs
                   WHERE scored_at IS NOT NULL
                     AND scored_at >= ?
                     AND fit_score >= ?
                   ORDER BY fit_score DESC""",
                (cutoff, min_score),
            ).fetchall()
        return [self._row_to_scored(r) for r in rows]

    def get_job_by_id(self, db_id: int) -> ScoredJob | None:
        """Get a single job by its database row id."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (db_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_scored(row)

    # ── Status Management ───────────────────────────────────────────

    def update_status(self, db_id: int, status: str, reason: str | None = None) -> bool:
        """Update job status and optional dismissal reason. Returns True if found."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, dismissal_reason = ? WHERE id = ?", 
                (status, reason, db_id)
            )
        if cursor.rowcount > 0:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.debug("Job %d status → %s", db_id, status)
            return True
        logger.warning("Job %d not found", db_id)
        return False

    def update_application_status(
        self,
        db_id: int,
        application_status: str,
        note: str | None = None,
    ) -> bool:
        """Update tracker status and append a timeline event."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT application_status, applied_at FROM jobs WHERE id = ?",
                (db_id,),
            ).fetchone()
            if row is None:
                logger.warning("Job %d not found for application status update", db_id)
                return False

            current_status = row["application_status"]
            if current_status == application_status:
                return True

            if current_status is None and application_status == "applied" and not row["applied_at"]:
                conn.execute(
                    """UPDATE jobs
                       SET application_status = ?, applied_at = ?
                       WHERE id = ?""",
                    (application_status, now, db_id),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET application_status = ? WHERE id = ?",
                    (application_status, db_id),
                )

            conn.execute(
                """INSERT INTO application_events (job_id, status, note, created_at)
                   VALUES (?, ?, ?, ?)""",
                (db_id, application_status, note, now),
            )

        self.set_metadata("last_job_status_change_at", now)
        logger.debug("Job %d application_status → %s", db_id, application_status)
        return True

    def update_applied_at(self, db_id: int, applied_at: str | None) -> bool:
        """Update the applied date without mutating tracker history."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET applied_at = ? WHERE id = ?",
                (applied_at, db_id),
            )
        if cursor.rowcount > 0:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.debug("Job %d applied_at updated", db_id)
            return True
        logger.warning("Job %d not found for applied_at update", db_id)
        return False

    def remove_from_tracker(self, db_id: int) -> bool:
        """Clear tracker-only state while preserving application history."""
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE jobs
                   SET application_status = NULL,
                       next_step = NULL,
                       next_step_date = NULL
                   WHERE id = ?""",
                (db_id,),
            )
        if cursor.rowcount > 0:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.debug("Job %d removed from tracker", db_id)
            return True
        logger.warning("Job %d not found for tracker removal", db_id)
        return False

    def update_notes(self, db_id: int, notes: str) -> bool:
        """Update free-form tracker notes."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET notes = ? WHERE id = ?",
                (notes, db_id),
            )
        if cursor.rowcount > 0:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.debug("Job %d notes updated", db_id)
            return True
        logger.warning("Job %d not found for notes update", db_id)
        return False

    def update_next_step(
        self,
        db_id: int,
        next_step: str | None,
        next_step_date: str | None,
    ) -> bool:
        """Update next-step tracker metadata."""
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE jobs
                   SET next_step = ?, next_step_date = ?
                   WHERE id = ?""",
                (next_step, next_step_date, db_id),
            )
        if cursor.rowcount > 0:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.debug("Job %d next-step updated", db_id)
            return True
        logger.warning("Job %d not found for next-step update", db_id)
        return False

    def update_job_description(self, db_id: int, description: str) -> bool:
        """Update job description. Returns True if found."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET description = ? WHERE id = ?", (description, db_id)
            )
        if cursor.rowcount > 0:
            logger.debug("Job %d description updated", db_id)
            return True
        logger.warning("Job %d not found for description update", db_id)
        return False

    def bulk_update_status(self, db_ids: list[int], status: str, reason: str | None = None) -> int:
        """Update multiple job statuses and optional reason in a single transaction."""
        if not db_ids:
            return 0
        with self._connect() as conn:
            # Chunking to avoid SQLite parameter limit (999)
            total_updated = 0
            for i in range(0, len(db_ids), 900):
                chunk = db_ids[i:i+900]
                placeholders = ",".join("?" * len(chunk))
                cursor = conn.execute(
                    f"UPDATE jobs SET status = ?, dismissal_reason = ? WHERE id IN ({placeholders})",
                    [status, reason] + chunk
                )
                total_updated += cursor.rowcount
        if total_updated:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.info("Bulk updated %d jobs status → %s", total_updated, status)
        return total_updated

    def bulk_update_status_with_reasons(self, updates: list[tuple[int, str]]) -> int:
        """Update multiple jobs each with their own dismissal reason."""
        if not updates:
            return 0
        with self._connect() as conn:
            cursor = conn.executemany(
                "UPDATE jobs SET status = 'dismissed', dismissal_reason = ? WHERE id = ?",
                [(reason, db_id) for db_id, reason in updates]
            )
            count = cursor.rowcount
        if count:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.info("Bulk updated %d dismissal reasons", count)
        return count

    def mark_stale(self, stale_days: int = 7) -> int:
        """Mark jobs absent for stale_days+ as 'closed'. Returns count."""
        cutoff = (datetime.utcnow() - timedelta(days=stale_days)).isoformat()

        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE jobs
                   SET status = 'closed'
                   WHERE last_seen_at IS NOT NULL
                     AND last_seen_at < ?
                     AND status NOT IN ('dismissed', 'closed')
                     AND application_status IS NULL""",
                (cutoff,),
            )
        count = cursor.rowcount
        if count:
            logger.info("Marked %d stale jobs as closed", count)
        return count

    def get_stale(self, days: int = 30) -> list[ScoredJob]:
        """Get recently closed (stale) jobs."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM jobs
                   WHERE status = 'closed'
                     AND last_seen_at >= ?
                   ORDER BY last_seen_at DESC""",
                (cutoff,),
            ).fetchall()
        return [self._row_to_scored(r) for r in rows]

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get database statistics for the dashboard."""
        today = datetime.utcnow().date().isoformat()
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        last_run = self.get_metadata("last_pipeline_run_at")

        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            new_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= ? AND status != 'dismissed'", (today,)
            ).fetchone()[0]
            total_new_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= ?", (today,)
            ).fetchone()[0]
            new_this_week = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= ? AND status != 'dismissed'", (week_ago,)
            ).fetchone()[0]
            high_priority_today_rows = conn.execute(
                "SELECT fit_score, score_breakdown FROM jobs WHERE first_seen_at >= ? AND score_breakdown IS NOT NULL",
                (today,),
            ).fetchall()
            scored = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE scored_at IS NOT NULL"
            ).fetchone()[0]
            applied = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE application_status IS NOT NULL"
            ).fetchone()[0]
            dismissed = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'dismissed'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'new'"
            ).fetchone()[0]
            closed = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'closed'"
            ).fetchone()[0]

            # Score distribution
            distribution: dict[str, int] = {}
            for label, low, high in [
                ("90-100", 90, 100),
                ("80-89", 80, 89),
                ("70-79", 70, 79),
                ("60-69", 60, 69),
                ("50-59", 50, 59),
                ("below-50", 0, 49),
            ]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM jobs WHERE fit_score BETWEEN ? AND ?",
                    (low, high),
                ).fetchone()[0]
                distribution[label] = count

            # Apply priority counts using normalized persisted score data
            priority_counts = {"high": 0, "medium": 0, "low": 0, "skip": 0}
            rows = conn.execute(
                "SELECT fit_score, score_breakdown FROM jobs WHERE score_breakdown IS NOT NULL"
            ).fetchall()
            for row in rows:
                breakdown, apply_priority, skip_reason, _ = self._parse_score_breakdown_payload(row["score_breakdown"])
                priority, _ = normalize_persisted_priority(
                    row["fit_score"],
                    breakdown,
                    apply_priority,
                    skip_reason,
                )
                if priority in priority_counts:
                    priority_counts[priority] += 1

            high_priority_today = 0
            for row in high_priority_today_rows:
                breakdown, apply_priority, skip_reason, _ = self._parse_score_breakdown_payload(row["score_breakdown"])
                priority, _ = normalize_persisted_priority(
                    row["fit_score"],
                    breakdown,
                    apply_priority,
                    skip_reason,
                )
                if priority == "high":
                    high_priority_today += 1

        return {
            "total_jobs": total,
            "new_today": new_today,
            "total_new_today": total_new_today,
            "high_priority_today": high_priority_today,
            "new_this_week": new_this_week,
            "last_pipeline_run_at": last_run,
            "scored": scored,
            "pending": pending,
            "applied": applied,
            "dismissed": dismissed,
            "closed": closed,
            "score_distribution": distribution,
            "apply_priority_counts": priority_counts,
        }

    def get_dismissal_stats(self) -> dict:
        """Get breakdown of dismissal reasons for the audit report."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT dismissal_reason, COUNT(*) as count FROM jobs WHERE status = 'dismissed' GROUP BY dismissal_reason ORDER BY count DESC"
            ).fetchall()
            
            reasons = {row[0] or "Unknown": row[1] for row in rows}
            total = sum(reasons.values())
            
        return {"reasons": reasons, "total": total}

    def get_jobs_filtered(
        self,
        status: list[str] | None = None,
        tracked_mode: Literal["all", "only", "exclude"] = "all",
        min_score: int | None = None,
        max_score: int | None = None,
        priority: str | None = None,
        company: str | None = None,
        search: str | None = None,
        sort: str = "score",
        order: str = "desc",
        page: int = 1,
        per_page: int = 50,
        days: int | None = None,
        is_sparse: bool | None = None,
        today_only: bool | None = None,
    ) -> tuple[list[dict], int]:
        """Filtered, paginated job list for the web API.
        
        Returns (rows_as_dicts, total_count). Excludes description for performance.
        """
        columns = (
            "id, ats_platform, company_slug, company_name, job_id, title, "
            "location, company_metadata, url, posted_at, first_seen_at, last_seen_at, "
            "fit_score, score_reasoning, score_breakdown, scored_at, status, application_status, "
            "applied_at, notes, next_step, next_step_date, source, dismissal_reason, match_tier, "
            "salary, salary_min, salary_max, salary_currency, is_sparse"
        )
        
        where_clauses: list[str] = []
        params: list = []
        
        if status:
            placeholders = ",".join("?" * len(status))
            where_clauses.append(f"status IN ({placeholders})")
            params.extend(status)

        if tracked_mode == "only":
            where_clauses.append("application_status IS NOT NULL")
        elif tracked_mode == "exclude":
            where_clauses.append("application_status IS NULL")
        
        if min_score is not None:
            where_clauses.append("fit_score >= ?")
            params.append(min_score)
        
        if max_score is not None:
            where_clauses.append("fit_score <= ?")
            params.append(max_score)
        
        if company:
            where_clauses.append("LOWER(company_name) LIKE ?")
            params.append(f"%{company.lower()}%")
        
        if search:
            where_clauses.append("(LOWER(title) LIKE ? OR LOWER(company_name) LIKE ? OR LOWER(description) LIKE ?)")
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%", f"%{search.lower()}%"])
        
        if days:
            where_clauses.append("first_seen_at >= datetime('now', ?)")
            params.append(f"-{days} days")
        
        if is_sparse is not None:
            where_clauses.append("is_sparse = ?")
            params.append(1 if is_sparse else 0)
        
        if today_only is True:
            # Calendar today: first_seen_at matches the current UTC date
            where_clauses.append("date(first_seen_at) = date('now')")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Sort validation
        sort_map = {
            "score": "fit_score",
            "date": "first_seen_at",
            "company": "company_name",
            "salary": "salary_min"
        }
        sort_col = sort_map.get(sort, "fit_score")
        order_sql = "ASC" if order.lower() == "asc" else "DESC"
        
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {columns} FROM jobs WHERE {where_sql} "
                f"ORDER BY {sort_col} {order_sql} NULLS LAST",
                params,
            ).fetchall()

            result = [dict(row) for row in rows]

        if priority:
            filtered: list[dict] = []
            for row in result:
                breakdown, apply_priority, skip_reason, _ = self._parse_score_breakdown_payload(row.get("score_breakdown"))
                normalized_priority, _ = normalize_persisted_priority(
                    row.get("fit_score", 0),
                    breakdown,
                    apply_priority,
                    skip_reason,
                )
                if normalized_priority == priority:
                    filtered.append(row)
            result = filtered

        total = len(result)
        offset = (page - 1) * per_page
        return result[offset:offset + per_page], total

    def get_applications_filtered(
        self,
        application_statuses: list[str] | None = None,
        search: str | None = None,
        sort: str = "next_step_date",
        order: str = "asc",
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[dict], int]:
        """Filtered, paginated tracker list."""
        columns = (
            "id, ats_platform, company_slug, company_name, job_id, title, "
            "location, company_metadata, url, posted_at, first_seen_at, last_seen_at, "
            "fit_score, score_reasoning, score_breakdown, scored_at, status, application_status, "
            "applied_at, notes, next_step, next_step_date, source, dismissal_reason, match_tier, "
            "salary, salary_min, salary_max, salary_currency, is_sparse"
        )

        where_clauses = ["application_status IS NOT NULL"]
        params: list[object] = []

        if application_statuses:
            placeholders = ",".join("?" * len(application_statuses))
            where_clauses.append(f"application_status IN ({placeholders})")
            params.extend(application_statuses)

        if search:
            where_clauses.append(
                "(LOWER(title) LIKE ? OR LOWER(company_name) LIKE ? OR LOWER(COALESCE(notes, '')) LIKE ?)"
            )
            search_value = f"%{search.lower()}%"
            params.extend([search_value, search_value, search_value])

        sort_map = {
            "applied_date": "applied_at",
            "company": "company_name",
            "status": "application_status",
            "next_step_date": "next_step_date",
        }
        sort_col = sort_map.get(sort, "next_step_date")
        order_sql = "DESC" if order.lower() == "desc" else "ASC"
        where_sql = " AND ".join(where_clauses)

        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT {columns}
                    FROM jobs
                    WHERE {where_sql}
                    ORDER BY {sort_col} {order_sql} NULLS LAST, applied_at DESC NULLS LAST""",
                params,
            ).fetchall()
            result = [dict(row) for row in rows]

        total = len(result)
        offset = (page - 1) * per_page
        return result[offset:offset + per_page], total

    def get_application_timeline(self, db_id: int) -> list[dict]:
        """Return tracker timeline events for a job."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, job_id, status, note, created_at
                   FROM application_events
                   WHERE job_id = ?
                   ORDER BY created_at ASC, id ASC""",
                (db_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_application_stats(self) -> dict:
        """Aggregate tracker stats for the applications page."""
        with self._connect() as conn:
            app_rows = conn.execute(
                """SELECT id, company_name, fit_score, source, application_status, applied_at
                   FROM jobs
                   WHERE application_status IS NOT NULL"""
            ).fetchall()
            event_rows = conn.execute(
                """SELECT job_id, status, created_at
                   FROM application_events
                   ORDER BY created_at ASC, id ASC"""
            ).fetchall()

        status_counts = {
            "applied": 0,
            "screening": 0,
            "interviewing": 0,
            "offer": 0,
            "accepted": 0,
            "rejected_by_company": 0,
            "rejected_by_user": 0,
            "ghosted": 0,
        }
        source_breakdown = {"pipeline": 0, "manual": 0}
        top_companies: dict[str, dict[str, object]] = {}
        active_count = 0
        offers_count = 0

        events_by_job: dict[int, list[sqlite3.Row]] = {}
        for event in event_rows:
            events_by_job.setdefault(event["job_id"], []).append(event)

        response_deltas: list[float] = []
        weekly_velocity: dict[str, int] = {}
        outcome_breakdown = {
            "offer": 0,
            "accepted": 0,
            "rejected_by_company": 0,
            "rejected_by_user": 0,
            "ghosted": 0,
        }
        funnel = {
            "applied": 0,
            "screening": 0,
            "interviewing": 0,
            "offer": 0,
            "accepted": 0,
        }

        for row in app_rows:
            app_status = row["application_status"]
            if app_status in status_counts:
                status_counts[app_status] += 1
            if app_status in {"applied", "screening", "interviewing"}:
                active_count += 1
            if app_status in {"offer", "accepted"}:
                offers_count += 1
            if app_status in outcome_breakdown:
                outcome_breakdown[app_status] += 1

            source = row["source"] or "pipeline"
            source_breakdown[source] = source_breakdown.get(source, 0) + 1

            company_name = row["company_name"] or "Unknown"
            company_stats = top_companies.setdefault(
                company_name,
                {"company_name": company_name, "applications": 0, "furthest_stage": "applied", "avg_score_sum": 0, "avg_score_count": 0},
            )
            company_stats["applications"] = int(company_stats["applications"]) + 1
            if row["fit_score"] is not None:
                company_stats["avg_score_sum"] = int(company_stats["avg_score_sum"]) + int(row["fit_score"])
                company_stats["avg_score_count"] = int(company_stats["avg_score_count"]) + 1

            stage_order = {
                "applied": 1,
                "screening": 2,
                "interviewing": 3,
                "offer": 4,
                "accepted": 5,
                "rejected_by_company": 3,
                "rejected_by_user": 3,
                "ghosted": 2,
            }
            current_best = str(company_stats["furthest_stage"])
            if stage_order.get(app_status, 0) > stage_order.get(current_best, 0):
                company_stats["furthest_stage"] = app_status

            applied_at_raw = row["applied_at"]
            if applied_at_raw:
                try:
                    applied_at = datetime.fromisoformat(str(applied_at_raw))
                except ValueError:
                    applied_at = None
                if applied_at is not None:
                    week_bucket = f"{applied_at.isocalendar().year}-W{applied_at.isocalendar().week:02d}"
                    weekly_velocity[week_bucket] = weekly_velocity.get(week_bucket, 0) + 1

                    events = events_by_job.get(row["id"], [])
                    for event in events:
                        if event["status"] != "applied":
                            try:
                                event_time = datetime.fromisoformat(str(event["created_at"]))
                            except ValueError:
                                continue
                            response_deltas.append((event_time - applied_at).total_seconds() / 86400)
                            break

            events = events_by_job.get(row["id"], [])
            seen_statuses = {event["status"] for event in events}
            for key in funnel:
                if key in seen_statuses or app_status == key:
                    funnel[key] += 1

        response_numerator = sum(
            status_counts[key]
            for key in ("screening", "interviewing", "offer", "accepted", "rejected_by_company")
        )
        total = len(app_rows)
        response_rate = round((response_numerator / total) * 100, 1) if total else 0.0
        avg_time = round(sum(response_deltas) / len(response_deltas), 1) if response_deltas else None

        top_company_rows: list[dict[str, object]] = []
        for data in top_companies.values():
            avg_score = None
            if int(data["avg_score_count"]) > 0:
                avg_score = round(int(data["avg_score_sum"]) / int(data["avg_score_count"]), 1)
            top_company_rows.append(
                {
                    "company_name": data["company_name"],
                    "applications": data["applications"],
                    "furthest_stage": data["furthest_stage"],
                    "avg_score": avg_score,
                }
            )
        top_company_rows.sort(key=lambda item: (-int(item["applications"]), str(item["company_name"])))

        return {
            "total": total,
            "active_count": active_count,
            "offers_count": offers_count,
            "response_rate": response_rate,
            "avg_time_to_response_days": avg_time,
            "status_counts": status_counts,
            "weekly_velocity": [
                {"week": week, "applications": weekly_velocity[week]}
                for week in sorted(weekly_velocity.keys())
            ],
            "funnel": funnel,
            "outcome_breakdown": outcome_breakdown,
            "source_breakdown": source_breakdown,
            "top_companies": top_company_rows[:10],
        }

    def get_job_by_identity(
        self,
        ats_platform: str,
        company_slug: str,
        external_job_id: str,
    ) -> dict | None:
        """Look up an existing job by its source identity."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM jobs
                   WHERE ats_platform = ? AND company_slug = ? AND job_id = ?""",
                (ats_platform, company_slug, external_job_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def import_job(
        self,
        *,
        ats_platform: str,
        company_slug: str,
        external_job_id: str | None,
        company_name: str,
        title: str,
        location: str | None,
        url: str,
        description: str | None,
        applied_at: str | None = None,
        notes: str | None = None,
        company_metadata: dict[str, object] | None = None,
        location_metadata: dict[str, object] | None = None,
        salary: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        salary_currency: str | None = None,
        source: str = "manual",
        initial_event_note: str | None = None,
    ) -> tuple[dict, bool]:
        """Create a tracked application or return an existing duplicate."""
        normalized_job_id = external_job_id or uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        normalized_applied_at = applied_at or now
        serialized_company_metadata = (
            Store._serialize_metadata(company_metadata) if company_metadata else None
        )
        serialized_location_metadata = (
            Store._serialize_metadata(location_metadata) if location_metadata else None
        )
        with self._connect() as conn:
            existing = conn.execute(
                """SELECT * FROM jobs
                   WHERE ats_platform = ? AND company_slug = ? AND job_id = ?""",
                (ats_platform, company_slug, normalized_job_id),
            ).fetchone()
            if existing is not None:
                return dict(existing), True

            cursor = conn.execute(
                """INSERT INTO jobs (
                       ats_platform, company_slug, job_id, company_name, company_metadata,
                       title, location, location_metadata, url, description, posted_at,
                       first_seen_at, last_seen_at, status, application_status, applied_at,
                       notes, source, salary, salary_min, salary_max, salary_currency
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ats_platform,
                    company_slug,
                    normalized_job_id,
                    company_name,
                    serialized_company_metadata,
                    title,
                    location,
                    serialized_location_metadata,
                    url,
                    description,
                    None,
                    now,
                    now,
                    "new",
                    "applied",
                    normalized_applied_at,
                    notes,
                    source,
                    salary,
                    salary_min,
                    salary_max,
                    salary_currency,
                ),
            )
            new_id = int(cursor.lastrowid)
            conn.execute(
                """INSERT INTO application_events (job_id, status, note, created_at)
                   VALUES (?, 'applied', ?, ?)""",
                (new_id, initial_event_note, normalized_applied_at),
            )
            created = conn.execute("SELECT * FROM jobs WHERE id = ?", (new_id,)).fetchone()

        self.set_metadata("last_job_status_change_at", now)
        return dict(created), False

    def get_job_detail(self, db_id: int) -> dict | None:
        """Get a single job by ID, including description."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (db_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_job(self, db_id: int) -> bool:
        """Hard-delete a job row and any dependent tracker events."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (db_id,))
        if cursor.rowcount > 0:
            self.set_metadata("last_job_status_change_at", datetime.utcnow().isoformat())
            logger.debug("Job %d deleted", db_id)
            return True
        logger.warning("Job %d not found for deletion", db_id)
        return False

    def get_trends(self, days: int = 30) -> dict:
        """Get trend data for charts: daily counts, skills, company stats, score trends."""
        with self._connect() as conn:
            # Daily discovery + funnel entry + scored count
            daily_rows = conn.execute("""
                WITH new_counts AS (
                    SELECT
                        date(first_seen_at) as day,
                        COUNT(*) as new_jobs
                    FROM jobs
                    WHERE date(first_seen_at) >= date('now', ?)
                    GROUP BY date(first_seen_at)
                ),
                funnel_counts AS (
                    SELECT
                        date(first_seen_at) as day,
                        COUNT(*) as in_funnel
                    FROM jobs
                    WHERE date(first_seen_at) >= date('now', ?)
                      AND (
                          match_tier IS NOT NULL
                          OR scored_at IS NOT NULL
                          OR status = 'scored'
                          OR application_status IS NOT NULL
                      )
                    GROUP BY date(first_seen_at)
                ),
                scored_counts AS (
                    SELECT
                        date(scored_at) as day,
                        COUNT(*) as scored
                    FROM jobs
                    WHERE scored_at IS NOT NULL
                      AND date(scored_at) >= date('now', ?)
                    GROUP BY date(scored_at)
                ),
                all_days AS (
                    SELECT day FROM new_counts
                    UNION
                    SELECT day FROM funnel_counts
                    UNION
                    SELECT day FROM scored_counts
                )
                SELECT
                    all_days.day as day,
                    COALESCE(new_counts.new_jobs, 0) as new_jobs,
                    COALESCE(funnel_counts.in_funnel, 0) as in_funnel,
                    COALESCE(scored_counts.scored, 0) as scored
                FROM all_days
                LEFT JOIN new_counts ON new_counts.day = all_days.day
                LEFT JOIN funnel_counts ON funnel_counts.day = all_days.day
                LEFT JOIN scored_counts ON scored_counts.day = all_days.day
                ORDER BY all_days.day ASC
            """, (f"-{days} days", f"-{days} days", f"-{days} days")).fetchall()

            # Skill frequency from key_matches in score_breakdown
            breakdown_rows = conn.execute(
                "SELECT score_breakdown FROM jobs WHERE score_breakdown IS NOT NULL AND fit_score IS NOT NULL"
            ).fetchall()

            funnel_rows = conn.execute("""
                SELECT
                    status,
                    application_status,
                    fit_score,
                    score_breakdown,
                    match_tier
                FROM jobs
                WHERE date(first_seen_at) >= date('now', ?)
            """, (f"-{days} days",)).fetchall()

            # Company stats
            company_rows = conn.execute("""
                SELECT
                    company_name,
                    COUNT(*) as job_count,
                    AVG(CASE WHEN fit_score IS NOT NULL THEN fit_score END) as avg_score,
                    MAX(date(COALESCE(last_seen_at, first_seen_at))) as last_seen
                FROM jobs
                WHERE (status IN ('new', 'scored') OR application_status IS NOT NULL)
                  AND date(COALESCE(last_seen_at, first_seen_at)) >= date('now', ?)
                GROUP BY company_name
                ORDER BY job_count DESC
                LIMIT 30
            """, (f"-{days} days",)).fetchall()

            # Score trend over time
            score_trend_rows = conn.execute("""
                SELECT date(scored_at) as day, AVG(fit_score) as avg_score
                FROM jobs
                WHERE scored_at IS NOT NULL AND fit_score IS NOT NULL
                  AND date(scored_at) >= date('now', ?)
                GROUP BY date(scored_at)
                ORDER BY day ASC
            """, (f"-{days} days",)).fetchall()

        # Process skills
        from collections import Counter
        skill_counter = Counter()
        for row in breakdown_rows:
            try:
                data = json.loads(row[0])
                for skill in data.get("key_matches", []):
                    skill_counter[skill.strip()] += 1
            except (json.JSONDecodeError, Exception):
                pass

        funnel_counts = {
            "collected": len(funnel_rows),
            "passed_prefilter": 0,
            "high_priority": 0,
            "applied": 0,
        }
        for row in funnel_rows:
            if row["match_tier"]:
                funnel_counts["passed_prefilter"] += 1
            if row["application_status"] is not None:
                funnel_counts["applied"] += 1
            if row["score_breakdown"]:
                breakdown, apply_priority, skip_reason, _ = self._parse_score_breakdown_payload(row["score_breakdown"])
                normalized_priority, _ = normalize_persisted_priority(
                    row["fit_score"],
                    breakdown,
                    apply_priority,
                    skip_reason,
                )
                if normalized_priority == "high":
                    funnel_counts["high_priority"] += 1

        return {
            "daily_counts": [
                {
                    "date": r["day"],
                    "new_jobs": r["new_jobs"],
                    "in_funnel": r["in_funnel"],
                    "scored": r["scored"],
                }
                for r in daily_rows
            ],
            "pipeline_funnel": funnel_counts,
            "top_skills": [
                {"skill": s, "count": c} for s, c in skill_counter.most_common(20)
            ],
            "company_stats": [
                {
                    "company_name": r["company_name"] or "Unknown",
                    "job_count": r["job_count"],
                    "avg_score": round(r["avg_score"], 1) if r["avg_score"] else None,
                    "last_seen": r["last_seen"],
                }
                for r in company_rows
            ],
            "score_trend": [
                {"date": r["day"], "avg_score": round(r["avg_score"], 1)}
                for r in score_trend_rows
            ],
        }

    def get_market_intelligence(self, days: int = 30) -> dict:
        """Aggregate skip reasons, country distribution, and missing skills from scored jobs."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT score_breakdown, location, salary, salary_min, salary_max, salary_currency FROM jobs
                   WHERE scored_at IS NOT NULL
                     AND date(scored_at) >= date('now', ?)""",
                (f"-{days} days",)
            ).fetchall()

        from collections import Counter
        skip_counter: Counter = Counter()
        missing_counter: Counter = Counter()
        country_counter: Counter = Counter()
        priority_counter: Counter = Counter()
        salary_counter: Counter = Counter()
        total = 0

        for row in rows:
            total += 1
            country = Store._parse_country(row["location"] or "")
            if country:
                country_counter[country] += 1

            representative_salary = _representative_annual_salary(
                row["salary"],
                row["salary_min"],
                row["salary_max"],
            )
            _, _, parsed_currency = parse_salary_string(row["salary"])
            normalized_currency = row["salary_currency"] or parsed_currency or "Unknown"
            if representative_salary is None or representative_salary <= 0:
                bucket = "Undisclosed"
                bucket_currency = None
            elif representative_salary < 60000:
                bucket = "< 60k"
                bucket_currency = normalized_currency
            elif representative_salary >= 200000:
                bucket = "200k+"
                bucket_currency = normalized_currency
            else:
                # 10k buckets from 60k to 200k
                base = (representative_salary // 10000) * 10
                bucket = f"{base}k-{base+10}k"
                bucket_currency = normalized_currency
            
            salary_counter[(bucket_currency, bucket)] += 1

            bd = row["score_breakdown"]
            if not bd:
                skip_counter["none"] += 1
                continue
            try:
                breakdown, apply_priority, skip_reason, data = self._parse_score_breakdown_payload(bd)
                normalized_priority, normalized_skip_reason = normalize_persisted_priority(
                    row["fit_score"] if "fit_score" in row.keys() else 0,
                    breakdown,
                    apply_priority,
                    skip_reason,
                )
                skip_counter[normalized_skip_reason] += 1
                priority_counter[normalized_priority] += 1
                for skill in data.get("missing_skills", []):
                    if skill and isinstance(skill, str):
                        missing_counter[skill.strip()] += 1
            except (json.JSONDecodeError, Exception):
                skip_counter["none"] += 1

        return {
            "skip_reason_distribution": dict(skip_counter),
            "country_distribution": [
                {"country": c, "count": n}
                for c, n in country_counter.most_common(10)
            ],
            "missing_skills": [
                {"skill": s, "count": n}
                for s, n in missing_counter.most_common(10)
            ],
            "total_scored": total,
            "apply_priority_counts": dict(priority_counter),
            "salary_distribution": [
                {"currency": currency, "range": salary_range, "count": count}
                for (currency, salary_range), count in sorted(
                    salary_counter.items(),
                    key=lambda item: _salary_bucket_sort_key(item[0][0], item[0][1]),
                )
            ],
        }

    # ── Rescore support ─────────────────────────────────────────────

    def get_jobs_for_rescore(self) -> list[CandidateJob]:
        """Get jobs eligible for bulk rescore.

        This includes:
        - previously scored jobs, regardless of current status
        - persisted `new` jobs that were collected during an earlier run but never scored

        The second case covers workflows like a fresh database after `--dry-run`,
        where candidates are saved locally but have no `scored_at` timestamp yet.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE scored_at IS NOT NULL
                   OR status = 'new'
                ORDER BY
                    CASE WHEN scored_at IS NULL THEN first_seen_at ELSE scored_at END DESC
                """
            ).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    # ── Metadata (KV Store) ──────────────────────────────────────────

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        """Get a value from the metadata table."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else default

    def set_metadata(self, key: str, value: str) -> None:
        """Set a value in the metadata table (upsert)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, value),
            )
        logger.debug("Set metadata %s = %s", key, value)

    # ── Row Converters ──────────────────────────────────────────────

    @staticmethod
    def _serialize_metadata(metadata: dict[str, object] | None) -> str:
        return json.dumps(metadata or {})

    @staticmethod
    def _parse_metadata(raw: str | None) -> dict[str, object]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_country(location: str) -> str | None:
        """Extract country name from a raw location string."""
        if not location or not location.strip():
            return None
        loc = location.strip()
        # "Remote" alone
        if loc.lower() in ("remote", "remote only", "fully remote", "worldwide"):
            return "Remote"
        parts = [p.strip() for p in loc.split(",")]
        last = parts[-1].strip()
        # US state abbreviations → United States
        US_STATES = {
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
            "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
            "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
            "TX","UT","VT","VA","WA","WV","WI","WY","DC",
        }
        if last.upper() in US_STATES:
            return "United States"
        # Abbreviation map
        ABBREV = {
            "UK": "United Kingdom",
            "UAE": "United Arab Emirates",
            "US": "United States",
            "USA": "United States",
        }
        return ABBREV.get(last.upper(), last) if last else None

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> CandidateJob:
        return CandidateJob(
            db_id=row["id"],
            ats_platform=row["ats_platform"],
            company_slug=row["company_slug"],
            company_name=row["company_name"] or "",
            job_id=row["job_id"],
            title=row["title"],
            location=row["location"] or "",
            company_metadata=Store._parse_metadata(row["company_metadata"]) if "company_metadata" in row.keys() else {},
            location_metadata=Store._parse_metadata(row["location_metadata"]) if "location_metadata" in row.keys() else {},
            url=row["url"],
            description=row["description"] or "",
            posted_at=row["posted_at"],
            first_seen_at=row["first_seen_at"],
            salary=row["salary"],
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
            salary_currency=row["salary_currency"],
        )

    @staticmethod
    def _row_to_scored(row: sqlite3.Row) -> ScoredJob:
        breakdown_raw = row["score_breakdown"]
        breakdown: dict[str, int] = {}
        key_matches: list[str] = []
        red_flags: list[str] = []
        fit_category = ""
        apply_priority = "skip"
        skip_reason = "none"
        missing_skills: list[str] = []
        normalization_audit: dict[str, object] = {}
        is_sparse = bool(row["is_sparse"]) if "is_sparse" in row.keys() else False

        if breakdown_raw:
            try:
                data = json.loads(breakdown_raw)
                breakdown = data.get("dimensions", {})
                key_matches = data.get("key_matches", [])
                red_flags = data.get("red_flags", [])
                fit_category = data.get("fit_category", "")
                apply_priority = data.get("apply_priority", "skip")
                skip_reason = data.get("skip_reason", "none")
                missing_skills = data.get("missing_skills", [])
                raw_audit = data.get("normalization_audit", {})
                if isinstance(raw_audit, dict):
                    normalization_audit = raw_audit
            except json.JSONDecodeError:
                pass

        apply_priority, skip_reason = normalize_persisted_priority(
            row["fit_score"] or 0,
            breakdown,
            apply_priority,
            skip_reason,
        )

        return ScoredJob(
            db_id=row["id"],
            ats_platform=row["ats_platform"],
            company_slug=row["company_slug"],
            company_name=row["company_name"] or "",
            job_id=row["job_id"],
            title=row["title"],
            location=row["location"] or "",
            company_metadata=Store._parse_metadata(row["company_metadata"]) if "company_metadata" in row.keys() else {},
            location_metadata=Store._parse_metadata(row["location_metadata"]) if "location_metadata" in row.keys() else {},
            url=row["url"],
            description=row["description"] or "",
            posted_at=row["posted_at"],
            first_seen_at=row["first_seen_at"],
            salary=row["salary"],
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
            salary_currency=row["salary_currency"],
            fit_score=row["fit_score"] or 0,
            reasoning=row["score_reasoning"] or "",
            breakdown=breakdown,
            key_matches=key_matches,
            red_flags=red_flags,
            fit_category=fit_category,
            apply_priority=apply_priority,
            skip_reason=skip_reason,
            missing_skills=missing_skills,
            normalization_audit=normalization_audit,
            scored_at=row["scored_at"],
            status=row["status"] or "new",
            is_sparse=is_sparse,
        )
