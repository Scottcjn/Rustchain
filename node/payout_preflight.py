"""
RustChain Wallet Transfer Preflight Validation
===============================================

Validates POST /wallet/transfer and /wallet/transfer/signed payloads
before processing. Returns structured error codes for client feedback.

Usage:
    from payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed
    
    # Admin transfer validation
    result = validate_wallet_transfer_admin({
        "from_miner": "n64-scott-unit1",
        "to_miner": "n64-scott-unit2",
        "amount_rtc": 100.5
    })
    
    if result.ok:
        print(f"Valid: {result.details}")
    else:
        print(f"Error: {result.error}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class PreflightResult:
    """
    Result of preflight validation.
    
    Attributes:
        ok: True if validation passed, False otherwise
        error: Error code string (empty if ok=True)
        details: Validation details or error context
    """
    ok: bool
    error: str
    details: Dict[str, Any]


def _as_dict(payload: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    """Convert payload to dict or return error."""
    if not isinstance(payload, dict):
        return None, "invalid_json_body"
    return payload, ""


def _safe_float(v: Any) -> Tuple[Optional[float], str]:
    """
    Safely convert a value to float with error handling.
    
    Args:
        v: Value to convert (can be string, int, float, or None)
        
    Returns:
        Tuple[Optional[float], str]: (value, error_code)
            - (float, ""): Success - valid finite float
            - (None, "amount_not_number"): Conversion failed (TypeError/ValueError)
            - (None, "amount_not_finite"): Value is inf or nan
            
    Use case:
        Validates amount fields in wallet transfer payloads
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None, "amount_not_number"
    if not math.isfinite(f):
        return None, "amount_not_finite"
    return f, ""


def validate_wallet_transfer_admin(payload: Any) -> PreflightResult:
    """
    Validate POST /wallet/transfer payload shape for admin-initiated transfers.
    
    Checks that the payload contains required fields (from_miner, to_miner, amount_rtc)
    and validates the amount is positive and can be quantized to micro-RTC (6 decimals).
    
    Args:
        payload: Request body dictionary containing:
            - from_miner: Source miner identifier (non-empty string)
            - to_miner: Destination miner identifier (non-empty string)
            - amount_rtc: Amount in RTC (positive number, min 0.000001)
            
    Returns:
        PreflightResult: Validation result with:
            - ok=True: details contains validated from_miner, to_miner, amount_rtc, amount_i64
            - ok=False: error code and empty details
            
    Error Codes:
        - invalid_json_body: Payload is not a dictionary
        - missing_from_or_to: from_miner or to_miner missing/empty
        - amount_not_number: amount_rtc cannot be converted to float
        - amount_not_finite: amount_rtc is inf or nan
        - amount_must_be_positive: amount_rtc <= 0
        - amount_too_small_after_quantization: amount rounds to 0 micro-RTC
        
    Example:
        >>> result = validate_wallet_transfer_admin({
        ...     "from_miner": "n64-scott-unit1",
        ...     "to_miner": "n64-scott-unit2",
        ...     "amount_rtc": 100.5
        ... })
        >>> result.ok
        True
        >>> result.details["amount_i64"]
        100500000
    """
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    from_miner = data.get("from_miner")
    to_miner = data.get("to_miner")
    amount_rtc, aerr = _safe_float(data.get("amount_rtc", 0))

    if not from_miner or not to_miner:
        return PreflightResult(ok=False, error="missing_from_or_to", details={})
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64 = int(amount_rtc * 1_000_000)
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": amount_rtc, "min_rtc": 0.000001},
        )

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_miner": str(from_miner),
            "to_miner": str(to_miner),
            "amount_rtc": amount_rtc,
            "amount_i64": amount_i64,
        },
    )


def validate_wallet_transfer_signed(payload: Any) -> PreflightResult:
    """
    Validate POST /wallet/transfer/signed payload shape for client-signed transfers.
    
    Validates all required fields for a signed wallet transfer including address format,
    amount, nonce, and signature. Does NOT verify the cryptographic signature itself -
    that should be done separately after preflight validation passes.
    
    Args:
        payload: Request body dictionary containing:
            - from_address: Source wallet address (format: RTC + 40 hex chars)
            - to_address: Destination wallet address (format: RTC + 40 hex chars)
            - amount_rtc: Amount in RTC (positive number, min 0.000001)
            - nonce: Transaction nonce (positive integer)
            - signature: Ed25519 signature (hex string)
            - public_key: Signer's public key (hex string)
            
    Returns:
        PreflightResult: Validation result with:
            - ok=True: details contains validated fields
            - ok=False: error code and details with context
            
    Error Codes:
        - invalid_json_body: Payload is not a dictionary
        - missing_required_fields: One or more required fields missing (listed in details)
        - amount_not_number/amount_not_finite: Amount validation failed
        - amount_must_be_positive: amount_rtc <= 0
        - amount_too_small_after_quantization: amount rounds to 0 micro-RTC
        - invalid_from_address_format: from_address doesn't match RTC + 40 hex pattern
        - invalid_to_address_format: to_address doesn't match RTC + 40 hex pattern
        - from_to_must_differ: Source and destination addresses are identical
        - nonce_not_int: Nonce cannot be converted to integer
        - nonce_must_be_gt_zero: Nonce <= 0
        
    Example:
        >>> result = validate_wallet_transfer_signed({
        ...     "from_address": "RTC" + "a" * 40,
        ...     "to_address": "RTC" + "b" * 40,
        ...     "amount_rtc": 50.0,
        ...     "nonce": 1,
        ...     "signature": "deadbeef" * 8,
        ...     "public_key": "cafe" * 16
        ... })
        >>> result.ok
        True
    """
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    required = ["from_address", "to_address", "amount_rtc", "nonce", "signature", "public_key"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return PreflightResult(ok=False, error="missing_required_fields", details={"missing": missing})

    from_address = str(data.get("from_address", "")).strip()
    to_address = str(data.get("to_address", "")).strip()
    amount_rtc, aerr = _safe_float(data.get("amount_rtc", 0))
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64 = int(amount_rtc * 1_000_000)
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": amount_rtc, "min_rtc": 0.000001},
        )

    if not (from_address.startswith("RTC") and len(from_address) == 43):
        return PreflightResult(ok=False, error="invalid_from_address_format", details={})
    if not (to_address.startswith("RTC") and len(to_address) == 43):
        return PreflightResult(ok=False, error="invalid_to_address_format", details={})
    if from_address == to_address:
        return PreflightResult(ok=False, error="from_to_must_differ", details={})

    try:
        nonce_int = int(str(data.get("nonce")))
    except (TypeError, ValueError):
        return PreflightResult(ok=False, error="nonce_not_int", details={})
    if nonce_int <= 0:
        return PreflightResult(ok=False, error="nonce_must_be_gt_zero", details={})

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

