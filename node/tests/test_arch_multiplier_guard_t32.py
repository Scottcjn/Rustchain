"""T3.2 regression: vintage arch-multiplier must not be forgeable via CPU-brand string.

Two layers are tested:

1. `derive_verified_device` Path B (`_claims_powerpc`) — the `brand_matches`
   fast-path used to return PowerPC/G4 on a CPU-brand token ALONE (a spoofer stuffs
   "g4" into cpu_brand on an x86 box → 2.5x antiquity tier; observed live as
   clockspoof/bypass miners recorded device_arch=g4). The fix vetoes the fast-path on
   POSITIVE x86 contradiction (x86/ARM brand tokens OR SSE/AVX in the SIMD fingerprint),
   never on the mere absence of PowerPC evidence — so honest PowerPC silicon (AltiVec,
   no SSE/AVX) is unaffected. Contradicting claims fall through to x86_64/default.

2. `_get_active_miner_antiquity_multiplier` — the antiquity BONUS (>1.0) is now
   gated on fingerprint_passed; a miner that failed/never ran the fingerprint keeps
   base weight (capped 1.0) but cannot wield a forged vintage tier in governance.
"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


def _simd_fp(**data):
    """Build a fingerprint with a simd_identity check carrying `data`."""
    return {"checks": {"simd_identity": {"data": dict(data)}}}


class ArchMultiplierGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ.setdefault("RUSTCHAIN_DB_PATH", os.path.join(cls._tmp.name, "t32.db"))
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        spec = importlib.util.spec_from_file_location("rcnode_t32_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _derive(self, device, fingerprint=None, fp_passed=True):
        return self.mod.derive_verified_device(device, fingerprint or {}, fp_passed)

    # --- Path B brand fast-path: honest PowerPC unaffected --------------------
    def test_real_g4_brand_with_altivec_is_powerpc(self):
        d = {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC G4 7450", "machine": "Power Macintosh"}
        out = self._derive(d, _simd_fp(altivec=True))
        self.assertEqual(out, {"device_family": "PowerPC", "device_arch": "G4"})

    def test_real_g4_brand_no_fingerprint_still_powerpc(self):
        """Legacy miners with no SIMD fingerprint must keep their tier (no x86
        contradiction == not a spoof). Absence of PPC evidence must NOT zero them."""
        d = {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC G4 7450", "machine": "Power Macintosh"}
        out = self._derive(d, {}, fp_passed=False)
        self.assertEqual(out, {"device_family": "PowerPC", "device_arch": "G4"})

    def test_real_g5_brand_is_powerpc(self):
        d = {"family": "PowerPC", "arch": "g5", "cpu": "PowerPC G5 970", "machine": "Power Macintosh"}
        out = self._derive(d, _simd_fp(altivec=True))
        self.assertEqual(out, {"device_family": "PowerPC", "device_arch": "G5"})

    def test_power8_brand_is_powerpc(self):
        d = {"family": "PowerPC", "arch": "power8", "cpu": "IBM POWER8 8286", "machine": ""}
        out = self._derive(d, _simd_fp(vsx=True))
        self.assertEqual(out, {"device_family": "PowerPC", "device_arch": "POWER8"})

    # --- Path B brand fast-path: spoofers vetoed ------------------------------
    def test_spoof_g4_brand_with_sse_is_downgraded(self):
        """clockspoof pattern: 'g4' brand on a box whose SIMD fingerprint honestly
        reports SSE → x86 contradiction → must NOT get PowerPC."""
        d = {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC G4", "machine": ""}
        out = self._derive(d, _simd_fp(has_sse=True))
        self.assertNotEqual(out["device_family"], "PowerPC")
        self.assertIn(out["device_arch"], ("default", "modern"))

    def test_spoof_g4_brand_with_avx_is_downgraded(self):
        d = {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC G4", "machine": ""}
        out = self._derive(d, _simd_fp(has_avx=True))
        self.assertNotEqual(out["device_family"], "PowerPC")

    def test_spoof_g4_brand_with_x86_features_is_downgraded(self):
        d = {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC G4", "machine": ""}
        out = self._derive(d, _simd_fp(x86_features=["sse2", "avx2"]))
        self.assertNotEqual(out["device_family"], "PowerPC")

    def test_brand_contaminated_intel_plus_g4_is_downgraded(self):
        """Brand stuffing: 'Intel Core i7 ... g4' has BOTH tokens → x86-contaminated
        → vetoed → strict validation downgrades to x86_64/default."""
        d = {"family": "PowerPC", "arch": "g4", "cpu": "Intel Core i7-9750H g4", "machine": ""}
        out = self._derive(d, _simd_fp())
        self.assertEqual(out, {"device_family": "x86_64", "device_arch": "default"})

    # --- governance multiplier: antiquity bonus gated on fingerprint ----------
    def _attest_db(self):
        c = sqlite3.connect(":memory:")
        c.execute(
            "CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER, "
            "device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0, "
            "fingerprint_passed INTEGER DEFAULT 0)"
        )
        return c

    def _seed_attest(self, c, miner, family, arch, fp):
        now = int(__import__("time").time())
        c.execute(
            "INSERT INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, fingerprint_passed) "
            "VALUES (?,?,?,?,?)", (miner, now, family, arch, fp))

    def test_g4_with_fingerprint_keeps_full_multiplier(self):
        c = self._attest_db()
        self._seed_attest(c, "g4-real", "PowerPC", "G4", 1)
        active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "g4-real")
        self.assertTrue(active)
        self.assertEqual(mult, 2.5)
        self.assertEqual(reason, "ok")

    def test_g4_without_fingerprint_capped_to_one(self):
        c = self._attest_db()
        self._seed_attest(c, "g4-spoof", "PowerPC", "G4", 0)
        active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "g4-spoof")
        self.assertTrue(active)            # still active — liveness preserved
        self.assertEqual(mult, 1.0)        # but no forged antiquity bonus
        self.assertEqual(reason, "antiquity_bonus_requires_fingerprint")

    def test_modern_miner_unaffected_by_cap(self):
        """A modern miner's base weight (<=1.0) is never raised or 'capped' oddly."""
        c = self._attest_db()
        self._seed_attest(c, "modern-x", "modern", "default", 0)
        active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "modern-x")
        self.assertTrue(active)
        self.assertLessEqual(mult, 1.0)
        self.assertEqual(reason, "ok")     # cap only triggers when multiplier > 1.0

    def test_not_attested(self):
        c = self._attest_db()
        active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "ghost")
        self.assertFalse(active)
        self.assertEqual(reason, "miner_not_attested")

    def test_text_zero_fingerprint_does_not_grant_bonus(self):
        """Codex audit: a TEXT '0'/'false' must not read truthy and grant a forged
        bonus (bool('0') is True in Python — explicit coercion required)."""
        for bad in ("0", "false", "False", "no", ""):
            c = self._attest_db()
            c.execute(
                "INSERT INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, fingerprint_passed) "
                "VALUES (?,?,?,?,?)", ("g4-textfp", int(__import__("time").time()), "PowerPC", "G4", bad))
            active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "g4-textfp")
            self.assertEqual(mult, 1.0, f"text fingerprint_passed={bad!r} must NOT grant bonus")
            self.assertEqual(reason, "antiquity_bonus_requires_fingerprint")

    def test_text_one_fingerprint_grants_bonus(self):
        c = self._attest_db()
        c.execute(
            "INSERT INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, fingerprint_passed) "
            "VALUES (?,?,?,?,?)", ("g4-textok", int(__import__("time").time()), "PowerPC", "G4", "1"))
        active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "g4-textok")
        self.assertEqual(mult, 2.5)
        self.assertEqual(reason, "ok")

    def test_legacy_schema_without_fingerprint_column_does_not_crash(self):
        """Grok blast-radius: a divergent/older node whose miner_attest_recent lacks the
        fingerprint_passed column must NOT raise on every governance call — it falls
        back to pre-cap behavior (derive-side arch downgrade still protects it)."""
        c = sqlite3.connect(":memory:")
        c.execute(
            "CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER, "
            "device_family TEXT, device_arch TEXT)")  # NO fingerprint_passed column
        c.execute(
            "INSERT INTO miner_attest_recent (miner, ts_ok, device_family, device_arch) VALUES (?,?,?,?)",
            ("g4-legacy", int(__import__("time").time()), "PowerPC", "G4"))
        active, mult, reason = self.mod._get_active_miner_antiquity_multiplier(c.cursor(), "g4-legacy")
        self.assertTrue(active)
        self.assertEqual(mult, 2.5)        # no cap applied (column absent) — no crash
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
