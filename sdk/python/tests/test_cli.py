# SPDX-License-Identifier: MIT
"""
Comprehensive Click CliRunner test suite for `rustchain_sdk.cli`.

Covers:
1. Every CLI command group and subcommand (`--help`, `--version`, `wallet create|balance|send`,
   `node`, `epoch`, `miners list`, `attest`) in both human and `--json` output modes.
2. Error paths: unreachable node, non-JSON 200, HTTP 4xx/5xx, bad address mismatch,
   bad amounts (`abc`, negative, `0`), invalid seed word count, missing required options.
3. Strict xfail regression tests (`xfail(strict=True)`) for:
   - Rustchain#8564: fractional RTC amounts & fees rejected by `int` Click parameter
   - Rustchain#8565: README `rustchain node status` and `rustchain epoch info` rejected by parser
   - Rustchain#8566: `rustchain attest --json` returns status early without challenge/sign/submit
   - Rustchain#8580: `rustchain wallet balance` prints `0 RTC` on canonical `amount_rtc` payload
   - Rustchain#8618: no-float-money exact decimal / integer minor-unit (`amount_i64` / uRTC) serialization
4. Zero live network enforcement via autouse socket-blocking fixture + mocked client transport.
"""

from __future__ import annotations

from decimal import Decimal
import json
import socket
from typing import Any, Dict, List
import pytest
from click.testing import CliRunner

from rustchain_sdk import __version__, cli
from rustchain_sdk.exceptions import (
    APIError,
    AttestationError,
    ConnectionError as SDKConnectionError,
    EpochError,
    HealthError,
    TransferError,
    ValidationError,
)


# ─────────────────────────────────────────────────────────────────
# Autouse Network Isolation Fixture (Zero Live Network Guarantee)
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def block_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block all live socket/network operations during CLI test execution."""
    def _blocked(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Live network access is strictly forbidden in test_cli.py")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


@pytest.fixture
def runner() -> CliRunner:
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


# ─────────────────────────────────────────────────────────────────
# Mock Fakes for Wallet and Client
# ─────────────────────────────────────────────────────────────────

DUMMY_SEED_12 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
DUMMY_SEED_24 = " ".join(["abandon"] * 23 + ["art"])
DUMMY_ADDRESS = "RTCcf42ef35704e2e281a803afbfbbdb9ad961ec021"
DUMMY_TO_ADDRESS = "RTC9999999999999999999999999999999999999999"
DUMMY_PUBKEY = "02" + "ab" * 31


class FakeWallet:
    def __init__(
        self,
        address: str = DUMMY_ADDRESS,
        public_key_hex: str = DUMMY_PUBKEY,
        seed_phrase: List[str] | None = None,
    ) -> None:
        self.address = address
        self.public_key_hex = public_key_hex
        self.seed_phrase = seed_phrase or DUMMY_SEED_12.split()

    @classmethod
    def create(cls, strength: int = 128) -> "FakeWallet":
        words = DUMMY_SEED_12.split() if strength == 128 else DUMMY_SEED_24.split()
        return cls(seed_phrase=words)

    @classmethod
    def from_seed_phrase(cls, words: List[str]) -> "FakeWallet":
        return cls(seed_phrase=words)

    def export(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "public_key": self.public_key_hex,
            "seed_phrase": self.seed_phrase,
        }

    def sign(self, message: bytes) -> bytes:
        return b"\xde\xad\xbe\xef" * 16


class FakeClient:
    """In-memory mock replacement for RustChainClient."""

    def __init__(self, base_url: str = cli.DEFAULT_NODE_URL, **kwargs: Any) -> None:
        self.base_url = base_url
        self.calls: List[tuple] = []
        self.balance_response: Dict[str, Any] = {"balance": 125, "nonce": 7}
        self.transfer_response: Dict[str, Any] = {
            "tx_hash": "0xabc123def456",
            "status": "accepted",
        }
        self.health_response: Dict[str, Any] = {
            "status": "ok",
            "version": "2.4.0",
            "uptime": 86400,
        }
        self.epoch_response: Dict[str, Any] = {
            "epoch": 412,
            "slot": 8192,
            "miners_active": 64,
        }
        self.miners_response: List[Dict[str, Any]] = [
            {"miner_id": "miner-g4-ppc", "arch": "PowerPC G4", "multiplier": 2.5},
            {"miner_id": "miner-m2-arm", "arch": "Apple Silicon", "multiplier": 1.2},
        ]
        self.attest_status_response: Dict[str, Any] = {
            "enrolled": True,
            "last_epoch": 411,
        }
        self.attest_challenge_response: Dict[str, Any] = {
            "challenge": "rtc-challenge-nonce-98765"
        }
        self.attest_submit_response: Dict[str, Any] = {
            "status": "verified",
            "epoch": 412,
        }
        self.raise_on: Dict[str, Exception] = {}

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def get_balance(self, address: str) -> Dict[str, Any]:
        self.calls.append(("get_balance", address))
        if "get_balance" in self.raise_on:
            raise self.raise_on["get_balance"]
        return self.balance_response

    async def wallet_transfer_with_wallet(
        self, wallet: Any, to_address: str, amount: Any, fee: Any
    ) -> Dict[str, Any]:
        self.calls.append(("wallet_transfer_with_wallet", wallet.address, to_address, amount, fee))
        if "wallet_transfer_with_wallet" in self.raise_on:
            raise self.raise_on["wallet_transfer_with_wallet"]
        return self.transfer_response

    async def health(self) -> Dict[str, Any]:
        self.calls.append(("health",))
        if "health" in self.raise_on:
            raise self.raise_on["health"]
        return self.health_response

    async def get_epoch(self) -> Dict[str, Any]:
        self.calls.append(("get_epoch",))
        if "get_epoch" in self.raise_on:
            raise self.raise_on["get_epoch"]
        return self.epoch_response

    async def get_miners(self) -> List[Dict[str, Any]]:
        self.calls.append(("get_miners",))
        if "get_miners" in self.raise_on:
            raise self.raise_on["get_miners"]
        return self.miners_response

    async def get_attestation_status(self, pubkey: str) -> Dict[str, Any]:
        self.calls.append(("get_attestation_status", pubkey))
        if "get_attestation_status" in self.raise_on:
            raise self.raise_on["get_attestation_status"]
        return self.attest_status_response

    async def attest_challenge(self, pubkey: str) -> Dict[str, Any]:
        self.calls.append(("attest_challenge", pubkey))
        if "attest_challenge" in self.raise_on:
            raise self.raise_on["attest_challenge"]
        return self.attest_challenge_response

    async def attest_submit(self, pubkey: str, challenge: str, signature: str) -> Dict[str, Any]:
        self.calls.append(("attest_submit", pubkey, challenge, signature))
        if "attest_submit" in self.raise_on:
            raise self.raise_on["attest_submit"]
        return self.attest_submit_response


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(cli, "RustChainWallet", FakeWallet)
    monkeypatch.setattr(cli, "RustChainClient", lambda **kwargs: client)
    return client


# ─────────────────────────────────────────────────────────────────
# 1. Help & Version Coverage for Every Group and Command
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "argv,expected_snippet",
    [
        (["--help"], "RustChain CLI"),
        (["wallet", "--help"], "Wallet management commands"),
        (["wallet", "create", "--help"], "Create a new RustChain wallet"),
        (["wallet", "balance", "--help"], "Check the balance of a wallet address"),
        (["wallet", "send", "--help"], "Send RTC from one wallet to another"),
        (["node", "--help"], "Check node health status"),
        (["epoch", "--help"], "Get current epoch information"),
        (["miners", "--help"], "Miner management commands"),
        (["miners", "list", "--help"], "List active miners"),
        (["attest", "--help"], "Request and submit an attestation"),
    ],
)
def test_cli_help_every_command_and_group(
    runner: CliRunner, argv: List[str], expected_snippet: str
) -> None:
    result = runner.invoke(cli.main, argv)
    assert result.exit_code == 0
    assert expected_snippet in result.stdout


def test_cli_version_option(runner: CliRunner) -> None:
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "rustchain" in result.stdout


# ─────────────────────────────────────────────────────────────────
# 2. Wallet Commands: create, balance, send (Human + JSON + Errors)
# ─────────────────────────────────────────────────────────────────

def test_wallet_create_default_12_words_human(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["wallet", "create"])
    assert result.exit_code == 0
    assert "Wallet created successfully!" in result.stdout
    assert DUMMY_ADDRESS in result.stdout
    assert DUMMY_PUBKEY in result.stdout
    assert "Seed Phrase (12 words):" in result.stdout
    assert "SAVE YOUR SEED PHRASE!" in result.stdout


def test_wallet_create_24_words_json(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["wallet", "create", "--words", "24", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["address"] == DUMMY_ADDRESS
    assert payload["public_key"] == DUMMY_PUBKEY
    assert len(payload["seed_phrase"]) == 24


def test_wallet_create_invalid_word_count_exits_nonzero(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["wallet", "create", "--words", "15"])
    assert result.exit_code == 1
    assert "Number of seed words must be 12 or 24" in result.stderr
    assert "Traceback" not in result.stderr


def test_wallet_balance_human_output(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(
        cli.main,
        ["wallet", "balance", DUMMY_ADDRESS, "--node", "https://node.rustchain.test"],
    )
    assert result.exit_code == 0
    assert f"Address:  {DUMMY_ADDRESS}" in result.stdout
    assert "Balance:  125 RTC" in result.stdout
    assert "Nonce:    7" in result.stdout
    assert fake_env.calls == [("get_balance", DUMMY_ADDRESS)]


def test_wallet_balance_json_output(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["wallet", "balance", DUMMY_ADDRESS, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == {"balance": 125, "nonce": 7}


def test_wallet_send_human_output(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(
        cli.main,
        [
            "wallet",
            "send",
            DUMMY_ADDRESS,
            DUMMY_TO_ADDRESS,
            "25",
            "--fee",
            "1",
            "--seed",
            DUMMY_SEED_12,
            "--node",
            "https://node.rustchain.test",
        ],
    )
    assert result.exit_code == 0
    assert "Transfer submitted!" in result.stdout
    assert f"From:     {DUMMY_ADDRESS}" in result.stdout
    assert f"To:       {DUMMY_TO_ADDRESS}" in result.stdout
    assert "Amount:   25 RTC" in result.stdout
    assert "Fee:      1 RTC" in result.stdout
    assert "Status:   accepted" in result.stdout
    assert "TX Hash:  0xabc123def456" in result.stdout
    assert fake_env.calls == [
        ("wallet_transfer_with_wallet", DUMMY_ADDRESS, DUMMY_TO_ADDRESS, 25, 1)
    ]


def test_wallet_send_json_output(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(
        cli.main,
        [
            "wallet",
            "send",
            DUMMY_ADDRESS,
            DUMMY_TO_ADDRESS,
            "10",
            "--seed",
            DUMMY_SEED_12,
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["tx_hash"] == "0xabc123def456"
    assert data["status"] == "accepted"


def test_wallet_send_address_mismatch_exits_nonzero(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(
        cli.main,
        [
            "wallet",
            "send",
            "RTCwrong_sender_address_000000000000000",
            DUMMY_TO_ADDRESS,
            "10",
            "--seed",
            DUMMY_SEED_12,
        ],
    )
    assert result.exit_code == 1
    assert "Address mismatch" in result.stderr
    assert fake_env.calls == []


# ─────────────────────────────────────────────────────────────────
# 3. Node, Epoch, Miners, Attest Commands (Human + JSON)
# ─────────────────────────────────────────────────────────────────

def test_node_status_healthy_human(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["node", "--node", "https://node.rustchain.test"])
    assert result.exit_code == 0
    assert "Node is healthy" in result.stdout
    assert "version:  2.4.0" in result.stdout
    assert "uptime:  86400" in result.stdout


def test_node_status_degraded_human(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    fake_env.health_response = {"status": "degraded", "version": "2.4.0"}
    result = runner.invoke(cli.main, ["node"])
    assert result.exit_code == 0
    assert "Node status: degraded" in result.stdout


def test_node_status_json(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["node", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["version"] == "2.4.0"


def test_epoch_info_human(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["epoch", "--node", "https://node.rustchain.test"])
    assert result.exit_code == 0
    assert "Epoch Info:" in result.stdout
    assert "epoch:  412" in result.stdout
    assert "slot:  8192" in result.stdout


def test_epoch_info_json(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["epoch", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == {"epoch": 412, "slot": 8192, "miners_active": 64}


def test_miners_list_human(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["miners", "list", "--node", "https://node.rustchain.test"])
    assert result.exit_code == 0
    assert "Active Miners (2):" in result.stdout
    assert "miner-g4-ppc" in result.stdout
    assert "miner-m2-arm" in result.stdout


def test_miners_list_json(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(cli.main, ["miners", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["miner_id"] == "miner-g4-ppc"


def test_attest_human_full_flow(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(
        cli.main,
        [
            "attest",
            DUMMY_ADDRESS,
            "--seed",
            DUMMY_SEED_12,
            "--node",
            "https://node.rustchain.test",
        ],
    )
    assert result.exit_code == 0
    assert "Requesting attestation challenge..." in result.stdout
    assert "Submitting attestation..." in result.stdout
    assert "Attestation submitted!" in result.stdout
    assert [c[0] for c in fake_env.calls] == [
        "get_attestation_status",
        "attest_challenge",
        "attest_submit",
    ]


def test_attest_empty_challenge_graceful_exit(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    fake_env.attest_challenge_response = {"challenge": ""}
    result = runner.invoke(
        cli.main,
        ["attest", DUMMY_ADDRESS, "--seed", DUMMY_SEED_12],
    )
    assert result.exit_code == 0
    assert "No challenge received." in result.stdout
    assert [c[0] for c in fake_env.calls] == [
        "get_attestation_status",
        "attest_challenge",
    ]


def test_attest_address_mismatch_exits_nonzero(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    result = runner.invoke(
        cli.main,
        ["attest", "RTCmismatch00000000000000000000000000", "--seed", DUMMY_SEED_12],
    )
    assert result.exit_code == 1
    assert "Address mismatch" in result.stderr
    assert fake_env.calls == []


# ─────────────────────────────────────────────────────────────────
# 4. Error Paths: Unreachable Node, Non-JSON 200, HTTP 4xx/5xx, Bad Inputs
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "argv,method_name,exc",
    [
        (
            ["wallet", "balance", DUMMY_ADDRESS],
            "get_balance",
            SDKConnectionError("Failed to connect to https://50.28.86.131: Connection refused"),
        ),
        (
            ["wallet", "balance", DUMMY_ADDRESS],
            "get_balance",
            APIError("Invalid JSON in 200 response from node", status_code=200),
        ),
        (
            ["node"],
            "health",
            HealthError("HTTP 503 Service Unavailable"),
        ),
        (
            ["epoch"],
            "get_epoch",
            EpochError("HTTP 500 Internal Server Error"),
        ),
        (
            ["miners", "list"],
            "get_miners",
            APIError("HTTP 404 Not Found", status_code=404),
        ),
        (
            ["wallet", "send", DUMMY_ADDRESS, DUMMY_TO_ADDRESS, "10", "--seed", DUMMY_SEED_12],
            "wallet_transfer_with_wallet",
            TransferError("Insufficient balance for transfer"),
        ),
        (
            ["attest", DUMMY_ADDRESS, "--seed", DUMMY_SEED_12],
            "get_attestation_status",
            AttestationError("HTTP 401 Unauthorized miner key"),
        ),
    ],
)
def test_cli_sdk_error_paths_exit_nonzero_without_traceback(
    runner: CliRunner,
    fake_env: FakeClient,
    argv: List[str],
    method_name: str,
    exc: Exception,
) -> None:
    fake_env.raise_on[method_name] = exc
    result = runner.invoke(cli.main, argv)
    assert result.exit_code == 1
    assert "Error:" in result.stderr
    assert str(exc) in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "argv,expected_err",
    [
        (
            ["wallet", "send", DUMMY_ADDRESS, DUMMY_TO_ADDRESS, "abc", "--seed", DUMMY_SEED_12],
            "Invalid value",
        ),
        (
            ["wallet", "send", DUMMY_ADDRESS, DUMMY_TO_ADDRESS, "10"],
            "Missing option '--seed'",
        ),
        (
            ["wallet", "balance"],
            "Missing argument 'ADDRESS'",
        ),
        (
            ["attest", DUMMY_ADDRESS],
            "Missing option '--seed'",
        ),
    ],
)
def test_cli_missing_options_and_non_numeric_amount_rejected(
    runner: CliRunner,
    fake_env: FakeClient,
    argv: List[str],
    expected_err: str,
) -> None:
    result = runner.invoke(cli.main, argv)
    assert result.exit_code != 0
    assert expected_err in result.stderr


def test_wallet_send_validation_error_on_bad_amount_or_address(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    fake_env.raise_on["wallet_transfer_with_wallet"] = ValidationError(
        "Amount must be strictly positive (> 0)"
    )
    result = runner.invoke(
        cli.main,
        ["wallet", "send", DUMMY_ADDRESS, DUMMY_TO_ADDRESS, "0", "--seed", DUMMY_SEED_12],
    )
    assert result.exit_code == 1
    assert "Amount must be strictly positive" in result.stderr


# ─────────────────────────────────────────────────────────────────
# 5. Strict xfail Regression Nets (#8564, #8565, #8566, #8580, #8618)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="Rustchain#8564")
def test_regression_8564_wallet_send_accepts_fractional_amount_and_fee(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    """
    Regression net for Rustchain#8564:
    `rustchain wallet send <from> <to> 0.5 --fee 0.01 --seed ...` must parse fractional
    RTC amounts and fees rather than failing with Click int conversion exit code 2.
    """
    result = runner.invoke(
        cli.main,
        [
            "wallet",
            "send",
            DUMMY_ADDRESS,
            DUMMY_TO_ADDRESS,
            "0.5",
            "--fee",
            "0.01",
            "--seed",
            DUMMY_SEED_12,
        ],
    )
    assert result.exit_code == 0
    assert len(fake_env.calls) == 1
    assert fake_env.calls[0][0] == "wallet_transfer_with_wallet"


@pytest.mark.xfail(strict=True, reason="Rustchain#8565")
def test_regression_8565_documented_node_status_and_epoch_info_subcommands(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    """
    Regression net for Rustchain#8565:
    README and CLI docstring advertise `rustchain node status` and `rustchain epoch info`.
    """
    res_node = runner.invoke(cli.main, ["node", "status"])
    res_epoch = runner.invoke(cli.main, ["epoch", "info"])
    assert res_node.exit_code == 0
    assert res_epoch.exit_code == 0
    assert ("health",) in fake_env.calls
    assert ("get_epoch",) in fake_env.calls


@pytest.mark.xfail(strict=True, reason="Rustchain#8566")
def test_regression_8566_attest_json_executes_full_attestation_flow(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    """
    Regression net for Rustchain#8566:
    `rustchain attest <address> --seed ... --json` must execute challenge -> sign -> submit
    and output the attestation result as JSON, not return early after `get_attestation_status`.
    """
    result = runner.invoke(
        cli.main,
        ["attest", DUMMY_ADDRESS, "--seed", DUMMY_SEED_12, "--json"],
    )
    assert result.exit_code == 0
    assert [c[0] for c in fake_env.calls] == [
        "get_attestation_status",
        "attest_challenge",
        "attest_submit",
    ]
    payload = json.loads(result.stdout)
    assert payload.get("status") == "verified"


@pytest.mark.xfail(strict=True, reason="Rustchain#8580")
def test_regression_8580_wallet_balance_reads_canonical_amount_rtc_field(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    """
    Regression net for Rustchain#8580:
    Canonical `/wallet/balance` responses return `{"amount_i64": 21000000, "amount_rtc": 21, "miner_id": ...}`.
    The CLI must display `21 RTC` instead of falling back to `0 RTC`.
    """
    fake_env.balance_response = {
        "amount_i64": 21000000,
        "amount_rtc": 21,
        "miner_id": DUMMY_ADDRESS,
    }
    result = runner.invoke(cli.main, ["wallet", "balance", DUMMY_ADDRESS])
    assert result.exit_code == 0
    assert "Balance:  21 RTC" in result.stdout


@pytest.mark.xfail(strict=True, reason="Rustchain#8618")
def test_regression_8618_no_float_money_exact_decimal_serialization(
    runner: CliRunner, fake_env: FakeClient
) -> None:
    """
    Regression net for Rustchain#8618:
    `wallet send --amount 0.1` and `0.29` must parse via exact `Decimal` (or integer minor units),
    never binary `float`, preserving exact decimal representation without IEEE-754 drift.
    """
    result = runner.invoke(
        cli.main,
        [
            "wallet",
            "send",
            DUMMY_ADDRESS,
            DUMMY_TO_ADDRESS,
            "0.1",
            "--fee",
            "0.01",
            "--seed",
            DUMMY_SEED_12,
        ],
    )
    assert result.exit_code == 0
    assert len(fake_env.calls) == 1
    _, _, _, sent_amount, sent_fee = fake_env.calls[0]
    assert not isinstance(sent_amount, float), "Money amount must not use binary float"
    assert not isinstance(sent_fee, float), "Money fee must not use binary float"
    assert Decimal(str(sent_amount)) == Decimal("0.1")
    assert Decimal(str(sent_fee)) == Decimal("0.01")
