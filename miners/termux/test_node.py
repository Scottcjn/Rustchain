#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local-only RustChain attestation test node for the Termux miner port.

The harness imports the repository's real Flask node and real attestation
handlers. It binds only to loopback, uses a disposable SQLite DB, disables P2P
auto-start, and generates an in-process admin key that is never printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import secrets
import sqlite3
import sys
from pathlib import Path

EXTRA_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS blocked_wallets (wallet TEXT PRIMARY KEY, reason TEXT)",
    "CREATE TABLE IF NOT EXISTS ip_rate_limit (client_ip TEXT NOT NULL, miner_id TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (client_ip, miner_id))",
    "CREATE TABLE IF NOT EXISTS miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER NOT NULL, device_family TEXT, device_arch TEXT, entropy_score REAL DEFAULT 0, fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT, warthog_bonus REAL DEFAULT 1.0)",
    "CREATE TABLE IF NOT EXISTS hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT NOT NULL, device_arch TEXT, device_model TEXT, bound_at INTEGER NOT NULL, attestation_count INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS miner_macs (miner TEXT NOT NULL, mac_hash TEXT NOT NULL, first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (miner, mac_hash))",
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="loopback RustChain attestation test node")
    parser.add_argument("--port", type=int, default=58333)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")

    repo_root = Path(__file__).resolve().parents[2]
    node_dir = repo_root / "node"
    module_path = node_dir / "rustchain_v2_integrated_v2.2.1_rip200.py"
    if not module_path.is_file():
        parser.error("run this helper from a full RustChain source checkout")

    tmpdir = Path(os.environ.get("TMPDIR", "/tmp"))
    db_path = args.db or (tmpdir / "rustchain-termux-testnode.db")
    if not args.keep_db:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            candidate.unlink(missing_ok=True)

    # Configure a local/test runtime before importing the node module.
    os.environ["RC_RUNTIME_ENV"] = "test"
    os.environ["RUSTCHAIN_ENV"] = "test"
    os.environ["RC_NODE_ROLE"] = "sync"
    os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ["RC_ADMIN_KEY"] = secrets.token_hex(24)

    sys.path.insert(0, str(node_dir))
    spec = importlib.util.spec_from_file_location("rustchain_termux_testnode", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load RustChain node module")
    node = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(node)

    # Match the repository's attestation regression harness: keep the canonical
    # challenge/submit handlers while disabling unrelated network integrations.
    node.HAVE_REPLAY_DEFENSE = False
    node.HAVE_WARTHOG = False
    node.init_db()
    with sqlite3.connect(db_path) as conn:
        for statement in EXTRA_SCHEMA:
            conn.execute(statement)
        conn.commit()

    print(f"[TERMUX-TEST-NODE] http://127.0.0.1:{args.port}")
    print(f"[TERMUX-TEST-NODE] db={db_path}")
    print("[TERMUX-TEST-NODE] production network and P2P are disabled")
    node.app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
