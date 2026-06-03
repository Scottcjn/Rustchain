# SPDX-License-Identifier: MIT
"""Deterministic data custody challenges for availability validators."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

DEFAULT_SAMPLE_COUNT = 16
DEFAULT_SAMPLE_SIZE = 32
MAX_SAMPLE_COUNT = 256
MAX_SAMPLE_SIZE = 4096


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(data: Dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def _derive_seed(
    piece_id: str,
    piece_size: int,
    epoch: int,
    validator_id: str,
    seed: Optional[str],
) -> bytes:
    if seed:
        return bytes.fromhex(seed) if _looks_like_hex(seed) else seed.encode()

    return _canonical_json({
        "epoch": epoch,
        "piece_id": piece_id,
        "piece_size": piece_size,
        "validator_id": validator_id,
    })


def _looks_like_hex(value: str) -> bool:
    if len(value) % 2:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


def _validate_challenge_params(
    piece_id: str,
    piece_size: int,
    epoch: int,
    validator_id: str,
    sample_count: int,
    sample_size: int,
) -> None:
    if not isinstance(piece_id, str) or not piece_id:
        raise ValueError("piece_id is required")
    if not isinstance(validator_id, str) or not validator_id:
        raise ValueError("validator_id is required")
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
        raise ValueError("epoch must be a non-negative integer")
    if not isinstance(piece_size, int) or isinstance(piece_size, bool) or piece_size <= 0:
        raise ValueError("piece_size must be a positive integer")
    if not isinstance(sample_count, int) or not 1 <= sample_count <= MAX_SAMPLE_COUNT:
        raise ValueError("sample_count out of range")
    if not isinstance(sample_size, int) or not 1 <= sample_size <= MAX_SAMPLE_SIZE:
        raise ValueError("sample_size out of range")
    if sample_size > piece_size:
        raise ValueError("sample_size cannot exceed piece_size")
    distinct_windows = piece_size - sample_size + 1
    if sample_count > distinct_windows:
        raise ValueError("sample_count exceeds distinct sample windows")


@dataclass(frozen=True)
class CustodyChallenge:
    piece_id: str
    piece_size: int
    epoch: int
    validator_id: str
    sample_offsets: List[int]
    sample_size: int = DEFAULT_SAMPLE_SIZE

    @property
    def challenge_hash(self) -> str:
        return _sha256_hex(_canonical_json(self.to_dict(include_hash=False)))

    def to_dict(self, include_hash: bool = True) -> Dict:
        data = {
            "piece_id": self.piece_id,
            "piece_size": self.piece_size,
            "epoch": self.epoch,
            "validator_id": self.validator_id,
            "sample_offsets": list(self.sample_offsets),
            "sample_size": self.sample_size,
        }
        if include_hash:
            data["challenge_hash"] = self.challenge_hash
        return data


@dataclass(frozen=True)
class CustodyProof:
    challenge_hash: str
    piece_id: str
    validator_id: str
    sample_hashes: Dict[str, str]
    piece_hash: Optional[str] = None

    def to_dict(self) -> Dict:
        data = {
            "challenge_hash": self.challenge_hash,
            "piece_id": self.piece_id,
            "validator_id": self.validator_id,
            "sample_hashes": dict(self.sample_hashes),
        }
        if self.piece_hash is not None:
            data["piece_hash"] = self.piece_hash
        return data


@dataclass(frozen=True)
class CustodyVerificationResult:
    valid: bool
    slashable: bool
    reason: str
    checked_samples: int
    failed_offsets: List[int]

    def to_dict(self) -> Dict:
        return {
            "valid": self.valid,
            "slashable": self.slashable,
            "reason": self.reason,
            "checked_samples": self.checked_samples,
            "failed_offsets": list(self.failed_offsets),
        }


def build_custody_challenge(
    piece_id: str,
    piece_size: int,
    epoch: int,
    validator_id: str,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: Optional[str] = None,
) -> CustodyChallenge:
    """Select deterministic sample offsets for a data availability custody check."""
    _validate_challenge_params(
        piece_id=piece_id,
        piece_size=piece_size,
        epoch=epoch,
        validator_id=validator_id,
        sample_count=sample_count,
        sample_size=sample_size,
    )

    max_offset = piece_size - sample_size
    seed_material = _derive_seed(piece_id, piece_size, epoch, validator_id, seed)
    offsets: List[int] = []
    seen_offsets = set()
    counter = 0

    while len(offsets) < sample_count:
        digest = hashlib.sha256(seed_material + counter.to_bytes(8, "big")).digest()
        offset = int.from_bytes(digest[:8], "big") % (max_offset + 1)
        if offset not in seen_offsets:
            offsets.append(offset)
            seen_offsets.add(offset)
        counter += 1

    return CustodyChallenge(
        piece_id=piece_id,
        piece_size=piece_size,
        epoch=epoch,
        validator_id=validator_id,
        sample_offsets=offsets,
        sample_size=sample_size,
    )


def create_custody_proof(data: bytes, challenge: CustodyChallenge) -> CustodyProof:
    """Hash the challenged data samples for a validator custody response."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if len(data) != challenge.piece_size:
        raise ValueError("data length does not match challenge piece_size")

    sample_hashes = {
        str(offset): _sha256_hex(data[offset:offset + challenge.sample_size])
        for offset in challenge.sample_offsets
    }
    return CustodyProof(
        challenge_hash=challenge.challenge_hash,
        piece_id=challenge.piece_id,
        validator_id=challenge.validator_id,
        sample_hashes=sample_hashes,
        piece_hash=_sha256_hex(data),
    )


def verify_custody_proof(
    data: bytes,
    challenge: CustodyChallenge,
    proof: CustodyProof,
) -> CustodyVerificationResult:
    """Verify sampled custody evidence and flag failures as slashable."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if len(data) != challenge.piece_size:
        raise ValueError("data length does not match challenge piece_size")

    if proof.challenge_hash != challenge.challenge_hash:
        return CustodyVerificationResult(
            valid=False,
            slashable=True,
            reason="challenge_hash_mismatch",
            checked_samples=0,
            failed_offsets=[],
        )
    if proof.piece_id != challenge.piece_id:
        return CustodyVerificationResult(
            valid=False,
            slashable=True,
            reason="piece_id_mismatch",
            checked_samples=0,
            failed_offsets=[],
        )
    if proof.validator_id != challenge.validator_id:
        return CustodyVerificationResult(
            valid=False,
            slashable=True,
            reason="validator_id_mismatch",
            checked_samples=0,
            failed_offsets=[],
        )
    if proof.piece_hash is not None:
        expected_piece_hash = _sha256_hex(data)
        if not hmac.compare_digest(proof.piece_hash, expected_piece_hash):
            return CustodyVerificationResult(
                valid=False,
                slashable=True,
                reason="piece_hash_mismatch",
                checked_samples=0,
                failed_offsets=[],
            )

    failed_offsets = []
    for offset in challenge.sample_offsets:
        expected = _sha256_hex(data[offset:offset + challenge.sample_size])
        observed = proof.sample_hashes.get(str(offset))
        if observed is None or not hmac.compare_digest(observed, expected):
            failed_offsets.append(offset)

    if failed_offsets:
        return CustodyVerificationResult(
            valid=False,
            slashable=True,
            reason="sample_hash_mismatch",
            checked_samples=len(challenge.sample_offsets),
            failed_offsets=failed_offsets,
        )

    return CustodyVerificationResult(
        valid=True,
        slashable=False,
        reason="ok",
        checked_samples=len(challenge.sample_offsets),
        failed_offsets=[],
    )
