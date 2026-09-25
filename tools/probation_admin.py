#!/usr/bin/env python3
"""probation_admin.py -- operator tool for the SYBIL-GUARD probation tables.

Run on the node, next to sybil_guard.py (operator only):
  ssh <node> 'cd <node-dir> && python3 - list' < tools/probation_admin.py
  ssh <node> 'cd <node-dir> && python3 - show RTCabc...' < tools/probation_admin.py
  ssh <node> 'cd <node-dir> && python3 - release RTCabc... --reason "verified G4 owner"' < tools/probation_admin.py
      (prints the plan; add --apply to write)
  python3 probation_admin.py allowlist

SCOPE: reads anything it needs, but WRITES ONLY the guard's own tables:
  miner_probation (the one row being released) and sybil_guard_admin_audit
  (created on first --apply). It never writes balances, ledger, epoch_enroll,
  sybil_review_escrow or the cohort table.

WHAT RELEASE DOES (and does not do)
  * clears needs_review / review_reason on the miner's miner_probation row;
  * state: -> grandfathered if the miner attested before the cutoff;
           -> trusted if --trust (skips the rest of probation; no exit caps);
           -> otherwise unchanged (it keeps working through probation normally).
  * writes one audit row: who (--operator, default $SUDO_USER/$USER), when,
    why (--reason, required), and before/after JSON of the row.
  * It does NOT pay anything. Escrow rows record WEIGHT, not funds; restoring
    past epochs is a separate, manual operator payment.
  * It does NOT make the release permanent against new evidence: a miner that
    sends the incident profile again is re-flagged on that attestation.
  * Cohort members (sybil_cohort_20260924) are refused unless --force-cohort.
    Even then, settlement still holds any wallet listed in the cohort table.
    Removing it from that table is a separate operator decision, so the tool
    prints that SQL and does not run it.
"""
import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys

DEFAULT_DB = "/root/rustchain/rustchain_v2.db"
AUDIT_TABLE = "sybil_guard_admin_audit"


def _import_guard(root):
    for p in (root, os.path.join(root, "node")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import sybil_guard  # noqa: E402  (the node's own module)
    return sybil_guard


def _ts(v):
    if v is None:
        return None
    try:
        return _dt.datetime.fromtimestamp(int(v), _dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    except (TypeError, ValueError, OverflowError, OSError):
        return str(v)


def _ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def _exists(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _escrow_units(c):
    if not _exists(c, "sybil_review_escrow"):
        return {}
    return {m: (int(u or 0), int(n)) for m, u, n in c.execute(
        "SELECT miner, SUM(would_be_weight_units), COUNT(*) FROM sybil_review_escrow GROUP BY miner")}


def cmd_list(db, sg, states=None, limit=200, out=None):
    out = out or sys.stdout
    c = _ro(db)
    try:
        if not _exists(c, "miner_probation"):
            print("miner_probation does not exist (guarded node not started yet)", file=out)
            return []
        esc = _escrow_units(c)
        cohort = set()
        if _exists(c, sg.INCIDENT_COHORT_TABLE):
            cohort = sg._cohort_members(c, [r[0] for r in c.execute("SELECT miner FROM miner_probation")])
        want = states or [sg.STATE_PROBATION, sg.STATE_QUEUED, sg.STATE_ADMISSION_QUEUED]
        rows = c.execute(
            "SELECT miner, state, reason, needs_review, review_reason, first_seen, last_seen, attest_count, "
            "varied_count, anomaly_count FROM miner_probation "
            f"WHERE needs_review = 1 OR state IN ({','.join('?' * len(want))}) "
            "ORDER BY needs_review DESC, first_seen DESC LIMIT ?", [*want, int(limit)]).fetchall()
    finally:
        c.close()
    out_rows = []
    print(f"{'miner':44} {'state':16} {'review':44} {'first_seen':20} {'att':>4} {'var':>4} {'anom':>4} "
          f"{'escrow_units':>14} cohort", file=out)
    for (m, st, why, nr, rr, fs, ls, ac, vc, an) in rows:
        u, n = esc.get(m, (0, 0))
        rec = {"miner": m, "state": st, "reason": why, "needs_review": bool(nr), "review_reason": rr,
               "first_seen": _ts(fs), "last_seen": _ts(ls), "attestations": ac, "varied": vc,
               "anomalies": an, "escrow_units": u, "escrow_epochs": n, "cohort": m in cohort}
        out_rows.append(rec)
        print(f"{m[:44]:44} {st:16} {(rr or '-')[:44]:44} {rec['first_seen'] or '-':20} {ac or 0:>4} "
              f"{vc or 0:>4} {an or 0:>4} {u:>14} {'YES' if m in cohort else ''}", file=out)
    print(f"\n{len(out_rows)} row(s). Escrow units are WEIGHT (1e9 = 1.0x), not RTC.", file=out)
    return out_rows


def cmd_show(db, sg, miner, out=None):
    out = out or sys.stdout
    c = _ro(db)
    try:
        row = sg._load(c, miner) if _exists(c, "miner_probation") else None
        info = {
            "miner": miner,
            "probation_row": row,
            "pre_cutoff_history": sg.has_pre_cutoff_history(c, miner),
            "cohort_member": bool(sg._cohort_members(c, [miner])) if _exists(c, sg.INCIDENT_COHORT_TABLE) else False,
            "stored_incident_matches": sum(1 for p in sg.fetch_profiles(c, miner) if sg.matches_incident_signature(p)),
            "escrow": [dict(zip(("epoch", "units", "reason", "created_at"), r)) for r in c.execute(
                "SELECT epoch, would_be_weight_units, reason, created_at FROM sybil_review_escrow "
                "WHERE miner=? ORDER BY epoch", (miner,))] if _exists(c, "sybil_review_escrow") else [],
            "audit": [dict(zip(("ts", "operator", "action", "reason"), r)) for r in c.execute(
                f"SELECT ts, operator, action, reason FROM {AUDIT_TABLE} WHERE miner=? ORDER BY id",
                (miner,))] if _exists(c, AUDIT_TABLE) else [],
            "allowlisted_in_this_shell": miner in sg.probation_allowlist(),
        }
    finally:
        c.close()
    print(json.dumps(info, indent=2, default=str), file=out)
    return info


def plan_release(c, sg, miner, trust=False, force_cohort=False):
    """Pure: returns (plan_dict, error_or_None). Reads only."""
    if not _exists(c, "miner_probation"):
        return None, "miner_probation does not exist"
    row = sg._load(c, miner)
    if row is None:
        return None, f"{miner}: no miner_probation row (nothing to release; see `allowlist` for new machines)"
    cohort = _exists(c, sg.INCIDENT_COHORT_TABLE) and bool(sg._cohort_members(c, [miner]))
    if cohort and not force_cohort:
        return None, (f"{miner} is in {sg.INCIDENT_COHORT_TABLE}; refusing without --force-cohort")
    pre = sg.has_pre_cutoff_history(c, miner)
    if pre:
        new_state, new_reason = sg.STATE_GRANDFATHERED, "operator_release:attested_before_cutoff"
    elif trust:
        new_state, new_reason = sg.STATE_TRUSTED, "operator_release:trusted"
    else:
        new_state, new_reason = row["state"], row.get("reason")
    after = dict(row, needs_review=0, review_reason=None, state=new_state, reason=new_reason)
    warnings = []
    if cohort:
        warnings.append(
            f"still listed in {sg.INCIDENT_COHORT_TABLE}: settlement will KEEP holding it until an operator runs: "
            f"DELETE FROM {sg.INCIDENT_COHORT_TABLE} WHERE miner = '{miner}';  (not run by this tool)")
    if new_state == sg.STATE_TRUSTED and not pre:
        warnings.append("--trust skips the remaining probation checks and exit caps for this miner")
    if row["state"] == sg.STATE_ADMISSION_QUEUED and new_state == row["state"]:
        warnings.append("still admission_queued: weight stays 0 until admitted; use --trust to lift it")
    warnings.append("the miner is re-flagged if it sends the incident profile again")
    warnings.append("no funds move: escrow rows record weight only; past epochs need a manual payment")
    return {"miner": miner, "before": row, "after": after, "cohort_member": cohort,
            "pre_cutoff_history": pre, "warnings": warnings}, None


def cmd_release(db, sg, miner, reason, operator, apply=False, trust=False, force_cohort=False, out=None):
    out = out or sys.stdout
    if not reason or not reason.strip():
        print("REFUSED: --reason is required", file=out)
        return 2
    if not apply:
        c = _ro(db)
        try:
            plan, err = plan_release(c, sg, miner, trust, force_cohort)
        finally:
            c.close()
        if err:
            print(f"REFUSED: {err}", file=out)
            return 2
        print(json.dumps({"DRY_RUN": True, **plan}, indent=2, default=str), file=out)
        print("\nDry run: nothing written. Re-run with --apply to release.", file=out)
        return 0
    c = sqlite3.connect(db, timeout=30, isolation_level=None)
    try:
        c.execute(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, operator TEXT NOT NULL,
            action TEXT NOT NULL, miner TEXT NOT NULL, reason TEXT NOT NULL,
            before_json TEXT, after_json TEXT)""")
        c.execute("BEGIN IMMEDIATE")
        try:
            plan, err = plan_release(c, sg, miner, trust, force_cohort)
            if err:
                c.execute("ROLLBACK")
                print(f"REFUSED: {err}", file=out)
                return 2
            a = plan["after"]
            cur = c.execute(
                "UPDATE miner_probation SET needs_review = 0, review_reason = NULL, state = ?, reason = ?, "
                "updated_at = ? WHERE miner = ?",
                (a["state"], a["reason"], int(_dt.datetime.now(_dt.timezone.utc).timestamp()), miner))
            if cur.rowcount != 1:
                raise RuntimeError(f"expected 1 row updated, got {cur.rowcount}")
            c.execute(f"INSERT INTO {AUDIT_TABLE} (ts, operator, action, miner, reason, before_json, after_json) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (int(_dt.datetime.now(_dt.timezone.utc).timestamp()), operator,
                       "release" + ("+force_cohort" if plan["cohort_member"] else ""), miner, reason.strip(),
                       json.dumps(plan["before"], default=str), json.dumps(a, default=str)))
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
    finally:
        c.close()
    print(json.dumps({"RELEASED": True, "miner": miner, "state": a["state"],
                      "warnings": plan["warnings"]}, indent=2), file=out)
    return 0


ALLOWLIST_GUIDE = """\
RC_PROBATION_ALLOWLIST: for a NEW lab machine (first seen after 2026-09-24 00:00Z) that you
know is real but whose client sends a static profile (e.g. the Python 2.x G4 client), so it
could never graduate by itself.

  * Comma-separated miner ids, read from the node process environment at each attestation:
      Environment="RC_PROBATION_ALLOWLIST=dual-g4-new,g5-lab-2"
    in /etc/systemd/system/rustchain.service (next to RC_ADMIN_KEY), then:
      systemctl daemon-reload && systemctl restart rustchain
  * It applies when the miner's miner_probation row is first created (state trusted,
    reason operator_allowlist). A miner that ALREADY has a row is not changed by the
    env var: use `release <miner> --trust --reason ...` instead (audited).
  * Allowlisted miners get their full hardware weight, and the welcome bonus once, on the next
    attestation. The incident detector still applies (needs_review overrides everything).
  * Miners that attested before the cutoff never need this: they are grandfathered.
  * Keep the list short and write down why each entry is there. Anyone on it skips probation.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--root", default=os.environ.get("RUSTCHAIN_ROOT", "/root/rustchain"),
                    help="directory holding sybil_guard.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("--state", action="append")
    p_list.add_argument("--limit", type=int, default=200)
    p_show = sub.add_parser("show")
    p_show.add_argument("miner")
    p_rel = sub.add_parser("release")
    p_rel.add_argument("miner")
    p_rel.add_argument("--reason", required=True)
    p_rel.add_argument("--operator", default=os.environ.get("SUDO_USER") or os.environ.get("USER") or "unknown")
    p_rel.add_argument("--trust", action="store_true", help="mark trusted (new miners only)")
    p_rel.add_argument("--force-cohort", action="store_true")
    p_rel.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    sub.add_parser("allowlist")
    args = ap.parse_args(argv)
    if args.cmd == "allowlist":
        print(ALLOWLIST_GUIDE)
        return 0
    sg = _import_guard(args.root)
    if args.cmd == "list":
        cmd_list(args.db, sg, args.state, args.limit)
        return 0
    if args.cmd == "show":
        cmd_show(args.db, sg, args.miner)
        return 0
    return cmd_release(args.db, sg, args.miner, args.reason, args.operator,
                       apply=args.apply, trust=args.trust, force_cohort=args.force_cohort)


if __name__ == "__main__":
    sys.exit(main())
