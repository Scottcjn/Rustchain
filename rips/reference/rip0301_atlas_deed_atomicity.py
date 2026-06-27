#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reference model for RIP-0301 Atlas deed atomicity.

This module is intentionally small and chain-agnostic. It models the invariant
from RIP-0301 Phase 2 question 5: Atlas deed ownership may change only after a
settled RTC transfer is observed consistently by the node, BoTTube, and
Sophiacord surfaces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping


REQUIRED_SURFACES = ("node", "bottube", "sophiacord")
SETTLEMENT_ASSET = "RTC"


class DeedAtomicityError(ValueError):
    """Raised when an Atlas deed transfer would violate RIP-0301 atomicity."""


@dataclass(frozen=True)
class SurfaceReceipt:
    """One surface's view of a settled Atlas deed transfer."""

    surface: str
    parcel_id: str
    seller: str
    buyer: str
    settlement_asset: str
    settlement_tx_id: str
    settled: bool


@dataclass(frozen=True)
class AtlasDeedTransfer:
    """Canonical event applied by every consumer after all receipts agree."""

    event_id: str
    parcel_id: str
    previous_owner: str
    new_owner: str
    price_micrortc: int
    settlement_tx_id: str
    surfaces: tuple[str, ...]


def build_atlas_deed_transfer(
    *,
    parcel_id: str,
    seller: str,
    buyer: str,
    price_micrortc: int,
    settlement_tx_id: str,
    receipts: Iterable[SurfaceReceipt],
) -> AtlasDeedTransfer:
    """Build a canonical deed transfer only when every surface agrees.

    The returned event is deterministic and can be replayed by node or UI
    consumers without trusting whichever surface observed the transfer first.
    """

    if not parcel_id:
        raise DeedAtomicityError("parcel_id is required")
    if not seller or not buyer:
        raise DeedAtomicityError("seller and buyer are required")
    if seller == buyer:
        raise DeedAtomicityError("self-transfer is not an Atlas deed sale")
    if price_micrortc <= 0:
        raise DeedAtomicityError("Atlas deed transfer requires positive RTC")
    if not settlement_tx_id:
        raise DeedAtomicityError("settlement_tx_id is required")

    receipt_by_surface: dict[str, SurfaceReceipt] = {}
    for receipt in receipts:
        if receipt.surface in receipt_by_surface:
            raise DeedAtomicityError(f"duplicate receipt for {receipt.surface}")
        receipt_by_surface[receipt.surface] = receipt

    required = set(REQUIRED_SURFACES)
    observed = set(receipt_by_surface)
    if observed != required:
        missing = sorted(required - observed)
        extra = sorted(observed - required)
        raise DeedAtomicityError(
            f"surface quorum mismatch; missing={missing}, extra={extra}"
        )

    for receipt in receipt_by_surface.values():
        _validate_surface_receipt(
            receipt,
            parcel_id=parcel_id,
            seller=seller,
            buyer=buyer,
            settlement_tx_id=settlement_tx_id,
        )

    surfaces = tuple(sorted(receipt_by_surface))
    event_payload = {
        "rip": "0301",
        "event": "atlas_deed_transfer",
        "parcel_id": parcel_id,
        "previous_owner": seller,
        "new_owner": buyer,
        "price_micrortc": price_micrortc,
        "settlement_tx_id": settlement_tx_id,
        "surfaces": surfaces,
    }
    event_id = _stable_hash(event_payload)
    return AtlasDeedTransfer(
        event_id=event_id,
        parcel_id=parcel_id,
        previous_owner=seller,
        new_owner=buyer,
        price_micrortc=price_micrortc,
        settlement_tx_id=settlement_tx_id,
        surfaces=surfaces,
    )


def apply_deed_transfer(
    current_owners: Mapping[str, str],
    transfer: AtlasDeedTransfer,
) -> dict[str, str]:
    """Return the post-transfer owner map, preserving all-or-nothing semantics."""

    current_owner = current_owners.get(transfer.parcel_id)
    if current_owner != transfer.previous_owner:
        raise DeedAtomicityError(
            f"parcel {transfer.parcel_id} is owned by {current_owner!r}, "
            f"not {transfer.previous_owner!r}"
        )

    updated = dict(current_owners)
    updated[transfer.parcel_id] = transfer.new_owner
    return updated


def _validate_surface_receipt(
    receipt: SurfaceReceipt,
    *,
    parcel_id: str,
    seller: str,
    buyer: str,
    settlement_tx_id: str,
) -> None:
    if not receipt.settled:
        raise DeedAtomicityError(f"{receipt.surface} has not observed settlement")
    if receipt.settlement_asset != SETTLEMENT_ASSET:
        raise DeedAtomicityError(
            f"{receipt.surface} observed {receipt.settlement_asset}, not RTC"
        )
    expected = {
        "parcel_id": parcel_id,
        "seller": seller,
        "buyer": buyer,
        "settlement_tx_id": settlement_tx_id,
    }
    actual = {
        "parcel_id": receipt.parcel_id,
        "seller": receipt.seller,
        "buyer": receipt.buyer,
        "settlement_tx_id": receipt.settlement_tx_id,
    }
    if actual != expected:
        raise DeedAtomicityError(
            f"{receipt.surface} receipt conflicts with canonical transfer"
        )


def _stable_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()

