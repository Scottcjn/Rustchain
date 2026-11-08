"""Click CliRunner test suite for RustChain Python SDK CLI (rustchain_sdk.cli).

Bounty: Scottcjn/rustchain-bounties#17181
Target: Scottcjn/Rustchain

Every command and group is tested through Click's CliRunner.
All HTTP transport is mocked in-process using respx and httpx.
An autouse fixture blocks all socket connections to guarantee zero live network traffic.

Regression tests for #8564, #8565, #8566, #8580, and #8618 are marked with
xfail(strict=True, reason="Rustchain#NNNN") to enforce strict tracking against
unmerged bug fixes.
"""

from __future__ import annotations

import json
import re
import socket
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
import respx
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Ensure sdk/python is in sys.path
_SDK_PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(_SDK_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_SDK_PYTHON_DIR))

from rustchain_sdk import __version__
from rustchain_sdk.cli import main
from rustchain_sdk.wallet import RustChainWallet

# Test fixtures and constants
NODE = "http://node.test"
MIRROR_NODE = "http://mirror.test:8080"

SEED_WORDS = ["abandon"] * 12
SEED = " ".join(SEED_WORDS)
WALLET = RustChainWallet.from_seed_phrase(SEED_WORDS)
ADDRESS = WALLET.address
OTHER_ADDRESS = "RTC" + "b" * 40

HEALTH_OK = {"status": "ok", "version": "1.4.2", "height": 123456}
HEALTH_DEGRADED = {"status": "degraded", "version": "1.4.2", "syncing": True}
EPOCH_INFO = {"epoch_number": 7, "start_time": 1700000000, "end_time": 1700086400}
MINERS_LIST = [
    {"miner_id": "miner-1", "address": ADDRESS},
    {"miner_id": "miner-2", "address": OTHER_ADDRESS},
]
BALANCE_LEGACY = {"balance": 42, "nonce": 3}
BALANCE_CANONICAL = {"amount_i64": 21000000, "amount_rtc": 21, "miner_id": "stmr"}
NETWORK_INFO = {"chain_id": "rustchain-mainnet", "network": "mainnet", "version": "1.4.2"}
TX_RESULT = {"status": "submitted", "tx_hash": "a" * 64}
ATTEST_STATUS = {"attested": False, "miner_public_key": WALLET.public_key_hex}
ATTEST_CHALLENGE = {"challenge": "challenge-xyz-123", "expires_in": 300}
ATTEST_SUBMIT = {"status": "attested", "tx_hash": "b" * 64}


# ─────────────────────────────────────────────────────────────────
# Fixtures and helpers
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def block_live_network(monkeypatch):
    """Enforce complete network isolation: any attempt to open a socket fails."""
    def blocked(*_args, **_kwargs):
        raise AssertionError("Live network access is strictly prohibited in CLI tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CliRunner instance."""
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


def get_stderr(result) -> str:
    """Retrieve stderr output safely across Click versions."""
    try:
        return result.stderr
    except (ValueError, AttributeError):
        return result.output or ""


def assert_clean_error(result, expected_exit_code=None, expected_message=None):
    """Verify non-zero exit code, presence of error message, and zero tracebacks."""
    if expected_exit_code is not None:
        assert result.exit_code == expected_exit_code, (
            f"Expected exit code {expected_exit_code}, got {result.exit_code}. Output: {result.output}"
        )
    else:
        assert result.exit_code != 0, f"Expected non-zero exit code, got 0. Output: {result.output}"

    stderr = get_stderr(result)
    combined = (result.output or "") + "\n" + (stderr or "")
    assert "Traceback (most recent call last)" not in combined, (
        f"Unexpected traceback in error output:\n{combined}"
    )
    if expected_message:
        assert expected_message.lower() in combined.lower(), (
            f"Expected error message {expected_message!r} not found in output:\n{combined}"
        )


def mock_send_routes(mock):
    """Set up standard mocks for transfer transaction submission."""
    mock.get(f"{NODE}/network/info").mock(
        return_value=httpx.Response(200, json=NETWORK_INFO)
    )
    return mock.post(f"{NODE}/wallet/transfer/signed").mock(
        return_value=httpx.Response(200, json=TX_RESULT)
    )


# ─────────────────────────────────────────────────────────────────
# 1. Help and Version surface
# ─────────────────────────────────────────────────────────────────

def test_root_help(runner):
    """Root command --help lists all primary command groups and commands."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.output
    for cmd in ("wallet", "node", "epoch", "miners", "attest"):
        assert cmd in result.output


@pytest.mark.parametrize(
    "cmd_args",
    [
        ["wallet"],
        ["wallet", "create"],
        ["wallet", "balance"],
        ["wallet", "send"],
        ["node"],
        ["epoch"],
        ["miners"],
        ["miners", "list"],
        ["attest"],
    ],
)
def test_help_every_command_and_group(runner, cmd_args):
    """Every command and group supports --help without errors."""
    result = runner.invoke(main, [*cmd_args, "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.output


def test_version_flag(runner):
    """--version outputs the correct SDK version."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert f"rustchain, version {__version__}" in result.output


def test_unknown_command_fails(runner):
    """Invoking an unknown command fails cleanly with exit code 2."""
    result = runner.invoke(main, ["nonexistent_command"])
    assert_clean_error(result, expected_exit_code=2, expected_message="No such command")


# ─────────────────────────────────────────────────────────────────
# 2. Wallet Create command
# ─────────────────────────────────────────────────────────────────

def test_wallet_create_human_default_12_words(runner):
    """wallet create defaults to 12 words and prints human-readable details."""
    result = runner.invoke(main, ["wallet", "create"])
    assert result.exit_code == 0
    assert "Wallet created successfully" in result.output
    assert "Address:      RTC" in result.output
    assert "Public Key:   " in result.output
    assert "Seed Phrase (12 words):" in result.output
    assert "SAVE YOUR SEED PHRASE" in result.output


def test_wallet_create_human_24_words(runner):
    """wallet create --words 24 creates a 24-word seed phrase."""
    result = runner.invoke(main, ["wallet", "create", "--words", "24"])
    assert result.exit_code == 0
    assert "Seed Phrase (24 words):" in result.output


def test_wallet_create_json_output(runner):
    """wallet create --json produces valid JSON with documented export keys."""
    result = runner.invoke(main, ["wallet", "create", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert set(data.keys()) == {"version", "address", "seed_phrase", "derivation_path"}
    assert data["address"].startswith(RustChainWallet.ADDRESS_PREFIX)
    assert len(data["seed_phrase"]) == 12


def test_wallet_create_invalid_words_count(runner):
    """wallet create --words 15 is rejected with exit code 1."""
    result = runner.invoke(main, ["wallet", "create", "--words", "15"])
    assert_clean_error(result, expected_exit_code=1, expected_message="must be 12 or 24")


def test_wallet_create_non_integer_words(runner):
    """wallet create --words abc is rejected by Click parser with exit code 2."""
    result = runner.invoke(main, ["wallet", "create", "--words", "abc"])
    assert_clean_error(result, expected_exit_code=2, expected_message="is not a valid integer")


# ─────────────────────────────────────────────────────────────────
# 3. Wallet Balance command
# ─────────────────────────────────────────────────────────────────

def test_wallet_balance_human(runner):
    """wallet balance prints human-readable address, balance, and nonce."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/wallet/balance").mock(
            return_value=httpx.Response(200, json=BALANCE_LEGACY)
        )
        result = runner.invoke(main, ["wallet", "balance", ADDRESS, "--node", NODE])

    assert result.exit_code == 0
    assert f"Address:  {ADDRESS}" in result.output
    assert "Balance:  42 RTC" in result.output
    assert "Nonce:    3" in result.output


def test_wallet_balance_json(runner):
    """wallet balance --json prints exact JSON returned by the node."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/wallet/balance").mock(
            return_value=httpx.Response(200, json=BALANCE_LEGACY)
        )
        result = runner.invoke(main, ["wallet", "balance", ADDRESS, "--node", NODE, "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == BALANCE_LEGACY


def test_wallet_balance_custom_node(runner):
    """wallet balance uses the custom --node URL."""
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{MIRROR_NODE}/wallet/balance").mock(
            return_value=httpx.Response(200, json=BALANCE_LEGACY)
        )
        result = runner.invoke(main, ["wallet", "balance", ADDRESS, "--node", MIRROR_NODE])

    assert result.exit_code == 0
    assert route.called
    assert route.calls[0].request.url.params["address"] == ADDRESS


def test_wallet_balance_missing_address(runner):
    """wallet balance without address argument fails with exit code 2."""
    result = runner.invoke(main, ["wallet", "balance"])
    assert_clean_error(result, expected_exit_code=2, expected_message="Missing argument 'ADDRESS'")


def test_wallet_balance_bad_address_error(runner):
    """wallet balance with an invalid address rejected by node exits with code 1."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/wallet/balance").mock(
            return_value=httpx.Response(400, json={"error": "invalid address format"})
        )
        result = runner.invoke(main, ["wallet", "balance", "invalid-address", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="invalid address format")


def test_wallet_balance_unreachable_node(runner):
    """wallet balance against an unreachable node exits non-zero without traceback."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/wallet/balance").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = runner.invoke(main, ["wallet", "balance", ADDRESS, "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="Failed to connect")


def test_wallet_balance_http_500(runner):
    """wallet balance on HTTP 500 error exits non-zero without traceback."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/wallet/balance").mock(
            return_value=httpx.Response(500, json={"error": "internal node error"})
        )
        result = runner.invoke(main, ["wallet", "balance", ADDRESS, "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="API error 500")


# ─────────────────────────────────────────────────────────────────
# 4. Wallet Send command
# ─────────────────────────────────────────────────────────────────

def test_wallet_send_human_success(runner):
    """wallet send successfully submits transfer and prints human figures."""
    with respx.mock(assert_all_called=False) as mock:
        transfer_route = mock_send_routes(mock)
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "10",
                "--fee", "1",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert result.exit_code == 0
    assert "Transfer submitted" in result.output
    assert f"From:     {ADDRESS}" in result.output
    assert f"To:       {OTHER_ADDRESS}" in result.output
    assert "Amount:   10 RTC" in result.output
    assert "Fee:      1 RTC" in result.output
    assert TX_RESULT["tx_hash"] in result.output
    assert transfer_route.called


def test_wallet_send_json_success(runner):
    """wallet send --json prints the exact JSON transaction result."""
    with respx.mock(assert_all_called=False) as mock:
        mock_send_routes(mock)
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "5",
                "--seed", SEED,
                "--node", NODE,
                "--json",
            ],
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == TX_RESULT


def test_wallet_send_payload_and_signature_verification(runner):
    """wallet send builds a valid canonical payload with verifiable Ed25519 signature."""
    with respx.mock(assert_all_called=False) as mock:
        transfer_route = mock_send_routes(mock)
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "7",
                "--fee", "2",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert result.exit_code == 0
    assert transfer_route.called
    req_body = json.loads(transfer_route.calls[0].request.content)

    assert req_body["from_address"] == ADDRESS
    assert req_body["to_address"] == OTHER_ADDRESS
    assert req_body["amount_rtc"] == 7
    assert req_body["fee_rtc"] == 2
    assert req_body["public_key"] == WALLET.public_key_hex
    assert req_body["chain_id"] == NETWORK_INFO["chain_id"]

    # Cryptographically verify that the Ed25519 signature matches the canonical signed message
    canonical_dict = {
        "amount": float(req_body["amount_rtc"]),
        "chain_id": req_body["chain_id"],
        "fee": float(req_body["fee_rtc"]),
        "from": req_body["from_address"],
        "memo": "",
        "nonce": str(req_body["nonce"]),
        "to": req_body["to_address"],
    }
    canonical_bytes = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(req_body["public_key"]))
    pubkey.verify(bytes.fromhex(req_body["signature"]), canonical_bytes)


def test_wallet_send_seed_mismatch_fails_before_network(runner):
    """wallet send rejects seed producing an address different from <from_address> before network."""
    with respx.mock(assert_all_called=False) as mock:
        mock.route().mock(side_effect=AssertionError("Mismatched seed must not contact the network"))
        result = runner.invoke(
            main,
            [
                "wallet", "send", OTHER_ADDRESS, ADDRESS, "5",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert_clean_error(result, expected_exit_code=1, expected_message="Address mismatch")


def test_wallet_send_missing_seed_option(runner):
    """wallet send requires --seed option; fails with exit code 2 when omitted."""
    result = runner.invoke(main, ["wallet", "send", ADDRESS, OTHER_ADDRESS, "5", "--node", NODE])
    assert_clean_error(result, expected_exit_code=2, expected_message="Missing option '--seed'")


@pytest.mark.parametrize(
    "args,expected_msg",
    [
        (["wallet", "send"], "Missing argument 'FROM_ADDRESS'"),
        (["wallet", "send", ADDRESS], "Missing argument 'TO_ADDRESS'"),
        (["wallet", "send", ADDRESS, OTHER_ADDRESS], "Missing argument 'AMOUNT'"),
    ],
)
def test_wallet_send_missing_arguments(runner, args, expected_msg):
    """wallet send requires from, to, and amount arguments."""
    result = runner.invoke(main, [*args, "--seed", SEED])
    assert_clean_error(result, expected_exit_code=2, expected_message=expected_msg)


def test_wallet_send_bad_amount_non_numeric(runner):
    """wallet send rejects non-numeric amount 'abc' before any network request."""
    with respx.mock(assert_all_called=False) as mock:
        mock.route().mock(side_effect=AssertionError("Bad amount must not contact the network"))
        result = runner.invoke(
            main,
            ["wallet", "send", ADDRESS, OTHER_ADDRESS, "abc", "--seed", SEED, "--node", NODE],
        )

    assert_clean_error(result, expected_exit_code=2, expected_message="Invalid value for 'AMOUNT'")


def test_wallet_send_bad_fee_non_numeric(runner):
    """wallet send rejects non-numeric fee before any network request."""
    with respx.mock(assert_all_called=False) as mock:
        mock.route().mock(side_effect=AssertionError("Bad fee must not contact the network"))
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "5",
                "--fee", "abc",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert_clean_error(result, expected_exit_code=2, expected_message="Invalid value for '--fee'")


def test_wallet_send_negative_amount_error(runner):
    """wallet send with negative amount is rejected by node with clean error."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/network/info").mock(return_value=httpx.Response(200, json=NETWORK_INFO))
        mock.post(f"{NODE}/wallet/transfer/signed").mock(
            return_value=httpx.Response(400, json={"error": "amount must be positive"})
        )
        # Using '--' tells Click that '-5' is the positional AMOUNT, not an option flag
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS,
                "--seed", SEED,
                "--node", NODE,
                "--", "-5",
            ],
        )

    assert_clean_error(result, expected_exit_code=1, expected_message="amount must be positive")


def test_wallet_send_zero_amount_error(runner):
    """wallet send with zero amount is rejected by node with clean error."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/network/info").mock(return_value=httpx.Response(200, json=NETWORK_INFO))
        mock.post(f"{NODE}/wallet/transfer/signed").mock(
            return_value=httpx.Response(400, json={"error": "amount must be positive"})
        )
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "0",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert_clean_error(result, expected_message="amount must be positive")


def test_wallet_send_unreachable_node(runner):
    """wallet send against unreachable node exits non-zero without traceback."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/network/info").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "5",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert_clean_error(result, expected_exit_code=1, expected_message="Failed to connect")


def test_wallet_send_http_500(runner):
    """wallet send on HTTP 500 exits non-zero without traceback."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/network/info").mock(return_value=httpx.Response(200, json=NETWORK_INFO))
        mock.post(f"{NODE}/wallet/transfer/signed").mock(
            return_value=httpx.Response(500, json={"error": "ledger submission failed"})
        )
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "5",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert_clean_error(result, expected_exit_code=1, expected_message="API error 500")


# ─────────────────────────────────────────────────────────────────
# 5. Node command
# ─────────────────────────────────────────────────────────────────

def test_node_status_human_healthy(runner):
    """node command prints healthy status and key-value fields."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH_OK))
        result = runner.invoke(main, ["node", "--node", NODE])

    assert result.exit_code == 0
    assert "Node is healthy" in result.output
    assert "status:  ok" in result.output
    assert "version:  1.4.2" in result.output


def test_node_status_human_degraded(runner):
    """node command reports degraded status when status != 'ok'."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH_DEGRADED))
        result = runner.invoke(main, ["node", "--node", NODE])

    assert result.exit_code == 0
    assert "Node status: degraded" in result.output


def test_node_status_json(runner):
    """node --json prints exact JSON payload from node."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH_OK))
        result = runner.invoke(main, ["node", "--node", NODE, "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == HEALTH_OK


def test_node_status_custom_node(runner):
    """node --node uses the specified URL."""
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{MIRROR_NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH_OK))
        result = runner.invoke(main, ["node", "--node", MIRROR_NODE])

    assert result.exit_code == 0
    assert route.called


def test_node_status_unreachable(runner):
    """node exits non-zero on connection failure."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(side_effect=httpx.ConnectError("host down"))
        result = runner.invoke(main, ["node", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="Failed to connect")


@pytest.mark.parametrize("status_code", [400, 403, 500, 503])
def test_node_status_http_errors(runner, status_code):
    """node exits non-zero on HTTP error responses."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(
            return_value=httpx.Response(status_code, json={"error": f"error {status_code}"})
        )
        result = runner.invoke(main, ["node", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message=f"API error {status_code}")


# ─────────────────────────────────────────────────────────────────
# 6. Epoch command
# ─────────────────────────────────────────────────────────────────

def test_epoch_info_human(runner):
    """epoch command prints human-readable epoch info."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH_INFO))
        result = runner.invoke(main, ["epoch", "--node", NODE])

    assert result.exit_code == 0
    assert "Epoch Info:" in result.output
    assert "epoch_number:  7" in result.output


def test_epoch_info_json(runner):
    """epoch --json prints exact JSON payload."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH_INFO))
        result = runner.invoke(main, ["epoch", "--node", NODE, "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == EPOCH_INFO


def test_epoch_info_custom_node(runner):
    """epoch --node contacts the specified node."""
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{MIRROR_NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH_INFO))
        result = runner.invoke(main, ["epoch", "--node", MIRROR_NODE])

    assert result.exit_code == 0
    assert route.called


def test_epoch_info_unreachable(runner):
    """epoch exits non-zero on connection failure."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/epoch").mock(side_effect=httpx.ConnectError("host down"))
        result = runner.invoke(main, ["epoch", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="Failed to connect")


@pytest.mark.parametrize("status_code", [400, 403, 500])
def test_epoch_info_http_errors(runner, status_code):
    """epoch exits non-zero on HTTP error responses."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/epoch").mock(
            return_value=httpx.Response(status_code, json={"error": f"error {status_code}"})
        )
        result = runner.invoke(main, ["epoch", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message=f"API error {status_code}")


# ─────────────────────────────────────────────────────────────────
# 7. Miners List command
# ─────────────────────────────────────────────────────────────────

def test_miners_list_human(runner):
    """miners list prints count and details of active miners."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json=MINERS_LIST))
        result = runner.invoke(main, ["miners", "list", "--node", NODE])

    assert result.exit_code == 0
    assert "Active Miners (2):" in result.output
    assert '"miner_id": "miner-1"' in result.output
    assert '"miner_id": "miner-2"' in result.output


def test_miners_list_empty(runner):
    """miners list handles an empty list cleanly."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json=[]))
        result = runner.invoke(main, ["miners", "list", "--node", NODE])

    assert result.exit_code == 0
    assert "Active Miners (0):" in result.output


def test_miners_list_wrapped_dict(runner):
    """miners list handles wrapped object response format {'miners': [...]}."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json={"miners": MINERS_LIST}))
        result = runner.invoke(main, ["miners", "list", "--node", NODE])

    assert result.exit_code == 0
    assert "Active Miners (2):" in result.output


def test_miners_list_json(runner):
    """miners list --json prints miners list as JSON."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json=MINERS_LIST))
        result = runner.invoke(main, ["miners", "list", "--node", NODE, "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == MINERS_LIST


def test_miners_list_custom_node(runner):
    """miners list --node contacts the specified node."""
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{MIRROR_NODE}/miners").mock(return_value=httpx.Response(200, json=MINERS_LIST))
        result = runner.invoke(main, ["miners", "list", "--node", MIRROR_NODE])

    assert result.exit_code == 0
    assert route.called


def test_miners_list_unreachable(runner):
    """miners list exits non-zero on connection failure."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/miners").mock(side_effect=httpx.ConnectError("host down"))
        result = runner.invoke(main, ["miners", "list", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="Failed to connect")


@pytest.mark.parametrize("status_code", [400, 403, 500])
def test_miners_list_http_errors(runner, status_code):
    """miners list exits non-zero on HTTP errors."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/miners").mock(
            return_value=httpx.Response(status_code, json={"error": f"error {status_code}"})
        )
        result = runner.invoke(main, ["miners", "list", "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message=f"API error {status_code}")


# ─────────────────────────────────────────────────────────────────
# 8. Attest command
# ─────────────────────────────────────────────────────────────────

def test_attest_human_full_flow(runner):
    """attest runs full flow: status check, challenge request, sign, and submit."""
    with respx.mock(assert_all_called=False) as mock:
        status_route = mock.get(f"{NODE}/attestation/status").mock(
            return_value=httpx.Response(200, json=ATTEST_STATUS)
        )
        challenge_route = mock.post(f"{NODE}/attestation/challenge").mock(
            return_value=httpx.Response(200, json=ATTEST_CHALLENGE)
        )
        submit_route = mock.post(f"{NODE}/attestation/submit").mock(
            return_value=httpx.Response(200, json=ATTEST_SUBMIT)
        )

        result = runner.invoke(
            main,
            ["attest", ADDRESS, "--seed", SEED, "--node", NODE],
        )

    assert result.exit_code == 0
    assert "Requesting attestation challenge..." in result.output
    assert "Submitting attestation..." in result.output
    assert "Attestation submitted!" in result.output

    assert status_route.called
    assert challenge_route.called
    assert submit_route.called

    # Verify cryptographic signature submitted in attestation
    submit_req = json.loads(submit_route.calls[0].request.content)
    assert submit_req["miner_public_key"] == WALLET.public_key_hex
    assert submit_req["challenge_response"] == ATTEST_CHALLENGE["challenge"]

    pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(submit_req["miner_public_key"]))
    pubkey.verify(
        bytes.fromhex(submit_req["signature"]),
        ATTEST_CHALLENGE["challenge"].encode("utf-8"),
    )


def test_attest_human_no_challenge_received(runner):
    """attest prints warning if node returns empty challenge."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/attestation/status").mock(
            return_value=httpx.Response(200, json=ATTEST_STATUS)
        )
        mock.post(f"{NODE}/attestation/challenge").mock(
            return_value=httpx.Response(200, json={"challenge": ""})
        )
        result = runner.invoke(
            main,
            ["attest", ADDRESS, "--seed", SEED, "--node", NODE],
        )

    assert result.exit_code == 0
    assert "No challenge received" in result.output


def test_attest_json_output_current_behavior(runner):
    """attest --json currently outputs the status dictionary as JSON."""
    with respx.mock(assert_all_called=False) as mock:
        status_route = mock.get(f"{NODE}/attestation/status").mock(
            return_value=httpx.Response(200, json=ATTEST_STATUS)
        )
        result = runner.invoke(
            main,
            ["attest", ADDRESS, "--seed", SEED, "--node", NODE, "--json"],
        )

    assert result.exit_code == 0
    assert status_route.called
    data = json.loads(result.output)
    assert data == ATTEST_STATUS


def test_attest_seed_mismatch_fails_before_network(runner):
    """attest rejects address mismatch before any network call."""
    with respx.mock(assert_all_called=False) as mock:
        mock.route().mock(side_effect=AssertionError("Mismatched seed must not contact the network"))
        result = runner.invoke(
            main,
            ["attest", OTHER_ADDRESS, "--seed", SEED, "--node", NODE],
        )

    assert_clean_error(result, expected_exit_code=1, expected_message="Address mismatch")


def test_attest_missing_seed_option(runner):
    """attest requires --seed; exits 2 when missing."""
    result = runner.invoke(main, ["attest", ADDRESS, "--node", NODE])
    assert_clean_error(result, expected_exit_code=2, expected_message="Missing option '--seed'")


def test_attest_missing_wallet_address(runner):
    """attest requires wallet address argument; exits 2 when missing."""
    result = runner.invoke(main, ["attest", "--seed", SEED])
    assert_clean_error(result, expected_exit_code=2, expected_message="Missing argument 'WALLET_ADDRESS'")


def test_attest_unreachable(runner):
    """attest exits non-zero on connection failure."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/attestation/status").mock(side_effect=httpx.ConnectError("host down"))
        result = runner.invoke(main, ["attest", ADDRESS, "--seed", SEED, "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="Failed to connect")


@pytest.mark.parametrize("status_code", [400, 403, 500])
def test_attest_http_errors(runner, status_code):
    """attest exits non-zero on HTTP errors."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/attestation/status").mock(
            return_value=httpx.Response(status_code, json={"error": f"error {status_code}"})
        )
        result = runner.invoke(main, ["attest", ADDRESS, "--seed", SEED, "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message=f"API error {status_code}")


# ─────────────────────────────────────────────────────────────────
# 9. Cross-Cutting Protocol and Response Integrity Tests
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "cmd_args,path",
    [
        (["node"], "/health"),
        (["epoch"], "/epoch"),
        (["wallet", "balance", ADDRESS], "/wallet/balance"),
    ],
)
def test_json_array_on_object_endpoint_fails_cleanly(runner, cmd_args, path):
    """When an endpoint expecting a JSON object receives a JSON array, client rejects it cleanly."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}{path}").mock(return_value=httpx.Response(200, json=["not", "an", "object"]))
        result = runner.invoke(main, [*cmd_args, "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="Expected JSON object response")


@pytest.mark.parametrize(
    "cmd_args,path",
    [
        (["node"], "/health"),
        (["epoch"], "/epoch"),
        (["wallet", "balance", ADDRESS], "/wallet/balance"),
        (["miners", "list"], "/miners"),
    ],
)
def test_redirect_refused_cleanly(runner, cmd_args, path):
    """API redirects (HTTP 301/302) are rejected by client to prevent security downgrade."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}{path}").mock(
            return_value=httpx.Response(302, headers={"Location": "http://evil.invalid/path"})
        )
        result = runner.invoke(main, [*cmd_args, "--node", NODE])

    assert_clean_error(result, expected_exit_code=1, expected_message="API redirected")


def test_non_json_200_surfaced_without_traceback(runner):
    """Non-JSON 200 responses do not cause Python tracebacks."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(
            return_value=httpx.Response(200, text="<!DOCTYPE html><html>Server Maintenance</html>")
        )
        result = runner.invoke(main, ["node", "--node", NODE])

    assert "Traceback (most recent call last)" not in (result.output + get_stderr(result))
    assert "Server Maintenance" in result.output


# ─────────────────────────────────────────────────────────────────
# 10. Regression Tests for Open Issues
# Marked xfail(strict=True) so they turn into hard failures when fixes land.
# ─────────────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="Rustchain#8564")
def test_regression_8564_fractional_amount_and_fee(runner):
    """Rustchain#8564: wallet send should accept fractional RTC amounts and fees."""
    with respx.mock(assert_all_called=False) as mock:
        transfer_route = mock_send_routes(mock)
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, "0.5",
                "--fee", "0.01",
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert result.exit_code == 0, (result.output, get_stderr(result))
    req = json.loads(transfer_route.calls[0].request.content)
    assert Decimal(str(req["amount_rtc"])) == Decimal("0.5")
    assert Decimal(str(req["fee_rtc"])) == Decimal("0.01")


@pytest.mark.xfail(strict=True, reason="Rustchain#8565")
def test_regression_8565_node_status_grammar(runner):
    """Rustchain#8565: README documented command 'rustchain node status' should work."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH_OK))
        result = runner.invoke(main, ["node", "status", "--node", NODE])

    assert result.exit_code == 0, (result.output, get_stderr(result))
    assert "Node is healthy" in result.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8565")
def test_regression_8565_epoch_info_grammar(runner):
    """Rustchain#8565: README documented command 'rustchain epoch info' should work."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH_INFO))
        result = runner.invoke(main, ["epoch", "info", "--node", NODE])

    assert result.exit_code == 0, (result.output, get_stderr(result))
    assert "Epoch Info:" in result.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8566")
def test_regression_8566_attest_json_runs_full_flow(runner):
    """Rustchain#8566: attest --json should run the full challenge/sign/submit flow."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/attestation/status").mock(return_value=httpx.Response(200, json=ATTEST_STATUS))
        challenge_route = mock.post(f"{NODE}/attestation/challenge").mock(
            return_value=httpx.Response(200, json=ATTEST_CHALLENGE)
        )
        submit_route = mock.post(f"{NODE}/attestation/submit").mock(
            return_value=httpx.Response(200, json=ATTEST_SUBMIT)
        )

        result = runner.invoke(
            main,
            ["attest", ADDRESS, "--seed", SEED, "--node", NODE, "--json"],
        )

    assert result.exit_code == 0, (result.output, get_stderr(result))
    assert challenge_route.called
    assert submit_route.called
    data = json.loads(result.output)
    assert data["status"] == "attested"


@pytest.mark.xfail(strict=True, reason="Rustchain#8580")
def test_regression_8580_balance_canonical_amount_rtc(runner):
    """Rustchain#8580: wallet balance should read canonical 'amount_rtc' field rather than printing 0 RTC."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{NODE}/wallet/balance").mock(
            return_value=httpx.Response(200, json=BALANCE_CANONICAL)
        )
        result = runner.invoke(main, ["wallet", "balance", ADDRESS, "--node", NODE])

    assert result.exit_code == 0, (result.output, get_stderr(result))
    assert "21 RTC" in result.output
    assert "0 RTC" not in result.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8618")
@pytest.mark.parametrize("amount_str", ["0.1", "0.29", "10.5", "0.01"])
def test_regression_8618_exact_decimal_no_float_money(runner, amount_str):
    """Rustchain#8618: wallet send must preserve exact decimal precision without float binary representation drift."""
    with respx.mock(assert_all_called=False) as mock:
        transfer_route = mock_send_routes(mock)
        result = runner.invoke(
            main,
            [
                "wallet", "send", ADDRESS, OTHER_ADDRESS, amount_str,
                "--seed", SEED,
                "--node", NODE,
            ],
        )

    assert result.exit_code == 0, (result.output, get_stderr(result))
    body = json.loads(transfer_route.calls[0].request.content.decode("utf-8"), parse_float=Decimal)
    raw_amount = body["amount_rtc"]
    decimal_amount = raw_amount if isinstance(raw_amount, Decimal) else Decimal(str(raw_amount))
    assert decimal_amount == Decimal(amount_str), f"Binary float precision drift detected: {raw_amount!r}"
    # Verify ledger micro-RTC scale has no fractional sub-units lost
    micro_rtc = decimal_amount * 1_000_000
    assert micro_rtc == int(micro_rtc)
