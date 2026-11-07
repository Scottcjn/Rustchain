# SPDX-License-Identifier: MIT
"""Click CliRunner suite for the RustChain CLI (sdk/python/rustchain_sdk/cli.py).

HTTP is mocked with respx — the same mocking library used by rustchain_sdk/tests.
Every request is intercepted in-process, so no test can reach a live node: any
unmocked route raises ConnectError before touching a socket.

Command -> test coverage:
    --help / --version        help tests below
    wallet create|balance|send  wallet_* tests
    node                      node_* tests
    epoch                     epoch_* tests
    miners list               miners_* tests
    attest                    attest_* tests

Regression tests for Rustchain#8564/#8565/#8566/#8580/#8618 assert the
*expected* behaviour described in each issue and are marked xfail(strict=True)
while those fixes are unmerged; they flip to hard failures the day a fix lands.
"""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo-root runs without pip install

from rustchain_sdk import __version__
from rustchain_sdk.cli import main
from rustchain_sdk.wallet import RustChainWallet

NODE = "http://mock-node.test"
MIRROR = "http://rustchain-mirror.test:9090"

SEED_WORDS = ["abandon"] * 12
SEED = " ".join(SEED_WORDS)
WALLET = RustChainWallet.from_seed_phrase(SEED_WORDS)
ADDR = WALLET.address
OTHER = "RTC" + "b" * 40

HEALTH = {"status": "ok", "version": "1.4.2", "height": 123456}
EPOCH = {"epoch_number": 7, "start_time": 1700000000, "end_time": 1700086400}
MINERS = [{"miner_id": "stmr", "address": ADDR}, {"miner_id": "gq6s", "address": OTHER}]
BALANCE_LEGACY = {"balance": 42, "nonce": 3}
BALANCE_CANON = {"amount_i64": 21000000, "amount_rtc": 21, "miner_id": "stmr"}
NETWORK_INFO = {"chain_id": "rustchain-mainnet", "network": "mainnet", "version": "1.4.2"}
TX_RESULT = {"status": "submitted", "tx_hash": "a" * 64}
ATTEST_STATUS = {"attested": False, "miner_public_key": WALLET.public_key_hex}
ATTEST_CHALLENGE = {"challenge": "chall-9f3a", "expires_in": 300}
ATTEST_SUBMIT = {"status": "attested", "tx_hash": "b" * 64}

runner = CliRunner()


def run_cli(*args):
    return runner.invoke(main, [str(a) for a in args])


def stderr_of(result):
    try:
        return result.stderr  # click >= 8.2 always captures streams separately
    except ValueError:
        # shortcut: click < 8.2 mixes the streams; drop when click is pinned to >= 8.2
        return result.output


def assert_clean_error(result, exit_code=None, message="Error"):
    """Non-zero exit carrying a message on stderr and never a traceback."""
    if exit_code is not None:
        assert result.exit_code == exit_code
    else:
        assert result.exit_code != 0
    err = stderr_of(result)
    assert message in err, f"expected {message!r} on stderr, got {err!r}"
    assert "Traceback" not in (result.output or "") + err


def mock_send_routes(mock):
    mock.get(f"{NODE}/network/info").mock(return_value=httpx.Response(200, json=NETWORK_INFO))
    return mock.post(f"{NODE}/wallet/transfer/signed").mock(
        return_value=httpx.Response(200, json=TX_RESULT)
    )


@pytest.fixture()
def node_mock():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


# ──────────────────────────────────────────────────────────────────
# Help & version surface (Rustchain#8565 guards the documented grammar)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "args",
    [
        [],
        ["wallet"],
        ["node"],
        ["epoch"],
        ["miners"],
        ["attest"],
        ["wallet", "create"],
        ["wallet", "balance"],
        ["wallet", "send"],
        ["miners", "list"],
    ],
)
def test_help_works_for_every_group_and_command(args):
    result = run_cli(*args, "--help")
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_root_help_lists_every_documented_command():
    result = run_cli("--help")
    assert result.exit_code == 0
    for command in ("wallet", "node", "epoch", "miners", "attest"):
        assert command in result.output


def test_version_flag_reports_the_sdk_version():
    result = run_cli("--version")
    assert result.exit_code == 0
    assert f"rustchain, version {__version__}" in result.output


# ──────────────────────────────────────────────────────────────────
# wallet create
# ──────────────────────────────────────────────────────────────────

def test_wallet_create_human_output_shows_address_and_warning():
    result = run_cli("wallet", "create")
    assert result.exit_code == 0
    assert "Wallet created successfully" in result.output
    assert "Address:      RTC" in result.output
    assert "Seed Phrase (12 words):" in result.output
    assert "SAVE YOUR SEED PHRASE" in result.output


def test_wallet_create_json_has_documented_export_keys():
    result = run_cli("wallet", "create", "--json")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert set(data) == {"version", "address", "seed_phrase", "derivation_path"}
    assert data["address"].startswith(RustChainWallet.ADDRESS_PREFIX)
    assert len(data["seed_phrase"]) == 12


def test_wallet_create_words_24_produces_24_word_seed():
    result = run_cli("wallet", "create", "--words", "24", "--json")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["seed_phrase"]) == 24
    assert all(isinstance(word, str) and word for word in data["seed_phrase"])


def test_wallet_create_invalid_word_count_exits_nonzero(node_mock):
    node_mock.route().mock(side_effect=AssertionError("wallet create must not hit the network"))
    result = run_cli("wallet", "create", "--words", "15")
    assert_clean_error(result, exit_code=1)
    assert "must be 12 or 24" in stderr_of(result)


# ──────────────────────────────────────────────────────────────────
# wallet balance
# ──────────────────────────────────────────────────────────────────

def test_wallet_balance_human_output_shows_legacy_payload_figures(node_mock):
    route = node_mock.get(f"{NODE}/wallet/balance").mock(
        return_value=httpx.Response(200, json=BALANCE_LEGACY)
    )
    result = run_cli("wallet", "balance", ADDR, "--node", NODE)
    assert result.exit_code == 0
    assert f"Address:  {ADDR}" in result.output
    assert "Balance:  42 RTC" in result.output  # control case from Rustchain#8580
    assert "Nonce:    3" in result.output
    assert route.calls[0].request.url.params["address"] == ADDR


def test_wallet_balance_json_output_matches_node_payload(node_mock):
    node_mock.get(f"{NODE}/wallet/balance").mock(
        return_value=httpx.Response(200, json=BALANCE_LEGACY)
    )
    result = run_cli("wallet", "balance", ADDR, "--node", NODE, "--json")
    assert result.exit_code == 0
    assert json.loads(result.output) == BALANCE_LEGACY


def test_wallet_balance_bad_address_exits_nonzero(node_mock):
    node_mock.get(f"{NODE}/wallet/balance").mock(
        return_value=httpx.Response(400, json={"error": "invalid address"})
    )
    result = run_cli("wallet", "balance", "RTC-not-an-address", "--node", NODE)
    assert_clean_error(result, exit_code=1)
    assert "invalid address" in stderr_of(result)


# ──────────────────────────────────────────────────────────────────
# wallet send
# ──────────────────────────────────────────────────────────────────

def test_wallet_send_human_output_shows_transfer_figures(node_mock):
    transfer = mock_send_routes(node_mock)
    result = run_cli("wallet", "send", ADDR, OTHER, "5", "--seed", SEED, "--fee", "1", "--node", NODE)
    assert result.exit_code == 0
    assert "Transfer submitted" in result.output
    assert f"From:     {ADDR}" in result.output
    assert f"To:       {OTHER}" in result.output
    assert "Amount:   5 RTC" in result.output
    assert "Fee:      1 RTC" in result.output
    assert TX_RESULT["tx_hash"] in result.output

    body = json.loads(transfer.calls[0].request.content)
    assert body["from_address"] == ADDR
    assert body["to_address"] == OTHER
    assert Decimal(str(body["amount_rtc"])) == Decimal("5")
    assert Decimal(str(body["fee_rtc"])) == Decimal("1")
    assert re.fullmatch(r"[0-9a-f]{128}", body["signature"])
    assert body["public_key"] == WALLET.public_key_hex
    # cross-network replay binding must not regress
    assert body["chain_id"] == NETWORK_INFO["chain_id"]


def test_wallet_send_json_output_matches_node_result(node_mock):
    mock_send_routes(node_mock)
    result = run_cli("wallet", "send", ADDR, OTHER, "5", "--seed", SEED, "--node", NODE, "--json")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == TX_RESULT["status"]
    assert data["tx_hash"] == TX_RESULT["tx_hash"]


def test_wallet_send_address_mismatch_stops_before_any_request(node_mock):
    node_mock.route().mock(side_effect=AssertionError("mismatched seed must not hit the network"))
    result = run_cli("wallet", "send", OTHER, ADDR, "5", "--seed", SEED, "--node", NODE)
    assert_clean_error(result, exit_code=1, message="Address mismatch")


@pytest.mark.parametrize(
    "args",
    [
        ["wallet", "send", ADDR, OTHER, "5"],  # missing required --seed (Rustchain#8565 grammar)
        ["attest", ADDR],                      # missing required --seed
    ],
)
def test_missing_required_seed_option_exits_nonzero(args):
    with respx.mock(assert_all_called=False) as mock:
        mock.route().mock(side_effect=AssertionError("parser error must not hit the network"))
        result = run_cli(*args, "--node", NODE)
    assert_clean_error(result, exit_code=2)
    assert "Missing option '--seed'" in stderr_of(result)


def test_wallet_send_non_numeric_amount_exits_nonzero(node_mock):
    mock_send_routes(node_mock)
    node_mock.route().mock(side_effect=AssertionError("bad amount must not hit the network"))
    result = run_cli("wallet", "send", ADDR, OTHER, "abc", "--seed", SEED, "--node", NODE)
    assert_clean_error(result, exit_code=2)
    assert "Invalid value for 'AMOUNT'" in stderr_of(result)


def test_wallet_send_negative_amount_exits_nonzero(node_mock):
    mock_send_routes(node_mock)
    node_mock.post(f"{NODE}/wallet/transfer/signed").mock(
        return_value=httpx.Response(400, json={"error": "amount must be positive"})
    )
    result = run_cli("wallet", "send", ADDR, OTHER, "-5", "--seed", SEED, "--node", NODE)
    assert_clean_error(result)


def test_wallet_send_zero_amount_exits_nonzero(node_mock):
    mock_send_routes(node_mock)
    node_mock.post(f"{NODE}/wallet/transfer/signed").mock(
        return_value=httpx.Response(400, json={"error": "amount must be positive"})
    )
    result = run_cli("wallet", "send", ADDR, OTHER, "0", "--seed", SEED, "--node", NODE)
    assert_clean_error(result)


# ──────────────────────────────────────────────────────────────────
# node / epoch / miners — success paths
# ──────────────────────────────────────────────────────────────────

def test_node_status_human_output_shows_key_fields(node_mock):
    node_mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH))
    result = run_cli("node", "--node", NODE)
    assert result.exit_code == 0
    assert "Node is healthy" in result.output
    assert "status:  ok" in result.output
    assert "version:  1.4.2" in result.output


def test_node_status_json_output_matches_node_payload(node_mock):
    node_mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH))
    result = run_cli("node", "--json", "--node", NODE)
    assert result.exit_code == 0
    assert json.loads(result.output) == HEALTH


def test_node_flag_overrides_the_default_node(node_mock):
    route = node_mock.get(f"{MIRROR}/health").mock(return_value=httpx.Response(200, json=HEALTH))
    result = run_cli("node", "--json", "--node", MIRROR)
    assert result.exit_code == 0
    request_url = route.calls[0].request.url
    assert request_url.host == "rustchain-mirror.test"
    assert request_url.port == 9090
    assert json.loads(result.output) == HEALTH


def test_epoch_info_human_output_shows_key_fields(node_mock):
    node_mock.get(f"{NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH))
    result = run_cli("epoch", "--node", NODE)
    assert result.exit_code == 0
    assert "Epoch Info:" in result.output
    assert "epoch_number:  7" in result.output


def test_epoch_info_json_output_matches_node_payload(node_mock):
    node_mock.get(f"{NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH))
    result = run_cli("epoch", "--json", "--node", NODE)
    assert result.exit_code == 0
    assert json.loads(result.output) == EPOCH


def test_miners_list_human_output_lists_every_miner(node_mock):
    node_mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json=MINERS))
    result = run_cli("miners", "list", "--node", NODE)
    assert result.exit_code == 0
    assert "Active Miners (2):" in result.output
    assert '"miner_id": "stmr"' in result.output
    assert '"miner_id": "gq6s"' in result.output


def test_miners_list_json_output_matches_node_payload(node_mock):
    node_mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json=MINERS))
    result = run_cli("miners", "list", "--json", "--node", NODE)
    assert result.exit_code == 0
    assert json.loads(result.output) == MINERS


def test_miners_list_accepts_wrapped_object_payload(node_mock):
    node_mock.get(f"{NODE}/miners").mock(return_value=httpx.Response(200, json={"miners": MINERS}))
    result = run_cli("miners", "list", "--node", NODE)
    assert result.exit_code == 0
    assert "Active Miners (2):" in result.output


# ──────────────────────────────────────────────────────────────────
# attest — success path on the current (non-JSON) grammar; see xfail below for --json
# ──────────────────────────────────────────────────────────────────

def test_attest_requests_challenge_signs_and_submits(node_mock):
    status = node_mock.get(f"{NODE}/attestation/status").mock(
        return_value=httpx.Response(200, json=ATTEST_STATUS)
    )
    node_mock.post(f"{NODE}/attestation/challenge").mock(
        return_value=httpx.Response(200, json=ATTEST_CHALLENGE)
    )
    submit = node_mock.post(f"{NODE}/attestation/submit").mock(
        return_value=httpx.Response(200, json=ATTEST_SUBMIT)
    )

    result = run_cli("attest", ADDR, "--seed", SEED, "--node", NODE)
    assert result.exit_code == 0
    assert "Attestation submitted" in result.output
    assert '"status": "attested"' in result.output

    assert status.calls[0].request.url.params["miner_public_key"] == WALLET.public_key_hex
    body = json.loads(submit.calls[0].request.content)
    assert body["miner_public_key"] == WALLET.public_key_hex
    assert body["challenge_response"] == ATTEST_CHALLENGE["challenge"]

    Ed25519PublicKey.from_public_bytes(bytes.fromhex(WALLET.public_key_hex)).verify(
        bytes.fromhex(body["signature"]), ATTEST_CHALLENGE["challenge"].encode()
    )


def test_attest_json_output_parses_as_json(node_mock):
    status = node_mock.get(f"{NODE}/attestation/status").mock(
        return_value=httpx.Response(200, json=ATTEST_STATUS)
    )
    result = run_cli("attest", ADDR, "--seed", SEED, "--node", NODE, "--json")
    assert result.exit_code == 0
    assert isinstance(json.loads(result.output), dict)
    assert status.called


# ──────────────────────────────────────────────────────────────────
# Shared error paths: unreachable node and HTTP 4xx/5xx on every network command
# ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "args",
    [
        ["wallet", "balance", ADDR],
        ["node"],
        ["epoch"],
        ["miners", "list"],
    ],
)
def test_unreachable_node_exits_nonzero_without_traceback(node_mock, args):
    node_mock.route().mock(side_effect=httpx.ConnectError("connection refused"))
    result = run_cli(*args, "--node", NODE)
    assert_clean_error(result, exit_code=1)
    assert "Failed to connect" in stderr_of(result)


@pytest.mark.parametrize("status_code", [400, 403, 500])
def test_http_error_status_exits_nonzero_with_message(node_mock, status_code):
    node_mock.get(f"{NODE}/health").mock(
        return_value=httpx.Response(status_code, json={"error": "node said no"})
    )
    result = run_cli("node", "--node", NODE)
    assert_clean_error(result, exit_code=1)
    err = stderr_of(result)
    assert f"API error {status_code}" in err
    # the node's own message must survive into stderr (Rustchain#8567 regression guard)
    assert "node said no" in err


@pytest.mark.xfail(
    strict=True,
    reason="non-JSON 200 body is currently echoed as raw_response instead of exiting non-zero; flips when the SDK rejects malformed JSON",
)
def test_non_json_200_exits_nonzero_without_traceback(node_mock):
    node_mock.get(f"{NODE}/health").mock(
        return_value=httpx.Response(200, text="<!DOCTYPE html>gateway offline</html>")
    )
    result = run_cli("node", "--json", "--node", NODE)
    assert_clean_error(result)


# ──────────────────────────────────────────────────────────────────
# Regression tests against the *expected* behaviour of open issues.
# xfail(strict=True): each one becomes a hard failure the day its fix is merged,
# which is when this net earns its keep. Remove the marker in that PR's review.
# ──────────────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="Rustchain#8564 fractional amount/fee parser fix not merged")
def test_send_accepts_fractional_amount_and_fee_8564(node_mock):
    transfer = mock_send_routes(node_mock)
    result = run_cli(
        "wallet", "send", ADDR, OTHER, "0.5", "--seed", SEED, "--fee", "0.01", "--node", NODE
    )
    assert result.exit_code == 0, (result.output, stderr_of(result))
    body = json.loads(transfer.calls[0].request.content)
    assert Decimal(str(body["amount_rtc"])) == Decimal("0.5")
    assert Decimal(str(body["fee_rtc"])) == Decimal("0.01")


@pytest.mark.xfail(strict=True, reason="Rustchain#8565 node status grammar fix not merged")
def test_readme_node_status_command_works_8565(node_mock):
    node_mock.get(f"{NODE}/health").mock(return_value=httpx.Response(200, json=HEALTH))
    result = run_cli("node", "status", "--json", "--node", NODE)
    assert result.exit_code == 0, (result.output, stderr_of(result))
    assert json.loads(result.output) == HEALTH


@pytest.mark.xfail(strict=True, reason="Rustchain#8565 epoch info grammar fix not merged")
def test_readme_epoch_info_command_works_8565(node_mock):
    node_mock.get(f"{NODE}/epoch").mock(return_value=httpx.Response(200, json=EPOCH))
    result = run_cli("epoch", "info", "--json", "--node", NODE)
    assert result.exit_code == 0, (result.output, stderr_of(result))
    assert json.loads(result.output) == EPOCH


@pytest.mark.xfail(strict=True, reason="Rustchain#8566 attest --json control-flow fix not merged")
def test_attest_json_runs_challenge_and_submit_8566(node_mock):
    node_mock.get(f"{NODE}/attestation/status").mock(
        return_value=httpx.Response(200, json=ATTEST_STATUS)
    )
    challenge = node_mock.post(f"{NODE}/attestation/challenge").mock(
        return_value=httpx.Response(200, json=ATTEST_CHALLENGE)
    )
    submit = node_mock.post(f"{NODE}/attestation/submit").mock(
        return_value=httpx.Response(200, json=ATTEST_SUBMIT)
    )

    result = run_cli("attest", ADDR, "--seed", SEED, "--node", NODE, "--json")
    assert result.exit_code == 0, (result.output, stderr_of(result))
    # --json only changes the output format; it must not skip the advertised operation chain
    assert challenge.called
    assert submit.called
    assert json.loads(result.output)["status"] == "attested"


@pytest.mark.xfail(strict=True, reason="Rustchain#8580 canonical amount_rtc display fix not merged")
def test_balance_reads_canonical_amount_rtc_field_8580(node_mock):
    # exact payload observed live on rustchain.org in the issue report
    node_mock.get(f"{NODE}/wallet/balance").mock(
        return_value=httpx.Response(200, json=BALANCE_CANON)
    )
    result = run_cli("wallet", "balance", ADDR, "--node", NODE)
    assert result.exit_code == 0, (result.output, stderr_of(result))
    assert "21 RTC" in result.output
    assert "0 RTC" not in result.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8618 exact-decimal money fix not merged")
@pytest.mark.parametrize("amount", ["0.1", "0.29", "10.5", "0.01"])
def test_send_serializes_the_exact_decimal_amount_8618(node_mock, amount):
    transfer = mock_send_routes(node_mock)
    result = run_cli("wallet", "send", ADDR, OTHER, amount, "--seed", SEED, "--node", NODE)
    assert result.exit_code == 0, (result.output, stderr_of(result))

    body = json.loads(transfer.calls[0].request.content.decode(), parse_float=Decimal)
    value = body["amount_rtc"]
    if not isinstance(value, Decimal):
        value = Decimal(str(value))  # also accepts a string-serialized amount
    assert value == Decimal(amount), f"binary-float money drift: {body['amount_rtc']!r}"

    micro_rtc = value.scaleb(6)  # ledger minor units — the conversion that float breaks
    assert micro_rtc == micro_rtc.to_integral_value()
