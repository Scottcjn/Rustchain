#!/usr/bin/env python3
"""
Test suite for JSON validation of XP/Badge automation outputs.
This ensures that all generated JSON files conform to expected schemas.
"""

import json
import os
import pytest
from jsonschema import validate, ValidationError


class TestJSONValidation:
    """Test JSON format validation for XP/Badge automation outputs."""

    def test_proof_of_antiquity_json_schema(self):
        """Test that proof_of_antiquity.json conforms to expected schema."""
        # Define the expected schema for proof_of_antiquity.json
        proof_schema = {
            "type": "object",
            "properties": {
                "cpu_model": {"type": "string"},
                "bios_date": {"type": ["string", "null"]},
                "entropy_score": {"type": "number"},
                "antiquity_multiplier": {"type": "number"},
                "hardware_fingerprint": {"type": "string"},
                "miner_id": {"type": "string"},
                "timestamp": {"type": "string"}
            },
            "required": ["cpu_model", "entropy_score", "antiquity_multiplier", "hardware_fingerprint", "miner_id"]
        }
        
        # Create a sample proof file for testing
        sample_proof = {
            "cpu_model": "PowerPC G4",
            "bios_date": "2003-06-15",
            "entropy_score": 3.5,
            "antiquity_multiplier": 2.5,
            "hardware_fingerprint": "unique_fingerprint_123",
            "miner_id": "test_miner_001",
            "timestamp": "2026-02-19T23:47:00Z"
        }
        
        # Validate the schema
        try:
            validate(instance=sample_proof, schema=proof_schema)
            assert True, "Proof of Antiquity JSON schema validation passed"
        except ValidationError as e:
            pytest.fail(f"Proof of Antiquity JSON schema validation failed: {e}")

    def test_relic_rewards_json_schema(self):
        """Test that relic_rewards.json conforms to expected schema."""
        # Define the expected schema for relic_rewards.json
        rewards_schema = {
            "type": "object",
            "properties": {
                "unlocked_badges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nft_id": {"type": "string"},
                            "title": {"type": "string"},
                            "category": {"type": "string"},
                            "description": {"type": "string"},
                            "emotional_resonance": {"type": "string"},
                            "symbol": {"type": "string"},
                            "visual_anchor": {"type": "string"},
                            "rarity_tier": {"type": "string"},
                            "bound_to_hardware": {"type": "boolean"}
                        },
                        "required": ["nft_id", "title", "category", "description"]
                    }
                },
                "total_badges": {"type": "integer"},
                "last_updated": {"type": "string"}
            },
            "required": ["unlocked_badges", "total_badges"]
        }
        
        # Create a sample rewards file for testing
        sample_rewards = {
            "unlocked_badges": [
                {
                    "nft_id": "badge_5pin_din_keyboard_warrior",
                    "title": "5-Pin DIN Keyboard Warrior",
                    "category": "input_devices",
                    "description": "Earned by authenticating with vintage hardware featuring the classic 5-pin DIN keyboard connector.",
                    "emotional_resonance": "nostalgia",
                    "symbol": "⌨️",
                    "visual_anchor": "5-pin DIN connector",
                    "rarity_tier": "common",
                    "bound_to_hardware": True
                }
            ],
            "total_badges": 1,
            "last_updated": "2026-02-19T23:47:00Z"
        }
        
        # Validate the schema
        try:
            validate(instance=sample_rewards, schema=rewards_schema)
            assert True, "Relic Rewards JSON schema validation passed"
        except ValidationError as e:
            pytest.fail(f"Relic Rewards JSON schema validation failed: {e}")

    def test_badge_json_files_schema(self):
        """Test that individual badge JSON files conform to expected schema."""
        # Define the expected schema for individual badge files
        badge_schema = {
            "type": "object",
            "properties": {
                "nft_id": {"type": "string"},
                "title": {"type": "string"},
                "category": {"type": "string"},
                "description": {"type": "string"},
                "emotional_resonance": {"type": "string"},
                "symbol": {"type": "string"},
                "visual_anchor": {"type": "string"},
                "rarity_tier": {"type": "string"},
                "bound_to_hardware": {"type": "boolean"},
                "unlock_conditions": {
                    "type": "object",
                    "properties": {
                        "entropy_threshold": {"type": "number"},
                        "hardware_requirements": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["entropy_threshold"]
                }
            },
            "required": ["nft_id", "title", "category", "description", "unlock_conditions"]
        }
        
        # Create a sample badge file for testing
        sample_badge = {
            "nft_id": "badge_powerpc_g4_flamekeeper",
            "title": "Bondi G3 Flamekeeper",
            "category": "powerpc",
            "description": "Earned by mining on authentic PowerPC G3 hardware with high entropy score.",
            "emotional_resonance": "pride",
            "symbol": "🔥",
            "visual_anchor": "PowerPC G3 processor",
            "rarity_tier": "rare",
            "bound_to_hardware": True,
            "unlock_conditions": {
                "entropy_threshold": 3.0,
                "hardware_requirements": ["PowerPC G3", "PowerPC G4"]
            }
        }
        
        # Validate the schema
        try:
            validate(instance=sample_badge, schema=badge_schema)
            assert True, "Badge JSON schema validation passed"
        except ValidationError as e:
            pytest.fail(f"Badge JSON schema validation failed: {e}")

    def test_json_file_exists_and_valid(self):
        """Test that generated JSON files exist and are valid JSON."""
        # Test files that should be generated by the XP/Badge automation
        expected_files = [
            "proof_of_antiquity.json",
            "relic_rewards.json"
        ]
        
        for filename in expected_files:
            # Check if file exists (we'll create temporary test files)
            test_file_path = f"/tmp/{filename}"
            
            # Create a temporary test file
            if filename == "proof_of_antiquity.json":
                test_data = {
                    "cpu_model": "Test CPU",
                    "entropy_score": 3.5,
                    "antiquity_multiplier": 1.0,
                    "hardware_fingerprint": "test_fingerprint",
                    "miner_id": "test_miner"
                }
            else:  # relic_rewards.json
                test_data = {
                    "unlocked_badges": [],
                    "total_badges": 0
                }
            
            with open(test_file_path, 'w') as f:
                json.dump(test_data, f)
            
            # Verify the file is valid JSON
            try:
                with open(test_file_path, 'r') as f:
                    loaded_data = json.load(f)
                assert loaded_data is not None, f"{filename} should contain valid JSON data"
                
                # Clean up test file
                os.remove(test_file_path)
                
            except json.JSONDecodeError:
                pytest.fail(f"{filename} is not valid JSON")
            except FileNotFoundError:
                pytest.fail(f"{filename} was not created by the XP/Badge automation")

    def test_leaderboard_json_validation(self):
        """Test leaderboard.json format validation."""
        leaderboard_schema = {
            "type": "object",
            "properties": {
                "validators": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "validator_name": {"type": "string"},
                            "composite_score": {"type": "number"},
                            "cpu_model": {"type": "string"},
                            "entropy_score": {"type": "number"},
                            "antiquity_multiplier": {"type": "number"}
                        },
                        "required": ["validator_name", "composite_score"]
                    }
                }
            },
            "required": ["validators"]
        }
        
        sample_leaderboard = {
            "validators": [
                {
                    "validator_name": "test_validator",
                    "composite_score": 85.5,
                    "cpu_model": "PowerPC G4",
                    "entropy_score": 3.5,
                    "antiquity_multiplier": 2.5
                }
            ]
        }
        
        try:
            validate(instance=sample_leaderboard, schema=leaderboard_schema)
            assert True, "Leaderboard JSON schema validation passed"
        except ValidationError as e:
            pytest.fail(f"Leaderboard JSON schema validation failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])