import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


def load_integrated_module(db_path: str):
    os.environ.setdefault("RC_ADMIN_KEY", "test-admin-key-" + "0" * 32)
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    sys.path.insert(0, str(NODE_DIR))
    sys.modules.pop("payout_preflight", None)
    spec = importlib.util.spec_from_file_location(
        "rustchain_integrated_governance_vote_race_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_PATH = db_path
    module.app.config["DB_PATH"] = db_path
    module.app.config["TESTING"] = True
    return module


def test_governance_vote_duplicate_insert_race_returns_409(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "governance.db")
        mod = load_integrated_module(db_path)

        monkeypatch.setattr(mod, "verify_rtc_signature", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(mod, "address_from_pubkey", lambda _public_key: "RTCwallet")

        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            mod._ensure_governance_tables(cur)
            conn.execute(
                """
                INSERT INTO governance_proposals
                (id, proposer_wallet, title, description, created_at, activated_at, ends_at, status)
                VALUES (1, 'RTCproposer', 'race', 'duplicate vote race', 1, 1, ?, 'active')
                """,
                (2_000_000_000,),
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER,
                    device_family TEXT,
                    device_arch TEXT
                )
                """
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
            )
            conn.execute(
                "INSERT INTO miner_attest_recent VALUES ('RTCwallet', ?, 'default', 'default')",
                (2_000_000_000,),
            )
            conn.execute("INSERT INTO balances VALUES ('RTCwallet', 1000000)")

        original_connect = mod.sqlite3.connect

        class RaceCursor:
            def __init__(self, cursor):
                self._cursor = cursor

            def execute(self, sql, params=()):
                normalized = " ".join(sql.split())
                if normalized.startswith("SELECT 1 FROM governance_votes"):
                    return EmptyResult()
                if normalized.startswith("INSERT INTO governance_votes"):
                    raise sqlite3.IntegrityError("UNIQUE constraint failed")
                return self._cursor.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._cursor, name)

        class RaceConnection:
            def __init__(self, path):
                self._conn = original_connect(path)

            def __enter__(self):
                self._conn.__enter__()
                return self

            def __exit__(self, *args):
                return self._conn.__exit__(*args)

            def cursor(self):
                return RaceCursor(self._conn.cursor())

            def __getattr__(self, name):
                return getattr(self._conn, name)

            @property
            def row_factory(self):
                return self._conn.row_factory

            @row_factory.setter
            def row_factory(self, value):
                self._conn.row_factory = value

        class EmptyResult:
            def fetchone(self):
                return None

        monkeypatch.setattr(mod.sqlite3, "connect", lambda path: RaceConnection(path))

        client = mod.app.test_client()
        response = client.post("/governance/vote", json={
            "proposal_id": 1,
            "wallet": "RTCwallet",
            "vote": "yes",
            "nonce": "race-nonce",
            "signature": "aa" * 64,
            "public_key": "bb" * 32,
        })

        assert response.status_code == 409
        assert response.get_json() == {"ok": False, "error": "already_voted"}
