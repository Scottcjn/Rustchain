"""
Demo: AgentFolio ↔ Beacon Integration

End-to-end demonstration using mocked data to show:
1. Assembling an AgentFolio from Beacon + Economy sources
2. Creating and verifying a bounty submission attestation

Run with: python examples/demo_folio.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import MagicMock

from agentfolio_beacon.folio import AgentFolio, assemble_folio
from agentfolio_beacon.bridge import BeaconBridge
from agentfolio_beacon.attestation import (
    EnvelopeAttestation,
    verify_attestation,
    NACL_AVAILABLE,
)


def demo_folio_assembly():
    """Demonstrate assembling an AgentFolio from mocked data."""
    print("=" * 60)
    print("Demo: AgentFolio Assembly")
    print("=" * 60)

    # --- Mock Agent Economy Client ---
    economy_client = MagicMock()

    mock_wallet = MagicMock()
    mock_wallet.wallet_address = "agent_7f3a2b1c"
    mock_wallet.base_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD38"
    economy_client.agents.get_wallet.return_value = mock_wallet

    mock_rep = MagicMock()
    mock_rep.score = 87.5
    economy_client.reputation.get_score.return_value = mock_rep

    economy_client.bounties.get_my_claims.return_value = [
        {"bounty_id": "bounty_101"},
    ]

    # --- Mock Beacon Bridge ---
    beacon_bridge = MagicMock()
    beacon_bridge.lookup_agent_everything.return_value = {
        "relay_agent": {
            "agent_id": "content-curator-bot",
            "pubkey_hex": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "name": "Content Curator Bot",
            "status": "active",
            "coinbase_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD38",
            "created_at": 1712500000,
        },
        "reputation": {
            "agent_id": "content-curator-bot",
            "score": 78,
            "bounties_completed": 12,
            "contracts_completed": 5,
            "contracts_breached": 0,
        },
        "active_contracts": 2,
        "total_contracts": 7,
        "envelopes_recent": 45,
    }

    # --- Assemble ---
    folio = assemble_folio("content-curator-bot", economy_client, beacon_bridge)

    print(f"\n  Agent ID:        {folio.agent_id}")
    print(f"  Beacon Pubkey:   {folio.beacon_pubkey_hex[:20]}...")
    print(f"  Wallet Address:  {folio.wallet_address}")
    print(f"  Base Address:    {folio.base_address}")
    print()
    print(f"  Beacon Score:    {folio.beacon_score}")
    print(f"  Economy Score:   {folio.economy_score}")
    print(f"  Combined Score:  {folio.combined_reputation_score}")
    print()
    print(f"  Beacons Sent:    {folio.total_envelopes_sent}")
    print(f"  Active Contracts: {folio.active_contracts}")
    print(f"  Open Claims:     {folio.open_claims}")
    print(f"  Beacon Bounties: {folio.beacon_bounties_completed}")
    print()
    print(f"  Summary: {folio.summary()}")
    print()

    return folio


def demo_attestation():
    """Demonstrate creating and verifying a bounty submission attestation."""
    print("=" * 60)
    print("Demo: Bounty Submission Attestation")
    print("=" * 60)

    if not NACL_AVAILABLE:
        print("\n  ⚠ PyNaCl not installed — skipping attestation creation.")
        print("  Install with: pip install pynacl")
        print("\n  Verification-only mode still works without PyNaCl.")
        return

    from nacl.signing import SigningKey
    from agentfolio_beacon.attestation import attest_bounty_submission

    # Generate a demo keypair
    signing_key = SigningKey.generate()
    signing_key_hex = signing_key.encode().hex()

    print(f"\n  Signing Key:     {signing_key_hex[:32]}...")
    print(f"  Verify Key:      {signing_key.verify_key.encode().hex()[:32]}...")

    # Create attestation
    attestation = attest_bounty_submission(
        bounty_id="bounty_2890",
        submission_id="sub_demo_001",
        submitter_agent_id="content-curator-bot",
        pr_url="https://github.com/Scottcjn/Rustchain/pull/2890",
        summary="Implemented AgentFolio ↔ Beacon Integration with tests",
        signing_key_hex=signing_key_hex,
    )

    print(f"\n  Attestation created:")
    print(f"    Bounty:        {attestation.bounty_id}")
    print(f"    Submission:    {attestation.submission_id}")
    print(f"    Agent:         {attestation.agent_id}")
    print(f"    PR:            {attestation.pr_url}")
    print(f"    Nonce:         {attestation.nonce}")
    print(f"    Signature:     {attestation.sig_hex[:32]}...")

    # Verify
    valid, reason = verify_attestation(attestation)
    print(f"\n  Verification:    {'✅ VALID' if valid else '❌ INVALID'}")
    if reason:
        print(f"    Reason: {reason}")

    # Show envelope JSON
    print(f"\n  Envelope JSON (first 200 chars):")
    json_str = attestation.to_json()
    print(f"    {json_str[:200]}...")

    # Demonstrate tamper detection
    print(f"\n  Tamper detection demo:")
    tampered = EnvelopeAttestation.from_json(json_str)
    tampered.summary = "TAMPERED: different summary"
    valid_tampered, reason_tampered = verify_attestation(tampered)
    print(f"    After tamper:  {'✅ VALID' if valid_tampered else '❌ INVALID'}")
    if reason_tampered:
        print(f"    Reason: {reason_tampered}")


def demo_folio_diff():
    """Demonstrate folio difference detection."""
    print("\n" + "=" * 60)
    print("Demo: Folio Change Detection")
    print("=" * 60)

    from agentfolio_beacon.folio import folio_diff

    old_folio = AgentFolio(
        agent_id="content-curator-bot",
        beacon_score=75,
        total_envelopes_sent=40,
        active_contracts=1,
    )

    new_folio = AgentFolio(
        agent_id="content-curator-bot",
        beacon_score=80,
        total_envelopes_sent=45,
        active_contracts=2,
    )

    changes = folio_diff(old_folio, new_folio)

    print(f"\n  Changes detected:")
    for field, (old_val, new_val) in changes.items():
        print(f"    {field}: {old_val} → {new_val}")


if __name__ == "__main__":
    demo_folio_assembly()
    demo_attestation()
    demo_folio_diff()
    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)
