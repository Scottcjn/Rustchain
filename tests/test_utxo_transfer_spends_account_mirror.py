# SPDX-License-Identifier: MIT
"""/utxo/transfer must not move account-mirrored funds while dual-write is off.

`account_mirror_boxes` is the discriminator that says "this box IS this wallet's
account balance" (bounty #2819). `_settle_account_transfer_in_utxo` closes the
account->UTXO direction: an account confirm spends the sender's mirror box so the
same funds cannot move twice. Its docstring is explicit that it runs
"independent of UTXO_DUAL_WRITE: a migrated box must be reconciled whenever it
exists" -- i.e. in the default config the box and the balance are the same money.

The UTXO->account direction is unguarded. With dual_write off (the live default,
UTXO_DUAL_WRITE defaults to "0"), /utxo/transfer spends the mirror box via
apply_transaction and then skips every account-model write, so the sender keeps
a full account balance that no longer has a box behind it -- and walks away with
the box value too.

Fixtures follow tests/test_utxo_transfer_replay.py; the seed reproduces exactly
what node/utxo_genesis_migration.py:220-251 writes.
"""
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest
from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

from utxo_db import UtxoDB, UNIT
from utxo_endpoints import register_utxo_blueprint

ALICE = "RTC_test_aabbccdd"
PUBKEY = "aabbccdd" * 8
GENESIS_HEIGHT = 0

# 100 RTC held both ways: as an account balance and as the box mirroring it.
ACCOUNT_I64 = 100_000_000
MIRROR_NRTC = 100 * UNIT


def mock_verify_sig(pubkey_hex, message, sig_hex):
    return True


def mock_addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"


def mock_current_slot():
    return 100


def _seed_migrated_wallet(conn, address, box_id):
    """Exactly what utxo_genesis_migration.py writes: box + R4 marker + provenance."""
    conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                 (address, ACCOUNT_I64))
    conn.execute(
        """INSERT INTO utxo_boxes
           (box_id, value_nrtc, proposition, owner_address, creation_height,
            transaction_id, output_index, tokens_json, registers_json, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (box_id, MIRROR_NRTC, f"prop_{address}", address, GENESIS_HEIGHT,
         "genesis_tx", 0, '[]', json.dumps({"R4": "genesis"}), int(time.time())),
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS account_mirror_boxes (
               box_id TEXT PRIMARY KEY, account_wallet TEXT NOT NULL,
               value_nrtc INTEGER NOT NULL, created_epoch INTEGER NOT NULL)""",
    )
    conn.execute(
        "INSERT INTO account_mirror_boxes (box_id, account_wallet, value_nrtc, created_epoch)"
        " VALUES (?,?,?,?)",
        (box_id, address, MIRROR_NRTC, GENESIS_HEIGHT),
    )


@pytest.fixture
def rig():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

    utxo_db = UtxoDB(db_path)
    utxo_db.init_tables()

    conn = sqlite3.connect(db_path)
    _seed_migrated_wallet(conn, ALICE, "mirror_box_alice")
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_utxo_blueprint(
        app, utxo_db, db_path,
        verify_sig_fn=mock_verify_sig,
        addr_from_pk_fn=mock_addr_from_pk,
        current_slot_fn=mock_current_slot,
        dual_write=False,   # the live default: UTXO_DUAL_WRITE defaults to "0"
    )
    return app.test_client(), utxo_db, db_path


def _transfer(client, to_address=ALICE, amount_rtc=99.0, nonce=1733420000000):
    return client.post("/utxo/transfer", json={
        "from_address": ALICE,
        "to_address": to_address,
        "amount_rtc": amount_rtc,
        "public_key": PUBKEY,
        "signature": "aa" * 64,
        "nonce": nonce,
    })


def _unspent_mirror_value(db_path, wallet):
    """What _settle_account_transfer_in_utxo can still reconcile: the join it uses."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(b.value_nrtc), 0)
                 FROM account_mirror_boxes m
                 JOIN utxo_boxes b ON b.box_id = m.box_id
                WHERE m.account_wallet = ? AND b.spent_at IS NULL""",
            (wallet,),
        ).fetchone()
    return row[0]


def test_account_balance_stays_backed_by_a_mirror_box(rig):
    """The invariant /pending/confirm relies on: balance still has a box behind it."""
    client, _, db_path = rig
    assert _unspent_mirror_value(db_path, ALICE) == MIRROR_NRTC, "seed sanity"

    _transfer(client)

    with sqlite3.connect(db_path) as conn:
        balance = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (ALICE,)).fetchone()[0]

    assert balance == ACCOUNT_I64, "dual-write is off, so the balance is untouched"
    assert _unspent_mirror_value(db_path, ALICE) > 0, (
        "account balance of %d is now backed by no unspent mirror box: /pending/confirm "
        "will read 'non-migrated sender' and let it move again -- bounty #2819, "
        "reached from the UTXO side" % balance
    )


def test_mirror_box_is_not_spent_while_dual_write_is_off(rig):
    """With no account write to pair it with, the mirror spend must not happen."""
    client, _, db_path = rig

    resp = _transfer(client)

    with sqlite3.connect(db_path) as conn:
        spent = conn.execute(
            "SELECT spent_at FROM utxo_boxes WHERE box_id = 'mirror_box_alice'").fetchone()[0]
    assert spent is None, "mirror box was spent without debiting the account it mirrors"
    assert resp.status_code == 409
    assert resp.get_json()["code"] == "ACCOUNT_MIRROR_BOX_NOT_SPENDABLE"


def test_independently_earned_boxes_are_unaffected(rig):
    """Guard the repo's stated concern: never burn/block non-mirror UTXOs."""
    client, utxo_db, db_path = rig
    assert utxo_db.apply_transaction(
        {"tx_type": "mining_reward", "inputs": [],
         "outputs": [{"address": mock_addr_from_pk("deadbeef" * 8), "value_nrtc": 50 * UNIT}],
         "timestamp": int(time.time()), "_allow_minting": True},
        block_height=5,
    ) is True

    resp = client.post("/utxo/transfer", json={
        "from_address": mock_addr_from_pk("deadbeef" * 8),
        "to_address": ALICE,
        "amount_rtc": 10.0,
        "public_key": "deadbeef" * 8,
        "signature": "bb" * 64,
        "nonce": 1733420000001,
    })

    assert resp.status_code == 200, resp.get_json()
