#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-202 — B0 block-format canonical contract (PURE, dormant).

B0 widens each committed block attestation from the current
``{miner, arch, family, timestamp}`` (insufficient to re-derive the anti-VM
weight) to carry the full ``device`` + ``fingerprint`` + ``fingerprint_passed``
that ``derive_verified_device`` consumes (RIP-202 operator decision D3 =
commit full raw evidence for fully trustless re-derivation), and commits the
``slot`` so a block's epoch is a deterministic function of *chain* data rather
than wall-clock (``current_slot()`` reads ``time.time()`` and is unsafe on
replay — found in B2 grounding).

This module is the PURE, side-effect-free canonical contract: the record shape,
the deterministic attestations hash over the widened records, and the
slot→epoch map. It is NOT wired into ``produce_block`` / ``_apply_blocks`` — that
wiring is the gated hard fork (ships dormant; byte-identical pre-activation).

Consensus-determinism guarantees (the reasons this is its own pinned module):
  * TOTAL ORDER for hashing — (miner, timestamp, content-digest) — so two
    attestations from the same miner cannot reorder by input order and diverge
    the hash across nodes (the live ``compute_attestations_hash`` sorts by miner
    ONLY; B0 tightens this).
  * CANONICAL JSON — sort_keys, tight separators, and ``allow_nan=False``.
    CPython's float ``repr`` is platform-independent (short-repr/David Gay
    dtoa), so a committed IEEE-754 double hashes identically on big-endian
    PowerPC and x86. Non-finite floats (NaN/Inf) are NOT valid consensus data
    and are rejected at build time (fail closed) rather than serialised to the
    invalid, non-round-tripping ``NaN`` token.
  * FROZEN ON FIRST USE — the field set, encoding, and ``BLOCK_VERSION`` become
    an immutable consensus contract once any block is produced under B0; change
    them only behind the on-chain activation height (PREREQ-A).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Mapping

# Block-format version stamped in the header once B0 is active. produce_block
# sets header.version = B0_BLOCK_VERSION at/after the activation epoch; older
# blocks keep version=1 and validate under the legacy hash, so replay of
# pre-activation history is byte-identical (no retroactive fork).
B0_BLOCK_VERSION = 2

# Must match the node's epoch length (BLOCKS_PER_EPOCH). Kept here as the
# canonical divisor for the slot→epoch map; the wiring step asserts equality
# with the node constant at import.
BLOCKS_PER_EPOCH = 144

# The exact committed fields, in the canonical record. Pinned: adding/removing
# a field is a consensus change gated by activation.
B0_ATTESTATION_FIELDS = ("miner", "device", "fingerprint", "fingerprint_passed", "timestamp")


class B0FormatError(ValueError):
    """Raised when an attestation cannot be canonicalised into a B0 record."""


def _assert_canonical_safe(obj: Any, path: str = "") -> None:
    """Recursively reject anything that is not canonical-JSON-safe + round-trip
    stable, so a record can never explode at hash/serialise time two hops away
    or mutate on a deserialise round-trip (which would diverge the consensus hash):

      * non-finite floats (NaN/+-Inf) — no valid JSON token, don't round-trip;
      * non-string mapping keys — ``sort_keys=True`` raises on mixed-type keys,
        and ``1`` vs ``"1"`` serialise ambiguously;
      * tuples/sets/bytes/custom objects — a tuple becomes a list on reload, so
        it would hash differently after a commit→deserialise round-trip.

    Allowed leaves: str, bool, int, finite float, None. Allowed containers:
    dict (str keys) and list.
    """
    if obj is None or isinstance(obj, (bool, int, str)):
        return  # bool is an int subclass; both are JSON-safe scalars
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise B0FormatError(f"non-finite float at {path or '<root>'}")
        return
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise B0FormatError(f"non-string mapping key {k!r} at {path or '<root>'}")
            _assert_canonical_safe(v, f"{path}.{k}")
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_canonical_safe(v, f"{path}[{i}]")
        return
    raise B0FormatError(f"non-JSON-safe {type(obj).__name__} at {path or '<root>'}")


def build_b0_attestation(
    miner: str,
    device: Mapping,
    fingerprint: Mapping,
    fingerprint_passed: bool,
    timestamp: int,
) -> Dict[str, Any]:
    """Construct one canonical B0 committed-attestation record (validated).

    Fail closed: a non-str/empty miner, non-dict device/fingerprint, non-bool
    pass flag, non-int timestamp, or any non-finite float raises B0FormatError
    so a malformed attestation never enters a block (and thus the hash).
    """
    if not isinstance(miner, str) or not miner:
        raise B0FormatError("miner must be a non-empty str")
    if not isinstance(device, Mapping):
        raise B0FormatError("device must be a dict")
    if not isinstance(fingerprint, Mapping):
        raise B0FormatError("fingerprint must be a dict")
    if not isinstance(fingerprint_passed, bool):
        raise B0FormatError("fingerprint_passed must be a bool")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise B0FormatError("timestamp must be an int")
    device = dict(device)
    fingerprint = dict(fingerprint)
    _assert_canonical_safe(device, "device")
    _assert_canonical_safe(fingerprint, "fingerprint")
    return {
        "miner": miner,
        "device": device,
        "fingerprint": fingerprint,
        "fingerprint_passed": fingerprint_passed,
        "timestamp": timestamp,
    }


def _canonical_bytes(obj: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, tight separators, no non-finite floats."""
    return json.dumps(
        obj, separators=(",", ":"), sort_keys=True, allow_nan=False
    ).encode("utf-8")


def _attestation_digest(att: Mapping) -> str:
    """Deterministic content digest of a B0 record (hash-order tiebreaker)."""
    projected = {k: att.get(k) for k in B0_ATTESTATION_FIELDS}
    return hashlib.sha256(_canonical_bytes(projected)).hexdigest()


def canonical_b0_attestations_hash(attestations: List[Mapping]) -> str:
    """Deterministic blake2b-256 over the B0 attestation set.

    TOTAL ORDER (miner, timestamp, content-digest) so the hash is independent of
    input order and stable for same-(miner,timestamp) records. Empty set hashes
    to the all-zero sentinel, matching the legacy ``compute_attestations_hash``.
    """
    if not attestations:
        return "0" * 64
    # Defense-in-depth: re-validate EVERY record through build_b0_attestation
    # (raises B0FormatError on malformed/missing/non-JSON-safe) so an
    # incomplete record can never enter the consensus hash as null-filled, and
    # a malformed one can never crash serialisation mid-block. The result is
    # exactly the pinned fields, so incidental extra keys can't perturb the hash.
    validated = [
        build_b0_attestation(
            a.get("miner"), a.get("device"), a.get("fingerprint"),
            a.get("fingerprint_passed"), a.get("timestamp"),
        )
        for a in attestations
    ]
    ordered = sorted(
        validated,
        key=lambda a: (a["miner"], a["timestamp"], _attestation_digest(a)),
    )
    return hashlib.blake2b(_canonical_bytes(ordered), digest_size=32).hexdigest()


def slot_to_epoch(slot: int, blocks_per_epoch: int = BLOCKS_PER_EPOCH) -> int:
    """Deterministic epoch for a committed slot. Pure; no wall-clock."""
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
        raise B0FormatError("slot must be a non-negative int")
    if isinstance(blocks_per_epoch, bool) or not isinstance(blocks_per_epoch, int) or blocks_per_epoch < 1:
        raise B0FormatError("blocks_per_epoch must be a positive int")
    return slot // blocks_per_epoch


def block_epoch(header: Mapping, blocks_per_epoch: int = BLOCKS_PER_EPOCH) -> int:
    """Epoch of a block from its committed ``slot`` header field (B0 adds it).

    Fail closed: a header lacking a valid committed slot raises, rather than
    silently falling back to wall-clock (which would diverge on replay).
    """
    slot = header.get("slot")
    if isinstance(slot, bool) or not isinstance(slot, int):
        raise B0FormatError("header missing committed integer 'slot' (B0)")
    return slot_to_epoch(slot, blocks_per_epoch)


def assert_blocks_per_epoch(node_blocks_per_epoch: int) -> None:
    """Fail fast if this module's pinned BLOCKS_PER_EPOCH diverges from the node's.

    The wiring step (B0-wire) MUST call this once at import against the node's
    authoritative constant. Backs the module-header contract with a real guard,
    so the pinned 144 can never silently become a second source of truth — a
    mismatch would diverge every epoch computation (eligibility, governance
    activation, B1 weight) from the live chain.
    """
    if node_blocks_per_epoch != BLOCKS_PER_EPOCH:
        raise B0FormatError(
            f"BLOCKS_PER_EPOCH mismatch: module pins {BLOCKS_PER_EPOCH}, "
            f"node uses {node_blocks_per_epoch} — wiring must reconcile before activation"
        )
