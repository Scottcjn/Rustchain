#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))

from claims_settlement import generate_batch_id


def test_generate_batch_id_uses_database_sequence_under_concurrency(tmp_path):
    db_path = str(tmp_path / "claims.db")

    conn = sqlite3.connect(db_path)
    conn.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        batch_ids = list(executor.map(lambda _: generate_batch_id(db_path), range(20)))

    assert len(batch_ids) == 20
    assert len(set(batch_ids)) == 20

    day_prefix = "_".join(batch_ids[0].split("_")[:4])
    assert all(batch_id.startswith(f"{day_prefix}_") for batch_id in batch_ids)

    sequences = sorted(int(batch_id.rsplit("_", 1)[1]) for batch_id in batch_ids)
    assert sequences == list(range(1, 21))

    batch_day = day_prefix.removeprefix("batch_")
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT sequence FROM settlement_batch_sequence WHERE batch_day = ?",
            (batch_day,),
        ).fetchone()
    finally:
        conn.close()

    assert row == (20,)
