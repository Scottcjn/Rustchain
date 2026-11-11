# SPDX-License-Identifier: Apache-2.0
"""Regression tests for Issue #7889 / Bounty #16253:
Consistent error handling + exit codes in wallet balance check script & CLI.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from tools import rustchain_wallet_cli as cli

ROOT = Path(__file__).resolve().parents[1]
CHECK_BALANCE_SH = ROOT / "scripts" / "check_balance.sh"


class FakeResponse:
    def __init__(self, payload, ok=True, status_code=200):
        self.payload = payload
        self.ok = ok
        self.status_code = status_code

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_cmd_balance_happy_path_and_alias(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *a, **kw: FakeResponse({"balance_rtc": "19.75", "miner_id": "RTCvalid12345"}))
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCvalid12345"))
    assert rc == cli.EXIT_SUCCESS
    captured = capsys.readouterr()
    assert '"amount_rtc": 19.75' in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("bad_wallet", ["", "   ", "RTC with spaces"])
def test_cmd_balance_invalid_wallet_returns_usage_error(bad_wallet, capsys):
    rc = cli.cmd_balance(SimpleNamespace(wallet_id=bad_wallet))
    assert rc == cli.EXIT_USAGE_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Invalid or empty wallet address" in captured.err


def test_cmd_balance_network_errors_return_exit_2(monkeypatch, capsys):
    def raise_conn(*a, **kw):
        raise cli.requests.exceptions.ConnectionError("DNS lookup failed")

    monkeypatch.setattr(cli.requests, "get", raise_conn)
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCnet123456"))
    assert rc == cli.EXIT_NETWORK_ERROR
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR: Network error" in captured.err


def test_cmd_balance_http_404_and_json_not_found_return_exit_4(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *a, **kw: FakeResponse({"error": "not found"}, ok=False, status_code=404))
    assert cli.cmd_balance(SimpleNamespace(wallet_id="RTCmissing404")) == cli.EXIT_WALLET_NOT_FOUND
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not found" in captured.err.lower()

    # HTTP 200 with ok=False and wallet not found error
    monkeypatch.setattr(
        cli.requests,
        "get",
        lambda *a, **kw: FakeResponse({"ok": False, "error": "Unknown wallet address"}, ok=True, status_code=200),
    )
    assert cli.cmd_balance(SimpleNamespace(wallet_id="RTCmissing200")) == cli.EXIT_WALLET_NOT_FOUND
    captured2 = capsys.readouterr()
    assert captured2.out == ""
    assert "not found" in captured2.err.lower()


@pytest.mark.parametrize(
    "bad_amount",
    [None, True, False, "not-a-number", "-5.0", -1, float("nan"), float("inf"), {"nested": 1}, [1]],
)
def test_cmd_balance_rejects_non_numeric_or_negative_balance(monkeypatch, capsys, bad_amount):
    monkeypatch.setattr(cli.requests, "get", lambda *a, **kw: FakeResponse({"amount_rtc": bad_amount}))
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCbadamount"))
    assert rc == cli.EXIT_BAD_RESPONSE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR:" in captured.err


def test_cmd_balance_rejects_mismatched_returned_wallet(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.requests,
        "get",
        lambda *a, **kw: FakeResponse({"amount_rtc": 10.0, "miner_id": "RTCotherwallet"}),
    )
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCrequested"))
    assert rc == cli.EXIT_BAD_RESPONSE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "does not match requested" in captured.err


def test_cmd_export_missing_wallet_returns_exit_4(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "KEYSTORE_DIR", tmp_path)
    rc = cli.cmd_export(SimpleNamespace(wallet="nonexistent-wallet"))
    assert rc == cli.EXIT_WALLET_NOT_FOUND
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Keystore not found" in captured.err


def test_check_balance_sh_documents_and_enforces_exit_codes():
    script_text = CHECK_BALANCE_SH.read_text(encoding="utf-8")
    assert "jq -e 'type == "object"'" in script_text
    assert "malformed or non-object JSON response" in script_text
    assert "response wallet '${RETURNED_WALLET}' does not match requested '${WALLET}'" in script_text
    assert ".amount_rtc // .balance_rtc" in script_text
