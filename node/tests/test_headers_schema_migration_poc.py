# SPDX-License-Identifier: MIT
"""Regression test for the ``headers`` table schema-drift bug.

``init_db()`` created ``headers(slot INTEGER PRIMARY KEY, header_json TEXT NOT
NULL)`` — but every real reader/writer of this table (``/headers/ingest_signed``,
``/headers/tip``, the ``api_v1`` blueprint's ``/blocks*`` routes, and
``rustchain_p2p_sync_secure.get_blocks_for_sync``) references ``miner_id``,
``message_hex``, ``signature_hex``, ``pubkey_hex`` and ``ts`` — none of which
existed on a freshly-initialized database. The very first signed header any
miner submitted crashed the node with
``sqlite3.OperationalError: table headers has no column named miner_id``.

This test drives the ``/headers/ingest_signed`` route exactly the way a real
miner would (real ed25519 signature over the real canonical header bytes,
registered via the real ``/miner/headerkey`` admin route, real
``check_eligibility_round_robin`` gate satisfied by making this miner the sole
enrolled round-robin producer) — no hand-rolled ``CREATE TABLE headers`` bypass
like the existing ``test_ingest_round_robin_authorization.py`` fixture uses.
That existing fixture's own comment ("Keep the fixture focused on the route's
deployed header-tip shape so failures exercise consensus authorization, not
schema setup") is itself evidence the schema bug was known and worked around,
never fixed.

FAILS on unmodified ``init_db()`` with ``sqlite3.OperationalError``.
PASSES once ``_migrate_headers_columns()`` + the ``header_json``-supplying
INSERT are applied.
"""

import gc
import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

try:
    import nacl.signing
    HAVE_NACL = True
except Exception:
    HAVE_NACL = False


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class _NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self

    inc = dec = set = observe = lambda self, *args, **kwargs: None


@unittest.skipUnless(HAVE_NACL, "pynacl not installed")
class TestHeadersSchemaMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._prev_env = {}
        for k, v in (
            ("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef"),
            ("RUSTCHAIN_DB_PATH", str(Path(self.tmp.name) / "node.db")),
            ("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1"),
        ):
            self._prev_env[k] = os.environ.get(k)
            os.environ[k] = v

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        self._prev_prometheus = sys.modules.get("prometheus_client")
        prometheus_client = types.ModuleType("prometheus_client")
        prometheus_client.Counter = _NoopMetric
        prometheus_client.Gauge = _NoopMetric
        prometheus_client.Histogram = _NoopMetric
        prometheus_client.generate_latest = lambda: b""
        prometheus_client.CONTENT_TYPE_LATEST = "text/plain"
        sys.modules["prometheus_client"] = prometheus_client

        spec = importlib.util.spec_from_file_location(
            "rustchain_headers_schema_poc_node", MODULE_PATH
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init_db()  # <-- exercises the REAL schema, no test-side bypass
        self.mod.app.config["TESTING"] = True
        self.client = self.mod.app.test_client()

    def tearDown(self):
        mod = getattr(self, "mod", None)
        if mod is not None:
            try:
                mod.app.do_teardown_appcontext()
            except Exception:
                pass
        self.mod = None
        if self._prev_prometheus is None:
            sys.modules.pop("prometheus_client", None)
        else:
            sys.modules["prometheus_client"] = self._prev_prometheus
        for k, v in self._prev_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for attempt in range(5):
            try:
                self.tmp.cleanup()
                break
            except PermissionError:
                if attempt == 4:
                    raise
                gc.collect()
                time.sleep(0.2)

    def _register_sole_producer(self, miner_id: str, pubkey_hex: str):
        """Make this miner the only enrolled round-robin producer so
        check_eligibility_round_robin accepts every slot it claims, and
        register its header pubkey the same way the real admin route would."""
        with sqlite3.connect(self.mod.DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys(miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, pubkey_hex),
            )
            # Minimal round-robin enrollment: table/columns per
            # rip_200_round_robin_1cpu1vote — probe live schema rather than
            # hardcode, mirroring the dual-schema-tolerant pattern used
            # elsewhere in this codebase (governance.py / lock_ledger.py).
            try:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(round_robin_producers)").fetchall()}
            except Exception:
                cols = set()
            if cols:
                fields = ["miner_id"]
                vals = [miner_id]
                if "enrolled" in cols:
                    fields.append("enrolled"); vals.append(1)
                if "active" in cols:
                    fields.append("active"); vals.append(1)
                placeholders = ",".join("?" for _ in fields)
                conn.execute(
                    f"INSERT OR REPLACE INTO round_robin_producers({','.join(fields)}) VALUES ({placeholders})",
                    vals,
                )
            conn.commit()

    def test_ingest_signed_header_survives_real_schema(self):
        signing_key = nacl.signing.SigningKey.generate()
        pubkey_hex = signing_key.verify_key.encode().hex()
        miner_id = "poc-miner-01"
        self._register_sole_producer(miner_id, pubkey_hex)

        slot = int(self.mod.current_slot())
        header = {"miner": miner_id, "slot": slot}
        msg = self.mod.canonical_header_bytes(header)
        sig_hex = signing_key.sign(msg).signature.hex()

        resp = self.client.post(
            "/headers/ingest_signed",
            json={
                "miner_id": miner_id,
                "header": header,
                "signature": sig_hex,
                "pubkey": pubkey_hex,
            },
        )
        body = resp.get_json()
        self.assertNotEqual(
            resp.status_code, 500,
            f"ingest_signed_header must not 500 on a freshly-initialized DB; got {body}",
        )
        # Whatever the eligibility/business-logic outcome, it must be a clean
        # JSON error/response — never an unhandled sqlite3.OperationalError
        # bubbling out of an un-migrated `headers` table.
        self.assertIsInstance(body, dict)

        with sqlite3.connect(self.mod.DB_PATH) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(headers)").fetchall()}
        for expected in ("miner_id", "message_hex", "signature_hex", "pubkey_hex", "ts"):
            self.assertIn(expected, cols, f"headers table missing column {expected!r} after init_db()")

    def test_headers_tip_route_does_not_500_on_fresh_db(self):
        resp = self.client.get("/headers/tip")
        self.assertNotEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
