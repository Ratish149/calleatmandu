import sqlite3
from pathlib import Path
from typing import Optional

from config import get_base_dir


class Database:
    """
    Lightweight SQLite storage for duplicate protection.
    Records printed job IDs to guarantee idempotency across reconnects.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.db_path = db_path
        else:
            data_dir = get_base_dir() / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "printer_jobs.db"

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables and indexes."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS printed_jobs (
                    job_id TEXT PRIMARY KEY,
                    order_number TEXT,
                    job_type TEXT,
                    printed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_order_number ON printed_jobs(order_number);
                """
            )

    def already_printed(self, job_id: str) -> bool:
        """Checks if a job_id has already been successfully printed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM printed_jobs WHERE job_id = ? LIMIT 1;", (str(job_id),))
            return cursor.fetchone() is not None

    def record_print(self, job_id: str, order_number: str = "", job_type: str = "") -> None:
        """Saves a successfully printed job."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO printed_jobs (job_id, order_number, job_type, printed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (str(job_id), str(order_number), str(job_type)),
            )


# Global singleton database instance
db = Database()
