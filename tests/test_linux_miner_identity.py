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
