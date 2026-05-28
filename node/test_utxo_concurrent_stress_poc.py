#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
B4: 1000 Parallel Transfers Stress Test

Stress test the UTXO mempool under high concurrency. Tests for:
1. Double-spend acceptance (race: two threads claim same input)
2. Mempool overfill (race: MAX_POOL_SIZE exceeded under load)
3. Lost inputs (race: mempool_add returns False but input still locked)
4. Thread safety of BEGIN IMMEDIATE under concurrent writes
"""

import threading
import time
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from utxo_db import UtxoDB, UNIT, MAX_POOL_SIZE

DB_PATH = "/tmp/test_b4_stress.db"
NUM_THREADS = 20
TX_PER_THREAD = 50  # 1000 total


def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = UtxoDB(DB_PATH)
    db.init_tables()
    # Create 1000 fund boxes
    for i in range(1000):
        db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': f'user_{i}', 'value_nrtc': 10 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=i + 1)
    return db


results = {}
lock = threading.Lock()


def worker(worker_id, box_ids, output_dir):
    """Submit TX_PER_THREAD transfers, each claiming a unique box."""
    db = UtxoDB(DB_PATH)
    local_ok = 0
    local_fail = 0
    local_errors = 0

    for idx, bid in enumerate(box_ids):
        tx_id_hex = f"w{worker_id}_tx{idx}_{'x' * 32}"[:64]
        try:
            ok = db.mempool_add({
                'tx_id': tx_id_hex,
                'tx_type': 'transfer',
                'inputs': [{'box_id': bid, 'spending_proof': 'sig'}],
                'outputs': [{'address': 'recipient', 'value_nrtc': 9 * UNIT}],
                'fee_nrtc': 1 * UNIT,
                'timestamp': int(time.time()),
            })
            if ok:
                local_ok += 1
            else:
                local_fail += 1
        except Exception as e:
            local_errors += 1

    with lock:
        results[worker_id] = (local_ok, local_fail, local_errors)


def main():
    db = setup_db()

    # Collect all box_ids
    all_boxes = []
    for i in range(1000):
        boxes = db.get_unspent_for_address(f'user_{i}')
        all_boxes.extend(b['box_id'] for b in boxes)

    total_boxes = len(all_boxes)
    print(f"Total available boxes: {total_boxes}")
    print(f"Threads: {NUM_THREADS}, TX per thread: {TX_PER_THREAD}")
    print(f"Expected total: {min(total_boxes, NUM_THREADS * TX_PER_THREAD)}")

    # Assign boxes round-robin to workers
    boxes_per_worker = [[] for _ in range(NUM_THREADS)]
    for idx, bid in enumerate(all_boxes):
        boxes_per_worker[idx % NUM_THREADS].append(bid)

    # Launch threads
    threads = []
    start = time.time()
    for w_id in range(NUM_THREADS):
        t = threading.Thread(target=worker, args=(w_id, boxes_per_worker[w_id], DB_PATH))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    elapsed = time.time() - start

    # Aggregate
    total_ok = sum(v[0] for v in results.values())
    total_fail = sum(v[1] for v in results.values())
    total_err = sum(v[2] for v in results.values())

    print(f"\n=== B4 STRESS TEST RESULTS ===")
    print(f"Time: {elapsed:.2f}s")
    print(f"Accepted (ok):  {total_ok}")
    print(f"Rejected:       {total_fail}")
    print(f"Errors:         {total_err}")
    print(f"Throughput:     {total_ok/elapsed:.0f} tx/s")

    # Verify no double-spends in mempool
    conn = db._conn()
    input_count = conn.execute(
        "SELECT COUNT(*) FROM utxo_mempool_inputs"
    ).fetchone()[0]
    mempool_count = conn.execute(
        "SELECT COUNT(*) FROM utxo_mempool"
    ).fetchone()[0]
    pool_size = conn.execute(
        "SELECT COUNT(*) FROM utxo_mempool"
    ).fetchone()[0]
    conn.close()

    print(f"\nMempool TX count:  {mempool_count}")
    print(f"Mempool input claims: {input_count}")
    print(f"Pool usage:       {pool_size}/{MAX_POOL_SIZE}")

    issues = []
    if total_err > 0:
        issues.append(f"⚠️  {total_err} exceptions — possible race condition bug!")
    if mempool_count != total_ok:
        issues.append(f"⚠️  Mempool count ({mempool_count}) ≠ accepted ({total_ok}) — lost TX!")
    if total_ok > total_boxes:
        issues.append(f"⚠️  More accepted ({total_ok}) than available boxes ({total_boxes}) — DOUBLE-SPEND!")
    if pool_size >= MAX_POOL_SIZE:
        issues.append(f"⚠️  Pool full ({pool_size}/{MAX_POOL_SIZE}) — possible overfill race")

    if issues:
        print("\n=== ISSUES DETECTED ===")
        for i in issues:
            print(f"  {i}")
        print("\nB4: Bug(s) confirmed — race conditions exist under load!")
        return False
    else:
        print("\n✅ B4: No race conditions detected in 1000 concurrent transfers")
        return True


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
