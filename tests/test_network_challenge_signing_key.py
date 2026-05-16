# SPDX-License-Identifier: MIT
"""Regressions for network challenge signing key handling."""

import hashlib
import hmac
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "rips"
    / "rustchain-core"
    / "src"
    / "anti_spoof"
    / "network_challenge.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("network_challenge", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _hardware_profile():
    return {
        "tier": "modern",
        "openfirmware": {"serial_number": "RC-TEST-001"},
    }


def test_network_challenge_uses_instance_secret_not_pubkey_hash():
    module = _load_module()
    signing_key = b"validator-secret-not-public"

    protocol = module.NetworkChallengeProtocol(
        "public-validator-key",
        _hardware_profile(),
        validator_signing_key=signing_key,
    )
    challenge = protocol.create_challenge("target-validator", _hardware_profile())

    public_derived_key = hashlib.sha256(protocol.pubkey.encode()).digest()
    forged_signature = hmac.new(
        public_derived_key,
        challenge.to_bytes(),
        hashlib.sha256,
    ).digest()
    expected_signature = hmac.new(
        signing_key,
        challenge.to_bytes(),
        hashlib.sha256,
    ).digest()

    assert challenge.signature == expected_signature
    assert challenge.signature != forged_signature


def test_network_challenge_generates_random_secret_when_not_configured(monkeypatch):
    module = _load_module()
    generated_key = b"\x42" * 32

    monkeypatch.delenv("RC_NETWORK_CHALLENGE_SIGNING_KEY", raising=False)
    monkeypatch.setattr(module.secrets, "token_bytes", lambda size: generated_key)

    protocol = module.NetworkChallengeProtocol("public-validator-key", _hardware_profile())
    challenge = protocol.create_challenge("target-validator", _hardware_profile())

    assert protocol.signing_key == generated_key
    assert challenge.signature == hmac.new(
        generated_key,
        challenge.to_bytes(),
        hashlib.sha256,
    ).digest()


def test_network_challenge_rejects_empty_configured_signing_key():
    module = _load_module()

    with pytest.raises(ValueError, match="must not be empty"):
        module.NetworkChallengeProtocol(
            "public-validator-key",
            _hardware_profile(),
            validator_signing_key=b"",
        )
