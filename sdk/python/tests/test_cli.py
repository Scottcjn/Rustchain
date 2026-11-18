# SPDX-License-Identifier: MIT
"""Click CliRunner test suite for ``sdk/python/rustchain_sdk/cli.py`` (#17181).

All HTTP calls are mocked in-process with ``respx`` (assert_all_mocked=True) so
no test ever touches a live socket or node.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import List

import httpx
import pytest
import respx
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from rustchain_sdk import __version__
from rustchain_sdk.cli import main
from rustchain_sdk.client import DEFAULT_NODE_URL
from rustchain_sdk.wallet import RustChainWallet

CUSTOM_NODE_URL = "https://50.28.86.131:8099"
RECIPIENT_ADDR = "RTC9999999999999999999999999999999999999999"


@pytest.fixture(autouse=True)
def _clean_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent container proxy environment variables from interfering with httpx URL parsing."""
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def runner() -> CliRunner:
    import inspect

    params = inspect.signature(CliRunner.__init__).parameters
    if "mix_stderr" in params:
        return CliRunner(mix_stderr=False)
    return CliRunner()


@pytest.fixture
def sender_wallet() -> RustChainWallet:
    return RustChainWallet.from_seed_phrase(["abandon"] * 12)


@pytest.fixture
def sender_seed(sender_wallet: RustChainWallet) -> str:
    return " ".join(sender_wallet.seed_phrase)


def _assert_no_traceback(result) -> None:
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert "Traceback (most recent call last)" not in combined


# ---------------------------------------------------------------------------
# 1. --help & --version across every group and subcommand
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv,expected_token",
    [
        (["--help"], "RustChain CLI"),
        (["wallet", "--help"], "Wallet management commands"),
        (["wallet", "create", "--help"], "--words"),
        (["wallet", "balance", "--help"], "ADDRESS"),
        (["wallet", "send", "--help"], "--seed"),
        (["node", "--help"], "Check node health status"),
        (["epoch", "--help"], "Get current epoch information"),
        (["miners", "--help"], "Miner management commands"),
        (["miners", "list", "--help"], "List active miners"),
        (["attest", "--help"], "WALLET_ADDRESS"),
    ],
)
def test_help_for_every_group_and_command(
    runner: CliRunner, argv: List[str], expected_token: str
):
    result = runner.invoke(main, argv)
    assert result.exit_code == 0, result.stderr
    assert expected_token in result.stdout
    _assert_no_traceback(result)


def test_version_option_outputs_sdk_version(runner: CliRunner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "rustchain" in result.stdout.lower()


# ---------------------------------------------------------------------------
# 2. wallet create / balance / send — success paths (human & --json)
# ---------------------------------------------------------------------------


def test_wallet_create_default_12_words_human(runner: CliRunner):
    result = runner.invoke(main, ["wallet", "create"])
    assert result.exit_code == 0, result.stderr
    assert "Wallet created successfully!" in result.stdout
    assert "Address:" in result.stdout
    assert "RTC" in result.stdout
    assert "Public Key:" in result.stdout
    assert "Seed Phrase (12 words):" in result.stdout
    assert "SAVE YOUR SEED PHRASE!" in result.stdout


def test_wallet_create_24_words_json(runner: CliRunner):
    result = runner.invoke(main, ["wallet", "create", "--words", "24", "--json"])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= {"version", "address", "seed_phrase", "derivation_path"}
    assert payload["version"] == 1
    assert payload["address"].startswith("RTC")
    assert len(payload["address"]) == 43
    assert isinstance(payload["seed_phrase"], list)
    assert len(payload["seed_phrase"]) == 24


def test_wallet_create_invalid_word_count_exits_nonzero(runner: CliRunner):
    result = runner.invoke(main, ["wallet", "create", "--words", "15"])
    assert result.exit_code == 1
    assert "Number of seed words must be 12 or 24" in result.stderr
    _assert_no_traceback(result)


@respx.mock
def test_wallet_balance_human_and_json_output(
    runner: CliRunner, sender_wallet: RustChainWallet
):
    node_payload = {
        "address": sender_wallet.address,
        "balance": 125,
        "nonce": 7,
    }
    route = respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
        return_value=httpx.Response(200, json=node_payload)
    )

    human_res = runner.invoke(main, ["wallet", "balance", sender_wallet.address])
    assert human_res.exit_code == 0, human_res.stderr
    assert sender_wallet.address in human_res.stdout
    assert "125 RTC" in human_res.stdout
    assert "Nonce:" in human_res.stdout and "7" in human_res.stdout
    assert route.calls.last.request.url.params["address"] == sender_wallet.address

    json_res = runner.invoke(
        main, ["wallet", "balance", sender_wallet.address, "--node", DEFAULT_NODE_URL, "--json"]
    )
    assert json_res.exit_code == 0, json_res.stderr
    parsed = json.loads(json_res.stdout)
    assert parsed == node_payload


@respx.mock
def test_wallet_send_human_and_json_verifies_ed25519_signature(
    runner: CliRunner, sender_wallet: RustChainWallet, sender_seed: str
):
    respx.get(f"{CUSTOM_NODE_URL}/network/info").mock(
        return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
    )
    tx_response = {"ok": True, "tx_hash": "0xdeadbeefcafe1234", "status": "pending"}
    post_route = respx.post(f"{CUSTOM_NODE_URL}/wallet/transfer/signed").mock(
        return_value=httpx.Response(200, json=tx_response)
    )

    human = runner.invoke(
        main,
        [
            "wallet",
            "send",
            sender_wallet.address,
            RECIPIENT_ADDR,
            "25",
            "--fee",
            "1",
            "--seed",
            sender_seed,
            "--node",
            CUSTOM_NODE_URL,
        ],
    )
    assert human.exit_code == 0, human.stderr
    assert "Transfer submitted!" in human.stdout
    assert sender_wallet.address in human.stdout
    assert RECIPIENT_ADDR in human.stdout
    assert "25 RTC" in human.stdout
    assert "1 RTC" in human.stdout
    assert "0xdeadbeefcafe1234" in human.stdout

    wire_body = json.loads(post_route.calls.last.request.content)
    assert wire_body["from_address"] == sender_wallet.address
    assert wire_body["to_address"] == RECIPIENT_ADDR
    assert wire_body["amount_rtc"] == 25
    assert wire_body["fee_rtc"] == 1
    assert wire_body["chain_id"] == "rustchain-mainnet-v2"
    assert wire_body["public_key"] == sender_wallet.public_key_hex

    # Verify the Ed25519 signature sent over the wire
    signed_msg = json.dumps(
        {
            "amount": 25.0,
            "chain_id": "rustchain-mainnet-v2",
            "fee": 1.0,
            "from": sender_wallet.address,
            "memo": "",
            "nonce": str(wire_body["nonce"]),
            "to": RECIPIENT_ADDR,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(wire_body["public_key"])).verify(
        bytes.fromhex(wire_body["signature"]), signed_msg
    )

    json_res = runner.invoke(
        main,
        [
            "wallet",
            "send",
            sender_wallet.address,
            RECIPIENT_ADDR,
            "10",
            "--seed",
            sender_seed,
            "--node",
            CUSTOM_NODE_URL,
            "--json",
        ],
    )
    assert json_res.exit_code == 0, json_res.stderr
    assert json.loads(json_res.stdout) == tx_response


# ---------------------------------------------------------------------------
# 3. node / epoch / miners list / attest — success paths (human & --json)
# ---------------------------------------------------------------------------


@respx.mock
def test_node_command_human_json_and_custom_node_override(runner: CliRunner):
    health_payload = {
        "status": "ok",
        "ok": True,
        "version": "2.2.1-rip200",
        "uptime_s": 867443,
        "db_rw": True,
    }
    route = respx.get(f"{CUSTOM_NODE_URL}/health").mock(
        return_value=httpx.Response(200, json=health_payload)
    )

    human = runner.invoke(main, ["node", "--node", CUSTOM_NODE_URL])
    assert human.exit_code == 0, human.stderr
    assert "Node is healthy" in human.stdout
    assert "2.2.1-rip200" in human.stdout
    assert "867443" in human.stdout
    assert route.called

    as_json = runner.invoke(main, ["node", "--node", CUSTOM_NODE_URL, "--json"])
    assert as_json.exit_code == 0, as_json.stderr
    assert json.loads(as_json.stdout) == health_payload


@respx.mock
def test_epoch_command_human_and_json(runner: CliRunner):
    epoch_payload = {
        "epoch": 144,
        "slot": 512,
        "epoch_pot": 1.5,
        "enrolled_miners": 31,
    }
    respx.get(f"{DEFAULT_NODE_URL}/epoch").mock(
        return_value=httpx.Response(200, json=epoch_payload)
    )

    human = runner.invoke(main, ["epoch"])
    assert human.exit_code == 0, human.stderr
    assert "Epoch Info:" in human.stdout
    assert "144" in human.stdout
    assert "31" in human.stdout

    as_json = runner.invoke(main, ["epoch", "--json"])
    assert as_json.exit_code == 0, as_json.stderr
    assert json.loads(as_json.stdout) == epoch_payload


@respx.mock
def test_miners_list_command_human_and_json(runner: CliRunner):
    miners_payload = [
        {"miner": "ppc-g4-1", "device_arch": "PowerPC G4", "antiquity_multiplier": 2.5},
        {"miner": "sparc-u5", "device_arch": "UltraSPARC", "antiquity_multiplier": 2.1},
    ]
    respx.get(f"{CUSTOM_NODE_URL}/miners").mock(
        return_value=httpx.Response(200, json={"miners": miners_payload})
    )

    human = runner.invoke(main, ["miners", "list", "--node", CUSTOM_NODE_URL])
    assert human.exit_code == 0, human.stderr
    assert "Active Miners (2):" in human.stdout
    assert "ppc-g4-1" in human.stdout
    assert "sparc-u5" in human.stdout

    as_json = runner.invoke(main, ["miners", "list", "--node", CUSTOM_NODE_URL, "--json"])
    assert as_json.exit_code == 0, as_json.stderr
    assert json.loads(as_json.stdout) == miners_payload


@respx.mock
def test_attest_command_full_challenge_sign_submit_flow(
    runner: CliRunner, sender_wallet: RustChainWallet, sender_seed: str
):
    status_route = respx.get(f"{DEFAULT_NODE_URL}/attestation/status").mock(
        return_value=httpx.Response(200, json={"enrolled": True, "epoch": 144})
    )
    challenge_nonce = "challenge-144-9f8e7d6c5b4a"
    challenge_route = respx.post(f"{DEFAULT_NODE_URL}/attestation/challenge").mock(
        return_value=httpx.Response(200, json={"challenge": challenge_nonce})
    )
    submit_route = respx.post(f"{DEFAULT_NODE_URL}/attestation/submit").mock(
        return_value=httpx.Response(200, json={"status": "attested", "ok": True})
    )

    res = runner.invoke(
        main,
        ["attest", sender_wallet.address, "--seed", sender_seed],
    )
    assert res.exit_code == 0, res.stderr
    assert "Requesting attestation challenge..." in res.stdout
    assert "Submitting attestation..." in res.stdout
    assert "Attestation submitted!" in res.stdout
    assert status_route.called and challenge_route.called and submit_route.called

    submit_body = json.loads(submit_route.calls.last.request.content)
    assert submit_body["miner_public_key"] == sender_wallet.public_key_hex
    assert submit_body["challenge_response"] == challenge_nonce
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(sender_wallet.public_key_hex)).verify(
        bytes.fromhex(submit_body["signature"]), challenge_nonce.encode("utf-8")
    )


# ---------------------------------------------------------------------------
# 4. Error paths: unreachable node, non-JSON 200, HTTP 4xx/5xx, bad address,
#    bad amount (abc, negative, 0), missing required options
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["wallet", "balance", RECIPIENT_ADDR],
        ["node"],
        ["epoch"],
        ["miners", "list"],
    ],
)
@respx.mock
def test_unreachable_node_exits_nonzero_with_stderr_and_no_traceback(
    runner: CliRunner, argv: List[str]
):
    respx.route().mock(side_effect=httpx.ConnectError("Connection refused"))
    result = runner.invoke(main, argv)
    assert result.exit_code != 0
    assert "Error:" in result.stderr
    _assert_no_traceback(result)


@pytest.mark.parametrize(
    "status_code,error_json,expected_msg",
    [
        (400, {"error": "invalid wallet address format"}, "invalid wallet address format"),
        (403, {"message": "forbidden miner key"}, "forbidden miner key"),
        (500, {"error": "database locked"}, "database locked"),
    ],
)
@respx.mock
def test_http_4xx_5xx_exits_nonzero_with_diagnostic_on_stderr(
    runner: CliRunner, status_code: int, error_json: dict, expected_msg: str
):
    respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
        return_value=httpx.Response(status_code, json=error_json)
    )
    result = runner.invoke(main, ["wallet", "balance", "bad-address"])
    assert result.exit_code == 1
    assert expected_msg in result.stderr
    _assert_no_traceback(result)


@respx.mock
def test_wallet_send_address_mismatch_exits_nonzero_before_any_http_call(
    runner: CliRunner, sender_seed: str
):
    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    result = runner.invoke(
        main,
        [
            "wallet",
            "send",
            RECIPIENT_ADDR,
            RECIPIENT_ADDR,
            "10",
            "--seed",
            sender_seed,
        ],
    )
    assert result.exit_code == 1
    assert "Address mismatch" in result.stderr
    assert not route.called
    _assert_no_traceback(result)


@pytest.mark.parametrize(
    "argv",
    [
        ["wallet", "send", RECIPIENT_ADDR, RECIPIENT_ADDR, "10"],
        ["attest", RECIPIENT_ADDR],
        ["wallet", "balance"],
    ],
)
def test_missing_required_options_or_arguments_exits_nonzero(
    runner: CliRunner, argv: List[str]
):
    result = runner.invoke(main, argv)
    assert result.exit_code != 0
    assert result.stderr.strip() != ""
    _assert_no_traceback(result)


def test_wallet_send_bad_amount_abc_exits_nonzero(
    runner: CliRunner, sender_wallet: RustChainWallet, sender_seed: str
):
    result = runner.invoke(
        main,
        [
            "wallet",
            "send",
            sender_wallet.address,
            RECIPIENT_ADDR,
            "abc",
            "--seed",
            sender_seed,
        ],
    )
    assert result.exit_code != 0
    assert result.stderr.strip() != ""
    _assert_no_traceback(result)


def test_wallet_send_negative_flag_syntax_exits_nonzero(
    runner: CliRunner, sender_wallet: RustChainWallet, sender_seed: str
):
    result = runner.invoke(
        main,
        [
            "wallet",
            "send",
            sender_wallet.address,
            RECIPIENT_ADDR,
            "-5",
            "--seed",
            sender_seed,
        ],
    )
    assert result.exit_code != 0
    assert result.stderr.strip() != ""
    _assert_no_traceback(result)


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8618: CLI wallet send currently does not reject negative/zero amounts before signing",
)
@pytest.mark.parametrize("bad_amount", ["-5", "0"])
@respx.mock
def test_wallet_send_negative_or_zero_amount_exits_nonzero(
    runner: CliRunner,
    sender_wallet: RustChainWallet,
    sender_seed: str,
    bad_amount: str,
):
    route = respx.route().mock(return_value=httpx.Response(200, json={"ok": True}))
    result = runner.invoke(
        main,
        [
            "wallet",
            "send",
            "--seed",
            sender_seed,
            "--",
            sender_wallet.address,
            RECIPIENT_ADDR,
            bad_amount,
        ],
    )
    assert result.exit_code != 0
    assert result.stderr.strip() != ""
    assert not route.called
    _assert_no_traceback(result)


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#17180/#17181: RustChainClient._get currently wraps non-JSON 200 as {'raw_response': ...} instead of raising APIError",
)
@respx.mock
def test_non_json_200_exits_nonzero_with_stderr(runner: CliRunner):
    respx.get(f"{DEFAULT_NODE_URL}/health").mock(
        return_value=httpx.Response(
            200,
            text="<!DOCTYPE html><html><body>not a node</body></html>",
            headers={"Content-Type": "text/html"},
        )
    )
    result = runner.invoke(main, ["node"])
    assert result.exit_code != 0
    assert result.stderr.strip() != ""
    _assert_no_traceback(result)


# ---------------------------------------------------------------------------
# 5. Regression tests for #8564, #8565, #8566, #8580, #8618 + No Float Money
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8564: wallet send currently declares amount and --fee as type=int, rejecting fractional RTC",
)
@respx.mock
def test_regression_8564_wallet_send_accepts_fractional_amount_and_fee(
    runner: CliRunner, sender_wallet: RustChainWallet, sender_seed: str
):
    respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
        return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
    )
    post_route = respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
        return_value=httpx.Response(200, json={"tx_hash": "0xfrac8564", "status": "pending"})
    )
    result = runner.invoke(
        main,
        [
            "wallet",
            "send",
            sender_wallet.address,
            RECIPIENT_ADDR,
            "0.5",
            "--fee",
            "0.01",
            "--seed",
            sender_seed,
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert post_route.called


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8565: README documents 'rustchain node status' and 'rustchain epoch info' which cli.py rejects",
)
@pytest.mark.parametrize(
    "argv,endpoint,payload",
    [
        (["node", "status"], "/health", {"status": "ok", "version": "2.2.1-rip200"}),
        (["epoch", "info"], "/epoch", {"epoch": 144, "slot": 10}),
    ],
)
@respx.mock
def test_regression_8565_documented_node_status_and_epoch_info_subcommands(
    runner: CliRunner, argv: List[str], endpoint: str, payload: dict
):
    respx.get(f"{DEFAULT_NODE_URL}{endpoint}").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = runner.invoke(main, argv)
    assert result.exit_code == 0, result.stderr


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8566: attest --json returns early after get_attestation_status without requesting challenge or submitting",
)
@respx.mock
def test_regression_8566_attest_json_executes_challenge_and_submit(
    runner: CliRunner, sender_wallet: RustChainWallet, sender_seed: str
):
    respx.get(f"{DEFAULT_NODE_URL}/attestation/status").mock(
        return_value=httpx.Response(200, json={"enrolled": True})
    )
    challenge_route = respx.post(f"{DEFAULT_NODE_URL}/attestation/challenge").mock(
        return_value=httpx.Response(200, json={"challenge": "ch-8566"})
    )
    submit_route = respx.post(f"{DEFAULT_NODE_URL}/attestation/submit").mock(
        return_value=httpx.Response(200, json={"status": "attested", "ok": True})
    )

    result = runner.invoke(
        main,
        ["attest", sender_wallet.address, "--seed", sender_seed, "--json"],
    )
    assert result.exit_code == 0, result.stderr
    assert challenge_route.called
    assert submit_route.called
    parsed = json.loads(result.stdout)
    assert parsed.get("status") == "attested"


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8580: wallet balance prints '0 RTC' when node returns canonical 'amount_rtc' instead of legacy 'balance'",
)
@respx.mock
def test_regression_8580_wallet_balance_reads_canonical_amount_rtc(
    runner: CliRunner, sender_wallet: RustChainWallet
):
    respx.get(f"{DEFAULT_NODE_URL}/wallet/balance").mock(
        return_value=httpx.Response(
            200,
            json={
                "miner_id": sender_wallet.address,
                "amount_rtc": 42.75,
                "amount_i64": 42750000,
                "nonce": 3,
            },
        )
    )
    result = runner.invoke(main, ["wallet", "balance", sender_wallet.address])
    assert result.exit_code == 0, result.stderr
    assert "42.75 RTC" in result.stdout


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8618: wallet send must accept Decimal/fractional amounts and serialize exact decimal / micro-RTC without float drift",
)
@pytest.mark.parametrize("exact_amount_str", ["0.1", "0.29", "0.000001"])
@respx.mock
def test_regression_8618_no_float_money_exact_decimal_serialization(
    runner: CliRunner,
    sender_wallet: RustChainWallet,
    sender_seed: str,
    exact_amount_str: str,
):
    respx.get(f"{DEFAULT_NODE_URL}/network/info").mock(
        return_value=httpx.Response(200, json={"chain_id": "rustchain-mainnet-v2"})
    )
    post_route = respx.post(f"{DEFAULT_NODE_URL}/wallet/transfer/signed").mock(
        return_value=httpx.Response(200, json={"tx_hash": "0xdec8618", "status": "pending"})
    )
    result = runner.invoke(
        main,
        [
            "wallet",
            "send",
            sender_wallet.address,
            RECIPIENT_ADDR,
            exact_amount_str,
            "--fee",
            "0",
            "--seed",
            sender_seed,
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert post_route.called
    raw_json = post_route.calls.last.request.content.decode("utf-8")
    parsed = json.loads(raw_json, parse_float=Decimal)
    expected_dec = Decimal(exact_amount_str)
    assert Decimal(str(parsed["amount_rtc"])) == expected_dec
    assert int(Decimal(str(parsed["amount_rtc"])) * Decimal(1_000_000)) == int(
        expected_dec * Decimal(1_000_000)
    )
