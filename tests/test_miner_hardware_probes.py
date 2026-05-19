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
    assert miner._parse_int_output("10\n") == 10
    assert miner._parse_memory_bytes_to_gb("17179869184\n") == 16
    assert miner._parse_wmic_value("Name=Intel Core i5-10400F\n\n", "Name") == "Intel Core i5-10400F"


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


def test_linux_miner_filters_virtual_macs_from_ip_link(monkeypatch):
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_mac_filter")
    instance = object.__new__(miner.LocalMiner)
    ip_link = "\n".join(
        [
            "1: lo: <LOOPBACK,UP> mtu 65536 link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00",
            "2: docker0: <BROADCAST,MULTICAST> mtu 1500 link/ether 02:42:00:12:34:56 brd ff:ff:ff:ff:ff:ff",
            "3: veth9@if2: <BROADCAST,MULTICAST> mtu 1500 link/ether 4a:24:1f:22:33:44 brd ff:ff:ff:ff:ff:ff",
            "4: tailscale0: <POINTOPOINT> mtu 1280 link/ether 66:55:44:33:22:11 brd ff:ff:ff:ff:ff:ff",
            "5: enp3s0: <BROADCAST,MULTICAST,UP> mtu 1500 link/ether 10:22:33:44:55:66 brd ff:ff:ff:ff:ff:ff",
            "6: wlan0: <BROADCAST,MULTICAST,UP> mtu 1500 link/ether 10:22:33:44:55:66 brd ff:ff:ff:ff:ff:ff",
            "7: eth0: <BROADCAST,MULTICAST,UP> mtu 1500 link/ether 02:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff",
            "8: enp4s0: <BROADCAST,MULTICAST,UP> mtu 1500 link/ether 06:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff",
        ]
    )
    calls = []

    class Result:
        stdout = ip_link

    def fake_run(args, **kwargs):
        calls.append(args)
        return Result()

    monkeypatch.setattr(miner.subprocess, "run", fake_run)

    assert instance._get_mac_addresses() == ["10:22:33:44:55:66"]
    assert calls == [["ip", "-o", "link"]]


def test_linux_miner_collects_darwin_hardware_with_sysctl(monkeypatch):
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_darwin_hw")
    instance = object.__new__(miner.LocalMiner)
    command_output = {
        ("sysctl", "-n", "machdep.cpu.brand_string"): "Apple M5\n",
        ("sysctl", "-n", "hw.ncpu"): "10\n",
        ("sysctl", "-n", "hw.memsize"): "17179869184\n",
    }

    monkeypatch.setattr(miner.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(miner.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(miner.socket, "gethostname", lambda: "macbook.local")
    monkeypatch.setattr(miner, "get_linux_serial", lambda: None)
    monkeypatch.setattr(miner.LocalMiner, "_get_mac_addresses", lambda self: ["aa:bb:cc:dd:ee:ff"])
    monkeypatch.setattr(miner.LocalMiner, "_run_cmd", lambda self, args: command_output.get(tuple(args), ""))

    hw = instance._get_hw_info()

    assert hw["platform"] == "Darwin"
    assert hw["family"] == "ARM"
    assert hw["arch"] == "aarch64"
    assert hw["cpu"] == "Apple M5"
    assert hw["cores"] == 10
    assert hw["memory_gb"] == 16


def test_linux_miner_darwin_hardware_falls_back_when_sysctl_missing(monkeypatch):
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_darwin_fallback_hw")
    instance = object.__new__(miner.LocalMiner)
    command_output = {
        ("sysctl", "-n", "machdep.cpu.brand_string"): None,
        ("sysctl", "-n", "hw.ncpu"): "",
        ("sysctl", "-n", "hw.memsize"): "",
    }

    monkeypatch.setattr(miner.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(miner.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(miner.socket, "gethostname", lambda: "macbook.local")
    monkeypatch.setattr(miner.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(miner, "get_linux_serial", lambda: None)
    monkeypatch.setattr(miner.LocalMiner, "_get_mac_addresses", lambda self: ["aa:bb:cc:dd:ee:ff"])
    monkeypatch.setattr(miner.LocalMiner, "_run_cmd", lambda self, args: command_output.get(tuple(args), ""))

    hw = instance._get_hw_info()

    assert hw["cpu"] == "Unknown"
    assert hw["cores"] == 8
    assert hw["memory_gb"] == 32


def test_linux_miner_windows_hardware_warns_and_uses_wmic_fallbacks(monkeypatch):
    miner = load_module(Path("miners/linux/rustchain_linux_miner.py"), "rustchain_linux_miner_windows_hw")
    instance = object.__new__(miner.LocalMiner)
    command_output = {
        ("wmic", "cpu", "get", "Name", "/value"): "Name=Intel Core i5-10400F @ 2.90GHz\n",
        ("wmic", "cpu", "get", "NumberOfLogicalProcessors", "/value"): "NumberOfLogicalProcessors=12\n",
        ("wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"): "TotalPhysicalMemory=34359738368\n",
    }

    monkeypatch.setattr(miner.platform, "system", lambda: "Windows")
    monkeypatch.setattr(miner.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(miner.socket, "gethostname", lambda: "GTX1660super")
    monkeypatch.setattr(miner, "get_linux_serial", lambda: None)
    monkeypatch.setattr(miner.LocalMiner, "_get_mac_addresses", lambda self: ["aa:bb:cc:dd:ee:ff"])
    monkeypatch.setattr(miner.LocalMiner, "_run_cmd", lambda self, args: command_output.get(tuple(args), ""))

    hw = instance._get_hw_info()

    assert hw["platform"] == "Windows"
    assert hw["cpu"] == "Intel Core i5-10400F @ 2.90GHz"
    assert hw["cores"] == 12
    assert hw["memory_gb"] == 32
    assert "not a primary supported platform" in hw["probe_warning"]


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
