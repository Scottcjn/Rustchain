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
