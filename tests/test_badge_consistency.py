#!/usr/bin/env python3
"""
Test suite for badge data consistency in RustChain XP/Badge automation system.

This test ensures that badge data is consistent across all files:
- badge_*.json files in badges/ directory
- relic_rewards.json 
- proof_of_antiquity.json
- leaderboard.json

Tests include:
- Badge ID uniqueness and consistency
- Required fields presence
- Data type validation
- Cross-file reference integrity
"""

import os
import json
import pytest
from pathlib import Path


class TestBadgeConsistency:
    """Test badge data consistency across all RustChain files."""
    
    def setup_method(self):
        """Set up test environment."""
        self.rustchain_root = Path(__file__).parent.parent
        self.badges_dir = self.rustchain_root / "badges"
        self.relic_rewards_file = self.rustchain_root / "relic_rewards.json"
        self.proof_file = self.rustchain_root / "proof_of_antiquity.json"
        self.leaderboard_file = self.rustchain_root / "leaderboard.json"
        
    def test_badge_files_exist(self):
        """Test that badge files exist in the badges directory."""
        assert self.badges_dir.exists(), "Badges directory should exist"
        badge_files = list(self.badges_dir.glob("badge_*.json"))
        assert len(badge_files) > 0, "Should have at least one badge file"
        
    def test_badge_id_uniqueness(self):
        """Test that all badge IDs are unique across all badge files."""
        badge_ids = set()
        duplicate_ids = []
        
        for badge_file in self.badges_dir.glob("badge_*.json"):
            try:
                with open(badge_file, 'r') as f:
                    badge_data = json.load(f)
                    badge_id = badge_data.get('nft_id')
                    if badge_id:
                        if badge_id in badge_ids:
                            duplicate_ids.append(badge_id)
                        else:
                            badge_ids.add(badge_id)
            except (json.JSONDecodeError, KeyError) as e:
                pytest.fail(f"Invalid badge file {badge_file}: {e}")
                
        assert len(duplicate_ids) == 0, f"Duplicate badge IDs found: {duplicate_ids}"
        
    def test_badge_required_fields(self):
        """Test that all badge files have required fields."""
        required_fields = ['nft_id', 'title', 'category', 'description', 
                          'emotional_resonance', 'symbol', 'visual_anchor', 
                          'rarity', 'bound']
        
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                
            for field in required_fields:
                assert field in badge_data, f"Badge {badge_file} missing required field: {field}"
                
    def test_relic_rewards_consistency(self):
        """Test that relic_rewards.json references valid badge IDs."""
        if not self.relic_rewards_file.exists():
            pytest.skip("relic_rewards.json not found")
            
        with open(self.relic_rewards_file, 'r') as f:
            relic_data = json.load(f)
            
        # Get all badge IDs from badge files
        badge_ids = set()
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                badge_ids.add(badge_data.get('nft_id'))
                
        # Check that all referenced badge IDs in relic_rewards exist
        if 'unlocked_badges' in relic_data:
            for badge_id in relic_data['unlocked_badges']:
                assert badge_id in badge_ids, f"Badge ID {badge_id} in relic_rewards.json not found in badge files"
                
    def test_proof_of_antiquity_badge_references(self):
        """Test that proof_of_antiquity.json badge references are valid."""
        if not self.proof_file.exists():
            pytest.skip("proof_of_antiquity.json not found")
            
        with open(self.proof_file, 'r') as f:
            proof_data = json.load(f)
            
        # Get all badge IDs from badge files
        badge_ids = set()
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                badge_ids.add(badge_data.get('nft_id'))
                
        # Check badge references in proof data
        if 'earned_badges' in proof_data:
            for badge_id in proof_data['earned_badges']:
                assert badge_id in badge_ids, f"Badge ID {badge_id} in proof_of_antiquity.json not found in badge files"
                
    def test_leaderboard_badge_consistency(self):
        """Test that leaderboard.json badge references are valid."""
        if not self.leaderboard_file.exists():
            pytest.skip("leaderboard.json not found")
            
        with open(self.leaderboard_file, 'r') as f:
            leaderboard_data = json.load(f)
            
        # Get all badge IDs from badge files
        badge_ids = set()
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                badge_ids.add(badge_data.get('nft_id'))
                
        # Check badge references in leaderboard
        if isinstance(leaderboard_data, list):
            for entry in leaderboard_data:
                if 'badges' in entry:
                    for badge_id in entry['badges']:
                        assert badge_id in badge_ids, f"Badge ID {badge_id} in leaderboard.json not found in badge files"
                        
    def test_badge_data_types(self):
        """Test that badge data has correct data types."""
        expected_types = {
            'nft_id': str,
            'title': str,
            'category': str,
            'description': str,
            'emotional_resonance': str,
            'symbol': str,
            'visual_anchor': str,
            'rarity': str,
            'bound': bool
        }
        
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                
            for field, expected_type in expected_types.items():
                assert field in badge_data, f"Badge {badge_file} missing field: {field}"
                assert isinstance(badge_data[field], expected_type), \
                    f"Badge {badge_file} field {field} has wrong type: expected {expected_type}, got {type(badge_data[field])}"
                    
    def test_badge_rarity_values(self):
        """Test that badge rarity values are valid."""
        valid_rarities = {'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic'}
        
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                
            rarity = badge_data.get('rarity')
            assert rarity in valid_rarities, f"Badge {badge_file} has invalid rarity: {rarity}"
            
    def test_cross_file_data_integrity(self):
        """Test overall data integrity across all files."""
        # This is a comprehensive test that combines multiple checks
        badge_ids = set()
        
        # Collect all badge IDs
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                badge_data = json.load(f)
                badge_id = badge_data.get('nft_id')
                assert badge_id is not None, f"Badge {badge_file} missing nft_id"
                badge_ids.add(badge_id)
                
        # Check relic_rewards.json
        if self.relic_rewards_file.exists():
            with open(self.relic_rewards_file, 'r') as f:
                relic_data = json.load(f)
            if 'unlocked_badges' in relic_data:
                for badge_id in relic_data['unlocked_badges']:
                    assert badge_id in badge_ids, f"Invalid badge ID in relic_rewards.json: {badge_id}"
                    
        # Check proof_of_antiquity.json
        if self.proof_file.exists():
            with open(self.proof_file, 'r') as f:
                proof_data = json.load(f)
            if 'earned_badges' in proof_data:
                for badge_id in proof_data['earned_badges']:
                    assert badge_id in badge_ids, f"Invalid badge ID in proof_of_antiquity.json: {badge_id}"
                    
        # Check leaderboard.json
        if self.leaderboard_file.exists():
            with open(self.leaderboard_file, 'r') as f:
                leaderboard_data = json.load(f)
            if isinstance(leaderboard_data, list):
                for entry in leaderboard_data:
                    if 'badges' in entry:
                        for badge_id in entry['badges']:
                            assert badge_id in badge_ids, f"Invalid badge ID in leaderboard.json: {badge_id}"
                            
    def test_badge_file_naming_convention(self):
        """Test that badge files follow the correct naming convention."""
        for badge_file in self.badges_dir.glob("*.json"):
            filename = badge_file.name
            assert filename.startswith('badge_'), f"Badge file {filename} should start with 'badge_'"
            assert filename.endswith('.json'), f"Badge file {filename} should end with '.json'"
            
    def test_no_duplicate_badge_files(self):
        """Test that there are no duplicate badge files with different names."""
        badge_contents = {}
        duplicate_files = []
        
        for badge_file in self.badges_dir.glob("badge_*.json"):
            with open(badge_file, 'r') as f:
                content = f.read()
                if content in badge_contents:
                    duplicate_files.append((badge_contents[content], badge_file.name))
                else:
                    badge_contents[content] = badge_file.name
                    
        assert len(duplicate_files) == 0, f"Duplicate badge files found: {duplicate_files}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])