# SPDX-License-Identifier: MIT
"""Chain-bound randomness beacon helpers for RustChain blocks."""

import json
from hashlib import blake2b
from typing import Dict

GENESIS_RANDOMNESS = "0" * 64
RANDOMNESS_DOMAIN = "rustchain:onchain-randomness:v1"


def _canonical_json(data: Dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_randomness_proof(
    *,
    height: int,
    block_hash: str,
    prev_hash: str,
    prev_randomness: str = GENESIS_RANDOMNESS,
    merkle_root: str = "",
    attestations_hash: str = "",
    producer: str = "",
    timestamp: int = 0,
) -> Dict:
    """Return the canonical public proof inputs for a block randomness value."""
    return {
        "domain": RANDOMNESS_DOMAIN,
        "height": int(height),
        "block_hash": str(block_hash),
        "prev_hash": str(prev_hash),
        "prev_randomness": str(prev_randomness or GENESIS_RANDOMNESS),
        "merkle_root": str(merkle_root),
        "attestations_hash": str(attestations_hash),
        "producer": str(producer),
        "timestamp": int(timestamp),
    }


def derive_randomness(proof: Dict) -> str:
    """Derive the beacon value from canonical proof material."""
    return blake2b(_canonical_json(proof), digest_size=32).hexdigest()


def build_randomness_record(
    *,
    height: int,
    block_hash: str,
    prev_hash: str,
    prev_randomness: str = GENESIS_RANDOMNESS,
    merkle_root: str = "",
    attestations_hash: str = "",
    producer: str = "",
    timestamp: int = 0,
) -> Dict:
    """Build the stored randomness beacon record for one committed block."""
    proof = build_randomness_proof(
        height=height,
        block_hash=block_hash,
        prev_hash=prev_hash,
        prev_randomness=prev_randomness,
        merkle_root=merkle_root,
        attestations_hash=attestations_hash,
        producer=producer,
        timestamp=timestamp,
    )
    return {
        "randomness": derive_randomness(proof),
        "proof": proof,
    }


def verify_randomness_record(randomness: str, proof: Dict) -> bool:
    """Verify a stored beacon value against its public proof material."""
    return str(randomness) == derive_randomness(proof)
