"""
models.py — Rent-a-Relic data models, machine registry, and Ed25519 signing helpers.

Machines are vintage compute nodes with verified hardware attestation.
Each machine carries a hardware passport used for provenance receipt signing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReservationStatus(str, Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    COMPLETED = "completed"
    EXPIRED   = "expired"
    CANCELLED = "cancelled"


class EscrowStatus(str, Enum):
    LOCKED   = "locked"
    RELEASED = "released"
    REFUNDED = "refunded"


# Allowed rental durations in hours
VALID_DURATIONS_HOURS = {1, 4, 24}

# RTC rate per hour per machine (can be overridden per machine)
DEFAULT_RTC_PER_HOUR = 5.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Machine:
    """Vintage compute node registered in the Rent-a-Relic marketplace."""
    machine_id: str
    name: str
    arch: str          # e.g. "ppc32", "sparc64", "alpha", "x86_68k"
    year: int          # year of manufacture / peak era
    cpu_model: str
    ram_mb: int
    os: str
    ssh_endpoint: str  # host:port
    photo_url: str
    attestation_count: int = 0
    rtc_per_hour: float = DEFAULT_RTC_PER_HOUR
    available: bool = True

    # Ed25519 key pair for this machine (generated at startup if not seeded)
    _private_key: Optional[Ed25519PrivateKey] = field(default=None, repr=False)
    _public_key_bytes: Optional[bytes] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._private_key is None:
            self._private_key = Ed25519PrivateKey.generate()
        pub = self._private_key.public_key()
        self._public_key_bytes = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def sign(self, data: bytes) -> bytes:
        """Sign bytes with this machine's Ed25519 key."""
        assert self._private_key is not None
        return self._private_key.sign(data)

    def passport_id(self) -> str:
        """Deterministic passport ID derived from public key."""
        return self._public_key_bytes.hex()[:32] if self._public_key_bytes else ""

    def public_key_hex(self) -> str:
        return self._public_key_bytes.hex() if self._public_key_bytes else ""

    def to_dict(self) -> dict:
        return {
            "machine_id":        self.machine_id,
            "name":              self.name,
            "arch":              self.arch,
            "year":              self.year,
            "cpu_model":         self.cpu_model,
            "ram_mb":            self.ram_mb,
            "os":                self.os,
            "ssh_endpoint":      self.ssh_endpoint,
            "photo_url":         self.photo_url,
            "attestation_count": self.attestation_count,
            "rtc_per_hour":      self.rtc_per_hour,
            "available":         self.available,
            "passport_id":       self.passport_id(),
            "public_key_hex":    self.public_key_hex(),
        }


@dataclass
class Reservation:
    """A rental session binding an agent to a machine."""
    session_id: str
    machine_id: str
    agent_id: str
    duration_hours: int       # must be in VALID_DURATIONS_HOURS
    rtc_amount: float
    status: ReservationStatus = ReservationStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    expires_at: Optional[float] = None
    completed_at: Optional[float] = None
    output_hash: Optional[str] = None   # SHA-256 of session output

    def activate(self) -> None:
        now = time.time()
        self.status     = ReservationStatus.ACTIVE
        self.started_at = now
        self.expires_at = now + self.duration_hours * 3600

    def complete(self, output_hash: str) -> None:
        self.status       = ReservationStatus.COMPLETED
        self.completed_at = time.time()
        self.output_hash  = output_hash

    def expire(self) -> None:
        self.status       = ReservationStatus.EXPIRED
        self.completed_at = time.time()

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "session_id":     self.session_id,
            "machine_id":     self.machine_id,
            "agent_id":       self.agent_id,
            "duration_hours": self.duration_hours,
            "rtc_amount":     self.rtc_amount,
            "status":         self.status.value,
            "created_at":     self.created_at,
            "started_at":     self.started_at,
            "expires_at":     self.expires_at,
            "completed_at":   self.completed_at,
            "output_hash":    self.output_hash,
        }


@dataclass
class Receipt:
    """Signed provenance receipt for a completed or active session."""
    receipt_id: str
    session_id: str
    machine_passport_id: str
    agent_id: str
    machine_id: str
    duration_hours: int
    output_hash: str
    attestation_proof: str   # hex-encoded attestation chain digest
    ed25519_signature: str   # hex-encoded signature over canonical fields
    public_key_hex: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EscrowTransaction:
    """RTC escrow lifecycle record."""
    escrow_id: str
    session_id: str
    agent_id: str
    machine_id: str
    amount: float
    status: EscrowStatus = EscrowStatus.LOCKED
    locked_at: float = field(default_factory=time.time)
    released_at: Optional[float] = None
    release_reason: Optional[str] = None   # "completed" | "timeout" | "cancelled"

    def release(self, reason: str) -> None:
        self.status         = EscrowStatus.RELEASED
        self.released_at    = time.time()
        self.release_reason = reason

    def refund(self) -> None:
        self.status         = EscrowStatus.REFUNDED
        self.released_at    = time.time()
        self.release_reason = "refunded"

    def to_dict(self) -> dict:
        return {
            "escrow_id":      self.escrow_id,
            "session_id":     self.session_id,
            "agent_id":       self.agent_id,
            "machine_id":     self.machine_id,
            "amount":         self.amount,
            "status":         self.status.value,
            "locked_at":      self.locked_at,
            "released_at":    self.released_at,
            "release_reason": self.release_reason,
        }


# ---------------------------------------------------------------------------
# Machine Registry — vintage hardware catalogue
# ---------------------------------------------------------------------------

def _make_machine(
    mid: str,
    name: str,
    arch: str,
    year: int,
    cpu: str,
    ram: int,
    os: str,
    ssh: str,
    photo: str,
    attest: int = 0,
    rtc: float = DEFAULT_RTC_PER_HOUR,
) -> Machine:
    return Machine(
        machine_id=mid,
        name=name,
        arch=arch,
        year=year,
        cpu_model=cpu,
        ram_mb=ram,
        os=os,
        ssh_endpoint=ssh,
        photo_url=photo,
        attestation_count=attest,
        rtc_per_hour=rtc,
    )


MACHINE_REGISTRY: dict[str, Machine] = {m.machine_id: m for m in [
    _make_machine(
        "g3-beige",    "Power Mac G3 (Beige)", "ppc32",   1998,
        "PowerPC 750 @ 300 MHz",    128,  "Mac OS X 10.2",
        "relics.rustchain.net:2201",
        "https://assets.rustchain.net/relics/g3_beige.jpg",
        attest=47, rtc=4.0,
    ),
    _make_machine(
        "g4-quicksilver", "Power Mac G4 QuickSilver", "ppc32", 2001,
        "PowerPC 7450 (G4) @ 733 MHz", 512, "Mac OS X 10.4",
        "relics.rustchain.net:2202",
        "https://assets.rustchain.net/relics/g4_qs.jpg",
        attest=83, rtc=5.0,
    ),
    _make_machine(
        "g5-dual",     "Power Mac G5 Dual 2.0", "ppc64",   2004,
        "PowerPC 970 (G5) @ 2.0 GHz x 2", 4096, "Mac OS X 10.5",
        "relics.rustchain.net:2203",
        "https://assets.rustchain.net/relics/g5_dual.jpg",
        attest=112, rtc=8.0,
    ),
    _make_machine(
        "power8-ibm",  "IBM POWER8 E870", "ppc64le", 2014,
        "IBM POWER8 @ 4.0 GHz (10-core)",  65536, "Ubuntu 18.04 ppc64le",
        "relics.rustchain.net:2204",
        "https://assets.rustchain.net/relics/power8_e870.jpg",
        attest=201, rtc=15.0,
    ),
    _make_machine(
        "sparc-ultra",  "Sun Ultra 60", "sparc64", 1999,
        "UltraSPARC-II @ 450 MHz x 2", 1024, "Solaris 10",
        "relics.rustchain.net:2205",
        "https://assets.rustchain.net/relics/ultra60.jpg",
        attest=66, rtc=6.0,
    ),
    _make_machine(
        "alpha-ds20",  "Compaq AlphaServer DS20E", "alpha", 2000,
        "Alpha EV68 @ 667 MHz x 2",  2048, "Tru64 UNIX 5.1b",
        "relics.rustchain.net:2206",
        "https://assets.rustchain.net/relics/ds20e.jpg",
        attest=38, rtc=7.0,
    ),
    _make_machine(
        "amiga-68k",   "Amiga 3000T", "m68k",    1991,
        "Motorola 68040 @ 25 MHz", 8, "AmigaOS 3.9",
        "relics.rustchain.net:2207",
        "https://assets.rustchain.net/relics/amiga3000t.jpg",
        attest=22, rtc=3.0,
    ),
    _make_machine(
        "riscv-hifive", "SiFive HiFive Unmatched", "riscv64", 2021,
        "SiFive U74 @ 1.2 GHz (4-core)", 16384, "Ubuntu 21.04 RISC-V",
        "relics.rustchain.net:2208",
        "https://assets.rustchain.net/relics/hifive_unmatched.jpg",
        attest=155, rtc=10.0,
    ),
]}
