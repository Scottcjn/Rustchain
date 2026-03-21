"""
Machine Registry — manages the catalog of vintage machines available for rent.
"""
import sqlite3
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from pathlib import Path


@dataclass
class Machine:
    """Represents a vintage machine in the registry."""
    token_id: int
    name: str
    model: str               # e.g., "POWER8", "Mac G5", "Sun UltraSPARC"
    specs: Dict[str, str]    # CPU, RAM, storage, GPU, etc.
    photo_url: str
    hourly_rate_rtc: float
    total_uptime_seconds: int = 0
    total_rentals: int = 0
    is_active: bool = True
    ed25519_pubkey_hex: str = ""
    attestation_history: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "token_id": self.token_id,
            "name": self.name,
            "model": self.model,
            "specs": self.specs,
            "photo_url": self.photo_url,
            "hourly_rate_rtc": self.hourly_rate_rtc,
            "total_uptime_seconds": self.uptime_formatted,
            "total_rentals": self.total_rentals,
            "is_active": self.is_active,
            "ed25519_pubkey": self.ed25519_pubkey_hex,
            "created_at": self.created_at,
        }

    @property
    def uptime_formatted(self) -> str:
        h, rem = divmod(self.total_uptime_seconds, 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def add_attestation(self, session_id: str, proof: str):
        self.attestation_history.append({
            "session_id": session_id,
            "proof": proof,
            "timestamp": time.time()
        })


class MachineRegistry:
    """
    SQLite-backed registry of vintage machines.
    Used both as a local cache and for MCP tool responses.
    """

    DB_PATH = Path(__file__).parent / "registry.db"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else self.DB_PATH
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS machines (
                    token_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    specs TEXT NOT NULL,   -- JSON
                    photo_url TEXT,
                    hourly_rate_rtc REAL NOT NULL,
                    total_uptime_seconds INTEGER DEFAULT 0,
                    total_rentals INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    ed25519_pubkey TEXT,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attestation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id INTEGER,
                    session_id TEXT,
                    proof TEXT,
                    timestamp REAL,
                    FOREIGN KEY (token_id) REFERENCES machines(token_id)
                )
            """)
            conn.commit()

    def register_machine(self, machine: Machine) -> int:
        """Add a machine to the registry."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO machines (token_id, name, model, specs, photo_url,
                                       hourly_rate_rtc, total_uptime_seconds,
                                       total_rentals, is_active, ed25519_pubkey, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                machine.token_id, machine.name, machine.model,
                json.dumps(machine.specs), machine.photo_url,
                machine.hourly_rate_rtc, machine.total_uptime_seconds,
                machine.total_rentals, int(machine.is_active),
                machine.ed25519_pubkey_hex, machine.created_at
            ))
            conn.commit()
        return machine.token_id

    def get_machine(self, token_id: int) -> Optional[Machine]:
        """Fetch a single machine by token ID."""
        import json
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM machines WHERE token_id = ?", (token_id,)
            ).fetchone()
        if not row:
            return None
        return Machine(
            token_id=row[0], name=row[1], model=row[2],
            specs=json.loads(row[3]), photo_url=row[4],
            hourly_rate_rtc=row[5], total_uptime_seconds=row[6],
            total_rentals=row[7], is_active=bool(row[8]),
            ed25519_pubkey_hex=row[9] or "", created_at=row[10] or time.time()
        )

    def list_machines(self, active_only: bool = True) -> List[Machine]:
        """List all machines, optionally filtering to active only."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM machines"
            if active_only:
                query += " WHERE is_active = 1"
            rows = conn.execute(query).fetchall()

        import json
        machines = []
        for row in rows:
            machines.append(Machine(
                token_id=row[0], name=row[1], model=row[2],
                specs=json.loads(row[3]), photo_url=row[4],
                hourly_rate_rtc=row[5], total_uptime_seconds=row[6],
                total_rentals=row[7], is_active=bool(row[8]),
                ed25519_pubkey_hex=row[9] or "", created_at=row[10] or time.time()
            ))
        return machines

    def update_uptime(self, token_id: int, added_seconds: int):
        """Increment machine uptime after a rental session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE machines SET total_uptime_seconds = total_uptime_seconds + ? WHERE token_id = ?",
                (added_seconds, token_id)
            )
            conn.commit()

    def add_attestation(self, token_id: int, session_id: str, proof: str):
        """Record an attestation event in history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO attestation_history (token_id, session_id, proof, timestamp) VALUES (?, ?, ?, ?)",
                (token_id, session_id, proof, time.time())
            )
            conn.commit()

    def get_attestations(self, token_id: int) -> List[Dict]:
        """Get attestation history for a machine."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT session_id, proof, timestamp FROM attestation_history WHERE token_id = ? ORDER BY timestamp DESC",
                (token_id,)
            ).fetchall()
        return [{"session_id": r[0], "proof": r[1], "timestamp": r[2]} for r in rows]

    def seed_demo_machines(self):
        """Populate registry with demo vintage machines."""
        demos = [
            Machine(
                token_id=0,
                name="Old Ironsides",
                model="IBM POWER8 8247-21L",
                specs={
                    "CPU": "POWER8 (3.02 GHz, 12 cores)",
                    "RAM": "512 GB DDR3 ECC",
                    "Storage": "4× 600 GB SAS 15k RPM",
                    "Network": "10GbE",
                    "OS": "AIX 7.2 / Ubuntu 20.04 (ppc64le)",
                    "Architecture": "ppc64le",
                },
                photo_url="ipfs://QmOldIron001/photo.jpg",
                hourly_rate_rtc=50.0,
                ed25519_pubkey_hex="a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
            ),
            Machine(
                token_id=1,
                name="Amber Ghost",
                model="Apple Mac G5 Quad 2005",
                specs={
                    "CPU": "PowerPC 970MP (2.5 GHz, 4 cores)",
                    "RAM": "256 GB DDR2",
                    "Storage": "2× 500 GB SATA + 512 GB SSD",
                    "GPU": "ATI X850 XT",
                    "OS": "Mac OS X 10.4 / Linux (ppc64)",
                    "Architecture": "ppc64",
                },
                photo_url="ipfs://QmAmberGh002/photo.jpg",
                hourly_rate_rtc=30.0,
                ed25519_pubkey_hex="b2c3d4e5f6789012bcdef123456789012bcdef123456789012bcdef12345678",
            ),
            Machine(
                token_id=2,
                name="Solaris Sparrow",
                model="Sun UltraSPARC T2",
                specs={
                    "CPU": "UltraSPARC T2 (1.4 GHz, 64 threads)",
                    "RAM": "128 GB DDR2",
                    "Storage": "4× 300 GB 10k RPM",
                    "Network": "4× 1GbE",
                    "OS": "Solaris 10 / OpenIndiana",
                    "Architecture": "sparc64",
                },
                photo_url="ipfs://QmSolarSp003/photo.jpg",
                hourly_rate_rtc=25.0,
                ed25519_pubkey_hex="c3d4e5f67890123cdef1234567890123cdef1234567890123cdef12345678901",
            ),
            Machine(
                token_id=3,
                name="Vax Phantom",
                model="DEC VAX 11/780 (Simulated)",
                specs={
                    "CPU": "Simulated VAX (KA780)",
                    "RAM": "16 MB",
                    "Storage": "Simulated RK07",
                    "OS": "VMS 7.3 / Ultrix",
                    "Architecture": "vax",
                    "Note": "Software emulated via SIMH",
                },
                photo_url="ipfs://QmVaxPhan004/photo.jpg",
                hourly_rate_rtc=15.0,
                ed25519_pubkey_hex="d4e5f678901234de12345678901234de12345678901234de12345678901234",
            ),
            Machine(
                token_id=4,
                name="Cray Shade",
                model="Cray X1E (Simulated)",
                specs={
                    "CPU": "Cray X1E MSP (10 GHz, 4 cores)",
                    "RAM": "64 GB",
                    "Storage": "18.5 GB/s bandwidth",
                    "OS": "Unicos/mp",
                    "Architecture": "cray",
                    "Note": "Software emulated",
                },
                photo_url="ipfs://QmCrayShd005/photo.jpg",
                hourly_rate_rtc=80.0,
                ed25519_pubkey_hex="e5f6789012345ef123456789012345f123456789012345f1234567890123456",
            ),
        ]
        for m in demos:
            try:
                self.register_machine(m)
                print(f"Registered: {m.name} ({m.model})")
            except sqlite3.IntegrityError:
                print(f"Already registered: {m.name}")


if __name__ == "__main__":
    registry = MachineRegistry()
    registry.seed_demo_machines()
    print("\nRegistered machines:")
    for m in registry.list_machines(active_only=False):
        print(f"  [{m.token_id}] {m.name} — {m.model} — {m.hourly_rate_rtc} RTC/hr — active={m.is_active}")
