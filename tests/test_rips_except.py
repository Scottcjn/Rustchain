from pathlib import Path


ENTROPY = (Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "validator" / "entropy.py").read_text(encoding="utf-8")
SETUP = (Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "validator" / "setup_validator.py").read_text(encoding="utf-8")


def test_entropy_no_bare_except():
    bare = [l for l in ENTROPY.split("\n") if l.strip() == "except:"]
    assert bare == [], f"Found bare excepts: {bare}"


def test_setup_no_bare_except():
    bare = [l for l in SETUP.split("\n") if l.strip() == "except:"]
    assert bare == [], f"Found bare excepts: {bare}"
