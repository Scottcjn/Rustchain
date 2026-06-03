# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "rips" / "rustchain-core" / "src" / "anti_spoof" / "mutating_challenge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("mutating_challenge_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hardware_profile():
    return {
        "cpu": {"model": "PowerMac3,6"},
        "openfirmware": {"serial_number": "OF123"},
        "gpu": {"device_id": "GPU123"},
        "storage": {"serial": "SSD123"},
    }


def _challenge_context(module):
    network = module.MutatingChallengeNetwork(["alpha-node", "beta-node"], genesis_seed=b"g" * 32)
    for validator in network.validator_failures:
        network.register_hardware(validator, _hardware_profile())
    challenge = network.on_new_block(10, b"b" * 32)[0]
    challenge.mutation_params.hash_rounds = 2
    return network, challenge


def _valid_response(module, network, challenge):
    response = module.MutatingResponse(
        challenge_id=challenge.challenge_id,
        responder=challenge.target,
        cache_timing_ticks=challenge.mutation_params.timing_min_ticks + 1,
        memory_timing_ticks=45000,
        pipeline_timing_ticks=8000,
        jitter_variance=challenge.mutation_params.jitter_min_percent,
        thermal_celsius=(
            challenge.mutation_params.thermal_min_c
            + challenge.mutation_params.thermal_max_c
        )
        // 2,
        serial_value=network._get_serial(
            network.validator_hardware[challenge.target],
            challenge.mutation_params.serial_type,
        ),
        proof_hash=b"",
        timestamp_ms=challenge.timestamp_ms + 1000,
    )
    response.proof_hash = response.compute_proof(challenge, b"")
    return response


def test_validate_response_accepts_matching_proof_hash():
    module = _load_module()
    network, challenge = _challenge_context(module)
    response = _valid_response(module, network, challenge)

    valid, confidence, failures = network.validate_response(response)

    assert valid is True
    assert confidence == 100.0
    assert failures == []


def test_validate_response_rejects_missing_proof_hash():
    module = _load_module()
    network, challenge = _challenge_context(module)
    response = _valid_response(module, network, challenge)
    response.proof_hash = b""

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 50.0
    assert "Missing proof hash" in failures


def test_validate_response_rejects_mismatched_proof_hash():
    module = _load_module()
    network, challenge = _challenge_context(module)
    response = _valid_response(module, network, challenge)
    response.proof_hash = b"\x00" * 32

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 50.0
    assert "Proof hash mismatch" in failures
