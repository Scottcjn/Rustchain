from pathlib import Path


ROM = (Path(__file__).resolve().parents[1] / "node" / "rom_fingerprint_db.py").read_text(encoding="utf-8")
HW = (Path(__file__).resolve().parents[1] / "node" / "hardware_fingerprint.py").read_text(encoding="utf-8")


def test_rom_no_bare_except():
    assert "except Exception:" in ROM


def test_hw_no_bare_except():
    assert HW.count("except:") == 0


def test_hw_exception_count():
    assert HW.count("except Exception:") >= 5
