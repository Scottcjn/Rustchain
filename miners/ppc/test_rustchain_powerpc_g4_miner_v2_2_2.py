import importlib.util
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("rustchain_powerpc_g4_miner_v2.2.2.py")
    spec = importlib.util.spec_from_file_location("rustchain_powerpc_g4_miner_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_output_helper_adds_timeout(monkeypatch):
    module = load_module()
    calls = []

    def fake_check_output(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return b"ok"

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)

    assert module._check_output_with_timeout(["system_profiler"]) == b"ok"
    assert calls[0][1]["timeout"] == module.COMMAND_TIMEOUT_SECONDS


def test_check_output_helper_preserves_explicit_timeout(monkeypatch):
    module = load_module()
    calls = []

    def fake_check_output(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return b"ok"

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)

    module._check_output_with_timeout(["system_profiler"], timeout=1)

    assert calls[0][1]["timeout"] == 1
