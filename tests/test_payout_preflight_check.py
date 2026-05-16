# SPDX-License-Identifier: MIT
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "payout_preflight_check.py"
spec = importlib.util.spec_from_file_location("payout_preflight_check", MODULE_PATH)
payout_preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payout_preflight_check)


def test_read_payload_reads_json_file(tmp_path):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"amount_rtc": 1, "to_miner": "bob"}')

    assert payout_preflight_check.read_payload(str(payload_path)) == {
        "amount_rtc": 1,
        "to_miner": "bob",
    }


def test_read_payload_reads_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"from_miner": "alice"}'))

    assert payout_preflight_check.read_payload("-") == {"from_miner": "alice"}


def test_main_admin_mode_returns_success(monkeypatch, tmp_path, capsys):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"from_miner":"alice","to_miner":"bob","amount_rtc":1}')
    monkeypatch.setattr(
        sys,
        "argv",
        ["payout_preflight_check", "--mode", "admin", "--input", str(payload_path)],
    )
    monkeypatch.setattr(
        payout_preflight_check,
        "validate_wallet_transfer_admin",
        lambda payload: SimpleNamespace(ok=True, error=None, details={"mode": "admin"}),
    )

    assert payout_preflight_check.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"ok": True, "error": None, "details": {"mode": "admin"}}


def test_main_signed_mode_returns_validation_failure(monkeypatch, tmp_path, capsys):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"from_address":"alice"}')
    monkeypatch.setattr(
        sys,
        "argv",
        ["payout_preflight_check", "--mode", "signed", "--input", str(payload_path)],
    )
    monkeypatch.setattr(
        payout_preflight_check,
        "validate_wallet_transfer_signed",
        lambda payload: SimpleNamespace(
            ok=False, error="missing_signature", details={"field": "signature"}
        ),
    )

    assert payout_preflight_check.main() == 1
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["error"] == "missing_signature"
    assert output["details"] == {"field": "signature"}


def test_main_invalid_json_returns_code_2(monkeypatch, tmp_path, capsys):
    payload_path = tmp_path / "bad.json"
    payload_path.write_text("{bad json")
    monkeypatch.setattr(
        sys,
        "argv",
        ["payout_preflight_check", "--mode", "admin", "--input", str(payload_path)],
    )

    assert payout_preflight_check.main() == 2
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["error"] == "invalid_json"
    assert output["details"]
