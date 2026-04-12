"""
AgentFolio ↔ Beacon Integration

Unified agent profiles, Beacon bridge adapter, and envelope attestation
for bounty submissions.

See docs/SPEC.md for the full specification.
"""

from agentfolio_beacon.folio import AgentFolio, assemble_folio, folio_diff, folios_to_table
from agentfolio_beacon.bridge import BeaconBridge
from agentfolio_beacon.attestation import (
    EnvelopeAttestation,
    attest_bounty_submission,
    verify_attestation,
    verify_attestation_from_envelope,
    verify_attestation_from_json,
)

__version__ = "0.1.0"
__all__ = [
    "AgentFolio",
    "assemble_folio",
    "folio_diff",
    "folios_to_table",
    "BeaconBridge",
    "EnvelopeAttestation",
    "attest_bounty_submission",
    "verify_attestation",
    "verify_attestation_from_envelope",
    "verify_attestation_from_json",
]
