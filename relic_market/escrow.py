"""
Escrow — RTC payment escrow management for relic rentals.
Handles locking RTC during reservation, releasing on completion, refunding on cancellation.
"""
import sqlite3
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import IntEnum


class EscrowState(IntEnum):
    PENDING = 0
    LOCKED = 1
    RELEASED = 2
    REFUNDED = 3


@dataclass
class EscrowEntry:
    """An escrow entry tracking locked RTC for a rental."""
    escrow_id: str
    rental_id: str
    machine_token_id: int
    renter: str
    amount_rtc: float
    state: EscrowState
    created_at: float = field(default_factory=time.time)
    released_at: Optional[float] = None
    tx_hash: Optional[str] = None


class EscrowManager:
    """
    Manages RTC escrow for rental reservations.

    In production, integrates with Solana wRTC or a payment channel.
    For this implementation, we track escrow state locally with SQLite
    and simulate the on-chain locking via a hash commitment scheme.
    """

    DB_PATH = Path(__file__).parent / "escrow.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else self.DB_PATH
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS escrow (
                    escrow_id TEXT PRIMARY KEY,
                    rental_id TEXT NOT NULL,
                    machine_token_id INTEGER,
                    renter TEXT NOT NULL,
                    amount_rtc REAL NOT NULL,
                    state INTEGER DEFAULT 0,
                    created_at REAL,
                    released_at REAL,
                    tx_hash TEXT,
                    commitment_hash TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rental ON escrow(rental_id)
            """)
            conn.commit()

    def _make_commitment(self, rental_id: str, amount: float, renter: str) -> str:
        """Create a deterministic commitment hash for the escrow."""
        raw = f"{rental_id}:{amount}:{renter}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def lock(self, rental_id: str, machine_token_id: int, renter: str, amount_rtc: float) -> EscrowEntry:
        """
        Lock RTC for a rental. In production, this would initiate a payment channel
        or submit a hash-lock transaction on Solana.
        Returns an EscrowEntry with the commitment hash.
        """
        escrow_id = hashlib.sha256(f"{rental_id}:{renter}".encode()).hexdigest()[:16]
        commitment = self._make_commitment(rental_id, amount_rtc, renter)

        entry = EscrowEntry(
            escrow_id=escrow_id,
            rental_id=rental_id,
            machine_token_id=machine_token_id,
            renter=renter,
            amount_rtc=amount_rtc,
            state=EscrowState.LOCKED,
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO escrow
                (escrow_id, rental_id, machine_token_id, renter, amount_rtc, state, created_at, commitment_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry.escrow_id, entry.rental_id, entry.machine_token_id,
                  entry.renter, entry.amount_rtc, int(entry.state),
                  entry.created_at, commitment))
            conn.commit()

        return entry

    def release(self, escrow_id: str, tx_hash: str) -> bool:
        """Release locked RTC to machine owner (called after successful session)."""
        with sqlite3.connect(self.db_path) as conn:
            affected = conn.execute("""
                UPDATE escrow SET state = ?, released_at = ?, tx_hash = ?
                WHERE escrow_id = ? AND state = ?
            """, (int(EscrowState.RELEASED), time.time(), tx_hash,
                  escrow_id, int(EscrowState.LOCKED))).rowcount
            conn.commit()
        return affected > 0

    def refund(self, escrow_id: str) -> bool:
        """Refund locked RTC to renter (called on cancellation)."""
        with sqlite3.connect(self.db_path) as conn:
            affected = conn.execute("""
                UPDATE escrow SET state = ?, released_at = ?
                WHERE escrow_id = ? AND state = ?
            """, (int(EscrowState.REFUNDED), time.time(),
                  escrow_id, int(EscrowState.LOCKED))).rowcount
            conn.commit()
        return affected > 0

    def get_entry(self, escrow_id: str) -> Optional[EscrowEntry]:
        """Fetch an escrow entry by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM escrow WHERE escrow_id = ?", (escrow_id,)
            ).fetchone()
        if not row:
            return None
        return EscrowEntry(
            escrow_id=row[0], rental_id=row[1], machine_token_id=row[2],
            renter=row[3], amount_rtc=row[4], state=EscrowState(row[5]),
            created_at=row[6], released_at=row[7], tx_hash=row[8]
        )

    def get_entries_by_renter(self, renter: str) -> List[EscrowEntry]:
        """Get all escrow entries for a renter."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM escrow WHERE renter = ? ORDER BY created_at DESC", (renter,)
            ).fetchall()
        return [
            EscrowEntry(escrow_id=r[0], rental_id=r[1], machine_token_id=r[2],
                        renter=r[3], amount_rtc=r[4], state=EscrowState(r[5]),
                        created_at=r[6], released_at=r[7], tx_hash=r[8])
            for r in rows
        ]

    def total_locked(self) -> float:
        """Total RTC currently locked in escrow."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount_rtc), 0) FROM escrow WHERE state = ?",
                (int(EscrowState.LOCKED),)
            ).fetchone()
        return row[0] if row else 0.0

    def summary(self) -> Dict:
        """Return a summary of escrow state."""
        with sqlite3.connect(self.db_path) as conn:
            locked = conn.execute(
                "SELECT COUNT(*) FROM escrow WHERE state = ?", (int(EscrowState.LOCKED),)
            ).fetchone()[0]
            released = conn.execute(
                "SELECT COUNT(*) FROM escrow WHERE state = ?", (int(EscrowState.RELEASED),)
            ).fetchone()[0]
            refunded = conn.execute(
                "SELECT COUNT(*) FROM escrow WHERE state = ?", (int(EscrowState.REFUNDED),)
            ).fetchone()[0]
        return {
            "total_locked_rtc": self.total_locked(),
            "active_escrows": locked,
            "released_count": released,
            "refunded_count": refunded,
        }


if __name__ == "__main__":
    escrow = EscrowManager()
    # Demo: lock some RTC
    entry = escrow.lock("rental_abc123", 0, "C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg", 50.0)
    print(f"Locked {entry.amount_rtc} RTC — escrow_id={entry.escrow_id}")
    print(f"Summary: {escrow.summary()}")
    print(f"Released: {escrow.release(entry.escrow_id, 'sol_tx_abc123')}")
    print(f"Final summary: {escrow.summary()}")
