# SPDX-License-Identifier: MIT

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_RIPS_PATH = REPO_ROOT / "rips" / "python"


def load_proof_of_antiquity():
    if str(PYTHON_RIPS_PATH) not in sys.path:
        sys.path.insert(0, str(PYTHON_RIPS_PATH))
    return importlib.import_module("rustchain.proof_of_antiquity")


def proof(score):
    return SimpleNamespace(antiquity_score=score)


def test_select_block_validator_uses_secrets_for_zero_score_fallback(monkeypatch):
    poa = load_proof_of_antiquity()
    proofs = [proof(0), proof(0), proof(0)]
    calls = []

    def fake_randbelow(bound):
        calls.append(bound)
        return 1

    monkeypatch.setattr(poa.secrets, "randbelow", fake_randbelow)

    assert poa.select_block_validator(proofs) is proofs[1]
    assert calls == [3]


def test_select_block_validator_uses_secrets_for_weighted_selection(monkeypatch):
    poa = load_proof_of_antiquity()
    proofs = [proof(1.0), proof(2.0)]
    calls = []

    def fake_randbelow(bound):
        calls.append(bound)
        return 2**52

    monkeypatch.setattr(poa.secrets, "randbelow", fake_randbelow)

    assert poa.select_block_validator(proofs) is proofs[1]
    assert calls == [2**53]


def test_select_block_validator_handles_tiny_positive_scores(monkeypatch):
    poa = load_proof_of_antiquity()
    proofs = [proof(1e-9)]
    calls = []

    def fake_randbelow(bound):
        calls.append(bound)
        return 0

    monkeypatch.setattr(poa.secrets, "randbelow", fake_randbelow)

    assert poa.select_block_validator(proofs) is proofs[0]
    assert calls == [2**53]


def test_select_block_validator_returns_none_for_empty_proofs():
    poa = load_proof_of_antiquity()

    assert poa.select_block_validator([]) is None
