# SPDX-License-Identifier: MIT

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CONNECTIONS = REPO_ROOT / "site" / "beacon" / "connections.js"


class BeaconContractAnimationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONNECTIONS.read_text(encoding="utf-8")

    def test_new_contract_lines_start_the_bounded_pulse(self):
        self.assertIn("startContractPulse(scene, contract.id", self.source)
        self.assertIn("contractPulseFrame(elapsed - pulse.startedAt", self.source)
        self.assertIn("if (frame.done) disposeContractPulse(i)", self.source)

    def test_pulse_uses_a_disposable_additive_glow(self):
        self.assertIn("blending: THREE.AdditiveBlending", self.source)
        self.assertIn("pulse.glow.geometry.dispose()", self.source)
        self.assertIn("pulse.glow.material.dispose()", self.source)

    def test_contract_removal_also_cleans_an_active_pulse(self):
        removal = self.source.split("export function removeContractLine", 1)[1]
        self.assertIn("contractPulses[i].contractId === contractId", removal)
        self.assertIn("disposeContractPulse(i)", removal)


if __name__ == "__main__":
    unittest.main()
