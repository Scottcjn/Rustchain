import importlib.util
import sqlite3
from pathlib import Path


EXPLORER_DASHBOARD = (
    Path(__file__).resolve().parents[1] / "explorer" / "rustchain_dashboard.py"
)


def load_dashboard():
    spec = importlib.util.spec_from_file_location(
        "explorer_rustchain_dashboard_multiplier_under_test",
        EXPLORER_DASHBOARD,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def _make_db(db_path, weights, epoch=12):
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE epochs (epoch INTEGER PRIMARY KEY, start_time INTEGER);
        CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER);
        CREATE TABLE miner_attest_recent (miner TEXT, device_arch TEXT);
        CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL);
        """
    )
    conn.execute("INSERT INTO epochs (epoch, start_time) VALUES (?, ?)", (epoch, 100))
    conn.executemany(
        "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
        [(epoch, f"miner_{i}", w) for i, w in enumerate(weights)],
    )
    conn.commit()
    conn.close()


def test_multiplier_impact_normalizes_against_full_epoch_not_top10(tmp_path, monkeypatch):
    """With >10 enrolled miners the shown per-miner shares must be normalized
    against the WHOLE epoch weight/count, matching the real payout math
    (sophia_elya_service SUM(weight), rip_200 total_weight). Summing only the
    displayed top-10 weights over-states every shown miner's projected RTC."""
    dashboard = load_dashboard()
    db_path = tmp_path / "rustchain.db"

    epoch, epoch_pot = 12, 12.0
    # 12 equally-weighted miners: true share = 12.0 / 12 = 1.0 RTC each.
    _make_db(db_path, weights=[1.0] * 12, epoch=epoch)

    class FakeResponse:
        def json(self):
            return {"epoch": epoch, "epoch_pot": epoch_pot}

    monkeypatch.setattr(dashboard, "DB_PATH", str(db_path))
    monkeypatch.setattr(dashboard.requests, "get", lambda *a, **k: FakeResponse())

    body = dashboard.app.test_client().get("/api/reward-analytics").get_json()
    impact = body["multiplier_impact"]

    assert len(impact) == 10  # still only the top-10 rows are displayed
    for row in impact:
        # Buggy code divided the pot by 10 (top-10 slice), inflating each share
        # to 1.2 RTC. Correct value normalizes against all 12 miners -> 1.0.
        assert abs(row["weighted_share_rtc"] - 1.0) < 1e-6, row
        assert abs(row["base_share_rtc"] - 1.0) < 1e-6, row

    # Sanity: the ten shown miners cannot collectively claim the entire pot when
    # 12 miners are enrolled (top-10 truncation used to make this sum to 12.0).
    assert sum(r["weighted_share_rtc"] for r in impact) < epoch_pot
