# SPDX-License-Identifier: MIT
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CITIES_JS = ROOT / "site" / "beacon" / "cities.js"
NODE_TEST = ROOT / "tests" / "beacon_city_skyline_layout.test.mjs"


class TestBeaconCitySkylines(unittest.TestCase):
    def test_city_renderer_uses_batched_procedural_meshes(self):
        source = CITIES_JS.read_text(encoding="utf-8")

        self.assertIn("generateSkylineLayout(city)", source)
        self.assertIn("new THREE.InstancedMesh", source)
        self.assertIn("city-skyline-facades-", source)
        self.assertIn("city-skyline-windows-", source)
        self.assertIn("city-skyline-spires-", source)
        self.assertIn("city-skyline-beacons-", source)

    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_city_layout_contract_with_node(self):
        completed = subprocess.run(
            ["node", "--test", str(NODE_TEST)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
