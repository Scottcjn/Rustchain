# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain SDK CLI wallet send command."""

import json
from decimal import Decimal

import httpx
import pytest
import respx
from click.testing import CliRunner

from rustchain_sdk.cli import main, EXIT_PENDING
from rustchain_sdk.client import DEFAULT_NODE_URL
from rustchain_sdk.wallet import RustChainWallet


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def test_wallet():
    """Create a deterministic test wallet."""
    seed_phrase = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    words = seed_phrase.split()
    wallet = RustChainWallet.from_seed_phrase(words)
    return wallet, seed_phrase


class TestCliWalletSend:
    """Tests for the `rustchain wallet send` CLI command."""

    @respx.mock
    def test_wallet_send_accepts_fractional_amount_and_fee(self, runner, test_wallet):
        """CLI allows fractional RTC amount and fractional fee."""
        wallet, seed_phrase = test_wallet
        to_address = "RTCrecipient0000000000000000000000000000000"

        respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
            return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
        )
        transfer_route = respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tx_hash": "0x1234567890abcdef",
                    "status": "confirmed",
                },
            )
        )

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                to_address,
                "0.5",
                "--fee",
                "0.01",
                "--seed",
                seed_phrase,
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Transfer submitted!" in result.output
        assert f"From:     {wallet.address}" in result.output
        assert f"To:       {to_address}" in result.output
        assert "Amount:   0.5 RTC" in result.output
        assert "Fee:      0.01 RTC" in result.output
        assert "TX Hash:  0x1234567890abcdef" in result.output

        payload = json.loads(transfer_route.calls[0].request.content)
        assert Decimal(str(payload["amount_rtc"])) == Decimal("0.5")
        assert Decimal(str(payload["fee_rtc"])) == Decimal("0.01")

    @respx.mock
    def test_wallet_send_accepts_integer_amount_and_default_fee(self, runner, test_wallet):
        """CLI allows integer RTC amount and defaults fee to 0."""
        wallet, seed_phrase = test_wallet
        to_address = "RTCrecipient0000000000000000000000000000000"

        respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
            return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
        )
        transfer_route = respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tx_hash": "0xfeedbeef",
                    "status": "confirmed",
                },
            )
        )

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                to_address,
                "10",
                "--seed",
                seed_phrase,
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Amount:   10 RTC" in result.output
        assert "Fee:      0 RTC" in result.output

        payload = json.loads(transfer_route.calls[0].request.content)
        assert Decimal(str(payload["amount_rtc"])) == Decimal("10")
        assert Decimal(str(payload["fee_rtc"])) == Decimal("0")

    @respx.mock
    def test_wallet_send_accepts_exact_micro_rtc_scale(self, runner, test_wallet):
        """CLI accepts amounts and fees up to 6 decimal places (micro-RTC)."""
        wallet, seed_phrase = test_wallet
        to_address = "RTCrecipient0000000000000000000000000000000"

        respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
            return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
        )
        transfer_route = respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tx_hash": "0xmicrohash",
                    "status": "confirmed",
                },
            )
        )

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                to_address,
                "0.000001",
                "--fee",
                "0.000002",
                "--seed",
                seed_phrase,
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(transfer_route.calls[0].request.content)
        assert Decimal(str(payload["amount_rtc"])) == Decimal("0.000001")
        assert Decimal(str(payload["fee_rtc"])) == Decimal("0.000002")

    @respx.mock
    def test_wallet_send_json_output_confirmed(self, runner, test_wallet):
        """CLI formats response as JSON when --json flag is passed on confirmed status."""
        wallet, seed_phrase = test_wallet
        to_address = "RTCrecipient0000000000000000000000000000000"

        respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
            return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
        )
        respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tx_hash": "0xjsonhash",
                    "status": "confirmed",
                },
            )
        )

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                to_address,
                "2.25",
                "--fee",
                "0.05",
                "--seed",
                seed_phrase,
                "--json",
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["tx_hash"] == "0xjsonhash"
        assert data["status"] == "confirmed"

    @respx.mock
    def test_wallet_send_pending_status_exits_pending_code_human(self, runner, test_wallet):
        """HTTP 200 with status 'pending' reports pending and exits with distinct exit code (2)."""
        wallet, seed_phrase = test_wallet
        to_address = "RTCrecipient0000000000000000000000000000000"

        respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
            return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
        )
        respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tx_hash": "0xpendinghash",
                    "status": "pending",
                },
            )
        )

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                to_address,
                "1.0",
                "--seed",
                seed_phrase,
            ],
        )

        assert result.exit_code == EXIT_PENDING
        assert "pending confirmation" in result.output
        assert "0xpendinghash" in result.output

    @respx.mock
    def test_wallet_send_pending_status_exits_pending_code_json(self, runner, test_wallet):
        """HTTP 200 with status 'pending' in --json mode exits with distinct exit code (2)."""
        wallet, seed_phrase = test_wallet
        to_address = "RTCrecipient0000000000000000000000000000000"

        respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
            return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
        )
        respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tx_hash": "0xpendinghash",
                    "status": "pending",
                },
            )
        )

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                to_address,
                "1.0",
                "--seed",
                seed_phrase,
                "--json",
            ],
        )

        assert result.exit_code == EXIT_PENDING
        data = json.loads(result.output)
        assert data["tx_hash"] == "0xpendinghash"
        assert data["status"] == "pending"

    @pytest.mark.parametrize("bad_amount", ["0", "-1", "-0.5"])
    def test_wallet_send_rejects_amount_le_zero(self, runner, test_wallet, bad_amount):
        """CLI rejects amount <= 0 before signing."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                "--seed",
                seed_phrase,
                wallet.address,
                "RTCto",
                "--",
                bad_amount,
            ],
        )
        assert result.exit_code == 1
        assert "amount must be greater than zero" in result.output

    @pytest.mark.parametrize("bad_amount", ["nan", "inf", "-inf", "NaN", "Infinity", "-Infinity"])
    def test_wallet_send_rejects_non_finite_amount(self, runner, test_wallet, bad_amount):
        """CLI rejects non-finite amounts before signing."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                "--seed",
                seed_phrase,
                wallet.address,
                "RTCto",
                "--",
                bad_amount,
            ],
        )
        assert result.exit_code == 1
        assert "Non-finite value for amount" in result.output

    @pytest.mark.parametrize("bad_fee", ["-0.000001", "-1"])
    def test_wallet_send_rejects_negative_fee(self, runner, test_wallet, bad_fee):
        """CLI rejects fee < 0 before signing."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                "--seed",
                seed_phrase,
                f"--fee={bad_fee}",
                wallet.address,
                "RTCto",
                "1.0",
            ],
        )
        assert result.exit_code == 1
        assert "fee cannot be negative" in result.output

    @pytest.mark.parametrize("bad_fee", ["nan", "inf", "-inf", "NaN", "Infinity", "-Infinity"])
    def test_wallet_send_rejects_non_finite_fee(self, runner, test_wallet, bad_fee):
        """CLI rejects non-finite fees before signing."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                "--seed",
                seed_phrase,
                f"--fee={bad_fee}",
                wallet.address,
                "RTCto",
                "1.0",
            ],
        )
        assert result.exit_code == 1
        assert "Non-finite value for fee" in result.output

    def test_wallet_send_rejects_inexact_chain_scale_amount(self, runner, test_wallet):
        """CLI rejects amount with more than 6 decimal places (inexact at chain scale)."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                "RTCto",
                "0.1234567",
                "--seed",
                seed_phrase,
            ],
        )
        assert result.exit_code == 1
        assert "not exact at chain scale" in result.output

    def test_wallet_send_rejects_inexact_chain_scale_fee(self, runner, test_wallet):
        """CLI rejects fee with more than 6 decimal places (inexact at chain scale)."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                "RTCto",
                "1.0",
                "--fee",
                "0.0000001",
                "--seed",
                seed_phrase,
            ],
        )
        assert result.exit_code == 1
        assert "not exact at chain scale" in result.output

    def test_wallet_send_rejects_non_numeric_amount(self, runner, test_wallet):
        """CLI returns exit code 1 when amount is not a valid number."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                "RTCto",
                "not-a-number",
                "--seed",
                seed_phrase,
            ],
        )
        assert result.exit_code == 1
        assert "Non-numeric string for amount" in result.output

    def test_wallet_send_rejects_non_numeric_fee(self, runner, test_wallet):
        """CLI returns exit code 1 when fee is not a valid number."""
        wallet, seed_phrase = test_wallet
        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                wallet.address,
                "RTCto",
                "1.0",
                "--fee",
                "invalid-fee",
                "--seed",
                seed_phrase,
            ],
        )
        assert result.exit_code == 1
        assert "Non-numeric string for fee" in result.output
