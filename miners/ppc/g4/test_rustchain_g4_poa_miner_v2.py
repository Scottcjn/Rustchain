import importlib.util
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("rustchain_g4_poa_miner_v2.py")
    spec = importlib.util.spec_from_file_location("rustchain_g4_poa_miner_v2_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_helper_adds_timeout(monkeypatch):
    module = load_module()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))

        class Result:
            stdout = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._run_with_timeout(["ifconfig"], capture_output=True, text=True)

    assert calls[0][1]["timeout"] == module.COMMAND_TIMEOUT_SECONDS


def test_run_helper_preserves_explicit_timeout(monkeypatch):
    module = load_module()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))

        class Result:
            stdout = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._run_with_timeout(["ifconfig"], timeout=1)

    assert calls[0][1]["timeout"] == 1
