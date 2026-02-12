from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    error: str
    details: Dict[str, Any]


def _as_dict(payload: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    if not isinstance(payload, dict):
        return None, "invalid_json_body"
    return payload, ""


def _safe_float(v: Any) -> Tuple[Optional[float], str]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None, "amount_not_number"
    if not math.isfinite(f):
        return None, "amount_not_finite"
    return f, ""


def validate_wallet_transfer_admin(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer payload shape (admin transfer)."""
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

    return PreflightResult(
        ok=True,
        error="",
        details={"from_miner": str(from_miner), "to_miner": str(to_miner), "amount_rtc": amount_rtc},
    )


def validate_wallet_transfer_signed(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer/signed payload shape (client-signed)."""
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
        details={"from_address": from_address, "to_address": to_address, "amount_rtc": amount_rtc, "nonce": nonce_int},
    )

