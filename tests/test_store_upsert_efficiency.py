import sqlite3
import tempfile
from pathlib import Path

from src.models import RawJob
from src.store import Store


class _ConnectionProxy:
    def __init__(self, conn: sqlite3.Connection, last_seen_updates: list[int]) -> None:
        self._conn = conn
        self._last_seen_updates = last_seen_updates

    def executemany(self, sql, seq_of_parameters):
        params = list(seq_of_parameters)
        if sql == "UPDATE jobs SET last_seen_at = ? WHERE ats_platform = ? AND company_slug = ? AND job_id = ?":
            self._last_seen_updates.append(len(params))
        return self._conn.executemany(sql, params)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_upsert_jobs_skips_last_seen_refresh_for_all_new_batch():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jobs.db"
        last_seen_updates: list[int] = []
        real_connect = sqlite3.connect

        def connect_proxy(*args, **kwargs):
            return _ConnectionProxy(real_connect(*args, **kwargs), last_seen_updates)

        original_connect = sqlite3.connect
        sqlite3.connect = connect_proxy
        try:
            store = Store(str(db_path))
            jobs = [
                RawJob(
                    ats_platform="aggregator",
                    company_slug="example",
                    company_name="Example",
                    job_id=f"job-{idx}",
                    title=f"Role {idx}",
                    location="Remote",
                    url=f"https://example.com/{idx}",
                    description="",
                    posted_at=None,
                    fetched_at="2026-04-08T00:00:00Z",
                )
                for idx in range(5)
            ]
            store.upsert_jobs(jobs)
        finally:
            sqlite3.connect = original_connect

        assert last_seen_updates == []
