from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    error: str
    details: Dict[str, Any]


def _as_dict(payload: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    if not isinstance(payload, dict):
        return None, "invalid_json_body"
    return payload, ""


def _safe_decimal(v: Any) -> Tuple[Optional[Decimal], str]:
    """Safely convert value to Decimal to avoid float precision issues."""
    try:
        # Convert to string first to ensure Decimal behavior matches intention
        d = Decimal(str(v))
    except (TypeError, ValueError, InvalidOperation):
        return None, "amount_not_number"
    if not d.is_finite():
        return None, "amount_not_finite"
    return d, ""


def validate_wallet_transfer_admin(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer payload shape (admin transfer)."""
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    from_miner = data.get("from_miner")
    to_miner = data.get("to_miner")
    amount_rtc_dec, aerr = _safe_decimal(data.get("amount_rtc", 0))

    if not from_miner or not to_miner:
        return PreflightResult(ok=False, error="missing_from_or_to", details={})
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc_dec is None or amount_rtc_dec <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    
    # Precise conversion to micro-RTC (1 RTC = 1,000,000 units)
    amount_i64 = int(amount_rtc_dec * Decimal("1000000"))
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": float(amount_rtc_dec), "min_rtc": 0.000001},
        )

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_miner": str(from_miner),
            "to_miner": str(to_miner),
            "amount_rtc": float(amount_rtc_dec),
            "amount_i64": amount_i64,
        },
    )


def is_valid_evm_address(address: str) -> bool:
    """Validate EVM (Ethereum/Base) address format."""
    import re
    return bool(re.match(r"^0x[a-fA-F0-9]{40}$", address))

def validate_wallet_transfer_signed(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer/signed payload shape (client-signed) with multi-chain support."""
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    required = ["from_address", "to_address", "amount_rtc", "nonce", "signature", "public_key"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return PreflightResult(ok=False, error="missing_required_fields", details={"missing": missing})

    from_address = str(data.get("from_address", "")).strip()
    to_address = str(data.get("to_address", "")).strip()
    chain = str(data.get("chain", "rustchain")).lower().strip()
    
    amount_rtc_dec, aerr = _safe_decimal(data.get("amount_rtc", 0))
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc_dec is None or amount_rtc_dec <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    
    amount_i64 = int(amount_rtc_dec * Decimal("1000000"))
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": float(amount_rtc_dec), "min_rtc": 0.000001},
        )

    # Chain-specific format validation
    if chain == "rustchain":
        if not (from_address.startswith("RTC") and len(from_address) == 43):
            return PreflightResult(ok=False, error="invalid_from_address_format", details={"chain": "rustchain"})
        if not (to_address.startswith("RTC") and len(to_address) == 43):
            return PreflightResult(ok=False, error="invalid_to_address_format", details={"chain": "rustchain"})
    elif chain in ("base", "ethereum"):
        if not is_valid_evm_address(from_address):
            return PreflightResult(ok=False, error="invalid_from_address_format", details={"chain": chain})
        if not is_valid_evm_address(to_address):
            return PreflightResult(ok=False, error="invalid_to_address_format", details={"chain": chain})
    
    if from_address == to_address:
        return PreflightResult(ok=False, error="from_to_must_differ", details={})

    try:
        nonce_int = int(str(data.get("nonce")))
    except (TypeError, ValueError):
        return PreflightResult(ok=False, error="nonce_not_int", details={})
    
    # FIX: Enforce a more reasonable range and positive value for nonces
    # and add support for potential timestamp-based nonces (milliseconds).
    if nonce_int <= 0:
        return PreflightResult(ok=False, error="nonce_must_be_gt_zero", details={})
    
    if nonce_int > 2**63 - 1: # Max signed 64-bit integer
        return PreflightResult(ok=False, error="nonce_too_large", details={})

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_address": from_address,
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "amount_i64": amount_i64,
            "nonce": nonce_int,
        },
    )

