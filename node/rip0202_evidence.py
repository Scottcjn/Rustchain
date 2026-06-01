#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-202 — B0-persist: raw attestation-evidence capture (additive, dormant).

Today ``/attest/submit`` derives ``device_family`` / ``device_arch`` /
``fingerprint_passed`` and DISCARDS the raw ``device`` + ``fingerprint`` dicts;
``miner_attest_recent`` never stores them. The producer therefore can't commit
the evidence B1 needs to re-derive enrollment (B0). This module captures that
evidence in an ADDITIVE side table so the producer can later read it.

Design:
  * PURE-except-DB: a caller supplies the connection; no global state, no
    wall-clock (``ts`` is passed in by the caller, i.e. the attestation ts).
  * FAIL CLOSED at capture: records are validated/canonicalised through
    ``rip0202_block_format.build_b0_attestation`` (rejects bad types + non-finite
    floats) BEFORE storage, so malformed evidence never persists and a later
    committed block can't carry it.
  * NON-DISRUPTIVE: a new ``attestation_evidence`` table; nothing existing reads
    or writes it. Wiring the one ``record_attestation_evidence`` call into
    ``_submit_attestation_impl`` and the join into ``get_attestations_for_block``
    are separate, low-risk follow-ups; this module ships unwired.
  * Canonical JSON storage (sort_keys, allow_nan=False) so device/fingerprint
    round-trip byte-stably for the B0 hash.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Mapping, Optional

from rip0202_block_format import build_b0_attestation, B0FormatError

ATTESTATION_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS attestation_evidence (
    miner              TEXT PRIMARY KEY,
    device_json        TEXT NOT NULL,
    fingerprint_json   TEXT NOT NULL,
    fingerprint_passed INTEGER NOT NULL,
    ts                 INTEGER NOT NULL
)
"""


def ensure_attestation_evidence_schema(conn: sqlite3.Connection) -> None:
    """Create the evidence table if absent. Call once at DB init (DDL implicit-
    commits — do NOT call inside a consensus transaction)."""
    conn.execute(ATTESTATION_EVIDENCE_SCHEMA)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, allow_nan=False)


def record_attestation_evidence(
    conn: sqlite3.Connection,
    miner: str,
    device: Mapping,
    fingerprint: Mapping,
    fingerprint_passed: bool,
    ts: int,
) -> None:
    """Validate (fail-closed) and upsert one miner's raw attestation evidence.

    Latest-evidence-per-miner (PRIMARY KEY miner, INSERT OR REPLACE), mirroring
    ``miner_attest_recent``'s per-miner keying. Raises B0FormatError on malformed
    input so the caller can reject the attestation rather than store junk.
    """
    rec = build_b0_attestation(miner, device, fingerprint, fingerprint_passed, ts)
    # TS-MONOTONIC upsert: only overwrite when the incoming attestation is at
    # least as new as the stored one. A delayed/replayed OLDER attestation must
    # not clobber newer evidence (which would silently drop a miner from the
    # producer's TTL-filtered view). Deterministic + order-independent.
    conn.execute(
        "INSERT INTO attestation_evidence "
        "(miner, device_json, fingerprint_json, fingerprint_passed, ts) VALUES (?,?,?,?,?) "
        "ON CONFLICT(miner) DO UPDATE SET "
        "device_json=excluded.device_json, fingerprint_json=excluded.fingerprint_json, "
        "fingerprint_passed=excluded.fingerprint_passed, ts=excluded.ts "
        "WHERE excluded.ts >= attestation_evidence.ts",
        (
            rec["miner"],
            _canonical(rec["device"]),
            _canonical(rec["fingerprint"]),
            1 if rec["fingerprint_passed"] else 0,
            rec["timestamp"],
        ),
    )


def load_committed_attestations(
    conn: sqlite3.Connection,
    min_ts: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Rebuild B0 attestation records from stored evidence (for the producer).

    Returns the widened ``build_b0_attestation`` records, sorted by miner for a
    stable base order. Rows that fail to parse/validate are skipped (fail
    closed) so one corrupt row can't break block production. ``min_ts`` mirrors
    the producer's ATTESTATION_TTL window when provided.
    """
    sql = "SELECT miner, device_json, fingerprint_json, fingerprint_passed, ts FROM attestation_evidence"
    params: tuple = ()
    if min_ts is not None:
        sql += " WHERE ts >= ?"
        params = (min_ts,)
    sql += " ORDER BY miner"
    out: List[Dict[str, Any]] = []
    for miner, dev_j, fp_j, passed, ts in conn.execute(sql, params).fetchall():
        try:
            # Strict stored-type validation (fail closed): a corrupt row with
            # passed=2 or ts=1.9 must be skipped, NOT loosely coerced via
            # bool()/int() (which would admit garbage into the committed set).
            if passed not in (0, 1):
                continue
            if isinstance(ts, bool) or not isinstance(ts, int):
                continue
            device = json.loads(dev_j)
            fingerprint = json.loads(fp_j)
            out.append(
                build_b0_attestation(miner, device, fingerprint, passed == 1, ts)
            )
        except (json.JSONDecodeError, B0FormatError, TypeError, ValueError):
            continue  # fail closed: skip a corrupt/invalid row
    return out
