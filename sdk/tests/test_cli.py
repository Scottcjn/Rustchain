"""CLI tests for ``rustchain_sdk.cli`` using Click's CliRunner.

The CLI never touches the network in these tests: every command builds a
``RustChainClient`` or ``RustChainWallet`` from the module namespace, so the
tests patch those two names in ``rustchain_sdk.cli`` and drive the commands
through ``CliRunner``.

Covered:
    * ``rustchain --version``
    * ``wallet create`` — plain output, ``--json``, invalid word count
    * ``wallet balance`` — plain output, ``--json``, node error
    * ``wallet send`` — success, seed/address mismatch
    * ``node`` — healthy and degraded nodes
    * ``epoch`` — plain and ``--json``
    * ``miners list`` — plain and ``--json``
    * ``attest`` — ``--json`` early return, missing challenge, success
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest
from click.testing import CliRunner

from rustchain_sdk import cli
from rustchain_sdk.exceptions import RustChainError


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeClient:
    """Stand-in for ``RustChainClient`` recording calls and returning canned data."""

    instances: List["FakeClient"] = []

    def __init__(self, base_url: str = "http://fake", **kwargs: Any) -> None:
        self.base_url = base_url
        self.kwargs = kwargs
        self.calls: List[tuple] = []
        self.raise_on: Optional[str] = None
        FakeClient.instances.append(self)

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    def _maybe_raise(self, method: str) -> None:
        if self.raise_on == method:
            raise RustChainError(f"{method} failed")

    async def get_balance(self, address: str) -> Dict[str, Any]:
        self.calls.append(("get_balance", address))
        self._maybe_raise("get_balance")
        return {"balance": 42, "nonce": 7}

    async def wallet_transfer_with_wallet(self, wallet: Any, to_address: str,
                                          amount: int, fee: int) -> Dict[str, Any]:
        self.calls.append(("wallet_transfer_with_wallet", to_address, amount, fee))
        self._maybe_raise("wallet_transfer_with_wallet")
        return {"tx_hash": "deadbeef", "status": "pending"}

    async def health(self) -> Dict[str, Any]:
        self.calls.append(("health",))
        self._maybe_raise("health")
        return {"status": "ok", "version": "1.0.0"}

    async def get_epoch(self) -> Dict[str, Any]:
        self.calls.append(("get_epoch",))
        self._maybe_raise("get_epoch")
        return {"epoch": 12, "started": "2026-01-01"}

    async def get_miners(self) -> List[Dict[str, Any]]:
        self.calls.append(("get_miners",))
        self._maybe_raise("get_miners")
        return [{"id": "m1", "score": 10.0}, {"id": "m2", "score": 20.0}]

    async def get_attestation_status(self, public_key_hex: str) -> Dict[str, Any]:
        self.calls.append(("get_attestation_status", public_key_hex))
        self._maybe_raise("get_attestation_status")
        return {"status": "unattested"}

    async def attest_challenge(self, public_key_hex: str) -> Dict[str, Any]:
        self.calls.append(("attest_challenge", public_key_hex))
        self._maybe_raise("attest_challenge")
        return {"challenge": "abc123"}

    async def attest_submit(self, public_key_hex: str, challenge: str,
                            signature: str) -> Dict[str, Any]:
        self.calls.append(("attest_submit", challenge, signature))
        self._maybe_raise("attest_submit")
        return {"ok": True}


class FakeWallet:
    """Stand-in for ``RustChainWallet``."""

    address = "RTC1fakeaddress"
    public_key_hex = "fakepubkey"
    seed_phrase = ["word"] * 12

    def __init__(self, strength: int = 128) -> None:
        self.strength = strength
        self.signed: List[bytes] = []

    @classmethod
    def create(cls, strength: int = 128) -> "FakeWallet":
        return cls(strength=strength)

    @classmethod
    def from_seed_phrase(cls, words: List[str]) -> "FakeWallet":
        return cls()

    def export(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "public_key": self.public_key_hex,
            "seed_phrase": " ".join(self.seed_phrase),
        }

    def sign(self, payload: bytes) -> bytes:
        self.signed.append(payload)
        return b"\x01\x02"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_sdk(monkeypatch: pytest.MonkeyPatch):
    """Patch the client and wallet inside the CLI module for every test."""
    FakeClient.instances = []
    monkeypatch.setattr(cli, "RustChainClient", FakeClient)
    monkeypatch.setattr(cli, "RustChainWallet", FakeWallet)
    yield


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Global
# ---------------------------------------------------------------------------

def test_version_flag(runner: CliRunner):
    result = runner.invoke(cli.main, ["--version"])
    assert result.exit_code == 0
    assert "rustchain" in result.output.lower()


def test_help_lists_groups(runner: CliRunner):
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    for group in ("wallet", "node", "epoch", "miners", "attest"):
        assert group in result.output


# ---------------------------------------------------------------------------
# wallet create
# ---------------------------------------------------------------------------

def test_wallet_create_plain_output(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "create"])
    assert result.exit_code == 0
    assert "Wallet created" in result.output
    assert FakeWallet.address in result.output
    assert "SAVE YOUR SEED PHRASE" in result.output


def test_wallet_create_json(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "create", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["address"] == FakeWallet.address
    assert payload["public_key"] == FakeWallet.public_key_hex
    assert payload["seed_phrase"]


def test_wallet_create_rejects_invalid_word_count(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "create", "--words", "15"])
    assert result.exit_code == 1
    assert "12 or 24" in result.output


# ---------------------------------------------------------------------------
# wallet balance
# ---------------------------------------------------------------------------

def test_wallet_balance_plain(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "balance", "RTC1abc"])
    assert result.exit_code == 0
    assert "RTC1abc" in result.output
    assert "42 RTC" in result.output
    assert "7" in result.output
    assert FakeClient.instances[0].calls == [("get_balance", "RTC1abc")]


def test_wallet_balance_json(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "balance", "RTC1abc", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"balance": 42, "nonce": 7}


def test_wallet_balance_reports_node_error(runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    class FailingClient(FakeClient):
        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, **kw)
            self.raise_on = "get_balance"

    monkeypatch.setattr(cli, "RustChainClient", FailingClient)
    result = runner.invoke(cli.main, ["wallet", "balance", "RTC1abc"])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_wallet_balance_custom_node(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "balance", "RTC1abc", "--node", "http://node:9"])
    assert result.exit_code == 0
    assert FakeClient.instances[0].base_url == "http://node:9"


# ---------------------------------------------------------------------------
# wallet send
# ---------------------------------------------------------------------------

def test_wallet_send_success(runner: CliRunner):
    result = runner.invoke(cli.main, [
        "wallet", "send", FakeWallet.address, "RTC1dest", "100",
        "--fee", "2", "--seed", "word " * 12,
    ])
    assert result.exit_code == 0
    assert "Transfer submitted" in result.output
    assert "deadbeef" in result.output
    assert ("wallet_transfer_with_wallet", "RTC1dest", 100, 2) in FakeClient.instances[0].calls


def test_wallet_send_json(runner: CliRunner):
    result = runner.invoke(cli.main, [
        "wallet", "send", FakeWallet.address, "RTC1dest", "5",
        "--seed", "word " * 12, "--json",
    ])
    assert result.exit_code == 0
    assert json.loads(result.output)["tx_hash"] == "deadbeef"


def test_wallet_send_detects_address_mismatch(runner: CliRunner):
    result = runner.invoke(cli.main, [
        "wallet", "send", "RTC1someoneelse", "RTC1dest", "5",
        "--seed", "word " * 12,
    ])
    assert result.exit_code == 1
    assert "Address mismatch" in result.output
    assert FakeClient.instances == []


def test_wallet_send_requires_seed(runner: CliRunner):
    result = runner.invoke(cli.main, ["wallet", "send", FakeWallet.address, "RTC1dest", "5"])
    assert result.exit_code != 0
    assert "--seed" in result.output


def test_wallet_send_rejects_non_integer_amount(runner: CliRunner):
    result = runner.invoke(cli.main, [
        "wallet", "send", FakeWallet.address, "RTC1dest", "1.5",
        "--seed", "word " * 12,
    ])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# node / epoch / miners
# ---------------------------------------------------------------------------

def test_node_status_healthy(runner: CliRunner):
    result = runner.invoke(cli.main, ["node"])
    assert result.exit_code == 0
    assert "healthy" in result.output
    assert "1.0.0" in result.output


def test_node_status_degraded(runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    class DegradedClient(FakeClient):
        async def health(self) -> Dict[str, Any]:
            return {"status": "degraded", "version": "1.0.0"}

    monkeypatch.setattr(cli, "RustChainClient", DegradedClient)
    result = runner.invoke(cli.main, ["node"])
    assert result.exit_code == 0
    assert "degraded" in result.output


def test_epoch_info_plain(runner: CliRunner):
    result = runner.invoke(cli.main, ["epoch"])
    assert result.exit_code == 0
    assert "Epoch Info" in result.output
    assert "12" in result.output


def test_epoch_info_json(runner: CliRunner):
    result = runner.invoke(cli.main, ["epoch", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"epoch": 12, "started": "2026-01-01"}


def test_miners_list_plain(runner: CliRunner):
    result = runner.invoke(cli.main, ["miners", "list"])
    assert result.exit_code == 0
    assert "Active Miners (2)" in result.output
    assert "m1" in result.output


def test_miners_list_json(runner: CliRunner):
    result = runner.invoke(cli.main, ["miners", "list", "--json"])
    assert result.exit_code == 0
    assert len(json.loads(result.output)) == 2


# ---------------------------------------------------------------------------
# attest
# ---------------------------------------------------------------------------

def test_attest_json_returns_status_only(runner: CliRunner):
    result = runner.invoke(cli.main, [
        "attest", FakeWallet.address, "--seed", "word " * 12, "--json",
    ])
    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "unattested"
    # --json must not continue to the challenge/submit steps
    assert [c[0] for c in FakeClient.instances[0].calls] == ["get_attestation_status"]


def test_attest_warns_when_no_challenge(runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    class NoChallengeClient(FakeClient):
        async def attest_challenge(self, public_key_hex: str) -> Dict[str, Any]:
            return {}

    monkeypatch.setattr(cli, "RustChainClient", NoChallengeClient)
    result = runner.invoke(cli.main, ["attest", FakeWallet.address, "--seed", "word " * 12])
    assert result.exit_code == 0
    assert "No challenge" in result.output


def test_attest_submits_signature(runner: CliRunner):
    result = runner.invoke(cli.main, ["attest", FakeWallet.address, "--seed", "word " * 12])
    assert result.exit_code == 0
    assert "Attestation submitted" in result.output
    calls = FakeClient.instances[0].calls
    assert ("attest_submit", "abc123", "0102") in calls


def test_attest_detects_address_mismatch(runner: CliRunner):
    result = runner.invoke(cli.main, ["attest", "RTC1other", "--seed", "word " * 12])
    assert result.exit_code == 1
    assert "Address mismatch" in result.output
