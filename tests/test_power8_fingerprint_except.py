from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "miners" / "power8" / "fingerprint_checks_power8.py").read_text(encoding="utf-8")


def test_no_bare_except():
    bare = [l for l in PY.split("\n") if l.strip() == "except:"]
    assert bare == [], f"Found bare excepts: {bare}"
