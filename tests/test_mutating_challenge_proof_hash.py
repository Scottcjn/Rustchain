import hashlib
import sys
import time
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "src" / "anti_spoof"
sys.path.insert(0, str(SRC))

from mutating_challenge import MutatingChallengeNetwork, MutatingResponse


def _hardware_profile(serial="SERIAL123"):
    return {
        "openfirmware": {"serial_number": serial},
        "cpu": {"model": "PowerMac3,6"},
        "gpu": {"device_id": "0x4966"},
        "storage": {"serial": "WD-WMAJ91385123"},
    }


def _network_and_challenge():
    network = MutatingChallengeNetwork(
        ["challenger-node", "target-node"],
        genesis_seed=b"proof-test-seed",
    )
    network.register_hardware("challenger-node", _hardware_profile("CHALLENGER123"))
    network.register_hardware("target-node", _hardware_profile("TARGET123"))

    challenges = network.on_new_block(10, hashlib.sha256(b"block-10").digest())
    challenge = next(item for item in challenges if item.target == "target-node")
    return network, challenge


def _valid_response(challenge, entropy=b"real-hardware-entropy"):
    params = challenge.mutation_params
    serial_value = {
        "openfirmware": "TARGET123",
        "platform": "PowerMac3,6",
        "gpu": "0x4966",
        "storage": "WD-WMAJ91385123",
    }[params.serial_type]
    response = MutatingResponse(
        challenge_id=challenge.challenge_id,
        responder=challenge.target,
        cache_timing_ticks=params.timing_min_ticks + 100,
        memory_timing_ticks=params.timing_min_ticks + 200,
        pipeline_timing_ticks=params.pipeline_test_depth + 200,
        jitter_variance=params.jitter_min_percent + 20,
        thermal_celsius=(params.thermal_min_c + params.thermal_max_c) // 2,
        serial_value=serial_value,
        proof_hash=b"",
        timestamp_ms=int(time.time() * 1000),
        hardware_entropy=entropy,
    )
    response.proof_hash = response.compute_proof(challenge, entropy)
    return response


def test_valid_response_with_non_empty_entropy_is_accepted():
    network, challenge = _network_and_challenge()
    response = _valid_response(challenge, entropy=b"actual-device-noise")

    valid, confidence, failures = network.validate_response(response)

    assert valid is True
    assert confidence == 100.0
    assert failures == []
    assert network.round_robin.results_this_round[challenge.target] is True


def test_missing_proof_hash_is_rejected_even_when_other_signals_pass():
    network, challenge = _network_and_challenge()
    response = _valid_response(challenge)
    response.proof_hash = b""

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 50.0
    assert failures == ["Missing proof hash"]
    assert network.validator_failures[challenge.target] == 1


def test_tampered_proof_hash_is_rejected():
    network, challenge = _network_and_challenge()
    response = _valid_response(challenge)
    response.proof_hash = bytes([response.proof_hash[0] ^ 1]) + response.proof_hash[1:]

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 50.0
    assert failures == ["Proof hash mismatch"]
    assert network.validator_failures[challenge.target] == 1


def test_wrong_entropy_for_same_proof_is_rejected():
    network, challenge = _network_and_challenge()
    response = _valid_response(challenge, entropy=b"original-entropy")
    response.hardware_entropy = b"different-entropy"

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 50.0
    assert failures == ["Proof hash mismatch"]
    assert network.validator_failures[challenge.target] == 1
