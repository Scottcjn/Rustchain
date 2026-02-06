from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class NodeHealth:
    ok: bool
    version: str
    uptime_s: int
    db_rw: bool
    backup_age_hours: float
    tip_age_slots: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeHealth':
        return cls(
            ok=data.get("ok", False),
            version=data.get("version", "unknown"),
            uptime_s=data.get("uptime_s", 0),
            db_rw=data.get("db_rw", False),
            backup_age_hours=data.get("backup_age_hours", 0.0),
            tip_age_slots=data.get("tip_age_slots", 0)
        )

@dataclass
class EpochInfo:
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EpochInfo':
        return cls(
            epoch=data.get("epoch", 0),
            slot=data.get("slot", 0),
            blocks_per_epoch=data.get("blocks_per_epoch", 144),
            epoch_pot=data.get("epoch_pot", 0.0),
            enrolled_miners=data.get("enrolled_miners", 0)
        )

@dataclass
class MinerInfo:
    miner: str
    device_family: str
    device_arch: str
    hardware_type: str
    antiquity_multiplier: float
    entropy_score: float
    last_attest: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MinerInfo':
        return cls(
            miner=data.get("miner", ""),
            device_family=data.get("device_family", ""),
            device_arch=data.get("device_arch", ""),
            hardware_type=data.get("hardware_type", ""),
            antiquity_multiplier=data.get("antiquity_multiplier", 1.0),
            entropy_score=data.get("entropy_score", 0.0),
            last_attest=data.get("last_attest", 0)
        )

@dataclass
class WalletBalance:
    miner_id: str
    amount_rtc: float
    amount_i64: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WalletBalance':
        return cls(
            miner_id=data.get("miner_id", ""),
            amount_rtc=data.get("amount_rtc", 0.0),
            amount_i64=data.get("amount_i64", 0)
        )

@dataclass
class TransferResult:
    success: bool
    tx_hash: Optional[str] = None
    new_balance: Optional[int] = None
    error: Optional[str] = None
    detail: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TransferResult':
        return cls(
            success=data.get("success", False),
            tx_hash=data.get("tx_hash"),
            new_balance=data.get("new_balance"),
            error=data.get("error"),
            detail=data.get("detail")
        )

@dataclass
class AttestChallenge:
    nonce: str
    expires_at: int
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttestChallenge':
        return cls(
            nonce=data.get("nonce", ""),
            expires_at=data.get("expires_at", 0)
        )

@dataclass
class AttestResult:
    success: bool
    enrolled: bool = False
    epoch: Optional[int] = None
    multiplier: Optional[float] = None
    next_settlement_slot: Optional[int] = None
    error: Optional[str] = None
    check_failed: Optional[str] = None
    detail: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttestResult':
        return cls(
            success=data.get("success", False),
            enrolled=data.get("enrolled", False),
            epoch=data.get("epoch"),
            multiplier=data.get("multiplier"),
            next_settlement_slot=data.get("next_settlement_slot"),
            error=data.get("error"),
            check_failed=data.get("check_failed"),
            detail=data.get("detail")
        )
