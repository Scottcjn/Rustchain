#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Signed ledger snapshots with a checkable state root.

The settlement node keeps the ledger in one SQLite database. This tool lets
other machines hold a copy of that ledger and prove it is the same one::

    # once, on the settlement node: create the publisher key
    python tools/ledger_snapshot.py keygen --key /etc/rustchain-state/publisher.key --pub publisher.pub

    # settlement node, on a timer: publish a signed snapshot
    python tools/ledger_snapshot.py snapshot --db rustchain_v2.db \\
        --out-dir /var/lib/rustchain-state --key /etc/rustchain-state/publisher.key

    # anyone holding a database or a snapshot: recompute the root
    python tools/ledger_snapshot.py root --db ledger.db
    python tools/ledger_snapshot.py verify --db ledger.db --manifest manifest.json

    # replica, on a timer: fetch, verify, install
    python tools/ledger_snapshot.py pull --base-url https://rustchain.org/state/ \\
        --pubkey /etc/rustchain-replica/publisher.pub --dest-dir /var/lib/rustchain-replica

What is covered: the tables in ``LEDGER_TABLES`` (balances, transfers, the
reward history, the UTXO set and its account mirror). Attestation, fingerprint
and rate-limit tables are deliberately left out: they hold miner IP addresses
and hardware details and are not part of what a balance depends on.

State root: for every covered table a schema line (column names, declared
types, primary key) and then every row in primary-key order are written as
canonical JSON lines and hashed with SHA-256. The root is the SHA-256 of the
canonical JSON of ``{table: table_hash}``. Two databases have the same root
exactly when every covered table has the same columns and the same rows.

Trust: the publisher signs the exact bytes of ``manifest.json`` with an
Ed25519 key. A replica pins the public key, checks the signature before it
reads a single field, recomputes the root from the rows it downloaded, and
installs nothing unless everything matches. Every manifest carries a strictly
increasing ``sequence``; a replica refuses anything that is not newer than
what it holds, so an old signed snapshot cannot be replayed at it.

One publisher per key. The sequence is a local counter that never falls below
the clock, so a publisher restored from backup keeps moving forward; it is not
a distributed counter. Do not run two publishers with the same key, and if a
publisher's state is ever lost or its clock was wrong, create a new key and
re-pin the replicas instead of guessing.

Published layout (``--out-dir``)::

    manifest.json                               safe to serve to anyone: one file holding the
                                                manifest text and its signature
    snapshots/ledger-<root>-<dbhash>.db.gz      serve to replicas; never rewritten
    (sequence, .lock: internal, do not serve)

Replica layout (``--dest-dir``): ``current`` is a symlink to a directory
holding ``ledger.db`` and the signed ``manifest.json``; it is switched in one rename.

The source database is only ever opened read-only, for one short read
transaction. Standard library plus the ``openssl`` binary (3.0+) for Ed25519.
Python 3.9+.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional, Tuple

FORMAT = 2
KEEP_SNAPSHOTS = 3
MAX_MANIFEST_BYTES = 1 << 20
DEFAULT_MAX_DB_BYTES = 1 << 30      # the ledger snapshot (a few MB today), not the node's whole database
DEFAULT_MIN_FREE_BYTES = 1 << 30
MAX_SNAPSHOT_SOURCE_BYTES = 256 << 20

# table -> columns left out of the copy and of the hash.
# balances.balance_rtc is a float rendering of amount_i64; floats do not have
# one canonical text form, and the integer column is the balance.
LEDGER_TABLES: Dict[str, Tuple[str, ...]] = {
    "balances": ("balance_rtc",),
    "pending_ledger": (),
    "ledger": (),
    "epoch_state": (),
    "epoch_rewards": (),
    "epoch_enroll": (),
    "utxo_boxes": (),
    "utxo_transactions": (),
    "account_mirror_boxes": (),
    "lock_ledger": (),
    "headers": (),
}
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_ ]*(\(\s*\d+(\s*,\s*\d+)?\s*\))?$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SUMMARY_KEYS = ("wallets", "total_balance_i64", "pending_max_id", "ledger_max_id", "last_settled_epoch")


class SnapshotError(Exception):
    """A snapshot could not be produced, or failed verification."""


# ---------------------------------------------------------------- hashing

def _q(name: str) -> str:
    if not _IDENT.match(name):
        raise SnapshotError(f"unsupported identifier in a ledger table: {name!r}")
    return '"' + name + '"'


def _connect_ro(path: str) -> sqlite3.Connection:
    if not os.path.isfile(path):
        raise SnapshotError(f"database not found: {path}")
    conn = sqlite3.connect("file:" + urllib.parse.quote(os.path.abspath(path)) + "?mode=ro", uri=True, timeout=30)
    conn.execute("PRAGMA query_only = ON")
    # Key order is defined on UTF-8 bytes. A UTF-16 database would order text keys differently.
    if conn.execute("PRAGMA encoding").fetchone()[0].upper() != "UTF-8":
        conn.close()
        raise SnapshotError(f"{path}: only UTF-8 databases are supported")
    return conn


def _table_layout(conn: sqlite3.Connection, table: str) -> Optional[Tuple[List[Tuple[str, str]], List[str]]]:
    """Return ([(column, declared_type)], [pk columns in key order]) or None if the table is absent."""
    info = conn.execute(f"PRAGMA table_xinfo({_q(table)})").fetchall()
    if not info:
        return None
    skip = set(LEDGER_TABLES[table])
    cols = []
    for _cid, name, typ, _notnull, _dflt, _pk, hidden in info:
        if hidden:
            raise SnapshotError(f"{table}.{name}: generated/hidden columns are not supported in a ledger table")
        typ = (typ or "").strip().upper()
        if typ and not _TYPE.match(typ):
            raise SnapshotError(f"{table}.{name}: unsupported declared type {typ!r}")
        _q(name)
        if name not in skip:
            cols.append((name, typ))
    pk = [r[1] for r in sorted((r for r in info if r[5] > 0), key=lambda r: r[5])]
    if not pk:
        raise SnapshotError(f"table {table} has no primary key; refusing to guess a row order")
    if any(c in skip for c in pk):
        raise SnapshotError(f"table {table}: a primary-key column is excluded from the hash")
    return cols, pk


def _canonical(value):
    if value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, bytes):
        return {"b": value.hex()}
    # A float here means a REAL value reached a ledger column. Fail loudly
    # instead of hashing a platform-dependent rendering.
    raise SnapshotError(f"non-canonical value of type {type(value).__name__} in a ledger table")


def _line(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def _hash_table(conn: sqlite3.Connection, table: str, sink=None) -> Optional[dict]:
    layout = _table_layout(conn, table)
    if layout is None:
        return None
    cols, pk = layout
    names = [c for c, _ in cols]
    pk_idx = [names.index(c) for c in pk]
    h = hashlib.sha256()
    h.update(_line({"columns": [[c, t] for c, t in cols], "primary_key": pk}))
    col_sql = ", ".join(_q(c) for c in names)
    # BINARY collation and an explicit key order: the row order must not depend on the table's own collations.
    order = ", ".join(f"{_q(c)} COLLATE BINARY" for c in pk)
    n = 0
    prev_key = None
    batch = []
    for row in conn.execute(f"SELECT {col_sql} FROM {_q(table)} ORDER BY {order}"):  # nosec B608 - identifiers validated by _q
        key = tuple(row[i] for i in pk_idx)
        if any(v is None for v in key):
            raise SnapshotError(f"{table}: NULL in a primary-key column; row order would be ambiguous")
        if key == prev_key:
            raise SnapshotError(f"{table}: duplicate primary key {key!r}")
        prev_key = key
        h.update(_line([_canonical(v) for v in row]))
        n += 1
        if sink is not None:
            batch.append(row)
            if len(batch) >= 2000:
                sink(table, cols, pk, batch)
                batch = []
    if sink is not None:
        sink(table, cols, pk, batch)
    return {"rows": n, "sha256": h.hexdigest()}


def state_root(tables: Dict[str, dict]) -> str:
    body = {"format": FORMAT, "tables": {t: tables[t]["sha256"] for t in sorted(tables)}}
    return hashlib.sha256(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def _summary(conn: sqlite3.Connection, present: Iterable[str]) -> dict:
    present = set(present)

    def one(sql):
        return conn.execute(sql).fetchone()[0]

    total = 0     # summed here, not in SQL: SQLite's SUM can overflow part-way even when the total fits
    for (amount,) in conn.execute("SELECT amount_i64 FROM balances"):
        if amount is not None:
            if not isinstance(amount, int):
                raise SnapshotError("balances.amount_i64 holds a non-integer value")
            total += amount
    out = {"wallets": one("SELECT COUNT(*) FROM balances"),
           "total_balance_i64": total,
           "pending_max_id": one("SELECT COALESCE(MAX(id), 0) FROM pending_ledger")}
    if "ledger" in present:
        out["ledger_max_id"] = one("SELECT COALESCE(MAX(id), 0) FROM ledger")
    if "epoch_state" in present:
        out["last_settled_epoch"] = one("SELECT COALESCE(MAX(epoch), -1) FROM epoch_state WHERE settled = 1")
    return out


def compute(conn: sqlite3.Connection, sink=None) -> dict:
    """Hash every covered table inside one read transaction (one consistent view)."""
    conn.execute("BEGIN")
    try:
        tables = {}
        for t in LEDGER_TABLES:
            res = _hash_table(conn, t, sink)
            if res is not None:
                tables[t] = res
        if "balances" not in tables or "pending_ledger" not in tables:
            raise SnapshotError("not a ledger database: balances and pending_ledger are required")
        return {"format": FORMAT, "state_root": state_root(tables), "tables": tables,
                "summary": _summary(conn, tables)}
    finally:
        conn.execute("ROLLBACK")


def compute_path(db: str) -> dict:
    conn = _connect_ro(db)
    try:
        return compute(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------- files

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_atomic(path: str, data: bytes, mode: int = 0o644) -> None:
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d)  # random name, O_EXCL: never follows a planted symlink
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        _fsync_dir(d)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _sweep(directory: str) -> None:
    """Remove work left behind by a killed run. Call only while holding the directory lock."""
    for name in os.listdir(directory):
        if re.fullmatch(r"\.(snap|pull|tmp)-[A-Za-z0-9_]+", name):
            path = os.path.join(directory, name)
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def _gunzip_sha256(path: str, limit: int) -> Optional[str]:
    h, n = hashlib.sha256(), 0
    try:
        with gzip.open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                n += len(chunk)
                if n > limit:
                    return None
                h.update(chunk)
    except (OSError, EOFError):
        return None
    return h.hexdigest()


class _Lock:
    def __init__(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        self._f = open(os.path.join(directory, ".lock"), "a+")

    def __enter__(self):
        try:
            fcntl.flock(self._f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._f.close()
            raise SnapshotError("another snapshot/pull is already running in this directory")
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._f, fcntl.LOCK_UN)
        self._f.close()


# ---------------------------------------------------------------- signatures (Ed25519 via openssl)

def _openssl(args: List[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["openssl"] + args, capture_output=True, timeout=30)  # nosec B603 B607 - fixed argv
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SnapshotError(f"openssl is required for signatures: {e}")


def keygen(key_path: str, pub_path: str) -> None:
    if os.path.exists(key_path):
        raise SnapshotError(f"refusing to overwrite an existing key: {key_path}")
    os.makedirs(os.path.dirname(os.path.abspath(key_path)), exist_ok=True)
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    r = _openssl(["genpkey", "-algorithm", "ED25519", "-out", key_path])
    if r.returncode != 0:
        os.unlink(key_path)
        raise SnapshotError("openssl could not create an Ed25519 key: " + r.stderr.decode(errors="replace")[:200])
    os.chmod(key_path, 0o600)
    r = _openssl(["pkey", "-in", key_path, "-pubout", "-out", pub_path])
    if r.returncode != 0:
        os.unlink(key_path)
        raise SnapshotError("openssl could not export the public key")


def _sign(key_path: str, data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        msg, sig = os.path.join(d, "m"), os.path.join(d, "s")
        with open(msg, "wb") as f:
            f.write(data)
        r = _openssl(["pkeyutl", "-sign", "-inkey", key_path, "-rawin", "-in", msg, "-out", sig])
        if r.returncode != 0:
            raise SnapshotError("signing failed: " + r.stderr.decode(errors="replace")[:200])
        with open(sig, "rb") as f:
            raw = f.read()
    if len(raw) != 64:
        raise SnapshotError("unexpected signature length (is the key Ed25519?)")
    return base64.b64encode(raw) + b"\n"


def _verify_sig(pub_path: str, data: bytes, sig_b64: bytes) -> None:
    if not os.path.isfile(pub_path):
        raise SnapshotError(f"publisher public key not found: {pub_path}")
    try:
        raw = base64.b64decode(sig_b64.strip(), validate=True)
    except ValueError:
        raise SnapshotError("manifest signature is not valid base64")
    if len(raw) != 64:
        raise SnapshotError("manifest signature has the wrong length")
    with tempfile.TemporaryDirectory() as d:
        msg, sig = os.path.join(d, "m"), os.path.join(d, "s")
        with open(msg, "wb") as f:
            f.write(data)
        with open(sig, "wb") as f:
            f.write(raw)
        r = _openssl(["pkeyutl", "-verify", "-pubin", "-inkey", pub_path, "-rawin", "-in", msg, "-sigfile", sig])
    if r.returncode != 0:
        raise SnapshotError("manifest signature does not verify against the pinned publisher key")


# ---------------------------------------------------------------- manifest

def _envelope(body: bytes, sig_b64: bytes) -> bytes:
    """One file = manifest text + signature, so the pair can never be published half-updated."""
    return (json.dumps({"payload": body.decode(), "signature": sig_b64.decode().strip(), "alg": "ed25519"},
                       indent=1, sort_keys=True) + "\n").encode()


def open_envelope(raw: bytes, pubkey: Optional[str]) -> Tuple[dict, bytes]:
    """Verify (when ``pubkey`` is given) and parse a signed manifest. Returns (manifest, raw)."""
    try:
        env = json.loads(raw)
        payload, sig = env["payload"], env["signature"]
        if not isinstance(payload, str) or not isinstance(sig, str) or env.get("alg") != "ed25519":
            raise KeyError("fields")
        payload_bytes = payload.encode()
    except (ValueError, KeyError, TypeError):
        raise SnapshotError("not a signed ledger manifest")
    if pubkey is not None:
        _verify_sig(pubkey, payload_bytes, sig.encode())     # exact signed bytes, before any field is believed
    try:
        return _check_manifest(json.loads(payload)), raw
    except ValueError:
        raise SnapshotError("signed payload is not JSON")


def _check_manifest(m) -> dict:
    """Structural validation. Raises SnapshotError; returns the manifest."""
    def bad(why):
        raise SnapshotError("malformed manifest: " + why)

    def is_int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    if not isinstance(m, dict) or m.get("format") != FORMAT:
        bad(f"not a format-{FORMAT} ledger manifest")
    if not is_int(m.get("sequence")) or m["sequence"] < 1:
        bad("sequence")
    if not isinstance(m.get("state_root"), str) or not _HEX64.match(m["state_root"]):
        bad("state_root")
    tables = m.get("tables")
    if not isinstance(tables, dict) or not tables:
        bad("tables")
    for name, t in tables.items():
        if name not in LEDGER_TABLES:
            bad(f"unknown table {name!r}")
        if not isinstance(t, dict) or not is_int(t.get("rows")) or t["rows"] < 0 \
                or not isinstance(t.get("sha256"), str) or not _HEX64.match(t["sha256"]):
            bad(f"table entry {name!r}")
    if set(tables) != set(LEDGER_TABLES):
        bad("a published ledger must carry exactly these tables: " + ", ".join(sorted(LEDGER_TABLES)))
    if state_root(tables) != m["state_root"]:
        bad("state_root does not follow from the table hashes")
    summary = m.get("summary")
    if not isinstance(summary, dict) or set(summary) != set(_SUMMARY_KEYS) or not all(is_int(v) for v in summary.values()):
        bad("summary")
    snap = m.get("snapshot")
    if not isinstance(snap, dict) or not isinstance(snap.get("file"), str) \
            or not all(isinstance(snap.get(k), str) and _HEX64.match(snap[k]) for k in ("sha256", "db_sha256")) \
            or snap["file"] != f"ledger-{m['state_root']}-{snap['db_sha256'][:16]}.db.gz" \
            or not all(is_int(snap.get(k)) and snap[k] > 0 for k in ("bytes", "db_bytes")):
        bad("snapshot")
    return m


def verify_db(db: str, manifest: dict) -> List[str]:
    """Return a list of problems (empty when ``db`` matches ``manifest`` in rows, counts and summary)."""
    _check_manifest(manifest)
    got = compute_path(db)
    problems = []
    want_tables = manifest["tables"]
    for t in sorted(set(want_tables) | set(got["tables"])):
        w, g = want_tables.get(t), got["tables"].get(t)
        if w is None:
            problems.append(f"{t}: present here, absent from the manifest")
        elif g is None:
            problems.append(f"{t}: in the manifest, missing here")
        elif w["sha256"] != g["sha256"] or w["rows"] != g["rows"]:
            problems.append(f"{t}: differs (rows here {g['rows']}, manifest {w['rows']})")
    if got["summary"] != manifest["summary"]:
        problems.append("summary differs from what the rows give")
    if got["state_root"] != manifest["state_root"] and not problems:
        problems.append("state root differs")
    return problems


# ---------------------------------------------------------------- publisher

def make_snapshot(db: str, out_dir: str, key_path: str, node: str = "",
                  min_free_bytes: int = DEFAULT_MIN_FREE_BYTES) -> dict:
    """Publish ``snapshots/ledger-<root>.db.gz`` and a signed ``manifest.json`` under ``out_dir``."""
    if not os.path.isfile(key_path):
        raise SnapshotError(f"publisher key not found: {key_path}")
    pub_dir, snap_dir = out_dir, os.path.join(out_dir, "snapshots")
    with _Lock(out_dir):
        os.makedirs(snap_dir, exist_ok=True)
        _sweep(out_dir)
        # The scratch copy shares a filesystem with whatever else lives here; never start a run that
        # could eat the space a live database needs to keep writing.
        if shutil.disk_usage(out_dir).free < min_free_bytes:
            raise SnapshotError(f"less than {min_free_bytes} bytes free under {out_dir}; not snapshotting")
        work = tempfile.mkdtemp(prefix=".snap-", dir=out_dir)
        try:
            out_db = os.path.join(work, "ledger.db")
            dst = sqlite3.connect(out_db)
            created = set()

            def sink(table, cols, pk, rows):
                if table not in created:
                    col_sql = ", ".join((_q(c) + " " + typ).rstrip() for c, typ in cols)
                    key = ", ".join(_q(c) for c in pk)
                    # WITHOUT ROWID keeps key columns exactly as stored (no rowid aliasing) for every key shape.
                    dst.execute(f"CREATE TABLE {_q(table)} ({col_sql}, PRIMARY KEY ({key})) WITHOUT ROWID")
                    created.add(table)
                if rows:
                    dst.executemany(f"INSERT INTO {_q(table)} VALUES ({','.join('?' * len(cols))})", rows)  # nosec B608

            src = _connect_ro(db)
            try:
                result = compute(src, sink)   # one short read transaction on the live database
            finally:
                src.close()
            dst.commit()
            dst.close()     # rows went in key order into a fresh file; no VACUUM, so no second full copy on disk
            if os.path.getsize(out_db) > MAX_SNAPSHOT_SOURCE_BYTES:
                raise SnapshotError("ledger snapshot is larger than expected; raise MAX_SNAPSHOT_SOURCE_BYTES deliberately")

            # The copy must hash to the same root as the source it was read from
            # (catches any value changed by type affinity on the way in).
            again = compute_path(out_db)
            if again != result:
                raise SnapshotError("snapshot does not hash to the source's state root; not publishing")

            seq_path = os.path.join(out_dir, "sequence")
            try:
                with open(seq_path) as f:
                    seq = int(f.read().strip())
            except FileNotFoundError:
                seq = 0
            except ValueError:
                raise SnapshotError(f"corrupt sequence file: {seq_path}")
            # Never below the clock: a publisher restored from an old backup still moves forward.
            seq = max(seq + 1, int(time.time()))

            db_sha = _sha256_file(out_db)
            name = f"ledger-{result['state_root']}-{db_sha[:16]}.db.gz"
            gz = os.path.join(work, name)
            target = os.path.join(snap_dir, name)
            with open(out_db, "rb") as fin, open(gz, "wb") as raw:
                with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as fout:
                    shutil.copyfileobj(fin, fout, 1 << 20)
                raw.flush()
                os.fsync(raw.fileno())
            os.chmod(gz, 0o644)
            # Published objects are immutable: same name means same database bytes, so reuse what is there.
            reuse = os.path.isfile(target) and _gunzip_sha256(target, os.path.getsize(out_db)) == db_sha
            final_gz = target if reuse else gz      # a damaged object on disk is replaced, not re-signed
            manifest = dict(result)
            manifest["sequence"] = seq
            manifest["created_at"] = int(time.time())
            manifest["node"] = node
            manifest["snapshot"] = {"file": name, "sha256": _sha256_file(final_gz), "bytes": os.path.getsize(final_gz),
                                    "db_sha256": db_sha, "db_bytes": os.path.getsize(out_db)}
            _check_manifest(manifest)
            body = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
            sig = _sign(key_path, body)

            # Order matters: the snapshot file exists before any manifest names it; the sequence is burned
            # before the manifest is visible, so a crash can skip a number but never reuse one.
            if final_gz is target:
                os.utime(target)          # keep it out of the pruning below
            else:
                os.replace(gz, target)
            _fsync_dir(snap_dir)
            _write_atomic(seq_path, f"{seq}\n".encode())
            _write_atomic(os.path.join(pub_dir, "manifest.json"), _envelope(body, sig))   # one atomic rename

            keep = sorted((f for f in os.listdir(snap_dir) if re.fullmatch(r"ledger-[0-9a-f]{64}-[0-9a-f]{16}\.db\.gz", f)),
                          key=lambda f: os.path.getmtime(os.path.join(snap_dir, f)), reverse=True)
            for old in keep[KEEP_SNAPSHOTS:]:
                if old != name:
                    os.unlink(os.path.join(snap_dir, old))
            return manifest
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- replica

class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise SnapshotError(f"refusing redirect to a non-https URL: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str, timeout: int, max_bytes: int, dest: Optional[str] = None) -> bytes:
    if not (url.startswith("https://") or url.startswith("file:///")):
        raise SnapshotError(f"refusing non-https URL: {url}")
    opener = urllib.request.build_opener(_HttpsOnly())
    req = urllib.request.Request(url, headers={"User-Agent": "rustchain-ledger-replica/2"})
    out = bytearray()
    deadline = time.monotonic() + max(timeout, 1) * 10     # whole transfer, so a trickling server cannot hold the lock
    try:
        return _fetch_body(opener, req, url, timeout, max_bytes, dest, out, deadline)
    except SnapshotError:
        raise
    except (OSError, ValueError) as e:
        raise SnapshotError(f"could not fetch {url}: {e}")


def _fetch_body(opener, req, url, timeout, max_bytes, dest, out, deadline) -> bytes:
    with opener.open(req, timeout=timeout) as r:  # nosec B310 - scheme checked above and on every redirect
        f = open(dest, "wb") if dest else None
        read = getattr(r, "read1", None) or r.read
        try:
            total = 0
            for chunk in iter(lambda: read(1 << 16), b""):
                if time.monotonic() > deadline:
                    raise SnapshotError(f"transfer took too long: {url}")
                total += len(chunk)
                if total > max_bytes:
                    raise SnapshotError(f"download larger than {max_bytes} bytes: {url}")
                if f:
                    f.write(chunk)
                else:
                    out += chunk
            if f:
                f.flush()
                os.fsync(f.fileno())
        finally:
            if f:
                f.close()
    return bytes(out)


def _installed(dest_dir: str) -> Optional[dict]:
    """The installed manifest, only if the installed database really matches it."""
    cur = os.path.join(dest_dir, "current")
    mpath, dpath = os.path.join(cur, "manifest.json"), os.path.join(cur, "ledger.db")
    if not (os.path.isfile(mpath) and os.path.isfile(dpath)):
        return None
    try:
        with open(mpath, "rb") as f:
            m, _ = open_envelope(f.read(), None)
        return m if not verify_db(dpath, m) else None
    except (SnapshotError, ValueError, OSError, sqlite3.Error):
        return None


def pull(base_url: str, pubkey: str, dest_dir: str, timeout: int = 120,
         max_db_bytes: int = DEFAULT_MAX_DB_BYTES, allow_regress: bool = False) -> dict:
    """Fetch, verify and install a snapshot. Raises SnapshotError and installs nothing on any doubt."""
    if not base_url.endswith("/"):
        base_url += "/"
    with _Lock(dest_dir):
        _sweep(dest_dir)
        cur_link = os.path.join(dest_dir, "current")
        if os.path.lexists(cur_link) and not os.path.islink(cur_link):
            raise SnapshotError(f"{cur_link} exists and is not a symlink; move {dest_dir} aside to start clean")
        manifest, body = open_envelope(_fetch(base_url + "manifest.json", timeout, MAX_MANIFEST_BYTES), pubkey)

        # The high-water mark lives in its own file, so a damaged or missing database cannot switch
        # replay protection off: only the exact snapshot last installed may be installed again (repair).
        hw_path = os.path.join(dest_dir, "high_water")
        hw_seq, hw_root = 0, ""
        cur_manifest = os.path.join(dest_dir, "current", "manifest.json")
        if not os.path.isfile(hw_path) and os.path.lexists(os.path.join(dest_dir, "current")):
            # An install without a floor (older layout, or the file was removed): rebuild the floor from the
            # installed manifest, but only if the pinned key signed it. Otherwise stop and let a human look.
            try:
                with open(cur_manifest, "rb") as f:
                    m0, _ = open_envelope(f.read(), pubkey)
            except (OSError, SnapshotError) as e:
                raise SnapshotError(f"installed replica has no high_water file and no verifiable manifest ({e}); "
                                    f"move {dest_dir} aside to start clean")
            _write_atomic(hw_path, f"{m0['sequence']} {m0['state_root']}\n".encode())
        if os.path.isfile(hw_path):
            try:
                with open(hw_path) as f:
                    a, b = f.read().split()
                hw_seq, hw_root = int(a), b
            except (ValueError, OSError):
                raise SnapshotError(f"unreadable high-water file {hw_path}; fix or remove it deliberately")
        if not allow_regress:
            if manifest["sequence"] < hw_seq or (manifest["sequence"] == hw_seq and manifest["state_root"] != hw_root):
                raise SnapshotError(f"offered snapshot is not newer than the installed one "
                                    f"(sequence {manifest['sequence']} vs {hw_seq}). If the publisher was "
                                    f"deliberately rolled back or re-keyed, run once with --allow-regress")
        current = _installed(dest_dir)
        if current is not None and current["state_root"] == manifest["state_root"]:
            # Same ledger. If the publisher re-signed it under a newer sequence, keep the signed proof of
            # that and move the floor, without downloading the same rows again.
            if current["sequence"] != manifest["sequence"]:
                _write_atomic(os.path.join(os.path.realpath(cur_link), "manifest.json"), body)
                _write_atomic(hw_path, f"{manifest['sequence']} {manifest['state_root']}\n".encode())
            return {"installed": False, "reason": "already current", "state_root": manifest["state_root"],
                    "sequence": manifest["sequence"], "source_created_at": manifest.get("created_at")}
        snap = manifest["snapshot"]
        if snap["db_bytes"] > max_db_bytes or snap["bytes"] > max_db_bytes:
            raise SnapshotError(f"snapshot larger than the configured limit of {max_db_bytes} bytes")
        free = shutil.disk_usage(dest_dir).free
        if free < 2 * snap["db_bytes"] + snap["bytes"] + (64 << 20):
            raise SnapshotError("not enough free disk space for this snapshot")

        version = f"v{manifest['sequence']}-{manifest['state_root'][:16]}-{os.urandom(4).hex()}"
        work = tempfile.mkdtemp(prefix=".pull-", dir=dest_dir)
        try:
            gz = os.path.join(work, "ledger.db.gz")
            _fetch(base_url + "snapshots/" + snap["file"], timeout, snap["bytes"], gz)
            if os.path.getsize(gz) != snap["bytes"] or _sha256_file(gz) != snap["sha256"]:
                raise SnapshotError("downloaded snapshot does not match the signed file hash")
            stage = os.path.join(work, version)
            os.mkdir(stage)
            db = os.path.join(stage, "ledger.db")
            written = 0
            with gzip.open(gz, "rb") as fin, open(db, "wb") as fout:
                for chunk in iter(lambda: fin.read(1 << 20), b""):
                    written += len(chunk)
                    if written > snap["db_bytes"]:
                        raise SnapshotError("snapshot expands beyond its signed size")
                    fout.write(chunk)
                fout.flush()
                os.fsync(fout.fileno())
            os.unlink(gz)
            if written != snap["db_bytes"] or _sha256_file(db) != snap["db_sha256"]:
                raise SnapshotError("expanded snapshot does not match the signed database hash")
            chk = sqlite3.connect("file:" + urllib.parse.quote(db) + "?mode=ro", uri=True)
            try:
                if chk.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise SnapshotError("downloaded snapshot fails SQLite integrity_check")
            finally:
                chk.close()
            problems = verify_db(db, manifest)
            if problems:
                raise SnapshotError("downloaded snapshot does not match its manifest: " + "; ".join(problems))
            for leftover in (db + "-wal", db + "-shm", db + "-journal"):
                if os.path.exists(leftover):
                    os.unlink(leftover)
            os.chmod(db, 0o644)
            _write_atomic(os.path.join(stage, "manifest.json"), body)
            _fsync_dir(stage)

            final = os.path.join(dest_dir, version)      # fresh name every time: never touches the live copy
            os.rename(stage, final)
            _fsync_dir(dest_dir)
            _write_atomic(hw_path, f"{manifest['sequence']} {manifest['state_root']}\n".encode())
            link = os.path.join(work, "current")
            os.symlink(version, link)
            os.replace(link, os.path.join(dest_dir, "current"))   # database and manifest switch together
            _fsync_dir(dest_dir)
            for old in os.listdir(dest_dir):
                if re.fullmatch(r"v\d+-[0-9a-f]{16}-[0-9a-f]{8}", old) and old != version:
                    shutil.rmtree(os.path.join(dest_dir, old), ignore_errors=True)
            return {"installed": True, "state_root": manifest["state_root"], "sequence": manifest["sequence"],
                    "source_created_at": manifest.get("created_at"), "summary": manifest["summary"]}
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="RustChain signed ledger snapshots with a checkable state root")
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen", help="create the publisher's Ed25519 key pair")
    k.add_argument("--key", required=True)
    k.add_argument("--pub", required=True)
    s = sub.add_parser("snapshot", help="publish a signed snapshot")
    s.add_argument("--db", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--key", required=True, help="publisher private key (PEM, Ed25519)")
    s.add_argument("--node", default="", help="label recorded in the manifest (not part of the root)")
    s.add_argument("--min-free-bytes", type=int, default=DEFAULT_MIN_FREE_BYTES,
                   help="refuse to run with less free space than this under --out-dir")
    r = sub.add_parser("root", help="print the state root of a database or snapshot")
    r.add_argument("--db", required=True)
    r.add_argument("--json", action="store_true")
    v = sub.add_parser("verify", help="check a database against a manifest (optionally its signature too)")
    v.add_argument("--db", required=True)
    v.add_argument("--manifest", required=True)
    v.add_argument("--pubkey", help="also verify the manifest's signature against this public key")
    f = sub.add_parser("pull", help="fetch, verify and install a snapshot (replica)")
    f.add_argument("--base-url", required=True, help="https URL of the published directory (holds manifest.json)")
    f.add_argument("--pubkey", required=True, help="pinned publisher public key (PEM)")
    f.add_argument("--dest-dir", required=True)
    f.add_argument("--timeout", type=int, default=120)
    f.add_argument("--max-db-bytes", type=int, default=DEFAULT_MAX_DB_BYTES)
    f.add_argument("--allow-regress", action="store_true",
                   help="accept a snapshot that is not newer than the installed one (after a deliberate rollback)")
    a = p.parse_args(argv)
    try:
        if a.cmd == "keygen":
            keygen(a.key, a.pub)
            print(f"wrote {a.key} (keep private) and {a.pub} (give to replicas)")
        elif a.cmd == "snapshot":
            m = make_snapshot(a.db, a.out_dir, a.key, a.node, a.min_free_bytes)
            print(f"sequence {m['sequence']}  state_root {m['state_root']}  wallets {m['summary']['wallets']}  "
                  f"pending_max_id {m['summary']['pending_max_id']}  snapshot {m['snapshot']['bytes']} bytes")
        elif a.cmd == "root":
            res = compute_path(a.db)
            print(json.dumps(res, indent=1, sort_keys=True) if a.json else res["state_root"])
        elif a.cmd == "verify":
            with open(a.manifest, "rb") as fh:
                manifest, _ = open_envelope(fh.read(), a.pubkey)
            problems = verify_db(a.db, manifest)
            if problems:
                print("MISMATCH")
                for line in problems:
                    print("  " + line)
                return 1
            print("ok: database matches the manifest's state root" + (" and the signature verifies" if a.pubkey else ""))
        elif a.cmd == "pull":
            print(json.dumps(pull(a.base_url, a.pubkey, a.dest_dir, a.timeout, a.max_db_bytes, a.allow_regress),
                             sort_keys=True))
    except (SnapshotError, sqlite3.Error, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
