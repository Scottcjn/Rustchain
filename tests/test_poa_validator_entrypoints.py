import json
import subprocess
import sys
from pathlib import Path


def test_poa_cli_runs_without_external_pythonpath(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    genesis = tmp_path / "genesis.json"
    genesis.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "rustchain-poa/cli/run_validator.py", str(genesis)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
, check=True)

    assert result.returncode == 0, result.stderr
    output = result.stdout[result.stdout.find("{") :]
    assert json.loads(output)["validated"] in {True, False}
