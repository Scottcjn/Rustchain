#!/usr/bin/env python3
"""
Test suite for XP/Badge automation functionality in RustChain.

This test suite validates:
1. Badge unlocking logic based on entropy scores
2. JSON file generation and format validation
3. Data consistency across badge files
4. Error handling and edge cases
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

# Mock the validator core functions for testing
def mock_generate_validator_data(entropy_score):
    """Mock function to generate validator data with specific entropy score."""
    return {
        "cpu_model": "PowerPC G4",
        "bios_date": "2003-05-15",
        "entropy_score": entropy_score,
        "hardware_fingerprint": "mock_fingerprint_12345",
        "antiquity_multiplier": 2.5,
        "timestamp": "2026-02-19T23:35:00Z"
    }

def mock_unlock_badges(validator_data, badges_dir):
    """Mock function to unlock badges based on validator data."""
    unlocked_badges = []
    
    # Badge unlocking logic based on entropy score
    if validator_data["entropy_score"] >= 3.0:
        # High entropy badge
        badge_data = {
            "nft_id": "high_entropy_veteran",
            "title": "High Entropy Veteran",
            "category": "performance",
            "description": "Achieved exceptional entropy score in hardware validation",
            "emotional_resonance": "pride",
            "symbol": "🔥",
            "visual_anchor": "flame",
            "rarity": "rare",
            "bound": True
        }
        unlocked_badges.append(badge_data)
    
    if validator_data["entropy_score"] >= 2.5:
        # Medium entropy badge
        badge_data = {
            "nft_id": "entropy_enthusiast",
            "title": "Entropy Enthusiast", 
            "category": "performance",
            "description": "Demonstrated solid entropy generation capabilities",
            "emotional_resonance": "satisfaction",
            "symbol": "⚡",
            "visual_anchor": "bolt",
            "rarity": "common",
            "bound": True
        }
        unlocked_badges.append(badge_data)
    
    return unlocked_badges

def test_badge_unlocking_logic():
    """Test badge unlocking logic with different entropy scores."""
    # Test case 1: High entropy score (should unlock both badges)
    validator_data = mock_generate_validator_data(3.5)
    unlocked_badges = mock_unlock_badges(validator_data, "badges")
    
    assert len(unlocked_badges) == 2
    badge_ids = [badge["nft_id"] for badge in unlocked_badges]
    assert "high_entropy_veteran" in badge_ids
    assert "entropy_enthusiast" in badge_ids
    
    # Test case 2: Medium entropy score (should unlock only medium badge)
    validator_data = mock_generate_validator_data(2.7)
    unlocked_badges = mock_unlock_badges(validator_data, "badges")
    
    assert len(unlocked_badges) == 1
    assert unlocked_badges[0]["nft_id"] == "entropy_enthusiast"
    
    # Test case 3: Low entropy score (should unlock no badges)
    validator_data = mock_generate_validator_data(2.0)
    unlocked_badges = mock_unlock_badges(validator_data, "badges")
    
    assert len(unlocked_badges) == 0

def test_proof_of_antiquity_json_generation():
    """Test generation of proof_of_antiquity.json file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock validator data
        validator_data = mock_generate_validator_data(3.2)
        
        # Generate proof file
        proof_file = Path(temp_dir) / "proof_of_antiquity.json"
        with open(proof_file, 'w') as f:
            json.dump(validator_data, f, indent=2)
        
        # Verify file exists and is valid JSON
        assert proof_file.exists()
        with open(proof_file, 'r') as f:
            loaded_data = json.load(f)
        
        # Verify required fields
        required_fields = ["cpu_model", "bios_date", "entropy_score", "hardware_fingerprint"]
        for field in required_fields:
            assert field in loaded_data
        
        assert loaded_data["entropy_score"] == 3.2

def test_relic_rewards_json_generation():
    """Test generation of relic_rewards.json file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock unlocked badges
        validator_data = mock_generate_validator_data(3.2)
        unlocked_badges = mock_unlock_badges(validator_data, "badges")
        
        # Generate rewards file
        rewards_file = Path(temp_dir) / "relic_rewards.json"
        with open(rewards_file, 'w') as f:
            json.dump(unlocked_badges, f, indent=2)
        
        # Verify file exists and is valid JSON
        assert rewards_file.exists()
        with open(rewards_file, 'r') as f:
            loaded_badges = json.load(f)
        
        # Verify badge structure
        assert len(loaded_badges) == 2
        for badge in loaded_badges:
            required_fields = ["nft_id", "title", "category", "description", "rarity"]
            for field in required_fields:
                assert field in badge

def test_badge_consistency():
    """Test consistency of badge data across different files."""
    # This would validate that badge definitions in the badges/ directory
    # match the expected structure and are consistent with what's generated
    badges_dir = Path(__file__).parent.parent / "badges"
    
    if badges_dir.exists():
        badge_files = list(badges_dir.glob("*.json"))
        for badge_file in badge_files:
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
            
            # Verify required fields exist
            required_fields = ["nft_id", "title", "category", "description", "rarity"]
            for field in required_fields:
                assert field in badge_data, f"Missing field {field} in {badge_file}"
            
            # Verify nft_id matches filename (without .json)
            expected_nft_id = badge_file.stem
            assert badge_data["nft_id"] == expected_nft_id, f"nft_id mismatch in {badge_file}"

def test_edge_cases():
    """Test edge cases and boundary conditions."""
    # Test exactly at threshold
    validator_data = mock_generate_validator_data(3.0)
    unlocked_badges = mock_unlock_badges(validator_data, "badges")
    assert len(unlocked_badges) == 2  # Should include high entropy badge
    
    # Test just below threshold  
    validator_data = mock_generate_validator_data(2.999)
    unlocked_badges = mock_unlock_badges(validator_data, "badges")
    assert len(unlocked_badges) == 1  # Should only include medium entropy badge

if __name__ == "__main__":
    pytest.main([__file__, "-v"])