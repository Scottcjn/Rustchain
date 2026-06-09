from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "static" / "bridge" / "update_stats.py").read_text(encoding="utf-8")


def test_bridge_except_is_typed():
    assert "except requests.RequestException: continue" in PY
