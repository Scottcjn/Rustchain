"""Pydantic models for RustChain API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Node health check response."""
    status: str
    version: Optional[str] = None
    uptime: Optional[float] = None
    node_id: Optional[str] = Field(None, alias="nodeId")
    peers: Optional[int] = None

    model_config = {"populate_by_name": True}


class Epoch(BaseModel):
    """Current epoch information."""
    epoch_number: int = Field(alias="epochNumber")
    start_time: Optional[str] = Field(None, alias="startTime")
    end_time: Optional[str] = Field(None, alias="endTime")
    active_miners: Optional[int] = Field(None, alias="activeMiners")
    total_rtc_mined: Optional[float] = Field(None, alias="totalRtcMined")
    status: Optional[str] = None

    model_config = {"populate_by_name": True}


class Miner(BaseModel):
    """Active miner information."""
    miner_id: str = Field(alias="minerId")
    wallet: Optional[str] = None
    device_family: Optional[str] = Field(None, alias="deviceFamily")
    device_arch: Optional[str] = Field(None, alias="deviceArch")
    antiquity_multiplier: Optional[float] = Field(None, alias="antiquityMultiplier")
    last_attestation: Optional[str] = Field(None, alias="lastAttestation")
    total_epochs: Optional[int] = Field(None, alias="totalEpochs")
    status: Optional[str] = None

    model_config = {"populate_by_name": True}


class Balance(BaseModel):
    """Wallet balance response."""
    wallet_id: str = Field(alias="walletId")
    balance: float
    pending: Optional[float] = 0.0
    last_updated: Optional[str] = Field(None, alias="lastUpdated")

    model_config = {"populate_by_name": True}


class AttestationStatus(BaseModel):
    """Miner attestation status."""
    miner_id: str = Field(alias="minerId")
    attested: bool
    last_attestation: Optional[str] = Field(None, alias="lastAttestation")
    consecutive_epochs: Optional[int] = Field(None, alias="consecutiveEpochs")
    hardware_verified: Optional[bool] = Field(None, alias="hardwareVerified")

    model_config = {"populate_by_name": True}


class Block(BaseModel):
    """Block data from the explorer."""
    block_number: int = Field(alias="blockNumber")
    hash: Optional[str] = None
    timestamp: Optional[str] = None
    miner: Optional[str] = None
    transactions: Optional[int] = 0
    rtc_reward: Optional[float] = Field(None, alias="rtcReward")

    model_config = {"populate_by_name": True}


class Transaction(BaseModel):
    """Transaction data from the explorer."""
    tx_hash: str = Field(alias="txHash")
    from_wallet: Optional[str] = Field(None, alias="from")
    to_wallet: Optional[str] = Field(None, alias="to")
    amount: Optional[float] = None
    timestamp: Optional[str] = None
    block_number: Optional[int] = Field(None, alias="blockNumber")
    tx_type: Optional[str] = Field(None, alias="type")

    model_config = {"populate_by_name": True}


class TransferResult(BaseModel):
    """Result of a signed transfer."""
    tx_hash: str = Field(alias="txHash")
    status: str
    amount: float
    from_wallet: str = Field(alias="from")
    to_wallet: str = Field(alias="to")

    model_config = {"populate_by_name": True}
