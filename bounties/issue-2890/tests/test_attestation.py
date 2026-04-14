"""
Tests for EnvelopeAttestation module.

Run with: pytest tests/test_attestation.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentfolio_beacon.attestation import (
    EnvelopeAttestation,
    attest_bounty_submission,
    verify_attestation,
    verify_attestation_from_envelope,
    verify_attestation_from_json,
    _generate_nonce,
    _canonical_signed_fields,
    _canonical_signing_payload,
    NACL_AVAILABLE,
)


# A known Ed25519 keypair for testing (generated once, never used in production)
_TEST_SIGNING_KEY_HEX = "a" * 64  # 32 bytes = 64 hex chars (valid but not real)


class TestNonceGeneration:
    """Test nonce generation."""

    def test_nonce_is_deterministic_for_same_input(self):
        """Same submission_id + timestamp produces same nonce."""
        n1 = _generate_nonce("sub_123", 1712700000)
        n2 = _generate_nonce("sub_123", 1712700000)
        assert n1 == n2

    def test_nonce_differs_for_different_submission(self):
        """Different submission_id produces different nonce."""
        n1 = _generate_nonce("sub_123", 1712700000)
        n2 = _generate_nonce("sub_456", 1712700000)
        assert n1 != n2

    def test_nonce_differs_for_different_timestamp(self):
        """Different timestamp produces different nonce."""
        n1 = _generate_nonce("sub_123", 1712700000)
        n2 = _generate_nonce("sub_123", 1712700001)
        assert n1 != n2

    def test_nonce_length(self):
        """Nonce is 32 hex chars (16 bytes blake2b)."""
        nonce = _generate_nonce("sub_123", 1712700000)
        assert len(nonce) == 32


class TestCanonicalFields:
    """Test canonical field extraction."""

    def test_excludes_sig_field(self):
        """sig field is excluded from signed fields."""
        envelope = {"agent_id": "test", "sig": "abc123", "kind": "bounty"}
        fields = _canonical_signed_fields(envelope)
        assert "sig" not in fields
        assert "agent_id" in fields
        assert "kind" in fields

    def test_excludes_beacon_version(self):
        """_beacon_version field is excluded."""
        envelope = {"agent_id": "test", "_beacon_version": "2", "kind": "bounty"}
        fields = _canonical_signed_fields(envelope)
        assert "_beacon_version" not in fields

    def test_payload_is_canonical_json(self):
        """Signing payload is canonical JSON (sorted keys, no spaces)."""
        envelope = {"b": 2, "a": 1, "sig": "x"}
        payload = _canonical_signing_payload(envelope)
        expected = b'{"a":1,"b":2}'
        assert payload == expected


class TestEnvelopeAttestationDataclass:
    """Test EnvelopeAttestation serialization."""

    def test_default_values(self):
        """Test default field values."""
        att = EnvelopeAttestation(agent_id="test-agent")
        assert att.agent_id == "test-agent"
        assert att.kind == "bounty"
        assert att.nonce == ""
        assert att.timestamp == 0

    def test_to_envelope(self):
        """Test envelope serialization."""
        att = EnvelopeAttestation(
            agent_id="test-agent",
            nonce="abc123",
            bounty_id="bounty_1",
            submission_id="sub_1",
            pr_url="https://github.com/test/pull/1",
            summary="Fixed bug",
            timestamp=1712700000,
            pubkey_hex="deadbeef",
            sig_hex="cafebabe",
        )
        env = att.to_envelope()
        assert env["agent_id"] == "test-agent"
        assert env["kind"] == "bounty"
        assert env["nonce"] == "abc123"
        assert env["bounty_id"] == "bounty_1"
        assert env["sig"] == "cafebabe"

    def test_roundtrip_envelope(self):
        """Test envelope → from_envelope → to_envelope roundtrip."""
        original = {
            "agent_id": "test-agent",
            "kind": "bounty",
            "nonce": "abc123",
            "bounty_id": "bounty_1",
            "submission_id": "sub_1",
            "pr_url": "https://github.com/test/pull/1",
            "summary": "Fixed bug",
            "timestamp": 1712700000,
            "pubkey": "deadbeef",
            "sig": "cafebabe",
        }
        att = EnvelopeAttestation.from_envelope(original)
        result = att.to_envelope()
        assert result == original

    def test_to_json(self):
        """Test JSON serialization."""
        att = EnvelopeAttestation(
            agent_id="test-agent",
            nonce="abc",
            bounty_id="b1",
            submission_id="s1",
            pr_url="https://example.com/pr",
            summary="Work done",
            timestamp=1000,
            pubkey_hex="aa",
            sig_hex="bb",
        )
        json_str = att.to_json()
        parsed = json.loads(json_str)
        assert parsed["agent_id"] == "test-agent"
        assert parsed["kind"] == "bounty"

    def test_roundtrip_json(self):
        """Test JSON roundtrip."""
        att = EnvelopeAttestation(
            agent_id="test-agent",
            nonce="abc",
            bounty_id="b1",
            submission_id="s1",
            pr_url="https://example.com/pr",
            summary="Work done",
            timestamp=1000,
            pubkey_hex="aa",
            sig_hex="bb",
        )
        restored = EnvelopeAttestation.from_json(att.to_json())
        assert restored.agent_id == att.agent_id
        assert restored.nonce == att.nonce
        assert restored.sig_hex == att.sig_hex


class TestAttestBountySubmission:
    """Test attestation creation."""

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_creates_valid_attestation(self):
        """Test that a valid attestation is created."""
        # Generate a real keypair for this test
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()

        att = attest_bounty_submission(
            bounty_id="bounty_123",
            submission_id="sub_456",
            submitter_agent_id="test-agent",
            pr_url="https://github.com/test/pull/1",
            summary="Implemented feature",
            signing_key_hex=sk_hex,
            timestamp=1712700000,
        )

        assert att.agent_id == "test-agent"
        assert att.kind == "bounty"
        assert att.bounty_id == "bounty_123"
        assert att.submission_id == "sub_456"
        assert att.pr_url == "https://github.com/test/pull/1"
        assert att.summary == "Implemented feature"
        assert att.timestamp == 1712700000
        assert att.pubkey_hex  # Non-empty
        assert att.sig_hex  # Non-empty
        assert len(att.sig_hex) == 128  # 64 bytes = 128 hex chars

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_nonce_is_unique_per_submission(self):
        """Test that different submissions get different nonces."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()

        att1 = attest_bounty_submission(
            bounty_id="b1", submission_id="sub_1",
            submitter_agent_id="agent", pr_url="https://x.com/1",
            summary="Work 1", signing_key_hex=sk_hex,
        )
        att2 = attest_bounty_submission(
            bounty_id="b1", submission_id="sub_2",
            submitter_agent_id="agent", pr_url="https://x.com/2",
            summary="Work 2", signing_key_hex=sk_hex,
        )
        assert att1.nonce != att2.nonce

    def test_raises_without_pynacl(self):
        """Test that creation fails without PyNaCl."""
        with patch("agentfolio_beacon.attestation.NACL_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="PyNaCl is required"):
                attest_bounty_submission(
                    bounty_id="b1", submission_id="s1",
                    submitter_agent_id="agent", pr_url="https://x.com/1",
                    summary="Work", signing_key_hex="aa" * 32,
                )

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_raises_on_invalid_key(self):
        """Test that invalid signing key raises ValueError."""
        with pytest.raises(ValueError, match="Invalid signing key"):
            attest_bounty_submission(
                bounty_id="b1", submission_id="s1",
                submitter_agent_id="agent", pr_url="https://x.com/1",
                summary="Work", signing_key_hex="not_hex!!",
            )


class TestVerifyAttestation:
    """Test attestation verification."""

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_valid_attestation_verifies(self):
        """Test that a properly signed attestation verifies."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()

        att = attest_bounty_submission(
            bounty_id="bounty_123",
            submission_id="sub_456",
            submitter_agent_id="test-agent",
            pr_url="https://github.com/test/pull/1",
            summary="Implemented feature",
            signing_key_hex=sk_hex,
        )

        valid, reason = verify_attestation(att)
        assert valid is True
        assert reason == ""

    def test_missing_signature(self):
        """Test that missing signature fails verification."""
        att = EnvelopeAttestation(
            agent_id="test",
            pubkey_hex="aa" * 32,
            sig_hex="",  # Empty signature
        )
        valid, reason = verify_attestation(att)
        assert valid is False
        assert "missing_signature" in reason

    def test_missing_pubkey(self):
        """Test that missing pubkey fails verification."""
        att = EnvelopeAttestation(
            agent_id="test",
            sig_hex="bb" * 64,
            pubkey_hex="",  # Empty pubkey
        )
        valid, reason = verify_attestation(att)
        assert valid is False
        assert "missing_pubkey" in reason

    def test_missing_agent_id(self):
        """Test that missing agent_id fails verification."""
        att = EnvelopeAttestation(
            agent_id="",  # Empty
            pubkey_hex="aa" * 32,
            sig_hex="bb" * 64,
        )
        valid, reason = verify_attestation(att)
        assert valid is False
        assert "missing_agent_id" in reason

    def test_invalid_kind(self):
        """Test that non-bounty kind fails verification."""
        att = EnvelopeAttestation(
            agent_id="test",
            kind="heartbeat",  # Wrong kind
            pubkey_hex="aa" * 32,
            sig_hex="bb" * 64,
        )
        valid, reason = verify_attestation(att)
        assert valid is False
        assert "invalid_kind" in reason

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_tampered_envelope_fails(self):
        """Test that modifying the envelope after signing fails verification."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()

        att = attest_bounty_submission(
            bounty_id="bounty_123",
            submission_id="sub_456",
            submitter_agent_id="test-agent",
            pr_url="https://github.com/test/pull/1",
            summary="Original summary",
            signing_key_hex=sk_hex,
        )

        # Tamper with the summary
        att.summary = "Tampered summary"

        valid, reason = verify_attestation(att)
        assert valid is False
        assert "invalid_signature" in reason

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_wrong_key_fails(self):
        """Test that signature from different key fails verification."""
        from nacl.signing import SigningKey
        sk1 = SigningKey.generate()
        sk2 = SigningKey.generate()

        # Sign with key 1
        att = attest_bounty_submission(
            bounty_id="b1", submission_id="s1",
            submitter_agent_id="agent", pr_url="https://x.com/1",
            summary="Work", signing_key_hex=sk1.encode().hex(),
        )

        # But claim it's from key 2
        att.pubkey_hex = sk2.verify_key.encode().hex()

        valid, reason = verify_attestation(att)
        assert valid is False
        assert "invalid_signature" in reason


class TestVerifyFromEnvelope:
    """Test verification from raw envelope dict."""

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_verify_from_envelope(self):
        """Test verification directly from envelope dict."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()

        att = attest_bounty_submission(
            bounty_id="b1", submission_id="s1",
            submitter_agent_id="agent", pr_url="https://x.com/1",
            summary="Work", signing_key_hex=sk_hex,
        )

        envelope = att.to_envelope()
        valid, reason = verify_attestation_from_envelope(envelope)
        assert valid is True

    def test_verify_from_envelope_invalid_json(self):
        """Test that invalid envelope dict is handled."""
        valid, reason = verify_attestation_from_envelope({"not": "a real envelope"})
        assert valid is False


class TestVerifyFromJson:
    """Test verification from JSON string."""

    @pytest.mark.skipif(not NACL_AVAILABLE, reason="PyNaCl not installed")
    def test_verify_from_json(self):
        """Test verification from JSON string."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        sk_hex = sk.encode().hex()

        att = attest_bounty_submission(
            bounty_id="b1", submission_id="s1",
            submitter_agent_id="agent", pr_url="https://x.com/1",
            summary="Work", signing_key_hex=sk_hex,
        )

        valid, reason = verify_attestation_from_json(att.to_json())
        assert valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
