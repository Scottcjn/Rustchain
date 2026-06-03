# SPDX-License-Identifier: MIT

import datetime
import importlib.util
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAIN_PARAMS_PATH = REPO_ROOT / "rips" / "rustchain-core" / "config" / "chain_params.py"


def load_chain_params():
    spec = importlib.util.spec_from_file_location("rustchain_core_chain_params", CHAIN_PARAMS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_year_uses_runtime_year():
    chain_params = load_chain_params()

    assert chain_params.CURRENT_YEAR == datetime.datetime.now().year


def test_current_year_has_single_assignment():
    source = CHAIN_PARAMS_PATH.read_text(encoding="utf-8")

    assignments = re.findall(r"^CURRENT_YEAR\s*:\s*int\s*=", source, flags=re.MULTILINE)
    assert len(assignments) == 1
    assert "CURRENT_YEAR: int = 2025" not in source
