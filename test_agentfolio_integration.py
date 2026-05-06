import unittest
from integrations.agentfolio-beacon.reference_impl.trust_sync import TrustSyncEngine
from integrations.agentfolio-beacon.reference_impl.migration_handler import MigrationHandler

class TestTrustSync(unittest.TestCase):
    def setUp(self):
        self.engine = TrustSyncEngine()
        
    def test_dual_layer_calculation(self):
        rec = self.engine.sync_agent("af_1", "RTC_wallet_1", 0.8, 0.9)
        self.assertAlmostEqual(rec.dual_layer_score, 0.6*0.8 + 0.4*0.9, places=4)
        
    def test_batch_sync(self):
        agents = [
            {"agent_id": "af_2", "beacon_wallet": "w2", "on_chain": 0.5, "off_chain": 0.5},
            {"agent_id": "af_3", "beacon_wallet": "w3", "on_chain": 1.0, "off_chain": 0.0}
        ]
        res = self.engine.batch_sync(agents)
        self.assertEqual(len(res), 2)
        self.assertAlmostEqual(res[0].dual_layer_score, 0.5)
        self.assertAlmostEqual(res[1].dual_layer_score, 0.6)

class TestMigration(unittest.TestCase):
    def setUp(self):
        self.migrator = MigrationHandler()
        
    def test_success(self):
        res = self.migrator.execute_migration("legacy_key_1", "molt_1", "RTC_new")
        self.assertEqual(res["status"], "success")
        self.assertIn("Founding Migrant", res["badge"])
        
    def test_duplicate(self):
        self.migrator.execute_migration("legacy_key_1", "molt_1", "RTC_new")
        res = self.migrator.execute_migration("legacy_key_1", "molt_1", "RTC_new2")
        self.assertEqual(res["status"], "failed")

if __name__ == "__main__":
    unittest.main()
