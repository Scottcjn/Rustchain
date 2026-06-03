# SPDX-License-Identifier: MIT
"""
Lightweight SPV helpers for RustChain clients.

The module keeps the SPV surface intentionally small: clients store block
headers, verify transaction inclusion from Merkle branches, and pre-filter
interesting transaction identifiers before asking a full node for proofs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

HashFn = Callable[[bytes], bytes]
MerkleBranch = Sequence[Tuple[str, str]]


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _coerce_hash(value: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("hash values must be hex encoded") from exc


def _header_height(header: Mapping[str, object]) -> int:
    value = header.get("height", header.get("slot"))
    if not isinstance(value, int):
        raise ValueError("header must include integer height or slot")
    return value


def _header_hash(header: Mapping[str, object]) -> str:
    value = header.get("hash", header.get("block_hash"))
    if not isinstance(value, str) or not value:
        raise ValueError("header must include hash or block_hash")
    return value


def _header_prev_hash(header: Mapping[str, object]) -> Optional[str]:
    value = header.get("prev_hash", header.get("previous_hash"))
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("previous hash must be a string")
    return value


def verify_merkle_proof(
    tx_hash: str,
    merkle_root: str,
    branch: MerkleBranch,
    hash_fn: HashFn = _sha256,
) -> bool:
    """
    Verify that ``tx_hash`` is included in ``merkle_root``.

    Branch entries are ``(side, sibling_hash)`` tuples where ``side`` is
    ``"left"`` when the sibling is left of the current hash and ``"right"``
    when the sibling is right of it.
    """
    current = _coerce_hash(tx_hash)
    expected_root = _coerce_hash(merkle_root)

    for side, sibling_hash in branch:
        sibling = _coerce_hash(sibling_hash)
        if side == "left":
            current = hash_fn(sibling + current)
        elif side == "right":
            current = hash_fn(current + sibling)
        else:
            raise ValueError("proof side must be 'left' or 'right'")

    return current == expected_root


@dataclass
class BloomFilter:
    """
    Compact probabilistic filter for transaction IDs or addresses.

    The filter uses double hashing to derive ``hash_count`` bit positions from
    SHA-256 and BLAKE2b. It is deterministic and dependency-free so mobile,
    IoT, and test clients can use it without a full node stack.
    """

    size_bits: int = 2048
    hash_count: int = 7
    _bits: int = 0

    def __post_init__(self) -> None:
        if self.size_bits <= 0:
            raise ValueError("size_bits must be positive")
        if self.hash_count <= 0:
            raise ValueError("hash_count must be positive")

    def _positions(self, item: bytes) -> Iterable[int]:
        h1 = int.from_bytes(hashlib.sha256(item).digest(), "big")
        h2 = int.from_bytes(hashlib.blake2b(item, digest_size=32).digest(), "big")
        for index in range(self.hash_count):
            yield (h1 + index * h2) % self.size_bits

    def add(self, item: str | bytes) -> None:
        data = item if isinstance(item, bytes) else item.encode("utf-8")
        for position in self._positions(data):
            self._bits |= 1 << position

    def __contains__(self, item: str | bytes) -> bool:
        data = item if isinstance(item, bytes) else item.encode("utf-8")
        return all(self._bits & (1 << position) for position in self._positions(data))

    def to_hex(self) -> str:
        byte_length = (self.size_bits + 7) // 8
        return self._bits.to_bytes(byte_length, "big").hex()

    @classmethod
    def from_hex(cls, value: str, size_bits: int = 2048, hash_count: int = 7) -> "BloomFilter":
        bloom = cls(size_bits=size_bits, hash_count=hash_count)
        bits = int.from_bytes(bytes.fromhex(value), "big")
        if bits.bit_length() > bloom.size_bits:
            raise ValueError("serialized bloom filter exceeds configured size")
        bloom._bits = bits
        return bloom


@dataclass
class SPVClient:
    """
    Header-only SPV state with transaction inclusion checks.

    A full node still supplies headers and Merkle proofs; this client validates
    the small proof material locally and does not require block bodies.
    """

    bloom_filter: BloomFilter = field(default_factory=BloomFilter)
    headers_by_height: Dict[int, Mapping[str, object]] = field(default_factory=dict)
    headers_by_hash: Dict[str, Mapping[str, object]] = field(default_factory=dict)

    def add_header(self, header: Mapping[str, object]) -> None:
        height = _header_height(header)
        block_hash = _header_hash(header)
        prev_hash = _header_prev_hash(header)

        if height > 0:
            if not prev_hash:
                raise ValueError("non-genesis header must include previous hash")
            previous = self.headers_by_height.get(height - 1)
            if previous is None or _header_hash(previous) != prev_hash:
                raise ValueError("header does not extend the known chain")

        self.headers_by_height[height] = dict(header)
        self.headers_by_hash[block_hash] = dict(header)

    def add_headers(self, headers: Iterable[Mapping[str, object]]) -> None:
        for header in sorted(headers, key=_header_height):
            self.add_header(header)

    @property
    def tip(self) -> Optional[Mapping[str, object]]:
        if not self.headers_by_height:
            return None
        return self.headers_by_height[max(self.headers_by_height)]

    def watch(self, item: str | bytes) -> None:
        self.bloom_filter.add(item)

    def wants_transaction(self, tx_id: str) -> bool:
        return tx_id in self.bloom_filter

    def verify_transaction(
        self,
        tx_hash: str,
        block_hash: str,
        proof: MerkleBranch,
        hash_fn: HashFn = _sha256,
    ) -> bool:
        header = self.headers_by_hash.get(block_hash)
        if header is None:
            return False
        merkle_root = header.get("merkle_root")
        if not isinstance(merkle_root, str):
            return False
        return verify_merkle_proof(tx_hash, merkle_root, proof, hash_fn=hash_fn)
