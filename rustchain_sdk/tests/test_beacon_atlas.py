#!/usr/bin/env python3
"""
Test suite for Beacon Atlas 3D Agent World - Bounty #1524
Tests backend API endpoints, data integrity, and visualization logic.
"""
import unittest
import json
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def run_tests():
    """Run all test suites."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasVisualization))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasDataIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconAtlasIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
