# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest


class FixedDatetime:
    @classmethod
    def utcnow(cls):
        return datetime(2026, 5, 13, 6, 30, 0)


@pytest.fixture()
def packet_radio_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "rustchain_packet_radio_validator.py"
    )
    spec = importlib.util.spec_from_file_location("packet_radio_validator", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def freeze_payload_clock(packet_radio_module, monkeypatch):
    monkeypatch.setattr(packet_radio_module, "datetime", FixedDatetime)


def test_generate_validator_payload_uses_expected_wire_format(
    packet_radio_module, monkeypatch
):
    freeze_payload_clock(packet_radio_module, monkeypatch)

    payload = packet_radio_module.generate_validator_payload()

    assert (
        payload
        == "RUSTCHAIN|VALIDATOR|KE5LVX|2026-05-13T06:30:00Z|PoA_BLOCK_PROOF_HASH"
    )


def test_generate_validator_payload_has_stable_fields(packet_radio_module, monkeypatch):
    freeze_payload_clock(packet_radio_module, monkeypatch)

    payload = packet_radio_module.generate_validator_payload()

    prefix, role, callsign, timestamp, proof_hash = payload.split("|")

    assert prefix == "RUSTCHAIN"
    assert role == "VALIDATOR"
    assert callsign == "KE5LVX"
    assert timestamp.endswith("Z")
    assert proof_hash == "PoA_BLOCK_PROOF_HASH"


def test_generate_validator_payload_has_exactly_five_fields(
    packet_radio_module, monkeypatch
):
    freeze_payload_clock(packet_radio_module, monkeypatch)

    payload = packet_radio_module.generate_validator_payload()

    assert len(payload.split("|")) == 5


def test_send_over_packet_radio_prints_payload_and_status(
    packet_radio_module, monkeypatch, capsys
):
    sleep_calls = []
    monkeypatch.setattr(packet_radio_module.time, "sleep", sleep_calls.append)

    packet_radio_module.send_over_packet_radio("RUSTCHAIN|VALIDATOR|TEST")

    output = capsys.readouterr().out
    assert "Preparing to transmit via TNC" in output
    assert ">>>> RUSTCHAIN|VALIDATOR|TEST" in output
    assert "Transmitting" in output
    assert "Packet sent" in output
    assert "Flame acknowledged" in output
    assert sleep_calls == [2]


def test_send_over_packet_radio_accepts_empty_payload(
    packet_radio_module, monkeypatch, capsys
):
    sleep_calls = []
    monkeypatch.setattr(packet_radio_module.time, "sleep", sleep_calls.append)

    packet_radio_module.send_over_packet_radio("")

    output = capsys.readouterr().out
    assert ">>>> " in output
    assert "Packet sent" in output
    assert sleep_calls == [2]
