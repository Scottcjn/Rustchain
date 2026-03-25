# SPDX-License-Identifier: MIT
"""
RustChain Machine Passport Ledger
Bounty #2309: 70 RTC

On-chain passport format for relic machines: ROM hashes, repair history,
capacitor swaps, motherboard photos, benchmark signatures, and lineage notes.

A miner stops being just an address and becomes a documented character
with a biography.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class RepairEntry:
    """A dated repair/maintenance log entry."""
    date: str                          # ISO date: "2024-03-15"
    description: str                   # "Replaced PRAM battery"
    technician: str = ""               # Who did the work
    parts: List[str] = field(default_factory=list)  # Parts used
    photo_hash: str = ""               # IPFS hash of repair photo

    def to_dict(self):
        return asdict(self)


@dataclass
class BenchmarkSignature:
    """Hardware benchmark fingerprint snapshot."""
    cache_timing_profile: Dict = field(default_factory=dict)  # L1/L2/L3 latencies
    simd_identity: Dict = field(default_factory=dict)         # AltiVec/SSE/AVX flags
    thermal_curve: List[float] = field(default_factory=list)  # Temperature readings
    clock_drift_hash: str = ""                                 # Drift fingerprint
    collected_at: str = ""                                     # ISO timestamp

    def to_dict(self):
        return asdict(self)


@dataclass
class AttestationHistory:
    """Summary of a machine's attestation participation."""
    first_seen_epoch: int = 0
    last_seen_epoch: int = 0
    total_epochs: int = 0
    total_rtc_earned: float = 0.0
    multiplier: float = 1.0
    streak_days: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class MachinePassport:
    """
    The Machine Passport — a biography for relic hardware.

    Each machine gets a unique passport documenting its identity,
    history, repairs, and attestation record on-chain.
    """
    machine_id: str                    # Hardware fingerprint hash
    name: str = ""                     # Human-given name ("Old Faithful")
    manufacture_year: int = 0          # Estimated from ROM/CPU stepping
    architecture: str = ""             # G4, G5, SPARC, MIPS, etc.
    cpu_model: str = ""                # "PowerPC G4 7447A"
    rom_hash: str = ""                 # ROM/firmware hash
    photo_hash: str = ""               # IPFS or BoTTube link to photo
    provenance: str = ""               # "eBay lot", "grandmother's closet"
    owner_address: str = ""            # RTC wallet address
    repair_log: List[RepairEntry] = field(default_factory=list)
    attestation_history: AttestationHistory = field(default_factory=AttestationHistory)
    benchmark_signatures: List[BenchmarkSignature] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self):
        d = asdict(self)
        return d

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict) -> "MachinePassport":
        repair_log = [RepairEntry(**r) for r in data.pop("repair_log", [])]
        attestation = AttestationHistory(**data.pop("attestation_history", {}))
        benchmarks = [BenchmarkSignature(**b) for b in data.pop("benchmark_signatures", [])]
        return cls(
            repair_log=repair_log,
            attestation_history=attestation,
            benchmark_signatures=benchmarks,
            **data,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "MachinePassport":
        return cls.from_dict(json.loads(json_str))

    def compute_passport_hash(self) -> str:
        """
        Compute an immutable hash of the passport for on-chain anchoring.
        Excludes mutable fields (updated_at) for stability.
        """
        canonical = {
            "machine_id": self.machine_id,
            "name": self.name,
            "manufacture_year": self.manufacture_year,
            "architecture": self.architecture,
            "cpu_model": self.cpu_model,
            "rom_hash": self.rom_hash,
            "repair_log": [r.to_dict() for r in self.repair_log],
            "benchmark_signatures": [b.to_dict() for b in self.benchmark_signatures],
        }
        blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def add_repair(self, date: str, description: str, **kwargs) -> None:
        """Add a repair/maintenance entry."""
        self.repair_log.append(RepairEntry(date=date, description=description, **kwargs))
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def add_benchmark(self, signature: BenchmarkSignature) -> None:
        """Add a benchmark snapshot."""
        if not signature.collected_at:
            signature.collected_at = datetime.utcnow().isoformat() + "Z"
        self.benchmark_signatures.append(signature)
        self.updated_at = datetime.utcnow().isoformat() + "Z"

    def hardware_age(self) -> int:
        """Calculate hardware age in years."""
        if self.manufacture_year:
            return datetime.utcnow().year - self.manufacture_year
        return 0

    def tier(self) -> str:
        """Determine hardware tier based on age."""
        age = self.hardware_age()
        if age >= 30:
            return "ancient"
        elif age >= 25:
            return "sacred"
        elif age >= 20:
            return "vintage"
        elif age >= 15:
            return "classic"
        elif age >= 10:
            return "retro"
        elif age >= 5:
            return "modern"
        return "recent"


# ── Passport Ledger (Storage) ────────────────────────────────────

class PassportLedger:
    """
    Persistent storage for Machine Passports.
    File-based JSON storage with SQLite-ready schema.
    """

    def __init__(self, data_dir: str = ""):
        self.data_dir = Path(data_dir or os.environ.get("PASSPORT_DATA_DIR", "/tmp/passport-ledger"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.data_dir / "index.json"
        self._index: Dict[str, str] = {}  # machine_id → filename
        self._load_index()

    def _load_index(self):
        if self._index_file.exists():
            try:
                self._index = json.loads(self._index_file.read_text())
            except (json.JSONDecodeError, KeyError):
                self._index = {}

    def _save_index(self):
        self._index_file.write_text(json.dumps(self._index, indent=2))

    def save(self, passport: MachinePassport) -> str:
        """Save a passport to disk. Returns the passport hash."""
        filename = f"{passport.machine_id}.json"
        filepath = self.data_dir / filename
        filepath.write_text(passport.to_json())
        self._index[passport.machine_id] = filename
        self._save_index()
        return passport.compute_passport_hash()

    def get(self, machine_id: str) -> Optional[MachinePassport]:
        """Retrieve a passport by machine_id."""
        filename = self._index.get(machine_id)
        if not filename:
            return None
        filepath = self.data_dir / filename
        if not filepath.exists():
            return None
        return MachinePassport.from_json(filepath.read_text())

    def list_all(self) -> List[str]:
        """List all machine IDs in the ledger."""
        return list(self._index.keys())

    def search(self, architecture: str = "", name: str = "") -> List[MachinePassport]:
        """Search passports by architecture or name."""
        results = []
        for mid in self._index:
            passport = self.get(mid)
            if not passport:
                continue
            if architecture and passport.architecture.lower() != architecture.lower():
                continue
            if name and name.lower() not in passport.name.lower():
                continue
            results.append(passport)
        return results

    def delete(self, machine_id: str) -> bool:
        """Delete a passport."""
        filename = self._index.pop(machine_id, None)
        if not filename:
            return False
        filepath = self.data_dir / filename
        if filepath.exists():
            filepath.unlink()
        self._save_index()
        return True

    @property
    def count(self) -> int:
        return len(self._index)
