"""Data models with full type hints."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass(frozen=True)
class HealthStatus:
    status: str
    uptime: float
    version: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class EpochInfo:
    epoch: int
    start_time: str
    end_time: str
    miners_active: int
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class Miner:
    id: str
    wallet: str
    hardware: str
    score: float
    status: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class Balance:
    wallet_id: str
    balance: float
    currency: str = "RTC"
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class TransferResult:
    tx_hash: str
    from_wallet: str
    to_wallet: str
    amount: float
    status: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class AttestationStatus:
    miner_id: str
    attested: bool
    epoch: int
    hardware_hash: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class Block:
    height: int
    hash: str
    timestamp: str
    miner: str
    tx_count: int
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

@dataclass(frozen=True)
class Transaction:
    tx_hash: str
    from_wallet: str
    to_wallet: str
    amount: float
    block_height: int
    timestamp: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)
