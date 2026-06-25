import importlib.util
import subprocess
from pathlib import Path


def load_validator():
    path = Path(__file__).resolve().parents[1] / "validate_bounty_2303.py"
    spec = importlib.util.spec_from_file_location("validate_bounty_2303", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_tests_bounds_pytest_subprocess(monkeypatch):
    validator = load_validator()
    captured = {}

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert validator.run_tests() is True
    assert captured["args"] == [
        validator.sys.executable,
        "-m",
        "pytest",
        "bridge/test_dashboard_api.py",
        "-v",
        "--tb=short",
    ]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["timeout"] == validator.PYTEST_TIMEOUT
