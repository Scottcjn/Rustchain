# SPDX-License-Identifier: MIT
"""Regression: the RIP-309 rotating measurement gate at epoch settlement must
FAIL CLOSED.

`finalize_epoch()` used to evaluate

    active_passed = all(checks_map.get(chk, True) for chk in active_checks)

which reads a measurement that was never submitted as a PASS. A miner therefore
kept its epoch weight by simply omitting the rotating checks it would have
failed -- defeating the per-epoch rotation, whose entire purpose is that the
measured subset is unpredictable. The enrollment path had already been hardened
against exactly this (`_fingerprint_check_passed`: "A missing / non-True
'passed' now fails", "'nothing' is not 'passed everything'"), but the fix was
never propagated to settlement.

These tests pin the settlement gate to the same fail-closed rule, while keeping
the structurally-unmeasurable exemption so legitimate capability-limited device
classes (micro, console-bridge) are not collateral damage.

Loader note: everything under test here is a pure predicate. Rather than exec
the whole node module -- which spins up a Flask app, touches a SQLite file and
registers Prometheus metrics into a process-global registry, and therefore
collides with sibling tests that exec it too -- the handful of pure definitions
this file needs are lifted straight out of the source with `ast`. That keeps
this test hermetic and order-independent (see also the sibling tests that
already collide with each other for exactly that reason).
"""

import ast
import unittest
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

_DEFS = (
    "RIP309_ROTATING_FINGERPRINT_CHECKS",
    "MICRO_LIMITED_ARCHES",
    "CONSOLE_BRIDGE_ARCHES",
    "_fingerprint_checks_map",
    "_structurally_unmeasurable_checks",
    "_fingerprint_check_passed",
    "_rip309_settlement_active_passed",
)


def _load_pure_defs():
    """Exec only the listed top-level definitions, in source order."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    wanted = set(_DEFS)
    nodes = []
    for node in tree.body:
        name = None
        if isinstance(node, ast.FunctionDef):
            name = node.name
        elif isinstance(node, ast.Assign):
            name = next(
                (t.id for t in node.targets if isinstance(t, ast.Name)), None
            )
        if name in wanted:
            nodes.append(node)

    missing = wanted - {
        n.name if isinstance(n, ast.FunctionDef)
        else next(t.id for t in n.targets if isinstance(t, ast.Name))
        for n in nodes
    }
    if missing:  # fail loudly rather than silently skip the regression
        raise AssertionError(f"definitions not found in node source: {sorted(missing)}")

    ns = {"__name__": "rip309_settlement_pure"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(MODULE_PATH), "exec"), ns)
    return ns


NODE = _load_pure_defs()

# finalize_epoch()'s own rotating check list (the names the settlement gate uses).
ACTIVE = ["anti_emulation", "cache_timing", "clock_drift", "simd_identity"]

# Arches with no structural exemption: every active check must be evidenced.
ORDINARY_ARCHES = ["", "x86", "modern", "ppc", "arm2"]


def _gate(checks_map, arch="x86", active=ACTIVE):
    return NODE["_rip309_settlement_active_passed"](checks_map, arch, active)


class Rip309SettlementGate(unittest.TestCase):
    """_rip309_settlement_active_passed must not treat absence as success."""

    # ---- baseline: honest submissions must be unaffected -------------------

    def test_all_active_checks_explicitly_true_passes(self):
        self.assertTrue(
            _gate({c: True for c in ACTIVE}),
            "a miner that passes every active check must keep its weight",
        )

    def test_one_active_check_false_fails(self):
        checks = {c: True for c in ACTIVE}
        checks["anti_emulation"] = False
        self.assertFalse(
            _gate(checks),
            "an explicitly failed active check must zero the weight",
        )

    # ---- the regression: omission is not success ---------------------------

    def test_omitted_active_checks_fail(self):
        """THE BUG. A miner omits the two checks it would fail and keeps only
        the two it can pass. Under the old `.get(chk, True)` form this returned
        True (weight kept); it must now fail."""
        self.assertFalse(
            _gate({"clock_drift": True, "cache_timing": True}),
            "omitting a rotating check must not be read as passing it",
        )

    def test_omission_fails_on_every_ordinary_arch(self):
        for arch in ORDINARY_ARCHES:
            with self.subTest(arch=arch):
                self.assertFalse(
                    _gate({"clock_drift": True}, arch=arch),
                    f"omission must fail on arch {arch!r}",
                )

    def test_empty_checks_map_fails(self):
        self.assertFalse(
            _gate({}),
            "an empty measurement map must fail, not pass",
        )

    def test_null_stored_column_fails(self):
        """Pre-migration rows hold NULL for fingerprint_checks_json."""
        self.assertFalse(
            _gate(None),
            "a NULL stored measurement map must fail, not pass",
        )

    def test_truthy_string_is_not_a_pass(self):
        """'false' is truthy in Python; the enrollment helper already rejects
        it via `is True`, and settlement must agree."""
        self.assertFalse(
            _gate({c: "false" for c in ACTIVE}),
            "a non-boolean truthy value must not be read as a pass",
        )

    def test_empty_dict_entry_is_not_a_pass(self):
        """{name: {}} is the exact forgery the enrollment comment calls out."""
        self.assertFalse(
            _gate({c: {} for c in ACTIVE}),
            "an empty per-check dict must not be read as a pass",
        )

    # ---- no collateral damage: unmeasurable checks stay neutral ------------

    def test_micro_arch_all_unmeasurable_keeps_weight(self):
        """A capability-limited class that cannot perform any rotating check
        must not be zeroed by this gate; enrollment already governs it via
        `_micro_accepted_for_rotation`."""
        micro_arch = next(iter(NODE["MICRO_LIMITED_ARCHES"]))
        self.assertTrue(
            _gate({}, arch=micro_arch),
            "checks a micro arch structurally cannot perform must stay neutral",
        )

    def test_console_bridge_still_needs_anti_emulation(self):
        """Console-bridge arches are exempt from all rotating checks EXCEPT
        anti_emulation (the bridge does measure it), so omitting it must fail."""
        console_arch = next(iter(NODE["CONSOLE_BRIDGE_ARCHES"]))
        self.assertFalse(
            _gate({}, arch=console_arch),
            "anti_emulation is measurable on console-bridge arches and must be evidenced",
        )
        self.assertTrue(
            _gate({"anti_emulation": True}, arch=console_arch),
            "a console-bridge arch evidencing anti_emulation must keep its weight",
        )

    # ---- the simd_bias / simd_identity aliasing hazards --------------------

    def test_simd_bias_alias_counts_as_simd_identity(self):
        """`simd_bias` and `simd_identity` are one measurement. The stored map
        carries whichever name the client sent, while the settlement check list
        uses `simd_identity`; a canonical `simd_bias` submission must not be
        scored as a missing result."""
        checks = {
            "clock_drift": True,
            "cache_timing": True,
            "thermal_drift": True,
            "instruction_jitter": True,
            "anti_emulation": True,
            "simd_bias": True,
        }
        self.assertTrue(
            _gate(checks),
            "a canonical simd_bias submission must satisfy the simd_identity check",
        )

    def test_unmeasurable_exemption_covers_both_simd_spellings(self):
        """The canonical tuple spells the measurement `simd_bias`, the
        settlement check list spells it `simd_identity`. The exemption has to
        span both, or a capability-limited device could never be excused."""
        console_arch = next(iter(NODE["CONSOLE_BRIDGE_ARCHES"]))
        unmeasurable = NODE["_structurally_unmeasurable_checks"](
            console_arch, {"checks": {}}
        )
        self.assertIn("simd_bias", unmeasurable)
        self.assertNotIn("simd_identity", unmeasurable)
        # ...and yet the gate must still excuse it, via the alias expansion:
        self.assertTrue(
            _gate({"anti_emulation": True}, arch=console_arch),
            "the unmeasurable exemption must reach simd_identity through the alias",
        )

    # ---- consistency with the enrollment helper that motivated the fix -----

    def test_settlement_agrees_with_enrollment_semantics(self):
        """Settlement and enrollment must not disagree about a missing result."""
        samples = [
            {},
            {"clock_drift": True},
            {"clock_drift": True, "cache_timing": True},
            {c: True for c in ACTIVE},
            {c: False for c in ACTIVE},
            {c: "false" for c in ACTIVE},
            {c: {} for c in ACTIVE},
        ]
        for checks in samples:
            with self.subTest(checks=checks):
                settlement = _gate(checks)
                enrollment = all(
                    NODE["_fingerprint_check_passed"](checks.get(c)) for c in ACTIVE
                )
                self.assertEqual(
                    settlement,
                    enrollment,
                    "settlement and enrollment disagree about missing results",
                )


if __name__ == "__main__":
    unittest.main()
