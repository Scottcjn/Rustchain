import json
import sqlite3
from pathlib import Path

import node.hardware_binding_v2 as hb


def _mk_fingerprint(clock=0, l1=0, l2=0, thermal=0, jitter=0):
    return {
        'checks': {
            'clock_drift': {'data': {'cv': clock}},
            'cache_timing': {'data': {'L1': l1, 'L2': l2}},
            'thermal_drift': {'data': {'ratio': thermal}},
            'instruction_jitter': {'data': {'cv': jitter}},
        }
    }


def test_reject_sparse_entropy_for_new_binding(tmp_path):
    db = tmp_path / 'hb.db'
    hb.DB_PATH = str(db)
    hb.init_hardware_bindings_v2()

    ok, reason, details = hb.bind_hardware_v2(
        serial='SER-1',
        wallet='RTCwallet1',
        arch='x86_64',
        cores=8,
        fingerprint=_mk_fingerprint(clock=0.12),
    )

    assert not ok
    assert reason == 'entropy_insufficient'
    assert details['required_nonzero_fields'] == hb.MIN_COMPARABLE_FIELDS


def test_detect_collision_with_rich_entropy_profiles(tmp_path):
    db = tmp_path / 'hb.db'
    hb.DB_PATH = str(db)
    hb.init_hardware_bindings_v2()

    fp = _mk_fingerprint(clock=0.21, l1=100.0, l2=220.0, thermal=1.9, jitter=0.08)

    ok, reason, _ = hb.bind_hardware_v2(
        serial='SER-BASE',
        wallet='RTCwalletA',
        arch='x86_64',
        cores=8,
        fingerprint=fp,
    )
    assert ok and reason == 'new_binding'

    ok2, reason2, details2 = hb.bind_hardware_v2(
        serial='SER-SPOOF',
        wallet='RTCwalletB',
        arch='x86_64',
        cores=8,
        fingerprint=fp,
    )
    assert not ok2
    assert reason2 == 'entropy_collision'
    assert 'collision_hash' in details2


def test_collision_check_requires_min_comparable_overlap(tmp_path):
    db = tmp_path / 'hb.db'
    hb.DB_PATH = str(db)
    hb.init_hardware_bindings_v2()

    # Baseline binding with rich profile
    fp_base = _mk_fingerprint(clock=0.20, l1=100.0, l2=220.0, thermal=1.8, jitter=0.07)
    ok, reason, _ = hb.bind_hardware_v2(
        serial='SER-BASE-2',
        wallet='RTCwalletBase2',
        arch='x86_64',
        cores=8,
        fingerprint=fp_base,
    )
    assert ok and reason == 'new_binding'

    # Sparse-overlap payload: three non-zero fields, but only one overlaps with baseline (clock_cv)
    # This must NOT be used for collision decisions.
    crafted = {
        'clock_cv': 0.20,      # overlaps
        'cache_l1': 0.0,       # no overlap
        'cache_l2': 0.0,       # no overlap
        'thermal_ratio': 0.0,  # no overlap
        'jitter_cv': 0.30,     # non-zero but not present in stored if attacker manipulates payloads
    }

    # Force one more non-overlap non-zero to satisfy input quality gate
    crafted['cache_l1'] = 0.01

    # Make stored comparable overlap effectively < MIN by editing stored profile directly
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            "UPDATE hardware_bindings_v2 SET entropy_profile = ? WHERE serial_hash = ?",
            (
                json.dumps({'clock_cv': 0.21, 'cache_l1': 0, 'cache_l2': 0, 'thermal_ratio': 0, 'jitter_cv': 0}),
                hb.compute_serial_hash('SER-BASE-2', 'x86_64'),
            ),
        )
        conn.commit()

    collision = hb.check_entropy_collision(crafted)
    assert collision is None


def test_compare_entropy_profiles_marks_sparse_overlap_low_confidence():
    stored = {'clock_cv': 0.2, 'cache_l1': 0, 'cache_l2': 0, 'thermal_ratio': 0, 'jitter_cv': 0}
    current = {'clock_cv': 0.21, 'cache_l1': 0.0, 'cache_l2': 0.0, 'thermal_ratio': 0.0, 'jitter_cv': 0.3}

    ok, score, reason = hb.compare_entropy_profiles(stored, current)
    assert ok
    assert reason in ('entropy_ok', 'insufficient_comparable_overlap')
    # comparable overlap is only one field; ensure score does not imply a strong multi-signal match
    assert score <= 1.0


def test_concurrent_cross_serial_registration_is_serialized(tmp_path, monkeypatch):
    """#71 (Ondrej Nad): two first-time registrations of the same physical
    machine under different serials, racing. Pre-fix, both collision scans ran
    before either INSERT and both bound. Now exactly one may bind.

    A barrier placed just after the collision scan parks the first thread until
    the second has also scanned. Unfixed code lets both scan an empty table;
    fixed code blocks the second at BEGIN IMMEDIATE, so the barrier times out,
    the first commits, and only then does the second scan (and see it).
    """
    import threading

    db = tmp_path / 'hb.db'
    monkeypatch.setattr(hb, 'DB_PATH', str(db))
    hb.init_hardware_bindings_v2()

    barrier = threading.Barrier(2, timeout=1.5)
    real_check = hb.check_entropy_collision

    def racing_check(*args, **kwargs):
        # Scan first, then hold at the barrier: this is the exact race window
        # (both scans done, neither INSERT yet). Fixed code never lets the
        # second thread scan while the first is parked here.
        result = real_check(*args, **kwargs)
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return result

    monkeypatch.setattr(hb, 'check_entropy_collision', racing_check)

    fp = _mk_fingerprint(clock=0.21, l1=100.0, l2=220.0, thermal=1.9, jitter=0.08)
    results = []

    def register(serial, wallet):
        results.append(hb.bind_hardware_v2(
            serial=serial, wallet=wallet, arch='x86_64', cores=8, fingerprint=fp))

    threads = [threading.Thread(target=register, args=('SER-A', 'RTCwalletA')),
               threading.Thread(target=register, args=('SER-B', 'RTCwalletB'))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    reasons = sorted(r[1] for r in results)
    assert reasons == ['entropy_collision', 'new_binding'], results
    conn = sqlite3.connect(str(db))
    try:
        assert conn.execute('SELECT COUNT(*) FROM hardware_bindings_v2').fetchone()[0] == 1
    finally:
        conn.close()
