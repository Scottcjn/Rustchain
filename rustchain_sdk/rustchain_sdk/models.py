# -*- coding: utf-8 -*-
"""
RustChain Python SDK - Data Models
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

@dataclass
class Epoch:
    number: int
    start_block: int
    end_block: int
    total_rewards: float
    miners_count: int
    settled_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Epoch":
        return cls(
            number=d.get("epoch_number", d.get("number", 0)),
            start_block=d.get("start_block", 0),
            end_block=d.get("end_block", 0),
            total_rewards=float(d.get("total_rewards", 0)),
            miners_count=d.get("miners_count", 0),
            settled_at=d.get("settled_at")
        )

@dataclass
class Miner:
    miner_id: str
    architecture: str
    hashrate: float
    attestation_score: float
    last_seen: str
    wallet: Optional[str] = None
    version: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Miner":
        return cls(
            miner_id=d.get("miner_id", ""),
            architecture=d.get("architecture", ""),
            hashrate=float(d.get("hashrate", 0)),
            attestation_score=float(d.get("attestation_score", 0)),
            last_seen=d.get("last_seen", ""),
            wallet=d.get("wallet"),
            version=d.get("version")
        )

@dataclass
class Wallet:
    wallet_id: str
    balance: float
    locked: float = 0.0
    pending: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "Wallet":
        return cls(
            wallet_id=d.get("wallet_id", ""),
            balance=float(d.get("balance", 0)),
            locked=float(d.get("locked", 0)),
            pending=float(d.get("pending", 0))
        )

@dataclass
class Transaction:
    tx_hash: str
    from_wallet: str
    to_wallet: str
    amount: float
    timestamp: str
    status: str
    block: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(
            tx_hash=d.get("tx_hash", ""),
            from_wallet=d.get("from", d.get("from_wallet", "")),
            to_wallet=d.get("to", d.get("to_wallet", "")),
            amount=float(d.get("amount", 0)),
            timestamp=d.get("timestamp", ""),
            status=d.get("status", ""),
            block=d.get("block_number")
        )

@dataclass
class Block:
    number: int
    hash: str
    timestamp: str
    miner: str
    tx_count: int
    attestations: int
    size_bytes: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(
            number=d.get("block_number", d.get("number", 0)),
            hash=d.get("hash", ""),
            timestamp=d.get("timestamp", ""),
            miner=d.get("miner", ""),
            tx_count=d.get("tx_count", 0),
            attestations=d.get("attestations", 0),
            size_bytes=d.get("size_bytes")
        )

@dataclass
class Attestation:
    miner_id: str
    score: float
    fingerprint: str
    status: str
    last_attestation: str
    architecture: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Attestation":
        return cls(
            miner_id=d.get("miner_id", ""),
            score=float(d.get("score", 0)),
            fingerprint=d.get("fingerprint", ""),
            status=d.get("status", ""),
            last_attestation=d.get("last_attestation", ""),
            architecture=d.get("architecture")
        )
