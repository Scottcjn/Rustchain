from dataclasses import dataclass
from typing import List, Optional

@dataclass
class HealthStatus:
    ok: bool
    version: str
    uptime_s: int
    db_rw: bool
    backup_age_hours: float
    tip_age_slots: int

@dataclass
class EpochInfo:
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int

@dataclass
class MinerInfo:
    miner: str
    device_family: str
    device_arch: str
    hardware_type: str
    antiquity_multiplier: float
    entropy_score: float
    last_attest: int

@dataclass
class Balance:
    miner_id: str
    amount_rtc: float
    amount_i64: int

@dataclass
class TransferResponse:
    success: bool
    tx_hash: Optional[str] = None
    new_balance: Optional[int] = None
    error: Optional[str] = None

@dataclass
class AttestationResponse:
    success: bool
    enrolled: bool = False
    epoch: Optional[int] = None
    multiplier: Optional[float] = None
    next_settlement_slot: Optional[int] = None
    error: Optional[str] = None
    detail: Optional[str] = None
