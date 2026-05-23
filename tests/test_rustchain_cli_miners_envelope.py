import argparse
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "cli"))
import rustchain_cli


def test_miners_count_handles_enveloped_response(capsys, monkeypatch):
    payload = {
        "miners": [
            {"miner": "m1", "device_arch": "x86"},
            {"miner": "m2", "device_arch": "arm64"},
            {"miner": "m3", "device_arch": "ppc"},
        ],
        "count": 3,
        "offset": 0,
    }
    monkeypatch.setattr(rustchain_cli, "fetch_api", lambda endpoint: payload)
    rustchain_cli.cmd_miners(argparse.Namespace(count=True, json=False))
    out = capsys.readouterr().out
    assert "Active miners: 3" in out


def test_miners_table_uses_current_row_keys(capsys, monkeypatch):
    payload = {
        "miners": [
            {"miner": "wallet-1", "device_arch": "x86_64", "last_seen": 1710000000},
        ],
        "count": 1,
    }
    monkeypatch.setattr(rustchain_cli, "fetch_api", lambda endpoint: payload)
    rustchain_cli.cmd_miners(argparse.Namespace(count=False, json=False))
    out = capsys.readouterr().out
    assert "wallet-1" in out
    assert "x86_64" in out
    assert "Active Miners (1 total, showing 20)" in out


def test_miners_json_preserves_raw_envelope(capsys, monkeypatch):
    payload = {"miners": [{"miner": "wallet-1"}], "count": 1}
    monkeypatch.setattr(rustchain_cli, "fetch_api", lambda endpoint: payload)
    rustchain_cli.cmd_miners(argparse.Namespace(count=False, json=True))
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["count"] == 1
    assert parsed["miners"][0]["miner"] == "wallet-1"


def test_miners_rejects_invalid_non_list_payload(monkeypatch):
    monkeypatch.setattr(rustchain_cli, "fetch_api", lambda endpoint: {"unexpected": "shape"})
    with pytest.raises(rustchain_cli.RustChainAPIError, match="Unexpected /api/miners response format"):
        rustchain_cli.cmd_miners(argparse.Namespace(count=True, json=False))
