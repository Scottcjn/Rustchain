from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "setup_miner.py").read_text(encoding="utf-8")


def test_subprocess_run_has_timeout():
    count = PY.count("subprocess.run(")
    timeout_count = PY.count("timeout=")
    assert timeout_count >= 3, f"Found {count} subprocess.run() but only {timeout_count} have timeout="
