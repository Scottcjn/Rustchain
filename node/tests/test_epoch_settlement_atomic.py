"""Atomic epoch-settlement guard + schema-migration tests.

These exercise the exact SQL contract that finalize_epoch() relies on to prevent
double-settlement (reward inflation past the supply cap). They are written as
isolated SQLite tests because importing the full integrated node module starts
P2P/Flask side effects; the logic under test is the claim + migration SQL.
"""
import sqlite3


def _new_epoch_state(con, *, legacy=False):
    if legacy:
        # Pre-migration shape (no settled / settled_ts) — what old DBs had.
        con.execute(
            "CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, "
            "accepted_blocks INTEGER DEFAULT 0, finalized INTEGER DEFAULT 0)"
        )
    else:
        con.execute(
            "CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, "
            "accepted_blocks INTEGER DEFAULT 0, finalized INTEGER DEFAULT 0, "
            "settled INTEGER DEFAULT 0, settled_ts INTEGER)"
        )


def _migrate(con):
    """The idempotent migration finalize-init runs."""
    cols = {row[1] for row in con.execute("PRAGMA table_info(epoch_state)").fetchall()}
    if "settled" not in cols:
        con.execute("ALTER TABLE epoch_state ADD COLUMN settled INTEGER DEFAULT 0")
    if "settled_ts" not in cols:
        con.execute("ALTER TABLE epoch_state ADD COLUMN settled_ts INTEGER")


def _claim(con, epoch):
    """The atomic claim finalize_epoch performs; returns rowcount (1=won, 0=lost)."""
    con.execute(
        "INSERT INTO epoch_state (epoch, settled) VALUES (?, 0) "
        "ON CONFLICT(epoch) DO NOTHING",
        (epoch,),
    )
    cur = con.execute(
        "UPDATE epoch_state SET settled = 1, settled_ts = 123 WHERE epoch = ? AND settled = 0",
        (epoch,),
    )
    return cur.rowcount


def test_migration_adds_columns_and_is_idempotent():
    con = sqlite3.connect(":memory:")
    _new_epoch_state(con, legacy=True)
    _migrate(con)
    cols = {row[1] for row in con.execute("PRAGMA table_info(epoch_state)").fetchall()}
    assert "settled" in cols and "settled_ts" in cols
    # Running again must not error (idempotent).
    _migrate(con)
    assert {row[1] for row in con.execute("PRAGMA table_info(epoch_state)").fetchall()} >= {
        "settled",
        "settled_ts",
    }


def test_claim_is_won_once_then_lost():
    con = sqlite3.connect(":memory:")
    _new_epoch_state(con)
    # First settlement attempt wins the claim.
    assert _claim(con, 42) == 1
    # Every subsequent attempt for the same epoch loses → finalize_epoch aborts
    # before crediting any balances, so rewards are paid exactly once.
    assert _claim(con, 42) == 0
    assert _claim(con, 42) == 0
    row = con.execute("SELECT settled FROM epoch_state WHERE epoch=42").fetchone()
    assert row[0] == 1


def test_claim_creates_row_when_absent():
    con = sqlite3.connect(":memory:")
    _new_epoch_state(con)
    # No pre-existing epoch_state row (block-accept never inserted one) must NOT
    # be mistaken for "already settled".
    assert con.execute("SELECT COUNT(*) FROM epoch_state WHERE epoch=7").fetchone()[0] == 0
    assert _claim(con, 7) == 1


def test_distinct_epochs_independent():
    con = sqlite3.connect(":memory:")
    _new_epoch_state(con)
    assert _claim(con, 1) == 1
    assert _claim(con, 2) == 1
    assert _claim(con, 1) == 0


def _backfill(con):
    """The upgrade backfill init runs (insert-missing + update-existing)."""
    con.execute(
        "INSERT OR IGNORE INTO epoch_state (epoch, settled, settled_ts) "
        "SELECT DISTINCT epoch, 1, 123 FROM epoch_rewards"
    )
    con.execute(
        "UPDATE epoch_state SET settled = 1 "
        "WHERE settled = 0 AND epoch IN (SELECT DISTINCT epoch FROM epoch_rewards)"
    )


def test_backfill_marks_already_rewarded_epoch_settled(tmp_path):
    # An epoch rewarded via epoch_rewards but with NO epoch_state row (the
    # dangerous case) must be inserted as settled by the backfill so it cannot
    # be re-claimed/re-credited after upgrade.
    db = str(tmp_path / "e.db")
    con = sqlite3.connect(db)
    _new_epoch_state(con, legacy=True)
    con.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER)")
    con.execute("INSERT INTO epoch_rewards VALUES (5, 'm1', 1000)")  # NO epoch_state row for 5
    con.commit()
    _migrate(con)
    assert con.execute("SELECT COUNT(*) FROM epoch_state WHERE epoch=5").fetchone()[0] == 0
    _backfill(con)
    row = con.execute("SELECT settled FROM epoch_state WHERE epoch=5").fetchone()
    assert row is not None and row[0] == 1
    # A subsequent finalize claim must LOSE (no second credit).
    assert _claim(con, 5) == 0


def test_backfill_marks_existing_unsettled_rewarded_epoch(tmp_path):
    db = str(tmp_path / "e2.db")
    con = sqlite3.connect(db)
    _new_epoch_state(con)
    con.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER)")
    con.execute("INSERT INTO epoch_rewards VALUES (8, 'm1', 1000)")
    con.execute("INSERT INTO epoch_state (epoch, settled) VALUES (8, 0)")  # exists, unsettled
    con.commit()
    _backfill(con)
    assert con.execute("SELECT settled FROM epoch_state WHERE epoch=8").fetchone()[0] == 1
    assert _claim(con, 8) == 0


def test_concurrent_begin_immediate_only_one_settles(tmp_path):
    # Two real connections contend on the same file DB; BEGIN IMMEDIATE must
    # serialize them so exactly one claim commits.
    db = str(tmp_path / "c.db")
    setup = sqlite3.connect(db)
    _new_epoch_state(setup)
    setup.commit()
    setup.close()

    a = sqlite3.connect(db, timeout=5)
    b = sqlite3.connect(db, timeout=5)
    a.execute("BEGIN IMMEDIATE")
    won_a = _claim(a, 9)  # holds the write lock
    # b cannot acquire IMMEDIATE while a holds it
    import sqlite3 as _s
    try:
        b.execute("BEGIN IMMEDIATE")
        b_blocked = False
    except _s.OperationalError:
        b_blocked = True
    a.execute("COMMIT")
    # Now b proceeds and must LOSE the claim (epoch already settled by a).
    if b_blocked:
        b.execute("BEGIN IMMEDIATE")
    won_b = _claim(b, 9)
    b.execute("COMMIT")
    assert won_a == 1
    assert won_b == 0
    a.close()
    b.close()
