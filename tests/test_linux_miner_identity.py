# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = REPO_ROOT / "miners" / "linux" / "rustchain_linux_miner.py"


def load_miner_module():
    spec = importlib.util.spec_from_file_location("linux_miner_under_test", MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_miner_id_uses_detected_arch_and_hostname():
    miner = load_miner_module()

    miner_id = miner._miner_id_from_hw(
        {
            "arch": "aarch64",
            "hostname": "Lab ARM Box",
        }
    )

    assert miner_id == "aarch64-lab-arm-box"
    assert "ryzen" not in miner_id


def test_linux_miner_source_does_not_hardcode_victus_identity():
    source = MINER_PATH.read_text(encoding="utf-8")

    assert "HP Victus" not in source
    assert "ryzen5-" not in source
    assert "RustChain Local Linux Miner" in source


def test_parse_ioreg_serial_extracts_platform_serial():
    miner = load_miner_module()

    output = '''
    +-o IOPlatformExpertDevice  <class IOPlatformExpertDevice, id 0x100000100, registered, matched, active, busy 0 (88 ms), retain 42>
        "IOPlatformSerialNumber" = "C02TESTSERIAL"
    '''

    assert miner._parse_ioreg_serial(output) == "C02TESTSERIAL"


def test_hardware_serial_uses_macos_probe(monkeypatch):
    miner = load_miner_module()

    monkeypatch.setattr(miner, "get_macos_serial", lambda: "mac-serial")
    monkeypatch.setattr(
        miner,
        "get_linux_serial",
        lambda: (_ for _ in ()).throw(AssertionError("Darwin should not use Linux serial probes")),
    )

    assert miner.get_hardware_serial("Darwin") == "mac-serial"


def test_local_miner_can_use_ephemeral_keypair_without_persisting(monkeypatch):
    miner = load_miner_module()
    calls = {"ephemeral": 0, "persisted": 0}

    def generate_ephemeral():
        calls["ephemeral"] += 1
        return {"private_key": "ephemeral-private", "public_key": "ephemeral-public"}

    def persist_key():
        calls["persisted"] += 1
        raise AssertionError("dry-run should not persist miner keys")

    monkeypatch.setattr(miner, "CRYPTO_AVAILABLE", True)
    monkeypatch.setattr(miner, "FINGERPRINT_AVAILABLE", False)
    monkeypatch.setattr(miner, "generate_keypair", generate_ephemeral)
    monkeypatch.setattr(miner, "get_or_create_keypair", persist_key)
    monkeypatch.setattr(miner, "get_hardware_serial", lambda: "test-serial")

    instance = miner.LocalMiner(wallet="RTC-test-wallet", persist_key=False)

    assert instance.public_key == "ephemeral-public"
    assert calls == {"ephemeral": 1, "persisted": 0}


def test_main_dry_run_disables_key_persistence(monkeypatch):
    miner = load_miner_module()
    seen = {}

    class FakeMiner:
        def __init__(self, **kwargs):
            seen["persist_key"] = kwargs["persist_key"]

        def dry_run(self):
            seen["dry_run"] = True
            return True

        def mine(self):
            raise AssertionError("dry-run should not start mining")

    monkeypatch.setattr(miner, "LocalMiner", FakeMiner)

    assert miner.main(["--dry-run"]) == 0
    assert seen == {"persist_key": False, "dry_run": True}


def test_main_normal_mode_keeps_key_persistence(monkeypatch):
    miner = load_miner_module()
    seen = {}

    class FakeMiner:
        def __init__(self, **kwargs):
            seen["persist_key"] = kwargs["persist_key"]

        def dry_run(self):
            raise AssertionError("normal mode should not run dry-run")

        def mine(self):
            seen["mine"] = True
            return 0

    monkeypatch.setattr(miner, "LocalMiner", FakeMiner)

    assert miner.main([]) == 0
    assert seen == {"persist_key": True, "mine": True}
