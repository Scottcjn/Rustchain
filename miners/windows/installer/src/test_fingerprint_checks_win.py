import importlib.util
import sys
import types
from pathlib import Path


def load_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", types.SimpleNamespace())
    module_path = Path(__file__).with_name("fingerprint_checks_win.py")
    spec = importlib.util.spec_from_file_location("fingerprint_checks_win_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_simd_identity_wmic_probe_uses_timeout(monkeypatch):
    module = load_module(monkeypatch)
    calls = []

    def fake_check_output(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return b"Caption\r\nIntel CPU with SSE AVX\r\n"

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(module.platform, "machine", lambda: "AMD64")

    valid, data = module.check_simd_identity()

    assert valid is True
    assert data["has_sse"] is True
    assert calls[0][0] == ["wmic", "cpu", "get", "Caption"]
    assert calls[0][1]["timeout"] == module.COMMAND_TIMEOUT_SECONDS


def test_simd_identity_falls_back_when_wmic_times_out(monkeypatch):
    module = load_module(monkeypatch)

    def fake_check_output(cmd, **kwargs):
        raise module.subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(module.platform, "processor", lambda: "fallback cpu")
    monkeypatch.setattr(module.platform, "machine", lambda: "AMD64")

    valid, data = module.check_simd_identity()

    assert valid is True
    assert data["cpu_caption"] == "fallback cpu"
