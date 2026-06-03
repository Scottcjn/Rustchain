# SPDX-License-Identifier: MIT
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "rustchain_basic_listener_with_proof.py"


class FixedDateTime:
    @staticmethod
    def utcnow():
        class Stamp:
            @staticmethod
            def isoformat():
                return "2026-05-20T17:45:00"

        return Stamp()


def load_module():
    spec = importlib.util.spec_from_file_location("rustchain_basic_listener", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_import_does_not_start_listener_loop(capsys):
    load_module()

    assert capsys.readouterr().out == ""


def test_check_for_proof_detects_key_phrase(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.chdir(tmp_path)

    assert module.check_for_proof() is False

    (tmp_path / "validator_output.log").write_text(
        "booting validator\n✅ Proof accepted by node network.\n",
        encoding="utf-8",
    )

    assert module.check_for_proof() is True


def test_write_proof_json_records_expected_payload(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "datetime", FixedDateTime)

    module.write_proof_json()

    payload = json.loads((tmp_path / "proof_of_listen_qb45.json").read_text(encoding="utf-8"))
    assert payload == {
        "validator_type": "QuickBASIC 4.5",
        "validator_id": "BASIC-KE5LVX",
        "timestamp": "2026-05-20T17:45:00Z",
        "proof_type": "stdout_log_phrase",
        "status": "validated",
        "trigger": module.KEY_PHRASE,
        "source_file": "validator_output.log",
    }
    assert "Proof of listen written" in capsys.readouterr().out


def test_listen_writes_proof_once_when_phrase_is_present(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "datetime", FixedDateTime)
    (tmp_path / "validator_output.log").write_text(module.KEY_PHRASE, encoding="utf-8")

    assert module.listen(poll_interval=0) is True

    assert (tmp_path / "proof_of_listen_qb45.json").exists()
    output = capsys.readouterr().out
    assert "RustChain BASIC Listener Activated" in output
    assert "BASIC validation detected" in output
