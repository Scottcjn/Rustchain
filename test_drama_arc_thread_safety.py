"""Thread safety test for DramaArcEngine.start_arc"""
import threading
import time
import unittest
from unittest.mock import MagicMock
from drama_arc_engine import DramaArcEngine, DramaArcType

class TestThreadSafety(unittest.TestCase):
    def test_concurrent_start_arc(self):
        """Test that concurrent start_arc calls don't create duplicate arcs."""
        mock_rel_engine = MagicMock()
        mock_rel_engine.start_drama_arc.return_value = {
            "success": True,
            "relationship": {"agent_a": "alice", "agent_b": "bob"}
        }
        mock_rel_engine.get_relationship.return_value = {
            "agent_a": "alice",
            "agent_b": "bob",
            "arc_type": "friendly_rivalry",
            "state": "neutral"
        }
        
        engine = DramaArcEngine(mock_rel_engine)
        results = []
        
        def start_arc_thread():
            result = engine.start_arc("alice", "bob", DramaArcType.FRIENDLY_RIVALRY)
            results.append(result)
        
        # Start 5 threads simultaneously
        threads = [threading.Thread(target=start_arc_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Only one should succeed, others should fail with "already exists"
        successes = [r for r in results if r.get("success")]
        failures = [r for r in results if not r.get("success")]
        
        self.assertEqual(len(successes), 1, "Exactly one thread should succeed")
        self.assertEqual(len(failures), 4, "Four threads should fail with duplicate error")
        self.assertIn("already exists", failures[0].get("error", ""))
        print(f"✓ Thread safety test passed: {len(successes)} success, {len(failures)} rejected")

if __name__ == "__main__":
    unittest.main()
