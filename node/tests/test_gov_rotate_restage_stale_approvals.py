"""Regression: governance-rotation approvals must bind to the staged member set.

/gov/rotate/approve verifies an Ed25519 signature over the canonical message
    ROTATE|{epoch}|{threshold}|sha256(members_json)
i.e. the signature authorizes ONE specific (threshold, member-set) proposal.

/gov/rotate/stage uses INSERT OR REPLACE on gov_rotation_proposals, so a proposal
for an epoch can be replaced in place with a DIFFERENT member set / threshold.
The bug: stage does NOT clear previously collected gov_rotation_approvals, and
/gov/rotate/commit only counts rows in gov_rotation_approvals -- it never
re-verifies the stored signatures against the CURRENT members_json. Result: a
signature that only ever authorized member-set A is counted toward committing an
entirely different member-set B. The multisig gate is bypassed.

This drives the real Flask endpoints. It must FAIL on current main (commit of the
re-staged set B succeeds with a stale approval) and PASS once stage clears stale
approvals for the epoch (approvals must be re-collected for the new message).
"""

import gc
import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

from nacl.signing import SigningKey

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


class TestGovRotateRestageStaleApprovals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="gov-rotate-restage-")
        cls._prev_db = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin = os.environ.get("RC_ADMIN_KEY")
        cls._db_path = os.path.join(cls._tmp, "gov.db")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db_path
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rc_integrated_gov_rotate_test", MODULE_PATH
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.init_db()  # create gov_rotation* / gov_signers tables
        cls.client = cls.mod.app.test_client()

        # Seed two active governance signers with known keypairs.
        cls.sk1 = SigningKey.generate()
        cls.sk2 = SigningKey.generate()
        cls.pub1 = cls.sk1.verify_key.encode().hex()
        cls.pub2 = cls.sk2.verify_key.encode().hex()
        con = sqlite3.connect(cls._db_path)
        con.execute(
            "INSERT OR REPLACE INTO gov_signers(signer_id, pubkey_hex, active) VALUES(1, ?, 1)",
            (cls.pub1,),
        )
        con.execute(
            "INSERT OR REPLACE INTO gov_signers(signer_id, pubkey_hex, active) VALUES(2, ?, 1)",
            (cls.pub2,),
        )
        con.commit()
        con.close()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.mod.app.do_teardown_appcontext()
        except Exception:
            pass
        cls.client = None
        cls.mod = None
        for key, prev in (("RUSTCHAIN_DB_PATH", cls._prev_db),
                          ("RC_ADMIN_KEY", cls._prev_admin)):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        gc.collect()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _stage(self, epoch, threshold, members):
        return self.client.post(
            "/gov/rotate/stage",
            json={"epoch_effective": epoch, "threshold": threshold, "members": members},
            headers={"X-Admin-Key": ADMIN_KEY},
        )

    def _approve(self, epoch, signer_id, sk, message):
        sig_hex = sk.sign(message.encode()).signature.hex()
        return self.client.post(
            "/gov/rotate/approve",
            json={"epoch_effective": epoch, "signer_id": signer_id, "sig_hex": sig_hex},
        )

    def _commit(self, epoch):
        return self.client.post("/gov/rotate/commit", json={"epoch_effective": epoch})

    def test_happy_path_commit_succeeds(self):
        """Control: a stage -> approve -> commit with no re-stage must succeed,
        so the fix does not break legitimate rotations."""
        epoch = 111111
        r = self._stage(epoch, 1, [{"signer_id": 1, "pubkey_hex": self.pub1}])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        msg = r.get_json()["message"]
        ra = self._approve(epoch, 1, self.sk1, msg)
        self.assertEqual(ra.status_code, 200, ra.get_data(as_text=True))
        rc = self._commit(epoch)
        self.assertEqual(rc.status_code, 200, rc.get_data(as_text=True))
        self.assertTrue(rc.get_json().get("ok"))
        self.assertEqual(rc.get_json().get("committed"), 1)

    def test_restage_different_members_invalidates_stale_approvals(self):
        """A signature over member-set A must NOT authorize committing set B."""
        epoch = 222222

        # Stage A and collect a valid approval (signature over message_A).
        r = self._stage(epoch, 1, [{"signer_id": 1, "pubkey_hex": self.pub1}])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        msg_a = r.get_json()["message"]
        ra = self._approve(epoch, 1, self.sk1, msg_a)
        self.assertEqual(ra.status_code, 200, ra.get_data(as_text=True))
        self.assertTrue(ra.get_json().get("ready"))

        # Re-stage the SAME epoch with a DIFFERENT member set (message changes).
        r2 = self._stage(epoch, 1, [{"signer_id": 2, "pubkey_hex": self.pub2}])
        self.assertEqual(r2.status_code, 200, r2.get_data(as_text=True))
        self.assertNotEqual(
            msg_a, r2.get_json()["message"],
            "re-stage must change the canonical signing message",
        )

        # Commit must NOT succeed: no signature authorizes the new set B.
        rc = self._commit(epoch)
        self.assertNotEqual(
            rc.status_code, 200,
            "commit of a re-staged member set succeeded using a stale approval "
            "that only ever signed the previous set (multisig bypass): "
            + rc.get_data(as_text=True),
        )
        self.assertFalse(rc.get_json().get("ok"))
        self.assertEqual(rc.get_json().get("reason"), "insufficient_approvals")


if __name__ == "__main__":
    unittest.main()
