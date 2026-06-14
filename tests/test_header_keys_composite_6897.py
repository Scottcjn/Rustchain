# SPDX-License-Identifier: MIT
"""Regression tests for the composite (miner_id, pubkey_hex) miner_header_keys key.

Consolidation fix for the Windows signed-header cluster (#6896/#6897): a wallet
identity may have several enrolled devices, each with its own header key. The
legacy single-column PRIMARY KEY(miner_id) made device enrollment last-writer-wins,
which broke the non-last device's signed-header verification. These tests pin:

  1. the legacy->composite migration preserves rows and is idempotent,
  2. two devices under one wallet both retain their keys (no overwrite),
  3. verify-any accepts a header signed by ANY registered device key,
  4. a non-registered (stranger) signature is still rejected.
"""
import sqlite3

import pytest


def _make_composite(c):
    c.execute(
        "CREATE TABLE miner_header_keys("
        "miner_id TEXT NOT NULL, pubkey_hex TEXT NOT NULL, "
        "PRIMARY KEY (miner_id, pubkey_hex))"
    )


def _migrate(c):
    """Mirror of the init_db() COLUMN-PRESERVING legacy->composite migration:
    reconstructs every existing column (type / NOT NULL / DEFAULT) so a production
    table carrying extra columns (e.g. `added_at`) keeps them."""
    cols = c.execute("PRAGMA table_info(miner_header_keys)").fetchall()
    pk = [col[1] for col in cols if col[5]]
    names = [col[1] for col in cols]
    if pk != ["miner_id"] or "miner_id" not in names or "pubkey_hex" not in names:
        return "noop"
    defs, col_list = [], []
    for _cid, name, ctype, notnull, dflt, _pk in cols:
        d = '"%s" %s' % (name, ctype or "TEXT")
        if notnull:
            d += " NOT NULL"
        if dflt is not None:
            d += " DEFAULT (%s)" % dflt
        defs.append(d)
        col_list.append('"%s"' % name)
    c.execute("ALTER TABLE miner_header_keys RENAME TO miner_header_keys_legacy_single")
    c.execute("CREATE TABLE miner_header_keys (%s, PRIMARY KEY (miner_id, pubkey_hex))" % ", ".join(defs))
    c.execute(
        "INSERT OR IGNORE INTO miner_header_keys (%s) SELECT %s FROM miner_header_keys_legacy_single"
        % (", ".join(col_list), ", ".join(col_list))
    )
    c.execute("DROP TABLE miner_header_keys_legacy_single")
    c.commit()
    return "migrated"


def test_migration_preserves_extra_columns_like_production_added_at():
    """Production `miner_header_keys` carries a 3rd `added_at` column (with an
    expression default) absent from the code's CREATE. The migration must keep it
    and its data — not silently drop it. Mirrors the exact prod DDL."""
    c = sqlite3.connect(":memory:")
    c.executescript(
        "CREATE TABLE miner_header_keys (\n"
        "  miner_id TEXT PRIMARY KEY,\n"
        "  pubkey_hex TEXT NOT NULL,\n"
        "  added_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))\n"
        ")"
    )
    c.execute("INSERT INTO miner_header_keys(miner_id,pubkey_hex,added_at) VALUES('walletA','aaaa',1759701180)")
    c.execute("INSERT INTO miner_header_keys(miner_id,pubkey_hex,added_at) VALUES('walletB','bbbb',1780774414)")
    c.commit()
    before = c.execute("SELECT miner_id,pubkey_hex,added_at FROM miner_header_keys ORDER BY miner_id").fetchall()

    assert _migrate(c) == "migrated"
    assert _pk_cols(c) == ["miner_id", "pubkey_hex"]
    # the added_at column survived with its values...
    assert "added_at" in [col[1] for col in c.execute("PRAGMA table_info(miner_header_keys)").fetchall()]
    assert c.execute("SELECT miner_id,pubkey_hex,added_at FROM miner_header_keys ORDER BY miner_id").fetchall() == before
    # ...and its default still fires for a new device key
    c.execute("INSERT INTO miner_header_keys(miner_id,pubkey_hex) VALUES('walletA','cccc') ON CONFLICT(miner_id,pubkey_hex) DO NOTHING")
    c.commit()
    assert c.execute("SELECT added_at>0 FROM miner_header_keys WHERE miner_id='walletA' AND pubkey_hex='cccc'").fetchone()[0] == 1
    assert _migrate(c) == "noop"  # idempotent


def _pk_cols(c):
    return [col[1] for col in c.execute("PRAGMA table_info(miner_header_keys)").fetchall() if col[5]]


def test_legacy_migration_preserves_rows_and_is_idempotent():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE miner_header_keys (miner_id TEXT PRIMARY KEY, pubkey_hex TEXT NOT NULL)")
    c.execute("INSERT INTO miner_header_keys VALUES (?, ?)", ("walletW", "aa" * 32))
    c.commit()

    assert _migrate(c) == "migrated"
    assert _pk_cols(c) == ["miner_id", "pubkey_hex"]
    assert c.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id='walletW'").fetchone()[0] == "aa" * 32
    # second run must be a no-op (idempotent)
    assert _migrate(c) == "noop"


def test_two_devices_one_wallet_keep_both_keys():
    c = sqlite3.connect(":memory:")
    _make_composite(c)
    for pk in ("aa" * 32, "bb" * 32):
        c.execute(
            "INSERT INTO miner_header_keys(miner_id,pubkey_hex) VALUES('walletW',?) "
            "ON CONFLICT(miner_id, pubkey_hex) DO NOTHING",
            (pk,),
        )
    # re-registering an existing key is idempotent, not an overwrite
    c.execute(
        "INSERT INTO miner_header_keys(miner_id,pubkey_hex) VALUES('walletW',?) "
        "ON CONFLICT(miner_id, pubkey_hex) DO NOTHING",
        ("aa" * 32,),
    )
    c.commit()
    keys = {r[0] for r in c.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id='walletW'").fetchall()}
    assert keys == {"aa" * 32, "bb" * 32}


def _prune(c, miner_id, k):
    c.execute(
        "DELETE FROM miner_header_keys WHERE miner_id=? AND rowid NOT IN "
        "(SELECT rowid FROM miner_header_keys WHERE miner_id=? ORDER BY rowid DESC LIMIT ?)",
        (miner_id, miner_id, k),
    )


def test_keys_per_identity_are_bounded_keeping_newest():
    c = sqlite3.connect(":memory:")
    _make_composite(c)
    # register 10 distinct keys, bound = 4 → only the 4 most-recent survive
    for i in range(10):
        c.execute(
            "INSERT INTO miner_header_keys(miner_id,pubkey_hex) VALUES('walletW',?) "
            "ON CONFLICT(miner_id, pubkey_hex) DO NOTHING",
            (f"{i:064x}",),
        )
        _prune(c, "walletW", 4)
    c.commit()
    survivors = {r[0] for r in c.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id='walletW'").fetchall()}
    assert survivors == {f"{i:064x}" for i in (6, 7, 8, 9)}  # newest 4 kept, oldest evicted


def test_verify_any_accepts_any_device_key_and_rejects_stranger():
    nacl_signing = pytest.importorskip("nacl.signing")
    SigningKey, VerifyKey = nacl_signing.SigningKey, nacl_signing.VerifyKey

    c = sqlite3.connect(":memory:")
    _make_composite(c)
    dev_a, dev_b = SigningKey.generate(), SigningKey.generate()
    for sk in (dev_a, dev_b):
        c.execute(
            "INSERT INTO miner_header_keys(miner_id,pubkey_hex) VALUES('walletW',?) "
            "ON CONFLICT(miner_id, pubkey_hex) DO NOTHING",
            (bytes(sk.verify_key).hex(),),
        )
    c.commit()
    candidates = [r[0] for r in c.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id='walletW'").fetchall()]

    def verify_any(cands, msg, sig):
        for k in cands:
            try:
                VerifyKey(bytes.fromhex(k)).verify(msg, sig)
                return True
            except Exception:
                continue
        return False

    msg = b"slot:42:miner:walletW:ts:123"
    # a header signed by the SECOND device must verify (the case the old code broke)
    assert verify_any(candidates, msg, bytes(dev_b.sign(msg).signature)) is True
    # a stranger's signature must NOT verify
    stranger = SigningKey.generate()
    assert verify_any(candidates, msg, bytes(stranger.sign(msg).signature)) is False
