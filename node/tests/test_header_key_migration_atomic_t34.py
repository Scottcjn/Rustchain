"""T3.4 regression: the miner_header_keys composite-PK migration must be ATOMIC.

The rebuild renames the legacy single-PK table, creates a composite-PK table, copies
rows, then drops the legacy table. If a crash/error lands after the RENAME but before
the DROP, the original table is renamed away and a fresh EMPTY composite table sits in
its place — on restart the migration check sees the composite PK and SKIPS, stranding
every key in *_legacy_single (silent loss of the block-header trust anchor). The
SAVEPOINT wrap makes the rebuild all-or-nothing: ROLLBACK TO restores the original
table intact for a clean retry.
"""
import importlib.util
import os
import sqlite3
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class _FailOn:
    """Connection proxy that raises on the first statement containing `needle`."""
    def __init__(self, real, needle):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_needle", needle)
        object.__setattr__(self, "_tripped", False)

    def execute(self, sql, *args):
        if not self._tripped and self._needle in sql:
            object.__setattr__(self, "_tripped", True)
            raise sqlite3.OperationalError(f"injected failure at: {self._needle}")
        return self._real.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._real, name)


class HeaderKeyMigrationAtomicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ.setdefault("RUSTCHAIN_DB_PATH", os.path.join(cls._tmp.name, "t34.db"))
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ.setdefault("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")
        spec = importlib.util.spec_from_file_location("rcnode_t34_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _legacy_db(self, extra_col=False, rows=()):
        c = sqlite3.connect(":memory:")
        if extra_col:
            c.execute("CREATE TABLE miner_header_keys (miner_id TEXT PRIMARY KEY, "
                      "pubkey_hex TEXT NOT NULL, added_at INTEGER DEFAULT 0)")
            for mid, pk, ts in rows:
                c.execute("INSERT INTO miner_header_keys VALUES (?,?,?)", (mid, pk, ts))
        else:
            c.execute("CREATE TABLE miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)")
            for mid, pk in rows:
                c.execute("INSERT INTO miner_header_keys VALUES (?,?)", (mid, pk))
        c.commit()
        return c

    def _pk_cols(self, c):
        return [r[1] for r in c.execute("PRAGMA table_info(miner_header_keys)").fetchall() if r[5]]

    def _tables(self, c):
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    # --- happy path --------------------------------------------------------
    def test_migrates_legacy_single_pk_preserving_rows(self):
        c = self._legacy_db(rows=[("g4-115", "aa" * 32), ("g5-179", "bb" * 32)])
        self.assertEqual(self._pk_cols(c), ["miner_id"])  # legacy single PK
        self.mod._migrate_miner_header_keys_composite(c)
        self.assertEqual(set(self._pk_cols(c)), {"miner_id", "pubkey_hex"})  # composite now
        rows = set(c.execute("SELECT miner_id, pubkey_hex FROM miner_header_keys").fetchall())
        self.assertEqual(rows, {("g4-115", "aa" * 32), ("g5-179", "bb" * 32)})
        self.assertNotIn("miner_header_keys_legacy_single", self._tables(c))

    def test_multidevice_allowed_after_migration(self):
        """The whole point: composite PK lets one miner_id hold multiple device keys."""
        c = self._legacy_db(rows=[("power8", "11" * 32)])
        self.mod._migrate_miner_header_keys_composite(c)
        c.execute("INSERT INTO miner_header_keys (miner_id, pubkey_hex) VALUES ('power8', ?)", ("22" * 32,))
        c.commit()
        n = c.execute("SELECT COUNT(*) FROM miner_header_keys WHERE miner_id='power8'").fetchone()[0]
        self.assertEqual(n, 2)

    def test_preserves_extra_columns(self):
        c = self._legacy_db(extra_col=True, rows=[("g4-115", "aa" * 32, 1717000000)])
        self.mod._migrate_miner_header_keys_composite(c)
        names = [r[1] for r in c.execute("PRAGMA table_info(miner_header_keys)").fetchall()]
        self.assertIn("added_at", names)
        self.assertEqual(
            c.execute("SELECT added_at FROM miner_header_keys WHERE miner_id='g4-115'").fetchone()[0],
            1717000000)

    def test_idempotent_on_already_composite(self):
        c = self._legacy_db(rows=[("g4-115", "aa" * 32)])
        self.mod._migrate_miner_header_keys_composite(c)   # first: migrates
        self.mod._migrate_miner_header_keys_composite(c)   # second: no-op, must not raise
        self.assertEqual(set(self._pk_cols(c)), {"miner_id", "pubkey_hex"})
        self.assertEqual(c.execute("SELECT COUNT(*) FROM miner_header_keys").fetchone()[0], 1)

    # --- atomicity ---------------------------------------------------------
    def test_failure_mid_migration_rolls_back_intact(self):
        """Inject a failure on the DROP (after RENAME+CREATE+INSERT). The SAVEPOINT must
        restore the ORIGINAL single-PK table with all rows, leave no *_legacy_single
        behind, and re-raise (so init_db fails loud)."""
        real = self._legacy_db(rows=[("g4-115", "aa" * 32), ("g5-179", "bb" * 32)])
        proxy = _FailOn(real, "DROP TABLE")
        with self.assertRaises(sqlite3.OperationalError):
            self.mod._migrate_miner_header_keys_composite(proxy)
        # original table restored: single PK, both rows, no legacy/scratch tables
        self.assertEqual(self._pk_cols(real), ["miner_id"])
        rows = set(real.execute("SELECT miner_id, pubkey_hex FROM miner_header_keys").fetchall())
        self.assertEqual(rows, {("g4-115", "aa" * 32), ("g5-179", "bb" * 32)})
        self.assertNotIn("miner_header_keys_legacy_single", self._tables(real))

    def test_failure_on_create_rolls_back_intact(self):
        """Failure even earlier (on CREATE, right after RENAME) must also restore."""
        real = self._legacy_db(rows=[("g4-115", "aa" * 32)])
        proxy = _FailOn(real, "CREATE TABLE")
        with self.assertRaises(sqlite3.OperationalError):
            self.mod._migrate_miner_header_keys_composite(proxy)
        self.assertEqual(self._pk_cols(real), ["miner_id"])
        self.assertEqual(
            real.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id='g4-115'").fetchone()[0],
            "aa" * 32)
        self.assertNotIn("miner_header_keys_legacy_single", self._tables(real))

    def test_retry_after_failure_succeeds(self):
        """After a rolled-back failure, a clean retry must complete the migration —
        proving no half-migrated state stranded the data."""
        real = self._legacy_db(rows=[("g4-115", "aa" * 32)])
        with self.assertRaises(sqlite3.OperationalError):
            self.mod._migrate_miner_header_keys_composite(_FailOn(real, "DROP TABLE"))
        # retry on the real (un-proxied) connection
        self.mod._migrate_miner_header_keys_composite(real)
        self.assertEqual(set(self._pk_cols(real)), {"miner_id", "pubkey_hex"})
        self.assertEqual(
            real.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id='g4-115'").fetchone()[0],
            "aa" * 32)


if __name__ == "__main__":
    unittest.main()
