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
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Callable, Generator

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
            
            # Migration: Add dismissal_reason if missing
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN dismissal_reason TEXT")
                logger.debug("Migrated DB: Added 'dismissal_reason' column")
            except sqlite3.OperationalError:
                # Column already exists or table doesn't exist yet
                pass

            # Migration: Add match_tier if missing
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN match_tier TEXT")
                logger.debug("Migrated DB: Added 'match_tier' column")
            except sqlite3.OperationalError:
                pass

            # Migration: Add salary fields if missing
            for col, col_type in [
                ("salary", "TEXT"),
                ("salary_min", "INTEGER"),
                ("salary_max", "INTEGER"),
                ("salary_currency", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
                    logger.debug("Migrated DB: Added '%s' column", col)
                except sqlite3.OperationalError:
                    pass

            # Migration: Add is_sparse if missing
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN is_sparse INTEGER DEFAULT 0")
                logger.debug("Migrated DB: Added 'is_sparse' column")
            except sqlite3.OperationalError:
                pass

            # Migration: Add location_metadata if missing
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN location_metadata TEXT")
                logger.debug("Migrated DB: Added 'location_metadata' column")
            except sqlite3.OperationalError:
                pass

            # Migration: Add company_metadata if missing
            try:
                conn.execute("ALTER TABLE jobs ADD COLUMN company_metadata TEXT")
                logger.debug("Migrated DB: Added 'company_metadata' column")
            except sqlite3.OperationalError:
                pass

            logger.debug("Database initialized at %s", self.db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context-managed database connection."""
        conn = sqlite3.connect(self.db_path, timeout=self._busy_timeout_ms / 1000)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
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
                     AND status NOT IN ('applied', 'dismissed', 'closed')""",
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
                "SELECT COUNT(*) FROM jobs WHERE status = 'applied'"
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
            "fit_score, score_reasoning, score_breakdown, scored_at, status, dismissal_reason, match_tier, "
            "salary, salary_min, salary_max, salary_currency, is_sparse"
        )
        
        where_clauses: list[str] = []
        params: list = []
        
        if status:
            placeholders = ",".join("?" * len(status))
            where_clauses.append(f"status IN ({placeholders})")
            params.extend(status)
        
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

    def get_job_detail(self, db_id: int) -> dict | None:
        """Get a single job by ID, including description."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (db_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

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
                          OR status IN ('scored', 'applied')
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
                WHERE status IN ('new', 'scored', 'applied')
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
            if row["status"] == "applied":
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
