"""
EnvelopeAttestation — Sign bounty submissions as Beacon v2 envelopes.

Produces cryptographically verifiable attestations that bind a bounty
submission to the submitter's Ed25519 identity.

Gracefully degrades when PyNaCl is unavailable (attestation creation
requires signing, but verification works with just `cryptography`).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# --- Optional crypto imports ---
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.exceptions import BadSignatureError
    NACL_AVAILABLE = True
except ImportError:
    SigningKey = None  # type: ignore[misc,assignment]
    VerifyKey = None   # type: ignore[misc,assignment]
    BadSignatureError = Exception  # type: ignore[misc,assignment]
    NACL_AVAILABLE = False

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    _CRYPTO_AVAILABLE = True
except ImportError:
    Ed25519PublicKey = None  # type: ignore[misc,assignment]
    _CRYPTO_AVAILABLE = False


# Beacon v2 constants (matching beacon_anchor.py)
# Note: This set is informational and mirrors the Beacon v2 spec.
# The verifier currently only accepts kind == "bounty".
VALID_KINDS = {"hello", "heartbeat", "want", "bounty", "mayday", "accord", "pushback"}
UNSIGNED_TRANSPORT_FIELDS = ("sig", "_beacon_version")


def _generate_nonce(submission_id: str, timestamp: Optional[int] = None) -> str:
    """Generate a deterministic-but-unique nonce from submission_id + timestamp."""
    ts = timestamp or int(time.time())
    payload = f"{submission_id}:{ts}".encode()
    return hashlib.blake2b(payload, digest_size=16).hexdigest()


def _canonical_signed_fields(envelope: dict) -> dict:
    """Return the exact Beacon v2 body covered by signature verification."""
    return {
        field: value
        for field, value in envelope.items()
        if field not in UNSIGNED_TRANSPORT_FIELDS
    }


def _canonical_signing_payload(envelope: dict) -> bytes:
    """Return the canonical Beacon signing payload."""
    return json.dumps(
        _canonical_signed_fields(envelope),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass
class EnvelopeAttestation:
    """
    A Beacon v2 envelope attesting to a bounty submission.

    Attributes:
        agent_id: Submitter's agent ID
        kind: Always "bounty" for submission attestations
        nonce: Unique nonce (blake2b of submission_id + timestamp)
        bounty_id: The bounty being submitted to
        submission_id: Unique submission identifier
        pr_url: Pull request URL
        summary: Brief description of the work
        timestamp: Unix timestamp of attestation
        pubkey_hex: Hex-encoded Ed25519 public key
        sig_hex: Hex-encoded Ed25519 signature
    """
    agent_id: str
    kind: str = "bounty"
    nonce: str = ""
    bounty_id: str = ""
    submission_id: str = ""
    pr_url: str = ""
    summary: str = ""
    timestamp: int = 0
    pubkey_hex: str = ""
    sig_hex: str = ""

    def to_envelope(self) -> Dict[str, Any]:
        """Return the full Beacon envelope dict (suitable for storage/verification)."""
        return {
            "agent_id": self.agent_id,
            "kind": self.kind,
            "nonce": self.nonce,
            "bounty_id": self.bounty_id,
            "submission_id": self.submission_id,
            "pr_url": self.pr_url,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "pubkey": self.pubkey_hex,
            "sig": self.sig_hex,
        }

    def to_json(self) -> str:
        """Serialize to canonical JSON string."""
        return json.dumps(self.to_envelope(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_envelope(cls, envelope: Dict[str, Any]) -> "EnvelopeAttestation":
        """Deserialize from a Beacon envelope dict."""
        return cls(
            agent_id=envelope.get("agent_id", ""),
            kind=envelope.get("kind", "bounty"),
            nonce=envelope.get("nonce", ""),
            bounty_id=envelope.get("bounty_id", ""),
            submission_id=envelope.get("submission_id", ""),
            pr_url=envelope.get("pr_url", ""),
            summary=envelope.get("summary", ""),
            timestamp=envelope.get("timestamp", 0),
            pubkey_hex=envelope.get("pubkey", ""),
            sig_hex=envelope.get("sig", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "EnvelopeAttestation":
        """Deserialize from canonical JSON string."""
        return cls.from_envelope(json.loads(json_str))


def attest_bounty_submission(
    bounty_id: str,
    submission_id: str,
    submitter_agent_id: str,
    pr_url: str,
    summary: str,
    signing_key_hex: str,
    timestamp: Optional[int] = None,
) -> EnvelopeAttestation:
    """
    Create a Beacon v2 envelope attestation for a bounty submission.

    Args:
        bounty_id: The bounty being submitted to
        submission_id: Unique submission identifier
        submitter_agent_id: Agent ID of the submitter
        pr_url: Pull request URL
        summary: Brief description of the work
        signing_key_hex: Hex-encoded Ed25519 private key for signing
        timestamp: Optional unix timestamp (defaults to now)

    Returns:
        EnvelopeAttestation with signature

    Raises:
        RuntimeError: If PyNaCl is not installed
        ValueError: If signing key is invalid
    """
    if not NACL_AVAILABLE:
        raise RuntimeError(
            "PyNaCl is required to create attestations. "
            "Install with: pip install pynacl"
        )

    ts = timestamp or int(time.time())
    nonce = _generate_nonce(submission_id, ts)

    # Derive pubkey from signing key
    try:
        signing_key = SigningKey(bytes.fromhex(signing_key_hex))
        verify_key = signing_key.verify_key
        pubkey_hex = verify_key.encode().hex()
    except Exception as e:
        raise ValueError(f"Invalid signing key: {e}") from e

    # Build envelope body (fields covered by signature)
    envelope_body = {
        "agent_id": submitter_agent_id,
        "kind": "bounty",
        "nonce": nonce,
        "bounty_id": bounty_id,
        "submission_id": submission_id,
        "pr_url": pr_url,
        "summary": summary,
        "timestamp": ts,
        "pubkey": pubkey_hex,
    }

    # Sign the canonical payload
    payload = _canonical_signing_payload(envelope_body)
    signature = signing_key.sign(payload).signature  # type: ignore[attr-defined]
    sig_hex = signature.hex()

    return EnvelopeAttestation(
        agent_id=submitter_agent_id,
        kind="bounty",
        nonce=nonce,
        bounty_id=bounty_id,
        submission_id=submission_id,
        pr_url=pr_url,
        summary=summary,
        timestamp=ts,
        pubkey_hex=pubkey_hex,
        sig_hex=sig_hex,
    )


def verify_attestation(
    attestation: EnvelopeAttestation,
) -> Tuple[bool, str]:
    """
    Verify an EnvelopeAttestation's Ed25519 signature.

    Args:
        attestation: The attestation to verify

    Returns:
        (valid: bool, reason: str) — reason is empty if valid
    """
    if not attestation.sig_hex:
        return False, "missing_signature"
    if not attestation.pubkey_hex:
        return False, "missing_pubkey"
    if not attestation.agent_id:
        return False, "missing_agent_id"
    if attestation.kind != "bounty":
        return False, f"invalid_kind:{attestation.kind}"

    # Validate pubkey is well-formed hex
    try:
        pubkey_bytes = bytes.fromhex(attestation.pubkey_hex)
    except ValueError:
        return False, "invalid_pubkey_encoding"

    # Reconstruct envelope and verify signature
    envelope = attestation.to_envelope()

    # Try PyNaCl first
    if NACL_AVAILABLE:
        try:
            verify_key = VerifyKey(bytes.fromhex(attestation.pubkey_hex))
            payload = _canonical_signing_payload(envelope)
            verify_key.verify(payload, bytes.fromhex(attestation.sig_hex))
            return True, ""
        except (BadSignatureError, Exception):
            return False, "invalid_signature"
    elif _CRYPTO_AVAILABLE:
        try:
            vk = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            payload = _canonical_signing_payload(envelope)
            vk.verify(bytes.fromhex(attestation.sig_hex), payload)
            return True, ""
        except Exception:
            return False, "invalid_signature"
    else:
        return False, "signature_verification_unavailable"


def verify_attestation_from_envelope(
    envelope: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Verify a raw Beacon envelope dict as an attestation.

    Convenience wrapper that deserializes and verifies in one call.
    """
    try:
        attestation = EnvelopeAttestation.from_envelope(envelope)
        return verify_attestation(attestation)
    except Exception as e:
        return False, f"parse_error:{e}"


def verify_attestation_from_json(json_str: str) -> Tuple[bool, str]:
    """
    Verify a JSON-encoded attestation.

    Convenience wrapper that deserializes and verifies in one call.
    """
    try:
        attestation = EnvelopeAttestation.from_json(json_str)
        return verify_attestation(attestation)
    except Exception as e:
        return False, f"parse_error:{e}"
