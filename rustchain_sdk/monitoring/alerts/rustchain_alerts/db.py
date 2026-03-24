"""SQLite persistence for alert history and miner state."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS alert_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    miner_id    TEXT NOT NULL,
    alert_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    fired_at    INTEGER NOT NULL,
    notified    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alert_miner_type
    ON alert_history(miner_id, alert_type, fired_at);

CREATE TABLE IF NOT EXISTS miner_state (
    miner_id        TEXT PRIMARY KEY,
    last_attest     INTEGER,
    balance_rtc     REAL,
    last_seen       INTEGER NOT NULL,
    offline_alerted INTEGER NOT NULL DEFAULT 0
);
"""


class AlertDB:
    def __init__(self, db_path: "str | Path" = "alerts.db") -> None:
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(CREATE_TABLES)

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── miner state ──────────────────────────────────────────────────────────

    def upsert_miner(
        self,
        miner_id: str,
        last_attest: Optional[int],
        balance_rtc: Optional[float],
        offline_alerted: Optional[bool] = None,
    ) -> None:
        now = int(time.time())
        with self._conn() as conn:
            if offline_alerted is not None:
                conn.execute(
                    """INSERT INTO miner_state(miner_id, last_attest, balance_rtc, last_seen, offline_alerted)
                       VALUES(?,?,?,?,?)
                       ON CONFLICT(miner_id) DO UPDATE SET
                           last_attest=excluded.last_attest,
                           balance_rtc=excluded.balance_rtc,
                           last_seen=excluded.last_seen,
                           offline_alerted=excluded.offline_alerted""",
                    (miner_id, last_attest, balance_rtc, now, int(offline_alerted)),
                )
            else:
                conn.execute(
                    """INSERT INTO miner_state(miner_id, last_attest, balance_rtc, last_seen)
                       VALUES(?,?,?,?)
                       ON CONFLICT(miner_id) DO UPDATE SET
                           last_attest=excluded.last_attest,
                           balance_rtc=excluded.balance_rtc,
                           last_seen=excluded.last_seen""",
                    (miner_id, last_attest, balance_rtc, now),
                )

    def get_miner(self, miner_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM miner_state WHERE miner_id=?", (miner_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_offline_alerted(self, miner_id: str, value: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE miner_state SET offline_alerted=? WHERE miner_id=?",
                (int(value), miner_id),
            )

    # ── alert deduplication ──────────────────────────────────────────────────

    def was_alerted_recently(
        self, miner_id: str, alert_type: str, within_seconds: int = 3600
    ) -> bool:
        cutoff = int(time.time()) - within_seconds
        with self._conn() as conn:
            row = conn.execute(
                """SELECT 1 FROM alert_history
                   WHERE miner_id=? AND alert_type=? AND fired_at > ?
                   LIMIT 1""",
                (miner_id, alert_type, cutoff),
            ).fetchone()
            return row is not None

    def record_alert(self, miner_id: str, alert_type: str, message: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO alert_history(miner_id, alert_type, message, fired_at, notified)
                   VALUES(?,?,?,?,1)""",
                (miner_id, alert_type, message, int(time.time())),
            )

    def recent_alerts(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM alert_history ORDER BY fired_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
