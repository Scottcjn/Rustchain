# SPDX-License-Identifier: MIT

import hashlib

import pytest

from node.spv_client import BloomFilter, SPVClient, verify_merkle_proof


def _hash_pair(left: str, right: str) -> str:
    return hashlib.sha256(bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def _leaf(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def test_merkle_proof_verifies_transaction_inclusion():
    tx_a = _leaf("tx-a")
    tx_b = _leaf("tx-b")
    tx_c = _leaf("tx-c")
    tx_d = _leaf("tx-d")
    left_root = _hash_pair(tx_a, tx_b)
    right_root = _hash_pair(tx_c, tx_d)
    root = _hash_pair(left_root, right_root)

    proof = [("left", tx_a), ("right", right_root)]

    assert verify_merkle_proof(tx_b, root, proof)
    assert not verify_merkle_proof(_leaf("other-tx"), root, proof)


def test_spv_client_stores_headers_only_and_checks_known_block_proof():
    tx_a = _leaf("tx-a")
    tx_b = _leaf("tx-b")
    merkle_root = _hash_pair(tx_a, tx_b)
    client = SPVClient()

    client.add_headers(
        [
            {
                "height": 0,
                "hash": "0" * 64,
                "prev_hash": None,
                "merkle_root": "0" * 64,
            },
            {
                "height": 1,
                "hash": "1" * 64,
                "prev_hash": "0" * 64,
                "merkle_root": merkle_root,
            },
        ]
    )

    assert client.tip["height"] == 1
    assert client.verify_transaction(tx_b, "1" * 64, [("left", tx_a)])
    assert not client.verify_transaction(tx_b, "2" * 64, [("left", tx_a)])


def test_spv_client_rejects_non_extending_header():
    client = SPVClient()
    client.add_header({"height": 0, "hash": "a" * 64, "merkle_root": "0" * 64})

    with pytest.raises(ValueError, match="does not extend"):
        client.add_header(
            {
                "height": 1,
                "hash": "b" * 64,
                "prev_hash": "c" * 64,
                "merkle_root": "0" * 64,
            }
        )


def test_spv_client_rejects_non_genesis_header_without_previous_hash():
    client = SPVClient()

    with pytest.raises(ValueError, match="previous hash"):
        client.add_header({"height": 5, "hash": "f" * 64, "merkle_root": "0" * 64})


def test_spv_client_rejects_header_without_known_previous_height():
    client = SPVClient()

    with pytest.raises(ValueError, match="does not extend"):
        client.add_header(
            {
                "height": 5,
                "hash": "f" * 64,
                "prev_hash": "e" * 64,
                "merkle_root": "0" * 64,
            }
        )


def test_bloom_filter_matches_watched_items_and_round_trips():
    bloom = BloomFilter(size_bits=256, hash_count=5)
    bloom.add("RTC-wallet-address")
    bloom.add(bytes.fromhex("ab" * 32))

    assert "RTC-wallet-address" in bloom
    assert bytes.fromhex("ab" * 32) in bloom
    assert "definitely-unwatched" not in bloom

    restored = BloomFilter.from_hex(bloom.to_hex(), size_bits=256, hash_count=5)
    assert "RTC-wallet-address" in restored


def test_bloom_filter_rejects_oversized_serialized_bits():
    with pytest.raises(ValueError, match="exceeds configured size"):
        BloomFilter.from_hex("ffff", size_bits=8, hash_count=1)
