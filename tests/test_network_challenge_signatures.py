# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


pytest.importorskip("cryptography")

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "rips" / "rustchain-core" / "src" / "anti_spoof" / "network_challenge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("network_challenge_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hardware_profile():
    return {
        "tier": "modern",
        "openfirmware": {"serial_number": "G84243AZQ6P"},
    }


def _valid_response(module, challenge, responder_private_key):
    response = module.ChallengeResponse(
        challenge_id=challenge.challenge_id,
        response_timestamp=challenge.timestamp + 1000,
        timebase_value=173470036125283,
        cache_l1_ticks=150,
        cache_l2_ticks=450,
        cache_ratio=3.0,
        memory_ticks=15000,
        thermal_celsius=43,
        hardware_serial="G84243AZQ6P",
        jitter_variance=25,
        pipeline_cycles=1200,
        response_hash=b"",
        responder_pubkey="",
        signature=b"",
    )
    response.response_hash = response.hash()
    return module.AntiSpoofValidator().sign_response(response, responder_private_key)


def test_protocol_rejects_mismatched_registered_pubkey():
    module = _load_module()
    private_key = module.generate_validator_private_key()
    public_key = module.derive_validator_pubkey(private_key)

    protocol = module.NetworkChallengeProtocol(public_key, _hardware_profile(), private_key)

    assert protocol.pubkey == public_key
    with pytest.raises(ValueError, match="validator_pubkey"):
        module.NetworkChallengeProtocol("00" * 32, _hardware_profile(), private_key)


def test_challenge_signature_is_bound_to_advertised_pubkey():
    module = _load_module()
    private_key = module.generate_validator_private_key()
    validator = module.AntiSpoofValidator()
    challenge = validator.generate_challenge(
        target_pubkey="target",
        expected_hardware=_hardware_profile(),
        challenger_privkey=private_key,
    )

    assert challenge.challenger_pubkey == module.derive_validator_pubkey(private_key)
    assert validator.validate_challenge_signature(challenge) is True

    challenge.signature = b"\x00" * 64
    assert validator.validate_challenge_signature(challenge) is False


def test_validate_response_rejects_forged_response_signature():
    module = _load_module()
    challenger_private_key = module.generate_validator_private_key()
    responder_private_key = module.generate_validator_private_key()
    validator = module.AntiSpoofValidator()
    challenge = validator.generate_challenge(
        target_pubkey=module.derive_validator_pubkey(responder_private_key),
        expected_hardware=_hardware_profile(),
        challenger_privkey=challenger_private_key,
    )
    response = _valid_response(module, challenge, responder_private_key)

    assert validator.validate_response(challenge, response).valid is True

    response.signature = b"\x00" * 64
    result = validator.validate_response(challenge, response)

    assert result.valid is False
    assert any("Response signature invalid" in reason for reason in result.failure_reasons)


def test_validate_response_rejects_forged_challenge_signature():
    module = _load_module()
    challenger_private_key = module.generate_validator_private_key()
    responder_private_key = module.generate_validator_private_key()
    validator = module.AntiSpoofValidator()
    challenge = validator.generate_challenge(
        target_pubkey=module.derive_validator_pubkey(responder_private_key),
        expected_hardware=_hardware_profile(),
        challenger_privkey=challenger_private_key,
    )
    response = _valid_response(module, challenge, responder_private_key)

    challenge.signature = b"\x00" * 64
    result = validator.validate_response(challenge, response)

    assert result.valid is False
    assert any("Challenge signature invalid" in reason for reason in result.failure_reasons)
