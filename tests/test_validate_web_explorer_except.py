from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "validate_web_explorer.py").read_text(encoding="utf-8")


def test_check_server_except_is_typed():
    assert "except requests.RequestException:" in PY
