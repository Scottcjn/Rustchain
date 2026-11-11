"""
CLI test suite for ``rustchain_sdk.cli`` (bounty Scottcjn/rustchain-bounties#17181).

Every command is driven through ``click.testing.CliRunner`` against the real
``RustChainClient``. HTTP is intercepted with ``httpx.MockTransport`` (built
into httpx, no extra dependency), so the client's own error mapping, JSON
handling and request construction are exercised end-to-end. No test touches
the network: an autouse fixture fails any test that tries to open a socket.

Regression tests for Rustchain#8564, #8565, #8566, #8580 and #8618 are written
against the *expected* behaviour in each issue and marked
``xfail(strict=True)`` until their fixes land, so they turn into hard failures
(prompting removal of the marker) the day the fix is merged.
"""

from __future__ import annotations

import json
import socket
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

import httpx
import pytest
from click.testing import CliRunner

from rustchain_sdk import __version__
from rustchain_sdk import cli as cli_module
from rustchain_sdk.cli import main
from rustchain_sdk.wallet import RustChainWallet

NODE = "http://node.test"
CHAIN_ID = "rustchain-mainnet-v2"

# Fixed, public test vector (never used on a real network).
SEED = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
WALLET = RustChainWallet.from_seed_phrase(SEED.split())
ADDRESS = WALLET.address
OTHER_ADDRESS = "RTC" + "0" * 40

Handler = Callable[[httpx.Request], httpx.Response]


# ─────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if anything tries to reach a real socket."""

    def guard(*_args, **_kwargs):
        raise AssertionError("network access attempted during CLI tests")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(socket, "getaddrinfo", guard)


@pytest.fixture
def runner() -> CliRunner:
    # Click >= 8.2 always separates stderr; older versions need mix_stderr=False.
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


class FakeNode:
    """Routes requests by (METHOD, path) and records every request seen."""

    def __init__(self, routes: Optional[Dict[Tuple[str, str], Handler]] = None):
        self.routes: Dict[Tuple[str, str], Handler] = dict(routes or {})
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        handler = self.routes.get((request.method, request.url.path))
        if handler is None:
            return httpx.Response(404, json={"error": f"no route {request.method} {request.url.path}"})
        return handler(request)

    def paths(self) -> List[Tuple[str, str]]:
        return [(r.method, r.url.path) for r in self.requests]

    def json_bodies(self, path: str) -> List[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == path]


def ok(payload) -> Handler:
    return lambda _req: httpx.Response(200, json=payload)


@pytest.fixture
def node(monkeypatch) -> FakeNode:
    """Patch the httpx.AsyncClient used by RustChainClient onto a FakeNode."""
    fake = FakeNode()
    real_async_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("verify", None)
        kwargs["transport"] = httpx.MockTransport(fake)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr("rustchain_sdk.client.httpx.AsyncClient", factory)
    return fake


def invoke(runner: CliRunner, args: List[str]):
    return runner.invoke(main, args, catch_exceptions=False)


def _cli_stderr(result) -> str:
    """stderr minus the client's unrelated TLS-cert logging warning."""
    return "\n".join(
        line for line in result.stderr.splitlines() if "node cert not found" not in line
    )


def assert_clean_failure(result, *needles: str) -> None:
    """Non-zero exit, message on stderr, and never a Python traceback."""
    stderr = _cli_stderr(result)
    assert result.exit_code != 0, result.output
    assert stderr.strip(), "expected an error message on stderr"
    assert "Traceback" not in result.output + result.stderr
    for needle in needles:
        assert needle in stderr, stderr


# ─────────────────────────────────────────────────────────────────
# Top level / --help for every group and command
# ─────────────────────────────────────────────────────────────────


def test_version(runner):
    result = invoke(runner, ["--version"])
    assert result.exit_code == 0
    assert f"rustchain, version {__version__}" in result.output


@pytest.mark.parametrize(
    "args, expected",
    [
        ([], ["wallet", "node", "epoch", "miners", "attest"]),
        (["wallet"], ["create", "balance", "send"]),
        (["wallet", "create"], ["--words", "--json"]),
        (["wallet", "balance"], ["ADDRESS", "--node", "--json"]),
        (["wallet", "send"], ["FROM_ADDRESS", "TO_ADDRESS", "AMOUNT", "--fee", "--seed", "--node", "--json"]),
        (["node"], ["--node", "--json"]),
        (["epoch"], ["--node", "--json"]),
        (["miners"], ["list"]),
        (["miners", "list"], ["--node", "--json"]),
        (["attest"], ["WALLET_ADDRESS", "--seed", "--node", "--json"]),
    ],
    ids=lambda v: " ".join(v) if isinstance(v, list) and all(isinstance(x, str) for x in v) else None,
)
def test_help(runner, args, expected):
    result = invoke(runner, args + ["--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    for token in expected:
        assert token in result.output


def test_unknown_command_fails(runner):
    result = invoke(runner, ["frobnicate"])
    assert result.exit_code == 2
    assert "No such command" in result.stderr


# ─────────────────────────────────────────────────────────────────
# wallet create (local only)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("words", [12, 24])
def test_wallet_create_json(runner, node, words):
    result = invoke(runner, ["wallet", "create", "--words", str(words), "--json"])
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.output)
    assert {"version", "address", "seed_phrase"} <= set(data)
    assert data["address"].startswith("RTC")
    assert len(data["seed_phrase"]) == words
    # Round-trip: the exported seed must regenerate the exported address.
    assert RustChainWallet.from_seed_phrase(data["seed_phrase"]).address == data["address"]
    assert node.requests == []


def test_wallet_create_human(runner, node):
    result = invoke(runner, ["wallet", "create"])
    assert result.exit_code == 0, result.stderr
    assert "Wallet created successfully" in result.output
    assert "Address:      RTC" in result.output
    assert "Seed Phrase (12 words)" in result.output
    assert "SAVE YOUR SEED PHRASE" in result.output
    assert node.requests == []


def test_wallet_create_rejects_bad_word_count(runner):
    result = invoke(runner, ["wallet", "create", "--words", "15"])
    assert_clean_failure(result, "12 or 24")


def test_wallet_create_rejects_non_integer_words(runner):
    result = invoke(runner, ["wallet", "create", "--words", "twelve"])
    assert_clean_failure(result, "not a valid integer")


# ─────────────────────────────────────────────────────────────────
# wallet balance
# ─────────────────────────────────────────────────────────────────


def test_wallet_balance_human(runner, node):
    node.routes[("GET", "/wallet/balance")] = ok({"balance": 42, "nonce": 3})
    result = invoke(runner, ["wallet", "balance", ADDRESS, "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert f"Address:  {ADDRESS}" in result.output
    assert "Balance:  42 RTC" in result.output
    assert "Nonce:    3" in result.output
    assert node.requests[0].url.params["address"] == ADDRESS


def test_wallet_balance_json(runner, node):
    payload = {"balance": 42, "nonce": 3, "address": ADDRESS}
    node.routes[("GET", "/wallet/balance")] = ok(payload)
    result = invoke(runner, ["wallet", "balance", ADDRESS, "--node", NODE, "--json"])
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.output) == payload


def test_wallet_balance_node_url_is_used(runner, node):
    node.routes[("GET", "/wallet/balance")] = ok({"balance": 1, "nonce": 0})
    invoke(runner, ["wallet", "balance", ADDRESS, "--node", "http://other.node:8099/"])
    assert node.requests[0].url.host == "other.node"
    assert node.requests[0].url.port == 8099


def test_wallet_balance_missing_address(runner):
    result = invoke(runner, ["wallet", "balance"])
    assert_clean_failure(result, "Missing argument 'ADDRESS'")


@pytest.mark.xfail(strict=True, reason="Rustchain#8580: canonical amount_rtc field is ignored")
def test_regression_8580_balance_reads_canonical_amount_rtc(runner, node):
    node.routes[("GET", "/wallet/balance")] = ok(
        {"amount_i64": 21000000, "amount_rtc": 21, "miner_id": "stmr"}
    )
    result = invoke(runner, ["wallet", "balance", ADDRESS, "--node", NODE])
    assert result.exit_code == 0
    assert "Balance:  21" in result.output
    assert "Balance:  0 RTC" not in result.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8580: missing balance must not render as 0 RTC")
def test_regression_8580_balance_without_known_fields_is_not_zero(runner, node):
    node.routes[("GET", "/wallet/balance")] = ok({"miner_id": "stmr"})
    result = invoke(runner, ["wallet", "balance", ADDRESS, "--node", NODE])
    assert "0 RTC" not in result.output


# ─────────────────────────────────────────────────────────────────
# wallet send
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def send_node(node) -> FakeNode:
    node.routes[("GET", "/network/info")] = ok({"chain_id": CHAIN_ID, "network": "mainnet"})
    node.routes[("POST", "/wallet/transfer/signed")] = ok({"tx_hash": "0xabc123", "status": "pending"})
    return node


def send_args(amount: str = "5", *extra: str) -> List[str]:
    return ["wallet", "send", ADDRESS, OTHER_ADDRESS, amount, "--seed", SEED, "--node", NODE, *extra]


def test_wallet_send_human(runner, send_node):
    result = invoke(runner, send_args("5", "--fee", "1"))
    assert result.exit_code == 0, result.stderr
    for line in (
        "Transfer submitted",
        f"From:     {ADDRESS}",
        f"To:       {OTHER_ADDRESS}",
        "Amount:   5 RTC",
        "Fee:      1 RTC",
        "Status:   pending",
        "TX Hash:  0xabc123",
    ):
        assert line in result.output

    assert send_node.paths() == [("GET", "/network/info"), ("POST", "/wallet/transfer/signed")]
    body = send_node.json_bodies("/wallet/transfer/signed")[0]
    assert body["from_address"] == ADDRESS
    assert body["to_address"] == OTHER_ADDRESS
    assert body["amount_rtc"] == 5
    assert body["fee_rtc"] == 1
    assert body["chain_id"] == CHAIN_ID
    assert body["public_key"] == WALLET.public_key_hex
    assert len(bytes.fromhex(body["signature"])) == 64


def test_wallet_send_signature_verifies(runner, send_node):
    """The submitted signature must verify against the canonical signed message."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    invoke(runner, send_args("7"))
    body = send_node.json_bodies("/wallet/transfer/signed")[0]
    message = json.dumps(
        {
            "amount": float(body["amount_rtc"]),
            "chain_id": body["chain_id"],
            "fee": float(body["fee_rtc"]),
            "from": body["from_address"],
            "memo": "",
            "nonce": str(body["nonce"]),
            "to": body["to_address"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(body["public_key"])).verify(
        bytes.fromhex(body["signature"]), message
    )  # raises InvalidSignature on mismatch


def test_wallet_send_json(runner, send_node):
    result = invoke(runner, send_args("5", "--json"))
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.output) == {"tx_hash": "0xabc123", "status": "pending"}


def test_wallet_send_seed_address_mismatch(runner, send_node):
    args = ["wallet", "send", OTHER_ADDRESS, ADDRESS, "5", "--seed", SEED, "--node", NODE]
    result = invoke(runner, args)
    assert_clean_failure(result, "Address mismatch")
    assert send_node.requests == [], "must not contact the node when the seed does not match"


def test_wallet_send_missing_seed(runner, send_node):
    result = invoke(runner, ["wallet", "send", ADDRESS, OTHER_ADDRESS, "5", "--node", NODE])
    assert_clean_failure(result, "Missing option '--seed'")
    assert send_node.requests == []


def test_wallet_send_missing_amount(runner, send_node):
    result = invoke(runner, ["wallet", "send", ADDRESS, OTHER_ADDRESS, "--seed", SEED])
    assert_clean_failure(result, "Missing argument 'AMOUNT'")
    assert send_node.requests == []


def test_wallet_send_rejects_non_numeric_amount(runner, send_node):
    result = invoke(runner, send_args("abc"))
    assert_clean_failure(result, "AMOUNT")
    assert send_node.requests == []


def test_wallet_send_rejects_non_numeric_fee(runner, send_node):
    result = invoke(runner, send_args("5", "--fee", "lots"))
    assert_clean_failure(result, "--fee")
    assert send_node.requests == []


@pytest.mark.xfail(strict=True, reason="CLI accepts negative amounts and signs them (no client-side guard)")
def test_wallet_send_rejects_negative_amount(runner, send_node):
    # "--" stops option parsing so "-5" reaches the AMOUNT argument.
    result = invoke(
        runner, ["wallet", "send", "--seed", SEED, "--node", NODE, ADDRESS, OTHER_ADDRESS, "--", "-5"]
    )
    assert_clean_failure(result)
    assert send_node.requests == [], "negative amounts must be rejected before signing"


@pytest.mark.xfail(strict=True, reason="CLI accepts a zero amount and signs it (no client-side guard)")
def test_wallet_send_rejects_zero_amount(runner, send_node):
    result = invoke(runner, send_args("0"))
    assert_clean_failure(result)
    assert send_node.requests == [], "zero amounts must be rejected before signing"


@pytest.mark.xfail(strict=True, reason="Rustchain#8564: fractional RTC amount rejected by int parser")
def test_regression_8564_fractional_amount_reaches_transfer(runner, send_node):
    result = invoke(runner, send_args("0.5"))
    assert result.exit_code == 0, result.stderr
    assert ("POST", "/wallet/transfer/signed") in send_node.paths()


@pytest.mark.xfail(strict=True, reason="Rustchain#8564: fractional RTC fee rejected by int parser")
def test_regression_8564_fractional_fee_reaches_transfer(runner, send_node):
    result = invoke(runner, send_args("1", "--fee", "0.01"))
    assert result.exit_code == 0, result.stderr
    assert ("POST", "/wallet/transfer/signed") in send_node.paths()


@pytest.mark.xfail(strict=True, reason="Rustchain#8564: README example 'send ... 10.5' must work")
def test_regression_8564_readme_example_amount(runner, send_node):
    result = invoke(runner, send_args("10.5"))
    assert result.exit_code == 0, result.stderr
    assert "Amount:   10.5 RTC" in result.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8618: money must be serialised exactly, not via binary float")
@pytest.mark.parametrize("amount", ["0.1", "0.29", "10.5"])
def test_regression_8618_send_amount_is_exact_decimal(runner, send_node, monkeypatch, amount):
    """
    ``wallet send --amount 0.1`` must never route money through ``float`` and
    must put exactly the user's decimal on the wire.

    Parsed as ``Decimal`` from the raw JSON token (not via float), the submitted
    ``amount_rtc`` must equal the decimal the user typed. Coordinate the wire
    representation (decimal string vs. integer micro-units) with #8618's fix and
    adjust only the extraction below, never the equality.
    """
    from rustchain_sdk.client import RustChainClient

    seen = {}
    original = RustChainClient.wallet_transfer_with_wallet

    async def recording(self, wallet, to_address, amount_arg, fee=0, *args, **kwargs):
        seen["amount"], seen["fee"] = amount_arg, fee
        return await original(self, wallet, to_address, amount_arg, fee, *args, **kwargs)

    monkeypatch.setattr(RustChainClient, "wallet_transfer_with_wallet", recording)

    result = invoke(runner, send_args(amount))
    assert result.exit_code == 0, result.stderr
    # The money value handed to the SDK must never be a binary float.
    assert not isinstance(seen["amount"], float), f"amount passed as float: {seen['amount']!r}"
    assert not isinstance(seen["fee"], float), f"fee passed as float: {seen['fee']!r}"
    raw = [r for r in send_node.requests if r.url.path == "/wallet/transfer/signed"][0].content
    body = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    wire = body["amount_rtc"]
    assert Decimal(str(wire)) == Decimal(amount)


def test_regression_8618_rejects_sub_unit_precision(runner, send_node):
    result = invoke(runner, send_args("0.0000000001"))
    assert_clean_failure(result)
    assert send_node.requests == []


# ─────────────────────────────────────────────────────────────────
# node
# ─────────────────────────────────────────────────────────────────


def test_node_human_healthy(runner, node):
    node.routes[("GET", "/health")] = ok({"status": "ok", "version": "2.4.1", "height": 1234})
    result = invoke(runner, ["node", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert "Node is healthy" in result.output
    assert "version:  2.4.1" in result.output
    assert "height:  1234" in result.output


def test_node_human_degraded(runner, node):
    node.routes[("GET", "/health")] = ok({"status": "syncing"})
    result = invoke(runner, ["node", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert "Node status: syncing" in result.output
    assert "Node is healthy" not in result.output


def test_node_json(runner, node):
    payload = {"status": "ok", "version": "2.4.1"}
    node.routes[("GET", "/health")] = ok(payload)
    result = invoke(runner, ["node", "--node", NODE, "--json"])
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.output) == payload


@pytest.mark.xfail(strict=True, reason="Rustchain#8565: README 'rustchain node status' rejected by parser")
def test_regression_8565_node_status_documented_form(runner, node):
    node.routes[("GET", "/health")] = ok({"status": "ok"})
    result = invoke(runner, ["node", "status", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert ("GET", "/health") in node.paths()


# ─────────────────────────────────────────────────────────────────
# epoch
# ─────────────────────────────────────────────────────────────────


def test_epoch_human(runner, node):
    node.routes[("GET", "/epoch")] = ok({"epoch": 77, "slot": 12, "enrolled_miners": 9})
    result = invoke(runner, ["epoch", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert "Epoch Info:" in result.output
    assert "epoch:  77" in result.output
    assert "slot:  12" in result.output
    assert "enrolled_miners:  9" in result.output


def test_epoch_json(runner, node):
    payload = {"epoch": 77, "slot": 12}
    node.routes[("GET", "/epoch")] = ok(payload)
    result = invoke(runner, ["epoch", "--node", NODE, "--json"])
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.output) == payload


@pytest.mark.xfail(strict=True, reason="Rustchain#8565: README 'rustchain epoch info' rejected by parser")
def test_regression_8565_epoch_info_documented_form(runner, node):
    node.routes[("GET", "/epoch")] = ok({"epoch": 77})
    result = invoke(runner, ["epoch", "info", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert ("GET", "/epoch") in node.paths()


# ─────────────────────────────────────────────────────────────────
# miners list
# ─────────────────────────────────────────────────────────────────

MINERS = [{"miner": "alice", "arch": "g4"}, {"miner": "bob", "arch": "x86_64"}]


@pytest.mark.parametrize(
    "payload",
    [MINERS, {"miners": MINERS}, {"data": MINERS}, {"items": MINERS}],
    ids=["bare-list", "miners-key", "data-key", "items-key"],
)
def test_miners_list_human(runner, node, payload):
    node.routes[("GET", "/miners")] = ok(payload)
    result = invoke(runner, ["miners", "list", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert "Active Miners (2):" in result.output
    assert '"miner": "alice"' in result.output
    assert '"miner": "bob"' in result.output


def test_miners_list_json(runner, node):
    node.routes[("GET", "/miners")] = ok({"miners": MINERS})
    result = invoke(runner, ["miners", "list", "--node", NODE, "--json"])
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.output) == MINERS


def test_miners_list_empty(runner, node):
    node.routes[("GET", "/miners")] = ok([])
    result = invoke(runner, ["miners", "list", "--node", NODE])
    assert result.exit_code == 0, result.stderr
    assert "Active Miners (0):" in result.output


# ─────────────────────────────────────────────────────────────────
# attest
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def attest_node(node) -> FakeNode:
    node.routes[("GET", "/attestation/status")] = ok({"attested": False, "epoch": 77})
    node.routes[("POST", "/attestation/challenge")] = ok({"challenge": "nonce-xyz", "expires": 60})
    node.routes[("POST", "/attestation/submit")] = ok({"ok": True, "multiplier": 2.5})
    return node


def attest_args(*extra: str) -> List[str]:
    return ["attest", ADDRESS, "--seed", SEED, "--node", NODE, *extra]


def test_attest_human_full_flow(runner, attest_node):
    result = invoke(runner, attest_args())
    assert result.exit_code == 0, result.stderr
    assert "Requesting attestation challenge" in result.output
    assert "Submitting attestation" in result.output
    assert "Attestation submitted" in result.output
    assert '"multiplier": 2.5' in result.output

    assert attest_node.paths() == [
        ("GET", "/attestation/status"),
        ("POST", "/attestation/challenge"),
        ("POST", "/attestation/submit"),
    ]
    assert attest_node.requests[0].url.params["miner_public_key"] == WALLET.public_key_hex
    submit = attest_node.json_bodies("/attestation/submit")[0]
    assert submit["miner_public_key"] == WALLET.public_key_hex
    assert submit["challenge_response"] == "nonce-xyz"
    assert submit["signature"] == WALLET.sign(b"nonce-xyz").hex()


def test_attest_no_challenge(runner, attest_node):
    attest_node.routes[("POST", "/attestation/challenge")] = ok({})
    result = invoke(runner, attest_args())
    assert result.exit_code == 0, result.stderr
    assert "No challenge received" in result.output
    assert ("POST", "/attestation/submit") not in attest_node.paths()


def test_attest_json_outputs_valid_json(runner, attest_node):
    result = invoke(runner, attest_args("--json"))
    assert result.exit_code == 0, result.stderr
    assert isinstance(json.loads(result.output), dict)


def test_attest_seed_address_mismatch(runner, attest_node):
    result = invoke(runner, ["attest", OTHER_ADDRESS, "--seed", SEED, "--node", NODE])
    assert_clean_failure(result, "Address mismatch")
    assert attest_node.requests == []


def test_attest_missing_seed(runner, attest_node):
    result = invoke(runner, ["attest", ADDRESS, "--node", NODE])
    assert_clean_failure(result, "Missing option '--seed'")


@pytest.mark.xfail(strict=True, reason="Rustchain#8566: attest --json returns status without attesting")
def test_regression_8566_attest_json_runs_full_flow(runner, attest_node):
    result = invoke(runner, attest_args("--json"))
    assert result.exit_code == 0, result.stderr
    json.loads(result.output)
    assert ("POST", "/attestation/challenge") in attest_node.paths()
    assert ("POST", "/attestation/submit") in attest_node.paths()


@pytest.mark.xfail(strict=True, reason="An invalid seed phrase currently escapes as a raw traceback")
def test_attest_invalid_seed_is_clean_error(runner, attest_node):
    result = runner.invoke(main, ["attest", ADDRESS, "--seed", "not a real seed", "--node", NODE])
    assert_clean_failure(result)


# ─────────────────────────────────────────────────────────────────
# Transport / server error paths, shared by every network command
# ─────────────────────────────────────────────────────────────────

NETWORK_COMMANDS = {
    "wallet balance": (["wallet", "balance", ADDRESS, "--node", NODE], ("GET", "/wallet/balance")),
    "wallet send": (send_args("5"), ("GET", "/network/info")),
    "node": (["node", "--node", NODE], ("GET", "/health")),
    "epoch": (["epoch", "--node", NODE], ("GET", "/epoch")),
    "miners list": (["miners", "list", "--node", NODE], ("GET", "/miners")),
    "attest": (attest_args(), ("GET", "/attestation/status")),
}


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("[Errno 111] Connection refused", request=request)


@pytest.mark.parametrize("name", list(NETWORK_COMMANDS))
def test_unreachable_node(runner, node, name):
    args, route = NETWORK_COMMANDS[name]
    node.routes[route] = _refuse
    result = invoke(runner, args)
    assert_clean_failure(result, "Failed to connect", NODE)


@pytest.mark.parametrize("status", [400, 404, 500, 503])
@pytest.mark.parametrize("name", list(NETWORK_COMMANDS))
def test_http_error_status(runner, node, name, status):
    args, route = NETWORK_COMMANDS[name]
    node.routes[route] = lambda _req: httpx.Response(status, json={"error": f"boom-{status}"})
    result = invoke(runner, args)
    assert_clean_failure(result, f"API error {status}", f"boom-{status}")


@pytest.mark.parametrize("name", list(NETWORK_COMMANDS))
def test_http_error_with_non_json_body(runner, node, name):
    args, route = NETWORK_COMMANDS[name]
    node.routes[route] = lambda _req: httpx.Response(502, text="<html>Bad Gateway</html>")
    result = invoke(runner, args)
    assert_clean_failure(result, "API error 502")


@pytest.mark.parametrize("name", ["node", "epoch"])
def test_non_json_200_is_surfaced_not_hidden(runner, node, name):
    """A 200 with an HTML/plain body is shown to the user, never a traceback."""
    args, route = NETWORK_COMMANDS[name]
    node.routes[route] = lambda _req: httpx.Response(200, text="<html>maintenance</html>")
    result = invoke(runner, args)
    assert "Traceback" not in result.output + result.stderr
    assert "maintenance" in result.output + result.stderr


@pytest.mark.xfail(strict=True, reason="non-JSON 200 from /wallet/balance is rendered as 'Balance: 0 RTC'")
def test_non_json_200_balance_is_not_reported_as_zero(runner, node):
    node.routes[("GET", "/wallet/balance")] = lambda _req: httpx.Response(200, text="<html>maintenance</html>")
    result = invoke(runner, ["wallet", "balance", ADDRESS, "--node", NODE])
    assert "0 RTC" not in result.output


def test_non_json_200_miners_is_empty_not_crash(runner, node):
    node.routes[("GET", "/miners")] = lambda _req: httpx.Response(200, text="maintenance")
    result = invoke(runner, ["miners", "list", "--node", NODE])
    assert result.exit_code == 0
    assert "Active Miners (0):" in result.output


@pytest.mark.parametrize("name", ["wallet balance", "node", "epoch"])
def test_json_array_on_object_endpoint(runner, node, name):
    args, route = NETWORK_COMMANDS[name]
    node.routes[route] = ok([1, 2, 3])
    result = invoke(runner, args)
    assert_clean_failure(result, "Expected JSON object response")


@pytest.mark.parametrize("name", ["wallet balance", "node", "epoch", "miners list"])
def test_redirect_is_refused(runner, node, name):
    args, route = NETWORK_COMMANDS[name]
    node.routes[route] = lambda _req: httpx.Response(302, headers={"location": "http://evil.test/"})
    result = invoke(runner, args)
    assert_clean_failure(result, "redirected", "evil.test")


def test_send_invalid_chain_id_aborts_before_signing(runner, node):
    node.routes[("GET", "/network/info")] = ok({"chain_id": "bad chain id!"})
    node.routes[("POST", "/wallet/transfer/signed")] = ok({"status": "pending"})
    result = invoke(runner, send_args("5"))
    assert_clean_failure(result, "invalid chain_id")
    assert ("POST", "/wallet/transfer/signed") not in node.paths()


def test_send_rejected_by_node(runner, send_node):
    send_node.routes[("POST", "/wallet/transfer/signed")] = lambda _req: httpx.Response(
        400, json={"error": "insufficient balance"}
    )
    result = invoke(runner, send_args("5"))
    assert_clean_failure(result, "API error 400", "insufficient balance")


def test_cli_module_is_runnable_as_script():
    """`python -m rustchain_sdk.cli` keeps its __main__ guard."""
    import inspect

    assert 'if __name__ == "__main__":' in inspect.getsource(cli_module)
