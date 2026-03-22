#!/usr/bin/env python3
"""
Ergo Anchor Chain Proof Verifier - Usage Examples
==================================================

This file demonstrates common usage patterns for the anchor verifier.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ergo_anchor_verifier import (
    AnchorProofVerifier,
    AnchorProofGenerator,
    AnchorProof,
    VerificationResult,
    NetworkType,
    CryptoUtils
)


def example_1_basic_verification():
    """Example 1: Basic proof verification."""
    print("=" * 70)
    print("Example 1: Basic Proof Verification")
    print("=" * 70)
    
    # Initialize verifier
    verifier = AnchorProofVerifier(
        network=NetworkType.MAINNET,
        confirmation_depth=6
    )
    
    # Create a sample proof (in practice, load from file)
    proof = AnchorProof(
        tx_id="a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
        block_id="b2c3d4e5f67890123456789012345678901234567890123456789012345678ef",
        block_height=100000,
        rustchain_height=50000,
        rustchain_hash="c3d4e5f6789012345678901234567890123456789012345678901234567890ab",
        state_root="d4e5f67890123456789012345678901234567890123456789012345678901234",
        attestations_root="e5f6789012345678901234567890123456789012345678901234567890123456",
        commitment_hash="f678901234567890123456789012345678901234567890123456789012345678",
        commitment_register="R5",
        commitment_value="0e40f678901234567890123456789012345678901234567890123456789012345678",
        timestamp=1711123456789,
        confirmations=10,
        network="mainnet"
    )
    
    # Verify (will fail without network, but demonstrates the API)
    print(f"Proof TX ID: {proof.tx_id[:16]}...")
    print(f"RustChain Height: {proof.rustchain_height}")
    print(f"Commitment Hash: {proof.commitment_hash[:16]}...")
    print()


def example_2_crypto_utils():
    """Example 2: Using cryptographic utilities."""
    print("=" * 70)
    print("Example 2: Cryptographic Utilities")
    print("=" * 70)
    
    # Compute Blake2b256 hash
    data = b"Hello, Ergo!"
    hash_bytes = CryptoUtils.blake2b256(data)
    hash_hex = CryptoUtils.blake2b256_hex(data)
    
    print(f"Data: {data.decode()}")
    print(f"Hash (bytes): {hash_bytes.hex()[:32]}...")
    print(f"Hash (hex): {hash_hex[:32]}...")
    print()
    
    # Compute commitment hash
    commitment = CryptoUtils.compute_commitment_hash(
        rustchain_height=1000,
        rustchain_hash="abc" + "0" * 61,
        state_root="def" + "0" * 61,
        attestations_root="ghi" + "0" * 61,
        timestamp=1234567890000
    )
    
    print(f"Commitment Hash: {commitment[:32]}...")
    print()
    
    # Validate hex string
    valid_hex = "a" * 64
    invalid_hex = "xyz" + "0" * 61
    
    print(f"Valid hex '{valid_hex[:16]}...': {CryptoUtils.validate_hex_string(valid_hex)}")
    print(f"Invalid hex '{invalid_hex[:16]}...': {CryptoUtils.validate_hex_string(invalid_hex)}")
    print()


def example_3_proof_generation():
    """Example 3: Generating proofs."""
    print("=" * 70)
    print("Example 3: Proof Generation")
    print("=" * 70)
    
    # Create proof generator
    generator = AnchorProofGenerator(network=NetworkType.MAINNET)
    
    print("Proof Generator initialized")
    print(f"Network: {generator.network.value}")
    print()
    
    # In practice, you would call:
    # proof = generator.generate_from_transaction(
    #     tx_id="...",
    #     rustchain_height=50000,
    #     rustchain_hash="...",
    #     state_root="...",
    #     attestations_root="..."
    # )
    print("To generate a proof from a transaction:")
    print("  proof = generator.generate_from_transaction(")
    print("      tx_id='<tx_id>',")
    print("      rustchain_height=50000,")
    print("      rustchain_hash='<hash>',")
    print("      state_root='<root>',")
    print("      attestations_root='<root>'")
    print("  )")
    print()


def example_4_batch_verification():
    """Example 4: Batch verification."""
    print("=" * 70)
    print("Example 4: Batch Verification")
    print("=" * 70)
    
    verifier = AnchorProofVerifier(network=NetworkType.MAINNET)
    
    # Create sample proofs
    proofs = []
    for i in range(3):
        proof = AnchorProof(
            tx_id=f"{'a' * 64}",
            block_id=f"{'b' * 64}",
            block_height=100000 + i,
            rustchain_height=50000 + i,
            rustchain_hash=f"{'c' * 64}",
            state_root=f"{'d' * 64}",
            attestations_root=f"{'e' * 64}",
            commitment_hash=f"{'f' * 64}",
            commitment_register="R5",
            commitment_value="0e40" + "f" * 64,
            timestamp=1711123456789,
            confirmations=10,
            network="mainnet"
        )
        proofs.append(proof)
    
    print(f"Created {len(proofs)} sample proofs")
    print()
    
    # In practice:
    # results = verifier.batch_verify(proofs)
    # valid = sum(1 for r in results if r.is_valid)
    # print(f"Valid: {valid}/{len(proofs)}")
    print("To verify batch:")
    print("  results = verifier.batch_verify(proofs)")
    print("  valid = sum(1 for r in results if r.is_valid)")
    print()


def example_5_audit_report():
    """Example 5: Generating audit reports."""
    print("=" * 70)
    print("Example 5: Audit Report Generation")
    print("=" * 70)
    
    verifier = AnchorProofVerifier(network=NetworkType.MAINNET)
    
    # Create sample results
    proof1 = AnchorProof(
        tx_id="a1" + "0" * 62,
        block_id="b1" + "0" * 62,
        block_height=100000,
        rustchain_height=50000,
        rustchain_hash="c1" + "0" * 62,
        state_root="d1" + "0" * 62,
        attestations_root="e1" + "0" * 62,
        commitment_hash="f1" + "0" * 62,
        commitment_register="R5",
        commitment_value="0e40" + "f1" + "0" * 60,
        timestamp=1711123456789,
        confirmations=10,
        network="mainnet"
    )
    
    results = [
        VerificationResult(
            is_valid=True,
            proof=proof1,
            tx_exists=True,
            tx_confirmed=True,
            commitment_matches=True,
            verification_time_ms=15.5
        ),
        VerificationResult(
            is_valid=False,
            proof=proof1,
            errors=["Transaction not found"],
            verification_time_ms=5.2
        )
    ]
    
    # Generate report
    report = verifier.generate_audit_report(results)
    
    print("Sample Audit Report:")
    print("-" * 70)
    print(report)
    print()


def example_6_json_serialization():
    """Example 6: JSON serialization."""
    print("=" * 70)
    print("Example 6: JSON Serialization")
    print("=" * 70)
    
    # Create proof
    proof = AnchorProof(
        tx_id="a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
        block_id="b2c3d4e5f67890123456789012345678901234567890123456789012345678ef",
        block_height=100000,
        rustchain_height=50000,
        rustchain_hash="c3d4e5f6789012345678901234567890123456789012345678901234567890ab",
        state_root="d4e5f67890123456789012345678901234567890123456789012345678901234",
        attestations_root="e5f6789012345678901234567890123456789012345678901234567890123456",
        commitment_hash="f678901234567890123456789012345678901234567890123456789012345678",
        commitment_register="R5",
        commitment_value="0e40f678901234567890123456789012345678901234567890123456789012345678",
        timestamp=1711123456789,
        confirmations=10,
        network="mainnet"
    )
    
    # Serialize to JSON
    json_str = proof.to_json()
    print(f"Serialized JSON (first 100 chars): {json_str[:100]}...")
    print()
    
    # Deserialize from JSON
    restored = AnchorProof.from_json(json_str)
    print(f"Deserialized TX ID: {restored.tx_id[:16]}...")
    print(f"TX IDs match: {proof.tx_id == restored.tx_id}")
    print()


def main():
    """Run all examples."""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "Ergo Anchor Chain Proof Verifier Examples" + " " * 15 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    example_1_basic_verification()
    example_2_crypto_utils()
    example_3_proof_generation()
    example_4_batch_verification()
    example_5_audit_report()
    example_6_json_serialization()
    
    print("=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
