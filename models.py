"""Pydantic models for RustChain API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Node health check response."""

    status: str = Field(description="Node health status (e.g. 'ok', 'degraded')")
    version: str | None = Field(default=None, description="Node software version")
    timestamp: datetime | None = Field(default=None, description="Server timestamp")


class EpochInfo(BaseModel):
    """Current epoch information."""

    epoch: int = Field(description="Epoch number")
    start_block: int = Field(description="First block in this epoch")
    end_block: int = Field(description="Last block in this epoch")
    start_time: datetime | None = Field(default=None, description="Epoch start time")
    end_time: datetime | None = Field(default=None, description="Epoch end time (estimated)")


class Miner(BaseModel):
    """A mining node on the RustChain network."""

    miner_id: str = Field(description="Unique miner identifier")
    wallet_id: str = Field(description="Wallet address of the miner")
    status: str = Field(description="Miner status (active/inactive/banned)")
    power: int = Field(description="Mining power / hashrate")
    rewards: float = Field(description="Total accumulated rewards")
    joined_at: datetime | None = Field(default=None, description="When miner joined")


class MinerListResponse(BaseModel):
    """Response when listing miners."""

    miners: list[Miner] = Field(description="List of miners")
    total: int = Field(description="Total number of miners")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Results per page")


class BalanceResponse(BaseModel):
    """Wallet balance response."""

    wallet_id: str = Field(description="Wallet address")
    balance: float = Field(description="RTC balance")
    locked: float = Field(default=0.0, description="Locked / staked balance")
    updated_at: datetime | None = Field(default=None, description="Last update time")


class TransferRequest(BaseModel):
    """Request body for a signed transfer."""

    from_wallet: str = Field(description="Sender wallet address")
    to_wallet: str = Field(description="Recipient wallet address")
    amount: float = Field(description="Amount to transfer")
    signature: str = Field(description="Base64-encoded Ed25519 signature")
    nonce: int | None = Field(default=None, description="Transaction nonce")


class TransferResponse(BaseModel):
    """Response from a transfer submission."""

    tx_hash: str = Field(description="Transaction hash")
    from_wallet: str = Field(description="Sender wallet")
    to_wallet: str = Field(description="Recipient wallet")
    amount: float = Field(description="Amount transferred")
    fee: float = Field(description="Transaction fee")
    status: str = Field(description="Transaction status")
    block: int | None = Field(default=None, description="Block number if confirmed")
    timestamp: datetime | None = Field(default=None, description="Transaction timestamp")


class AttestationStatus(BaseModel):
    """Attestation status for a miner."""

    miner_id: str = Field(description="Miner identifier")
    attested: bool = Field(description="Whether the miner is currently attested")
    attestations_count: int = Field(
        default=0, description="Number of attestations performed"
    )
    last_attested_at: datetime | None = Field(
        default=None, description="Last attestation time"
    )
    score: float = Field(default=0.0, description="Attestation score (0-100)")


class Block(BaseModel):
    """A block on the RustChain blockchain."""

    hash: str = Field(description="Block hash")
    height: int = Field(description="Block height / number")
    timestamp: datetime | None = Field(default=None, description="Block timestamp")
    miner_id: str | None = Field(default=None, description="Miner who produced the block")
    tx_count: int = Field(default=0, description="Number of transactions in block")
    size: int | None = Field(default=None, description="Block size in bytes")
    parent_hash: str | None = Field(default=None, description="Parent block hash")


class BlockListResponse(BaseModel):
    """Response when listing blocks."""

    blocks: list[Block] = Field(description="List of blocks")
    total: int = Field(description="Total number of blocks")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Results per page")


class Transaction(BaseModel):
    """A transaction on the RustChain blockchain."""

    tx_hash: str = Field(description="Transaction hash")
    from_wallet: str = Field(description="Sender wallet address")
    to_wallet: str | None = Field(default=None, description="Recipient wallet address")
    amount: float = Field(description="Transaction amount")
    fee: float = Field(description="Transaction fee")
    status: str = Field(description="Transaction status (pending/confirmed/failed)")
    block: int | None = Field(default=None, description="Block number if confirmed")
    timestamp: datetime | None = Field(default=None, description="Transaction timestamp")
    type: str = Field(default="transfer", description="Transaction type")


class TransactionListResponse(BaseModel):
    """Response when listing transactions."""

    transactions: list[Transaction] = Field(description="List of transactions")
    total: int = Field(description="Total number of transactions")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Results per page")


class ExplorerModels:
    """Namespace marker for explorer-related models."""

    Block = Block
    BlockListResponse = BlockListResponse
    Transaction = Transaction
    TransactionListResponse = TransactionListResponse
