import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


class NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def inc(self, *args, **kwargs):
        pass

    def dec(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self


def load_integrated_node(db_path):
    node_dir = Path(__file__).resolve().parents[1]
    previous_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
    previous_admin_key = os.environ.get("RC_ADMIN_KEY")
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ["RC_ADMIN_KEY"] = "0" * 32

    if str(node_dir) not in sys.path:
        sys.path.insert(0, str(node_dir))

    import prometheus_client

    previous_metrics = (
        prometheus_client.Counter,
        prometheus_client.Gauge,
        prometheus_client.Histogram,
    )
    prometheus_client.Counter = NoopMetric
    prometheus_client.Gauge = NoopMetric
    prometheus_client.Histogram = NoopMetric
    try:
        spec = importlib.util.spec_from_file_location(
            "rustchain_integrated_beacon_status_test",
            node_dir / "rustchain_v2_integrated_v2.2.1_rip200.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        (
            prometheus_client.Counter,
            prometheus_client.Gauge,
            prometheus_client.Histogram,
        ) = previous_metrics
        if previous_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = previous_db_path
        if previous_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = previous_admin_key


def test_resolve_bcn_wallet_reports_inactive_status():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "node.db"
        atlas_path = Path(tmpdir) / "atlas.db"
        module = load_integrated_node(db_path)
        module.BEACON_ATLAS_DB = str(atlas_path)

        with sqlite3.connect(atlas_path) as conn:
            conn.execute(
                """
                CREATE TABLE relay_agents (
                    agent_id TEXT PRIMARY KEY,
                    pubkey_hex TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO relay_agents(agent_id, pubkey_hex, name, status) VALUES (?, ?, ?, ?)",
                ("bcn_inactive", "00" * 32, "Inactive Agent", "suspended"),
            )

        result = module.resolve_bcn_wallet("bcn_inactive")

    assert result == {"found": False, "error": "beacon_agent_status:suspended"}
