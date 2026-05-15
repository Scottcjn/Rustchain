from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, Optional, Tuple


MICRO_RTC = Decimal("1000000")


def _is_rtc_address(value: str) -> bool:
    return value.startswith("RTC") and len(value) == 43


def _is_bcn_address(value: str) -> bool:
    return value.startswith("bcn_") and len(value) >= 8


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
    try:
        amount = Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None, "amount_not_number"
    if not amount.is_finite():
        return None, "amount_not_finite"
    return amount, ""


def _amount_i64(amount_rtc: Decimal) -> int:
    return int((amount_rtc * MICRO_RTC).to_integral_value(rounding=ROUND_DOWN))


def _is_missing_required(data: Dict[str, Any], key: str) -> bool:
    return key not in data or data.get(key) is None or data.get(key) == ""


def validate_wallet_transfer_admin(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer payload shape (admin transfer)."""
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    from_miner = data.get("from_miner")
    to_miner = data.get("to_miner")
    amount_rtc, aerr = _safe_decimal(data.get("amount_rtc", 0))

    if not from_miner or not to_miner:
        return PreflightResult(ok=False, error="missing_from_or_to", details={})
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64 = _amount_i64(amount_rtc)
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": float(amount_rtc), "min_rtc": 0.000001},
        )

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_miner": str(from_miner),
            "to_miner": str(to_miner),
            "amount_rtc": float(amount_rtc),
            "amount_i64": amount_i64,
        },
    )


def validate_wallet_transfer_signed(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer/signed payload shape (client-signed)."""
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    required = ["from_address", "to_address", "amount_rtc", "nonce", "signature"]
    missing = [k for k in required if _is_missing_required(data, k)]
    if missing:
        return PreflightResult(ok=False, error="missing_required_fields", details={"missing": missing})

    from_address = str(data.get("from_address", "")).strip()
    to_address = str(data.get("to_address", "")).strip()
    amount_rtc, aerr = _safe_decimal(data.get("amount_rtc", 0))
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64 = _amount_i64(amount_rtc)
    if amount_i64 <= 0:
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": float(amount_rtc), "min_rtc": 0.000001},
        )

    if not (_is_rtc_address(from_address) or _is_bcn_address(from_address)):
        return PreflightResult(ok=False, error="invalid_from_address_format", details={})
    if not (_is_rtc_address(to_address) or _is_bcn_address(to_address)):
        return PreflightResult(ok=False, error="invalid_to_address_format", details={})
    if from_address == to_address:
        return PreflightResult(ok=False, error="from_to_must_differ", details={})
    if _is_rtc_address(from_address) and _is_missing_required(data, "public_key"):
        return PreflightResult(ok=False, error="missing_required_fields", details={"missing": ["public_key"]})

    try:
        nonce_int = int(str(data.get("nonce")))
    except (TypeError, ValueError):
        return PreflightResult(ok=False, error="nonce_not_int", details={})
    if nonce_int <= 0:
        return PreflightResult(ok=False, error="nonce_must_be_gt_zero", details={})

    chain_id = str(data.get("chain_id", "")).strip()
    if chain_id and not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", chain_id):
        return PreflightResult(ok=False, error="invalid_chain_id_format", details={})

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_address": from_address,
            "to_address": to_address,
            "amount_rtc": float(amount_rtc),
            "amount_i64": amount_i64,
            "nonce": nonce_int,
            "chain_id": chain_id or None,
        },
    )
