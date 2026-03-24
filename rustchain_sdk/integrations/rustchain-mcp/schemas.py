#!/usr/bin/env python3
"""
RustChain MCP - Type Schemas

Typed dataclasses and Pydantic-like schemas for RustChain API responses.
Provides clear contracts for health, epoch, balance, and query endpoints.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HealthStatus:
    """Response from /api/health endpoint."""
    status: str
    timestamp: int
    service: str
    version: Optional[str] = None
    uptime_s: Optional[int] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status.lower() in ("ok", "healthy", "running")
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthStatus":
        """Create from API response dict."""
        return cls(
            status=data.get("status", data.get("ok", "unknown")),
            timestamp=data.get("timestamp", 0),
            service=data.get("service", "unknown"),
            version=data.get("version"),
            uptime_s=data.get("uptime_s"),
        )


@dataclass
class EpochInfo:
    """Response from /epoch endpoint."""
    epoch: int
    slot: int
    height: int
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    active_miners: Optional[int] = None
    total_rewards: Optional[float] = None
    status: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpochInfo":
        """Create from API response dict."""
        return cls(
            epoch=data.get("epoch", 0),
            slot=data.get("slot", 0),
            height=data.get("height", 0),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            active_miners=data.get("active_miners"),
            total_rewards=data.get("total_rewards"),
            status=data.get("status"),
        )


@dataclass
class WalletBalance:
    """Response from /wallet/balance endpoint."""
    miner_id: str
    amount_rtc: float
    amount_i64: int
    pending: Optional[float] = None
    staked: Optional[float] = None
    last_updated: Optional[int] = None
    
    @property
    def total_rtc(self) -> float:
        """Total balance including staked."""
        return self.amount_rtc + (self.staked or 0)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WalletBalance":
        """Create from API response dict."""
        return cls(
            miner_id=data.get("miner_id", data.get("wallet", "")),
            amount_rtc=data.get("amount_rtc", data.get("balance", 0)),
            amount_i64=data.get("amount_i64", data.get("balance_i64", 0)),
            pending=data.get("pending"),
            staked=data.get("staked"),
            last_updated=data.get("last_updated"),
        )


@dataclass
class QueryResult:
    """Generic query result for /api/query endpoint."""
    success: bool
    data: Any = field(default_factory=dict)
    error: Optional[str] = None
    count: Optional[int] = None
    query_type: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryResult":
        """Create from API response dict."""
        return cls(
            success=data.get("success", data.get("ok", False)),
            data=data.get("data", data.get("result", {})),
            error=data.get("error"),
            count=data.get("count"),
            query_type=data.get("query_type"),
        )


@dataclass
class MinerInfo:
    """Miner information from /api/miners endpoint."""
    miner_id: str
    wallet: str
    hardware: str
    score: float
    epochs_mined: int
    last_seen: int
    status: str
    antiquity_multiplier: Optional[float] = None
    last_attest: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MinerInfo":
        """Create from API response dict."""
        return cls(
            miner_id=data.get("miner_id", data.get("id", "")),
            wallet=data.get("wallet", ""),
            hardware=data.get("hardware", ""),
            score=data.get("score", 0),
            epochs_mined=data.get("epochs_mined", 0),
            last_seen=data.get("last_seen", 0),
            status=data.get("status", "unknown"),
            antiquity_multiplier=data.get("antiquity_multiplier"),
            last_attest=data.get("last_attest"),
        )


@dataclass
class NetworkStats:
    """Network statistics from /api/stats endpoint."""
    current_epoch: int
    total_miners: int
    active_miners: int
    total_supply: float
    network_hashrate: Optional[float] = None
    avg_block_time: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkStats":
        """Create from API response dict."""
        return cls(
            current_epoch=data.get("current_epoch", data.get("epoch", 0)),
            total_miners=data.get("total_miners", 0),
            active_miners=data.get("active_miners", 0),
            total_supply=data.get("total_supply", 0),
            network_hashrate=data.get("network_hashrate"),
            avg_block_time=data.get("avg_block_time"),
        )


@dataclass
class APIError(Exception):
    """Standardized API error."""
    code: str
    message: str
    status_code: int = 500
    details: Optional[dict[str, Any]] = None
    
    @classmethod
    def from_response(cls, status: int, body: dict[str, Any]) -> "APIError":
        """Create from API error response."""
        return cls(
            code=body.get("error", body.get("code", "UNKNOWN_ERROR")),
            message=body.get("message", body.get("error_description", "Unknown error")),
            status_code=status,
            details=body.get("details"),
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "error": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


# JSON Schema definitions for MCP tool input validation

HEALTH_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

EPOCH_SCHEMA = {
    "type": "object",
    "properties": {
        "epoch": {
            "type": "integer",
            "description": "Epoch number (optional, defaults to current)",
        },
    },
    "additionalProperties": False,
}

BALANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "miner_id": {
            "type": "string",
            "description": "Miner ID or wallet name",
        },
    },
    "required": ["miner_id"],
    "additionalProperties": False,
}

QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "query_type": {
            "type": "string",
            "description": "Type of query (e.g., 'miners', 'blocks', 'transactions')",
        },
        "params": {
            "type": "object",
            "description": "Query parameters",
            "additionalProperties": True,
        },
        "limit": {
            "type": "integer",
            "description": "Maximum results to return (default: 50)",
        },
    },
    "required": ["query_type"],
    "additionalProperties": False,
}
