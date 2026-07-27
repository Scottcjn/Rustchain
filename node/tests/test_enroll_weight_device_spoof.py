# SPDX-License-Identifier: MIT
"""
Regression test for reward-weight spoofing via the unsigned `device` field on
/epoch/enroll.

Vulnerability (pre-fix): enroll_epoch computed the HARDWARE_WEIGHTS reward
multiplier from the caller-supplied request-body `device` (family/arch). The
enrollment signature only covers (miner_pubkey|miner_id|epoch), so `device` is
unsigned and attacker-controlled. A miner that attests on ordinary x86
(verified device x86/modern -> 0.8x) could enroll claiming e.g. ARM `arm2`
(4.0x) and be recorded with a ~5x inflated epoch weight, draining the fixed
per-epoch reward pot from honest participants.

Fix: the weight is bound to the *verified* device the node stored at
attestation (miner_attest_recent.device_family / device_arch, written from
derive_verified_device) via resolve_enroll_weight_device(). The request-body
`device` is only consulted as a legacy fallback when no verified device exists.

These tests drive the real /epoch/enroll endpoint with a valid Ed25519
signature (reusing the harness style of test_enroll_signature_verification).
They FAIL on the pre-fix code (stored hw_weight == 4.0) and PASS on the fix
(stored hw_weight == 0.8). A legacy-fallback test guards against regressing
miners whose stored verified device is absent.
"""

import importlib.util
import gc
import os
import sqlite3
import sys
import tempfile
import time
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
    "CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk))",
    "CREATE TABLE IF NOT EXISTS balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT)",
    "CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, pot REAL, finalized INTEGER DEFAULT 0)",
]


def _sign_message(miner_id, wallet, nonce, commitment):
    signing_key = nacl.signing.SigningKey.generate()
    pubkey_hex = signing_key.verify_key.encode().hex()
    message = '{}|{}|{}|{}'.format(miner_id, wallet, nonce, commitment)
    signature = signing_key.sign(message.encode('utf-8'))
    return signature.signature.hex(), pubkey_hex, signing_key


def _sign_enrollment(miner_pk, miner_id, epoch, signing_key):
    pubkey_hex = signing_key.verify_key.encode().hex()
    message = '{}|{}|{}'.format(miner_pk, miner_id, epoch)
    signature = signing_key.sign(message.encode('utf-8'))
    return signature.signature.hex(), pubkey_hex


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestEnrollWeightDeviceSpoof(unittest.TestCase):
    HONEST_FAMILY = "x86"
    HONEST_ARCH = "modern"      # HARDWARE_WEIGHTS["x86"]["modern"] == 0.8
    SPOOF_FAMILY = "ARM"
    SPOOF_ARCH = "arm2"          # HARDWARE_WEIGHTS["ARM"]["arm2"] == 4.0

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev = {k: os.environ.get(k) for k in
                     ("RC_ADMIN_KEY", "RUSTCHAIN_DB_PATH", "RUSTCHAIN_DISABLE_P2P_AUTO_START")}
        cls._loaded = []
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._release()
        for attempt in range(5):
            try:
                cls._tmp.cleanup()
                break
            except PermissionError:
                if attempt == 4:
                    raise
                gc.collect()
                time.sleep(0.2)

    @classmethod
    def _release(cls):
        try:
            from prometheus_client import REGISTRY
        except Exception:
            cls._loaded = []
            return
        for mod in cls._loaded:
            for metric_name in ("withdrawal_requests", "withdrawal_completed",
                                "withdrawal_failed", "balance_gauge", "epoch_gauge",
                                "withdrawal_queue_size"):
                metric = getattr(mod, metric_name, None)
                if metric is None:
                    continue
                try:
                    REGISTRY.unregister(metric)
                except (KeyError, ValueError):
                    pass
        cls._loaded = []
        gc.collect()

    def tearDown(self):
        self._release()

    def _load(self, module_name, db_name):
        self._release()
        db_path = str(Path(self._tmp.name) / db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._loaded.append(mod)
        mod.HAVE_REPLAY_DEFENSE = False
        for attempt in range(5):
            try:
                mod.init_db()
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 4:
                    raise
                time.sleep(0.2)
        with sqlite3.connect(db_path) as conn:
            for stmt in EXTRA_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        return mod, db_path

    def _enroll(self, mod, payload):
        with mod.app.test_request_context("/epoch/enroll", method="POST", json=payload):
            resp = mod.enroll_epoch()
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def _attest(self, mod, miner, miner_id):
        with mod.app.test_request_context("/attest/challenge", method="POST", json={}):
            nonce = mod.get_challenge().get_json()["nonce"]
        commitment = "deadbeef"
        sig_hex, pubkey_hex, signing_key = _sign_message(miner_id, miner, nonce, commitment)
        payload = {
            "miner": miner,
            "miner_id": miner_id,
            "report": {"nonce": nonce, "commitment": commitment},
            "device": {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {"all_passed": True, "checks": {"clock_drift": {"passed": True}}},
            "signature": sig_hex,
            "public_key": pubkey_hex,
        }
        with mod.app.test_request_context("/attest/submit", method="POST", json=payload):
            status, body = self._resp(mod._submit_attestation_impl())
        self.assertEqual(status, 200, f"attestation failed: {body}")
        return signing_key

    @staticmethod
    def _resp(resp):
        if isinstance(resp, tuple):
            body, status = resp
            return status, body.get_json()
        return resp.status_code, resp.get_json()

    def _set_verified_device(self, db_path, miner, family, arch):
        # Pin fingerprint_passed=1 and a recent MAC so enrollment takes the real
        # reward path (a failed fingerprint / missing MAC would zero or gate the
        # weight and mask the multiplier-selection behavior this test targets).
        now = int(time.time())
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE miner_attest_recent "
                "SET device_family=?, device_arch=?, fingerprint_passed=1 WHERE miner=?",
                (family, arch, miner),
            )
            conn.execute(
                "INSERT OR REPLACE INTO miner_macs "
                "(miner, mac_hash, first_ts, last_ts, count) VALUES (?, ?, ?, ?, 1)",
                (miner, "aa" * 6, now, now),
            )
            conn.commit()

    def _current_epoch(self, mod):
        with mod.app.test_request_context("/epoch", method="GET"):
            return mod.get_epoch().get_json()["epoch"]

    def test_spoofed_device_cannot_inflate_weight(self):
        """Enroll body claiming a high-multiplier arch must NOT raise the reward
        weight above the miner's attested (verified) hardware tier."""
        mod, db_path = self._load("rc_enroll_spoof", "enroll_spoof.db")

        honest_w = mod.HARDWARE_WEIGHTS[self.HONEST_FAMILY][self.HONEST_ARCH]
        spoof_w = mod.HARDWARE_WEIGHTS[self.SPOOF_FAMILY][self.SPOOF_ARCH]
        self.assertLess(honest_w, spoof_w, "test fixture must span a real weight gap")

        miner = "RTC_SPOOFER"
        miner_id = "miner_spoof_1"
        signing_key = self._attest(mod, miner, miner_id)
        # Pin the node's *verified* view of this miner's hardware to honest x86.
        self._set_verified_device(db_path, miner, self.HONEST_FAMILY, self.HONEST_ARCH)

        epoch = self._current_epoch(mod)
        sig_hex, enroll_pubkey = _sign_enrollment(miner, miner_id, epoch, signing_key)
        status, body = self._enroll(mod, {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            # Attacker claims a 4.0x arch it never attested to.
            "device": {"family": self.SPOOF_FAMILY, "arch": self.SPOOF_ARCH},
            "signature": sig_hex,
            "public_key": enroll_pubkey,
        })

        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"], body)
        # The reward multiplier is bound to the attested hardware, not the body.
        self.assertEqual(body["hw_weight"], honest_w,
                         f"weight should follow verified {self.HONEST_ARCH}={honest_w}")
        self.assertNotEqual(body["hw_weight"], spoof_w,
                            "spoofed body device must not set the reward weight")
        # The honest multiplier produces a positive epoch weight (real reward
        # path, not the failed-fingerprint zero-weight branch). weight_units =
        # epoch_weight_to_units(hw_weight * active_ratio), so hw_weight is what
        # scales the miner's share of the fixed epoch pot.
        self.assertGreater(body["weight"], 0.0, "honest miner should have positive weight")

    def test_legacy_miner_without_verified_device_falls_back_to_body(self):
        """A pre-migration row with no stored verified device must still honor the
        body device, so deployed legacy miners are not regressed to weight 1.0."""
        mod, db_path = self._load("rc_enroll_legacy", "enroll_legacy.db")

        miner = "RTC_LEGACY"
        miner_id = "miner_legacy_1"
        signing_key = self._attest(mod, miner, miner_id)
        # Simulate a legacy/pre-migration attestation row: no verified device.
        self._set_verified_device(db_path, miner, None, None)

        epoch = self._current_epoch(mod)
        sig_hex, enroll_pubkey = _sign_enrollment(miner, miner_id, epoch, signing_key)
        body_w = mod.HARDWARE_WEIGHTS[self.SPOOF_FAMILY][self.SPOOF_ARCH]
        status, body = self._enroll(mod, {
            "miner_pubkey": miner,
            "miner_id": miner_id,
            "device": {"family": self.SPOOF_FAMILY, "arch": self.SPOOF_ARCH},
            "signature": sig_hex,
            "public_key": enroll_pubkey,
        })

        self.assertEqual(status, 200, body)
        self.assertEqual(body["hw_weight"], body_w,
                         "legacy row with no verified device should use body device")


if __name__ == "__main__":
    unittest.main(verbosity=2)
