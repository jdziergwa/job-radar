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
