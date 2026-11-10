# SPDX-License-Identifier: MIT
"""Exact RTC amount handling for signed transfers (#8618)."""

import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from rustchain_sdk import ValidationError, to_micro_rtc, micro_rtc_to_str
from rustchain_sdk.amounts import MAX_MICRO_RTC, micro_rtc_to_float
from rustchain_sdk.wallet import RustChainWallet


# ── to_micro_rtc ────────────────────────────────────────────────

@pytest.mark.parametrize(
    "value, expected",
    [
        ("0.29", 290_000),
        ("10.5", 10_500_000),
        ("0.01", 10_000),
        ("0.000001", 1),
        ("1", 1_000_000),
        ("  2.5  ", 2_500_000),
        ("1e-6", 1),
        ("8388608", 8_388_608_000_000),
        (Decimal("0.29"), 290_000),
        (7, 7_000_000),
        (0.29, 290_000),   # float read via its shortest repr, not its binary value
        (10.5, 10_500_000),
        (0.01, 10_000),
    ],
)
def test_exact_conversion(value, expected):
    assert to_micro_rtc(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0.0000001",            # 7 dp: finer than 1 micro-RTC
        "1.1234567",
        0.1 + 0.2,              # 0.30000000000000004 -- binary float noise
        Decimal("0.0000005"),
    ],
)
def test_rejects_more_precision_than_ledger(value):
    with pytest.raises(ValidationError, match="more than 6 decimal places"):
        to_micro_rtc(value)


@pytest.mark.parametrize(
    "value", ["", "   ", "abc", "1,5", None, True, False, [1], "nan", "inf", float("nan"), float("inf")]
)
def test_rejects_non_numbers(value):
    with pytest.raises(ValidationError):
        to_micro_rtc(value)


@pytest.mark.parametrize("value", ["0", 0, "-1", "-0.000001", Decimal("-5")])
def test_amount_must_be_positive(value):
    with pytest.raises(ValidationError):
        to_micro_rtc(value, "amount")


def test_fee_may_be_zero_but_not_negative():
    assert to_micro_rtc("0", "fee", allow_zero=True) == 0
    assert to_micro_rtc(0, "fee", allow_zero=True) == 0
    with pytest.raises(ValidationError, match="fee"):
        to_micro_rtc("-0.01", "fee", allow_zero=True)


def test_rejects_too_large():
    assert to_micro_rtc("999999999.999999") == MAX_MICRO_RTC
    with pytest.raises(ValidationError, match="too large"):
        to_micro_rtc("1000000000")


def test_wire_float_round_trips_exactly_at_the_limits():
    for micro in (1, 290_000, 10_500_000, 123_456_789_012_345, MAX_MICRO_RTC):
        f = micro_rtc_to_float(micro)
        assert Decimal(repr(f)) * 1_000_000 == micro
        assert Decimal(json.dumps(f)) * 1_000_000 == micro


def test_micro_rtc_to_str():
    assert micro_rtc_to_str(290_000) == "0.29"
    assert micro_rtc_to_str(10_500_000) == "10.5"
    assert micro_rtc_to_str(1) == "0.000001"
    assert micro_rtc_to_str(5_000_000) == "5"
    assert micro_rtc_to_str(0) == "0"


# ── sign_transfer ───────────────────────────────────────────────

@pytest.fixture
def wallet():
    return RustChainWallet.create(strength=128)


def _signed_message(wallet, monkeypatch, *args, **kwargs):
    captured = {}

    def fake_sign(message):
        captured["message"] = message
        return b"\x01" * 64

    monkeypatch.setattr(wallet, "sign", fake_sign)
    transfer = wallet.sign_transfer(*args, **kwargs)
    return transfer, captured["message"]


@pytest.mark.parametrize(
    "amount, fee, amount_i64, fee_i64",
    [("0.29", "0.01", 290_000, 10_000), ("10.5", "0", 10_500_000, 0), (Decimal("0.000001"), 0, 1, 0)],
)
def test_sign_transfer_exposes_exact_micro_units(wallet, monkeypatch, amount, fee, amount_i64, fee_i64):
    transfer, message = _signed_message(wallet, monkeypatch, "RTCrecipient123", amount, fee=fee, nonce=1)
    assert transfer["amount_i64"] == amount_i64
    assert transfer["fee_i64"] == fee_i64
    signed = json.loads(message)
    assert Decimal(repr(signed["amount"])) * 1_000_000 == amount_i64
    assert Decimal(repr(signed["fee"])) * 1_000_000 == fee_i64
    # Payload is JSON-serializable even when Decimal inputs are used.
    json.dumps(transfer)


def test_sign_transfer_rejects_over_precision_before_signing(wallet, monkeypatch):
    def must_not_sign(message):
        raise AssertionError("signed an amount the ledger cannot represent")

    monkeypatch.setattr(wallet, "sign", must_not_sign)
    with pytest.raises(ValidationError, match="amount"):
        wallet.sign_transfer("RTCrecipient123", "0.0000001")
    with pytest.raises(ValidationError, match="fee"):
        wallet.sign_transfer("RTCrecipient123", "1", fee="0.0000001")
    with pytest.raises(ValidationError):
        wallet.sign_transfer("RTCrecipient123", 0)


# ── agreement with the node's own quantization ──────────────────

def _load_node_preflight():
    path = Path(__file__).resolve().parents[4] / "node" / "payout_preflight.py"
    if not path.exists():
        pytest.skip("node/payout_preflight.py not present (SDK installed standalone)")
    spec = importlib.util.spec_from_file_location("rc_payout_preflight", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve the defining module here
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("amount", ["0.29", "10.5", "0.01", "0.000001", "8388607.999999", "123456.789012"])
def test_node_quantizes_to_the_same_micro_units_and_message(wallet, monkeypatch, amount):
    preflight = _load_node_preflight()
    transfer, message = _signed_message(
        wallet, monkeypatch, "RTC" + "a" * 40, amount, fee="0.01", nonce=1700000000123
    )
    # What actually crosses the wire: the client's JSON payload.
    wire = json.loads(json.dumps({
        "from_address": wallet.address,
        "to_address": transfer["to_address"],
        "amount_rtc": transfer["amount_rtc"],
        "fee_rtc": transfer["fee_rtc"],
        "nonce": transfer["nonce"],
        "signature": transfer["signature"],
        "public_key": transfer["public_key"],
    }))
    result = preflight.validate_wallet_transfer_signed(wire)
    assert result.ok, result.error
    assert result.details["amount_i64"] == transfer["amount_i64"]

    # The node rebuilds the signed message from the preflight floats
    # (_wallet_transfer_signed_messages); it must be byte-identical.
    rebuilt = json.dumps(
        {
            "from": wallet.address,
            "to": transfer["to_address"],
            "amount": result.details["amount_rtc"],
            "fee": result.details["fee_rtc"],
            "memo": "",
            "nonce": str(transfer["nonce"]),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert rebuilt == message
