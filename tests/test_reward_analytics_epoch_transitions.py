import importlib.util
import sqlite3
from pathlib import Path


EXPLORER_DASHBOARD = (
    Path(__file__).resolve().parents[1] / "explorer" / "rustchain_dashboard.py"
)


def load_dashboard():
    spec = importlib.util.spec_from_file_location(
        "explorer_rustchain_dashboard_under_test",
        EXPLORER_DASHBOARD,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def test_build_epoch_transition_analytics_from_epoch_start_history():
    dashboard = load_dashboard()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE epochs (epoch INTEGER PRIMARY KEY, start_time INTEGER)")
    conn.executemany(
        "INSERT INTO epochs (epoch, start_time) VALUES (?, ?)",
        [
            (7, 1000),
            (8, 4600),
            (9, 8200),
        ],
    )

    history, metrics = dashboard.build_epoch_transition_analytics(conn)

    assert history == [
        {
            "from_epoch": 7,
            "to_epoch": 8,
            "transition_at": 4600,
            "interval_seconds": 3600,
        },
        {
            "from_epoch": 8,
            "to_epoch": 9,
            "transition_at": 8200,
            "interval_seconds": 3600,
        },
    ]
    assert metrics == {
        "transition_count": 2,
        "average_interval_seconds": 3600.0,
        "last_transition_at": 8200,
        "last_from_epoch": 8,
        "last_to_epoch": 9,
    }


def test_reward_analytics_api_includes_epoch_transition_payload(tmp_path, monkeypatch):
    dashboard = load_dashboard()
    db_path = tmp_path / "rustchain.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE epochs (epoch INTEGER PRIMARY KEY, start_time INTEGER);
        CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER);
        CREATE TABLE miner_attest_recent (miner TEXT, device_arch TEXT);
        CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL);
        """
    )
    conn.executemany(
        "INSERT INTO epochs (epoch, start_time) VALUES (?, ?)",
        [(10, 100), (11, 3700), (12, 7300)],
    )
    conn.executemany(
        "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
        [(10, "miner_a", 1000000), (11, "miner_a", 2000000)],
    )
    conn.execute(
        "INSERT INTO miner_attest_recent (miner, device_arch) VALUES (?, ?)",
        ("miner_a", "ppc"),
    )
    conn.execute(
        "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
        (12, "miner_a", 2.5),
    )
    conn.commit()
    conn.close()

    class FakeResponse:
        def json(self):
            return {"epoch": 12, "epoch_pot": 3.0}

    monkeypatch.setattr(dashboard, "DB_PATH", str(db_path))
    monkeypatch.setattr(dashboard.requests, "get", lambda *args, **kwargs: FakeResponse())

    response = dashboard.app.test_client().get("/api/reward-analytics")

    assert response.status_code == 200
    body = response.get_json()
    assert body["epoch_transition_history"][-1] == {
        "from_epoch": 11,
        "to_epoch": 12,
        "transition_at": 7300,
        "interval_seconds": 3600,
    }
    assert body["epoch_transition_metrics"]["transition_count"] == 2
    assert body["epoch_transition_metrics"]["last_to_epoch"] == 12
