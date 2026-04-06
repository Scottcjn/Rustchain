#!/usr/bin/env python3
"""
Cross-Module Epoch Window Consistency Test
============================================

Verifies that all active consensus-adjacent modules share the same
GENESIS_TIMESTAMP constant. A mismatch causes epoch window drift,
broken founder-veto expiry, and incorrect anti-double-mining checks.

This test catches any future regression where a module is updated
independently without synchronising the genesis constant.

Run: python3 tests/test_epoch_window_consistency.py
"""

import os
import re
import sys
import importlib.util
import unittest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE_DIR = os.path.join(PROJECT_ROOT, "node")

# Canonical value from the protocol spec (RIP_POA_SPEC_v1.0.md)
CANONICAL_GENESIS = 1764706927  # Dec 2, 2025 — production chain launch

# Modules that are expected to import successfully (lightweight deps)
IMPORTABLE_MODULES = [
    ("rip_200_round_robin_1cpu1vote", "node/rip_200_round_robin_1cpu1vote.py"),
    ("rip_200_v2", "node/rip_200_round_robin_1cpu1vote_v2.py"),
    ("rewards_impl", "node/rewards_implementation_rip200.py"),
    ("anti_double_mining", "node/anti_double_mining.py"),
    ("governance", "node/governance.py"),
    ("fossil_export", "fossils/fossil_record_export.py"),
    ("chain_params", "rips/rustchain-core/config/chain_params.py"),
]

# Modules checked by source-scan only (heavy deps: Flask, rustchain_crypto, etc.)
SOURCE_SCAN_MODULES = [
    ("rustchain_block_producer", "node/rustchain_block_producer.py"),
    ("rustchain_migration", "node/rustchain_migration.py"),
    ("integrated_node", "node/rustchain_v2_integrated_v2.2.1_rip200.py"),
    ("claims_eligibility", "node/claims_eligibility.py"),
]

# Old values that must NOT appear in arithmetic expressions
OLD_GENESIS_VALUES = [1728000000, 1700000000, 1735689600]


def load_module_from_file(module_name, file_path):
    """Load a Python module from an arbitrary file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def extract_genesis_from_source(file_path):
    """Extract GENESIS_TIMESTAMP value from source via regex (no import)."""
    with open(file_path, "r") as f:
        source = f.read()
    # Match: GENESIS_TIMESTAMP = <int>  or  GENESIS_TIMESTAMP: int = <int>
    match = re.search(
        r"""GENESIS_TIMESTAMP\s*(?::\s*int)?\s*=\s*(\d+)""",
        source,
    )
    if match:
        return int(match.group(1))
    return None


def has_hardcoded_old_literal(file_path):
    """Check if source contains old genesis value in an arithmetic expression."""
    with open(file_path, "r") as f:
        source = f.read()
    for old_val in OLD_GENESIS_VALUES:
        # Match patterns like: 1728000000 +  or  + 1728000000
        if re.search(rf"""(?<!\d){old_val}\s*\+""", source):
            return True, old_val
    return False, None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenesisTimestampConsistency(unittest.TestCase):
    """All active modules must share the same GENESIS_TIMESTAMP."""

    @classmethod
    def setUpClass(cls):
        cls.modules = {}       # name -> module (importable ones)
        cls.import_failures = []
        cls.source_values = {} # name -> extracted value (source scan)

        # Import lightweight modules
        for name, rel_path in IMPORTABLE_MODULES:
            file_path = os.path.join(PROJECT_ROOT, rel_path)
            if not os.path.isfile(file_path):
                cls.import_failures.append((name, f"file not found: {file_path}"))
                continue
            mod = load_module_from_file(name, file_path)
            if mod is None:
                cls.import_failures.append((name, "import failed"))
            else:
                cls.modules[name] = mod

        # Source-scan heavy modules
        for name, rel_path in SOURCE_SCAN_MODULES:
            file_path = os.path.join(PROJECT_ROOT, rel_path)
            if not os.path.isfile(file_path):
                cls.import_failures.append((name, f"file not found: {file_path}"))
                continue
            val = extract_genesis_from_source(file_path)
            if val is not None:
                cls.source_values[name] = val

    # -- Import-based tests --

    def test_importable_modules_loaded(self):
        """All lightweight modules must import successfully."""
        if self.import_failures:
            msgs = [f"  {n}: {e}" for n, e in self.import_failures
                    if n in [m for m, _ in IMPORTABLE_MODULES]]
            if msgs:
                self.fail("Failed to load modules:\n" + "\n".join(msgs))

    def test_all_importable_define_genesis(self):
        """Every importable module must define GENESIS_TIMESTAMP."""
        missing = [
            name for name, mod in self.modules.items()
            if not hasattr(mod, "GENESIS_TIMESTAMP")
        ]
        if missing:
            self.fail(f"Modules missing GENESIS_TIMESTAMP: {', '.join(missing)}")

    def test_importable_match_canonical(self):
        """Every imported module's GENESIS_TIMESTAMP must equal canonical."""
        mismatches = {}
        for name, mod in self.modules.items():
            val = getattr(mod, "GENESIS_TIMESTAMP", None)
            if val != CANONICAL_GENESIS:
                mismatches[name] = val
        if mismatches:
            detail = "\n".join(
                f"  {name} = {val} (expected {CANONICAL_GENESIS})"
                for name, val in sorted(mismatches.items())
            )
            self.fail(f"GENESIS_TIMESTAMP mismatch:\n{detail}")

    # -- Source-scan tests --

    def test_source_scan_match_canonical(self):
        """Source-extracted GENESIS_TIMESTAMP must equal canonical value."""
        mismatches = {
            name: val for name, val in self.source_values.items()
            if val != CANONICAL_GENESIS
        }
        if mismatches:
            detail = "\n".join(
                f"  {name} = {val} (expected {CANONICAL_GENESIS})"
                for name, val in sorted(mismatches.items())
            )
            self.fail(f"GENESIS_TIMESTAMP mismatch (source scan):\n{detail}")

    def test_no_hardcoded_old_literals(self):
        """No source file may contain old genesis literals in arithmetic."""
        all_paths = []
        for _, rel_path in IMPORTABLE_MODULES + SOURCE_SCAN_MODULES:
            all_paths.append((_, os.path.join(PROJECT_ROOT, rel_path)))

        offenders = []
        for name, file_path in all_paths:
            if not os.path.isfile(file_path):
                continue
            found, val = has_hardcoded_old_literal(file_path)
            if found:
                offenders.append((name, val))

        if offenders:
            detail = "\n".join(
                f"  {name}: still uses {val} in arithmetic"
                for name, val in offenders
            )
            self.fail(f"Hardcoded old genesis literals found:\n{detail}")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
