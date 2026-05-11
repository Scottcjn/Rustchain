import io
import json

from tools import payout_preflight_check


def test_read_payload_loads_json_file(tmp_path):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text('{"from_miner": "alice", "amount_rtc": 1.25}', encoding="utf-8")

    assert payout_preflight_check.read_payload(str(payload_path)) == {
        "from_miner": "alice",
        "amount_rtc": 1.25,
    }


def test_read_payload_reads_stdin_when_path_is_dash(monkeypatch):
    monkeypatch.setattr(payout_preflight_check.sys, "stdin", io.StringIO('{"ok": true}'))

    assert payout_preflight_check.read_payload("-") == {"ok": True}


def test_main_returns_success_for_valid_admin_payload(tmp_path, monkeypatch, capsys):
    payload_path = tmp_path / "admin.json"
    payload_path.write_text(
        json.dumps(
            {
                "from_miner": "alice",
                "to_miner": "bob",
                "amount_rtc": "2.5",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        payout_preflight_check.sys,
        "argv",
        ["payout_preflight_check.py", "--mode", "admin", "--input", str(payload_path)],
    )

    assert payout_preflight_check.main() == 0
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["details"]["amount_i64"] == 2500000


def test_main_returns_validation_error_for_signed_payload(capsys, monkeypatch):
    monkeypatch.setattr(payout_preflight_check.sys, "stdin", io.StringIO('{"from_address": "RTCbad"}'))
    monkeypatch.setattr(
        payout_preflight_check.sys,
        "argv",
        ["payout_preflight_check.py", "--mode", "signed", "--input", "-"],
    )

    assert payout_preflight_check.main() == 1
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "ok": False,
        "error": "missing_required_fields",
        "details": {"missing": ["to_address", "amount_rtc", "nonce", "signature", "public_key"]},
    }


def test_main_returns_invalid_json_error(tmp_path, monkeypatch, capsys):
    payload_path = tmp_path / "bad.json"
    payload_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        payout_preflight_check.sys,
        "argv",
        ["payout_preflight_check.py", "--mode", "admin", "--input", str(payload_path)],
    )

    assert payout_preflight_check.main() == 2
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is False
    assert body["error"] == "invalid_json"
    assert "details" in body
