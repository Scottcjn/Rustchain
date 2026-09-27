# SPDX-License-Identifier: MIT
"""ADM IDENTITY FIX (2026-09-25).

Before: anti_double_mining keyed machines on hash(arch + profile["checks"]),
but the profile it reads is the flat 4-metric temporal profile, so every miner
hashed to hash(arch) and ADM paid ONE miner per architecture (prod epochs
250-295). Now a machine is identified only by persisted machine evidence:
same MAC hash (recent) AND same server-observed source_ip AND same arch.
"""
import sqlite3

import pytest

import sg_helpers  # noqa: F401  (node/ on sys.path; must precede node imports)
import anti_double_mining as adm
import rewards_implementation_rip200 as ri
import test_sybil_guard_settlement as tsg

U = tsg.U
POT = ri.PER_EPOCH_URTC
EPOCH = tsg.EPOCH
G4 = tsg.HONEST_G4
X86 = tsg.HONEST_X86
EPOCH_START = adm.GENESIS_TIMESTAMP + EPOCH * 144 * adm.BLOCK_TIME


def _add_evidence(path, ips=None, macs=None, mac_ts=None):
    """ips: {miner: ip}; macs: {miner: [mac_hash,...]}"""
    c = sqlite3.connect(path)
    c.execute("ALTER TABLE miner_attest_recent ADD COLUMN source_ip TEXT")
    c.execute("CREATE TABLE miner_macs (miner TEXT NOT NULL, mac_hash TEXT NOT NULL, first_ts INTEGER "
              "NOT NULL, last_ts INTEGER NOT NULL, count INTEGER DEFAULT 1, PRIMARY KEY (miner, mac_hash))")
    for m, ip in (ips or {}).items():
        c.execute("UPDATE miner_attest_recent SET source_ip=? WHERE miner=?", (ip, m))
    ts = EPOCH_START + 60 if mac_ts is None else mac_ts
    for m, hs in (macs or {}).items():
        for h in hs:
            c.execute("INSERT INTO miner_macs VALUES (?,?,?,?,1)", (m, h, ts, ts))
    c.commit()
    c.close()


def _settle(path, use_adm=True):
    res = ri.settle_epoch_rip200(str(path), EPOCH, enable_anti_double_mining=use_adm)
    assert res.get("ok") is True, res
    bal = tsg.balances(str(path))
    assert sum(bal.values()) == POT          # exactly 1.5 RTC, always
    return res, bal


def test_same_arch_distinct_miners_are_not_collapsed(tmp_path):
    db = tmp_path / "a.db"
    tsg.make_db(str(db), [("g4-a", "G4", int(2.5 * U), G4),
                          ("g4-b", "G4", int(2.5 * U), {**G4, "clock_drift_cv": 0.0177}),
                          ("x86-a", "modern", int(0.8 * U), X86)])
    res, bal = _settle(db)
    assert sorted(bal) == ["g4-a", "g4-b", "x86-a"]
    assert res["anti_double_mining_telemetry"]["duplicate_miner_ids_skipped"] == 0


def test_lab_g4s_with_identical_static_profile_behind_one_nat_all_paid(tmp_path):
    """The lab's real G4s send the SAME constant profile from one WAN IP; distinct MACs."""
    db = tmp_path / "lab.db"
    miners = [(f"g4-{i}", "G4", int(2.5 * U), G4) for i in range(4)]
    tsg.make_db(str(db), miners)
    _add_evidence(db, ips={m[0]: "203.0.113.7" for m in miners},
                  macs={m[0]: [f"mac{i}"] for i, m in enumerate(miners)})
    _, bal = _settle(db)
    assert sorted(bal) == [m[0] for m in miners]
    assert len(set(bal.values())) == 1 or max(bal.values()) - min(bal.values()) <= 3


def test_adm_matches_standard_path_when_no_duplicates(tmp_path):
    rows = [("g4-a", "G4", int(2.5 * U), G4), ("g4-b", "G4", int(2.5 * U), G4),
            ("x86-a", "modern", int(0.8 * U), X86), ("x86-b", "modern", U, X86)]
    a, b = tmp_path / "adm.db", tmp_path / "std.db"
    tsg.make_db(str(a), rows)
    tsg.make_db(str(b), rows)
    _, bal_a = _settle(a, True)
    _, bal_b = _settle(b, False)
    assert set(bal_a) == set(bal_b)
    for m in bal_a:
        assert abs(bal_a[m] - bal_b[m]) <= 3     # remainder placement only


def test_true_duplicate_same_mac_same_ip_same_arch_collapses_to_heaviest(tmp_path):
    db = tmp_path / "dup.db"
    tsg.make_db(str(db), [("box-alias1", "G4", U, G4), ("box-main", "G4", int(2.5 * U), G4),
                          ("x86-a", "modern", int(0.8 * U), X86)])
    _add_evidence(db, ips={"box-alias1": "198.51.100.9", "box-main": "198.51.100.9",
                           "x86-a": "198.51.100.9"},
                  macs={"box-alias1": ["macA"], "box-main": ["macA", "macB"], "x86-a": ["macX"]})
    res, bal = _settle(db)
    assert sorted(bal) == ["box-main", "x86-a"]
    tel = res["anti_double_mining_telemetry"]
    assert tel["duplicate_miner_ids_skipped"] == 1
    assert tel["skipped_details"] == [{"skipped": "box-alias1", "rewarded_representative": "box-main"}]


def test_bridge_miner_is_held_and_does_not_merge_honest_miners(tmp_path):
    """Round 2 (review): A reports X, att reports X+Y, B reports Y, all same ip/arch.
    Union-find used to chain A-att-B into ONE machine (one slot). Now att is a
    bridge conflict: held at 0 and escrowed; A and B are paid separately."""
    db = tmp_path / "bridge.db"
    tsg.make_db(str(db), [("A", "G5", 2 * U, G4), ("att", "G5", 3 * U, G4), ("B", "G5", 2 * U, G4)])
    _add_evidence(db, ips={m: "198.51.100.1" for m in ("A", "att", "B")},
                  macs={"A": ["X"], "att": ["X", "Y"], "B": ["Y"]})
    res, bal = _settle(db)
    assert sorted(bal) == ["A", "B"]
    assert bal["A"] + bal["B"] == POT and abs(bal["A"] - bal["B"]) <= 1
    assert res["anti_double_mining_telemetry"]["duplicate_miner_ids_skipped"] == 0
    assert tsg.escrow(str(db)) == [("att", 3 * U, "adm_identity_bridge_conflict")]


def test_bridge_resolver_reports_conflict_and_keeps_true_clique(tmp_path):
    """A clique that shares a MAC still collapses; only the bridging miner conflicts."""
    db = tmp_path / "clique.db"
    tsg.make_db(str(db), [(m, "G5", U, G4) for m in ("c1", "c2", "att", "B")])
    _add_evidence(db, ips={m: "198.51.100.1" for m in ("c1", "c2", "att", "B")},
                  macs={"c1": ["X"], "c2": ["X"], "att": ["X", "Y"], "B": ["Y"]})
    with sqlite3.connect(db) as c:
        ids, conflicts = adm.resolve_machine_identities_ex(
            c, {m: "G5" for m in ("c1", "c2", "att", "B")}, EPOCH_START)
    assert set(conflicts) == {"att"} and conflicts["att"] == ["B", "c1", "c2"]
    assert ids["c1"] == ids["c2"]
    assert len({ids["c1"], ids["att"], ids["B"]}) == 3


def test_all_share_one_mac_is_a_clique_not_a_conflict(tmp_path):
    db = tmp_path / "trio.db"
    tsg.make_db(str(db), [("m1", "G5", 2 * U, G4), ("m2", "G5", 2 * U, G4), ("m3", "G5", 2 * U, G4)])
    _add_evidence(db, ips={m: "198.51.100.1" for m in ("m1", "m2", "m3")},
                  macs={"m1": ["p"], "m2": ["p", "q"], "m3": ["p", "q"]})
    res, bal = _settle(db)
    assert len(bal) == 1
    assert res["anti_double_mining_telemetry"]["duplicate_miner_ids_skipped"] == 2
    assert tsg.escrow(str(db)) == []


def _set_mac_window(path, miner, first_ts, last_ts):
    with sqlite3.connect(path) as c:
        c.execute("UPDATE miner_macs SET first_ts=?, last_ts=? WHERE miner=?", (first_ts, last_ts, miner))


EPOCH_LAST_SLOT = EPOCH_START + 143 * adm.BLOCK_TIME
NEXT_EPOCH_START = EPOCH_START + 144 * adm.BLOCK_TIME   # exclusive upper bound (round-2 review)


@pytest.mark.parametrize("case,merged", [
    ("first_seen_after_epoch_end", False),     # a later observation cannot regroup a past epoch
    ("first_seen_at_next_epoch_start", False), # boundary: == next start is EXCLUDED
    ("first_seen_in_final_slot", True),        # boundary: inside the last 600 s slot is INCLUDED
    ("first_seen_one_second_before_next", True),
    ("seen_before_and_still_active", True),    # normal late settlement of an active duplicate
    ("inside_epoch", True),
    ("stale_before_window", False),
])
def test_mac_evidence_is_epoch_scoped(tmp_path, case, merged):
    db = tmp_path / f"{case}.db"
    tsg.make_db(str(db), [("main", "G4", 2 * U, G4), ("alias", "G4", U, G4)])
    _add_evidence(db, ips={"main": "198.51.100.2", "alias": "198.51.100.2"},
                  macs={"main": ["M"], "alias": ["M"]})
    window = {
        "first_seen_after_epoch_end": (NEXT_EPOCH_START + 60, NEXT_EPOCH_START + 3600),
        "first_seen_at_next_epoch_start": (NEXT_EPOCH_START, NEXT_EPOCH_START + 3600),
        "first_seen_in_final_slot": (EPOCH_LAST_SLOT + 60, EPOCH_LAST_SLOT + 120),
        "first_seen_one_second_before_next": (NEXT_EPOCH_START - 1, NEXT_EPOCH_START + 600),
        "seen_before_and_still_active": (EPOCH_START - 86400, NEXT_EPOCH_START + 5 * 86400),
        "inside_epoch": (EPOCH_START + 60, EPOCH_START + 600),
        "stale_before_window": (EPOCH_START - 30 * 86400, EPOCH_START - adm.ADM_MAC_RECENCY_S - 1),
    }[case]
    _set_mac_window(db, "alias", *window)
    with sqlite3.connect(db) as c:
        ids = adm.resolve_machine_identities(c, {"main": "G4", "alias": "G4"}, EPOCH_START,
                                             NEXT_EPOCH_START)
        # Same answer through the settlement entry point, which derives the bound itself.
        groups, _ = adm.get_epoch_miner_groups_ex(c, EPOCH)
        dup = adm.detect_duplicate_identities(c, EPOCH, EPOCH_START, EPOCH_LAST_SLOT)
    assert (ids["main"] == ids["alias"]) is merged
    assert (len(groups) == 1) is merged
    assert (len(dup) == 1) is merged


def test_default_evidence_bound_is_next_epoch_start(tmp_path):
    db = tmp_path / "default.db"
    tsg.make_db(str(db), [("main", "G4", 2 * U, G4), ("alias", "G4", U, G4)])
    _add_evidence(db, ips={"main": "198.51.100.2", "alias": "198.51.100.2"},
                  macs={"main": ["M"], "alias": ["M"]})
    _set_mac_window(db, "alias", EPOCH_LAST_SLOT + 300, EPOCH_LAST_SLOT + 300)
    with sqlite3.connect(db) as c:
        ids = adm.resolve_machine_identities(c, {"main": "G4", "alias": "G4"}, EPOCH_START)
    assert ids["main"] == ids["alias"]


def _poison_first_seen(path, column_sql):
    with sqlite3.connect(path) as c:
        c.execute(column_sql)


@pytest.mark.parametrize("where", ["ts_ok", "bound_at", "both"])
def test_infinite_first_seen_never_raises_and_bridge_hold_still_applies(tmp_path, where, caplog):
    """Round-2 review: a REAL inf in ts_ok / bound_at made int() raise
    OverflowError inside _first_seen_map and aborted settlement. It must be
    treated as missing evidence: settlement completes via ADM, the bridge
    conflict is still held + escrowed, and a true duplicate still collapses."""
    db = tmp_path / f"inf_{where}.db"
    tsg.make_db(str(db), [("A", "G5", 2 * U, G4), ("att", "G5", 3 * U, G4), ("B", "G5", 2 * U, G4),
                          ("d1", "G4", U, G4), ("d2", "G4", 2 * U, G4)])
    _add_evidence(db, ips={m: "198.51.100.1" for m in ("A", "att", "B", "d1", "d2")},
                  macs={"A": ["X"], "att": ["X", "Y"], "B": ["Y"], "d1": ["D"], "d2": ["D"]})
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT, "
                  "bound_at INTEGER)")
        if where in ("ts_ok", "both"):
            c.execute("INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES "
                      "('d1', 9e999, 1), ('d2', -1e999, 1), ('d2', -5, 1), ('A', 'garbage', 1)")
        if where in ("bound_at", "both"):
            c.execute("INSERT INTO hardware_bindings VALUES ('h1', 'd1', 9e999), ('h2', 'd2', 9e999)")
        # Confirm SQLite really stored IEEE inf, not NULL / text.
        vals = [r[0] for r in c.execute(
            "SELECT ts_ok FROM miner_attest_history WHERE typeof(ts_ok)='real' "
            "UNION ALL SELECT bound_at FROM hardware_bindings WHERE typeof(bound_at)='real'")]
        assert vals and all(v in (float("inf"), float("-inf")) for v in vals)
        assert adm._first_seen_map(c, ["d1", "d2", "A"]) == {}
    caplog.set_level("ERROR", logger="anti_double_mining")
    res, bal = _settle(db)
    assert "anti_double_mining_telemetry" in res          # the ADM path ran, not a fallback
    assert "att" not in bal and {"A", "B"} <= set(bal)
    assert res["anti_double_mining_telemetry"]["duplicate_miner_ids_skipped"] == 1
    assert ("att", 3 * U, "adm_identity_bridge_conflict") in tsg.escrow(str(db))
    # Logged (once per first-seen lookup, not once per bad row), never raised.
    assert any("invalid first-seen timestamp" in r.getMessage() for r in caplog.records)


def test_nat_copycat_cannot_displace_established_miner(tmp_path, caplog):
    """Attacker behind the victim's NAT copies its MAC and enrolls heavier. The
    established (earlier first-seen) identity keeps the slot; the copycat is skipped."""
    db = tmp_path / "copycat.db"
    tsg.make_db(str(db), [("victim", "G4", U, G4), ("copycat", "G4", int(2.5 * U), G4),
                          ("x86-a", "modern", int(0.8 * U), X86)])
    _add_evidence(db, ips={"victim": "198.51.100.8", "copycat": "198.51.100.8"},
                  macs={"victim": ["macV"], "copycat": ["macV"]})
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES "
                  "('victim', ?, 1), ('copycat', ?, 1)", (EPOCH_START - 90 * 86400, EPOCH_START + 100))
    caplog.set_level("WARNING", logger="anti_double_mining")
    res, bal = _settle(db)
    assert sorted(bal) == ["victim", "x86-a"]
    assert res["anti_double_mining_telemetry"]["skipped_details"] == [
        {"skipped": "copycat", "rewarded_representative": "victim"}]
    assert any("kept established victim" in r.getMessage() for r in caplog.records)


def test_hardware_binding_counts_as_first_seen(tmp_path):
    db = tmp_path / "hb.db"
    tsg.make_db(str(db), [("bound", "G4", U, G4), ("newer", "G4", 2 * U, G4)])
    _add_evidence(db, ips={"bound": "198.51.100.9", "newer": "198.51.100.9"},
                  macs={"bound": ["m"], "newer": ["m"]})
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE hardware_bindings (hardware_id TEXT PRIMARY KEY, bound_miner TEXT, "
                  "bound_at INTEGER)")
        c.execute("INSERT INTO hardware_bindings VALUES ('h1', 'bound', 1000)")
        c.execute("INSERT INTO miner_attest_history (miner, ts_ok, fingerprint_passed) VALUES "
                  "('newer', 5000, 1)")
    _, bal = _settle(db)
    assert sorted(bal) == ["bound"]


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", -5, "abc", b"\x00", None])
def test_malformed_enrolled_weights_are_zero_and_never_raise(tmp_path, bad, caplog):
    db = tmp_path / "w.db"
    tsg.make_db(str(db), [("good", "G4", int(2.5 * U), G4), ("bad", "G4", U, G4)])
    val = {"nan": float("nan"), "inf": float("inf"), "-inf": float("-inf")}.get(bad, bad)
    with sqlite3.connect(db) as c:
        c.execute("UPDATE epoch_enroll SET weight=? WHERE miner_pk='bad'", (val,))
    caplog.set_level("ERROR", logger="anti_double_mining")
    res, bal = _settle(db)
    assert bal == {"good": POT}
    assert res["anti_double_mining_telemetry"]["total_machines"] == 2
    with sqlite3.connect(db) as c:
        stored = c.execute("SELECT weight FROM epoch_enroll WHERE miner_pk='bad'").fetchone()[0]
    if stored is not None:   # SQLite stores NaN as NULL, which is simply "no weight"
        assert any("treated as 0" in r.getMessage() for r in caplog.records)


def test_safe_weight_unit():
    for v in (float("nan"), float("inf"), -1, "x", [], 10 ** 400):
        assert adm._safe_weight(v) == 0.0
    assert adm._safe_weight("2.5") == 2.5 and adm._safe_weight(3) == 3.0


def test_ip_schema_without_miner_column_falls_back_per_miner():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE miner_attest_recent (wallet TEXT, source_ip TEXT)")
    c.execute("CREATE TABLE miner_macs (miner TEXT, mac_hash TEXT, first_ts INT, last_ts INT)")
    c.execute("INSERT INTO miner_macs VALUES ('a','m',?,?), ('b','m',?,?)", (EPOCH_START,) * 4)
    ids = adm.resolve_machine_identities(c, {"a": "G4", "b": "G4"}, EPOCH_START)
    assert ids["a"] != ids["b"]


def test_non_text_ip_values_do_not_raise_or_merge():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INT, source_ip)")
    c.execute("CREATE TABLE miner_macs (miner TEXT, mac_hash TEXT, first_ts INT, last_ts INT)")
    c.executemany("INSERT INTO miner_attest_recent VALUES (?,?,?)",
                  [("a", 1, 12345), ("b", 1, 12345), ("c", 1, b"10.0.0.1"), ("d", 1, b"10.0.0.1"),
                   ("e", 1, b"\xff\xfe"), ("f", 1, b"\xff\xfe")])
    for m in "abcdef":
        c.execute("INSERT INTO miner_macs VALUES (?, 'm', ?, ?)", (m, EPOCH_START, EPOCH_START))
    ids = adm.resolve_machine_identities(c, {m: "G4" for m in "abcdef"}, EPOCH_START)
    assert ids["a"] != ids["b"]            # integer IP ignored -> no evidence
    assert ids["c"] == ids["d"]            # utf-8 bytes IP decoded -> real evidence
    assert ids["e"] != ids["f"]            # undecodable bytes ignored


def test_present_but_broken_table_fails_loudly():
    """A genuine sqlite error on a PRESENT table must propagate (settlement
    rolls back, epoch stays unsettled) -- not silently fall back to per-miner."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INT, source_ip TEXT)")
    c.execute("INSERT INTO miner_attest_recent VALUES ('a', 1, '10.0.0.1')")
    c.execute("CREATE TABLE gone (miner TEXT, mac_hash TEXT, first_ts INT, last_ts INT)")
    c.execute("CREATE VIEW miner_macs AS SELECT miner, mac_hash, first_ts, last_ts FROM gone")
    c.execute("DROP TABLE gone")
    with pytest.raises(sqlite3.OperationalError):
        adm.resolve_machine_identities(c, {"a": "G4"}, EPOCH_START)


def test_identity_queries_are_batched():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INT, source_ip TEXT)")
    c.execute("CREATE TABLE miner_macs (miner TEXT, mac_hash TEXT, first_ts INT, last_ts INT)")
    miners = [f"m{i}" for i in range(1200)]
    c.executemany("INSERT INTO miner_attest_recent VALUES (?, 1, '10.0.0.1')", [(m,) for m in miners])
    c.executemany("INSERT INTO miner_macs VALUES (?, ?, ?, ?)",
                  [(m, f"mac{i}", EPOCH_START, EPOCH_START) for i, m in enumerate(miners)])
    stmts = []
    c.set_trace_callback(stmts.append)
    ids = adm.resolve_machine_identities(c, {m: "G4" for m in miners}, EPOCH_START)
    data = [q for q in stmts if q.lstrip().upper().startswith("SELECT")]
    assert len(set(ids.values())) == 1200
    assert len(data) == 6   # ceil(1200/500)=3 chunks x 2 tables, not 2N


@pytest.mark.parametrize("variant", ["different_ip", "different_arch", "stale_mac", "no_ip"])
def test_mac_alone_is_not_enough(tmp_path, variant):
    """A claimed MAC must be corroborated by the server-observed IP (anti-griefing)."""
    db = tmp_path / f"{variant}.db"
    arch_b = "G5" if variant == "different_arch" else "G4"
    tsg.make_db(str(db), [("victim", "G4", int(2.5 * U), G4), ("claimer", arch_b, 3 * U, G4)])
    ips = {"victim": "198.51.100.5", "claimer": "198.51.100.5"}
    if variant == "different_ip":
        ips["claimer"] = "203.0.113.99"
    if variant == "no_ip":
        ips = {"victim": "198.51.100.5"}
    mac_ts = EPOCH_START - adm.ADM_MAC_RECENCY_S - 10 if variant == "stale_mac" else None
    _add_evidence(db, ips=ips, macs={"victim": ["macV"], "claimer": ["macV"]}, mac_ts=mac_ts)
    _, bal = _settle(db)
    assert sorted(bal) == ["claimer", "victim"]


def test_held_alias_never_displaces_unheld_same_machine(tmp_path):
    db = tmp_path / "held.db"
    tsg.make_db(str(db), [("real", "G4", U, G4), ("alias", "G4", int(2.5 * U), G4)], held=("alias",))
    _add_evidence(db, ips={"real": "198.51.100.3", "alias": "198.51.100.3"},
                  macs={"real": ["m"], "alias": ["m"]})
    _, bal = _settle(db)
    assert sorted(bal) == ["real"]


def test_held_miner_without_evidence_still_zero(tmp_path):
    db = tmp_path / "held2.db"
    tsg.make_db(str(db), [("g4-a", "G4", int(2.5 * U), G4), ("sybil", "G4", U, tsg._sybil_profile(1))],
                held=("sybil",))
    _, bal = _settle(db)
    assert sorted(bal) == ["g4-a"]


def test_resolve_identities_fallback_schema(tmp_path):
    """No source_ip column / no miner_macs table -> every miner its own identity."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_arch TEXT)")
    ids = adm.resolve_machine_identities(c, {"a": "G4", "b": "G4", "c": "G4"}, EPOCH_START)
    assert len(set(ids.values())) == 3


def test_detect_duplicate_identities_uses_machine_evidence(tmp_path):
    db = tmp_path / "det.db"
    tsg.make_db(str(db), [("a", "G4", U, G4), ("b", "G4", U, G4), ("c", "G4", U, G4)])
    _add_evidence(db, ips={"a": "10.0.0.1", "b": "10.0.0.1", "c": "10.0.0.1"},
                  macs={"a": ["x"], "b": ["x"], "c": ["y"]})
    with sqlite3.connect(db) as c:
        dups = adm.detect_duplicate_identities(c, EPOCH, EPOCH_START, EPOCH_START + 86400)
    assert [sorted(d.associated_miner_ids) for d in dups] == [["a", "b"]]
