import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "rustchainnode"
    / "rustchainnode"
    / "hardware.py"
)


def load_hardware_module():
    spec = importlib.util.spec_from_file_location("rustchainnode_hardware_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_detect_cpu_info_maps_modern_x86_and_normalizes_system(monkeypatch):
    module = load_hardware_module()
    monkeypatch.setattr(module.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module.platform, "python_version", lambda: "3.11.9")
    monkeypatch.setattr(module.os, "cpu_count", lambda: 8)

    info = module.detect_cpu_info()

    assert info == {
        "arch": "amd64",
        "arch_type": "modern_x86",
        "system": "linux",
        "cpu_count": 8,
        "optimal_threads": 8,
        "antiquity_multiplier": 1.0,
        "python_version": "3.11.9",
    }


def test_detect_cpu_info_uses_one_thread_when_cpu_count_is_unavailable(monkeypatch):
    module = load_hardware_module()
    monkeypatch.setattr(module.platform, "machine", lambda: "mips64")
    monkeypatch.setattr(module.platform, "system", lambda: "FreeBSD")
    monkeypatch.setattr(module.platform, "python_version", lambda: "3.12.1")
    monkeypatch.setattr(module.os, "cpu_count", lambda: None)

    info = module.detect_cpu_info()

    assert info["arch"] == "mips64"
    assert info["arch_type"] == "unknown"
    assert info["system"] == "freebsd"
    assert info["cpu_count"] == 1
    assert info["optimal_threads"] == 1
    assert info["antiquity_multiplier"] == 1.0


def test_detect_cpu_info_maps_vintage_powerpc_multiplier(monkeypatch):
    module = load_hardware_module()
    monkeypatch.setattr(module.platform, "machine", lambda: "ppc")
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module.platform, "python_version", lambda: "3.10.0")
    monkeypatch.setattr(module.os, "cpu_count", lambda: 2)

    info = module.detect_cpu_info()

    assert info["arch_type"] == "ppc"
    assert info["optimal_threads"] == 2
    assert info["antiquity_multiplier"] == 2.5


def test_get_optimal_config_uses_detected_hardware_and_custom_port(monkeypatch):
    module = load_hardware_module()
    monkeypatch.setattr(
        module,
        "detect_cpu_info",
        lambda: {
            "optimal_threads": 4,
            "arch_type": "ppc64le",
            "antiquity_multiplier": 1.8,
        },
    )

    config = module.get_optimal_config("RTC123", port=9100)

    assert config == {
        "wallet": "RTC123",
        "port": 9100,
        "threads": 4,
        "arch_type": "ppc64le",
        "antiquity_multiplier": 1.8,
        "node_url": "https://50.28.86.131",
        "auto_configured": True,
    }
