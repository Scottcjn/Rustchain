from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "rips" / "rustchain-core" / "validator" / "setup_validator.py").read_text(encoding="utf-8")


def test_subprocess_run_has_timeout():
    run_calls = PY.count("subprocess.run([")
    timeout_calls = PY.count("timeout=30")
    assert timeout_calls >= 4, f"Found {run_calls} subprocess.run() calls but only {timeout_calls} have timeout=30"
