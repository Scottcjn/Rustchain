from pathlib import Path


FP = (Path(__file__).resolve().parents[1] / "miners" / "windows" / "fingerprint_checks.py").read_text(encoding="utf-8")
FPWIN = (Path(__file__).resolve().parents[1] / "miners" / "windows" / "installer" / "src" / "fingerprint_checks_win.py").read_text(encoding="utf-8")


def test_fingerprint_no_bare_except():
    bare = [l for l in FP.split("\n") if l.strip() == "except:"]
    assert bare == [], f"Found bare excepts: {bare}"


def test_fingerprint_win_no_bare_except():
    bare = [l for l in FPWIN.split("\n") if l.strip() == "except:"]
    assert bare == [], f"Found bare excepts: {bare}"
