"""
green_tracker.py — RustChain Machine E-Waste Preservation Tracker
Tracks machines preserved from e-waste through RustChain mining.
Bounty #2218
"""

import sqlite3
import json
import datetime
from typing import Optional, List, Dict, Any


# ── E-Waste weight estimates per architecture (kg) ──────────────────────────
EWASTE_WEIGHTS_KG: Dict[str, float] = {
    "G3":      6.0,
    "G4":      8.0,
    "G5":     12.0,
    "POWER8":  25.0,
    "POWER9":  28.0,
    "POWER10": 30.0,
    "x86":     5.0,
    "x86_64":  5.0,
    "ARM":     0.5,
    "ARM64":   0.5,
    "RPi":     0.1,
    "MIPS":    1.0,
    "SPARC":   10.0,
    "Alpha":   12.0,
    "PA-RISC": 15.0,
    "Amiga":   3.5,
    "default": 5.0,
}

# ── CO2 estimates (kg CO2-eq) ────────────────────────────────────────────────
# Manufacturing a new comparable machine
NEW_HARDWARE_CO2_KG: Dict[str, float] = {
    "G3":      200.0,
    "G4":      250.0,
    "G5":      400.0,
    "POWER8":  800.0,
    "POWER9":  900.0,
    "POWER10": 1000.0,
    "x86":     180.0,
    "x86_64":  200.0,
    "ARM":     50.0,
    "ARM64":   50.0,
    "RPi":     10.0,
    "MIPS":    60.0,
    "SPARC":   350.0,
    "Alpha":   400.0,
    "PA-RISC": 500.0,
    "Amiga":   120.0,
    "default": 200.0,
}
# Annual operational CO2 for continuing to run the old machine (kg/year)
REUSE_CO2_PER_YEAR_KG = 30.0


class GreenTracker:
    """Tracks machines preserved from e-waste via RustChain mining."""

    def __init__(self, db_path: str = "green_tracker.db"):
        self.db_path = db_path
        # For :memory: databases, reuse a single connection so data persists.
        if db_path == ":memory:":
            self._shared_conn: Optional[sqlite3.Connection] = sqlite3.connect(db_path)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON")
        else:
            self._shared_conn = None
        self._init_db()

    # ── Internal helpers ────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS machines (
                machine_id        TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                arch              TEXT NOT NULL,
                year_manufactured INTEGER NOT NULL,
                condition         TEXT NOT NULL,
                location          TEXT NOT NULL,
                photo_url         TEXT,
                registered_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mining_sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id  TEXT NOT NULL REFERENCES machines(machine_id),
                epoch       INTEGER NOT NULL,
                rtc_earned  REAL NOT NULL,
                power_watts REAL NOT NULL,
                recorded_at TEXT NOT NULL
            );
        """)

    # ── Public API ──────────────────────────────────────────────────────────

    def register_machine(
        self,
        machine_id: str,
        name: str,
        arch: str,
        year_manufactured: int,
        condition: str,
        location: str,
        photo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a machine as preserved from e-waste."""
        now = datetime.datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO machines
                    (machine_id, name, arch, year_manufactured, condition,
                     location, photo_url, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (machine_id, name, arch, year_manufactured, condition,
                 location, photo_url, now),
            )
        return {
            "machine_id": machine_id,
            "name": name,
            "arch": arch,
            "ewaste_prevented_kg": self.estimate_ewaste_prevented(
                {"arch": arch}
            ),
            "registered_at": now,
        }

    def record_mining_session(
        self,
        machine_id: str,
        epoch: int,
        rtc_earned: float,
        power_watts: float,
    ) -> Dict[str, Any]:
        """Record a completed mining epoch for a machine."""
        now = datetime.datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mining_sessions
                    (machine_id, epoch, rtc_earned, power_watts, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (machine_id, epoch, rtc_earned, power_watts, now),
            )
        return {"machine_id": machine_id, "epoch": epoch,
                "rtc_earned": rtc_earned, "recorded_at": now}

    def get_machine_stats(self, machine_id: str) -> Dict[str, Any]:
        """Return total RTC, epochs, and estimated CO2 saved for a machine."""
        with self._connect() as conn:
            machine = conn.execute(
                "SELECT * FROM machines WHERE machine_id = ?", (machine_id,)
            ).fetchone()
            if not machine:
                raise ValueError(f"Machine '{machine_id}' not found")

            stats = conn.execute(
                """
                SELECT COUNT(*) AS total_epochs,
                       COALESCE(SUM(rtc_earned), 0) AS total_rtc,
                       COALESCE(SUM(power_watts), 0) AS total_power_watts
                FROM mining_sessions WHERE machine_id = ?
                """,
                (machine_id,),
            ).fetchone()

        arch = machine["arch"]
        years_active = max(
            1, datetime.datetime.utcnow().year - machine["year_manufactured"]
        )
        co2_saved = self._co2_saved(arch, years_active)
        ewaste_kg = self.estimate_ewaste_prevented(dict(machine))

        return {
            "machine_id": machine_id,
            "name": machine["name"],
            "arch": arch,
            "year_manufactured": machine["year_manufactured"],
            "condition": machine["condition"],
            "location": machine["location"],
            "total_epochs": stats["total_epochs"],
            "total_rtc_earned": round(stats["total_rtc"], 4),
            "total_power_watts_logged": round(stats["total_power_watts"], 2),
            "ewaste_prevented_kg": ewaste_kg,
            "co2_saved_kg": round(co2_saved, 2),
            "years_active": years_active,
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Return aggregate stats across all tracked machines."""
        with self._connect() as conn:
            machines = conn.execute("SELECT * FROM machines").fetchall()
            agg = conn.execute(
                """
                SELECT COUNT(*) AS total_sessions,
                       COALESCE(SUM(rtc_earned), 0) AS total_rtc
                FROM mining_sessions
                """
            ).fetchone()

        total_ewaste_kg = sum(
            self.estimate_ewaste_prevented(dict(m)) for m in machines
        )
        total_co2 = sum(
            self._co2_saved(
                m["arch"],
                max(1, datetime.datetime.utcnow().year - m["year_manufactured"]),
            )
            for m in machines
        )

        return {
            "total_machines_preserved": len(machines),
            "total_mining_sessions": agg["total_sessions"],
            "total_rtc_earned": round(agg["total_rtc"], 4),
            "total_ewaste_prevented_kg": round(total_ewaste_kg, 2),
            "total_co2_saved_kg": round(total_co2, 2),
        }

    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return top machines ranked by RTC earned."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.machine_id, m.name, m.arch, m.location,
                       COALESCE(SUM(s.rtc_earned), 0) AS total_rtc,
                       COUNT(s.id) AS total_epochs
                FROM machines m
                LEFT JOIN mining_sessions s ON s.machine_id = m.machine_id
                GROUP BY m.machine_id
                ORDER BY total_rtc DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_architecture(self, arch: str) -> List[Dict[str, Any]]:
        """Return all machines of a given architecture."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM machines WHERE arch = ?", (arch,)
            ).fetchall()
        return [dict(r) for r in rows]

    def estimate_ewaste_prevented(self, machine: Dict[str, Any]) -> float:
        """Return estimated e-waste prevented (kg) for the given machine."""
        arch = machine.get("arch", "default")
        return EWASTE_WEIGHTS_KG.get(arch, EWASTE_WEIGHTS_KG["default"])

    def export_badge_data(self, machine_id: str) -> Dict[str, Any]:
        """Export JSON badge data for 'Preserved from E-Waste' NFT/badge."""
        stats = self.get_machine_stats(machine_id)
        badge = {
            "badge": "Preserved from E-Waste",
            "version": "1.0",
            "issued_by": "RustChain Green Initiative",
            "issued_at": datetime.datetime.utcnow().isoformat() + "Z",
            "machine": {
                "id": stats["machine_id"],
                "name": stats["name"],
                "architecture": stats["arch"],
                "year_manufactured": stats["year_manufactured"],
                "condition": stats["condition"],
                "location": stats["location"],
            },
            "impact": {
                "ewaste_prevented_kg": stats["ewaste_prevented_kg"],
                "co2_saved_kg": stats["co2_saved_kg"],
                "total_rtc_earned": stats["total_rtc_earned"],
                "total_mining_epochs": stats["total_epochs"],
                "years_active": stats["years_active"],
            },
            "metadata": {
                "description": (
                    f"{stats['name']} ({stats['arch']}, {stats['year_manufactured']}) "
                    f"has been preserved from e-waste and is actively mining "
                    f"on RustChain, saving an estimated "
                    f"{stats['ewaste_prevented_kg']} kg of e-waste and "
                    f"{stats['co2_saved_kg']} kg of CO2."
                ),
                "image_url": "https://rustchain.network/badges/green-preserved.png",
                "external_url": (
                    f"https://rustchain.network/green/{stats['machine_id']}"
                ),
            },
        }
        return badge

    # ── Private calculations ────────────────────────────────────────────────

    def _co2_saved(self, arch: str, years_active: int) -> float:
        """
        CO2 saved = new hardware manufacturing CO2 minus annual reuse cost.
        Each year the machine stays in service avoids one new-hardware cycle,
        minus the operational CO2 for running the old machine.
        """
        new_hw_co2 = NEW_HARDWARE_CO2_KG.get(arch, NEW_HARDWARE_CO2_KG["default"])
        saved = new_hw_co2 - (REUSE_CO2_PER_YEAR_KG * years_active)
        return max(0.0, saved)
