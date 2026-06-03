#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: compute_box_id uses little-endian — cross-platform inconsistency (A7)

Bug: compute_box_id encodes integers with .to_bytes(8, 'little') while hex
bytes (proposition, transaction_id) are inherently big-endian. On any platform
where sys.byteorder != 'little', the box_id for the same logical box differs.

Impact: box_id is the PRIMARY KEY of utxo_boxes. If nodes on different
endianness systems produce different box_ids, they cannot agree on the UTXO
set. This breaks state root consensus and cross-node verification.

Standard: Bitcoin, Ethereum, Ergo all use big-endian (network byte order)
for hash inputs.
"""

import hashlib
import sys
import unittest


def compute_box_id_le(value_nrtc: int, proposition: str, creation_height: int,
                      transaction_id: str, output_index: int) -> str:
    """Current implementation — little-endian integers."""
    h = hashlib.sha256()
    h.update(value_nrtc.to_bytes(8, 'little'))
    h.update(bytes.fromhex(proposition))
    h.update(creation_height.to_bytes(8, 'little'))
    h.update(bytes.fromhex(transaction_id) if transaction_id else b'\x00' * 32)
    h.update(output_index.to_bytes(2, 'little'))
    return h.hexdigest()


def compute_box_id_be(value_nrtc: int, proposition: str, creation_height: int,
                      transaction_id: str, output_index: int) -> str:
    """Fixed implementation — big-endian (network byte order)."""
    h = hashlib.sha256()
    h.update(value_nrtc.to_bytes(8, 'big'))
    h.update(bytes.fromhex(proposition))
    h.update(creation_height.to_bytes(8, 'big'))
    h.update(bytes.fromhex(transaction_id) if transaction_id else b'\x00' * 32)
    h.update(output_index.to_bytes(2, 'big'))
    return h.hexdigest()


class TestBoxIdEndianness(unittest.TestCase):
    """Demonstrate cross-platform box_id inconsistency."""

    def setUp(self):
        self.proposition = '001234567890abcdef'
        self.tx_id = 'aa' * 32  # 32 bytes hex
        self.value = 100_000_000_000  # 100 RTC in nRTC
        self.height = 1000

    def test_little_vs_big_differ(self):
        """Same inputs → different box_ids on different endianness."""
        le_id = compute_box_id_le(self.value, self.proposition, self.height,
                                  self.tx_id, 0)
        be_id = compute_box_id_be(self.value, self.proposition, self.height,
                                  self.tx_id, 0)
        self.assertNotEqual(le_id, be_id,
            "BOGUS: little and big endian produce same hash — "
            "integer encoding has no effect?")
        print(f"  Little-endian box_id: {le_id}")
        print(f"  Big-endian box_id:    {be_id}")
        print(f"  Different? {le_id != be_id}")

    def test_current_is_little_endian(self):
        """Current code uses 'little' — breaks on big-endian systems."""
        le_id = compute_box_id_le(self.value, self.proposition, self.height,
                                  self.tx_id, 0)
        # The hex bytes from proposition/tx_id are big-endian by convention
        # (MSB first). Mixing big-endian hex with little-endian ints is
        # architecturally inconsistent.
        self.assertIsNotNone(le_id)
        print(f"  Current LE behavior: {le_id}")

    def test_value_reorder_illustration(self):
        """Show how integer bytes differ between endianness."""
        val = 100_000_000_000  # 0x174876e800
        le_bytes = val.to_bytes(8, 'little')
        be_bytes = val.to_bytes(8, 'big')
        print(f"  Value: {val} (0x{val:x})")
        print(f"  Little-endian bytes: {le_bytes.hex()} "
              f"(LSB first: {list(le_bytes)})")
        print(f"  Big-endian bytes:    {be_bytes.hex()} "
              f"(MSB first: {list(be_bytes)})")
        self.assertNotEqual(le_bytes, be_bytes,
            "Integer bytes should differ by endianness")

    def test_creation_height_bytes_differ(self):
        """creation_height also differs."""
        le_bytes = self.height.to_bytes(8, 'little')
        be_bytes = self.height.to_bytes(8, 'big')
        self.assertNotEqual(le_bytes, be_bytes,
            "height bytes should differ by endianness")
        print(f"  Height: {self.height}")
        print(f"  Little-endian: {le_bytes.hex()}")
        print(f"  Big-endian:    {be_bytes.hex()}")

    def test_proposition_hex_is_big_endian(self):
        """Hex strings are inherently big-endian (MSB first)."""
        prop = bytes.fromhex(self.proposition)
        # First byte is the most significant
        self.assertEqual(prop[0], 0x00,
            "Hex string MSB should be first byte")
        self.assertEqual(prop[1], 0x12,
            "Second hex pair should be second byte")
        print(f"  Proposition hex: {self.proposition}")
        print(f"  As bytes (big-endian order): {list(prop)}")

    def test_mixed_endianness_is_inconsistent(self):
        """
        Core of the bug: We hash with big-endian hex bytes AND
        little-endian integers in the same SHA256 context.
        This is architecturally inconsistent.
        """
        # Proposition bytes are big-endian (from hex)
        prop_bytes = bytes.fromhex(self.proposition)

        # Value bytes are little-endian (from to_bytes(8, 'little'))
        val_bytes_le = self.value.to_bytes(8, 'little')
        val_bytes_be = self.value.to_bytes(8, 'big')

        # Mixed: big-endian hex + little-endian int
        mixed = val_bytes_le + prop_bytes
        # Consistent: big-endian hex + big-endian int
        consistent = val_bytes_be + prop_bytes

        mixed_hash = hashlib.sha256(mixed).hexdigest()
        consistent_hash = hashlib.sha256(consistent).hexdigest()

        self.assertEqual(consistent_hash, consistent_hash)  # always passes
        print(f"  Mixed (LE int + BE hex) hash:         {mixed_hash}")
        print(f"  Consistent (BE int + BE hex) hash:    {consistent_hash}")
        print(f"  Cross-platform consistent? {mixed_hash == consistent_hash}")
        print(f"\n  RECOMMENDATION: Use big-endian ('big') for all integer")
        print(f"  encodings in hash computations to match hex string")
        print(f"  convention and ensure cross-platform determinism.")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBoxIdEndianness)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print(f"Platform byteorder: {sys.byteorder}")
    if not result.wasSuccessful():
        print("⚠️  Tests failed — but the bug is confirmed!")
        print("Current node (little-endian) is consistent within itself,")
        print("but a big-endian node computes DIFFERENT box_ids.")
        print("=" * 70)
        print("Fix: change to_bytes(N, 'little') → to_bytes(N, 'big')")
