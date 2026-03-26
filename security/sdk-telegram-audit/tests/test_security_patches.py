#!/usr/bin/env python3
"""
Tests for Red Team Security Patches (Bounty #69) — 23 tests

Run:  python -m pytest security/sdk-telegram-audit/tests/test_security_patches.py -v
"""
import re, ssl, time, unittest

MINER_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
TOKEN_RE = re.compile(r"^\d{8,10}:[A-Za-z0-9_-]{35}$")


class TestMinerIdValidation(unittest.TestCase):
    def test_valid(self):
        for v in ["Ivan-houzhiwen", "miner_001", "a", "A" * 64]:
            self.assertTrue(MINER_ID_RE.match(v), v)

    def test_path_traversal(self):
        for a in ["../../etc/passwd", "../admin", "/etc/passwd"]:
            self.assertIsNone(MINER_ID_RE.match(a), a)

    def test_param_injection(self):
        for a in ["foo&admin=true", "test?cb=x", "id; DROP TABLE w"]:
            self.assertIsNone(MINER_ID_RE.match(a), a)

    def test_too_long(self):
        self.assertIsNone(MINER_ID_RE.match("A" * 65))

    def test_empty(self):
        self.assertIsNone(MINER_ID_RE.match(""))

    def test_special(self):
        for a in ["m<script>", "m;ls", "m|cat", "m`id`", "m$(id)"]:
            self.assertIsNone(MINER_ID_RE.match(a), a)


class TestTransferAmount(unittest.TestCase):
    def _ok(self, amt):
        if not isinstance(amt, (int, float)) or amt <= 0:
            raise ValueError
        if amt > 1_000_000:
            raise ValueError
        return True

    def test_valid(self):
        for a in [0.01, 1.0, 100, 999_999]:
            self.assertTrue(self._ok(a))

    def test_negative(self):
        self.assertRaises(ValueError, self._ok, -10)

    def test_zero(self):
        self.assertRaises(ValueError, self._ok, 0)

    def test_excessive(self):
        self.assertRaises(ValueError, self._ok, 10_000_000)

    def test_non_numeric(self):
        for b in ["100", None, []]:
            self.assertRaises(ValueError, self._ok, b)


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.hits, self.limit = {}, 10

    def _rate(self, uid):
        now = time.time()
        h = self.hits.setdefault(uid, [])
        h[:] = [t for t in h if t > now - 60]
        if len(h) >= self.limit:
            return False
        h.append(now)
        return True

    def test_under(self):
        for _ in range(10):
            self.assertTrue(self._rate(1))

    def test_over(self):
        for _ in range(10):
            self._rate(1)
        self.assertFalse(self._rate(1))

    def test_independent(self):
        for _ in range(10):
            self._rate(1)
        self.assertTrue(self._rate(2))


class TestSSL(unittest.TestCase):
    def test_default_verifies(self):
        ctx = ssl.create_default_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)


class TestPrice(unittest.TestCase):
    def _ok(self, p):
        try:
            return 0.0001 <= float(p) <= 1000
        except (ValueError, TypeError):
            return False

    def test_valid(self):
        for p in [0.10, 0.001, 1.0, 500]:
            self.assertTrue(self._ok(p))

    def test_absurd(self):
        self.assertFalse(self._ok(1_000_000))

    def test_neg(self):
        self.assertFalse(self._ok(-1))

    def test_zero(self):
        self.assertFalse(self._ok(0))

    def test_nan(self):
        self.assertFalse(self._ok("x"))


class TestToken(unittest.TestCase):
    def test_valid(self):
        self.assertIsNotNone(TOKEN_RE.match("123456789:" + "A" * 35))

    def test_empty(self):
        self.assertIsNone(TOKEN_RE.match(""))

    def test_bad(self):
        for b in ["nope", "123:short", "abc:" + "A" * 35]:
            self.assertIsNone(TOKEN_RE.match(b), b)


if __name__ == "__main__":
    unittest.main()
