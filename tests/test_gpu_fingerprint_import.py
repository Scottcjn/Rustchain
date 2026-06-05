# SPDX-License-Identifier: MIT
"""Regression coverage for importing the GPU fingerprint helper on CPU CI."""

import builtins
import importlib.util
import sys
from pathlib import Path

import pytest


def test_gpu_fingerprint_import_without_torch_does_not_exit(monkeypatch):
    original_import = builtins.__import__

    def import_without_torch(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "torch", raising=False)
    monkeypatch.delitem(sys.modules, "torch.cuda", raising=False)
    monkeypatch.setattr(builtins, "__import__", import_without_torch)

    module_path = Path(__file__).resolve().parents[1] / "miners" / "gpu_fingerprint.py"
    spec = importlib.util.spec_from_file_location("gpu_fingerprint_without_torch", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    monkeypatch.setitem(sys.modules, spec.name, module)

    spec.loader.exec_module(module)

    assert module.HAS_TORCH is False
    with pytest.raises(RuntimeError, match="PyTorch with CUDA support required"):
        module.check_requirements()
