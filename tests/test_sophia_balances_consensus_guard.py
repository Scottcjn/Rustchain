# SPDX-License-Identifier: MIT
"""Guard test: sophia_elya_service._ensure_balance_micro_schema must NEVER rebuild
the consensus balances ledger.

`sophia_elya_service.py` uses a relative `DB_PATH = "./rustchain_v2.db"` and, when run
as __main__, calls `_ensure_balance_micro_schema`, which (for a non-INTEGER balance_rtc)
RENAMEs `balances`, recreates it as 2 columns (miner_pk, balance_rtc), and drops the
original. The consensus `balances` is keyed by `miner_id` with the canonical micro-RTC
amount in `amount_i64` (+ coinbase_address) — rebuilding it would WIPE every balance.
The guard must detect consensus columns and leave the table untouched, while still
migrating a genuine Sophia-shaped table.
"""
import os
import re
import sqlite3

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "node", "sophia_elya_service.py")


def _load_fn():
    src = open(SRC, encoding="utf-8").read()
    start = src.index("def _ensure_balance_micro_schema(conn):")
    end = src.index("\ndef _ensure_epoch_state_settlement_schema")
    ns = {"RTC_MICRO_UNITS": 1_000_000}
    exec(src[start:end], ns)
    return ns["_ensure_balance_micro_schema"]


CONSENSUS_DDL = (
    "CREATE TABLE balances (miner_id TEXT PRIMARY KEY NOT NULL, "
    "amount_i64 INTEGER NOT NULL DEFAULT 0 CHECK(amount_i64 >= 0), "
    "miner_pk TEXT, balance_rtc REAL DEFAULT 0.0, coinbase_address TEXT DEFAULT NULL)"
)


def test_consensus_balances_left_untouched():
    fn = _load_fn()
    c = sqlite3.connect(":memory:")
    c.executescript(CONSENSUS_DDL)
    c.execute("INSERT INTO balances(miner_id,amount_i64,miner_pk,balance_rtc) VALUES('m1',5000000,'pk1',0.0)")
    c.execute("INSERT INTO balances(miner_id,amount_i64,miner_pk) VALUES('m2',9000000,'pk2')")
    c.commit()
    before = c.execute("SELECT miner_id,amount_i64,coinbase_address FROM balances ORDER BY miner_id").fetchall()

    fn(c)  # must be a no-op on the consensus ledger

    cols = {r[1] for r in c.execute("PRAGMA table_info(balances)").fetchall()}
    assert cols == {"miner_id", "amount_i64", "miner_pk", "balance_rtc", "coinbase_address"}
    after = c.execute("SELECT miner_id,amount_i64,coinbase_address FROM balances ORDER BY miner_id").fetchall()
    assert after == before  # amount_i64 NOT wiped, no rows lost


def test_genuine_sophia_balances_still_migrate_to_integer_micro():
    fn = _load_fn()
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0.0)")
    c.execute("INSERT INTO balances VALUES('pk1', 2.5)")
    c.commit()

    fn(c)  # legit migration path preserved

    btype = c.execute("SELECT type FROM pragma_table_info('balances') WHERE name='balance_rtc'").fetchone()[0]
    assert btype == "INTEGER"
    assert c.execute("SELECT balance_rtc FROM balances WHERE miner_pk='pk1'").fetchone()[0] == 2_500_000
