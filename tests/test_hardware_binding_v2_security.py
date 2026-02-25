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
