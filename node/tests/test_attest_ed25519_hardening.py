# SPDX-License-Identifier: MIT
"""
Hardened Ed25519 attestation enforcement tests (#8016 / hardening of PR #8052).

Covers the design that the raw PR #8052 got wrong:
  * identity format gate: RTC-hex form AND symbolic lab IDs are both accepted for
    attestation, but only self-certifying RTC-hex keys public-TOFU-pin;
  * TOFU pin-then-verify for a real RTC-hex address (key must derive to it);
  * first-signer-hijack is prevented for GRANDFATHERED identities (existing
    symbolic/legacy names cannot be captured by a stranger's first signature);
  * admin unpin/rotate closes the lockout attack, with a pin freeze so a stranger
    cannot immediately re-capture an unpinned identity;
  * three enforcement phases (log_only / enforce_new / enforce_all) each behave
    correctly, and a grandfathered miner still attests unsigned in Phase 1;
  * partial signature pairs are rejected;
  * the unsigned allowlist is case-SENSITIVE.

These tests exercise mod._submit_attestation_impl() and mod.admin_attest_key()
directly against a temp DB, mirroring test_attest_signature_verification.py.
"""

import hashlib
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import nacl.signing
    HAVE_NACL = True
except Exception:
    HAVE_NACL = False

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

EXTRA_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS blocked_wallets (wallet TEXT PRIMARY KEY, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS ip_rate_limit (client_ip TEXT NOT NULL, miner_id TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (client_ip, miner_id))",
    "CREATE TABLE IF NOT EXISTS miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER NOT NULL, device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0, fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT, warthog_bonus REAL DEFAULT 1.0, signing_pubkey TEXT)",
    "CREATE TABLE IF NOT EXISTS hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT NOT NULL, device_arch TEXT, device_model TEXT, bound_at INTEGER NOT NULL, attestation_count INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS miner_macs (miner TEXT NOT NULL, mac_hash TEXT NOT NULL, first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (miner, mac_hash))",
    "CREATE TABLE IF NOT EXISTS attest_grandfathered (miner TEXT PRIMARY KEY, added_at INTEGER NOT NULL DEFAULT 0, reason TEXT DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS attest_key_admin (miner TEXT PRIMARY KEY, pin_frozen INTEGER NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0, note TEXT DEFAULT '')",
]

ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _keypair():
    sk = nacl.signing.SigningKey.generate()
    pubkey_hex = sk.verify_key.encode().hex()
    return sk, pubkey_hex


def _rtc_address_for(pubkey_hex):
    """Mirror node address_from_pubkey: RTC + first 40 chars of SHA256(pubkey)."""
    return "RTC" + hashlib.sha256(bytes.fromhex(pubkey_hex)).hexdigest()[:40]


def _legacy_sign(sk, miner_id, wallet, nonce, commitment):
    msg = "{}|{}|{}|{}".format(miner_id, wallet, nonce, commitment).encode("utf-8")
    return sk.sign(msg).signature.hex()


class HardenBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev = {k: os.environ.get(k) for k in (
            "RC_ADMIN_KEY", "RUSTCHAIN_DB_PATH", "RTC_ATTEST_ENFORCE_MODE",
            "RTC_UNSIGNED_ATTEST_ALLOWLIST",
        )}
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY
        os.environ.pop("RTC_ATTEST_ENFORCE_MODE", None)
        os.environ.pop("RTC_UNSIGNED_ATTEST_ALLOWLIST", None)
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._tmp.cleanup()

    def setUp(self):
        # Each test defaults to log_only unless it opts into a phase.
        os.environ.pop("RTC_ATTEST_ENFORCE_MODE", None)
        os.environ.pop("RTC_UNSIGNED_ATTEST_ALLOWLIST", None)

    def _db_path(self, name):
        return str(Path(self._tmp.name) / name)

    def _load(self, module_name, db_name):
        db_path = self._db_path(db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_db()
        with sqlite3.connect(db_path) as conn:
            for stmt in EXTRA_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        self._db = db_path
        return mod

    def _resp(self, resp):
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def _challenge(self, mod):
        with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
            return mod.get_challenge().get_json()["nonce"]

    def _submit(self, mod, payload):
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            return self._resp(mod._submit_attestation_impl())

    def _admin_key(self, mod, body):
        with mod.app.test_request_context(
            "/admin/attest/key", method="POST", json=body,
            headers={"X-Admin-Key": ADMIN_KEY},
        ):
            return self._resp(mod.admin_attest_key())

    _uniq = 0

    def _payload(self, miner, nonce, sig=None, pub=None, miner_id=None, commitment="deadbeef"):
        # Each call gets a distinct device + fingerprint so per-machine hardware
        # binding and the fingerprint-replay defense (both unrelated to signature
        # enforcement) do not spuriously reject back-to-back test submissions.
        HardenBase._uniq += 1
        u = HardenBase._uniq
        p = {
            "miner": miner,
            "report": {"nonce": nonce, "commitment": commitment},
            "device": {"family": "x86_64", "arch": "default", "model": f"test-box-{u}", "cores": 4},
            "signals": {"hostname": f"test-host-{u}", "macs": [f"aa:bb:cc:00:{u % 256:02x}:{(u >> 8) % 256:02x}"]},
            "fingerprint": {
                "checks": {
                    "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.05 + u * 1e-6, "samples": 64 + u}},
                },
                "all_passed": True,
                "nonce": f"fp-{u}",
            },
        }
        if sig is not None:
            p["signature"] = sig
        if pub is not None:
            p["public_key"] = pub
        if miner_id is not None:
            p["miner_id"] = miner_id
        return p

    def _stored_key(self, miner):
        with sqlite3.connect(self._db) as c:
            row = c.execute(
                "SELECT signing_pubkey FROM miner_attest_recent WHERE miner=?", (miner,)
            ).fetchone()
        return row[0] if row and row[0] else None

    def _grandfather(self, miner):
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR REPLACE INTO attest_grandfathered (miner, added_at) VALUES (?, 1)", (miner,))
            c.commit()

    def _submit_signed_rtc(self, mod, miner=None):
        """Attest as a self-certifying RTC-hex address. Returns (miner, sk, pubkey)."""
        sk, pub = _keypair()
        if miner is None:
            miner = _rtc_address_for(pub)
        miner_id = "mid_" + pub[:8]
        nonce = self._challenge(mod)
        sig = _legacy_sign(sk, miner_id, miner, nonce, "deadbeef")
        status, body = self._submit(mod, self._payload(miner, nonce, sig, pub, miner_id))
        return miner, sk, pub, status, body


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestFormatGate(HardenBase):
    def test_symbolic_id_accepted(self):
        """Established symbolic lab IDs attest fine (not rejected by a format gate)."""
        mod = self._load("h_fmt_sym", "h_fmt_sym.db")
        for miner in ("dual-g4-125", "power8-s824-sophia", "ppc_g5_130_x", "victus-x86-scott"):
            nonce = self._challenge(mod)
            status, body = self._submit(mod, self._payload(miner, nonce))
            self.assertEqual(status, 200, f"{miner}: {body}")
            self.assertTrue(body["ok"])

    def test_rtc_hex_id_accepted_and_pins(self):
        """A real RTC-hex address whose key derives to it is accepted and pins (TOFU)."""
        mod = self._load("h_fmt_rtc", "h_fmt_rtc.db")
        miner, sk, pub, status, body = self._submit_signed_rtc(mod)
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"])
        self.assertEqual(self._stored_key(miner), pub)

    def test_rtc_prefixed_nonhex_treated_symbolic(self):
        """RTC-prefixed but non-hex (e.g. RTC_VALID_MINER) is symbolic: no address binding."""
        mod = self._load("h_fmt_rtcish", "h_fmt_rtcish.db")
        self.assertFalse(mod._is_rtc_hex_address("RTC_VALID_MINER"))
        self.assertFalse(mod._is_rtc_hex_address("RTCdos8086test1234567890abcdef12345678"))
        self.assertTrue(mod._is_rtc_hex_address("RTC" + "a" * 40))
        self.assertFalse(mod._is_rtc_hex_address("RTC" + "A" * 40))  # uppercase not node-derived


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestTOFUPinning(HardenBase):
    def test_tofu_pins_then_verifies(self):
        """First signed attestation pins; a later signature with a DIFFERENT key is blocked."""
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_tofu", "h_tofu.db")
        miner, sk, pub, status, body = self._submit_signed_rtc(mod)
        self.assertEqual(status, 200, body)
        self.assertEqual(self._stored_key(miner), pub)

        # Same key again → still accepted.
        nonce = self._challenge(mod)
        sig = _legacy_sign(sk, "mid_x", miner, nonce, "deadbeef")
        status2, body2 = self._submit(mod, self._payload(miner, nonce, sig, pub, "mid_x"))
        self.assertEqual(status2, 200, body2)

        # Different key for the SAME address cannot derive → PUBKEY_ADDRESS_MISMATCH.
        sk2, pub2 = _keypair()
        nonce3 = self._challenge(mod)
        sig3 = _legacy_sign(sk2, "mid_y", miner, nonce3, "deadbeef")
        status3, body3 = self._submit(mod, self._payload(miner, nonce3, sig3, pub2, "mid_y"))
        self.assertEqual(status3, 400, body3)
        self.assertEqual(body3["code"], "PUBKEY_ADDRESS_MISMATCH")

    def test_rotation_blocked_for_symbolic_pinned(self):
        """Once a symbolic miner has a key on file, a new key is rejected (rotation block)."""
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_rot", "h_rot.db")
        miner = "lab-symbolic-01"
        # Directly pin a key (as if admin-enrolled), then try to rotate via attestation.
        sk1, pub1 = _keypair()
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT INTO miner_attest_recent (miner, ts_ok, signing_pubkey) VALUES (?, 1, ?)", (miner, pub1))
            c.commit()
        sk2, pub2 = _keypair()
        nonce = self._challenge(mod)
        sig = _legacy_sign(sk2, "mid", miner, nonce, "deadbeef")
        status, body = self._submit(mod, self._payload(miner, nonce, sig, pub2, "mid"))
        self.assertEqual(status, 400, body)
        self.assertEqual(body["code"], "SIGNING_KEY_MISMATCH")


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestFirstSignerHijack(HardenBase):
    def test_grandfathered_symbolic_not_captured_by_stranger(self):
        """A stranger's first signature must NOT pin a grandfathered symbolic identity."""
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_hij", "h_hij.db")
        miner = "dual-g4-125"
        self._grandfather(miner)
        # Attacker signs with their own fresh key.
        sk, pub = _keypair()
        nonce = self._challenge(mod)
        sig = _legacy_sign(sk, "atk", miner, nonce, "deadbeef")
        status, body = self._submit(mod, self._payload(miner, nonce, sig, pub, "atk"))
        # Attestation is accepted (valid signature) but NO key is pinned.
        self.assertEqual(status, 200, body)
        self.assertIsNone(self._stored_key(miner),
                          "grandfathered symbolic identity must not be TOFU-pinned")

    def test_new_symbolic_can_tofu_pin(self):
        """A brand-new (non-grandfathered) symbolic identity may pin on first signature."""
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_new", "h_new.db")
        miner = "fresh-miner-xyz"
        sk, pub = _keypair()
        nonce = self._challenge(mod)
        sig = _legacy_sign(sk, "mid", miner, nonce, "deadbeef")
        status, body = self._submit(mod, self._payload(miner, nonce, sig, pub, "mid"))
        self.assertEqual(status, 200, body)
        self.assertEqual(self._stored_key(miner), pub)


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestPhases(HardenBase):
    def test_log_only_accepts_unsigned_new(self):
        mod = self._load("h_p0", "h_p0.db")  # default log_only
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload("brand-new-1", nonce))
        self.assertEqual(status, 200, body)

    def test_enforce_new_rejects_unsigned_new(self):
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_p1n", "h_p1n.db")
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload("brand-new-2", nonce))
        self.assertEqual(status, 400, body)
        self.assertEqual(body["code"], "MISSING_SIGNATURE")

    def test_enforce_new_allows_unsigned_grandfathered(self):
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_p1g", "h_p1g.db")
        miner = "ppc_g5_130_legacy"
        self._grandfather(miner)
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload(miner, nonce))
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"])

    def test_enforce_all_rejects_unsigned_grandfathered(self):
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_all"
        mod = self._load("h_p2g", "h_p2g.db")
        miner = "ppc_g5_130_legacy2"
        self._grandfather(miner)
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload(miner, nonce))
        self.assertEqual(status, 400, body)
        self.assertEqual(body["code"], "MISSING_SIGNATURE")

    def test_enforce_new_rejects_unsigned_when_key_on_file(self):
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_p1k", "h_p1k.db")
        miner = "keyed-miner"
        sk, pub = _keypair()
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT INTO miner_attest_recent (miner, ts_ok, signing_pubkey) VALUES (?, 1, ?)", (miner, pub))
            c.commit()
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload(miner, nonce))
        self.assertEqual(status, 400, body)
        self.assertEqual(body["code"], "MISSING_SIGNATURE")


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestAllowlistAndPairs(HardenBase):
    def test_allowlist_case_sensitive(self):
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_all"
        mod = self._load("h_al", "h_al.db")
        miner = "Vintage-Apple-II"
        # Wrong case must NOT match.
        os.environ["RTC_UNSIGNED_ATTEST_ALLOWLIST"] = "vintage-apple-ii"
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload(miner, nonce))
        self.assertEqual(status, 400, body)
        self.assertEqual(body["code"], "MISSING_SIGNATURE")
        # Exact case matches → unsigned allowed even in enforce_all.
        os.environ["RTC_UNSIGNED_ATTEST_ALLOWLIST"] = miner
        nonce2 = self._challenge(mod)
        status2, body2 = self._submit(mod, self._payload(miner, nonce2))
        self.assertEqual(status2, 200, body2)

    def test_partial_signature_rejected(self):
        mod = self._load("h_pp", "h_pp.db")  # log_only — still rejects partial
        nonce = self._challenge(mod)
        status, body = self._submit(mod, self._payload("m1", nonce, sig="aa" * 64))
        self.assertEqual(status, 400, body)
        self.assertEqual(body["code"], "INCOMPLETE_SIGNATURE")
        nonce2 = self._challenge(mod)
        status2, body2 = self._submit(mod, self._payload("m2", nonce2, pub="bb" * 32))
        self.assertEqual(status2, 400, body2)
        self.assertEqual(body2["code"], "INCOMPLETE_SIGNATURE")


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestAdminKeyManagement(HardenBase):
    def test_admin_unpin_then_freeze_prevents_repin(self):
        os.environ["RTC_ATTEST_ENFORCE_MODE"] = "enforce_new"
        mod = self._load("h_adm", "h_adm.db")
        # Pin a self-certifying RTC-hex identity.
        miner, sk, pub, status, body = self._submit_signed_rtc(mod)
        self.assertEqual(self._stored_key(miner), pub)

        # Admin unpins → key cleared and pin frozen.
        st, b = self._admin_key(mod, {"miner": miner, "action": "unpin", "note": "lost key"})
        self.assertEqual(st, 200, b)
        self.assertTrue(b["pin_frozen"])
        self.assertIsNone(self._stored_key(miner))
        gen_after_unpin = b["generation"]

        # A signed attestation (even a correctly-deriving key) must NOT re-pin while frozen.
        nonce = self._challenge(mod)
        sig = _legacy_sign(sk, "mid", miner, nonce, "deadbeef")
        st2, b2 = self._submit(mod, self._payload(miner, nonce, sig, pub, "mid"))
        self.assertEqual(st2, 200, b2)
        self.assertIsNone(self._stored_key(miner), "frozen identity must not public re-pin")

        # Admin 'set' installs a NEW key authoritatively and clears the freeze.
        sk3, pub3 = _keypair()
        st3, b3 = self._admin_key(mod, {"miner": miner, "action": "set", "public_key": pub3})
        self.assertEqual(st3, 200, b3)
        self.assertFalse(b3["pin_frozen"])
        self.assertEqual(self._stored_key(miner), pub3)
        self.assertGreater(b3["generation"], gen_after_unpin)

    def test_admin_requires_key(self):
        mod = self._load("h_adm_auth", "h_adm_auth.db")
        with mod.app.test_request_context("/admin/attest/key", method="POST",
                                          json={"miner": "x", "action": "status"}):
            status, body = self._resp(mod.admin_attest_key())
        self.assertIn(status, (401, 403, 503))

    def test_admin_status_reports_state(self):
        mod = self._load("h_adm_stat", "h_adm_stat.db")
        st, b = self._admin_key(mod, {"miner": "some-miner", "action": "status"})
        self.assertEqual(st, 200, b)
        self.assertIsNone(b["pinned_pubkey"])
        self.assertFalse(b["pin_frozen"])


if __name__ == "__main__":
    unittest.main()
