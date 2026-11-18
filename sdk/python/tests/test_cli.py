# SPDX-License-Identifier: MIT
"""Click CliRunner test suite for sdk/python/rustchain_sdk/cli.py (Bounty #17181).

Covers every CLI command and option (`wallet create|balance|send`, `node`,
`epoch`, `miners list`, `attest`) with mocked HTTP transport — zero live network
requests — plus strict `xfail` regression tests for open issues #8564, #8565,
#8566, #8580, and #8618.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from click.testing import CliRunner

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from rustchain_sdk import cli
from rustchain_sdk.exceptions import ConnectionError as RCConnectionError
from rustchain_sdk.exceptions import APIError, RustChainError
from rustchain_sdk.wallet import RustChainWallet


class MockClientContext:
    """Deterministic async context manager replacing RustChainClient in CLI tests."""

    def __init__(
        self,
        *,
        balance_resp: Any = None,
        transfer_resp: Any = None,
        health_resp: Any = None,
        epoch_resp: Any = None,
        miners_resp: Any = None,
        attest_status_resp: Any = None,
        attest_challenge_resp: Any = None,
        attest_submit_resp: Any = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.balance_resp = balance_resp or {"address": "RTCtest", "balance": 42, "nonce": 3}
        self.transfer_resp = transfer_resp or {"status": "submitted", "tx_hash": "0xabc123"}
        self.health_resp = health_resp or {"status": "ok", "version": "2.4.0", "uptime_s": 86400}
        self.epoch_resp = epoch_resp or {"epoch": 128, "slot": 420, "epoch_pot": 500}
        self.miners_resp = miners_resp if miners_resp is not None else [
            {"miner_id": "g4-powerbook", "arch": "ppc", "antiquity_multiplier": 2.5}
        ]
        self.attest_status_resp = attest_status_resp or {"attested": True, "epoch": 128}
        self.attest_challenge_resp = attest_challenge_resp or {"challenge": "nonce_challenge_128"}
        self.attest_submit_resp = attest_submit_resp or {"accepted": True, "epoch": 128}
        self.raise_exc = raise_exc
        self.calls: List[tuple] = []

    def __call__(self, base_url: str = "https://rustchain.org", **kwargs: Any) -> "MockClientContext":
        self.base_url = base_url
        return self

    async def __aenter__(self) -> "MockClientContext":
        if self.raise_exc is not None:
            raise self.raise_exc
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def get_balance(self, address: str) -> Dict[str, Any]:
        self.calls.append(("get_balance", address))
        return self.balance_resp

    async def wallet_transfer_with_wallet(
        self, wallet: RustChainWallet, to_address: str, amount: Any, fee: int
    ) -> Dict[str, Any]:
        self.calls.append(("wallet_transfer_with_wallet", wallet.address, to_address, amount, fee))
        return self.transfer_resp

    async def health(self) -> Dict[str, Any]:
        self.calls.append(("health",))
        return self.health_resp

    async def get_epoch(self) -> Dict[str, Any]:
        self.calls.append(("get_epoch",))
        return self.epoch_resp

    async def get_miners(self) -> List[Dict[str, Any]]:
        self.calls.append(("get_miners",))
        return self.miners_resp

    async def get_attestation_status(self, pubkey_hex: str) -> Dict[str, Any]:
        self.calls.append(("get_attestation_status", pubkey_hex))
        return self.attest_status_resp

    async def attest_challenge(self, pubkey_hex: str) -> Dict[str, Any]:
        self.calls.append(("attest_challenge", pubkey_hex))
        return self.attest_challenge_resp

    async def attest_submit(self, pubkey_hex: str, challenge: str, signature: str) -> Dict[str, Any]:
        self.calls.append(("attest_submit", pubkey_hex, challenge, signature))
        return self.attest_submit_resp


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_wallet() -> RustChainWallet:
    return RustChainWallet.create(strength=128)


# ---------------------------------------------------------------------------
# 1. Help & Version Coverage for Every Group and Command
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "argv",
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
)
def test_all_commands_help_and_version(runner: CliRunner, argv: List[str]) -> None:
    res = runner.invoke(cli.main, argv)
    assert res.exit_code == 0
    assert len(res.output.strip()) > 10


# ---------------------------------------------------------------------------
# 2. wallet create|balance|send Success & Error Paths
# ---------------------------------------------------------------------------

def test_wallet_create_12_and_24_words_human_and_json(runner: CliRunner) -> None:
    res_human = runner.invoke(cli.main, ["wallet", "create", "--words", "12"])
    assert res_human.exit_code == 0
    assert "Wallet created successfully!" in res_human.output
    assert "Seed Phrase (12 words):" in res_human.output

    res_json = runner.invoke(cli.main, ["wallet", "create", "--words", "24", "--json"])
    assert res_json.exit_code == 0
    payload = json.loads(res_json.output)
    assert payload["address"].startswith("RTC")
    assert isinstance(payload["seed_phrase"], list) and len(payload["seed_phrase"]) == 24


def test_wallet_create_invalid_word_count_exits_nonzero(runner: CliRunner) -> None:
    res = runner.invoke(cli.main, ["wallet", "create", "--words", "15"])
    assert res.exit_code == 1
    assert "Number of seed words must be 12 or 24" in res.output


def test_wallet_balance_human_and_json(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_ctx = MockClientContext(balance_resp={"address": "RTC123", "balance": 150, "nonce": 7})
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)

    res_human = runner.invoke(cli.main, ["wallet", "balance", "RTC123"])
    assert res_human.exit_code == 0
    assert "Address:  RTC123" in res_human.output
    assert "Balance:  150 RTC" in res_human.output
    assert "Nonce:    7" in res_human.output

    res_json = runner.invoke(cli.main, ["wallet", "balance", "RTC123", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["balance"] == 150
    assert data["nonce"] == 7


def test_wallet_send_success_and_error_paths(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext(transfer_resp={"status": "confirmed", "tx_hash": "0xfeedbeef"})
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    seed_str = " ".join(sample_wallet.seed_phrase)

    # Human success
    res = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "25", "--fee", "1", "--seed", seed_str],
    )
    assert res.exit_code == 0
    assert "Transfer submitted!" in res.output
    assert "0xfeedbeef" in res.output

    # JSON success
    res_json = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "25", "--seed", seed_str, "--json"],
    )
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.output)
    assert parsed["tx_hash"] == "0xfeedbeef"

    # Address mismatch error
    res_mismatch = runner.invoke(
        cli.main,
        ["wallet", "send", "RTCwrongaddress", "RTCdest999", "10", "--seed", seed_str],
    )
    assert res_mismatch.exit_code == 1
    assert "Address mismatch" in res_mismatch.output

    # Non-numeric amount rejected by Click parser
    res_bad_amt = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "abc", "--seed", seed_str],
    )
    assert res_bad_amt.exit_code == 2

    # Missing required --seed option
    res_no_seed = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "10"],
    )
    assert res_no_seed.exit_code == 2


# ---------------------------------------------------------------------------
# 3. node, epoch, miners list, attest Success & Error Paths
# ---------------------------------------------------------------------------

def test_node_epoch_and_miners_list_commands(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext()
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)

    # node
    res_node = runner.invoke(cli.main, ["node"])
    assert res_node.exit_code == 0
    assert "Node is healthy" in res_node.output
    res_node_json = runner.invoke(cli.main, ["node", "--json"])
    assert res_node_json.exit_code == 0
    assert json.loads(res_node_json.output)["version"] == "2.4.0"

    # epoch
    res_epoch = runner.invoke(cli.main, ["epoch"])
    assert res_epoch.exit_code == 0
    assert "Epoch Info:" in res_epoch.output
    res_epoch_json = runner.invoke(cli.main, ["epoch", "--json"])
    assert res_epoch_json.exit_code == 0
    assert json.loads(res_epoch_json.output)["epoch"] == 128

    # miners list
    res_miners = runner.invoke(cli.main, ["miners", "list"])
    assert res_miners.exit_code == 0
    assert "Active Miners (1):" in res_miners.output
    res_miners_json = runner.invoke(cli.main, ["miners", "list", "--json"])
    assert res_miners_json.exit_code == 0
    assert json.loads(res_miners_json.output)[0]["miner_id"] == "g4-powerbook"


def test_attest_human_flow_and_network_error_handling(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext()
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    seed_str = " ".join(sample_wallet.seed_phrase)

    res = runner.invoke(cli.main, ["attest", sample_wallet.address, "--seed", seed_str])
    assert res.exit_code == 0
    assert "Attestation submitted!" in res.output
    assert any(c[0] == "attest_submit" for c in mock_ctx.calls)

    # Unreachable node / APIError exits with code 1 and prints error without traceback
    err_ctx = MockClientContext(raise_exc=RCConnectionError("Connection refused"))
    monkeypatch.setattr(cli, "RustChainClient", err_ctx)
    for cmd in [
        ["wallet", "balance", "RTC123"],
        ["node"],
        ["epoch"],
        ["miners", "list"],
        ["attest", sample_wallet.address, "--seed", seed_str],
    ]:
        err_res = runner.invoke(cli.main, cmd)
        assert err_res.exit_code == 1
        assert "Error:" in err_res.output
        assert "Traceback" not in err_res.output


# ---------------------------------------------------------------------------
# 4. Regression Tests for #8564, #8565, #8566, #8580, #8618
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Rustchain#8564: fractional RTC amounts rejected by Click type=int")
def test_regression_8564_fractional_amount_accepted(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext()
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    seed_str = " ".join(sample_wallet.seed_phrase)
    res = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest", "0.5", "--seed", seed_str],
    )
    assert res.exit_code == 0


@pytest.mark.xfail(strict=True, reason="Rustchain#8565: README documents 'node status' and 'epoch info' subcommands")
def test_regression_8565_readme_subcommands_node_status_and_epoch_info(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext()
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    res_node = runner.invoke(cli.main, ["node", "status"])
    res_epoch = runner.invoke(cli.main, ["epoch", "info"])
    assert res_node.exit_code == 0
    assert res_epoch.exit_code == 0


@pytest.mark.xfail(strict=True, reason="Rustchain#8566: 'attest --json' returns early before requesting challenge or submitting attestation")
def test_regression_8566_attest_json_actually_submits_attestation(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext()
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    seed_str = " ".join(sample_wallet.seed_phrase)
    res = runner.invoke(cli.main, ["attest", sample_wallet.address, "--seed", seed_str, "--json"])
    assert res.exit_code == 0
    assert any(c[0] == "attest_submit" for c in mock_ctx.calls)


@pytest.mark.xfail(strict=True, reason="Rustchain#8580: wallet balance prints 0 RTC when node returns canonical amount_rtc / amount_i64")
def test_regression_8580_balance_reads_canonical_amount_rtc_field(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_ctx = MockClientContext(
        balance_resp={"miner_id": "RTC123", "amount_rtc": 12.5, "amount_i64": 12500000}
    )
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    res = runner.invoke(cli.main, ["wallet", "balance", "RTC123"])
    assert res.exit_code == 0
    assert "12.5 RTC" in res.output


@pytest.mark.xfail(strict=True, reason="Rustchain#8618: wallet send must serialize exact Decimal string/micro-RTC without float money")
def test_regression_8618_no_float_money_serialization(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decimal import Decimal

    mock_ctx = MockClientContext()
    monkeypatch.setattr(cli, "RustChainClient", mock_ctx)
    seed_str = " ".join(sample_wallet.seed_phrase)
    res = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest", "0.1", "--seed", seed_str],
    )
    assert res.exit_code == 0
    sent_amount = mock_ctx.calls[0][3]
    assert isinstance(sent_amount, (Decimal, str)) and str(sent_amount) == "0.1"
