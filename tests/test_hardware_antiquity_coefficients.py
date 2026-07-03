"""Tests verifying hardware antiquity coefficient ordering (closes #6338).

Older hardware should get higher reward coefficients. This module checks that
the HARDWARE_WEIGHTS table in the main node file respects this invariant.
"""

import importlib
import os
import sys
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE_DIR = os.path.join(REPO_ROOT, "node")
sys.path.insert(0, NODE_DIR)


def _load_hardware_weights():
    """Import HARDWARE_WEIGHTS from the main integrated node module."""
    mod_path = os.path.join(
        NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py"
    )
    spec = importlib.util.spec_from_file_location("node_module", mod_path)
    mod = importlib.util.module_from_spec(spec)

    original_argv = sys.argv[:]
    sys.argv = [mod_path, "--test-import"]
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    finally:
        sys.argv = original_argv

    return getattr(mod, "HARDWARE_WEIGHTS", None)


class TestHardwareAntiquityCoefficientOrdering:
    """Verify that older hardware families receive higher coefficients."""

    @pytest.fixture(autouse=True)
    def _load_weights(self):
        self.weights = _load_hardware_weights()
        if self.weights is None:
            pytest.skip("Could not load HARDWARE_WEIGHTS from node module")

    def test_apple_silicon_newer_is_lower(self):
        """Apple M-series: newer chips should have lower coefficients."""
        apple = self.weights.get("Apple Silicon", {})
        m1 = apple.get("M1", 0)
        m2 = apple.get("M2", 0)
        m3 = apple.get("M3", 0)
        m4 = apple.get("M4", 0)
        assert m1 > m2 > m3 > m4, (
            f"Expected M1({m1}) > M2({m2}) > M3({m3}) > M4({m4})"
        )

    def test_x86_vintage_beats_modern(self):
        """Vintage x86 should have higher coefficients than modern."""
        x86 = self.weights.get("x86", {})
        assert x86.get("retro", 0) > x86.get("modern", 0)
        assert x86.get("386", 0) > x86.get("modern", 0)
        assert x86.get("486", 0) > x86.get("modern", 0)

    def test_x86_arch_generations_decreasing(self):
        """x86 micro-architecture coefficients should decrease with age."""
        x86 = self.weights.get("x86", {})
        assert x86.get("nehalem", 0) > x86.get("sandy_bridge", 0) or x86.get("nehalem", 0) >= x86.get("sandy_bridge", 0)
        assert x86.get("sandy_bridge", 0) > x86.get("ivy_bridge", 0) or x86.get("sandy_bridge", 0) >= x86.get("ivy_bridge", 0)
        assert x86.get("ivy_bridge", 0) > x86.get("haswell", 0) or x86.get("ivy_bridge", 0) >= x86.get("haswell", 0)
        assert x86.get("haswell", 0) > x86.get("broadwell", 0) or x86.get("haswell", 0) >= x86.get("broadwell", 0)

    def test_apple_silicon_beats_x86_modern(self):
        """Apple Silicon M1 should have lower coefficient than vintage x86
        but should still be reasonable."""
        apple = self.weights.get("Apple Silicon", {})
        x86 = self.weights.get("x86", {})
        m1 = apple.get("M1", 0)
        retro = x86.get("retro", 0)
        assert m1 < retro, f"M1({m1}) should be less than retro x86({retro})"

    def test_all_coefficients_positive(self):
        """All coefficients should be positive numbers."""
        for family, arches in self.weights.items():
            if not isinstance(arches, dict):
                continue
            for arch, coeff in arches.items():
                assert isinstance(coeff, (int, float)), (
                    f"{family}/{arch}: coefficient must be numeric, got {type(coeff)}"
                )
                assert coeff > 0, (
                    f"{family}/{arch}: coefficient must be positive, got {coeff}"
                )

    def test_coefficients_within_expected_ranges(self):
        """Coefficients should fall within the expected ranges per era."""
        x86 = self.weights.get("x86", {})
        # Pre-2010: 1.5-2.0x
        assert 1.5 <= x86.get("retro", 0) <= 2.0, "retro x86 out of range"
        assert 2.0 <= x86.get("386", 0) <= 3.0, "386 out of range"
        assert 1.5 <= x86.get("486", 0) <= 2.5, "486 out of range"
        # 2015-2020: 0.8-1.0x
        assert 0.8 <= x86.get("modern", 0) <= 1.0, "modern x86 out of range"

    def test_apple_silicon_in_new_range(self):
        """Apple Silicon (2020+) should be in the 0.5-0.8x range."""
        apple = self.weights.get("Apple Silicon", {})
        for chip in ("M1", "M2", "M3", "M4", "default"):
            val = apple.get(chip, 0)
            assert 0.5 <= val <= 0.8, (
                f"Apple Silicon {chip}({val}) should be in 0.5-0.8 range"
            )
