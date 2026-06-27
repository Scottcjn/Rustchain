#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reference tests for RIP-0301 Atlas deed atomicity."""

import unittest

from rips.reference.rip0301_atlas_deed_atomicity import (
    DeedAtomicityError,
    SurfaceReceipt,
    apply_deed_transfer,
    build_atlas_deed_transfer,
)


def _receipts(**overrides):
    base = {
        "parcel_id": "atlas:bayou:00047",
        "seller": "beacon:alice",
        "buyer": "beacon:bob",
        "settlement_asset": "RTC",
        "settlement_tx_id": "rtc-tx-0301-atomic",
        "settled": True,
    }
    base.update(overrides)
    return [
        SurfaceReceipt(surface="node", **base),
        SurfaceReceipt(surface="bottube", **base),
        SurfaceReceipt(surface="sophiacord", **base),
    ]


class TestRip0301AtlasDeedAtomicity(unittest.TestCase):
    def test_settled_rtc_quorum_yields_deterministic_deed_event(self):
        kwargs = {
            "parcel_id": "atlas:bayou:00047",
            "seller": "beacon:alice",
            "buyer": "beacon:bob",
            "price_micrortc": 1_500_000,
            "settlement_tx_id": "rtc-tx-0301-atomic",
        }
        transfer = build_atlas_deed_transfer(receipts=_receipts(), **kwargs)
        transfer_reordered = build_atlas_deed_transfer(
            receipts=reversed(_receipts()), **kwargs
        )

        self.assertEqual(transfer.event_id, transfer_reordered.event_id)
        self.assertEqual(transfer.surfaces, ("bottube", "node", "sophiacord"))

        owners = {"atlas:bayou:00047": "beacon:alice"}
        self.assertEqual(
            apply_deed_transfer(owners, transfer),
            {"atlas:bayou:00047": "beacon:bob"},
        )
        self.assertEqual(owners, {"atlas:bayou:00047": "beacon:alice"})

    def test_tip_credit_receipt_cannot_move_atlas_land(self):
        with self.assertRaisesRegex(DeedAtomicityError, "not RTC"):
            build_atlas_deed_transfer(
                parcel_id="atlas:bayou:00047",
                seller="beacon:alice",
                buyer="beacon:bob",
                price_micrortc=1_500_000,
                settlement_tx_id="rtc-tx-0301-atomic",
                receipts=_receipts(settlement_asset="TIP_CREDIT"),
            )

    def test_split_brain_surface_receipt_is_rejected(self):
        receipts = _receipts()
        receipts[1] = SurfaceReceipt(
            surface="bottube",
            parcel_id="atlas:bayou:00047",
            seller="beacon:alice",
            buyer="beacon:mallory",
            settlement_asset="RTC",
            settlement_tx_id="rtc-tx-0301-atomic",
            settled=True,
        )

        with self.assertRaisesRegex(DeedAtomicityError, "conflicts"):
            build_atlas_deed_transfer(
                parcel_id="atlas:bayou:00047",
                seller="beacon:alice",
                buyer="beacon:bob",
                price_micrortc=1_500_000,
                settlement_tx_id="rtc-tx-0301-atomic",
                receipts=receipts,
            )

    def test_partial_surface_update_is_not_atomic(self):
        with self.assertRaisesRegex(DeedAtomicityError, "surface quorum mismatch"):
            build_atlas_deed_transfer(
                parcel_id="atlas:bayou:00047",
                seller="beacon:alice",
                buyer="beacon:bob",
                price_micrortc=1_500_000,
                settlement_tx_id="rtc-tx-0301-atomic",
                receipts=_receipts()[:2],
            )

    def test_owner_mismatch_preserves_current_state(self):
        transfer = build_atlas_deed_transfer(
            parcel_id="atlas:bayou:00047",
            seller="beacon:alice",
            buyer="beacon:bob",
            price_micrortc=1_500_000,
            settlement_tx_id="rtc-tx-0301-atomic",
            receipts=_receipts(),
        )
        owners = {"atlas:bayou:00047": "beacon:carol"}

        with self.assertRaisesRegex(DeedAtomicityError, "owned by"):
            apply_deed_transfer(owners, transfer)

        self.assertEqual(owners, {"atlas:bayou:00047": "beacon:carol"})


if __name__ == "__main__":
    unittest.main()

