# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain SDK CLI wallet send command."""

import json

import httpx
import pytest
import respx
from click.testing import CliRunner

from rustchain_sdk.cli import main
from rustchain_sdk.client import DEFAULT_NODE_URL
from rustchain_sdk.wallet import RustChainWallet


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


@pytest.fixture
def test_wallet():
    """Create a deterministic test wallet."""
    # 12-word seed phrase producing a known wallet address
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
        assert payload["amount_rtc"] == 0.5
        assert payload["fee_rtc"] == 0.01

    @respx.mock
    def test_wallet_send_accepts_integer_amount_and_default_fee(self, runner, test_wallet):
        """CLI allows integer RTC amount and defaults fee to 0.0."""
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
        assert "Amount:   10.0 RTC" in result.output
        assert "Fee:      0.0 RTC" in result.output

        payload = json.loads(transfer_route.calls[0].request.content)
        assert payload["amount_rtc"] == 10.0
        assert payload["fee_rtc"] == 0.0

    @respx.mock
    def test_wallet_send_json_output(self, runner, test_wallet):
        """CLI formats response as JSON when --json flag is passed."""
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
        assert data["status"] == "pending"

    def test_wallet_send_rejects_non_numeric_amount(self, runner, test_wallet):
        """CLI returns exit code 2 when amount is not a valid number."""
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
        assert result.exit_code == 2
        assert "not a valid float" in result.output

    def test_wallet_send_rejects_non_numeric_fee(self, runner, test_wallet):
        """CLI returns exit code 2 when fee is not a valid number."""
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
        assert result.exit_code == 2
        assert "not a valid float" in result.output
