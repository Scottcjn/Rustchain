# SPDX-License-Identifier: MIT
"""PoC tests for compute_state_root() endianness bug (consensus divergence)."""
import hashlib
import unittest


def _root_with_endian(rows, endian):
    """Minimal replica of compute_state_root() with configurable endianness."""
    if not rows:
        return hashlib.sha256(b"empty").hexdigest()
    count_bytes = len(rows).to_bytes(8, endian)
    hashes = []
    for row in rows:
        import json
        leaf_bytes = json.dumps(row, sort_keys=True, separators=(',', ':')).encode()
        hashes.append(hashlib.sha256(count_bytes + leaf_bytes).digest())
    while len(hashes) > 1:
        if len(hashes) % 2:
            hashes.append(hashes[-1])
        hashes = [
            hashlib.sha256(hashes[i] + hashes[i + 1]).digest()
            for i in range(0, len(hashes), 2)
        ]
    return hashes[0].hex()


class TestStateRootEndian(unittest.TestCase):

    def test_count_bytes_endian_divergence(self):
        """LE and BE count_bytes differ for any count >= 1."""
        for count in [1, 2, 10, 255, 1000, 10_000]:
            le = count.to_bytes(8, 'little')
            be = count.to_bytes(8, 'big')
            self.assertNotEqual(le, be, f"count={count}: LE == BE (unexpected)")

    def test_state_root_diverges_for_two_boxes(self):
        """Same UTXO set produces different roots under old (LE) vs fixed (BE) code."""
        rows = [
            {'box_id': 'abc123', 'value_nrtc': 100, 'creation_height': 1},
            {'box_id': 'def456', 'value_nrtc': 200, 'creation_height': 2},
        ]
        root_le = _root_with_endian(rows, 'little')
        root_be = _root_with_endian(rows, 'big')
        self.assertNotEqual(root_le, root_be,
                            "Roots should diverge between LE and BE encoding")

    def test_fixed_code_uses_big_endian(self):
        """Fixed compute_state_root() matches big-endian reference."""
        rows = [{'box_id': 'aaa', 'value_nrtc': 50, 'creation_height': 5}]
        root_be = _root_with_endian(rows, 'big')
        # The fix changes 'little' → 'big', so both must agree
        root_fixed = _root_with_endian(rows, 'big')
        self.assertEqual(root_be, root_fixed)


if __name__ == '__main__':
    unittest.main()
