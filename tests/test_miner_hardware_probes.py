# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


def load_module(relative_path, module_name):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_linux_miner_parses_lscpu_and_free_output():
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner")

    assert miner._parse_lscpu_model("Architecture: x86_64\nModel name: AMD Ryzen 5 8645HS\n") == "AMD Ryzen 5 8645HS"
    assert miner._parse_free_memory_gb("       total used free\nMem:      31    1   30\nSwap:      0    0    0\n") == 31


def test_power8_miner_parses_lscpu_proc_cpuinfo_and_free_output():
    miner = load_module(Path("miners/power8/rustchain_power8_miner.py"), "rustchain_power8_miner")

    assert miner._parse_lscpu_model("Architecture: ppc64le\nModel name: POWER8E\n") == "POWER8E"
    assert miner._parse_proc_cpu_model("processor\t: 0\ncpu\t\t: POWER8 (raw), altivec supported\n") == "POWER8 (raw), altivec supported"
    assert miner._parse_free_memory_gb("       total used free\nMem:     576    9  567\n") == 576


def test_linux_miner_run_cmd_uses_argument_list_without_shell(monkeypatch):
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_run_cmd")
    instance = object.__new__(miner.LocalMiner)
    calls = []

    class Result:
        stdout = "ok\n"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr(miner.subprocess, "run", fake_run)

    assert instance._run_cmd(["nproc"]) == "ok"
    assert calls == [(["nproc"], {"stdout": miner.subprocess.PIPE, "stderr": miner.subprocess.PIPE, "text": True, "timeout": 10})]


def test_linux_miner_adds_hardware_binding_entropy_aliases():
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_entropy_aliases")
    results = {
        "clock_drift": {"data": {"cv": 0.022}},
        "cache_timing": {"data": {"l1_ns": 11.5, "l2_ns": 18.75}},
        "thermal_drift": {"data": {"drift_ratio": 1.034}},
        "instruction_jitter": {
            "data": {
                "int_avg_ns": 1000,
                "int_stdev": 50,
                "fp_avg_ns": 2000,
                "fp_stdev": 40,
                "branch_avg_ns": 1500,
                "branch_stdev": 30,
            }
        },
    }

    profile = miner._add_hardware_binding_entropy_aliases(results)

    assert profile == {
        "clock_cv": 0.022,
        "cache_l1": 11.5,
        "cache_l2": 18.75,
        "thermal_ratio": 1.034,
        "jitter_cv": 0.03,
    }
    assert results["cache_timing"]["data"]["L1"] == 11.5
    assert results["cache_timing"]["data"]["L2"] == 18.75
    assert results["thermal_drift"]["data"]["ratio"] == 1.034
    assert results["instruction_jitter"]["data"]["cv"] == 0.03


def test_linux_miner_filters_virtual_macs_and_prefers_active_physical_iface():
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_macs")
    output = """
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000\\    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000\\    link/ether 88:a2:9e:a6:58:ce brd ff:ff:ff:ff:ff:ff
3: wlan0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc fq_codel state DOWN mode DORMANT group default qlen 1000\\    link/ether 88:a2:9e:a6:58:cf brd ff:ff:ff:ff:ff:ff
5: docker0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN mode DEFAULT group default \\    link/ether 02:42:a7:e5:ff:ff brd ff:ff:ff:ff:ff:ff
8: vethf5058cc@if7: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master br-c6f6f37bad09 state UP mode DEFAULT group default \\    link/ether 0a:e2:34:f6:e2:0a brd ff:ff:ff:ff:ff:ff link-netnsid 0
"""

    assert miner._parse_ip_link_macs(output) == ["88:a2:9e:a6:58:ce"]


def test_power8_miner_run_cmd_uses_argument_list_without_shell(monkeypatch):
    miner = load_module(Path("miners/power8/rustchain_power8_miner.py"), "rustchain_power8_miner_run_cmd")
    instance = object.__new__(miner.LocalMiner)
    calls = []

    class Result:
        stdout = "ok\n"

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr(miner.subprocess, "run", fake_run)

    assert instance._run_cmd(["nproc"]) == "ok"
    assert calls == [(["nproc"], {"stdout": miner.subprocess.PIPE, "stderr": miner.subprocess.PIPE, "text": True, "timeout": 10})]
