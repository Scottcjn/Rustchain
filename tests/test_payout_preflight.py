# SPDX-License-Identifier: MIT
"""
Unit tests for payout_preflight.py - Bounty #1589
"""
import pytest
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from payout_preflight import (
    _as_dict,
    _safe_decimal,
    _amount_i64,
    validate_wallet_transfer_admin,
    validate_wallet_transfer_signed,
    PreflightResult,
    MICRO_RTC,
)


class TestAsDict:
      def test_valid_dict(self):
                result, err = _as_dict({"key": "value"})
                assert result == {"key": "value"}
                assert err == ""

      def test_empty_dict(self):
                result, err = _as_dict({})
                assert result == {}
                assert err == ""

      def test_none_rejected(self):
                result, err = _as_dict(None)
                assert result is None
                assert err == "invalid_json_body"

      def test_list_rejected(self):
                result, err = _as_dict([1, 2, 3])
                assert result is None
                assert err == "invalid_json_body"

      def test_string_rejected(self):
                result, err = _as_dict("hello")
                assert result is None
                assert err == "invalid_json_body"

      def test_int_rejected(self):
                result, err = _as_dict(42)
                assert result is None
                assert err == "invalid_json_body"


class TestSafeDecimal:
      def test_valid_integer(self):
                val, err = _safe_decimal(100)
                assert val == Decimal("100")
                assert err == ""

      def test_valid_float(self):
                val, err = _safe_decimal(1.5)
                assert val is not None
                assert err == ""

      def test_valid_string_number(self):
                val, err = _safe_decimal("42.123")
                assert val == Decimal("42.123")
                assert err == ""

      def test_nan_rejected(self):
                val, err = _safe_decimal(float("nan"))
                assert err == "amount_not_finite"

      def test_infinity_rejected(self):
                val, err = _safe_decimal(float("inf"))
                assert err == "amount_not_finite"

      def test_negative_infinity_rejected(self):
                val, err = _safe_decimal(float("-inf"))
                assert err == "amount_not_finite"

      def test_non_numeric_string_rejected(self):
                val, err = _safe_decimal("not_a_number")
                assert val is None
                assert err == "amount_not_number"

      def test_none_rejected(self):
                val, err = _safe_decimal(None)
                assert val is None
                assert err == "amount_not_number"

      def test_empty_string_rejected(self):
                val, err = _safe_decimal("")
                assert val is None
                assert err == "amount_not_number"

      def test_zero_is_valid(self):
                val, err = _safe_decimal(0)
                assert val == Decimal("0")
                assert err == ""

      def test_very_large_number(self):
                val, err = _safe_decimal("999999999999999999.999999")
                assert val is not None
                assert err == ""


class TestAmountI64:
      def test_one_rtc(self):
                assert _amount_i64(Decimal("1")) == 1_000_000

      def test_fractional_rtc(self):
                assert _amount_i64(Decimal("0.5")) == 500_000

      def test_minimum_representable(self):
                assert _amount_i64(Decimal("0.000001")) == 1

      def test_sub_micro_rounds_down(self):
                assert _amount_i64(Decimal("0.0000001")) == 0

      def test_zero(self):
                assert _amount_i64(Decimal("0")) == 0

      def test_rounds_down_not_up(self):
                assert _amount_i64(Decimal("0.0000019999999")) == 1


class TestValidateWalletTransferAdmin:
      def test_valid_transfer(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "to_miner": "miner_beta",
                              "amount_rtc": 10.0,
                })
                assert result.ok is True
                assert result.error == ""
                assert result.details["from_miner"] == "miner_alpha"
                assert result.details["to_miner"] == "miner_beta"
                assert result.details["amount_rtc"] == 10.0
                assert result.details["amount_i64"] == 10_000_000

      def test_missing_from_miner(self):
                result = validate_wallet_transfer_admin({
                              "to_miner": "miner_beta",
                              "amount_rtc": 10.0,
                })
                assert result.ok is False
                assert result.error == "missing_from_or_to"

      def test_missing_to_miner(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "amount_rtc": 10.0,
                })
                assert result.ok is False
                assert result.error == "missing_from_or_to"

      def test_zero_amount_rejected(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "to_miner": "miner_beta",
                              "amount_rtc": 0,
                })
                assert result.ok is False
                assert result.error == "amount_must_be_positive"

      def test_negative_amount_rejected(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "to_miner": "miner_beta",
                              "amount_rtc": -5.0,
                })
                assert result.ok is False
                assert result.error == "amount_must_be_positive"

      def test_non_dict_payload_rejected(self):
                result = validate_wallet_transfer_admin("not_a_dict")
                assert result.ok is False
                assert result.error == "invalid_json_body"

      def test_nan_amount_rejected(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "to_miner": "miner_beta",
                              "amount_rtc": float("nan"),
                })
                assert result.ok is False

      def test_dust_amount_rejected(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "to_miner": "miner_beta",
                              "amount_rtc": 0.00000001,
                })
                assert result.ok is False
                assert result.error == "amount_too_small_after_quantization"

      def test_string_amount_works(self):
                result = validate_wallet_transfer_admin({
                              "from_miner": "miner_alpha",
                              "to_miner": "miner_beta",
                              "amount_rtc": "5.5",
                })
                assert result.ok is True
                assert result.details["amount_rtc"] == 5.5


class TestValidateWalletTransferSigned:
      @staticmethod
      def _make_address(suffix="a"):
                return "RTC" + suffix * 40

      def _valid_payload(self, **overrides):
                base = {
                              "from_address": self._make_address("a"),
                              "to_address": self._make_address("b"),
                              "amount_rtc": 10.0,
                              "nonce": 1,
                              "signature": "sig_abc123",
                              "public_key": "pk_abc123",
                }
                base.update(overrides)
                return base

      def test_valid_signed_transfer(self):
                result = validate_wallet_transfer_signed(self._valid_payload())
                assert result.ok is True
                assert result.error == ""
                assert result.details["nonce"] == 1

      def test_missing_required_fields(self):
                result = validate_wallet_transfer_signed({
                              "from_address": self._make_address("a"),
                })
                assert result.ok is False
                assert result.error == "missing_required_fields"

      def test_invalid_from_address_format(self):
                payload = self._valid_payload(from_address="BTC" + "a" * 40)
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "invalid_from_address_format"

      def test_invalid_from_address_length(self):
                payload = self._valid_payload(from_address="RTCshort")
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "invalid_from_address_format"

      def test_self_transfer_rejected(self):
                addr = self._make_address("x")
                payload = self._valid_payload(from_address=addr, to_address=addr)
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "from_to_must_differ"

      def test_negative_nonce_rejected(self):
                payload = self._valid_payload(nonce=-1)
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "nonce_must_be_gt_zero"

      def test_zero_nonce_rejected(self):
                payload = self._valid_payload(nonce=0)
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "nonce_must_be_gt_zero"

      def test_non_numeric_nonce_rejected(self):
                payload = self._valid_payload(nonce="abc")
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "nonce_not_int"

      def test_valid_chain_id(self):
                payload = self._valid_payload(chain_id="rustchain-mainnet-v1")
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is True
                assert result.details["chain_id"] == "rustchain-mainnet-v1"

      def test_invalid_chain_id_rejected(self):
                payload = self._valid_payload(chain_id="bad chain!@#")
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "invalid_chain_id_format"

      def test_chain_id_too_long_rejected(self):
                payload = self._valid_payload(chain_id="a" * 65)
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "invalid_chain_id_format"

      def test_zero_amount_rejected(self):
                payload = self._valid_payload(amount_rtc=0)
                result = validate_wallet_transfer_signed(payload)
                assert result.ok is False
                assert result.error == "amount_must_be_positive"

      def test_non_dict_payload_rejected(self):
                result = validate_wallet_transfer_signed(None)
                assert result.ok is False
                assert result.error == "invalid_json_body"


class TestPreflightResult:
      def test_ok_result_fields(self):
                result = PreflightResult(ok=True, error="", details={"key": "val"})
                assert result.ok is True
                assert result.error == ""

      def test_error_result_fields(self):
                result = PreflightResult(ok=False, error="test_err", details={})
                assert result.ok is False
                assert result.error == "test_err"

      def test_frozen_dataclass(self):
                result = PreflightResult(ok=True, error="", details={})
                with pytest.raises(AttributeError):
                              result.ok = False
                  
