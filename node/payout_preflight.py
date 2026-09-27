from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, Optional, Tuple


MICRO_RTC = Decimal("1000000")
MAX_I64 = 2**63 - 1
# An RTC address is ``RTC`` + SHA256(pubkey)[:40], and ``hexdigest()`` is lowercase,
# so a canonical address is lowercase hex. Accepting uppercase here used to let a
# mixed-case variant through, which creates a SECOND account nobody can ever sign
# for -- that is exactly how 239 RTC was stranded on surim0n's mixed-case address.
_RTC_ADDRESS_RE = re.compile(r"RTC[0-9a-f]{40}")
# Anything that *claims* to be an RTC address by prefix. Used to tell "this caller
# meant to type an address and got it wrong" apart from "this is a handle wallet".
_RTC_PREFIXED_RE = re.compile(r"(?i)^rtc")


def _is_rtc_address(value: str) -> bool:
    return bool(_RTC_ADDRESS_RE.fullmatch(value))


def _destination_error(value: str) -> str:
    """Return an error code if ``value`` is an unusable payout destination, else "".

    Two kinds of destination are legitimate:
      * a canonical RTC address (``RTC`` + 40 lowercase hex), and
      * a non-address account id -- hosted handle wallets (``xxzzzzy``), founder
        buckets (``founder_community``) and symbolic miner ids (``dual-g4-125``).
        1,113 such accounts hold real balances, so they must keep working.

    What is NOT legitimate is a string that starts with ``RTC`` but is not a
    canonical address. Nothing can ever sign for it, so any value sent there is
    burned while the ledger records a successful payout. On 2026-09-20 an audit
    found 22 such addresses holding ~906 RTC -- roughly 520 of it real contributor
    bounty money that never became spendable. Every one of them would have been
    rejected by this check: one-character truncations
    (``RTC1d48d848...daaf2f3``), an extra character (``...c37706b``), a Solana
    address pasted into an RTC field, an account literally named ``RTC``, and
    free-text ids like ``RTC-agent-antigravity-9944``.
    """
    if _is_rtc_address(value):
        return ""
    if _RTC_PREFIXED_RE.match(value):
        return "invalid_destination_address"
    return ""


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


def _validate_amount_i64(amount_rtc: Decimal) -> Tuple[Optional[int], str]:
    amount_i64 = _amount_i64(amount_rtc)
    if amount_i64 <= 0:
        return None, "amount_too_small_after_quantization"
    if amount_i64 > MAX_I64:
        return None, "amount_exceeds_i64"
    return amount_i64, ""


def _miner_id_field(value: Any) -> Tuple[Optional[str], str]:
    if value is None or value == "":
        return None, "missing_from_or_to"
    if not isinstance(value, str):
        return None, "invalid_from_or_to_type"
    value = value.strip()
    if not value:
        return None, "missing_from_or_to"
    return value, ""


def validate_wallet_transfer_admin(payload: Any) -> PreflightResult:
    """Validate POST /wallet/transfer payload shape (admin transfer)."""
    data, err = _as_dict(payload)
    if err:
        return PreflightResult(ok=False, error=err, details={})

    from_miner, from_err = _miner_id_field(data.get("from_miner"))
    to_miner, to_err = _miner_id_field(data.get("to_miner"))
    amount_rtc, aerr = _safe_decimal(data.get("amount_rtc", 0))

    if from_err or to_err:
        return PreflightResult(ok=False, error=from_err or to_err, details={})

    # Destination must be spendable. Deliberately asymmetric: `to_miner` is checked,
    # `from_miner` is NOT, because sweeping funds OFF an already-broken address is
    # how stranded balances get recovered (see the 2026-09-20 merges) and must stay
    # possible. Guarding the destination stops new strandings; leaving the source
    # open lets us clean up the old ones.
    dest_err = _destination_error(to_miner or "")
    if dest_err:
        return PreflightResult(
            ok=False,
            error=dest_err,
            details={
                "to_miner": to_miner,
                "hint": "An RTC address is 'RTC' + 40 lowercase hex characters. "
                        "For a hosted handle wallet, pass the bare handle with no "
                        "'RTC' prefix.",
            },
        )
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64, ierr = _validate_amount_i64(amount_rtc)
    if ierr == "amount_too_small_after_quantization":
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": float(amount_rtc), "min_rtc": 0.000001},
        )
    if ierr:
        return PreflightResult(ok=False, error=ierr, details={})

    return PreflightResult(
        ok=True,
        error="",
        details={
            "from_miner": from_miner,
            "to_miner": to_miner,
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
    missing = [k for k in required if k not in data or data.get(k) in (None, "")]
    if missing:
        return PreflightResult(ok=False, error="missing_required_fields", details={"missing": missing})

    from_address = str(data.get("from_address", "")).strip()
    to_address = str(data.get("to_address", "")).strip()
    amount_rtc, aerr = _safe_decimal(data.get("amount_rtc", 0))
    if aerr:
        return PreflightResult(ok=False, error=aerr, details={})
    if amount_rtc is None or amount_rtc <= 0:
        return PreflightResult(ok=False, error="amount_must_be_positive", details={})
    amount_i64, ierr = _validate_amount_i64(amount_rtc)
    if ierr == "amount_too_small_after_quantization":
        return PreflightResult(
            ok=False,
            error="amount_too_small_after_quantization",
            details={"amount_rtc": float(amount_rtc), "min_rtc": 0.000001},
        )
    if ierr:
        return PreflightResult(ok=False, error=ierr, details={})
    fee_rtc, ferr = _safe_decimal(data.get("fee_rtc", 0))
    if ferr:
        return PreflightResult(ok=False, error=ferr, details={"field": "fee_rtc"})
    if fee_rtc is None or fee_rtc < 0:
        return PreflightResult(ok=False, error="fee_must_be_non_negative", details={})

    if not (_is_rtc_address(from_address) or _is_bcn_address(from_address)):
        return PreflightResult(ok=False, error="invalid_from_address_format", details={})
    if not (_is_rtc_address(to_address) or _is_bcn_address(to_address)):
        return PreflightResult(ok=False, error="invalid_to_address_format", details={})
    if from_address == to_address:
        return PreflightResult(ok=False, error="from_to_must_differ", details={})
    if _is_rtc_address(from_address) and not data.get("public_key"):
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
            "fee_rtc": float(fee_rtc),
            "nonce": nonce_int,
            "chain_id": chain_id or None,
        },
    )
