from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "wallet" / "rustchain_wallet_ppc.py").read_text(encoding="utf-8")


def test_all_except_typed():
    assert "except (ValueError, TypeError):" in PY
    assert "except (IOError, OSError):" in PY
    assert "except ValueError:" in PY


def test_no_bare_except():
    lines = [l for l in PY.split("\n") if l.strip().startswith("except:")]
    assert lines == [], f"Found bare excepts: {lines}"
