"""
CLI tests for the RustChain Python SDK (`rustchain` command).

Every test is fully offline: all HTTP traffic is mocked with respx at the
``--node`` base URL (``https://node.test``). respx raises for any request that
has no registered route, so a test that escapes its mocks fails loudly instead
of touching the network.

Layout of the suite
-------------------
1. ``--help`` / ``--version`` smoke tests for every command group and leaf.
2. Success paths: human output and ``--json`` output for each command, with
   mocked node JSON.
3. Error paths: unreachable node, HTTP 4xx/5xx, non-JSON 200, malformed
   arguments, missing required options. Expected: non-zero exit and a message
   on stderr — never a Python traceback.
4. Regression tests for the reproducible CLI bugs this suite is the safety
   net for: Rustchain#8564, #8565, #8566, #8580, #8618. Each strict xfail
   records why it fails today: the covering issue number, or an explicit
   "no tracked issue yet" rationale for spec-mandated behavior no issue
   covers.
5. Exact-decimal tests for #8618. Note: for clean literals, Python's
   shortest-round-trip repr makes float and Decimal indistinguishable on the
   wire, so the suite pairs a tripwire (parser-flip) test with an
   excess-precision rejection test (the actually discriminating case).
"""

import json
import re
from decimal import Decimal

import httpx
import pytest
import respx
from click.testing import CliRunner

from rustchain_sdk.cli import main
from rustchain_sdk import __version__

NODE = "https://node.test"
HEALTH_OK = {"status": "ok", "version": "1.2.3", "uptime_s": 86400}
EPOCH_INFO = {"epoch": 42, "start_time": "2026-11-01T00:00:00Z", "end_time": "2026-11-08T00:00:00Z"}
MINERS = [
    {"miner": "m-1", "architecture": "power8", "tokens": 1234},
    {"miner": "m-2", "architecture": "x86_64", "tokens": 99},
]
BALANCE_LEGACY = {"balance": 42, "nonce": 7}
# Canonical /wallet/balance payload (see Rustchain#8580): the documented field
# is ``amount_rtc``; ``balance`` is only a compatibility alias.
BALANCE_CANONICAL = {"amount_i64": 21000000, "amount_rtc": 21, "miner_id": "stmr"}
NETWORK_INFO = {"chain_id": "rustchain-mainnet-1"}
TRANSFER_RESULT = {"tx_hash": "0xdeadbeefcafe", "status": "pending"}
ATTEST_STATUS = {"miner_public_key": "pk", "attested": False, "epoch": 42}
ATTEST_CHALLENGE = {"challenge": "challenge-data-123", "expires_in": 300}
ATTEST_SUBMIT = {"status": "accepted", "epoch": 42}


def all_output(result) -> str:
    """stdout + stderr, whatever click mixes where."""
    err = getattr(result, "stderr", "") or ""
    return result.output + ("\n" + err if err else "")


def assert_no_traceback(result) -> None:
    assert "Traceback" not in all_output(result)


def invoke(args, **kwargs):
    runner = CliRunner()
    return runner.invoke(main, args, **kwargs)


@pytest.fixture()
def node():
    """A respx router that guarantees no network escapes these tests."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


@pytest.fixture()
def sender_wallet():
    from rustchain_sdk import RustChainWallet

    return RustChainWallet.create(strength=128)


def mock_health(node, body=HEALTH_OK, status=200):
    return node.get(f"{NODE}/health").mock(
        return_value=httpx.Response(status, json=body)
    )


def mock_epoch(node, body=EPOCH_INFO, status=200):
    return node.get(f"{NODE}/epoch").mock(
        return_value=httpx.Response(status, json=body)
    )


def mock_miners(node, body=None, status=200):
    body = MINERS if body is None else body
    return node.get(f"{NODE}/miners").mock(
        return_value=httpx.Response(status, json=body)
    )


def mock_balance(node, body=BALANCE_LEGACY, status=200):
    return node.get(f"{NODE}/wallet/balance").mock(
        return_value=httpx.Response(status, json=body)
    )


def mock_network_info(node, body=NETWORK_INFO, status=200):
    return node.get(f"{NODE}/network/info").mock(
        return_value=httpx.Response(status, json=body)
    )


def mock_transfer_signed(node, body=TRANSFER_RESULT, status=200):
    return node.post(f"{NODE}/wallet/transfer/signed").mock(
        return_value=httpx.Response(status, json=body)
    )


def mock_attestation(node):
    status = node.get(f"{NODE}/attestation/status").mock(
        return_value=httpx.Response(200, json=ATTEST_STATUS)
    )
    challenge = node.post(f"{NODE}/attestation/challenge").mock(
        return_value=httpx.Response(200, json=ATTEST_CHALLENGE)
    )
    submit = node.post(f"{NODE}/attestation/submit").mock(
        return_value=httpx.Response(200, json=ATTEST_SUBMIT)
    )
    return status, challenge, submit


# ─────────────────────────────────────────────────────────────────
# 1. Help / version smoke tests — every command has working help
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["--version"],
        ["wallet", "--help"],
        ["wallet", "create", "--help"],
        ["wallet", "balance", "--help"],
        ["wallet", "send", "--help"],
        ["node", "--help"],
        ["epoch", "--help"],
        ["miners", "--help"],
        ["miners", "list", "--help"],
        ["attest", "--help"],
    ],
    ids=lambda a: " ".join(a),
)
def test_help_and_version(args):
    result = invoke(args)
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    if args == ["--version"]:
        assert __version__ in output
    else:
        assert "Usage" in output


# ─────────────────────────────────────────────────────────────────
# 2. wallet create
# ─────────────────────────────────────────────────────────────────

def test_wallet_create_default_human():
    result = invoke(["wallet", "create"])
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Wallet created successfully" in output
    assert "Address:" in output
    assert "Seed Phrase (12 words):" in output
    assert "SAVE YOUR SEED PHRASE" in output


def test_wallet_create_words_24_human():
    result = invoke(["wallet", "create", "--words", "24"])
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Seed Phrase (24 words):" in output


def test_wallet_create_json_parses_and_has_keys():
    result = invoke(["wallet", "create", "--json"])
    assert result.exit_code == 0
    assert_no_traceback(result)
    data = json.loads(result.output)
    assert data["version"] == 1
    assert data["address"].startswith("RTC")
    assert len(data["seed_phrase"]) == 12
    assert data["derivation_path"] == "m/44'/9000'/0'/0/0"


def test_wallet_create_json_24_words():
    result = invoke(["wallet", "create", "--json", "--words", "24"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["seed_phrase"]) == 24


def test_wallet_create_invalid_words_rejected():
    result = invoke(["wallet", "create", "--words", "13"])
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "12 or 24" in all_output(result)


# ─────────────────────────────────────────────────────────────────
# 3. wallet balance
# ─────────────────────────────────────────────────────────────────

def test_balance_human(node):
    mock_balance(node, BALANCE_LEGACY)
    result = invoke(["wallet", "balance", "RTC" + "a" * 40, "--node", NODE])
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Address:" in output
    assert "42 RTC" in output
    assert "Nonce:    7" in output


def test_balance_json(node):
    mock_balance(node, BALANCE_LEGACY)
    result = invoke(["wallet", "balance", "RTC" + "a" * 40, "--node", NODE, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == BALANCE_LEGACY


def test_balance_unreachable_node(node):
    route = node.get(f"{NODE}/wallet/balance").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = invoke(["wallet", "balance", "RTC" + "a" * 40, "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_balance_http_500_exits_nonzero_with_stderr(node):
    route = mock_balance(node, {"message": "boom"}, status=500)
    result = invoke(["wallet", "balance", "RTC" + "a" * 40, "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


# Note: there is no client-side address validation; this drives a node-side
# 400 response, not a local address check.
def test_balance_http_400_exits_nonzero_with_message(node):
    route = mock_balance(node, {"message": "invalid address", "error": "invalid address"}, status=400)
    result = invoke(["wallet", "balance", "not-an-rtc-address", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert "invalid address" in all_output(result)
    assert_no_traceback(result)
    assert "Error" in all_output(result)


# Rustchain#8580 — the CLI reads ``balance``/``nonce`` and ignores the
# canonical ``amount_rtc`` field, printing "0 RTC" for a funded wallet.
@pytest.mark.xfail(strict=True, reason="Rustchain#8580")
def test_balance_canonical_amount_rtc_field(node):
    mock_balance(node, BALANCE_CANONICAL)
    result = invoke(["wallet", "balance", "stmr", "--node", NODE])
    assert "21 RTC" in all_output(result)


# ─────────────────────────────────────────────────────────────────
# 4. wallet send
# ─────────────────────────────────────────────────────────────────

def test_send_success_human(node, sender_wallet):
    mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    to = "RTC" + "b" * 40
    result = invoke(
        ["wallet", "send", sender_wallet.address, to, "1", "--seed", seed, "--node", NODE]
    )
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Transfer submitted!" in output
    assert "0xdeadbeefcafe" in output
    assert "1 RTC" in output
    assert transfer.called


def test_send_success_json(node, sender_wallet):
    mock_network_info(node)
    mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        [
            "wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "1",
            "--seed", seed, "--node", NODE, "--json",
        ]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == TRANSFER_RESULT


def test_send_payload_fields_include_chain_and_signature(node, sender_wallet):
    network = mock_network_info(node)
    transfer = mock_transfer_signed(node)
    to = "RTC" + "c" * 40
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, to, "2", "--fee", "2", "--seed", seed, "--node", NODE]
    )
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert network.called
    payload = json.loads(transfer.calls.last.request.content)
    assert payload["from_address"] == sender_wallet.address
    assert payload["to_address"] == to
    assert Decimal(str(payload["amount_rtc"])) == Decimal("2")
    assert Decimal(str(payload["fee_rtc"])) == Decimal("2")
    assert payload["chain_id"] == "rustchain-mainnet-1"
    assert payload["public_key"]
    assert bytes.fromhex(payload["signature"])
    assert int(payload["nonce"]) > 0


def test_send_address_mismatch_exits_nonzero(node, sender_wallet):
    network = mock_network_info(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", "RTC" + "0" * 40, "RTC" + "b" * 40, "1", "--seed", seed, "--node", NODE]
    )
    assert result.exit_code != 0
    assert not network.called
    assert_no_traceback(result)
    assert "mismatch" in all_output(result).lower()


def test_send_amount_abc_rejected(node, sender_wallet):
    network = mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "abc", "--seed", seed, "--node", NODE]
    )
    assert result.exit_code != 0
    # rejected at the parser before any HTTP is attempted
    assert not network.called and not transfer.called
    assert_no_traceback(result)
    assert "abc" in all_output(result)


# Click rejects a bare "-1" as an option token at parse time ("No such
# option '-1'", exit 2), so this passes today without validation changes.
# It stays a valid regression guard for the spec's "negative amount exits
# non-zero" requirement.
def test_send_amount_negative_rejected(node, sender_wallet):
    network = mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "-1", "--seed", seed, "--node", NODE]
    )
    assert result.exit_code != 0
    assert not network.called and not transfer.called
    assert_no_traceback(result)
    assert "-1" in all_output(result)


@pytest.mark.xfail(strict=True, reason="bounty #17181 spec requires amount '0' to exit non-zero; zero is accepted by the CLI on main and no issue covers it yet")
def test_send_amount_zero_rejected(node, sender_wallet):
    network = mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "0", "--seed", seed, "--node", NODE]
    )
    assert result.exit_code != 0
    assert not network.called and not transfer.called
    assert_no_traceback(result)


def test_send_unreachable_node(node, sender_wallet):
    route = node.get(f"{NODE}/network/info").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "1", "--seed", seed, "--node", NODE]
    )
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_send_transfer_http_400_exits_nonzero(node, sender_wallet):
    mock_network_info(node)
    route = mock_transfer_signed(node, {"message": "insufficient funds", "error": "insufficient funds"}, status=400)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "1", "--seed", seed, "--node", NODE]
    )
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_send_missing_seed_exits_nonzero(node, sender_wallet):
    network = mock_network_info(node)
    transfer = mock_transfer_signed(node)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "1", "--node", NODE]
    )
    assert result.exit_code != 0
    assert not network.called and not transfer.called
    assert_no_traceback(result)
    assert "seed" in all_output(result).lower()


# Rustchain#8564 — fractional RTC amounts/fees must parse and reach the
# transfer operation. The Click parameters are still ``type=int`` on main.
@pytest.mark.xfail(strict=True, reason="Rustchain#8564")
def test_send_fractional_amount_reaches_transfer(node, sender_wallet):
    mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "0.5", "--seed", seed, "--node", NODE]
    )
    assert result.exit_code == 0
    assert transfer.called


@pytest.mark.xfail(strict=True, reason="Rustchain#8564")
def test_send_fractional_fee_reaches_transfer(node, sender_wallet):
    mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        [
            "wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "1",
            "--fee", "0.01", "--seed", seed, "--node", NODE,
        ]
    )
    assert result.exit_code == 0
    assert transfer.called


# Rustchain#8618 — bounty-required regression: `wallet send --amount 0.1`
# must serialize the exact decimal, not a binary float. Fails on main at the
# #8564 parser gate (exit 2). THIS IS A TRIPWIRE, NOT A DISCRIMINATOR:
# Python's json.dumps uses shortest-round-trip repr, so any literal that
# round-trips cleanly (0.1 does) serializes identically from float or Decimal.
# No clean-literal CLI assertion can distinguish binary-float from Decimal;
# that is why test_send_excess_precision_rejected below exists instead.
# When a #8618 fix lands, this test passes and the strict marker hard-fails
# until the marker is removed — by design.
@pytest.mark.xfail(strict=True, reason="Rustchain#8618")
def test_send_amount_and_fee_are_exact_decimals(node, sender_wallet):
    mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        [
            "wallet", "send", sender_wallet.address, "RTC" + "b" * 40, "0.1",
            "--fee", "0.01", "--seed", seed, "--node", NODE,
        ]
    )
    assert result.exit_code == 0
    raw = transfer.calls.last.request.content
    assert re.search(rb'"amount_rtc":\s*"?0\.1"?', raw)
    assert re.search(rb'"fee_rtc":\s*"?0\.01"?', raw)
    payload = json.loads(raw)
    assert Decimal(str(payload["amount_rtc"])) == Decimal("0.1")
    assert Decimal(str(payload["fee_rtc"])) == Decimal("0.01")


# Rustchain#8618 — the discriminating case. RTC amounts are meaningful to at
# most 6 decimals (micro-RTC). #8618 reports "No precision validation (max
# decimals) anywhere in the new path". An amount with 7 decimals must be
# rejected, not silently accepted. Today this passes only via the #8564
# parser gate (exit 2); a float-parsing band-aid (e.g. the open #8610) would
# silently accept 0.1234567 and turn this red; a proper #8618 fix adds a
# max-decimals guard and keeps it red-green-stable.
def test_send_excess_precision_rejected(node, sender_wallet):
    network = mock_network_info(node)
    transfer = mock_transfer_signed(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        [
            "wallet", "send", sender_wallet.address, "RTC" + "b" * 40,
            "0.1234567", "--seed", seed, "--node", NODE,
        ]
    )
    assert result.exit_code != 0
    assert not network.called and not transfer.called
    assert_no_traceback(result)


# ─────────────────────────────────────────────────────────────────
# 5. node status
# ─────────────────────────────────────────────────────────────────

def test_node_human(node):
    mock_health(node, HEALTH_OK)
    result = invoke(["node", "--node", NODE])
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Node is healthy" in output
    assert "1.2.3" in output


def test_node_json(node):
    mock_health(node, HEALTH_OK)
    result = invoke(["node", "--node", NODE, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == HEALTH_OK


def test_node_unreachable(node):
    route = node.get(f"{NODE}/health").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = invoke(["node", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_node_http_500_exits_nonzero(node):
    route = mock_health(node, {"message": "boom"}, status=500)
    result = invoke(["node", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


@pytest.mark.xfail(strict=True, reason="non-JSON 200 text/html is not surfaced as an error (client wraps it as raw_response); no tracked issue yet")
def test_node_non_json_200_is_an_error(node):
    node.get(f"{NODE}/health").mock(
        return_value=httpx.Response(
            200, content=b"<html>SPA parking page</html>", headers={"content-type": "text/html"}
        )
    )
    result = invoke(["node", "--node", NODE])
    assert result.exit_code != 0
    assert_no_traceback(result)


# Rustchain#8565 — the README and usage header document `rustchain node
# status`, but `node` is a leaf command on main, so the documented form
# exits 2 in the parser.
@pytest.mark.xfail(strict=True, reason="Rustchain#8565")
def test_node_status_documented_invocation(node):
    mock_health(node, HEALTH_OK)
    result = invoke(["node", "status", "--node", NODE])
    assert result.exit_code == 0
    assert "Node is healthy" in all_output(result)


# ─────────────────────────────────────────────────────────────────
# 6. epoch info
# ─────────────────────────────────────────────────────────────────

def test_epoch_human(node):
    mock_epoch(node, EPOCH_INFO)
    result = invoke(["epoch", "--node", NODE])
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Epoch Info:" in output
    assert "42" in output


def test_epoch_json(node):
    mock_epoch(node, EPOCH_INFO)
    result = invoke(["epoch", "--node", NODE, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == EPOCH_INFO


def test_epoch_unreachable(node):
    route = node.get(f"{NODE}/epoch").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = invoke(["epoch", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_epoch_http_500_exits_nonzero(node):
    route = mock_epoch(node, {"message": "boom"}, status=500)
    result = invoke(["epoch", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


@pytest.mark.xfail(strict=True, reason="non-JSON 200 text/html is not surfaced as an error (client wraps it as raw_response); no tracked issue yet")
def test_epoch_non_json_200_is_an_error(node):
    node.get(f"{NODE}/epoch").mock(
        return_value=httpx.Response(
            200, content=b"<html>SPA parking page</html>", headers={"content-type": "text/html"}
        )
    )
    result = invoke(["epoch", "--node", NODE])
    assert result.exit_code != 0
    assert_no_traceback(result)


# Rustchain#8565 — the README and usage header document `rustchain epoch
# info`, which the parser rejects on main.
@pytest.mark.xfail(strict=True, reason="Rustchain#8565")
def test_epoch_info_documented_invocation(node):
    mock_epoch(node, EPOCH_INFO)
    result = invoke(["epoch", "info", "--node", NODE])
    assert result.exit_code == 0
    assert "42" in all_output(result)


# ─────────────────────────────────────────────────────────────────
# 7. miners list
# ─────────────────────────────────────────────────────────────────

def test_miners_list_human(node):
    mock_miners(node, MINERS)
    result = invoke(["miners", "list", "--node", NODE])
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Active Miners (2):" in output
    assert "m-1" in output


def test_miners_list_json(node):
    mock_miners(node, MINERS)
    result = invoke(["miners", "list", "--node", NODE, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == MINERS


def test_miners_list_accepts_wrapped_payload(node):
    # client normalizes {"miners": [...]} envelopes to a list
    mock_miners(node, {"miners": MINERS})
    result = invoke(["miners", "list", "--node", NODE])
    output = all_output(result)
    assert result.exit_code == 0
    assert "Active Miners (2):" in output


def test_miners_list_unreachable(node):
    route = node.get(f"{NODE}/miners").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    result = invoke(["miners", "list", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_miners_list_http_500_exits_nonzero(node):
    route = mock_miners(node, {"message": "boom"}, status=500)
    result = invoke(["miners", "list", "--node", NODE])
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


# ─────────────────────────────────────────────────────────────────
# 8. attest
# ─────────────────────────────────────────────────────────────────

def test_attest_human_full_flow(node, sender_wallet):
    status, challenge, submit = mock_attestation(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["attest", sender_wallet.address, "--seed", seed, "--node", NODE]
    )
    output = all_output(result)
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert "Attestation submitted!" in output
    assert status.called and challenge.called and submit.called


def test_attest_address_mismatch_exits_nonzero(node, sender_wallet):
    status, challenge, submit = mock_attestation(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["attest", "RTC" + "0" * 40, "--seed", seed, "--node", NODE]
    )
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "mismatch" in all_output(result).lower()
    assert not status.called and not challenge.called and not submit.called


def test_attest_unreachable_node(node, sender_wallet):
    route = node.get(f"{NODE}/attestation/status").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["attest", sender_wallet.address, "--seed", seed, "--node", NODE]
    )
    assert route.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


def test_attest_missing_seed_exits_nonzero(node, sender_wallet):
    status, challenge, submit = mock_attestation(node)
    result = invoke(["attest", sender_wallet.address, "--node", NODE])
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "seed" in all_output(result).lower()
    assert not status.called


def test_attest_submit_http_400_exits_nonzero(node, sender_wallet):
    node.get(f"{NODE}/attestation/status").mock(
        return_value=httpx.Response(200, json=ATTEST_STATUS)
    )
    node.post(f"{NODE}/attestation/challenge").mock(
        return_value=httpx.Response(200, json=ATTEST_CHALLENGE)
    )
    submit = node.post(f"{NODE}/attestation/submit").mock(
        return_value=httpx.Response(400, json={"message": "bad signature", "error": "bad signature"})
    )
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["attest", sender_wallet.address, "--seed", seed, "--node", NODE]
    )
    assert submit.called
    assert result.exit_code != 0
    assert_no_traceback(result)
    assert "Error" in all_output(result)


# Passing companion to the #8566 xfail below: `attest --json` must at
# minimum emit parseable JSON and never a traceback. This passes both
# before the fix (status-only JSON) and after it (full-flow JSON).
def test_attest_json_output_is_parseable_json(node, sender_wallet):
    mock_attestation(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["attest", sender_wallet.address, "--seed", seed, "--node", NODE, "--json"]
    )
    assert result.exit_code == 0
    assert_no_traceback(result)
    json.loads(result.output)


# Rustchain#8566 — `attest --json` prints the status object and returns
# without running the advertised challenge/sign/submit flow. An output-format
# flag must not silently turn the command into a status-only no-op.
@pytest.mark.xfail(strict=True, reason="Rustchain#8566")
def test_attest_json_runs_full_flow(node, sender_wallet):
    status, challenge, submit = mock_attestation(node)
    seed = " ".join(sender_wallet.seed_phrase)
    result = invoke(
        ["attest", sender_wallet.address, "--seed", seed, "--node", NODE, "--json"]
    )
    assert result.exit_code == 0
    assert_no_traceback(result)
    assert challenge.called
    assert submit.called
    json.loads(result.output)
