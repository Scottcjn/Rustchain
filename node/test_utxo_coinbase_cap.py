# SPDX-License-Identifier: MIT
"""
Regression tests for the UTXO coinbase mint cap.
"""

import os
import tempfile
import time
import unittest

from utxo_db import UtxoDB, UNIT, MAX_COINBASE_OUTPUT_NRTC


class TestUtxoCoinbaseCap(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_mining_reward_rejects_epoch_multiplier_cap(self):
        """Mining reward must not allow 144 epochs worth of RTC at once."""
        self.assertEqual(MAX_COINBASE_OUTPUT_NRTC, 150 * UNIT)
        old_multiplier_cap = 150 * 144 * UNIT
        self.assertGreater(old_multiplier_cap, MAX_COINBASE_OUTPUT_NRTC)

        ok = self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'attacker',
                         'value_nrtc': old_multiplier_cap}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=10)

        self.assertFalse(ok)
        self.assertEqual(self.db.get_balance('attacker'), 0)


if __name__ == '__main__':
    unittest.main()
