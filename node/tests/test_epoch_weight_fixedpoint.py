#!/usr/bin/env python3
"""Regression tests for deterministic epoch enrollment weights."""

import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"
_NODE_MODULE = None
_IMPORT_TMPDIR = None


def load_node_module():
    global _NODE_MODULE, _IMPORT_TMPDIR
    if _NODE_MODULE is not None:
        return _NODE_MODULE

    _IMPORT_TMPDIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = str(Path(_IMPORT_TMPDIR.name) / "import.db")
    old_rustchain_db = os.environ.get("RUSTCHAIN_DB_PATH")
    old_db = os.environ.get("DB_PATH")
    old_admin_key = os.environ.get("RC_ADMIN_KEY")
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ["DB_PATH"] = db_path
    os.environ["RC_ADMIN_KEY"] = "test-admin-key-for-epoch-weight-fixedpoint"
    sys.path.insert(0, str(NODE_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "rustchain_epoch_weight_fixedpoint_test_module", MODULE_PATH
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["rustchain_epoch_weight_fixedpoint_test_module"] = module
        spec.loader.exec_module(module)
        _NODE_MODULE = module
        return module
    finally:
        if old_rustchain_db is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = old_rustchain_db
        if old_db is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old_db
        if old_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = old_admin_key
        try:
            sys.path.remove(str(NODE_DIR))
        except ValueError:
            pass


def test_epoch_weight_conversion_preserves_small_vm_weight():
    node = load_node_module()

    assert node.epoch_weight_to_units(2.5) == 2_500_000_000
    assert node.epoch_weight_to_units("0.000000001") == 1
    assert node.epoch_weight_units_to_display(1) == 0.000000001


def test_epoch_enroll_schema_uses_integer_weight_column():
    node = load_node_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "schema.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER, PRIMARY KEY (epoch, miner_pk))"
            )
            node.ensure_epoch_enroll_integer_weights(conn)
            columns = conn.execute("PRAGMA table_info(epoch_enroll)").fetchall()
        finally:
            conn.close()

    weight_column = next(col for col in columns if col[1] == "weight")
    assert weight_column[2].upper() == "INTEGER"


def test_legacy_real_weights_migrate_to_fixed_point_units():
    node = load_node_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "legacy.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk))"
            )
            conn.execute(
                "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (7, "miner_A", 0.1),
            )
            conn.execute(
                "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (7, "miner_B", 2.5),
            )
            node.ensure_epoch_enroll_integer_weights(conn)
            columns = conn.execute("PRAGMA table_info(epoch_enroll)").fetchall()
            rows = conn.execute(
                "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ? ORDER BY miner_pk",
                (7,),
            ).fetchall()
        finally:
            conn.close()

    weight_column = next(col for col in columns if col[1] == "weight")
    assert weight_column[2].upper() == "INTEGER"
    assert rows == [("miner_A", 100_000_000), ("miner_B", 2_500_000_000)]
