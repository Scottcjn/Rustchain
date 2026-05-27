# SPDX-License-Identifier: MIT
import importlib
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOT_CHIME_SRC = REPO_ROOT / "issue2307_boot_chime" / "src"


def test_proof_of_iron_imports_from_documented_src_path(monkeypatch):
    monkeypatch.syspath_prepend(str(BOOT_CHIME_SRC))
    monkeypatch.setitem(sys.modules, "numpy", types.SimpleNamespace(ndarray=object))

    sys.modules.pop("proof_of_iron", None)

    module = importlib.import_module("proof_of_iron")

    assert module.ProofOfIron.__name__ == "ProofOfIron"
    assert module.AcousticFingerprint.__name__ == "AcousticFingerprint"
    assert module.BootChimeCapture.__name__ == "BootChimeCapture"
