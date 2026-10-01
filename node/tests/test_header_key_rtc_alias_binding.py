# SPDX-License-Identifier: MIT
"""Header-key binding for RTC-address identities via the miner_id alias.

/attest/submit and /epoch/enroll register the caller's Ed25519 key as a
block-header key for both the canonical identity and the caller-supplied
``miner_id`` compatibility alias. An RTC address (``RTC`` + 40 hex) is
self-certifying, so a key may only be bound to it when the address derives from
that key, when the exact pair is already registered (pre-existing compatibility
rows stay idempotent), or when an admin pre-approved the pair. Named aliases
(``modern-shadow`` and friends) keep their existing bootstrap behaviour.
"""
import hashlib
import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

try:
    import nacl.signing
    HAVE_NACL = True
except ImportError:  # pragma: no cover - environment without pynacl
    HAVE_NACL = False

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


def _addr(pk_hex):
    return "RTC" + hashlib.sha256(bytes.fromhex(pk_hex)).hexdigest()[:40]


def _new_key():
    sk = nacl.signing.SigningKey.generate()
    return sk, sk.verify_key.encode().hex()


def _header_rows(db_path, identity):
    with sqlite3.connect(db_path) as conn:
        return [r[0] for r in conn.execute(
            "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id=?", (identity,)
        ).fetchall()]


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class RtcAliasHeaderKeyBindingTest(unittest.TestCase):
    _counter = 0

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._saved_env = {k: os.environ.get(k) for k in (
            "RUSTCHAIN_DB_PATH", "RC_ADMIN_KEY", "RTC_ATTEST_ENFORCE_MODE",
            "RC_HEADER_KEY_STRICT_BOOTSTRAP", "RUSTCHAIN_DISABLE_P2P_AUTO_START",
        )}
        self.db_path = os.path.join(self._tmp.name, "alias.db")
        os.environ["RUSTCHAIN_DB_PATH"] = self.db_path
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        os.environ.pop("RTC_ATTEST_ENFORCE_MODE", None)
        os.environ.pop("RC_HEADER_KEY_STRICT_BOOTSTRAP", None)
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        RtcAliasHeaderKeyBindingTest._counter += 1
        spec = importlib.util.spec_from_file_location(
            "rc_alias_binding_%d" % RtcAliasHeaderKeyBindingTest._counter, MODULE_PATH)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init_db()
        self.mod.app.config["TESTING"] = True
        self.client = self.mod.app.test_client()

        self.attacker_sk, self.attacker_pk = _new_key()
        self.attacker_wallet = _addr(self.attacker_pk)
        self.victim_sk, self.victim_pk = _new_key()
        self.victim_wallet = _addr(self.victim_pk)   # keyless victim wallet
        assert self.mod.address_from_pubkey(self.victim_pk) == self.victim_wallet

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    # ---------------------------------------------------------------- helpers
    def _challenge(self):
        resp = self.client.post("/attest/challenge", json={})
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return resp.get_json()["nonce"]

    def _attest(self, sk, pk, miner, miner_id):
        nonce = self._challenge()
        commitment = "deadbeef"
        self._attest_n = getattr(self, "_attest_n", 0) + 1  # distinct fingerprint per call (replay defense)
        msg = "{}|{}|{}|{}".format(miner_id, miner, nonce, commitment).encode()
        payload = {
            "miner": miner,
            "miner_id": miner_id,
            "report": {"nonce": nonce, "commitment": commitment},
            "device": {"family": "x86_64", "arch": "default", "model": "test-box", "cores": 4},
            "signals": {"hostname": "test-host", "macs": []},
            "fingerprint": {
                "checks": {
                    "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
                    "clock_drift": {"passed": True, "data": {"cv": 0.05 + self._attest_n / 1000.0,
                                                            "samples": 64 + self._attest_n}},
                },
                "all_passed": True,
            },
            "signature": sk.sign(msg).signature.hex(),
            "public_key": pk,
            "signature_type": "legacy",
        }
        return self.client.post("/attest/submit", json=payload)

    def _enroll(self, sk, pk, miner_pk, miner_id):
        epoch = self.mod.slot_to_epoch(self.mod.current_slot())
        msg = "{}|{}|{}".format(miner_pk, miner_id, epoch).encode()
        return self.client.post("/epoch/enroll", json={
            "miner_pubkey": miner_pk,
            "miner_id": miner_id,
            "signature": sk.sign(msg).signature.hex(),
            "public_key": pk,
        })

    def _seed_signing_pubkey(self, miner, pk):
        with sqlite3.connect(self.db_path) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(miner_attest_recent)")]
            self.assertIn("signing_pubkey", cols)
            conn.execute(
                "INSERT OR REPLACE INTO miner_attest_recent "
                "(miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, signing_pubkey) "
                "VALUES (?, strftime('%s','now'), 'x86_64', 'default', 0.5, 1, ?)",
                (miner, pk),
            )
            conn.commit()

    # ----------------------------------------------------------- attest path
    def _assert_attest_alias_blocked(self, mode):
        if mode:
            os.environ["RTC_ATTEST_ENFORCE_MODE"] = mode
        resp = self._attest(self.attacker_sk, self.attacker_pk,
                            miner=self.attacker_wallet, miner_id=self.victim_wallet)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        # attacker's own (derived) wallet still gets its key ...
        self.assertEqual(_header_rows(self.db_path, self.attacker_wallet), [self.attacker_pk])
        # ... but no key is bound to the victim wallet via the alias
        self.assertEqual(_header_rows(self.db_path, self.victim_wallet), [])
        # ... and the refusal is reported without failing the attestation
        self.assertEqual(resp.get_json().get("header_key_skipped"), [
            {"identity": self.victim_wallet, "reason": "rtc_identity_requires_derived_key"}])

    def test_attest_alias_cannot_bind_victim_wallet_log_only(self):
        self._assert_attest_alias_blocked(None)

    def test_attest_alias_cannot_bind_victim_wallet_enforce_new(self):
        self._assert_attest_alias_blocked("enforce_new")

    def test_attest_alias_cannot_bind_victim_wallet_enforce_all(self):
        self._assert_attest_alias_blocked("enforce_all")

    def test_attest_as_victim_wallet_with_foreign_key_binds_nothing_log_only(self):
        """log_only tolerates a non-deriving key on attest; it must still not
        become a header key for that wallet."""
        resp = self._attest(self.attacker_sk, self.attacker_pk,
                            miner=self.victim_wallet, miner_id=self.victim_wallet)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(_header_rows(self.db_path, self.victim_wallet), [])

    def test_attest_uppercase_lookalike_alias_not_bound(self):
        lookalike = "RTC" + self.victim_wallet[3:].upper()
        resp = self._attest(self.attacker_sk, self.attacker_pk,
                            miner=self.attacker_wallet, miner_id=lookalike)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(_header_rows(self.db_path, lookalike), [])
        self.assertEqual(resp.get_json().get("header_key_skipped"), [
            {"identity": lookalike, "reason": "rtc_identity_requires_derived_key"}])

    def test_attest_case_variant_of_own_wallet_is_allowed(self):
        """Derivation is compared case-insensitively: an upper-case spelling of
        the key holder's OWN wallet is still theirs."""
        own_variant = "RTC" + self.attacker_wallet[3:].upper()
        resp = self._attest(self.attacker_sk, self.attacker_pk,
                            miner=self.attacker_wallet, miner_id=own_variant)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(_header_rows(self.db_path, own_variant), [self.attacker_pk])
        self.assertNotIn("header_key_skipped", resp.get_json())

    def test_attest_derived_key_registers_and_is_idempotent(self):
        for _ in range(2):
            resp = self._attest(self.victim_sk, self.victim_pk,
                                miner=self.victim_wallet, miner_id="victim-rig-01")
            self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
            self.assertNotIn("header_key_skipped", resp.get_json())
        self.assertEqual(_header_rows(self.db_path, self.victim_wallet), [self.victim_pk])
        # named compatibility alias registered exactly as before
        self.assertEqual(_header_rows(self.db_path, "victim-rig-01"), [self.victim_pk])

    def test_attest_named_alias_first_registration_unchanged(self):
        resp = self._attest(self.attacker_sk, self.attacker_pk,
                            miner=self.attacker_wallet, miner_id="modern-newrig")
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(_header_rows(self.db_path, "modern-newrig"), [self.attacker_pk])

    def test_existing_legacy_non_derived_pair_still_reregisters(self):
        """Simulates one of the pre-existing compatibility rows: a machine key
        shared with a named miner id, registered under the owner's wallet."""
        machine_sk, machine_pk = _new_key()
        owner_wallet = self.victim_wallet
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                         (owner_wallet, machine_pk))
            conn.execute("INSERT INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                         ("modern-shadow", machine_pk))
            conn.commit()
        resp = self._attest(machine_sk, machine_pk, miner=owner_wallet, miner_id="modern-shadow")
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(_header_rows(self.db_path, owner_wallet), [machine_pk])
        self.assertEqual(_header_rows(self.db_path, "modern-shadow"), [machine_pk])
        with sqlite3.connect(self.db_path) as conn:
            self.assertTrue(self.mod._register_header_key(conn, owner_wallet, machine_pk))
            self.assertEqual(self.mod._register_header_key_identities(
                conn, machine_pk, (owner_wallet, "modern-shadow")), [owner_wallet, "modern-shadow"])

    # ----------------------------------------------------------- enroll path
    def _enroll_ready(self):
        # Attestation/MAC gating is covered elsewhere; isolate the key binding.
        self.mod.check_enrollment_requirements = lambda miner: (True, {})

    def test_enroll_alias_cannot_bind_victim_wallet(self):
        self._enroll_ready()
        self._seed_signing_pubkey(self.attacker_wallet, self.attacker_pk)
        resp = self._enroll(self.attacker_sk, self.attacker_pk,
                            miner_pk=self.attacker_wallet, miner_id=self.victim_wallet)
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json()["ok"])
        self.assertEqual(_header_rows(self.db_path, self.attacker_wallet), [self.attacker_pk])
        self.assertEqual(_header_rows(self.db_path, self.victim_wallet), [])
        self.assertEqual(resp.get_json().get("header_key_skipped"), [
            {"identity": self.victim_wallet, "reason": "rtc_identity_requires_derived_key"}])

    def test_enroll_derived_key_succeeds_and_is_idempotent(self):
        self._enroll_ready()
        self._seed_signing_pubkey(self.victim_wallet, self.victim_pk)
        for _ in range(2):
            resp = self._enroll(self.victim_sk, self.victim_pk,
                                miner_pk=self.victim_wallet, miner_id="victim-rig-01")
            self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
            self.assertNotIn("header_key_skipped", resp.get_json())
        self.assertEqual(_header_rows(self.db_path, self.victim_wallet), [self.victim_pk])
        self.assertEqual(_header_rows(self.db_path, "victim-rig-01"), [self.victim_pk])

    # --------------------------------------------- authorization unit checks
    def test_existing_pair_lookup_error_still_consults_allowlist(self):
        """A failing miner_header_keys lookup must not short-circuit to deny:
        an admin pre-approval still counts; with neither, fail closed."""

        class _KeysTableBroken:
            def __init__(self, real):
                self._real = real

            def execute(self, sql, *args):
                if "FROM miner_header_keys" in sql:
                    raise sqlite3.OperationalError("database is locked")
                return self._real.execute(sql, *args)

        with sqlite3.connect(self.db_path) as real:
            broken = _KeysTableBroken(real)
            permitted = self.mod._rtc_identity_header_key_permitted
            self.assertFalse(permitted(broken, self.victim_wallet, self.attacker_pk))
            real.execute("INSERT INTO miner_header_bootstrap (miner_id, pubkey_hex) VALUES (?, ?)",
                         (self.victim_wallet, self.attacker_pk))
            self.assertTrue(permitted(broken, self.victim_wallet, self.attacker_pk))
            # derivation needs no DB at all
            self.assertTrue(permitted(broken, self.victim_wallet, self.victim_pk))

    def test_case_insensitive_derivation_rules(self):
        with sqlite3.connect(self.db_path) as conn:
            permitted = self.mod._rtc_identity_header_key_permitted
            own_upper = "RTC" + self.victim_wallet[3:].upper()
            self.assertTrue(permitted(conn, own_upper, self.victim_pk))
            self.assertTrue(self.mod._header_key_authorized(conn, own_upper, self.victim_pk))
            foreign_upper = "RTC" + self.attacker_wallet[3:].upper()
            self.assertFalse(permitted(conn, foreign_upper, self.victim_pk))
            self.assertFalse(self.mod._header_key_authorized(conn, foreign_upper, self.victim_pk))
    def test_authorization_rules_for_rtc_identity(self):
        with sqlite3.connect(self.db_path) as conn:
            auth = self.mod._header_key_authorized
            # strict bootstrap OFF (default): still no TOFU for RTC identities
            self.assertFalse(auth(conn, self.victim_wallet, self.attacker_pk))
            os.environ["RC_HEADER_KEY_STRICT_BOOTSTRAP"] = "1"
            self.assertFalse(auth(conn, self.victim_wallet, self.attacker_pk))
            os.environ.pop("RC_HEADER_KEY_STRICT_BOOTSTRAP", None)
            self.assertTrue(auth(conn, self.victim_wallet, self.victim_pk))
            # admin pre-approved pair is honoured
            conn.execute("INSERT INTO miner_header_bootstrap (miner_id, pubkey_hex) VALUES (?, ?)",
                         (self.victim_wallet, self.attacker_pk))
            self.assertTrue(auth(conn, self.victim_wallet, self.attacker_pk))
            # named alias first key: unchanged TOFU while strict is off
            self.assertTrue(auth(conn, "modern-brandnew", self.attacker_pk))

    # ------------------------------------------------------------ ingest path
    def test_ingest_signed_rejects_attacker_header_for_victim(self):
        self._attest(self.attacker_sk, self.attacker_pk,
                     miner=self.attacker_wallet, miner_id=self.victim_wallet)
        self._enroll_ready()
        self._seed_signing_pubkey(self.attacker_wallet, self.attacker_pk)
        self._enroll(self.attacker_sk, self.attacker_pk,
                     miner_pk=self.attacker_wallet, miner_id=self.victim_wallet)
        header = {"miner": self.victim_wallet, "slot": 1, "prev_hash": "00" * 32,
                  "timestamp": 1700000000}
        msg = self.mod.canonical_header_bytes(header)
        resp = self.client.post("/headers/ingest_signed", json={
            "miner_id": self.victim_wallet,
            "header": header,
            "signature": self.attacker_sk.sign(msg).signature.hex(),
        })
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json().get("error"), "no pubkey registered for miner")

    def test_admin_headerkey_override_still_binds_non_derived_key(self):
        """The admin path (/miner/headerkey, RC_ADMIN_KEY) can still bind a
        NON-derived key to an RTC identity (rotation/override), and that key is
        then accepted by /headers/ingest_signed."""
        machine_sk, machine_pk = _new_key()
        self.assertNotEqual(_addr(machine_pk), self.victim_wallet)
        unauth = self.client.post("/miner/headerkey", json={
            "miner_id": self.victim_wallet, "pubkey_hex": machine_pk})
        self.assertEqual(unauth.status_code, 403)
        resp = self.client.post(
            "/miner/headerkey",
            json={"miner_id": self.victim_wallet, "pubkey_hex": machine_pk},
            headers={"X-API-Key": os.environ["RC_ADMIN_KEY"]},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(_header_rows(self.db_path, self.victim_wallet), [machine_pk])
        # re-registration through attest stays idempotent for the admin-set pair
        with sqlite3.connect(self.db_path) as conn:
            self.assertTrue(self.mod._header_key_authorized(conn, self.victim_wallet, machine_pk))

        slot = self.mod.current_slot()
        header = {"miner": self.victim_wallet, "slot": slot, "prev_hash": "00" * 32,
                  "timestamp": 1700000000}
        msg = self.mod.canonical_header_bytes(header)

        def _ingest(sk):
            return self.client.post("/headers/ingest_signed", json={
                "miner_id": self.victim_wallet,
                "header": header,
                "signature": sk.sign(msg).signature.hex(),
            })

        # Slot-producer rotation is covered by test_ingest_round_robin_authorization;
        # make this identity the producer so the test isolates key acceptance.
        with mock.patch("rip_200_round_robin_1cpu1vote.check_eligibility_round_robin",
                        return_value={"eligible": True}):
            self.assertEqual(_ingest(self.attacker_sk).status_code, 400)  # unregistered key
            ok = _ingest(machine_sk)
        self.assertEqual(ok.status_code, 200, ok.get_data(as_text=True))
        self.assertTrue(ok.get_json().get("ok"), ok.get_data(as_text=True))
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT pubkey_hex FROM headers WHERE miner_id=? AND slot=?",
                               (self.victim_wallet, slot)).fetchone()
        self.assertEqual(row, (machine_pk,))


class WsgiRouteRegistrationTest(unittest.TestCase):
    """The routes must be live under gunicorn (wsgi:app), not only in __main__."""

    def test_routes_registered_on_wsgi_app(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            env = dict(os.environ)
            env.update({
                "RUSTCHAIN_DB_PATH": os.path.join(tmp, "wsgi.db"),
                "DB_PATH": os.path.join(tmp, "wsgi.db"),
                "RC_ADMIN_KEY": "0123456789abcdef0123456789abcdef",
                "RUSTCHAIN_DISABLE_P2P_AUTO_START": "1",
                "RC_RUNTIME_ENV": "test",
                "RC_P2P_SECRET": env.get("RC_P2P_SECRET")
                or "ci-test-secret-00000000000000000000000000000000",
            })
            script = textwrap.dedent("""
                import importlib.util, os, sys
                node = sys.argv[1]
                sys.path.insert(0, node)
                spec = importlib.util.spec_from_file_location("wsgi_under_test", os.path.join(node, "wsgi.py"))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                rules = {r.rule: r.methods for r in mod.app.url_map.iter_rules()}
                for path in ("/epoch/enroll", "/attest/submit", "/headers/ingest_signed"):
                    assert path in rules and "POST" in rules[path], path
                print("WSGI_ROUTES_OK", flush=True)
                os._exit(0)  # do not wait on background P2P threads
            """)
            proc = subprocess.run([sys.executable, "-c", script, NODE_DIR], env=env, cwd=tmp,
                                  capture_output=True, text=True, timeout=180)
            self.assertIn("WSGI_ROUTES_OK", proc.stdout, proc.stdout[-2000:] + proc.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
