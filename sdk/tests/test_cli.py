# SPDX-License-Identifier: MIT
"""
RustChain Python SDK CLI Test Suite (Click CliRunner)
Tests all commands in rustchain_sdk/cli.py:
- wallet create (12/24 words, json, error handling)
- wallet balance (standard, json, error handling)
- wallet send (standard, json, address mismatch, error handling)
- node status (health check, json)
- epoch info (standard, json)
- miners list (standard, json)
- attest (challenge & submission, json)
"""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure sdk/python is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../python")))

import pytest
from click.testing import CliRunner

from rustchain_sdk.cli import main
from rustchain_sdk.exceptions import RustChainError


@pytest.fixture
def runner():
    return CliRunner()


class TestCliGeneral:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "RustChain CLI" in result.output
        assert "wallet" in result.output
        assert "node" in result.output
        assert "epoch" in result.output
        assert "miners" in result.output
        assert "attest" in result.output

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "rustchain" in result.output.lower()


class TestCliWalletCreate:
    def test_wallet_create_default_12_words(self, runner):
        result = runner.invoke(main, ["wallet", "create"])
        assert result.exit_code == 0
        assert "Wallet created successfully!" in result.output
        assert "Address:" in result.output
        assert "Seed Phrase (12 words):" in result.output

    def test_wallet_create_24_words(self, runner):
        result = runner.invoke(main, ["wallet", "create", "--words", "24"])
        assert result.exit_code == 0
        assert "Seed Phrase (24 words):" in result.output

    def test_wallet_create_json(self, runner):
        result = runner.invoke(main, ["wallet", "create", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "address" in data
        assert "seed_phrase" in data
        assert len(data["seed_phrase"]) == 12

    def test_wallet_create_invalid_words(self, runner):
        result = runner.invoke(main, ["wallet", "create", "--words", "16"])
        assert result.exit_code == 1
        assert "Number of seed words must be 12 or 24" in result.output


class TestCliWalletBalance:
    @patch("rustchain_sdk.cli.RustChainClient")
    def test_wallet_balance_text(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_balance.return_value = {"balance": 150.5, "nonce": 7}
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["wallet", "balance", "RTC1testaddr"])
        assert result.exit_code == 0
        assert "Address:  RTC1testaddr" in result.output
        assert "Balance:  150.5 RTC" in result.output
        assert "Nonce:    7" in result.output

    @patch("rustchain_sdk.cli.RustChainClient")
    def test_wallet_balance_json(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_balance.return_value = {"balance": 200, "nonce": 12}
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["wallet", "balance", "RTC1testaddr", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["balance"] == 200
        assert data["nonce"] == 12

    @patch("rustchain_sdk.cli.RustChainClient")
    def test_wallet_balance_error(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_balance.side_effect = RustChainError("Account not found")
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["wallet", "balance", "RTC1invalid"])
        assert result.exit_code == 1
        assert "Account not found" in result.output


class TestCliWalletSend:
    @patch("rustchain_sdk.cli.RustChainClient")
    @patch("rustchain_sdk.cli.RustChainWallet")
    def test_wallet_send_success(self, mock_wallet_cls, mock_client_cls, runner):
        mock_wallet = MagicMock()
        mock_wallet.address = "RTC1fromaddr"
        mock_wallet_cls.from_seed_phrase.return_value = mock_wallet

        mock_instance = AsyncMock()
        mock_instance.wallet_transfer_with_wallet.return_value = {
            "tx_hash": "0xabcdef123456",
            "status": "confirmed",
        }
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                "RTC1fromaddr",
                "RTC1toaddr",
                "50",
                "--fee",
                "1",
                "--seed",
                "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12",
            ],
        )
        assert result.exit_code == 0
        assert "Transfer submitted!" in result.output
        assert "Amount:   50 RTC" in result.output
        assert "TX Hash:  0xabcdef123456" in result.output

    @patch("rustchain_sdk.cli.RustChainWallet")
    def test_wallet_send_address_mismatch(self, mock_wallet_cls, runner):
        mock_wallet = MagicMock()
        mock_wallet.address = "RTC1different"
        mock_wallet_cls.from_seed_phrase.return_value = mock_wallet

        result = runner.invoke(
            main,
            [
                "wallet",
                "send",
                "RTC1expected",
                "RTC1toaddr",
                "50",
                "--seed",
                "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12",
            ],
        )
        assert result.exit_code == 1
        assert "Address mismatch" in result.output


class TestCliNodeStatus:
    @patch("rustchain_sdk.cli.RustChainClient")
    def test_node_status_healthy(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.health.return_value = {
            "status": "ok",
            "version": "1.4.2",
            "peers": 42,
        }
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["node"])
        assert result.exit_code == 0
        assert "Node is healthy" in result.output
        assert "1.4.2" in result.output

    @patch("rustchain_sdk.cli.RustChainClient")
    def test_node_status_json(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.health.return_value = {"status": "ok", "version": "1.4.2"}
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["node", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


class TestCliEpochInfo:
    @patch("rustchain_sdk.cli.RustChainClient")
    def test_epoch_info_text(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_epoch.return_value = {
            "epoch_number": 420,
            "miners_count": 88,
        }
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["epoch"])
        assert result.exit_code == 0
        assert "Epoch Info:" in result.output
        assert "epoch_number:  420" in result.output

    @patch("rustchain_sdk.cli.RustChainClient")
    def test_epoch_info_json(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_epoch.return_value = {"epoch": 100}
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["epoch", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["epoch"] == 100


class TestCliMinersList:
    @patch("rustchain_sdk.cli.RustChainClient")
    def test_miners_list_text(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_miners.return_value = [
            {"miner_id": "m1", "hashrate": "150MH"},
            {"miner_id": "m2", "hashrate": "200MH"},
        ]
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["miners", "list"])
        assert result.exit_code == 0
        assert "Active Miners (2):" in result.output
        assert "m1" in result.output

    @patch("rustchain_sdk.cli.RustChainClient")
    def test_miners_list_json(self, mock_client_cls, runner):
        mock_instance = AsyncMock()
        mock_instance.get_miners.return_value = [{"miner_id": "m1"}]
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(main, ["miners", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["miner_id"] == "m1"


class TestCliAttest:
    @patch("rustchain_sdk.cli.RustChainClient")
    @patch("rustchain_sdk.cli.RustChainWallet")
    def test_attest_success(self, mock_wallet_cls, mock_client_cls, runner):
        mock_wallet = MagicMock()
        mock_wallet.address = "RTC1mineraddr"
        mock_wallet.public_key_hex = "pubkeyhex123"
        mock_wallet.sign.return_value = b"signaturesignature"
        mock_wallet_cls.from_seed_phrase.return_value = mock_wallet

        mock_instance = AsyncMock()
        mock_instance.get_attestation_status.return_value = {"active": True}
        mock_instance.attest_challenge.return_value = {"challenge": "challenge_token_abc"}
        mock_instance.attest_submit.return_value = {
            "status": "success",
            "attestation_id": "att-998877",
        }
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client_cls.return_value = mock_instance

        result = runner.invoke(
            main,
            [
                "attest",
                "RTC1mineraddr",
                "--seed",
                "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12",
            ],
        )
        assert result.exit_code == 0
        assert "Submitting attestation..." in result.output
        assert "Attestation submitted!" in result.output

    @patch("rustchain_sdk.cli.RustChainWallet")
    def test_attest_address_mismatch(self, mock_wallet_cls, runner):
        mock_wallet = MagicMock()
        mock_wallet.address = "RTC1different"
        mock_wallet_cls.from_seed_phrase.return_value = mock_wallet

        result = runner.invoke(
            main,
            [
                "attest",
                "RTC1expected",
                "--seed",
                "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12",
            ],
        )
        assert result.exit_code == 1
        assert "Address mismatch" in result.output
