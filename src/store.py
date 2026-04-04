"""SQLite storage layer for Job Radar.

Handles dedup, persistence, scoring results, and status tracking.
Database path is passed in to support multi-profile operation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator

from src.models import CandidateJob, RawJob, ScoredJob

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
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

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._connect() as conn:
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

            logger.debug("Database initialized at %s", self.db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context-managed database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Upsert ──────────────────────────────────────────────────────

    def upsert_jobs(self, jobs: list[RawJob]) -> list[RawJob]:
        """Insert new jobs, skip duplicates. Returns only newly inserted jobs."""
        if not jobs:
            return []
            
        now = datetime.utcnow().isoformat()
        
        # We need to find which jobs are actually "new"
        # For small sets (<1000) we can just use the try/except loop, 
        # but for large sets we should batch.
        
        with self._connect() as conn:
            # 1. Update last_seen_at for all in batch
            update_data = [
                (now, j.ats_platform, j.company_slug, j.job_id)
                for j in jobs
            ]
            conn.executemany(
                "UPDATE jobs SET last_seen_at = ? WHERE ats_platform = ? AND company_slug = ? AND job_id = ?",
                update_data
            )
            
            # 2. Insert new jobs (using INSERT OR IGNORE for speed)
            insert_data = [
                (
                    j.ats_platform, j.company_slug, j.job_id,
                    j.company_name, j.title, j.location,
                    j.url, j.description, j.posted_at, now, now
                )
                for j in jobs
            ]
            
            # SQLite doesn't directly return which rows were inserted in a batch,
            # so we'll check counts or just revert to the old logic if we MUST know exactly which are new.
            # However, for the pipeline, we often need to know the 'new' ones to report them.
            
            # Alternative: Insert to a temp table and find delta, or just do the loop but more efficiently.
            # Let's keep the loop for now but use a single transaction (which _connect already does).
            # The REAL bottleneck in the original code was likely if _connect was called inside the loop.
            # It wasn't, but let's make it even faster by pre-checking existing IDs.
            
            keys = [(j.ats_platform, j.company_slug, j.job_id) for j in jobs]
            # Chunk keys to avoid SQLite parameter limit (999)
            existing_keys = set()
            for i in range(0, len(keys), 300):
                chunk = keys[i:i+300]
                placeholders = ",".join(["(?,?,?)"] * len(chunk))
                flat_params = [p for k in chunk for p in k]
                rows = conn.execute(
                    f"SELECT ats_platform, company_slug, job_id FROM jobs WHERE (ats_platform, company_slug, job_id) IN ({placeholders})",
                    flat_params
                ).fetchall()
                for r in rows:
                    existing_keys.add((r[0], r[1], r[2]))

            new_jobs = []
            to_insert = []
            to_backfill = []
            
            for j in jobs:
                key = (j.ats_platform, j.company_slug, j.job_id)
                if key not in existing_keys:
                    new_jobs.append(j)
                    to_insert.append((
                        j.ats_platform, j.company_slug, j.job_id,
                        j.company_name, j.title, j.location,
                        j.url, j.description, j.posted_at, now, now,
                        j.status, j.dismissal_reason, j.match_tier
                    ))
                elif j.description and len(j.description) > 50:
                    # Potential backfill for existing jobs with missing descriptions
                    to_backfill.append((j.description, j.ats_platform, j.company_slug, j.job_id))
            
            if to_insert:
                conn.executemany(
                    "INSERT INTO jobs (ats_platform, company_slug, job_id, company_name, title, location, url, description, posted_at, first_seen_at, last_seen_at, status, dismissal_reason, match_tier) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    to_insert
                )
            
            if to_backfill:
                # Only update if the existing description is missing or very short (stub)
                conn.executemany(
                    "UPDATE jobs SET description = ? WHERE ats_platform = ? AND company_slug = ? AND job_id = ? AND (description IS NULL OR length(description) < 50)",
                    to_backfill
                )

        logger.info("Upserted %d jobs, %d new", len(jobs), len(new_jobs))
        return new_jobs

    # ── Scoring ─────────────────────────────────────────────────────

    def update_score(
        self,
        db_id: int,
        fit_score: int,
        reasoning: str,
        breakdown: dict[str, int],
        key_matches: list[str] | None = None,
        red_flags: list[str] | None = None,
        apply_priority: str = "skip",
        skip_reason: str = "none",
        missing_skills: list[str] | None = None,
    ) -> None:
        """Store LLM scoring results for a job."""
        now = datetime.utcnow().isoformat()
        breakdown_json = json.dumps({
            "dimensions": breakdown,
            "key_matches": key_matches or [],
            "red_flags": red_flags or [],
            "apply_priority": apply_priority,
            "skip_reason": skip_reason or "none",
            "missing_skills": missing_skills or [],
        })

        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs
                   SET fit_score = ?, score_reasoning = ?, score_breakdown = ?,
                       scored_at = ?, status = 'scored'
                   WHERE id = ?""",
                (fit_score, reasoning, breakdown_json, now, db_id),
            )
        logger.debug("Scored job %d: %d%%", db_id, fit_score)

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

            # Apply priority counts from score_breakdown JSON
            priority_counts = {"high": 0, "medium": 0, "low": 0, "skip": 0}
            try:
                rows = conn.execute(
                    "SELECT score_breakdown FROM jobs WHERE score_breakdown IS NOT NULL"
                ).fetchall()
                for row in rows:
                    data = json.loads(row[0])
                    p = data.get("apply_priority", "skip")
                    if p in priority_counts:
                        priority_counts[p] += 1
            except (json.JSONDecodeError, Exception):
                pass

        return {
            "total_jobs": total,
            "new_today": new_today,
            "total_new_today": total_new_today,
            "new_this_week": new_this_week,
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
    ) -> tuple[list[dict], int]:
        """Filtered, paginated job list for the web API.
        
        Returns (rows_as_dicts, total_count). Excludes description for performance.
        """
        columns = (
            "id, ats_platform, company_slug, company_name, job_id, title, "
            "location, url, posted_at, first_seen_at, last_seen_at, "
            "fit_score, score_reasoning, score_breakdown, scored_at, status, dismissal_reason, match_tier"
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
        
        if priority:
            where_clauses.append("JSON_EXTRACT(score_breakdown, '$.apply_priority') = ?")
            params.append(priority)
        
        if company:
            where_clauses.append("LOWER(company_name) LIKE ?")
            params.append(f"%{company.lower()}%")
        
        if search:
            where_clauses.append("(LOWER(title) LIKE ? OR LOWER(company_name) LIKE ? OR LOWER(description) LIKE ?)")
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%", f"%{search.lower()}%"])
        
        if days:
            where_clauses.append("first_seen_at >= datetime('now', ?)")
            params.append(f"-{days} days")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Sort validation
        sort_map = {"score": "fit_score", "date": "first_seen_at", "company": "company_name"}
        sort_col = sort_map.get(sort, "fit_score")
        order_sql = "ASC" if order.lower() == "asc" else "DESC"
        
        offset = (page - 1) * per_page
        
        with self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM jobs WHERE {where_sql}", params
            ).fetchone()[0]
            
            rows = conn.execute(
                f"SELECT {columns} FROM jobs WHERE {where_sql} "
                f"ORDER BY {sort_col} {order_sql} NULLS LAST "
                f"LIMIT ? OFFSET ?",
                params + [per_page, offset],
            ).fetchall()
            
            result = [dict(row) for row in rows]
        
        return result, total

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
            # Daily new jobs + scored count
            daily_rows = conn.execute("""
                SELECT
                    date(first_seen_at) as day,
                    COUNT(*) as new_jobs,
                    SUM(CASE WHEN status IN ('scored', 'applied', 'dismissed') THEN 1 ELSE 0 END) as scored
                FROM jobs
                WHERE date(first_seen_at) >= date('now', ?)
                GROUP BY date(first_seen_at)
                ORDER BY day ASC
            """, (f"-{days} days",)).fetchall()

            # Skill frequency from key_matches in score_breakdown
            breakdown_rows = conn.execute(
                "SELECT score_breakdown FROM jobs WHERE score_breakdown IS NOT NULL AND fit_score IS NOT NULL"
            ).fetchall()

            # Company stats
            company_rows = conn.execute("""
                SELECT
                    company_name,
                    COUNT(*) as job_count,
                    AVG(CASE WHEN fit_score IS NOT NULL THEN fit_score END) as avg_score,
                    MAX(date(last_seen_at)) as last_seen
                FROM jobs
                GROUP BY company_name
                ORDER BY job_count DESC
                LIMIT 30
            """).fetchall()

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

        return {
            "daily_counts": [
                {"date": r["day"], "new_jobs": r["new_jobs"], "scored": r["scored"]}
                for r in daily_rows
            ],
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
                """SELECT score_breakdown, location FROM jobs
                   WHERE scored_at IS NOT NULL
                     AND date(scored_at) >= date('now', ?)""",
                (f"-{days} days",)
            ).fetchall()

        from collections import Counter
        skip_counter: Counter = Counter()
        missing_counter: Counter = Counter()
        country_counter: Counter = Counter()
        priority_counter: Counter = Counter()
        total = 0

        for row in rows:
            total += 1
            country = Store._parse_country(row["location"] or "")
            if country:
                country_counter[country] += 1

            bd = row["score_breakdown"]
            if not bd:
                skip_counter["none"] += 1
                continue
            try:
                data = json.loads(bd)
                skip_counter[data.get("skip_reason", "none")] += 1
                priority_counter[data.get("apply_priority", "skip")] += 1
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
        }

    # ── Rescore support ─────────────────────────────────────────────

    def get_scored_for_rescore(self) -> list[CandidateJob]:
        """Get all previously scored jobs for re-scoring."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE scored_at IS NOT NULL ORDER BY scored_at DESC"
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
            url=row["url"],
            description=row["description"] or "",
            posted_at=row["posted_at"],
            first_seen_at=row["first_seen_at"],
        )

    @staticmethod
    def _row_to_scored(row: sqlite3.Row) -> ScoredJob:
        breakdown_raw = row["score_breakdown"]
        breakdown: dict[str, int] = {}
        key_matches: list[str] = []
        red_flags: list[str] = []
        apply_priority = "skip"
        skip_reason = "none"
        missing_skills: list[str] = []

        if breakdown_raw:
            try:
                data = json.loads(breakdown_raw)
                breakdown = data.get("dimensions", {})
                key_matches = data.get("key_matches", [])
                red_flags = data.get("red_flags", [])
                apply_priority = data.get("apply_priority", "skip")
                skip_reason = data.get("skip_reason", "none")
                missing_skills = data.get("missing_skills", [])
            except json.JSONDecodeError:
                pass

        return ScoredJob(
            db_id=row["id"],
            ats_platform=row["ats_platform"],
            company_slug=row["company_slug"],
            company_name=row["company_name"] or "",
            job_id=row["job_id"],
            title=row["title"],
            location=row["location"] or "",
            url=row["url"],
            description=row["description"] or "",
            posted_at=row["posted_at"],
            first_seen_at=row["first_seen_at"],
            fit_score=row["fit_score"] or 0,
            reasoning=row["score_reasoning"] or "",
            breakdown=breakdown,
            key_matches=key_matches,
            red_flags=red_flags,
            apply_priority=apply_priority,
            skip_reason=skip_reason,
            missing_skills=missing_skills,
            scored_at=row["scored_at"],
            status=row["status"] or "new",
        )
