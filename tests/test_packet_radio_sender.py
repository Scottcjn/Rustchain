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
def packet_sender_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "tools" / "rustchain_packet_radio_sender.py"
    )
    spec = importlib.util.spec_from_file_location("packet_radio_sender", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def freeze_proof_inputs(packet_sender_module, monkeypatch, block_suffix=4242):
    monkeypatch.setattr(packet_sender_module, "datetime", FixedDatetime)
    monkeypatch.setattr(
        packet_sender_module.random, "randint", lambda _low, _high: block_suffix
    )


def test_generate_validator_proof_uses_expected_ax25_format(
    packet_sender_module, monkeypatch
):
    freeze_proof_inputs(packet_sender_module, monkeypatch)

    proof = packet_sender_module.generate_validator_proof()

    assert (
        proof
        == "KE5LVX> RUSTGW: PROOF RUST-BLOCK-4242 @ 2026-05-13T06:30:00Z"
    )


def test_generate_validator_proof_requests_four_digit_block_id(
    packet_sender_module, monkeypatch
):
    randint_calls = []

    def fake_randint(low, high):
        randint_calls.append((low, high))
        return 1000

    monkeypatch.setattr(packet_sender_module, "datetime", FixedDatetime)
    monkeypatch.setattr(packet_sender_module.random, "randint", fake_randint)

    proof = packet_sender_module.generate_validator_proof()

    assert "RUST-BLOCK-1000" in proof
    assert randint_calls == [(1000, 9999)]


def test_generate_validator_proof_has_stable_parts(packet_sender_module, monkeypatch):
    freeze_proof_inputs(packet_sender_module, monkeypatch, block_suffix=9999)

    proof = packet_sender_module.generate_validator_proof()

    assert proof.startswith("KE5LVX> RUSTGW: PROOF ")
    assert "RUST-BLOCK-9999" in proof
    assert proof.endswith("Z")


def test_transmit_packet_prints_packet_and_status(
    packet_sender_module, monkeypatch, capsys
):
    sleep_calls = []
    monkeypatch.setattr(packet_sender_module.time, "sleep", sleep_calls.append)

    packet_sender_module.transmit_packet("KE5LVX> RUSTGW: PROOF TEST")

    output = capsys.readouterr().out
    assert "Transmitting via RF" in output
    assert ">>> KE5LVX> RUSTGW: PROOF TEST" in output
    assert "Transmission complete" in output
    assert "73 confirmation" in output
    assert sleep_calls == [2]


def test_transmit_packet_accepts_empty_packet(packet_sender_module, monkeypatch, capsys):
    sleep_calls = []
    monkeypatch.setattr(packet_sender_module.time, "sleep", sleep_calls.append)

    packet_sender_module.transmit_packet("")

    output = capsys.readouterr().out
    assert ">>> " in output
    assert "Transmission complete" in output
    assert sleep_calls == [2]
