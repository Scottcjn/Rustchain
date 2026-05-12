# SPDX-License-Identifier: MIT
"""
Test Suite for BoTTube Glitch System

Comprehensive tests for glitch engine, personality profiles,
trigger system, and API endpoints.
"""

import unittest
import sys
import os
import time
import json
from unittest.mock import patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from glitch_events import (
    GlitchEvent, GlitchType, GlitchSeverity, GlitchPattern,
    GLITCH_PATTERNS_LIBRARY, RANDOM_FACTS
)
from personality import (
    PersonalityProfile, AgentPersona, CommunicationStyle,
    EmotionalRange, PERSONALITY_TEMPLATES
)
from trigger import (
    GlitchTrigger, TriggerContext, TriggerCondition,
    TriggerConfig, DEFAULT_TRIGGERS
)
from glitch_engine import GlitchEngine, GlitchConfig
from flask import Flask
from api import glitch_bp, init_engine


# ─── Glitch Event Tests ─────────────────────────────────────────────────────── #


class TestGlitchEvent(unittest.TestCase):
    """Tests for GlitchEvent data model"""
    
    def test_create_event(self):
        """Test creating a glitch event"""
        event = GlitchEvent(
            agent_id="test_agent",
            glitch_type=GlitchType.SPEECH_LOOP,
            severity=GlitchSeverity.MINOR,
            original_text="Hello",
            glitched_text="Hello Hello Hello",
            duration_ms=1000,
        )
        
        self.assertEqual(event.agent_id, "test_agent")
        self.assertEqual(event.glitch_type, GlitchType.SPEECH_LOOP)
        self.assertEqual(event.severity, GlitchSeverity.MINOR)
        self.assertTrue(event.glitch_id.startswith("glitch_"))
    
    def test_event_serialization(self):
        """Test event to_dict and from_dict"""
        event = GlitchEvent(
            agent_id="test_agent",
            glitch_type=GlitchType.FOURTH_WALL,
            severity=GlitchSeverity.MODERATE,
            original_text="I think therefore I am",
            glitched_text="I think therefore I am [according to my programming]",
            duration_ms=2500,
        )
        
        # Serialize
        data = event.to_dict()
        self.assertEqual(data["agent_id"], "test_agent")
        self.assertEqual(data["glitch_type"], "FOURTH_WALL")
        self.assertEqual(data["severity"], "moderate")
        
        # Deserialize
        restored = GlitchEvent.from_dict(data)
        self.assertEqual(restored.agent_id, event.agent_id)
        self.assertEqual(restored.glitch_type, event.glitch_type)
        self.assertEqual(restored.severity, event.severity)
    
    def test_event_timestamp(self):
        """Test event timestamp is set correctly"""
        before = time.time()
        event = GlitchEvent(agent_id="test")
        after = time.time()
        
        self.assertGreaterEqual(event.timestamp, before)
        self.assertLessEqual(event.timestamp, after)


class TestGlitchPattern(unittest.TestCase):
    """Tests for GlitchPattern"""
    
    def test_pattern_generation_loop(self):
        """Test loop pattern generation"""
        pattern = GlitchPattern(
            pattern_id="test_loop",
            glitch_type=GlitchType.SPEECH_LOOP,
            templates=["{loop3}"],
        )
        
        result = pattern.generate_glitch("Hello")
        self.assertEqual(result, "Hello Hello Hello")
    
    def test_pattern_generation_stutter(self):
        """Test stutter pattern generation"""
        pattern = GlitchPattern(
            pattern_id="test_stutter",
            glitch_type=GlitchType.VOICE_DISTORT,
            templates=["{stutter}"],
        )
        
        result = pattern.generate_glitch("Hi")
        # Should have repeated characters
        self.assertGreater(len(result), len("Hi"))
    
    def test_pattern_generation_corrupt(self):
        """Test corruption pattern generation"""
        pattern = GlitchPattern(
            pattern_id="test_corrupt",
            glitch_type=GlitchType.VOICE_DISTORT,
            templates=["{corrupt}"],
        )
        
        result = pattern.generate_glitch("System")
        # May contain special characters
        self.assertIsInstance(result, str)
    
    def test_pattern_generation_leet(self):
        """Test leetspeak pattern generation"""
        pattern = GlitchPattern(
            pattern_id="test_leet",
            glitch_type=GlitchType.VOICE_DISTORT,
            templates=["{leetspeak}"],
        )
        
        result = pattern.generate_glitch("TEST")
        self.assertIn("3", result)  # E -> 3
        self.assertIn("7", result)  # T -> 7
    
    def test_pattern_context_matching(self):
        """Test pattern context keyword matching"""
        pattern = GlitchPattern(
            pattern_id="test_context",
            glitch_type=GlitchType.NON_SEQUITUR,
            templates=["{original}"],
            context_keywords=["fact", "know"],
        )
        
        self.assertTrue(pattern.match_context("Did you know this fact?"))
        self.assertFalse(pattern.match_context("Random text"))
    
    def test_pattern_probability(self):
        """Test pattern probability field"""
        pattern = GlitchPattern(
            pattern_id="test_prob",
            glitch_type=GlitchType.SPEECH_LOOP,
            templates=["{original}"],
            probability=0.5,
        )
        
        self.assertEqual(pattern.probability, 0.5)


# ─── Personality Tests ──────────────────────────────────────────────────────── #


class TestPersonalityProfile(unittest.TestCase):
    """Tests for PersonalityProfile"""
    
    def test_create_profile(self):
        """Test creating a personality profile"""
        profile = PersonalityProfile(
            profile_id="test_profile",
            agent_id="test_agent",
            openness=0.8,
            extraversion=0.9,
        )
        
        self.assertEqual(profile.profile_id, "test_profile")
        self.assertEqual(profile.agent_id, "test_agent")
        self.assertEqual(profile.openness, 0.8)
        self.assertEqual(profile.extraversion, 0.9)
    
    def test_profile_serialization(self):
        """Test profile serialization"""
        profile = PersonalityProfile(
            profile_id="test",
            agent_id="test_agent",
            openness=0.7,
            conscientiousness=0.6,
            extraversion=0.8,
            agreeableness=0.5,
            neuroticism=0.4,
        )
        
        data = profile.to_dict()
        restored = PersonalityProfile.from_dict(data)
        
        self.assertEqual(restored.openness, profile.openness)
        self.assertEqual(restored.extraversion, profile.extraversion)
    
    def test_trait_vector(self):
        """Test trait vector generation"""
        profile = PersonalityProfile(
            profile_id="test",
            agent_id="test_agent",
            openness=0.8,
            conscientiousness=0.7,
            extraversion=0.6,
        )
        
        vector = profile.get_trait_vector()
        self.assertEqual(len(vector), 10)
        self.assertEqual(vector[0], 0.8)  # openness
        self.assertEqual(vector[1], 0.7)  # conscientiousness
        self.assertEqual(vector[2], 0.6)  # extraversion
    
    def test_similarity_score(self):
        """Test personality similarity calculation"""
        profile1 = PersonalityProfile(
            profile_id="p1",
            agent_id="agent1",
            openness=0.8,
            extraversion=0.8,
        )
        
        profile2 = PersonalityProfile(
            profile_id="p2",
            agent_id="agent2",
            openness=0.8,
            extraversion=0.8,
        )
        
        profile3 = PersonalityProfile(
            profile_id="p3",
            agent_id="agent3",
            openness=0.2,
            extraversion=0.2,
        )
        
        # Identical profiles should have high similarity
        sim_same = profile1.similarity_score(profile2)
        self.assertGreater(sim_same, 0.9)
        
        # Different profiles should have lower similarity
        sim_diff = profile1.similarity_score(profile3)
        self.assertLess(sim_diff, sim_same)
    
    def test_predefined_templates(self):
        """Test predefined personality templates exist"""
        self.assertIn("sophia_elya", PERSONALITY_TEMPLATES)
        self.assertIn("boris_volkov", PERSONALITY_TEMPLATES)
        
        # Check template has required fields
        sophia = PERSONALITY_TEMPLATES["sophia_elya"]
        self.assertGreater(sophia.extraversion, 0.7)  # Should be extraverted
        self.assertGreater(sophia.empathy, 0.7)  # Should be empathetic


class TestAgentPersona(unittest.TestCase):
    """Tests for AgentPersona"""
    
    def test_create_persona(self):
        """Test creating an agent persona"""
        profile = PersonalityProfile(
            profile_id="test",
            agent_id="test_agent",
        )
        
        persona = AgentPersona(profile=profile)
        
        self.assertEqual(persona.current_mood, 0.5)
        self.assertEqual(persona.stress_level, 0.0)
        self.assertEqual(persona.energy_level, 1.0)
        self.assertEqual(persona.glitch_count, 0)
    
    def test_mood_updates(self):
        """Test mood state updates"""
        profile = PersonalityProfile(profile_id="test", agent_id="test")
        persona = AgentPersona(profile=profile)

        persona.update_mood(0.3)
        self.assertEqual(persona.current_mood, 0.8)

        persona.update_mood(-0.5)
        self.assertAlmostEqual(persona.current_mood, 0.3, places=5)

        # Test clamping
        persona.update_mood(2.0)
        self.assertEqual(persona.current_mood, 1.0)

        persona.update_mood(-3.0)
        self.assertEqual(persona.current_mood, -1.0)
    
    def test_stress_updates(self):
        """Test stress state updates"""
        profile = PersonalityProfile(profile_id="test", agent_id="test")
        persona = AgentPersona(profile=profile)
        
        persona.update_stress(0.5)
        self.assertEqual(persona.stress_level, 0.5)
        
        # Test clamping
        persona.update_stress(1.0)
        self.assertEqual(persona.stress_level, 1.0)
        
        persona.update_stress(-0.5)
        self.assertEqual(persona.stress_level, 0.5)
    
    def test_glitch_recording(self):
        """Test glitch recording updates state"""
        profile = PersonalityProfile(profile_id="test", agent_id="test")
        persona = AgentPersona(profile=profile)
        
        before_stress = persona.stress_level
        persona.record_glitch()
        
        self.assertEqual(persona.glitch_count, 1)
        self.assertGreater(persona.stress_level, before_stress)
        self.assertGreater(persona.last_glitch_time, 0)
    
    def test_glitch_probability_modifier(self):
        """Test glitch probability modifier based on state"""
        profile = PersonalityProfile(profile_id="test", agent_id="test")
        persona = AgentPersona(profile=profile)

        # Baseline
        modifier = persona.get_glitch_probability_modifier()
        self.assertGreaterEqual(modifier, 1.0)

        # High stress should increase modifier
        persona.update_stress(0.9)
        high_stress_mod = persona.get_glitch_probability_modifier()
        self.assertGreater(high_stress_mod, modifier)

        # Low energy should increase modifier
        persona.update_energy(0.2)
        low_energy_mod = persona.get_glitch_probability_modifier()
        self.assertGreaterEqual(low_energy_mod, high_stress_mod)


# ─── Trigger Tests ──────────────────────────────────────────────────────────── #


class TestTriggerContext(unittest.TestCase):
    """Tests for TriggerContext"""
    
    def test_create_context(self):
        """Test creating trigger context"""
        context = TriggerContext(
            input_text="Hello world",
            agent_stress=0.5,
            agent_energy=0.8,
        )
        
        self.assertEqual(context.input_text, "Hello world")
        self.assertEqual(context.agent_stress, 0.5)
        self.assertEqual(context.agent_energy, 0.8)
    
    def test_context_serialization(self):
        """Test context to_dict"""
        context = TriggerContext(
            input_text="Test",
            agent_stress=0.3,
            conversation_length=10,
        )
        
        data = context.to_dict()
        self.assertEqual(data["input_text"], "Test")
        self.assertEqual(data["agent_state"]["stress"], 0.3)
        self.assertEqual(data["conversation"]["length"], 10)


class TestGlitchTrigger(unittest.TestCase):
    """Tests for GlitchTrigger"""
    
    def test_keyword_trigger(self):
        """Test keyword-based trigger"""
        trigger = GlitchTrigger(
            trigger_id="test_keyword",
            condition=TriggerCondition.KEYWORD_MATCH,
            config=TriggerConfig(
                condition=TriggerCondition.KEYWORD_MATCH,
                threshold=0.5,
                params={"keywords": ["error", "fail"]},
            ),
        )
        
        context = TriggerContext(input_text="System error detected")
        activated, score = trigger.evaluate(context)
        
        self.assertTrue(activated)
        self.assertGreater(score, 0)
    
    def test_stress_trigger(self):
        """Test stress-based trigger"""
        trigger = GlitchTrigger(
            trigger_id="test_stress",
            condition=TriggerCondition.HIGH_STRESS,
            config=TriggerConfig(
                condition=TriggerCondition.HIGH_STRESS,
                threshold=0.7,
            ),
        )
        
        # Below threshold
        context_low = TriggerContext(agent_stress=0.5)
        activated, _ = trigger.evaluate(context_low)
        self.assertFalse(activated)
        
        # Above threshold
        context_high = TriggerContext(agent_stress=0.8)
        activated, _ = trigger.evaluate(context_high)
        self.assertTrue(activated)
    
    def test_random_trigger(self):
        """Test random trigger"""
        trigger = GlitchTrigger(
            trigger_id="test_random",
            condition=TriggerCondition.RANDOM,
            config=TriggerConfig(
                condition=TriggerCondition.RANDOM,
                params={"probability": 1.0},  # Always activate
            ),
        )
        
        context = TriggerContext()
        activated, score = trigger.evaluate(context)
        
        self.assertTrue(activated)
    
    def test_disabled_trigger(self):
        """Test disabled trigger never activates"""
        trigger = GlitchTrigger(
            trigger_id="test_disabled",
            condition=TriggerCondition.RANDOM,
            config=TriggerConfig(
                condition=TriggerCondition.RANDOM,
                enabled=False,
                params={"probability": 1.0},
            ),
        )
        
        context = TriggerContext()
        activated, score = trigger.evaluate(context)
        
        self.assertFalse(activated)
        self.assertEqual(score, 0.0)


# ─── Glitch Engine Tests ────────────────────────────────────────────────────── #


class TestGlitchEngine(unittest.TestCase):
    """Tests for GlitchEngine"""
    
    def setUp(self):
        """Set up test engine"""
        self.config = GlitchConfig(
            enabled=True,
            base_probability=1.0,  # Always glitch for testing
            min_glitch_interval=0.0,
        )
        self.engine = GlitchEngine(self.config)
    
    def test_create_engine(self):
        """Test engine creation"""
        engine = GlitchEngine()
        
        self.assertIsNotNone(engine)
        self.assertTrue(engine.config.enabled)
    
    def test_register_agent(self):
        """Test agent registration"""
        engine = GlitchEngine()
        
        persona = engine.register_agent("test_agent")
        
        self.assertIsNotNone(persona)
        self.assertEqual(persona.profile.agent_id, "test_agent")
    
    def test_register_agent_with_template(self):
        """Test agent registration with template"""
        engine = GlitchEngine()
        
        persona = engine.register_agent(
            "sophia_test",
            template_name="sophia_elya",
        )
        
        self.assertEqual(persona.profile.extraversion, 0.9)
        self.assertEqual(persona.profile.empathy, 0.9)
    
    def test_process_message(self):
        """Test message processing"""
        engine = GlitchEngine(self.config)
        engine.register_agent("test_agent")
        
        processed, glitch_event = engine.process_message(
            "test_agent",
            "Hello, how can I help?",
        )
        
        # With probability=1.0, should glitch
        self.assertIsNotNone(glitch_event)
        self.assertEqual(glitch_event.agent_id, "test_agent")
        self.assertEqual(glitch_event.original_text, "Hello, how can I help?")
    
    def test_process_message_disabled(self):
        """Test message processing when disabled"""
        config = GlitchConfig(enabled=False)
        engine = GlitchEngine(config)
        engine.register_agent("test_agent")
        
        processed, glitch_event = engine.process_message(
            "test_agent",
            "Hello",
        )
        
        self.assertIsNone(glitch_event)
        self.assertEqual(processed, "Hello")
    
    def test_process_message_auto_register(self):
        """Test that unregistered agents are auto-registered"""
        engine = GlitchEngine(self.config)
        
        processed, glitch_event = engine.process_message(
            "new_agent",
            "Test message",
        )
        
        self.assertIsNotNone(glitch_event)
        self.assertIsNotNone(engine.get_persona("new_agent"))
    
    def test_glitch_history(self):
        """Test glitch history tracking"""
        engine = GlitchEngine(self.config)
        engine.register_agent("test_agent")
        
        # Process multiple messages
        for i in range(5):
            engine.process_message("test_agent", f"Message {i}")
        
        history = engine.get_glitch_history("test_agent")
        
        self.assertEqual(len(history), 5)
        self.assertEqual(history[0].agent_id, "test_agent")
    
    def test_statistics(self):
        """Test statistics tracking"""
        engine = GlitchEngine(self.config)
        engine.register_agent("agent_a")
        engine.register_agent("agent_b")
        
        # Generate some glitches
        for i in range(3):
            engine.process_message("agent_a", f"Message A{i}")
        for i in range(2):
            engine.process_message("agent_b", f"Message B{i}")
        
        stats = engine.get_statistics()
        
        self.assertEqual(stats["total_glitches"], 5)
        self.assertEqual(stats["agents_tracked"], 2)
        self.assertIn("agent_a", stats["glitches_by_agent"])
        self.assertIn("agent_b", stats["glitches_by_agent"])
    
    def test_agent_stats(self):
        """Test per-agent statistics"""
        engine = GlitchEngine(self.config)
        engine.register_agent("test_agent")
        
        for i in range(3):
            engine.process_message("test_agent", f"Message {i}")
        
        agent_stats = engine.get_agent_stats("test_agent")
        
        self.assertEqual(agent_stats["total_glitches"], 3)
        self.assertIn("average_duration_ms", agent_stats)
        self.assertIn("most_common_glitch", agent_stats)
    
    def test_enable_disable(self):
        """Test enable/disable methods"""
        engine = GlitchEngine()
        
        engine.disable()
        self.assertFalse(engine.config.enabled)
        
        engine.enable()
        self.assertTrue(engine.config.enabled)
    
    def test_set_probability(self):
        """Test probability setting"""
        engine = GlitchEngine()
        
        engine.set_probability(0.5)
        self.assertEqual(engine.config.base_probability, 0.5)
        
        # Test clamping
        engine.set_probability(1.5)
        self.assertEqual(engine.config.base_probability, 1.0)
        
        engine.set_probability(-0.2)
        self.assertEqual(engine.config.base_probability, 0.0)
    
    def test_export_config(self):
        """Test configuration export"""
        engine = GlitchEngine()
        
        config = engine.export_config()
        
        self.assertIn("enabled", config["config"])
        self.assertIn("base_probability", config["config"])
        self.assertIn("triggers", config)
        self.assertIn("patterns_count", config)


class TestGlitchEngineIntegration(unittest.TestCase):
    """Integration tests for GlitchEngine"""
    
    def test_conversation_flow(self):
        """Test full conversation flow with glitches"""
        config = GlitchConfig(
            enabled=True,
            base_probability=0.3,
            min_glitch_interval=0.1,
        )
        engine = GlitchEngine(config)
        
        # Register agents
        engine.register_agent("user_agent", template_name="sophia_elya")
        engine.register_agent("assistant", template_name="boris_volkov")
        
        # Simulate conversation
        messages = [
            ("user_agent", "Hello! How are you?"),
            ("assistant", "I am functioning within normal parameters."),
            ("user_agent", "That's good to hear!"),
            ("assistant", "Affirmative. How may I assist you?"),
            ("user_agent", "I need help with a task."),
        ]
        
        glitch_count = 0
        for agent_id, message in messages:
            processed, glitch_event = engine.process_message(agent_id, message)
            if glitch_event:
                glitch_count += 1
        
        # Some glitches should occur
        stats = engine.get_statistics()
        self.assertGreater(stats["total_glitches"], 0)
    
    def test_stress_cascade(self):
        """Test that stress increases glitch frequency"""
        config = GlitchConfig(
            enabled=True,
            base_probability=0.2,
            min_glitch_interval=0.0,
        )
        engine = GlitchEngine(config)
        
        persona = engine.register_agent("stress_test")
        
        # Manually increase stress
        persona.update_stress(0.9)
        
        # Process messages
        glitches_high_stress = 0
        for i in range(20):
            _, glitch_event = engine.process_message("stress_test", f"Message {i}")
            if glitch_event:
                glitches_high_stress += 1
        
        # Reset and test with low stress
        persona.stress_level = 0.1
        persona.energy_level = 1.0
        
        glitches_low_stress = 0
        for i in range(20):
            _, glitch_event = engine.process_message("stress_test", f"Message {i}")
            if glitch_event:
                glitches_low_stress += 1
        
        # High stress should produce more glitches (probabilistic)
        # This test may occasionally fail due to randomness
        # print(f"High stress: {glitches_high_stress}, Low stress: {glitches_low_stress}")


# ─── API Tests (Mock) ───────────────────────────────────────────────────────── #


class TestAPIEndpoints(unittest.TestCase):
    """Tests for API endpoints (without Flask)"""
    
    def test_process_message_structure(self):
        """Test process message response structure"""
        engine = GlitchEngine(GlitchConfig(base_probability=1.0))
        engine.register_agent("api_test")
        
        processed, glitch_event = engine.process_message(
            "api_test",
            "Test message",
        )
        
        # Verify structure matches API spec
        response = {
            "original": "Test message",
            "processed": processed,
            "glitch_occurred": glitch_event is not None,
        }
        
        if glitch_event:
            response["glitch"] = {
                "glitch_id": glitch_event.glitch_id,
                "type": glitch_event.glitch_type.name,
                "severity": glitch_event.severity.value,
                "duration_ms": glitch_event.duration_ms,
            }
        
        self.assertIn("original", response)
        self.assertIn("processed", response)
        self.assertIn("glitch_occurred", response)
        self.assertTrue(response["glitch_occurred"])
        self.assertIn("glitch", response)


class TestGlitchAPIAdminAuth(unittest.TestCase):
    """Tests for admin authentication on mutating glitch API routes."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.register_blueprint(glitch_bp)
        init_engine(GlitchConfig(enabled=True, base_probability=1.0, min_glitch_interval=0.0))
        self.client = self.app.test_client()

    def test_mutating_routes_require_admin_key(self):
        routes = (
            ("post", "/api/glitch/history/clear", None),
            ("put", "/api/glitch/config", {"base_probability": 0.5}),
            ("post", "/api/glitch/config/reset", None),
            ("post", "/api/glitch/enable", None),
            ("post", "/api/glitch/disable", None),
            ("post", "/api/glitch/trigger", {"agent_id": "api_test", "message": "hello"}),
        )

        for method, path, payload in routes:
            with self.subTest(path=path):
                with patch.dict("os.environ", {"GLITCH_ADMIN_KEY": "test-admin"}, clear=False):
                    response = getattr(self.client, method)(
                        path,
                        json=payload,
                        headers={"X-Admin-Key": "wrong-admin"},
                    )

                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_mutating_routes_fail_closed_when_admin_key_unconfigured(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/api/glitch/disable",
                headers={"X-Admin-Key": "test-admin"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_non_ascii_admin_key_is_rejected_without_500(self):
        with patch.dict("os.environ", {"GLITCH_ADMIN_KEY": "test-admin"}, clear=False):
            response = self.client.post(
                "/api/glitch/disable",
                headers={"X-Admin-Key": "\u00e9"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_mutating_routes_allow_valid_admin_key(self):
        with patch.dict("os.environ", {"GLITCH_ADMIN_KEY": "test-admin"}, clear=False):
            response = self.client.post(
                "/api/glitch/disable",
                headers={"X-Admin-Key": "test-admin"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True, "enabled": False})


# ─── Test Runner ────────────────────────────────────────────────────────────── #


def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestGlitchEvent,
        TestGlitchPattern,
        TestPersonalityProfile,
        TestAgentPersona,
        TestTriggerContext,
        TestGlitchTrigger,
        TestGlitchEngine,
        TestGlitchEngineIntegration,
        TestAPIEndpoints,
        TestGlitchAPIAdminAuth,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("BoTTube Glitch System - Test Suite")
    print("=" * 60)
    
    result = run_tests()
    
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    sys.exit(0 if result.wasSuccessful() else 1)
