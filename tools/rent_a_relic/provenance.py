"""
provenance.py -- Ed25519-signed provenance receipts for Rent-a-Relic sessions.

A receipt is a tamper-evident attestation that a specific vintage machine
hosted a specific agent session for a specific duration.  The receipt is
signed by the machine's Ed25519 key so any third party can verify it with
only the public key (stored in the machine's on-chain passport).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidSignature

if TYPE_CHECKING:
    from tools.rent_a_relic.models import Machine, Reservation, Receipt


def _canonical_payload(
    machine_passport_id: str,
    session_id: str,
    agent_id: str,
    duration_hours: int,
    output_hash: str,
    attestation_proof: str,
    timestamp: float,
) -> bytes:
    """Build a deterministic, UTF-8 encoded JSON payload for signing."""
    payload = {
        "attestation_proof":   attestation_proof,
        "agent_id":            agent_id,
        "duration_hours":      duration_hours,
        "machine_passport_id": machine_passport_id,
        "output_hash":         output_hash,
        "session_id":          session_id,
        "timestamp":           timestamp,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _build_attestation_proof(machine_id: str, session_id: str, agent_id: str) -> str:
    """Derive an attestation proof digest (SHA-256 stub)."""
    raw = f"{machine_id}:{session_id}:{agent_id}".encode()
    return hashlib.sha256(raw).hexdigest()


def generate_receipt(machine: "Machine", reservation: "Reservation") -> "Receipt":
    """Create and sign a provenance receipt for a reservation."""
    from tools.rent_a_relic.models import Receipt

    timestamp         = time.time()
    passport_id       = machine.passport_id()
    attestation_proof = _build_attestation_proof(
        machine.machine_id, reservation.session_id, reservation.agent_id
    )
    output_hash = reservation.output_hash or hashlib.sha256(
        reservation.session_id.encode()
    ).hexdigest()

    payload = _canonical_payload(
        machine_passport_id=passport_id,
        session_id=reservation.session_id,
        agent_id=reservation.agent_id,
        duration_hours=reservation.duration_hours,
        output_hash=output_hash,
        attestation_proof=attestation_proof,
        timestamp=timestamp,
    )

    raw_sig           = machine.sign(payload)
    ed25519_signature = raw_sig.hex()

    return Receipt(
        receipt_id=str(uuid.uuid4()),
        session_id=reservation.session_id,
        machine_passport_id=passport_id,
        agent_id=reservation.agent_id,
        machine_id=machine.machine_id,
        duration_hours=reservation.duration_hours,
        output_hash=output_hash,
        attestation_proof=attestation_proof,
        ed25519_signature=ed25519_signature,
        public_key_hex=machine.public_key_hex(),
        timestamp=timestamp,
    )


def verify_receipt(receipt: "Receipt") -> bool:
    """Verify the Ed25519 signature on a receipt. Returns True if valid."""
    try:
        pub_bytes = bytes.fromhex(receipt.public_key_hex)
        pub_key   = Ed25519PublicKey.from_public_bytes(pub_bytes)

        payload = _canonical_payload(
            machine_passport_id=receipt.machine_passport_id,
            session_id=receipt.session_id,
            agent_id=receipt.agent_id,
            duration_hours=receipt.duration_hours,
            output_hash=receipt.output_hash,
            attestation_proof=receipt.attestation_proof,
            timestamp=receipt.timestamp,
        )

        sig = bytes.fromhex(receipt.ed25519_signature)
        pub_key.verify(sig, payload)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False
