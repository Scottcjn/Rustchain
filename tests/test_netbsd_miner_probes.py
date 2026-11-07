# SPDX-License-Identifier: MIT
"""Deterministic tests for NetBSD-native hardware probes."""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "netbsd" / "rustchain_netbsd_miner.py"
SPEC = importlib.util.spec_from_file_location("netbsd_miner", MINER_PATH)
miner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(miner)


def test_architecture_classification_uses_measured_architecture():
    assert miner._classify_family("amd64") == ("x86", "amd64")
    assert miner._classify_family("sparc64") == ("SPARC", "sparc")
    assert miner._classify_family("unrecognized-netbsd-port") == ("unknown", "unknown")


def test_missing_sysctl_values_remain_unknown(monkeypatch):
    values = {
        "kern.ostype": "NetBSD",
        "hw.machine_arch": "amd64",
        "machdep.cpu_model": "Measured CPU model",
        "hw.ncpuonline": "",
        "hw.ncpu": "not-a-number",
        "hw.physmem64": "",
        "hw.physmem": "invalid",
    }
    monkeypatch.setattr(miner, "_netbsd_sysctl", lambda key: values.get(key, ""))

    class Probe:
        def _get_mac_addresses(self):
            return []

    hw = miner._netbsd_get_hw_info(Probe())
    assert hw["platform"] == "NetBSD"
    assert hw["machine"] == "amd64"
    assert hw["family"] == "x86"
    assert hw["arch"] == "amd64"
    assert hw["cores"] is None
    assert hw["memory_gb"] is None
    assert hw["macs"] == []
    assert hw["mac"] is None


def test_missing_netbsd_mac_does_not_call_linux_probe(monkeypatch):
    outputs = {"ifconfig -l": "lo0 em0"}

    def run(args, **kwargs):
        class Result:
            stdout = outputs.get(" ".join(args), "")
        return Result()

    monkeypatch.setattr(miner.subprocess, "run", run)

    class Probe:
        _core_class = type("Core", (), {"_get_mac_addresses": staticmethod(
            lambda _self: (_ for _ in ()).throw(AssertionError("Linux probe invoked"))
        )})

    assert miner._netbsd_get_mac_addresses(Probe()) == []


def test_test_only_never_enters_network_or_mining_path(monkeypatch, capsys):
    calls = []

    class LocalMiner:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs["persist_key"]))
            self.hw_info = {}

        def dry_run(self):
            calls.append(("dry_run",))

        def mine(self):
            calls.append(("mine",))

    class Core:
        NODE_URL = "https://rustchain.org"

    Core.LocalMiner = LocalMiner

    monkeypatch.setattr(miner, "assert_netbsd_platform", lambda: None)
    monkeypatch.setattr(miner, "_load_core_miner", lambda: Core)
    monkeypatch.setattr(miner, "_netbsd_sysctl", lambda key: {
        "kern.ostype": "NetBSD",
        "kern.osrelease": "10.0",
    }.get(key, ""))
    monkeypatch.setenv("RUSTCHAIN_NODE", "https://rustchain.org")

    assert miner.main(["--test-only"]) == 0
    assert calls == [("init", False)]
    assert "No attestation was sent" in capsys.readouterr().out
