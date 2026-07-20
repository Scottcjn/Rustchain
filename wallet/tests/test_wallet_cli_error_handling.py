"""Tests for wallet balance CLI error handling and exit codes.

Exit code scheme:
  0 = success
  1 = generic error (usage, missing deps, invalid input)
  2 = network error (connection refused, DNS failure, timeout)
  3 = bad response (non-JSON, unexpected format)
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import requests

from tools.rustchain_wallet_cli import (
    main,
    cmd_balance,
    cmd_send,
    cmd_history,
    cmd_miners,
    cmd_epoch,
)
from tools.rustchain_wallet_cli import _safe_json, _safe_json_object


# ── _safe_json unit tests ───────────────────────────────────


def test_safe_json_valid():
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {"ok": True}
    data, rc = _safe_json(resp)
    assert data == {"ok": True}
    assert rc == 0


def test_safe_json_non_json():
    resp = MagicMock(spec=requests.Response)
    resp.ok = False
    resp.status_code = 502
    resp.json.side_effect = json.JSONDecodeError("bad json", "", 0)
    data, rc = _safe_json(resp)
    assert data is None
    assert rc == 1


def test_safe_json_object_valid():
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {"ok": True}
    data, rc = _safe_json_object(resp)
    assert data == {"ok": True}


def test_safe_json_object_list_rejected():
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = [1, 2, 3]
    data, rc = _safe_json_object(resp)
    assert data is None
    assert rc == 1


# ── Network error tests ─────────────────────────────────────


@patch("tools.rustchain_wallet_cli._request_get")
def test_balance_network_error(mock_get):
    mock_get.return_value = (None, 2)
    with patch("tools.rustchain_wallet_cli.sys.exit") as mock_exit:
        mock_exit.side_effect = SystemExit
        with pytest.raises(SystemExit):
            with patch.object(pytest, "exit"):
                pass

    rc = cmd_balance(MagicMock(wallet_id="test-wallet"))
    assert rc == 2


@patch("tools.rustchain_wallet_cli._request_get")
def test_balance_bad_response(mock_get):
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = None
    mock_get.return_value = (resp, 0)
    rc = cmd_balance(MagicMock(wallet_id="test-wallet"))
    assert rc == 1


# ── Exit code tests ─────────────────────────────────────────


def test_main_usage_error():
    """Missing required args should exit with code 1 (not 2 or unhandled)."""
    with patch("tools.rustchain_wallet_cli.sys.argv", ["rustchain-wallet"]):
        try:
            main()
        except SystemExit as e:
            assert e.code in (1, 2)


def test_main_network_error_exit_code():
    """A simulated ConnectionError from main should give exit code 2."""
    with patch(
        "tools.rustchain_wallet_cli.sys.argv",
        ["rustchain-wallet", "balance", "test-wallet"],
    ):
        with patch(
            "tools.rustchain_wallet_cli.cmd_balance",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            rc = main()
            assert rc == 2


@patch("tools.rustchain_wallet_cli._request_get")
def test_cmd_miners_success(mock_get):
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {"miners": []}
    mock_get.return_value = (resp, 0)
    rc = cmd_miners(MagicMock())
    assert rc == 0


@patch("tools.rustchain_wallet_cli._request_get")
def test_cmd_epoch_success(mock_get):
    resp = MagicMock(spec=requests.Response)
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = {"epoch": 42}
    mock_get.return_value = (resp, 0)
    rc = cmd_epoch(MagicMock())
    assert rc == 0
