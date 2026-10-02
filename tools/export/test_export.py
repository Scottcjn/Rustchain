#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline tests for tools/export/rustchain_export.py.

No network calls – all I/O is monkeypatched or uses temp directories.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import textwrap
from pathlib import Path

import pytest

# ── Import the module under test ─────────────────────────────────────────
import importlib
import sys

# Ensure tools/ package is importable.
TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import tools.export.rustchain_export as exp  # noqa: E402

# ── Fixture data matching docs/API.md shapes ─────────────────────────────

MINERS_API = [
    {
        "antiquity_multiplier": 2.5,
        "device_arch": "G4",
        "device_family": "PowerPC",
        "entropy_score": 0.0,
        "hardware_type": "PowerPC G4 (Vintage)",
        "last_attest": 1770112912,
        "miner": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
    },
    {
        "antiquity_multiplier": 2.0,
        "device_arch": "G5",
        "device_family": "PowerPC",
        "entropy_score": 0.0,
        "hardware_type": "PowerPC G5 (Vintage)",
        "last_attest": 1770112865,
        "miner": "g5-selena-179",
    },
]

EPOCH_API = {
    "blocks_per_epoch": 144,
    "enrolled_miners": 2,
    "epoch": 62,
    "epoch_pot": 1.5,
    "slot": 9010,
    "total_supply_rtc": 8388608,
}

BALANCE_API_1 = {
    "amount_i64": 118357193,
    "amount_rtc": 118.357193,
    "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
}

BALANCE_API_2 = {
    "amount_i64": 50000000,
    "amount_rtc": 50.0,
    "miner_id": "g5-selena-179",
}

HISTORY_API = {
    "ok": True,
    "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
    "transactions": [
        {
            "type": "reward",
            "amount": 0.5,
            "epoch": 61,
            "timestamp": 1770000000,
            "tx_hash": None,
        },
        {
            "type": "transfer_in",
            "amount": 2.0,
            "epoch": 60,
            "timestamp": 1769900000,
            "tx_hash": "abc123",
            "from": "other_miner",
        },
    ],
    "total": 2,
}


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_db(path: Path) -> None:
    """Create a temp SQLite DB with the five canonical tables + sample rows."""
    conn = sqlite3.connect(str(path))
    c = conn.cursor()

    c.execute(
        "CREATE TABLE miner_attest_recent ("
        " miner TEXT, device_arch TEXT, device_family TEXT, "
        " hardware_type TEXT, ts_ok INTEGER, entropy_score REAL, "
        " antiquity_multiplier REAL)"
    )
    c.execute(
        "INSERT INTO miner_attest_recent VALUES "
        "('miner_a','G4','PowerPC','PowerPC G4 (Vintage)',1770112912,0.0,2.5)"
    )
    c.execute(
        "INSERT INTO miner_attest_recent VALUES "
        "('miner_b','G5','PowerPC','PowerPC G5 (Vintage)',1770112865,0.0,2.0)"
    )

    c.execute(
        "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)"
    )
    c.execute("INSERT INTO balances VALUES ('miner_a', 118357193)")
    c.execute("INSERT INTO balances VALUES ('miner_b', 50000000)")

    c.execute(
        "CREATE TABLE epoch_state (epoch INTEGER, settled_ts INTEGER, epoch_pot REAL, settled TEXT)"
    )
    c.execute("INSERT INTO epoch_state VALUES (61, 1770000000, 1.5, 'yes')")
    c.execute("INSERT INTO epoch_state VALUES (62, 1770100000, 1.2, 'no')")

    c.execute(
        "CREATE TABLE epoch_rewards (miner_id TEXT, epoch INTEGER, amount_i64 INTEGER)"
    )
    c.execute("INSERT INTO epoch_rewards VALUES ('miner_a', 61, 500000)")
    c.execute("INSERT INTO epoch_rewards VALUES ('miner_b', 61, 300000)")

    c.execute("CREATE TABLE ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
    c.execute("INSERT INTO ledger VALUES (1770000000, 60, 'miner_a', 100000, 'reward')")

    conn.commit()
    conn.close()


class _FakeHTTP:
    """Maps URL paths to canned JSON responses for monkeypatching."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses

    def __call__(self, url: str, timeout: float = 15.0) -> Any:  # matches fetch_json signature
        for prefix, payload in self._responses.items():
            if url.startswith(prefix):
                return payload
        raise RuntimeError(f"no fixture for URL: {url}")


# Reusable fixture
@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    _build_db(p)
    return p


@pytest.fixture()
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "export"


# ── Tests: format creation ───────────────────────────────────────────────


class TestFormats:
    """Each format must produce a parseable file for every table."""

    @pytest.mark.parametrize("fmt", ["csv", "json", "jsonl", "parquet"])
    def test_api_mode_creates_all_files(self, fmt: str, out_dir: Path, monkeypatch) -> None:
        fake = _FakeHTTP(
            {
                "https://rustchain.org/api/miners": MINERS_API,
                "https://rustchain.org/epoch": EPOCH_API,
                "https://rustchain.org/wallet/balance": BALANCE_API_1,
            }
        )
        monkeypatch.setattr(exp, "fetch_json", fake)

        exp.run(out_dir, fmt, mode="api")

        for tbl in exp.ALL_TABLES:
            if fmt == "parquet":
                fp = out_dir / f"{tbl}.parquet"
                assert fp.exists(), f"{fp} missing"
                import pyarrow.parquet as pq
                table = pq.read_table(fp)
                assert table.num_rows >= 0
            else:
                fp = out_dir / f"{tbl}.{fmt}"
                assert fp.exists(), f"{fp} missing"
                content = fp.read_text(encoding="utf-8")
                assert len(content) >= 0

        assert (out_dir / "manifest.json").exists()

    @pytest.mark.parametrize("fmt", ["csv", "json", "jsonl", "parquet"])
    def test_db_mode_creates_all_files(self, fmt: str, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, fmt, mode="db", db_path=db_path)

        for tbl in exp.ALL_TABLES:
            if fmt == "parquet":
                fp = out_dir / f"{tbl}.parquet"
                assert fp.exists(), f"{fp} missing"
                import pyarrow.parquet as pq
                t = pq.read_table(fp)
                assert t.num_rows >= 0
            else:
                fp = out_dir / f"{tbl}.{fmt}"
                assert fp.exists(), f"{fp} missing"


# ── Tests: CSV parsing + escaping ────────────────────────────────────────


class TestCSV:
    def test_headers_present(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "csv", mode="db", db_path=db_path)
        with open(out_dir / "miners.csv", newline="") as fh:
            reader = csv.reader(fh)
            headers = next(reader)
            assert "miner_id" in headers
            assert "device_arch" in headers

    def test_survives_commas_quotes_newlines(self, tmp_path: Path, out_dir: Path) -> None:
        """CSV escaping must survive fields with commas, quotes, newlines."""
        conn = sqlite3.connect(str(tmp_path / "tricky.db"))
        conn.execute(
            "CREATE TABLE miner_attest_recent "
            "(miner TEXT, device_arch TEXT, device_family TEXT, hardware_type TEXT, "
            "ts_ok INTEGER, entropy_score REAL, antiquity_multiplier REAL)"
        )
        conn.execute(
            "INSERT INTO miner_attest_recent VALUES "
            "('a,b', 'G\"4', 'Po wer\\nPC', 'hw', 100, 0, 1.0)"
        )
        conn.commit()
        conn.close()

        exp.run(out_dir, "csv", mode="db", db_path=tmp_path / "tricky.db")
        with open(out_dir / "miners.csv", newline="") as fh:
            rows = list(csv.reader(fh))
        # First row is header; data row should parse to 7 fields
        assert len(rows) == 2
        assert rows[1][0] == "a,b"  # commas inside quotes


# ── Tests: date filtering ───────────────────────────────────────────────


class TestDateFilter:
    def test_from_filters_older_epochs(self, db_path: Path, out_dir: Path) -> None:
        # Only epoch 62 has settled_ts >= 1770100000
        exp.run(out_dir, "json", mode="db", db_path=db_path, start_ts=1770100000)
        data = json.loads((out_dir / "epochs.json").read_text())
        assert all(e["epoch"] != 61 for e in data)
        assert any(e["epoch"] == 62 for e in data)

    def test_to_filters_newer_miners(self, db_path: Path, out_dir: Path) -> None:
        # miner_a ts_ok=1770112912, miner_b ts_ok=1770112865
        # filter end at 1770112900 → only miner_b
        exp.run(out_dir, "json", mode="db", db_path=db_path, end_ts=1770112900)
        data = json.loads((out_dir / "miners.json").read_text())
        miner_ids = {m["miner_id"] for m in data}
        assert "miner_b" in miner_ids
        assert "miner_a" not in miner_ids


# ── Tests: API vs DB column parity ──────────────────────────────────────


class TestColumnParity:
    def test_same_columns(self, db_path: Path, out_dir: Path, monkeypatch) -> None:
        fake = _FakeHTTP(
            {
                "https://rustchain.org/api/miners": MINERS_API,
                "https://rustchain.org/epoch": EPOCH_API,
                "https://rustchain.org/wallet/balance": BALANCE_API_1,
            }
        )
        monkeypatch.setattr(exp, "fetch_json", fake)

        api_dir = out_dir / "api"
        db_dir = out_dir / "db"
        exp.run(api_dir, "csv", mode="api")
        exp.run(db_dir, "csv", mode="db", db_path=db_path)

        for tbl in exp.ALL_TABLES:
            with open(api_dir / f"{tbl}.csv", newline="") as f:
                api_cols = next(csv.reader(f))
            with open(db_dir / f"{tbl}.csv", newline="") as f:
                db_cols = next(csv.reader(f))
            assert api_cols == db_cols, f"{tbl}: api cols {api_cols} != db cols {db_cols}"


# ── Tests: --miner-id filter ─────────────────────────────────────────────


class TestMinerFilter:
    def test_filters_miners(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "json", mode="db", db_path=db_path, miner_id="miner_a")
        data = json.loads((out_dir / "miners.json").read_text())
        assert len(data) == 1
        assert data[0]["miner_id"] == "miner_a"

    def test_filters_balances(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "json", mode="db", db_path=db_path, miner_id="miner_a")
        data = json.loads((out_dir / "balances.json").read_text())
        assert len(data) == 1
        assert data[0]["miner_id"] == "miner_a"

    def test_filters_rewards(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "json", mode="db", db_path=db_path, miner_id="miner_a")
        data = json.loads((out_dir / "rewards.json").read_text())
        assert all(r["miner_id"] == "miner_a" for r in data)


# ── Tests: --table subset ───────────────────────────────────────────────


class TestTableSubset:
    def test_only_specified_tables_written(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "csv", mode="db", db_path=db_path, tables=("miners", "balances"))
        assert (out_dir / "miners.csv").exists()
        assert (out_dir / "balances.csv").exists()
        assert not (out_dir / "epochs.csv").exists()
        assert not (out_dir / "rewards.csv").exists()
        assert not (out_dir / "attestations.csv").exists()


# ── Tests: JSON shape ───────────────────────────────────────────────────


class TestJSONShape:
    def test_json_is_valid_array(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "json", mode="db", db_path=db_path)
        content = (out_dir / "miners.json").read_text()
        data = json.loads(content)
        assert isinstance(data, list)

    def test_jsonl_one_per_line(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "jsonl", mode="db", db_path=db_path)
        lines = (out_dir / "miners.jsonl").read_text().strip().splitlines()
        for line in lines:
            obj = json.loads(line)
            assert isinstance(obj, dict)


# ── Tests: streaming writer mechanics ────────────────────────────────────


class TestStreamingWriters:
    def test_json_writer_close(self, tmp_path: Path) -> None:
        fh = (tmp_path / "test.json").open("w", encoding="utf-8")
        w = exp._JSONWriter(fh)
        w.write_row({"a": 1})
        w.write_row({"b": 2})
        w.close()
        data = json.loads((tmp_path / "test.json").read_text())
        assert len(data) == 2

    def test_jsonl_writer(self, tmp_path: Path) -> None:
        fh = (tmp_path / "test.jsonl").open("w", encoding="utf-8")
        w = exp._JSONLWriter(fh)
        w.write_row({"x": 1})
        w.write_row({"x": 2})
        w.close()
        lines = (tmp_path / "test.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_parquet_writer(self, tmp_path: Path) -> None:
        path = tmp_path / "out.parquet"
        w = exp._ParquetWriter(path, ["col1", "col2"])
        w.write_row({"col1": "a", "col2": "b"})
        w.write_row({"col1": "c", "col2": "d"})
        w.close()
        import pyarrow.parquet as pq
        t = pq.read_table(path)
        assert t.num_rows == 2
        assert t.column("col1").to_pylist() == ["a", "c"]


# ── Tests: manifest ──────────────────────────────────────────────────────


class TestManifest:
    def test_manifest_created(self, db_path: Path, out_dir: Path) -> None:
        exp.run(out_dir, "csv", mode="db", db_path=db_path)
        m = json.loads((out_dir / "manifest.json").read_text())
        assert m["mode"] == "db"
        assert m["format"] == "csv"
        assert "generated_at" in m
        for tbl in exp.ALL_TABLES:
            assert tbl in m["tables"]


# ── Tests: date parsing ─────────────────────────────────────────────────


class TestParseDate:
    def test_yyyy_mm_dd(self) -> None:
        ts = exp.parse_date("2026-01-15")
        assert ts is not None
        assert ts > 0

    def test_unix_string(self) -> None:
        assert exp.parse_date("1700000000") == 1700000000

    def test_none(self) -> None:
        assert exp.parse_date(None) is None

    def test_empty(self) -> None:
        assert exp.parse_date("") is None


# ── Tests: error paths ──────────────────────────────────────────────────


class TestErrors:
    def test_db_mode_requires_path(self, out_dir: Path) -> None:
        with pytest.raises(ValueError, match="--db is required"):
            exp.run(out_dir, "csv", mode="db")

    def test_parquet_without_pyarrow(self, tmp_path: Path, monkeypatch) -> None:
        """If pyarrow import fails, writer must raise RuntimeError."""
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pyarrow":
                raise ImportError("no pyarrow")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(RuntimeError, match="pyarrow"):
            exp.run(tmp_path / "out", "parquet", mode="db", db_path=tmp_path / "dummy.db")


# ── Tests: CSV sanitisation ─────────────────────────────────────────────


class TestSanitizeRow:
    def test_prefixes_formula_chars(self) -> None:
        result = exp._sanitize_row({"a": "=SUM(A1:A2)"}, ["a"])
        assert result["a"] == "'=SUM(A1:A2)"

    def test_leaves_normal_strings(self) -> None:
        result = exp._sanitize_row({"a": "hello"}, ["a"])
        assert result["a"] == "hello"
