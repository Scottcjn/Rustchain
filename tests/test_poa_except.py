from pathlib import Path


SYNC = (Path(__file__).resolve().parents[1] / "rustchain-poa" / "tools" / "relay" / "poa_sync_watcher.py").read_text(encoding="utf-8")
HW = (Path(__file__).resolve().parents[1] / "rustchain-poa" / "validator" / "hardware_fingerprint.py").read_text(encoding="utf-8")
EMU = (Path(__file__).resolve().parents[1] / "rustchain-poa" / "validator" / "emulation_detector.py").read_text(encoding="utf-8")


def test_poa_sync_except_typed():
    assert "except (json.JSONDecodeError, OSError):" in SYNC


def test_poa_hw_except_typed():
    assert "except (subprocess.CalledProcessError, OSError):" in HW


def test_poa_emu_except_typed():
    assert "except (subprocess.CalledProcessError, FileNotFoundError):" in EMU
