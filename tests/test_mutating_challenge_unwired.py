# SPDX-License-Identifier: MIT
"""
Guards for the experimental anti_spoof/mutating_challenge sketch.

1. validate_response fails closed on a responder that is not the challenge
   target, and on a target with no registered hardware profile.
2. Nothing under node/ or miners/ imports the module. It is a design sketch
   with known gaps (see its module docstring); wiring it into the node must be
   a deliberate, reviewed change that also updates this test.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "rips" / "rustchain-core" / "src" / "anti_spoof" / "mutating_challenge.py"

FORBIDDEN_NAMES = {"anti_spoof", "mutating_challenge"}
PRODUCTION_TREES = ("node", "miners")
SKIP_DIR_NAMES = {"tests", "test", "__pycache__", "node_modules", "venv", ".venv"}


def _load_module():
    spec = importlib.util.spec_from_file_location("mutating_challenge_unwired_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hardware_profile():
    return {
        "cpu": {"model": "PowerMac3,6"},
        "openfirmware": {"serial_number": "OF123"},
        "gpu": {"device_id": "GPU123"},
        "storage": {"serial": "SSD123"},
    }


def _network_and_challenge(module, register=True):
    network = module.MutatingChallengeNetwork(["alpha-node", "beta-node"], genesis_seed=b"g" * 32)
    if register:
        for validator in network.validator_failures:
            network.register_hardware(validator, _hardware_profile())
    challenge = network.on_new_block(10, b"b" * 32)[0]
    challenge.mutation_params.hash_rounds = 2
    return network, challenge


def _well_formed_response(module, challenge, responder, serial_value):
    params = challenge.mutation_params
    response = module.MutatingResponse(
        challenge_id=challenge.challenge_id,
        responder=responder,
        cache_timing_ticks=params.timing_min_ticks + 1,
        memory_timing_ticks=45000,
        pipeline_timing_ticks=8000,
        jitter_variance=params.jitter_min_percent,
        thermal_celsius=(params.thermal_min_c + params.thermal_max_c) // 2,
        serial_value=serial_value,
        proof_hash=b"",
        timestamp_ms=challenge.timestamp_ms + 1000,
    )
    response.proof_hash = response.compute_proof(challenge, b"")
    return response


def test_validate_response_rejects_responder_that_is_not_the_target():
    module = _load_module()
    network, challenge = _network_and_challenge(module)
    serial = network._get_serial(_hardware_profile(), challenge.mutation_params.serial_type)

    # Control: the same response from the real target is accepted.
    accepted = _well_formed_response(module, challenge, challenge.target, serial)
    assert network.validate_response(accepted)[0] is True
    network.round_robin.results_this_round.clear()

    response = _well_formed_response(module, challenge, challenge.challenger, serial)
    assert response.responder != challenge.target

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 0.0
    assert failures == ["Responder does not match challenge target"]
    # A rejected impostor must neither record a result for the target nor
    # push the target towards the slashing threshold.
    assert network.round_robin.results_this_round == {}
    assert network.validator_failures[challenge.target] == 0


def test_validate_response_rejects_target_without_hardware_profile():
    module = _load_module()
    network, challenge = _network_and_challenge(module, register=False)
    assert challenge.target not in network.validator_hardware

    # Otherwise fully well-formed: this passed at reduced confidence before.
    response = _well_formed_response(module, challenge, challenge.target, "ANY-SERIAL")

    valid, confidence, failures = network.validate_response(response)

    assert valid is False
    assert confidence == 0.0
    assert failures == ["No hardware profile registered for target"]
    assert network.round_robin.results_this_round == {}
    assert network.validator_failures[challenge.target] == 0


def test_validate_response_rejects_target_with_empty_hardware_profile():
    module = _load_module()
    network, challenge = _network_and_challenge(module, register=False)
    network.register_hardware(challenge.target, {})

    response = _well_formed_response(module, challenge, challenge.target, "ANY-SERIAL")

    valid, _confidence, failures = network.validate_response(response)

    assert valid is False
    assert failures == ["No hardware profile registered for target"]


def _imported_module_names(tree):
    """Yield every dotted module name a parsed file imports, statically or dynamically."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.Call):
            # importlib.import_module("..."), __import__("..."), and
            # spec_from_file_location(name, ".../mutating_challenge.py")
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in {"import_module", "__import__", "spec_from_file_location"}:
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            yield sub.value


def _references_forbidden(name):
    parts = set(Path(name.replace("\\", "/")).with_suffix("").as_posix().replace("/", ".").split("."))
    return bool(parts & FORBIDDEN_NAMES)


def _is_test_file(path):
    rel_parts = path.relative_to(ROOT).parts
    if any(part in SKIP_DIR_NAMES for part in rel_parts[:-1]):
        return True
    return path.name.startswith("test_") or path.name.endswith("_test.py") or path.name == "conftest.py"


def _scan(tree_name):
    offenders, scanned = [], 0
    for path in sorted((ROOT / tree_name).rglob("*.py")):
        if _is_test_file(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            # e.g. Python 2 miners for vintage machines; they cannot import a
            # Python 3 module, and a text check still covers them.
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(name in text for name in FORBIDDEN_NAMES):
                offenders.append(f"{path.relative_to(ROOT)} (unparseable; mentions module by name)")
            scanned += 1
            continue
        scanned += 1
        for name in _imported_module_names(tree):
            if _references_forbidden(name):
                offenders.append(f"{path.relative_to(ROOT)} imports {name}")
    return offenders, scanned


def test_import_scanner_detects_forbidden_imports():
    samples = [
        "import anti_spoof",
        "import anti_spoof.mutating_challenge as mc",
        "from anti_spoof import mutating_challenge",
        "from rips.src.anti_spoof.mutating_challenge import MutatingChallengeNetwork",
        "from . import mutating_challenge",
        "import importlib\nimportlib.import_module('anti_spoof.mutating_challenge')",
        "__import__('mutating_challenge')",
        "import importlib.util as u\nu.spec_from_file_location('m', 'rips/src/anti_spoof/mutating_challenge.py')",
    ]
    for source in samples:
        names = list(_imported_module_names(ast.parse(source)))
        assert any(_references_forbidden(name) for name in names), source

    for source in ["import hashlib", "from node import anti_double_mining", "x = 'anti_spoof'"]:
        names = list(_imported_module_names(ast.parse(source)))
        assert not any(_references_forbidden(name) for name in names), source


def test_mutating_challenge_is_not_imported_by_node_or_miners():
    assert MODULE_PATH.is_file()

    offenders = []
    for tree_name in PRODUCTION_TREES:
        assert (ROOT / tree_name).is_dir(), f"expected {tree_name}/ at repo root"
        found, scanned = _scan(tree_name)
        assert scanned > 0, f"no python files scanned under {tree_name}/"
        offenders.extend(found)

    assert offenders == [], (
        "anti_spoof/mutating_challenge is an experimental design sketch and must not be "
        "imported by node/ or miners/ until the prerequisites in its module docstring are "
        "implemented and reviewed:\n  " + "\n  ".join(offenders)
    )
