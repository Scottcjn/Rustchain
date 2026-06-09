from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_integrated_node_fingerprint_debug_does_not_use_bare_except():
    source = (ROOT / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py").read_text(
        encoding="utf-8"
    )

    assert "except: pass" not in source
    assert "payload serialization failed" in source


def test_status_monitor_history_load_does_not_use_bare_except():
    source = (ROOT / "static" / "status" / "monitor.py").read_text(encoding="utf-8")

    assert "except: pass" not in source
    assert "except (OSError, json.JSONDecodeError):" in source
