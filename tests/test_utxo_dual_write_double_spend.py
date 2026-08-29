# SPDX-License-Identifier: MIT
"""/utxo/transfer must not arm a cross-model double spend under dual-write.

Reported privately by danaher-j (Jordan Danaher); residual of bounty #2819.

The account->UTXO direction (`_settle_account_transfer_in_utxo`) is reconciled
independent of dual-write. The UTXO->account direction was not: the mirror-box
exclusion in /utxo/transfer was gated on ``if not _dual_write``. So under
UTXO_DUAL_WRITE=1 a migrated `account_mirror_boxes` box was freely
coin-selectable; the transfer minted receiver + change outputs with NO mirror
provenance (`registers_json` defaults to '{}'), then shadow-debited the account.
After a rollback to dual_write=0 those unmirrored outputs escape
`_spendable_utxo_candidates`, so the same value is spendable through BOTH the
UTXO and account models -- a double spend.

`integrity_check` compared SUMs only, so `models_agree` stayed True throughout:
one wallet's mirror surplus nets against another wallet's deficit.

The fix ungates the mirror-box exclusion (both dual-write states) and adds a
per-wallet `unspent mirror value <= account balance` assertion to
`integrity_check`, surfaced under the distinct key ``mirror_exceeds_account``.

Fixtures follow tests/test_utxo_transfer_spends_account_mirror.py; the seed
reproduces what node/utxo_genesis_migration.py writes.
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

# uRTC (account i64, 6 decimals) -> nRTC (UTXO, 8 decimals). Defined locally so
# this test collects and fails on the actual double-spend assertions on an
# unfixed tree, not on an import of a fix-introduced symbol.
NRTC_PER_ACCOUNT_UNIT = UNIT // 1_000_000  # 100

ALICE = "RTC_test_aabbccdd"
RECEIVER = "RTC_test_receiver0"
PUBKEY = "aabbccdd" * 8
GENESIS_HEIGHT = 0

# 100 RTC held both ways: as an account balance and as the box mirroring it.
ACCOUNT_I64 = 100_000_000          # 100 RTC in uRTC (6 decimals)
MIRROR_NRTC = 100 * UNIT           # 100 RTC in nRTC (8 decimals)


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


def _make_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    # The dual_write=1 branch of /utxo/transfer writes the account ledger; create
    # it so the transfer SUCCEEDS on an unfixed tree and the test fails on the
    # real double-spend assertion, not on a missing-table exception.
    conn.execute(
        "CREATE TABLE ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, "
        "delta_i64 INTEGER, reason TEXT)")
    conn.commit()
    conn.close()

    utxo_db = UtxoDB(db_path)
    utxo_db.init_tables()

    conn = sqlite3.connect(db_path)
    _seed_migrated_wallet(conn, ALICE, "mirror_box_alice")
    conn.commit()
    conn.close()
    return utxo_db, db_path


def _client(utxo_db, db_path, dual_write):
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_utxo_blueprint(
        app, utxo_db, db_path,
        verify_sig_fn=mock_verify_sig,
        addr_from_pk_fn=mock_addr_from_pk,
        current_slot_fn=mock_current_slot,
        dual_write=dual_write,
    )
    return app.test_client()


@pytest.fixture
def dual_write_rig():
    """Migrated wallet, /utxo/transfer registered with UTXO_DUAL_WRITE=1."""
    utxo_db, db_path = _make_db()
    client = _client(utxo_db, db_path, dual_write=True)
    yield client, utxo_db, db_path
    os.unlink(db_path)


def _transfer(client, to_address=RECEIVER, amount_rtc=99.0, nonce=1733420000000):
    return client.post("/utxo/transfer", json={
        "from_address": ALICE,
        "to_address": to_address,
        "amount_rtc": amount_rtc,
        "public_key": PUBKEY,
        "signature": "aa" * 64,
        "nonce": nonce,
    })


def _sender_change_boxes(db_path):
    """Unspent boxes owned by ALICE that carry NO account_mirror_boxes provenance."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT b.box_id, b.value_nrtc
                 FROM utxo_boxes b
                 LEFT JOIN account_mirror_boxes m ON m.box_id = b.box_id
                WHERE b.owner_address = ? AND b.spent_at IS NULL AND m.box_id IS NULL""",
            (ALICE,),
        ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# 1. The transfer that arms the double spend must be blocked under dual-write.
# ---------------------------------------------------------------------------

def test_dual_write_transfer_of_mirror_box_is_blocked(dual_write_rig):
    """Under dual_write=1, spending a migrated mirror box must fail closed.

    On main the mirror-box exclusion is gated `if not _dual_write`, so this
    transfer returns 200, spends the mirror box, and mints a 1 RTC change box
    with no mirror provenance -- the seed of the double spend. The fix ungates
    the exclusion, so the transfer is rejected and no unmirrored change appears.
    """
    client, _, db_path = dual_write_rig

    resp = _transfer(client)   # 99 RTC out of the 100 RTC mirror box

    assert resp.status_code == 409, (
        "dual-write transfer of a migrated mirror box was NOT blocked "
        "(status %s) -- an unmirrored change box is now spendable via both "
        "models after rollback" % resp.status_code
    )
    assert resp.get_json()["code"] == "ACCOUNT_MIRROR_BOX_NOT_SPENDABLE"

    # Mirror box untouched, no unmirrored change box minted.
    with sqlite3.connect(db_path) as conn:
        spent = conn.execute(
            "SELECT spent_at FROM utxo_boxes WHERE box_id = 'mirror_box_alice'").fetchone()[0]
    assert spent is None, "mirror box was spent under dual-write with no provenance for its change"
    assert _sender_change_boxes(db_path) == [], (
        "an unmirrored change box was minted; after rollback to dual_write=0 it "
        "escapes _spendable_utxo_candidates and is double-spendable"
    )


# ---------------------------------------------------------------------------
# 2. End-to-end: dual-write transfer then rollback must not double-spend.
# ---------------------------------------------------------------------------

def _unmirrored_unspent_utxo_nrtc(db_path, wallet):
    """Value the wallet can spend via the UTXO path once dual-write is off.

    Post-rollback the account model is authoritative and mirror boxes are
    blocked, so a wallet's independently-spendable UTXO value is the sum of its
    unspent boxes that carry NO account_mirror_boxes provenance.
    """
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(b.value_nrtc), 0)
                 FROM utxo_boxes b
                 LEFT JOIN account_mirror_boxes m ON m.box_id = b.box_id
                WHERE b.owner_address = ? AND b.spent_at IS NULL AND m.box_id IS NULL""",
            (wallet,),
        ).fetchone()
    return row[0]


def test_no_cross_model_double_spend_after_rollback(dual_write_rig):
    """The full danaher-j repro through the endpoint, both dual-write states.

    ALICE is a *purely migrated* wallet: she earned no independent UTXOs, so her
    only legitimate value is the account balance that her mirror box mirrors.
    That means she must NEVER simultaneously hold a spendable account balance AND
    an unmirrored (independently spendable) UTXO box -- that is the same money
    counted twice.

    Step 1 (dual_write=1): ALICE moves 99 RTC of her migrated box to RECEIVER.
    Step 2 (rollback to dual_write=0): ALICE tries to move a residual again.

    On main, step 1 spends the mirror box and mints an unmirrored 1 RTC change
    box while the account is debited only in the shadow model, so after rollback
    ALICE holds account balance AND unmirrored UTXO -- the double spend. The fix
    blocks step 1, so no unmirrored value is ever created.
    """
    client, utxo_db, db_path = dual_write_rig

    # Step 1: dual-write transfer (arms the bug on main).
    _transfer(client, amount_rtc=99.0, nonce=1733420000000)

    # Step 2: process restarts with UTXO_DUAL_WRITE=0.
    rollback_client = _client(utxo_db, db_path, dual_write=False)
    rollback_client.post("/utxo/transfer", json={
        "from_address": ALICE,
        "to_address": RECEIVER,
        "amount_rtc": 0.5,
        "public_key": PUBKEY,
        "signature": "aa" * 64,
        "nonce": 1733420000001,
    })

    with sqlite3.connect(db_path) as conn:
        account_i64 = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (ALICE,)).fetchone()[0]
    unmirrored_nrtc = _unmirrored_unspent_utxo_nrtc(db_path, ALICE)

    assert not (account_i64 > 0 and unmirrored_nrtc > 0), (
        "cross-model double spend: purely-migrated ALICE holds a spendable "
        "account balance (%d uRTC) AND an unmirrored UTXO box (%d nRTC) at the "
        "same time -- the same value is spendable through both models" % (
            account_i64, unmirrored_nrtc)
    )


# ---------------------------------------------------------------------------
# 3. integrity_check must catch a per-wallet divergence hidden by equal totals.
# ---------------------------------------------------------------------------

def test_integrity_check_flags_per_wallet_mirror_over_balance():
    """A total-only comparison stays models_agree=True while a wallet is short.

    Wallet X holds a 100 RTC unspent mirror box but 0 account balance (the
    double-spend signature: value present in the UTXO model, gone from account).
    Wallet Y holds 100 RTC of account balance and no boxes. Totals match, so the
    legacy total-only check reports models_agree=True. The fix asserts the
    per-wallet invariant and fails with the distinct `mirror_exceeds_account`.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
        conn.commit()
        conn.close()

        utxo_db = UtxoDB(db_path)
        utxo_db.init_tables()

        wallet_x = "RTC_short_x"
        wallet_y = "RTC_flush_y"
        with sqlite3.connect(db_path) as conn:
            # X: 100 RTC unspent mirror box, 0 account balance -> per-wallet violation.
            conn.execute("INSERT INTO balances VALUES (?, 0)", (wallet_x,))
            conn.execute(
                """INSERT INTO utxo_boxes
                   (box_id, value_nrtc, proposition, owner_address, creation_height,
                    transaction_id, output_index, tokens_json, registers_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("box_x", MIRROR_NRTC, f"prop_{wallet_x}", wallet_x, 0,
                 "gtx", 0, '[]', json.dumps({"R4": "genesis"}), int(time.time())),
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS account_mirror_boxes (
                       box_id TEXT PRIMARY KEY, account_wallet TEXT NOT NULL,
                       value_nrtc INTEGER NOT NULL, created_epoch INTEGER NOT NULL)""")
            conn.execute("INSERT INTO account_mirror_boxes VALUES (?,?,?,?)",
                         ("box_x", wallet_x, MIRROR_NRTC, 0))
            # Y: 100 RTC account balance, no boxes -> makes the TOTALS agree.
            conn.execute("INSERT INTO balances VALUES (?, ?)", (wallet_y, ACCOUNT_I64))
            conn.commit()

        # Total account = 100 RTC (Y) -> 100 * UNIT nRTC; total unspent UTXO = box_x = 100 * UNIT.
        with sqlite3.connect(db_path) as conn:
            account_total_i64 = conn.execute(
                "SELECT COALESCE(SUM(amount_i64), 0) FROM balances").fetchone()[0]
        expected_total_nrtc = account_total_i64 * NRTC_PER_ACCOUNT_UNIT

        result = utxo_db.integrity_check(expected_total=expected_total_nrtc)

        assert result.get("models_agree") is True, (
            "totals must agree so the test proves the per-wallet check adds signal "
            "the total-only comparison cannot"
        )
        assert "mirror_exceeds_account" in result and result["ok"] is False, (
            "per-wallet mirror<=balance divergence hid behind matching totals "
            "(models_agree=%r, ok=%r) -- the danaher-j double-spend signature is "
            "invisible to the total-only integrity check" % (
                result.get("models_agree"), result.get("ok"))
        )
        assert result.get("mirror_provenance_checked") is True
        violation = result["mirror_exceeds_account"][0]
        assert violation["wallet"] == wallet_x
        assert violation["mirror_unspent_nrtc"] == MIRROR_NRTC
        assert violation["account_balance_nrtc"] == 0
        assert violation["excess_nrtc"] == MIRROR_NRTC
    finally:
        os.unlink(db_path)


def test_integrity_check_passes_when_mirror_backed_by_balance():
    """A correctly-mirrored wallet (mirror value == balance) must not be flagged."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
        conn.commit()
        conn.close()

        utxo_db = UtxoDB(db_path)
        utxo_db.init_tables()
        with sqlite3.connect(db_path) as conn:
            _seed_migrated_wallet(conn, ALICE, "mirror_box_alice")
            conn.commit()
            account_total_i64 = conn.execute(
                "SELECT COALESCE(SUM(amount_i64), 0) FROM balances").fetchone()[0]
        expected_total_nrtc = account_total_i64 * NRTC_PER_ACCOUNT_UNIT

        result = utxo_db.integrity_check(expected_total=expected_total_nrtc)
        assert result["ok"] is True
        assert result.get("models_agree") is True
        assert result.get("mirror_provenance_checked") is True
        assert "mirror_exceeds_account" not in result
    finally:
        os.unlink(db_path)
