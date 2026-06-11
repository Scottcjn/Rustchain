"""T3.5 + T3.6 fail-closed hardening.

T3.5: /beacon/submit had only a DB-backed, per-agent_id rate limit wrapped in
`except Exception: pass` — a DB error failed OPEN and agent_id rotation evaded it.
A DB-independent, per-IP, fail-closed in-memory ceiling now runs first.

T3.6: the node-file RIP-309 rotation selector returned a PREDICTABLE 4-of-6 subset
when the previous block hash was unavailable (the all-zeros fallback), letting an
attacker know exactly which checks to pass. It now fails CLOSED (all 6 active),
matching the reward path and finalize_epoch.
"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


_MOD = None


def _load():
    # Memoized: load the 10k-line node module ONCE for this file (both test classes
    # share it). Re-exec'ing it per-class re-registers module-global Prometheus metrics
    # against the shared REGISTRY, which fails when this file runs in a large multi-file
    # suite — a single load mirrors the well-behaved single-class beacon tests.
    global _MOD
    if _MOD is not None:
        return _MOD
    os.environ.setdefault("RUSTCHAIN_DB_PATH", tempfile.mkstemp(suffix=".db")[1])
    os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
    os.environ.setdefault("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")
    spec = importlib.util.spec_from_file_location("rcnode_t35_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MOD = mod
    return mod


class BeaconRateLimitT35(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def setUp(self):
        self.mod._BEACON_IP_RATE_LIMIT_BUCKETS.clear()
        self._orig_max = self.mod.BEACON_IP_RATE_LIMIT_MAX
        self.mod.BEACON_IP_RATE_LIMIT_MAX = 3

    def tearDown(self):
        self.mod.BEACON_IP_RATE_LIMIT_MAX = self._orig_max
        self.mod._BEACON_IP_RATE_LIMIT_BUCKETS.clear()

    def test_allows_up_to_max_then_blocks(self):
        t = 1_000_000
        for i in range(3):
            allowed, _ = self.mod._check_beacon_rate_limit("1.2.3.4", now_ts=t)
            self.assertTrue(allowed, f"call {i} should be allowed")
        allowed, retry = self.mod._check_beacon_rate_limit("1.2.3.4", now_ts=t)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)

    def test_db_independent(self):
        """The limiter must not touch the DB at all (no fail-open on DB error)."""
        # No DB connection involved; pure in-memory. Exhaust the bucket.
        t = 2_000_000
        for _ in range(3):
            self.mod._check_beacon_rate_limit("9.9.9.9", now_ts=t)
        allowed, _ = self.mod._check_beacon_rate_limit("9.9.9.9", now_ts=t)
        self.assertFalse(allowed, "ceiling must hold with zero DB involvement")

    def test_per_ip_isolation(self):
        t = 3_000_000
        for _ in range(3):
            self.mod._check_beacon_rate_limit("10.0.0.1", now_ts=t)
        # a different IP is unaffected
        allowed, _ = self.mod._check_beacon_rate_limit("10.0.0.2", now_ts=t)
        self.assertTrue(allowed)

    def test_window_expiry_allows_again(self):
        t = 4_000_000
        for _ in range(3):
            self.mod._check_beacon_rate_limit("8.8.8.8", now_ts=t)
        self.assertFalse(self.mod._check_beacon_rate_limit("8.8.8.8", now_ts=t)[0])
        later = t + self.mod.BEACON_IP_RATE_LIMIT_WINDOW + 1
        self.assertTrue(self.mod._check_beacon_rate_limit("8.8.8.8", now_ts=later)[0])

    def test_stale_buckets_evicted_when_over_cap(self):
        """Memory bound: once the table exceeds the key cap, fully-expired IPs are
        dropped on the next check."""
        orig_cap = self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS
        self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS = 5
        try:
            t = 5_000_000
            # seed 8 stale IPs (attempts far in the past)
            for i in range(8):
                self.mod._BEACON_IP_RATE_LIMIT_BUCKETS[f"stale-{i}"] = [t - 10_000]
            # a fresh check past the cap triggers eviction of the stale keys
            self.mod._check_beacon_rate_limit("fresh-ip", now_ts=t)
            self.assertNotIn("stale-0", self.mod._BEACON_IP_RATE_LIMIT_BUCKETS)
            self.assertIn("fresh-ip", self.mod._BEACON_IP_RATE_LIMIT_BUCKETS)
        finally:
            self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS = orig_cap

    def test_active_flood_hard_bounded(self):
        """Even an all-ACTIVE flood (no stale keys) must not grow the table past the
        cap — least-recently-active keys are evicted to a hard bound."""
        orig_cap = self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS
        self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS = 10
        try:
            t = 6_000_000
            # 20 distinct IPs all active within the window (increasing recency)
            for i in range(20):
                self.mod._BEACON_IP_RATE_LIMIT_BUCKETS[f"active-{i}"] = [t - (20 - i)]
            self.mod._check_beacon_rate_limit("newcomer", now_ts=t)
            self.assertLessEqual(len(self.mod._BEACON_IP_RATE_LIMIT_BUCKETS),
                                 self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS + 1)
            # the most-recently-active survivors + newcomer remain; oldest evicted
            self.assertIn("newcomer", self.mod._BEACON_IP_RATE_LIMIT_BUCKETS)
            self.assertNotIn("active-0", self.mod._BEACON_IP_RATE_LIMIT_BUCKETS)
        finally:
            self.mod._BEACON_IP_RATE_LIMIT_MAX_KEYS = orig_cap

    def test_endpoint_returns_429_when_exhausted(self):
        self.mod._BEACON_IP_RATE_LIMIT_BUCKETS.clear()
        self.mod.BEACON_IP_RATE_LIMIT_MAX = 2
        with self.mod.app.test_request_context("/beacon/submit", method="POST", json={"x": 1}):
            # exhaust
            self.mod._check_beacon_rate_limit(self.mod.get_client_ip())
            self.mod._check_beacon_rate_limit(self.mod.get_client_ip())
            resp = self.mod.beacon_submit()
        status = resp.status_code if hasattr(resp, "status_code") else resp[1]
        self.assertEqual(status, 429)


class Rip309FailClosedT36(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def test_fallback_hash_activates_all_six(self):
        active = self.mod.select_active_fingerprint_checks(self.mod.RIP309_NONCE_FALLBACK)
        self.assertEqual(set(active), set(self.mod.RIP309_ROTATING_FINGERPRINT_CHECKS))
        self.assertEqual(len(active), 6)

    def test_empty_and_none_activate_all_six(self):
        for bad in ("", "   ", None):
            active = self.mod.select_active_fingerprint_checks(bad)
            self.assertEqual(set(active), set(self.mod.RIP309_ROTATING_FINGERPRINT_CHECKS),
                             f"{bad!r} must fail closed to all 6")

    def test_real_hash_still_selects_subset(self):
        """A genuine block hash keeps the rotating 4-of-6 (unpredictability preserved)."""
        h = "a" * 64
        active = self.mod.select_active_fingerprint_checks(h)
        self.assertEqual(len(active), self.mod.RIP309_ACTIVE_FINGERPRINT_CHECKS)
        # deterministic for the same hash
        self.assertEqual(active, self.mod.select_active_fingerprint_checks(h))

    def test_distinct_real_hashes_can_differ(self):
        sets = {self.mod.select_active_fingerprint_checks(hex(i)[2:].rjust(64, "0"))
                for i in range(50)}
        self.assertGreater(len(sets), 1, "valid hashes should rotate the active subset")

    def test_epoch_zero_rotation_is_all_six(self):
        """get_epoch_fingerprint_rotation(epoch=0) → prev hash unavailable → all 6 active,
        none inactive (matches the reward path's empty-hash fallback)."""
        with sqlite3.connect(":memory:") as conn:
            rot = self.mod.get_epoch_fingerprint_rotation(conn, 0)
        self.assertEqual(set(rot["active_checks"]), set(self.mod.RIP309_ROTATING_FINGERPRINT_CHECKS))
        self.assertEqual(rot["inactive_checks"], [])

    def test_roundrobin_duplicate_selector_also_fails_closed(self):
        """The duplicate selector in rip_200_round_robin_1cpu1vote must fail closed too
        (a leaked-import landmine if it didn't)."""
        import rip_200_round_robin_1cpu1vote as rr
        for bad in ("", "0" * 64, None):
            self.assertEqual(set(rr.select_active_fingerprint_checks(bad)),
                             set(rr.ROTATING_FINGERPRINT_CHECKS), f"{bad!r} must fail closed")
        # a real hash still rotates a subset
        self.assertEqual(len(rr.select_active_fingerprint_checks("b" * 64)),
                         rr.ACTIVE_FINGERPRINT_CHECK_COUNT)


if __name__ == "__main__":
    unittest.main()
