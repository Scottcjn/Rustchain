# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain SDK CLI."""

import json

import httpx
import pytest
import respx
from click.testing import CliRunner

from rustchain_sdk.cli import main
from rustchain_sdk.client import DEFAULT_NODE_URL


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


class TestCliWalletBalance:
    """Tests for the `rustchain wallet balance` CLI command."""

    @respx.mock
    def test_canonical_amount_rtc_displayed(self, runner):
        """CLI renders amount_rtc from canonical node responses with matching nonce."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "stmr",
                    "amount_rtc": 21.0,
                    "amount_i64": 21000000,
                    "nonce": 0,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "stmr"])
        assert result.exit_code == 0
        assert "Address:  stmr" in result.output
        assert "Balance:  21.0 RTC" in result.output
        assert "Nonce:    0" in result.output

    @respx.mock
    def test_legacy_balance_compatibility(self, runner):
        """CLI maintains compatibility with legacy balance/nonce responses."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "address": "RTClegacy123",
                    "balance": 42,
                    "nonce": 3,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "RTClegacy123"])
        assert result.exit_code == 0
        assert "Address:  RTClegacy123" in result.output
        assert "Balance:  42 RTC" in result.output
        assert "Nonce:    3" in result.output

    @respx.mock
    def test_amount_i64_fallback_when_amount_rtc_missing(self, runner):
        """CLI calculates balance via Decimal from amount_i64 if amount_rtc is missing."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "RTCfallback",
                    "amount_i64": 5000000,
                    "nonce": 1,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "RTCfallback"])
        assert result.exit_code == 0
        assert "Address:  RTCfallback" in result.output
        assert "Balance:  5 RTC" in result.output
        assert "Nonce:    1" in result.output

    @respx.mock
    def test_missing_balance_exits_nonzero(self, runner):
        """CLI exits non-zero instead of printing 'unavailable' when balance is missing."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "RTCunknown",
                    "nonce": 0,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "RTCunknown"])
        assert result.exit_code != 0
        assert "Missing balance" in (result.stderr or result.output)

    @respx.mock
    def test_missing_nonce_exits_nonzero(self, runner):
        """CLI exits non-zero instead of inventing Nonce: 0 when nonce is missing."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "stmr",
                    "amount_rtc": 10.0,
                    "amount_i64": 10000000,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "stmr"])
        assert result.exit_code != 0
        assert "Missing nonce" in (result.stderr or result.output)

    @respx.mock
    def test_miner_id_mismatch_exits_nonzero(self, runner):
        """CLI exits non-zero when response miner_id does not match requested address."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "wrong_miner",
                    "amount_rtc": 10.0,
                    "amount_i64": 10000000,
                    "nonce": 0,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "stmr"])
        assert result.exit_code != 0
        assert "does not match requested address" in (result.stderr or result.output)

    @respx.mock
    def test_address_mismatch_exits_nonzero(self, runner):
        """CLI exits non-zero when response address does not match requested address."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "address": "RTCdifferent",
                    "balance": 10,
                    "nonce": 1,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "RTCrequested"])
        assert result.exit_code != 0
        assert "does not match requested address" in (result.stderr or result.output)

    @respx.mock
    def test_disagreement_between_amount_rtc_and_amount_i64_exits_nonzero(self, runner):
        """CLI errors out when both amount_rtc and amount_i64 are present and disagree."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "stmr",
                    "amount_rtc": 21.0,
                    "amount_i64": 25000000,  # 25 RTC != 21.0 RTC
                    "nonce": 0,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "stmr"])
        assert result.exit_code != 0
        assert "Balance mismatch" in (result.stderr or result.output)

    @pytest.mark.parametrize("bad_val", [True, False, "true", "nan", "inf", "-inf", "not_a_number"])
    @respx.mock
    def test_reject_non_finite_numeric_balance(self, runner, bad_val):
        """CLI rejects boolean, non-finite (NaN, inf) and non-numeric balance values."""
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "stmr",
                    "amount_rtc": bad_val,
                    "nonce": 0,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "stmr"])
        assert result.exit_code != 0

    @respx.mock
    def test_amount_i64_precision_preserved_beyond_float(self, runner):
        """amount_i64 does not lose precision via float conversion (e.g. >2^53 integer)."""
        # 9007199254740993 is 2^53 + 1, precision would be lost in standard float64
        huge_micro = 9007199254740993
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "miner_id": "huge_acc",
                    "amount_i64": huge_micro,
                    "nonce": 0,
                },
            )
        )
        result = runner.invoke(main, ["wallet", "balance", "huge_acc"])
        assert result.exit_code == 0
        assert "Balance:  9007199254.740993 RTC" in result.output

    @respx.mock
    def test_wallet_balance_json_flag(self, runner):
        """--json flag outputs raw formatted JSON when response is valid."""
        payload = {
            "miner_id": "stmr",
            "amount_rtc": 21.0,
            "amount_i64": 21000000,
            "nonce": 12,
        }
        respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = runner.invoke(main, ["wallet", "balance", "stmr", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["amount_rtc"] == 21.0
        assert data["amount_i64"] == 21000000
        assert data["nonce"] == 12
