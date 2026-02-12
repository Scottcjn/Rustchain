import sqlite3
import time
import unittest

from node.attest_nonce import (
    consume_challenge,
    ensure_tables,
    issue_challenge,
    mark_nonce_used,
    validate_nonce_freshness,
)


class AttestNonceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_freshness_ok(self):
        now = int(time.time())
        ok, reason = validate_nonce_freshness(str(now), now_ts=now, skew_seconds=60)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_freshness_rejects_out_of_window(self):
        now = int(time.time())
        ok, reason = validate_nonce_freshness(str(now - 999), now_ts=now, skew_seconds=60)
        self.assertFalse(ok)
        self.assertEqual(reason, "nonce_out_of_window")

    def test_mark_nonce_used_replay(self):
        ok1, _ = mark_nonce_used(self.conn, miner_id="m1", nonce="123", ttl_seconds=60, now_ts=1000)
        ok2, why2 = mark_nonce_used(self.conn, miner_id="m1", nonce="123", ttl_seconds=60, now_ts=1001)
        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertEqual(why2, "replay_detected")

    def test_challenge_one_time(self):
        ch = issue_challenge(self.conn, ttl_seconds=120, now_ts=1000)
        self.assertTrue(consume_challenge(self.conn, ch.nonce, now_ts=1001))
        self.assertFalse(consume_challenge(self.conn, ch.nonce, now_ts=1002))


if __name__ == "__main__":
    unittest.main()

