# SPDX-License-Identifier: MIT
"""tools/ledger_snapshot.py: state root, snapshot round trip, and replica pull safety."""

import gzip
import importlib.util
import json
import os
import sqlite3
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "ledger_snapshot", Path(__file__).resolve().parents[1] / "tools" / "ledger_snapshot.py"
)
ls = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ls)


def make_db(path, extra_balance=None, attest=True):
    c = sqlite3.connect(path)
    c.executescript(
        """
        CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER, miner_pk TEXT, balance_rtc REAL, coinbase_address TEXT);
        CREATE TABLE pending_ledger (id INTEGER PRIMARY KEY, ts INTEGER, epoch INTEGER, from_miner TEXT, to_miner TEXT,
            amount_i64 INTEGER, reason TEXT, status TEXT, voided_by TEXT, voided_reason TEXT, created_at INTEGER,
            confirms_at INTEGER, confirmed_at INTEGER, tx_hash TEXT);
        CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT);
        CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER, settled_ts INTEGER);
        CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER, PRIMARY KEY (epoch, miner_id));
        CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER, PRIMARY KEY (epoch, miner_pk));
        CREATE TABLE utxo_boxes (box_id TEXT PRIMARY KEY, value_nrtc INTEGER, spent_at INTEGER);
        CREATE TABLE utxo_transactions (tx_id TEXT PRIMARY KEY, tx_type TEXT);
        CREATE TABLE account_mirror_boxes (box_id TEXT PRIMARY KEY, account_wallet TEXT, value_nrtc INTEGER);
        CREATE TABLE lock_ledger (id INTEGER PRIMARY KEY, miner_id TEXT, amount_i64 INTEGER);
        CREATE TABLE headers (slot INTEGER PRIMARY KEY, miner_id TEXT);
        """
    )
    c.executemany("INSERT INTO balances VALUES (?,?,?,?,?)", [
        ("founder_community", 5_000_000, None, 5.0, None),
        ("RTC" + "a" * 40, 1_500_000, "ab" * 32, 1.5, None),
        ("naïve-wallet", 0, None, 0.0, None),
    ])
    if extra_balance:
        c.execute("INSERT INTO balances VALUES (?,?,?,?,?)", extra_balance)
    c.execute("INSERT INTO pending_ledger VALUES (1,10,1,'founder_community',?,1500000,'bounty','confirmed',NULL,NULL,10,20,21,'h1')",
              ("RTC" + "a" * 40,))
    c.execute("INSERT INTO ledger (ts,epoch,miner_id,delta_i64,reason) VALUES (10,1,'founder_community',-1500000,'bounty')")
    c.execute("INSERT INTO epoch_state VALUES (1,1,30)")
    c.execute("INSERT INTO epoch_rewards VALUES (1,'founder_community',7)")
    if attest:
        # Not a ledger table: must never be copied or hashed.
        c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, source_ip TEXT)")
        c.execute("INSERT INTO miner_attest_recent VALUES ('m','203.0.113.9')")
    c.commit()
    c.close()
    return path


def root_of(path):
    conn = ls._connect_ro(str(path))
    try:
        return ls.compute(conn)
    finally:
        conn.close()


def test_root_is_stable_and_ignores_non_ledger_tables_and_float_column(tmp_path):
    a = make_db(tmp_path / "a.db")
    b = make_db(tmp_path / "b.db", attest=False)
    assert root_of(a)["state_root"] == root_of(b)["state_root"]
    c = sqlite3.connect(a)
    c.execute("UPDATE balances SET balance_rtc = 999.25")           # derived float column: not hashed
    c.execute("UPDATE miner_attest_recent SET source_ip = '198.51.100.1'")  # not a ledger table
    c.commit()
    c.close()
    assert root_of(a)["state_root"] == root_of(b)["state_root"]


@pytest.mark.parametrize("sql", [
    "UPDATE balances SET amount_i64 = amount_i64 + 1 WHERE miner_id = 'founder_community'",
    "INSERT INTO balances VALUES ('ghost', 1, NULL, 0.000001, NULL)",
    "DELETE FROM balances WHERE miner_id = 'naïve-wallet'",
    "UPDATE pending_ledger SET status = 'voided'",
    "UPDATE pending_ledger SET to_miner = 'someone-else'",
    "INSERT INTO ledger (ts,epoch,miner_id,delta_i64,reason) VALUES (11,1,'x',1,'y')",
    "UPDATE epoch_rewards SET share_i64 = 8",
    "UPDATE epoch_state SET settled = 0",
])
def test_any_ledger_change_changes_the_root(tmp_path, sql):
    a = make_db(tmp_path / "a.db")
    before = root_of(a)["state_root"]
    c = sqlite3.connect(a)
    c.execute(sql)
    c.commit()
    c.close()
    assert root_of(a)["state_root"] != before


def test_float_in_a_hashed_column_is_refused(tmp_path):
    a = make_db(tmp_path / "a.db")
    c = sqlite3.connect(a)
    c.execute("UPDATE epoch_rewards SET share_i64 = 1.5")
    c.commit()
    c.close()
    with pytest.raises(ls.SnapshotError):
        root_of(a)


def test_not_a_ledger_database(tmp_path):
    p = tmp_path / "x.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE t (a INTEGER PRIMARY KEY)")
    c.commit()
    c.close()
    with pytest.raises(ls.SnapshotError):
        root_of(p)


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    d = tmp_path_factory.mktemp("keys")
    ls.keygen(str(d / "pub.key"), str(d / "pub.pem"))
    ls.keygen(str(d / "other.key"), str(d / "other.pem"))
    return d


def snap(src, out, keys, key="pub.key"):
    return ls.make_snapshot(str(src), str(out), str(keys / key), node="n1", min_free_bytes=1 << 20)


def gz_path(out, m):
    return Path(out) / "snapshots" / m["snapshot"]["file"]


def test_snapshot_round_trip_and_private_tables_left_out(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    m1 = snap(src, tmp_path / "o1", keys)
    m2 = snap(src, tmp_path / "o2", keys)
    assert m1["state_root"] == m2["state_root"] == root_of(src)["state_root"]
    assert m1["snapshot"]["db_sha256"] == m2["snapshot"]["db_sha256"]
    out = tmp_path / "copy.db"
    out.write_bytes(gzip.decompress(gz_path(tmp_path / "o1", m1).read_bytes()))
    assert ls.verify_db(str(out), m1) == []
    names = {r[0] for r in sqlite3.connect(out).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "miner_attest_recent" not in names
    assert "balance_rtc" not in [r[1] for r in sqlite3.connect(out).execute("PRAGMA table_info(balances)")]
    assert b"203.0.113.9" not in out.read_bytes()
    assert sqlite3.connect(src).execute("SELECT COUNT(*) FROM balances").fetchone()[0] == 3  # source untouched


def test_sequence_increases_and_old_snapshots_are_pruned(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    seqs = []
    for i in range(6):
        c = sqlite3.connect(src)
        c.execute("INSERT INTO ledger (ts,epoch,miner_id,delta_i64,reason) VALUES (?,1,'x',1,'y')", (100 + i,))
        c.commit()
        c.close()
        seqs.append(snap(src, tmp_path / "o", keys)["sequence"])
    assert seqs == sorted(set(seqs)) and seqs[0] >= 1_700_000_000   # strictly increasing, clock-based
    assert len(os.listdir(tmp_path / "o" / "snapshots")) == ls.KEEP_SNAPSHOTS
    assert sorted(f for f in os.listdir(tmp_path / "o") if not f.startswith(".")) == ["manifest.json", "sequence", "snapshots"]


def test_verify_reports_which_table_differs_and_rejects_inconsistent_manifest(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    m = snap(src, tmp_path / "o", keys)
    other = make_db(tmp_path / "other.db", extra_balance=("extra", 5, None, 0.000005, None))
    assert any(p.startswith("balances: differs") for p in ls.verify_db(str(other), m))
    forged = json.loads(json.dumps(m))
    forged["state_root"] = "0" * 64
    with pytest.raises(ls.SnapshotError, match="state_root does not follow"):
        ls.verify_db(str(src), forged)
    lying = json.loads(json.dumps(m))
    lying["summary"]["pending_max_id"] = 10 ** 9
    assert "summary differs from what the rows give" in ls.verify_db(str(src), lying)
    for breakage in ({"tables": {"balances": {"rows": "1", "sha256": "x"}}}, {"sequence": 0}, {"snapshot": {"file": "../../etc/passwd"}}):
        bad = dict(json.loads(json.dumps(m)), **breakage)
        with pytest.raises(ls.SnapshotError, match="malformed manifest"):
            ls.verify_db(str(src), bad)


def url(d):
    return Path(d).as_uri() + "/"


def do_pull(pub, dest, keys, **kw):
    return ls.pull(url(pub), str(keys / "pub.pem"), str(dest), **kw)


def replica_root(dest):
    return root_of(Path(dest) / "current" / "ledger.db")["state_root"]


def bump(src, n):
    c = sqlite3.connect(src)
    c.execute("INSERT INTO pending_ledger VALUES (?,11,1,'founder_community','x',1,'r','pending',NULL,NULL,11,21,NULL,?)", (n, f"h{n}"))
    c.commit()
    c.close()


def test_pull_installs_atomically_then_is_idempotent(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    snap(src, tmp_path / "pub", keys)
    dest = tmp_path / "replica"
    assert do_pull(tmp_path / "pub", dest, keys)["installed"] is True
    assert replica_root(dest) == root_of(src)["state_root"]
    assert os.path.islink(dest / "current")
    assert do_pull(tmp_path / "pub", dest, keys)["installed"] is False
    bump(src, 2)
    snap(src, tmp_path / "pub", keys)
    assert do_pull(tmp_path / "pub", dest, keys)["installed"] is True
    assert replica_root(dest) == root_of(src)["state_root"]
    visible = sorted(f for f in os.listdir(dest) if not f.startswith("."))
    assert len(visible) == 3 and visible[:2] == ["current", "high_water"]          # one version dir, no litter


def test_pull_rejects_wrong_signer_and_unsigned_changes(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys, key="other.key")                      # a mirror signing with its own key
    with pytest.raises(ls.SnapshotError, match="signature does not verify"):
        do_pull(pub, dest, keys)
    snap(src, pub, keys)
    env = json.loads((pub / "manifest.json").read_text())
    env["payload"] = env["payload"].replace('"node": "n1"', '"node": "ev"')
    assert '"node": "ev"' in env["payload"]
    (pub / "manifest.json").write_text(json.dumps(env))         # payload changed after signing
    with pytest.raises(ls.SnapshotError, match="signature does not verify"):
        do_pull(pub, dest, keys)
    assert not (dest / "current").exists()


def test_pull_rejects_tampered_snapshot_and_keeps_the_old_one(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys)
    do_pull(pub, dest, keys)
    good = replica_root(dest)
    bump(src, 2)
    m = snap(src, pub, keys)
    evil = tmp_path / "evil.db"
    evil.write_bytes(gzip.decompress(gz_path(pub, m).read_bytes()))
    c = sqlite3.connect(evil)
    c.execute("UPDATE balances SET amount_i64 = 999999999 WHERE miner_id = 'naïve-wallet'")
    c.commit()
    c.close()
    gz_path(pub, m).write_bytes(gzip.compress(evil.read_bytes()))
    with pytest.raises(ls.SnapshotError):
        do_pull(pub, dest, keys)
    assert replica_root(dest) == good


def test_pull_refuses_replay_of_an_older_signed_snapshot(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys)
    old = tmp_path / "old_pub"
    import shutil
    shutil.copytree(pub, old)
    # Same max ids, different state: a status flip must still count as newer.
    c = sqlite3.connect(src)
    c.execute("UPDATE pending_ledger SET status = 'voided'")
    c.commit()
    c.close()
    snap(src, pub, keys)
    do_pull(pub, dest, keys)
    with pytest.raises(ls.SnapshotError, match="not newer"):
        do_pull(old, dest, keys)
    assert do_pull(old, dest, keys, allow_regress=True)["installed"] is True


def test_pull_repairs_a_corrupted_install(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys)
    do_pull(pub, dest, keys)
    c = sqlite3.connect(dest / "current" / "ledger.db")
    c.execute("UPDATE balances SET amount_i64 = 1")
    c.commit()
    c.close()
    assert do_pull(pub, dest, keys)["installed"] is True
    assert replica_root(dest) == root_of(src)["state_root"]


def test_corruption_does_not_switch_off_replay_protection(tmp_path, keys):
    import shutil
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys)
    old = tmp_path / "old_pub"
    shutil.copytree(pub, old)
    bump(src, 2)
    snap(src, pub, keys)
    do_pull(pub, dest, keys)
    os.unlink(os.path.realpath(dest / "current" / "ledger.db"))     # the installed database is lost
    with pytest.raises(ls.SnapshotError, match="not newer"):
        do_pull(old, dest, keys)
    assert do_pull(pub, dest, keys)["installed"] is True             # the real current one repairs it


def test_missing_floor_is_rebuilt_only_from_a_signed_manifest(tmp_path, keys):
    import shutil
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys)
    old = tmp_path / "old_pub"
    shutil.copytree(pub, old)
    bump(src, 2)
    snap(src, pub, keys)
    do_pull(pub, dest, keys)
    os.unlink(dest / "high_water")
    os.unlink(os.path.realpath(dest / "current" / "ledger.db"))
    with pytest.raises(ls.SnapshotError, match="not newer"):
        do_pull(old, dest, keys)                                     # floor came back from the signed manifest
    os.unlink(dest / "high_water")
    (Path(os.path.realpath(dest / "current")) / "manifest.json").write_text("{}")
    with pytest.raises(ls.SnapshotError, match="no verifiable manifest"):
        do_pull(pub, dest, keys)


def test_same_ledger_republished_keeps_the_published_object(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    m1 = snap(src, tmp_path / "o", keys)
    before = os.stat(gz_path(tmp_path / "o", m1)).st_ino
    m2 = snap(src, tmp_path / "o", keys)
    assert m2["snapshot"]["file"] == m1["snapshot"]["file"] and m2["sequence"] > m1["sequence"]
    assert os.stat(gz_path(tmp_path / "o", m2)).st_ino == before      # not rewritten


def test_stale_work_is_swept_and_damaged_object_is_replaced(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    o = tmp_path / "o"
    m1 = snap(src, o, keys)
    (o / ".snap-killed").mkdir()
    (o / ".snap-killed" / "ledger.db").write_bytes(b"x" * 100)
    gz_path(o, m1).write_bytes(b"truncated")                          # the published object got damaged
    m2 = snap(src, o, keys)
    assert not (o / ".snap-killed").exists()
    dest = tmp_path / "replica"
    (dest / ".pull-killed").mkdir(parents=True)
    assert do_pull(o, dest, keys)["installed"] is True                # replica can use it again
    assert not (dest / ".pull-killed").exists()
    assert m2["snapshot"]["sha256"] != ls.hashlib.sha256(b"truncated").hexdigest()


def test_same_root_under_a_newer_sequence_moves_the_floor_without_reinstalling(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    snap(src, pub, keys)
    do_pull(pub, dest, keys)
    before = os.path.realpath(dest / "current")
    m2 = snap(src, pub, keys)
    assert do_pull(pub, dest, keys)["installed"] is False
    assert os.path.realpath(dest / "current") == before
    assert (dest / "high_water").read_text().split()[0] == str(m2["sequence"])


def test_low_disk_utf16_and_big_totals(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    with pytest.raises(ls.SnapshotError, match="free"):
        ls.make_snapshot(str(src), str(tmp_path / "o"), str(keys / "pub.key"), min_free_bytes=1 << 60)
    u = tmp_path / "u16.db"
    c = sqlite3.connect(u)
    c.execute("PRAGMA encoding = 'UTF-16le'")
    c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
    c.commit()
    c.close()
    with pytest.raises(ls.SnapshotError, match="UTF-8"):
        root_of(u)
    c = sqlite3.connect(src)
    c.executemany("INSERT INTO balances VALUES (?,?,NULL,0.0,NULL)", [("a-max", 2 ** 63 - 1), ("b-one", 1), ("c-neg", -1)])
    c.commit()
    c.close()
    assert root_of(src)["summary"]["total_balance_i64"] == 2 ** 63 - 1 + 6_500_000


def test_fetch_errors_are_snapshot_errors(tmp_path, keys):
    with pytest.raises(ls.SnapshotError, match="could not fetch"):
        ls.pull(Path(tmp_path / "nowhere").as_uri() + "/", str(keys / "pub.pem"), str(tmp_path / "r"))
    dest = tmp_path / "r2"
    (dest / "current").mkdir(parents=True)
    with pytest.raises(ls.SnapshotError, match="not a symlink"):
        ls.pull(Path(tmp_path / "nowhere").as_uri() + "/", str(keys / "pub.pem"), str(dest))


def test_manifest_must_carry_every_ledger_table(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    c = sqlite3.connect(src)
    c.execute("DROP TABLE headers")
    c.commit()
    c.close()
    assert root_of(src)["state_root"]                                # comparing is still allowed
    with pytest.raises(ls.SnapshotError, match="exactly these tables"):
        snap(src, tmp_path / "o", keys)                              # publishing is not


def test_pull_enforces_signed_sizes(tmp_path, keys):
    src = make_db(tmp_path / "src.db")
    pub, dest = tmp_path / "pub", tmp_path / "replica"
    m = snap(src, pub, keys)
    with pytest.raises(ls.SnapshotError, match="configured limit"):
        do_pull(pub, dest, keys, max_db_bytes=100)
    gz_path(pub, m).write_bytes(gzip.compress(b"\0" * (m["snapshot"]["db_bytes"] * 50)))   # a bomb
    with pytest.raises(ls.SnapshotError):
        do_pull(pub, dest, keys)
    assert not (dest / "current").exists()


def test_pull_refuses_plain_http(tmp_path, keys):
    with pytest.raises(ls.SnapshotError, match="non-https"):
        ls.pull("http://example.invalid/state/", str(keys / "pub.pem"), str(tmp_path / "r"))


def test_null_primary_key_and_odd_identifiers_are_refused(tmp_path):
    a = make_db(tmp_path / "a.db")
    c = sqlite3.connect(a)
    c.execute("INSERT INTO epoch_rewards VALUES (2, NULL, 1)")
    c.commit()
    c.close()
    with pytest.raises(ls.SnapshotError, match="NULL in a primary-key"):
        root_of(a)
    b = tmp_path / "b.db"
    c = sqlite3.connect(b)
    c.executescript('CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER, "x"" y" TEXT);'
                    "CREATE TABLE pending_ledger (id INTEGER PRIMARY KEY);")
    c.commit()
    c.close()
    with pytest.raises(ls.SnapshotError, match="unsupported identifier"):
        root_of(b)


def test_schema_is_part_of_the_root(tmp_path):
    a = make_db(tmp_path / "a.db")
    before = root_of(a)["state_root"]
    c = sqlite3.connect(a)
    c.execute("ALTER TABLE epoch_state ADD COLUMN note TEXT")
    c.commit()
    c.close()
    assert root_of(a)["state_root"] != before


def test_cli_exit_codes(tmp_path, keys, capsys):
    src = make_db(tmp_path / "src.db")
    o = tmp_path / "o"
    assert ls.main(["snapshot", "--db", str(src), "--out-dir", str(o), "--key", str(keys / "pub.key")]) == 0
    assert ls.main(["verify", "--db", str(src), "--manifest", str(o / "manifest.json"), "--pubkey", str(keys / "pub.pem")]) == 0
    assert ls.main(["verify", "--db", str(src), "--manifest", str(o / "manifest.json"), "--pubkey", str(keys / "other.pem")]) == 2
    other = make_db(tmp_path / "other.db", extra_balance=("extra", 5, None, 0.000005, None))
    assert ls.main(["verify", "--db", str(other), "--manifest", str(o / "manifest.json")]) == 1
    assert ls.main(["root", "--db", str(tmp_path / "missing.db")]) == 2
    assert ls.main(["keygen", "--key", str(keys / "pub.key"), "--pub", str(tmp_path / "x.pem")]) == 2   # no overwrite
    capsys.readouterr()
