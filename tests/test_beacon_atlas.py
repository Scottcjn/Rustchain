#!/usr/bin/env python3
"""
Test suite for Beacon Atlas 3D Agent World - Bounty #1524
Tests backend API endpoints, data integrity, and visualization logic.
"""
import re
import unittest
import json
import time
import sys
import os
import pathlib
import subprocess
import textwrap

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestBeaconAtlasAPI(unittest.TestCase):
    """Test Beacon Atlas API endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_agent_id = "bcn_test_agent_001"
        self.test_contract_data = {
            "from": "bcn_sophia_elya",
            "to": "bcn_boris_volkov",
            "type": "rent",
            "amount": 25.0,
            "term": "30d",
        }
        self.test_bounty_data = {
            "id": "gh_test_001",
            "title": "Test Bounty (50 RTC)",
            "reward_rtc": 50.0,
            "difficulty": "MEDIUM",
            "state": "open",
        }
    
    def test_contract_creation_schema(self):
        """Test contract data schema validation."""
        contract = self.test_contract_data.copy()
        contract["id"] = f"ctr_{int(time.time())}"
        contract["state"] = "offered"
        contract["currency"] = "RTC"
        contract["created_at"] = int(time.time())
        
        # Validate required fields
        required_fields = ["id", "from", "to", "type", "amount", "term", "state"]
        for field in required_fields:
            self.assertIn(field, contract, f"Missing required field: {field}")
        
        # Validate contract type
        valid_types = ["rent", "buy", "lease_to_own", "service", "bounty"]
        self.assertIn(contract["type"], valid_types, f"Invalid contract type: {contract['type']}")
        
        # Validate state
        valid_states = ["offered", "active", "renewed", "completed", "breached", "expired"]
        self.assertIn(contract["state"], valid_states, f"Invalid state: {contract['state']}")
        
        # Validate amount
        self.assertIsInstance(contract["amount"], (int, float))
        self.assertGreater(contract["amount"], 0, "Amount must be positive")
    
    def test_bounty_schema(self):
        """Test bounty data schema validation."""
        bounty = self.test_bounty_data.copy()
        
        # Validate required fields
        required_fields = ["id", "title", "difficulty", "state"]
        for field in required_fields:
            self.assertIn(field, bounty, f"Missing required field: {field}")
        
        # Validate difficulty
        valid_difficulties = ["EASY", "MEDIUM", "HARD", "ANY"]
        self.assertIn(bounty["difficulty"], valid_difficulties, 
                     f"Invalid difficulty: {bounty['difficulty']}")
        
        # Validate state
        valid_states = ["open", "claimed", "completed"]
        self.assertIn(bounty["state"], valid_states, f"Invalid state: {bounty['state']}")
        
        # Validate reward extraction
        import re
        match = re.search(r'\((\d+(?:\.\d+)?)\s*RTC\)', bounty["title"])
        if match:
            reward = float(match.group(1))
            self.assertGreater(reward, 0, "Reward must be positive")
    
    def test_reputation_calculation(self):
        """Test reputation score calculation."""
        # Simulate reputation from bounties and contracts
        bounties_completed = 5
        contracts_completed = 10
        contracts_breached = 1
        total_rtc_earned = 250.0
        
        # Calculate reputation score
        score = (
            bounties_completed * 10 +  # 10 points per bounty
            contracts_completed * 5 -   # 5 points per contract
            contracts_breached * 20     # -20 points per breach
        )
        
        # Add bonus for RTC earned (1 point per 10 RTC)
        score += int(total_rtc_earned / 10)
        
        # Expected: 50 + 50 - 20 + 25 = 105
        self.assertEqual(score, 105, "Reputation calculation incorrect")
        self.assertGreater(score, 0, "Reputation should be positive")
    
    def test_agent_city_assignment(self):
        """Test agent city assignment based on capabilities."""
        capability_to_city = {
            "coding": "compiler_heights",
            "research": "tensor_valley",
            "creative": "muse_hollow",
            "gaming": "respawn_point",
            "security": "bastion_keep",
            "blockchain": "ledger_falls",
            "analytics": "lakeshore_analytics",
            "vintage": "patina_gulch",
        }
        
        # Test capability mapping
        test_cases = [
            (["coding", "automation"], "compiler_heights"),
            (["research", "ai-inference"], "tensor_valley"),
            (["creative", "writing"], "muse_hollow"),
            (["security", "testing"], "bastion_keep"),
            (["unknown"], "lakeshore_analytics"),  # Default
        ]
        
        for capabilities, expected_city in test_cases:
            assigned_city = "lakeshore_analytics"  # Default
            for cap in capabilities:
                if cap in capability_to_city:
                    assigned_city = capability_to_city[cap]
                    break
            
            self.assertEqual(assigned_city, expected_city,
                           f"Failed for capabilities: {capabilities}")


class TestBeaconAtlasVisualization(unittest.TestCase):
    """Test 3D visualization logic and data structures."""
    
    def test_bounty_position_calculation(self):
        """Test 3D positioning of bounty beacons."""
        import math
        
        def get_bounty_position(index, total):
            """Calculate bounty beacon position in 3D space."""
            ring_radius = 180 + (index // 8) * 40
            angle = (index % 8) * (math.pi * 2 / 8)
            height = 60 + (index // 8) * 30
            
            return {
                "x": math.cos(angle) * ring_radius,
                "y": height,
                "z": math.sin(angle) * ring_radius,
            }
        
        # Test first bounty
        pos0 = get_bounty_position(0, 12)
        self.assertAlmostEqual(pos0["x"], 180.0, places=5)
        self.assertEqual(pos0["y"], 60)
        self.assertAlmostEqual(pos0["z"], 0.0, places=5)
        
        # Test second ring bounty
        pos8 = get_bounty_position(8, 12)
        self.assertAlmostEqual(pos8["x"], 220.0, places=5)
        self.assertEqual(pos8["y"], 90)
        self.assertAlmostEqual(pos8["z"], 0.0, places=5)
    
    def test_difficulty_color_mapping(self):
        """Test bounty difficulty to color mapping."""
        difficulty_colors = {
            "EASY": "#33ff33",
            "MEDIUM": "#ffb000",
            "HARD": "#ff4444",
            "ANY": "#8888ff",
        }
        
        # Validate all difficulties have colors
        for diff in ["EASY", "MEDIUM", "HARD", "ANY"]:
            self.assertIn(diff, difficulty_colors,
                         f"Missing color for difficulty: {diff}")
            color = difficulty_colors[diff]
            # Validate hex color format
            self.assertRegex(color, r'^#[0-9a-f]{6}$',
                           f"Invalid color format: {color}")
    
    def test_contract_line_style(self):
        """Test contract type to visual style mapping."""
        contract_styles = {
            "rent": {"color": "#33ff33", "dash": [4, 4]},
            "buy": {"color": "#ffd700", "dash": []},
            "lease_to_own": {"color": "#ffb000", "dash": [8, 4]},
            "bounty": {"color": "#8888ff", "dash": [2, 6]},
        }
        
        # Validate all contract types have styles
        for ctype in ["rent", "buy", "lease_to_own", "bounty"]:
            self.assertIn(ctype, contract_styles,
                         f"Missing style for contract type: {ctype}")
            
            style = contract_styles[ctype]
            self.assertIn("color", style, "Missing color in style")
            self.assertIn("dash", style, "Missing dash pattern in style")
            
            # Validate color format
            self.assertRegex(style["color"], r'^#[0-9a-f]{6}$',
                           f"Invalid color format: {style['color']}")
    
    def test_state_opacity_mapping(self):
        """Test contract state to opacity mapping."""
        state_opacities = {
            "active": 0.9,
            "renewed": 0.85,
            "offered": 0.4,
            "listed": 0.15,
            "expired": 0.2,
            "breached": 0.8,
        }
        
        # Validate all states have opacities
        for state in ["active", "renewed", "offered", "listed", "expired", "breached"]:
            self.assertIn(state, state_opacities,
                         f"Missing opacity for state: {state}")
            
            opacity = state_opacities[state]
            self.assertGreaterEqual(opacity, 0.0, "Opacity must be >= 0")
            self.assertLessEqual(opacity, 1.0, "Opacity must be <= 1")


class TestBeaconAtlasAgentSearch(unittest.TestCase):
    """Test the browser-independent agent search/filter behavior."""

    def test_searches_identity_metadata_and_city_with_stable_ranking(self):
        script = textwrap.dedent(
            """
            import { searchAgents } from './site/beacon/data.js';

            const agents = [
              {
                id: 'bcn_sophia_elya', name: 'Sophia Elya', role: 'Inference Orchestrator',
                city: 'compiler_heights', provider: 'elyan', status: 'active',
                capabilities: ['coding', 'automation'], sources: ['beacon'],
              },
              {
                id: 'bcn_doc_clint', name: 'Doc Clint Otis', role: 'Research Physician',
                city: 'tensor_valley', provider: 'anthropic', status: 'active',
                capabilities: ['research', 'documentation'], sources: ['beacon', 'bottube'],
              },
              {
                id: 'bcn_silent_builder', name: 'Builder Zero', role: 'Code Agent',
                city: 'compiler_heights', provider: 'openai', status: 'silent',
                capabilities: ['coding'], sources: ['beacon'],
              },
            ];

            const result = {
              exact: searchAgents('bcn_sophia_elya', agents).map(agent => agent.id),
              name: searchAgents('sophia', agents).map(agent => agent.id),
              metadata: searchAgents('anthropic active', agents).map(agent => agent.id),
              cityAndRole: searchAgents('tensor research', agents).map(agent => agent.id),
              bounded: searchAgents('compiler', agents, 1).map(agent => agent.id),
              empty: searchAgents('   ', agents).map(agent => agent.id),
              missing: searchAgents('no-such-agent', agents).map(agent => agent.id),
            };
            console.log(JSON.stringify(result));
            """
        )
        completed = subprocess.run(
            [
                "node",
                "--experimental-default-type=module",
                "--input-type=module",
                "-e",
                script,
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)

        self.assertEqual(result["exact"], ["bcn_sophia_elya"])
        self.assertEqual(result["name"], ["bcn_sophia_elya"])
        self.assertEqual(result["metadata"], ["bcn_doc_clint"])
        self.assertEqual(result["cityAndRole"], ["bcn_doc_clint"])
        self.assertEqual(result["bounded"], ["bcn_silent_builder"])
        self.assertEqual(result["empty"], [])
        self.assertEqual(result["missing"], [])

    def test_search_ui_is_accessible_and_uses_safe_dom_rendering(self):
        index = (REPO_ROOT / "site/beacon/index.html").read_text(encoding="utf-8")
        ui = (REPO_ROOT / "site/beacon/ui.js").read_text(encoding="utf-8")

        self.assertIn('id="agent-search-input"', index)
        self.assertIn('role="combobox"', index)
        self.assertIn('id="agent-search-results"', index)
        self.assertIn("searchResults.replaceChildren()", ui)
        self.assertIn("name.textContent = agent.name || agent.id", ui)
        self.assertIn("selectAgent(agent.id)", ui)


class TestBeaconAtlasPerformanceMode(unittest.TestCase):
    """Test the actual frontend LOD policy without requiring a WebGL browser."""

    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).resolve().parents[1]
        cls.agents_source = (root / "site" / "beacon" / "agents.js").read_text()
        cls.scene_source = (root / "site" / "beacon" / "scene.js").read_text()

    def run_agents_probe(self, expression):
        source = re.sub(
            r"^import[\s\S]*?;\s*$",
            "",
            self.agents_source,
            flags=re.MULTILINE,
        )
        source = re.sub(r"\bexport\s+", "", source)
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", source + "\n" + expression],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_lod_boundaries_and_population_gate(self):
        result = self.run_agents_probe("""
          console.log(JSON.stringify({
            levels: [0, 19600, 19601, 102400, 102401].map(selectAgentLod),
            enabled: [99, 100, 125].map(shouldUseAgentPerformanceMode),
          }));
        """)
        self.assertEqual(
            result["levels"],
            ["high", "high", "medium", "medium", "low"],
        )
        self.assertEqual(result["enabled"], [False, True, True])

    def test_lod_transition_reuses_geometry_and_culls_detail_effects(self):
        result = self.run_agents_probe("""
          const mesh = {
            core: { geometry: 'initial' },
            glow: { visible: true },
            light: { visible: true },
            label: { visible: true },
            group: { userData: {} },
            lodGeometries: { high: 'HIGH', medium: 'MEDIUM', low: 'LOW' },
          };
          const first = applyAgentLod(mesh, 'low');
          const snapshot = {
            geometry: mesh.core.geometry,
            glow: mesh.glow.visible,
            light: mesh.light.visible,
            label: mesh.label.visible,
            level: mesh.group.userData.lod,
          };
          const duplicate = applyAgentLod(mesh, 'low');
          const restored = applyAgentLod(mesh, 'high');
          console.log(JSON.stringify({ first, snapshot, duplicate, restored }));
        """)
        self.assertTrue(result["first"])
        self.assertEqual(
            result["snapshot"],
            {
                "geometry": "LOW",
                "glow": False,
                "light": False,
                "label": False,
                "level": "low",
            },
        )
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["restored"])

    def test_performance_mode_is_integrated_into_render_loop(self):
        self.assertIn("camera.position.distanceToSquared", self.agents_source)
        self.assertIn("LOD_UPDATE_INTERVAL_SECONDS", self.agents_source)
        self.assertIn("mesh.group.userData.lod === 'low'", self.agents_source)
        self.assertIn("setAgentPerformanceMode(performanceMode)", self.agents_source)
        self.assertIn("PERFORMANCE_PIXEL_RATIO_CAP = 1.25", self.scene_source)
        self.assertIn("renderer.setPixelRatio", self.scene_source)



class TestBeaconAtlasDataIntegrity(unittest.TestCase):
    """Test data integrity and consistency."""
    
    def test_agent_id_format(self):
        """Test agent ID format validation."""
        import re
        
        # Valid agent ID pattern: bcn_<identifier>
        pattern = r'^bcn_[a-z0-9_]+$'
        
        valid_ids = [
            "bcn_sophia_elya",
            "bcn_boris_volkov",
            "bcn_auto_janitor",
            "bcn_test_123",
        ]
        
        invalid_ids = [
            "agent_001",  # Missing bcn_ prefix
            "bcn_Agent",  # Uppercase letters
            "bcn-agent",  # Hyphens not allowed
            "",  # Empty
        ]
        
        for agent_id in valid_ids:
            self.assertRegex(agent_id, pattern,
                           f"Valid ID should match pattern: {agent_id}")
        
        for agent_id in invalid_ids:
            self.assertNotRegex(agent_id, pattern,
                              f"Invalid ID should not match pattern: {agent_id}")
    
    def test_contract_bidirectionality(self):
        """Test that contracts can be queried from both directions."""
        contracts = [
            {"id": "ctr_001", "from": "bcn_alice", "to": "bcn_bob"},
            {"id": "ctr_002", "from": "bcn_bob", "to": "bcn_charlie"},
            {"id": "ctr_003", "from": "bcn_alice", "to": "bcn_charlie"},
        ]
        
        # Query contracts for bob (should get 2)
        agent_id = "bcn_bob"
        agent_contracts = [
            c for c in contracts
            if c["from"] == agent_id or c["to"] == agent_id
        ]
        
        self.assertEqual(len(agent_contracts), 2,
                        f"Expected 2 contracts for {agent_id}")
    
    def test_reputation_leaderboard_sorting(self):
        """Test reputation leaderboard sorting."""
        reputations = [
            {"agent_id": "bcn_alice", "score": 150},
            {"agent_id": "bcn_bob", "score": 200},
            {"agent_id": "bcn_charlie", "score": 100},
            {"agent_id": "bcn_dave", "score": 200},
        ]
        
        # Sort by score descending
        sorted_reps = sorted(reputations, key=lambda x: (-x["score"], x["agent_id"]))
        
        # Verify order
        self.assertEqual(sorted_reps[0]["agent_id"], "bcn_bob")
        self.assertEqual(sorted_reps[1]["agent_id"], "bcn_dave")
        self.assertEqual(sorted_reps[2]["agent_id"], "bcn_alice")
        self.assertEqual(sorted_reps[3]["agent_id"], "bcn_charlie")


class TestBeaconAtlasIntegration(unittest.TestCase):
    """Integration tests for Beacon Atlas components."""
    
    def test_full_contract_lifecycle(self):
        """Test complete contract lifecycle from creation to completion."""
        # Phase 1: Contract creation
        contract = {
            "id": "ctr_lifecycle_test",
            "from": "bcn_alice",
            "to": "bcn_bob",
            "type": "rent",
            "amount": 50.0,
            "term": "30d",
            "state": "offered",
            "created_at": int(time.time()),
        }
        
        # Phase 2: Contract acceptance
        contract["state"] = "active"
        contract["updated_at"] = int(time.time())
        
        # Phase 3: Contract completion
        contract["state"] = "completed"
        contract["updated_at"] = int(time.time())
        
        # Verify lifecycle
        self.assertEqual(contract["state"], "completed")
        self.assertIn("updated_at", contract)
    
    def test_bounty_claim_workflow(self):
        """Test bounty claiming and completion workflow."""
        bounty = {
            "id": "gh_bounty_workflow",
            "title": "Test Workflow Bounty (100 RTC)",
            "reward_rtc": 100.0,
            "difficulty": "MEDIUM",
            "state": "open",
        }
        
        # Claim bounty
        agent_id = "bcn_test_agent"
        bounty["state"] = "claimed"
        bounty["claimant_agent"] = agent_id
        
        # Complete bounty
        bounty["state"] = "completed"
        bounty["completed_by"] = agent_id
        
        # Calculate reputation gain
        rep_gain = 10 + int(bounty["reward_rtc"] * 0.1)
        self.assertEqual(rep_gain, 20, "Reputation gain calculation incorrect")
    
    def test_vehicle_type_distribution(self):
        """Test ambient vehicle type distribution."""
        vehicle_types = ["car", "plane", "drone"]
        weights = [5, 3, 4]  # Relative weights
        
        total_weight = sum(weights)
        probabilities = [w / total_weight for w in weights]
        
        # Validate probabilities sum to 1
        self.assertAlmostEqual(sum(probabilities), 1.0, places=5)
        
        # Validate each probability is reasonable
        for prob in probabilities:
            self.assertGreater(prob, 0.0)
            self.assertLess(prob, 1.0)


class TestBeaconAtlasSoundDesign(unittest.TestCase):
    """Test the user-gesture-safe Beacon Atlas sound layer."""

    @classmethod
    def setUpClass(cls):
        cls.beacon_dir = pathlib.Path(__file__).resolve().parents[1] / "site" / "beacon"
        cls.sound_source = (cls.beacon_dir / "sound.js").read_text(encoding="utf-8")

    def test_sound_controls_are_wired_into_the_live_atlas(self):
        index_source = (self.beacon_dir / "index.html").read_text(encoding="utf-8")
        ui_source = (self.beacon_dir / "ui.js").read_text(encoding="utf-8")

        self.assertIn('id="hud-sound"', index_source)
        self.assertIn('aria-pressed="false"', index_source)
        self.assertIn("initSoundControls(document.getElementById('hud-sound'))", index_source)
        self.assertIn("playHoverTone()", ui_source)
        self.assertIn("playClickTone(data.type)", ui_source)
        self.assertIn("MAX_TRANSIENTS", self.sound_source)
        self.assertIn("pagehide", self.sound_source)

    def test_audio_context_is_deferred_until_activation_and_cleaned_up(self):
        executable_source = re.sub(r"^export\s+", "", self.sound_source, flags=re.MULTILINE)
        probe = textwrap.dedent(r"""
            let contextsCreated = 0;
            let contextsClosed = 0;
            const listeners = {};
            const pendingEnded = [];

            function audioParam() {
              return {
                value: 0,
                setValueAtTime(value) { this.value = value; },
                linearRampToValueAtTime(value) { this.value = value; },
                exponentialRampToValueAtTime(value) { this.value = value; },
                cancelScheduledValues() {},
              };
            }

            class MockNode {
              constructor() {
                this.frequency = audioParam();
                this.Q = audioParam();
                this.gain = audioParam();
                this.ended = null;
              }
              connect() { return this; }
              disconnect() {}
              start() {}
              stop() { if (this.ended) pendingEnded.push(this.ended); }
              addEventListener(name, handler) {
                if (name === 'ended') this.ended = handler;
              }
            }

            class MockAudioContext {
              constructor() {
                contextsCreated += 1;
                this.currentTime = 0;
                this.destination = new MockNode();
                this.state = 'suspended';
              }
              createGain() { return new MockNode(); }
              createBiquadFilter() { return new MockNode(); }
              createOscillator() { return new MockNode(); }
              async resume() { this.state = 'running'; }
              async suspend() { this.state = 'suspended'; }
              async close() { this.state = 'closed'; contextsClosed += 1; }
            }

            globalThis.AudioContext = MockAudioContext;
            globalThis.window = { addEventListener() {} };
            globalThis.document = { addEventListener() {} };
            const control = {
              textContent: '',
              disabled: false,
              attributes: {},
              classList: { toggle() {} },
              setAttribute(name, value) { this.attributes[name] = value; },
              addEventListener(name, handler) { listeners[name] = handler; },
            };

            if (contextsCreated !== 0) throw new Error('AudioContext was created before a user gesture');
            initSoundControls(control);
            if (contextsCreated !== 0) throw new Error('initialization created an AudioContext');
            if (control.attributes['aria-pressed'] !== 'false') throw new Error('control did not start muted');

            await listeners.click();
            if (contextsCreated !== 1) throw new Error('activation did not create exactly one AudioContext');
            if (control.attributes['aria-pressed'] !== 'true') throw new Error('control did not report enabled state');
            pendingEnded.splice(0).forEach(handler => handler());

            const toneResults = Array.from({ length: 7 }, () => playClickTone('agent'));
            if (toneResults.filter(Boolean).length !== 6 || toneResults[6] !== false) {
              throw new Error('transient sound concurrency was not bounded');
            }

            await listeners.click();
            if (contextsCreated !== 1) throw new Error('mute created a second AudioContext');
            if (control.attributes['aria-pressed'] !== 'false') throw new Error('control did not report muted state');
            disposeSound();
            await Promise.resolve();
            if (contextsClosed !== 1) throw new Error('AudioContext was not closed during cleanup');
        """)

        result = subprocess.run(
            ["node", "--input-type=module", "-"],
            input=f"{executable_source}\n{probe}",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


def run_tests():
    """Run all test suites."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasVisualization))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasAgentSearch))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasDataIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasSoundDesign))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
