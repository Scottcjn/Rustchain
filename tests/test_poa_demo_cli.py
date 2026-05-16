import os
import subprocess
import sys
from pathlib import Path


def test_proof_of_antiquity_demo_runs():
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "rips" / "python")
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, "-m", "rustchain.proof_of_antiquity"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "RUSTCHAIN PROOF OF ANTIQUITY" in result.stdout
    assert "Ryzen 9 7950X" in result.stdout
    assert "NameError" not in result.stderr
