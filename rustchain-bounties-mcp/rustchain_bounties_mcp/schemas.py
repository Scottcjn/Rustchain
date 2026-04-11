"""
RustChain Bounties MCP — Type Schemas

Typed dataclasses for all API responses from the RustChain node.
Maps directly to JSON returned by the Flask endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Health  (GET /health)
# ---------------------------------------------------------------------------

@dataclass
class HealthStatus:
    """Response from GET /health."""
    ok: bool
    version: str
    uptime_s: int
    db_rw: bool
    backup_age_hours: Optional[float] = None
    tip_age_slots: Optional[int] = None

    @property
    def is_healthy(self) -> bool:
        return self.ok and self.db_rw

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthStatus":
        return cls(
            ok=bool(data.get("ok", False)),
            version=data.get("version", "unknown"),
            uptime_s=int(data.get("uptime_s", 0)),
            db_rw=bool(data.get("db_rw", False)),
            backup_age_hours=data.get("backup_age_hours"),
            tip_age_slots=data.get("tip_age_slots"),
        )


# ---------------------------------------------------------------------------
# Epoch  (GET /epoch)
# ---------------------------------------------------------------------------

@dataclass
class EpochInfo:
    """Response from GET /epoch."""
    epoch: int
    slot: int
    epoch_pot: float
    enrolled_miners: int
    blocks_per_epoch: int
    total_supply_rtc: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpochInfo":
        return cls(
            epoch=int(data.get("epoch", 0)),
            slot=int(data.get("slot", 0)),
            epoch_pot=float(data.get("epoch_pot", 0)),
            enrolled_miners=int(data.get("enrolled_miners", 0)),
            blocks_per_epoch=int(data.get("blocks_per_epoch", 0)),
            total_supply_rtc=float(data.get("total_supply_rtc", 0)),
        )


# ---------------------------------------------------------------------------
# Balance  (GET /wallet/balance?miner_id=…)
# ---------------------------------------------------------------------------

@dataclass
class WalletBalance:
    """Response from GET /wallet/balance."""
    miner_id: str
    amount_i64: int
    amount_rtc: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WalletBalance":
        return cls(
            miner_id=data.get("miner_id", ""),
            amount_i64=int(data.get("amount_i64", 0)),
            amount_rtc=float(data.get("amount_rtc", 0)),
        )


# ---------------------------------------------------------------------------
# Miner  (GET /api/miners)
# ---------------------------------------------------------------------------

@dataclass
class MinerInfo:
    """Single miner entry from GET /api/miners."""
    miner: str
    last_attest: int
    device_family: str
    device_arch: str
    entropy_score: float
    antiquity_multiplier: float
    hardware_type: str
    first_attest: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MinerInfo":
        return cls(
            miner=data.get("miner", ""),
            last_attest=int(data.get("last_attest", 0)),
            device_family=data.get("device_family", "unknown"),
            device_arch=data.get("device_arch", "unknown"),
            entropy_score=float(data.get("entropy_score", 0)),
            antiquity_multiplier=float(data.get("antiquity_multiplier", 1.0)),
            hardware_type=data.get("hardware_type", "Unknown/Other"),
            first_attest=data.get("first_attest"),
        )


# ---------------------------------------------------------------------------
# Wallet Verification  (GET /wallet/balance?miner_id=… — wallet presence check)
# ---------------------------------------------------------------------------

@dataclass
class WalletVerifyResult:
    """Result of wallet verification via balance query.

    Note: The node does not expose a dedicated wallet-creation endpoint.
    Wallets are provisioned implicitly on first activity.  This result
    reflects whether a wallet row exists for the given miner_id.
    """
    wallet_address: str
    exists: bool
    balance_rtc: float
    message: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WalletVerifyResult":
        return cls(
            wallet_address=data.get("wallet_address", data.get("address", data.get("miner_id", ""))),
            exists=bool(data.get("exists", data.get("created", data.get("ok", False)))),
            balance_rtc=float(data.get("balance_rtc", data.get("amount_rtc", 0))),
            message=data.get("message", data.get("error", "")),
        )


# ---------------------------------------------------------------------------
# Attestation  (POST /attest/challenge  +  POST /attest/submit)
# ---------------------------------------------------------------------------

@dataclass
class AttestChallenge:
    """Response from POST /attest/challenge."""
    nonce: str
    expires_at: int
    server_time: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttestChallenge":
        return cls(
            nonce=data.get("nonce", ""),
            expires_at=int(data.get("expires_at", 0)),
            server_time=int(data.get("server_time", 0)),
        )


@dataclass
class AttestSubmitResult:
    """Response from POST /attest/submit."""
    ok: bool
    message: str
    miner_id: Optional[str] = None
    enrolled_epoch: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttestSubmitResult":
        return cls(
            ok=bool(data.get("ok", data.get("success", False))),
            message=data.get("message", data.get("error", "")),
            miner_id=data.get("miner_id"),
            enrolled_epoch=data.get("enrolled_epoch"),
        )


# ---------------------------------------------------------------------------
# Bounties  (GET /api/bounties  — from beacon / bounty registry)
# ---------------------------------------------------------------------------

@dataclass
class BountyInfo:
    """Single bounty entry."""
    issue_number: int
    title: str
    reward_rtc: float
    status: str
    url: Optional[str] = None
    description: Optional[str] = None
    difficulty: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BountyInfo":
        return cls(
            issue_number=int(data.get("issue_number", data.get("issue", 0))),
            title=data.get("title", ""),
            reward_rtc=float(data.get("reward_rtc", data.get("reward", 0))),
            status=data.get("status", "open"),
            url=data.get("url"),
            description=data.get("description"),
            difficulty=data.get("difficulty"),
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# API Error
# ---------------------------------------------------------------------------

@dataclass
class APIError(Exception):
    """Standardized API error."""
    code: str
    message: str
    status_code: int = 500
    details: Optional[dict[str, Any]] = None

    @classmethod
    def from_response(cls, status: int, body: Any) -> "APIError":
        if isinstance(body, dict):
            return cls(
                code=body.get("error", body.get("code", "UNKNOWN_ERROR")),
                message=body.get("message", body.get("error_description", str(body))),
                status_code=status,
                details=body.get("details"),
            )
        return cls(
            code="HTTP_ERROR",
            message=str(body),
            status_code=status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# MCP Tool Input Schemas (JSON Schema dicts)
# ---------------------------------------------------------------------------

HEALTH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

EPOCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

BALANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "miner_id": {"type": "string", "description": "Miner ID or wallet address"},
    },
    "required": ["miner_id"],
    "additionalProperties": False,
}

MINERS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "description": "Max miners to return (default 50)", "default": 50},
        "hardware_type": {"type": "string", "description": "Filter by hardware family (e.g. 'PowerPC')"},
    },
    "additionalProperties": False,
}

VERIFY_WALLET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "miner_id": {"type": "string", "description": "Miner ID to verify wallet for"},
    },
    "required": ["miner_id"],
    "additionalProperties": False,
}

ATTEST_CHALLENGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

SUBMIT_ATTESTATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "miner_id": {"type": "string", "description": "Miner identifier"},
        "device": {
            "type": "object",
            "description": "Device fingerprint dict (device_model, device_arch, cores, etc.)",
        },
        "nonce": {"type": "string", "description": "Challenge nonce from rustchain_attest_challenge"},
        "signature": {"type": "string", "description": "Ed25519 signature hex (optional)"},
        "public_key": {"type": "string", "description": "Signing public key hex (optional)"},
    },
    "required": ["miner_id", "device", "nonce"],
    "additionalProperties": False,
}

BOUNTIES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "description": "Filter by status: open, claimed, completed (default: open)"},
        "limit": {"type": "integer", "description": "Max results (default 50)", "default": 50},
    },
    "additionalProperties": False,
}
