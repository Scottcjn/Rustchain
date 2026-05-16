"""
attestation_validators.py — Extracted validator functions from
node/rustchain_v2_integrated_v2.2.1_rip200.py for self-contained fuzz testing.

These are verbatim copies of the production functions, with only the
Flask/jsonify dependency stubbed out so they can be unit-tested without
importing the 275 KB server module.
"""

import math
import re
from typing import Any, Optional, Tuple


# ---------------------------------------------------------------------------
# Minimal stub so _attest_field_error doesn't need Flask
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal stand-in for a Flask Response tuple."""
    def __init__(self, body: dict, status: int):
        self.body = body
        self.status = status

    def __repr__(self):
        return f"<FakeResponse {self.status} {self.body}>"


def _jsonify(d: dict) -> "_FakeResponse":
    return d  # just return the dict; status is attached as a tuple below


def _attest_field_error(code: str, message: str, status: int = 400):
    """Build a consistent error payload for malformed attestation inputs."""
    return (
        {
            "ok": False,
            "error": code.lower(),
            "message": message,
            "code": code,
        },
        status,
    )


# ---------------------------------------------------------------------------
# Verbatim validator functions (copied from production source)
# ---------------------------------------------------------------------------

def _attest_mapping(value: Any) -> dict:
    """Return a dict-like payload section or an empty mapping."""
    return value if isinstance(value, dict) else {}


_ATTEST_MINER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _attest_text(value: Any) -> Optional[str]:
    """Accept only non-empty text values from untrusted attestation input."""
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return None


def _attest_valid_miner(value: Any) -> Optional[str]:
    """Accept only bounded miner identifiers with a conservative character set."""
    text = _attest_text(value)
    if text and _ATTEST_MINER_RE.fullmatch(text):
        return text
    return None


def _attest_is_valid_positive_int(value: Any, max_value: int = 4096) -> bool:
    """Validate positive integer-like input without silently coercing hostile shapes."""
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return False
    try:
        coerced = int(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return 1 <= coerced <= max_value


def _attest_positive_int(value: Any, default: int = 1) -> int:
    """Coerce untrusted integer-like values to a safe positive integer."""
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return coerced if coerced > 0 else default


def _attest_string_list(value: Any) -> list:
    """Coerce a list-like field into a list of non-empty strings."""
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = _attest_text(item)
        if text:
            items.append(text)
    return items


def _validate_attestation_payload_shape(data: Any):
    """Reject malformed attestation payload shapes before normalisation."""
    for field_name, code in (
        ("device", "INVALID_DEVICE"),
        ("signals", "INVALID_SIGNALS"),
        ("report", "INVALID_REPORT"),
        ("fingerprint", "INVALID_FINGERPRINT"),
    ):
        if (
            field_name in data
            and data[field_name] is not None
            and not isinstance(data[field_name], dict)
        ):
            return _attest_field_error(code, f"Field '{field_name}' must be a JSON object")

    for field_name in ("miner", "miner_id"):
        if (
            field_name in data
            and data[field_name] is not None
            and not isinstance(data[field_name], str)
        ):
            return _attest_field_error(
                "INVALID_MINER", f"Field '{field_name}' must be a non-empty string"
            )
        if (
            field_name in data
            and _attest_text(data[field_name])
            and not _attest_valid_miner(data[field_name])
        ):
            return _attest_field_error(
                "INVALID_MINER",
                "Fields 'miner' and 'miner_id' must use only letters, numbers, '.', '_', ':' or '-' "
                "and be at most 128 characters",
            )

    for field_name, code in (
        ("signature", "INVALID_SIGNATURE_TYPE"),
        ("public_key", "INVALID_PUBLIC_KEY_TYPE"),
    ):
        if (
            field_name in data
            and data[field_name] is not None
            and not isinstance(data[field_name], str)
        ):
            return _attest_field_error(code, f"Field '{field_name}' must be a string")

    miner = _attest_valid_miner(data.get("miner")) or _attest_valid_miner(data.get("miner_id"))
    if not miner and not (
        _attest_text(data.get("miner")) or _attest_text(data.get("miner_id"))
    ):
        return _attest_field_error(
            "MISSING_MINER",
            "Field 'miner' or 'miner_id' must be a non-empty identifier using only "
            "letters, numbers, '.', '_', ':' or '-'",
        )
    if not miner:
        return _attest_field_error(
            "INVALID_MINER",
            "Field 'miner' or 'miner_id' must use only letters, numbers, '.', '_', ':' or '-' "
            "and be at most 128 characters",
        )

    device = data.get("device")
    if isinstance(device, dict):
        if "cores" in device and not _attest_is_valid_positive_int(device.get("cores")):
            return _attest_field_error(
                "INVALID_DEVICE_CORES",
                "Field 'device.cores' must be a positive integer between 1 and 4096",
                status=422,
            )
        for field_name in (
            "device_family",
            "family",
            "device_arch",
            "arch",
            "device_model",
            "model",
            "cpu",
            "serial_number",
            "serial",
        ):
            if (
                field_name in device
                and device[field_name] is not None
                and not isinstance(device[field_name], str)
            ):
                return _attest_field_error(
                    "INVALID_DEVICE", f"Field 'device.{field_name}' must be a string"
                )

    signals = data.get("signals")
    if isinstance(signals, dict):
        if "macs" in signals:
            macs = signals.get("macs")
            if not isinstance(macs, list) or any(_attest_text(mac) is None for mac in macs):
                return _attest_field_error(
                    "INVALID_SIGNALS_MACS",
                    "Field 'signals.macs' must be a list of non-empty strings",
                )
        for field_name in ("hostname", "serial"):
            if (
                field_name in signals
                and signals[field_name] is not None
                and not isinstance(signals[field_name], str)
            ):
                return _attest_field_error(
                    "INVALID_SIGNALS", f"Field 'signals.{field_name}' must be a string"
                )

    report = data.get("report")
    if isinstance(report, dict):
        for field_name in ("nonce", "commitment"):
            if (
                field_name in report
                and report[field_name] is not None
                and not isinstance(report[field_name], str)
            ):
                return _attest_field_error(
                    "INVALID_REPORT", f"Field 'report.{field_name}' must be a string"
                )

    fingerprint = data.get("fingerprint")
    if (
        isinstance(fingerprint, dict)
        and "checks" in fingerprint
        and not isinstance(fingerprint.get("checks"), dict)
    ):
        return _attest_field_error(
            "INVALID_FINGERPRINT_CHECKS",
            "Field 'fingerprint.checks' must be a JSON object",
        )

    return None
