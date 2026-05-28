# SPDX-License-Identifier: MIT
"""Tests for compute_state_root() endianness fix (consensus divergence)."""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from utxo_db import UtxoDB  # noqa: E402


def _reference_root(rows, endian):
    """Faithful replica of compute_state_root() with configurable endianness.

    Mirrors the real implementation's leaf schema and domain-separated odd-node
    padding so the reference diverges from production only when endianness differs.
    """
    if not rows:
        return hashlib.sha256(b"empty").hexdigest()
    count_bytes = len(rows).to_bytes(8, endian)
    hashes = []
    for row in rows:
        leaf = {
            'box_id': row['box_id'],
            'value_nrtc': row['value_nrtc'],
            'proposition': row['proposition'],
            'owner_address': row['owner_address'],
            'creation_height': row['creation_height'],
            'transaction_id': row['transaction_id'],
            'output_index': row['output_index'],
            'tokens_json': row['tokens_json'],
            'registers_json': row['registers_json'],
        }
        leaf_bytes = json.dumps(leaf, sort_keys=True, separators=(',', ':')).encode()
        hashes.append(hashlib.sha256(count_bytes + leaf_bytes).digest())
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashlib.sha256(b'\x01' + hashes[-1]).digest())
        hashes = [
            hashlib.sha256(hashes[i] + hashes[i + 1]).digest()
            for i in range(0, len(hashes), 2)
        ]
    return hashes[0].hex()


# Canonical test fixtures ordered by box_id ASC (matches compute_state_root ORDER BY)
_BOXES = [
    {
        'box_id': 'box001',
        'value_nrtc': 500_000_000,
        'proposition': 'prop_a',
        'owner_address': 'addr_a',
        'creation_height': 10,
        'transaction_id': 'txabc',
        'output_index': 0,
        'tokens_json': '[]',
        'registers_json': '{}',
    },
    {
        'box_id': 'box002',
        'value_nrtc': 250_000_000,
        'proposition': 'prop_b',
        'owner_address': 'addr_b',
        'creation_height': 11,
        'transaction_id': 'txdef',
        'output_index': 1,
        'tokens_json': '[]',
        'registers_json': '{}',
    },
]


def _seed_db(db_path, boxes):
    conn = sqlite3.connect(db_path)
    try:
        now = int(time.time())
        for box in boxes:
            conn.execute(
                """INSERT INTO utxo_boxes
                       (box_id, value_nrtc, proposition, owner_address,
                        creation_height, transaction_id, output_index,
                        tokens_json, registers_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (box['box_id'], box['value_nrtc'], box['proposition'],
                 box['owner_address'], box['creation_height'],
                 box['transaction_id'], box['output_index'],
                 box['tokens_json'], box['registers_json'], now),
            )
        conn.commit()
    finally:
        conn.close()


class TestStateRootEndian(unittest.TestCase):

    def test_count_bytes_endian_divergence(self):
        """LE and BE count_bytes differ for any count >= 1."""
        for count in [1, 2, 10, 255, 1000, 10_000]:
            le = count.to_bytes(8, 'little')
            be = count.to_bytes(8, 'big')
            self.assertNotEqual(le, be, f"count={count}: LE == BE (unexpected)")

    def test_state_root_diverges_between_endian_references(self):
        """Same UTXO set produces different roots under old (LE) vs fixed (BE) logic."""
        root_le = _reference_root(_BOXES, 'little')
        root_be = _reference_root(_BOXES, 'big')
        self.assertNotEqual(root_le, root_be,
                            "Roots should diverge between LE and BE encoding")

    def test_compute_state_root_matches_big_endian_reference(self):
        """UtxoDB.compute_state_root() must equal the big-endian reference.

        This test fails if utxo_db.py line 861 is reverted from 'big' to 'little'.
        """
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            db = UtxoDB(db_path)
            db.init_tables()
            _seed_db(db_path, _BOXES)

            actual = db.compute_state_root()
            expected_be = _reference_root(_BOXES, 'big')
            expected_le = _reference_root(_BOXES, 'little')

            self.assertEqual(
                actual, expected_be,
                "compute_state_root() must produce the big-endian root",
            )
            self.assertNotEqual(
                actual, expected_le,
                "compute_state_root() must not produce the little-endian root",
            )
        finally:
            os.unlink(db_path)


if __name__ == '__main__':
    unittest.main()
