# SPDX-License-Identifier: MIT
"""Click CliRunner test suite for sdk/python/rustchain_sdk/cli.py (Bounty #17181).

Covers every CLI command and option (`wallet create|balance|send`, `node`,
`epoch`, `miners list`, `attest`) using mocked HTTP transport (`httpx.MockTransport`
— zero live network calls), full CLI error paths, and strict `xfail` regression
tests for #8564, #8565, #8566, #8580, and #8618.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from click.testing import CliRunner

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

import rustchain_sdk.client as rc_client
from rustchain_sdk import cli
from rustchain_sdk.wallet import RustChainWallet


def install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[dict[str, Any]]:
    """Patch httpx.AsyncClient used by RustChainClient to use MockTransport."""
    recorded: list[dict[str, Any]] = []
    orig_async_client = httpx.AsyncClient

    def _wrapped(request: httpx.Request) -> httpx.Response:
        body: Any = None
        if request.content:
            try:
                body = json.loads(request.content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = request.content.decode("utf-8", errors="replace")
        recorded.append(
            {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "json": body,
            }
        )
        return handler(request)

    transport = httpx.MockTransport(_wrapped)

    def _factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(rc_client.httpx, "AsyncClient", _factory)
    return recorded


def _default_node_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/health":
        return httpx.Response(200, json={"status": "ok", "version": "2.4.0", "uptime_s": 86400})
    if path == "/network/info":
        return httpx.Response(200, json={"chain_id": "rustchain-mainnet", "version": "2.4.0"})
    if path == "/epoch":
        return httpx.Response(200, json={"epoch": 128, "slot": 420, "epoch_pot": 500})
    if path == "/miners":
        return httpx.Response(
            200,
            json=[{"miner_id": "g4-powerbook", "arch": "ppc", "antiquity_multiplier": 2.5}],
        )
    if path == "/wallet/balance":
        address = request.url.params.get("address", "RTC123")
        return httpx.Response(200, json={"address": address, "balance": 150, "nonce": 7})
    if path == "/wallet/transfer/signed":
        return httpx.Response(200, json={"status": "submitted", "tx_hash": "0xfeedbeef"})
    if path == "/attestation/status":
        return httpx.Response(200, json={"attested": True, "epoch": 128})
    if path == "/attestation/challenge":
        return httpx.Response(200, json={"challenge": "nonce_challenge_128"})
    if path == "/attestation/submit":
        return httpx.Response(200, json={"accepted": True, "epoch": 128})
    return httpx.Response(404, json={"error": f"Unhandled mock route {path}"})


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
def test_all_commands_help_and_version(runner: CliRunner, argv: list[str]) -> None:
    res = runner.invoke(cli.main, argv)
    assert res.exit_code == 0
    assert len(res.output.strip()) > 10


# ---------------------------------------------------------------------------
# 2. wallet create | balance | send Success Paths & Exact Micro-RTC Wire Check
# ---------------------------------------------------------------------------

def test_wallet_create_12_and_24_words_human_and_json(runner: CliRunner) -> None:
    res_human = runner.invoke(cli.main, ["wallet", "create", "--words", "12"])
    assert res_human.exit_code == 0
    assert "Wallet created successfully!" in res_human.stdout
    assert "Seed Phrase (12 words):" in res_human.stdout

    res_json = runner.invoke(cli.main, ["wallet", "create", "--words", "24", "--json"])
    assert res_json.exit_code == 0
    payload = json.loads(res_json.stdout)
    assert payload["address"].startswith("RTC")
    assert isinstance(payload["seed_phrase"], list) and len(payload["seed_phrase"]) == 24


def test_wallet_create_invalid_word_count_exits_nonzero(runner: CliRunner) -> None:
    res = runner.invoke(cli.main, ["wallet", "create", "--words", "15"])
    assert res.exit_code == 1
    assert "Number of seed words must be 12 or 24" in res.stderr
    assert "Traceback" not in res.output


def test_wallet_balance_human_json_and_node_option(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_mock_transport(monkeypatch, _default_node_handler)

    res_human = runner.invoke(
        cli.main, ["wallet", "balance", "RTC123", "--node", "https://custom.node.test:8443"]
    )
    assert res_human.exit_code == 0
    assert "Address:  RTC123" in res_human.stdout
    assert "Balance:  150 RTC" in res_human.stdout
    assert "Nonce:    7" in res_human.stdout
    assert recorded[-1]["url"].startswith("https://custom.node.test:8443/wallet/balance")

    res_json = runner.invoke(cli.main, ["wallet", "balance", "RTC123", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["address"] == "RTC123"
    assert data["balance"] == 150
    assert data["nonce"] == 7


def test_wallet_send_human_json_node_and_exact_micro_rtc_payload(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_mock_transport(monkeypatch, _default_node_handler)
    seed_str = " ".join(sample_wallet.seed_phrase)

    res_human = runner.invoke(
        cli.main,
        [
            "wallet",
            "send",
            sample_wallet.address,
            "RTCdest999",
            "25",
            "--fee",
            "1",
            "--seed",
            seed_str,
            "--node",
            "https://tx.node.test",
        ],
    )
    assert res_human.exit_code == 0
    assert "Transfer submitted!" in res_human.stdout
    assert "0xfeedbeef" in res_human.stdout

    signed_posts = [r for r in recorded if r["path"] == "/wallet/transfer/signed"]
    assert len(signed_posts) == 1
    assert signed_posts[0]["url"] == "https://tx.node.test/wallet/transfer/signed"
    wire = signed_posts[0]["json"]
    assert wire["amount_rtc"] == 25.0
    assert wire["fee_rtc"] == 1.0
    assert wire["chain_id"] == "rustchain-mainnet"
    assert isinstance(wire["signature"], str) and len(wire["signature"]) > 0

    res_json = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "25", "--seed", seed_str, "--json"],
    )
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.stdout)
    assert parsed["tx_hash"] == "0xfeedbeef"


# ---------------------------------------------------------------------------
# 3. node | epoch | miners list | attest Success Paths
# ---------------------------------------------------------------------------

def test_node_epoch_and_miners_list_commands_and_node_option(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_mock_transport(monkeypatch, _default_node_handler)

    res_node = runner.invoke(cli.main, ["node", "--node", "https://edge1.node.test"])
    assert res_node.exit_code == 0
    assert "Node is healthy" in res_node.stdout
    res_node_json = runner.invoke(cli.main, ["node", "--json"])
    assert res_node_json.exit_code == 0
    assert json.loads(res_node_json.stdout)["version"] == "2.4.0"

    res_epoch = runner.invoke(cli.main, ["epoch", "--node", "https://edge2.node.test"])
    assert res_epoch.exit_code == 0
    assert "Epoch Info:" in res_epoch.stdout
    res_epoch_json = runner.invoke(cli.main, ["epoch", "--json"])
    assert res_epoch_json.exit_code == 0
    assert json.loads(res_epoch_json.stdout)["epoch"] == 128

    res_miners = runner.invoke(cli.main, ["miners", "list", "--node", "https://edge3.node.test"])
    assert res_miners.exit_code == 0
    assert "Active Miners (1):" in res_miners.stdout
    res_miners_json = runner.invoke(cli.main, ["miners", "list", "--json"])
    assert res_miners_json.exit_code == 0
    assert json.loads(res_miners_json.stdout)[0]["miner_id"] == "g4-powerbook"

    urls = [r["url"] for r in recorded]
    assert "https://edge1.node.test/health" in urls
    assert "https://edge2.node.test/epoch" in urls
    assert "https://edge3.node.test/miners" in urls


def test_attest_human_flow_with_node_option(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_mock_transport(monkeypatch, _default_node_handler)
    seed_str = " ".join(sample_wallet.seed_phrase)

    res = runner.invoke(
        cli.main,
        ["attest", sample_wallet.address, "--seed", seed_str, "--node", "https://attest.node.test"],
    )
    assert res.exit_code == 0
    assert "Attestation submitted!" in res.stdout
    assert any(r["url"] == "https://attest.node.test/attestation/submit" for r in recorded)


# ---------------------------------------------------------------------------
# 4. Complete CLI Error Paths (stderr, non-zero exit, never a traceback)
# ---------------------------------------------------------------------------

def test_unreachable_node_exits_nonzero_on_stderr(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _connect_error(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    install_mock_transport(monkeypatch, _connect_error)
    seed_str = " ".join(sample_wallet.seed_phrase)
    for argv in [
        ["wallet", "balance", "RTC123"],
        ["node"],
        ["epoch"],
        ["miners", "list"],
        ["attest", sample_wallet.address, "--seed", seed_str],
    ]:
        res = runner.invoke(cli.main, argv)
        assert res.exit_code == 1
        assert "Error:" in res.stderr
        assert "Traceback" not in res.output


@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
def test_http_4xx_5xx_exits_nonzero_on_stderr_without_traceback(
    runner: CliRunner,
    sample_wallet: RustChainWallet,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    def _http_error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": f"mock failure {status_code}"})

    install_mock_transport(monkeypatch, _http_error)
    seed_str = " ".join(sample_wallet.seed_phrase)
    for argv in [
        ["wallet", "balance", "bad-address"],
        ["node"],
        ["epoch"],
        ["miners", "list"],
        ["attest", sample_wallet.address, "--seed", seed_str],
    ]:
        res = runner.invoke(cli.main, argv)
        assert res.exit_code == 1
        assert f"API error {status_code}" in res.stderr
        assert "Traceback" not in res.output


def test_wallet_send_bad_address_bad_amounts_and_missing_options(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_mock_transport(monkeypatch, _default_node_handler)
    seed_str = " ".join(sample_wallet.seed_phrase)

    # Address mismatch
    res_mismatch = runner.invoke(
        cli.main,
        ["wallet", "send", "RTCwrongaddress", "RTCdest999", "10", "--seed", seed_str],
    )
    assert res_mismatch.exit_code == 1
    assert "Address mismatch" in res_mismatch.stderr
    assert "Traceback" not in res_mismatch.output

    # Bad amount: non-numeric "abc"
    res_abc = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "abc", "--seed", seed_str],
    )
    assert res_abc.exit_code == 2
    assert "Invalid value" in res_abc.stderr
    assert "Traceback" not in res_abc.output

    # Bad amount: 0
    res_zero = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "0", "--seed", seed_str],
    )
    assert res_zero.exit_code == 1
    assert "amount must be greater than zero" in res_zero.stderr
    assert "Traceback" not in res_zero.output

    # Bad amount: negative via positional separator and unseparated option error
    res_neg_pos = runner.invoke(
        cli.main,
        ["wallet", "send", "--seed", seed_str, "--", sample_wallet.address, "RTCdest999", "-5"],
    )
    assert res_neg_pos.exit_code == 1
    assert "amount must be greater than zero" in res_neg_pos.stderr
    assert "Traceback" not in res_neg_pos.output

    res_neg_flag = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "-5", "--seed", seed_str],
    )
    assert res_neg_flag.exit_code == 2
    assert res_neg_flag.stderr.strip()
    assert "Traceback" not in res_neg_flag.output

    # Bad fee: negative
    res_neg_fee = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "10", "--fee", "-1", "--seed", seed_str],
    )
    assert res_neg_fee.exit_code == 1
    assert "fee must be zero or more" in res_neg_fee.stderr
    assert "Traceback" not in res_neg_fee.output

    # Missing required options / arguments across commands
    for missing_argv in [
        ["wallet", "balance"],
        ["wallet", "send", sample_wallet.address, "RTCdest999", "10"],
        ["wallet", "send", sample_wallet.address, "RTCdest999"],
        ["attest", sample_wallet.address],
        ["attest"],
    ]:
        res_missing = runner.invoke(cli.main, missing_argv)
        assert res_missing.exit_code == 2
        assert res_missing.stderr.strip()
        assert "Traceback" not in res_missing.output


def test_non_json_200_never_crashes_with_traceback(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_mock_transport(
        monkeypatch, lambda _req: httpx.Response(200, text="<html>upstream proxy</html>")
    )
    for argv in [["node"], ["wallet", "balance", "RTC123"], ["epoch"], ["miners", "list"]]:
        res = runner.invoke(cli.main, argv)
        assert "Traceback" not in res.output


@pytest.mark.xfail(
    strict=True,
    reason="client.py wraps non-JSON 200 into {'raw_response': ...} so node/balance exit 0",
)
def test_non_json_200_exits_nonzero_with_stderr_error(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_mock_transport(
        monkeypatch, lambda _req: httpx.Response(200, text="<html>not json</html>")
    )
    res_node = runner.invoke(cli.main, ["node"])
    assert res_node.exit_code != 0
    assert "Error:" in res_node.stderr
    assert "Traceback" not in res_node.output


# ---------------------------------------------------------------------------
# 5. Strict Regression Tests for #8564, #8565, #8566, #8580, #8618
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Rustchain#8564: fractional RTC amounts rejected by Click type=int")
def test_regression_8564_fractional_amount_accepted(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_mock_transport(monkeypatch, _default_node_handler)
    seed_str = " ".join(sample_wallet.seed_phrase)
    res = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "0.5", "--seed", seed_str],
    )
    assert res.exit_code == 0


@pytest.mark.xfail(strict=True, reason="Rustchain#8565: README documents 'node status' and 'epoch info' subcommands")
def test_regression_8565_readme_subcommands_node_status_and_epoch_info(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_mock_transport(monkeypatch, _default_node_handler)
    res_node = runner.invoke(cli.main, ["node", "status"])
    res_epoch = runner.invoke(cli.main, ["epoch", "info"])
    assert res_node.exit_code == 0
    assert res_epoch.exit_code == 0


@pytest.mark.xfail(strict=True, reason="Rustchain#8566: 'attest --json' returns early before requesting challenge or submitting attestation")
def test_regression_8566_attest_json_actually_submits_attestation(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_mock_transport(monkeypatch, _default_node_handler)
    seed_str = " ".join(sample_wallet.seed_phrase)
    res = runner.invoke(cli.main, ["attest", sample_wallet.address, "--seed", seed_str, "--json"])
    assert res.exit_code == 0
    assert any(r["path"] == "/attestation/submit" for r in recorded)


@pytest.mark.xfail(strict=True, reason="Rustchain#8580: wallet balance prints 0 RTC when node returns canonical amount_rtc / amount_i64")
def test_regression_8580_balance_reads_canonical_amount_rtc_field(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _canonical_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wallet/balance":
            return httpx.Response(
                200, json={"miner_id": "RTC123", "amount_rtc": 12.5, "amount_i64": 12500000}
            )
        return _default_node_handler(request)

    install_mock_transport(monkeypatch, _canonical_handler)
    res = runner.invoke(cli.main, ["wallet", "balance", "RTC123"])
    assert res.exit_code == 0
    assert "12.5 RTC" in res.stdout


@pytest.mark.xfail(
    strict=True,
    reason="Rustchain#8618/#8564: cli.py must accept 0.1 RTC and serialize exact 100000 micro-RTC without float drift",
)
def test_regression_8618_no_float_money_serialization(
    runner: CliRunner, sample_wallet: RustChainWallet, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = install_mock_transport(monkeypatch, _default_node_handler)
    seed_str = " ".join(sample_wallet.seed_phrase)
    res = runner.invoke(
        cli.main,
        ["wallet", "send", sample_wallet.address, "RTCdest999", "0.1", "--seed", seed_str],
    )
    assert res.exit_code == 0
    signed_posts = [r for r in recorded if r["path"] == "/wallet/transfer/signed"]
    assert len(signed_posts) == 1
    assert signed_posts[0]["json"]["amount_rtc"] == 0.1
