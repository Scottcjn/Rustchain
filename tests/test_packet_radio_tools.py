# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_tool(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_tool("rustchain_packet_radio_validator", "rustchain_packet_radio_validator.py")
sender = _load_tool("rustchain_packet_radio_sender", "rustchain_packet_radio_sender.py")


class FixedDateTime:
    @staticmethod
    def utcnow():
        return FixedDateTime()

    def isoformat(self):
        return "2026-05-13T22:00:00"


def test_validator_payload_uses_expected_wire_format(monkeypatch):
    monkeypatch.setattr(validator, "datetime", FixedDateTime)

    payload = validator.generate_validator_payload()

    assert payload == (
        "RUSTCHAIN|VALIDATOR|KE5LVX|2026-05-13T22:00:00Z|PoA_BLOCK_PROOF_HASH"
    )


def test_validator_send_prints_payload_and_skips_real_delay(monkeypatch, capsys):
    slept = []
    monkeypatch.setattr(validator.time, "sleep", lambda seconds: slept.append(seconds))

    validator.send_over_packet_radio("RUSTCHAIN|VALIDATOR|payload")

    output = capsys.readouterr().out
    assert "Preparing to transmit via TNC" in output
    assert "RUSTCHAIN|VALIDATOR|payload" in output
    assert "Packet sent" in output
    assert slept == [2]


def test_sender_generate_validator_proof_uses_callsign_destination_and_block(monkeypatch):
    monkeypatch.setattr(sender.random, "randint", lambda start, end: 4242)
    monkeypatch.setattr(sender, "datetime", FixedDateTime)

    proof = sender.generate_validator_proof()

    assert proof == "KE5LVX> RUSTGW: PROOF RUST-BLOCK-4242 @ 2026-05-13T22:00:00Z"


def test_sender_transmit_packet_prints_packet_and_skips_delay(monkeypatch, capsys):
    slept = []
    monkeypatch.setattr(sender.time, "sleep", lambda seconds: slept.append(seconds))

    sender.transmit_packet("KE5LVX> RUSTGW: PROOF RUST-BLOCK-4242")

    output = capsys.readouterr().out
    assert "Transmitting via RF" in output
    assert "RUST-BLOCK-4242" in output
    assert "Transmission complete" in output
    assert slept == [2]
