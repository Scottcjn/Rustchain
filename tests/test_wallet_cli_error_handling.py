import pytest
import sys
from types import SimpleNamespace
from tools import rustchain_wallet_cli as cli

class FakeResponse:
    def __init__(self, payload, ok=True, status_code=200):
        self.payload = payload
        self.ok = ok
        self.status_code = status_code

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_cmd_balance_empty_wallet_id(capsys):
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="   "))
    assert rc == cli.EXIT_USAGE_ERROR
    assert "Wallet address is required" in capsys.readouterr().err


def test_cmd_balance_network_error(monkeypatch, capsys):
    def mock_get(*args, **kwargs):
        raise cli.requests.exceptions.ConnectionError("Connection refused")

    monkeypatch.setattr(cli.requests, "get", mock_get)
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCabc"))
    assert rc == cli.EXIT_NETWORK_ERROR
    assert "Network error" in capsys.readouterr().err


def test_cmd_balance_http_error(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *args, **kwargs: FakeResponse("Internal Error", ok=False, status_code=500))
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCabc"))
    assert rc == cli.EXIT_BAD_RESPONSE
    assert "HTTP 500" in capsys.readouterr().err


def test_cmd_balance_invalid_json(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *args, **kwargs: FakeResponse(ValueError("Expecting value"), ok=True))
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCabc"))
    assert rc == cli.EXIT_BAD_RESPONSE
    assert "invalid JSON" in capsys.readouterr().err


def test_cmd_balance_non_object_json(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *args, **kwargs: FakeResponse(["item1"]))
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCabc"))
    assert rc == cli.EXIT_BAD_RESPONSE
    assert "not an object" in capsys.readouterr().err


def test_cmd_balance_success(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *args, **kwargs: FakeResponse({"balance_rtc": 50.0}))
    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCabc"))
    assert rc == cli.EXIT_SUCCESS
    captured = capsys.readouterr()
    assert "50.0" in captured.out
    assert captured.err == ""
