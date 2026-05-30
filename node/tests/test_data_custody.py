# SPDX-License-Identifier: MIT

import pytest

from node.data_custody import (
    build_custody_challenge,
    create_custody_proof,
    verify_custody_proof,
)


def test_challenge_offsets_are_deterministic_for_validator_epoch():
    first = build_custody_challenge(
        piece_id="piece-a",
        piece_size=1024,
        epoch=7,
        validator_id="validator-1",
        sample_count=8,
        sample_size=16,
    )
    second = build_custody_challenge(
        piece_id="piece-a",
        piece_size=1024,
        epoch=7,
        validator_id="validator-1",
        sample_count=8,
        sample_size=16,
    )

    assert first.sample_offsets == second.sample_offsets
    assert first.challenge_hash == second.challenge_hash
    assert all(0 <= offset <= 1008 for offset in first.sample_offsets)


def test_valid_custody_proof_verifies_all_challenged_samples():
    data = bytes(range(256)) * 4
    challenge = build_custody_challenge(
        piece_id="piece-a",
        piece_size=len(data),
        epoch=9,
        validator_id="validator-1",
        sample_count=10,
        sample_size=24,
    )
    proof = create_custody_proof(data, challenge)

    result = verify_custody_proof(data, challenge, proof)

    assert result.valid is True
    assert result.slashable is False
    assert result.checked_samples == 10
    assert result.failed_offsets == []


def test_missing_sample_hash_is_slashable_custody_failure():
    data = b"availability-piece" * 64
    challenge = build_custody_challenge(
        piece_id="piece-a",
        piece_size=len(data),
        epoch=11,
        validator_id="validator-1",
        sample_count=6,
        sample_size=32,
    )
    proof = create_custody_proof(data, challenge)
    sample_hashes = proof.to_dict()["sample_hashes"]
    removed_offset = challenge.sample_offsets[0]
    sample_hashes.pop(str(removed_offset))

    incomplete_proof = type(proof)(
        challenge_hash=proof.challenge_hash,
        piece_id=proof.piece_id,
        validator_id=proof.validator_id,
        sample_hashes=sample_hashes,
        piece_hash=proof.piece_hash,
    )

    result = verify_custody_proof(data, challenge, incomplete_proof)

    assert result.valid is False
    assert result.slashable is True
    assert result.reason == "sample_hash_mismatch"
    assert removed_offset in result.failed_offsets


def test_tampered_sample_hash_is_slashable_custody_failure():
    data = b"availability-piece" * 64
    challenge = build_custody_challenge(
        piece_id="piece-a",
        piece_size=len(data),
        epoch=12,
        validator_id="validator-1",
        sample_count=6,
        sample_size=32,
    )
    proof = create_custody_proof(data, challenge)
    sample_hashes = proof.to_dict()["sample_hashes"]
    tampered_offset = challenge.sample_offsets[-1]
    sample_hashes[str(tampered_offset)] = "00" * 32

    tampered_proof = type(proof)(
        challenge_hash=proof.challenge_hash,
        piece_id=proof.piece_id,
        validator_id=proof.validator_id,
        sample_hashes=sample_hashes,
        piece_hash=proof.piece_hash,
    )

    result = verify_custody_proof(data, challenge, tampered_proof)

    assert result.valid is False
    assert result.slashable is True
    assert result.reason == "sample_hash_mismatch"
    assert tampered_offset in result.failed_offsets


def test_challenge_rejects_impossible_sample_size():
    with pytest.raises(ValueError, match="sample_size cannot exceed piece_size"):
        build_custody_challenge(
            piece_id="piece-a",
            piece_size=16,
            epoch=1,
            validator_id="validator-1",
            sample_count=1,
            sample_size=32,
        )
